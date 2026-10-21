---
type: Convention
title: Model names live in model_routes.toml; module constants read the cached route at import
description: Every model id is resolved once per process from the committed route file (route() is functools.cache, selected by POLICY_ATLAS_MODEL_ROUTE) into module-level constants, so a test of a non-default route must run in a subprocess, not a reload; the mechanical pin against regressions is the 29-constant equality test plus a grep narrowed to assignment lines (comments may name models); the loader rejects unknown routes, steps, tiers, backend names and wrong-shaped sections at import, but a step-exception value that is not a tier name is sent verbatim as a model id.
tags: [model-routes, configuration, import-time, testing, bedrock]
timestamp: 2026-10-14
---

# Rules

- **One file, one selector.** `backend/src/policy_atlas/model_routes.toml` names every
  text-model call site once (`[steps]`, 23 steps, four tiers) and, per route, the model
  for each tier, the `reasoning_effort` knob keyed by model id, the embedding section
  and the search-queries backend. `POLICY_ATLAS_MODEL_ROUTE` picks the route; unset is
  `openai-direct`, byte-identical to the pre-053 requests except the embedding batch
  size (128 to 96, contract D4). An uncommitted overlay named by
  `POLICY_ATLAS_MODEL_ROUTE_FILE` replaces or adds whole routes for experiments and
  may not carry `[steps]`. The nine `POLICY_ATLAS_*_MODEL` variables are retired:
  ignored, named in one start-up warning.
- **Constants resolve at import and stay resolved.** `route()` is cached for the
  process and `CLASSIFY_MODEL = route().model_for("classify")` runs when the module
  loads. A test that wants another route must start a fresh interpreter
  (`subprocess.run([sys.executable, "-c", ...])` with the two variables scrubbed);
  monkeypatching the environment or reloading the module in-process does not change
  constants other modules already imported. `tests/conftest.py` scrubs
  `POLICY_ATLAS_MODEL_ROUTE*`, `OPENAI_BASE_URL` and `AWS_BEARER_TOKEN_BEDROCK` at
  module top so a developer's `.env` cannot move the suite.
- **The pin is a test on the constants, not a grep of the tree.** Comments and
  docstrings legitimately mention model names, so "no literal model name in code" is
  checked by `test_every_module_constant_equals_its_pre_053_literal` (all 29) and a
  grep narrowed to assignment lines (`= "gpt-` / `= "text-embedding-`), which matches
  only the route file.
- **What fails loud and what cannot.** Unknown route, step, tier, backend name
  (`embeddings.backend`, `search_queries.backend`), a section that is not a table, and
  a malformed or missing file all raise `RuntimeError` naming the file and key at the
  first product import, including from an overlay. The one value the loader takes as
  written is a step exception that matches no tier name: by design it is a model id,
  so a typo there reaches the provider as a 404, not a start-up error.
- **The client address comes from the route, never the environment.**
  `resolve_openai_client` always passes `base_url=route().openai_base_url`, so a stray
  `OPENAI_BASE_URL` cannot move a selected route (tested at the client seam).

# Why

Task 053 replaced 25 literals in 15 modules and nine environment overrides with one
(29 literals in 19 modules and thirteen overrides once the options-scoping merge of
2026-10-21 was folded in; Sol joined as the `judgment` tier)
reviewed file so that a Bedrock route could name models that exist there and an
evaluation could try any model by adding a route. The review stack found two silent
fallbacks the first cut left (an unknown `search_queries.backend` built the OpenAI
class; a wrong-shaped overlay leaked `TypeError`), both found independently by the
Codex and Claude lanes, and closed them in the loader.

# Citations

- [ADR 0041](../adr/0041-bedrock-inference-route-and-model-route-file.md); [053 contract D3](../tasks/053-bedrock-local-route/contract.md)
- `backend/src/policy_atlas/core/model_routes.py`; `backend/tests/core/test_model_routes.py`
  (`test_import_time_selection_follows_the_variable`,
  `test_every_module_constant_equals_its_pre_053_literal`,
  `test_unknown_backend_names_and_wrong_shapes_fail_loud`,
  `test_stray_openai_base_url_does_not_move_the_client`)
- [053 verification § Review findings](../tasks/053-bedrock-local-route/verification.md)
