# Verification: 028-ux-refinement

Evidence for the 028 build (steps 5–6). Public-safe. Filled at step 6;
**Review findings** + **Rubric status** land after the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline, T0) | pass | 2026-08-04, pre-build re-ground |
| `make verify` (phase A exit — schema gate) | pass | after two lead test fixes (below) |
| `make verify-fast` + `make drift-check` (phase B exit) | pass | |
| `make verify` (phase C exit — chain-adjacent gate) | pass | client re-synced for budget bounds (2..SECTION_CAP) |
| `make verify` (phase D + F.1–F.3 exit — runner-adjacent gate) | pass | after the 15-test deliberate fallout fix (below) |
| backend runtime/api/synthesis/core suites (G.1 exit) | pass | 907 passed; one SSE backlog load-flake, passes isolated (below) |
| `cd frontend && pnpm typecheck && pnpm lint && pnpm test` | pass | 168/168 after F.5 + naming pass |
| `pnpm e2e` (mock journey, updated) | pass | 6/6, twice, under `--workers=1` (default 4-worker mode is load-sensitive on this box — noted below) |
| `make fe-api-smoke` | pass | 3/3 against the real API in stub mode |
| `make verify` (step-6 exit) | pass | fully green on the final tree (fourth run; the first three each tripped one load/isolation-sensitive test — see below) |
| `make verify` (step-7 baseline, pre-lanes) | pass | 2026-08-05, branch tip incl. the rider commit |
| `make verify` (step-7 exit, post-fixes) | pass | 2007 backend + 185 frontend tests; one intermediate run failed 627 tests on the TooManyColumns test-DB exhaustion (§ Known unverified — environmental, DB recreated) |
| `pnpm e2e --workers=1` (step-7 exit) | pass | 6/6 on the fixed tree |
| `make fe-api-smoke` (step-7 exit) | pass | 3/3 |

## Checks beyond the build

- **Deterministic tests** — the G.1 named matrix (plan phase G.1), each row
  either named to existing tests or newly added:
  mode-table permutations at every runner boundary · per-point option
  floors incl. depth-conditional absences · watch-promotion keeps lattice
  identity on both runner paths · `rename_theme` atomicity + P2-only +
  rollback · authored-option validation (drop/log/event at authoring,
  tampered-delta loud refusal at apply, ≤2 cap, endorsement projection) ·
  section-budget threading (synthesise directive + P4 preview) + the full
  `time_band_for` table · evidence sort determinism (nulls-last both
  directions, stable ingestion-order tie-break, 422s) · theme-id filter ·
  summary states (post-commit visibility, rollback isolation,
  degrade-and-disable, failed-persists-no-text, multi-block omission,
  content-hash unaffected) · stale-plan fence (record → demote → 409
  `plan_stale` → re-approve clears; legacy payloads keep as-built
  behaviour). Migration roundtrip: `tests/core/test_migrations_028.py`
  (upgrade → columns null → downgrade → legacy rows intact).
