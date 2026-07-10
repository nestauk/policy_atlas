# Verification: 017-orchestrator

Evidence for one slice. Filled at step 6 (build conversation B, 2026-07-10);
**Review findings** + **Rubric status** land after the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (okf-validate · test · typecheck · lint · build) | pass | step-6 exit run, full suite — see the exit line below |
| `make test` | pass | 950+ tests incl. the new orchestration/runner/steering/planner/CLI suites |
| `make typecheck` | pass | mypy, 107 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |

Phase gates (all green at their boundary, per the plan's binding gate map):
Phase 0 baseline full verify (904 passed) · Phase 1 full verify (schema class)
· Phase 2 full verify (reader contact) · Phase 3 verify-fast · Phase 4 full
verify (public interface) · Phase 5 verify-fast · step-6 exit full verify.

**Environment incident (recorded, not code):** during the Phase 1–2 gates the
host degraded badly (swap ~15.8 GB/17 GB exhausted; Docker Desktop's VM wedged
twice with its API returning 500s; load average peaked ~240). Two Docker
Desktop restarts recovered it. Two pre-existing tests failed under that
degradation and were root-caused rather than re-rolled — see Diff summary
items 6–7; both fixes preserve the asserted properties.

## Checks beyond the build

- **Deterministic tests** — all pass:
  - Schema round-trip + constraints for the one approved table
    (`tests/test_orchestration_plan_schema.py`, 6 tests): amendment version
    rows, duplicate-version rejection, status/payload CHECKs, cross-project
    scope FK guard.
  - Spine-by-construction + fail-closed compile
    (`tests/test_orchestration_plan.py`, 15 tests): no composable plan omits
    or reorders a spine component (3×3 axis matrix), unknown
    components/fields reject, dependency-chain violations reject, intent-fit
    strike composes validly, off-diagonal (rapid×deep, deep×landscape)
    composes, round-trip approved-payload ↔ composed-chain equivalence,
    nothing ever compiles into the synthesis section directive.
  - Runner + failure semantics (`tests/test_runner.py`, 11 tests):
    two-phase per-component run lifecycle, reference threading
    (deepest-successful, transitive), retry-once-as-new-run, spine-fail →
    honest run failure with no downstream, discretionary-fail → degrade +
    skip-with-reason + corpus-only synthesise, DB-abort → fresh-transaction
    `component.failed` backstop (idempotent), failed run ids never feed
    downstream, directive application preserves unrelated scope context.
  - Steering (`tests/test_steering.py`, 12 tests): pause-set compile pinned
    for all four modes, Frequent pauses every boundary, adjustment → new
    user-attributed plan version row + recompose, already-run adjustments
    rejected honestly, abort leaves committed components + abandoned plan +
    no artefact, Unattended never pauses + auto-resolutions flagged +
    collated, deterministic renders, steer-point triggers from persisted
    selection flags, intent-vocabulary option grammar pinned, emphasis
    rank-shift through the real select path (quality ×2.0 and
    screen_confidence ×2.5 provably reorder a fixture candidate set),
    steer-point reselect flow threads the new selection run id downstream.
  - Planner (`tests/test_planner.py`, 14 tests): stub turn shapes, ready
    drafts round-trip into registry-valid `OrchestrationPlan`s,
    suggestion-degrade rules, key-required OpenAI backend.
  - CLI (`tests/test_orchestrate.py`, 6 tests): full stub end-to-end (intent
    → plan → approval row → composed run → artefact row), landscape
    composition without the deep chain, numbered suggestion pick, abandon
    leaves no rows, validation fail-closed runs nothing, Unattended never
    pauses.
- **Live check** (contract decision 10 pin — changed surfaces + one modest
  composed run; scope not exceeded):
  - **(a) Planner-only, 7 conversations** across the V2 question-taxonomy
    categories (1 intervention · 2 topic ×2 incl. one deliberately thin · 3
    impact · 4 stats · 5 literature · 7 stakeholder); no chains run. All
    decision-10 probes observed:
    - sharp refined questions, honest assumptions + visible defaults in
      every plan (e.g. "no geography restriction applied" stated as an
      assumption rather than silently assumed);
    - **intent-fit**: the stats intent (child obesity rates, Scotland)
      composed characterise-only at landscape; the stakeholder intent
      (national narratives) composed WITHOUT the deep chain at standard
      depth, with honest per-component exclusion rationale ("not measured
      effects of interventions") — two non-intervention compositions without
      the deep chain;
    - **anchored nudge**: "deeper" on the ACEs intervention plan re-derived
      the whole plan standard×standard (~15–30 min) → deep×deep
      (~90–100 min) with its new band;
    - **scope constraint compiled**: "last 10 years" → `filters.shared.
      published_after = 2016-01-01`; the Scotland stats intent also compiled
      `overton.publisher_country = United Kingdom`;
    - **screening criteria**: user-expressed ("exclude opinion pieces") and
      planner-suggested criteria present as visible plan fields on the
      literature + intervention intents;
    - **suggested answers**: the thin "obesity" intent drew exactly one
      shape question with 5 sensible broad→narrow suggestions; the other six
      conversations asked nothing (no question where none was
      shape-necessary);
    - **off-diagonal live**: the thin-topic conversation landed deep×landscape
      (a horizon scan) after a landscape-mapping answer.
    Two prompt defects were caught fail-closed by validation (never a silent
    run) and fixed in the lead-owned prompt during the check: the model wrote
    exclusion rationale under a compound key (`select_extract_group`), and
    paired `screen_stage2` with landscape depth — `planner_v1` now pins exact
    rationale keys and the stage-2/depth coupling. Re-runs composed validly.
    Records: planner conversation JSON (redacted transcript shapes) retained
    locally; cost ≈ 25K tokens (pennies).
  - **(b) One composed end-to-end run** — see § End-to-end command; evidence
    below.
  - **(c) Failure semantics + Unattended: test-level only** (fault-injected
    + scripted, per the pin) — no live fault probe.

## End-to-end command

```
# from the repo root, .env providing OPENAI_API_KEY/LANGFUSE_*/OVERTON_API_KEY
uv run python -m policy_atlas.orchestrate
# intent: "What interventions are effective at increasing heat pump adoption in UK homes?"
# -> approve -> Moderate run -> steer-point answered with option 3 (strongest evidence) -> continue
```

(The recorded run drove `orchestrate.main()` with a deterministic rule-based
console — same code path as the `python -m` entrypoint; transcript retained
locally.)

**Live run (b) evidence** (2026-07-10, project `91d2d684`, dev DB; transcript
+ stdout retained locally):

- **Question:** "What interventions are effective at increasing heat pump
  adoption in UK homes?" (A Sustainable Future mission). Planner proposed
  standard×standard, full discretionary set, Moderate, in ONE turn (no
  question — none was shape-necessary); assumptions included the
  publication-vs-study-geography honesty note verbatim ("'UK homes' is
  treated as ... study geography to be screened in the document text, not as
  a grey-literature publisher-country filter").
- **First attempt failed honestly** (recorded, exit 2): the planner emitted
  screening criteria >200 chars — valid on the plan model, rejected by the
  screen directive grammar mid-run. Runner behaviour was exactly decision 8:
  retry-once, honest spine failure, no downstream components, collation
  rendered. Fix: `OrchestrationPlan.screening_criteria` now enforces the
  screen grammar's caps at plan validation (compile-target parity,
  test-pinned) + a prompt rule (one short rule per criterion). Second
  attempt below.
- **Outcome:** exit 0 · plan-run status **succeeded** · **artefact minted** ·
  wall ≈ **2425 s (~40 min)** end to end.
- **Steering exercised live:** the deepening-selection steer-point paused at
  Moderate post-`select`; the **strongest-evidence** intent-vocabulary
  option was chosen → **plan version row 2** (user-attributed; v1 →
  superseded) → `select` re-ran (36.9 s / 38.1 s) → the second selection's
  `selection_provenance.directive` carries `weight_emphasis {"quality": 2.0}`
  with effective quality weight 0.25 → **0.5** (multiplier semantics, exactly
  as pinned). The landscape→synthesis crossing paused once more (Continue).
- **Plan↔chain equivalence (the audit point):** `plan.compiled` events in
  order = acquire · screen · classify · appraise · ingest_full_text ·
  screen_stage2 · characterise · select(v1) · select(v2) · extract(v2) ·
  group(v2) · synthesise(v2) — the composed chain of the approved plan, with
  `plan_version` flipping to 2 exactly at the post-steering re-run; extract's
  reference is the v2 selection run; synthesise's reference is the grouping
  run (deepest successful).
- **Per-component wall-clocks (s):** acquire 21.3 · screen 63.0 · classify
  36.2 · appraise 0.1 · ingest_full_text 107.0 (32 attempted, 22 ingested,
  5 fetch_failed, 5 parse_failed — reason-coded) · screen_stage2 47.4
  (16 confirmed, 6 demoted, 10 skipped_no_fulltext) · characterise 53.0 ·
  select 36.9 + 38.1 · extract 393.0 · group 569.2 · synthesise 1046.7.
- **Honesty labels intact:** synthesis counts/flags carry the full verdict
  lanes (tier_1 18 · tier_2 1 · tier_3 11 · tier_4 5 ·
  unsupported_mis_cited 7), citations 82 verified / 9 unverified,
  `weakly_grounded_present` / `unsupported_claims_present` /
  `groups_unsectioned` flags raised, `citations_from_unselected` 0.
  (Prose quality is explicitly 018's bar, not 017's.)
- **Band re-seed:** measured ~40 min vs the ~15–30 min target → the
  standard-depth `TIME_BANDS` rows re-seeded from this run (~30–45 min);
  the target-vs-measured divergence is recorded in the constants comment as
  the depth-seam calibration item (018/eval), per the
  displayed-band-is-measured discipline.
- One transient Overton transport error mid-acquire was absorbed with the
  backend's partial results recorded honestly in the coverage record
  (`by_backend.overton.error` populated, run still adequate).

## Diff summary

1. **`orchestration_plan` table** (the one approved schema addition) +
   alembic migration `d2f8a4c1e9b7` + constraints; six test files' stale
   `len(metadata.tables) == 25` assertions bumped to 26.
2. **`orchestration_plan.py`** — fail-closed plan model (extra="forbid",
   strict), two-axis gradation tables (search effort × analysis depth,
   contract revs 2.7–2.9), named diagonal pairings, TIME_BANDS seeded from
   the 016/015 measured anchors, spine-by-construction `compose()`, derived
   expected-artefact-shape + time band (validate-or-fill, so round-trip
   holds). Live-check fix folded in: `screening_criteria` enforces the screen
   directive grammar's caps (≤50 × ≤200 chars) at plan validation —
   compile-target parity by construction (the live run's first attempt failed
   mid-run on exactly this gap); standard-depth TIME_BANDS re-seeded from the
   measured live run.
3. **`runner.py`** — the EB capability-runner: two-phase per-component run
   lifecycle, `leg_directive` authoring seam (the LLM EB-expert drop-in),
   reference threading, retry cap, degrade/skip matrix, fresh-transaction
   failure-event backstop, check-in/pause IO seam, wall-clock dev summary.
4. **`search_loop.py`** — additive `standard` DEPTH_CONSTANTS row + per-depth
   arm selection (snowball/suggest gated off at standard). *Flagged
   deviation (minor, within contract vocabulary):* two hardcoded
   `depth == "deep"` comparisons had to widen to `("deep", "standard")` for
   the standard loop to enter the deep-round path and accumulate budgets
   across rounds — both provably no-ops for rapid/deep (same literal
   compared), test-pinned byte-identical behaviour.
5. **`screen.py`** — screening directive grammar widened fail-closed to
   `{stage?, criteria?}` (caps: 50 criteria × 200 chars); criteria compose
   into the screen's intent INPUT only; `evidence_scope.intent` never
   rewritten (DB-row isolation test).
6. **`tests/test_search_migration.py`** *(pre-existing test, fixed —
   build-revealed coupling):* the migration-roundtrip test downgraded with
   relative `"-1"` (meaning "one below the widen migration" only while that
   was head) and held seed rows in an open transaction across alembic DDL on
   a second connection — the new migration made every downgrade drop
   `orchestration_plan`, whose FK DDL deadlocked behind the uncommitted
   seeds. Restructured: explicit pre-widen revision target; seeds strictly
   after DDL in their own rolled-back transactions. Property asserted
   unchanged.
7. **`tests/test_ingest_full_text.py`** *(pre-existing test, fixed):* the
   lapsed-deadline sibling test used `parse_timeout=5.0`, but the deadline
   clock starts at `proc.start()` and includes child spawn + package import —
   >5 s under host load, mislabelling a healthy worker as the very timeout
   the test rules out. Raised to 20 s; the asserted property (a
   lapsed-deadline sibling's buffered `ok` must be honoured) is unchanged.
8. **`steering.py`** — pause-set compile, SteeringResponse vocabulary,
   deterministic renders, bounded adjustment application → user-attributed
   plan version rows, abort, Unattended auto-resolve + flags, collation;
   deepening-selection triggers/options/reselect (task 7).
9. **`planner_prompt.py`** (lead-authored, the slice's one new prompt
   surface) · **`planner.py`** (OpenAI/stub backends, suggestion degrade) ·
   **`orchestrate.py`** (the one approved CLI entrypoint).
10. **Spec flow-back** — execution-orchestration § Steering modes gains
    Unattended (pre-declared-visible-defaults path) + log.md entry; ADR 0014
    already carried the refinement. **deferred.md** — harness failure-event
    gap discharged for the product path (both entries), boost-v2 adjudication
    recorded, enum spelling fixed, new 017 seams section, tag-consolidation
    trigger sharpened.

**Flagged deviations (visible, per task-cycle-build § minor deviations):**
- Skipped components carry their skip reason in `RunPlanOutcome` + the
  end-of-run collation, not the event log — the event substrate requires a
  run id (composite FK) and a skipped component has no run; the same
  substrate constraint the contract already adjudicated table-first for plan
  events (rev 2.5 blocker 2).
- Steer-point emphasis/nomination adjustments apply at the **commit layer**
  (the selection directive, captured in `selection_result.
  selection_provenance.directive`) rather than as plan-payload fields — the
  plan model deliberately carries only the coarse budget (decision 4); the
  user-attributed plan version row records the steering event (decision 6's
  provenance rule). The v2 row's payload is therefore structurally unchanged;
  attribution + the re-run's provenance carry the substance. Review should
  confirm this placement.
- The live-check prompt fixes (rationale-key vocabulary; stage-2/depth
  coupling) were made mid-check to the lead-owned prompt and the affected
  conversations re-run — logged here as observation→change pairs.

## Review findings

Review stack ran 2026-07-10 (step 7, fresh conversation). Lanes: contract
verifier (Opus, read-only) · `/code-review` medium (8 finder angles,
per-angle pathspecs) · security auditor · Codex adversarial (family-flip:
scoped to the Claude-written surfaces; Codex authored tasks 2/3/4/6) ·
live-trace content review (lead) · OKF (in `make verify`). Live-run economy
pin honoured: no live re-run; all live claims verified against the recorded
transcripts + dev DB `91d2d684` (plan rows, `plan.compiled` chain, selection
provenance) — every one corroborated.

**Convergent (cross-family, high-confidence) — adopted & fixed:**
- **Screen-criteria silent truncation** (Codex HIGH + security MEDIUM,
  proven empirically): a long `question` + valid criteria composed past
  `SCREEN_INTENT_MAX=2000` and criteria silently vanished at prompt assembly
  while the plan row claimed they governed screening. Fix: plan validation
  now composes the real screen intent (same composer) and rejects when it
  exceeds the cap — compile-target parity extended from per-criterion caps
  to the composed whole; test-pinned.
- **Planner history-window/first-turn coupling** (`/code-review` finder A +
  security lane): guarded with a module assert
  (`(MAX_PLANNER_TURNS-1)*2+1 <= PLANNER_HISTORY_TURNS_MAX`); not reachable
  at the current constants (max 19 turns at call time vs window 20).

**Unique-to-one-lane — adopted & fixed:**
- **Steering round-trip rejected legitimate minimal deltas** (`/code-review`
  finder A, verifier-CONFIRMED; the top correctness finding): `compose()`
  always injects sibling keys (acquire `depth`, screen_stage2 `stage`), and
  `_validate_delta_round_trip`'s raw `!=` rejected any partial-key
  adjustment (e.g. criteria-only on screen_stage2) with
  `SteeringAdjustmentError`; no test covered a partial delta. Fix:
  containment semantics (`_delta_contains`) — the recompiled delta must
  contain the request; inexpressible requests still fail closed. Both
  directions test-pinned, incl. a full-runner partial-delta adjustment.
- **Unattended `steer_point_defaults` unreachable via the product path**
  (contract verifier, MAJOR): the runner honoured the field but
  `PlanDraftWire` couldn't carry it, so no planner conversation could ever
  populate it — every product-path Unattended run fell back to the
  `unconfigured_default` flag, and the prompt promised a field the model
  could not emit. Fix: wired through the draft (`PlanDraftWire.
  steer_point_defaults`), prompt vocabulary added (lead-authored), and the
  steer-point *name* registry pinned fail-closed (`STEER_POINTS`) — which
  immediately caught two test fixtures declaring `"deepening-selection"`
  (hyphen) against the runtime's `"deepening_selection"` (underscore): a
  declared default that could never have matched, silently indistinguishable
  from the fallback. Fixtures corrected; end-to-end wire test added.
- **Turn-cap exhaustion masked as user abandonment** (Codex MEDIUM,
  confirmed): `EXIT_NO_PLAN` was defined but never returned. Fix:
  `_plan_conversation` now distinguishes `"abandoned"` from `"no_plan"`;
  exit 2 on non-convergence; test-pinned.
- **NUL scrub gap on nested draft fields** (`/code-review` finder A):
  `_scrub_turn` scrubbed only reply/question; a NUL in any plan-draft field
  would pass plan validation and crash at JSONB insert. Fix: recursive
  scrub of the draft (reuses `extract._scrub_nul`); test-pinned.
- **Terminal-escape injection at the approval gate** (security LOW):
  planner output printed raw; escape sequences could rewrite the very plan
  lines under approval. Fix: `StdConsole.print` strips C0/C1/DEL (bar
  `\n`/`\t`); test-pinned.
- **`publisher_country` unbounded + `backend_scope` cross-check missing**
  (security LOWs): plan-valid `academic_only` + `publisher_country` failed
  mid-run (the exact plan-valid/run-fail shape decision 8 exists to avoid),
  and the value was an unbounded free string. Fix: length/charset caps +
  a model-validator cross-check mirroring the steering path; test-pinned.
- **Cleanup** (`/code-review` cleanup angles + contract verifier MINOR):
  `runner.SPINE_COMPONENTS` now derived from `SPINE` (was an independent
  literal that could drift and silently change run-status semantics);
  `steering._clip_components_to_depth` reuses `_enabled_components` (was a
  divergent copy); shared `_persist_new_plan_version` helper (two
  near-identical supersede/insert blocks); `events.read_for_run` replaces
  two unbounded whole-project event reads per component attempt; dead
  `declared_hatches` field deleted (rev 2.9 dissolved the hatch; the
  contract sanctions exactly one non-executing field).

**Adjudicated — declined or deferred (with reasons):**
- **Commit-layer steer-point placement** (flagged deviation 2; Codex HIGH
  independently converged with the lead's trace lane): CONFIRMED as
  designed — decision 4 deliberately keeps the fine directive out of the
  plan payload; reconstruction works via `plan.compiled(v2)` → select
  re-run → `selection_result.selection_provenance.directive` (all durable
  tables, verified in the dev DB). Adopted as-is; the v2 row's lack of a
  *pointer* to where the substance lives is noted on the existing
  plan-provenance seam in deferred.md.
- **Skip-reason carrier** (flagged deviation 1): adopted as-is — same
  substrate constraint the contract adjudicated table-first for plan events;
  skip reasons live in `RunPlanOutcome` + collation. Durable skip-reason
  persistence rides the deferred resume/provenance seams.
- **Mid-check prompt fixes** (flagged deviation 3): adopted — logged
  observation→change pairs, affected conversations re-run.
- **Pre-existing test fixes** (diff items 6–7): confirmed by the
  removed-behaviour finder — both asserted properties preserved.
- `_reference_kwargs` if/elif ladder (altitude): declined — thin-v1; the
  deferred LLM EB-expert seam reworks directive authoring anyway.
- `CliIO`/`UnattendedIO` duplicated 2-line `check_in` (simplification):
  declined — below the action bar.
- Unattended auto-resolve firing on a skipped/failed `select` (contract
  verifier NOTE): declined — an honest, harmless flag.
- TIME_BANDS single-measured-pairing (NOTE): already the recorded 018/eval
  calibration item.
- Security INFOs (planner session rate-limiting → web-app slice; Langfuse
  host inside the user-operated boundary; `_scrub_turn` NUL-only parity):
  noted, no action this slice.

**Evidence corrections from the trace lane:** the transient Overton
transport error was in the FIRST attempt's acquire (project `128c0a81`),
recorded in the `component.completed` event's `by_backend.overton.error`
(status `ok`, run adequate) — not in the coverage record as previously
worded. The live run's synthesise flags also included the pre-existing 013
repair-lane flags (`claims_rejected_structural` · `repair_path_taken` ·
`repair_count_mismatch`) alongside the three listed — 013 honesty machinery
behaving as designed on real output. The duplicated select/group transcript
lines are the deliberate pause-context re-render (`runner.py` passes
`render_check_in` back into `pause()`).

- **`/simplify`:** skipped with justification — the `/code-review` pass ran
  dedicated reuse/simplification/efficiency/altitude finder angles and their
  adopted fixes were applied above; a separate same-family pass would
  duplicate it.
- **`/okf validate`:** green at every gate (46 concepts, 0 violations).

**Review economy (recorded honestly):** reasoning-class ≈ 305K (contract
verifier 169K · security 121K · Codex launcher 15K) vs the ≤250K proxy;
fast-worker ≈ 720K (8 scoped finders 611K · 1 verifier 55K · 1 fix worker
56K) vs the ≤500K proxy. The overrun bought a large finding set on a 9.3K-line
diff (five adopted correctness/integrity fixes, two of them cross-family
convergent); per-angle pathspecs were applied throughout.

## Rubric status

Checked after the review stack (step 7, 2026-07-10). Items 1–18: **hold** —
the contract verifier's per-item pass (its one MAJOR, the Unattended
defaults wiring gap, and its MINOR, the dead `declared_hatches` field, are
both fixed above; item 18's disclosure gap is closed by this section).
Item 19: **holds** — the Tier-3 stack ran in full (contract verifier ·
`/code-review` medium · security lane · Codex adversarial · simplification
folded into the code-review cleanup angles, recorded above); findings and
adjudications in § Review findings. Post-fix `make verify` green.

## Intent & assumptions

- The thin v1 carve per ADR 0014: deterministic runner (no LLM EB-expert),
  no resume engine, no narration surface, section-directive compile stays
  empty, boost grammar v1.
- `TIME_BANDS` are seeded from the 016/015 measured anchors + the live-check
  wall-clocks; target-vs-measured divergence is a recorded depth-seam
  calibration item for 018/eval (never silent band inflation).

## Known unverified items

- The OpenAI planner backend's live path is exercised by the live check, not
  the suite (suite is stub-only by design, zero-egress).
- `publisher_country` compile emits the planner's country string verbatim
  ("United Kingdom" observed); whether Overton's filter key expects that
  exact form is unverified against a live filtered search — recorded for 018.
- Unattended mode ran scripted (test-level) only, per the live-check pin.
- The steer-point's deepen-named-clusters option was not exercised live (the
  strongest-evidence option was); its compile is rank-shift/grammar
  test-pinned.
- The planner emitting `steer_point_defaults` (wired during review) is
  stub/test-pinned only; no live planner conversation has exercised the new
  prompt vocabulary — a planner-only probe (pennies) fits 018's refine loop.

## Public safety

- No secrets, keys, or raw fetched document text in this file or the diff.
- Planner conversation records and the live-run transcript are retained
  locally (scratchpad), NOT committed — counts, shapes and wall-clocks only
  here.
- Committed fixtures unchanged (016 discipline); the live run wrote to the
  local dev database only.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** the three flagged deviations above (skip-reason
  carrier · commit-layer steer-point placement · mid-check prompt fixes) +
  the two pre-existing-test fixes (diff items 6–7).
- **Executor provenance (family flip):** tasks 1, 5b, 5, 9, 12 = fast-worker
  (Sonnet); tasks 2, 3, 4, 6 = Codex (as planned); tasks 7, 10 =
  **deep-reasoner (Opus) — user-directed re-route mid-build (2026-07-10),
  not Codex exhaustion**; tasks 8, 11 + all briefs/reviews = lead. The Codex
  adversarial reviewer in conversation C therefore has fresh eyes on 7/10
  but authored 2/3/4/6 — scope the family-flip accordingly.
- **Diff-scoping exclusions for review:** `tests/test_orchestrate.py` /
  `test_steering.py` / `test_runner.py` scripted-IO fixtures are volume, not
  judgment — per-angle scoping per the plan's review-stack sizing.
- **Live-trace pointers:** Langfuse traces for the planner conversations +
  the composed run (2026-07-10, project ids in the local records).
- **Live-run economy (user call, 2026-07-10):** the review stack must NOT
  re-run the full composed end-to-end live run unless strictly necessary —
  it costs ~40 min wall + live spend, and this build's run is fully
  evidenced above (plan rows, plan.compiled chain, selection provenance,
  wall-clocks, honesty labels, dev-DB project `91d2d684` + Langfuse traces).
  Review lanes verify against the recorded evidence + the dev DB / traces;
  a fresh live probe needs a specific finding that the recorded run cannot
  answer. Planner-only conversations (pennies, seconds) remain fine.
- **Knowledge candidates** (one bullet per durable-seeming lesson, however
  raw):
  - Alembic migration-roundtrip tests must pin explicit revision targets and
    never hold seed rows in an open transaction across DDL on a second
    connection — any later migration whose FKs touch the seeded tables
    deadlocks (observed live: DROP TABLE blocked on an uncommitted
    evidence_scope insert; 14-minute silent hang).
  - Any test whose deadline clock starts at `Process.start()` is really
    asserting "spawn + import < deadline" — on a loaded host that inverts
    into a false failure; deadlines guarding drain logic need spawn headroom
    (5 s → 20 s here) or a start-signal handshake.
  - macOS swap exhaustion presents as *Docker daemon wedge* (API 500s, VM
    vCPU spin) long before anything names memory — check `sysctl
    vm.swapusage` first when Docker "breaks" mid-suite.
  - Structured-output planners invent compound dict keys (e.g.
    `select_extract_group`) for grouped reasoning unless the prompt pins the
    exact key vocabulary — schema `extra="forbid"` catches it, but the fix
    belongs in the prompt, and the fail-closed loop (validation error → back
    into conversation) is exactly the right recovery surface.
  - A planner told only "stage-2 fits standard/deep" will still pair it with
    landscape; cross-field constraints the schema can't express must be
    stated as hard vocabulary rules in the prompt ("ONLY available when...").
  - The event-log's run-id FK shapes what can carry audit state: anything
    that happens without a run (a skipped component, a pre-run plan event)
    needs a table-first or outcome-object carrier — the same constraint
    resurfaced three times this slice (plan lifecycle, skip reasons,
    steering events).
  - LangGraph-harness components that catch their own exceptions commit
    "failed" state cleanly; a runner layered above must distinguish
    evented-failure (committed) from escaped-exception (rolled back) — the
    two-phase run lifecycle (identity committed before work) is what makes
    the fresh-transaction backstop's FK validity trivial.
  - `weight_emphasis` values are multipliers on default weights, never
    renormalised — any steering option pinned as "target weights" would be
    wrong; rank-shift tests (prove the reorder, not the numbers) are the
    right pin for emphasis semantics.
  - Live planner latency is material (~20–30 s/turn at judgment-class):
    018's surface should stream or show progress per turn.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md): LLM EB-expert
capability agent (drop-in at `runner.py::leg_directive`) · plan-field ↔
chat-turn provenance · resume engine (idempotency-key requirement recorded) ·
steering conversational half · runner-visible usage aggregate ·
boost-grammar v2 (eval-gated) · tag-consolidation (sharpened trigger) ·
skeleton-direct harness failure-event residual.
