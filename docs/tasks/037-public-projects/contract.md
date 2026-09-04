# Task contract: 037-public-projects

> **Status:** approved. Contract approved: 2026-09-04 · owner ·
> Plan approved: 2026-09-04 · owner (both in one review; the owner asked to
> keep the adversarial review short — one combined pass over contract +
> rubric + plan instead of two staged passes) · ADR: 0035. The ❓ excerpt
> default (§ Public / private boundary) stands — the owner did not rule
> against it.
>
> **Adversarial review ran 2026-09-04** (one combined Codex pass, per the
> owner). Five findings, all adjudicated valid and folded in: (1) the
> reused Results view calls chat/stream hooks — the plan now specifies a
> public view mode and a network assertion; (2) the shared query cache
> could show stale private data across sign-out — the cache is now cleared
> on identity change; (3) signed-in outsiders reached the full shell — the
> read shape gains an `access` field (see D5) and both routers render the
> slim view for public-leg reads; (4) a wrong-scheme or malformed
> `Authorization` header would have passed as anonymous — D2 now keys on
> the raw header; (5) `is_public: null` would 500 — it joins the
> explicit-null 422 rule. Item 3 adds one additive read-only field beyond
> the first draft — flagged to the owner with this revision.

## Goal

A Task owner can share one Task with the public. Anyone who has the link —
signed in or not — opens the **same URL** the owner uses and sees the
**Results** and **Sources** tabs. Nothing else becomes public. The owner can
turn public sharing off at any time, and the link stops working at once.

## Deliverable

One PR containing:

- A **Public link** section on the Share tab: an owner-only on/off control
  and a Copy-link button, with copy that says what becomes visible.
- A new `project.is_public` boolean column (default `false`) and the
  `is_public` field on the project read and update shapes.
- A **public read leg** on the exact endpoint list in § Public read surface:
  a request with no bearer token succeeds only when the Task is public and
  active; every other route keeps today's behaviour.
- Frontend routes so a signed-out visitor can open
  `/projects/{id}/results` and `/projects/{id}/sources/*` directly; a
  private or unknown Task keeps today's behaviour (stash the URL, show the
  splash page).
- Spec updates (`web-api.md`) and the discharge note for the
  "read-only/public links" part of `docs/deferred.md` § Export & sharing.

## Terms

| Term | Meaning |
|---|---|
| **Task** | The `project` database row. On screen a `project` is called a Task (ADR 0031). |
| **Project** | The `portfolio` database row — a named group of Tasks. On screen a `portfolio` is called a Project. |
| **public Task** | A `project` row with `is_public = true` and `status = 'active'`. |
| **anonymous visitor** | A browser session with no signed-in user. Its API requests carry no `Authorization` header. |
| **public read surface** | The exact list of GET endpoints an anonymous visitor may call (§ Public read surface). Nothing outside this list changes. |
| **read grade** | The task-033 access rule for signed-in users: owner ∪ same-org colleague ∪ admin (`web-api.md` § Tenancy). This slice does not change it. |
| **redacted shape** | The project response as served through the public leg: `owner_display = null`, `portfolio_ids = []`, `is_owner = false`, `access = "public"`. All other fields unchanged. Graded reads carry `access = "full"`. |
| **conformance allowlist** | `backend/tests/api/test_api_conformance.py` — the frozen list of routes that may answer without a token. This slice widens it deliberately. |

## Read first

- `docs/specs/system/web-api.md` — §§ Auth, Tenancy, Error envelope, Projects.
- `docs/tasks/036-splash-page/contract.md` — precedent: the public router
  split and the first public endpoint.
- ADR 0033 (tenancy) and ADR 0032 (portfolio membership) — the invariants
  this slice must not disturb.

## Requirements

One numbering, used by the scope, the acceptance checks, the rubric and the
plan.

- **R1 — Owner control.** The Share tab lets the Task owner turn public
  sharing on and off and copy the link. Only the owner can do this. Each
  change is recorded as an audit event.
- **R2 — Anonymous read.** An anonymous visitor who opens a public Task's
  URL sees the Results and Sources tabs, with their full current content,
  and nothing else — no Plan, Share, History, chat, downloads of other
  kinds are unaffected (the Download control on Results stays, it is
  client-side only).
- **R3 — Same URL.** The public link is the normal app URL
  (`/projects/{id}/results`). There is no separate "public" URL. A
  signed-out visitor on the Plan path (`/projects/{id}`) of a public Task is
  redirected to `/results`.
