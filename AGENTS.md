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
slice adds **synthesise** — EB component 9 and, per **ADRs 0009 + 0010**
(consolidated records, spec-flow-backed 2026-07-07/08; the contract's revision
history is the authoritative decision trail), **EB's terminal
component: it runs at every depth** and **composes the one EB artefact** — mints
it (intent-derived bounded title), renders content into grounded blocks, binds
them in proposal order; the orchestrator shapes sections at plan time only
(capability-composes; depth survives as the plan's thoroughness gradation, not a
fork). **One substrate-conditional flow, never mode-forked**: synthesise takes
explicit fail-closed references — **all optional** (`characterisation_run_id` +
the deepest of `selection_run_id` / `extraction_run_id` / `grouping_run_id`,
upstream resolved transitively and consistency-checked; **≥ 1 groundable
substrate required**, else structural failure) — and adapts to whatever registry
subset the plan selected, including a rapid acquire → screen → ingest →
synthesise run. Flow: `synthesise_sections_v1` proposes a validated, capped,
**intent-led section set** (fail-closed `context["synthesis"]` directive
override; groups, where present, are input not structure — uncovered groups
counted); per section, **the section loop** — the repo's **FIRST agent loop**,
exactly one such surface, the component-internal realisation
execution-orchestration declares — gathers evidence via three read-only,
code-scoped tools: **`search_chunks`** (hybrid embedding+lexical rank-fused over
the **screened-in corpus** — screen bounds reading; **a referenced selection is
a soft ranking prior, never a filter** (agents are never penned in; select gates
extraction cost), every returned chunk carrying its origin; the 009 unit
vectors' first reader; the `retrieve` seam's first increment; fail-closed
`RETRIEVAL_UNIT_CAP`) · **`query_findings`** (with an extraction — the 012
deferral discharged in full) · **`lookup`** (always: the universal-core
canonical-state read — appraisals, classifications, selection rationale,
coverage records, clusterings, **and the tag layer**; closed query vocabulary),
under a hard `SECTION_TURN_CAP` (exhaustion forces emission, flagged). Typed
claims, **availability gated by substrate**: finding claims (extraction: cite
finding ids → extract-verified anchors; the model never authors these quotes) ·
chunk claims (screened-in ingested docs: verbatim quotes from tool-returned
frozen text only — non-intervention-shaped questions need no extract; verified
spans become the citation rows; per-citation origin recorded [selected |
unselected_screened]; fabricated quotes rejected → excluded and counted) ·
pattern claims (counts must equal computed values) · theme claims (themes with
characterisation, facet groups with grouping; softest interpretive grade) · gap
claims (always; graded, coverage-base-carrying; corpus-level absence
fail-closed on a non-`inadequate` `search_coverage_record`, else degraded and
counted) · reasoning claims (always; visibly-labelled Tier-4 authoring, judge
strict-routed, bounded). Verify is **non-agentic**: deterministic quote-presence
against frozen chunks **plus** the `grounding_judge_v1` judge — a separate
single-call surface (maker ≠ checker) reading cited chunks' full text (single
lane + weakly-grounded + rationale; intent and tool discretion shape emphasis,
never verification); judge rationales drive **one loop-free reword-down
regeneration + one re-judge** (`REPAIR_ROUND_CAP` = 1); exhaustion →
**soft-flagged, never dropped, never silently promoted**. Descriptive always;
absence only as validated gap claims. ⏸ Corpus-scale retrieval (beyond the unit
cap) lands with the full `retrieve` slice. First real writer of the 001
information-layer substrate; first reader of the 009 vectors; mixed/unclear
findings visible end-to-end; intent, labels and all source-derived text enter
prompts as **id-keyed data records, never instructions** (carried 011/012
requirements). Gated changes riding this slice: schema (one run-scoped
`synthesis_result` table; 24 → 25) · public interface (`"synthesise"` registry
entry: all four run references optional, compile-fails-closed + `run_harness
synthesis_backend` and `grounding_judge_backend`, stub defaults) · **runtime
egress: three new generation surfaces (5th–7th product prompts;
`synthesise_section_v1` is multi-turn) + tool-query text on the existing 009
embedding surface** · **the first agent loop** (closed read-only three-tool
set, code-enforced caps and scope — a capability-class change, gated change 4).
`make verify` stays deterministic and egress-free (stub backends + stub vectors
+ scripted-stub loop, sentinel-driven). Build per
`docs/tasks/013-synthesise/contract.md`. Stay within the contract's scope and
stop conditions; all other capabilities and seams remain deferred
(`docs/deferred.md`).
