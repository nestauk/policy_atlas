# Verification: 024-steering-surface

Evidence for the 024 build (steps 5–6). Build ran 2026-07-16 across seven
committed phases on `task/024-steering-surface`; the plan's gate map was
followed exactly (five full gates / three fast gates). Review findings +
rubric status are added by conversation C (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` (via `make verify`) | pass | 1767 passed, 0 failed (baseline was 1320 — +447 tests this slice) |
| `make typecheck` | pass | mypy clean, 180 source files |
| `make lint` | pass | ruff clean |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | 77 concepts, 0 violations (spec flow-back validated) |
| Migration roundtrip | pass | `a3c6f9e2b7d4` downgrade → v1-shaped seed → upgrade → downgrade → upgrade (`tests/core/test_capability_run_migration.py`) |

Per-phase gates (all green at their commits): Phase 1 full (1340) ·
Phase 2 fast (1558) · Phase 3 full (1589) · Phase 4 fast (1649) ·
Phase 5 full (1761) · Phase 6 fast (1761) · step-6 exit full (1767).

## Checks beyond the build

- **Schema diff is exactly the approved gate**: `capability_run` +
  composite `runs` FK (decision 2) and
  `source_screening_result.screen_generation` + widened partial unique
  index (decision 7b). `event_log` untouched.
- **Deterministic acceptance-check suites** (contract § Acceptance, all pass):
  - Steering events at every path with payload completeness:
    `tests/runtime/test_steering_events.py` (pause · decision × user/
    orchestrator/standing_default deciders · rejected · refused · skipped ·
    auto-resolved) + run-id invariant unit tests.
  - **The rebuild test**: `tests/runtime/test_steering_history.py::
    test_two_walk_rebuild_from_fresh_connection` — two steered walks in one
    project reproduced from a fresh connection, payload-key partitioning
    asserted.
  - Router/watch wire-model fail-closed + confirm gate (unconfirmed never
    applies) + degrade-to-floor on backend error:
    `tests/runtime/test_router_compile.py`,
    `tests/runtime/test_orchestrator_backend.py`.
  - Watch deliberation bounds: cap = 2 enforced, `lookup`/`query_findings`
    allowlist (search/retrieve rejected), calls + digests evented, stubbed
    tools (`test_orchestrator_backend.py`, `test_injection_fixtures.py`).
  - Floor triggers over seeded rows, all decision-8 classes:
    `tests/runtime/test_steering_triggers.py` (35 tests).
  - Authored-options degrade test (authoring failure → canonical menu).
  - Parser suites for every key/channel + `standard`/absent ≡ as-built
    guards (D1/D3/D5/D6/D7/D8/D9, B1/B3/B5, B2′ emphasis).
  - B2′ fencing: `test_extraction_and_vetter_payloads_byte_identical_with_or_
    without_emphasis` (byte-level, the contract's prompt-diff evidence) +
    `test_fingerprint_excludes_emphasis_via_memo_hit` (memo reuse preserved,
    extraction backend proven un-reentered) + annotator coverage validation +
    run-scoped persistence + consumer payload marks
    (`test_relevance_annotator.py`, `test_relevance_consumer.py`).
  - Re-run modes: additive re-entry reprocesses nothing already processed;
    replacement moves references with rows intact; segment re-entry
    fault-injected (`test_segment_reentry.py`, `test_steering.py`).
  - D1 rubric override → derived `rubric_version` travels
    (`test_appraise.py` + pending-overlay run-through in `test_steering.py`).
  - Unattended (c): pinned-rule override, hard stop honoured, loudest-flag
    ordering, discretion hook consulted only with no pinned rule
    (`test_steering_unattended.py`).
  - Poisoned-input fixtures (M7/n3): hostile `query_findings` in tier-2
    deliberation, hostile finding into the annotator (all fail open/closed
    correctly), author-blind scrub equality across all four channels ×
    accept/reject (`test_injection_fixtures.py`,
    `test_relevance_injection.py`) — no real holes found.
  - Authority order: live user answer beats a standing rule
    (`test_steering_lattice.py::test_user_answer_beats_standing_declared_rule`);
    rules > orchestrator structural (hook placement test).
  - Strict-wire-schema regression (live-check finding, see below):
    `tests/runtime/test_wire_schema_strictness.py`.
- **P1 evidenced by fault-injected/deterministic tests** per the contract pin
  (the healthy live corpus did not fire it; the stub corpus fires it
  deterministically in `test_steering_unattended.py`/`test_steering_lattice.py`).

## End-to-end command

```
# from the repo root, .env providing OPENAI_API_KEY/LANGFUSE_*/OVERTON_API_KEY
set -a && . ./.env && set +a && \
PYTHONPATH=src uv run python <scratchpad>/live_check_024.py
```

The driver runs `orchestrate.main()` with a deterministic rule-based console
— the same code path as `python -m policy_atlas.runtime.orchestrate` (the
017 precedent). Transcripts + `steering_history()` JSON digests retained
locally (`live_check_024_run2.log`/`live_check_024.log` + history JSONs).

**Live evidence (pinned scope, two Moderate runs on live backends, dev DB,
2026-07-16):**

- Run A (project `105dd61a`, walk `9ef1c85e`): plan approved in one planning
  turn; **P4 sections pruned via prose** — free text → router fan-out →
  confirmation ("Nothing was refused") → confirmed adjust applied (event seq
  278) → **mode change to minimal** at the re-presentation (seq 281); the
  minimal segment's boundaries observed by the watch (clean_boundary
  events); **inexpressible intent honestly refused** (seq 274: "…not
  expressible in the steering vocabulary"). Run succeeded, artefact minted.
- Run B (project `bdd4094c`, walk `df8bd452`): **P2 free-text additive
  re-search applied** (seq 266, `rerun_mode=additive`, confirmed) → the
  acquire→characterise segment re-walk ran incrementally (2nd
  `search_coverage_record`, 23 executed queries, `already_ingested=10`,
  nothing reprocessed) → P2 re-presented once → continue. **P3 combined
  levers**: the inexpressible intent refused with a plain-language reason
  (seq 354), then "Select fewer documents and favour the strongest UK-based
  evidence" → confirmation declared "this will REDO selection, replacing the
  current one" → confirmed replacement re-run applied (seq 356); the second
  lever honestly refused under the one-cycle rule (seq 355). **The watch
  authored five run-specific options live at P2** (each grounded in real
  state: full-text coverage 9/19, theme counts, per-backend mix — the
  suggested-answers pattern at boundaries, attributed). P4's prose steer was
  mis-labelled `replacement` by the live router and **honestly demoted by the
  author-blind layer** (seqs 365-6) — the confirm gate never saw an invalid
  apply; the same steer applied cleanly in Run A. Run succeeded end-to-end.
- `steering_history()` captured from a fresh connection after each run: one
  walk story per run, every steering event payload-partitioned to its
  `capability_run_id`, `clean_boundary`/`decision_point` verdicts
  distinguishing observed from unwatched.
- Cost: two runs ≈ within the pinned ~$5–12 envelope; ~25 + ~35 min
  wall-clock. ≤20 orchestrator turns per run (gated invocation held: 13
  clean-boundary no-LLM events vs 4 decision points in each walk).

## Diff summary

Seven phases (commits `f7ab7b6` · `8afcbe1` · `ef87c69` · `4b2efde` ·
`afc9faa` · `3a25b0c` + this one), ~19k insertions:

1. **Walk identity + event chassis + projection**: `capability_run` +
   migration; six-event steering vocabulary with payload rules, run-id
   invariant, transactional pairing; `steering_history` payload-partitioned
   read model.
2. **Grammar widening**: seven keys (D1/D3/D5/D6/D7/D8/D9) + three guidance
   channels (B1/B3/B5) with fenced data-not-instructions blocks, fail-closed
   parsers, provenance, as-built guards, cross-component isolation suite.
3. **Re-run machinery**: component-parameterised replacement re-runs;
   additive segment re-entry (new bounded runner construct); generation
   supersession (generation-first effective rows, rescreen write path,
   consumer lockstep).
4. **Lattice + triggers + Unattended**: P1–P4 topology per the mode table;
   decision-8 trigger floor; deterministic P2/P3/P4 bundles; canonical
   option floors; Unattended (c) discretion with pinned-rule authority.
5. **Orchestrator seam**: `orchestrator_v1` prompt family (planning moment
   succeeds planner_v5; router; watch triage/decision/authoring);
   OpenAI/stub backends; gated invocation; deliberation loop; router
   compile→confirm→apply path; pending-overlay + mixed-grammar delta
   splitting; B2′ sibling annotator; CLI wiring; injection fixtures.
6. **Flow-back**: execution-orchestration § Steering modes & routing rule
   rewritten (decider dial, classifier-⏸ discharge, Unattended revision,
   Minimal change named); deferred.md sweep; build log.

**Flagged deviations (minor, resolved within contract vocabulary — the 007
precedent; adjudication items for step 7):**

- **`stage2_toggle` P2 option omitted** — enabling `screen_full` mid-run is a
  chain-composition change the plan grammar cannot express; honest omission
  per the annex's own rule, recorded in deferred.md (Task 11).
- **Latent silent-drop honesty bug found + fixed (15d)**: pending-extract
  deltas carrying `refresh`/`relevance_emphasis` were accepted, recorded on
  the plan version, and silently discarded at plan-mapping. Fixed by
  mixed-grammar delta splitting (plan-mappable keys → plan path; commit-layer
  keys → pending overlay) + two newly-reachable clobber guards.
- **Pending-overlay mechanism (15c)** — commit-layer directives for pending
  components (synthesis sections/boosts, appraisal rubric, characterise
  keys) now reach the component's executed directive; `plan.compiled` events
  echo the overlay. Without it the contract's grammar-widening promise ended
  at the record.
- **Live-check wire fix**: the OpenAI strict response-format rejects open
  `dict[str, Any]` wire fields (the SDK's local converter does NOT catch
  this — 400s only surface live). Fixed with transport twins carrying
  JSON-string deltas, decoded fail-closed at the seam; regression test pins
  every live wire model closed.
- **Router delta-envelope normaliser** (live-check finding): live routers
  wrap deltas in the component name or dotted family names; a tolerant
  normaliser now runs BEFORE the same fail-closed validation (widens what
  parses, never what validates). Characterise (family key == component
  name) is explicitly never unwrapped.
- **Authored-option attribution**: a user-picked watch-authored option
  stamps `decided_by=user, authored_by=orchestrator` on the decision event
  (`Adjust.authored_by` thread).
- **Minimal fired-only** is the contract's named behaviour change (spec
  flow-back names it; two tests pin it).

## Intent & assumptions

- Executor substitutions: Codex quota exhausted (verified 2026-07-16), so
  every `codex→deep-reasoner` fallback in the plan was exercised
  (codex-exhaustion rule); substitutions logged in `log.md`. Two agents were
  resumed after mid-stream API stalls; their work verified normally.
- Neither pre-authorised de-scope lever was pulled: tier-2 watch
  deliberation shipped (machinery + stubbed tools; see gaps for the live
  read executors) and criteria-changed re-screen shipped on the
  generation-supersession design.

## Known unverified items

- **Live read executors for watch deliberation are not wired**
  (`run_plan` passes `read_tools=None`): a live `insufficient` escalates
  rather than reading. The loop, cap, allowlist and eventing are fully
  proven with stubbed tools (the contract's own guidance); escalations are
  the recorded demand meter. Deferred.md carries the seam.
- **B2′ annotator not exercised live** (no live steer set
  `relevance_emphasis` — the live runs were standard-depth, extract not
  composed). Fully evidenced at test level incl. hostile-input fixtures;
  the live P3 combined-lever run steered selection instead.
- **Unattended live**: scripted tests only (per the plan's live-check pin —
  Minimal segment live, Unattended deterministic).
- Segment-reentry re-presentation boundary runs unwatched
  (`orchestrator=None` there) — contained edge, deferred.md.
- The two live-run projects remain in the dev DB (dev-side artefacts, as
  017's did).

## Public safety

Committed content is code, prompts, specs and tests with synthetic steering
text only. Live transcripts + history digests retained locally, not
committed; the quotes above are structural (event types, sequences, refusal
reasons authored by this build's own synthetic steering prose). No secrets,
no corpus text, no credentials in the diff or this file.

## Review handoff (step-7/8 inputs)

Adjudication items: the seven flagged deviations above. Executor
provenance: fast-worker (tasks 1, 3, 4, 5, 6, 10, 16b-scope, 18, 20),
deep-reasoner (tasks 2, 7, 8, 9, 11, 12, 14, 15+15b/c/d, 16a, 17), lead
(13, 19, gates, live check, wire/normaliser/attribution fixes). Diff-scoping
per plan: exclude fixtures + scripted-IO data from review diffs. Live traces:
Langfuse sessions for the two runs (2026-07-16, projects `105dd61a`,
`bdd4094c`).

- **Knowledge candidates**:
  - OpenAI strict response-format rejects open `dict[str, Any]` wire fields
    and the SDK's `to_strict_json_schema` does NOT catch it — 400s surface
    only live. Pattern: transport twins with JSON-string payload fields +
    a schema-strictness regression test (`test_wire_schema_strictness.py`).
  - Live routers emit deltas in variant envelopes (component-wrapped,
    dotted); normalise BEFORE fail-closed validation, never after — and
    beware components whose family key equals their name (characterise).
  - Plan-mappable vs commit-layer directive keys are a real partition:
    without an explicit split + pending overlay, commit-layer keys on mixed
    components are silently dropped at plan-mapping (found as a latent
    honesty bug; the two clobber guards it unmasked were load-bearing).
  - Parallel subagents in ONE shared checkout corrupt each other's full-suite
    evidence (Tasks 4/5 window); disjoint file mandates mostly work, but the
    honest pattern is per-agent worktrees or serialisation for shared
    modules (`steering.py`).
  - The shared test DB accumulates orphaned projects from interrupted runs;
    migration roundtrip tests then fail on downgrade check-constraint
    re-adds (twice this build). `delete_project_data` must track new
    FK-bearing tables (`capability_run`, `orchestration_plan` were both
    missing at some point).
  - A migration-roundtrip test that seeds via shared helpers breaks when a
    helper later names a new column: seed pre-migration shapes inline.
  - Test-level e2e with stub backends cannot catch strict-schema or
    prompt-shape live failures — the pinned live check caught three real
    integration bugs the 1761-test suite could not.
  - The watch's live option-authoring quality exceeded expectations (five
    grounded, honest options at P2 first try) — evidence for the eval slice
    that boundary authoring is viable at judgment-class.
  - D3 repeat-refresh fingerprint collision (deterministic refresh-tagged
    fingerprint) is a known ceiling — supersession-style plumbing if
    repeated refreshes become real.
  - `agent_judgement_routed{clean_boundary}` events double-emit per boundary
    (before+after) — visible in the live walk stories (13 clean events on a
    9-component run); harmless but worth a look at review.

## Deferred work

Seams recorded in [docs/deferred.md](../../deferred.md) § Steering surface
(task 024 seams) — 11 annex Still-OUT entries + 8 file-anchored
build-discovered seams; 017-era discharges marked in place.
