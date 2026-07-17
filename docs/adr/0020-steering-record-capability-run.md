# ADR 0020 — The durable steering record: steering events + the capability_run walk entity

**Status:** Accepted — 2026-07-16 (Shabeer Rauf; task 024 contract rev 4 as
amended). Decision trail: the 024 contract's revision history, the
steerability-refinement annex (five owner review rounds), and two
adversarial reviews (contract-stage, plan-stage — deep-reasoner lanes of
record; Codex blocked on workspace credits, attempted twice).

## Context

Through 023, steering decisions were only partially durable: accepted plan
amendments persisted as `orchestration_plan` version rows, but check-ins,
pauses (options + fired triggers), Continue decisions, rejected
adjustments, refused intents, and Unattended auto-resolutions lived in
process memory and console output. The spec's §9 posture — the decision
log as a projection over a single canonical event spine; transcripts
non-canonical — was unfulfillable for steering: a front-end could not
rebuild the orchestrated conversation's decision history after the user
went away. Separately, the *walk* (one capability execution over a plan)
had no schema identity — 017's deferred capability-run seam — leaving
multi-run projects with no grouping key and the planning conversation with
no durable anchor.

## Decisions

1. **Steering events on the existing `event_log`, unchanged.** New event
   types: `steering.pause` · `steering.decision` · `steering.rejected` ·
   `steering.refused` · `component.skipped` · `agent_judgement_routed`.
   Every payload carries `capability_run_id` + plan lineage + boundary;
   decisions carry `decided_by` (`user | orchestrator | standing_default`),
   `authored_by`, verbatim `user_text` where prose was given, the
   interpreted action, confirmation state, execution profile, and re-run
   mode. Mode changes ride `steering.decision`. Attachment: the run the
   event is about (`after_component`); otherwise the most-recent attempted
   run id as FK plumbing — semantics live in the payload. No steering
   event is emitted before the first component run exists
   (`event_log.run_id` is NOT NULL by design and stays so).
2. **Transactionality, qualified.** Decision/skip/re-run events commit in
   the same transaction as their adjacent state change (plan version row,
   abandon flip) — the §9 invariant; pause/refused/rejected are standalone
   appends (no state-change partner exists). Append-only is inviolate.
3. **The `capability_run` entity** (discharges the 017 seam, minimal by
   "model only what behaves"): id · project · scope · capability ·
   approved plan ref · status · nullable `session_id` (the
   planning-conversation anchor) · timestamps; `runs` gains a composite
   `(capability_run_id, project_id)` FK per the cross-project-guard
   convention. Not modelled until a second capability behaves:
   composition fields, artefact back-refs (derivable), turn tables (025).
4. **The projection is the contract.** `steering_history()` rebuilds the
   ordered pause → options/triggers → decision → outcome story per walk
   from Postgres alone — the front-end read surface, pinned by a
   fresh-connection rebuild test covering two walks in one project.
   Because pause events persist the presented payload, orchestrator
   decisions are replayable from the record by construction.

## Consequences

- The decider-dial principle (ADR 0021) is auditable: mode moves who
  answers; the record's shape never changes.
- Verbatim-text provenance ("never paraphrase-laundered") holds at the
  steer grain; transcripts stay companion stores (per-user chat lands
  with 025's transcript table — spec §9 unchanged).
- The walk entity is the join key the front-end build screen, catch-me-up,
  and multi-question projects need; a future EB+options composition is one
  orchestration plan with each capability run its own row.
- Seam: `capability_run_id` travels in event payloads (serial v3.0 walks
  don't interleave); a functional index is a front-end-era option.
