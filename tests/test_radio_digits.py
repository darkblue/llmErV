import asyncio
import json
import threading
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import save, get
from backend.asr.base import ASRError
from backend.asr.base import ASRResult
from backend.asr.radio_digits import candidate, profile, vocabulary
from backend.asr import vosk_streaming as streaming

client = TestClient(app)


def test_standard_readings_and_conservative_mapping():
    assert {d: profile()["readings"][d] for d in "1270"} == dict(
        zip("1270", "幺两拐洞")
    )
    assert profile()["source"]["pdf_page"] == 12
    value = candidate("洞 幺 两 拐 洞")
    assert value["digits"] == "01270" and value["readings"] == "洞幺两拐洞"
    assert value["requires_audio_review"] and value["verification"] == "unverified"
    for text in [
        "两架飞机",
        "拐弯到洞口",
        "跑道幺两",
        "两三个",
        "[unk] 幺 两",
        "幺" * 33,
        "腰两拐洞",
    ]:
        assert candidate(text) is None
    assert candidate("腰 两 拐 洞", True)["digits"] == "1270"
    assert candidate("两", True)["digits"] == "2"
    assert candidate("[unk]", True) is None


def test_grammar_checks_native_vocabulary_and_fails_explicitly():
    class Model:
        def vosk_model_find_word(self, word):
            return -1 if word in {"幺", "邀"} else 1

    words = vocabulary(Model())
    assert "腰" in words and "幺" not in words and "[unk]" in words
    Model.vosk_model_find_word = lambda self, word: -1
    with pytest.raises(ASRError, match="RADIO_DIGIT_VOCABULARY_UNSUPPORTED"):
        vocabulary(Model())


def test_incremental_decoder_uses_grammar_and_preserves_raw_text(monkeypatch):
    import vosk

    class Model:
        def vosk_model_find_word(self, word):
            return 1

    class Recognizer:
        def __init__(self, model, rate, grammar):
            assert rate == 16000
            self.grammar = json.loads(grammar)
            assert all(
                word in self.grammar for word in ["幺", "两", "拐", "洞", "[unk]"]
            )

        def SetWords(self, enabled):
            pass

        def AcceptWaveform(self, pcm):
            return False

        def PartialResult(self):
            return '{"partial": "幺 两"}'

        def FinalResult(self):
            return '{"text": "腰 两 拐 洞"}'

    monkeypatch.setattr(vosk, "KaldiRecognizer", Recognizer)
    monkeypatch.setattr(streaming, "load_model", lambda: Model())
    monkeypatch.setattr(streaming, "_SLOTS", threading.BoundedSemaphore(1))

    async def run():
        adapter = streaming.VoskStreaming(radio_digits=True)
        await adapter.start_session([])
        await adapter.send_audio_chunk(b"\0\0" * 3200)
        partial = await adapter.get_partial_result()
        assert not partial.is_final and partial.radio_digits is None
        final = await adapter.finalize_segment()
        assert final.raw_text == "腰 两 拐 洞" and final.text == "腰两拐洞"
        assert final.radio_digits["digits"] == "1270"
        await adapter.end_session()
        assert streaming._SLOTS.acquire(blocking=False)
        streaming._SLOTS.release()

    asyncio.run(run())


def test_radio_mode_not_silently_enabled_for_mock():
    with (Path(__file__).parent / "fixtures/tone.wav").open("rb") as file:
        audio = client.post("/audio", files={"file": ("tone.wav", file)}).json()
    with client.websocket_connect("/ws/recognize") as ws:
        ws.send_json(
            {
                "type": "start",
                "source_id": audio["id"],
                "recognition_mode": "radio_digits",
            }
        )
        assert ws.receive_json()["code"] == "ASR_MODE_UNSUPPORTED"


