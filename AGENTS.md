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
Implementation — task `008-full-text`.

Tasks `001-walking-skeleton` through `007-acquire` are complete (merged). The active slice
adds **full-text ingestion** — the post-screen Tier-0 step: for a scope's screened-in
acquired sources, resolve candidate URLs from the provider fields task 007 retained, fetch
through a `DocumentFetcher` seam (v3.0: fixture replay of committed real, openly-licensed
documents — zero runtime egress; the live fetcher stays behind the egress gate), parse
structure-aware (PDF via `pymupdf4llm` — meets the couple-of-minutes-per-run wall-clock
target; docling ML-layout escalation and time-budget-aware parser selection are recorded
seams; HTML via `trafilatura`), segment under named versioned policies with
page/heading-path chunk locators, and
attach the resulting immutable `full_text` snapshot to the corpus document via
`project_source_snapshot.full_text_snapshot_id`. **Never truncate** — full text or an
honest, reason-coded failure; a failed source stays on the text in hand with a queryable
`full_text_status`. Ingestion fans out per document over a bounded process pool with
deterministic results. Vectorisation is deferred to the slice where vectors are first read.
Three gated changes ride this slice (schema columns · `pymupdf4llm` + `trafilatura`
dependencies · `run_harness` `document_fetcher` parameter). Build per
`docs/tasks/008-full-text/contract.md`. Stay within the contract's scope and stop conditions;
all other capabilities and seams remain deferred (`docs/deferred.md`).