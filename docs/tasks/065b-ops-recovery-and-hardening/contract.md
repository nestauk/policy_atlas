# Task 065b: ops hotfix (account recovery commands, and firewall and browser policy cover)

**Risk tier:** low (a hotfix, built in the `hotfix/ops-metabase-waf-csp` branch at the
owner's request on 2026-11-23). This one file holds the scope, the owner ruling and the
evidence; there is no separate rubric or verification file.

This hotfix holds two separate changes:

1. **Account recovery:** operator commands for accounts with no mailbox (the sections that
   follow).
2. **Hardening:** the firewall and the Content Security Policy now cover the ops pages and
   Metabase (at the end of this file, under "Second change").

## Why

Some accounts have an address with no mailbox (shared test accounts). Sign-in with an authenticator app (task 064d) works for
them, because the code comes from the app and not from email. "Forgot password" does not
work, because Cognito sends the reset code by email. An operator had to call the AWS
command line directly.

## What changed

- `make user-reset-app ENV=<env> EMAIL=<address>` (or `SUB=<cognito subject>`): a make
  wrapper for the `user reset-app` command that task 064d built. No change in behaviour.
- `make user-reissue ENV=<env> EMAIL=<address>`: `user reissue` now also accepts an account
  that has already signed in (Cognito status `CONFIRMED`). One command resets a password in
  both cases, with no extra flag.
- Temporary passwords (from `user create` with a manual invite and from `user reissue`) now
  use only the symbols `@ % + = -`. The earlier set also had `! # ^ * _`, which a shell or a
  chat app can rewrite or remove on the way to the person (owner request, 2026-11-23). The
  length stays 20 characters.

## Owner ruling (2026-11-23)

An operator may replace the password of a signed-in account. This relaxes the earlier rule
that `user reissue` serves only accounts that never signed in. A first version asked for
an explicit flag (`CONFIRMED=1`) for a signed-in account; the owner ruled it out the same
day: an operator who resets a password does not care which state the account is in. The
limits that stay:

- The new password is always temporary: the person must choose their own at the next
  sign-in.
- The command line still accepts no password; it creates one and prints it once.
- `RESET_REQUIRED` and `UNCONFIRMED` accounts are refused.
- No new AWS permission: it uses `AdminSetUserPassword`, which operators already hold.

## Out of scope / known gaps

- Nothing stops an operator from resetting the password of a person who has a working
  mailbox and could use "Forgot password". The runbook says to prefer that route.
- A reissue does not sign the person out of sessions that are already open.
- A reissue writes no row in the ops action log (it never did); the operator's AWS identity
  is in the command trace only.
- Giving these accounts a real mailbox (an alias that forwards), which would make "Forgot
  password" work with no operator.

## Evidence

- `backend/tests/ops`: 200 passed (stubbed Cognito client); linter clean.
- `make verify` not run for this change.
- The password symbol change: `backend/tests/ops` passed again after it; not part of the
  Codex reviews above (the owner runs a separate review).
- Staging live run, 2026-11-23 (owner): `make user-reissue ENV=staging
  EMAIL=<a shared test account>` on a `CONFIRMED` account worked. The same command run
  from the `dev` checkout, which does not have this change, refused the account as before.
- **Pending:** one live run of `make user-reset-app` on staging.

## Files

`Makefile`, `backend/src/policy_atlas/ops/cli.py`, `backend/src/policy_atlas/ops/commands.py`,
`backend/tests/ops/test_make_wrappers.py`, `backend/tests/ops/test_ops_commands.py`,
`infra/DEPLOYMENT.md`.

## Second change: firewall and Content Security Policy for the ops pages and Metabase

Built in the same branch at the owner's request on 2026-11-23. **Risk tier:** medium
(infrastructure and response headers), handled as a hotfix: this section is the scope and
the evidence, and the reasons are in the amendments to ADR 0047 and ADR 0048.

### Why

Tasks 064b and 064c protected the public website and the API. A check on 2026-11-23 showed
that the ops pages and Metabase got little from either:

- The firewall (AWS WAF, the web application firewall) sits on the shared load balancer, but
  its general rate rule and managed rule groups matched the API host only.
- The Content Security Policy (CSP, the header that tells a browser where a page may load
  content from) is sent by CloudFront, which serves only the public website. The ops pages
  sent a framing ban and nothing else. Metabase sends its own policy.

Both sites keep their allowlists of addresses. This change adds a second layer.

### What changed

1. **Firewall hosts.** The general rate rule and the three managed rule groups now match a
   list of hosts: the API, the ops pages and, where the analytics stack is deployed,
   Metabase. The rate rule counts one address across the three hosts together. The waitlist
   rules do not change.
2. **A policy for the ops pages.** The app stack builds the ops policy with the same
   function as the website's and gives it to the ops container
   (`OPS_CONTENT_SECURITY_POLICY`, `OPS_CSP_MODE`). The ops service sends it. It has no API
   origin, no CAPTCHA hosts and `frame-ancestors 'none'`.
3. **One mode key.** The existing `csp_mode` governs both sites. In report-only mode the ops
   pages keep the enforced framing ban they had before.

No config value changes: both environments stay at `waf.mode: "count"` and
`csp_mode: "report-only"`, so a deploy blocks nothing new.

### Out of scope / known gaps

- `waf.mode` is one switch for the three hosts. Metabase sends long queries that a managed
  rule may match, so the count week must include the ops pages and Metabase before the
  switch to block (the deploy guide says how).
- The ops pages get no `Referrer-Policy` or `Permissions-Policy` header.
- The API's JSON responses still carry no policy (`docs/deferred.md`).
- Production has no ops host yet; it gets this with the release that brings the ops service.

### Evidence

- `infra`: `make test`, 173 passed.
- `make verify-fast` passed on the branch with both changes; `mypy` and
  `make okf-validate` clean.
- Codex review of the working tree with both changes, 2026-11-23: no correctness issue
  found.
- The full `make verify` not run. No `cdk synth` against an AWS account.
- **Pending (owner, after a staging deploy):** the browser console pass on
  `https://ops.<domain_name>` (deploy guide, "The ops pages"), and the ops pages and
  Metabase in the firewall count week.

### Files

`infra/app.py`, `infra/infra/policy_atlas_stack.py`, `infra/infra/components/waf.py`,
`infra/infra/components/security_headers.py`, `infra/tests/unit/test_waf.py`,
`infra/tests/unit/test_security_headers.py`, `infra/tests/unit/test_service_wiring.py`,
`infra/tests/unit/test_synth.py`, `backend/src/policy_atlas/api/app.py`,
`backend/src/policy_atlas/api/settings.py`, `backend/tests/api/test_service_role.py`,
`backend/README.md`, `infra/DEPLOYMENT.md` (firewall and security header sections),
`docs/deferred.md`, ADR 0047 and ADR 0048 (amendments).
