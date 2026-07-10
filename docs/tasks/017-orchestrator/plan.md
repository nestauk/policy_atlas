# Plan: 017-orchestrator

> **Status:** rev 2 — plan-stage adversarial review adjudicated
> (Codex, 6 findings: 2 blocker · 3 major · 1 minor, **6/6 adopted**,
> all verified in as-built code). Blockers: (1) `weight_emphasis` is
> **multiplicative** on the default weights, never renormalised
> (`select.py:439,568`) — the steer-point option constants re-pinned
> as multipliers with rank-shift tests; (2) the failure-event
> backstop needed a **two-phase run lifecycle** — the run row (+
> `run.started` + `plan.compiled`) commits in its own short
> transaction BEFORE leg work, so it survives a leg rollback and the
> fresh-transaction `component.failed` keeps FK validity
> (`schema.py:101/113`, `harness.py:579`). Majors: the screening
> directive parser rejects unknown keys (`screen.py:165-171`) — task
> 5 now owns widening the grammar to `{stage?, criteria?}`; token
> usage is trace-only as-built (backends discard `_usage`) — the dev
> summary log narrows to wall-clock, per-leg tokens read from
> Langfuse, single-line aggregation recorded as a seam (contract
> decision 11 micro-clarified, rev 2.6); task 3's brief gains the
> full per-leg run lifecycle + component reference-kwargs map (the
> 015 brief-self-sufficiency lesson). Minor: ADR 0014 ownership
> pinned — lead authors it at plan confirmation (step 4), before the
> build.
> Rev 1 drafted against contract **rev 2.5**. Plan 🛑 pending.
> Contract: [contract.md](contract.md).
>
> "Plan-pinned" constants below are THIS plan's code constants,
> reviewed at the plan 🛑 (see the contract's terminology note —
> never the orchestration plan-as-object this slice builds).

Executor routing per harness.md § Agent-side model routing: default =
delegate; every `lead` mark carries a justification. The standing
Codex-exhaustion fallback: if Codex runs out mid-build, re-route down
the ladder (judgment → deep-reasoner, mechanical → fast-worker,
brief-unwritable → lead), record substitutions in `verification.md`,
never stall.

## Plan-pinned constants

**Modules (flat, repo pattern — five new files, three touched):**

