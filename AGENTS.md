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
Implementation — task `009-characterise`.

Tasks `001-walking-skeleton` through `008-full-text` are complete (merged). The active slice
adds **characterise** — the EB shallow terminus (component 5) — and, because its clustering
is the system's first vector reader, the **embed seam** comes due with it: an
`EmbeddingBackend` protocol with a **live provider implementation (OpenAI
`text-embedding-3-small` — the slice that opens the runtime-egress/inference gate)** plus a
deterministic stub for tests; **eager-and-uniform vectorisation at ingest** (every
ingestion path embeds its chunks; absence of an embedding row = pending, idempotent
backfill). Characterise itself: deterministic **coverage distributions over Tier-0
columns** (metadata-grounded patterns, base = the scope's screened-in set, flag-not-block)
and **topic-level clustering** over document embeddings via HDBSCAN with an honest
`unclustered` noise bucket (run-local, never canonical; deterministic c-TF-IDF labels
persist as topic/theme tags — LLM labelling is a recorded seam). Durable output = a
run-scoped characterisation row + `source_tag` rows + a
structured **landscape summary** in the `component.completed` payload (the future
steer-point/orchestrator-chat relay surface). **No artefact/blocks here** — the single EB
artefact is composed at the run terminus by a later composition slice. Gated changes ride
this slice (schema: `chunk_embedding` · `characterisation_result` · `source_tag` ·
dependencies: `openai`, `scikit-learn` · `run_harness` `embedding_backend` parameter ·
**runtime egress: live embedding calls**). Build per `docs/tasks/009-characterise/contract.md`. Stay
within the contract's scope and stop conditions; all other capabilities and seams remain
deferred (`docs/deferred.md`).