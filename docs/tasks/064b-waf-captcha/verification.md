# Verification: 064b-waf-captcha

Evidence for the second slice of the 064 security hardening programme. Contract
[contract.md](contract.md) (revision 2), plan [plan.md](plan.md) (draft 2), rubric
[rubric.md](rubric.md), ADR [0047](../../adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md).
Built 2026-11-17 on `task/064b-waf-captcha`. Public-safe: no addresses, keys or account ids.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline, before any change) | pass | backend 4,830 passed · 1 skipped; infra 119 passed; frontend 1,992 tests in 138 files; build green. Docker had to be started first (the compose database was down). |
| `make deploy-build-guard-test` (baseline) | pass | migration-wait and guard PASS. |
| `make -C infra test` (Phase 1 gate) | pass | 125 passed (6 new in `tests/unit/test_waf.py`). Negative check: `GENERAL_RATE_LIMIT = 2999` makes `test_w3_…` fail; restored to 3,000. |
| `make deploy-build-guard-test` (Phase 2 gate) | pass | three PASS lines: migration wait, `test-waf-report`, deploy guard. `deploy.sh check` passes for `staging` and `prod`; with staging's `waf.mode` set to `"audit"` it fails naming `backend.waf.mode` (Codex's negative check; config restored). |
| `make verify-fast` + `pnpm typecheck && pnpm lint && pnpm test` (Phase 3 gate) | pass | backend 4,793 passed (fast suite); mypy 562 files clean; ruff clean; frontend 1,997 tests (5 new); one pre-existing eslint warning in `SplashField.tsx`. |
| `make audit` (exit) | pass | |
| `make deploy-build-guard-test` (exit) | pass | |
| `make verify` (step-6 exit) | pass | see § Exit gate below |
| `make verify` (after the review fixes) | pass | second run; the first hit the known ToC fan-out flake, § Exit gate |

## Checks beyond the build

- **Deterministic tests, one per problem** (rubric item 6):
  - W1 `test_w1_web_acl_association_config_pin_and_validation`: the shipped staging
    template has one `AWS::WAFv2::WebACL` (REGIONAL, `policy-atlas-v3-api`, default allow)
    and one association whose `ResourceArn` is the shared load balancer's SSM parameter;
    the prod config synthesises both; `enabled: false` synthesises no `AWS::WAFv2::*`
    resource and no log group; a missing key, `mode: "audit"`, a string `enabled`,
    `captcha` without `enabled`, and `None` each raise `ValueError`; both environments'
    `waf` blocks in `pa_config.json` are pinned (`staging` count + captcha on, `prod` count
    + captcha off).
  - W2 `test_w2_…`: limit 50, window 300, aggregate `IP`, `Block` in both modes, scope-down
    = `POST` and the path with `URL_DECODE` (0) then `LOWERCASE` (1).
  - W3 `test_w3_…`: limit = `GENERAL_RATE_LIMIT` ≥ 3,000, scope-down on the lower-cased
    `host` header equal to the API host, `Count` in count mode and `Block` in block mode.
  - W4 `test_w4_…`: the three groups at priorities 40/50/60, `OverrideAction` `Count` or
    `None` per mode, no `Action`, scope-down = host AND NOT(`/healthz` OR `/readyz`
    prefix), `SizeRestrictions_BODY` overridden to count on the common group in both modes
    and no override on the other two.
  - W5 `test_w5_…`: the CAPTCHA rule absent with `captcha: false` (prod config and a staging
    variant), present with `true`, priority below `waitlist-rate`, the same statement as the
    rate rule's scope-down, `Captcha` action, immunity 1,800, `TokenDomains` equal to
    `[domain_name]` for both `v3.policyatlas.uk` and `policyatlas.uk`, and absent when off.
  - W6 vitest (`WaitlistForm CAPTCHA`): no script URL → no box, no script tag, headers
    exactly `{Content-Type}`; configured + solved → `x-aws-waf-token: tok-1` and one render
    into the box; `405` + `x-amzn-waf-action: captcha` → "Please solve the puzzle again" and
    a second render; plain `405` → the generic message and one render; script never loads →
    one `<script data-waf-captcha>` with `src` ending `/jsapi.js` (no double slash), the
    reload message after 10 s with submit disabled and no fetch, then a late `load` clears
    the message, renders, and re-enables submit. Backend
    `test_cors_preflight_allows_the_waf_captcha_token_header_with_content_type`: an
    `OPTIONS` preflight asking for `content-type,x-aws-waf-token` is allowed for both.
  - W7 `scripts/test_deploy_build_guard.sh`: with `PA_DEPLOY_GUARD_WAF_CAPTCHA=1` each of
    the two values missing fails naming it; with `0` both missing passes; the key lookup
    through `PA_DEPLOY_WAF_KEYS_ONLY=1` against a stubbed `aws` takes the key whose token
    domains equal `[v3.policyatlas.uk]` and not the other key, and with only a
    `policyatlas.uk` key fails naming `create-api-key --scope REGIONAL --token-domains
    v3.policyatlas.uk`.
  - W8 `test_w8_…`: log group `aws-waf-logs-policy-atlas-v3`, retention 30 days, delete on
    removal; the logging configuration's `ResourceArn` is the ACL, its one destination
    contains the group name and not `:*`, the filter is `DROP` by default with one
    `KEEP`/`MEETS_ANY` filter on exactly `{COUNT, BLOCK, CAPTCHA, EXCLUDED_AS_COUNT}`, and
    it depends on the log group; every rule's metric name is its rule name.
    `scripts/test_waf_report.sh`: against recorded output the report prints the
    `managed-common` metric row (`3 0 0`) and the `SizeRestrictions_BODY` row from the log
    query (a counted rule inside a group), and `--addresses` adds `httpRequest.clientIp` to
    the query.
