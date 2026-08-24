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
> Owner calls taken at re-open (2026-08-24):
> **(e)** **`portfolio` takes the same tenancy grades as `project`** — its own `org_id`
> and `visibility` columns, and `owned_portfolio()` folds into the same access helper.
> Without it a colleague would see shared Tasks while the Project that groups them stayed
> invisible.
> **(f)** **An admin flag ships in this slice** — `app_user.is_admin`, ops-assigned,
> granting **read of every row in every organisation, `private` included**, so an admin
> can support any Task from the real UI. **Read only: it grants no write, ever.** It is
> deliberately the designated home for future admin capability (an admin dashboard hangs
> off this flag, not off a second boolean), but in this slice it grants exactly one thing,
> and that is what the tests pin. Because it sees private work, **disclosure is the
> control**: every admin read is traced, the privacy notice says so, and the word
> "private" in the UI is corrected to what it actually means (see § What `private` means).
>
> **(g)** **`app_user` stores the Cognito email, and admins can find work by it.** The
> access token carries `sub` only, so the email is fetched **once at ops enrolment** and
> stored. Enrolment is *by* email (an operator knows the address, not the UUID). Admins
> get an `owner_email` filter on the two listings — no user directory, no admin screen.
> This makes the application database hold directly identifiable personal data for the
> first time, so the privacy notice changes with it and de-enrolment clears the address.
>
> **(h)** **The ops CLI owns the whole account lifecycle** — it creates and deletes the
> Cognito user, not only reads it, so an operator never handles a pool ID or attribute
> names by hand. Delete is the highest-consequence command in the slice and is specified
> as such below: it never destroys work, and it is the erasure lever proper.
>
> **Sequencing note (owner, 2026-08-24):** the code/screen vocabulary split stays as
> ADR 0031 left it for this slice. A **standalone rename slice follows 033** — `project`
> → `task`, `portfolio` → `project`, mechanical, no behaviour change — and it will have to
> cover the code this slice adds. 033 therefore does not spend effort softening the split;
> it just states the mapping and works in code words.

## Goal

Users belong to an organisation. A signed-in user sees, by default, both their own work
and their organisation's org-visible work — `project` rows and the `portfolio` rows that
group them — and can switch between the two in the frontend. Org-visible rows are readable
end-to-end by org colleagues, who can also hold their **own** chat conversations on them;
every mutating action (rename, archive, runs, planning turns, steering, visibility,
portfolio membership) remains the owner's alone.

## Deliverable

One PR landing: `organisation` + `app_user` tables (the latter carrying the ops-only
`is_admin` flag), `org_id`/`visibility` columns on both
`project` and `portfolio` (additive Alembic migration off 032's head `b3c7d914e0a2`),
org-aware authorization on every project- and portfolio-scoped route (three read legs:
owner, same-org, admin), `GET /api/v1/me`,
the `scope` filter on the `projects` and `portfolios` listings, chat ownership
(`conversation.created_by`), ops tooling (CLI + make targets) for org create / user
enrolment / row assignment / admin grant, the frontend switcher + read-only
affordances + identity chip + the visibility and privacy-notice copy,
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
     (ops-set; access tokens carry no usable name claim) ·
     **`is_admin` Boolean NOT NULL DEFAULT `false`** (owner call (f)) ·
     **`email` Text nullable** (owner call (g); the Cognito address, resolved once at
     enrolment — never sent by a client, never read from a token) ·
     `created_at`. **One org per user** — multi-org membership is a deferred join-table
     seam.
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
   existing archived/status rules unchanged) ∪ (**`is_admin`** — any row, any org, any
   `visibility`) · **write** = owner only, in every case: an `is_admin` holder who is not
   the owner gets 403 on every mutation, exactly like an org colleague. The admin leg is
   the **only** place in this slice that reads `is_admin`; no mutation, no listing filter
   and no projection consults it. Not-visible →
   **404** (BOLA rule unchanged, indistinguishable body); visible-but-not-writable →
   **403 `forbidden`** (new error code — the reserved hook fires; the existing cross-owner
   404 suite stands, cross-owner ≠ same-org). **Every** project- and portfolio-scoped
   route goes through the helper: read models, SSE snapshot, runs, planning, check-ins,
   conversations, and 032's portfolio routes. **The remaining inline ownership joins in
   `conversations.py`/`chat_turns.py` consolidate onto the same helper** (in-scope
   refactor). The plan **enumerates the call sites from the code as it stands at plan
   time** — rev 1's fixed counts ("12 read models", "×6 inline sites") predate 031 and 032
   and are deliberately not restated here.
