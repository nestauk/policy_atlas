# ADR 0019 — Capability-aware package structure

**Status:** Accepted (owner, 2026-07-14) · **Task:** 023-codebase-health

## Context

`src/policy_atlas/` grew to 63 flat modules (~44K lines) across tasks 001–022. The 2026-07-14
whole-codebase review ([findings](../tasks/023-codebase-health/review-findings.md)) confirmed
the flat layout is past its limit but the import graph is a clean DAG — a regroup is
mechanically safe. Two structural facts drive the shape chosen:

1. The system spec's hierarchy is **tools → components → capabilities → artefacts**
   ([data-model](../specs/system/data-model.md)), and Evidence Base is v3.0's only
   capability, with Options Assessment, Impact, Transferability, VfM, ToC, Risk deferred
   ([product](../specs/product.md)) and baseline assessment on the owner's roadmap.
2. The repo will become a **backend + frontend monorepo** (demo frontend to be pulled in),
   with a top-level CDK deployment directory named `infra/` (precedent: the V2 repo).

## Decision

Three top-level packages inside `policy_atlas`, with the EB capability as one subpackage
and phase sub-buckets inside it:

```
policy_atlas/
  runtime/        orchestrate, runner, harness, steering, orchestration_plan,
                  planner, planner_prompt, run_spec
  evidence_base/  clustering_engine
    sourcing/ · screen/ · corpus/ · extract/ · group/ · synthesis/
  core/           schema, db, events, logging, tracing, usage, inference,
                  openai_client, embeddings, prompt_fields, tags, fixtures, windowing
  data/           (package data — stays at root; orchestrate's stub mode reads it via
                   the harness default fixture backends, importlib.resources anchors
                   are top-package)
```

Named rulings (owner, 2026-07-14):

- **`core/`, not `infra/`** — avoids semantic collision with the future top-level CDK
  `infra/` directory in the monorepo. (`platform/` considered; owner chose `core/` as the
  honest description of the contents.)
- **`evidence_base/`, not `eb/`** — spelled out.
- **No `tools/` bucket** — the spec classes search/retrieve/grounding as universal core
  tools, but no incoming capability will search; they will work off the EB-gathered corpus.
  Search stays in `evidence_base/sourcing/`; extraction of a shared tool layer becomes real
  only if a web-search capability or new data sources land (seam recorded in
  [deferred.md](../deferred.md)).
- **Prompts co-located with their phase**, not a global `prompts/` bucket — each `*_prompt`
  module imports its phase's records/fields; a prompts bucket would manufacture cross-bucket
  edges.
- **`tests/` mirrors the tree** — `tests/` is already a package with absolute helper
  imports, so the mirror move is cheap now and avoids a second churn wave;
  `conftest.py`/`helpers.py`/`synthesis_wire.py` stay at `tests/` root.
- **IOF/ICF naming symmetry** rides the same slice: `iof_records`/`icf_records`,
  `iof_prompt`/`icf_prompt`, one merged `finding_vetter` — ending the unmarked-default
  asymmetry (IOF built first, holding generic names ICF then had to mark against).
- **Skeleton retired; orchestrate is the standardised smoke + live-check vehicle**
  (owner, 2026-07-14, reversing the same-day "stays" ruling on the evidence that no
  recent slice used the stub skeleton smoke, the runner test suite already covers the
  full stub chain, and 022's live check could equally have run through orchestrate).
  The `policy-atlas-skeleton` console script is removed;
  `python -m policy_atlas.runtime.orchestrate` is the entry point, with a no-key stub
  mode and an injectable console seam for scripted checks.

## Consequences

- Future capabilities land as siblings of `evidence_base/`, reusing `runtime/` and `core/`.
- `runtime/` vocabulary is EB-bound today (runner self-describes as the EB capability-runner);
  a second capability forces a planner/runner vocabulary split — a seam noted, not built
  (build light, leave seams).
- One extra import level everywhere (`policy_atlas.evidence_base.extract.…`); paid once,
  pre-eval, before baselines pin trace shapes and import paths.
- The sole console script (`policy-atlas-skeleton`) is removed with the skeleton
  retirement; no `[project.scripts]` entry remains.

## Alternatives rejected

- **Flat 8 phase buckets, no capability wrapper** (the review sub-agent's proposal): loses
  the capability seam the specs and roadmap name; re-restructuring at capability #2 would
  cost more than the one directory level costs now.
- **Global `prompts/` bucket**: manufactured cross-bucket import edges (see above).
- **`tools/` layer now**: speculative until a second search consumer exists (owner ruling).
