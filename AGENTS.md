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
Implementation — task `012-group`.

Tasks `001-walking-skeleton` through `011-extract` are complete (merged). The active
slice adds **group** — EB component 8, facet-level theming, the step between extract
and synthesise: over the findings of an explicitly referenced extraction run, group
on the **intent-derived facet** — in v3.0 one of the schema's source-named
references (**intervention | outcome | population**), never v2's fixed four;
mechanisms/barriers stay landscape-only until the `implementation_context_finding`
seam lands. This is the chain's **second clustering** (topic-level at characterise;
facet-level over extracted findings here) and, like the first, an **interpretive
shape, not a count** — softest provenance grade, additionally inheriting the
extraction dependency. Groups are **run-local execution state** (capability.md §
Cluster persistence): one run-scoped `grouping_result` roll-up row; memberships
never promote to canonical state, findings are never mutated, no tags written.
Mechanically: the LLM partitions the **distinct facet values** (id-keyed data
records, schema-constrained), membership then derives deterministically
value → findings; exhaustiveness is code-enforced with a counted `ungrouped`
residual (plus `no_value` for null-facet findings) — no catch-all label, nothing
silently dropped; **mixed/unclear findings are first-class members** (the carried
011 requirement). Every group is countable against its base: the grouped set is
exactly the referenced run's finding set (memo-reused included), test-enforced.
Gated changes riding this slice: schema (one run-scoped table —
`grouping_result`; table count 23 → 24) · public interface (`"group"` registry
entry requiring an explicit `extraction_run_id` Plan/Config field,
compile-fails-closed + `run_harness facet_grouping_backend`, stub default) ·
**runtime egress: the `group_facet_v1` generation surface — the repo's fourth
product prompt**, over source-named facet values (source-derived text; fixture
corpus openly licensed). `make verify` stays deterministic and egress-free (stub
backend, sentinel-driven). Build per `docs/tasks/012-group/contract.md`. Stay
within the contract's scope and stop conditions; all other capabilities and seams
remain deferred (`docs/deferred.md`).