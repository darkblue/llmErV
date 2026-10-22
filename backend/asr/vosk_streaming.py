"""True streaming CPU ASR. Shared read-only model, isolated recognizer per session."""

import asyncio
import json
import os
import threading
from pathlib import Path
from .base import ASRAdapter, ASRResult, ASRError

_MODEL = None
_MODEL_PATH = None
_MODEL_LOCK = threading.Lock()
_SLOTS = threading.BoundedSemaphore(max(1, int(os.getenv("ASR_MAX_SESSIONS", "1"))))


def model_path():
    return Path(os.getenv("ASR_MODEL") or "models/vosk-model-small-cn-0.22").resolve()


def load_model():
    global _MODEL, _MODEL_PATH
    path = model_path()
    if (
        not (path / "am/final.mdl").is_file()
        or not (path / "conf/model.conf").is_file()
    ):
        raise FileNotFoundError("ASR_MODEL_MISSING")
    with _MODEL_LOCK:
        if _MODEL is None or _MODEL_PATH != str(path):
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)
            _MODEL = Model(str(path))
            _MODEL_PATH = str(path)
    return _MODEL


class VoskStreaming(ASRAdapter):
    # Arbitrary vocabulary/grammar restriction is not native hotword boosting.
    native_hotwords = False

    async def start_session(self, hotwords):
        self.recognizer = None
        self.result = None
        self.closed = False
        self.has_slot = _SLOTS.acquire(blocking=False)
        if not self.has_slot:
            raise ASRError("ASR_BUSY")
        try:
            from vosk import KaldiRecognizer

            model = await asyncio.to_thread(load_model)
            self.recognizer = KaldiRecognizer(model, 16000)
            self.recognizer.SetWords(True)
            self.samples = 0
            self.segment_start = 0.0
        except ModuleNotFoundError as e:
            await self.end_session()
            raise ASRError("ASR_DEPENDENCY_MISSING") from e
        except FileNotFoundError as e:
            await self.end_session()
            raise ASRError("ASR_MODEL_MISSING") from e
        except Exception as e:
            await self.end_session()
            raise ASRError("ASR_MODEL_LOAD_FAILED") from e

    def _parse(self, value, final):
        data = json.loads(value)
        text = data.get("text" if final else "partial", "").strip()
        words = data.get("result") or []
        # Vosk returns Chinese tokens separated by spaces; remove only boundaries
        # between Chinese characters, preserving Latin callsigns and numbers.
        import re

        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        confidence = sum(w["conf"] for w in words) / len(words) if words else None
        end = self.samples / 16000
        value = ASRResult(
            text,
            final,
            words[0]["start"] if words else self.segment_start,
            words[-1]["end"] if words else end,
            confidence,
        )
        if final:
            self.segment_start = end
        return value

    async def send_audio_chunk(self, pcm):
        if self.closed:
            raise RuntimeError("ASR_SESSION_CLOSED")
        self.samples += len(pcm) // 2
        final = await asyncio.to_thread(self.recognizer.AcceptWaveform, pcm)
        value = self.recognizer.Result() if final else self.recognizer.PartialResult()
        self.result = self._parse(value, final)

    async def get_partial_result(self):
        value, self.result = self.result, None
        return value

    async def finalize_segment(self):
        if self.closed:
            return None
        data = await asyncio.to_thread(self.recognizer.FinalResult)
        self.result = None
        return self._parse(data, True)

    async def end_session(self):
        self.recognizer = None
        self.result = None
        self.closed = True
        if getattr(self, "has_slot", False):
            _SLOTS.release()
            self.has_slot = False
