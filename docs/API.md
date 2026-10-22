# API v0.1
FastAPI `/docs` serves generated REST OpenAPI.
- GET /health: process readiness, configured provider (not proof of model readiness).
- POST /audio multipart `file`: 201 metadata; 413 size, 415 format, 422 invalid/duration/decode failure.
- GET /audio?q=: filename search; GET /audio/{id}/content: normalized WAV; DELETE /audio/{id}: delete audio, history retained.
- GET /sessions; GET /sessions/{id}/transcripts; PATCH /transcripts/{segment_id} `{text}`: preserve original, update correction.
- GET /events: rule outputs, evidence and verification statuses.
- GET/PUT /hotwords: `{words: string[]}`; dictionary_only, native_supported=false. Import/export this JSON in UI.

WS /ws/recognize:
1. JSON `{type:"start",source_id:"uploaded-audio-uuid"}` within 15s.
2. Server `{type:"ready",session_id,asr_engine,sample_rate:16000,resume_supported:false}`.
3. Binary PCM16LE mono 16kHz chunks (even length, 1–64000 bytes). The browser paces real time; server limits total duration but does not independently enforce pacing for third-party clients.
4. Server `partial` with session_id/source_id/segment_id/start_time/end_time/text/is_final/confidence/speaker_id/asr_engine; same segment replaces previous Partial. Progress includes sequence/audio_time/inference_ms/rtf. Client roundtrip metric includes transport and inference.
5. Controls `{type:"pause"|"resume"|"stop"|"finish"}`; pause/resume emits state; stop/finish emits final (if nonempty), event and ended, then closes. Empty input produces ended only. Paused chunks produce INVALID_STATE without being consumed.
6. Error `{type:"error",code}`: INVALID_START, PROVIDER_UNAVAILABLE, INVALID_STATE, INVALID_CHUNK, SESSION_TOO_LONG, TIMEOUT, SESSION_FAILED.

120s without activity expires a session, including a long pause. On transport close discard active Partial, keep previously saved Finals; reconnect by explicitly starting a new session. Unknown/malformed JSON fails the session cleanly. No automatic replay or resumable transport yet.
