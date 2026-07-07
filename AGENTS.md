# Agent protocol

- Use the commands in the `Makefile`.
- For non-trivial work, plan before editing.
- Write Google-style docstrings (`Args:`/`Returns:`/`Raises:` sections) for public modules,
  classes and functions; keep them concise. Trivial helpers and test functions need none.
- Use `docs/specs/` for product and system intent — **living intent, not golden**. If building shows
  a spec is wrong or improvable, flag it and flow the change back (`docs/specs/README`); don't
  silently obey it or silently deviate.
- Use `docs/tasks/<task-id>/` for per-task artefacts: `contract.md` (scope), `rubric.md`
  (completion criteria, when risk is medium or high), `verification.md` (evidence, or in the PR).
  `<task-id>` is `NNN-slug` (zero-padded, e.g. `001-example-slice`). Templates live in `docs/tasks/_templates/`.
- Agent-side model routing: the lead (Fable 5) plans, judges, synthesizes; delegate volume via the
  pinned agents in `.claude/agents/` — `deep-reasoner` (Opus) for reasoning offload, `fast-worker`
  (Sonnet) for mechanical sweeps and search — and Codex for the heterogeneous peer (review/rescue).
  **Prompt-bearing work (product prompts, judge rubrics, eval criteria) is lead-only — never
  delegated to a weaker model.** Details: `docs/agentic-ops/harness.md` § Agent-side model routing.
- Deterministic work (date math, parsing, counting, format conversion) runs as a script or command,
  not in latent space — if the same question twice must give the same answer, compute it.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files or secrets.
- Touch only what the task requires.

# Current phase
Implementation — task `013-synthesise`.

Tasks `001-walking-skeleton` through `012-group` are complete (merged). The active
slice adds **synthesise** — EB component 9, the deep terminus, closing the chain:
over the named groups of an explicitly referenced grouping run, **per group produce
a grounded block** reporting what the findings show — **descriptive** (the
direction-spread steer: "5 of 7 positive, two null"), never evaluative, never a
weighted verdict (the ⏸ consensus seam) and never an absence claim (deep coverage
rests on the selected/extracted base and is base-labelled, never promoted to corpus
absence). Each claim is grounded via the real **`produce-grounded-block`**
mechanism — synthesise → cite → verify → write, with cite and verify mandatory:
citations are **co-emitted, never post-hoc** (claims cite member finding ids; code
resolves them to the findings' extract-verified anchors — the model never authors a
quote), verify = the **deterministic quote-presence check** against frozen chunks
**plus the LLM-as-judge grounding classifier** (single lane: exactly one of
Tier 1–4 / Unsupported-mis-cited, plus a weakly-grounded flag and free-form
rationale), repair = one bounded **reword-down** pass; on exhaustion a claim lands
**soft-flagged, never dropped, never silently promoted**. This slice is the first
real writer of the 001 information-layer substrate: real
`block`/`addressable_unit`/`annotation`/`citation` rows at **claim grain**, plus a
deterministic **pattern annotation** per block carrying the code-computed direction
spread (finding-query grade, extraction-base-labelled); mixed/unclear findings stay
visible end-to-end (the carried 011/012 requirement). Group labels/descriptions and
all finding text enter prompts as **id-keyed data records, never instructions**
(the carried 012 requirement). Gated changes riding this slice: schema (one
run-scoped `synthesis_result` table; table count 24 → 25) · public interface
(`"synthesise"` registry entry requiring an explicit `grouping_run_id` Plan/Config
field, compile-fails-closed + `run_harness synthesis_backend` and
`grounding_judge_backend`, stub defaults) · **runtime egress: two new generation
surfaces — `synthesise_block_v1` and `grounding_judge_v1`, the repo's fifth and
sixth product prompts** (finding records incl. verbatim quotes leave on the live
path; fixture corpus openly licensed). `make verify` stays deterministic and
egress-free (stub backends, sentinel-driven). Build per
`docs/tasks/013-synthesise/contract.md`. Stay within the contract's scope and stop
conditions; all other capabilities and seams remain deferred (`docs/deferred.md`).
