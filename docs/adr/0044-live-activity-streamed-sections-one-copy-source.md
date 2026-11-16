# ADR 0044 — Live activity from coalesced ticks, streamed report sections, the planner's reply as a stream, and one server source of progress copy

- **Status:** Accepted — 2026-11-04 (Shabeer Rauf, owner, task 058 plan gate). Amended at the
  review stack, 2026-11-09 (§ Amendments at the review); the owner accepts the amendments with
  the pull request.
- **Date:** 2026-11-04
- **Task:** [058-perceived-latency](../tasks/058-perceived-latency/contract.md) (contract
  revision 2 and plan draft 3 both approved 2026-11-04; design annex version 5)
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

## Amendments at the review (2026-11-09)

The build's fifteen owner polish rounds changed four decisions and three consequences. The
review stack (contract verifier, adversarial reader) found the text above contradicted by the
code; this section records what ships. The decisions above are left as written for the record.

1. **Decision 2, the writer's final turn.** Not a strict `json_schema` response with no tools.
   On a live run the model emitted its forced tool call on turn 2 in one burst, so nothing
   streamed (owner question 1, 2026-11-05; `research/exp-stream-cache-probe.md`). What ships:
   the writer calls a no-argument `write_section` tool when it has gathered enough; the next
   turn streams with the six tools kept, `tool_choice` "none" and no `response_format`, so the
   cached prompt prefix is reused; the reply is parsed as the `emit_section` arguments (a code
   fence is stripped first). The key findings, the introduction and the case studies stream the
   same way (rounds 7 and 8). A stream failure still re-runs the turn once without streaming;
   the count of those fallbacks now rides in the synthesis component's completed payload as
   `stream_fallbacks` (review finding: one real fallback on 2026-11-06 was visible only in the
   trace). The section prompt moved to `synthesise_section_v12`, a behaviour change, not a
   call-shape re-pin.
2. **Decision 6, the run strip.** The run status bar is a button that opens the Task Agent
   and steps aside while the sidebar shows it (owner round 8); the paused state and the
   reconnecting line live on it. The nav's Plan control left (owner round 2); the plan opens
   from the card.
3. **Decision 7, the longlist read.** `GET /longlist` gained `LonglistThemeOut.document_count`,
   `OptionProfileOut.acts_on`, `OptionDocumentOut.authors` and `.venue` (rounds 12 and 13), and
   `RunOut` gained `stages` (round 11) so an earlier walk's card keeps its steps. The options
   read is as decided.
4. **Decision 1, the tick.** The tick also carries `capability_run_id` so a longlist walk's
   page tells its option searches' lines from its own (round 11); eight more ephemeral frames
   joined the two: `artefact.section_sources`, `artefact.section_claim`,
   `artefact.section_card`, `artefact.source_note`, `search.query`, `characterise.themes`
   (rounds 6 to 9). The hub's memory of them is swept on the 600 s TTL whether or not a model
   call is open (review finding).
5. **Consequence "No schema change".** One column was added: `project.archived_at`
   (migration `c4e8a2f6d1b3`, owner request in round 11, 2026-11-06; archiving a project
   archives its solo tasks that are in no other project, owner round 14, and skips a task whose
   walk is running or paused, review finding). ADR 0031 anticipated the column. The contract's
   G3 and G4 gates (the column; `d3-geo`, `topojson-client`, `world-atlas` for the Landscape map,
   round 11) are ratified by the owner at the review's human gate, not by this record.
6. **Consequence "re-pinned for a call-shape change only".** Seven prompt files were re-pinned
   (verification.md § Prompt-hash re-pin): the section prompt (v12), the planner prompt (bands,
   plain copy; the band table `task_plan.py` is now hashed too), the scoping planner (v7), the
   option profile (v5), the shortlist prompt (v2, writing no note), and two new files, the
   shortlist note and the task and chat titles.
7. **Consequence "Measured success".** The fixed-question measures were not run: the owner
   chose the live checks on the dev app through rounds 6 to 15 instead (2026-11-09). No
   before-and-after figure exists; the capture tool stays for a later measurement.
8. **Structural note from the adversarial lane.** The live frames and the durable event log are
   two channels with no shared clock: live state is add-only across a reconnect unless a
   `replace` resets it (now sent whenever a draft exists, empty or not), and the hub is one
   process's memory (a second API replica would turn ticks off with nothing failing a test;
   `docs/deferred.md` § Web app carries the seam).
