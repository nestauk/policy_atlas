# Verification: 033-ux-snags

Evidence for one slice. Public-safe: no secrets, raw source text, credentials or
unredacted traces. Filled at step 6; **Review findings** and **Rubric status**
are added after the review stack (step 7), which runs in a fresh conversation.

> **Adversarial review did not run.** The owner waived it on 2026-08-24 (plan
> § Review stack, D6; 032 precedent). The slice **stays Tier 3** regardless — a
> join table, a public write-shape change, and a planner bump are a hard gate.
> What is given up is the fresh-context attack on the *design*: the lane that
> finds an unstated assumption or a missed requirement rather than a local bug.
> The places that would most have benefited are membership tenancy on the join
> table, Included `source_count` honesty, and OECD-as-origin vs study-setting
> in `planner_v9`. `/security-review` and the OpenAPI diff cover the first two;
> the prompt change is lead-authored and pinned. The exposure is narrower than
> a blanket waiver but is not zero. It was also unavailable as specified: the
> mechanism is the other model family via `codex-rescue`, and the Codex CLI is
> not installed — the same gap escalated on 031 and 032, so **no non-Claude
> reviewer has read this slice either**. The PR must repeat this waiver.

## Approval gates

All three fired and all three were approved by the owner on 2026-08-24, in the
combined contract+plan gate, before implementation:

| Gate | What changed | Approved |
|---|---|---|
| Schema | `portfolio_membership` join table; migrate `project.portfolio_id`; drop that column. Alembic `c4e8a2b1d9f3` (revises `b3c7d914e0a2`) | yes |
| Public interface | `ProjectOut.portfolio_ids` replaces `portfolio_id`; PATCH replace-all (`omit` unchanged, `[]` unassign); `source_count` = Included; additive `FindingOut.chunk_id`; SSE summary may include `round_index` | yes |
| Prompt surface | `planner_v8` → `planner_v9`; default `country_group: "OECD members"`; spoken chip; origin ≠ study setting | yes |

No extra table, route, or prompt surface beyond those three.

**Round 2 (owner steers, 2026-08-25):** the prompt gate shipped as
**`planner_v10`**, superseding v9 within this branch — the owner added a
verbatim OECD study-setting screening criterion (`OECD_SETTING_CRITERION`)
alongside the origin default, because origin filters cannot see study
setting. Same gate, one further rev; hash re-pinned; pin test asserts v10.
See § Round 2 below for the other steers.

## Commands run

| Command | Result | Notes |
|---|---|---|
| Isolated `make verify` at Phase 0 (clean `dev`) | **not captured** | See § Gate-map deviations |
| Isolated `make verify` at end of Phase 1 | **not captured** | Same |
| `make verify` during build (agent) | **fail** then **fail** | 7 red tests (table-count 35 vs 34; SSE `stage.started` vs every `run.started`); then ruff E501 on the OECD/HIC line. See § Incidents |
| `make verify` (step-6 exit, owner, 2026-08-24) | **pass** (`EXIT=0`) | backend **2174 passed** · mypy 266 files clean · ruff clean · uv build · infra 45 passed · audit-paths 105 files, 0 violations · prompt-hash-guard 12 modules unchanged · font-guard · drift-check OK · `make frontend-verify` **409 tests / 61 files**, vite build |
| `pnpm exec playwright test e2e/journey.spec.ts` | **not run to completion** | Playwright Chromium binary missing in this environment (`playwright install` not run). Not a product failure. |

**Gate-map deviations.** The plan asked for three *isolated* full `make verify`
runs (baseline, end of schema/API, step-6 exit) and per-frontend-phase
`make frontend-verify`. This conversation picked up a branch that already had
the implementation in flight. Isolated Phase 0 and Phase 1 full runs were
**not** recorded separately; the owner's green step-6 `make verify` is the
full-suite evidence. Frontend work was gated by that same `frontend-verify`
(it is the last stage of `make verify`), not by three named mid-phase runs.
Phases were **not** committed as the plan's per-phase commits — the working
tree is still uncommitted on `task/033-ux-snags` (commit only on request).

## Checks beyond the build

