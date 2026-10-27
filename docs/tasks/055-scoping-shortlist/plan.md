# Plan: 055-scoping-shortlist

Items 1–14, rulings S1–S26, review amendments A1–A30 and O1–O5, measures M1–M7 and every
term are defined in [contract.md](contract.md). This plan cites them and adds nothing to
scope. It was written against the as-built code at `eedf9ef9` (dev) as mapped on 2026-10-27,
not against the contract's own claims; where a phase names a file and line, the executor
re-checks it before editing.

> **Status:** drafted 2026-10-27 · lead. **Plan-stage adversarial review ran 2026-10-27**
> (`codex-rescue`, read-only, job `task-mvq4nchu-y1fzv6`): 27 findings, verdict "material
> change needed"; the lead checked the code claims of PR1, PR3, PR8, PR12, PR13, PR21 and
> PR22 — they hold. All 27 folded in § Plan-review folds and in the P-decisions below; four
> change a contract detail and are listed in the contract's § Amendments at the plan gate.
> **Plan approval (before implementation): ⏳ owner.** ADR 0041 is written at step 4, after
> plan approval and before any build phase.

Executor marks per AGENTS.md § Agent-side model routing. Owner rulings stand: judgment-bearing
build phases go to `deep-reasoner`, not `codex` (2026-09-04); anything that must be built
goes to a delegate (2026-09-29); prompt-bearing work, product copy and taste-bearing frontend
design are `lead` (2026-09-05). No phase is marked `codex`. Every `lead` mark carries its
reason. Seam semantics are fixed in § Decisions below; a delegate's brief builds them and
does not design them. Every delegate brief says: run the phase's gate yourself; the final
message is the report, with the gate's tail.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), Phase 1 (the revision
— schema class), Phase 3 (the runner and the chains), Phase 5 (closes Phases 4 and 5: the
routes and the Task Agent, API contact) and Phase 8 (step-6 exit). Phases 2, 4, 6 and 7
close on `make verify-fast` · `make prompt-guard` · `make drift-check`, plus
`make frontend-verify` in Phase 6. Phase 2 is logic in the scoping package and the read
model with no schema contact; Phase 4 is API logic whose full gate Phase 5 carries; Phase 6
is frontend; Phase 7 changes prompts only. **One green commit per phase, and one per loop
round that changes a prompt.** The full gate runs serially; parallel delegates use one test
DB each (`gate-snapshot-worktree`).

**Order.** Plumbing first (Phases 1–6), then the prompt loops (Phase 7) on the stored tasks,
then the live check (Phase 8). Phase 7 cannot start before Phase 3 (the component) and
Phase 2 (the line); Phase 6 can run beside Phase 7.

## Decisions fixed here (lead seam design)

P1. **The appetite on the plan.** `ScopingPlan.risk_appetite: RiskAppetite = "mostly_tried"`,
`RiskAppetite = Literal["tried_only", "mostly_tried", "open_to_untested"]`, in
`runtime/scoping_plan.py`. `ScopingPlanPatch.risk_appetite: RiskAppetite | None`
(`api/contract/task_agent.py`). The field travels every path a plan field travels (PR11):
`wire_draft_from_plan` (the successor-conversation seed), `build_scoping_plan`, the API
draft and patch models, and the Task Agent's `part_ids`; a test proves an offered choice
survives approval, seeding and a later edit. `PlanOut` serves it through the payload as
today. **No `shortlist_pending` flag** (PR8: a response-only flag vanishes on the next
query invalidation); instead `LonglistOut.shortlist.stale: bool` = the latest proposal's
`provenance.appetite` ≠ the current plan's `risk_appetite`, or no proposal exists for a
built longlist, derived in `repository.longlist_out`; the view shows "Press Suggest more
to re-propose" when it is true. The words live once on the backend
(`RISK_APPETITE_LABELS` in `scoping_plan.py`, the three answers of S2) and once on the
frontend (`planVocabulary.ts`, A25); each map is tested against the approved labels, and
their key sets against the generated enum (PR23).

P2. **Staleness.** `longlist_inputs(plan: ScopingPlan) -> dict` in `scoping_plan.py`
projects the ten fields of A6 by `model_dump(include=…)`. `LonglistOut.plan_inputs_changed`
= `longlist_inputs(current approved plan) != longlist_inputs(plan at
longlist_result.plan_version)`, computed in `repository.longlist_out`. `planStart.ts` reads
it for the `rebuild_longlist` state instead of comparing versions; `rebuild_or_confirm`
keeps its version comparison (it is about the baseline).

