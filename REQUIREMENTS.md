# Phase 1 requirements and acceptance
P0: Chinese responsive console, upload/search/delete, metadata, safe decode and playback.
P1: Browser playback clock controls 16kHz PCM WebSocket chunks; pause/resume/stop/restart; stable Partial identity and immutable Final; independent sessions; persistence.
P2: Real Vosk CPU streaming adapter with licensed Mandarin upload/WebSocket integration tests and pinned model in Docker. FunASR online adapter remains optional/unverified. Airport radio accuracy requires representative authorized recordings; no accuracy claim from one demo clip.
P3: Editable/importable/exportable dictionary (no native hotword claim), manual transcript corrections, conservative rules with evidence and null unknown fields.
P4: Session history, basic file search, event read API. Rich event editing/filtering deferred.
P5: Containerization, health probes, backend tests, browser E2E, deployment instructions. Public deployment requires authorized infrastructure.
Limits: 50MiB/file, 30 minutes, WAV/MP3/FLAC/M4A/OGG. Demo is single-user, no authentication. Never expose it with sensitive recordings before authentication, authorization, audit and retention controls are added.