- **Manual / browser:** the frontend-designer ran Vite alone with the two values set and a
  Playwright stub answering `jsapi.js` with a placeholder widget, at 1280 and 400 px, light
  and dark, before and after the first focus, and in the unavailable state. Screenshots in
  `evidence/` (`placement-stub-1280.png`, `placement-stub-400-unavailable.png`), which the
  repo's `.gitignore` keeps out of git by rule (`docs/tasks/*/evidence/`); they are kept
  locally and can be attached to the PR. They show placement only; the real AWS widget needs the real key over HTTPS and is the
  staging check's job.
- **The CDK property names** were right as planned (`scope`, not `scope_`, is accepted by
  the installed `aws_cdk` 2.261 for `CfnWebACL`).

## End-to-end command

Local end to end (the exact commands run, from the repo root, Docker up):

```
make verify
make deploy-build-guard-test
make audit
cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

The contracted live end to end runs on staging after the deploy (§ Staging live check
below) and could not run in this conversation: it needs the owner's two hand steps per
account and a push to `dev`.

## Phase 0 measurement (W3, owner ruling)

**Run 2026-11-17, from a console export.** The staging SSO token had expired, so the owner
ran the query in the CloudWatch console (Log Analytics, log group
`/policy_atlas_v3/application`, last 14 days) and exported the result as CSV into this
folder (gitignored by `*.csv`, deleted after the read).

The contract's per-address query cannot work on staging yet: the API logs the load
balancer's private address, not the visitor's, because `--proxy-headers` (task 064a, PR
#120) is not deployed there. A first raw export confirmed it: three addresses in five
hours, all private. So the measurement took the **site-wide** peak instead, which bounds
any single address from above:

```
SOURCE logGroups(namePrefix: ["/policy_atlas_v3/application"], class: "STANDARD") START=-14d END=0s |
fields @message
| parse @message /:\d+ - "(?<method>[A-Z]+) (?<path>\S+)/
| filter ispresent(path) and path not like /^\/(healthz|readyz)/
| stats count(*) as requests by bin(5m) as window
| sort requests desc
| limit 10000
```

| Window (UTC) | Requests, all clients, health paths excluded |
|---|---|
| 2026-11-10 14:35 | 520 |
| 2026-11-09 14:35 | 474 |
| 2026-11-09 15:25 | 450 |
| 2026-11-16 21:10 | 400 |
| 2026-11-04 14:25 | 400 |

1,699 windows from 2026-11-04 to 2026-11-17; median 17, 95th percentile 117. The same
query on production (owner export, same day): 343 windows from 2026-11-03 to 2026-11-17,
peak **264** (2026-11-06 14:05 UTC), median 14, 95th percentile 94, so staging's peak is
the higher one and the one the limit is derived from. Ten times the staging peak is
5,200, rounded up to a thousand: **`GENERAL_RATE_LIMIT = 6000`**
(`infra/infra/components/waf.py`). Contract W3 row, ADR 0047, `infra/DEPLOYMENT.md` and
`docs/deferred.md` say the same. A per-address re-measurement after 064a reaches staging
can only lower the figure, never below 3,000; it is one constant and a normal deploy.

## Staging live check (contract § Acceptance checks)

**Hand steps done 2026-11-18.** The deploy role in both accounts (`GithubOIDCRole`) already
allows `wafv2:ListAPIKeys`: it has `AdministratorAccess` (checked with
`iam simulate-principal-policy`; wider than DEPLOYMENT.md § 1 asks for, a separate task). The
owner created the staging API key for `v3.policyatlas.uk`; `list-api-keys` returns it with the
account's CAPTCHA script URL. **Pending** the merge of #120 and this PR to `dev`. To record afterwards, in this order:

1. W1: `aws wafv2 get-web-acl` lists the six rule names; the association points at the
   load balancer.
2. W5, W6: the puzzle on first focus (one screenshot into `evidence/`); a submission after
   solving gets the thanks message; `curl -i -X POST https://api.v3.policyatlas.uk/api/v1/waitlist -H 'content-type: application/json' -d '{}'`
   gets `405`, `x-amzn-waf-action: captcha` and the CORS headers; the same with
   `/api/v1/waitlis%74` gets the same refusal.