3a. **What `private` means (owner call (f)).** `is_admin` reads every row in every
   organisation, `visibility='private'` included. That makes `private` a promise about
   **colleagues**, not about the operator, so the product must stop implying otherwise —
   the control here is disclosure, not restriction:
   - **The UI word is corrected.** The visibility toggle says what it does — private
     hides a Task from your organisation — and does not suggest it is hidden from
     everyone. One label, no explainer paragraph (just-enough-text). Copy lands with the
     toggle in this slice, not later.
   - **The privacy notice says it — twice.** `views/legal/PrivacyView.tsx` § 6 "Who has
     access to your information?" gains one plain sentence: named administrators can
     access content in the service for support and maintenance, and those accesses are
     logged. **§ 3 "What personal data will we collect?" gains the email address**
     (owner call (g)): the application database has held only opaque identifiers until
     now, and storing the address makes it directly identifiable personal data. Both are
     legal-copy changes on a live public page — **owner sign-off before merge**, and
     neither may be written as if it were a routine string edit.
   - **Every admin read is traced.** One `structlog` line per read served by the admin leg
     (`event="admin_read"`, acting `user_id`, row kind and id, owning `org_id`), and none
     on a read the caller was entitled to anyway — an admin reading their own org must not
     generate noise, or the signal is worthless. JSON logs already ship to CloudWatch
     (`LOG_FORMAT=json`), so this needs no table and no new infra. **Not** `event_log`:
     that table is project-scoped and sequence-ordered per project, and writing to it on a
     read path would both pollute a run's audit stream and put a write inside a GET.

   The flag is granted only by the ops CLI, so there is no route, request body or
   self-serve path that can reach it.

3b. **How identity reaches the database (owner call (g)).** The only claim the API reads
   is `sub` ([`auth.py`](../../../backend/src/policy_atlas/api/auth.py) →
   `AuthenticatedUser.user_id`), and that stays true: `get_current_user` remains DB-free
   and Cognito-free. Everything else about a person is resolved **once, out of band, by
   the ops CLI**:
   - The pool is configured `UsernameAttributes: ["email"]`, so `cognito:username` is a
     generated UUID, **not** the address — there is nothing extra to harvest from a token.
     The address lives in the pool's `email` attribute, the ID token and userinfo, none of
     which the API sees.
   - **`sub` stays the key.** Emails change (a surname, a move between departments) and
     Cognito allows the attribute to be updated; `sub` never changes and is never reused.
     Keying on an address would silently detach a person's Tasks the day it changed.
   - **Enrolment is by email:** the operator runs `enrol --email jane@example.gov.uk`; the
     CLI resolves it to a `sub` via Cognito, then upserts `app_user`. If it resolves to no
     user or more than one, it **fails loudly and writes nothing** — a half-enrolled row
     is worse than none.
   - **`boto3`, in an ops-only dependency group (approval-gated; owner opened this
     2026-08-24).** The CLI calls `cognito-idp:ListUsers` through the SDK — typed
     exceptions, no argv, no stdout parsing, and **no command-construction site to
     review**. It goes in a new `[dependency-groups] ops` entry, **not** the runtime
     dependencies: `uv sync` installs default groups only and the image is built with
     `uv sync --no-dev --frozen` ([`backend/Dockerfile`](../../../backend/Dockerfile)), so
     a non-default group is excluded with **no Dockerfile change** and the ~100MB of
     `boto3`+`botocore` never reaches the API container. The rejected alternative was
     shelling out to the AWS CLI; it avoided the dependency but bought argv construction
     and stderr parsing in exchange, which is the worse trade.
   - **The operator's role needs `cognito-idp:ListUsers`, `AdminCreateUser` and
     `AdminDeleteUser`** (owner calls (g), (h)), documented alongside the existing jumpbox
     IAM guidance in `infra/JUMPBOX.md`.
   - **No new IAM on the API.** The permission to read the pool sits with the human
     operator's role, **never** with the API task role, and the import is reachable only
     from the CLI entry point — asserted structurally, so an API module cannot grow a
     `boto3` import unnoticed.
   - **Erasure lever:** de-enrolment clears `email` as well as `org_id`. It is the one
     command that removes the identifiable data this slice introduces.

