# Contributing
Setup: `uv sync`, `uv run pre-commit install`. Test: `PECCA_TEST_SMALL=1 uv run pytest`. Lint: `uv run ruff check . && uv run mypy src`.
Sign off every commit (DCO): `git commit -s`. No CLA.
Add a candidate with `@pecca.register`; a connector with `@pecca.connectors.register(interface=..., type=...)`; a profile as `profiles/<name>.yaml` (keep the disclaimer header).
PR checklist: tests added, ruff/mypy clean, docs updated, commits signed off.
