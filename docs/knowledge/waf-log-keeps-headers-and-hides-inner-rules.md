---
type: Integration quirk
title: A WAF log record keeps every request header, and a rule inside a managed group shows only in the log, never in the metrics
description: Redact `authorization` (and `cookie`, `x-aws-waf-token`) in the logging configuration or a counted signed-in request stores the bearer token for the log's retention; the CloudWatch `WebACL` dimension is the ACL's metric name; a group-level count override reports the group, so the rule that matched is read from the log's `ruleGroupList`, grouped client-side because a Logs Insights `stats` sees only the first element of an array.
tags: [waf, logging, cloudwatch, redaction, security, metrics, logs-insights, integration-quirk]
generated:
  by: process:okf-migrate
  at: 2026-11-17
sources:
  - resource: "../tasks/064b-waf-captcha/verification.md"
    title: "[task 064b verification](../tasks/064b-waf-captcha/verification.md) \u00a7 Review findings (security lane; contract verifier F2, F3; Codex adversarial 1, 2)."
  - resource: "infra/infra/components/waf.py"
    title: "`infra/infra/components/waf.py` (`REDACTED_HEADERS`, the ACL's visibility config), `scripts/waf_report.sh`, `scripts/test_waf_report.sh`."
  - resource: "AWS WAF developer guide: \"Log fields\", \"Monitoring with CloudWatch\"."
    title: "AWS WAF developer guide: \"Log fields\", \"Monitoring with CloudWatch\"."
  - resource: "infra/DEPLOYMENT.md"
    title: "`infra/DEPLOYMENT.md` \u00a7 4 \"The firewall\"."
---

# Rule

Four facts about AWS WAF on the load balancer that the 064b review stack established,
each the kind that costs a deploy or a leak to learn live:

1. **The log stores every request header.** A WAF log record carries
   `httpRequest.headers` in full. With a filter that keeps counted requests, any
   authenticated request a rule counts (a body over 8 KB, a managed-rule false positive on
   free text) writes the `Authorization: Bearer …` header into the log group for its
   retention, readable by anyone with `logs:GetLogEvents` in the account. Name the headers
   in `RedactedFields` (`authorization`, `cookie`, `x-aws-waf-token`) and assert them in
   the synth test. The API's own promise "raw bearer token, never logged" does not reach
   a log AWS writes before the API.
2. **The CloudWatch `WebACL` dimension takes the web ACL's *metric name*, not its name.**
   The same for `Rule`. Give the ACL a metric name equal to its name, so a report script
   queries one constant; otherwise every total silently reads 0.
3. **A whole-group count override hides the inner rule from the metrics.** In count mode
   the metrics and the terminating rule name the group; the rule that matched is in the
   log's `ruleGroupList[].terminatingRule` / `nonTerminatingMatchingRules[]` /
   `excludedRules[]`, and an ACL-level count rule is in the record's top-level
   `nonTerminatingMatchingRules[]` with `terminatingRuleId: Default_Action`.
4. **A Logs Insights `stats … by` over an array field sees only the element you index.**
   `ruleGroupList.0.nonTerminatingMatchingRules.0.ruleId` drops the second match and the
   second group. Fetch the raw records (`fields @message`, the filtered log is small) and
   group in Python over every list; count a request once per rule it matched.

Also from the same stack: an emergency `disassociate-web-acl` is not undone by the next
deploy, because CloudFormation updates only changed template resources and does not
detect the drift (see [noop-deploys-dont-reassert-template-pins](noop-deploys-dont-reassert-template-pins.md));
`associate-web-acl` by hand puts it back.
