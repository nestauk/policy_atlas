# Verification: 027-frontend-uplift

Evidence for the 027 build (steps 5–6). Review findings + rubric status are added by the
review conversation (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, 038af93) | pass | build-open re-ground (T0.1) |
| `make verify` (phase A gate) | pass | schema phase — table-count pins updated 29→30 |
| `make verify` (phase B gate) | pass | CLI byte-pins + SSE replay/pending suites green **unmodified** |
| `make verify` (phase C gate) | pass | incl. drift-check after regen |
| `make verify-fast` + planning suite (phase D gate) | pass | per the plan's gate map |
| `make verify` (phase E gate) | pass | 101 vitest at that point |
| verify-fast + `pnpm e2e` + `make fe-api-smoke` (phase F gate) | pass | e2e 4/4 · smoke 3/3 · vitest 114/114 |
| `make verify` (step-6 exit, 2026-07-29, incl. the three live-check fixes) | pass | phase G commit |

Backend suite size at exit ≈ 1950 tests; frontend vitest 114 tests / 25 files.

## Checks beyond the build

- **Deterministic tests** — all contract-matrix rows have a named owner test and ran green:
  two-phase persistence + crash-between-phases pending render · durable `client_turn_id`
  idempotency across restart (verbatim response) · retry/staleness rules (latest-only,
  409 `stale_turn`, 10-min fail-on-read) · rehydration parity (identical planner call
  composition; `planner_state` not `response`) · `GET /plan` draft-after-restart ·
  transcript round-trip + pagination + owner-scoped 404 · migration up/down on a populated
  DB · lifecycle-placement delta (started live mid-component · rollback leaves
  started→failed pair · byte-pins/SSE suites untouched) · emitter contention (streams while
  a synthesise-like TX is held open) · streamed-section replay idempotence ·
  display-index mapping incl. empty-key-findings close · terminal honesty event trail ·
  server-side filter collection-true counts · findings union narrows on `profile` ·
  dossier dual-snapshot `cited_in` scoped to latest synthesis · reducer extension incl.
  new-run reset + thread composition · CountUp/motion under `prefers-reduced-motion` ·
  plan-pane label maps (unknown key omits) · answered-state render · annotation slicing
  overlap/oversize + quote-highlight fallbacks · live-section fill-in + terminal-partial
  banner · streamed-prose scrub (adversarial fixture strings) · hygiene components
  (badge/title/404/boundary/toast) · mock journey + reduced-motion.
- **AI evals** — none (no prompt surface changed; hash guard untouched).
- **Manual / browser / API** — the G.1 live check (below) plus the mock-journey e2e
  (`pnpm e2e`, now a CI lane) and `make fe-api-smoke` against the real API.

## End-to-end command

Live check (scripted drive, owner-approved fallback — see Deviations):

```sh
# stack: postgres on :5432 · make -C backend dev (:8000, dev DB at alembic head)
#        VITE_DEV_TOKEN=<dev-issuer token> pnpm dev (:5173)
cd backend && uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer \
  --sub "<user>" --client-id policy-atlas-dev --ttl 14400 > /tmp/pa-token.txt
cd frontend && LIVE_TOKEN="$(cat /tmp/pa-token.txt)" \
  pnpm playwright test --config playwright.live-027.config.ts
```

Mock journey: `cd frontend && pnpm e2e` · real-API smoke: `make fe-api-smoke`.

## Live check narrative (G.1)

Scripted Playwright drive (owner-approved fallback), 2026-07-29, local stack: real
backend on :8000 (dev DB at alembic head), Vite on :5173 with `VITE_DEV_TOKEN`,
real chain at rapid effort / standard depth / academic-only. Two spec files
(`e2e/live-027.spec.ts` part A, `e2e/live-027b.spec.ts` part B), evidence
screenshots numbered 01–24 in `evidence/`.

**Part A (04:59–05:32 UTC, project "027 live check", FREQUENT steering):**
- 04:59:11 — landing rename (cancel restores, Enter applies) + archive two-step
  confirm, archive vocabulary ✓ (01).
- 04:59:12–33 — real planner turn; plan pane forms (question, chips, settings,
  time band, forming chip) ✓ (02).
