# Implementation plan: 033-ux-snags

> **Status:** Contract approved 2026-08-24 · owner. Plan approved 2026-08-24 ·
> owner (combined gate). ADR: 0032 (membership many-to-many).
>
> Terms and S1–S10 live in [contract.md](contract.md). This plan cites them.

## Context

032 shipped the lifecycle IA. Ten snags remain. Three of them are gated
(join table, public write shape, planner bump); the rest are frontend or
small additive API. One slice, one PR.

## Decisions

| # | Decision | Choice |
|---|---|---|
| **D1** | Membership write shape | Replace-all `PATCH {portfolio_ids}`. Omit = unchanged, `[]` = unassign all. The Share UI always has the full list, so add/remove is a new full set. No extra membership routes. |
| **D2** | Share lock | Share is open from task creation. Assignment is about the task, not the run. Sharing copy stays coming-soon. |
| **D3** | Round labelling | Flatten `round_index` onto SSE summary. Frontend keeps every acquire/screen SSE entry. Ingest (`ingest_full_text` → public `acquire`) is labelled from missing `round_index` / registry, not as Searching. Focused stays unnumbered. |
| **D4** | Quote context | Additive `chunk_id` on `FindingOut`; lazy `GET .../chunks/{id}/context`. Do not embed context on the list payload. |
| **D5** | OECD | Planner default only, plus Plan-document copy. No silent screening criterion. No frontend-only default that can disagree with the chat. |
| **D6** | Review | Standard stack, adversarial waived (032). Codex not on PATH. |
| **D7** | Executor | Lead for S10 and membership semantics. Rest of the build is this conversation (Codex CLI absent). |

## Gates

Three full `make verify` runs:

| # | When | Class |
|---|---|---|
| 1 | Phase 0 | build-open baseline |
| 2 | End of Phase 1 | schema / public API |
| 3 | End of Phase 7 | step-6 exit |

Phases 2–3 (backend, no new table): `make verify-fast` plus `make drift-check`
after OpenAPI regen. Phases 4–6 (frontend / prompt+frontend): Phase 4 also
needs `prompt-guard` green; frontend phases gate on `make frontend-verify`.

## Phases

Each phase ends in a commit on `task/033-ux-snags`.

### Phase 0 — Baseline

`make verify` on the branch. Record the test count.

**Gate:** full `make verify`.

### Phase 1 — Schema + membership API + S1 count

1. Table `portfolio_membership`. Copy `project.portfolio_id` into it. Drop
   the column and FK.
2. `ProjectOut.portfolio_ids`. PATCH replace-all. `task_count` from the join.
3. `source_count` = count of effective screens with status `relevant`.
4. Spec `web-api.md`. Tests: migrate round-trip; two memberships; unassign;
   cross-owner 404; S1 null/zero/included.
5. `make openapi-sync`.

**Gate:** full `make verify`.

### Phase 2 — S7 lock + regression

PATCH name / `portfolio_ids` already `FOR UPDATE` the project row. Confirm
event append happens in that transaction. Regression: PATCH while a walk is
running → 200, status unchanged. Frontend: project-query invalidation must
not reset the SSE store.

**Gate:** `make verify-fast`.

### Phase 3 — S9 `chunk_id`

Nullable `chunk_id` on the finding read shape from the first grounding
anchor. OpenAPI regen. Abstract-only stays null.

**Gate:** `make verify-fast` + `make drift-check`.

### Phase 4 — S10 `planner_v9`

Lead. Default `country_group` to `"OECD members"` unless the user asked
otherwise or cleared it. Say so in `reply` + scope chip. Relabel Plan
document. Hash pin + planner replay.

**Gate:** `make verify-fast` (includes prompt-guard) + `make frontend-verify`
for the copy change.

### Phase 5 — Frontend S2 S4 S5 S6 S8

BETA chip; empty-account redirect; round rows; queries section; findings
pager + one `setSearchParams`. Flatten `round_index` in SSE if not done in
Phase 1.

**Gate:** `make frontend-verify`.

### Phase 6 — Share membership UI + mock `/portfolios`

List, add, remove. Unlock Share. Mock portfolios + membership.

**Gate:** `make frontend-verify`.

### Phase 7 — Step-6

`verification.md`. Full `make verify`. `make frontend-verify`. Playwright
mock journey if the Share/empty-account paths are in it.

**Gate:** full `make verify`.

## Executor summary

Lead: Phase 4 prompt, Phase 1 membership semantics, adjudication. Mechanical
edits in this conversation (Codex absent).
