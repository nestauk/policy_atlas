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

Seven phase commits on `task/029-copilot-chat` (A: 917ae97 · B: 1426ddf ·
C: 5fea94a · D: 782705b · E: 3e2e060 · F: 4f1f505 · G: _pending_):
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

_Added at step 7 (fresh conversation)._

## Rubric status

_Checked at step 7; build-time self-check: rubric 1–7, 9–21 exercised by the
suites named above; 8 (review stack) pending; 10a enrichment shipped (the
contract's cut-line was NOT exercised — no contract revision needed); 19
docs land with H1._

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