def test_digit_approval_requires_listening_rejects_stale_and_keeps_audit():
    with (Path(__file__).parent / "fixtures/tone.wav").open("rb") as file:
        audio = client.post("/audio", files={"file": ("tone.wav", file)}).json()
    item = client.post(
        "/transcripts/import",
        json={
            "source_id": audio["id"],
            "text": "洞幺两拐洞",
            "start_time": 0,
            "end_time": 2,
        },
    ).json()
    url = f"/transcripts/{item['segment_id']}/radio-digits"
    proposal = client.get(url).json()
    assert proposal["candidate"]["digits"] == "01270"
    body = {"base_hash": proposal["base_hash"]}
    assert (
        client.post(url + "/apply", json=body).json()["detail"]
        == "AUDIO_REVIEW_ACK_REQUIRED"
    )
    result = client.post(
        url + "/apply", json={**body, "acknowledge_audio_review": True}
    )
    assert result.status_code == 200
    assert result.json()["corrected_text"] == "01270"
    assert result.json()["original_text"] == "洞幺两拐洞"
    assert (
        client.post(
            url + "/apply", json={**body, "acknowledge_audio_review": True}
        ).status_code
        == 409
    )
    audit = client.get(f"/transcripts/{item['segment_id']}/revisions").json()[0]
    assert (
        audit["method"] == "radio_digit_review"
        and audit["event_reanalysis"] == "completed"
    )
    assert audit["evidence"][0]["digit_profile"]["source"]["clause"] == "3.4.1.1 表1"
    assert get(item["segment_id"] + ":event")["fields"]["flight"]["value"] is None
    item.update(asr_engine="mock")
    save("transcript", item["segment_id"], item)
    assert client.get(url).json()["candidate"] is None


def test_numeric_slice_has_original_audio_timestamps_and_bounds(monkeypatch):
    import backend.main as main

    class Adapter:
        async def start_session(self, words):
            pass

        async def send_audio_chunk(self, pcm):
            pass

        async def get_partial_result(self):
            return ASRResult(
                "幺两", True, 0.05, 0.2, radio_digits=candidate("幺两", True)
            )

        async def finalize_segment(self):
            return None

        async def end_session(self):
            self.closed = True

    adapter = Adapter()
    monkeypatch.setattr(main, "create_adapter", lambda mode: adapter)
    monkeypatch.setattr(main, "PROVIDER", "vosk")
    with (Path(__file__).parent / "fixtures/tone.wav").open("rb") as file:
        source = client.post("/audio", files={"file": ("tone.wav", file)}).json()
    with client.websocket_connect("/ws/recognize") as ws:
        ws.send_json(
            {
                "type": "start",
                "source_id": source["id"],
                "recognition_mode": "radio_digits",
                "audio_offset": 1,
            }
        )
        assert ws.receive_json()["type"] == "model_status"
        ready = ws.receive_json()
        ws.send_bytes(b"\0\0" * 3200)
        final = ws.receive_json()
        assert final["start_time"] == 1.05 and final["end_time"] == 1.2
        assert final["radio_digits"]["digits"] == "12"
        assert ws.receive_json()["type"] == "event"
        assert ws.receive_json()["audio_time"] == 1.2
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["type"] == "ended"
    stored = client.get(f"/sessions/{ready['session_id']}/transcripts").json()[0]
    assert stored["start_time"] == 1.05 and adapter.closed
    for offset in [-1, 4, "1", True]:
        with client.websocket_connect("/ws/recognize") as ws:
            ws.send_json(
                {
                    "type": "start",
                    "source_id": source["id"],
                    "recognition_mode": "radio_digits",
                    "audio_offset": offset,
                }
            )
            assert ws.receive_json()["code"] == "INVALID_AUDIO_OFFSET"
    with client.websocket_connect("/ws/recognize") as ws:
        ws.send_json(
            {
                "type": "start",
                "source_id": source["id"],
                "recognition_mode": "radio_digits",
                "audio_offset": 3.9,
            }
        )
        ws.receive_json()
        ws.receive_json()
        ws.send_bytes(b"\0\0" * 3200)
        assert ws.receive_json()["code"] == "SESSION_TOO_LONG"
