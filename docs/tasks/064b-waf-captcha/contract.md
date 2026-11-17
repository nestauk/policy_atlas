# Task contract: 064b-waf-captcha

Second slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted, revision 2 (2026-11-17). Revision 1 was reviewed the same day by two
> read-only lanes (Codex 12 findings, Opus 26; records in the gitignored `research/`). Every
> finding is folded into this revision or listed under § Owner items. The main changes:
> the CAPTCHA values are resolved before the stack deploy (W7); production ships with the
> CAPTCHA off; the waitlist limit is 50; the path match decodes first; the general rule and
> the managed groups apply to the API host only; the log filter keeps counted managed-rule
> matches; an emergency off switch. Contract approved (before planning): 2026-11-17 · owner,
> with the rulings under § Owner items (puzzle kept; the general limit is pinned by a
> measurement in the build's Phase 0; production runs its own count week; the managed
> groups skip the health paths; the two hand steps per account are the owner's). · Plan
> approved (before implementation): 2026-11-17 · owner (draft 2) · ADR:
> [0047](../../adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md), Accepted 2026-11-17.

## Goal

Put a firewall in front of the API so that one machine cannot flood it, known attack
patterns are seen and later blocked, and the public waitlist form cannot be filled by a
script. Today nothing stands between the internet and the API except the load balancer, and
the waitlist's only protection is a hidden form field.

## Deliverable

One pull request on `task/064b-waf-captcha` into `dev` that lands W1 to W8 below: an AWS WAF
web ACL attached to the shared load balancer, built from three per-environment keys in
`infra/pa_config.json`; a CAPTCHA on the waitlist form; the deploy script changes that give
the frontend its CAPTCHA settings; a filtered firewall log and a small report script for
the count week; the deployment notes; and tests for each. After the staging deploy, the
live checks in § Acceptance checks, then one week of count mode on staging before the owner
switches the managed rules to block. Production gets the firewall in count mode with the
same PR and its CAPTCHA by a later config change.

## Terms

| Term | Meaning |
|---|---|
| **Review id** (`H-03`, `M-30`) | The id in the 2026-10-19 project review (`original_review.md` in the programme folder). |
| **W1 to W8** | The eight problems of this slice, numbered below. The rubric and the plan use these numbers. |
| **WAF** | AWS Web Application Firewall. A service that inspects each HTTP request before the load balancer passes it on, and can count, block or challenge it. |
| **Web ACL** | Web access control list: the WAF object that holds the rules. One web ACL is attached to one load balancer. Ours is *regional* (it lives in eu-west-2 next to the load balancer), not the CloudFront kind. |
| **Rule** | One entry in the web ACL. Each rule has a statement (what to match) and an action (what to do). Rules run in priority order; the first blocking match ends the evaluation. AWS charges per rule per month. |
| **Scope-down statement** | A condition inside a rule that limits which requests the rule looks at at all. Used here to limit rules to one host or one path. |
| **Rate-based rule** | A rule that counts requests per client IP address over a window and acts once the count passes a limit. The limit is per address, not in total, and AWS applies it approximately and with a short delay. |
| **Managed rule group** | A set of rules AWS writes and updates. This slice uses three: common web attacks (`AWSManagedRulesCommonRuleSet`, 700 WCU), known bad inputs (`AWSManagedRulesKnownBadInputsRuleSet`, 200) and an IP reputation list (`AWSManagedRulesAmazonIpReputationList`, 25). A group counts as one rule for billing. |
| **Count mode** | The rule records that it matched and lets the request through. The match shows in CloudWatch and in the firewall log. Used to learn what a rule would block before it blocks. |
| **Block mode** | The rule refuses the request with a 403. |
| **CAPTCHA** | The "prove you are a person" puzzle. AWS WAF has its own: a rule with the CAPTCHA action refuses a request that carries no valid token, and a JavaScript library (the WAF SDK) shows the puzzle and gets the token. |
| **Token** | A signed value the WAF SDK obtains for the browser after the puzzle is solved. The form sends it in a request header with each submission. |
| **Token domain list** | The list of website domains whose tokens the web ACL accepts. By default only the API's own host. A listed domain covers all its subdomains, so one entry, the environment's `domain_name` (`v3.policyatlas.uk` on staging, `policyatlas.uk` in production), covers the page, `www` and `api`. |
| **API key** (WAF) | A public key the CAPTCHA script needs to render a puzzle. Created once per AWS account and region with one command, bound to the token domain, and cannot be changed afterwards. Not a secret: it ships in the browser bundle. It belongs to the account, not to the web ACL. |
| **Application integration URL** | The per-account AWS URL that serves the CAPTCHA script (`<url>/jsapi.js`). The command that lists API keys returns it. |
| **Immunity time** | How long after a solved puzzle the token keeps working without a new puzzle. |
| **Sampled requests** | Up to 100 matched requests per rule from the **last three hours only**, free. Useful right after a deliberate test pass, useless for a week in hindsight, which is why W8 adds a log. |
| **Firewall log** | WAF's own request log, written to a CloudWatch log group whose name must start with `aws-waf-logs-`. A logging filter keeps only requests that some rule counted, blocked or challenged, so normal traffic is never logged. One month of retention. |
| **Logs Insights** | CloudWatch's query language for log groups. The report script runs one query over the firewall log. |
| **WCU** | Web ACL capacity units: a measure of how much work the rules do. One web ACL may use at most 1,500. The three managed groups use 925; the other rules a few each. |
| **Shared load balancer** | The one application load balancer in the network stack that serves the API (`api.<domain>`) and Metabase (`metabase.<domain>`). The web ACL is attached to the whole balancer; this slice scopes every rule to the API host (W3, W4) or the waitlist path (W2, W5), so Metabase traffic matches nothing and is allowed by default. |
| **CORS, preflight** | Cross-origin resource sharing: the browser rule that a page on one host may call an API on another only if the API says so. Before a request with a custom header, the browser sends an `OPTIONS` request, the *preflight*, and the API's reply lists the headers it allows. |
| **ARN** | Amazon Resource Name: the full identifier of one AWS resource. The load balancer's ARN is what the web ACL attaches to. |
| **SSM** | AWS Systems Manager Parameter Store: where the network stack publishes the load balancer's ARN for the app stack to read at deploy time. |
| **CDK, L1, synth, CloudFormation** | AWS Cloud Development Kit: the Python library our infrastructure is written in. *Synth* turns it into a CloudFormation template (AWS's JSON description of resources), which `make -C infra test` asserts on. WAF has only *L1* constructs, which map one to one onto template properties. |
| **`waf.enabled`, `waf.mode`, `waf.captcha`** | The three per-environment keys this slice adds under `backend` in `infra/pa_config.json`. Defined under W1. |

## Read first

- `infra/infra/network_stack.py` (the shared load balancer, exported through SSM) and
  `infra/infra/components/shared_alb.py` (how the app stack imports it; the web ACL
  association needs the load balancer's ARN, which this import already has).
- `infra/infra/policy_atlas_stack.py` lines 36 to 130 (how `pa_config.json` keys reach the
  stack and the container) and 283 to 312 (the backend listener rule).
- `infra/infra/components/ingest_worker.py` as the pattern for a component file that the
  app stack instantiates.
- `infra/tests/unit/test_synth.py` (template assertions; `test_app_stack_deploy_invariant_values_are_template_pinned`
  at line 282 is the pin pattern) and `infra/tests/unit/test_service_wiring.py` line 64
  (the container environment is asserted as a closed set; nothing new reaches the container).
- `scripts/deploy.sh`: the embedded Python config reader (lines 30 to 200, which exports the
  per-environment values as `readonly` shell variables), `resolve_frontend_publish_config`
  (lines 606 to 631), `require_production_build_environment`, the `PA_DEPLOY_GUARD_ONLY`
  harness (line 714), and the `update` flow (`deploy_all_stacks` runs **before**
  `common_tail`, which is what makes W7's ordering matter).
  `scripts/test_deploy_build_guard.sh` exercises the guard; it runs in CI's `fe-api-smoke`
  job through `make deploy-build-guard-test`, not in `make verify`.
- `frontend/src/views/splash/WaitlistForm.tsx` and its test; `frontend/src/vite-env.d.ts`
  (every `VITE_*` value is declared there); `frontend/src/mock/api.ts` line 381 (the mock
  waitlist reply); `frontend/index.html` (the only HTML shell).
- `backend/src/policy_atlas/api/app.py` lines 197 to 203 (CORS: `allow_headers` is a closed
  list of two) and `backend/tests/api/test_cors_and_envelope.py`.
- `backend/src/policy_atlas/api/routers/waitlist.py` (the route has one method, `POST`).
- `docs/specs/system/web-api.md` § Waitlist.
- `docs/deferred.md` line 2471 ("Waitlist spam: WAF rate rule is the upgrade path", decided
  2026-09-03 with "no CAPTCHA") and § Security quick wins (H-02 body size limits, not in
  064a). This slice supersedes the 2026-09-03 "no CAPTCHA" decision on the owner's 2026-11
  ruling; the line is updated, not deleted.
- `infra/DEPLOYMENT.md` § 2 (first-deploy preconditions, where the API key and the deploy
  permissions go), § 4 (the steady-state deploy order) and § 5 (the env and secret map).
- The research notes in this task's gitignored `research/aws-waf-facts.md` (AWS documentation
  facts with URLs, gathered 2026-11-17). ADR 0047 repeats the six URLs that matter.

## The problems

| # | Review | Today | Required |
|---|---|---|---|
| **W1** | H-03 | No web ACL exists. The load balancer passes every request to the API. | A regional web ACL, built by a new component `infra/infra/components/waf.py` that the app stack instantiates and associates with the imported shared load balancer (`CfnWebACLAssociation` on the load balancer ARN). Three keys under `backend` in `infra/pa_config.json`, both environments, read like `ingest_mode` is: `waf.enabled` (bool; `false` synthesises no WAF resource at all, which is the rollback), `waf.mode` (`"count"` or `"block"`; applies to W3 and W4), `waf.captcha` (bool; W5 and W7). A missing key, any other value, or `captcha: true` with `enabled: false` makes synth **and** the deploy script fail. Default action allow. Every rule and the web ACL itself emit CloudWatch metrics and keep sampled requests. Initial values: staging `enabled true, mode count, captcha true`; production `enabled true, mode count, captcha false`. Production's CAPTCHA is turned on by a later config change after the staging live check (programme rule: staging leads by one release). Each environment is switched to block by its own config change after its own count week. The synth tests pin both environments' values. |
| **W2** | H-03, M-30 | A script can post to the waitlist without limit; the honeypot is the only check. | A rate-based rule: more than 50 requests per 5 minutes from one address to `POST /api/v1/waitlist` are blocked. Fifty, not ten, because an office, an event's wifi or a mobile network can put many real people behind one address, and W5 already stops scripts; the number only bounds a script that has a valid token. Always block, not governed by `waf.mode`. Aggregated on the connection's source address (the API is reached through the load balancer directly, not through CloudFront, so the address is the client's). The path match applies `URL_DECODE` then `LOWERCASE` before comparing, so `/api/v1/waitlis%74` is the same path (the API decodes it; the rule must too). |
| **W3** | H-03 | One address can send as many requests as it likes to any route, including `/readyz`, which opens a database connection, and the public task views. | A rate-based rule over every request **to the API host** (`Host` header equals `api.<domain>`). The limit is 🟡 **3,000 requests per 5 minutes per address pending a measurement** (owner ruling 2026-11-17): the build's Phase 0 reads the staging API log for the last two weeks, finds the busiest address in any 5-minute window, and pins the limit at ten times that peak, rounded up to a thousand and never below 3,000; the number and the query result go in `verification.md`. The starting figure comes from the frontend: an open task polls three queries every 15 seconds while a run is active (12 requests a minute) plus one progress stream, so even an office of twenty people on one address stays under 300 a minute. Action follows `waf.mode`. In count mode the week shows whether any address crossed the line, not the real peak (a rate rule records nothing below its limit). |
| **W4** | H-03 | No known-attack filtering. | The three managed rule groups, each scoped to the API host like W3 **and excluding the two health paths** (`/healthz`, `/readyz`), so the load balancer's health check and the deploy script's readiness call can never be refused by a managed rule, whatever address they come from (owner ruling 2026-11-17: do not block by default). In count mode the whole group's action is overridden to count; AWS notes that a blocking rule inside the group then still ends that group's evaluation, so the week sees the first matching rule per request, which is enough to decide an exclusion but means a second match can surface after the first is excluded, which is why the deliberate pass is repeated after the switch to block. In block mode the groups keep their own actions. In both modes the common group's `SizeRestrictions_BODY` rule (request body over 8 KB; a load balancer web ACL inspects exactly the first 8 KB and nothing more) is overridden to count, because chat messages, plan edits and theory-of-change imports can exceed 8 KB. Any other rule the count week shows matching normal use is excluded the same way before the switch to block; that list is hard-coded in the component today (one name) and becomes a config key only if the week finds a second. |
| **W5** | M-30 | Nothing distinguishes a browser from a script on the waitlist route. | A rule with the CAPTCHA action, statement `POST` **and** the decoded, lower-cased path `/api/v1/waitlist`, present when `waf.captcha` is true, ahead of W2 in priority so a tokenless request is refused before it is counted. Immunity time 1,800 seconds (30 minutes), so a person who solves the puzzle first and then writes a long answer is not asked twice; AWS's default is 300 and the cost is nil. The web ACL's token domain list holds one entry, the environment's `domain_name`, because the token is issued to the page's domain and spent on the API's, and a listed domain covers its subdomains. The rule matches `POST` only, so the browser's CORS preflight (`OPTIONS`) passes it without a token; AWS says puzzles can never be served to a preflight. A request with no valid token gets WAF's own reply: status `405` with the header `x-amzn-waf-action: captcha` and CORS headers that expose it, and never reaches the API. |
| **W6** | M-30 | The form posts with `fetch` and two headers. | When `VITE_WAF_CAPTCHA_SCRIPT_URL` is set, the form loads the CAPTCHA script (`<url>/jsapi.js`, which loads the rest of the SDK itself) once, **on the first interaction with the form** (focus on any field), not on page load, so a visitor who never signs up loads no third-party script; renders the puzzle inside the form above the submit button with `AwsWafCaptcha.renderCaptcha` and the API key from `VITE_WAF_CAPTCHA_API_KEY`; keeps submit disabled until the puzzle's `onSuccess` hands over a token; and sends that token in the `x-aws-waf-token` request header with the submission (the token cookie does not cross hosts; the header does). The puzzle is shown up front rather than after a refusal, because with a CAPTCHA rule the first tokenless submission always fails, and AWS's "render on 405" pattern would cost every person a failed round trip. When the script URL is unset (local development, CI, the mock journey) the form behaves exactly as today: no script, no puzzle, no header. The API's CORS `allow_headers` gains `x-aws-waf-token`; a backend test sends a preflight asking for `content-type, x-aws-waf-token` together, as a browser does, and asserts the reply allows both. The form treats a reply as a CAPTCHA refusal only when the `x-amzn-waf-action` header reads `captcha` (an expired token), shows "Please solve the puzzle again" and re-renders the puzzle in the same place; a `405` without that header (the route itself never sends one; the form only ever sends `POST`) is the generic error. If the script has not loaded 10 seconds after the first interaction, the form shows "The sign-up check did not load. Reload the page to try again." and keeps submit disabled; if the script then arrives, the puzzle renders and the message clears, so a slow connection delays a person and never locks them out. Vitest covers five branches: no script URL means no puzzle and no header; a configured URL and a solved puzzle send the header; a `405` with the WAF header shows the solve-again message and renders the puzzle again; a `405` without it shows the generic one; a script that never loads shows the reload message with submit disabled. The widget's placement and spacing are the `frontend-designer`'s call at build; this contract pins behaviour only. |
| **W7** | — | The frontend build gets three `VITE_*` values from the deploy script, resolved after the stack deploy. | Two more, `VITE_WAF_CAPTCHA_SCRIPT_URL` and `VITE_WAF_CAPTCHA_API_KEY`, resolved **before `deploy_all_stacks`** (a new step at the top of `update`, after the config checks and before anything touches AWS state), only when the environment's `waf.enabled` and `waf.captcha` are both true: `aws wafv2 list-api-keys --scope REGIONAL` returns the application integration URL and the keys; the script takes the key whose token domains equal `[domain_name]` and fails with a message naming the one command to run when there is none. The key is created by hand once per account as a first-deploy precondition in `infra/DEPLOYMENT.md` § 2 (`aws wafv2 create-api-key --scope REGIONAL --token-domains <domain_name>`), so the script needs `wafv2:ListAPIKeys` only, and that permission is listed with the other deploy-role permissions in § 1. `require_production_build_environment` checks both values when CAPTCHA is on; `scripts/test_deploy_build_guard.sh` gains the on and off cases through a `PA_DEPLOY_GUARD_WAF_CAPTCHA` override that the guard harness honours and nothing else reads. When CAPTCHA is off, both values stay unset and the form stays as today. Both values are public by design (they ship in the browser bundle), so they are not secrets, need no Secrets Manager entry, and may appear in the deploy log. **Accepted window:** during a deploy that turns the CAPTCHA on, the old frontend bundle is live for the minutes between the service coming back and the new bundle being published, and a waitlist submission in that window is refused. The same deploy takes the whole API down for its migration step, so the window adds nothing new. |
| **W8** | — | Reading the count week means clicking through the AWS console, and WAF keeps request samples for three hours only. | Two parts. **The log:** a `CfnLoggingConfiguration` on the web ACL writing to a CloudWatch log group `aws-waf-logs-policy-atlas-v3` (same name in both accounts; the prefix is mandatory), retention one month, with a logging filter that keeps a request when some rule's action was `COUNT`, `BLOCK`, `CAPTCHA` or `EXCLUDED_AS_COUNT` (the action a rule overridden to count reports, which is how the body-size rule's matches are logged) and drops the rest, so ordinary traffic is never stored and the volume stays inside WAF's included log allowance. Created with the web ACL, removed with it. **The report:** `scripts/waf_report.sh <env> [days] [--addresses]`, read-only with the operator's credentials, prints per rule the counted, blocked and CAPTCHA totals from the `AWS/WAFV2` metrics for the last `days` days (default 7), then one Logs Insights query over the log group for the same period giving, per **rule inside a group** (from the log's rule-group match fields, since the group's own name is all the metrics and the terminating rule show in count mode), the request count and the distinct paths, with client addresses shown only when `--addresses` is passed. `infra/DEPLOYMENT.md` gains a section "The firewall": the three keys, the count week (the deliberate pass below, then the report, then the decision per rule), how to switch to block (`waf.mode` in config, deployed the normal way) and the required repeat of the deliberate pass right after, how to exclude a rule, how to turn the whole thing off by config, the **emergency off switch** (`aws wafv2 disassociate-web-acl --resource-arn <load balancer ARN>`, which detaches the firewall in seconds and is undone by the next deploy, for a false positive in production that cannot wait for a release), the token domain, and where the CAPTCHA values come from. |

One number per problem, one invariant per problem. W2 and W5 both protect the waitlist, but
W5 stops a script that has no token and W2 bounds a script that has one; neither stops a
person, who can retry a puzzle without limit.

## Scope / Out of scope

- **In:** `infra/infra/components/waf.py` (new: web ACL, association, log group, logging
  configuration), `infra/infra/policy_atlas_stack.py` (instantiate the component; pass
  nothing new to the container), `infra/pa_config.json`, `infra/tests/unit/test_synth.py`
  and `test_service_wiring.py`, `scripts/deploy.sh`, `scripts/test_deploy_build_guard.sh`,
  `scripts/waf_report.sh` and `scripts/test_waf_report.sh` (new; the test is a prerequisite
  of `make deploy-build-guard-test` so CI runs it with no workflow change),
  `frontend/src/views/splash/WaitlistForm.tsx` and its test, a new
  `frontend/src/views/splash/wafCaptcha.ts` (the hook and the SDK's types),
  `frontend/src/vite-env.d.ts`, `backend/src/policy_atlas/api/app.py` (one header in
  `allow_headers`), `backend/tests/api/test_cors_and_envelope.py`, `infra/DEPLOYMENT.md`
  (§ 1 permission, § 2 precondition, new § The firewall), `docs/specs/system/web-api.md`
  § Waitlist (one sentence on the CAPTCHA header), `docs/deferred.md` (the 2026-09-03 line
  and the H-02 line), the programme map's 064b paragraph (already updated with this
  contract), ADR 0047.
- **Out:** the Content Security Policy (064c; it must list the SDK script source, which is
  why it follows this slice). MFA and threat protection (064d). A WAF on CloudFront (the
  frontend is static files on S3; nothing to protect beyond what CloudFront does). Request
  body size limits (H-02): see § Owner items 4. Alerts on WAF metrics (there is no alarm
  topic yet; H-05). Per-user request rate limits inside the API (H-04, after the quota has
  run). Any change to the waitlist route's behaviour, the honeypot, or the splash page's
  text (the privacy line next to the submit button is Data Protection Officer work with
  the privacy notice). Metabase: every rule is scoped to the API host or the waitlist path,
  so Metabase traffic is allowed by the default action and keeps its own IP allowlist.

## Constraints & approval gates

- **Production config:** three new keys in `infra/pa_config.json` for both environments.
  The web ACL, its association, its log group and logging configuration are new live
  resources in both AWS accounts. One WAF API key per account, created by hand as a
  precondition. One new deploy-role permission per account, `wafv2:ListAPIKeys`, added by
  hand (the deploy role is not in CDK; `infra/DEPLOYMENT.md` § 1 lists it). The programme
  rule applies: every environment-specific value is a key; the rule limits (50 and 3,000
  per 5 minutes), the immunity time, the host scoping and the body-size exclusion have one
  right value everywhere and are hard-coded in the component.
- **Public interface:** the API accepts one more request header (`x-aws-waf-token`) in
  CORS. No route, status code or body changes. The waitlist route's contract in
  `web-api.md` gains one sentence.
- **Dependencies:** none in the backend or infra. The frontend loads the WAF SDK at run time
  from an AWS URL; it is not an npm package and does not enter `package.json`. This is the
  first third-party script the frontend loads, which is why 064c (CSP) comes next, and it
  is loaded on the first interaction with the form, not on page load.
- **Auth, tenancy, schema, CI, egress:** none. The web ACL does not read or write project
  data; it sees request metadata and the first 8 KB of a body, at AWS, before the API.
- **Cost:** about $11 a month per environment (web ACL $5; six rules at $1 each: W2, W3,
  three groups, W5), plus $0.60 per million requests and $0.40 per 1,000 CAPTCHA puzzles
  (eu-west-2 price list, 2026-09-14). The WAF API key and sampled requests are free. WAF's
  log allowance (500 MB of CloudWatch Logs per million requests) covers a log that keeps
  only matched requests. Whether WAF's CloudWatch metrics are free is not stated by AWS;
  at our request volume the difference is cents.
- **Staging leads by one release** (programme rule): CAPTCHA and block mode can lock people
  out, so the order is staging (count, CAPTCHA on, one real sign-in and one real waitlist
  submission), production (count, CAPTCHA off, with this PR), production CAPTCHA on (config
  change after the staging live check), staging block after its week, production block
  after its week.
- **Rollback:** `waf.enabled: false` and a deploy removes the web ACL, its association, its
  logging configuration and the log group, and the deploy script then resolves no CAPTCHA
  values, so the form has no puzzle. `waf.mode: count` undoes a block. `waf.captcha: false`
  removes the CAPTCHA rule and the frontend's puzzle at the next deploy. The emergency off
  switch (W8) detaches the firewall in seconds without a deploy. No data to restore. The WAF
  API key is harmless to leave behind.
- **Capacity:** the web ACL's limit is 1,500 WCU; the three managed groups use 925 and the
  other rules a few each. Synth cannot see capacity; `aws wafv2 check-capacity` or the first
  staging deploy is the check. Adding a fourth managed group later needs that check again,
  noted in DEPLOYMENT.md.

## Public / private boundary

All artefacts are public-safe. The firewall log and the sampled requests contain client IP
addresses: the log lives in the AWS account for one month, the report script prints
addresses only with `--addresses`, and verification records counts, rule names and paths,
never addresses. The CAPTCHA script URL and API key are public values by AWS's design
(they ship in the browser bundle) and may appear in deploy logs.

## Design annex

None. The slice's one visual element is the AWS CAPTCHA widget, whose look AWS controls.
Its placement inside the form is the `frontend-designer`'s decision at build and is
recorded with a screenshot in `verification.md`, not pinned here.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** Three config keys, each of which changes the synthesised
  template. No key for a value with one right answer.
- **Flag, don't drop.** H-02 and the GitHub-runner risk are owner items below, not silent
  omissions.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: the web ACL cannot be associated with the imported load balancer
from the app stack (then the component moves to the network stack, which changes the config
file it reads); the WAF SDK cannot obtain a token for a cross-origin API call with the
token domain list as specified (then the CAPTCHA rule moves to a same-origin shape, a
contract change); or `check-capacity` shows the rules exceed the web ACL's capacity.

## Acceptance checks

- `make verify` green; `make -C infra test` green; `make deploy-build-guard-test` green
  (it now runs the report script's test too).
- Tests, one per problem, listed in the plan: W1 to W5 as synth assertions on both
  environments' templates (resources present when enabled, absent when disabled; a bad
  mode and `captcha` without `enabled` raise; actions follow `waf.mode`; the host
  scope-down on W3 and W4; the body-size override; the path match's two transformations;
  the CAPTCHA rule present only with `waf.captcha`, ahead of W2, immunity 1,800; token
  domains equal `[domain_name]`); W6 the five vitest branches and the backend preflight test;
  W7 the guard's on and off cases plus a stubbed-`aws` case for the key lookup (a matching
  key is taken, no match fails with the named command); W8 the logging configuration's
  group name, retention, destination ARN without a `:*` suffix and filter actions as synth
  assertions, and the report script against recorded output that includes a counted rule
  inside a group.
- **Live check on staging after the deploy** (about 25 minutes, the owner's account):
  - W1: `aws wafv2 get-web-acl` lists the same rule names as the synthesised template, and
    the association points at the load balancer.
  - W5, W6: the splash page shows the puzzle on first focus; a submission after solving it
    gets the thanks message; a `curl -i` post with no token gets `405`, the
    `x-amzn-waf-action: captcha` header and the CORS headers, and never reaches the API;
    the same with the path written `/api/v1/waitlis%74` gets the same refusal.
  - W2: with a token copied from the browser's solved puzzle, posts in a loop from one
    address get a `403` shortly after about fifty (AWS applies the limit approximately).
  - W3, W4: zero blocked requests in the first hour (count mode); the metrics exist per
    rule; one request to the Metabase host matches no rule.
  - A real sign-in and the deliberate pass: open the task list, send one chat message over
    8 KB, edit a plan, import a theory-of-change image, open a public task view, and
    confirm with the report script that only the body-size rule counted any of them, and
    that the report names that rule, not just its group.
  - W8: the log group has entries for the pass and none for ordinary requests.
- **The count week on staging, then production** (the owner, with the report script):
  after seven days, run the report, decide per rule, switch `waf.mode` to block in config,
  deploy, and **repeat the deliberate pass at once**; if anything is refused, set
  `waf.mode: count` again (or use the emergency off switch) and exclude the rule. Recorded
  in verification as done or not done; this slice is merged before the week ends, so the
  switch is a follow-on config change.

## Verification evidence expected

Command results, the staging check notes with one screenshot of the puzzle in the form, the
report script's output with addresses removed, one real log record (addresses removed)
showing the field that names the rule inside a group, the diff summary, and the ADR link,
in `verification.md`.

## Owner items (ruled 2026-11-17)

1. **CAPTCHA puzzle or silent challenge.** The owner ruled CAPTCHA (2026-11) and confirmed
   it at the gate. WAF also offers a *challenge* action: the SDK proves it is a real
   browser without a puzzle, so people see nothing, and only plain scripts are stopped. It
   costs $0.40 per million instead of per thousand and needs no widget, but a script
   driving a real browser passes it. Settled: the puzzle.
2. **General rate limit.** The owner asked how many requests a typical workflow creates
   before pinning a number. Settled: measured from the staging API log in the build's
   Phase 0, pinned at ten times the busiest address's 5-minute peak, rounded up to a
   thousand, never below 3,000 (W3). The staging count week then shows whether any
   address crosses it; it cannot show the real peak.
3. **Production counts for its own week** (programme rule, as written). Settled: yes.
4. **H-02 (request size limit) cannot be closed here.** A load balancer web ACL inspects
   the first 8 KB of a body and no more, so WAF can only tell "over 8 KB" from "under",
   and over 8 KB is normal for this API. A real size cap belongs in the API process (a
   body limit in the server or a middleware), a later slice. The `docs/deferred.md` H-02
   line says so. No decision needed; stated so it is not read as forgotten.
5. **The deploy's own readiness check in block mode.** After each deploy the script calls
   `/readyz` from a GitHub runner address. If the IP reputation group ever listed that
   address, the call would be refused and the deploy would report failure after the
   service is up. The owner ruled "do not block by default". Settled: the managed groups
   skip `/healthz` and `/readyz` (W4), so neither the load balancer's health check nor the
   deploy's readiness call can ever be refused by them.
6. **Two hand steps per account before the first deploy** (the deploy-role permission and
   the API key). Settled: the owner does them; the script only lists keys.

## Risk tier & review focus

**Tier 4** (production config in both accounts, a new third-party script in the browser, a
change that can refuse real users). Review stack: contract verifier, `/code-review`,
`/security-review`, adversarial review of contract and plan, simplification pass, human
deep review. Focus: a request from a real browser can never be refused by W2 or W5 in
normal use (the preflight passes, the token reaches the API's web ACL from the page's
domain, the immunity time covers a long form session, a slow script delays but never
locks); the deploy resolves the CAPTCHA values before it touches AWS state and never
builds a production bundle without them while the rule is live; `waf.enabled: false`
synthesises nothing and resolves nothing; the body-size override really is in count in
both modes; Metabase traffic matches no rule; the report names the rule inside a group;
the report script reads and never writes.
