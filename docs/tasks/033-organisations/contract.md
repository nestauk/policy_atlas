# Task contract: 033-organisations

> **Status:** drafted 2026-08-11 (rev 1) · re-opened and de-collided 2026-08-24 (rev 2.0) ·
> **rev 3.0, 2026-08-24 — rewritten after the contract-stage adversarial review.**
> Three lanes (tenancy/authorization, scope/coherence, and Codex as the heterogeneous
> peer) all recommended against approving rev 2.0. The scope lane recommended splitting
> into three slices; **the owner ruled to keep one slice and patch every finding**
> (2026-08-24). This revision does that. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: 0032.
>
> **What rev 3.0 changes.** Four kinds of finding, all now addressed in the body:
> **(1) self-contradictions** — `is_admin` "read leg only" versus the listings that must
> read it; "write = owner only, exactly like an org colleague" when colleagues *are*
> granted three chat mutations; `/me` writing inside a GET against the contract's own
> stated rule; `HistoryView` "scopes to the caller" against the org read grade.
> **(2) wrong about the world** — the live privacy notice already claims the email is
> stored (§ 3) and already promises permanent Aurora deletion on request (§ 7); the repo
> already ships `make prod-user`, which does the opposite of what rev 2.0 pinned; the
> `boto3` ops-group plan broke `make verify`; the downgrade is schema-reversible but
> **data-destructive and chat-exposing**. **(3) design holes** — no stated NULL-`org_id`
> rule, nothing stamping `org_id` on new rows, i.5's stated way out defeated by i.2.
> **(4) single-owner assumptions baked into existing code** — seven conversation-id
> routes outside the old enumeration, SSE that authorises once and streams forever, a
> stale-turn sweeper keyed to the project owner, and a blind `.values(**changes)` splat on
> `PATCH /portfolios/{id}`. Category 4 is the reason this slice is larger than rev 2.0
> described: **tenancy is not a refactor of ownership checks, it invalidates assumptions
> held throughout the request, streaming, sweeping and caching paths.**
>
> **Vocabulary (032, ADR 0031 — read before every noun below).** Screen word **Task** =
> the code row `project`. Screen word **Project** = the code row `portfolio`. This
> contract uses **code words** throughout; user-facing strings are given in screen words
> and marked as such. A standalone rename slice follows 033 and must cover this slice's
> code.
>
> **Owner calls (2026-08-11):** **(a)** membership is app-owned and ops-assigned — no pool
> reconfiguration, no groups, no claims, no federation, and membership is never read from
> the IdP (amended by (h): the CLI does create Cognito *users*) · **(b)** org access =
> read everything + own chats; all other mutations stay owner-only · **(c)** per-row
> `visibility`, default `org` · **(d)** no enrolment backfill — dark launch.
> **Owner calls (2026-08-24):** **(e)** `portfolio` takes the same tenancy grades as
> `project` · **(j)** **enrolment carries the person's existing work with them, private**
> (owner, 2026-08-24 — amends (d)): `user enrol` stamps the person's `org_id` onto every
> `project` and `portfolio` they own **and sets those rows `visibility='private'`**. (d)'s
> "no enrolment backfill" still holds for the database at large — no row moves except the
> enrolled person's own · **(f)** `app_user.is_admin` grants **read** of every row in every
> organisation, `private` included; no write, ever · **(g)** `app_user` stores the Cognito
> email; admins filter work by it · **(h)** the ops CLI creates Cognito users; **deleting
> them is Out**, coupled to ownership transfer · **(i)** visibility cascades between a
> `portfolio` and its `project`s, deterministic, no prompts.

## Goal

Users belong to an organisation. A signed-in user sees, by default, their own work and
their organisation's org-visible work — `project` rows and the `portfolio` rows that group
them — and can switch between the two. Org-visible rows are readable end-to-end by org
colleagues, who may also hold their **own** chat conversations on them. Every other
mutating action remains the owner's alone. A small number of ops-assigned
**administrators** read across every organisation for support, writing nothing, with every
such read traced.

## Deliverable