3. W2: with a token from the browser, a loop of posts from one address gets `403` after
   about fifty.
4. W3, W4: zero blocked requests in the first hour; metrics per rule; one request to the
   Metabase host matches no rule; `curl -H 'Host: api.v3.policyatlas.uk:443' https://api.v3.policyatlas.uk/api/v1/tasks`
   (the host-header edge case) is counted by `general-rate` like any other request.
5. The deliberate pass (sign in, task list, one chat message over 8 KB, a plan edit, a
   theory-of-change image import, a public task view) then
   `AWS_PROFILE=pa_staging scripts/waf_report.sh staging 1`: only the body-size rule
   counted, named as `SizeRestrictions_BODY`, not just its group. Paste the output here
   with addresses removed, and one real log record (addresses removed) showing the field
   that names the rule inside a group, so the report's query is confirmed against the real
   field names (plan P8; the query assumes `ruleGroupList.N.terminatingRule.ruleId` and
   `ruleGroupList.N.nonTerminatingMatchingRules.0.ruleId`).
6. W8: the log group has entries for the pass and none for ordinary requests.
7. The count week: recorded as **pending** (a follow-on config change switches `waf.mode`).
8. The emergency switch, once: `disassociate-web-acl`, confirm the report says the ACL is
   absent from the load balancer or counts nothing, then `associate-web-acl` as
   DEPLOYMENT.md shows, and confirm it counts again.

## Diff summary

Four commits on the branch, one per build phase, plus the docs:

- **Phase 1 (infra)** — `infra/infra/components/waf.py` (new, 270 lines): `ApiFirewall`
  validates `backend.waf`, and when enabled creates the web ACL (six rules, or five without
  the CAPTCHA), the association on the imported load balancer's ARN, the log group and the
  filtered logging configuration. `policy_atlas_stack.py` instantiates it after the shared
  ALB import; nothing new reaches the container. `pa_config.json` gains the three keys for
  both environments. `tests/unit/test_waf.py` (new) and one namespacing case.
- **Phase 2 (scripts)** — `deploy.sh`: config validation of `backend.waf` in the Python
  reader (a seventh exported value, `WAF_CAPTCHA`); `resolve_waf_captcha_values` called
  before any stack deploy when the CAPTCHA is on; the production build guard requires the
  two values then; two harness lines. `test_deploy_build_guard.sh` gains the on/off and
  key-lookup cases. `waf_report.sh` and `test_waf_report.sh` (new); the Makefile makes the
  report test a prerequisite of `deploy-build-guard-test`.
