"""Real-model integration check on self-authored synthetic Mandarin, never private recordings."""

import asyncio
import json
from pathlib import Path
import resource
import subprocess
import tempfile
import time
import wave

from backend.asr.vosk_streaming import VoskStreaming

PHRASE = "你好，这是语音识别测试。这里是指挥中心。"


async def check(path):
    adapter = VoskStreaming()
    await adapter.start_session([])
    texts, partials, finalized_at = [], [], []
    with wave.open(str(path), "rb") as wav:
        assert wav.getframerate() == 16000 and wav.getnchannels() == 1
        audio_seconds = wav.getnframes() / 16000
        frames = 0
        started = time.perf_counter()
        try:
            while data := wav.readframes(3200):
                frames += len(data) // 2
                await adapter.send_audio_chunk(data)
                result = await adapter.get_partial_result()
                if result and result.text:
                    if result.is_final:
                        texts.append(result.text)
                        finalized_at.append(frames / 16000)
                    else:
                        partials.append(result.text)
            result = await adapter.finalize_segment()
            if result and result.text:
                texts.append(result.text)
        finally:
            await adapter.end_session()
        rtf = (time.perf_counter() - started) / audio_seconds
    text = "".join(texts)
    payload = json.dumps(
        {
            "engine": "vosk",
            "expected_synthetic_phrase": PHRASE,
            "observed_text": text,
            "partial_count": len(partials),
            "endpoint_final_audio_times": finalized_at,
            "audio_seconds": audio_seconds,
            "inference_rtf": rtf,
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        },
        ensure_ascii=False,
    )
    print(payload, flush=True)
    print(
        "::notice title=ASR observed metrics::" + payload.replace("%", "%25"),
        flush=True,
    )
    assert partials, "Expected incremental hypotheses before finalization"
    assert any(word in text for word in ("你好", "语音", "指挥")), (
        "Synthetic speech was not recognized; inspect the actual result"
    )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="llmerv-real-asr-") as temp:
        raw, normalized = Path(temp) / "tts.wav", Path(temp) / "normalized.wav"
        subprocess.run(
            ["espeak-ng", "-v", "cmn", "-s", "130", "-w", str(raw), PHRASE], check=True
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(raw),
                "-af",
                "apad=pad_dur=2",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(normalized),
            ],
            check=True,
        )
        asyncio.run(check(normalized))
