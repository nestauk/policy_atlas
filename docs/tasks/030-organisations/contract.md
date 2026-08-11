# Task contract: 030-organisations

> **Status:** drafted 2026-08-11 (rev 1); **rev 1.1, 2026-08-11 (owner):** no separate
> "org" scope — the user is part of the org, so the org view IS the full visible list;
> `scope=all|mine`, two-state frontend switcher. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: 0030 (to be drafted with the plan).
>
> Owner calls taken at the design interview (2026-08-11), encoded below:
> **(a)** membership is **app-owned and ops-assigned** (new tables; no Cognito/IdP changes);
> **(b)** org access = **read everything + own chats** (all other mutations stay owner-only);
> **(c)** per-project **`visibility` flag, default `org`**;
> **(d)** **no enrolment backfill** — orgs start empty; existing projects stay personal-only
> until assigned via the ops tooling (dark launch).

## Goal

Users belong to an organisation. A signed-in user sees, by default, both their own
projects and their organisation's org-visible projects, and can switch between the two in
the frontend. Org-visible projects are readable end-to-end by org colleagues, who can also
hold their **own** chat conversations on them; every mutating action (rename, archive,
runs, planning turns, steering, visibility) remains the owner's alone.

## Deliverable

One PR landing: `organisation` + `app_user` tables and the project `org_id`/`visibility`
columns (additive Alembic migration off 029's head), org-aware authorization on every
project-scoped route, `GET /api/v1/me`, the projects `scope` filter, chat ownership
(`conversation.created_by`), ops tooling (CLI + make targets) for org create / user
enrolment / project assignment, the frontend switcher + read-only affordances + identity
chip, spec flow-back to `web-api.md`, ADR 0030, and `verification.md` with the scoped live
check.

## Read first

- [web-api.md](../../specs/system/web-api.md) — § Auth boundary (the BOLA 404 rule and the
  **pre-reserved 403** "for future role failures within an owned scope" — this slice is
  that future), § Projects, § Conversations (029 surface, unmerged — read on this branch).
- [data-model.md](../../specs/system/data-model.md) — § Entity hierarchy (tenancy sits
  *above* it; nothing inside the project hierarchy changes).
- `docs/deferred.md` — "NULL-owner pre-025 projects" (posture stands: NOT adopted),
  "Concurrent-run write guard" (one-active-run-per-project is already the per-project
  invariant; org read access adds no second writer), 029 seams section.
- Current code: `api/auth.py` (claims: `sub` only — no email/groups/org in Cognito access
  tokens), `api/routers/_common.py` `owned_project()`, the six inline ownership joins in
  029's `conversations.py`/`chat_turns.py`, `infra/infra/cognito_auth.py` (feature-free
  pool — membership cannot come from the IdP as configured).

## Scope / Out of scope

**In:**

1. **Schema (approval-gated · additive migration chained off 029's head `d8e4a1c7f2b9`):**
   - `organisation` — `org_id` UUID PK · `name` Text NOT NULL UNIQUE · `created_at`.
   - `app_user` — `user_id` Text PK (the token `sub`, the grain the system already keys
     on) · `org_id` FK → organisation **nullable** · `display_name` Text nullable
     (ops-set; access tokens carry no usable name claim) · `created_at`. **One org per
     user** — multi-org membership is a deferred join-table seam.
   - `project` — add `org_id` FK nullable + `visibility` Text NOT NULL DEFAULT `'org'`
     CHECK (`org`|`private`); listing indexes for the two access legs
     (owner leg; `(org_id, visibility, status)` leg).
   - `conversation` — add `created_by` Text nullable, **backfilled from the owning
     project's `owner_user_id`** (deterministic: only owners could create conversations
     before this slice; rows under NULL-owner projects stay NULL and unreachable). The
     only data-touching migration step.
   - No enrolment backfill. `runtime/orchestrate.py` CLI projects keep
     `owner_user_id=NULL`, `org_id=NULL` — unchanged posture.
2. **User provisioning:** `app_user` row upserted (`ON CONFLICT DO NOTHING`) at
   `GET /api/v1/me` and by ops enrolment — **no DB writes in the auth dependency**;
   `get_current_user` stays DB-free.
3. **Authorization:** `owned_project()` generalises to one access helper with two grades —
   **read** = owner ∪ (same org ∧ `visibility='org'` ∧ project not archived-hidden rules
   unchanged) · **write** = owner only. Not-visible → **404** (BOLA rule unchanged,
   indistinguishable body); visible-but-not-writable → **403 `forbidden`** (new error
   code — the reserved hook fires; existing ~20 cross-owner 404 tests stand, cross-owner
   ≠ same-org). All 12 read-model routes, SSE snapshot, runs/planning/check-ins GETs go
   through the read grade; every mutation through write. **029's six inline ownership
   joins consolidate onto the same helper** (in-scope refactor, plan names each site).
4. **Chats on org projects:** org members create and read **their own** conversations
   (`created_by = sub`); chat listings filter to own chats (owner's legacy NULL rows
   resolve to the owner). Planning conversations: readable with the project, writable by
   owner only. Chat-turn POST/cancel allowed only on own conversations. The
   `_OWNER_PENDING_CAP` pending-turn count **re-keys to the acting user** (via
   `created_by`), not the project owner — one user's in-flight turns never throttle a
   colleague.
