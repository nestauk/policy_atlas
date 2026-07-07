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
(spec-flow-backed 2026-07-07), **EB's terminal component at every depth**: it
**composes the one EB artefact** — mints it (intent-derived bounded title),
renders content into grounded blocks, binds them in section order; the
orchestrator shapes sections at plan time only (capability-composes). Two paths
build now. **Landscape path** (always): model prose over the referenced
characterisation record via `synthesise_landscape_v1`, intent as emphasis data;
typed claims deterministically validated against the record; no citations, no
judge, nothing faked. **Deep path** (when the deep chain ran): **intent-led
sections** — `synthesise_sections_v1` proposes a validated, capped section set
from intent + group summaries (fail-closed `context["synthesis"]` directive
override; groups are **input, not structure** — uncovered groups counted, never
dropped); per section `synthesise_section_v1` writes prose whose typed claims
**mix grounding modes**: finding claims (cite finding ids → extract-verified
anchors; the model never authors these quotes), **selected-set chunk claims**
(verbatim quotes from the windowed frozen text of the section's basis documents —
already in hand, no `retrieve` needed; the claimed location is untrusted,
verified spans become the citation rows; fabricated quotes rejected → excluded
and counted), and pattern claims (counts must equal computed spreads). Verify =
deterministic quote-presence against frozen chunks **plus** the
`grounding_judge_v1` judge reading cited chunks' full text (single lane, Tier
1–4 / Unsupported-mis-cited + weakly-grounded + rationale; intent shapes
emphasis, never verification); one bounded reword-down repair; exhaustion →
**soft-flagged, never dropped, never silently promoted**. Descriptive always: no
recommendations, no weighted verdicts (⏸ consensus seam), **no absence claims**.
⏸ **Corpus-wide** chunk grounding (unselected documents) lands with `retrieve`,
not here. First real writer of the 001 information-layer substrate
(`block`/`addressable_unit`/`annotation`/`citation` at claim grain);
mixed/unclear findings stay visible end-to-end; intent, group labels and all
source-derived text enter prompts as **id-keyed data records, never
instructions** (carried 011/012 requirements). Gated changes riding this slice:
schema (one run-scoped `synthesis_result` table; table count 24 → 25) · public
interface (`"synthesise"` registry entry requiring `characterisation_run_id` +
optional `grouping_run_id`, compile-fails-closed + `run_harness
synthesis_backend` and `grounding_judge_backend`, stub defaults) · **runtime
egress: four new generation surfaces — `synthesise_landscape_v1`,
`synthesise_sections_v1`, `synthesise_section_v1`, `grounding_judge_v1`, the
repo's fifth–eighth product prompts** (windowed full document text, finding
records incl. verbatim quotes, cited chunk text and user intent leave on the
live path; fixture corpus openly licensed). `make verify` stays deterministic
and egress-free (stub backends, sentinel-driven). Build per
`docs/tasks/013-synthesise/contract.md`. Stay within the contract's scope and
stop conditions; all other capabilities and seams remain deferred
(`docs/deferred.md`).
