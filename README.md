# llmErV
Airport Emergency Rescue Voice Intelligence Platform · 机场应急救援智能语音平台

Phase 1 development demo. **Default is 模拟识别**: actual uploaded audio is played and streamed in PCM chunks; the mock prints received duration, not recognized speech. Real FunASR adapter is optional and not validated with a downloaded model. No accuracy claim or automatic command dispatch.

## Start
Prerequisites: Python 3.11+, Node 22+, FFmpeg/FFprobe.
```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
# separate terminal
cd frontend
npm ci
npm run dev
```
Browser: port 3000. Backend: port 8000. Upload `tests/fixtures/tone.wav`, select Start, pause/resume/stop, inspect Final and history. Tone is original synthesized 440Hz stereo 44.1kHz (CC0), not airport communications. `python scripts/generate_audio.py` reproduces it.

Docker: `docker compose up --build -d`. Test service: `docker compose --profile test run --rm test`.

## Tests
```bash
.venv/bin/python -m pytest -q
cd frontend
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e  # backend must already run; starts frontend automatically
# existing Chromium: CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e
```

## Structure
```text
backend/  main.py models.py
          asr/       adapter interface, mock, optional FunASR
          audio/     FFprobe/FFmpeg
          events/    evidence rules, provider protocols, CER/WER
          adapters/  future source contracts
frontend/ app/ components/ui/ lib/ e2e/
tests/    backend tests + synthetic fixture
docker/   frontend/backend Dockerfiles
docs/     API.md DEPLOYMENT.md
scripts/  fixture generator
```

Configuration: `.env.example` lists ASR_PROVIDER, ASR_MODEL, LLM_PROVIDER, LLM_API_KEY, DATABASE_URL, FRONTEND_URL, BACKEND_URL, NEXT_PUBLIC_BACKEND_URL. Uvicorn does not implicitly load `.env`: export settings or pass `--env-file .env`. Rules are currently the only event provider; setting LLM_PROVIDER does not enable an LLM. Backend URL in browser is NEXT_PUBLIC_BACKEND_URL; BACKEND_URL is reserved for server integrations. Default database/audio under `data/`; SQLAlchemy allows PostgreSQL via `postgresql+psycopg://...`.

See [Architecture](ARCHITECTURE.md), [requirements](REQUIREMENTS.md), [API](docs/API.md), [deployment](docs/DEPLOYMENT.md), [remaining work](TASKS.md). This demo has no authentication; use synthetic/non-sensitive data in a controlled environment.

## 对话修订工作台
`/review` 支持导入规范/单卡 PDF、按页核实摘录、录音时间段回听、有限术语建议、人工确认应用及修订审计。保留原文，不按单卡补写关键事实，不把 Mock 当作真实对话。支持带音轨 MP4 输入和人工原文导入。详见 [使用与参考条款](docs/VOICE_REVIEW.md)。本地运行额外需要 Poppler 的 `pdfinfo` / `pdftotext`（Docker 已包含 `poppler-utils`）。