5. **API (approval-gated · additive):** `GET /api/v1/me` →
   `{user_id, display_name, organisation: {org_id, name} | null}` ·
   `GET /projects?scope=all|mine` (default `all` = everything visible to the caller —
   own projects incl. private, plus org-visible colleagues' projects; the user is part
   of the org, so there is no separate "org" scope — owner call, rev 1.1) ·
   `ProjectOut` gains `visibility`, `is_owner`, `owner_display` ·
   `PATCH /projects/{id}` accepts `visibility` (owner-only) · error envelope gains
   403 `forbidden`. `make openapi-sync` regenerates the two generated files.
6. **Ops tooling:** small `policy_atlas.ops` CLI + make targets — create org · enrol user
   (upsert `app_user`, set `org_id`, optional `display_name`) · assign project to org ·
   de-enrol (the rollback lever). Prod invocation documented in DEPLOYMENT.md (same
   pattern as migrations; no new infra).
7. **Frontend:** two-state landing switcher **Organisation · Mine** (default
   Organisation = the full visible list; Mine = owned-by-me filter; labels per the
   just-enough-text principle) ·
   org cards show `owner_display` · `is_owner=false` hides rename/archive/planning
   composer/run/steering controls (read-only affordances) and shows only own chats ·
   visibility toggle in project settings (owner only) · identity chip renders
   `display_name` (fallback: current sub rendering) via `/me` · mock API mirrors the
   scope/403 behaviour.
8. **Spec flow-back (ships with the slice):** `web-api.md` § Auth boundary (org read
   grade, 403 semantics, `/me`, scope param) + a tenancy note above data-model's entity
   hierarchy. Deferred seams recorded in `docs/deferred.md`.

**Out (⏸ deferred, recorded, not silently omitted):**

- Roles beyond owner/org-member (admin, editor); any org-management **UI** — ops CLI only.
- Self-serve onboarding: invitations, email-domain mapping, IdP claims/groups/federation.
- Multi-org membership; project ownership transfer; sharing to named individuals.
- Write/co-edit on org projects beyond own chats (incl. steering by non-owners).
- Seeing colleagues' chats (owner moderation view); org-level run/chat capacity policy.
- Adoption of NULL-owner pre-025 projects (recorded posture stands).
- Workspace-cluster IA, hard purge, cursor pagination — their own recorded seams.
- The `project_out()` per-row `latest_run` N+1 — noted, bounded by the page cap; recorded
  as a seam, not fixed here.

## Constraints & approval gates

This slice **is** the approval: schema (three tables touched + one new), auth/tenancy
semantics, public API additions — all named above; nothing beyond them. No new
dependencies. No egress change (no new product egress; `/me` and ops CLI are DB-only).
No CI change. Migration is additive; downgrade drops the additions (and `created_by`).
**Sequencing pin:** 030's build opens only after 029 merges to `dev`; this branch follows
the stacked-squash-merge playbook at that point. Generated files only via
`make openapi-sync`.

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
is indistinguishable 404, visible-unwritable is 403, and tests pin both directions.

## Stop conditions

Template set, plus: any temptation to widen into roles/admin UI, IdP changes, or write
access on org projects halts and escalates — those are recorded Out items.

## Acceptance checks

- `make verify` green; `make drift-check` green after `openapi-sync`.
- Deterministic tests (no AI eval — no LLM surface): migration roundtrip on the scratch-DB
  pattern (029's `test_migrations_029.py` as template) incl. `created_by` backfill; tenancy
  matrix — same-org read 200 / write 403 / cross-org 404 / `visibility='private'` hides
  from org / scope filter correctness / own-chats isolation (colleague's chat invisible,
  turn POST on it 404s) / pending-cap keyed to acting user / `/me` JIT upsert idempotency;
  existing cross-owner 404 suite untouched and green.
- **Live check (contract-time scope pin):** on staging — enrol two users into one org via
  the ops CLI; verify: org project visible to colleague (read-only affordances render),
  private project hidden, colleague opens own chat on org project + owner cannot see it,
  rename attempt by colleague → 403, switcher filters correctly, identity chip shows
  ops-set display name. Plus one cheap full-chain smoke (an existing personal project
  still loads end-to-end). **Not** a full live e2e run.

## Verification evidence expected

`verification.md`: command outputs, the tenancy-matrix test names, migration
up/down evidence, live-check notes per the pin above, diff summary, public-safety
confirmation, known gaps.

## Risk tier & review focus

**Tier 4** — tenancy/auth semantics + schema migration on the live DB + public-API
additions (029 precedent). So: human-approved plan · ADR 0030 · rollback plan · security
lane + adversarial review at contract, plan and code · human deep review.

**Rollback plan:** the migration downgrades cleanly (drops additive tables/columns); the
feature dark-launches — with no orgs created, behaviour is byte-identical to today, and
**de-enrolment** (ops CLI) reverts any org to pure per-owner behaviour without a deploy.

**Review focus:** the tenancy boundary (org A ↛ org B; private ↛ org; the six consolidated
join sites — none left behind), 403-vs-404 discipline, no auth-path DB writes, migration
safety on live data, no scope creep into roles/UI/IdP.
