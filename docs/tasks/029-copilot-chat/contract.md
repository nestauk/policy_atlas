# Task contract: 029-copilot-chat

> **Status:** drafted 2026-08-05 (as `029-copilot-qa`); **rev 2, 2026-08-10 — unified
> conversation model, owner-directed** (interview outcome: fold the planning-conversation
> restructure in; "qa" naming dropped repo-wide). Contract approved (before planning):
> _pending · owner_ · Plan approved: _pending_ · ADR: _expected (unified conversation
> model + lineage chain + chat fast-path pin)_.
>
> **rev 2 (owner interview, 2026-08-06→10):** (1) **Naming**: "qa" reads as quality
> assurance and undersells the surface — user-facing **Chats**, code `conversation` /
> `chat_turn` / `chat_v1`, slug → `029-copilot-chat`. (2) **Model**: a project holds
> **many conversations**, Claude-Projects-style — follow-up chats (many, read-only,
> project-scoped) and planning conversations (**one per plan lineage**, superseding
> 027's rolling single thread — which 027 itself recorded as "single-thread *until* the
> co-pilot slice brings its own thread model"). (3) **Chats answer across artefacts** —
> an artefact is an entry point and a provenance fact, never a scope fence.
> (4) **Chats never mutate**: a question needing new evidence or a re-run hands off to
> the planning conversation (a link, not a plan mutation). (5) The audit chain becomes
> first-class: **planning conversation → plan → capability run → artefact**.
>
> **rev 2.1 (2026-08-10): web-research pass** (owner-directed; three-lane survey of
> 2025–26 practice — product containers, transcript/context engineering, grounded-chat
> UX; sources in `research-notes.md`). Validated as-is: owned Postgres transcript store
> (the *recommended* pattern for regulated/FOI deployments, not a compromise) ·
> client-minted idempotency · many-chats-per-project (Claude/ChatGPT Projects,
> Perplexity Spaces) · no cross-chat recall by default · read-only tool scope (OWASP
> LLM01 / lethal-trifecta guidance) · trust tiers + abstention (**leads** consumer
> practice) · deterministic citation floor (**leads** most products). Amendments folded:
> **(a)** inline `[n]` citation markers + click/hover-to-quote (footer-only lags —
> inline click-to-source is table stakes; reuses the artefact citation grammar +
> chunk-context read model); **(b)** token ceiling alongside the K-turn window; context
> assembler shaped so a summarizer slots in later; **(c)** `answer_payload` carries
> model id + prompt version (audit hardening); **(d)** honest latency affordance while
> blocking; **(e)** plain-prose/no-markdown re-recorded as a *security control*
> (EchoLeak-class CVE-2025-32711 showed markdown-link rendering exfiltrating from
> "read-only" chat — our renderer closes that channel), and the misattribution gap
> (id-membership doesn't catch "real chunk, unsupported claim") explicitly routed to
> the eval slice. **❓ reopened at the 🛑: streaming** — blocking answers were the one
> genuinely non-mainstream pin (grounded chat streams near-universally; the
> state-of-the-art shape is stream-prose-then-attach-verified-citations).
>
> **rev 2.2 (owner call, 2026-08-10): streaming IN** — stream-then-verify on the turn
> POST, under a provider-neutral wire pin (text deltas + one terminal validated
> payload) so the Bedrock move re-ports only the provider adapter it rewrites anyway.
> Owner's framing: "I would ideally prefer streaming"; waiting for Bedrock buys
> nothing under the neutral pin. Strand 3 carries the mechanics.
>
> **rev 2.3 (2026-08-10): V2 chat review folded in** (owner-directed survey of the
> sibling `discovery_policy_atlas` chat; adjudication in
> [v2-chat-review.md](v2-chat-review.md)). Ports: **(a)** cite-only-what-you-read +
> post-answer compaction invariants (strand 4 — **rev 2.3.1, owner challenge:** the
> *mechanism* is house-pattern durable-id `citations[]`, not V2's server-pre-assigned
> number register, which was declined as a free-prose-era workaround); **(b)**
> typed stream progress events with user-facing tool labels + collapsing activity
> summary (strand 3/6); **(c)** cancel affordance — client abort, server generator
> cleanup, honest terminal turn state (strand 3); **(d)** cross-chat turn-state
> concurrency test (acceptance checks). V2's warts stand as evidence for pins 029
> already carries: localStorage-only transcripts (vs our server store), live egress
> from chat (vs our no-`search` boundary), raw interpolation (vs our injection
> posture), regex prose-fighting (vs our structured terminal payload), no
> idempotency/cancellation (vs `client_turn_id` + (c)).
>
> **rev 2.4 (2026-08-10): turn-persistence check vs production systems** (owner
> question; research in [research-notes.md](research-notes.md) § Lane 4). Lifecycle
> validated: buffer-then-atomic-commit is the AI SDK `onFinish` orthodoxy; honest
> `failed` rows exceed most templates; explicit `turn_index` is sturdier than the
> timestamp ordering templates use. Two divergences adjudicated: **turn-pair row
> grain kept knowingly** (no production system does it, but it models exactly our
> ask→answer shape; the pair→per-message split is the named regenerate/branching
> seam) and **cancel now keeps the partial** (production norm — LibreChat
> `unfinished`, assistant-ui `incomplete/cancelled`; status `cancelled`, markers
> inert, "stopped before evidence check" badge in place of a tier).
>
> **rev 2.5 (2026-08-10): framework/dependency adjudication** (owner question).
> Declined with reasons: LangChain (not in the stack; the in-house tool loop already
> does the job, audit-integrated) · running chat on the LangGraph harness (already a
> dep, but it's the durable walk substrate — a chat turn needs no checkpoints/
> boundaries; chat stays on `run_section_loop`) · Vercel AI SDK (TS server half
> useless against FastAPI; client half fights the provider-neutral wire pin + house
> store patterns) · Langfuse prompt management (prompts stay code-pinned,
> git-versioned, lead-authored — the governance posture). Folded: per-turn **Langfuse
> trace id stored in `answer_payload`** (strand 7 — DB row ↔ trace audit linkage);
> **thumbs-feedback → Langfuse scores** named as the eval slice's gold-set seam
> (Out list).
>
> **rev 2.8 (2026-08-10, owner calls):** (1) `POLICY_ATLAS_CHAT_MODEL` defaults to
> **`gpt-5.6-terra`** (faster class for the conversational budget; same provider and
> approved route). (2) **Fresh-chat hydration enumerated** in strand 5 — project
> identity + coverage sentence + funnel headline + artefact headline layer (title,
> summary, section titles) + labelled entry context; orient-don't-stuff, everything
> else tool-fetched.
>
> **rev 2.7 (2026-08-10, owner calls at the mockup review):** (1) **per-citation
> judge tiers IN** — the async grounding judge runs post-stream and attaches
> per-citation §3.3 verdicts (citations are
> honestly "unchecked" until enrichment; judge failure never blocks). Resolves the
> tier-grain question: answer-level self-report both flattened mixed answers and
> self-graded in the judge's vocabulary; async enrichment is judge-true with zero
> visible latency. Staged as its own plan phase, cuttable at the plan 🛑. (2) The
> Chats-library **Open/Closed badges are cut** (copy diet — tab presence and the
> preview carry the same information). **rev 2.7.1:** the derived answer-wide
> weakest-tier chip is cut too (owner) — per-citation verdicts are the tier display;
> only the zero-citation "pure LLM reasoning" marker and the stopped badge remain
> answer-level, each because there is no citation to carry the signal.
>
> **rev 2.6 (2026-08-10): PR #35 chat mockup re-mined** (owner-directed; the
> colleague's demo branch this slice's container model came from, now read for its
> interaction detail — adjudication in [design-inputs.md](design-inputs.md)).
> Adopted: **context chips with "Whole project" zero-state** (the concrete UX for
> "artefact = entry point, never a fence"; `@`-multi-select deferred to
> workspace-cluster) and **URL-addressable conversations** (deep-linkable threads —
> the mockup's in-memory-only reopen is its own dead end). A dozen presentation
> details recorded as build-time inputs; declines recorded with reasons (thread-type
> special-casing, quick-reply chips, hard delete, start-run-from-chat).
>
> **Contract-stage adversarial review** (Tier 3+ standard): after owner approval,
> read-only `codex-rescue` brief over contract + rubric; fall back down the ladder
> on credit failure per the codex-exhaustion rule.
>
> Branch `task/029-copilot-chat` from merged `dev` (stack 026/027/028 landed 2026-08-06).

## Goal

After an analysis run completes, the user follows through in **chats**: while reading an
artefact they open separate conversations per line of questioning (one rolling transcript
would bury them — the Claude/ChatGPT-Projects mental model), and get fast, honestly-tiered
answers grounded in the **whole project's** committed evidence. Alongside, planning is
re-homed into the same conversation model: **one planning conversation per plan lineage**,
closing when its run completes, giving the clean audit spine *conversation → plan → run →
artefact* and bounding planner rehydration (today's full-replay rolling thread grows
without bound). Chat answers are **ephemeral** — no artefact, never hidden project state.

Discharges the pre-registered seam (027 PR #35 adjudication; deferred.md § 024 transcript
companion store + § 027 co-pilot Q&A UI seam + lead-authored prompt surface).

## Deliverable

PR onto `dev` landing: the `conversation` entity + `chat_turn` store + lineage columns
(migration incl. legacy backfill), the `/api/v1` conversation/chat endpoints, the
lead-authored `chat_v1` orchestrator moment on the live read-tool loop, trust-tier-labelled
answers with deterministically-floored citations, planning-conversation lifecycle, and the
conversation-aware rail + Chats library in the frontend. `verification.md` with the scoped
live check.

## Read first

- [execution-orchestration.md](../../specs/system/execution-orchestration.md) — co-pilot
  scope, read-tool rule, tier honesty; § Tier-0 retrieval contract (Q&A lookup profile).
- Frozen source [backend-architecture-reference.md](../../specs/sources/backend/backend-architecture-reference.md)
  § The orchestrator & co-pilot — the 🟡 fast-path discipline this contract pins.
- [plan-as-object.md](../../specs/system/plan-as-object.md) — the plan lineage the
  planning conversation now maps onto.
- [web-api.md](../../specs/system/web-api.md) — § Planning turns (mechanics preserved),
  § Auth boundary, § SSE (frozen vocabulary — untouched).
- [provenance-grounding.md](../../specs/system/provenance-grounding.md) — §3.3 trust-tier
  taxonomy the answer labels reuse.
- deferred.md — § 024 transcript companion store · § 027 co-pilot Q&A UI seam ·
  § 024 "live DB-backed read executors" (adjacent seam, stays deferred) · § 025
  run/artefact read-model gap (partially closed here by `artefact.capability_run_id`).
- 027 `contract.md` strand 12 + `rehydration-mapping.md` — the planning-transcript
  precedent this slice re-homes (two-phase persistence, idempotency, no-backfill → now
  a real backfill, see strand 1).
- This slice's own inputs: [research-notes.md](research-notes.md) (2025–26 practice,
  4 lanes) · [v2-chat-review.md](v2-chat-review.md) (V2 lessons) ·
  [design-inputs.md](design-inputs.md) (PR #35 mockup adjudication).

## Design pins (the strands)

### 1 — Schema: the unified conversation model (approval gate: schema — incl. one live-data migration)

- **`conversation`** — `id` (UUID PK) · `project_id` FK · `kind ∈ planning | chat` ·
  `title` (chats: server-derived from first question, PATCH-renameable; planning:
  server-derived from the plan/run) · `status ∈ active | closed | archived` ·
  `created_at`, `closed_at`, `archived_at`. Owner scope rides the project.
  Invariant: **at most one `active` planning conversation per project** (partial unique
  index) — preserves the single-plan-draft invariant and the run fence.
- **`chat_turn`** — `id` PK · `conversation_id` FK (kind=chat) · `turn_index` ·
  `client_turn_id` (uniques `(conversation_id, turn_index)`, `(conversation_id,
  client_turn_id)`) · `user_message` (≤10 000 chars) · `answer` (prose) ·
  `answer_payload` JSONB (citations, trust tier, bounded tool digest, **model id +
  prompt version** — per-turn audit metadata, rev 2.1) ·
  `capability_run_id` (nullable FK, `uq_capr_id_project` composite precedent — records
  which run's committed state answered; provenance, **not** scope) ·
  `status ∈ pending | completed | failed | cancelled` · `created_at`, `completed_at`.
  **Grain note (rev 2.4):** the turn-pair row (user message + answer in one row) is a
  deliberate departure from production per-message-row schemas — sound while the shape
  is strictly ask→answer (no regenerate, no branching, no tool rows: all out of
  scope), with the exit named: pair→per-message split is a mechanical additive
  migration recorded as the seam regenerate/branching would open with.
- **`planning_transcript`** gains `conversation_id` FK — turn columns and mechanics
  otherwise untouched. Turn storage stays per-kind (planning columns and chat columns
  share almost nothing; "model only what behaves" — no speculative unified turn table).
- **Lineage chain**: the plan row gains a nullable `conversation_id` (exact placement
  against the as-built plan/version tables is a plan-time mapping); `capability_run`
  already pins `plan_id + plan_version`; **`artefact` gains nullable
  `capability_run_id`** — closing the named 025/027 gap so *conversation → plan → run →
  artefact* is walkable end-to-end. All additive, nullable, no legacy fabrication.
- **Legacy backfill (the one data migration — the riskiest element of the slice):**
  each project with existing planning turns gets exactly one legacy planning
  conversation owning all its rows; its `active`/`closed` status is derived honestly
  from plan/run state at migration time (open draft newer than the last completed run →
  `active`; else `closed`) — precise rule finalized at plan 🛑, with a tested downgrade
  path (rollback plan, Tier-4 discipline).
- **Provider-side conversation state stays forbidden** (018 standing constraint —
  audit/FOI/portability). No hard delete anywhere; PR #35's "delete" is archive/reopen.

### 2 — Planning-conversation lifecycle (supersedes 027's rolling thread)

- One planning conversation per **plan lineage**: created with the project (or on first
  planning turn); steer-point plan revisions mid-run stay within its lineage; a run
  reaching `succeeded | degraded` **closes** it; "Run the analysis again" opens a new
  one **seeded from the executed plan** (the existing `previous_draft` mechanics — no
  transcript replay across conversations). Failed/aborted/interrupted runs leave it
  `active` for replanning within the same lineage.
- **Planner rehydration scopes to the conversation's own turns** — bounding context by
  construction (the rolling model's unbounded full-replay is the engineering defect this
  fixes, not just aesthetics).
- Planning-turn mechanics preserved verbatim: two-phase persistence, LLM outside
  transactions, `client_turn_id` idempotency, turn locks, 409 vocabulary, run fence.
- Cross-conversation rationale carry-over ("we excluded pre-2015 because…") is **not**
  automatic — the plan object carries the decisions; prose recall is a named deferred
  seam, honestly.

### 3 — API: additive `/api/v1` endpoints (approval gate: public interface)

All owner-scoped (404-indistinguishable BOLA rule), standard pagination + error envelope.

- `GET /projects/{id}/conversations?kind=&status=` — the library read model (both kinds;
  newest first; latest-turn preview; chats + closed planning conversations browsable).
- `POST /projects/{id}/conversations` `{}` → 201 chat conversation (kind=chat only —
  planning conversations are lifecycle-created, never minted by hand).
- `PATCH /conversations/{cid}` `{title?}` · `POST /conversations/{cid}/archive` ·
  `.../unarchive` — chats only, idempotent, mirroring project-archive semantics.
- `POST /conversations/{cid}/turns` `{message, client_turn_id}` → blocking `ChatTurnOut`
  (answer + citations + tier), kind=chat; mirrors planning-turn mechanics wholesale
  (pending row under project lock → LLM outside transaction → completed row; idempotent
  retry of latest turn; 409 `stale_turn` / `chat_turn_in_progress`; 10-min stale expiry;
  honest pending/failed rows). `GET .../turns` — paginated ascending.
- **Existing planning endpoints keep their paths and semantics** (`/planning-turns`,
  `/plan`) — they now operate on the project's single active planning conversation;
  responses additively expose `conversation_id`. Evolution stays additive; nothing
  removed.
- **Chat eligibility fence:** turns require ≥1 completed run (`succeeded | degraded`) —
  else 409 `no_completed_run`; while the walk is `running | paused` → 409 `run_active`
  (mid-run reads would see a half-written evidence base; steering is the mid-run
  channel). *Owner cut-line: allow chats while paused — defer unless wanted now.*
- **Streaming — IN, stream-then-verify (owner call, rev 2.2; resolves rev 2.1's ❓).**
  `POST .../turns` returns a **fetch-stream** (never the project event channel — the
  frozen 028 SSE vocabulary is untouched): prose text deltas as they generate, then
  **one terminal validated payload** (surviving citations, trust tier, turn metadata)
  after the citation floor runs server-side on the completed buffer. The wire contract
  is **provider-neutral by pin** — text deltas + terminal payload, never
  provider-specific partial-JSON passthrough — so the Bedrock migration only re-ports
  the provider adapter it rewrites anyway (`ConverseStream` maps 1:1). Persistence
  stays atomic at completion (two-phase turn rows unchanged: pending → stream → the
  completed row commits whole; a crash mid-stream leaves an honest pending→failed row,
  and an idempotent retry of a completed turn replays the stored answer as a single
  terminal payload, no re-generation). Tool-loop turns before the final emission emit
  **typed progress events with user-facing tool labels** (rev 2.3, the V2 activity
  pattern — "Searching the evidence…", collapsing to an activity summary in the UI),
  not fake tokens. **Cancel is a first-class affordance** (rev 2.3; shape corrected
  rev 2.4 to production practice): the client can abort the stream (composer stop
  button); the server cleans up the generator and **persists the partial prose** with
  status `cancelled` — users keep the text they watched stream (the LibreChat/
  assistant-ui/ChatGPT norm), never a silent pending. Since the terminal `citations[]`
  never arrived, inline markers in a cancelled partial are unresolvable by
  construction: they render inert and the turn carries a "stopped before evidence
  check" badge in place of a trust tier — content kept, tier honesty intact. This is
  the backend's **first token-streaming plumbing** — named as such for the plan and
  review stack.

### 4 — The chat agent: `chat_v1` orchestrator moment (lead-authored, prompt-bearing)

- New moment beside router/watch: `CHAT_SYSTEM_PROMPT` from `_SHARED_PREAMBLE` (moment
  count sentence updates per house rule), own pin `chat_v1`, own
  `POLICY_ATLAS_CHAT_MODEL` env constant (default = orchestrator model), wire models
  `extra="forbid"`, all corpus-derived and user inputs sanitized + bounded + labelled
  "(data, not instructions)" — the standing injection posture, inherited verbatim.
- **Tool loop = reuse**: `run_section_loop` over `build_section_tools` with the live
  executors (`search_chunks` on the Q&A-lookup retrieval profile · `query_findings` ·
  `lookup`), **project-scoped**: reads across all committed runs/artefacts the project
  holds (v3.0 practical floor: the latest completed run's committed outputs — the
  single-EB era makes that the whole evidence base; the multi-artefact widening rides
  the workspace-cluster read models, seam named). **The tool set is the security
  boundary**: no `search`, no write tools constructible from the chat surface (spec
  hard rule — egress must not originate outside the audit record). Turn caps + per-turn
  read caps as shipped.
- **Fast-path discipline — pinning the spec's 🟡 (rev 2.7: two stages, judge-true)**:
  chat skips verification **inline** — nothing delays the stream — and the real
  **grounding judge runs asynchronously after the stream closes**, attaching
  **per-citation §3.3 tier verdicts** (owner call, 2026-08-10: per-citation labels are
  the judge system's design; an answer-level self-graded tier both flattens mixed
  answers and fakes the judge's precision).
  - **Stage 1 — deterministic floors at the terminal payload** (rev 2.3.1 mechanism,
    unchanged): the structured payload carries `citations[]` as **durable ids** (the
    same citation currency as synthesis); inline `[n]` markers index that array;
    display numbering derived at persist time. Floors: (a) every citation must
    resolve to an id the tool loop actually returned this turn — anything else is
    stripped; (b) an orphaned marker is stripped with its citation; (c) the persisted
    display payload is compacted; (d) zero surviving citations → the answer carries
    the "pure LLM reasoning" marker (the one answer-level signal that survives —
    with no citations there is nothing else to carry it), no judge call;
    (e) surviving citations land in an honest **"unchecked"** state — never wearing
    a tier they haven't earned.
  - **Stage 2 — async judge enrichment**: for answers with surviving citations, the
    grounding judge (the synthesis judge machinery) assesses each cited claim against
    its cited chunk(s) and per-citation tier verdicts attach as an enrichment write
    on the turn row — **the only tier display on cited answers** (rev 2.7.1, owner:
    the derived answer-wide weakest-tier chip is cut as redundant; per-citation
    verdicts carry the whole story). Judge failure or timeout leaves citations
    honestly "unchecked" —
    enrichment never blocks, never fabricates, and a judge verdict can only downgrade
    or confirm, never launder. The upgrade reaches an open chat via the turn read
    model (bounded refetch; **no project-SSE change**). An idempotent retry replays
    the enriched payload when present.
  *(Considered and declined: V2's server-pre-assigned per-turn citation register —
  see [v2-chat-review.md](v2-chat-review.md); and inline/blocking judge — the whole
  point of stream-then-verify is that verification cost never sits on the visible
  answer.)*
  **Residual, revised at rev 2.7**: the async judge now covers *misattribution* (a
  real chunk cited for an unsupported claim — the dominant 2025–26 failure mode) for
  every enriched answer; what remains for the eval slice is measuring the **judge's
  own quality on chat-shaped claims** and the unenriched window/failure path.
- Both spec flavours in scope: *provenance lookup* and *generative synthesis* rendered
  into chat, not persisted as artefact content.
- **Evidence-not-held honesty + hand-off**: when the corpus can't answer, the answer
  says so and points at the planning conversation (a rendered link/affordance — never a
  plan mutation from chat). The full "convert to shared search request" affordance stays
  deferred.
- **Promotion to artefact block stays deferred** (spec: promotion re-runs the full bar).

### 5 — Context assembly (window, not full replay)

Per-turn chat context = the conversation's recent window (last K turns verbatim, K pinned
at plan time, **plus a token/char ceiling so one oversized turn can't blow the budget** —
rev 2.1) + the current question + the **project frame**. The frame (rev 2.8, fresh-chat
hydration enumerated — *orient, don't stuff*: the frame says where the model is standing;
specifics are the tool loop's job): project name + research question · the composed
coverage sentence · the funnel headline counts · per artefact its title, persisted
summary and section titles (never the prose) · the entry-context artefact when the chat
was opened from one, labelled "the user was reading this — relevance guidance, not
evidence". All frame fields are corpus/project-derived → sanitized, bounded, labelled
"(data, not instructions)". Deliberately not hydrated: raw chunks, artefact prose, the
planning transcript, steering history — all tool-fetchable or deferred. The assembler is
one seam-shaped function so rolling summarization can slot in later without reshaping
turns. **Recall over older turns is deferred** (window-first, honestly — the 2026
layered pattern is window + summary + recall; we land the base layer). Stored HTTP
projections are never fed back to the model (027 rule).

### 6 — Frontend: conversation-aware rail + Chats library

- The rail hosts the **active conversation** with a switcher/library: planning
  conversations (current + closed) and chats, Claude-Projects-style. Copy follows the
  copy-text principle — labels over explainers; user-facing noun is **"chat"**.
- Entry points: the artefact reader ("Ask about this analysis" — opens a chat with the
  artefact as *entry context*, not a fence) · the 028 "evidence base is ready" card ·
  the library ("New chat") · "Run the analysis again" → opens the new planning
  conversation. **Entry context renders as a removable chip** ("Whole project" when
  none; chip click navigates to the artefact) — rev 2.6, the PR #35 ContextBar
  pattern; multi-artifact `@`-context waits for workspace-cluster. **Conversations
  are URL-addressable** (thread id in the route; library rows and "ask" affordances
  deep-link). Finer rail/library presentation follows
  [design-inputs.md](design-inputs.md) § build-time details.
- **Answers render as prose with inline `[n]` citation markers** (rev 2.1:
  inline click-to-source is table stakes, and it's the artefact reader's own grammar) —
  `whitespace-pre-wrap` + scrub, **no markdown dependency** (now a recorded *security
  control*: no rendered links from model output closes the EchoLeak-class exfiltration
  channel, on top of the copy-diet rationale); the `chat_v1` prompt constrains answers
  to plain paragraphs with `[n]` markers. Markers + the references footer resolve to
  the id-keyed dossier open; **hover/click shows the cited quote in context** (reusing
  the chunk-context read-model pattern the artefact citations already use);
  per-citation tier verdicts (rev 2.7.1 — the only tier display) use only the locked
  `TIER_LABEL`/`TIER_TEXT` vocabulary, alongside the zero-citation pure-LLM marker
  and the stopped badge.
- Composer is the extracted 028 `Composer` with per-kind copy; disabled states stay
  honest (pending turn; fence states show why).
- State layer mirrors `usePlanningTranscript` (durable query + optimistic reducer +
  per-`client_turn_id` retry); conversation switch is a query-key change.

### 7 — Tracing hygiene

One Langfuse `session_id` **per conversation** — chats *and* planning conversations
(discharging the known planning wart of a throwaway session per turn, which the
conversation entity now makes natural). Prompt-version metadata on every call. The
turn's **Langfuse trace id is stored in `answer_payload`** (rev 2.5) — the durable
row and the trace reference each other, so the audit walk crosses planes in one hop.

## Scope / Out of scope

- **In:** strands 1–7; migration + backfill + tests; API contract package additions
  (OpenAPI/TS client regeneration); `web-api.md` § Conversations rewrite in the same
  change; deferred.md updates; ADR; rollback plan for the backfill.
- **Out (⏸ stays deferred, named):** answer promotion to artefact block · shared search
  request conversion · streaming for *planning* turns (chat streams; planning stays
  blocking — its own later uplift) · recall beyond the window (incl.
  cross-planning-conversation rationale carry) · feeding the live read executors to the
  watch deliberation sites (`read_tools=None` — adjacent, untouched) · multi-artefact
  read-model widening (workspace-cluster) · catch-me-up / multi-user visibility ·
  Bedrock routing · presentational per-run segmentation of the legacy rolling thread ·
  chats that replan or trigger runs (never — a hand-off link is the ceiling) ·
  cross-chat memory/recall (2026 practice keeps it opt-in and memory-mediated; our
  chats stay mutually blind, knowledge travels via artefacts) · LLM auto-titling
  (first-question truncation v1; async cheap-model titling is a noted easy upgrade) ·
  regenerate/edit/branching (the pair→per-message row split is its named migration
  seam, rev 2.4) · resumable mid-stream recovery (Redis-style delta buffer — additive
  later precisely because the DB only ever commits terminal rows) · answer
  thumbs-feedback → Langfuse scores (rev 2.5 — the eval slice's gold-set seam; that
  slice decides the surface).

## Constraints & approval gates

Gates this contract asks the owner to open (approval = contract approval):
- **Schema**: strand 1 — new tables/columns are additive; **one data migration**
  (legacy planning-conversation backfill) on live production data.
- **Public interface**: strand 3 (additive under `/api/v1`; SSE untouched; planning
  endpoints keep paths).
- **Prompt surface**: `chat_v1` (lead-authored; high-leverage — named per house rule).
- **Egress**: none new — same approved OpenAI inference route, new call site; **no**
  search egress from chat by construction.
- **Dependencies**: none expected (no markdown renderer — plain-prose answers).
- CI / prod config / auth: untouched.

## Public / private boundary

Chat and planning transcripts (user prose + corpus-derived text) are private — DB only,
never committed, never in fixtures unless sanitized per the sanitized-fixtures policy.
Contract/rubric/plan/ADR are public-safe. Repo is public — nothing project-real in test
data.

## Model route

OpenAI under the approved controls (v3.0 posture; Bedrock behind the routing seam).
New surface: `chat_v1` on `POLICY_ATLAS_CHAT_MODEL`, **default `gpt-5.6-terra`**
(owner call, rev 2.8 — the faster class fits the conversational budget; same
provider, same approved route).
The async enrichment reuses the **existing grounding-judge surface and model class**
(rev 2.7) — a new call site, not a new prompt surface; any judge-prompt adaptation
for chat-shaped claims is lead-only and version-bumped.
Prompt-bearing: `CHAT_SYSTEM_PROMPT` + chat wire-model field descriptions — lead-only.
Staging OpenAI quota exhausted (honest-429) — the live check runs locally against a
funded key, or after billing top-up.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — per-kind turn tables; no speculative unified turn row.
- **Flag, don't drop** — the citation floor strips-and-downgrades visibly, never silently.
- **Honest absence** — "the corpus doesn't hold this" is a first-class answer shape;
  legacy lineage columns stay `NULL`, never fabricated.
- Deferred seams land in deferred.md, not as silent omissions.

## Stop conditions

Halt and escalate when: any gate would widen beyond the strands (e.g. a reshape of
planning-turn columns turns out to be needed) · the backfill rule can't be made honest
for some live project state · executor wiring for a completed run needs runner changes
beyond trivial plumbing · scope would grow past this slice · turn/token budget spent.

## Acceptance checks

- `make verify` green (root; backend + frontend).
- **Deterministic tests**: migration up/down **+ backfill fixture cases** (no-run
  project · completed-run project · mid-replan project) · one-active-planning-
  conversation invariant · planning-conversation closure on run completion + seeded
  successor · planner rehydration scoped to conversation · chat turn idempotency/stale/
  in-progress · eligibility fences (`no_completed_run`, `run_active`) · BOLA 404s on
  conversations/turns · citation floor (fabricated id stripped + tier downgraded; zero
  citations → pure-LLM label) · chat tool set contains no `search`/write tool
  (allowlist test) · archive semantics (chats only) · lineage walk (conversation → plan
  → run → artefact) on a stub run · stub-backend chat e2e (create → turn → durable
  rehydration) · **streaming contract tests** (typed progress events then deltas then
  exactly one terminal payload; mid-stream failure → honest failed row + client
  recovery; client cancel → generator cleanup + partial prose persisted as `cancelled`
  with inert markers + no-tier badge; idempotent retry of a completed turn replays
  stored answer without re-generation; disconnect cleanup) · **citation-floor tests** (unresolvable/out-of-range citation stripped;
  orphan marker stripped; compaction numbers survivors by first appearance; uncited
  entries never displayed; zero survivors → pure-LLM answer, no judge call) ·
  **judge-enrichment tests** (per-citation verdicts attach on the turn row — no
  answer-wide chip; judge failure/timeout leaves citations "unchecked" and
  the turn completed; retry replays enriched payload when present; stub-judge
  deterministic path) · **cross-chat concurrency test** (concurrent turns in different chats of one
  project share no turn state — the V2 request-scoped-state lesson) · frontend
  component tests (library, switcher, per-citation verdicts + pure-LLM/stopped
  markers, composer states incl. stop button,
  hand-off affordance, stream rendering + activity summary).
- **Live manual check (contract-time scope pin):** on one existing completed-run
  project — post-migration state sane (legacy planning conversation status honest);
  open a chat from the artefact; one provenance-lookup + one generative-synthesis
  question; citations resolve to real dossiers, tier labels render; an
  evidence-not-held question renders the planning hand-off; thread + turns survive an
  API restart; library rename/archive/reopen round-trip; "Run the analysis again" opens
  a fresh planning conversation seeded from the executed plan. Plus the one cheap
  full-chain smoke (existing mock-journey e2e in CI). Estimated wall time ≤30 min. A
  full live end-to-end run is deliberately **not** in scope.
- AI-judge eval of answer quality is **not** in this slice — named input to the
  deferred eval slice.

## Verification evidence expected

`verification.md`: command outputs · migration + backfill evidence (incl. the live-DB
state before/after and the rollback rehearsal note) · live-check notes with the
questions and rendered tiers/citations · restart-durability note · diff summary ·
public-safety confirmation · deferred-seam list.

## Risk tier & review focus

**Tier 4** — everything Tier 3 was (schema + public interface + a new prompt-bearing
surface consuming untrusted input) **plus a data migration on live production data**
(the legacy backfill) and a restructure of the production planning surface. Tier-4
additions: human-approved plan (standard here anyway) · ADR · **rollback plan for the
migration**. Review stack: contract verifier · code review (medium, per review-economy)
· one security lane (injection posture, tool-set boundary, BOLA, idempotency races) ·
adversarial review at contract + plan + code · human deep review. Focus: backfill
honesty + rollback · the one-active-planning-conversation invariant under race ·
tool-set security boundary · citation-floor correctness · prompt-injection posture ·
scope creep toward the deferred seams.