3c. **Deleting a person (owner call (h)).** `user delete --email` removes the Cognito
   account so they can no longer sign in, and **clears `email` and `display_name`** from
   `app_user`. It is the erasure lever proper: the identifiable data goes, the row stays,
   keyed by an opaque `sub` that no longer resolves to a person.
   - **It never touches their work.** `project.owner_user_id` is plain text with no
     foreign key, so nothing cascades, and nothing is permitted to: a CLI flag must not be
     able to destroy research. Their Tasks and Projects remain, owned by a `sub` nobody
     holds — the same unreachable state the recorded "NULL-owner pre-025 projects" posture
     already accepts. Ownership transfer stays **Out**, so **there is no lever to give
     that work to somebody else**; deleting a person who owns live work strands it, and
     the command says so before it acts.
   - **It reports before it acts.** The command prints the address, the organisation, and
     the count of Tasks and Projects about to become unreachable, then requires the
     operator to retype the address to proceed. `--force` skips the prompt for scripted
     use. This is an irreversible cross-system action; a confirmation is not ceremony.
   - **Unknown address fails loudly and writes nothing** — in either system.
   - Delete is the erasure command; **de-enrol** remains the *reversible* lever that just
     removes org membership and the stored address.

4. **Chats on org projects:** org members create and read **their own** conversations
   (`created_by = sub`); chat listings filter to own chats (owner's legacy NULL rows
   resolve to the owner). Planning conversations: readable with the project, writable by
   owner only. Chat-turn POST/cancel allowed only on own conversations. The
   `_OWNER_PENDING_CAP` pending-turn count **re-keys to the acting user** (via
   `created_by`), not the project owner — one user's in-flight turns never throttle a
   colleague.
5. **API (approval-gated · additive):** `GET /api/v1/me` →
   `{user_id, display_name, email, organisation: {org_id, name} | null, is_admin: bool}`
   (the frontend needs it to label the wider list honestly — see § Frontend) ·
   `GET /projects?scope=all|mine` **and `GET /portfolios?scope=all|mine`** (default `all`
   = everything visible to the caller — own rows incl. private, plus org-visible
   colleagues' rows; the user is part of the org, so there is no separate "org" scope —
   owner call, rev 1.1) · `ProjectOut` **and `PortfolioOut`** gain `visibility`,
   `is_owner`, `owner_display` (`display_name` when set, else `email`, else the current
   `sub` rendering) · **`?owner_email=` on both listings, honoured only for `is_admin`
   holders — anyone else passing it gets 400 `invalid_parameter`, which reveals nothing
   about whether any address exists.** No user directory and no admin screen (Out) · `PATCH /projects/{id}` **and `PATCH /portfolios/{id}`**
   accept `visibility` (owner-only) · error envelope gains 403 `forbidden`.
   `make openapi-sync` regenerates the two generated files.
   **Portfolio task counts** (`portfolios.py` `_task_counts`) count only rows the caller
   can read — a colleague must not learn a private task exists from a count.
