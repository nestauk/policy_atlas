# Implementation plan: 064b-waf-captcha

> Status: **draft 2 (2026-11-17), awaiting the owner's plan gate.** Draft 1 was reviewed the
> same day by two read-only lanes (Codex 12 findings, Opus 26; records in the gitignored
> `research/`); every finding is folded here or into contract revision 2. Contract:
> [contract.md](contract.md) (revision 2, awaiting approval). Rubric: [rubric.md](rubric.md).
> ADR: [0047](../../adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md), drafted.
> Problems W1 to W8 and the terms are defined in the contract and not restated here. Executor
> routing follows `docs/agentic-ops/harness.md` § Agent-side model routing: judgment-bearing
> build work goes to `codex` or `deep-reasoner`, mechanical volume to `fast-worker`, seam
> design, live runs and owner-facing reads stay with the lead. The build runs in a fresh
> conversation with task-cycle-build, opening on Phase 0.

## Order and why

Infrastructure first (W1 to W5, W8's log), because it is one new file with one test file and
nothing else depends on its shape except the names the deploy script and the report script
read. Then the deploy script (W7), because the frontend build needs its values and its new
pre-deploy step is the one ordering change in the release path. Then the frontend and the
CORS header together (W6), because they are the two halves of one request. Then the report
script and the docs (W8). The whole slice touches no schema, no auth code and no runtime
path, so one full-verify gate at build-open and one at exit are enough; the phases in
between gate on `make -C infra test` or `make verify-fast`.

## Decisions taken in this plan

| # | Problem | Decision |
|---|---|---|
| P1 | W1 | New `infra/infra/components/waf.py` with one class `ApiFirewall(Construct)` taking `load_balancer_arn: str`, `api_host: str`, `domain_name: str`, `waf_config: dict`. It requires all three keys, raises `ValueError` on a missing key, a `mode` outside `{"count", "block"}`, a non-boolean, or `captcha` true with `enabled` false, the way `policy_atlas_stack.py` checks `ingest_mode`. When `enabled` is false the constructor creates nothing (the stack still instantiates it, so the config is validated in every environment). Otherwise it creates `wafv2.CfnWebACL(scope_="REGIONAL", name="policy-atlas-v3-api", default_action=allow, visibility_config=…, token_domains=[domain_name] if captcha else None, rules=[…])` (the parameter is spelled `scope_` in the Python package because `scope` is the construct's parent; every nested value is built from the typed `CfnWebACL.*Property` classes, not raw dicts, so a wrong property name fails at synth), `wafv2.CfnWebACLAssociation(resource_arn=load_balancer_arn, web_acl_arn=acl.attr_arn)`, and W8's log (P6). The stack calls it after `import_shared_alb` with `shared_alb.load_balancer_arn`, `be_domain`, `domain_name` and `be_config["waf"]`. `pa_config.json` gains `"waf": {"enabled": true, "mode": "count", "captcha": true}` under `backend` for staging and `{"enabled": true, "mode": "count", "captcha": false}` for prod. Metric names: `pa-v3-waf` and, per rule, the rule name. |
| P2 | W2, W3 | Shared statement helpers in the component: `_api_host()` = byte match `single_header: host` EXACTLY `api_host` with `LOWERCASE`; `_waitlist_post()` = `and(byte_match uri_path EXACTLY "/api/v1/waitlist" with text transformations [URL_DECODE (priority 0), LOWERCASE (priority 1)], byte_match method EXACTLY "POST")`. `waitlist-rate` (priority 20): `rate_based_statement(limit=50, evaluation_window_sec=300, aggregate_key_type="IP", scope_down_statement=_waitlist_post())`, action `{"block": {}}` in both modes. `general-rate` (priority 30): `rate_based_statement(limit=3000, evaluation_window_sec=300, aggregate_key_type="IP", scope_down_statement=_api_host())`, action block when `mode == "block"` else count. |
| P3 | W4 | Three rules with `managed_rule_group_statement(vendor_name="AWS", name=…, scope_down_statement=_api_host())`, priorities 40 to 60, `override_action={"count": {}}` in count mode and `{"none": {}}` in block mode. The common group's statement carries `rule_action_overrides=[RuleActionOverrideProperty(name="SizeRestrictions_BODY", action_to_use={"count": {}})]` in both modes; the names come from the module constant `COMMON_RULES_ALWAYS_COUNTED = ("SizeRestrictions_BODY",)`, the place a second name would go. |
| P4 | W5 | One rule `waitlist-captcha`, priority 10 (ahead of W2, so a refused tokenless request is not also counted toward the rate limit), present only when `captcha` is true: statement `_waitlist_post()`, `action={"captcha": {}}`, `captcha_config=CaptchaConfigProperty(immunity_time_property=ImmunityTimePropertyProperty(immunity_time=1800))`. |
| P5 | W6 | New `frontend/src/views/splash/wafCaptcha.ts`: the SDK's `window.AwsWafCaptcha` type (the SDK ships none) and a hook `useWafCaptcha(containerRef)` that reads `import.meta.env.VITE_WAF_CAPTCHA_SCRIPT_URL` and `VITE_WAF_CAPTCHA_API_KEY` **inside the hook** (so `vi.stubEnv` works), returns `{configured, token, status, arm, reset}`. `arm()` is called by the form on the first focus of any field: if `window.AwsWafCaptcha` already exists it renders at once; otherwise it appends `<script src="<url>/jsapi.js">` once (idempotent on the document by a `data-` marker) and renders on the script's `load` event; a 10-second timer sets `status: "unavailable"`, which a later `load` clears. `render` calls `window.AwsWafCaptcha.renderCaptcha(container, {apiKey, onSuccess: token => setToken(token), onError: () => setStatus("unavailable")})`; `reset()` clears the token and renders again into the same container. `WaitlistForm.tsx`: a `ref` div above the submit button; `onFocus` on the form calls `arm()`; the `fetch` headers gain `"x-aws-waf-token": token` when set; submit is disabled while `configured && !token`; `status === "unavailable"` shows "The sign-up check did not load. Reload the page to try again."; a reply with `response.headers.get("x-amzn-waf-action") === "captcha"` sets "Please solve the puzzle again" and calls `reset()`. `vite-env.d.ts` declares both values with the public-by-design note. `app.py`: `allow_headers=["Authorization", "Content-Type", "x-aws-waf-token"]`. Tests: `WaitlistForm.test.tsx` gains the five cases of rubric item 6 with `vi.stubEnv`, a fake `window.AwsWafCaptcha` installed before render (so no script is injected and jsdom's never-firing `load` is not relied on) whose `renderCaptcha` calls `onSuccess("tok")` synchronously and counts its calls (the solve-again case asserts a second render), and `vi.useFakeTimers` for the never-loads case; `test_cors_and_envelope.py` sends `Access-Control-Request-Headers: content-type,x-aws-waf-token` and asserts both are allowed. `mock/api.ts` needs no change. |
| P6 | W8 log | In `waf.py`, when enabled: `logs.LogGroup(log_group_name="aws-waf-logs-policy-atlas-v3", retention=ONE_MONTH, removal_policy=DESTROY)` and `wafv2.CfnLoggingConfiguration(resource_arn=acl.attr_arn, log_destination_configs=[Stack.of(self).format_arn(service="logs", resource="log-group", resource_name=group.log_group_name, arn_format=ArnFormat.COLON_RESOURCE_NAME)], logging_filter=LoggingFilterProperty(default_behavior="DROP", filters=[FilterProperty(behavior="KEEP", requirement="MEETS_ANY", conditions=[ConditionProperty(action_condition=ActionConditionProperty(action=a)) for a in ("COUNT", "BLOCK", "CAPTCHA", "EXCLUDED_AS_COUNT")])]))`. The destination ARN is built without the `:*` suffix that `LogGroup.log_group_arn` carries, because WAF rejects it as a destination (a reviewer's recollection; the first staging deploy confirms). `EXCLUDED_AS_COUNT` is the action a rule overridden to count reports (the installed package's docstring says so), which is how the body-size rule's matches reach the log. Property names confirmed against the installed `aws_cdk.aws_wafv2` (2.261.0) on 2026-11-17: `CfnWebACL(scope_, default_action, visibility_config, rules, captcha_config, token_domains, …)`, `RuleProperty(name, priority, statement, visibility_config, action, captcha_config, override_action)`, `RateBasedStatementProperty(aggregate_key_type, limit, evaluation_window_sec, scope_down_statement)`, `ManagedRuleGroupStatementProperty(name, vendor_name, rule_action_overrides, scope_down_statement)`, `RuleActionOverrideProperty(action_to_use, name)`, `CaptchaConfigProperty(immunity_time_property=ImmunityTimePropertyProperty(immunity_time))`, `ByteMatchStatementProperty(field_to_match, positional_constraint, search_string, text_transformations)`, `FieldToMatchProperty(method, uri_path, single_header, …)`, `CfnWebACLAssociation(resource_arn, web_acl_arn)`, `CfnLoggingConfiguration(resource_arn, log_destination_configs, logging_filter)`, `LoggingFilterProperty(default_behavior, filters)`. |
| P7 | W7 | `scripts/deploy.sh`: the embedded Python reader validates `backend.waf` (all three keys, their types, the mode values, `captcha` implies `enabled`) and exports a seventh value `WAF_CAPTCHA` (`1` when `enabled and captcha`, else `0`) into the `readonly` set, so `deploy.sh check` fails on a bad key before any AWS call. New function `resolve_waf_captcha_values()`: `aws wafv2 list-api-keys --scope REGIONAL --region "$DEPLOY_REGION"`, parsed with the script's existing `python3 -c` pattern; takes `ApplicationIntegrationURL` and the first key whose `TokenDomains` equals `["$PUBLIC_DOMAIN"]`; exports `VITE_WAF_CAPTCHA_SCRIPT_URL="${url}"` and `VITE_WAF_CAPTCHA_API_KEY`; with no matching key it fails: "no WAF API key for <domain>; run: aws wafv2 create-api-key --scope REGIONAL --token-domains <domain> (DEPLOYMENT.md § 2)". It is called in `update` **before `deploy_all_stacks`** when `WAF_CAPTCHA=1`, right after the region checks, so a missing permission or key fails before any AWS state changes. `resolve_frontend_publish_config` keeps its place and no longer needs to resolve them. `require_production_build_environment` adds both names to its check when `WAF_CAPTCHA=1`. The guard harness (`PA_DEPLOY_GUARD_ONLY=1`) gains one line, `WAF_CAPTCHA="${PA_DEPLOY_GUARD_WAF_CAPTCHA:-$WAF_CAPTCHA}"`, read nowhere else, so the test can exercise both cases regardless of the committed config. `scripts/test_deploy_build_guard.sh` gains: with the override `1`, each of the two values missing fails; with `0`, both missing passes. The key lookup gets its own stubbed-`aws` case in the same file (a recorded `list-api-keys` reply with a matching key, one without). `infra/DEPLOYMENT.md` § 1 lists `wafv2:ListAPIKeys` for the deploy role; § 2 adds the API key as a precondition for both accounts with the one command. |
| P8 | W8 report | `scripts/waf_report.sh <env> [days] [--addresses]`: resolves the web ACL by name (`aws wafv2 list-web-acls --scope REGIONAL`), prints per rule `CountedRequests`, `BlockedRequests`, `CaptchaRequests` sums from `aws cloudwatch get-metric-statistics` (namespace `AWS/WAFV2`, dimensions `WebACL`, `Rule`, `Region`, period one day), then `aws logs start-query` on the log group with a Logs Insights query grouped by the rule inside the group (the `ruleGroupList` match fields and `nonTerminatingMatchingRules`; the exact field names are read from one real staging record at build and recorded in `verification.md`) and `httpRequest.uri`, adding `httpRequest.clientIp` with `--addresses`, waits for the result and prints it. Read-only; no `set -x`. Same `bash` conventions as `fe_api_smoke.sh`. `scripts/test_waf_report.sh` runs it with a fake `aws` function returning recorded JSON that includes one counted rule inside a group, and asserts that rule's name is printed; the Makefile makes it a prerequisite of `deploy-build-guard-test`, so CI runs it with no workflow change. |
| P9 | Docs | `infra/DEPLOYMENT.md` § 1 (permission), § 2 (API key precondition), § The firewall (contract W8 list, including the emergency `disassociate-web-acl` command and the repeated pass after the block switch). `docs/specs/system/web-api.md` § Waitlist: one sentence ("Behind the firewall, the form sends a CAPTCHA token in `x-aws-waf-token`; the API never reads it"). `docs/deferred.md`: update the 2026-09-03 line and the H-02 line, add the alerts, exclusion-list, production-CAPTCHA and GitHub-runner seams. ADR 0047 as built. One `docs/specs/log.md` line. `docs/agentic-ops/environment.md` header line (step 8). |
| P10 | Gates | Full `make verify` plus `make -C infra test` at build-open (gate 1) and at the step-6 exit (gate 2, plus `make audit` and `make deploy-build-guard-test`). Phase 1 gates on `make -C infra test`; Phase 2 on `make deploy-build-guard-test`; Phase 3 on `make verify-fast`. No phase touches schema, auth or the runtime, so no mid-build full gate. |

## Phases

| Phase | Problems | Work | Executor | Gate |
|---|---|---|---|---|
| 0 | — | Build-open baseline: `make verify`, `make -C infra test`, `make deploy-build-guard-test`. (The `aws_cdk.aws_wafv2` property names in P6 were confirmed against the installed package at plan time.) | `fast-worker` (commands whose output is pasted into `verification.md`) | full verify |
| 1 | W1 to W5, W8 log | P1 to P4 and P6: the component, the stack call, the config keys, synth tests for both environments (enabled, disabled, bad mode, captcha without enabled, each rule's statement and action per mode, host scope-downs, the two path transformations, the body-size override, the CAPTCHA rule only with `captcha` and ahead of W2, token domains, the log group, destination ARN and filter). | `codex` (unfamiliar L1 API, multi-property coherence, machine-verifiable by the synth tests) | `make -C infra test` |
| 2 | W7, W8 report | P7 and P8: the config validation, the pre-deploy step, the guard, the report script, both script tests, the Makefile prerequisite. | `codex` (two shell scripts against AWS CLI output shapes, verifiable by the script tests) | `make deploy-build-guard-test` + `make verify-fast` |
| 3 | W6 | P5: the hook, the form, the CORS header, the vitest cases, the preflight test. | `frontend-designer` for the hook, the form and its tests (the slice's only user-facing surface; widget placement is its call); `fast-worker` for the one-line CORS change and its test | `make verify-fast` |
| 4 | docs | P9. | lead (owner-facing prose and the decision record) | step-6 exit: full verify + `make -C infra test` + `make deploy-build-guard-test` + `make audit` |
| staging | all | Before the deploy: the owner adds the deploy-role permission and creates the API key in the staging account (§ 2). Push to `dev`, wait for the staging deploy, run the contract's live checks and the deliberate pass, run the report, read one real log record for the field names, record in `verification.md` with one screenshot of the puzzle. | lead (the owner's accounts and browser) | — |

Every `lead` mark: Phase 4 is owner-facing prose and a decision record; the staging check
needs the owner's accounts.

## Risks and how the plan meets them

- **The association fails from the app stack.** The imported load balancer's ARN resolves
  at deploy time through SSM, and `CfnWebACLAssociation.resource_arn` takes a string, so
  synth cannot see a problem that deploy would. The first staging deploy is the proof; the
  contract's stop condition names the fallback (move the component to the network stack).
- **The deploy turns the CAPTCHA on before the frontend can answer it.** The values are
  resolved before the stack deploy, so a missing permission or key fails with nothing
  changed. The minutes between the service coming back and the new bundle being published
  are an accepted window (contract W7); production ships with the CAPTCHA off and turns it
  on by a later config change, after staging has proved the flow.
- **The token is refused cross-origin.** The research notes rest on one AWS blog for the
  claim that the page's domain is what the token carries. The token domain list with the
  environment's domain covers both readings (page and API are its subdomains). The live
  check W5/W6 is the proof.
- **An encoded path skips the waitlist rules.** The API routes on the decoded path; the
  rules decode before comparing (`URL_DECODE` then `LOWERCASE`). A synth assertion and a
  live `curl` with `%74` cover it.
- **The form shows a puzzle locally.** Only when `VITE_WAF_CAPTCHA_SCRIPT_URL` is set, which
  `make dev`, CI and the mock journey never do. No test fixture sets it except the vitest
  cases that stub it.
- **A slow or blocked script locks a person out.** The puzzle renders whenever the script
  arrives, even after the 10-second message; a person with a blocker that stops
  `awswaf.com` sees the reload message and cannot sign up, which is the price of a CAPTCHA
  and is recorded in `docs/deferred.md` (a contact address next to the message is privacy
  notice work).
- **A tokenless request is counted toward the waitlist rate limit.** The CAPTCHA rule runs
  first and ends evaluation on refusal, so a script with no token never reaches the rate
  rule; a script with a stolen token is bounded by it at 50.
- **The count week sees nothing because traffic is low.** The deliberate pass in the live
  check creates the matches that matter (a body over 8 KB, an upload, a public view) and the
  report is run right after it, from the log and inside the three-hour sample window.
- **The log hides the rule that matched.** In count mode every request ends at the default
  action, so the terminating rule is never the managed rule. The filter keeps
  `EXCLUDED_AS_COUNT` and the report groups by the rule-group match fields; one real record
  from staging confirms the field names before the report is trusted.
- **Metabase traffic.** Every rule is scoped to the API host or the waitlist path, so the
  Metabase host matches nothing and keeps its own IP allowlist. The live check sends one
  request to it and expects no match.
- **The deploy's readiness check in block mode** (contract owner item 5): accepted.
- **The API key cannot be edited.** A domain change needs a new key, created by hand; the
  deploy script matches by token domains, so it picks the right one and names the command
  when none fits.

## Owner items at the plan gate

1. Contract § Owner items 1 to 3 and 5 (puzzle versus challenge; the 3,000 limit; whether
   production runs its own count week; the readiness-check risk).
2. **Two hand steps per account before the first deploy:** add `wafv2:ListAPIKeys` to the
   deploy role, and run `aws wafv2 create-api-key --scope REGIONAL --token-domains
   <domain_name>`. The alternative, letting the script create the key, needs
   `wafv2:CreateAPIKey` as well and one more code path; this plan chooses the hand step.
   Confirm.