P3. **The revision.** One file `backend/alembic/versions/<rev>_shortlist_places.py` on
`f1b6d3a8c2e5`: `option.shortlist_state` Text null + `ck_option_shortlist_state`;
`option.shortlist_reason` Text null; `longlist_result.shortlist` JSONB NOT NULL
`server_default '{}'::jsonb`, **the default kept** (PR1: the longlist writer's insert at
`longlist.py:1966-1981` does not name the column; keeping the default is smaller than
editing the insert, and the SQLAlchemy table carries the same `server_default`);
`ck_scope_purpose` dropped and re-created with `'shortlist'` added, and the literal in
`core/schema.py:435-437` gains it too (PR24: there is no `SCOPE_PURPOSES` constant).
Downgrade in this order: `UPDATE evidence_scope SET purpose = NULL WHERE purpose =
'shortlist'`; restore the old check; drop the three columns; `UPDATE plan SET payload =
payload - 'risk_appetite'`. The migration test seeds three plan versions, an option with a
place, a shortlist scope, and round-trips. Schema constant `OPTION_SHORTLIST_STATES =
("proposed", "added_by_you", "set_aside")`.

P4. **The component.** Package `options_scoping/shortlist/` with `shortlist.py` and
`shortlist_prompt.py`. Entry `shortlist_scope(conn, *, task_id, run_id, context, backend)
-> dict` on the `theme_scope` pattern; raises `ShortlistFailure`. Steps: load the plan
(`walk_plan`); the baseline text through a **public** `baseline_text(conn, task_id) -> str
| None` extracted in Phase 3 from the chat renderer's private `_rendered_body` in
`runtime/chat_context.py:98-134` (PR15; the first `SHORTLIST_BASELINE_MAX_CHARS = 20_000`
characters, the cut counted as `baseline_chars_cut` in provenance and named in the note's
footer beside the document-line count); the task-wide newest `longlist_result` (read, not
yet locked; PR25); the included unmerged options and their `OptionOut` through
`repository.option_out` (the delegate confirms the import causes no cycle — the scoping
package already imports `api.readmodels` nowhere, so `card_text` is called through a small
`options_scoping/shortlist/cards.py` that imports lazily inside the function); the
**previous proposal from the newest `shortlist.proposed` event** of the task, not from the
row (PR2: a Rebuild inserts a fresh row); clear picks whose option is now excluded or
merged (O1); compute `to_fill`; build the payload; call; check; re-ask once; **then** lock
the newest row `FOR UPDATE`, re-check that it is still the newest and that the candidate
options are still included (else `ShortlistFailure("longlist changed")`), write; append
`shortlist.proposed`. `to_fill`: when
`context["suggest"]` is absent (chain end, appetite walk): release every `proposed` place,
then `max(0, PLACES_TARGET − added_by_you places)`; when present: `PLACES_TARGET − places`
if places < 5, else 1. With `to_fill == 0` the call still runs for the note, with a
`fill: 0` instruction. Candidates = included, unmerged, not `added_by_you`, not
`set_aside`, not already proposed (in the suggest case). Fewer candidates than `to_fill` →
`to_fill = len(candidates)`.

