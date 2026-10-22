import wave
from pathlib import Path
import pytest

from fastapi.testclient import TestClient
from backend.main import app
from backend.asr.mock import MockASR
from backend.events.extract import extract
from backend.models import DATA

client = TestClient(app)
FIXTURE = Path(__file__).parent / "fixtures/tone.wav"


def upload():
    with FIXTURE.open("rb") as f:
        r = client.post("/audio", files={"file": ("tone.wav", f, "audio/wav")})
    assert r.status_code == 201, r.text
    return r.json()


def start(ws, id):
    ws.send_json({"type": "start", "source_id": id})
    ready = ws.receive_json()
    assert ready["type"] == "ready"
    return ready["session_id"]


def chunk(ws):
    ws.send_bytes(b"\x00\x00" * 3200)
    partial, progress = ws.receive_json(), ws.receive_json()
    assert partial["type"] == "partial" and not partial["is_final"]
    assert progress["type"] == "progress"
    return partial


def finish(ws):
    ws.send_json({"type": "finish"})
    final, event, ended = ws.receive_json(), ws.receive_json(), ws.receive_json()
    assert final["is_final"] and event["type"] == "event" and ended["type"] == "ended"
    assert all(f["value"] is None for f in event["fields"].values())
    return final


def test_upload_resample_search_delete():
    item = upload()
    assert item["sample_rate"] == 44100 and item["channels"] == 2
    with wave.open(str(DATA / (item["id"] + ".wav"))) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (
            16000,
            1,
            2,
        )
    assert client.get("/audio?q=tone").json()
    assert client.get("/audio/" + item["id"] + "/content").status_code == 200
    assert client.delete("/audio/" + item["id"]).status_code == 204
    assert client.get("/audio/" + item["id"] + "/content").status_code == 404


@pytest.mark.parametrize(
    "name,data,status", [("bad.exe", b"bad", 415), ("bad.wav", b"bad", 422)]
)
def test_invalid_upload(name, data, status):
    assert client.post("/audio", files={"file": (name, data)}).status_code == status


def test_size_limit(monkeypatch):
    import backend.main

    monkeypatch.setattr(backend.main, "MAX_BYTES", 10)
    assert (
        client.post("/audio", files={"file": ("large.wav", b"x" * 11)}).status_code
        == 413
    )


def test_duration_limit(tmp_path):
    from backend.audio.codec import decode

    p = tmp_path / "zero.wav"
    with wave.open(str(p), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"")
    with pytest.raises(ValueError):
        decode(p, tmp_path / "out.wav")


def test_pause_resume_partial_final_revision():
    id = upload()["id"]
    with client.websocket_connect("/ws/recognize") as ws:
        sid = start(ws, id)
        first = chunk(ws)
        second = chunk(ws)
        assert first["segment_id"] == second["segment_id"]
        assert second["end_time"] == 0.4
        ws.send_json({"type": "pause"})
        assert ws.receive_json()["status"] == "paused"
        ws.send_bytes(b"\x00\x00")
        assert ws.receive_json()["code"] == "INVALID_STATE"
        ws.send_json({"type": "resume"})
        assert ws.receive_json()["status"] == "running"
        final = finish(ws)
    records = client.get(f"/sessions/{sid}/transcripts").json()
    assert len(records) == 1
    r = client.patch("/transcripts/" + final["segment_id"], json={"text": "人工修订"})
    assert r.json()["original_text"] == final["text"]
    assert r.json()["corrected_text"] == "人工修订"


def test_isolation_disconnect_stop():
    id = upload()["id"]
    with client.websocket_connect("/ws/recognize") as a:
        sa = start(a, id)
        with client.websocket_connect("/ws/recognize") as b:
            sb = start(b, id)
            assert sa != sb
            chunk(a)
            chunk(a)
            assert chunk(b)["end_time"] == 0.2
            b.send_json({"type": "stop"})
            assert b.receive_json()["is_final"]
            b.receive_json()
            assert b.receive_json()["status"] == "stopped"
    assert any(
        s["id"] == sa and s["status"] == "disconnected"
        for s in client.get("/sessions").json()
    )


def test_protocol_errors():
    with client.websocket_connect("/ws/recognize") as ws:
        ws.send_json({"type": "start", "source_id": "missing"})
        assert ws.receive_json()["code"] == "INVALID_START"
    id = upload()["id"]
    with client.websocket_connect("/ws/recognize") as ws:
        start(ws, id)
        ws.send_bytes(b"x")
        assert ws.receive_json()["code"] == "INVALID_CHUNK"
        ws.send_json({"type": "stop"})
        assert ws.receive_json()["type"] == "ended"


def test_dictionary_and_evidence():
    assert client.put("/hotwords", json={"words": ["消防", "消防", "塔台"]}).json()[
        "words"
    ] == ["消防", "塔台"]
    s = {
        "session_id": "s",
        "segment_id": "x",
        "text": "CA1234 跑道27起火，请消防支援",
        "asr_engine": "funasr",
        "start_time": 0,
        "end_time": 3,
    }
    event = extract(s)
    assert event["fields"]["flight"]["value"] == "CA1234"
    assert event["fields"]["location"]["evidence"]["segment_id"] == "x"
    assert event["fields"]["casualties"]["value"] is None


def test_mock_lifecycle():
    import asyncio

    async def run():
        a = MockASR()
        await a.start_session([])
        await a.send_audio_chunk(b"\0\0" * 16000)
        assert (await a.get_partial_result()).text.endswith("1.0 秒")
        assert (await a.finalize_segment()).is_final
        await a.end_session()
        assert a.closed

    asyncio.run(run())


@pytest.mark.parametrize("extension", ["mp3", "flac", "m4a", "ogg"])
def test_supported_formats(extension, tmp_path):
    import subprocess

    file = tmp_path / ("tone." + extension)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(FIXTURE), str(file)], check=True, timeout=15
    )
    with file.open("rb") as f:
        r = client.post("/audio", files={"file": (file.name, f)})
    assert r.status_code == 201
    assert 3.9 <= r.json()["duration"] <= 4.2


def test_non_audio_id_cannot_delete_dictionary():
    client.put("/hotwords", json={"words": ["消防"]})
    assert client.delete("/audio/hotwords").status_code == 404
    assert client.get("/hotwords").json()["words"] == ["消防"]


def test_error_rate():
    from backend.events.evaluation import error_rate

    assert error_rate("机场消防", "机场消方") == 0.25
    assert error_rate(
        "airport fire service", "airport service", "word"
    ) == pytest.approx(1 / 3)
