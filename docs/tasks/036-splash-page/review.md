# Review — task 036 splash page (pre-PR, working tree on `task/036-splash-page`)

Reviewed 2026-09-03. Scope: the uncommitted working-tree changes (the committed
part of this branch is task 034, reviewed separately).

**What this slice does:** a public splash page for logged-out visitors (hero +
animated fold-mark constellation), a public `POST /api/v1/waitlist` endpoint
with a new `waitlist_entry` table, a Request-access form, split routers
(public vs authenticated), and the fold-mark logo in the app nav (animated
while a run is active).

**Verdict (final, 2026-09-03): all issues resolved.** Blocking issues fixed;
spam honeypot and privacy-notice addition implemented after owner approval.
Verified: frontend 510/510, backend waitlist + conformance green, lint 0
errors, tsc clean, `make drift-check` OK. The contract is written
([contract.md](contract.md)) and the PR is open.

---

## Blocking — broken right now (all FIXED 2026-09-03)

1. **24 frontend tests fail** (`pnpm vitest run`: 486 pass, 24 fail).
   Two causes, both in test code, not product code:
   - `AppShell.test.tsx` and `AppShell.errorBoundary.test.tsx` (22 failures):
     AppShell now calls `useProjects`, but the tests' `vi.mock("../api/queries")`
     does not export it. Add `useProjects` to the mock.
   - `WaitlistForm.test.tsx` (2 failures): the tests look for a label
     `/role or reason for access/i`, but the label is now "What would you like
     to use Policy Atlas for?". Update the queries.

2. **Lint fails with 7 errors.**
   - `SplashField.tsx:152` — unused `_c`, `_y`, `_r` destructured names.
   - `react-hooks/set-state-in-effect` errors in `FoldMarkAnimated.tsx`
     (lines 49, 62) and `SplashField.tsx` (lines 57, 157).
   `make verify` cannot pass until these are fixed or explicitly waived.

3. **Duplicate-email race returns a 500, not a 409.**
   `routers/waitlist.py` does a SELECT then an INSERT. Two simultaneous
   submits with the same email: both pass the SELECT, one INSERT hits
   `uq_waitlist_entry_email` and the user gets a 500. *Fixed:* the SELECT is
   gone; the INSERT catches `IntegrityError` and raises `already_registered`
   — the unique constraint is now the only arbiter.

## Owner decisions needed before merge

4. **The privacy notice does not mention the waitlist.** This is the first
   public PII intake (name, email, organisation, free-text reason), and
   `/privacy` says nothing about it — no purpose, no retention. The form also
   has no privacy link or consent line near Submit. Given this project's
   privacy-notice history (033 escalations), this needs an owner ruling before
   merge, not after.

5. **No spam protection on the public endpoint.** Anyone can script-fill
   `waitlist_entry` (field lengths are capped, but emails are free to
   invent). Options: a WAF/CloudFront rate rule, a honeypot field, or accept
   the risk for a private beta and record it in `docs/deferred.md`. Pick one
   explicitly.

6. **Email enumeration.** The 409 tells any visitor whether an email is
   already on the waitlist. Probably acceptable for a waitlist; flag it so
   the acceptance is deliberate.

## Scope creep — owner ruled 2026-09-03: keep the changes, log them

7. **`synthesise.py` nav_label change reverses a task-034 decision.** Rev 8
   of the 034 contract said an over-long `nav_label` is *rejected, never
   clamped* (the old test cites "rev 8 M5"). This diff flips it to
   truncate-with-ellipsis. **Logged:** owner accepted 2026-09-03; recorded
   as deviation D-8 in `docs/tasks/034-synthesis-report/verification.md`.
   The PR description should still name it.

8. **Unrelated riders:** the two re-run bug entries in `docs/deferred.md`
   (good to keep — they are docs) and the `.cursor/plans` gitignore line.
   Harmless, but name them in the PR description so they don't look like
   accidents.

## Process

9. **There is no `docs/tasks/036-splash-page/` contract or rubric.** This
   slice changes the schema (new table + migration), the auth boundary (first
   public write route), and the public API — all things AGENTS.md says need
   approval. **Resolved 2026-09-03:** owner approvals recorded and the
   contract written after the build — see [contract.md](contract.md).

## Minor — resolved 2026-09-03 except where noted

10. **Dev-token sign-in loses the return path.** `RequireAuth` and the
    public catch-all stash the attempted URL; the OIDC flow restores it, but
    the dev-token flow never reads it — a dev deep link always lands on `/`.
    Dev-only; ACCEPTED as-is.
