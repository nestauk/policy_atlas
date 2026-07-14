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
Implementation — task `023-codebase-health` (design in progress,
2026-07-14). A behaviour-preserving pre-eval cleanup slice built
from the owner-adjudicated whole-codebase review
(`docs/tasks/023-codebase-health/review-findings.md` — six review
lanes + a lead naming/structure re-sweep, all findings adjudicated
2026-07-14): dead-code cuts (~830 lines + the adjudicated echo-chain
cut), IOF/ICF naming symmetry (iof_/icf_ module pairs), the
capability-aware package regroup (`runtime/` ·
`evidence_base/{sourcing,screen,corpus,extract,group,synthesis}` ·
`core/` — owner-named, monorepo/CDK-aware), embeddings.py client/usage
split, test pre-hardening (string-path patch sites, country-filter
fail-closed rows, search-generation wire test), docs truth (README
rewrite, prompt-pin corrections), the three approved dependency
edits (declare lxml+pymupdf, raise stale floors, prune
[tool.pyright]), three adopted wall-clock optimisations (group
assignment concurrency, appraise bulk insert, sumprod cosine), and
**skeleton retirement** — `orchestrate` (no-key stub mode, scripted
console) is the standardised smoke + live-check vehicle from this
slice on. Tier 3 (deps hard gate). Design and build run in the
review conversation by owner decision; the review stack runs
fresh.

Tasks `001-walking-skeleton` through `022-synthesis-refinement` are
complete (merged) — the EB chain runs end-to-end live behind the
thin v1 orchestrator with prose-first synthesis output shape v2
(ADR 0015), select at standard depth, fail-closed country
filters/groups, IOF schema v2 (ADR 0016), the ICF second finding
schema + kind-typed `query_findings` + kind-spanning membership
bridge (ADR 0017), multi-facet grouping on the shared two-stage
clustering engine + the 022 cost/surface work (ADR 0018, −49%
synthesis cost), and the pinned prompt surfaces (`planner_v5`,
`extract_iof_v7` + vetter, `extract_icf_v2` + vetter,
`synthesise_section_v7` (v6 frozen as the cost-harness baseline),
`synthesise_sections_v2`). 018 trailing lanes: **C4 demo surface**
(codex lane, throwaway `demo-live-run` branch — never merges) and
**D2 rehearsal** (owner-scheduled). After 023: the eval slice
(cost as a first-class axis), then Bedrock, then the workspace
cluster. All other seams remain deferred (`docs/deferred.md`).

