#!/usr/bin/env bash
# GitHub's Azure mirror has intermittently stalled media dependency downloads.
# Keep Ubuntu package signature verification; use official HTTPS mirrors.
set -euo pipefail
llmerv_required=(ffmpeg ffprobe)
llmerv_packages=(ffmpeg)
if [[ "${1:-}" != "--audio-only" ]]; then
  llmerv_required+=(pdfinfo pdftotext)
  llmerv_packages+=(poppler-utils)
fi
llmerv_missing=0
for llmerv_tool in "${llmerv_required[@]}"; do
  command -v "$llmerv_tool" >/dev/null || llmerv_missing=1
done
if (( llmerv_missing )); then
  if [[ -f /etc/apt/apt-mirrors.txt ]]; then
    printf '%s\n' 'https://archive.ubuntu.com/ubuntu/' | sudo tee /etc/apt/apt-mirrors.txt >/dev/null
  fi
  if [[ -f /etc/apt/apt-mirrors-security.txt ]]; then
    printf '%s\n' 'https://security.ubuntu.com/ubuntu/' | sudo tee /etc/apt/apt-mirrors-security.txt >/dev/null
  fi
  sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends "${llmerv_packages[@]}"
fi
ffmpeg -version
ffprobe -version
if [[ "${1:-}" != "--audio-only" ]]; then
  pdfinfo -v
  pdftotext -v
fi
