# Changelog
## 0.1.0 — 2026-10-22
Initial Phase 1 development demo: real-time uploaded audio transport, explicitly labeled Mock ASR, optional unverified online FunASR adapter, audio safety checks, persistent transcripts/manual corrections, evidence-based event rules, dictionary, Chinese console, tests and container deployment assets.

## 0.2.0 — 2026-10-22
Evidence-based dialogue review workspace with private PDF references, scanned-document manual excerpts, per-page verification, bounded terminology suggestions, audio-time-linked playback, operator approval, immutable originals and atomic revision audit. Contextual human checklist for supplied MH/T 4014-2003. MP4 audio track support. No actual user-exercise speech validation yet: media attachment exceeds transfer limit.

## 0.3.0 — 2026-10-22
Real incremental Mandarin ASR using Vosk, checksum-pinned model bundled in backend Docker image, explicit readiness/errors, independent endpoint Finals with native timing/confidence, original model text, free-tier single-session limit and native memory/thread controls. MIT Mandarin fixture and genuine upload/WebSocket/history inference CI; Mock remains explicit and never silently substituted for failed real inference.
