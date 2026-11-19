---
paths:
  - "backend/src/policy_atlas/model_routes.toml"
  - "backend/src/policy_atlas/core/**"
  - "backend/src/policy_atlas/evidence_search/**"
  - "backend/src/policy_atlas/options_scoping/**"
  - "backend/src/policy_atlas/theory_of_change/**"
  - "backend/src/policy_atlas/runtime/**"
---

# Model calls: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- Postgres cannot store the NUL character in TEXT or JSONB, and models do emit it. Model
  output goes through `scrub_nul` (`backend/src/policy_atlas/core/prompt_fields.py`) before
  it is stored, or the insert fails only on a live run and rolls back the whole step.
- Retries stack: `core/tracing.py` sends each call up to `MODEL_CALL_ATTEMPTS` times, and
  `runtime/runner.py` reruns a failed model-bearing component once. A retry added inside a
  step multiplies with both, so its cost and wait are the product, not one call.
- Stored extraction findings are reused when the fingerprint in `evidence_search/extract/`
  matches. The fingerprints hold each extract step's model but not the extractors' own
  reasoning effort, so changing that effort in `model_routes.toml` reuses the old findings.
