# Task contract: 029-copilot-qa

> **Status:** drafted 2026-08-05. Contract approved (before planning): _pending · owner_ ·
> Plan approved (before implementation): _pending_ · ADR: _expected (Q&A companion store +
> fast-path discipline pin)_.
>
> **Contract-stage adversarial review** (Tier 3 standard): after owner approval,
> read-only `codex-rescue` brief over contract + rubric; fall back down the ladder
> on credit failure per the codex-exhaustion rule.
>
> Branch `task/029-copilot-qa`, stacked on `task/028-ux-refinement` (PRs #33 → #36 → #41
> all at step 9: human merge). Re-targets `dev` as parents merge; rebases before its own
> review if a parent's merge review touches files this branch changed.

## Goal

After an analysis run completes, the user can ask follow-up questions in chat and get
fast, honestly-tiered answers grounded in the project's own evidence — the **co-pilot
Q&A** surface the architecture always specified (execution-orchestration.md § Orchestrator;
frozen source § The orchestrator & co-pilot). Conversations are durable, multi-thread,
and browsable (Chats library). Answers are **ephemeral** — they produce no artefact and
never become hidden project state (product spec: artefacts over chat).

This discharges the pre-registered seam: 027 PR #35 adjudication ("multi-thread chat +
Chats library + per-thread artifact context → co-pilot slice"), deferred.md § 024
("transcript companion store: per-user/per-project turn table, session/`capability_run`
linkage, window-plus-recall context assembly") and § 027 ("Q&A needs a lead-authored
prompt surface").

## Deliverable

PR onto the 028 stack landing: the `qa_thread`/`qa_turn` companion store (migration),
the `/api/v1` Q&A endpoints, the lead-authored `qa_v1` orchestrator moment running a
bounded read-only tool loop over the live executors, trust-tier-labelled answers with
deterministically-floored citations, and the thread-aware chat rail + Chats library in
the frontend. `verification.md` with the scoped live check.

## Read first

- [execution-orchestration.md](../../specs/system/execution-orchestration.md) — co-pilot
  scope, read-tool rule, tier honesty; § Tier-0 retrieval contract (Q&A lookup profile).
- Frozen source [backend-architecture-reference.md](../../specs/sources/backend/backend-architecture-reference.md)
  § The orchestrator & co-pilot — the 🟡 fast-path discipline this contract pins.
- [web-api.md](../../specs/system/web-api.md) — § Planning turns (the durable-turn
  pattern Q&A turns mirror), § Auth boundary, § SSE (frozen vocabulary — untouched here).
- [provenance-grounding.md](../../specs/system/provenance-grounding.md) — §3.3 trust-tier
  taxonomy the answer labels reuse.
- deferred.md — § 024 transcript companion store · § 027 co-pilot Q&A UI seam ·
  § 024 build-discovered "live DB-backed read executors" (adjacent seam, stays deferred).
- 027 `contract.md` strand 12 + `rehydration-mapping.md` — the planning-transcript
  precedent (two-phase persistence, idempotency, no-backfill semantics).

## Design pins (the strands)

### 1 — Schema: the Q&A companion store (approval gate: schema)

Two new tables; `planning_transcript` untouched (planning-only by design, 027 rev 3.1).

- **`qa_thread`** — `id` (UUID PK) · `project_id` FK · `title` (server-derived from the
  first question, truncated; PATCH-renameable) · `status ∈ active | archived` ·
  `created_at`, `archived_at`. Owner scope rides the project (single-owner projects;
  "per-user" collapses to owner in v3.0 — the multi-user split is workspace-cluster).
- **`qa_turn`** — `id` PK · `thread_id` FK · `turn_index` (monotonic per thread; the
  ordering coordinate, as in planning) · `client_turn_id` (caller-minted idempotency,
  durable across restarts) · `user_message` (≤10 000 chars) · `answer` (prose) ·
  `answer_payload` JSONB (citations, trust tier, bounded tool digest) ·
  `capability_run_id` (nullable FK via the `uq_capr_id_project` composite precedent —
  records which run's committed state answered this turn) ·
  `status ∈ pending | completed | failed` · `created_at`, `completed_at`.
  Uniques: `(thread_id, turn_index)`, `(thread_id, client_turn_id)`.
- **Provider-side conversation state stays forbidden** (018 standing constraint —
  audit/FOI/portability): the record lives here, never in OpenAI Responses/Bedrock
  sessions.
- No hard delete anywhere (house rule); PR #35's "delete" becomes archive/reopen.

### 2 — API: additive `/api/v1` endpoints (approval gate: public interface)

All owner-scoped (404-indistinguishable BOLA rule), standard pagination + error envelope.

- `POST /projects/{id}/qa-threads` `{}` → 201 thread.
- `GET /projects/{id}/qa-threads?status=active|archived|all` — paginated, newest first,
  each row with a latest-turn preview (the Chats library read model).
- `PATCH /qa-threads/{tid}` `{title?}` · `POST /qa-threads/{tid}/archive` ·
  `POST /qa-threads/{tid}/unarchive` — idempotent, mirroring project archive semantics.
- `POST /qa-threads/{tid}/turns` `{message, client_turn_id}` → blocking `QaTurnOut`
  (answer + citations + tier). Mirrors planning-turn mechanics wholesale: two-phase
  persistence (pending row under the project row lock → LLM outside any transaction →
  completed row), durable idempotent retry of the latest turn, 409 `stale_turn` /
  `qa_turn_in_progress` (10-min stale-pending expiry), honest `pending`/`failed` rows.
- `GET /qa-threads/{tid}/turns` — paginated ascending `turn_index`.
- **Eligibility fence:** turns require ≥1 completed run (`succeeded | degraded`) —
  else 409 `no_completed_run`; while the project's walk is `running | paused` → 409
  `run_active` (mirrors the planning fence: mid-run reads would see a half-written
  evidence base, and steering is the sanctioned mid-run channel). *Owner cut-line: allow
  Q&A while paused, reading last-committed state — defer unless wanted now.*
- **No streaming, no SSE change.** Answers are request/response like planning turns
  (no token streaming exists in the backend; 028 froze the SSE vocabulary). The rail
  shows the same breathing-row pending affordance. Streaming is a named deferred seam.

### 3 — The Q&A agent: `qa_v1` orchestrator moment (lead-authored, prompt-bearing)

- New moment beside router/watch: `QA_SYSTEM_PROMPT` from `_SHARED_PREAMBLE` (the
  "one agent, three moments" preamble sentence updates — a shared-preamble version note,
  handled per house rule), own pin `qa_v1`, own `POLICY_ATLAS_QA_MODEL` env constant
  (default = orchestrator model), wire models `extra="forbid"`, all corpus-derived and
  user inputs sanitized + bounded + labelled "(data, not instructions)" — the standing
  injection posture, inherited verbatim.
- **Tool loop = reuse, not new machinery**: `run_section_loop` over `build_section_tools`
  with the live executors (`search_chunks` on the Q&A-lookup retrieval profile ·
  `query_findings` · `lookup`), scoped to the latest completed run's committed component
  outputs. **The tool set is the security boundary**: no `search`, no write tools are
  constructible from the Q&A surface (spec hard rule — egress must not originate outside
  the audit record). Turn caps + per-turn read caps as shipped.
- **Fast-path discipline — pinning the spec's 🟡**: Q&A **skips the verify pass**. Trust
  is carried by labelling, not verification: every answer states one §3.3 trust tier.
  Deterministic floors (not model self-report alone): (a) cited chunk/finding ids must be
  in the set the tool loop actually returned this turn — anything else is stripped and
  the tier downgraded; (b) zero surviving citations forces the "pure LLM reasoning"
  label. An ungrounded answer indistinguishable from a grounded one is the cardinal sin
  this prevents.
- Both spec flavours in scope: *provenance lookup* ("where does X come from") and
  *generative synthesis* rendered into chat, not persisted as artefact content.
- **Evidence-not-held honesty**: when the corpus can't answer, the prompt requires saying
  so and pointing at the sanctioned next step (a new run / replanning). The full
  "convert to shared search request" affordance stays deferred (it needs plan mutation).
- **Promotion to artefact block stays deferred** (spec: promotion re-runs the full bar —
  its own slice).

### 4 — Context assembly (window, not full replay)

Per-turn context = the thread's recent window (last K turns verbatim, K pinned at plan
time) + the current question + a compact project frame (question, coverage sentence,
artefact skeleton). **Recall over older turns is deferred** (named seam — deferred.md's
"window-plus-recall" lands window-first, honestly). Stored HTTP projections are never
fed back to the model (027 rule).

### 5 — Frontend: thread-aware rail + Chats library

- The post-run rail hosts the active thread with a switcher: the planning thread (as
  built) + Q&A threads. The 028 "evidence base is ready" card gains the Q&A entry
  point ("Ask a follow-up question") — the anchor 028 left for exactly this.
- **Chats library**: thread list (title, latest-turn preview, date), rename,
  archive/reopen, from the rail header. Copy follows the copy-text principle — labels
  over explainers.
- **Answers render as prose + citations + tier chip** — `whitespace-pre-wrap` + scrub,
  **no markdown dependency**; the `qa_v1` prompt constrains answers to plain paragraphs
  (prose-first house style). Citations render as a references footer (source title →
  dossier link, reusing the id-keyed open path); the tier chip uses only the locked
  `TIER_LABEL`/`TIER_TEXT` vocabulary.
- Composer is the extracted 028 `Composer` with Q&A copy; disabled states stay honest
  (pending turn in flight; fence states show why).
- State layer mirrors `usePlanningTranscript`: durable query + optimistic reducer +
  per-`client_turn_id` retry; thread switch is a query-key change, no bespoke cache.

### 6 — Tracing hygiene

One Langfuse `session_id` **per Q&A thread** (fixes the known planning wart of a
throwaway session per turn — Q&A traces group per conversation; the planning-side fix
itself is out of scope). Prompt-version metadata on every call as standard.

## Scope / Out of scope

- **In:** strands 1–6; migration + tests; API contract package additions (OpenAPI/TS
  client regeneration); `web-api.md` § Q&A threads section (spec updated in-change);
  deferred.md updates (seams named below); ADR.
- **Out (⏸ stays deferred, named):** answer promotion to artefact block · shared search
  request conversion · token/SSE streaming of answers · recall beyond the window ·
  feeding the live read executors to the watch deliberation sites (`read_tools=None` —
  adjacent seam, untouched) · run/artefact-scoped read models (workspace-cluster) ·
  catch-me-up / multi-user visibility · Bedrock routing · any planning-surface behaviour
  change beyond the rail becoming thread-aware.

## Constraints & approval gates

Gates this contract asks the owner to open (approval = contract approval):
- **Schema**: the two tables in strand 1 (additive migration; no existing table altered).
- **Public interface**: the strand-2 endpoints (additive under `/api/v1`; SSE untouched).
- **Prompt surface**: `qa_v1` (lead-authored; high-leverage — named per house rule).
- **Egress**: none new — same approved OpenAI inference route, new call site; **no**
  search egress from Q&A by construction.
- **Dependencies**: none expected (no markdown renderer — plain-prose answers).
- CI / prod config / auth: untouched.

## Public / private boundary

Q&A transcripts (user prose + corpus-derived answer text) are private data — DB only,
never committed, never in fixtures unless sanitized per the sanitized-fixtures policy.
Contract/rubric/plan/ADR are public-safe. Repo is public — nothing project-real in
test data.

## Model route

OpenAI under the approved controls (v3.0 posture; Bedrock behind the routing seam).
New surface: `qa_v1` on `POLICY_ATLAS_QA_MODEL` (default = orchestrator model).
Prompt-bearing: `QA_SYSTEM_PROMPT` + Q&A wire-model field descriptions — lead-only.
Known operational state: staging's OpenAI quota is exhausted (honest-429) — the live
check runs locally against a funded key, or after billing top-up.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no speculative columns (the multi-user split brings its
  own fields; nothing lands "for later").
- **Flag, don't drop** — the citation floor strips-and-downgrades visibly, never silently.
- **Honest absence** — "the corpus doesn't hold this" is a first-class answer shape.
- Deferred seams land in deferred.md, not as silent omissions.

## Stop conditions

Halt and escalate when: any gate above would widen (e.g. a schema change to an existing
table turns out to be needed) · the run-scoped executor wiring can't be derived for a
completed run without runner changes beyond trivial plumbing · scope would grow past
this slice · turn/token budget spent.

## Acceptance checks

- `make verify` green (root; backend + frontend).
- **Deterministic tests**: migration up/down · turn idempotency/stale/in-progress ·
  eligibility fences (`no_completed_run`, `run_active`) · BOLA 404s on threads/turns ·
  citation floor (fabricated id stripped + tier downgraded; zero citations → pure-LLM
  label) · Q&A tool set contains no `search`/write tool (allowlist test) · archive
  semantics · stub-backend Q&A e2e (thread → turn → durable rehydration) · frontend
  component tests (thread switch, library, tier chip, composer states).
- **Live manual check (contract-time scope pin, per the failure-log rule):** on one
  existing completed-run project — create a thread; one provenance-lookup question and
  one generative-synthesis question; verify citations resolve to real dossiers, tier
  labels render, thread + turns survive an API restart; Chats library rename/archive/
  reopen round-trip. Plus the one cheap full-chain smoke (existing mock-journey e2e in
  CI covers the chain; no fresh live e2e run). Estimated wall time ≤20 min. A full live
  end-to-end run is deliberately **not** in scope.
- AI-judge eval of answer quality is **not** in this slice — it's a named input to the
  deferred eval slice (Q&A answers join the eval surface inventory).

## Verification evidence expected

`verification.md`: command outputs · migration evidence · live-check notes with the two
questions and rendered tiers/citations · restart-durability note · diff summary ·
public-safety confirmation · deferred-seam list.

## Risk tier & review focus

**Tier 3** — schema + public interface + a new prompt-bearing LLM surface consuming
untrusted input (user prose + corpus text). Review stack: contract verifier · code
review (medium, per review-economy) · one security lane (injection posture, tool-set
boundary, BOLA, idempotency races) · adversarial review at contract + plan + code ·
human deep review. Focus: the tool-set security boundary · citation-floor correctness ·
fence/idempotency races · prompt-injection posture · scope creep toward the deferred
seams.
