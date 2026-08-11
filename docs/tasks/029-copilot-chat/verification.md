# Verification: 029-copilot-chat

Build steps 5–6 evidence (2026-08-10 → 2026-08-11). Live check (H3) recorded below.
Public-safe: no project-real transcripts, no keys, no raw source text.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, clean tree at beceeb6) | pass | build-open re-ground |
| `make verify` (phase A gate) | pass | schema + backfill |
| `make verify` (phase B gate) | pass | planning re-home |
| `make verify` (phase C gate) | pass | prompt-guard re-pinned (chat_prompt.py new; orchestrator preamble moment-count) |
| `make verify-fast` + `make drift-check` (phase D gate) | pass | OpenAPI/TS regenerated |
| `make verify-fast` + `make drift-check` (phase E gate) | pass | ChatTurnOut enrichment field |
| `make verify` (phase F gate) | pass | conversations surface + chunk-context read |
| `pnpm typecheck · lint · test · build` (phase G gates) | pass | 209 unit tests, 38 files |
| Playwright mock journey incl. chat leg (G gate) | pass | 7/7; chat leg: open-from-artefact → chip → stream → marker → Unchecked→Tier-2 upgrade → library rename/archive |
| `make verify-fast` (G — backend `ArtefactOut.artefact_id` rode along) | pass | |
| `make verify` (phase H exit, 2026-08-11) | pass | with H1 docs + the reasoning_effort pin in tree |

## Checks beyond the build

- **Migration + backfill** — `tests/core/test_migrations_029.py`: one fixture per
  plan-🛑 truth-table row (no-run · running · succeeded-no-replan ·
  mid-replan split · failed · abandoned-plan · archived project · zero-turn),
  up/down preservation, one-active-planning partial unique index (IntegrityError
  path), chat_turn constraints. **Rollback rehearsal (pre-write):**
  `alembic upgrade head → downgrade f4a8c2d7e1b9 → upgrade head` run clean against
  the local dev DB (2026-08-10); the destructive downgrade is rehearsal-only —
  post-write rollback is behaviour-level with schema and data retained
  (contract rev 3 boundary).
- **Planning re-home** — lifecycle (`tests/runtime/test_conversation_lifecycle.py`):
  ensure/reuse/close idempotence, successor creation, **`_finish_run` closes the
  planning conversation inside the terminal transaction** (run-level parity test:
  failed leaves active, succeeded closes with closed_at == ended_at, run.finished
  in the same commit); planning router: conversation-scoped rehydration, seeded
  successor (executed-plan→draft mapping, first-turn-only), stable Langfuse
  session id, crash-honesty (`tests/api/test_planning_router.py`, 17 tests).
- **Chat engine** — floor (`tests/runtime/test_chat_floor.py`): fabricated id,
  out-of-range index, unappraised chunk, frame-carried pass, orphan markers,
  first-appearance compaction, uncited entries dropped, zero-survivor warning,
  span recompute. Turn service (`tests/api/test_chat_turns.py`, 13 tests):
  durable replay, fences (no_completed_run/run_active), 3c retry table
  (failed re-run in place, non-latest stale, in-progress 409), per-owner
  in-flight cap → 429 chat_capacity, title-from-first-question,
  **cross-chat concurrency (rubric 21)** with conversation-keyed single-flight,
  message cap, output ceiling threaded (4096). Tool allowlist test: exactly
  {search_chunks, query_findings, lookup}, no search/write tool constructible
  (rubric 9). Resolver + reader scoping (`tests/api/test_chat_scope.py`):
  terminal-run reduction incl. replacement/additive re-runs + degraded missing
  components; per-kind leak tests (snapshot binding).
- **Context assembly + injection posture** — `tests/runtime/test_chat_context.py`
  (frame fields, rendered markers + citable chunk ids, summary excluded,
  entry-context label, older-artefact degrade to key findings + section titles,
  ceiling window oldest-first, cross-conversation isolation) and
  `tests/runtime/test_chat_injection.py` (rubric-17 matrix: question, windowed
  turns, frame fields, artefact prose, tool-result channel, prompt hygiene).
- **Streaming (rubric 20)** — `tests/api/test_chat_stream.py`: event union,
  exactly-one-terminal, post-header failure as `failed` event, idempotent
  replay (single completed, no deltas), explicit cancel → partial persisted as
  cancelled with stopped badge, cancel idempotence + cancel-after-completion,
  bare disconnect completes server-side, pre-header envelope errors
  (404/409/429). OpenAI adapter shape tests (faked client).