- **Phase 3 (frontend + CORS)** — `wafCaptcha.ts` (new hook), `WaitlistForm.tsx`,
  `WaitlistForm.test.tsx`, `vite-env.d.ts`; `app.py` one header; one preflight test.
- **Docs** — `infra/DEPLOYMENT.md` (§ 1 permission, § 2 precondition 7, § 4 step 0 and
  "The firewall", § 8 rollback), `docs/specs/system/web-api.md` § Waitlist (one sentence),
  `docs/deferred.md` (the 2026-09-03 line, the H-02 line, a 064b seams section),
  `docs/specs/log.md`, ADR 0047 status line, this file (the `evidence/` screenshots are gitignored by repo rule).

**Flagged deviations (minor, within the contract's vocabulary):**

1. **Tests live in a new `infra/tests/unit/test_waf.py`**, not inside `test_synth.py` as
   the contract's scope list names. The ingest worker (`test_ingest_worker.py`) set the
   precedent; the file reuses `test_synth`'s shipped staging template and synthesises the
   component alone for the variants. `test_synth.py` gains one namespacing row.
2. **The CAPTCHA values are resolved before both `update` and `bootstrap`**, not only at
   the top of `update` (contract W7). Both modes publish the frontend, and the guard
   would refuse a bootstrap build without the values; the step still runs before any
   AWS state changes in either mode.
3. **A second deploy-script harness** (`PA_DEPLOY_WAF_KEYS_ONLY=1`) exists so the key
   lookup can be tested against a stubbed `aws` (contract § Acceptance checks asks for
   that case). The plan said the guard harness "gains one line"; the lookup needed its own
   entry point, three lines, in the style of the migration-wait harness.
4. **`WAF_CAPTCHA` is not in the deploy script's `readonly` list**, because the guard
   harness's override reassigns it. Nothing else writes it.
5. **The form has a `data-testid="waf-captcha"`** on the puzzle box and an early return in
   `onSubmit` while the puzzle is unsolved (belt and braces next to the disabled button,
   in case AWS's widget submits the form).
6. **The never-loads vitest uses `vi.useFakeTimers({ shouldAdvanceTime: true })`**: plain
   fake timers hang `userEvent`, which waits on a real `setTimeout(0)`.

**Proposals from the build, not applied (owner pass):**

- "Please solve the puzzle again" has no full stop, unlike the form's other messages; the
  contract pins the string as is.
- After a refusal the solve-again message stays until the next submit, even once the new
  puzzle is solved; clearing it when a fresh token arrives is a small change the contract
  neither asks for nor forbids.

## Review findings

Review stack run 2026-11-17 in the build conversation (owner waiver, rubric item 10). Lanes:
`contract-verifier` (Opus, read-only), Codex adversarial pass (read-only rescue brief),
`/code-review medium` (the Claude half of the heterogeneous pair), one security lane (a
scoped finder on the 064b diff only, since `/security-review` diffed the whole branch
including 064a), `/simplify` last. Family flip held: Claude lanes read the Codex-built
infra and scripts; Codex read the Claude-built frontend, CORS and docs.

- **Contract verifier** (8 findings; 3 adopted, 2 doc fixes, 3 declined):
  - **F1 High, adopted (convergent with nothing else: unique to this lane, and the most
    valuable finding of the stack).** The logging filter rendered camelCase keys
    (`defaultBehavior`, `filters`, …) because CDK 2.261 types `logging_filter` as `Any`,
    so the typed property serialises with the library's names and CloudFormation would
    reject the stack on first deploy. The synth test had pinned the wrong keys. Fix: a
    plain dict with CloudFormation's PascalCase keys; the test now asserts them and that
    no key starts lower-case. The plan's assumption "a wrong property name fails at
    synth" does not hold for `Any`-typed properties (knowledge candidate).
  - **F2 Medium, adopted.** The report queried the `WebACL` metric dimension by the ACL's
    name while its metric name was `pa-v3-waf`, so every total would have read 0. Fix:
    the ACL's metric name is now its name (`policy-atlas-v3-api`); the report test asserts
    the dimension value.
  - **F3 Medium, adopted as a documentation correction, flagged to the owner.** "The next
    deploy re-attaches" the emergency-detached firewall is false: CloudFormation updates
    only changed template resources and does not detect the drift. DEPLOYMENT.md now gives
    the `associate-web-acl` command; ADR 0047 decision 9 carries the correction; the
    contract's W8 row still says "undone by the next deploy" (the contract is the owner's
    approved record; the owner may amend it). A deploy postcondition is a deferred seam.
  - **F4 Low, adopted.** The health-path exclusion is now `EXACTLY`, matching the
    contract's "the two health paths".
  - **F5 Low, adopted (converges with the security lane's sub-bar note and with
    `/code-review`'s finding 2).** The host scope-down matches by `STARTS_WITH`, so a
    request with `Host: api.<domain>:443` or a trailing dot cannot skip W3/W4.
  - **F6 Low, fixed.** The exit test count is 4,831.
  - **F7 Low, declined.** The deploy script's config validation has no automated test
    beyond the manual `"audit"` check; the reader takes its config directory from the
    repo root, and an override for the test would add surface for one case the synth
    tests already cover with the same rules.
  - **F8 Trivial, fixed.** The ADR's stale "open until the plan gate" sentence.
- **`/code-review medium`** (7 findings; 3 adopted, 4 declined):
  - **Adopted:** a synchronous throw from `renderCaptcha` left submit disabled with no
    message (now caught and treated as unavailable, with a sixth vitest case); the key
    lookup now takes a key whose token domains *include* the environment's domain (an
    operator may add more; minor deviation from the contract's "equal to", flagged
    below); `ApiFirewall` has its Args/Raises docstring.
  - **Declined: host-scoping the waitlist rules.** A host condition on the CAPTCHA rule
    would be a CAPTCHA bypass through a `Host: …:443` header (the same trick F5 closes
    for W3/W4). The contract scopes W2 and W5 to the path on purpose; a `POST
    /api/v1/waitlist` to the Metabase host answered 405 by the firewall is harmless.
  - **Declined: pagination of `list-api-keys`.** One or two keys per account.
  - **Declined: reading the ACL and log group names from `waf.py`.** The report runs
    outside the infra virtualenv; three literal copies are pinned by the synth test, the
    report test and DEPLOYMENT.md.
  - **Declined: dropping the deploy script's config validation as a duplicate of
    synth.** The contract requires `deploy.sh check` to fail on a bad key before any AWS
    call; CI runs it before requesting credentials.
  - **Declined: one `get-metric-data` call instead of 21 `get-metric-statistics`
    calls.** A weekly operator script; tens of seconds are fine.
- **Security lane** (1 finding, adopted): the WAF log stored every request header, so a
  counted signed-in request (any body over 8 KB, any managed-rule false positive) wrote
  the bearer token into the log group for a month. Fix: `RedactedFields` for
  `authorization`, `cookie` and `x-aws-waf-token`, asserted by the synth test. Checked
  sound: the CAPTCHA rule's path match against encoding tricks, the health exclusion,
  the token domain list, Metabase, CORS, the frontend, both scripts' input handling.
- **Codex adversarial** (3 findings, all adopted):
  - The report's Logs Insights `stats` read only the first inner match of each group and
    missed the ACL's own non-terminating matches (a count-mode `general-rate` would show
    as `Default_Action`). Fix: the query fetches raw records and Python groups them,
    reading every place a rule name appears; ceiling 10,000 records per run (deferred).
  - The report test proved nothing about the query. Fix: a fixture of two WAF-shaped
    records (two inner matches plus an ACL-level count in one; a CAPTCHA refusal in the
    other); the test asserts each rule's row, that `Default_Action` is never a rule, and
    that addresses appear only with `--addresses`.
  - A CAPTCHA-off deploy left inherited `VITE_WAF_CAPTCHA_*` values in the environment,
    and Vite bundles any `VITE_*` value. Fix: the deploy unsets both when the CAPTCHA is
    off; the key-lookup harness honours the guard override, and a guard-test case starts
    with stale values and asserts they are gone.
