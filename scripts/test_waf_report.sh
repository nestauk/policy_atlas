#!/usr/bin/env bash
# Exercise waf_report.sh against a recorded-shaped, read-only AWS CLI stub.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_script="$repo_root/scripts/waf_report.sh"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/policy-atlas-waf-report.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
export STUB_LOG="$work_dir/aws.log"

aws() {
    echo "aws $*" >>"$STUB_LOG"
    case "$1 $2" in
        "wafv2 list-web-acls")
            printf '%s\n' '{"WebACLs":[{"Name":"policy-atlas-v3-api","Id":"acl-1","ARN":"arn:aws:wafv2:eu-west-2:123456789012:regional/webacl/policy-atlas-v3-api/acl-1"}]}'
            ;;
        "wafv2 get-web-acl")
            printf '%s\n' '{"WebACL":{"Rules":[{"Name":"waitlist-captcha"},{"Name":"waitlist-rate"},{"Name":"general-rate"},{"Name":"managed-common"},{"Name":"managed-known-bad-inputs"},{"Name":"managed-ip-reputation"}]}}'
            ;;
        "cloudwatch get-metric-statistics")
            if [[ "$*" == *"CountedRequests"* && "$*" == *"Name=Rule,Value=managed-common"* ]]; then
                printf '%s\n' '{"Datapoints":[{"Sum":3}]}'
            else
                printf '%s\n' '{"Datapoints":[]}'
            fi
            ;;
        "logs start-query") printf '%s\n' '{"queryId":"q1"}' ;;
        "logs get-query-results")
            # Two WAF-shaped records (the "log fields" page's shape): one request
            # that matched two rules inside the common group and the ACL's own
            # count-mode general-rate rule, ending at the default action; one
            # refused by the CAPTCHA rule. Addresses are documentation-range.
            printf '%s\n' "$STUB_RESULTS_JSON"
            ;;
        *) echo "unexpected aws call: $*" >&2; return 1 ;;
    esac
}
export -f aws

record_chat='{"timestamp":1,"action":"ALLOW","terminatingRuleId":"Default_Action","terminatingRuleType":"REGULAR","httpRequest":{"clientIp":"203.0.113.8","uri":"/api/v1/tasks/abc/chat","httpMethod":"POST"},"nonTerminatingMatchingRules":[{"ruleId":"general-rate","action":"COUNT"}],"ruleGroupList":[{"ruleGroupId":"AWS#AWSManagedRulesCommonRuleSet","terminatingRule":null,"nonTerminatingMatchingRules":[{"ruleId":"SizeRestrictions_BODY","action":"COUNT","overriddenAction":"BLOCK"},{"ruleId":"CrossSiteScripting_BODY","action":"COUNT"}],"excludedRules":null}]}'
record_waitlist='{"timestamp":2,"action":"CAPTCHA","terminatingRuleId":"waitlist-captcha","terminatingRuleType":"REGULAR","httpRequest":{"clientIp":"203.0.113.9","uri":"/api/v1/waitlist","httpMethod":"POST"},"nonTerminatingMatchingRules":[],"ruleGroupList":[]}'
export STUB_RESULTS_JSON
STUB_RESULTS_JSON="$(python3 -c '
import json, sys
rows = [[{"field": "@message", "value": m}] for m in sys.argv[1:]]
print(json.dumps({"status": "Complete", "results": rows}))
' "$record_chat" "$record_waitlist")"

output="$(bash "$report_script" staging 7)"
for expected in 'SizeRestrictions_BODY +1 +/api/v1/tasks/abc/chat' 'CrossSiteScripting_BODY +1 +/api/v1/tasks/abc/chat' \
    'general-rate +1 +/api/v1/tasks/abc/chat' 'waitlist-captcha +1 +/api/v1/waitlist' '^managed-common +3 +0 +0$'; do
    if ! grep -Eq "$expected" <<<"$output"; then
        echo "ERROR: report is missing the row: $expected" >&2
        printf '%s\n' "$output" >&2
        exit 1
    fi
done
if [[ "$output" == *"Default_Action"* || "$output" == *"203.0.113"* ]]; then
    echo "ERROR: report printed the default action as a rule, or an address without --addresses" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi
if ! grep -q 'Name=WebACL,Value=policy-atlas-v3-api' "$STUB_LOG"; then
    echo "ERROR: metrics were not queried by the web ACL metric name" >&2
    exit 1
fi

with_addresses="$(bash "$report_script" --addresses staging 7)"
if ! grep -Eq 'waitlist-captcha +1 +/api/v1/waitlist +203\.0\.113\.9' <<<"$with_addresses"; then
    echo "ERROR: --addresses did not print the client address" >&2
    printf '%s\n' "$with_addresses" >&2
    exit 1
fi

echo "test-waf-report: PASS"
