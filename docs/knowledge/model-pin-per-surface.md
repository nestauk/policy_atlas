---
type: Convention
title: Every model call site reads its own step from the route file
description: Each surface that calls a model names its own step in model_routes.toml and reads it with route().model_for. A surface that borrowed another surface's step would move when that step is re-pinned.
tags: [models, configuration, routing]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: model-routes
    resource: backend/src/policy_atlas/model_routes.toml
  - id: agent-backend
    resource: backend/src/policy_atlas/runtime/agent_backend.py
  - id: routing-test
    resource: backend/tests/runtime/test_agent_backend.py
    title: test_model_routing_by_moment
---

# Rule

- Every model call site has its own step under `[steps]` in `model_routes.toml` and reads it
  with `route().model_for("<step>")` (for example `AGENT_TRIAGE_MODEL =
  route().model_for("agent_triage")` in `runtime/agent_backend.py`). Do not reuse another
  surface's step or constant: a re-pin of that step would move both surfaces.
- After a model change, run `test_model_routing_by_moment`
  (`backend/tests/runtime/test_agent_backend.py`).
- Prompt text and model choice are pinned apart: `scripts/prompt_hash_guard.py` pins prompt
  text, the route file pins models.
