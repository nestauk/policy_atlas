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
| full verify + mock e2e 4/4 + fe-api-smoke (each owner-feedback commit, 2026-07-29) | pass | 7 commits, gates asserted per commit message; vitest reached 120/26 |
| `make verify` (review-stack entry, 2026-07-29) | pass | step-7 self-verify gate |
| `make verify` + `pnpm e2e` (review-stack exit, 2026-07-29, incl. all adopted fixes) | pass | vitest 127/26 · e2e 5/5 (new rail-keyboard spec) |

Backend suite size at review exit ≈ 1960 tests; frontend vitest 127 tests / 26 files
(step-6 exit was 114/25; the owner-feedback round took it to 120/26 — the build-exit
number above is historical, this line is current).

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
screenshots numbered 01–24 attached to PR #36 (kept out of the git tree —
binary evidence lives on the PR, see `.gitignore` `docs/tasks/*/evidence/`).

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

**Additive read-model list as approved vs as landed** (corrected by the review stack,
2026-07-29 — the earlier "one field-level delta" statement undercounted): items 1–15 of
read-model-additions.md rev 2 §2 landed exactly, plus **six** field-level additive
deltas, each owner-originated but landing outside the rev-2 exhaustive list:
`PlanningTranscriptTurnOut.client_turn_id` (D.1 retry-after-reload), `ClaimOut.theme` +
`ThemeRefItemOut` (+`.sources`) (owner feedback, 8169f7e/6fa3ce3),
`CitationOut.source_id` + `.grounding_rationale` (owner feedback, closed the 025
deferred.md seam — recorded there), and `CitationOut.evidence_type` (owner feedback
39aef12, the appraisal-chip tooltip; previously recorded nowhere — PR asks the owner to
ratify explicitly).

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

