"""Generate self-authored speech with a pinned MIT MeloTTS voice (CI only)."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import wave

MANIFEST = Path(__file__).resolve().parents[1] / "tests/fixtures/radio-tts-model.json"


def generate(model_dir, output):
    import numpy as np
    import sherpa_onnx

    manifest = json.loads(MANIFEST.read_text())
    for name, expected in manifest["files"].items():
        path = model_dir / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['commit']}/{name}"
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            digest = hashlib.sha256()
            size = 0
            with (
                urllib.request.urlopen(url, timeout=90) as response,
                temporary.open("wb") as file,
            ):
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 80 * 1024 * 1024:
                        raise ValueError("TTS dependency exceeds limit")
                    digest.update(chunk)
                    file.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError("TTS SHA256 mismatch")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(model_dir / "model.int8.onnx"),
                lexicon=str(model_dir / "lexicon.txt"),
                tokens=str(model_dir / "tokens.txt"),
                dict_dir=str(model_dir / "dict"),
            ),
            num_threads=1,
            provider="cpu",
        )
    )
    tts = sherpa_onnx.OfflineTts(config)
    audio = tts.generate(manifest["text"], sid=0, speed=1.0)
    samples = np.clip(np.asarray(audio.samples), -1, 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(audio.sample_rate)
        wav.writeframes((samples * 32767).astype("<i2").tobytes())
    print(
        json.dumps(
            {
                "generator": "MeloTTS/sherpa-onnx",
                "license": "MIT",
                "text": manifest["text"],
                "model_commit": manifest["commit"],
                "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.model_dir, args.output)