- **Deterministic tests** — Included `source_count` (null with no
  `capability_run`, 0 after a run with none Included, 2 after two `relevant`
  screens and one not); membership (two portfolios, omit-leaves-unchanged,
  `[]` unassign, unowned id 404 and no write, unknown-vs-cross-owner 404
  equality); S7 PATCH name + `portfolio_ids` while `running` → 200, status
  unchanged; S9 IOF `chunk_id` set / ICF null; S5 SSE summary flattens nested
  `round_index`; ingest_full_text is not a public `acquire` stage;
  `planner_v9` pin + OECD / origin-not-setting / contiguous HIC refusal
  strings; migration round-trip in `tests/core/test_schema.py`; frontend: round
  labels, Search queries section, lifecycle Share-from-creation, Plan document
  "Source geography" / "None selected". Results in the table above.
- **AI evals** — none. The planner bump is judged at a live planning turn, not
  a scored eval (contract § Acceptance checks).
- **Manual / browser** — see § Live check.

## Migration round-trip

Revision **`c4e8a2b1d9f3`** (revises 032's `b3c7d914e0a2`): creates
`portfolio_membership` (`portfolio_id`, `project_id`, `created_at`), PK
`(portfolio_id, project_id)`, FKs, copies existing `project.portfolio_id`
rows, drops the column and `fk_project_portfolio_id`. Unassigned projects
stay unassigned (no membership row). Asserted in `tests/core/test_schema.py`.

`len(metadata.tables)` is **34** (33 on `dev` + join table). The module
docstring's "plus one read view" is `finding_reference_union`, which is
already inside that 34 — it is not a 35th metadata entry. Six copy-pasted
`== 35` asserts were wrong; they now match 34.

## End-to-end command

```
make verify
```

Owner run, 2026-08-24, `EXIT=0`. Backend pytest 2174 passed in ~299s; frontend
vitest 409 passed in ~18s.

Named backend tests that pin the snags:

```
make -C backend test \
  tests/api/test_projects_router.py \
  tests/api/test_portfolios_router.py \
  tests/api/test_read_models.py \
  tests/api/test_sse.py \
  tests/runtime/test_planner.py \
  tests/core/test_schema.py
```

## Diff summary

Committed on `task/033-ux-snags` (from `dev`): `518cff2` (round 1, below)
and `5594693` (round 2, § Round 2). One slice, ten snags:

1. **S1** — `source_count` counts effective screens with status `relevant`
   (Included). `None` iff no `capability_run`; `0` if a run exists and none
   are Included.
2. **S2** — `<Chip tone="blue">BETA</Chip>` next to the wordmark (`NavHomeLink`).
3. **S3 / ADR 0032** — `portfolio_membership`; public `portfolio_ids`; Share
   lists / add / remove; Share unlocked from task creation; mock
   `GET /api/v1/portfolios`.
4. **S4** — `/` with zero active and zero archived tasks → `/new`. Archived-only
   is not first-time. Deep links untouched.
5. **S5** — SSE `_summary` flattens nested `round_index`. Frontend keeps every
   acquire/screen SSE entry; labels `Searching (Round N)` / `Screening (Round N)`
   when N > 1. `ingest_full_text` is **unmapped** from public `acquire` (it
   used to overwrite Searching). `_draft_from_plan` uses `STAGE_BY_REGISTRY.get`
   so unmapped components do not `KeyError`.
6. **S6** — "Search queries" under the All-sources table from
   `coverage.backends_detail[].queries`. Honest absence when empty.
7. **S7** — PATCH name / `portfolio_ids` already `FOR UPDATE` the project row;
   regression: 200 and `running` unchanged.
8. **S8** — Findings `page_size` 50, `?page=`, Previous/Next; one
   `setSearchParams` updater; group chips set `facet` + `group` together.
9. **S9** — additive `FindingOut.chunk_id`; expand uses existing chunk-context
   route + highlight. Abstract-only stays null.
10. **S10** — `PLANNER_PROMPT_VERSION = "planner_v9"`; default OECD members
    origin; spoken chip; "Source geography" / "None selected"; no silent
    UK/HIC screening criterion. Hash pin via `python3 scripts/prompt_hash_guard.py --update`
    for `planner_prompt.py` only. OpenAPI via `make openapi-sync`.

Specs `web-api.md` and `data-model.md` updated. Many-to-many and mock
`/portfolios` discharged in `docs/deferred.md`. Real sharing stays deferred.

## Round 2 — owner steers after the round-1 build (2026-08-25/26)

Commit `5594693`, plus a small uncommitted tail (journey.spec.ts scoping,
OpenAPI regen). Not new snags; all are steers on the shipped surfaces:

1. **`planner_v10`** — OECD study-setting screening criterion added verbatim
   (`OECD_SETTING_CRITERION`), on top of v9's origin default. Hash re-pinned
   via `prompt_hash_guard.py --update`; `test_planner_prompt_version_pinned`
   asserts v10.
2. **Results tab unlocked while `running`/`paused`** — supersedes 032's
   locking table so the in-progress write-up is reachable; failed/aborted/
   interrupted still lock Results. `lifecycle.ts` + tests updated.
3. **Citation-context rework** (grey off-topic neighbours; artefact 404s) —
   both context keyings now share `_clamped_quote_window` in
   `repository.py`: `locate_unique_span` for the artefact path too (curly
   quotes/case/whitespace now 200 instead of 404), `previous`/`next` reduced
   from whole adjacent chunks to ≤220-char edge snippets attached only when
   the ±800 window hits that chunk boundary, cuts snapped to word boundaries,
   `...` marking truncated edges. Spec § chunk context and
   `docs/knowledge/chunk-context-two-keyings.md` updated; new tests in
   `test_read_models.py`.
4. **Type-scale / layout pass** — all-caps labels and chips `text-caption` →
   `text-meta` (14px); chart ticks 14px; `scrollbar-gutter` released under
   `html.overflow-hidden` (dead right-edge strip); Sources/Plan widths kept;
   query cells `break-all`; count line moved between filters and table.
5. **Failed summary placeholder removed** — `AnswerCallout` renders nothing
   on `failed` (pending copy stays).

Round-2 verification: `make frontend-verify` green 2026-08-25 (414 tests /
62 files); targeted backend suites 2026-08-26 — `test_read_models.py` +
`test_conversations_router.py` 33 passed, ruff clean; `make openapi-sync` +
`make drift-check` OK 2026-08-26 after the ChunkContextOut docstring change.
A full `make verify` has **not** been re-run after round 2 — run it before
the PR.

## Incidents (build-time, for the review conversation)

- **`len(metadata.tables)` is 34, not 35.** Adding `portfolio_membership` to a
  metadata dict that already includes the `finding_reference_union` view yields
  34 keys. Six files (embeddings, appraise, classify, screen, acquire,
  ingest_full_text) had been bumped to 35. Symptom of a duplicated magic
  number, same class as 032's table-count tax.
- **Unmapping `ingest_full_text` from public `acquire` breaks a 1:1
  `stage.started` ↔ `run.started` assertion.** Replay still emits
  `run.started` for ingest; it no longer emits a public stage frame. The test
  now counts only payloads for which `stage_for_payload` is not `None`.
  `_draft_from_plan` must use `.get()` on `STAGE_BY_REGISTRY` or planning
  `KeyError`s on ingest.
- **The HIC-refusal string must stay a contiguous substring *and* fit ruff
  E501.** Splitting `Do NOT add a UK or high-income screening criterion`
  across lines failed `test_planner_prompt_defaults_source_origin_to_oecd_members`.
  Keeping it on one over-long line failed ruff. Wrap *after* the required
  phrase; then re-pin the prompt hash.
- **S1 `source_count` keys off `capability_run`, not `runs`.** Screening rows
  still FK `screened_by_run_id` → `runs.run_id`. Tests must seed both or the
  count stays `None`.
- **Direct pytest against `DATABASE_URL=.../policy_atlas` is refused.** Use
  `make test` (targets `policy_atlas_test`).
- **Piped `make verify | tail` can hide a red exit.** Same 032 lesson. Read
  `EXIT` from `make`, not from `tail`.

## Public safety

Everything in the working tree is public-safe: task docs, ADR, migration, API
contract, prompt text, tests and fixtures with synthetic content. No acquired
or uploaded source text, no real run traces, no live model output, no
screenshots of real projects.

## Review findings

_Added at step 7, in a fresh conversation — the adjudicator must not be the
chat that wrote the code._

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **`/simplify`:**
- **Adversarial review:** not run — waived by the owner 2026-08-24, and
  unavailable as specified (no Codex CLI on PATH). See the note at the top of
  this file.

## Rubric status

_Added at step 7. Every item in [rubric.md](rubric.md) checked, or explicitly
listed as not satisfied with the reason._

## Intent & assumptions

- Screen **Task** = `project`; screen **Project** = `portfolio` (ADR 0031).
- Included = effective screen `relevant`.
- OECD pin is the exact label `"OECD members"` (38 ISO codes).
- Share-from-creation is assignment, not sharing. Copy stays coming-soon.
- Default geography is publisher/author origin, not study setting.

## Live check

**Scope, as the contract pinned it:** changed surfaces plus a cheap full-chain
smoke. Deep-run findings (S8/S9) need a live model route.

**Staging model route.** Staging's OpenAI quota has been recorded exhausted
since 2026-07-28 (AGENTS.md). No live planning turn and no deep-run findings
expand were driven against a real project. **Not claimed as passed.**

**Mock Playwright journey.** Not completed here: Chromium headless is not
installed in the agent environment (`pnpm exec playwright install` was not
run). The suite is still the 032 rewrite (`frontend/e2e/journey.spec.ts`) and
is a **separate CI job**, not part of `make verify`. Unit/component tests
cover BETA (`Nav.tsx`), empty redirect (`TasksListView.tsx`), round labels
(`RunningCard.test.tsx`), Search queries (`SourcesView.test.tsx`), Share
unlock (`lifecycle.test.ts`), Plan geography copy (`PlanDocument.test.tsx`).
**Eye-driven mock pass of Share add/remove, empty-account redirect, and the
running-card round list was not done in a browser in this conversation.**

| # | Contract check | Result |
|---|---|---|
| S2 BETA chip | Unit/render only | Covered by `NavHomeLink` + Chip; **not** eye-checked in a browser |
| S4 empty `/` → `/new` | Unit | `TasksListView` navigates when active and archived lists are both empty |
| S3 Share add/remove + mock `/portfolios` | Component + mock API | Share PATCH `portfolio_ids`; mock GET `/portfolios`. **Not** clicked in a browser |
| S5 round rows | Unit | `Searching (Round 2)` / `Screening (Round 2)` when max round > 1 |
| S6 queries section | Component test | Heading + OpenAlex query from mock coverage |
| S8/S9 live findings | **Gap** | Needs a live model route; staging quota exhausted; fixtures + this row |

## Known unverified items

- Isolated Phase 0 and Phase 1 full `make verify` runs (gate-map deviation).
- Browser eye-check of BETA, empty redirect, Share membership, round card,
  queries section.
- Mock Playwright journey (missing browser binary here; CI still has the job).
- Live OECD default in a real planning conversation (needs a live planner
  route).
- Live group-chip 422: one `setSearchParams` updater is in place; **not**
  exercised against a live API. If CI or a human finds a remaining
  label-vs-`group_id` mismatch, fix or record — do not drop.
- Per-phase git commits — the work landed as two commits (round 1 + round 2),
  not the plan's per-phase commits.
- Full `make verify` after round 2 (only targeted suites + frontend-verify +
  drift-check re-run since the owner's 2026-08-24 green run).

## Review handoff (step-7/8 inputs)

**Adjudication items**

- Gate-map: three isolated full verifies not captured; one green owner
  `make verify` at exit.
- Uncommitted phases vs plan's per-phase commits.
- Table-count 34 vs a mistaken 35.
- `ingest_full_text` no longer a public Searching row — intentional S5.
- Live S8/S9/S10 and browser eye-check recorded as gaps, not passes.
- S8b live 422 not re-probed after the single-updater fix.

**Executor provenance** — no family flip. Codex CLI is not on PATH. Lead wrote
the planner bump and membership semantics. The rest of the build ran in this
conversation.

**Knowledge candidates** (step-8 input):

- **`metadata.tables` counts views that are registered as `Table`s.** "N tables
  plus one read view" is prose, not `len+1`. Adding a real table does not
  always bump the magic number by the amount the docstring suggests.
- **Six (now still six) hard-coded `len(metadata.tables) == K` asserts** in
  unrelated test modules remain a schema-slice tax. 032 already named this;
  033 paid it again.
- **Public stage vocabulary and `run.started` are not 1:1** once a registry
  component is unmapped. Replay tests must filter through `stage_for_payload`.
- **`STAGE_BY_REGISTRY[x]` in planning will throw** for any component you just
  unmapped from the public vocabulary. Use `.get()`.
- **Prompt substring tests and ruff E501 fight.** Keep the required phrase
  contiguous; wrap *after* it; re-run `scripts/prompt_hash_guard.py --update`.
- **`source_count` "has a run" means `capability_run`,** while screening FKs
  point at `runs`. Seeding only one of them looks like a product bug.
- **Direct pytest against `policy_atlas` is refused.** `make test` is the
  only legal entry.
- **macOS default volume is case-insensitive.** Do not treat a case-only path
  change as a different repository.

## Deferred work

Seams in [docs/deferred.md](../../deferred.md):

- Many-to-many membership — **discharged**.
- Mock `/portfolios` — **discharged**.
- Real sharing/export, portfolio soft-delete, case studies, `plan.title`
  write-back, `project`→task rename in the database — still deferred.
