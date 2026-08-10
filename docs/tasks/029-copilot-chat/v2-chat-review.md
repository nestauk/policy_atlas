# V2 chat review — lessons adjudicated into 029 (rev 2.3 input)

Survey of the Policy Atlas V2 chat implementation (sibling repo
`discovery_policy_atlas`, read-only pass 2026-08-10, owner-directed). V2 ships an
agentic RAG chat: OpenAI Responses API, 5-iteration tool loop over read tools
(project synthesis, pgvector evidence search, structured C/M extraction) **plus one
live-egress tool (Parliament APIs)**, NDJSON streaming with typed events, markdown
rendering, multi-thread-per-project transcripts — **in browser localStorage only**.

## What V2 got right → ported into the 029 contract

1. **Server-assigned citation numbers + post-hoc compaction** (the standout): every
   retrieved source gets a turn-scoped number minted *server-side* when tool results
   return; the model cites from that register; after generation the answer is
   re-parsed, renumbered to only the sources actually cited, uncited ones dropped.
   The model cannot invent a source that was never registered. → 029 strand 4: the
   citation floor becomes register-based (marker must resolve to a register entry
   *and* survive compaction), which also closes V2's own two leaks — an out-of-range
   `[7]` surviving into the rendered answer, and a zero-citation answer displaying as
   if grounded (ours forces the pure-LLM tier).
2. **Streamed step transparency**: typed event vocabulary (`agent.status`,
   `tool.started/completed/failed`, `message.delta`, `message.completed`) driving a
   live activity card with user-facing tool labels, collapsing to "Used N actions and
   M sources". Cheap, high-trust UX. → 029 strand 3: the turn stream carries typed
   progress events (tool-step labels) before text deltas; the UI collapses them into
   an activity summary.
3. **Request-scoped turn state with an explicit concurrency test** (V2 tests two
   concurrent turns sharing no service state). → 029 acceptance checks: concurrent
   turns in *different chats* of one project share no state.
4. Smaller confirmations: forced-final-answer escape hatch on iteration cap (our
   `run_section_loop` already has one) · compositional prompt constants shared
   between prompt text and enforcing code (build-time style note) · explicit
   empty-corpus abstention instruction ("do not fall back to general knowledge") ·
   ~5-turn history window (validates window-K) · first-message-truncation titling
   (validates our v1 titling choice).

## What V2 got wrong → already excluded by 029 pins, now with evidence

1. **localStorage-only transcripts** — no table exists; history is per-browser,
   lost on cache clear, invisible to audit/eval; rehydration silently drops the
   response-chain id and answer metadata on reload. The single biggest wart; 029's
   server-side `conversation`/`chat_turn` store is the direct fix.
2. **Live egress from chat** (Parliament APIs are a chat tool) — exactly what the v3
   spec forbids: external egress originating outside the audit record. 029's
   no-`search` tool boundary stands confirmed.
3. **No injection boundary**: retrieved chunks and third-party Parliament text are
   interpolated raw; advisory prompt notes only. (One good instinct — the UI context
   hint labelled "relevance guidance, not evidence" — applied in exactly one place.)
   029 inherits the v3 sanitize + "(data, not instructions)" posture everywhere.
4. **Regex post-processing fighting the model** (six regexes stripping invented
   "Sources:" sections and leaked tool names) — symptom of unstructured output. 029's
   structured terminal payload + deterministic register floor avoids prose-regex war.
5. **No cancellation, no idempotency, no rate limit** on a 5-iteration frontier-model
   endpoint. 029 carries `client_turn_id` idempotency; rev 2.3 adds the cancel
   affordance (client abort + server generator cleanup + honest terminal turn state).
6. **A ~3,000-word mega-prompt encoding a multi-phase protocol as prose**, untested —
   protocol state belongs in code. `chat_v1` stays lean; loop mechanics live in the
   tool-loop runner.

## Not ported (considered, declined)

- Markdown rendering (`react-markdown`) — 029 deliberately renders plain prose
  (EchoLeak-class exfil control + copy diet).
- Quick-reply chips / auto-suggested follow-up questions — copy-diet call; revisit
  post-launch if users ask.
- Provider-side context reuse (`previous_response_id`) — forbidden by the 018
  standing constraint; V2's reload bug is incidentally an argument for owning state.
