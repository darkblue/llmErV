# Deployment
## Local / Docker
`docker compose up --build -d`; ports 3000/8000. `docker compose --profile test run --rm test` runs backend tests. Docker service healthchecks probe HTTP. Named audio-data volume retains SQLite/audio. Rebuild frontend when NEXT_PUBLIC_BACKEND_URL changes (build-time setting).
For local development see README. Only synthetic tone test data is distributed; generate with `python scripts/generate_audio.py`.

## Vercel frontend / independent backend
Import repository into Vercel, root `frontend`, framework Next.js, set `NEXT_PUBLIC_BACKEND_URL=https://your-backend-host` before building. Browser uses HTTPS/WSS. Never set an API secret in NEXT_PUBLIC variables. Backend Dockerfile runs on Railway/Render or an inference host with persistent volume mounted `/app/data`; expose 8000 and set FRONTEND_URL to the exact frontend origin. LLM_API_KEY belongs only in secure backend settings. Vercel does not run persistent ASR workers.

Mock remains the default configuration. The backend Dockerfile now bundles the checksum-pinned Vosk small Chinese model; set ASR_PROVIDER=vosk and ASR_MODEL=/opt/llmerv-models/vosk-model-small-cn-0.22 to activate true CPU streaming inference without an API key. Keep ASR_MAX_SESSIONS=1 on a free instance and check /health reports asr.ready=true. See [ASR.md](ASR.md) for exact Render settings, benchmark limits and licensed speech fixture. FunASR remains optional for stronger inference hosts; install requirements-asr.txt separately, supply model assets and validate actual recognition before claiming readiness.

The user has deployed a Vercel/Render trial. Repository changes do not themselves establish that the online services have updated; production settings are not changed automatically. Public operation requires authentication, per-user authorization, TLS, upload rate/concurrency limits, restricted egress, retention policy, backups, audit logs and database migrations. This release is a development demonstration, not an operational emergency command system. No dispatch actions are automated.

## Codex nested-container build
If the nested Docker network cannot resolve the platform proxy, run `python scripts/cloud_docker_build.py`. It resolves only proxy hostnames, supplies build-time host mappings/proxy arguments and mounts the platform's public CA certificate as an optional BuildKit secret. It does not disable verification or copy credential values. On ordinary hosts use normal `docker compose build`.