P5. **The wire and the checks.** Short ids `o1…oN` assigned after shuffling the candidates
with `random.Random(f"{run_id}:{attempt}")`; kept places and set-asides are listed by name
and short id too, so the model can refer to them in the note. `ShortlistWire{picks:
list[ShortlistPickWire{option_id: str, reason: str}], note: str}`. Checks, in order: every
pick id maps to a candidate; no duplicates; `len(picks) == to_fill`; every reason is
1–`SHORTLIST_REASON_MAX_CHARS` characters after strip; the note is 1–1,200 characters. A
failed check re-asks once: **a shortlist-specific two-attempt loop** in `shortlist.py`
(PR4: `call_with_retry` repeats the same zero-argument callable and cannot carry the
failures) whose second call appends a user turn naming each failed check; a second failure
raises `ShortlistFailure`; a test asserts the second request's text. Constants in
`shortlist.py`: `PLACES_TARGET = 5`, `SHORTLIST_REASON_MAX_CHARS = 400`,
`SHORTLIST_NOTE_MAX_CHARS = 1_200`, `SHORTLIST_INPUT_CHARS_MAX = 400_000`. The write:
`option.shortlist_state = "proposed"`, `shortlist_reason`; `longlist_result.shortlist =
{"note", "provenance": {"prompt_version", "model", "appetite", "plan_version", "run_id",
"input_chars", "document_lines_cut", "baseline_chars_cut", "to_fill", "attempts",
"usage": [{"input_tokens", "output_tokens", "elapsed_ms"} per attempt]}}` (PR16; cost is
read from Langfuse by the staged driver, as 046 did, not stored). The event payload:
`{"places": [{option_id, name, state, reason}], "note", "appetite", "plan_version",
"prompt_version", "model", "run_id"}`. The `component.completed` summary:
`{"component": "shortlist", "filled", "kept", "set_aside", "input_chars",
"document_lines_cut", "attempts", "input_tokens", "output_tokens"}`.

P6. **The backend seam.** `LonglistBackend` gains `propose_shortlist(self, *, system: str,
user: str) -> UsageResult[ShortlistWire]` (PR3: the existing methods return
`UsageResult[T]`, `longlist_backend.py:150-180`), live through
`traced_parse(response_format=ShortlistWire, …)` under the static name
`longlist:shortlist` on `LONGLIST_JUDGMENT_MODEL`; `StubLonglistBackend` gains
`shortlist_responses: deque` with a deterministic default (the first `to_fill` candidates
in input order, reason "stub", note "stub note") and records `shortlist_inputs`.

P7. **Card text.** `api/readmodels/card_text.py`: `option_card_text(option: OptionOut, *,
plan_outcomes: list[str], lines_order: Sequence[str]) -> CardText` (the fixed text and the
document lines kept apart), the matrix of A12, in the card's section order, Markdown
headings per section, one document per line. The budget (PR20): the fixed sections of the
request (system prompt, plan, baseline, kept and set-aside cards' fixed parts, excluded
lines, previous proposal) are rendered first; `document_budget = SHORTLIST_INPUT_CHARS_MAX
− len(fixed)`; `fit_cards(cards, budget) -> tuple[list[str], int]` trims one document line
per option per round, oldest year first (null year counts as oldest), and returns the texts
and the count cut; if every document line is gone and the request still exceeds the
ceiling, `ShortlistFailure("input over ceiling")` — never a silent truncation. The final
system-plus-user length is asserted in a test. The golden fixture lives in
`backend/tests/api/fixtures/option_out_full.json`.

P8. **The walk.** In `scoping_plan.py`: `SHORTLIST_PURPOSE = "shortlist"`,
`SHORTLIST_CHAIN = (("shortlist", False),)`, a `compose_scoping` branch;
`LONGLIST_CHAIN` gains `("shortlist", False)` after `theme`. Registration (five points):
`task_plan.OPTIONS_SCOPING_STEPS`, `run_spec.COMPONENT_REGISTRY`,
`runner.LLM_BEARING_COMPONENTS`, `harness._SCOPING_STEPS` (`shortlist_scope`,
`"longlist_backend"`), `harness.build_graph`. Stage: `STAGE_BY_REGISTRY["shortlist"] =
"select"`, **and** `STAGE_PRESENTATION` gains a per-registry override so the scoping
component shows ("Shortlisting", "Proposing places for close reading.") while the Evidence
search's `select` keeps its words (PR21: the shared blurb "The strongest, most varied set"
is a ranking claim; the override's words are the lead's, approved by the owner at 6b).
Opener `open_shortlist_walk(engine, *, task_id, user, executor, backends, suggest: bool)`
in `api/longlist_start.py` **with the same shape as `open_longlist_walk`** (PR5:
`admit_and_mint` takes an Engine, executor and backends and hard-codes the longlist
composition; the shortlist opener duplicates only the purpose, intent and context lines);
scope context `{"suggest": true}` when `suggest`; refusals `run_active`, `capacity`,
`no_longlist`, `nothing_to_propose` (computed from the option rows), and `plan_stale` when
`longlist_inputs(current) ≠ longlist_inputs(pinned)` (PR6). It returns a `LatestRun`
(PR22), the class `PlanOut.opened_run` already uses.

