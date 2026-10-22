# Deployment
## Local / Docker
`docker compose up --build -d`; ports 3000/8000. `docker compose --profile test run --rm test` runs backend tests. Docker service healthchecks probe HTTP. Named audio-data volume retains SQLite/audio. Rebuild frontend when NEXT_PUBLIC_BACKEND_URL changes (build-time setting).
For local development see README. Only synthetic tone test data is distributed; generate with `python scripts/generate_audio.py`.

## Vercel frontend / independent backend
Import repository into Vercel, root `frontend`, framework Next.js, set `NEXT_PUBLIC_BACKEND_URL=https://your-backend-host` before building. Browser uses HTTPS/WSS. Never set an API secret in NEXT_PUBLIC variables. Backend Dockerfile runs on Railway/Render or an inference host with persistent volume mounted `/app/data`; expose 8000 and set FRONTEND_URL to the exact frontend origin. LLM_API_KEY belongs only in secure backend settings. Vercel does not run persistent ASR workers.

Mock is the default. For real inference create a separate image from backend image with `pip install -r backend/requirements-asr.txt`, copy this optional requirements file into that image, supply trusted model download access/cache, and set ASR_PROVIDER=funasr, ASR_MODEL=paraformer-zh-streaming. Warm and verify model on authorized Chinese speech before claiming availability. No GPU or model assets bundled. Model downloads may require modelscope.cn and actual artifact destinations; do not disable TLS/checksums. Optional dependencies need deployment-specific version locking and model licensing review.

No public deployment has been performed. Public operation requires authentication, per-user authorization, TLS, upload rate/concurrency limits, restricted egress, retention policy, backups, audit logs and database migrations. This release is a development demonstration, not an operational emergency command system. No dispatch actions are automated.
