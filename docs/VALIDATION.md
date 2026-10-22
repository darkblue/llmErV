# Validation evidence (2026-10-22)
- Python 3.12, Node 24, FFmpeg available; no visible NVIDIA GPU.
- Backend pytest: 10 passed; upload format/size/duration, 44.1kHz stereo→16kHz mono, search/delete, WebSocket chunk/partial/final, lifecycle, revision, concurrent isolation/disconnect, dictionary/evidence, Mock adapter lifecycle.
- Browser Chromium E2E: 2 passed, actual upload/playback/streaming, pause freezes input, resume, Final, manual revision, history, stop/restart.
- Next.js production build and TypeScript checks passed.
- pip check: no broken requirements.
- Real ASR not tested: ModelScope access returned proxy policy 403; no cached model or GPU. Adapter source is not evidence of model accuracy. CER/WER utility provided, no speech evaluation dataset supplied.
- Docker and GitHub PR status are updated in the final report; initial Docker build hit nested-container DNS; Git read works while GitHub API returned Forbidden.
- Tests use self-generated tones only, no operational communications.
