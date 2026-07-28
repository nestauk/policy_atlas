---
type: Integration quirk
title: uv src-layout images — deps layer via --no-install-project, project layer via a second sync
description: Two-stage uv sync (deps with --no-dev --no-install-project --frozen before COPY, then --no-dev --frozen after) gives cacheable dependency layers and a real installed policy_atlas package — no PYTHONPATH hacks.
tags: [docker, uv, python, build]
timestamp: 2026-07-28
---

# Rule

`backend/Dockerfile` (026 A.4): copy `pyproject.toml` + `uv.lock` alone, run
`uv sync --no-dev --no-install-project --frozen` (dependency layer, cache-stable
across source edits), then `COPY src/ …` and `uv sync --no-dev --frozen` (installs the
project itself). Result: `import policy_atlas` works in-container as a real installed
package — no `PYTHONPATH`, no `pip install -e` residue — and source-only changes
rebuild one thin layer.

# Watch out

The runtime stage copies `.venv` and must invoke through it (factory CMD
`uvicorn policy_atlas.api.app:create_app --factory`); pin the uv binary's image tag —
`ghcr.io/astral-sh/uv:latest` is a moving tag straight into a production build (026
review, supply-chain finding).