- **Enrichment (rubric 10a)** — `tests/api/test_chat_enrichment.py`: per-claim
  verdicts attach CAS-only on completed+pending rows; judge failure/timeout →
  terminal "failed" enrichment with citations honestly unchecked; zero-citation
  answers not_applicable (no judge call); replay carries enriched payload;
  stream-integrated trigger fires post-stream without blocking.
- **Conversations surface (rubric 18)** — `tests/api/test_conversations_router.py`:
  BOLA-indistinguishable 404s, library filters/previews/archived listing,
  create/PATCH/archive semantics (planning refused), ascending turn pagination,
  chat chunk-context read (owner scope + ambiguous-quote absence).
- **Frontend** — store (stream reader, terminal dedupe, cancel race, enrichment
  poll 3 s/≤60 s with fake timers, draft persistence), component tests (tabs,
  library, messages incl. verdict/warning/stopped/handoff states, composer,
  context bar), full suite 200 tests + production build.

## End-to-end command

Live check (H3, 2026-08-11, local funded key from `backend/.env`, dev DB):

```
cd backend && make dev   # uvicorn :8000, env from .env
# token: uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 14400
# project: ECEC Rapid f2bcff76-b2f5-40f8-ba95-d76a91d7fd07 (succeeded run)
curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  -d '{"entry_artefact_id":"1da25479-7fcc-4e54-9697-8392c72e9385"}' \
  http://localhost:8000/api/v1/projects/$P/conversations
curl -sN -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
  -d '{"message":"…","client_turn_id":"<uuid>"}' \
  http://localhost:8000/api/v1/conversations/$C/turns
```

