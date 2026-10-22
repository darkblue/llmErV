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

## Reference review v0.2
- `POST /references?kind=exercise_card|caac_standard&source_url=...` multipart PDF (15MiB/200 pages). Returns UUID, SHA256, physical page count, extraction status, unverified page excerpts; source URL is optional metadata, never fetched by the server. A scanned PDF requires manual excerpts. No automatic OCR claim.
- `GET /references`, `GET /references/{id}/content`.
- `POST /references/{id}/excerpts` `{page,text}` → unverified manual excerpt.
- `PUT /references/{id}/excerpts/{excerpt_id}/verification` `{verified,acknowledge_source_review}`. True requires explicit acknowledgment; can revoke.
- `GET /review/capabilities` exposes bounded vocabulary/engine limitations. `GET /review/rules`, `POST /review/rules` `{reference_id,excerpt_id,before,after}` creates evidence-bound generic term mapping; one edit only, digit/action/negation changes refused.
- `POST /transcripts/import` `{source_id,text,start_time,end_time}` imports user text within recorded duration. Tagged manual_input, never a genuine ASR result.
- `POST /transcripts/{id}/review` `{reference_ids,communication_context}` returns base_hash, candidate spans, references, requires_audio_review and can_apply. Context: `aoc_rescue` (default), `atc_air_ground`, `unknown`. Parsed supplied 2003 standard enables context-sensitive human checklist, not compliance findings.
- `POST /transcripts/{id}/review/apply` additionally needs `{base_hash,suggestion_ids,acknowledge_audio_review:true}`. Server recomputes proposals, checks source verification, rejects overlap and writes correction+audit atomically. Original text unchanged.
- `GET /transcripts/{id}/revisions` returns audit including manual PATCH edits from original UI. No authenticated operator identity yet. Event analysis remains based on original transcript; no silent reanalysis.
- Errors: REFERENCE_NOT_FOUND / FINAL_SEGMENT_NOT_FOUND (404); REFERENCE_TOO_LARGE (413); PDF_REQUIRED (415); INVALID_PDF_OR_EXTRACTION_FAILED, UNSAFE_RULE_USE_MANUAL_REVIEW, RULE_NOT_SUPPORTED_BY_EXCERPT, SOURCE_REVIEW_ACK_REQUIRED, AUDIO_REVIEW_ACK_REQUIRED, REFERENCE_REVIEW_REQUIRED, INVALID_SUGGESTION, OVERLAPPING_SUGGESTIONS, TRANSCRIPT_OUTSIDE_AUDIO (422); STALE_TRANSCRIPT_REVIEW_AGAIN (409).
- Audio extension allowlist now also accepts `.mp4`; FFmpeg extracts audio only. Existing upload limits apply.