P9. **Routes and actions.** `api/longlist_actions.py` gains `shortlist_option` and
`unshortlist_option` (the `exclude_option` pattern: `admit_longlist_action`, the row, the
state change, `_event`); **`exclude_option` also sets `shortlist_state = NULL,
shortlist_reason = NULL`** and `include_option` does not restore them, with a regression
test (PR10); events `OPTION_SHORTLISTED = "option.shortlisted"`, `OPTION_UNSHORTLISTED =
"option.unshortlisted"`, `SHORTLIST_PROPOSED = "shortlist.proposed"` in `repository.py`
beside the existing three; `GET /decisions` renders the two user events as `decided_by:
user` and the proposal as `decided_by: agent` with the line "Policy Atlas proposed N
places". `api/routers/longlist.py` gains the three routes of the contract's table; the
suggest route returns 202 `LatestRun` (PR22).

P10. **The appetite patch.** `patch_plan` is restructured on the `confirm_baseline` pattern
(PR7, `task_agent.py:1644-1652, 1757-1804`): the scoping branch returns its `PlanOut` into
a local, the transaction exits, then `_open_shortlist_after_patch(engine, task_id, user,
executor, backends, previous, current)` runs when `risk_appetite` changed between the
previous and the new version, `longlist_inputs(current) == longlist_inputs(the longlist's
pinned version)` (PR6: not merely the previous version), and a longlist exists; it calls
`open_shortlist_walk(suggest=False)` and sets `opened_run` on the response; on a refusal it
opens nothing and the view's `shortlist.stale` (P1) tells the user to press Suggest more.
When `longlist_inputs` differ, open nothing: the Rebuild path re-proposes through the
chain. A race between this opener and a Suggest more press resolves through the existing
`run_active` refusal: the second caller is refused.

P11. **Rebuild protection (O1).** `user_holds_state(row.exclusion)` stays exclusion-only
(PR9: widening it would shield a user place from every constrain write). A new predicate
`merge_protected(row) = user_holds_state(row.exclusion) or row.shortlist_state ==
"added_by_you"` is applied **only** at the duplicate keep/merge decision in
`constrain.py:850-871` and at the seed fold in `longlist.py:804-859`; exclusion verdicts
still apply and are stored. The read model already serves the exclusion on the row; the
shortlist view shows it as the breach notice.

P12. **Coverage and maturity.** `coverage.option_coverage` adds `evaluating_evidence_type`
and `latest_evaluation_year`. The year's carrier (PR13): `_Unit` and `CoverageMember` in
`longlist.py` and `coverage.py` gain `year: int | None`, read by the read path's existing
`_year(metadata)` helper (`repository.py:191`: `publication_year`, then `year`) applied to
the snapshot metadata the unit already carries, through both the own and the linked paths;
DOI-collapsed documents take the newest year among their copies; a malformed year is
`None` and never counts. `options_scoping/longlist/maturity.py`: `maturity_of(coverage:
Mapping, *, where_country: str | None, today_year: int) -> Maturity | None` (None when the
coverage lacks the new keys); `MATURITY_RECENT_YEARS = 5`; `REVIEW_EVIDENCE_TYPE =
"Systematic Review and Meta-Analysis"`. Read model `MaturityOut{rung:
Literal["proposal_only", "described", "evaluated", "reviewed"], design_mix: str,
none_in_your_setting: bool, latest_evaluation_year: int | None, stale: bool}` on
`OptionSummaryOut.maturity: MaturityOut | None`. The words are frontend copy in
`longlistPresentation.ts`.

P13. **The Potential impact line.** `LINE_QUESTIONS["potential_impact"]`, plain; appended
last in `LINE_NAMES`; `ProfileLineKey` gains it; **`_profile_out` requires the legacy eight
keys and appends `potential_impact` only when present** (PR12: today it returns `None` on
the first missing key, `repository.py:3410-3436`), with tests for eight- and nine-line
rows. Its call uses a dedicated payload (PR19): the shared per-option payload plus, from
the result's coverage entry, the record units (`tried_on`) and `evaluated_countries`, and
once per call the baseline text (first `POTENTIAL_IMPACT_BASELINE_MAX_CHARS = 12_000`
characters), the outcomes as written, the target unit and Where; `PotentialImpactWire`
carries `answer: str = Field(max_length=400)` so the ceiling is enforced on the wire and a
longer answer fails the attempt (the existing one retry applies). The system prompt and
template are `POTENTIAL_IMPACT_SYSTEM_PROMPT` / `POTENTIAL_IMPACT_USER_TEMPLATE`, **lead-
authored before the plumbing is delegated** (PR14). The other eight lines' templates do
not change. `OPTION_PROFILE_PROMPT_VERSION = "option_profile_v4"`; the test at
`test_option_profile.py:350` updates. The card shows it as the last line of "What it would
take"; the grid has no column for it.

