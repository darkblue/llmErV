"""Expose bounded CI diagnostics through check annotations, as well as artifacts."""

from pathlib import Path
import xml.etree.ElementTree as ET


def annotate(title, text):
    text = text[-6000:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title={title}::{text}")


if __name__ == "__main__":
    for name in (
        "backend.log",
        "browser.log",
        "frontend-install.log",
        "frontend-build.log",
        "docker-build.log",
        "container-tests.log",
    ):
        path = Path("/tmp") / name
        if path.is_file():
            annotate(
                name, "\n".join(path.read_text(errors="replace").splitlines()[-45:])
            )
    report = Path("/tmp/backend-tests.xml")
    if report.is_file():
        for failed in ET.parse(report).iter("failure"):
            annotate("Backend test failure", failed.text or failed.get("message", ""))