- 04:59:33 — **API killed mid-planning (SIGKILL by port), confirmed down, restarted**;
  04:59:39 — page reload: the thread survived verbatim ✓ (03); an idempotent re-POST
  of the first turn's `client_turn_id` + message returned the stored turn verbatim
  (200, same reply) ✓; the next planner turn worked (rehydration) and the plan
  reached **ready** ✓ (04).
- 04:59:49 — run 1 started; the journey filled live (timeline · funnel · coverage
  with backends_detail + queries + adequacy sentence · plan recap · mini-nav) ✓ (05).
- 05:13:00 — check-in pending: **nav badge + `document.title` "●" marker confirmed
  from the Sources view** ✓ (06, 07); answered via a server-supplied option; the
  **answered-state echo** rendered in the journey ✓ (08). ~30 further steering
  decisions were recorded (thread run-block echoes ✓).
- **Finding (pre-existing, out-of-slice):** under FREQUENT steering with a
  thin-corpus trigger, the before-select boundary re-paused after every proceed
  decision (`agent_judgement_routed select → steering.pause → run.parked →
  steering.decision → continuation → agent_judgement_routed …`, event seq
  364–388 on project 5e08e143). The 024/025 steering machinery is contract-pinned
  untouched by 027 and its suites are green — escalated to review/owner as a
  product finding, run aborted cleanly via the abort option.

**Part B (05:40–07:14 UTC, project "027 live check B", UNATTENDED):**
- The planner walked one standing instruction per turn before honestly marking an
  unattended plan ready (good product behaviour; the spec needed 6 approvals).
- 05:56:31 — run started; **landing card showed the live running state without a
  manual refresh** ✓ (21).
- Chain: acquire 44 → screen 16 relevant → classify → appraise 12 → ingest 13 →
  screen_full 8 confirmed → characterise → synthesise.
- 06:00:31 — **the artefact page streamed live**: skeleton headings with focus
  placeholders, "Writing this section now…", prose filling in place at
  whole-section grain ✓ (09, 10); 06:02:06 — **browser reload mid-synthesis
  replayed exactly the completed sections** ✓ (11).
- 06:09:01 — run succeeded; completion card + "Read the evidence base" CTA ✓ (12);
  thread run block ✓ (13). Committed A4 evidence base with coverage snapshot ✓
  (14); **claim popover with quote-highlighted chunk context** ✓ (15) and the
  **dossier via `?source=`** ✓ (16).
- Findings: none in this corpus — the planner pinned structured extraction to
  deep depth, so standard depth has no extract stage; the kind filters still
  proved URL-addressable (`?profile=iof|icf`) with the honest empty state ✓
  (17, 18). The kind-aware row/expansion renders are covered by unit tests +
  mock fixtures + the mock e2e.
- Sources view + server-side status filter (`?status=` URL, counts) ✓ (19, 20).
- 06:54:16 — run 2 started from the completion card's new "Run the analysis
  again" control (see fixes below); 06:59:19 — **API SIGKILLed mid-synthesis**
  (after skeleton + 1 completed + 1 writing section) ✓ (22); restarted; the run
  was marked **interrupted** honestly (025 semantics unchanged), the **streamed
  sections stayed visible under the explicit terminal banner** (drafted
  sections, citations never attached) ✓ (23), and the planning thread was
  intact ✓ (24).