- The three live-check-driven fixes (updated at review): terminal-partial precedence
  gained stack coverage (banner unit-tested across failed/aborted/interrupted; selector
  suite stands); the upcoming-timeline render and the run-again control remain proven
  by the live legs + typecheck/lint only — accepted at review as small presentational
  branches with live evidence, not test-pinned.
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
(attached to PR #36) show only invented/live-dev data on localhost. The replaced favicon
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

## Review findings (step 7, 2026-07-29 — fresh conversation)

Lanes run (Tier-3 baseline, family flip per the provenance map): **contract verifier**
(pinned Opus, read-only, re-ran gates itself) · **Codex adversarial** (GPT-5, anchored
the Claude-written surfaces) · **four scoped Claude finder angles** (fast-worker,
lens-matched pathspecs, anchored the Codex-written surfaces) · **security lane**
(security-auditor) · lead live-evidence/content review + adjudication. Reviewer diffs
excluded `frontend/openapi.json`, `src/api/gen/**`, `evidence/*.png`, `docs/tasks/**`.
Budget: ~250K reasoning-class (contract verifier 232K + Codex) + ~440K fast-worker.

**Convergent across families (high-confidence):** the planning run-fence TOCTOU
(Codex MAJOR 1 ≡ security MAJOR 1 ≡ planning-finder MAJOR 1, three independent angles
on the same seam) and the annotation-offset basis (security's code-point/UTF-16 finding
subsumed Codex's word-boundary MINOR). **Unique-to-one-lane finds that justified the
lane:** contract verifier — the false "restored at source" e2e comment, the unrecorded
`CitationOut.evidence_type`, the emitter-failure ADR gap, the transcript pane
empty/loading/error conflation; Codex — theme refs resolving "latest" instead of the
synthesis row's pinned run ids, the dossier-by-title click; Claude finders — the
thread null-boundary inversion, the stale_turn retry dead-end; security — the
unbounded pre-authz `_turn_locks` registry, the uncapped durable planning message.

### Adopted and fixed on the branch (re-verified green)

Backend: phase-1 turn reservation takes the project row lock (`for_update=True` —
closes the cross-process turn_index/duplicate-insert 500s); phase 2 re-checks the run
fence under that lock before persisting an approved plan (a run starting during the
planner call now fails the turn with 409 `run_active`, tested); theme/group references
resolve via the synthesis row's `characterisation_run_id`/`grouping_run_id` FKs, never
latest-by-created_at (decoy-run regression test); `ProgressEmitter` failures degrade
and disable emission instead of failing the walk (ADR 0027 decision 5 now true as
built; structlog warning; tested); `stage_for_payload` excludes `screen_full` (the map
entry is a plan-steps collapse only — the leaked SSE stage frame duplicated deep-depth
timeline rows and was an unapproved SSE-observable change; pinned by test);
`_turn_locks` bounded (256, evicts unheld locks — the lost `_sessions` LRU bound);
`PlanningTurnCreate.message` capped at 10 000 (durable + rehydrated into every later
prompt); `refs_out` never emits the "Unknown source" placeholder as a URL; bool guards
on `cited_by_count`/`fwci`; all-null gap caveats omit; `cited_in` gains a deterministic
ORDER BY; stale harness docstring rewritten; dead `HarnessState.block_ids` deleted;
fresh-pending rows assert as `pending` in the transcript listing.

Frontend: thread composition renders a no-prior-turn run before the turns, not after
(condition inverted by a `null` short-circuit; tested); failed composer rows render the
real conflict copy and a `stale_turn` failure swaps Retry for "Refresh conversation"
(retrying the same `client_turn_id` could never clear it); the transcript pane
distinguishes loading/error/empty (was: start-from-scratch copy during load and on
error); annotation spans slice by **code points** (server offsets are Python `str`
indices; astral chars shifted every later span — astral unit test); theme-source
clicks open the dossier by `source_id` (title collisions/>200-row projects resolved
wrongly); `highlightParts` starts remapped matches on the word, not inside a collapsed
whitespace run; unknown gap grades and search backends omit instead of raw-rendering;
check-in mode options use the locked `STEERING_MODE_LABEL`; LandscapeView gains a real
error branch (error ≠ empty); `finding.intervention` scrubbed in the aria-label;
coverage-snapshot values scrubbed; 404 view sets a document title; dead `anim-slide-in`
deleted and `anim-rise` removed from click-toggled disclosures (decoration, not
data-arrival); e2e specs re-assert `getByRole("list", { name: "Stage timeline" })` and
the false "regression not fixed at source" comments are gone (the label IS restored at
source); the reduced-motion spec now also fails on console errors; overflow checks run
rail-collapsed too; new keyboard spec drives the rail toggle via Enter/Space.

Tests added in-stack: `AnnotatedProse` exported + slicing guards unit-tested (the
contract's named vitest now exists); terminal-partial banner parametrised over
failed/aborted/interrupted; the streamed-prose scrub test now proves `scrub()` (control
/format-char assertions React escaping can't satisfy); emitter-isolation, phase-2
fence, decoy-run, screen_full-exclusion, thread null-boundary, whitespace-remap tests
as above.

### Declined (recorded reasons)

- Renderer-side word-boundary expansion of annotation spans (Codex MINOR): offsets are
  a server data contract; the mid-word fixture was fixed at source in the owner round,
  and the real cross-boundary defect was the code-point basis (fixed above).
- `cited_in` dedupe (contract NOTE): multiple citations of one source are distinct
  provenance occurrences — the fixture asserts three entries deliberately.
- Authz-before-lock reorder in `create_planning_turn` (security MINOR 2b): project ids
  are unguessable UUIDs, authz itself is unaffected, and the bounded registry removes
  the memory vector; the reorder costs an extra ownership query per turn.
- Keyboard e2e for the check-in card and dossier (contract MINOR 13, partial): both are
  native buttons/radios with vitest behaviour coverage; the rail toggle (custom
  control) got the dedicated keyboard spec, claim-span tabbing was already asserted.
- A second `/simplify` pass: the finder fan-out carried the cleanup lenses and the
  ponytail-mode lead applied deletion-first fixes (dead CSS/state removed); a
  same-family re-read would duplicate it.

### Deferred (docs/deferred.md § task 027 seams)

Orphaned `component.started` on hard process death (walk-level recovery keeps the
user-facing state honest); [D-2] project-wide decision scoping and [D-4]
`DecisionOut.detail` narrowing (the rev-2 annex committed them to deferred.md — the
entries were missing, now added); filter pagination's O(N)-per-page collection derive.

### For the owner at PR review

- **`CitationOut.evidence_type` ratification**: owner-directed (39aef12 tooltip) but
  recorded in no additive list until now — the corrected as-landed list above is the
  record. **Ratified by the owner at PR-open (2026-07-30).**
- The runner's boundary-consume suppression has one untested edge (a plan change on
  resume that reorders the parked component away from `remaining_steps[0]` would
  re-present a decided question); judged unreachable today because reordering routes
  through segment reentry — flagged for awareness, not fixed.
- Evidence screenshots show the operator's own email (already public in git authorship;
  future screenshots of non-owner sessions must not repeat this).

### Flagged-deviation adjudications (each confirmed or contested explicitly)

T0.2 brand DEFER and G.1 scripted fallback — owner-ruled, stand. `client_turn_id`
exposure — confirmed (ratified in contract rev 4). Thread run-block receipt-time
anchoring — confirmed; the Codex lane probed misassignment edges and the null-boundary
defect it sat on is fixed + tested. Codex A.1 retry fix — confirmed, now also a
knowledge concept. F.2's two defect fixes — the rename-invalidation stands; the
"Stage timeline restored" claim was true of the source but the e2e assertions had NOT
been restored and carried a comment claiming the opposite — fixed in-stack (this was
the stack's fake-done catch). Favicon replacement and live-027 spec exclusion —
confirmed (exclusion verified in `playwright.config.ts` + CI lane); **keep** the
live-027 specs as acceptance evidence tooling. The pending-row UX and
`AnsweredCheckIn` allowlist — confirmed against code; the fresh-pending listing is now
test-pinned. The steering re-pause livelock — root-caused in-build, fixed in the owner
round (4c4a65d); the stack verified the fix consumes only the decided boundary (parity
tests cover consume + no-over-skip) and the deferred.md record matches shipped code.

### Rubric status after adjudication

1 holds (the missing annotation vitest now exists; strands re-verified) · 2 holds
(gate table current) · 3 holds **except** the `evidence_type` ratification pending at
step 9 (corrected additive record above) · 4–7 hold · 8 = this section · 9 holds (the
two fallback leaks fixed; grep clean) · 10 holds (transcript pane + LandscapeView
fixed) · 11 holds (aria-label + snapshot cells closed; lint ban intact) · 12 holds
(decorative anim-rise removed; console listener real) · 13 holds — the three pinned
params + new filters are URL-backed; claim slide-over, decision-row and finding-row
expansion are **documented exclusions** (transient reading states, same shape as pin
8's row-expansion exclusion; `?claim=` deep-linking noted as a future additive) · 14
holds · 15 holds (crash-between-phases render now evidence-backed both sides) · 16
holds (terminal-path evidence covers all three; emitter isolation built + tested).
