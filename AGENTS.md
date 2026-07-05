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

Tasks `001-walking-skeleton` through `008-full-text` are complete (merged). The active
slice adds **characterise** — the EB shallow terminus (component 5) — and **opens the
runtime-egress gate on both fronts** (user-confirmed): **embeddings** (an
`EmbeddingBackend` protocol; live OpenAI `text-embedding-3-small`; eager-and-uniform
chunk-grain vectorisation at ingest, landed ahead of its first reader as an approved
exception — chunk vectors are certain retrieval/synthesis substrate) and **generation**
(the repo's first product prompts: the `characterise_grouping_v1` discovery+assignment
pair, lead-authored, co-versioned).
Characterise itself: deterministic **coverage distributions over Tier-0 columns**
(metadata-grounded patterns, base = the scope's screened-in set, flag-not-block) and
**thematic grouping via a bounded two-stage LLM procedure** — discover themes (one
judgment-model call over all titles/abstracts), then assign each document against the
fixed theme list (batched concurrent cheap-model calls), schema-constrained throughout,
**code-enforced per-batch exhaustive assignment** with targeted per-batch repair, an
honest counted `unclustered` bucket, a call budget known before the run
(`1 + ceil(n/batch) + repairs`), no placeholder themes or silent drops representable
(v2's theming defects structurally closed). Groupings are run-local,
never canonical; theme names persist as typed topic/theme tags. The **tag layer lands
with assertion provenance** (`source_tag.asserted_by`): acquire materialises provider
topical assertions (OpenAlex topics/SDGs; Overton topics/classifications/LLM themes) as
provenance-classed tags, and coverage aggregates the tag layer by
`(tag_type, asserted_by)` — provider, provider-LLM and own-capability assertions never
mix. The **injection posture
comes due here** (first slice where third-party corpus text enters an LLM prompt —
id-keyed data records, constrained schema, no tools). Durable output = a run-scoped
characterisation row + `source_tag` rows + a structured **landscape summary** in the
`component.completed` payload (the future steer-point/orchestrator-chat relay surface).
**No artefact/blocks here** — the single EB artefact is composed at the run terminus by a
later composition slice. `make verify` stays deterministic and egress-free (stub embedder
+ stub grouper); live is explicit wiring + env key. Gated changes ride this slice
(schema: `chunk_embedding` · `characterisation_result` · `source_tag` · dependency:
`openai` · `run_harness` `embedding_backend` parameter · **runtime egress: embeddings +
the grouping generation call**). Build per `docs/tasks/009-characterise/contract.md`.
Stay within the contract's scope and stop conditions; all other capabilities and seams
remain deferred (`docs/deferred.md`).