6. **Ops tooling:** small `policy_atlas.ops` CLI + make targets — create org ·
   **create user** (owner call (h): `user create --email --org [--display-name]` runs
   Cognito `AdminCreateUser` then enrols in one command; Cognito **must** go first because
   the `sub` it returns is the DB key. If the Cognito step succeeds and the database step
   fails, the CLI **does not** delete the just-created account — it fails loudly and prints
   the exact `user enrol` command that finishes the job. The stranded state is benign: a
   signed-in user with no org sees only their own work. An address that already exists in
   Cognito fails with "already exists — use `user enrol`", not a silent no-op.
   **No password ever passes through this codebase or this CLI:** `AdminCreateUser`
   accepts a `--temporary-password`, and the CLI deliberately does **not** expose one —
   supplying it would put a working credential in shell history and in CI logs if the
   command were scripted. Cognito generates the temporary password, emails it, and the
   user sets their own through the hosted UI's `NEW_PASSWORD_REQUIRED` challenge. Password
   reset is likewise self-serve via the pool's `verified_email` recovery; **no CLI command
   sets, resets or reads a password**) ·
   **delete user** (owner call (h) — see § Deleting a person) · enrol user
   **by email** (resolve `sub` via the AWS CLI, upsert `app_user`, set `org_id` and
   `email`, optional `display_name`) · assign a `project` **or
   `portfolio`** to an org · de-enrol (the rollback lever — **clears `email`**) ·
   **grant/revoke `is_admin`**
   (the only way to set it — there is no HTTP route that grants it, so the flag cannot be
   self-served or escalated to through the API). **Invocation is the operator's laptop over the SSM
   jumpbox tunnel** ([DEPLOYMENT.md § 6](../../../infra/DEPLOYMENT.md)), **not** the ECS
   migration-task pattern: the CLI needs Cognito read, and that permission must sit with
   the human operator's role rather than with any task role in the account. No new infra;
   documented in DEPLOYMENT.md alongside the existing developer DB access.
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
   **The account menu says who you are signed in as** (`AppShell.tsx` `AccountMenu`, the
   avatar popover that today holds only Sign out): the signed-in **email** and the
   **organisation name**, above a divider, with Sign out beneath. Values only — no
   "Signed in as" preamble; the account icon is the label (just-enough-text). An
   unenrolled user shows the email alone, with no empty row and no "No organisation"
   filler. An `is_admin` holder's menu also names that, because this is the honest place
   to tell someone their sight is wider than normal. The popover is `w-44` today and an
   address will not fit: widen it and truncate the email with its full value in `title`,
   so a long address degrades rather than breaking the layout. Both values come from
   `/me`, so **the mock API must serve `/me`** or the menu is unrenderable in mock mode
   and in the CI mock journey.
   **`is_admin` holders:** the Organisation switch shows the everything list, and the
   surface **says so plainly** — an admin must never mistake another org's work for their
   own org's. One label, not a banner or an explainer (just-enough-text). Rows outside the
   holder's own org show the owning organisation's name. Every read-only affordance rule
   above applies unchanged, since the holder is not the owner.
   **Visibility-toggle copy and the privacy-notice sentence ship here too** (§ What
   `private` means) — the privacy page edit is owner-signed before merge.
   **Mock API:** `src/mock/api.ts` mirrors the scope/403 behaviour for `/projects`. It
   serves no `/api/v1/portfolios` at all (032's recorded seam), so portfolio scope/403
   behaviour is covered by backend route tests and frontend unit tests only. Extending
   the mock fixture is **Out** — recorded, not silently skipped.
8. **Spec flow-back (ships with the slice):** `web-api.md` § Auth boundary (org read
   grade, 403 semantics, `/me`, scope param on both listings) + a tenancy note above
   data-model's entity hierarchy. Deferred seams recorded in `docs/deferred.md`.

**Out (⏸ deferred, recorded, not silently omitted):**

- **A role system** — per-org roles, editor/viewer grades, org admins, delegation, any
  org-management **UI**. `is_admin` (owner call (f)) is one global ops-set boolean, not
  the first row of a permissions table; the day roles need to vary per organisation, that
  is a roles slice and this flag folds into it.
- **Admin write of any kind** — archive, delete, rename, reassign ownership, run on
  someone's behalf, impersonation. `is_admin` is a read grade (owner call (f)); every
  mutation 403s for a non-owner holder exactly as it does for an org colleague.
- **An admin dashboard or any admin surface** — the flag is the designated home for one
  when it is built, and that slice adds the surface. This slice ships no admin screen:
  an admin sees the ordinary product, wider.
- **A user directory** — `?owner_email=` filters *work* by its owner's address (owner call
  (g)). There is no route that lists users, searches them by partial address, or reports
  whether an address is enrolled. An admin who wants to know "who is in this org" reads
  it off the work, or asks the ops CLI.
