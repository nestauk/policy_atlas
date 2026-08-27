# Task contract: 033-ux-snags

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** approved 2026-08-24 · owner (combined contract+plan gate).
> Plan approved (before implementation): 2026-08-24 · owner ·
> ADR: [0032](../../adr/0032-portfolio-membership-many-to-many.md).
>
> **Branching:** `task/033-ux-snags` from `dev`. 032 is merged.
>
> **Lightweight cycle:** adversarial review is waived (032 precedent). The
> tier stays 3. `verification.md` and the PR must say so. Codex is not on
> PATH; no phase routes to it.

## Goal

Fix ten numbered UX snags on the 032 surfaces. Planning-chat behaviour
changes only for the geography default (S10).

## Deliverable

One PR on `task/033-ux-snags` that:

- Counts Included sources on the task list (S1).
- Shows a BETA chip next to the wordmark (S2).
- Lets one task belong to many projects, assigned from Share (S3).
- Sends a first-time user from `/` to `/new` (S4).
- Shows every search/screen round on the running card (S5).
- Lists search queries under the All-sources table (S6).
- Keeps a running walk alive across rename and membership writes (S7).
- Pages the findings table and makes group chips work (S8).
- Shows a finding quote in its chunk (S9).
- Defaults source origin to OECD members and says so in planning chat (S10).

## Terms

| Term | Meaning |
|---|---|
| **Task** | Screen word for a `project` row (ADR 0031). |
| **Project** | Screen word for a `portfolio` row (ADR 0031). |
| **Included** | Funnel `relevant`: latest effective screen status `relevant`. Same population as the Sources filter `Included`. |
| **Round** | One acquire pass plus the screen that follows it. Broad = 2, Broadest = 3. |
| **OECD members** | Pinned Tier-1 country-group label. 38 ISO codes in `country_filters.py`. Exact string the planner must emit. |
| **S1–S10** | Defect ids. Goal, scope, invariants, plan phases and rubric items all cite these. |

## Read first

- [web-api.md](../../specs/system/web-api.md) § Projects, § Portfolios, § Read models (findings, coverage, chunk context).
- [data-model.md](../../specs/system/data-model.md) § Entity hierarchy (portfolio sits *above* the project; this slice does not insert a container between project and artefact).
- ADR [0031](../../adr/0031-portfolio-layer-above-the-project.md) (amended by 0032 on membership cardinality).
- `planner_v8` in `backend/src/policy_atlas/runtime/planner_prompt.py` (geography / `country_group` rules).

## Defects

### S1 — Task-list source count is Found, not Included

`ProjectOut.source_count` counts every `project_source_snapshot` row. The
task list should show Included only — the funnel's `relevant` population.

