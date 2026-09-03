# Task contract: 036-splash-page

> **Status:** approved. Written 2026-09-03, after the build — the owner built
> this slice directly and approved the schema, auth-boundary and public-API
> changes in the 036 review discussion (2026-09-03). Review record:
> [review.md](review.md). ADR: none (no architecture decision beyond what is
> recorded here and in the web-api spec).

## Goal

Give Policy Atlas a public front door. A visitor who is not signed in sees a
splash page that says what the tool is, lets them request access, and lets an
existing user sign in. The signed-in app itself does not change.

## Deliverable

One PR containing:

- A splash page at `/` for logged-out visitors: hero copy, an animated
  fold-mark constellation, a Request-access form, a Sign-in button, and
  links (Nesta, project page, Substack, privacy, terms).
- A public `POST /api/v1/waitlist` endpoint and a new `waitlist_entry`
  table that stores access requests (name, email, optional organisation,
  intended use).
- Routing split into a public router (splash, privacy, terms) and the
  authenticated app router; deep links are stashed and restored after
  sign-in.
- The fold-mark logo in the app nav, animated while any run is active.

## Scope / Out of scope

- **In:** splash views (`frontend/src/views/splash/`), fold-mark components
  (`frontend/src/ui/brand/FoldMark*`), router split (`routes.tsx`, `App.tsx`,
  `frontend/src/routes/`), auth providers (splash instead of a hard gate),
  waitlist contract/router/migration/tests (backend), privacy-notice
  addition, `web-api.md` § Waitlist.
- **Out:** any admin view of the waitlist (ops read the table directly);
  automatic promotion from waitlist to account (enrolment stays the ops CLI
  from task 033); email verification or notification sending; feature-steps
  screenshots (behind a flag until images exist).

## Constraints & approval gates

All three gated changes were approved by the owner on 2026-09-03:

- **Schema:** one additive table (`waitlist_entry`), unique on email. No
  existing table changes. Rollback = drop the table.
- **Auth boundary:** `POST /api/v1/waitlist` is the first intentionally
  public data route. Everything else stays behind the bearer token; the API
  conformance test pins this.
- **Public interface:** the new endpoint is additive; no existing route
  changes.

No new dependencies. No new egress — the endpoint writes to our own
database only. Spam controls: field length caps, one row per email, and a
hidden honeypot field (a filled honeypot gets a fake success and stores
nothing). Upgrade path if real spam appears: a WAF rate rule
(`docs/deferred.md`).

## Public / private boundary

Waitlist rows are personal data: they live in the database only, are never
committed, and the API response echoes only the email — organisation and
intended use are not sent back, so logs do not amplify them. The privacy
notice (§ 3) tells requesters what we collect and why.

## Model route

n/a — no inference in this slice.

## Acceptance checks

- `make verify` green (backend + frontend tests, typecheck, lint, build).
- Backend: waitlist tests cover create, duplicate → 409, invalid email →
  422, optional organisation, and the honeypot storing nothing.
- Frontend: splash and form tests; the conformance test confirms every
  other route still requires auth.
- Manual: load the splash logged out, submit a request, sign in, and check
  a deep link returns you to the page you asked for.

## Risk tier & review focus

**Tier 3** — public untrusted input, an auth-boundary change and a schema
addition. Not tier 4: the migration is additive-only (no existing data
touched, trivial rollback) and the public-API change adds one route without
touching any existing one. Review focus: the public route's input handling,
the auth boundary staying closed everywhere else, and PII hygiene. The
review ran 2026-09-03 ([review.md](review.md)); all findings fixed or
accepted by the owner.
