# Pre-implementation stubs. Targets fail on purpose so `make verify` is red,
# not falsely green, until wired to real tooling.
# Stack: Postgres/Aurora, LangGraph, OpenAI->Bedrock, Langfuse (uv + pytest + ruff + mypy).
# To wire a target: replace its body with the real command shown in the comment.

.PHONY: setup test typecheck lint build verify

setup:        # -> uv sync
	@echo "make setup: not yet wired (uv sync)" >&2; exit 1

test:         # -> uv run pytest
	@echo "make test: not yet wired (uv run pytest)" >&2; exit 1

typecheck:    # -> uv run mypy .
	@echo "make typecheck: not yet wired (uv run mypy .)" >&2; exit 1

lint:         # -> uv run ruff check .
	@echo "make lint: not yet wired (uv run ruff check .)" >&2; exit 1

build:        # -> packaging/build step
	@echo "make build: not yet wired" >&2; exit 1

verify: test typecheck lint build
