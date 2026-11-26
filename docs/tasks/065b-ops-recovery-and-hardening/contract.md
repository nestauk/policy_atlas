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

## Review (2026-11-23)

A fresh conversation ran the review stack on the one commit of this branch, against
`origin/dev`. The change touches sign-in recovery and infrastructure, so it ran with the
higher-risk set of lanes, not as a low-risk hotfix. `make verify` was green before the lanes
ran (4,992 backend tests).

### Lanes

| Lane | Reviewer | Result |
| --- | --- | --- |
| Contract verifier | `contract-verifier` subagent | Every claim above is built as written; nine notes, mostly documents the change made out of date |
| Security | a general-purpose Opus agent with the security review brief (the pinned `security-auditor` subagent was not available) | No finding at high confidence; eight candidates checked and rejected |
| Adversarial | Codex, read-only brief | One confirmed defect (deactivated account) |
| Code review | `/code-review` at medium | Nine findings |
| Over-engineering | `ponytail-review` | Nothing to cut |

### Findings and rulings

| # | Finding | Found by | Ruling |
| --- | --- | --- | --- |
| 1 | `user reissue` replaced the password of a deactivated account that had signed in before (Cognito keeps it `CONFIRMED`); the earlier never-signed-in rule had refused it | Codex, `/code-review`, contract verifier | **Fixed.** The command reads `Enabled` and refuses; one test |
| 2 | Nothing tested that Metabase's host reaches the firewall rules | `/code-review`, contract verifier | **Fixed.** The synth test passes the host and checks three hosts, and two hosts without it. The one expression in `infra/app.py` that builds the name still has no test |
| 3 | The deploy guide's capacity figure (987) was measured before the rules matched three hosts, and `aws wafv2 check-capacity` was not run for the new statement shape | contract verifier | **Fixed in the guide; the check is pending** (see below) |
| 4 | The deploy guide said "Never both headers at once"; the ops pages send both in report-only mode | contract verifier | **Fixed** |
| 5 | After a reissue on a signed-in account, "Forgot password" does not work until the person signs in (Cognito behaviour, from the reviewer's memory, not tested) | `/code-review` | **Fixed in the guide** |
| 6 | The rate limit comment gave the API measurement as the reason for a limit that now counts three hosts | contract verifier | **Fixed** (comment) |
| 7 | ADR 0048 Consequences and `readiness.md` still said only CloudFront sends a policy; the `reissue` help text promised more than the command accepts | contract verifier | **Fixed** |
| 8 | The known gaps were only in this file | contract verifier | **Fixed.** Four entries in `docs/deferred.md` |
| 9 | One rate count and one `waf.mode` for three hosts: Metabase traffic from one office address can use up the product's allowance | `/code-review`, Codex (as a deploy risk) | **Deferred** (`docs/deferred.md`); the count week is the control |
| 10 | A reissue does not sign out open sessions and writes no ops action log row | `/code-review` | **Deferred** (`docs/deferred.md`); already a known gap above. The owner ruled on 2026-11-23: not in this hotfix |
| 11 | The symbols `@ % + = -` can still be rewritten: `--` becomes a long dash in Apple apps; a first character of `-`, `+`, `=` or `@` reads as a flag or a spreadsheet formula | `/code-review` | **Declined.** The owner ruled on 2026-11-23: the set stays |
| 12 | `frame-src 'self'` with `frame-ancestors 'none'` would refuse a hidden sign-in frame | `/code-review` | **Declined.** Session renewal uses the refresh token, not a frame; the pending console pass on the ops host covers it |
| 13 | The backend treats any `OPS_CSP_MODE` other than `enforce` as report-only | `/code-review` | **Declined.** Only the stack sets it, and an unknown `csp_mode` fails `cdk synth` |
| 14 | The symbol test calls a private helper | `/code-review` | **Declined.** The same proof at the command boundary needs 200 stubbed Cognito calls |
| 15 | The one-host branch and the empty-list check in `waf.py` have no caller that needs them | `ponytail-review` | **Declined.** Each stops a deploy-time failure or a silent no-match |

### Second round: Codex re-review of the fixes

| # | Finding | Ruling |
| --- | --- | --- |
| 16 | The fix for finding 1 read Cognito only. A `user reactivate` that fails half way leaves a person marked deactivated in the database while Cognito has them enabled; `user reset-app` refuses in either case | **Fixed.** `user reissue` reads the database mark too; one test. An account with no row stays reissuable |
| 17 | A Cognito error from the new enabled check reaches the operator as a traceback, not a `refused:` line | **Deferred** (`docs/deferred.md`). `user create` and `user reset-app` call the same helper the same way, and nothing is changed when it fails; the repair belongs in the command line's entry point, for all three. The deploy guide now names the `AdminGetUser` permission |
| 18 | The deploy guide stated the "Forgot password" behaviour of finding 5 as a tested fact | **Fixed.** The sentence now says it is expected and not yet checked on our pool |

### Third round: Codex re-review of the second-round fix

| # | Finding | Ruling |
| --- | --- | --- |
| 19 | The module header of `ops/commands.py` still said `user reissue` takes no connection and listed its old Cognito calls | **Fixed** (docstring) |
| 20 | If Cognito returned an account with no `sub` attribute, the database check would find no row and the reissue would continue | **Declined.** Cognito gives every account a `sub`, and the Cognito enabled check still runs. The owner ruled on 2026-11-23 that this hotfix takes no further changes; a guard that refuses an empty `sub` would close it |

This was the last of the three rounds the review process allows.

### Evidence after the fixes

- `make verify` on the tree with the first- and second-round fixes: green. Backend 4,994
  passed; `infra` 173 passed.
- After it, only the docstring of finding 19 and this file changed; `make verify-fast` passed.
- One earlier run had one failure, `tests/ops/test_db_role.py` (`role "pa_ops" is not
  permitted to log in`). The test is not part of this change, passed alone, and passed in the
  next full run. The `pa_ops` login is shared by every test database on the local Postgres.

### Firewall capacity check

`aws wafv2 check-capacity --scope REGIONAL` on the six rules of the synthesised staging template
(three hosts), run by the owner on 2026-11-23: **1,003** of 1,500 units. The firewall service
accepts the new rule shape. The deploy guide carries the figure.

No knowledge record was written: no finding is a verified fact that outlasts this change. The
"Forgot password" behaviour in finding 5 would be one after a live check.

### Pending (owner)

- The items already listed as pending above.
