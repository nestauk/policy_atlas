# Task 024 log

## 2026-07-16 — build phases 0–5

Design phase closed (contract rev 4 approved, ADRs 0020–0023 authored,
`steerability-refinement.md` settled through owner review round 5). Build
opened in a fresh conversation (task-cycle-build) and landed five phase
commits plus one pre-build design carry-back, all on `task/024-steering-surface`
(six shas, per `git log --oneline -12`):

* `4bfd55b` — deferred.md carry-back (per-query source provenance seam) —
  last design-phase commit before Phase 0's build-open baseline verify (no
  diff of its own).
* `f7ab7b6` — **Phase 1**: `capability_run` walk identity + composite `runs`
  FK + `screen_generation` column/index; runner walk-row lifecycle; the
  six-event steering chassis (transactional pairing rules); `steering_history`
  projection.
* `8afcbe1` — **Phase 2**: grammar widening — D3/D5/D6/D7/D8/D1/D9 structured
  keys + B1/B3/B5 guidance channels, shared bounded validator, isolation
  tests, `standard`/absent ≡ as-built guards.
* `ef87c69` — **Phase 3**: re-run machinery — component-parameterised
  replacement re-runs, `ReEnterSegment` (additive segment re-entry, new
  bounded runner construct), generation supersession
  (`effective_screen_rows` generation-first ordering + re-screen write path).
* `4b2efde` — **Phase 4**: trigger floor (decision-8 classes) + the P1–P4
  steer-point lattice + mode table + canonical option floors + Unattended
  (c) discretion (`SteerPointDefault`, `DiscretionHook`, authority-order
  test).
* `afc9faa` — **Phase 5**: `orchestrator_v1` prompt family (three moments) +
  orchestrator backend (gated invocation, single-shot bundles, fallback
  deliberation loop) + router compile path (fan-out, partial-compile,
  confirm-before-apply) + B2′ finding-relevance channel + CLI + injection
  fixtures.

**Executor substitutions.** Every `codex→deep-reasoner` mark in the plan
fired as written: Codex workspace credits were exhausted at the design-phase
adjudication (`45db04a`, confirmed 2026-07-16 before build), so all
plan-designated Codex briefs (Phase 1 task 2; Phase 3 tasks 7–9; Phase 4
tasks 11–12; Phase 5 tasks 14, 15, 17) ran on deep-reasoner throughout the
build, per the standing codex-exhaustion-fallback rule — no build slowdown,
substitutions logged as they landed rather than deferred to verification.md.

**Two API-stall agent resumes.** Two deep-reasoner sub-agent runs stalled
mid-turn on a provider API hang during the build and were resumed
(SendMessage to the same agent id, full context intact) rather than
restarted from scratch — no rework, no lost turns; both resumed runs
completed and landed in their phase's commit.

**Lead-adjudicated in-build extensions (Phase 5, task 15).** Three router
gaps surfaced only once the fan-out compile path was built end-to-end;
lead adjudicated each as a same-concern extension of task 15 rather than a
new task, closing a contract-vocabulary gap the plan hadn't named:

* **15b — P2/P4 apply surfaces.** Segment re-entry at P2 (including
  criteria+rescreen via the generation-supersession path) and
  re-characterise/re-group replacement re-runs needed one shared apply
  surface so standing rules and watch decisions could reuse it identically
  to a live user answer — the plan's P1–P4 wiring (Phase 4, task 11) named
  the bundles but not this shared commit-time surface.
* **15c — pending-overlay.** Commit-layer directives (the fine-grained
  deltas steer-point options actually apply) needed a pending-overlay
  layer distinct from the persisted directive so a mid-flight steer could
  compose without clobbering an in-progress one.
* **15d — mixed-grammar delta splitting.** Per-key delta splitting for
  extract (`refresh`/`relevance_emphasis`) and group
  (`granularity`/`guidance`) — mixing two channels/keys in one free-text ask
  needed per-key routing through the pending overlay rather than one
  whole-component delta.

**Latent silent-drop honesty bug (found + fixed by 15d).** Building the
mixed-grammar split for extract surfaced a live bug: pending extract deltas
that mixed `refresh` and `relevance_emphasis` in one compiled fragment were
silently dropping whichever key wasn't recognised by the (until-then)
whole-delta apply path — no error, no refusal event, just a quietly
incomplete apply. Fixed in the same commit (`afc9faa`) by routing extract
(and group) through the per-key overlay instead of a whole-delta merge;
covered by the new mixed-grammar tests in `test_router_compile.py`. Caught
during the build, not by review — recorded here per the task-cycle
build-phase disclosure discipline.

**Verification.** Full `make verify` green at Phase 0 (baseline), Phase 1
exit, Phase 3 exit, and Phase 5 exit (public interface + LLM integration);
`make verify-fast` at Phase 2 and Phase 4 exits — per the plan's gate
consolidation table. 1761 tests passing at the Phase 5 exit.

Deferred work from this build → `docs/deferred.md` § Steering surface
(task 024 seams) — see that section for the full annex Still-OUT sweep,
build-discovered seams, and the 017-era entries this task discharges
(the capability-run entity, the deepening-selection/landscape/re-grouping
steer-point pauses, and half of the "steering conversational half" entry).
