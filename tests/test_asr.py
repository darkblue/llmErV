import asyncio
import hashlib
import io
import json
import threading
from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.asr.base import ASRResult, ASRError
from backend.asr import vosk_streaming as streaming
from scripts.provision_vosk_model import provision


class RecognizerDouble:
    """Protocol test double, not recognition evidence."""

    def __init__(self, model, sample_rate):
        self.count = 0
        self.sample_rate = sample_rate

    def SetWords(self, enabled):
        self.words = enabled

    def AcceptWaveform(self, pcm):
        self.count += 1
        return self.count == 2

    def PartialResult(self):
        return json.dumps({"partial": "指 挥 中 心" if self.count else ""})

    def Result(self):
        return json.dumps(
            {"text": "指 挥 中 心", "result": [{"start": 0.1, "end": 0.3, "conf": 0.8}]}
        )

    def FinalResult(self):
        return json.dumps(
            {"text": "塔 台", "result": [{"start": 0.4, "end": 0.6, "conf": 0.9}]}
        )


@pytest.fixture
def recognizer_double(monkeypatch):
    import vosk

    monkeypatch.setattr(vosk, "KaldiRecognizer", RecognizerDouble)
    monkeypatch.setattr(streaming, "load_model", lambda: object())
    monkeypatch.setattr(streaming, "_SLOTS", threading.BoundedSemaphore(1))


def test_incremental_adapter_metadata_and_slot_cleanup(recognizer_double):
    async def run():
        a, b = streaming.VoskStreaming(), streaming.VoskStreaming()
        await a.start_session(["任意热词不作为限定语法"])
        with pytest.raises(ASRError, match="ASR_BUSY"):
            await b.start_session([])
        await a.send_audio_chunk(b"\0\0" * 3200)
        partial = await a.get_partial_result()
        assert partial.text == "指挥中心" and not partial.is_final
        assert partial.raw_text == "指 挥 中 心"
        await a.send_audio_chunk(b"\0\0" * 3200)
        final = await a.get_partial_result()
        assert final.is_final and final.start_time == 0.1 and final.end_time == 0.3
        assert final.confidence == 0.8
        assert (await a.finalize_segment()).text == "塔台"
        await a.end_session()
        await a.end_session()
        await b.start_session([])
        assert b.recognizer.count == 0
        await b.end_session()

    asyncio.run(run())


def test_missing_model_releases_session_slot(recognizer_double, monkeypatch):
    def missing():
        raise FileNotFoundError("missing")

    monkeypatch.setattr(streaming, "load_model", missing)

    async def run():
        a = streaming.VoskStreaming()
        with pytest.raises(ASRError, match="ASR_MODEL_MISSING"):
            await a.start_session([])
        assert streaming._SLOTS.acquire(blocking=False)
        streaming._SLOTS.release()

    asyncio.run(run())


def test_session_cache_isolation(recognizer_double, monkeypatch):
    monkeypatch.setattr(streaming, "_SLOTS", threading.BoundedSemaphore(2))

    async def run():
        a, b = streaming.VoskStreaming(), streaming.VoskStreaming()
        await a.start_session([])
        await b.start_session([])
        await a.send_audio_chunk(b"\0\0" * 3200)
        await a.send_audio_chunk(b"\0\0" * 3200)
        await b.send_audio_chunk(b"\0\0" * 3200)
        assert (await a.get_partial_result()).is_final
        assert not (await b.get_partial_result()).is_final
        assert a.samples == 6400 and b.samples == 3200
        await a.end_session()
        await b.end_session()

    asyncio.run(run())


def test_websocket_endpoint_finals_and_history(monkeypatch):
    import backend.main as main

    class AdapterDouble:
        async def start_session(self, words):
            self.count = 0

        async def send_audio_chunk(self, pcm):
            self.count += 1

        async def get_partial_result(self):
            if self.count == 2:
                return ASRResult("指挥中心", True, 0.1, 0.35, 0.9, "指 挥 中 心")
            return ASRResult(
                "塔" if self.count > 2 else "指挥",
                False,
                0.4 if self.count > 2 else 0,
                self.count * 0.2,
            )

        async def finalize_segment(self):
            return ASRResult("塔台收到", True, 0.4, 0.6, 0.8)

        async def end_session(self):
            self.closed = True

    adapter = AdapterDouble()
    monkeypatch.setattr(main, "create_adapter", lambda: adapter)
    monkeypatch.setattr(main, "PROVIDER", "vosk")
    client = TestClient(app)
    with (Path(__file__).parent / "fixtures/tone.wav").open("rb") as f:
        id = client.post("/audio", files={"file": ("tone.wav", f)}).json()["id"]
    with client.websocket_connect("/ws/recognize") as ws:
        ws.send_json({"type": "start", "source_id": id})
        assert ws.receive_json()["type"] == "model_status"
        sid = ws.receive_json()["session_id"]
        frames = []
        for _ in range(3):
            ws.send_bytes(b"\0\0" * 3200)
            while True:
                message = ws.receive_json()
                frames.append(message)
                if message["type"] == "progress":
                    break
        finals = [m for m in frames if m["type"] == "final"]
        assert len(finals) == 1 and finals[0]["original_text"] == "指 挥 中 心"
        assert finals[0]["confidence"] == 0.9
        first = finals[0]["segment_id"]
        assert frames[-2]["type"] == "partial" and frames[-2]["segment_id"] != first
        ws.send_json({"type": "finish"})
        final = ws.receive_json()
        assert final["type"] == "final" and final["segment_id"] != first
        assert ws.receive_json()["type"] == "event"
        assert ws.receive_json()["type"] == "ended"
    records = client.get("/sessions/" + sid + "/transcripts").json()
    assert [r["text"] for r in records] == ["指挥中心", "塔台收到"]
    assert adapter.closed


def test_model_health_unavailable_is_not_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("ASR_PROVIDER", "vosk")
    monkeypatch.setenv("ASR_MODEL", str(tmp_path / "absent"))
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert not health["asr"]["ready"]
        assert health["asr"]["error_code"] == "ASR_MODEL_MISSING"
        assert health["mode"] == "ASR 未就绪"
    from backend.asr.providers import initialize

    monkeypatch.setenv("ASR_PROVIDER", "mock")
    asyncio.run(initialize())


def model_zip(unsafe=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("test-model/am/final.mdl", "self-authored test bytes")
        z.writestr("test-model/conf/model.conf", "test config")
        if unsafe:
            z.writestr(unsafe, "unsafe")
    return out.getvalue()


def manifest(data):
    return {
        "id": "test-model",
        "url": "https://example.com/test.zip",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def test_model_checksum_install_repeatability(monkeypatch, tmp_path):
    data = model_zip()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(data))
    path = provision(manifest(data), tmp_path)
    assert (path / "am/final.mdl").read_text() == "self-authored test bytes"
    assert provision(manifest(data), tmp_path) == path


def test_model_checksum_and_archive_traversal_rejected(monkeypatch, tmp_path):
    data = model_zip()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(data))
    bad = manifest(data)
    bad["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA256"):
        provision(bad, tmp_path)
    data = model_zip("test-model/../../escape.txt")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(data))
    with pytest.raises(ValueError, match="Unsafe"):
        provision(manifest(data), tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()
