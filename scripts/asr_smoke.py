"""Real model integration via upload + WebSocket using an MIT upstream Mandarin demo."""

import hashlib
import json
from pathlib import Path
import resource
import subprocess
import tempfile
import time
import wave
from fastapi.testclient import TestClient
from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/mandarin-example.wav"
MANIFEST = json.loads(FIXTURE.with_suffix(".json").read_text())


def check(normalized):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == MANIFEST["sha256"]
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["asr_provider"] == "vosk" and health["asr"]["ready"], health
        with normalized.open("rb") as f:
            response = client.post(
                "/audio", files={"file": ("licensed-mandarin-demo.wav", f, "audio/wav")}
            )
        assert response.status_code == 201, response.text
        source = response.json()
        partials, finals, final_times = [], [], []
        with (
            client.websocket_connect("/ws/recognize") as ws,
            wave.open(str(normalized), "rb") as wav,
        ):
            ws.send_json({"type": "start", "source_id": source["id"]})
            assert ws.receive_json()["type"] == "model_status"
            ready = ws.receive_json()
            assert ready["type"] == "ready" and ready["asr_engine"] == "vosk", ready
            sid = ready["session_id"]
            duration = wav.getnframes() / 16000
            frames = 0
            started = time.perf_counter()
            while pcm := wav.readframes(3200):
                frames += len(pcm) // 2
                ws.send_bytes(pcm)
                while True:
                    message = ws.receive_json()
                    assert message["type"] != "error", message
                    if message["type"] == "partial" and message["text"]:
                        partials.append(message["text"])
                    if message["type"] == "final":
                        finals.append(message)
                        final_times.append(frames / 16000)
                    if message["type"] == "progress":
                        break
            ws.send_json({"type": "finish"})
            while True:
                message = ws.receive_json()
                assert message["type"] != "error", message
                if message["type"] == "final":
                    finals.append(message)
                if message["type"] == "ended":
                    break
            rtf = (time.perf_counter() - started) / duration
        history = client.get("/sessions/" + sid + "/transcripts").json()
        assert len(history) == len(finals)
        assert all(r["asr_engine"] == "vosk" and r["is_final"] for r in history)
        text = "".join(r["text"] for r in history)
        payload = json.dumps(
            {
                "engine": "vosk",
                "source": "MIT FunASR demo (not private recording)",
                "reference": MANIFEST["reference"],
                "observed_text": text,
                "partial_count": len(partials),
                "endpoint_final_audio_times": final_times,
                "audio_seconds": duration,
                "inference_rtf": rtf,
                "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / 1024,
            },
            ensure_ascii=False,
        )
        print(payload, flush=True)
        print(
            "::notice title=ASR observed metrics::" + payload.replace("%", "%25"),
            flush=True,
        )
        assert partials, "Expected incremental hypotheses"
        assert final_times, (
            "Expected endpoint Final before stop, not only file-level finalization"
        )
        assert sum(word in text for word in ("欢迎", "语音识别", "模型")) >= 2, (
            "Reference content not recognized; inspect actual output"
        )
        assert client.delete("/audio/" + source["id"]).status_code == 204


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="llmerv-real-asr-") as temp:
        normalized = Path(temp) / "normalized.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(FIXTURE),
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
        check(normalized)