P14. **The Task Agent offer (S26).** `APPETITE_OPTION_IDS = {"appetite_tried": "tried_only",
"appetite_mostly": "mostly_tried", "appetite_open": "open_to_untested"}` beside
`DEPTH_OPTION_IDS`; `ScopingPlanDraftWire.risk_appetite: str | None` with the depth field's
instruction pattern; `_appetite_from(text)` beside `_depth_from`; the stub's
`_STUB_APPETITE_OPTIONS`; the prompt offers the three answers once, after depth, and
defaults to the middle when the user does not choose; the step list reads "Shortlist" built,
"Assessment … not in this release". `TASK_AGENT_SCOPING_PROMPT_VERSION =
"task_agent_scoping_v6"`.

P15. **The frontend.** `frontend/src/views/longlist/ShortlistView.tsx` rendered by
`LonglistView` under a third mode chip "Shortlist"; `useShortlistVerb(taskId, "shortlist" |
"unshortlist")` and `useSuggestMore(taskId)` in `api/mutations.ts` on the `useOptionVerb`
pattern; `OptionActionButton` gains the two shortlist actions; the appetite control is a
`<select>` over `RISK_APPETITE_LABELS` calling `usePatchPlan` (no chat seeding) and lives in
`ShortlistView` and in `PlanDocument`'s ScopingSettings; `mock/api.ts` handlers for the
three routes and the patch with in-memory state and the 409 cases. Copy and layout are the
lead's (Phase 6b).

P16. **The staged-check drivers** (PR17), both in the gitignored
`docs/tasks/055-scoping-shortlist/evidence/`: `write_potential_impact.py` runs only the
`potential_impact` call through the live backend for each task in `tasks.json` (the
manifest: seven task ids, four marked `tuning`, three `check`) and writes the key into
`longlist_result.option_profile`; `run_shortlist_check.py` takes the manifest and, per task,
patches the appetite to each of the three values in the order tried_only → mostly_tried →
open_to_untested through the API, waits on each opened walk's completion (the run's
`status` through the existing runs reader, 10 minutes cap), reads back the places, reasons,
note and provenance, and for the check tasks runs `mostly_tried` a second time; it writes
one JSON per proposal and a `measures.json` with M1 (hand column left blank), M2 (lexical
check), M3, M5 (tokens and elapsed from provenance, cost from Langfuse by run id) and M6.
The hand readings are added to the JSONs by the lead. Not product code; recorded in
`verification.md`.

P17. **Degraded notice** (PR26): the shortlist view keys its notice to the task's latest run
having `purpose == "shortlist"` and a degraded or failed status; an unrelated degraded run
shows nothing there (view test).

## Open at the plan gate

- **The words** of the appetite control, the stage override and the shortlist view's
  labels are fixed at Phase 6b with the owner (lead copy).

## Plan-review folds (2026-10-27)

