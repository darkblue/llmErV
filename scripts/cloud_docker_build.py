"""Optional cloud proxy/CA build override; no credentials are saved or logged."""

import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
hosts = {}
for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    host = urlparse(os.environ.get(name, "")).hostname
    if host:
        hosts[host] = socket.gethostbyname(host)
cert = os.environ.get("CODEX_PROXY_CERT")
build = {"extra_hosts": [f"{host}:{ip}" for host, ip in hosts.items()]}
config = {
    "services": {name: {"build": dict(build)} for name in ("backend", "frontend")}
}
if cert and Path(cert).is_file():
    config["secrets"] = {"cloud_ca": {"file": cert}}
    for service in config["services"].values():
        service["build"]["secrets"] = ["cloud_ca"]
with tempfile.TemporaryDirectory(prefix="llmerv-build-") as temp:
    override = Path(temp) / "override.json"
    override.write_text(json.dumps(config))
    env = dict(os.environ)
    env.setdefault("DOCKER_CONFIG", "/workspace/.docker")
    command = [
        "docker",
        "compose",
        "-f",
        str(root / "compose.yaml"),
        "-f",
        str(override),
        "build",
    ]
    for name in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "no_proxy",
        "NO_PROXY",
    ):
        if name in env:
            command.extend(["--build-arg", name])
    subprocess.run(command, cwd=root, env=env, check=True)
