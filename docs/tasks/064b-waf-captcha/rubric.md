# Rubric: 064b-waf-captcha

The slice is **done only if every box holds**. Problem numbers W1 to W8 and the terms are
defined in [contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] `make verify`, `make -C infra test` and `make deploy-build-guard-test` pass; the
       staging live checks in the contract pass and are recorded, with the count week's
       outcome recorded as done or pending.
3. [ ] No approval-gated change beyond the contract's list: three config keys, the web ACL,
       its association, its log group and logging configuration in both accounts, one WAF
       API key per account (created by hand), one deploy-role permission per account
       (`wafv2:ListAPIKeys`, added by hand), one CORS header, two `VITE_*` values, one
       deploy-script pre-deploy step and guard, two new scripts, the matching spec sentence.
4. [ ] No generated files or secrets edited by hand. The CAPTCHA script URL and API key are
       public values and are never stored as secrets.
5. [ ] No tests deleted, skipped or weakened without written justification. The container
       environment test (`test_api_container_has_the_complete_deployed_plain_environment_map`)
       keeps its closed set unchanged, because no new variable reaches the container.
6. [ ] One test per problem exists and fails on the old code: W1 the web ACL and the
       association synthesise for both environments when `waf.enabled` is true, nothing
       WAF-shaped synthesises when it is false, an unknown `waf.mode` value raises, and
       `captcha: true` with `enabled: false` raises; W2 the waitlist rate rule has limit 50,
       block action in both modes, and a scope-down of `POST` and the path with the
       `URL_DECODE` then `LOWERCASE` transformations; W3 the general rate rule has the limit
       pinned in Phase 0 (at least 3,000), a scope-down to the API host, and an action that
       follows `waf.mode`; W4 the three groups are present, scoped to the API host with
       `/healthz` and `/readyz` excluded, their override follows `waf.mode`, and
       `SizeRestrictions_BODY` is counted in both modes; W5 the CAPTCHA rule is present only
       with `waf.captcha`, has a lower priority number than W2, its statement is `POST` and
       the transformed path, immunity 1,800, and the token domain list equals
       `[domain_name]` for the environment; W6 vitest: no script URL means no puzzle and no
       token header, a configured URL and a solved puzzle send the header, a `405` with
       `x-amzn-waf-action: captcha` shows the solve-again message and renders the puzzle
       again, a plain `405` shows the generic one, and a script that never loads shows the
       reload message with submit disabled; and the backend preflight asking for
       `content-type, x-aws-waf-token` is allowed; W7 the guard fails on a missing CAPTCHA
       value when CAPTCHA is on and passes when it is off, and the key lookup against a
       stubbed `aws` takes the key whose domains match and fails with the named command
       when none does; W8 the logging configuration synthesises with the `aws-waf-logs-`
       group, one-month retention, a destination ARN without `:*`, and a filter that keeps
       `COUNT`, `BLOCK`, `CAPTCHA` and `EXCLUDED_AS_COUNT` and drops the rest; and the
       report script, run against recorded output that includes a counted rule inside a
       group, prints that rule's name.
7. [ ] Verification evidence recorded in [verification.md](verification.md), including one
       screenshot of the puzzle in the form, the first report-script output with addresses
       removed, and one real log record (addresses removed) showing the field that names
       the rule inside a group.
8. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md): the
       2026-09-03 "no CAPTCHA" line updated; H-02 marked as not closable at the load
       balancer (8 KB inspection) and left for an API-side body limit; no alerts on WAF
       metrics until an alarm topic exists; the count-to-block switch and production's
       CAPTCHA as follow-on config changes; the rule exclusion list hard-coded until a
       second name is needed; the GitHub-runner readiness risk in block mode.
9. [ ] ADR 0047 written and accepted; `infra/DEPLOYMENT.md` documents the deploy-role
       permission (§ 1), the API key precondition (§ 2) and, in § The firewall, the three
       keys, the count week, the switch to block with the repeated pass, the exclusion of a
       rule, the off switch by config, the emergency off switch, the token domain and where
       the CAPTCHA values come from.
10. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
