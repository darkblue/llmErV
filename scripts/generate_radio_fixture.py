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
    import onnxruntime as ort

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
    # Follow the upstream Melo ONNX test recipe directly. In particular, use
    # model speaker_id and the lexicon's separate phone/tone sequences.
    # https://github.com/k2-fsa/sherpa-onnx/blob/master/scripts/melo-tts/test.py
    tokens = {
        word: int(index)
        for word, index in (
            line.split() for line in (model_dir / "tokens.txt").read_text().splitlines()
        )
    }
    readings = ["幺", "两", "拐", "洞"]
    lexicon = {}
    for line in (model_dir / "lexicon.txt").read_text().splitlines():
        parts = line.split()
        if parts and parts[0] in readings:
            values = parts[1:]
            count = len(values) // 2
            lexicon[parts[0]] = (
                [tokens[p] for p in values[:count]],
                [int(t) for t in values[count:]],
            )
    ort.set_seed(0)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    model = ort.InferenceSession(
        str(model_dir / "model.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    metadata = model.get_modelmeta().custom_metadata_map
    sample_rate = int(metadata["sample_rate"])
    speaker_id = int(metadata["speaker_id"])
    print(
        json.dumps(
            {
                "sample_rate": sample_rate,
                "speaker_id": speaker_id,
                "add_blank": metadata["add_blank"],
            }
        ),
        flush=True,
    )
    clips = []
    metrics = []
    for reading in [manifest["text"]]:
        # Melo's Chinese G2P includes utterance boundaries *before* add_blank:
        # https://github.com/myshell-ai/MeloTTS/blob/main/melo/text/chinese_mix.py
        phones, tones = [tokens["_"]], [0]
        punctuation = {"，": ",", "。": "."}
        for char in reading:
            if char in lexicon:
                word_phones, word_tones = lexicon[char]
                phones.extend(word_phones)
                tones.extend(word_tones)
            elif char in punctuation:
                phones.append(tokens[punctuation[char]])
                tones.append(0)
            else:
                raise ValueError("Unexpected character in authored radio fixture")
        phones.append(tokens["_"])
        tones.append(0)
        if int(metadata["add_blank"]):
            padded_phones = [0] * (2 * len(phones) + 1)
            padded_tones = [0] * (2 * len(tones) + 1)
            padded_phones[1::2], padded_tones[1::2] = phones, tones
            phones, tones = padded_phones, padded_tones
        clip = (
            model.run(
                ["y"],
                {
                    "x": np.asarray([phones], dtype=np.int64),
                    "tones": np.asarray([tones], dtype=np.int64),
                    "x_lengths": np.asarray([len(phones)], dtype=np.int64),
                    "sid": np.asarray([speaker_id], dtype=np.int64),
                    "noise_scale": np.asarray([0.6], dtype=np.float32),
                    "noise_scale_w": np.asarray([0.8], dtype=np.float32),
                "length_scale": np.asarray([1.0], dtype=np.float32),
                },
            )[0]
            .reshape(-1)
            .astype(np.float32)
        )
        peak = float(np.max(np.abs(clip))) if len(clip) else 0
        rms = float(np.sqrt(np.mean(clip**2))) if len(clip) else 0
        metrics.append(
            {
                "reading": reading,
                "seconds": len(clip) / sample_rate,
                "peak": peak,
                "rms": rms,
            }
        )
        print(json.dumps(metrics[-1], ensure_ascii=False), flush=True)
        if len(clip) < sample_rate // 10 or not np.isfinite(clip).all() or peak < 0.001:
            raise ValueError("Synthetic fixture has no usable voiced audio")
        clips.extend(
            [
                clip / peak * 0.8,
                np.zeros(round(sample_rate * 0.3), dtype=np.float32),
            ]
        )
    samples = np.clip(np.concatenate(clips), -1, 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((samples * 32767).astype("<i2").tobytes())
    print(
        json.dumps(
            {
                "generator": "MeloTTS/ONNX Runtime, upstream phone/tone recipe",
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