- **`/simplify`** (four cleanup lanes; reuse: one minor, efficiency: none, simplification:
  seven, altitude: four). Applied: the managed-group override as a fourth column of the
  group table (two lanes); a `_rate_rule` helper for the two rate rules; `_byte_match` takes
  transformation names and numbers them itself; one override line serves both deploy-script
  harnesses; the key-set check in the deploy script's reader is one comparison; the hook's
  four-value status is a boolean `unavailable` (nothing read the other values); the report
  names a missing environment instead of a traceback; one comment trimmed. Declined: JMESPath
  `--query` in place of the report's small Python picks (the test stub would then have to
  honour `--query`); a single `PA_DEPLOY_HARNESS` switch for the harness blocks (the repo's
  pattern is one block per harness, as the migration waiter); removing the deploy script's
  config validation as a duplicate of synth (the contract requires `deploy.sh check` to fail
  first); the report's parse of five match sources "simplified" to two (the two it would
  drop are where the count week's answers live); a shared config reader between the two
  scripts (one lives inside the other's heredoc).

- **`/okf validate`:** runs inside `make verify` (green).

**Deviation verdicts (the six flagged above):** all six adopted as is by the contract
verifier. One more minor deviation from the review fixes: the key lookup accepts a key
whose token domains include `domain_name` rather than equal `[domain_name]` (contract W7).

**Fake-done check on the review fixes:** no test relaxed or removed; the camelCase
assertions were replaced by the correct PascalCase ones plus a stricter no-lower-case
check; the report test grew from one weak substring assertion to five row assertions.

## Rubric status

1. Contract rows W1 to W8: in the code (tests above); W1's "synth tests pin both
   environments' values" holds; W3's number is measured (§ Phase 0).
2. `make verify`, `make -C infra test`, `make deploy-build-guard-test`: pass. Staging live
   checks: **pending** the hand steps and the deploy. Count week: **pending**.
3. No approval-gated change beyond the contract's list.
4. No generated files or secrets edited; the two CAPTCHA values are public and never stored
   as secrets.
5. No test deleted, skipped or weakened; the container environment test's closed set is
   unchanged.
6. One test per problem, listed above; each was watched to fail or was checked negatively
   (W3's constant; the guard's missing-value cases fail by construction on the old
   script, which had no CAPTCHA branch).
7. This file; the placement screenshots are stubs, the real-widget screenshot, the report
   output and the real log record are **pending** the staging check.
8. `docs/deferred.md` updated as listed.
9. ADR 0047 accepted and marked built; `infra/DEPLOYMENT.md` § 1, § 2 and § 4 "The
   firewall" cover every item in the rubric.
10. Review stack: **ran** (five lanes, § Review findings), fixes applied, `make verify`
    green after them. Owner ruling 2026-11-17 (this conversation): build and review may
    run in the same session; recorded here as the written justification for the
    fresh-conversation rule being waived.

## Intent & assumptions

- The web ACL can be associated from the app stack with the SSM-resolved ARN (plan risk 1):
  synth accepts it; the first staging deploy is the proof.
- The log destination ARN without `:*` is what WAF wants (plan P6): unverified by any AWS
  document; the first staging deploy is the proof.
- The report's Logs Insights field names (`ruleGroupList.N.…`) follow AWS's logging-fields
  page and its examples; one real record confirms them before the owner relies on the
  report.
- The CAPTCHA token issued on the page's domain is accepted on the API's host through the
  token domain list (plan risk 3): the live check W5/W6 is the proof.

## Known unverified items

- The staging live check, the real-widget screenshot, the report against real data, the
  count week; a per-address re-measurement of W3 once 064a logs the client address.
- `aws wafv2 check-capacity` run 2026-11-18 on the synthesised rules (staging session):
  **987** capacity units of 1,500. It first rejected `SingleHeader: {"name": "host"}` in
  the host match (the rate rule and the three managed groups): `single_header` is another
  `Any`-typed field, so the typed `SingleHeaderProperty` rendered a camelCase key that
  synth, the tests and the review stack all accepted. Fixed to the plain dict
  `{"Name": "host"}`; the test now asserts no lower-case key anywhere in the web ACL.
  Without this check the first staging deploy would have failed and rolled back.
- `cdk diff PaV3AppStack` against live staging (read-only change set, 2026-11-18, with the
  fix): four additions, `AWS::WAFv2::WebACL`, `AWS::WAFv2::WebACLAssociation`,
  `AWS::Logs::LogGroup`, `AWS::WAFv2::LoggingConfiguration`; no IAM or security-group
  change. Every other line is 064a's (PR #120, not yet deployed): the pool's deletion
  protection and 12-character minimum, the two new container environment values and
  `FORWARDED_ALLOW_IPS`, the new image digest, the `/healthz` target-group check, the
  CloudFront redirect to HTTPS. The cert stack has no differences.

## Public safety

Everything here and in `evidence/` is safe to publish: no addresses, no keys, no account
ids. The staging check's additions must stay that way (remove client addresses from the
report output and the log record before pasting).

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** Phase 1 and Phase 2 were built by Codex
  (GPT family) from the lead's briefs in the task's gitignored `research/`; Phase 3 by the
  `frontend-designer` (Opus) and a `fast-worker` (Sonnet); the docs by the lead (Fable).
  The lead reviewed every delegated diff and made the small fixes noted in the commit
  messages. Claude's reviewer lanes are the other family for Phases 1 and 2.
