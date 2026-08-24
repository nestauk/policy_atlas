# Task contract: 033-organisations

> **Status:** drafted 2026-08-11 (rev 1) · **rev 2.0, 2026-08-24 — re-opened and
> de-collided.** The slice sat in design while 031 and 032 merged (134 commits on `dev`).
> Renumbered **030 → 033** (three merged tasks already hold 030); **ADR 0030 → 0032**
> (0030 = SSM jumpbox, 0031 = the portfolio layer). Contract approved (before planning):
> _pending_ · Plan approved (before implementation): _pending_ · ADR: 0032.
>
> **Vocabulary (032, ADR 0031 — read before every noun below).** Screen word **Task** =
> the code row `project`. Screen word **Project** = the code row `portfolio`. This
> contract uses **code words** throughout; every user-facing string it specifies is
> given in screen words and marked as such. Resolving the split is not this slice's job
> — it stays with the workspace-cluster slice.
>
> Owner calls taken at the design interview (2026-08-11), unchanged, encoded below:
> **(a)** membership is **app-owned and ops-assigned** (new tables; no Cognito/IdP changes);
> **(b)** org access = **read everything + own chats** (all other mutations stay owner-only);
> **(c)** per-`project` **`visibility` flag, default `org`**;
> **(d)** **no enrolment backfill** — orgs start empty; existing rows stay personal-only
> until assigned via the ops tooling (dark launch).
>
> Owner call taken at re-open (2026-08-24):
> **(e)** **`portfolio` takes the same tenancy grades as `project`** — its own `org_id`
> and `visibility` columns, and `owned_portfolio()` folds into the same access helper.
> Without it a colleague would see shared Tasks while the Project that groups them stayed
> invisible.

## Goal

Users belong to an organisation. A signed-in user sees, by default, both their own work
and their organisation's org-visible work — `project` rows and the `portfolio` rows that
group them — and can switch between the two in the frontend. Org-visible rows are readable
end-to-end by org colleagues, who can also hold their **own** chat conversations on them;
every mutating action (rename, archive, runs, planning turns, steering, visibility,
portfolio membership) remains the owner's alone.

## Deliverable

