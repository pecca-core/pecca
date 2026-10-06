## What and why

## Checklist
- [ ] Tests added or updated (`PECCA_TEST_SMALL=1 uv run pytest`)
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy src` pass
- [ ] Docs updated (and `uv run python scripts/gen_docs.py` if the CLI or config schema changed)
- [ ] Commits are signed off (`git commit -s`, DCO)