- **Adjudication items:** the six flagged deviations above; the two copy/behaviour
  proposals; the deploy-script placement of the CAPTCHA resolve (before the mode branch).
- **Diff scoping:** no binaries in the diff (the `evidence/` screenshots are gitignored).
- **Knowledge candidates:**
  - The background shell runner in this harness ran nothing when the command was a
    parenthesised compound with a redirect; the plain form worked. Prefer foreground runs
    with a long timeout for long gates (they move to the background on their own).
  - `make verify` depends on Docker Desktop being up; a build-open baseline on a laptop
    starts with `open -a Docker` and a wait loop. Worth a line in the build skill or
    `make verify`'s error text.
  - For `aws_cdk.aws_wafv2.CfnWebACL`, the WAF scope is the keyword `scope` in the installed
    2.261 package (the plan expected `scope_`); the constructor's parent is positional.
  - The frontend-designer agent definition names eleven design skills that do not exist on
    this machine (only the `frontend-design` plugin skill, at a different path). The agent
    worked without them; the definition should list what is really installed.
  - `vi.useFakeTimers()` plus `userEvent` hangs; `{ shouldAdvanceTime: true }` is the
    working combination for a "nothing arrives for 10 s" test.
  - macOS bash is 3.2: no `mapfile`, no `${var,,}`. A script test that passes locally may
    be passing on Homebrew bash; write the scripts for 3.2 when operators run them on
    laptops.
  - A whole-group count override hides the inner rule from metrics; the log's
    `ruleGroupList` is the only place it shows. Design the report around the log first.
  - Playwright can stub a third-party script (`jsapi.js`) to screenshot placement without
    the real widget; the real look still needs the live account.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) § Firewall and CAPTCHA (task 064b
seams).

## Exit gate

`make verify` at the step-6 exit (2026-11-17, after all four commits): exit 0. Backend suite
green (4,831 passed, 1 skipped: the baseline's 4,830 plus the new preflight test), infra 125 passed, frontend 1,997 tests in 138 files, build green,
OKF validate, eval check, path audit, prompt guard, font guard and drift check all pass.
`make audit` exit 0. `make deploy-build-guard-test` three PASS lines.

**After the review stack's fixes (2026-11-17):** `make verify` ran twice. The first run had
one failure, `tests/theory_of_change/test_light_check.py::test_a_link_can_pick_and_judge_a_study_another_link_found`,
a `uq_event_log_task_sequence` collision in the theory-of-change fan-out under parallel
workers, the pre-existing ceiling 064a recorded (`docs/deferred.md` § Security quick wins,
event-log retry ceiling); the test passes alone, and this slice touches no backend code
beyond one CORS header. The second run: exit 0, backend 4,831 passed, infra 125, frontend
1,998, build green. `make deploy-build-guard-test` three PASS lines; `make okf-validate`
221 concepts, no violations.