- `null` = no run yet (question unasked).
- `0` = a run exists and none are Included (including "screening has not
  marked any yet").
- `N` = N Included sources.

Reuse the effective-screen population. Do not invent a third counter.

### S2 — BETA chip

A BETA chip sits immediately to the right of the wordmark in the top nav
(`NavHomeLink`). Use the existing `Chip`. Not a route, not in the nav
items.

### S3 — A task can belong to many projects

Today membership is one nullable `project.portfolio_id` (deferred in
`docs/deferred.md`). This slice discharges that seam.

- Join table `portfolio_membership` (`portfolio_id`, `project_id`,
  `created_at`). PK `(portfolio_id, project_id)`.
- Migrate existing FK rows, then drop `project.portfolio_id`.
- `ProjectOut.portfolio_ids: uuid[]` replaces `portfolio_id`. Empty list
  = unassigned (still a normal state).
- `PATCH` `portfolio_ids`: omit = unchanged; `[]` = unassign all; a list
  replaces the set. Each id must be an owned portfolio or the write is
  404 and does not happen (existence oracle rule unchanged).
- A task in two projects counts in both `task_count`s. `source_count`
  stays on the task and is never summed onto a project.
- Share tab lists current memberships, "Add to a project", and remove.
  Sharing copy stays "coming soon".
- Share is **open from task creation**, not locked until the run
  succeeds. Assignment is about the task, not the run.
- Mock `/api/v1/portfolios` (deferred in 032) is in this slice so Share
  works under `VITE_MOCK=1`.

### S4 — First-time user lands on New

After login, `/` with zero **active** tasks redirects to `/new`. Clicking
Tasks with an empty account may bounce again (empty home is New). Do not
steal a deep-link (`/projects/:id`, `/new`, `/portfolios`, …). Archived-only
is not first-time: those users have created a task.

### S5 — Running card hides earlier rounds

`stageRows` keeps one SSE entry per stage key, so Broad/Broadest collapse
to the last round. `ingest_full_text` also maps to public stage `acquire`
and can overwrite Searching.

- Keep every acquire/screen cycle as its own row.
- Label `Searching (Round 2)` / `Screening (Round 2)` when more than one
  round exists or is in flight. Round 1 of a single-round (Focused) run
  stays `Searching` / `Screening`.
- Flatten `round_index` onto SSE `stage.completed` summary (nested values
  are stripped today).
- Full-text ingest is not a Searching row.

### S6 — Boolean queries are not on Sources

`GET .../coverage` already returns `backends_detail[].queries`. 032
unmounted the old "Where I looked" card. Add a "Search queries" section
**under** the All-sources table. Group by backend. No new round field.

### S7 — Rename (and membership) must not stop a running walk

PATCH name and membership are not 409 `run_active` today; archive and
plan-edit are. A rename that appears to stop the walk is a defect.

Likely causes: event-log sequence collision (`events.append` retries 5
times; the PATCH already `FOR UPDATE`s the project row) and frontend
query invalidation tearing down the SSE store.

Invariant: PATCH name and add/remove membership while a walk is
`running` or `paused` → 200, run stays in that status, stream continues.
Do not 409 these writes.

### S8a — Findings table is not paged

The API already pages (default 50, cap 200). The UI asks for 200 and
never pages, so deep extracts look endless and anything past 200 is
dropped while the heading still shows the full total.

Copy the Sources pager. `page_size` 50. URL `?page=`. Reset page when
kind/group filters change.

### S8b — Group chips 422 on the live API

Two `setSearchParams` calls in one click leave `?group=` without
`?facet=`. Live API 422s (`facet` and `group` must arrive together). Mock
ignores the incomplete pair, so the chip looks like a no-op.

One updater, same pattern as Sources. If the filter still fails after
that (label vs `group_id`), fix or record in `verification.md`. Do not
silently drop.

### S9 — Findings show the quote without the chunk

`FindingOut` has `quote` / `quote_verified` only. Additive nullable
`chunk_id` on the finding read shape. Expanding a row with a `chunk_id`
calls existing `GET .../chunks/{chunk_id}/context?quote=`. Abstract-only
findings stay quote-only. Reuse the artefact/chat highlight pattern.

### S10 — Default source origin is OECD members

Default **source origin** to `country_group: "OECD members"`. Bump
`planner_v8` → `planner_v9`. The planner says so in `reply` and on the
scope chip.

Relabel "Document geography" → "Source geography". Empty display →
"None selected".

Honesty: this filter is publisher / author-affiliation origin, **not**
study setting. Do **not** silently add a UK/high-income screening
criterion. The planner may offer a study-setting criterion if the user
asks about UK setting. Hash pin + planner replay.

A user who clears geography keeps "no origin filter". Do not re-apply
the default on later turns.

## Scope / Out of scope

**In:** schema + Alembic; project/portfolio routers and contract;
findings read model; SSE summary flattening; `planner_v9`; Share,
Sources, Findings, running card, nav, task list, first-login redirect;
mock portfolios; OpenAPI regen; specs `web-api.md` (and a short
data-model note that the join table sits above the project).

**Out:** real sharing/export; portfolio soft-delete; case studies;
writing `plan.title` back; changing `screen_v2` / `select_rerank_v1`;
findings pager on the source dossier or artefact; more than 8 group
chips; renaming `project`→task in the database; Overton "Very high
human development" group.

## Constraints & approval gates

Approved with this contract (combined gate, 2026-08-24 · owner):

1. **Schema** — `portfolio_membership`; drop `project.portfolio_id`.
2. **Public API** — `source_count` means Included; `portfolio_ids`
   replaces `portfolio_id`; additive `FindingOut.chunk_id`; SSE summary
   may include `round_index`.
3. **Prompt** — `planner_v9` OECD default + spoken chip. Lead-only.

No new runtime egress. No new dependencies. OpenAPI is regenerated, not
edited by hand. Prompt hashes update only for `planner_prompt.py`.

## Public / private boundary

Public-safe: contract, plan, rubric, ADR, OpenAPI, tests, verification
notes. Private: live source text, traces, credentials.

## Model route

`planner_v9` uses the existing planning route (OpenAI under approved
controls). No new provider. No other prompt surface changes.

## Disciplines binding this slice

- Don't flatten status. OECD-as-origin is not study setting — say so.
- Model only what behaves: membership rows change grouping; they do not
  give a portfolio a lifecycle.
- Honest absence: `source_count` null vs 0 stays distinct.
- Flag, don't drop: S8b is fixed or recorded, not silently omitted.
- Deferred seams stay in `docs/deferred.md` (real sharing, portfolio
  archive, case studies).

## Stop conditions

Halt if a new table, route or prompt surface beyond the three named
gates is needed; if OECD-as-origin cannot be said honestly; if rename
still kills a walk after the lock/SSE fixes and the cause is outside
this slice.

## Acceptance checks

- `make verify` green at baseline, end of schema/API phase, and step-6
  exit. Frontend phases: `make frontend-verify`.
- Deterministic tests for S1, S3 membership (including two portfolios,
  unassign, cross-owner 404), S7 running-walk PATCH, S8a/S8b, S9
  `chunk_id` null vs set, S10 planner replay / geography compile.
- Manual: BETA chip; empty-account redirect; Share add/remove;
  queries section; running-card rounds (fixture or live). Deep-run
  findings (S8/S9) need a live model route; if staging quota is
  exhausted, fixtures + a recorded gap.

## Verification evidence expected

Commands, OpenAPI/prompt-hash confirmation, membership migration
round-trip, the S7 regression, live-check notes, adversarial-waived
statement, remaining gaps → `docs/deferred.md`.

## Risk tier & review focus

**Tier 3** — join table + public write shape + prompt bump. Standard
review (contract verifier, `/code-review`, `/security-review`,
`/simplify`, human deep review). Adversarial waived. Focus: tenancy on
membership writes, `source_count` honesty, prompt honesty for OECD,
SSE/run not torn down on PATCH.
