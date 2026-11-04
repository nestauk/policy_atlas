# ADR 0044 — Live activity from coalesced ticks, streamed report sections, the planner's reply as a stream, and one server source of progress copy

- **Status:** Proposed — awaiting the task 058 plan gate (owner).
- **Date:** 2026-11-04
- **Task:** [058-perceived-latency](../tasks/058-perceived-latency/contract.md) (contract
  revision 2 approved 2026-11-04; plan draft 2 under review; design annex version 5)
- **Builds on:** [ADR 0027](0027-durable-planning-transcript-artefact-streaming.md) decision 4 (the skeleton and
  per-section progress frames; whole-section grain; the artefact of record lands at commit) ·
  [ADR 0015](0015-prose-first-synthesis-with-span-anchored-claims.md) (repair rewrites the
  segment in place; flag, don't drop) · [ADR 0042](0042-gpt6-switch-per-call-site-routing-and-caching.md)
  (one route step per model call) · [ADR 0043](0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md)
  (per-step timeouts; streamed calls sit outside the retry loop) ·
  [web-api.md](../specs/system/web-api.md) § SSE (the frame vocabulary and the ephemeral
  tick channel).

## Context

After tasks 056 and 057 cut real time, a run still looks stuck: 90% of active run time sits in
gaps over 30 s with no new event on the page (59 walks, dev database, 2026-11-04). The
longest silence is the full-text stage, whose live counts are not stored and vanish on a
reload; the second is writing, where a section appears only after it is written, judged and
repaired (p50 26 s, p90 108 s per section). The Result tab shows a placeholder for most of an
Evidence search and the previous report during a re-run. The planner's reply arrives whole
after 3 to 12 s. Progress copy lives in four places with five disagreements. Options
scoping's longlist build (median 14 min) shows nothing until clustering.

Experiments settled the mechanics. On the Bedrock route the forced tool call the writer uses
today delivers its arguments in one burst at the end, so it cannot stream; a strict
`json_schema` response streams the prose ahead of the claims, and the app's real section
schema was accepted strict as-is on the writer's tier. The cost of giving that turn its own
cache lineage is a median $0.03 per report. Every model call already passes through one
wrapper that knows the step and the task; one tick per call would overflow the SSE channel,
so ticks are coalesced. Closing the HTTP client does not interrupt a call, so cancel is out
of this slice. The owner's rulings fixed the shape: card direction C, no labels that restate
the page, a blur-and-settle treatment for a sentence under repair, two routes to the agent,
and replace-don't-layer because the frontend and backend deploy together.

## Decisions

1. **Activity is a coalesced, ephemeral tick with one field set for every stage.** The
   model-call wrapper publishes the stage's verb and a liveness mark, with a heartbeat every
   10 s while a call is open; each loop that knows its total publishes its own count with a
   unit; the hub coalesces at 500 ms per task and stage and keeps the current run's last tick
   and section draft in process memory for a connecting client. Ticks are never persisted and
   never state-bearing; `section_completed` and the durable stage frames stay the record.
2. **The writer's final turn streams as a strict `json_schema` response with no tools.** The
   research turns keep their tools; the repair keeps its forced tool call; the parsed object
   continues into the unchanged claim path. Prose deltas and the judge's failing spans are
   ephemeral frames; a connecting client gets the draft so far as one replacing delta. A
   stream failure re-runs the turn once without streaming. The cache cost is accepted.
3. **A sentence under repair blurs and settles; nothing marks it afterwards.** The visible
   transition is the marker the flag-don't-drop rule asks for; pre-repair text is not stored
   and not surfaced.
4. **The planner's reply streams** with the chat route's event shape, replacing the JSON
   response; the opening turn streams in the Agent tab.
5. **One server source of progress copy.** `STAGE_PRESENTATION` holds labels, blurbs, verbs,
   count keys and the card's row grouping, in the client's terse voice; the client vocabulary
   is deleted; the spec lists all 19 stage keys.
6. **Two routes to the agent on any tab**: the sidebar rail's mark and the Agent tab. The run
   strip is status only; the paused banner is removed; the re-run notice has no button; the
   sidebar carries the real stream.
7. **The longlist exists from the suggest stage** through a new task-scoped options read
   that carries each option's child search status; the longlist read and `has_longlist` are
   unchanged; the list fills in waves because profiles, checks and themes commit together.
8. **No cancel, no computed time band, no telemetry, no email** in this slice; each is a
   recorded seam.

## Consequences

- Public interface grows by the reshaped tick, two ephemeral frames, a question field on the
  planner turn, a stage label on the active run, the options read and the streamed planner
  route; the web-api spec is amended as owner items. No schema change.
- The section-writing prompt file's hash is re-pinned for a call-shape change only.
- A reload shows the current activity and the prose written so far; a process restart loses
  the draft until the section completes, by design.
- The live tail, the tick memory and the draft stay process-local, as the deployment posture
  already is; the cross-instance seam is unchanged.
- The frontend-heavy parts run under the task cycle's frontend variant (PR #113): the design
  annex carries looks, the contract carries behaviours, and polish passes run inside the
  task before and after review.
- Measured success: zero silent gaps over 30 s on a healthy run, first streamed prose within
  5 s of the writing turn, on the fixed questions before and after, on laptop and staging.
