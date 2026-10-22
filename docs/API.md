# API v0.1
FastAPI `/docs` serves generated REST OpenAPI.
- GET /health: process readiness, configured provider (not proof of model readiness).
- POST /audio multipart `file`: 201 metadata; 413 size, 415 format, 422 invalid/duration/decode failure.
- GET /audio?q=: filename search; GET /audio/{id}/content: normalized WAV; DELETE /audio/{id}: delete audio, history retained.
- GET /sessions; GET /sessions/{id}/transcripts; PATCH /transcripts/{segment_id} `{text}`: preserve original, update correction.
- GET /events?session_id=: current rule outputs, evidence and verification statuses; optional session filter. Results derive from each segment's current corrected_text, falling back to text for legacy records, so old persisted analysis cannot override revisions. Ordered by audio timestamp. `review_version` and `mock_excluded` describe the basis.
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
- `GET /transcripts/{id}/revisions` returns audit including manual PATCH edits from original UI. No authenticated operator identity yet. Saving a manual/reference revision atomically updates corrected_text, its derived event and the audit (`event_reanalysis=completed`). Original text remains unchanged; event evidence identifies the revision and remains unverified.
- Errors: REFERENCE_NOT_FOUND / FINAL_SEGMENT_NOT_FOUND (404); REFERENCE_TOO_LARGE (413); PDF_REQUIRED (415); INVALID_PDF_OR_EXTRACTION_FAILED, UNSAFE_RULE_USE_MANUAL_REVIEW, RULE_NOT_SUPPORTED_BY_EXCERPT, SOURCE_REVIEW_ACK_REQUIRED, AUDIO_REVIEW_ACK_REQUIRED, REFERENCE_REVIEW_REQUIRED, INVALID_SUGGESTION, OVERLAPPING_SUGGESTIONS, TRANSCRIPT_OUTSIDE_AUDIO (422); STALE_TRANSCRIPT_REVIEW_AGAIN (409).
- Audio extension allowlist now also accepts `.mp4`; FFmpeg extracts audio only. Existing upload limits apply.

## ASR v0.3
- `GET /health` 增加 `asr` 能力与 readiness，区分模型未就绪和 HTTP 服务可用。
- `GET /asr/capabilities` 返回 provider/ready/status/error_code/model/sample_rate/supports_partial/supports_endpoint_final/native_hotwords。
- WS 可先发送 `model_status`（loading），再发送 ready；真实模型未成功初始化不发送 ready，不回退 Mock。
- Vosk 可在每个语句结束时发送 Final+event，而不必等整个文件停止。后续 Partial 使用新的 segment_id；stop/finish 只提交剩余文本，不重复已保存 Final。Final 使用词时间戳和模型可用置信度。
- 新错误 ASR_DEPENDENCY_MISSING、ASR_MODEL_MISSING、ASR_MODEL_LOAD_FAILED、ASR_BUSY。默认最多一个真实识别会话。
- `original_text` 保留模型原始分词空格；显示 text 仅移除中文词间空格，corrected_text 供独立人工修订。

## 数字专项 v0.4
- `GET /asr/radio-digits`: 固定报读映射、来源条款及机制说明。1幺、2两、7拐、0洞，资料为用户提供的 2003 版，现行有效性未核验。
- `GET /asr/capabilities` 增加 recognition_modes；Vosk 支持 general / radio_digits，其余仅 general。native_hotwords 仍为 false，专项使用受限语法而非通用热词加权。
- WS start 可选 `{recognition_mode:"radio_digits",audio_offset:秒数}`；默认 general/0。浏览器只播放并发送选定数字短句的 PCM，最多30秒；服务端检查 offset 为录音内有限非负数，限制输入到原录音结尾及30秒。General 不接受非零 offset。
- ready/Final/session 保存 recognition_mode，Final 的 start_time/end_time 是原录音绝对时间。radio_digits 包含未核实 digits/readings、原始词、来源、机制。含未知词不生成完整候选；不替换 text/original_text。Partial 不提供数字定稿。
- `GET /transcripts/{id}/radio-digits` 返回 base_hash 和当前候选；Mock 不提供。普通模式仅映射完整且明确的报读数字串，专项允许受限解码器的同音声学词条，不在普通语句中使用同音替换。
- `POST /transcripts/{id}/radio-digits/apply` `{base_hash,acknowledge_audio_review:true}`：重新计算候选，验证版本、回听确认，写入 corrected_text、审计（radio_digit_review）并重算事件；前导零保留。原始文本不变，不从数字串猜测航班或跑道。
- 错误：ASR_MODE_UNSUPPORTED、RADIO_DIGIT_VOCABULARY_UNSUPPORTED、INVALID_AUDIO_OFFSET（WS）；NO_RADIO_DIGIT_CANDIDATE（422）；复用回听确认和版本冲突错误。旧后端未确认专项模式时，客户端终止会话。
