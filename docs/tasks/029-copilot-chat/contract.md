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
  `answer_payload` JSONB (citations, trust tier, bounded tool digest) ·
  `capability_run_id` (nullable FK, `uq_capr_id_project` composite precedent — records
  which run's committed state answered; provenance, **not** scope) ·
  `status ∈ pending | completed | failed` · `created_at`, `completed_at`.
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
- **No streaming, no SSE change** (no token streaming exists; 028 froze the SSE
  vocabulary). Blocking request/response with the breathing-row affordance; streaming
  is a named deferred seam.

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
- **Fast-path discipline — pinning the spec's 🟡**: chat **skips the verify pass**.
  Trust is carried by labelling with deterministic floors: (a) cited chunk/finding ids
  must be in the set the tool loop actually returned this turn — anything else is
  stripped and the tier downgraded; (b) zero surviving citations forces the "pure LLM
  reasoning" label; (c) no answer renders untier-labelled (§3.3 taxonomy). An ungrounded
  answer indistinguishable from a grounded one is the cardinal sin this prevents.
- Both spec flavours in scope: *provenance lookup* and *generative synthesis* rendered
  into chat, not persisted as artefact content.
- **Evidence-not-held honesty + hand-off**: when the corpus can't answer, the answer
  says so and points at the planning conversation (a rendered link/affordance — never a
  plan mutation from chat). The full "convert to shared search request" affordance stays
  deferred.
- **Promotion to artefact block stays deferred** (spec: promotion re-runs the full bar).

### 5 — Context assembly (window, not full replay)

Per-turn chat context = the conversation's recent window (last K turns verbatim, K pinned
at plan time) + the current question + a compact project frame (question, coverage
sentence, artefact skeleton(s)). **Recall over older turns is deferred** (window-first,
honestly). Stored HTTP projections are never fed back to the model (027 rule).

### 6 — Frontend: conversation-aware rail + Chats library

- The rail hosts the **active conversation** with a switcher/library: planning
  conversations (current + closed) and chats, Claude-Projects-style. Copy follows the
  copy-text principle — labels over explainers; user-facing noun is **"chat"**.
- Entry points: the artefact reader ("Ask about this analysis" — opens a chat with the
  artefact as *entry context*, not a fence) · the 028 "evidence base is ready" card ·
  the library ("New chat") · "Run the analysis again" → opens the new planning
  conversation.
- **Answers render as prose + citations + tier chip** — `whitespace-pre-wrap` + scrub,
  **no markdown dependency**; the `chat_v1` prompt constrains answers to plain
  paragraphs. Citations render as a references footer (source title → id-keyed dossier
  open); tier chips use only the locked `TIER_LABEL`/`TIER_TEXT` vocabulary.
- Composer is the extracted 028 `Composer` with per-kind copy; disabled states stay
  honest (pending turn; fence states show why).
- State layer mirrors `usePlanningTranscript` (durable query + optimistic reducer +
  per-`client_turn_id` retry); conversation switch is a query-key change.

### 7 — Tracing hygiene

One Langfuse `session_id` **per conversation** — chats *and* planning conversations
(discharging the known planning wart of a throwaway session per turn, which the
conversation entity now makes natural). Prompt-version metadata on every call.

## Scope / Out of scope

- **In:** strands 1–7; migration + backfill + tests; API contract package additions
  (OpenAPI/TS client regeneration); `web-api.md` § Conversations rewrite in the same
  change; deferred.md updates; ADR; rollback plan for the backfill.
- **Out (⏸ stays deferred, named):** answer promotion to artefact block · shared search
  request conversion · token/SSE streaming · recall beyond the window (incl.
  cross-planning-conversation rationale carry) · feeding the live read executors to the
  watch deliberation sites (`read_tools=None` — adjacent, untouched) · multi-artefact
  read-model widening (workspace-cluster) · catch-me-up / multi-user visibility ·
  Bedrock routing · presentational per-run segmentation of the legacy rolling thread ·
  chats that replan or trigger runs (never — a hand-off link is the ceiling).

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
New surface: `chat_v1` on `POLICY_ATLAS_CHAT_MODEL` (default = orchestrator model).
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
  rehydration) · frontend component tests (library, switcher, tier chip, composer
  states, hand-off affordance).
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
