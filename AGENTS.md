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
Implementation — task `014-llm-screen-classify`.

Tasks `001-walking-skeleton` through `013-synthesise` are complete (merged) —
the EB chain runs end-to-end, terminus included. The active slice is the
**first of the live-demo path** (014 LLM screen+classify → 015 live search →
016 live fetch/ingest → 017 demo dress-rehearsal → eval slice): it replaces
the deterministic `screen` and `classify` stubs with **live LLM tools**
behind two new backend seams (`ScreeningBackend` · `ClassificationBackend`,
stub defaults — `make verify` stays deterministic and egress-free). Screen
becomes a real recall-oriented relevance filter over the metadata envelope
(title + abstract, `screen_basis` computed in code, fail-open on missing
abstract; judged against the scope intent as id-keyed data); classify
becomes a real evidence-type classifier over the closed 9-value list
(intent-free — classification is a property of the document), consuming
structured provider priors as data fields, **plus** its spec-required
second output: bounded methodological/structural tag proposals into
`source_tag` (`asserted_by='classify'`,
`tag_type='methodological_structural'`). Gated changes riding this slice:
**runtime egress** (two new generation surfaces, `screen_v1` ·
`classify_v1`, the 8th/9th product prompts — the first product LLM read of
acquired third-party text; injection posture from task 007 decision 9 comes
due) · **public interface** (`run_harness` gains `screening_backend` +
`classification_backend`) · **schema** (one CHECK-widening migration on
`ck_stag_tag_type`; no new tables). Build per
`docs/tasks/014-llm-screen-classify/contract.md`. Stay within the
contract's scope and stop conditions; live search/fetch and all other
seams remain deferred (`docs/deferred.md`).