- `orchestration_plan.py` — the plan model + composer:
  - `OrchestrationPlan` (pydantic, fail-closed): `question` ·
    `scoping_notes: list[str]` · `screening_criteria: list[str]` ·
    `backend_scope` (exactly `academic_only|grey_lit_only|both`) ·
    `scope_constraints` (`published_after`/`published_before` ISO
    dates · `publisher_country` — compiled into the two-level
    `filters` grammar: recency under `shared`, geography under
    `overton` only; OpenAlex has no as-built geography key, stated
    in the plan's assumptions when a geography constraint is set) ·
    `gradation` (`lighter|standard|deeper` — internal bundle names,
    never a user-facing dial) · `components: list[str]` + `component_
    rationale` (intent-fit × gradation, visible) · `grouping_facet` ·
    `steering_mode` (`frequent|moderate|minimal|unattended`) ·
    `steer_point_defaults` (pre-declarable rules only; schema forbids
    runtime-data references by construction — a rule is
    `{steer_point: str, action: "proceed_flag"|"stop"}`) ·
    `declared_hatches` (v1: the thin-base search escalation, always
    declared) · `expected_artefact_shape` (derived, non-executing) ·
    `assumptions: list[str]` · `time_band` (derived) · `title`.
  - `GRADATION_BUNDLES` (the compile table; intent-fit strikes the
    deep chain / facet from any bundle):

    | bundle | search depth | stage-2 | characterise | deep chain | selection budget | band (derived) |
    |---|---|---|---|---|---|---|
    | `lighter` | rapid | off | on | off | — | ~10–20 min |
    | `standard` (default) | rapid (+ thin-base hatch, as-built) | on | on | on | 12 | ~30–60 min |
    | `deeper` | deep | on | on | on | 25 (`DEFAULT_SELECTION_BUDGET`) | ~90–150 min |

    Bands from the 016 verification wall-clocks (ingest 134.8 s,
    synthesise 589.9 s on a 32-doc corpus) + the demo deep-run prior
    (~95 min); worded as ranges, recomputed per composition
    (`TIME_BANDS` constant beside the bundles).
  - `compose(plan) -> ComposedChain`: ordered leg specs (component ·
    per-leg directive deltas · reference-threading rule). Spine
    enforced by construction (the leg list is built from the spine
    constant + discretionary inserts, never free-assembled);
    validation errors are caught errors, never silent runs.
- `planner.py` — `PlannerBackend` protocol · `OpenAIPlannerBackend`
  (structured outputs + Langfuse tracing inside the backend — the
  `screening_backend.py` pattern) · `StubPlannerBackend`
  (deterministic, fixture-shaped). Turn shape: `PlannerTurn {reply,
  plan_draft: OrchestrationPlan-partial, question: str|None,
  suggested_answers: list[str] (2–5, broad→narrow)|None, ready:
  bool}`. Suggestion failure degrades to a plain question.
  `PLANNER_MODEL = "gpt-5.5"` (judgment-class, contract § Model
  route; env-overridable constant, `SYNTHESIS_MODEL` pattern).
- `planner_prompt.py` — `planner_v1`, **lead-authored**:
  question-type-neutral; enough-context-to-propose; ask-only-on-shape
  (the "structure, depth, or direction" test); anchored middle-
  gradation default proposal; lighter/as-proposed/deeper re-derivation;
  scoping/criteria suggestions gated on intent-fit; never promises
  findings; assumptions first-class.
- `runner.py` — the EB capability-runner: `run_plan(engine, plan,
  backends, io: OrchestratorIO)`. Per-leg `engine.begin()`
  transactions (block-boundary commits) with the **two-phase per-leg
  run lifecycle** (rev 2, blocker 2): phase A — a short transaction
  creates the `runs` row + appends `run.started` + `plan.compiled`
  (payload incl. plan_id/plan_version + the leg's reference kwargs)
  and COMMITS; phase B — the leg's work transaction. A leg failure
  rolls back phase B only; the committed run row keeps
  `event_log`'s composite FK valid, so the fresh-transaction
  `component.failed` append + run-status update always lands.
  Reference kwargs per component (the `_run_component` map,
  productionised): select ← characterisation_run_id (+
  ranking_backend) · extract ← selection_run_id · group ←
  extraction_run_id · synthesise ← deepest successful reference.
  The directive-authoring slot
  is one function — `leg_directive(plan, leg, upstream_state) ->
  dict` (scope-context deltas per leg: search depth+filters ·
  screening stage/criteria · selection budget/emphasis/strata ·
  grouping facet) — **the named seam the future LLM EB-expert drops
  into**. Reference threading: deepest-successful + transitive
  (as-built synthesise semantics). `LEG_RETRY_CAP = 1` for LLM-bearing
  legs (screen · classify · characterise · select · extract · group ·
  synthesise; acquire owns its own round/retry machinery). Failure
  semantics per contract decision 8, including the **fresh-transaction
  failure-event backstop**: on leg exception, roll back the leg
  transaction, open a short fresh transaction, append
  `component.failed` (idempotent — check-before-insert against the
  harness's own write) + set run status. End-of-run: collation of
  flagged events + one structured dev summary log line carrying
  **per-leg wall-clocks** (rev 2, finding 4: token usage is
  trace-only as-built — every backend discards `_usage` after
  tracing, so per-leg tokens are read in **Langfuse**, where they
  already exist per call; both surfaces are developer-side, honouring
  the contract; a runner-visible usage aggregate is a recorded seam —
  arrives with a usage-return refactor or the component-progress
  protocol; contract decision 11 micro-clarified as rev 2.6).
- `orchestrate.py` — the CLI entrypoint (`python -m
  policy_atlas.orchestrate`): planning conversation loop (numbered
  suggested-answer menus + free text) → plan review → approval writes
  the `orchestration_plan` row (status `approved`, version 1) →
  project + evidence-scope creation → runner with `CliIO` (blocking
  check-ins per mode; `UnattendedIO` auto-resolves per the plan's
  rules). Live flag = `OPENAI_API_KEY` presence (skeleton precedent);
  no key → stub planner + stub chain (demo/dev path stays egress-free).
- **Touched:** `schema.py` + one alembic migration (the
  `orchestration_plan` table below) · `screen.py` (criteria input
  composition only) · `harness.py` only if the backstop needs a hook
  (prefer runner-level; harness untouched otherwise).

**The `orchestration_plan` table (the one approved schema addition):**

```
orchestration_plan(
  plan_id UUID PK,
  project_id UUID FK → project, NOT NULL,
  evidence_scope_id UUID FK → evidence_scope, NULLABLE (set at approval),
  version INTEGER NOT NULL,            -- 1..n; amendments append rows
  status TEXT NOT NULL,                -- proposed|approved|superseded|abandoned
  payload JSONB NOT NULL,              -- the validated OrchestrationPlan dump
  created_at timestamptz NOT NULL,
  created_by TEXT NOT NULL,            -- 'user'|'planner' attribution
  approved_at timestamptz NULL,
  UNIQUE (project_id, version)         -- one plan lineage per project in v1
)
```

Run linkage: `plan.compiled` event payloads gain `plan_id` +
`plan_version` — **no `runs` column** (the minimal form; a column is
not needed while events carry it). Amendment = new row at version n+1
(`created_by='user'`), prior row → `superseded`.

**Steering pause sets (mode → boundaries):**
- `frequent`: every leg boundary.
- `moderate`: the deepening-selection steer-point (post-`select`,
  pre-`extract`) + the landscape→synthesis crossing (pre-`synthesise`).
- `minimal`: the steer-point only (substance).
- `unattended`: none; the plan's rules auto-resolve; every resolution
  flagged; collation always renders at end-of-run (all modes).

Steer-point triggers (computable, from select's persisted rationale +
plan content): excluded-large-stratum (`LARGE_STRATUM_SHARE = 0.20`,
as-built) · excluded user-nominated cluster/doc (plan
`priority_strata`/`must_include_ids` vs selection rationale) ·
thin base (as-built select flags). Option mapping (contract decision
6 rev 2.5): clusters → `priority_strata` (+`must_include_ids`) ·
strongest → `weight_emphasis: {"quality": 2.0}` · most-relevant →
`weight_emphasis: {"screen_confidence": 2.5}` — **multipliers on the
default weights** (rev 2, blocker 1: `select.py` multiplies defaults
by emphasis values and sums unnormalised — there is no
renormalisation; the earlier target-weight framing was wrong).
Rank-shift tests prove each option reorders a fixture candidate set
the intended way. · budget → `budget` · as-proposed → no delta.
After adjustment: new plan version row → recompose remaining legs →
re-run `select`.

**Screening-criteria compose (contract decision 2 rev 2.5):**
`context["screening"]["criteria"]: list[str]` (length/char caps
mirroring the selection directive's `DIRECTIVE_LIST_MAX` discipline).
**The screening directive grammar widens** (rev 2, finding 3: the
as-built parser rejects any key besides `stage`, `screen.py:165-171`)
— task 5 owns the fail-closed widening to `{stage?: int, criteria?:
list[str]}`, criteria preserved alongside a stage-2 directive, with
stage-1 AND stage-2 tests. Criteria are consumed ONLY in `screen.py`
payload assembly — the intent INPUT string grows a fenced "Additional
screening criteria" block; the prompt template is unchanged;
`evidence_scope.intent` itself is never rewritten. Test-pinned isolation: criteria appear in the screen
payload; search-generation inputs and synthesise's intent read the
untouched scope intent.

**Zero-egress suite posture:** stub planner; all runner/steering/
composer tests run on stub backends + the fixture corpus; the CLI is
tested with scripted IO. `make verify` unchanged in character.

## Tasks

**Phase 0 — build-open baseline (full `make verify`)** — operator/lead.

**Phase 1 — schema + plan model + composer (full `make verify` gate —
schema class, mandatory)**
1. `orchestration_plan` table (`schema.py`) + alembic migration +
   schema round-trip tests. — **fast-worker** *(exact DDL above;
   mechanical)*
2. `orchestration_plan.py`: model + `GRADATION_BUNDLES` + `compose()`
   + expected-shape/time-band derivation + validation; tests pinning
   spine-by-construction (no composable plan omits/reorders a spine
   leg), fail-closed unknowns, intent-fit strike behaviour,
   steer-point-defaults schema (pre-declarable rules only), round-trip
   (approved payload ↔ composed chain equivalence). — **codex**
   *(judgment-bearing model/composer coherence; machine-verifiable
   done = the contract's acceptance list; seam DESIGN — fields,
   signatures, bundle values — is lead's and already pinned above)*

**Phase 2 — the EB capability-runner (full `make verify` gate —
reader contact: task 5 touches `screen.py`)**
3. `runner.py` core: chain walk with the **two-phase per-leg run
   lifecycle** (run row + `run.started` + `plan.compiled` w/
   plan_id/version + reference kwargs committed before leg work — the
   constants block pins the shape and the per-component kwargs map),
   reference threading, `leg_directive` authoring slot, retry cap,
   degrade/skip matrix, end-of-run collation + the wall-clock dev
   summary log. `run_harness` stays a one-component dispatcher — the
   runner owns everything `skeleton._run_component` does today, per
   plan, per leg. — **codex** *(the slice's core; multi-constraint
   coherence; fault-injection tests specced below make done
   machine-verifiable; rev 2 — brief made self-sufficient on the run
   lifecycle, the 015 lesson)*
4. Failure semantics + the fresh-transaction failure-event backstop;
   fault-injected tests: spine-leg fail → run fail, no downstream;
   discretionary fail → degrade + deepest-successful synthesise;
   DB-abort component → `component.failed` survives on a fresh
   transaction; retry fires once. — **codex** *(same subsystem as 3,
   separate brief so each has one concern)*
5. `screen.py`: screening-directive grammar widening (`{stage?,
   criteria?}`, fail-closed, caps per the constants block) + criteria
   input composition + isolation tests (screen payload gains the
   block at stage 1 AND stage 2; a criteria+stage-2 directive
   round-trips; search-generation + synthesise inputs provably never
   see criteria). — **fast-worker** *(exact spec + test list; rev 2 —
   grammar widening made explicit, finding 3)*

**Phase 3 — steering core (`make verify-fast` gate — new-module logic
over Phase-2 seams, no schema/reader contact)**
6. Mode → pause-set compile · deterministic check-in renders (reuse
   the `skeleton.py` render-helper pattern) · bounded adjustment
   application (grammar-validated → plan version row → recompose
   remaining legs) · abort · Unattended auto-resolve + flags ·
   end-of-run collation render. — **codex**
7. Deepening-selection steer-point: trigger computation, option
   mapping per the pinned table, select re-run flow, honest
   "not yet" refusals. — **codex** *(separate brief: reads select's
   rationale shape)*

**Phase 4 — planner + CLI (full `make verify` gate — public
interface lands; end-to-end integration)**
8. `planner_prompt.py` (`planner_v1`). — **lead** *(prompt-bearing —
   AGENTS.md rule; the one non-delegable authoring task)*
9. `planner.py` backends (OpenAI structured-output + stub + tracing —
   mirrors `screening_backend.py`/`classification_backend.py`
   exactly) + turn-shape tests + suggestion-degrade tests. —
   **fast-worker** *(pattern-mirroring mechanical)*
10. `orchestrate.py` CLI: conversation loop, menus + free text, plan
    review/approval → plan row, runner invocation with `CliIO`/
    `UnattendedIO`, exit codes; scripted-IO tests (incl. a full stub
    end-to-end: intent → plan → composed run → artefact row). —
    **codex** *(multi-file integration; scripted-IO done)*

**Phase 5 — flow-back + records (`make verify-fast` gate — docs +
ledger only)** *(ADR 0014 is NOT here — rev 2, finding 6: the lead
authors it at plan confirmation, step 4, committed on the branch
before the build opens; Phase 5's spec/ledger edits reference it.)*
11. Spec refinement: execution-orchestration § Steering modes gains
    Unattended (pre-declared-visible-defaults path, firm principle's
    purpose preserved) + `log.md` entry. — **lead** *(spec prose is
    design-bearing)*
12. `deferred.md` sweep from the lead's list: discharge the harness
    failure-event entry (if task 4 shipped it) · boost-v2 adjudication
    note · LLM EB-expert capability-agent seam (the `leg_directive`
    drop-in) · plan-field↔chat-turn provenance seam · resume-engine
    idempotency note · backend-enum spelling fix (line ~191) ·
    tag-consolidation sharpened trigger · steering conversational-half
    seams. — **fast-worker** *(mechanical edits from an exact list)*

**Phase 6 — step-6 exit (full `make verify`, mandatory) + the live
check + `verification.md`** — **lead** *(operational judgment; the
live check is the lead's hands on the product path)*.

## Live-check script (contract decision 10 pin)

(a) **Planner-only** (no chains): six conversations sampled across
the V2 question-taxonomy categories. Reviewed for: sharp question ·
honest assumptions/defaults · intent-fit composition (≥1
non-intervention intent composes without the deep chain) · one
anchored-nudge re-derivation with its new band · one scope constraint
landing as compiled filters · one screening criterion visibly
composed · suggested answers present and sane, absent when no
question was shape-necessary. Cost: pennies (planner turns only).
(b) **One composed end-to-end run**: real Nesta-mission question,
`standard` bundle, **Moderate**; the deepening-selection steer-point
exercised live with one intent-vocabulary option (plan version row
observed); plan↔chain equivalence from the audit trail; per-leg
wall-clocks + dev token roll-up recorded; artefact honesty labels
spot-checked. Expected wall: ~30–60 min; cost: low single-digit
dollars (mini-class legs + judgment-class planner/synthesis).
(c) Failure semantics + Unattended: **test-level only** (Phase 2/3
fault-injected + scripted tests) — no live fault probe.

## Review-stack sizing (for conversation C)

Medium `/code-review` with per-angle diff scoping (composer · runner
failure paths · steering compile · planner/CLI); **one** security
lane headlined by: planner prompt-injection posture, plan-compile
fail-closed completeness, the rev-2.5 sequencing invariant, and the
criteria-isolation property; contract-verifier (Opus); Codex
adversarial family-flip. Budget ≤250K reasoning / ≤500K fast-worker
(016 overshot the fast-worker proxy at 1.07M — scope angles tighter;
the corpus-relocation exclusion lesson generalises to excluding
fixture/scripted-IO test data from review diffs).

## Gate consolidation summary

| Boundary | Gate | Why |
|---|---|---|
| Phase 0 open | full `make verify` | mandatory baseline class |
| Phase 1 exit | full `make verify` | schema migration (mandatory class) |
| Phase 2 exit | full `make verify` | reader contact (`screen.py` input assembly) |
| Phase 3 exit | `make verify-fast` | new-module steering logic only |
| Phase 4 exit | full `make verify` | public interface + integration seam |
| Phase 5 exit | `make verify-fast` | docs/ledger only |
| Phase 6 exit | full `make verify` | step-6 exit (mandatory class) |

Five full-verify gates on a five-code-phase slice — no two adjacent
full gates carry the same signal; the two fast gates are argued above.
