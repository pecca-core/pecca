.PHONY: test lint docs notebooks

test:
	PECCA_TEST_SMALL=1 uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

docs:
	uv run python scripts/gen_docs.py && uv run mkdocs build --strict

# Executes every notebook under examples/ in place (set PECCA_SKIP_DOCKER=1 to skip Docker cells).
# Needs the framework packages: pip install langgraph langchain-core strands-agents google-adk openai-agents claude-agent-sdk
notebooks:
	uv run python scripts/make_notebooks.py && uv run python scripts/run_notebooks.py