- **R4 — The boundary stays closed.** Every route outside the public read
  surface behaves exactly as today. A private, archived or unknown Task
  gives an anonymous visitor the same indistinguishable 404 the tenancy
  rules give everyone else. Public Tasks never appear in anyone's listings
  because of this flag.
- **R5 — Revocation.** Turning public sharing off (or archiving the Task)
  makes the next anonymous request fail with the standard 404. No stream
  survives, because no stream is public.

## Design decisions (fixed by this contract)

- **D1 — A separate boolean, not a third `visibility` value.**
  `is_public` is a new column, orthogonal to `visibility` (`org|private`).
  Reasons: the task-033 portfolio invariant (cascade, recompute, the 409
  `visibility_conflict` rule) stays untouched with zero code changes; and a
  Task inside a Project — which cannot set its own `visibility` at all —
  can still be shared publicly. Public sharing and organisation sharing are
  independent facts about a row.
- **D2 — Optional authentication on the public surface only.** The public
  endpoints treat a request as anonymous only when the **raw
  `Authorization` header is absent**. Any present header — bad token,
  expired token, wrong scheme (`Basic …`), malformed value — still gets
  401, exactly as today (the signed-in refresh flow depends on this; and
  `HTTPBearer(auto_error=False)` alone cannot make this distinction, so
  the dependency checks the header, not the parsed credentials). No other
  route accepts a missing header.
- **D3 — Link-only.** `is_public` grants access to direct reads of that one
  Task. It plays no part in listings, search, portfolio reads, or the
  colleague and admin legs. There is no public index of public Tasks.
- **D4 — Signed-in callers get the public leg too.** Public means public: a
  signed-in user who is not the owner, not a colleague and not an admin can
  read a public Task the same way an anonymous visitor can, in the redacted
  shape — and sees the same slim two-tab view, not the full app shell (the
  frontend switches on `access = "public"`). The graded legs are checked
  first, so entitled readers see what they see today.
- **D5 — Redaction, and the view switch.** Reads served by the public leg
  return the redacted shape (§ Terms), including `access = "public"` — the
  one bit the frontend needs to render the public view for signed-in
  outsiders (D4). The admin trace is not involved: a public-leg read is
  not an admin read.
- **D6 — Revocation is a row check.** Every public-leg request checks
  `is_public` and `status` on the row at request time. There is no token,
  no signed link, no cache to invalidate.

## Public read surface

`GET /api/v1/projects/{id}` (redacted shape) plus these ten routes from
`read_models.py`: `funnel` · `landscape` · `groups` · `evidence` ·
`findings` · `sources/{source_id}` · `artefact` · `coverage` ·
`citations/{citation_key}/context` · `chunks/{chunk_id}/context`.

Explicitly **not** public: `decisions` (History tab), planning turns, runs,
check-ins, conversations and chat, the SSE event stream, all listings, all
portfolio routes, all writes except the owner's own `PATCH` of `is_public`.

## Scope / Out of scope

- **In (backend):** one additive migration (`project.is_public`);
  `core/schema.py`; `contract/projects.py` (`ProjectOut.is_public`,
  `ProjectUpdate.is_public`); `routers/projects.py` (PATCH handling + the
  audit event + optional auth on `GET /projects/{id}`);
  `routers/read_models.py` (optional auth + the public-or-graded gate);
  `routers/_access.py` (one narrow public-leg helper); `api/auth.py`
  (`get_optional_user`); the conformance tests and the new test battery.
- **In (frontend):** `ShareView.tsx` (Public link section); `routes.tsx` /
  `App.tsx` / `routes/` (public task routes + a public shell);
  `lifecycle.ts` + `LifecycleBar` usage (two-tab set when anonymous);
  `api/client.ts` / `authMiddleware.ts` (tokenless reads when signed out);
  regenerated `api/gen/types.ts` via `pnpm gen`.
- **In (docs):** `web-api.md`, `docs/deferred.md`, this task's artefacts.
- **Out:** portfolio-level public sharing; a public index or gallery of
  public Tasks; share tokens or signed URLs; public chat or Q&A; the
  waitlist and splash content; any change to the graded legs, the cascade,
  the admin trace, or listings; enrolment and ops CLI; mock-API public
  mode (the mock keeps serving the signed-in world; noted as a gap).

## Constraints & approval gates

Three gated changes need the owner's approval with this contract:

