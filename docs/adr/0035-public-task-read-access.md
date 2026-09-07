# ADR 0035 — Public Task read access via an `is_public` flag

- **Status:** Accepted — 2026-09-04 (owner, with the 037 combined
  contract+plan gate)
- **Decision 5 amended** by [ADR 0036](0036-one-vocabulary-across-code-schema-api-and-screen.md)
  — 2026-09-05 (task 038): the public paths are `/tasks/{id}/result` and
  `/tasks/{id}/sources/*`, with no redirects from the paths written below.
- **Date:** 2026-09-04
- **Task:** 037-public-projects
- **Relates to:** [ADR 0033](0033-organisation-tenancy-and-global-admin-read.md)
  (the graded read; unchanged), [ADR 0031](0031-portfolio-layer-above-the-project.md)
  / [ADR 0032](0032-portfolio-membership-many-to-many.md) (the portfolio
  invariant; unchanged), task 036 (the public router and the first public
  endpoint; extended).

## Context

Owners want to share one Task's results with people outside the app. Until
now every data route required a bearer token except `POST /api/v1/waitlist`
(task 036). Tenancy (ADR 0033) grades reads as owner ∪ same-org ∪ admin;
`visibility` is `org|private` and is coupled to portfolio membership by the
task-033 invariant — a Task inside a Project cannot set its own
`visibility` at all. The pre-rewrite v2 app used a separate public URL;
nothing of it survives, and a second URL splits the link space.

## Decisions

1. **Public is a separate boolean, not a third `visibility` value.**
   `project.is_public BOOLEAN NOT NULL DEFAULT FALSE`. Organisation sharing
   and public sharing are independent facts about a row. The portfolio
   cascade, the membership recompute and the 409 `visibility_conflict`
   rule are untouched, and a Task inside a Project can still be public.

   *Rejected:* `visibility = 'public'`. It collides with the invariant
   (members carry their portfolios' visibility), so a Task in a Project
   could never be public, and every cascade path would need a third case.

   *Rejected:* signed share links / share tokens. A second credential
   system with its own revocation problem; a row check needs none.

2. **One conditionally-public read surface, optional auth, same paths.**
   Exactly eleven GET routes accept a missing `Authorization` header:
   `GET /projects/{id}` plus the `read_models.py` routes except
   `decisions`. Anonymous means the raw `Authorization` header is
   **absent**; any present header that does not authenticate — bad token,
   wrong scheme, malformed value — still 401s. Anonymous callers pass only
   the check `is_public AND status='active'`; failure is the standard
   indistinguishable 404. Signed-in callers keep the graded read first and
   fall back to the public check.

3. **Link-only.** `is_public` plays no part in listings, search, portfolio
   reads, or the colleague and admin legs. There is no public index. A
   public-leg read is not an admin read and is not traced as one.

4. **Redaction on the public leg, with an explicit marker.** Reads served
   by the public check return `owner_display = null`, `portfolio_ids = []`,
   `is_owner = false` and `access = "public"` (graded reads say
   `access = "full"`). The marker is the one bit the frontend needs to
   show signed-in outsiders the same slim public view as anonymous
   visitors, instead of the full app shell.

5. **The frontend keeps one URL.** The task-036 public router gains the
   same `/projects/{id}/results` and `/projects/{id}/sources/*` paths,
   rendered by the existing views in a slim two-tab shell. A private,
   archived or unknown Task keeps the stash-and-splash behaviour.

## Consequences

- A public Task exposes its report, source metadata, findings and the
  verbatim excerpt routes (citation/chunk context) to anyone with the
  link; the Share tab states this before the owner turns it on (owner
  accepted the excerpt default, 2026-09-04).
- The conformance test gains a third route class (*conditionally public*)
  beside "always 401" and the waitlist allowlist; the boundary stays
  pinned by tests.
- Revocation is instant: flip the flag (or archive) and the next anonymous
  request 404s. Rollback of the whole feature is one dropped column.
- The "read-only/public links" part of `docs/deferred.md` § Export &
  sharing is discharged; portfolio-level public sharing, a public index
  and public chat stay deferred.
