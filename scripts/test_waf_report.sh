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
            printf '%s\n' '{"status":"Complete","results":[[{"field":"rule","value":"SizeRestrictions_BODY"},{"field":"requests","value":"3"},{"field":"path","value":"/api/v1/tasks/abc/chat"},{"field":"address","value":"203.0.113.8"}]]}'
            ;;
        *) echo "unexpected aws call: $*" >&2; return 1 ;;
    esac
}
export -f aws

output="$(bash "$report_script" staging 7)"
if [[ "$output" != *"SizeRestrictions_BODY"* ]] || ! grep -Eq '^managed-common +3 +0 +0$' <<<"$output"; then
    echo "ERROR: report did not print the recorded counted rule and metric" >&2
    printf '%s\n' "$output" >&2
    exit 1
fi

: >"$STUB_LOG"
bash "$report_script" --addresses staging 7 >/dev/null
if ! grep -Fq 'httpRequest.clientIp as address' "$STUB_LOG"; then
    echo "ERROR: --addresses did not add clientIp to the Logs Insights query" >&2
    exit 1
fi

echo "test-waf-report: PASS"
