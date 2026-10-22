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
                    if size > 220 * 1024 * 1024:
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
                model=str(model_dir / "model.onnx"),
                lexicon=str(model_dir / "lexicon.txt"),
                tokens=str(model_dir / "tokens.txt"),
                dict_dir=str(model_dir / "dict"),
                noise_scale=0.667,
                noise_scale_w=0.8,
            ),
            num_threads=1,
            provider="cpu",
        )
    )
    tts = sherpa_onnx.OfflineTts(config)
    clips = []
    metrics = []
    for reading in ["幺", "两", "拐", "洞"]:
        audio = tts.generate(reading, sid=0, speed=0.5)
        clip = np.asarray(audio.samples).copy()
        peak = float(np.max(np.abs(clip))) if len(clip) else 0
        rms = float(np.sqrt(np.mean(clip**2))) if len(clip) else 0
        metrics.append(
            {
                "reading": reading,
                "seconds": len(clip) / audio.sample_rate,
                "peak": peak,
                "rms": rms,
            }
        )
        print(json.dumps(metrics[-1], ensure_ascii=False), flush=True)
        if (
            len(clip) < audio.sample_rate // 10
            or not np.isfinite(clip).all()
            or peak < 0.001
        ):
            raise ValueError("Synthetic fixture has no usable voiced audio")
        clips.extend(
            [
                clip / peak * 0.8,
                np.zeros(round(audio.sample_rate * 0.3), dtype=np.float32),
            ]
        )
    samples = np.clip(np.concatenate(clips), -1, 1)
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
                "digit_audio_metrics": metrics,
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