One PR landing: the `organisation` and `app_user` tables; `org_id` and `visibility` on
`project` and `portfolio`; `conversation.created_by`; one access helper with three read
legs (owner, same-org, admin) and one write grade, applied to **every** project-,
portfolio- **and conversation-scoped** route; org-aware SSE that re-authorises as it
streams; the re-keyed chat pending cap **and its sweeper**; `GET /api/v1/me`; `scope`,
`owner_email` and `portfolio_id` filters on the listings; the portfolio/project visibility
and org invariant; the ops CLI (org create, user create, enrol, de-enrol, row assignment,
admin grant/revoke) with `boto3` in a declared dependency group; the frontend switcher,
read-only affordance matrix, account menu, cache invalidation and visibility-outcome copy;
spec flow-back; ADR 0032; and `verification.md`. **No privacy-notice copy changes**
(owner, 2026-08-24) — the three discrepancies ship as a recorded escalation instead.

**Removed by this slice:** the `staging-user`, `prod-user` and `cognito-user` make targets
(`Makefile`), which the CLI supersedes and whose password-in-argv behaviour this contract
forbids.

## Read first

- [web-api.md](../../specs/system/web-api.md) — § Auth boundary (the BOLA 404 rule; the
  pre-reserved 403; **the existing error-code map — 400 `malformed`, 422
  `validation_error`** — which this slice must extend rather than contradict).
- [data-model.md](../../specs/system/data-model.md) — § Entity hierarchy.
- [ADR 0031](../../adr/0031-portfolio-layer-above-the-project.md) — the portfolio layer;
  **decision 4 says assignment is a PATCH, not a field on create**, which § API amends.
- `docs/deferred.md` — 029 and 032 seams; the 033 entries.
- [DEPLOYMENT.md § 6](../../../infra/DEPLOYMENT.md) and `JUMPBOX.md` — how the ops CLI
  reaches the database, and where its operator IAM is documented.
- `frontend/src/views/legal/PrivacyView.tsx` — read §§ 3, 6 and 7 to understand the three
  recorded discrepancies (§ 12). **This slice does not edit the file.**
