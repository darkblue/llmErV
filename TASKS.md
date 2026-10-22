# Delivery status
- [x] Sidebar keeps session evidence across empty segments, loads history and follows manual/reference corrections with versioned evidence; revision UI explicitly saves and previews updated analysis
- [x] P0 upload, metadata, playback, Chinese console
- [x] P1 real-time PCM transport, Mock, lifecycle, Partial/Final, isolation
- [ ] P2 actual FunASR inference acceptance (adapter implemented; model access blocked)
- [x] P3 dictionary, manual edits, conservative event rules
- [ ] P3 native hotwords / automatic terminology correction / actual LLM
- [x] P4 lightweight persistence, basic session history/search, events API
- [ ] P4 rich event management and verified workflow
- [x] P5 backend 16 tests, browser E2E, production build/typecheck, Docker builds/health, deployment documentation
- [ ] Public preview / authenticated production service
- [ ] Real hardware, diarization, VAD segments, reconnection resume, speed control, normalized DB migrations

## Reference dialogue review
- [x] Official source read: user-supplied MH/T 4014-2003; current legal validity unverified
- [x] Reference PDF import, scans/manual excerpts, page evidence and local verification
- [x] Audio replay, bounded term candidates, approval, immutable originals, stale-review protection, audit
- [x] AOC vs ATC context-sensitive human checklist (not automated compliance audit)
- [x] MP4 audio-track import and explicitly labeled manual transcript import
- [ ] User exercise actual speech validation: attachment transfer exceeds 32MiB; needs extracted audio/smaller parts
- [ ] Broad phonetic ASR correction, authenticated operator audit, cross-turn readback analysis and automated OCR

## Real ASR / free CPU trial
- [x] Real Vosk Mandarin incremental inference and per-utterance Finals
- [x] Fixed-SHA model distribution in Docker, explicit readiness/failure and one-session default
- [x] Licensed Mandarin upload/WS/history integration check and CI performance report
- [x] Protocol/model artifact tests, Render enablement documentation
- [ ] User's original exercise recording acceptance (previous video exceeded transfer limit)
- [ ] Representative airport radio evaluation, native hotword boosting, diarization, production authentication
- [ ] FunASR on GPU / stronger CPU instance acceptance (Vosk is the tested free-trial engine)