- **Keeping `email` in step with Cognito** — it is resolved once at enrolment and never
  re-synced, so an address changed in Cognito afterwards goes stale in the app until an
  operator re-enrols. `sub` is the key precisely so that staleness is cosmetic, never a
  correctness or access problem. A re-sync command is a seam, not a gap.
- Self-serve onboarding: invitations, email-domain mapping, IdP claims/groups/federation.
- Multi-org membership; **ownership transfer**; sharing to named individuals. Transfer's
  absence is now load-bearing: `user delete` (owner call (h)) strands whatever the deleted
  person owned, and nothing in this slice can hand it to a colleague. The first operator
  who needs to delete someone with live work is the trigger for a transfer slice.
- Write/co-edit on org-visible rows beyond own chats (incl. steering by non-owners).
- Seeing colleagues' chats (owner moderation view); org-level run/chat capacity policy.
- Adoption of NULL-owner pre-025 projects (recorded posture stands).
- **Extending `src/mock/api.ts` to serve `/api/v1/portfolios`** — 032's seam; this slice
  inherits the gap rather than closing it.
- **Resolving the code-word/screen-word split** (ADR 0031) — its **own rename slice,
  scheduled after 033** (owner, 2026-08-24): `project` → `task`, `portfolio` → `project`,
  mechanical, no behaviour change, and it must also cover the code this slice adds. This
  contract works in code words and does nothing to soften the split.
- **A `portfolio` whose visibility disagrees with its tasks'** — no cascade, no
  validation: a private task inside an org-visible portfolio simply stays hidden and
  uncounted. Cascade rules are a seam.
- Workspace-cluster IA, hard purge, cursor pagination — their own recorded seams.
- The `project_out()` per-row `latest_run` N+1 — noted, bounded by the page cap; recorded
  as a seam, not fixed here.

## Constraints & approval gates