- Current code the slice must change, not merely wrap: `api/routers/_common.py`,
  `projects.py`, `portfolios.py` (**`update_portfolio`'s `.values(**changes)` splat**),
  `conversations.py` (**two routers** — one project-scoped, one keyed by conversation id),
  `chat_turns.py` (**`_expire_stale_pending_turns`, keyed to the project owner**),
  `sse.py` (**`_tail` takes no authorization argument**), `read_models.py`, `runs.py`,
  `planning.py`, `check_ins.py`, `auth.py`, `core/schema.py`.

## Scope / Out of scope

**In:**

1. **Schema (approval-gated · additive migration chained off 032's head `b3c7d914e0a2`):**
   - `organisation` — `org_id` UUID PK · `name` Text NOT NULL UNIQUE · `created_at`.
   - `app_user` — `user_id` Text PK (the token `sub`) · `org_id` FK → organisation
     nullable · `display_name` Text **NOT NULL** (see § Identity: the email must never be
     a display fallback) · `email` Text nullable · `is_admin` Boolean NOT NULL DEFAULT
     `false` · `created_at`.
   - `project` and `portfolio` — each gains `org_id` FK nullable and `visibility` Text NOT
     NULL DEFAULT `'org'` CHECK (`org`|`private`), plus the listing indexes for the org
     leg (`project`: `(org_id, visibility, status)`; `portfolio`: `(org_id, visibility)` —
     it has no `status`).
   - `conversation` — `created_by` Text nullable, backfilled from the owning `project`'s
     `owner_user_id`.
   - No enrolment backfill. `runtime/orchestrate.py` rows keep `owner_user_id=NULL`.

2. **User provisioning.** `GET /api/v1/me` upserts `app_user` **`ON CONFLICT DO
   NOTHING`** — it creates a bare row and must never clobber ops-set fields. Ops enrolment
   upserts **`ON CONFLICT DO UPDATE`**. `get_current_user` stays DB-free and Cognito-free.
   **On the write-inside-a-GET question** (§ 3a rejects `event_log` partly on that ground):
   the asymmetry is deliberate and stated here so a reviewer does not have to guess — JIT
   provisioning is a **once-per-user** insert that no-ops thereafter, whereas an
   `event_log` trace would be a write on **every** read. Both rules survive.

3. **Authorization.** One helper, three read legs and one write grade:
   - **read** = owner ∪ (**same org**: `app_user.org_id` non-NULL **and** equal to the
     row's non-NULL `org_id` **and** `visibility='org'`, existing archived/status rules
     unchanged) ∪ (**admin**: `is_admin`, any row, any org, any `visibility`).
   - **write** = **owner only**, with exactly one documented exception: the three chat
     mutations owner call (b) grants a same-org colleague (§ 4). **An `is_admin` holder is
     not a colleague** and receives **none** of them — admin is read-only without
     exception. Rev 2.0's phrase "403 on every mutation, exactly like an org colleague"
     was false in both halves and is struck.
   - **The NULL rule, stated because it is the highest-blast-radius mistake available
     here:** a row with `org_id IS NULL` is reachable by its owner and by an admin only; a
     caller with `org_id IS NULL` matches **no** org leg. The org leg **must be expressed
     as a SQL predicate**, never as a Python comparison of two loaded values, because
     `None == None` is `True` in Python and would expose every unenrolled user's work to
     every other unenrolled user on day one. Pinned by a named test using two callers and
     two rows, all with NULL `org_id`.
   - Not-visible → **404**, indistinguishable body. Visible-but-not-writable → **403
     `forbidden`**.
   - **Every** project-, portfolio- **and conversation-scoped** route resolves access
     through the helper. The plan enumerates the call sites from the tree; the enumeration
     must include `api/routers/conversations.py`'s **second router**, mounted at
     `/api/v1/conversations`, whose seven routes take a conversation id and no project id
     (§ 4). Rev 2.0's enumeration missed it entirely.

3a. **The admin leg, its trace, and what may read the flag.** Rev 2.0 said the helper was
   the only reader of `is_admin` and simultaneously required two listings to consult it.
   The closed list of legitimate readers is therefore **named** here, and the structural
   assertion is made against this list rather than against "nowhere else":
   **(i)** the row-access helper's admin leg · **(ii)** the listing scope resolver ·
   **(iii)** the `owner_email` filter gate · **(iv)** the `/me` projection.
   Anything else reading the flag is a defect. **No write path may read it.**
   - **Trace grain, defined because "one line per read" is meaningless for a listing.**
     Direct row reads served by the admin leg emit **one line per row**
     (`event="admin_read"`). Listing and search requests served across organisations emit
     **one line per request**, carrying the filter, the page and the row count. **A search
     returning zero rows still emits its line** — otherwise an admin can probe whether an
     address owns any work, repeatedly and invisibly. **An SSE subscription emits a line at
     subscribe and one per re-authorisation batch** (§ 5), not one line for an unbounded
     stream. Nothing is emitted for a read the caller was already entitled to.
   - **Grant and revoke of `is_admin` are themselves traced** by the ops CLI, naming the
     operator, the subject and the direction. A privileged grant with no record of who made
     it is not auditable.

3b. **Identity, and what is shown to whom.** The only claim any request path reads is
   `sub`. Everything else is resolved once, out of band, by the ops CLI.
   - The pool is `UsernameAttributes: ["email"]`, so `cognito:username` is a generated
     UUID, not the address; the address lives in the pool attribute, the ID token and
     userinfo, none of which the API sees. **`sub` stays the key** — addresses change,
     `sub` does not.
   - **`display_name` is NOT NULL and required at enrolment, and `owner_display` never
     falls back to the email** (`display_name`, else the `sub` rendering). Rev 2.0's
     email fallback would have printed every colleague's address on every row and card,
     and let an admin harvest `{email, organisation}` for every owner in the system — which
     is the user directory this contract declares Out, reached by another door.
   - **`email` is ops- and admin-facing only.** It appears in `/me` (the caller's own row)
     and in the `owner_email` filter. It is never rendered to another user.
   - **Staleness is not cosmetic and is not accepted silently.** An address changed in
     Cognito goes stale until re-enrolment; that breaks admin search and means the app
     holds an inaccurate address. `user resync --email` re-resolves it, and the gap is
     recorded rather than dismissed.

4. **Chats, and the seven routes rev 2.0 missed.** Org members create and read **their
   own** conversations (`created_by = sub`). The three mutations owner call (b) grants a
   colleague are exactly: create a conversation on a readable project, post a turn to
   **their own** conversation, and cancel **their own** turn. Nothing else.
   - **The conversation-id router** (`/api/v1/conversations`) is graded route by route:
     `GET /{id}`, `GET /{id}/turns`, `PATCH /{id}`, `POST /{id}/archive`, `POST
     /{id}/unarchive` — **own conversation only** for chats (the creator), **project owner
     only** for planning conversations; an admin may **read** `GET /{id}` and `GET
     /{id}/turns` (traced) and may write none of them. A same-org colleague who did not
     create the conversation gets **404**, not 403 — the row's existence is not theirs to
     learn. `GET /{id}/turns` returning a transcript by id is the leak this grading closes.
   - **The own-chats filter is specified exactly**, because a bare `created_by IS NULL`
     disjunct would hand colleagues the owner's legacy rows:
     `created_by = :me OR (created_by IS NULL AND project.owner_user_id = :me)`.
   - **The pending cap re-keys to the acting user, and so does its sweeper.**
     `_expire_stale_pending_turns` currently selects conversations by
     `project.owner_user_id`; re-keying the cap without re-keying the sweep means a
     colleague whose two turns die mid-flight is rate-limited **permanently, on every
     project, with no operator lever**, while an owner's sweep silently fails other
     people's in-flight turns. Both are re-keyed to `created_by` together.
   - **Named consequence:** re-keying removes the only per-project chat-spend bound — an
     organisation of N members can drive 2N concurrent chat turns against one owner's
     project. Org-level capacity policy stays Out; this contract states the change rather
     than presenting it as neutral fairness.
   - **Lock scope:** colleague chat paths must not take `SELECT … FOR UPDATE` on the
     owner's `project` row, or a colleague's turn blocks the owner's rename, archive and
     run-start. The plan names the lock each path actually needs.

5. **SSE, which authorises once today.** `_snapshot` calls the helper; `_tail` takes no
   authorization argument and loops indefinitely. Under owner-only tenancy that was sound
   because ownership never changed. This slice introduces four revocation events —
   de-enrolment, a visibility flip, an i.4 cascade, and admin revoke — **none of which
   close an open stream**. So: **the tail re-authorises on each batch** (one indexed query
   against a row the loop already identifies) and closes the stream when access is gone.
   Without this the rollback plan's "de-enrolment reverts to per-owner behaviour without a
   deploy" is false.

6. **The visibility and org invariant (owner call (i)).** **A `project` with a
   `portfolio_id` carries that `portfolio`'s `visibility` *and* its `org_id`.** Rev 2.0
   covered `visibility` only, which let an operator assign a project to org A and its
   portfolio to org B and have org B's members read and count a row belonging to org A.
   A `project` with no portfolio is unconstrained. Deterministic; nothing prompts.
   - **(i.1)** `POST /portfolios {from_project_id}` — the new portfolio inherits that
     project's `visibility` and `org_id` and takes it as its first member. **This amends
     ADR 0031 decision 4** ("assignment is a PATCH, not a field on create"); ADR 0032 must
     record the amendment. The source project resolves under the **write** grade — under a
     read grade a colleague, or an admin, could change the visibility of a row they do not
     own, which is the concrete admin-write escape.
   - **(i.2)** private project → org portfolio: the project is promoted.
   - **(i.3)** org project → private portfolio: the project is demoted (the non-exposing
     direction).
   - **(i.4)** a portfolio's visibility changes: every member follows. **The cascade is
     the only writer of `portfolio.visibility`** — `update_portfolio`'s blind
     `.values(**changes)` splat must not be allowed to carry the field, or an owner sets a
     Project private, the UI agrees, and its Tasks stay readable by the whole
     organisation. Archived members **are** included, and the outcome copy counts only the
     members the caller can see.
   - **(i.5)** setting a `project`'s visibility while it is in a `portfolio`: **409
     `visibility_conflict`**. The two ways out are "change the Project's visibility" and
     "**leave the Task out of the Project**" — *not* rev 2.0's "remove it first", which was
     a no-op loop: removing keeps the old visibility (i.6), setting it private then
     succeeds, and re-adding fires i.2 and silently re-exposes the row.
   - **(i.6)** removing a `project` from a `portfolio`: visibility and `org_id` unchanged.
   - **A `PATCH /projects/{id}` body carrying both `visibility` and `portfolio_id`
     is rejected 422** — the two orderings give different results, and "the UI and a direct
     API caller get identical results" is otherwise untestable.
   - Enforcement lives in the write paths plus a property test; the invariant spans two
     tables, so no CHECK can express it.

7. **Org stamping, enrolment, and what an unenrolled user's work does.**
   `POST /projects` and `POST /portfolios` stamp `org_id` from the creator's
   `app_user.org_id` — **NULL when the creator is unenrolled**.
   - **Before enrolment:** an unenrolled user's rows are reachable by their owner and by an
     admin, and by nobody else (§ 3's NULL rule). `visibility='org'` sits on them as an
     inert default — "org" means nothing where there is no org. The frontend hides the
     switcher entirely when `/me` returns no organisation, so an unenrolled user sees
     today's application unchanged. That is the dark launch.
   - **Enrolment carries their work with them, private (owner call (j)).** `user enrol`
     stamps `org_id` onto every `project` and `portfolio` the person owns **and sets those
     rows `visibility='private'`** — in **one transaction** with the `app_user` upsert,
     reporting the counts it moved. Two properties make this the right default:
     **nothing is ever exposed by an operator action** — the rows arrive private and the
     person opts each one into their organisation deliberately — and **the person sees no
     change**, because rows with a NULL `org_id` were already invisible to everyone but
     them. The alternative, leaving their history behind, would split a person's work in
     two with nothing on screen explaining why.
   - **The invariant survives the move** because a `portfolio`'s members are always owned
     by the portfolio's owner: setting `portfolio_id` requires ownership of both rows
     (032, `projects.py`). So one person's rows are a closed set, and stamping them
     together leaves every `project` matching its `portfolio` on both `org_id` and
     `visibility`. The move is a set operation, not a row-by-row walk through the cascade
     path — which would transiently violate the invariant.
   - **Re-enrolment into a different organisation moves the rows again, and re-privatises
     them.** Work that the person had deliberately shared with organisation A does **not**
     arrive shared in organisation B. Pinned by a test.
   - **De-enrolment takes the rows back out:** it clears `org_id` on every `project` and
     `portfolio` the person owns, so nothing of theirs stays readable by the organisation
     they left. **Owner decision worth knowing:** this treats work as belonging to the
     person, not the organisation — an org loses sight of a departing member's Tasks. The
     alternative (the organisation retains access to work done in it) is defensible and
     would need ownership transfer, which is Out. Flagged, not assumed.

8. **API (approval-gated · additive).** `GET /api/v1/me` →
   `{user_id, display_name, email, organisation: {org_id, name} | null, is_admin}` ·
   `scope=all|mine` on both listings · **`portfolio_id` filter on `GET /projects`**,
   because `PortfolioDetailView` filters the default 50-row global page client-side today
   and would silently under-report a Project's Tasks once the visible estate spans an
   organisation · `owner_email` on both listings, admin-only · `ProjectOut` and
   `PortfolioOut` gain `visibility`, `is_owner`, `owner_display` · `PATCH` accepts
   `visibility` (owner-only) · `POST /portfolios` accepts `from_project_id` · error
   envelope gains **403 `forbidden`** and **409 `visibility_conflict`**; a non-admin
   passing `owner_email` and a both-fields PATCH both return **422 `validation_error`**,
   the code the existing map already assigns, **not** a third "your parameter is wrong"
   semantic. Portfolio task counts include only rows the caller may read **and** rows in
   the caller's own org. `make openapi-sync` regenerates the two generated files.

9. **Ops tooling.** `policy_atlas.ops` CLI plus make targets: create org · **create user**
   (`AdminCreateUser` **with `DesiredDeliveryMediums=["EMAIL"]` — AWS defaults this to
   SMS**, then enrol; Cognito first because its `sub` is the key; on a database failure the
   account is kept and the `user enrol` remediation printed) · enrol by email · resync
   email · assign a single `project` or `portfolio` to an org (**moving both together where one is a
   member of the other**, per § 6) · de-enrol (clears `org_id`, `email` and `is_admin` on
   `app_user`, **and `org_id` on every row the person owns**) · grant/revoke admin.
   **No password passes through the CLI**: no `--temporary-password`, ever.
   - **Environment safety, because Cognito and Postgres are addressed separately.** An
     operator with a production tunnel open on `localhost:15432` and staging credentials
     would write staging identities into production. Every command takes an explicit
     `--env staging|prod`, **verifies that the AWS account and user-pool id it resolved
     match the database it is connected to** (a row in `organisation` or a settings table
     naming the environment), and refuses to act on a mismatch. This is the single
     highest-consequence operational failure in the design.
   - **Concurrency.** Enrol, de-enrol and admin grant/revoke are last-writer-wins as
     specified, so operator B can resurrect admin on a row operator A just de-enrolled.
     Each command reads the row `FOR UPDATE` and refuses when the current state does not
     match what the operator was acting on.
   - **Invocation** is the operator's laptop over the SSM jumpbox tunnel (DEPLOYMENT.md
     § 6), **not** the ECS migration-task pattern — Cognito permission belongs to the human
     operator, not to a task role. Operator IAM: `ListUsers` and `AdminCreateUser` only.
   - **The `staging-user` / `prod-user` / `cognito-user` make targets are deleted** in this
     PR. They create a Cognito user without enrolling it, suppress the invitation, and take
     a password on the command line. Leaving them would ship two contradictory procedures,
     and the make target is the one with muscle memory behind it.

10. **`boto3`, and the dependency-group problem rev 2.0 got wrong.** A non-default group is
    excluded from the image — and from `uv sync`, so the CLI's tests fail at import, mypy
    `strict` over `src` errors on `import boto3`, and `pip-audit --skip-editable` never
    sees the dependency. So: **`ops` is a declared group installed in development and CI,
    with `--no-group ops` added to `backend/Dockerfile`** — a named, approval-gated
    Dockerfile change — keeping `boto3`+`botocore` out of the runtime image while the tests
    and the audit can reach it. **`boto3-stubs[cognito-idp]` ships in the same group**;
    strict mypy has no inline types for boto3. Rev 2.0's "No CI change" claim is struck.
    The review checks the **built image**, not the declaration.

11. **Frontend.** The switcher (**Organisation · Mine**, hidden entirely when `/me` returns
    `organisation: null`, so rubric 11's dark-launch invariant holds on day one) on
    `TasksListView` and `PortfoliosView` · `owner_display` on rows and cards ·
    **a named owner/non-owner affordance matrix**, because `LifecycleRoute` gates on run
    status alone and cannot make a component read-only: `PlanningPane` (and its duplicate
    inside `ChatSidePanel`), `PlanCard`, `RunPane`, the suggestion chips, the plan-start
    card, check-in responses, and retry controls each own mutations independently, and a
    non-owner who can still click Run is a write-path bug · **the check-in banner in
    `AppShell` scopes to the owner** — today it polls for every viewer and tells a
    colleague a check-in is "waiting on you" when steering is owner-only · `HistoryView`
    **shows the owner's decisions and planning turns to any caller who can read the
    project** (rev 2.0's "scopes to the caller" contradicted the read grade; that line is
    struck) · the account menu names email, organisation and admin state, falling back to
    the `sub` rendering when unenrolled · visibility-outcome copy, one line, stated not
    asked · the admin's wider list says plainly that it spans organisations, and renders a
    **null** owning organisation without a blank line (admin sees NULL-`org_id` rows,
    including `runtime/orchestrate.py` CLI rows) · **React Query invalidation across
    families** — a cascade changes rows in a different query family from the mutation, and
    `scope` must be part of every affected query key, or the toast says "Now private" while
    the cards show the opposite until reload · the mock API serves `/me` and the portfolio
    routes it needs for these journeys.

12. **Privacy and governance — no copy change ships (owner, 2026-08-24).** The owner
    ruled that the privacy notice is **not rewritten by this slice**: legal copy belongs to
    whoever owns the notice (the page names a Data Protection Officer), not to an
    engineering contract. So `PrivacyView.tsx` is **untouched**, and the three edits rev
    3.0 specified are withdrawn. What replaces them is an escalation, not silence, because
    the discrepancies are real and this slice widens two of them:
    - **§ 7 promises what the system cannot do.** It states that on request personal data
      "will be permanently deleted from our Amazon Aurora PostgreSQL database".
      De-enrolment keeps every Task, query, result and transcript, keeps the `sub`, leaves
      the Cognito account untouched, and leaves seven days of backups.
    - **§ 3 is already inaccurate today** — it calls the email "the only user-specific
      identifier we store" when the database stores no email at all and does store the
      `sub`. This slice makes the email real, which removes half the inaccuracy and leaves
      the "only" claim wrong.
    - **§ 6 does not mention administrator access**, and after owner call (f) an
      ops-assigned administrator reads every row in every organisation, `private`
      included.
    **Consequence, stated once and carried rather than re-argued:** with no § 6 sentence,
    the control set for the admin leg is **the trace log alone** — "disclosure is the
    control" (§ 3a) no longer holds, because nothing discloses it to users.
    **What ships instead:** `verification.md` records the three discrepancies verbatim and
    names them as an **open escalation to the notice's owner**, and `docs/deferred.md`
    carries them so they cannot be lost. A **DPIA screening and processing-record update
    are still required before merge** — those are governance artefacts, not copy, and this
    slice introduces identifiable personal data and a global privileged read.

13. **Spec flow-back.** `web-api.md` § Auth boundary (the three read legs, the NULL rule,
    403/409/422 semantics, `/me`, the three filters), § Portfolios (the invariant),
    § Conversations (the conversation-id router's grades) · `data-model.md` tenancy note ·
    `JUMPBOX.md` operator IAM · `DEPLOYMENT.md` § 6 CLI invocation and the rollback posture
    below · seams in `docs/deferred.md`.

**Out (⏸ deferred, recorded):**

- A role system; per-org roles; any org-management UI. `is_admin` is one global boolean.
- **Admin write of any kind**, including chat. An admin is not a colleague.
- An admin dashboard or any admin surface; a user directory or address search.
- **Deleting a Cognito user from the CLI**, coupled to **ownership transfer** — neither
  ships without the other. De-enrolment is the removal lever, and it does **not** stop an
  offboarded person signing in; disabling the account is a Cognito operation outside this
  tooling.
- Multi-org membership; sharing to named individuals.
- Org-level run/chat capacity policy (see § 4's named consequence).
- MFA on the pool — recorded as a known accepted risk against `is_admin` (`deferred.md`).
- Adoption of NULL-owner pre-025 rows: still not adopted, but note the **admin leg makes
  them visible**, which amends the "unreachable" wording in the recorded posture.
- Extending the mock API beyond what § 11 names; cursor pagination; the `latest_run` N+1.
- Resolving the code/screen vocabulary split — the rename slice that follows.

## Constraints & approval gates

Schema (2 new tables, 2 altered, 1 backfilled) · auth and tenancy semantics · public API
additions · **`boto3` + `boto3-stubs` in a new `ops` dependency group** · **a
`backend/Dockerfile` change (`--no-group ops`)** · **deletion of three existing make targets** · **Cognito account creation**. Each
is an approval in its own right and this contract is where they are granted.
**"No CI change" is struck** — CI installs the `ops` group. Egress: the ops CLI calls
`ListUsers` and `AdminCreateUser` under the operator's own IAM; **the API's egress is
unchanged** and the task role gains no Cognito permission.

**Sequencing pin:** `b3c7d914e0a2` is the sole alembic head. Deploy order is unchanged and
load-bearing: register task definitions → stop the API → migrate from the **new** image →
start the new API → publish the frontend. New backend code must never start before the
migration.

**Rollback posture — corrected, because rev 2.0's "downgrades cleanly" was false.** The
downgrade is schema-reversible and **data-destructive**: it drops `created_by`, so every
colleague's chat authorship is lost, and pre-033 code lists *all* conversations on a
project to its owner — **a rollback after adoption exposes colleagues' private chats to
the Task owner**. It also drops both `visibility` columns, so a later re-upgrade defaults
every row back to `org` and no private choice can be reconstructed. Therefore: **roll
forward, not back.** The dark-launch is the real safety net — with no orgs enrolled the
behaviour is byte-identical to today, and de-enrolment reverts an organisation without a
deploy. A downgrade is a last resort requiring a backup restore, and the ECS migration
task runs `alembic upgrade head` only, so it has no downgrade path at all: the procedure
is documented in DEPLOYMENT.md rather than assumed.

**Migration safety:** `ALTER TABLE` takes `ACCESS EXCLUSIVE`; a developer's idle jumpbox
session can block it while the API is scaled to zero. The migration sets a lock timeout,
the deploy runbook gains a blocker preflight, and the `created_by` backfill is rehearsed
against production-scale data before it runs live.

## Public / private boundary

Public-safe: synthetic subs in fixtures, no real addresses, no staging org names, no
secrets or allowlists committed.

## Model route

n/a — no LLM-bearing step; prompt surfaces untouched.

## Disciplines

Model only what behaves · the 404/403 line is contract · **counts and absences leak too**
(a zero-result search is still a disclosure event) · **a published promise the system
cannot keep is a defect** — this slice cannot fix the one it found, so it escalates it in
writing rather than shipping past it in silence.

## Stop conditions

Roles, admin write, IdP changes, user deletion, ownership transfer, or resolving the
vocabulary split — each halts and escalates.

## Acceptance checks

- `make verify` green (**with the `ops` group installed**); `make drift-check` green.
- **Tenancy matrix**, each pinned by a named test: same-org read 200 · same-org write 403 ·
  cross-org 404 · `private` hidden from the org · **two NULL-`org_id` callers cannot see
  each other's NULL-`org_id` rows** · scope and `portfolio_id` filters correct on both
  listings · counts exclude unreadable and out-of-org rows · own-chats isolation in both
  directions, **including a direct `GET /conversations/{id}/turns` deep link** · the
  legacy-NULL `created_by` disjunct · pending cap **and sweeper** keyed to the acting user
  · `/me` upsert idempotency and non-clobbering.
- **Admin:** reads an org-visible and a private row in a foreign org · **is refused every
  mutation including chat creation and turn POST** · only the four named readers consult
  the flag (structural) · trace grain — one line per row read, one per listing request
  **including a zero-result search**, one per SSE re-authorisation · defaults `false`.
- **Invariant:** the property over i.1–i.6 covering `visibility` **and `org_id`** · i.5
  409 · the both-fields PATCH 422 · `update_portfolio` cannot write `visibility` outside
  the cascade · the i.5-then-i.2 loop cannot silently re-expose a row.
- **SSE:** an open stream closes on de-enrolment, on a visibility flip and on admin revoke.
- **Ops:** create sends an email medium explicitly · environment mismatch refuses to act ·
  concurrent grant/de-enrol cannot resurrect admin · new rows stamp `org_id` from the
  creator · **enrolment moves every row the person owns and sets them `private`, in one
  transaction, reporting the counts** · **re-enrolment into a second org moves them again
  and re-privatises rows that had been shared with the first** · **de-enrolment clears
  `org_id` on their rows so the org they left loses sight of them** · the invariant holds
  across all three moves · no path calls `AdminDeleteUser`.
- **Migration:** up/down roundtrip; `created_by` backfill; **a test proving the documented
  rollback exposure**, so the risk is evidenced rather than asserted.
- **Frontend:** the affordance matrix component by component · the switcher absent with no
  organisation · cache convergence after a cascade **without reload** · the check-in banner
  absent for a non-owner.
- **Live check** on staging: two users in one org plus a third admin in neither; **enrol a user
  who already owns Tasks and confirm they arrive private and still work for their owner,
  then share one deliberately**; org-visible and private Tasks; own-chat isolation; rename 403; both switchers; `owner_email`;
  `portfolio_id` paging beyond 50 rows; the account menu per user; the invitation email
  actually arriving (**the pool has no `EmailConfiguration`, so this uses the
  50-per-day `COGNITO_DEFAULT` sender and needs a real deliverable mailbox — an unstated
  prerequisite in rev 2.0 that could strand the slice at step 6**); and an SSE stream closing
  on revoke.

## Verification evidence expected

Command outputs; the named test list per matrix row; migration up/down evidence and the
backfill rehearsal; the built-image check for `boto3`; live-check notes; **the three privacy-notice
discrepancies quoted verbatim as an open escalation to the notice's owner**; the DPIA
screening outcome; diff
summary; public-safety confirmation; known gaps.

## Risk tier & review focus

**Tier 4.** Human-approved plan · ADR 0032 (recording the ADR 0031 D4 amendment) · the
rollback posture above · security lane · adversarial review at plan and code stages · human
deep review.

**The security lane reads three unrelated threat models** — the tenancy boundary, the
privileged read plus its audit, and the operator CLI against a live identity provider —
**and must be scoped as three passes, not one.** The owner chose one slice over the
reviewers' recommended split (2026-08-24); this is the review cost that decision carries,
and it is stated here rather than discovered at step 7.

**Review focus:** the NULL-`org_id` rule expressed in SQL · the conversation-id router's
grades · SSE re-authorisation · the sweeper re-key · `update_portfolio` not writing
`visibility` · the four named readers of `is_admin` and no fifth · trace grain including
zero-result searches · `owner_display` never rendering an address · org stamping and
re-enrolment · environment mismatch in the CLI · the rollback exposure being documented
and evidenced.