- **Schema:** one additive column, `project.is_public BOOLEAN NOT NULL
  DEFAULT FALSE`. No existing rows change meaning. Rollback = drop the
  column; turning every link off = one UPDATE.
- **Auth boundary:** the public read surface (11 routes) moves from
  "always 401 without a token" to "404 unless the row is public". The
  conformance test gains a third class — *conditionally public* — so the
  boundary stays pinned by tests, not by convention.
- **Public interface:** two additive fields on the project read shape
  (`is_public`, `access`) and one on the update shape (`is_public`). No
  existing field or route changes shape. (`access` was added by the
  adversarial-review adjudication — finding 3.)

No new dependencies. No new egress. No inference.

## Public / private boundary

Making a Task public exposes, to anyone on the internet with the link: the
Task name and question, the synthesis report, the source list and metadata,
the findings, and the **verbatim text excerpts** behind citations and chunk
context (the provenance sheet quotes acquired source text at excerpt
length). The Share tab copy must state this before the owner turns the
control on.

❓ **Owner decision:** keep the two excerpt routes
(`citations/{key}/context`, `chunks/{id}/context`) inside the public
surface (default: yes — a public report without its provenance quotes is a
weaker product), or hold them back for anonymous callers. The default
stands unless the owner rules otherwise at this gate.

Nothing in this slice writes personal data. The redacted shape keeps the
owner's display name and the portfolio ids out of anonymous responses.

## Model route

n/a — no inference in this slice.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — `is_public` earns its column: it changes the
  read gate. No other new flags.
- **Flag, don't drop** — gaps (mock-API public mode, public e2e) are named
  in `verification.md` and `docs/deferred.md`, not silently omitted.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: an approval gate above is hit beyond what this
contract approves, a blocker has no in-scope fix, scope would grow past
this slice (for example portfolio-level public sharing), or the turn/token
budget is spent. Report the blocker; don't push through.

## Acceptance checks

- `make verify` green (backend + frontend tests, typecheck, lint, build).
- Backend tests, by requirement:
  - **R1:** `PATCH {is_public}` — owner 200; colleague 403; anonymous 401;
    explicit `{is_public: null}` → 422 (the NOT-NULL rule, never a 500);
    audit event written on each flip; `is_public` on `ProjectOut`.
  - **R2/R4:** every public-surface route — anonymous 200 on a public
    active Task; anonymous 404 on a private, archived and unknown Task with
    byte-identical bodies; any present `Authorization` header that does
    not authenticate → 401 (bad token, expired, `Basic` scheme, malformed
    value — the D2 matrix); `decisions`,
    listings, SSE, chat, planning stay 401 for anonymous; listings for
    other signed-in users unchanged by the flag; the redacted shape holds
    (D5); a signed-in outsider reads a public Task (D4).
  - **R5:** flip off → the very next anonymous request 404s.
  - Conformance: the allowlist and the 404-sweep updated to carry the
    conditionally-public class; every route not on the public surface
    still 401s without a token.
  - Schema round-trip test updated for the new column.
- Frontend tests: Share tab control (owner-only, copy link); anonymous tab
  set is Results + Sources only; Plan path redirects to Results when
  anonymous; private Task keeps the stash-and-splash behaviour; the public
  view issues **only** public-surface GETs (no conversations, no SSE, no
  decisions — asserted on the request log of the test client); the query
  cache is cleared on sign-in/sign-out, so a just-signed-out owner never
  sees cached private data on a public or revoked URL; a signed-in
  outsider (`access = "public"`) gets the slim two-tab view.
- Manual (live-check pin, ~5 minutes, no full-chain e2e): in a signed-out
  browser open a public Task link → Results and Sources render; flip
  sharing off as the owner → the link now lands on the splash page; a
  private Task's link lands on the splash page.

## Verification evidence expected

`verification.md` with: command results, the manual-check notes above, the
diff summary, confirmation that no route outside the public surface changed
behaviour (the conformance run is the evidence), and the named gaps.

## Risk tier & review focus

**Tier 3** — an auth-boundary change on eleven existing routes, one
additive schema change, and a public-interface addition. Not Tier 4: the
migration is additive-only with a one-statement rollback, no existing route
changes shape, and revocation is instant. The step-4 ADR is written anyway
(D1/D2 are architecture). Review focus: the public-or-graded gate (the one
new predicate), the conformance boundary, redaction, and that listings and
the portfolio invariant are untouched. Adversarial review at contract and
plan stage; the security lane reads the access-layer diff.