- **Frontend vitest** (the contract's judgment-bearing list): part-card
  render incl. no-part/superseded/rehydrated-confirm (F34 derivation
  tests) · confirm-marker grammar round-trip · chip-edit batching ·
  send-vs-prefill option rule · plan-card inline render is
  approved-status-gated (test added at step 7 — see § Review findings) ·
  section collapse + summary fallback (fallback marker later cut in
  refinement batch 12, owner ruling — fallbacks render unmarked; the guard
  test asserts the shipped rule) ·
  bullet annotation slicing incl. boundary-crossing degrade · check-in
  bundle renders per point · P2 rename staging · P4 row editing · sort/
  theme URL state.
- **AI evals** — none this slice (owner ruling: the fork-B spot-check is
  ordinary verification, not an eval proxy; eval slice is deferred work).
- **Manual / browser / API** — the two live legs below.

## End-to-end command

Mock journey (CI-shaped):

```
cd frontend && pnpm e2e
```

Live check (real backend + real planner + real chain; dev stack up via
`make dev`, dev DB migrated with `cd backend && uv run alembic upgrade head`):

```
cd backend && LIVE_TOKEN=$(uv run python -m policy_atlas.api.dev_issuer mint \
  --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 14400 | tail -1)
cd ../frontend && LIVE_TOKEN=$LIVE_TOKEN LIVE_LEG=a \
  pnpm playwright test --config playwright.live-028.config.ts   # leg A
# then LIVE_LEG=b for leg B
```

Evidence screenshots: `docs/tasks/028-ux-refinement/evidence/`.

## Live check narration

(Timestamps are in the spec's own log lines, `[live-028 …]`, echoed in the
Playwright output; screenshots per surface in evidence/.)

**Leg A — Quick look, unattended** (project "028 live leg A"):
Timeline (spec log, UTC): 11:35:17 centred empty state (no rail pre-run, the
three-beat signposting visible) → opening message → 11:35:31 question part
card (planner-authored title; ✓ via primary) → 11:35:56 scope card with
editable chips → chip edited in the native date editor, staged, and applied
as ONE batched planning turn (11:36:21) → 11:36:36 thoroughness card with
the outcome-first presets ("Quick look — a short cited overview from a
focused search · ~5-10 min") → Quick look pressed → 11:36:47 inline READY
plan card (details open, honest band, "runs without pausing — ask for
check-ins if you want them") → Start from the card → 50/50 two-pane run
view. Run 11:36:47→11:47:47 (~11 min — above the card's "~5-10 min" label; the
band's calibration is flagged to the eval workstream, § Review findings),
**zero pauses** (the loop asserted no Waiting-on-your-input ever rendered —
the unattended default held, including through full-text fetch failures).
Artefact: **exactly 3 ordinary sections + key findings + conclusions** (the
Quick-look section budget held end-to-end through sections_v3); key
findings rendered as **5 bullets** with a **working claim popover** opened
from inside a bullet; collapsed ordinary sections showed their one-line
summaries; contents sidebar present; **3 verified block summaries**;
**artefact summary honestly `failed`** (judge rejected 3/3 — the bounded
regenerate + honest-fail degrade working live; never rendered as a
summary). Sources: Year sort → URL `sort=year` → second press `order=asc`.
Screenshots a-01…a-12 in evidence/. **PASS (12.7 min).**

**Leg B — Standard review, frequent (requested in words)** (project
"028 live leg B"):
Attempts 1-3 failed on DRIVER races (my Playwright answer loop, not the
product — narrated in § Known gaps); attempt 4 exercised everything up to
and including P4: compound opening fast-path (one recap turn to ready) →
**API killed and restarted mid-planning; thread + part state rehydrated**
(12:24:43) → ready card → Start → **pause salience confirmed on every
surface** (journey heading "Paused — waiting on you", paused status banner,
solid-orange progress strip, cross-tab banner on Sources jumping back to
the check-in) → **P1 search-review bundle** (backend counts, queries,
sample titles) answered from its floor → seven generic frequent-mode
boundary pauses answered ("Continue the run") → **P2 themes bundle with ✎
rename** — one theme renamed inline, the rename **rode the single answer**
as validated params (12:44:30) → **P3 reading-list shortlist** shown;
**free-text steer through the compile→confirm mini-thread** ("Read 18
documents in full…" → "Here's what that would change" → Apply, 12:45:50) →
**P4 proposed-sections card with inline ✎ edit** — one title edited, the
full displayed list submitted (12:46:32). Screenshots b-01…b-11.

The run then exposed **two real product findings** (the live check doing
its job):

1. **P4 sections-directive cap mismatch (FIXED in-slice):** the displayed
   list's focus texts come from the synthesis proposal (≤300 chars) but the
   steering directive grammar caps focus at 200 — submitting the displayed
   list (primary OR edited) 422'd whenever any focus was long. Fixed at the
   single source: the runner clamps focus to the directive bound when
   building the P4 bundle + as_proposed delta (displayed == submitted ==
   valid), and the card's edit inputs carry maxLength=200. Lattice tests
   green post-fix.
2. **Stream delivery after an in-card refusal (OPEN — review-stack
   adjudication item):** while the 422 loop held the pause open, the page's
   SSE stream closed (`api.sse_closed`) and no reconnect followed — the
   resolve/pending frames stopped reaching the reducer, so the stale card
   stayed up. Transient (reload rehydrates via the check-ins query; the
   nav-badge poll still fires) but it weakens pause salience after an
   answer refusal. Needs a fresh look at useRunStream's reconnect policy —
   flagged, not hot-patched (027 substrate).

After the fix the walk resumed and **succeeded**. Terminal state verified
via the API read models (bounded scope — no fresh ~25-min browser re-leg):
the artefact's 7 ordinary section titles **exactly match the submitted
displayed list** (the fixed P4 submit mechanism proven live end-to-end;
the clamped list was re-submitted through the `edit_sections` channel after
the fix, superseding the spec's pre-fix edited list, so the "edited live"
title itself is pinned by the P4 grammar/vitest coverage rather than this
run's artefact); **artefact summary `verified`** this leg; 6 verified +
3 honestly-failed block summaries (the failed ones rendered the
first-sentence fallback with markers as then built; batch 12 later cut the
marker — fallbacks now render unmarked, owner ruling).

**Cost spot-checks:**
- **Summariser + judge per-run delta (leg A, quick look):** summary layer =
  138,065 prompt + 8,071 completion = **146,136 tokens** (55,296 cached) of
  the run's 563,487 total — ~26% of run tokens; 3 block summaries verified
  first-pass, the artefact summary consumed 3 write+judge rounds before its
  honest fail (the single biggest summary spend). At gpt-5.5 rates this is
  cents per run; the artefact-grain judge strictness is the calibration
  knob (eval workstream).
- **Key-findings v2 (fork B):** live output is a clean 5-bullet block, one
  headline per line, claim spans anchored within single bullets (popovers
  verified live). A paid same-substrate v1-vs-v2 A/B was not run — no v1
  baseline artefact survives the rev, and the owner ruled this ordinary
  verification; the v2 block's shape + span integrity are pinned by unit
  tests and the live render.
- **sections_v3 before/after:** the strand-12 comparison rides the live
  legs: leg A's list ("What the evidence shows…" lead + 2 named aspects +
  structural) reads as an arc and honoured budget 3; leg B's 7-ordinary
  list opens with the answer-shaped lead framing the aspects that follow.
  Pre-rev lists (027 evidence) were parallel-topic piles with a generic
  overview; the jar the interviews named is gone from both live lists.

**Bounded live scope, stated honestly:** Groups-card and deep-run surfaces
ride the mock e2e + the G.1 matrix (plan ruling — a deep live run buys ~90
min for surfaces the deterministic tests already pin). The fork-B
key-findings check compares the v2 bullets' live rendering + call usage
within one run rather than a paid same-substrate A/B re-run — the v1
baseline artefact for a true A/B no longer exists post-rev, and the owner
ruled this ordinary verification, not an eval proxy.

## Diff summary

One slice, ten committed phases on `task/028-ux-refinement` (stacked on
`task/027-frontend-uplift`):

- **A (`ddd79a4`)** — one additive migration (transcript `part` ·
  block/artefact `summary`+`summary_status` · `source_tag.theme_id`) with
  roundtrip test; content-keyed theme identity (uuid5 of project+name —
  deterministic, rename-safe); evidence `sort`/`order`/`theme` params per
  the pinned sort spec (in-memory over the already-materialised ladder —
  consistent with the as-built collection-true architecture, flagged as a
  deviation from "SQL-side" in the brief); landscape `scope=cited`;
  summaries projection; `section_budget` mirrors; client regen.
- **B (`c1519f5`)** — `planner_v6` (sequential parts · outcome-first
  thoroughness compiling `section_budget` · steer-point walk deleted ·
  default `published_before` dropped · unattended default · country-list
  ratification on the scope card) + part persistence/validation
  (malformed → prose + a `planning_part_dropped` structlog warning — not a
  domain event; seam noted in deferred.md) + the stale-start fence
  (`source_turn_index` · GET /plan demotion · 409 `plan_stale`, code
  registered in the 409 set).
- **C (`de64151`)** — `synthesise_sections_v3` (narrative arc + budget
  clause) · `synthesise_key_findings_v2` (bullets) · `summariser_v1` +
  `summary_judge_v1` (new `summary_prompts.py`); summaries runtime
  post-commit in standalone transactions with flat judging, bounded
  regeneration and degrade-and-disable; budget threading through proposal,
  repair and the P4 preview; `time_band_for` small-budget row.
- **D (`ea573c3` + `b098588`)** — `watch_authoring_v1` (first dedicated
  authoring prompt; `endorses_option_id` wire) and the steering taxonomy
  change-set: `finding_groups` point, unattended-default mode table, P1 →
  `search_review`, floors re-homed/slimmed in plain reader copy,
  `rename_theme` delta, promotion keeps lattice identity, one validator ×
  three producers, authored exposure, `CheckInOut.bundle`.
- **E (`cef29d9` + `cdb304f`)** — named type scale as tokens + views sweep
  (body ≥16px floor; artefact prose and chat bubbles lead-adjudicated up
  to `text-body`), composer textarea (3 rows, bounded auto-grow,
  Enter/Shift+Enter, 027 disabled semantics verbatim), 50/50 run split.
- **F.1 (`0a4b3db`)** — part cards (send-vs-prefill option rule: presets
  with sub lines send; bare secondary options prefill), editable chips
  batched into one turn, confirm-marker grammar + F34 client-side ✓
  derivation, inline ready plan card as the only start surface, centred
  single-column planning stage; `PlanPane` deleted.
- **F.2 + F.3 (`de81db6`)** — contents sidebar with scroll-spy; collapsible
  sections with the verified-summary/first-sentence-fallback rule (marker
  cut in batch 12)
  (`focus` never renders; key findings never collapsible); bullet render
  with span-boundary degrade; verified artefact summary under the header;
  References collapse; cited-scoped gathered section with funnel line +
  Landscape pointer; sortable sources (Origin retained non-sortable;
  "Evidence strength") + theme filter by id; mock API mirrors the sort
  spec.
- **F.4 (`c187d99`)** — check-in bundles per point, P2 rename UI (renames
  ride the single answer), P4 inline section editing (backend
  `edit_sections` submission channel restored — the contract retires the
  retype-everything BUTTON, not the grammar channel; lead-adjudicated gap
  in D's delivery), endorsements under the endorsed option, suggested
  block, free-text mini-thread, pause-salience set (heading/banner/strip/
  cross-tab banner).
- **F.5 + naming (`867b9c4`)** — settings-in-header (committed small win),
  three-beat signposting, snapshot-cell navigation (`cited=true` — the
  brief's `status=cited` doesn't exist; verified against the real params),
  findings deep-gate empty copy, "Key themes"/"Documents" vocabulary with
  document→sources affordances, unattended label "None — ask if you want
  them".
- **G.1 (`5d29763`)** — the coverage matrix above.
- **G.2** — e2e/smoke updates, the live legs + spec
  (`live-028.spec.ts` + config, committed excluded-from-CI like live-027),
  this file, deferred.md, evidence.

**Flagged deviations (minor, resolved within contract vocabulary):**
(1-4 flagged by the build; 5-8 surfaced by the step-7 review stack as
owner-directed refinement outcomes the build had not listed — recorded here
with the same status, adjudications in § Review findings.)

1. **Leg B preset** — the plan's leg-B wording says "Quick look, FREQUENT"
   but pins P2/P3 cards; Quick look composes landscape depth (no `select`),
   so those lattice points cannot exist there. The CONTRACT's acceptance
   pin says leg B uses the standard preset — followed the contract
   (standard × frequent exercises P1/P2/P3/P4).
2. **Evidence sort execution** — server-side and collection-true before
   pagination as pinned, but implemented over the already-materialised
   in-memory status ladder (the as-built `evidence_page` architecture)
   rather than SQL `ORDER BY`; same observable semantics, perf profile
   unchanged from the existing whole-project materialisation.
3. **`edit_sections` channel** — restored to the P4 floor as a
   requires-input submission channel rendered as inline row-editing, never
   a button (the contract retires the retype-everything button; the
   channel is how edited lists submit).
4. **Deliberate pin updates** — 15 steering tests updated for the ruled
   behaviour change-set (named in `b098588`); three prompt-version pins
   (sections_v3 · key_findings_v2 · planner_v6); the CLI blocking-pause
   byte-identical render re-baselined twice (P4 floor changes); the
   unattended steering-mode label pin. Review-stack additions to this
   declared list: `test_p3_refresh_extraction_option_applies_end_to_end`
   was replaced by a floor-absence assert (the apply-path coverage loss is
   the trade; `refresh_extraction` stays reachable via authored
   suggestions), and the `most_relevant` screen-confidence-proxy disclosure
   was dropped from its option copy under the owner's plain-copy ruling —
   both now declared.
5. **Summary fallback marker cut** (batch 12, owner ruling) — first-sentence
   fallbacks render unmarked; contract :475/:502 text predates the ruling.
   Evidence claims in this file corrected at step 7.
6. **Conclusions default collapsed** (batch 9, owner ruling) — contract
   strand 5 said default open; every ordinary section + conclusions now
   `defaultOpen={false}` with key findings never collapsible.
7. **Composer ships 2 rows** (batch 1, owner list) — contract said ~3;
   auto-grow rests on `field-sizing:content` (no-JS fallback is a manually
   resizable 2-row box).
8. **`CheckInOut.bundle` ships as `dict`** — api-additions.md said "typed
   per-point projection"; the projection is server-side allowlisted but the
   contract type is open; typed-client seam noted in deferred.md.

## Refinement pass (owner live-demo list, 2026-08-05)

Fourteen owner-directed batches after step-6 exit, all lead-authored on
`task/028-ux-refinement` (`f8f509a..6e4ef99`), each batch gated
(FE typecheck/lint/vitest/mock-e2e; backend pytest/mypy/ruff/drift-check
where touched) and screenshot-verified against a `VITE_MOCK` build:

- **1 (`f8f509a`)** planning surface: one-line empty state, unboxed planner
  replies, 2-row resizable composer, viewport-height independent scrolling,
  part-card rationale behind a Notes disclosure, stacked preset options,
  optimistic confirm-marker bubbles hidden, plan-card chips grouped under
  Search filters/Screening rules, unattended copy cut, e2e pin updated.
- **2 (`fa70b2f`)** chat pins to bottom (ResizeObserver on the thread —
  child-owned queries grow content without a pane render); plan card at its
  chronological position; a consumed approval hides its Start footer and
  collapses by default.
- **3 (`727c0dd`)** landing per the Claude design: centred display prompt,
  no pane heading, primary Send disabled-until-text.
- **4 (`0ed499b`)** landing polish: placeholder de-duplicated, prompt in
  the top third, full-bleed white planning stage, 56px arrow Send.
- **5 (`2bfa2cd`)** send-button iteration: white SVG arrow, dual-cutout
  (`cutout-2` utility), 48×40, centred on the composer.
- **6 (`208d1f4`)** sources rework (backend additive): origin/evidence_type/
  strength filters; `screen_reason`/`classification_reason` recovered from
  the event log (event-payload-only; agreeing-rep selection; no migration)
  + `read_in_full`; Relevant verdict column; Status = read depth; cited
  hover copy; **FIX** found in-batch: new filter params missing from the
  react-query key served cached rows — key extended + `queryKeys` guard
  test.
- **7 (`e7fd5cc`)** header-mounted filters, subtitle cut, Uploaded origin
  option dropped, reasoning-only relevance hover, humanized reason codes.
- **8 (`bc4a4be`)** backend `sort=relevance` (p(relevant) spectrum; table
  default, desc) + `year_from`/`year_to`; funnel-icon filters + year-range
  popover; status buttons All·Included·Screened out with All default; full
  ingest-failure vocabulary humanized (`blocked_by_host` …).
- **9 (`5133aa6`)** evidence-base header: subtitle removed, conclusions
  collapse to summaries, Sources "N cited out of M included", Study
  types/Years count the CITED set (scope=cited landscape), Screened out
  bare count.
- **10 (`fc98562`)** completion-card body copy cut; landscape plots one per
  row; **FIX**: "Where I looked" nearly empty on completed projects — the
  durable coverage read model serves public backend names ("OpenAlex") but
  the label map was keyed on stream keys ("openalex"); case-insensitive
  lookup + fixture aligned to the server shape.
- **11 (`027d6f9`)** coverage sentence/disclaimer cut; "Run the analysis
  again" removed (replanned plans start from their inline plan card;
  live-027b spec re-pointed); geography caveat cut; settings icon;
  completed runs close the chat with a prominent evidence-base link.
- **12 (`9493cb2`)** summary fallback marker cut; chevron settings icon;
  journey cards reverse-chronological (themes high, Where I looked
  bottom); sticky anchor bar and funnel footer removed.
- **13 (`dd6447c`)** prominent blue Expand +/Collapse − toggles; type-scale
  sweep — 33 off-scale sizes in shared components (nav, buttons, chips,
  tabs, popovers, sheets, tooltips, toasts, feedback, auth) normalised
  onto the named scale.
- **14 (`6e4ef99`)** chips reset to the pre-sweep 11.5px brand token
  (owner ruling — deliberate off-scale); workspace plan recap mirrors the
  plan card's Search filters/Screening rules grouping; check-ins drop the
  decimal time + Technical detail disclosure.

**Review-relevant notes:** (a) two real defects were found and fixed by
this pass's own visual checks (batch 6 query-key caching, batch 10
backend-name case mismatch) — both now regression-guarded; (b) the
completion card no longer offers a same-plan re-run — the replan → inline
plan card path is the only restart affordance; (c) mock mode serves the
same landscape for both scopes, so cited-scoped header counts (batch 9)
are demo-identical to corpus counts — real projects differ; (d) additive
API growth beyond api-additions.md: evidence `origin`/`evidence_type`/
`strength`/`year_from`/`year_to`/`sort=relevance` params and
`screen_reason`/`classification_reason`/`read_in_full` response fields —
all additive, drift-check green, golden-tested.

## Intent & assumptions

Everything traces to contract strands 1–14 and the two adversarial-review
records (23/23 + 39/39 adjudications in). The six gated prompt surfaces —
`planner_v6` · `synthesise_sections_v3` · `synthesise_key_findings_v2` ·
`summariser_v1` · `summary_judge_v1` · `watch_authoring_v1` — were
lead-authored, versioned (never edited in place); prompt-guard re-pinned in
the same commits for the four surfaces living in name-matched prompt
modules — `synthesise_sections_v3` and `synthesise_key_findings_v2` live in
`synthesis_backend.py`, which the name-based guard cannot pin; their guard
is the version-pin tests (scope gap recorded in § Known unverified). Additive API surface exactly as enumerated in
[api-additions.md](api-additions.md) — approved vs landed match; the one
named read-behaviour change (GET /plan draft-freshness) was owner-signed at
the plan gate.

## Known unverified items

- **Groups card + deep-run steering live** — mock e2e + G.1 matrix only
  (plan-pinned bounded scope). NB the review stack found and fixed the FG
  regroup apply path (M1, § Review findings) — deterministic end-to-end
  coverage now exists; live exercise still pending.
- **SSE reconnect after a swallowed close** — ROOT-CAUSED at step 7 (was
  the open leg-B finding): `api.sse_closed` is the server generator's
  close log; the client reconnect loop is sound but `sse.ts` has no
  read-inactivity watchdog, so when an intermediary (dev Vite http-proxy;
  CloudFront in prod can do the same) swallows the upstream close,
  `reader.read()` pends forever with `connectionStatus` still "connected".
  Fix shape: abort the attempt after ~45s without bytes (server heartbeats
  every 15s) into the existing backoff loop. DEFERRED to its own slice
  (027 substrate file used as byte-identical evidence for rubric 14 this
  slice; prod CloudFront behaviour deserves its own verification) —
  deferred.md entry rides step 8.
- **`test_sse.py::test_sse_backlog_to_tail_has_no_duplicate_or_missing_mapped_sequences`**
  flakes under full-suite parallel load; passes isolated every time.
  Pre-existing timing sensitivity, not a 028 regression (it is untouched by
  this slice); left un-quarantined so the review sees it.
- **Summary/judge calibration** — eval-workstream territory (deferred.md).
- **prompt-guard scope gap** (found, recorded for step 8): the hash guard
  pins files whose NAME contains "prompt"; `synthesis_backend.py` carries
  prompt constants but is guarded only by its version-pin tests.
- **Suite-level timing sensitivity on this machine** — three tests tripped
  in full parallel runs and pass isolated: the SSE backlog test and the
  full-text-ingest timeout test (genuine load-timing; both re-verified
  green isolated), and the G.1 authored-option drop test (a REAL isolation
  defect, fixed: `structlog.testing.capture_logs` cannot intercept loggers
  already bound under the app's cached config, so its assertion was
  order-dependent — the flaky log assertion was removed in favour of the
  durable steering-event assertion it duplicated).
- **Mock e2e worker parallelism** — the journey suite is reliable at
  `--workers=1` on this box and load-sensitive at the default 4; CI runs on
  a quieter machine, left as-is with this note.
- **Suite-order sensitivity, one more instance (step 7):** a serial
  runtime+synthesis+api sweep tripped
  `test_steering_events.py::test_rejected_adjustment_emits_reason_then_continue`
  once; it passes isolated and at file scope (twice each). Same
  pre-existing cross-file-state class as the entries above; watched at the
  step-7 exit `make verify`.
- **Shared test DB exhausts Postgres's 1600-column limit (step 7, root-
  caused):** one step-7 `make verify` failed 627 tests after
  `test_screen_step_rename_migration` died mid-roundtrip with
  `psycopg.errors.TooManyColumns` and stranded `policy_atlas_test`
  downgraded. Postgres counts DROPPED columns toward the per-table 1600
  cap, and the migration-roundtrip tests add/drop the same columns on the
  long-lived shared DB every run — after enough suite runs a table tips
  over and the failure presents as a mass cascade, not as its cause.
  Remedy: recreate `policy_atlas_test` (only a table rewrite-from-scratch
  reclaims dropped-column slots). Not a 028 defect; knowledge candidate
  (step 8) — periodic test-DB recreation or per-run scratch DBs.

## Public safety

No secrets, tokens, keys or personal data in the diff, fixtures, prompts or
this file. Live-check screenshots show only the dev app with synthetic
questions and openly-licensed source titles. The dev-issuer token was
minted locally and never committed. Mock fixtures follow the
sanitized-fixtures policy; no font binaries committed.

## Review handoff (step-7/8 inputs)

**Executor provenance (family flip):** Codex implemented phases A, B
(machinery), C (runtime), D and the G.1 matrix; Claude fast-workers swept E
and built F.3/F.5 and the e2e updates; the lead authored all six prompt
surfaces, F.1/F.2/F.4 product surfaces, the live spec, and adjudicated
every delegated diff. Claude-family review should anchor the Codex-authored
backend diffs (A/B/C/D/G.1); the security lane's pinned scope is in
plan.md § Review-stack handoff.

**Adjudication items:** the four flagged deviations above; the
`edit_sections` restoration (check the confirm-ladder semantics); the leg-B
preset correction.

**Knowledge candidates** (one per durable-seeming lesson; step 8 authors
docs/knowledge from these against the final code):

- Codex sandbox cannot reach Docker/Postgres: every backend phase needs the
  lead to run DB gates; briefs must say "reason statically — we run the
  suite after", and the test fallout lands on the lead's desk in one batch.
- Codex-authored tests remain the dominant delegated-defect surface (022
  lesson re-confirmed): the 15-test fallout + one invalid plan fixture
  (deep-only components at standard depth) were all test bugs; product code
  survived adjudication unchanged.
- prompt-guard's name-based file matching misses prompt constants living in
  non-"prompt" modules (`synthesis_backend.py`) — version-pin tests are the
  actual guard there; consider widening the glob or moving constants.
- Content-keyed identity via `uuid5(namespace, f"{project}:{name}")` keeps
  stub runs byte-identical AND makes theme-filter bookmarks survive
  re-characterise — deterministic ids beat run-keyed uuid4 wherever
  fixtures pin byte-equality.
- OpenAI strict response format can't carry open JSON objects: the
  transport-twin pattern (delta as JSON-encoded string + fail-closed
  `to_wire()`) extends cleanly to new fields (`endorses_option_id`), but
  every new wire field must be threaded through BOTH twins or it silently
  drops.
- Retiring a UI button is not retiring its grammar channel: the P4
  `edit_sections` requires-input option is the submission path for inline
  editing; D's literal reading dropped both and the frontend had no way to
  submit an edited list.
- Two families editing one working tree concurrently is safe when file sets
  are disjoint and each brief lists the sibling's files; string-anchored
  Edits on a SHARED file (queries.ts) from two agents also merged cleanly —
  but a mid-flight `pnpm typecheck` sees the union and cross-fires (D's
  regenerated types broke F.1's check transiently).
- Playwright strict mode + brand copy: `getByText("ready")` collides with
  prose containing "ready" — pin chips with `{ exact: true }` from the
  start in acceptance specs.
- The mock e2e suite and a live Playwright leg cannot run concurrently on
  one laptop — the load makes mock `page.goto` time out; serialise them.
- The dev DB needs `alembic upgrade head` after a schema phase before any
  live check — the SPA surfaces it as "conversation couldn't be loaded"
  (a 500 on the missing column), not as anything schema-shaped.

## Review findings (step 7, 2026-08-05)

Fresh conversation; the lead adjudicated, no lane was the author of the code
it reviewed. Baseline `make verify` fully green at tip before any lane ran
(1995 backend + 176 frontend tests). Diff base `task/027-frontend-uplift`
(026/027 unmerged; dev...HEAD would re-review them). The one rider commit
(`2d9d913`, 2-line `make dev` port guard) was read by the adjudicator and
is what it claims.

**Lanes run (Tier 3):**

- **Contract verifier** — fresh pinned-Opus `contract-verifier` agent:
  all 17 rubric items vs as-built code + verification.md/ADR claim audit;
  independently re-ran drift-check, fe-api-smoke, vitest, mock e2e and six
  backend suites (all green). 5 MAJOR / 27 minor-info findings.
- **Claude defect lane** — `agent-skills:code-reviewer` subagent anchoring
  the Codex-written backend (family flip; phases A/B/C/D/G.1).
  **Substitution note:** `/code-review medium` is user-typed-only in this
  session (model invocation disabled by the harness); the skill's listed
  alternative reviewer was used instead, same scope + per-lens pathspecs.
  2 MAJOR / 6 minor findings + INFO.
- **Security lane** — `agent-skills:security-auditor` on the plan-pinned
  scope (part-card rendering · authored options · params · summaries · six
  prompt diffs · refinement reason fields). 0 critical/major, 4 MINOR,
  5 INFO; authored-option pipeline and summary persist/render gates
  assessed defence-in-depth-correct.
- **Codex adversarial** — read-only codex-rescue pass anchoring the
  Claude-written surfaces (six prompts, F.1/F.2/F.4 + refinement batches,
  e2e/live specs). 2 High / 5 Medium.
- **Live-trace content review** (lead) — the two build-flagged anomalies
  root-caused in-stack: P4 focus-clamp fix verified in code (runner
  overlay + card maxLength; title bound already within the directive cap);
  SSE-reconnect root-caused (client watchdog gap — § Known unverified).
- **OKF bundle check** — inside `make verify`, green.
- **/simplify** — skipped, recorded: the 14-batch owner refinement pass +
  this stack's copy-map/cleanup fixes already did the what-to-cut work; a
  same-family cleanup pass would duplicate it (economy rule).

**Convergent findings (cross-family, high confidence):** the option-id
charset gap (security MINOR + Codex Medium + contract F18) and the
summary length-bound gap (Codex Medium + Claude-lane INFO + contract F25)
— both adopted and fixed.

**MAJOR findings, all adopted and fixed in-stack:**

1. **M1 (Claude lane) — finding_groups regroup options were dead.** Both
   apply paths refused the FG floor's `{"group": ...}` deltas: replacement
   re-run wiring existed only for P3 (`rerun_component` select-only at both
   after-boundary sites), so regroup degraded to an already-run adjustment
   and was refused (HTTP 422 / CLI reprompt). The G.1 matrix asserted only
   option ids + grammar compilation — no test answered an FG pause
   end-to-end (the 022 "Codex tests are the defect surface" lesson, again).
   Fixed: shared `_after_boundary_rerun_component` wires `group` at FG on
   both paths, with the P3-mirror degrade when group has no persisted run;
   new end-to-end test drives a frequent deep walk, answers the FG pause
   with regroup, and asserts two group runs + synthesise threading the new
   one + the wired pause surface.
2. **M2 (Claude lane) — P4 "as proposed" dropped `group_ids`.** The overlay
   projected `{title, focus}` only, silently unscoping grouped deep runs
   and stamping user-authored provenance on the accept path; answer-time
   validation would also have 422'd any group_ids-bearing delta
   (`grouping_group_ids=None`). Fixed: the overlay carries non-empty
   `group_ids`; `parse_synthesis_directive` gained `defer_group_membership`
   (answer-time form/bounds check, membership still enforced by the
   execution-time re-parse — a tampered id now fails loud at execution
   instead of 422-at-answer, canonical path unaffected); the frontend P4
   parser/edit round-trip carries `group_ids` opaquely. m1 folded in: the
   overlay also trims the displayed list to the section budget (the budget
   clause was prompt-advisory; an over-budget proposal failed at execution
   with no repair). New overlay pin test (kills contract F4's
   delete-the-overlay-suite-stays-green gap) asserts displayed ==
   submitted == valid, focus clamp, budget trim, group_ids carry.
3. **F1/F3/F15-class MAJORs from the contract lane are owner-decision
   items** — see the cluster below; F5 (claimed PlanCard vitest didn't
   exist) fixed by writing the test; F2's stale evidence claims corrected
   in place; F8 recorded (screenshots depict the 2026-08-04 pre-refinement
   tree; batch-level screenshot gating was the refinement pass's visual
   evidence; no live re-leg ran against the refined tree — batches 6/8
   backend additions are golden-tested only).
4. **C4 (Codex lane) — endorsements were unserialisable-or-padded.** The
   authoring wire required `component`+`delta` while the prompt forbade
   restating the endorsed option. Fixed: both transport twins nullable on
   endorsements, `to_wire()` keeps endorsements and still drops deltaless
   new options, `_validated_authored_options` accepts endorsements and
   strips their padding (projection discards it anyway; apply-time refusal
   on a directly-selected endorsement stays loud);
   `watch_authoring_v2` + prompt-guard re-pin. Wire test added.
5. **C2 (Codex lane) — live-spec restart helper swept port 8000.** Now
   kills only the PID tree it spawned; the leg-B first restart (the
   make-dev-started API) requires `LIVE_ALLOW_API_TAKEOVER=1` and verifies
   every 8000 listener is a policy-atlas uvicorn before killing, refusing
   otherwise.

**Adopted minor fixes:** option-id charset enforced in `_validated_part`
(drop + `invalid_option_id`, degrade-to-prose posture) · planner `part`
NUL-scrubbed before JSONB persist · theme-rename bounds (200 chars,
control-chars refused) · `insert_source_tags` do-update only for
theme-carrying calls (None-callers keep do-nothing; no NULL clobber, batch
dupes tolerated) · deterministic characterisation-row tie-break for
renames · deterministic summary format floor (block 300 / artefact 750
chars = 1.5x the prompt ask, `[n]` citation markers refused; violations
consume a regenerate attempt, judge saved) · agreeing-rep reason returns
nothing rather than a contradicting rep's text · landscape cited-scope
membership via set · P1 bundle renders public backend names (shared
`backendLabel`, raw-key fixture now guards it — the batch-10 defect class,
third instance) · `scrub()` on the read-depth tooltip · copy maps moved
into presentation modules (`RUN_BLOCK_STATUS`, check-in headings,
`BACKEND_LABELS`) · dossier abstract onto the body token + prose measure ·
`sectionSummary` dead `verified` field removed, docstring now states the
shipped rule · queryKeys guard covers all 12 params independently ·
PlanCard approved-gate vitest (5 cases) · span-survives-collapse/expand
vitest · live-spec legacy-fallback assertion made real (was vacuously
passing on text the UI never renders). All regression-tested: 68 new/
touched backend tests + 185 frontend tests green.

**Declined, with reasons:** C7 live-spec strictness (the live spec is a
scripted narration harness pinning the observed run; ≥3-bullets/verified-
summary encode that run, not CI policy) · C1 key-findings bullet-format
enforcement (render path degrades honestly per the F.2 span tests;
format-repair is judge/eval-workstream territory — deferred.md) · F29
AGENTS.md phase pointer (moves with the next slice's design step, per the
task-cycle skill) · F16 batch-13 commit-message overstatement (history is
immutable; recorded here: the chart-label claim covered only two tooltip
classes; six pre-existing recharts 11px ticks remain) · F17 unknown-reason
de-snaking (deliberate: ingest/screen reason codes are an open diagnostic
set, unlike the closed UI vocabularies whose unknown keys are omitted) ·
aria-label scrub (React escapes attributes; format-char screen-reader risk
negligible) · sort=strength ascending default (order param exists; table
default is relevance desc).

**Deferred to deferred.md (step 8 authors the entries):** SSE inactivity
watchdog (root-caused, fix shape pinned — § Known unverified) ·
`summary_status="pending"` dead vocabulary (FE keys strictly on
"verified", so no mislabel today; in-flight vs legacy indistinguishable) ·
P1 sample titles are project-wide (multi-question seam) ·
`_source_reason_maps` full-event-log scan per request (funnel_out
precedent; needs a payload-filtered query when event logs grow) · F20
in-flight-turn vs plan_stale fence test · `planning_part_dropped` as a
domain event · typed `CheckInOut.bundle` · F26 artefact-grain
failed-suppression test (top-level ArtefactView isn't vitest-renderable
without new scaffolding; section-grain equivalent is tested) · summary
runtime niceties (writer_calls accounting on raised attempts, judge-
feedback rider on regenerate, double block fetch, protocol naming).

**Deviation adjudications (all eight § Flagged deviations):** 1 (leg-B
preset) confirmed — the contract pin governs; 2 (in-memory sort) confirmed
— collection-true semantics verified precisely by the contract lane
(whole-collection filter/sort before a Python slice; nulls-last; stable
ties; total over the filtered set); 3 (`edit_sections` channel) confirmed
— restored as a requires-input submission channel rendered as row editing,
never a button; grammar unchanged; 4 (pin updates) confirmed with the two
review-stack additions now declared; 5-8 (marker cut · conclusions
collapsed · 2-row composer · dict bundle) adopted as owner-ruled/recorded
deviations — the contract text predates the refinement rulings and stays
historical.

**Fake-done check on this phase's own fixes:** no test was relaxed or
deleted (all changes add assertions or enforce stricter behaviour); the
FG/overlay/endorsement fixes ship with tests that fail on the pre-fix
code; the marker-claim edits correct evidence to match shipped behaviour
rather than weakening a requirement silently (the requirement change is
recorded as deviation 5).

**Owner-decision cluster — the copy diet vs rubric 15 (decide at review):**
the refinement pass cut three honesty-bearing surfaces that rubric 15
protects. (a) **Coverage adequacy** (contract F1): `coverage.sentence`
still composes "Coverage was judged adequate/inadequate" but no frontend
consumer remains — an early-stopped, inadequate-coverage run shows no
adequacy statement anywhere. Recommendation: render the sentence only when
the verdict is inadequate (silence = fine, speech only on a problem).
(b) **Per-query relevance attribution** (F3): the "attributed across this
project" disclaimer is gone while per-backend relevant counts render above
a per-query list. Recommendation: one short base qualifier on the count
line. (c) **Screened-out visibility in the journey funnel** (F24): the
exclusion count survives only as the evidence-base bare count.
Recommendation: accept (the artefact page keeps the linked cell).
Also for the owner: F8 — whether to re-shoot the evidence screenshots
against the refined tree, or accept batch-level verification as recorded.

## Rubric status

(Step 7. "Holds" cites the § Review findings evidence above; the contract
lane's per-item table is the detailed record.)

1. **Holds w/ recorded deviations** — forks A/B/C land as pinned; eight
   flagged deviations adjudicated (§ above).
2. **Holds** — all gates green at tip + independently re-run by the
   contract lane; live check ran 2026-08-04 (pre-refinement tree — F8
   recorded, owner call on re-shoot); review-stack clause = this section.
3. **Holds** — one additive migration exactly as enumerated (5+1 columns,
   owner-approved); additive-only API confirmed against api-additions.md +
   the declared refinement growth; deps/CI/auth/prod-config/SSE untouched
   (SSE byte-identical; watchdog deferred). `watch_authoring_v2` is a
   review-fix rev of a gate-listed surface, guard re-pinned.
4. **Holds** — drift-check + prompt-guard green after the v2 re-pin.
5. **Holds** — no deletions/skips beyond the declared list; two
   review-stack additions to that list now declared (deviation 4); this
   phase's fixes only added/strengthened tests.
6. **Holds w/ corrections** — evidence claims corrected (marker, prompt-
   guard scope, band, F5 test now exists); fork-B cost spot-check remains
   the owner-ruled shape/usage observation, not an A/B (recorded).
7. **Holds at step 8** — deferred.md entries authored/updated there
   (existing entries contradiction-checked clean by the contract lane).
8. **Holds** — this stack: contract verifier · Claude defect lane
   (recorded substitution) · security lane · Codex adversarial · live-trace
   review · adjudication; findings recorded here.
9. **Holds** — tokens + measure verified; zero new ad-hoc sizes at tip
   beyond the owner-ruled chip; dossier abstract brought onto the scale at
   step 7; recharts ticks pre-existing (recorded).
10. **Holds** — no raw enum on any surface after the P1 backend-label fix
    (third instance of the class — knowledge candidate); locked vocabs
    omit unknowns; the open-set reason codes de-snake by design (recorded);
    `focus` never renders; fallback summaries render unmarked per
    deviation 5.
11. **Holds** — span-boundary degrade verified honest (degrade + re-emit
    whole claim); collapse→expand survival now tested.
12. **Holds** — phase-one machinery zero-diff; fence traced end to end;
    part round-trip tested; part payloads now NUL-scrubbed + option-id
    enforced (stricter).
13. **Holds** — collection-true verified precisely; URL-addressable (no
    component filter state); queryKeys guard now complete; tie stability
    tested.
14. **Holds** — auth diff cosmetic; eslint scrub/safeHref bans intact; SSE
    byte-identical; store/mock suites green.
15. **Holds except the owner cluster** — copy maps now fully in
    presentation modules (step-7 moves included); the three honesty cuts
    are owner decisions pending (§ above) — the box closes on the owner's
    ruling.
16. **Holds** — flat judging structural; failed-carries-no-text
    DB-enforced; deterministic length/citation floor added under the
    judge; legacy fallback renders (unmarked per deviation 5; live-spec
    assertion now real).
17. **Holds** — taxonomy verified per the contract lane's trace incl.
    server-enforced P2-only rename (+ new bounds) and jargon-clean floors;
    the FG regroup apply path — the one broken affordance — fixed and
    end-to-end tested; authored-option validation now covers endorsements;
    pause-salience cross-tab is by construction (banner above the Outlet),
    e2e asserts the Sources instance (scope recorded).