| # | Finding (short) | Fold |
|---|---|---|
| PR1 | A NOT NULL column with its default dropped breaks the longlist insert | P3: the default is kept |
| PR2 | A Rebuild inserts a fresh row, losing the previous proposal | P4: the previous proposal is read from the newest `shortlist.proposed` event |
| PR3 | Backends return `UsageResult[T]`; `traced_parse` takes `response_format` | P6 |
| PR4 | `call_with_retry` cannot carry the failures into the second call | P5: a shortlist-specific two-attempt loop |
| PR5 | `admit_and_mint` is not a generic admission seam | P8: the opener has `open_longlist_walk`'s shape |
| PR6 | Appetite-only check must compare to the longlist's pinned version | P8, P10: `plan_stale` and the pinned comparison |
| PR7 | `patch_plan` returns inside its transaction | P10: the `confirm_baseline` pattern |
| PR8 | A response-only `shortlist_pending` flag vanishes | P1: derived `shortlist.stale` on `LonglistOut` (contract amendment PG1) |
| PR9 | Widening `user_holds_state` shields too much | P11: a separate `merge_protected` predicate |
| PR10 | Exclude must clear the place | P9 |
| PR11 | The appetite must travel the seed, builder and `part_ids` paths | P1 |
| PR12 | `_profile_out` returns `None` on a missing key | P13 |
| PR13 | No year carrier in `_Unit`/`CoverageMember` | P12 |
| PR14 | Prompt text assigned to `fast-worker` | P13, Phase 2: lead authors first |
| PR15 | The baseline reader is private; baseline cut unaccounted | P4: a public `baseline_text`; `baseline_chars_cut` (contract amendment PG2) |
| PR16 | No storage for usage or elapsed time | P5: `provenance.usage` per attempt; cost from Langfuse |
| PR17 | No executable driver or manifest for the 24 proposals | P16 |
| PR18 | Phase 2 changes public models on a fast gate | Phase 2 gate gains `make openapi-sync` and the generated-artifact diff |
| PR19 | No route for the line's coverage inputs; no 400-char enforcement | P13 |
| PR20 | The ceiling must cover the whole request | P7 |
| PR21 | The shared `select` blurb is a ranking claim | P8: a per-registry presentation override (contract amendment PG3) |
| PR22 | `OpenedRunOut` does not exist | P8, P9: `LatestRun` |
| PR23 | Label maps cannot be compared through the OpenAPI enum | P1 |
| PR24 | `SCOPE_PURPOSES` does not exist | P3 |
| PR25 | A `FOR UPDATE` lock held across model calls | P4: lock late, re-validate, write |
| PR26 | The degraded notice needs a key | P17 |
| PR27 | "21 proposals" survives in the rubric and contract | Fixed to 24 (contract amendment PG4) |

## Phase 0 — Build-open baseline — `lead` (inline)

Reason: a one-command check. Full `make verify` on the branch head; record the tail. Commit
ADR 0041 (step 4) before Phase 1.

## Phase 1 — The revision, the plan field, staleness, read-model additions (items 1, 10; P1–P3; A1, A6, A15, A22) — `deep-reasoner`

Brief: P3's revision and test; P1's field, patch, labels map and `shortlist_pending`; P2's
projection and `plan_inputs_changed`; `OptionSummaryOut.shortlist: ShortlistStateOut |
None` (`state`, `reason`) and `LonglistOut.shortlist: ShortlistOut` (`note`, `provenance`,
`places_target`) served from the columns, empty for old rows; `make openapi-sync`; the
contract's item-1 tests except the opener (Phase 4). Done when full `make verify` is green.

Gate: **full `make verify`**. Commit.

## Phase 2 — Coverage, maturity and the Potential impact line (items 6, 7; P12, P13; A3; PR12–PR14, PR18, PR19) — `lead` then `fast-worker`