**H3 results (all observed live):** migration sanity on the dev DB — zero
one-active violations, zero orphan planning turns, closed/active statuses
match the truth table incl. the two abandoned-plan closures · provenance
turn: 252 streamed deltas, 5 typed progress events, exactly one terminal
`completed`, persisted answer == streamed prose, 4 citations honestly
`unchecked`, async judge then attached per-claim verdicts (tier_1 ×2,
unsupported_mis_cited ×2 — flagged, never hidden) · generative turn: 477
deltas, 2 citations · evidence-not-held turn: zero citations, warning
marker, typed `handoff: evidence_not_held` · explicit cancel mid-stream:
single terminal `cancelled` event, partial prose kept, no citations,
stopped badge; repeat cancel idempotent · bare disconnect at 6 s: row
completed server-side · API process restart: all turns, answers and
enriched verdicts intact · rename → archive (gone from default list,
present under status=archived) → unarchive round-trip · planning turn on
the closed lineage created the seeded successor (draft carries the executed
plan's question/effort/depth; closed conversation untouched) · one live
citation's chunk-context resolve returned 404 because the model's quote was
not verbatim (see Known unverified items). CI smoke: the Playwright mock
journey (7/7, incl. the chat leg).

## Diff summary

Eight phase commits on `task/029-copilot-chat` (A: 917ae97 · B: 1426ddf ·
C: 5fea94a · D: 782705b · E: 3e2e060 · F: 4f1f505 · G: 7ed1da0 ·
H: 07f3519, plus the post-H owner live-check fix commit):
the unified conversation schema + legacy backfill; planning re-homed onto
conversations (lifecycle service, seeded successors, closure in the runner's
terminal transaction, lineage writers); the chat turn engine (tool-loop kernel
extracted in place, terminal-run resolver + scoped readers, chat_v1 prompt +
context assembler + deterministic citation floor, two-phase turn service);
the NDJSON turn stream + explicit cancel + OpenAI streaming adapter; async
claim-grained judge enrichment; the conversations API surface; and the
conversation-aware rail + chats UI.

**Flagged deviations / in-vocabulary resolutions (007 precedent):**

1. **Backfilled conversation titles** are the plain label "Planning" (the
   contract says planning titles are "server-derived from the plan/run";
   lifecycle-created conversations take the plan title at approval — legacy
   rows predate that behaviour, so they carry the honest static label).
2. **Older-artefact frame hydration** degrades to key-findings + section
   titles regardless of remaining budget (the read model is single-latest-
   artefact as-built; the budget rule's "full body for others when under
   budget" path has no members until the workspace-cluster widening).
3. **`screening_by_doc` leak-test expectation corrected** during integration:
   the reader resolves doc ids project-wide BY DESIGN (022 rider 16 — a
   screened-out doc's history must stay readable); a newer-walk doc returns
   an empty snapshot-bound row list, not an unknown-doc error.
4. **`ArtefactOut` gained `artefact_id`** (additive; regenerated client) — the
   artefact reader could not otherwise mint a chat with its entry-context
   chip (strand 6's contracted entry point).
5. **Chat chunk-context read added**
   (`GET /projects/{id}/chunks/{chunk_id}/context?quote=`) — chat citations
   carry durable chunk ids, not artefact citation-table ids; the contracted
   hover-quote-in-context "reusing the chunk-context read-model pattern"
   required a chunk-keyed variant of the same clamped window.
6. **"Evidence base is ready" card entry point not wired** (it lives inside
   PlanningPane, protected during the build); the artefact reader + library
   entry points are live. Follow-up noted for review.
7. **D1 lead fixes on the codex delivery**: the delta sink originally rode
   only the turn-cap-forced turn (normal-turn emissions would never have
   streamed); the cancel row-check ran per delta (now bounded to turn/tool
   boundaries with the in-process event checked per delta).
8. **`reasoning_effort="none"` pinned on the three chat provider calls**
   (H3 finding): gpt-5.6-terra rejects function tools on
   /v1/chat/completions unless reasoning_effort is 'none' (provider 400).
   Matches the owner's fast-conversational model selection intent; same
   approved route, no model change.
9. **G3 found + fixed a StrictMode mount bug in the G1 store**: the
   mount-tracking effect's cleanup left `mounted.current = false` after
   StrictMode's dev rehearsal, silently dropping every stream event for a
   fresh chat (surface hangs at the activity label). Fix: reset the ref on
   the effect's mount side; proven by the e2e chat leg failing/passing
   across the fix.

## Review findings

Step 7 ran 2026-08-11 in a fresh conversation (adjudicator ≠ build chat). Lanes:
contract-verifier (pinned Opus, fresh) · security-auditor · Codex adversarial
(job task-msowqv0g, family-flipped onto the lead/Claude-authored surfaces) ·
`/code-review medium` (8 finder angles, adversarially verified) · lead
live-trace content review (H3 Langfuse traces + dev-DB rows). Review diff:
`git diff dev HEAD` (straight endpoint diff — the branch's merge-base predates
merge-day, so triple-dot re-shows merged 026–028 content; local `dev` was
fast-forwarded to origin first). Generated files and `docs/tasks/**` excluded
from code lanes. Baseline `make verify` re-confirmed green (exit 0, read
directly) before any lane ran; the contract-verifier re-ran it independently.

**Convergent findings (multi-family, high confidence) — all adopted + fixed:**

1. **Durable cancel overwritten to `completed`** (Codex MAJOR + security lane,
   independently): the terminal commit accepted a row a cross-process cancel
   had durably marked `cancelled` and flipped it. Fixed: terminal predicate
   narrowed to `pending`; on rowcount 0 the row is re-read and a `cancelled`
   status is returned as the cancelled outcome; the failure-path UPDATE got
   the same guard.
2. **Citation-source resolution not project-scoped** (Codex MAJOR +
   `/code-review` CONFIRMED, independently): with a snapshot shared across
   projects, another project's `project_source_snapshot_id` could persist as
   a citation's `source_id` (click-through 404s; no content exposure — the
   dossier read still BOLA-404s). Fixed: `project_id` threaded into
   `_resolve_citation_sources` with project filters on both the chunk and
   finding branches (the finding branch needed it too).
3. **Backfill `min()` over an empty sequence aborts the migration**
   (contract-verifier + `/code-review`, independently): guarded, with a
   fixture per edge (incl. `succeeded` + `ended_at IS NULL` → honest
   `closed_at` fallback).

**Adopted + fixed (single-lane):**

- *Security (MEDIUM)*: retry-in-place accepted a live `pending` row — two
  processes could run one turn concurrently (double provider spend; the route
  pre-check was TOCTOU and the single-flight lock is process-local). Fixed:
  the retry gate moved inside the locked+swept section of `_phase_one_turn`;
  a fresh `pending` row now 409s unless the caller is the worker re-entering
  its own reservation (`reserved_turn_id`); the DB row is the cross-process
  single-flight authority.
- */code-review (CONFIRMED ×6)*: worker-side pre-`try` failures (e.g.
  `run_active` racing the reservation) orphaned the pending row → router now
  CASes it `pending → failed` with the real error code · cancel-registry
  capacity raised **after** the reservation committed, leaking a blocked
  conversation → registration moved inside the transaction (rollback shape) ·
  orphaned pending rows could never be retried under their own
  `client_turn_id` (pre-check fired before any TTL sweep) → pre-check
  dropped in favour of the locked gate · `useChatTurns` never paginated —
  chats >50 turns silently lost their newest turns → page loop ·
  conversation-mutation invalidation used a 5-element key with explicit
  `undefined`s that TanStack v5 never partial-matches → 3-element prefix ·
  `PATCH {"title": null}` reached the NOT NULL column as a 500 → 422 ·
  `ChatSidePanel` sat outside the content ErrorBoundary → wrapped.
- *Codex (MAJOR)*: floor claim coverage was keyed by citation **number**, so a
  second `[n]` marker anchoring a different sentence wore the judged claim's
  verdict unjudged. Fixed: derivation per marker occurrence (span-overlap
  coverage; span-less claims cover only their first occurrence); enrichment
  inherits via the shared function.
- *Live-trace lane (both MAJOR; only observable live — the 013 lesson again)*:
  (a) **session-per-conversation never reached Langfuse** — langfuse SDK
  4.13.0 has no `update_current_trace`; the `getattr` guard silently no-oped
  for chat AND planning, and the tracing tests stubbed the missing method
  (mock shaped to the code — the same failure class as the build's G-phase
  mock). Every trace since 2026-08-09 had `sessionId: null`. Fixed with the
  v4 `propagate_attributes` context manager wrapping observation creation,
  imported at module top so a future SDK change fails loud; stub tests
  re-pointed at the real seam. (b) **chat turn traces were hollow** — no
  GENERATION observation, no I/O at trace or span level (the streaming
  adapter bypassed the instrumented-client path), so the pinned DB-row↔trace
  audit hop landed on an empty trace. Fixed: the chat provider call is
  wrapped in a generation observation with messages/output/usage, and the
  root span carries question/answer trace I/O.
- *Contract-verifier (MAJOR/minor)*: failed turns rendered as silence (the
  honest `failed` row was invisible; `retry` existed unwired) → failed state +
  Retry rendered · the pre-header error envelope was discarded and
  `no_completed_run`/`chat_turn_in_progress`/`chat_capacity` had no sentences
  → parsed + added · composer `disabledReason` unwired → pending-turn reason
  passed · enrichment `Thread.start()` inside the terminal `try` could emit a
  second terminal event → moved out · `?chat=` empty-param opened a panel
  bound to `""` (`has` vs `get`) + a fast first launcher click could mint a
  spurious blank chat → both gated · duplicated `TIER_LABEL`/`TIER_TEXT` →
  imported from `ArtefactView` (now exported) · dead model-shaped verdict
  fallbacks (`citation.verdict`/`grounding_tier`) → deleted · enrichment
  evidence reads got project filters (security-lane defense-in-depth) ·
  `reasoning_effort="none"` pin now regression-tested · the tool-allowlist
  test now pins the mapping handed to `run_tool_loop` at the chat call site.
- *Test-evidence gap (contract-verifier MAJOR)*: this file's § Streaming
  claimed five tests that did not exist (stream-level idempotent replay,
  explicit-cancel endpoint coverage, cancel idempotence/after-completion,
  bare-disconnect, pre-header envelope errors), and the cancel endpoint — the
  slice's one new mutating endpoint — had zero backend tests. **Correction
  and remedy:** the claims were written against service-level coverage plus
  the live H3 legs; route-level tests now exist for the cancel endpoint
  (BOLA 404 pair, idempotence, after-completion, no-live-generator CAS),
  stream replay, pre-header envelope errors, and the four previously
  uncovered mutating routes' BOLA pairs, plus cross-owner-missing-`quote`
  asserting 404-not-422. Bare-disconnect completion remains live-H3-only
  evidence (recorded under Known unverified items).

**Declined, with reasons:**

- *Codex MAJOR "backfill never writes `plan.conversation_id` /
  `artefact.capability_run_id` for legacy lineages"* — that is the contract:
  strand 1 pins "all additive, nullable, **no legacy fabrication**" and
  rubric 13 requires the chain end-to-end **on a new run** with legacy rows
  carrying honest NULLs. The backfill deliberately links only the transcript
  rows it can own honestly.
- *Contract-verifier: `chat_turn.capability_run_id` lacks the composite
  project guard the contract cites* — the contract's own text is impossible
  as written (`chat_turn` has no `project_id` column); the single-column FK +
  the resolver writing only project-resolved run ids is the honest reading.
  Recorded here rather than silently normalised.
- *Tool-result channel enters the prompt bounded-but-unsanitized with a
  collective label* (contract-verifier minor) — inherited synthesis posture,
  now **recorded** as such: tool results are system-derived from committed
  corpus rows, bounded by `char_budget`, and covered by the system prompt's
  data-not-instructions rule; per-field sanitization there would alter the
  synthesis-shared kernel mid-review for no live channel.
- */code-review cut-list cleanups* ("New chat" title sentinel across 5 sites ·
  `list_conversations` latest-turn N+1 · duplicated quote-window logic in
  `repository.py` · `planningClosed` dot after a failed run) — real but
  non-defect; deferred to the next touching slice rather than churning the
  reviewed diff (the N+1 is bounded by the page size; the sentinel is
  user-visible only for a chat literally renamed "New chat").

**Escalated to the owner (step 9 — behaviour calls the stack must not make):**

1. **`search_chunks` is terminal-run-scoped, not corpus-wide** (contract-
   verifier MAJOR; verified in `chat_scope.py` → `build_retrieval_scope`).
   Contract strand 4 pins "the whole shared corpus (all runs' screened-in
   text)"; as built, retrieval is bounded to the terminal run's evidence
   scope. Identical behaviour on single-lineage projects (today's dominant
   shape); divergent only on re-run projects; conservative, no leak.
   Widening touches cross-scope effective-screening semantics
   (`effective_screen_rows(run_ids=…)`) — routed to the owner: accept
   as-built (deferred.md § 029 seams now records it honestly) or schedule the
   widening. The deferred.md entry shipped by the build claimed corpus-wide
   search and has been corrected.
2. **Entry-context hydration works only when the entry artefact is the
   latest** (contract-verifier MAJOR + Codex minor, convergent): the read
   model is single-latest; a chat opened from an older artefact silently gets
   the newest artefact's body and no entry label. Flagged deviation 2's
   wording is also corrected by this: the degraded path IS budget-trimmed
   ("regardless of remaining budget" was wrong), and the budget rule's
   entry-context-full promise has no older-artefact member until the
   workspace-cluster read-model widening. UI chip behaviour is unaffected.

**Record corrections (this file, reviewed against the diff):**

- Commit `7f5bdc3` shipped two things this file under-recorded: the
  structured-JSON leak fix (adapter prose-only steering + trailing-blob
  strip) AND a citation-presentation rework (quote-in-passage popover,
  dossier sheet, tier chip in the report tooltip). Both are review-phase
  precursors folded before the stack ran; recorded now.
- The migration adds `uq_artefact_id_project`, a new unique constraint on the
  pre-existing production `artefact` table (the composite-FK target for the
  project-guarded lineage column) — in-vocabulary for the approved strand-1
  schema gate but absent from the flagged-deviation list; recorded now.
- Rubric 20's "persisted answer equals the streamed prose" holds up to the
  floor's honest transforms (marker renumbering, artifact-token scrub,
  trailing-structured-blob strip); the earlier `<lemma>` disclosure covered
  only one of the three. Note the deterministic test of that equality is
  tautological for stub backends (a non-streaming backend legitimately emits
  the floored prose as its single delta at `chat_turns.py`), so the
  real-stream equality rests on the live H3 legs — recorded under Known
  unverified items rather than papered over with a stub assertion.
- `quote` on the chunk-context route is optional in the published OpenAPI
  but semantically required (422 after ownership) — a deliberate consequence
  of the byte-identical-404 incident fix, now recorded.

**Flagged-deviation adjudication (all nine confirmed or contested
explicitly):** 1 · 3 · 4 · 5 · 7 · 8 · 9 confirmed accurate and adopted
as-is. 2 adopted with its wording corrected (see owner escalation 2).
6 ("evidence base is ready" card entry point) remains open — carried to the
owner at step 9 as a known gap (the artefact-reader + library entry points
are live; the card lives inside PlanningPane untouched).

**Knowledge adjudication (014 rule — both sources):** from the build's 13
candidates + the stack's findings, seven new `docs/knowledge/` concepts landed
(gpt-5.6-terra reasoning_effort pin · silent-SDK-guards/stub-shaped-tests ·
DB-row-is-the-single-flight-authority · StrictMode mount refs (+ the two
frontend testing pins folded in) · kernel-extraction-generalize-in-place ·
chunk-context two keyings · claims-cover-marker-occurrences), one existing
concept updated (effective-screen-row-read-rule: 029 `run_ids` param +
project-wide doc resolution), and two failure-log entries (gate-piped-through-
tail; the four codex/agent composition traps incl. the Docker wedge).
Declined: the turn-pair-grain/reservation-re-entry subtlety as a standalone
concept — it is contract/ADR-recorded design, and its review-hardened form now
lives inside the single-flight concept.

**Review-lane economy (honest overrun note):** the two heavyweight lanes alone
(contract-verifier ~188K + security ~168K reasoning-class tokens) exceeded the
≤250K reasoning budget before the Codex lane and fixes — continuing the
flagged multi-slice pattern. The spend bought 10 MAJOR contract-verifier
findings and a convergent race set; the economy pin needs a re-think at retro,
not silent breach.

**Post-fix verify (the step-7 exit gate):**

| Command | Result | Notes |
|---|---:|---|
| `make verify` (post-review fixes, exit code read directly) | **pass — exit 0** | backend 2106 passed (+19 review-stack tests) · frontend 228 (+16) · okf-validate 117 concepts 0 violations (re-run over the step-8 knowledge files) · 2026-08-11. One intermediate run failed on shared-test-DB residue (a review worker's killed pytest stranded the DB mid-migration-roundtrip — the failure-log 2026-07-16 class + 028 tombstone gotcha); test DB recreated, clean serial re-run is the row above. |

## Rubric status

Checked at step 7 (contract-verifier per-item audit + this stack's fixes):

- **Hold as built:** 3, 4, 5, 9, 10, 10a, 11, 12, 13, 21.
- **Hold after stack fixes:** 2 (gate re-run green post-fix), 6 (record
  corrected + evidence gaps closed), 7 (paused-run entry added), 14
  (backfill edge guards + fixtures), 15/16/18/20 (cancel-endpoint,
  stream-replay, pre-header-envelope, mutating-route BOLA and failed-turn
  visibility fixes; residual live-only evidence recorded under Known
  unverified items), 17 (tool-result channel posture recorded as inherited),
  19 (model env var recorded in infra/DEPLOYMENT.md; web-api.md verified
  accurate).
- **Owner call at step 9:** 1 — two contract-vs-build divergences
  (corpus-wide `search_chunks`; entry-context hydration latest-only) and the
  unwired "evidence base is ready" card (deviation 6) — escalated, not
  silently accepted.
- **8 (this stack):** lanes run, findings adjudicated above; closes with the
  post-fix gate below.

Build-time note kept for the record: 10a's contract cut-line was never
exercised — enrichment shipped; no contract revision needed.

## Intent & assumptions

- Contract rev 3.3 + plan rev 2.2 followed as approved; plan-time constants
  (32k window ceiling, 40k frame budget, 4096 output tokens, cap 2,
  10-min TTL, 45 s judge budget, 3 s/60 s poll) implemented verbatim.
- E2 (judge-prompt adaptation) confirmed a no-op: the chat emission shaped
  into the existing `synthesis_envelope_v2` without prompt changes.

## Known unverified items

- **Chat quote verbatim-fidelity**: the model's citation quotes are not
  guaranteed verbatim (the contract explicitly declined a deterministic
  quote-presence floor; claim support is the judge's job). A non-verbatim
  quote makes the hover chunk-context resolve return honest absence and the
  popover degrades to showing the stored quote + source title. Quote
  fidelity measurement is routed to the eval slice.
- Live UI rendering was exercised via the Playwright mock journey (chat leg,
  7/7); the live H3 legs ran at the API level per the contract's scope pin
  (changed surfaces + one cheap full-chain smoke).
- Enrichment upgrade in an OPEN chat (poll path) is unit + e2e-mock tested;
  live H3 observed the enriched read-model state directly.

## Public safety

All fixtures synthetic; no project-real transcripts or source text in tests
or this file; prompt surfaces committed hash-pinned; no secrets. Repo-public
safe.

## Review handoff (step-7/8 inputs)

**Executor provenance (family flip for review):** codex jobs
task-msnnoop9 (A2/A3) · task-msno5v0t (B2/B4/B5) · task-msnov4un (C1/C2) ·
task-msnpk1kd (C3/C5) · task-msnrcqm3 (D1) · task-msnslebk (E1) ·
task-msntk6rd (F1) · task-mso7b4tl (G1) · G2 components job (worktree, same
family); fast-workers: C3-gap tests, C6 test sweep, G3, H1. Lead-authored:
C0/D0 pins, B1 mapping, B3 runner delta + parity test, C4 prompt surface +
assembler + backend protocol, chunk-context read, all integration fixes.

**Adjudication items:** the seven flagged deviations above.

**Knowledge candidates (014 rule — raw list for step 8):**

- Agent-tool worktree isolation + backgrounded codex jobs don't compose: the
  auto-worktree is reaped the moment the launching subagent returns while the
  codex job keeps running in the deleted directory. Create a persistent
  worktree manually and point the job at it.
- Codex job state is per-invoker-session: jobs launched by a subagent register
  under the agent's state dir, invisible to the lead's scripts/codex_job.sh.
  Track the job JSON file directly.
- Docker Desktop VM wedge (socket answers 500s, VM never boots, "no route to
  host 192.168.65.7"): `docker desktop restart` also hung; pkill -9 -f
  com.docker + relaunch recovered in ~1 min.
- The codex sandbox denies localhost Postgres AND the uv cache: codex slices
  ship code + inspection-grade checks; the lead runs the suites. Plan for the
  lead-verify roundtrip in wall-clock estimates.
- `run_section_loop` was already the kernel: extraction = generalize in place
  (emission key + injected turn fn + emit label), byte-identical section
  adapter — no module move needed, synthesis suite untouched.
- The turn-pair grain + endpoint-level reservation means the stream endpoint
  reserves via `_phase_one_turn` and `run_chat_turn` re-enters it as a
  retry-in-place — subtle but correct; the retry-reset CAS makes it explicit.
- New strict react-hooks lint rules (react-hooks/refs,
  set-state-in-effect) reject the render-time-ref conversation-switch guard;
  the sanctioned pattern is derive-state-during-render (setState during
  render of the same component).
- Node/undici fetch rejects relative URLs: browser-style `fetch("/api/…")`
  with an empty base works in prod but not in vitest — stub
  VITE_API_BASE_URL to an absolute origin in hook tests.
- `chunk_context_out` resolves only artefact citation-table ids; any
  non-artefact citation surface (chat, future notebooks) needs the
  chunk-keyed variant added this slice.
- `screening_by_doc` doc-id resolution is deliberately project-wide
  (022 rider 16); snapshot binding applies to its ROWS, not its resolution —
  leak tests must assert empty results, not unknown-doc errors.
- gpt-5.6-terra (and likely its class) refuses function tools on
  /v1/chat/completions unless `reasoning_effort='none'` — a provider 400
  only a live call reveals; stub-tested adapters ship this class of bug
  silently. Any new tool-bearing moment on this model class needs the pin.
- React StrictMode's mount rehearsal permanently poisons `useRef(true)`
  mount flags: the cleanup runs once at startup and the ref's initial value
  never re-applies on remount — always re-assert the ref in the effect's
  mount side. This silently no-ops any callback gated on it (here: every
  chat stream event in dev).

## Owner live-check findings + fixes (2026-08-11, post-H)

The owner's own live pass surfaced four defects and three copy/affordance
calls; all fixed on the build branch, full `make verify` green:

1. **Judge enrichment stuck "Unchecked"** — root cause: the model emitted a
   citation with an EMPTY `claims[]`, so the claim-grained judge had no
   mapping and enrichment terminally failed; separately, the frontend read
   `citation.verdict` while the server persists `state: "verdict:<tier>"`,
   so even successful enrichment never displayed (the mock had been shaped
   to the component, hiding it — mock now emits the server shape and the
   e2e proves the real path). Fixes: the floor derives sentence-grain
   claims for any citation no claim references (marker-anchored, handling
   markers on either side of the full stop); enrichment applies the same
   derivation symmetrically so pre-fix rows check too; the prompt now
   requires a claim per citation; the References chip distinguishes
   terminal-failed ("Unchecked · check unavailable"). The owner's stuck
   turn was re-enriched live: the judge ruled its citation
   `unsupported_mis_cited` — honest (the cited chunk did not support the
   claim), now visible as "Unsupported — flagged".
2. **`<lemma>` in the answer** — a stray provider artifact token streamed
   and persisted. Fix: the floor scrubs lone angle-bracket token lines and
   trailing fragments; the prompt forbids markup/placeholder tokens.
   (Streaming can still show one transiently; the terminal payload replaces
   the buffer.)
3. **References rendered as raw chunk ids** — the payload carried durable
   ids only. Fix: citation display facts (envelope source title +
   `source_id`) resolve at persist time (bibliographic-authority rule);
   the References footer and copy-answer text render titles with id
   fallback for legacy rows.
4. **"Answered from an individual document"** — retrieval verified
   corpus-wide (selection is a soft prior only); the failure was answer
   craft + the id-only display. Fix: `chat_v1` gains a corpus-membership
   rule (whole-set questions use coverage/docs_by_tag/tag_aggregate +
   query_findings and multiple searches before concluding absence). Judge
   quality on such answers stays routed to the eval slice.
5. **Copy calls**: "Copy answer" and the library's rename/archive are icon
   buttons (aria-labelled); the "Whole project" zero-state label is
   removed (no entry chip → no bar).

**Deferred to owner decision (scope):** opening the chat side-by-side from
Evidence Base / Sources / other views — a real workspace-shell change (the
rail exists only in the workspace route today), proposed as a follow-up
slice or a 029 contract amendment, not a build-time fix.

Prompt hashes re-pinned (chat_v1 wording additions). New floor behaviours
carry deterministic tests (derived-claim anchoring both marker placements,
artifact-token scrub, source-title resolution).

## Contract rev 3.4 build (2026-08-11, owner-approved amendment)

Chat side by side on every project view: `ChatSidePanel` mounts in AppShell
on all project-scoped routes outside the workspace — closed, a compact
right-edge "Chat" toggle (opens the most recent chat or creates one); open,
a fixed-width panel beside the view hosting the chat thread + composer +
Chats library, with new-chat and close actions. Open state is
URL-addressable (`?chat=<cid>` on the current route — the existing
deep-link grammar), so a chat beside the evidence base survives refresh and
sharing. The artefact reader's "Ask about this analysis" now opens the
panel in place (entry-context chip intact) instead of navigating to the
workspace. Planning stays a workspace surface — the panel's hand-off
affordance navigates there. Presentation-layer only: same chat engine,
endpoints and security posture; no API change.

Owner refinements (same day): the closed-state launcher is a circular
bottom-left speech-bubble button ("Open chat", aria-labelled); the open
panel sits on the LEFT of the view — parity with the workspace rail — and
is drag/keyboard resizable via a right-edge separator (280–640 px, the
rail's own clamp and delta geometry); with a chat open, the panel and the
view scroll independently (fixed viewport height, each column owns its
scroll — the workspace's two-pane behaviour; page scroll returns when the
panel closes).

Evidence: `ChatSidePanel` component tests (launcher → latest-or-new, header
actions, blank-chat reuse), AppShell mock extended, e2e chat leg reworked
to prove the side-by-side shape (URL stays on `/evidence-base?chat=`,
panel + artefact visible together) — frontend 212 tests, build, Playwright
7/7, full `make verify` green.

## ⚠️ Gate-integrity incident + correction (2026-08-11)

**Two real test failures were hidden by the build conversation's own gate
mechanics from Phase A onward.** The lead ran background gates as
`make verify … | tail -N`; the pipe returned tail's exit status, so make's
red exit was swallowed and every phase gate A→G (and the post-H fix gates)
was REPORTED green while carrying failures. The baseline run was genuinely
green. Full audit of the retained gate logs found exactly two distinct
failures, no others:

1. `test_planning_transcript_migration_downgrade_roundtrip` — failed at
   EVERY gate from Phase A: the 027 test asserts the planning_transcript
   exact column shape, which 029's approved additive `conversation_id`
   extends. Fixed by adding the column to the expected set with a
   justification comment (an outdated exact-shape assertion for an
   approved additive migration — not a weakened test).
2. `test_project_scoped_get_routes_hide_ownership_with_byte_identical_404
   [/chunks/{chunk_id}/context]` — failed from Phase F: the chunk-context
   route's required `quote` query param 422'd before ownership resolution,
   breaking the byte-identical-404 conformance rule (the 422s were
   themselves byte-identical, so no actual ownership oracle existed — but
   the route now resolves ownership FIRST and 422s only for a legitimate
   owner missing the param).

The authoritative gate is the re-run below with the exit code read
directly (no pipe). Phase commits A–H therefore carried failure #1 (F–H
also #2) at commit time; the fixes land in the post-H commit series on the
same branch before review.

| Command | Result | Notes |
|---|---:|---|
| `make verify` (post-incident, exit code read directly) | **pass — exit 0, 0 FAILED** | the authoritative full gate (2026-08-11; fresh test DB after the 028 TooManyColumns tombstone gotcha recurred at day-scale) |

**Knowledge candidate (process):** never run a gate as `cmd | tail` —
without pipefail the pipe reports the filter's exit status, and a red gate
reads green. Write the log to a file and test `$?`, or `set -o pipefail`.
