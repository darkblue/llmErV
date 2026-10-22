# Development rules
- Work on a feature branch and submit a PR; never merge main or deploy production automatically.
- Never commit secrets, private audio, model weights or database contents.
- Mock ASR must remain visibly labeled and must never fabricate actual recognition.
- Preserve original transcripts. Unknown emergency facts stay null with source evidence.
- Test: `python -m pytest -q`; frontend: `npm run typecheck && npm run build`, `npm run test:e2e` with backend running.
- Existing cloud checkout is isolated; use it without creating a worktree unless explicitly requested.
