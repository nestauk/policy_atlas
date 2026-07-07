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
Implementation — task `011-extract`.

Tasks `001-walking-skeleton` through `010-select` are complete (merged). The active
slice adds **extract** — EB component 7, Tier-1 extraction, the step `select` gates:
per selected document, extract **`intervention_outcome_finding`** records — the
framework's first reusable findings-layer schema. Grain: one *(intervention, outcome,
effect)* claim grounded in a **single source**; intervention/outcome/population are
**source-named references**, never canonical entities. **Base fields only** (what the
source reports — effect direction/size/type, uncertainty, p-value, design/N/k/I²,
population, causality-by-design, primacy/prevalence); question-relative judgements
(normalised magnitude, causal weighting, is-beneficial) are Impact/VfM enrichment and
stay out. Findings are **durable information-layer records** (unlike run-local
characterisation/selection rows), memoised by *(source snapshot, extraction
fingerprint)* — reuse checked before any call; the extraction *service* and evidence
dataset snapshots stay recorded seams. Every finding **anchors to frozen source
text** (verbatim quote + chunk reference, deterministically checked at write,
flagged-not-dropped on failure); `abstract_only` docs are extracted from the envelope
abstract, basis-flagged, never skipped. Per-source fan-out with windowed id-keyed
segment records, pre-run call budget, per-doc honest failure
(`extraction_failed`, reason-coded — never partial, never silent); doc-level statuses
`extracted | no_findings | extraction_failed` cover exactly the selected set
(invariants test-enforced); coverage states are never phrased as absence. Gated
changes riding this slice: schema (three tables — `source_extraction_record` ·
`intervention_outcome_finding` · `extraction_result`, project-scope-guarded; table
count 20 → 23) · public interface (`"extract"` registry entry requiring an explicit
`selection_run_id` Plan/Config field, compile-fails-closed + `run_harness
extraction_backend`, stub default) · **runtime egress: the `extract_iof_v1`
generation surface — the repo's third product prompt and its first over full document
text** (frozen chunks, windowed; fixture corpus is openly licensed). `make verify`
stays deterministic and egress-free (stub backend, sentinel-driven). Build per
`docs/tasks/011-extract/contract.md`. Stay within the contract's scope and stop
conditions; all other capabilities and seams remain deferred (`docs/deferred.md`).