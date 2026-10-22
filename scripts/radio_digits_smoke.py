"""Real constrained decoder check; synthetic audio is not airport accuracy data."""

import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app
from backend.asr.vosk_streaming import load_model
from backend.asr.radio_digits import vocabulary


def check():
    with (
        tempfile.TemporaryDirectory(prefix="radio-digits-") as folder,
        TestClient(app) as client,
    ):
        path = Path(folder)
        source_audio = Path(os.environ["RADIO_DIGIT_SOURCE"])
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source_audio),
                "-af",
                "adelay=1000|1000,apad=pad_dur=2",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(path / "digits.wav"),
            ],
            check=True,
        )
        with (path / "digits.wav").open("rb") as file:
            r = client.post(
                "/audio",
                files={"file": ("self-authored-synthetic-radio-digits.wav", file)},
            )
        assert r.status_code == 201, r.text
        source = r.json()
        finals, partials = [], []
        with (
            client.websocket_connect("/ws/recognize") as ws,
            wave.open(str(path / "digits.wav")) as wav,
        ):
            ws.send_json(
                {
                    "type": "start",
                    "source_id": source["id"],
                    "recognition_mode": "radio_digits",
                    "audio_offset": 0.5,
                }
            )
            assert ws.receive_json()["type"] == "model_status"
            ready = ws.receive_json()
            assert ready["type"] == "ready", ready
            sid = ready["session_id"]
            wav.setpos(8000)
            while pcm := wav.readframes(3200):
                ws.send_bytes(pcm)
                while True:
                    m = ws.receive_json()
                    assert m["type"] != "error", m
                    if m["type"] == "partial" and m["text"]:
                        partials.append(m["text"])
                    if m["type"] == "final":
                        finals.append(m)
                    if m["type"] == "progress":
                        break
            ws.send_json({"type": "finish"})
            while True:
                m = ws.receive_json()
                assert m["type"] != "error", m
                if m["type"] == "final":
                    finals.append(m)
                if m["type"] == "ended":
                    break
        observed = "".join(
            m["radio_digits"]["digits"] for m in finals if m.get("radio_digits")
        )
        # Same samples, unrestricted decoder: distinguish fixture quality from
        # constrained-grammar regressions without using the reference as input.
        from vosk import KaldiRecognizer

        baseline = KaldiRecognizer(load_model(), 16000)
        baseline_texts = []
        with wave.open(str(path / "digits.wav")) as wav:
            wav.setpos(8000)
            while pcm := wav.readframes(3200):
                if baseline.AcceptWaveform(pcm):
                    baseline_texts.append(json.loads(baseline.Result()).get("text", ""))
            baseline_texts.append(json.loads(baseline.FinalResult()).get("text", ""))
        report = {
            "source": "self-authored MIT MeloTTS synthetic speech; not human radio evaluation",
            "reference": "1270",
            "synthesis_input": "幺，两，拐，洞。",
            "observed_digits": observed,
            "general_decoder_baseline": " ".join(baseline_texts).strip(),
            "raw_finals": [m["original_text"] for m in finals],
            "partials": len(partials),
            "native_vocabulary": vocabulary(load_model()),
        }
        encoded = json.dumps(report, ensure_ascii=False)
        print(encoded, flush=True)
        print(
            "::notice title=Radio digit decoder evidence::"
            + encoded.replace("%", "%25"),
            flush=True,
        )
        if os.getenv("RADIO_DIGIT_FIXTURE_OUT"):
            shutil.copyfile(path / "digits.wav", os.environ["RADIO_DIGIT_FIXTURE_OUT"])
        assert partials and finals, "Expected real incremental decoding"
        assert all(
            m["start_time"] >= 0.5 and m["recognition_mode"] == "radio_digits"
            for m in finals
        )
        assert observed == "1270", (
            "Synthetic digit content mismatch; inspect observed output, do not claim accuracy"
        )
        history = client.get(f"/sessions/{sid}/transcripts").json()
        assert len(history) == len(finals)
        assert all(
            m["radio_digits"]["verification"] == "unverified"
            for m in history
            if m["radio_digits"]
        )


if __name__ == "__main__":
    check()