**Live-check-driven fixes (lead, in this phase's commit):**
1. Timeline rendered FUTURE plan steps as "skipped — a prior step failed"
   (E.2 transcription defect caught on screenshot 06) → upcoming steps now render
   as idle "upcoming", never skipped.
2. A replanned-ready plan after a SUCCESSFUL run had no start affordance (plan
   pane renders pre-first-run only) → the completion card gained a
   "Run the analysis again" control (parallel to the failed/interrupted cards).
3. A prior committed artefact hid the terminal-partial live view after a
   mid-synthesis crash → `hasTerminalPartialLiveArtefact` now takes precedence
   over the committed render (honesty: the user's latest run ended badly).

The parked-restart/two-user 025 leg was not re-run (contract-pinned exclusion).
Keyboard-nav/reduced-motion/overflow browser checks ran in the deterministic
mock e2e (`pnpm e2e`, CI lane) rather than the live pass.

## Diff summary

Six phase commits on `task/027-frontend-uplift` (branch base 038af93, from
`task/026-infra-deployment` lineage):

1. **Phase A (586f714)** — durable planning transcript: one `planning_transcript` table
   (migration e9a7c3d1f6b4 + tested downgrade; `turn_index` ordering; dual
   `planner_state`/`response` representation), two-phase persistence with pinned
   retry/staleness rules, process-local turn-lock registry replacing `_sessions`
   wholesale, `GET /plan` rewired to the durable draft, paginated owner-scoped
   transcript GET; web-api.md § Planning turns rewritten.
2. **Phase B (1d45c0d)** — the one approved runner delta: `component.started`/`completed`
   bracket the component transaction in short standalone transactions
   (`stage.started` genuinely live; rollback leaves a coherent started→failed pair);
   `ProgressEmitter` appends `artefact.skeleton`/`section_started`/`section_completed`
   on independent transactions (display-index identity, key-findings presented first,
   empty-slot close); synthesise wired at loop top / post-write; SSE forwards the three
   frames.
3. **Phase C (0a01368)** — read-model enrichment exactly per read-model-additions.md
   rev 2 §2 (items 1–15) + C.2 server-side filters with collection-true `total_items`.
4. **Phase D (12df90b)** — frontend substrate: `liveSections` reducer + terminal-partial
   selector, transcript query/optimistic state (same-`client_turn_id` retry), pure
   thread-composition model, motion utilities + CountUp, the collapsible/resizable rail.
5. **Phase E (4a4bc58)** — the view uplift across all strands 1–11 (30 files).
6. **Phase F (e6edab6)** — strand 14 hygiene + fixtures/e2e/CI lane.

**Flagged deviations & build-time adjudications (visible, not silent):**
- **T0.2 brand reconciliation: owner-ruled DEFER at build open** (agent Figma access
  still blocked); build proceeded on the in-repo distillation per pin 11.
- **G.1 drive: owner-ruled scripted fallback** (Claude Chrome extension unavailable);
  the same pinned legs ran via Playwright against the real backend + real chain, with
  the API process genuinely killed/restarted. Keyboard/reduced-motion/overflow browser
  checks ran in the deterministic mock e2e rather than the live pass.
- **Transcript rows expose `client_turn_id`** (additive; D.1 found retry-after-reload
  impossible without it — it is the caller's own idempotency key).
- **Thread run-block anchoring**: `RunOut` carries no turn-index boundary; blocks are
  anchored by comparing turn receipt-times to run windows (assignment only — ordering
  stays `turn_index`/event-sequence; honest under the 409 fence).
- **Codex A.1 retry bug fixed by lead**: phase-2 completion `UPDATE` accepted only
  `pending`; a retried failed row (retry-in-place) 500'd. Now `pending|failed`, tested.
- **F.2 found two real defects, fixed by lead at source**: the journey timeline lost its
  "Stage timeline" accessible name (restored); `useUpdateProject` invalidated a key that
  missed the projects-list (rename left a stale landing card — fixed).
- **Favicon**: the pre-existing `public/favicon.svg` had Figma-export hallmarks
  (display-p3, filter chains) — replaced with a plain Nesta-blue square (licensing
  hygiene for the public repo).
- **live-027 spec**: committed as an explicitly-excluded acceptance spec
  (`playwright.live-027.config.ts`); never picked up by `pnpm e2e` or CI.

**Additive read-model list as approved vs as landed**: items 1–15 of
read-model-additions.md rev 2 §2 landed exactly; the one field-level delta is the
`client_turn_id` addition above (same additive gate, flagged here).

## Substrate invariants

Auth seam/OIDC gating, SSE cursor reconnect, reducer replay-idempotence, `queryKeys`
shape (extended, not reshaped), `scrub()`/`safeHref()` + lint ban, URL-addressable state,
mock mode, provider nesting, pnpm supply-chain config, deploy assumptions — untouched or
extended additively; their pre-existing tests run green unmodified. One accessible-name
regression (Stage timeline) was caught in-build and restored. The 025 CLI byte-pin tests
and SSE replay/pending suites pass **unmodified** across the lifecycle-placement delta.

## Intent & assumptions

- The 025 "draft conversation is lost on restart" pin is **superseded** by strand 12
  (web-api.md rewritten accordingly). No backfill: pre-existing projects have zero turn
  rows; any in-memory drafts in flight at deploy time are lost once, honestly.
- `artefact.*` events are presentation/progress records; the artefact of record still
  lands only at component commit. Old clients ignore the new frames.
- The live search card is the honest D-1 rev 2 redefinition: tick-based activity while
  acquire runs; per-backend counts arrive at stage completion via `backends_detail`.

## Known unverified items

- The three live-check-driven fixes (upcoming-timeline render, run-again control,
  terminal-partial precedence over a committed artefact) are proven by the live legs
  themselves + typecheck/lint but carry no dedicated unit tests yet — named for the
  review conversation.
- Findings rows never rendered against live data (this corpus had no extract stage —
  standard depth); the kind-aware renders rest on unit tests + mock fixtures + mock e2e.
- ICF rows in a live corpus additionally depend on the planner including the `icf`
  extract profile (deep depth).
- The staging deploy is explicitly out of scope (026 owns deploy; no production config
  touched).
- Row expansion in findings/sources is transient local state, not a URL target (pin 8's
  documented exclusion).
- Multi-instance turn-locking stays the deferred 025 LISTEN/NOTIFY seam (process-local
  lock registry by design under the one-instance posture).

## Public safety

No secrets, keys, or real-source raw text added. Mock fixtures are invented, sanitized
values (sanitized-fixtures policy). The dev-issuer keypair stays untracked. Screenshots
in `evidence/` show only invented/live-dev data on localhost. The replaced favicon
removes a possibly Figma-licensed asset from the public repo.

## Owner-feedback round (2026-07-29, post-step-6, pre-review)

**Contract rev 4 records this round's pin-superseding amendments** — the review
stack judges against rev 4, not rev 3.3. Beyond the first batch below, the round
continued with: Searching card removed outright (coverage card carries it) ·
annotations rebuilt to the demo grammar (whole-span click → "Where this comes
from" slide-over; inline [n] chips; muted styling; locked tier vocabulary;
paragraph flow restored via inline span[role=button]) · landscape plot polish +
themes descending · `ClaimOut.theme` + `ThemeRefItemOut.sources` (two further
additive read-model fields: named theme references and their member documents,
disclosed in the panel with dossier links) · root `make dev` target. Each landed
with full gates green; fixture span-offset and tier-value bugs were found by
visual verification and fixed.

The owner reviewed the build hands-on and directed a feedback batch; all landed on the
branch with the same gates (full verify + mock e2e 4/4 + fe-api-smoke):

- **Steering re-pause loop FIXED (owner-directed scope addition into the pinned 024/025
  machinery)**: continuation now records the parked pause's boundary+component
  (`ContinuationState.parked_boundary/parked_component`); a `continue`/`adjust`/
  `mode_change` resume of a parked **before**-boundary no longer re-presents it
  (live-path parity). Two new tests in `test_continuation_parity.py`; the full runtime
  suite (452) green. This discharges the live-check livelock finding.
- Evidence-base tab on a fresh project: `useArtefact`/`useCoverage` treat 404 as the
  normal empty state (no retry storm, instant placeholder).
- Favicon 🌐 · Projects page title "Projects" (subtitle removed) · rename/archive as
  icon buttons (accessible names unchanged).
- Check-ins moved into the chat pane; machine completion renders presented friendly
  (stage label + labelled counts, raw behind a collapsed disclosure); answered state
  keeps the chosen option visible with an "Other options" disclosure (session-local —
  the API does not durably expose the chosen option id; named for a future additive
  field); run feed collapses repeated search echoes into counter lines and re-labels
  or drops vague component rows.
- Activity card hidden (chat pane carries run activity); workspace grid blowout fixed
  (`minmax(0,…)` tracks — the "expands too wide" report); plan pane restyled to the
  journey recap grammar; publication-years now a shared vertical full-range chart;
  journey/Landscape share chart components; discovered-themes card added.

## Review handoff (step-7/8 inputs)

**Executor provenance (family flip):** A.1/A.2, B.1, C.1, D.1, E.2 first-pass, E.5 =
Codex (GPT-5 family) · C.2, F.1, F.2 = fast-worker (Claude Sonnet) · T0.2/D.2/E.1/E.3/
E.4/G + all gate adjudications, briefs and fixes = lead (Claude Fable). Codex sandbox
cannot reach localhost Postgres — all DB-backed tests were executed by the lead.

**Adjudication items for review:** the flagged deviations above, plus:
- **The steering re-pause livelock** (live check part A; also in deferred.md) — a
  product finding in contract-pinned-untouched 024/025 machinery; needs an owner rule.
- The three live-check fixes (timeline upcoming / run-again control / terminal-partial
  precedence) — each is a behaviour adjudication made by the lead mid-acceptance;
  review should confirm the calls.
- `e2e/live-027*.spec.ts` + `playwright.live-027.config.ts` are committed as the
  acceptance evidence tooling — excluded from `pnpm e2e` and CI by testIgnore/testMatch;
  review may keep or drop them.
- The `pending`-row UX: a crash between phases renders "This turn didn't finish — it
  will retry or expire shortly" and fails-on-read after 10 minutes.
- `AnsweredCheckIn` renders only allowlist-labelled response detail (raw ids/params
  never render); when nothing is allowlisted it says "The run continued as suggested."
- The dev DB needs `alembic upgrade head` after this slice (the live check tripped on
  this — see knowledge candidates).

**Knowledge candidates (raw — step 8 authors docs/knowledge from these):**
- Codex jobs cannot reach localhost Postgres; delegated backend phases must say "tests
  run lead-side" in the brief, and the lead must actually run them before the gate.
- Retry-in-place needs the phase-2 UPDATE to accept the retried row's terminal status
  (`failed`), not just `pending` — the happy path never sees this.
- The six table-count pins (29→30) fail on every schema slice exactly as the 011 retro
  predicted; they live in screen/classify/appraise/acquire/ingest_full_text/embeddings
  tests.
- Moving lifecycle events to the runner keeps event-log bytes identical only because
  `config.component == registry_component` at the single `run_harness` call site —
  worth a comment if a second call site ever appears.
- An exhaustive generated SSE union forces reducer cases at generation time: B-phase
  regen left no-op cases for D.1 to fill — a good pattern for additive SSE work.
- Two codex jobs + the lead can share one worktree when every brief carries an explicit
  file-ownership list; the one overlap (E.5 extending the lead's minutes-old dossier
  wiring) was intentional and clean.
- A fast-worker killed by a transient API stall resumes losslessly via SendMessage to
  the same agent id.
- `pkill` on uvicorn: confirm the API answers 0 AND the port is free (`lsof -ti :8000`)
  before respawning — the socket outlives the process and the replacement gets
  EADDRINUSE (live-check debugging, 2026-07-29).
- The dev database is NOT migrated by `make test` (which owns the test DB); a schema
  slice must run `alembic upgrade head` against dev before any live check.
- Playwright specs in this repo are ESM — `__dirname` needs the `fileURLToPath` shim.
- Killing the dev API for crash legs: kill by PORT with LISTEN scope
  (`lsof -ti tcp:8000 -sTCP:LISTEN | xargs kill -9`) — uvicorn --reload's worker is a
  multiprocessing-spawn child whose argv never contains "uvicorn" (a name-based pkill
  orphans the serving process), graceful SIGTERM drains the browser's open SSE
  connection holding LISTEN for minutes, and an unscoped lsof also matches the
  browser/Vite CLIENT sockets and would kill the test itself.
- An unattended plan is not one turn: the planner walks a standing instruction per
  steer point before honestly marking ready (~6 approvals) — scripted drives need a
  generous turn budget.
- The planner pins structured extraction to deep analysis depth — a standard-depth run
  has no findings; live checks that need findings rows must ask for deep depth.
