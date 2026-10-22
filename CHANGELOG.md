# Changelog
## 0.4.0 — 2026-10-22
Opt-in Vosk constrained radio-digit streaming decoder for selected audio ranges up to 30s, based on supplied MH/T 4014-2003 table 1 (1幺/2两/7拐/0洞). Shared weights and single-session resource limit retained. Original model text, absolute source timestamps, unverified digit candidates, explicit audio-reviewed application and audit; ordinary conversation is not globally rewritten or model-trained. Real-model synthetic acceptance and browser review checks added, with observed outcomes reported by CI.

## 0.3.1 — 2026-10-22
Repair event sidebar aggregation, history loading and review-to-console navigation. Manual and reference revisions now recompute evidence-bound events atomically; event reads derive from current text for legacy compatibility. Explicit save action, corrected transcript display, event evidence/time/version, empty/Mock feedback and review analysis preview. Extend literal event rules to all ten fields and suppress common denied hazards; no ASR retraining or automatic operational commands.

## 0.1.0 — 2026-10-22
Initial Phase 1 development demo: real-time uploaded audio transport, explicitly labeled Mock ASR, optional unverified online FunASR adapter, audio safety checks, persistent transcripts/manual corrections, evidence-based event rules, dictionary, Chinese console, tests and container deployment assets.

## 0.2.0 — 2026-10-22
Evidence-based dialogue review workspace with private PDF references, scanned-document manual excerpts, per-page verification, bounded terminology suggestions, audio-time-linked playback, operator approval, immutable originals and atomic revision audit. Contextual human checklist for supplied MH/T 4014-2003. MP4 audio track support. No actual user-exercise speech validation yet: media attachment exceeds transfer limit.

## 0.3.0 — 2026-10-22
Real incremental Mandarin ASR using Vosk, checksum-pinned model bundled in backend Docker image, explicit readiness/errors, independent endpoint Finals with native timing/confidence, original model text, free-tier single-session limit and native memory/thread controls. MIT Mandarin fixture and genuine upload/WebSocket/history inference CI; Mock remains explicit and never silently substituted for failed real inference.