One PR landing: `organisation` + `app_user` tables, `org_id`/`visibility` columns on both
`project` and `portfolio` (additive Alembic migration off 032's head `b3c7d914e0a2`),
org-aware authorization on every project- and portfolio-scoped route, `GET /api/v1/me`,
the `scope` filter on the `projects` and `portfolios` listings, chat ownership
(`conversation.created_by`), ops tooling (CLI + make targets) for org create / user
enrolment / row assignment, the frontend switcher + read-only affordances + identity chip,
spec flow-back to `web-api.md`, ADR 0032, and `verification.md` with the scoped live check.

## Read first

- [web-api.md](../../specs/system/web-api.md) — § Auth boundary (the BOLA 404 rule and the
  **pre-reserved 403** "for future role failures within an owned scope" — this slice is
  that future; the reservation survived 029, 031 and 032 intact), § Projects,
  § Portfolios, § Conversations.
- [data-model.md](../../specs/system/data-model.md) — § Entity hierarchy (tenancy sits
  *above* it; nothing inside the hierarchy changes).
- [ADR 0031](../../adr/0031-portfolio-layer-above-the-project.md) — the portfolio layer and
  the code-word/screen-word split this contract inherits.
- [032's contract](../032-task-lifecycle-ia/contract.md) and its seams block in
  `docs/deferred.md` § Task lifecycle IA — in particular the recorded gap that
  `src/mock/api.ts` serves no `/api/v1/portfolios`.
- `docs/deferred.md` — "NULL-owner pre-025 projects" (posture stands: NOT adopted),
  "Concurrent-run write guard", 029 and 032 seams sections.
- Current code: `api/auth.py` (claims: `sub` only — no email/groups/org in Cognito access
  tokens), `api/routers/_common.py` `owned_project()` **and `owned_portfolio()`**,
  `api/routers/portfolios.py` (032's four routes), the inline ownership joins in
  `conversations.py`/`chat_turns.py`, `infra/infra/cognito_auth.py` (feature-free pool —
  membership cannot come from the IdP as configured).

## Scope / Out of scope

**In:**

1. **Schema (approval-gated · additive migration chained off 032's head `b3c7d914e0a2`):**
   - `organisation` — `org_id` UUID PK · `name` Text NOT NULL UNIQUE · `created_at`.
   - `app_user` — `user_id` Text PK (the token `sub`, the grain the system already keys
     on) · `org_id` FK → organisation **nullable** · `display_name` Text nullable
     (ops-set; access tokens carry no usable name claim) · `created_at`. **One org per
     user** — multi-org membership is a deferred join-table seam.
   - `project` — add `org_id` FK nullable + `visibility` Text NOT NULL DEFAULT `'org'`
     CHECK (`org`|`private`); listing indexes for the two access legs
     (owner leg; `(org_id, visibility, status)` leg).
   - `portfolio` — the same two columns and the same CHECK (owner call (e)); listing index
     for the org leg. `portfolio` has no `status` column (032 deferred its soft-delete),
     so its org leg is `(org_id, visibility)`.
   - `conversation` — add `created_by` Text nullable, **backfilled from the owning
     `project`'s `owner_user_id`** (deterministic: only owners could create conversations
     before this slice; rows under NULL-owner projects stay NULL and unreachable). The
     only data-touching migration step. 032's conversation constraints (status,
     `archived_at`, the one-active-planning partial index) are untouched by the backfill.
   - No enrolment backfill. `runtime/orchestrate.py` CLI projects keep
     `owner_user_id=NULL`, `org_id=NULL` — unchanged posture.
2. **User provisioning:** `app_user` row upserted (`ON CONFLICT DO NOTHING`) at
   `GET /api/v1/me` and by ops enrolment — **no DB writes in the auth dependency**;
   `get_current_user` stays DB-free.
3. **Authorization:** `owned_project()` **and `owned_portfolio()`** generalise onto one
   access helper with two grades — **read** = owner ∪ (same org ∧ `visibility='org'` ∧
   existing archived/status rules unchanged) · **write** = owner only. Not-visible →
   **404** (BOLA rule unchanged, indistinguishable body); visible-but-not-writable →
   **403 `forbidden`** (new error code — the reserved hook fires; the existing cross-owner
   404 suite stands, cross-owner ≠ same-org). **Every** project- and portfolio-scoped
   route goes through the helper: read models, SSE snapshot, runs, planning, check-ins,
   conversations, and 032's portfolio routes. **The remaining inline ownership joins in
   `conversations.py`/`chat_turns.py` consolidate onto the same helper** (in-scope
   refactor). The plan **enumerates the call sites from the code as it stands at plan
   time** — rev 1's fixed counts ("12 read models", "×6 inline sites") predate 031 and 032
   and are deliberately not restated here.
4. **Chats on org projects:** org members create and read **their own** conversations
   (`created_by = sub`); chat listings filter to own chats (owner's legacy NULL rows
   resolve to the owner). Planning conversations: readable with the project, writable by
   owner only. Chat-turn POST/cancel allowed only on own conversations. The
   `_OWNER_PENDING_CAP` pending-turn count **re-keys to the acting user** (via
   `created_by`), not the project owner — one user's in-flight turns never throttle a
   colleague.
5. **API (approval-gated · additive):** `GET /api/v1/me` →
   `{user_id, display_name, organisation: {org_id, name} | null}` ·
   `GET /projects?scope=all|mine` **and `GET /portfolios?scope=all|mine`** (default `all`
   = everything visible to the caller — own rows incl. private, plus org-visible
   colleagues' rows; the user is part of the org, so there is no separate "org" scope —
   owner call, rev 1.1) · `ProjectOut` **and `PortfolioOut`** gain `visibility`,
   `is_owner`, `owner_display` · `PATCH /projects/{id}` **and `PATCH /portfolios/{id}`**
   accept `visibility` (owner-only) · error envelope gains 403 `forbidden`.
   `make openapi-sync` regenerates the two generated files.
   **Portfolio task counts** (`portfolios.py` `_task_counts`) count only rows the caller
   can read — a colleague must not learn a private task exists from a count.
6. **Ops tooling:** small `policy_atlas.ops` CLI + make targets — create org · enrol user
   (upsert `app_user`, set `org_id`, optional `display_name`) · assign a `project` **or
   `portfolio`** to an org · de-enrol (the rollback lever). Prod invocation documented in
   DEPLOYMENT.md (same pattern as migrations; no new infra).
7. **Frontend (surfaces named as they stand after 032):** two-state switcher, screen
   labels **Organisation · Mine** (default Organisation = the full visible list; Mine =
   owned-by-me filter; labels per the just-enough-text principle), on
   `views/TasksListView.tsx` (`/`, the Tasks list) and `views/PortfoliosView.tsx`
   (`/portfolios`, the Projects list) · rows and cards show `owner_display`
   (`TaskListRow.tsx`, `TaskListPanel.tsx`, `PortfoliosView.tsx`) · `is_owner=false` hides
   rename/archive/planning composer/run/steering controls and shows only own chats
   (`workspace/chat/ChatsLibrary.tsx`) · **the lifecycle bar and `LifecycleRoute` stage
   gating render read-only for a non-owner** — a locked or owner-only stage must be
   unreachable by URL as well as by click, matching 032's existing gating rule ·
   `HistoryView.tsx` scopes to the caller · visibility toggle in Task and Project settings
   (owner only) · identity chip renders `display_name` (fallback: current sub rendering)
   via `/me`.
   **Mock API:** `src/mock/api.ts` mirrors the scope/403 behaviour for `/projects`. It
   serves no `/api/v1/portfolios` at all (032's recorded seam), so portfolio scope/403
   behaviour is covered by backend route tests and frontend unit tests only. Extending
   the mock fixture is **Out** — recorded, not silently skipped.
8. **Spec flow-back (ships with the slice):** `web-api.md` § Auth boundary (org read
   grade, 403 semantics, `/me`, scope param on both listings) + a tenancy note above
   data-model's entity hierarchy. Deferred seams recorded in `docs/deferred.md`.

**Out (⏸ deferred, recorded, not silently omitted):**

- Roles beyond owner/org-member (admin, editor); any org-management **UI** — ops CLI only.
- Self-serve onboarding: invitations, email-domain mapping, IdP claims/groups/federation.
- Multi-org membership; ownership transfer; sharing to named individuals.
- Write/co-edit on org-visible rows beyond own chats (incl. steering by non-owners).
- Seeing colleagues' chats (owner moderation view); org-level run/chat capacity policy.
- Adoption of NULL-owner pre-025 projects (recorded posture stands).
- **Extending `src/mock/api.ts` to serve `/api/v1/portfolios`** — 032's seam; this slice
  inherits the gap rather than closing it.
- **Resolving the code-word/screen-word split** (ADR 0031) — stays with the
  workspace-cluster slice; this contract works in code words.
- **A `portfolio` whose visibility disagrees with its tasks'** — no cascade, no
  validation: a private task inside an org-visible portfolio simply stays hidden and
  uncounted. Cascade rules are a seam.
- Workspace-cluster IA, hard purge, cursor pagination — their own recorded seams.
- The `project_out()` per-row `latest_run` N+1 — noted, bounded by the page cap; recorded
  as a seam, not fixed here.

## Constraints & approval gates

This slice **is** the approval: schema (two new tables, two tables gaining columns, one
gaining a backfilled column), auth/tenancy semantics, public API additions — all named
above; nothing beyond them. No new dependencies. No egress change (`/me` and ops CLI are
DB-only). No CI change. Migration is additive; downgrade drops the additions (and
`created_by`). **Sequencing pin — re-derived 2026-08-24:** 029, 031 and 032 are all merged
to `dev` (head `b8729a5`); this branch is cut fresh from merged `dev`, and
**`b3c7d914e0a2` (032's portfolio layer) is confirmed the sole alembic head** this slice
chains off. Generated files only via `make openapi-sync`.

## Public / private boundary

All committed artefacts are public-safe (public AGPL repo): no real user identifiers in
fixtures/tests (synthetic subs per the `resource_support.py` pattern), no staging org/user
names in committed docs, secrets/IP allowlists never committed (standing rule).

## Model route

n/a — no LLM-bearing step. `chat_v1` and all prompt surfaces are untouched; chats gain an
owner column, not new behaviour.

## Disciplines binding this slice

Template set, plus: **model only what behaves** — no roles column, no org settings bag, no
`is_admin` flag ships without a v3.0 reader; **the 404/403 line is contract** — not-visible
is indistinguishable 404, visible-unwritable is 403, and tests pin both directions;
**counts leak too** — a number derived from rows the caller cannot read is a disclosure.

## Stop conditions

Template set, plus: any temptation to widen into roles/admin UI, IdP changes, write access
on org rows, or resolving the 032 vocabulary split halts and escalates — those are recorded
Out items.

## Acceptance checks

- `make verify` green; `make drift-check` green after `openapi-sync`.
- Deterministic tests (no AI eval — no LLM surface): migration roundtrip on the scratch-DB
  pattern (029's `test_migrations_029.py` as template) incl. `created_by` backfill; tenancy
  matrix — same-org read 200 / write 403 / cross-org 404 / `visibility='private'` hides
  from org / scope filter correctness on **both** listings / portfolio task counts exclude
  unreadable tasks / own-chats isolation (colleague's chat invisible, turn POST on it
  404s) / pending-cap keyed to acting user / `/me` JIT upsert idempotency; the existing
  cross-owner 404 suite untouched and green (it now spans ten API test files including
  `test_portfolios_router.py` — the plan enumerates them from the tree, not from this
  contract).
- **Live check (contract-time scope pin):** on staging — enrol two users into one org via
  the ops CLI; verify: org-visible Task **and** the Project grouping it visible to the
  colleague (read-only affordances render, lifecycle stages gated), private Task hidden
  and uncounted, colleague opens own chat on an org Task + owner cannot see it, rename
  attempt by colleague → 403, both switchers filter correctly, identity chip shows the
  ops-set display name. Plus one cheap full-chain smoke (an existing personal Task still
  loads end-to-end). **Not** a full live e2e run.
  *Known constraint:* staging's OpenAI quota was recorded exhausted; the live check is
  tenancy-only and needs no model route, but the full-chain smoke does — if the quota is
  still out, record that as a gap rather than skipping it silently.

## Verification evidence expected

`verification.md`: command outputs, the tenancy-matrix test names, migration
up/down evidence, live-check notes per the pin above, diff summary, public-safety
confirmation, known gaps.

## Risk tier & review focus

**Tier 4** — tenancy/auth semantics + schema migration on the live DB + public-API
additions (029 precedent). So: human-approved plan · ADR 0032 · rollback plan · security
lane + adversarial review at contract, plan and code · human deep review.

**Rollback plan:** the migration downgrades cleanly (drops additive tables/columns); the
feature dark-launches — with no orgs created, behaviour is byte-identical to today, and
**de-enrolment** (ops CLI) reverts any org to pure per-owner behaviour without a deploy.

**Review focus:** the tenancy boundary (org A ↛ org B; private ↛ org; every consolidated
join site — none left behind, on portfolios as well as projects), count-based disclosure,
403-vs-404 discipline, no auth-path DB writes, migration safety on live data, no scope
creep into roles/UI/IdP/vocabulary.
