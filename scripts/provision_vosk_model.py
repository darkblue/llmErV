"""Download official pinned model with TLS/SHA256 checks; never fetch during ASR sessions."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import urllib.request
import zipfile


def provision(manifest, destination):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / manifest["id"]
    marker = target / ".archive-sha256"
    if marker.is_file() and marker.read_text().strip() == manifest["sha256"]:
        if (target / "am/final.mdl").is_file() and (
            target / "conf/model.conf"
        ).is_file():
            return target
        raise ValueError("Existing model is incomplete; restore it before proceeding")
    if target.exists():
        raise ValueError("Existing unverified model directory will not be overwritten")
    if not manifest["url"].startswith("https://") or len(manifest["sha256"]) != 64:
        raise ValueError("HTTPS and SHA256 required")
    with tempfile.TemporaryDirectory(prefix="llmerv-model-", dir=destination) as temp:
        archive = Path(temp) / "model.zip"
        digest = hashlib.sha256()
        total = 0
        deadline = time.monotonic() + 180
        with (
            urllib.request.urlopen(manifest["url"], timeout=30) as response,
            archive.open("wb") as out,
        ):
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 96 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ValueError("Model download limit exceeded")
                out.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != manifest["sha256"]:
            raise ValueError("Model SHA256 mismatch; download rejected")
        extraction = Path(temp) / "extracted"
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if (
                len(entries) > 5000
                or sum(x.file_size for x in entries) > 512 * 1024 * 1024
            ):
                raise ValueError("Model archive size limit exceeded")
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != manifest["id"]
                    or stat.S_ISLNK(entry.external_attr >> 16)
                ):
                    raise ValueError("Unsafe model archive member")
            source.extractall(extraction)
        model = extraction / manifest["id"]
        if (
            not (model / "am/final.mdl").is_file()
            or not (model / "conf/model.conf").is_file()
        ):
            raise ValueError("Archive is not a supported Vosk model")
        (model / ".archive-sha256").write_text(manifest["sha256"] + "\n")
        for path in model.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        model.chmod(0o755)
        shutil.move(str(model), str(target))
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("backend/asr/model.json"))
    parser.add_argument("--destination", type=Path, default=Path("models"))
    args = parser.parse_args()
    print(provision(json.loads(args.manifest.read_text()), args.destination))