2a `lead` (reason: prompt-bearing): `POTENTIAL_IMPACT_SYSTEM_PROMPT`, the user template and
the wire's field descriptions, written first and committed with the version bump and
re-pin (PR14). Tuned in Phase 7.
2b `fast-worker`: P12's year carrier, coverage keys, `maturity.py`, `MaturityOut`, the
item-7 tests; P13's key, payload, wire ceiling, `_profile_out` rule, the card's ninth line
and `LINE_NAMES` on the frontend, the item-6 tests. `make openapi-sync` and the generated
TypeScript diff reviewed in the same commit (PR18).

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` · `make openapi-sync`
(clean) · `make frontend-verify`. Commit (2a and 2b separately).

## Phase 3 — The component, the walk, the seam, the card text (items 3, 4; P4–P8; A5, A7, A11–A13, A27; PR1–PR6, PR15, PR16, PR20–PR22, PR25) — `lead` then `deep-reasoner`

3a `lead` (reason: prompt-bearing): `SHORTLIST_SYSTEM_PROMPT`, the user template and the
wire's field descriptions (`shortlist_v1`), written first, committed and re-pinned. Tuned
in Phase 7.
3b `deep-reasoner`: P4–P8 in full; the public `baseline_text`; the stub's queue and
defaults; the golden card-text test and the whole-request length test; the item-3 and
item-4 tests of the contract (checks, the second request's text, places, chain order,
degrade, the shortlist walk, the stage frame and override, registration, the late lock and
re-validation, the event, the previous proposal from the event). One brief; the delegate
reports the measured card-text size of the mock longlist fixture and confirms the import
path causes no cycle.

Gate: **full `make verify`**. Commit.

## Phase 4 — Routes, actions, events, the appetite patch, Rebuild protection (items 2, 5; P9–P11; A4, A16, A18; O1, O2; PR6–PR11) — `deep-reasoner`

Brief: P9's handlers, routes and events, the Exclude clearing, the History line; P10's
restructured patch flow; P1's `shortlist.stale`; P11's `merge_protected` at its two sites;
the opener's refusals; the item-2, item-5 and remaining item-1 tests; `make openapi-sync`.

Gate: `make verify-fast` · `make drift-check` (the full gate at Phase 5). Commit.

## Phase 5 — The Task Agent offer (item 9; P14; S26) — `lead` + `fast-worker`

5a `lead` (reason: prompt-bearing): the prompt's appetite offer and step wording,
`task_agent_scoping_v6`, re-pin.
5b `fast-worker`: the wire field, `APPETITE_OPTION_IDS`, `_appetite_from`, the stub
options, the seed/builder/`part_ids` paths of P1 (PR11), `SCOPING_STEPS` wording, the
item-9 tests.

Gate: **full `make verify`** (closes Phases 4 and 5). Commit.

## Phase 6 — The frontend (items 2, 8; P15; A9, A17, A22, A25; O3) — `fast-worker` then `lead`

6a `fast-worker`: structure. `ShortlistView` with the contract's seven blocks in order, the
empty state, the `stale` line and the degraded notice keyed per P17; the mode chip; the
actions on rows, tiles and card; the appetite control in both places; the mutations; the
mock handlers; `planStart.ts` on `plan_inputs_changed`; the contract's frontend tests.
6b `lead` (reason: taste-bearing surface and product copy; `impeccable`): the rows' layout
against the list rows (R85) and the card's grey lines, the words of every label, empty
state and notice, the disabled Assess line, the note's label, the stage override's words
(P8), the appetite control's words — each put to the owner. Screenshots of the live dev
app (`playwright-screenshots-live-dev`) into the evidence folder.

Gate: `make frontend-verify` · `make verify-fast`. Commit (6a and 6b separately).

## Phase 7 — The prompt loops on the stored tasks (item 13; M1–M6) — `lead`

Reason: prompt-bearing and the hand reading. Four tuning tasks, three check tasks (named in
`verification.md` before the first round).

7a **Potential impact.** Run P16's script on the tuning tasks; read every line against the
contract's form (conditional magnitude · pathway against the baseline · reach · evidence
footing; no "works", no number); revise the prompt; at most three rounds; then the check
tasks once (M4). Each round: re-pin, commit on `make verify-fast` · `make prompt-guard`.
7b **The shortlist.** `run_shortlist_check.py` (P16) over the tuning tasks (12 proposals);
read each reason against its card (M1), the lexical check (M2), the mix (M3); revise the
prompt; at most three rounds; then the driver over the check tasks: three appetites each
plus the second `mostly_tried` run (12 proposals; M3, M5, M6). Each round as 7a. The
per-proposal JSONs with the hand columns filled, `measures.json` and the M table go in the
evidence folder and `verification.md`.

Stop measure for the loops: a round that changes no reading on the tuning set ends the
loop; the check set is read once and never tuned on.

## Phase 8 — Live check, evidence, specs, deferred, step-6 exit — `lead`

Reason: owner-facing decisions and the hand check. One rapid run on a new task through the
browser (the contract's stage 2; M7 with the seeded places); the M1–M7 table read back from
the saved files; the token, character and cost figures beside the longlist walk's; the
prompt texts and hash diff; the OpenAPI diff; the migration round-trip tail. Spec changes
1–9 and 4b–4c: the lead puts each wording to the owner and applies only accepted wording,
with one line each in `docs/specs/log.md`. `docs/deferred.md` § task 055 seams. Full
`make verify`; the CI run URL for rubric 15. **Stop.** The review runs in a fresh
conversation with `task-cycle-review`.

Gate: **full `make verify`**. Commit.