This slice **is** the approval: schema (two new tables, two tables gaining columns, one
gaining a backfilled column), auth/tenancy semantics, public API additions — all named
above; nothing beyond them. **One new dependency, approval-gated and named: `boto3`, in a
new ops-only dependency group** (owner opened this 2026-08-24) — excluded from the API
image by the existing `uv sync --no-dev --frozen` build, so the runtime is unchanged.
**Egress change, named and bounded:** the ops CLI gains one outbound Cognito call, made by
a human operator under their own IAM. **The API's egress is unchanged** — `/me` and every
request path stay DB-only, and the API task role gains no Cognito permission. No CI change. Migration is additive; downgrade drops the additions (and
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
  404s) / pending-cap keyed to acting user / `/me` JIT upsert idempotency /
  **`is_admin`: reads an org-visible row in a foreign org 200 · reads a
  `visibility='private'` row in a foreign org 200 · is refused every mutation 403 ·
  defaults `false` so the dark-launch invariant is untouched · emits exactly one trace
  line per admin-leg read and none on a read the caller was already entitled to · no
  mutation, listing filter or projection reads the flag (asserted structurally, not only
  behaviourally — the name invites drift)** / **owner call (g): enrolment by email
  resolves and stores the address · an email matching no user, or more than one, fails
  loudly and writes nothing · `?owner_email=` returns an admin the right rows · a
  non-admin passing `owner_email` gets 400 regardless of whether the address exists (no
  oracle) · de-enrolment clears `email` · `owner_display` falls back
  `display_name` → `email` → `sub` · the Cognito call is absent from every request path
  (asserted structurally: the API imports nothing that reaches Cognito)** / **owner call
  (h): `user create` creates then enrols · a Cognito-succeeded/DB-failed create leaves the
  account and prints the `user enrol` remediation rather than deleting it · an existing
  address fails with "use enrol" · `user delete` clears `email` and `display_name`, removes
  the Cognito account, and **leaves every owned row untouched** (pinned by a test that
  counts the owner's projects before and after) · delete on an unknown address writes to
  neither system · `--force` is the only way to skip the retype confirmation** / **the account
  menu renders email + organisation from `/me`, shows the email alone when unenrolled, and
  names admin state when `is_admin`**; the existing
  cross-owner 404 suite untouched and green (it now spans ten API test files including
  `test_portfolios_router.py` — the plan enumerates them from the tree, not from this
  contract).
- **Live check (contract-time scope pin):** on staging — enrol two users into one org via
  the ops CLI; verify: org-visible Task **and** the Project grouping it visible to the
  colleague (read-only affordances render, lifecycle stages gated), private Task hidden
  and uncounted, colleague opens own chat on an org Task + owner cannot see it, rename
  attempt by colleague → 403, both switchers filter correctly, identity chip shows the
  ops-set display name — **enrolling both users by email address, not by `sub`**. **Then grant `is_admin` to a third user in neither org and verify:
  they browse both the org-visible Task and the private one, the owning organisation is
  named on screen, a rename attempt returns 403, and one trace line per admin read appears
  in CloudWatch with none for their own-org reads. Revoke, and confirm the wider list
  disappears. Check that `?owner_email=` finds a colleague's Task for the admin and 400s
  for a non-admin, and that the corrected visibility-toggle copy and **both** privacy-notice
  changes (§ 3 and § 6) render on the live pages. Open the account menu as each of the
  three users and confirm it names the right email, organisation and admin state. Finally
  round-trip owner call (h) on a throwaway address: `user create` it into the org, sign in
  once, then `user delete` it and confirm the account cannot sign in, the stored address is
  gone, and any Task it owned still exists in the database.** Plus one cheap
  full-chain smoke (an existing personal Task still loads end-to-end). **Not** a full live
  e2e run.

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

**Named call-out for the security lane — `is_admin` (owner call (f)).** It reads every
row in the system, so it is the highest-value target in this design and must be reviewed
as such, not as one more boolean:
(1) it is settable **only** by the ops CLI — no HTTP route writes it, and no request body
can reach it, so there is no self-serve or mass-assignment path;
(2) it appears on the **read** leg only — a reviewer should try to find any write path,
listing filter or projection that consults it and fail. The broad name invites exactly
this drift, which is why the check is structural and not just behavioural;
(3) `/me` exposing it is a read of the caller's own row, not a capability;
(4) the trace fires on the admin leg alone — an admin reading what they were already
entitled to must not generate noise, or the audit signal is worthless;
(5) the disclosure is part of the security surface, not decoration: if the privacy-notice
sentence or the corrected visibility copy is missing, the slice ships a product that
tells users `private` means something it does not. **The privacy page is live public
legal copy — owner sign-off before merge.**
Default `false` means an un-granted deployment behaves exactly as it does today.
**Known accepted risk, decided by the owner 2026-08-24, not an oversight to re-raise:** the
pool has no MFA (`MfaConfiguration: None`) and no explicit password policy, so an `is_admin`
account — which reads every row in every organisation — is protected by a password alone.
033 holds its no-infra-change constraint; the gap is recorded in `docs/deferred.md` with
per-user MFA as the identified route, to revisit before the first real organisation is
enrolled in prod.

**Second call-out — the Cognito lookup and stored email (owner call (g)).**
(1) `boto3` must stay in the `ops` group and out of the runtime: confirm the built image
does not contain it, not merely that the group is declared correctly;
(2) the lookup runs **only** in the ops CLI. The check that no request path can reach
Cognito is structural — no API module imports `boto3`, directly or transitively — and the
API task role must gain no Cognito permission, verified in the CDK diff and not just in
the Python;
(3) `?owner_email=` must not become an enumeration oracle: a non-admin gets the same 400
whether or not the address exists, and an admin's result set is bounded by the same
pagination as any other listing;
(4) `email` is now personal data in the application database. Both erasure levers have to
actually work — de-enrolment clears the address, `user delete` clears it and removes the
account — and § 3 of the privacy notice has to be accurate about what is stored. These are
review items, not paperwork;
(5) **`user delete` is the most destructive command in the repo** (owner call (h)) and gets
read line by line: it must remove the Cognito account and the stored personal data, and
must **not** delete, reassign or cascade to a single owned row. The test that counts owned
projects before and after is the one that matters. `--force` exists for scripts; a reviewer
should check it is not the default path anywhere in the make targets.