11. **AppShell projects-list fetch for the logo — KEPT, comment corrected.**
    On a second look the cost is small: AppShell is the layout route, so it
    mounts once per session (not per navigation). Real cost: one list fetch
    per session plus useProjects's own 15s poll while a run is active — and
    the poll is exactly what keeps the logo honest. The store's run stream is
    per-project (no global signal), so this is already the simple option.
    The over-claiming comment is rewritten to state the true cost.
12. **Dead code in `SplashField` — FIXED.** The no-op `sig`/`lastSig` check
    is deleted; the loop now just recomputes and sets state each frame,
    which is what it always did in effect. (Per-frame re-render is the
    design — rotation is interpolated per frame.)
13. **Grammar — FIXED** ("Tell us how you would use Policy Atlas").
14. **Dead export — FIXED:** the deprecated `router` export is deleted
    (verified: no importers).
15. **Possible stale URL on dev sign-out** (unverified): both routers are
    created at module load, so signing out on a deep route swaps to a
    `publicRouter` whose internal location may predate the navigation — the
    splash shows but the URL bar may keep the old path. OIDC sign-out does a
    full-page redirect, so this can only bite dev mode. Worth a manual check.

## Checked and fine

- Backend: `tests/api/test_waitlist.py` + conformance tests pass (72) against
  the test DB. The conformance allowlist correctly names `/api/v1/waitlist`
  as the only public data route.
- `WaitlistSignupOut` deliberately omits organisation and role/reason — good
  PII hygiene in responses.
- Input caps (`extra="forbid"`, length maxes, email shape check) are sane for
  a public POST. `get_conn` commits/rolls back correctly.
- The migration chains onto the current head and the table matches
  `core/schema.py`.
- The `--color-aqua` token change only affects the splash (no other usage —
  verified by grep).
- Mock mode covers the form: `installMockApi` patches fetch globally and the
  mock handles `POST /api/v1/waitlist`.
- The spec update in `web-api.md` matches the built behaviour.
- `frontend/tsc` passes.

---

## Proposals — owner approved and implemented 2026-09-03

### Spam (issue 5) — honeypot IMPLEMENTED; WAF rule logged in deferred.md

Recommendation, cheapest first:

1. **Honeypot field** (~15 lines, no dependency, invisible to users): add a
   hidden text input (e.g. `website`) to the form that humans never see.
   Bots fill it. The backend accepts the optional field and, when it is
   non-empty, returns a fake 201 without inserting — the bot learns nothing.
2. **Record the upgrade path in `docs/deferred.md`:** a CloudFront/WAF
   rate-based rule on `POST /api/v1/waitlist` if real spam appears. Infra
   change, no app code.

Not recommended: CAPTCHA (dependency + UX + GDPR cost, overkill for a
private-beta waitlist) and an in-app rate limiter (needs shared state across
containers; the WAF does it better).

The existing defences already bound the damage: field length caps,
`extra="forbid"`, one row per email.

### Privacy notice (issue 4) — ADDED to § 3 of `/privacy`

The text as shipped:

> **Access requests.** If you ask for access to Policy Atlas through the
> "Request access" form, we collect your name, your email address, your
> organisation (if you give it), and what you tell us about how you would
> use the tool. We use this information only to review your request and to
> contact you about access to the beta. We keep it until the private beta
> ends, or until you ask us to remove it (contact the DPO at the address
> above). We do not share it outside Nesta. The lawful basis is our
> legitimate interest in responding to your request.

A one-line pointer on the form near Submit was tried and removed (owner
call, 2026-09-03) — the splash footer already links to the notice.

## Fixes applied 2026-09-03 (this review, post-discussion)

- Backend: waitlist duplicate race → `IntegrityError` → 409 (issue 3).
- Tests: `useProjects` added to the two AppShell test mocks; WaitlistForm
  label queries updated (issue 1). Frontend suite 510/510.
- Lint: `FoldMarkAnimated` and `SplashField` restructured (no setState in
  effect bodies, no unused vars); dead `sig` check deleted (issues 2, 12).
- Copy: form label grammar (issue 13).
- Cleanup: deprecated `router` export deleted (issue 14); AppShell logo
  comment corrected (issue 11).
- Logged: nav_label truncation recorded as D-8 in the 034 verification
  (issue 7).
- Verified after the changes: frontend vitest 510/510, backend waitlist +
  conformance tests green, eslint 0 errors, tsc clean, ruff + mypy clean on
  the touched backend file.
