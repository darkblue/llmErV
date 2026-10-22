# Validation evidence (2026-10-22)
- Python 3.12, Node 24, FFmpeg available; no visible NVIDIA GPU.
- Backend pytest: 16 passed; upload format/size/duration, 44.1kHz stereo→16kHz mono, search/delete, WebSocket chunk/partial/final, lifecycle, revision, concurrent isolation/disconnect, dictionary/evidence, Mock adapter lifecycle.
- Browser Chromium E2E: 2 passed, actual upload/playback/streaming, pause freezes input, resume, Final, manual revision, history, stop/restart.
- Next.js production build and TypeScript checks passed.
- pip check: no broken requirements.
- Real ASR not tested: ModelScope access returned proxy policy 403; no cached model or GPU. Adapter source is not evidence of model accuracy. CER/WER utility provided, no speech evaluation dataset supplied.
- Docker frontend/backend builds passed after supported proxy DNS mapping and platform CA trust setup. Non-root source ownership was corrected. Compose backend tests: 16 passed. Backend health and frontend HTTP 200 verified. Both containers healthy. Browser E2E against containerized production services: 2 passed.
- Git feature branch pushed successfully. Automatic PR creation failed: GitHub GraphQL API returned Forbidden; existing Git HTTPS proxy authentication supports push. No main merge or production deployment performed.
- Known warnings: Starlette TestClient httpx deprecation; non-root Docker pytest cache cannot write /app/.pytest_cache (test results unaffected).
- Tests use self-generated tones only, no operational communications.

# Dialogue review validation — 2026-10-22
- Source PDF from user-supplied CAAC URL downloaded after required network domain became available. Identified MH/T 4014-2003, 71 PDF pages; current legal validity not verified. Substantive clause citations checked against physical PDF pages: 3.1→11, 3.2/3.3/3.4.1→12, 3.9→24. Table of contents deliberately excluded from clause matching.
- User's four-page scanned card visually inspected and privately imported. Only limited printed excerpts recorded, left unverified for operator confirmation; no personal contact details or uncertain handwritten flight/location values embedded in source or correction rules.
- Backend: **26 passed** locally and **26 passed in Docker**. Added PDF validation/extraction, page boundaries, source/audio acknowledgments, preserved facts, immutable originals, custom-rule safety, reference revocation, stale/concurrent edits, original UI manual-edit audit, context-sensitive checklist, manual import and MP4 audio track checks.
- Browser E2E: **3 passed** against containerized production services. New case authors its own PDF and uses synthetic tone; exercises import, source verification, manual text provenance, playback, per-candidate acceptance, audio acknowledgment, original preservation and audit.
- TypeScript, Next.js production build and Ruff checks passed. Both Docker images built; both services healthy. Private reference files and database records survived container replacement.
- Remaining: actual exercise MP4 could not be downloaded because the attachment transfer tool caps files at 32MiB. No actual exercise speech recognition, dialogue correction acceptance or accuracy evaluation has been performed. A smaller/extracted audio attachment is required. The synthetic manual text in tests is test input, not speech transcribed from the tone.

## CI prerequisite repair
The original GitHub push/PR runs failed in backend pytest before frontend/Docker checks. Reproducing the runner's missing Poppler tools locally yielded 6 failed / 20 passed; restoring `pdfinfo` and `pdftotext` yielded 26 passed. The workflow now installs and verifies `ffmpeg` plus `poppler-utils`, pins Ubuntu 24.04, fails explicitly when backend startup times out, checks container health and retains JUnit/backend/container logs and browser failure traces. Actual GitHub rerun outcomes are reported separately after execution.
