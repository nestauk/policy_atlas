#!/usr/bin/env bash
# Print read-only WAF metrics and matched-request report data for one environment.
# It writes nothing and uses the operator's current AWS credentials.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
config_file="$repo_root/infra/pa_config.json"
addresses=0
env_name=""
days=""

for argument in "$@"; do
    case "$argument" in
        --addresses) addresses=1 ;;
        staging|prod)
            if [[ -n "$env_name" ]]; then
                echo "FAIL: specify exactly one environment" >&2
                exit 2
            fi
            env_name="$argument"
            ;;
        *)
            if [[ -z "$days" && "$argument" =~ ^[0-9]+$ ]]; then
                days="$argument"
            else
                echo "Usage: $0 <staging|prod> [days] [--addresses]" >&2
                exit 2
            fi
            ;;
    esac
done

if [[ -z "$env_name" ]]; then
    echo "Usage: $0 <staging|prod> [days] [--addresses]" >&2
    exit 2
fi
days="${days:-7}"
if (( days < 1 )); then
    echo "FAIL: days must be at least 1" >&2
    exit 2
fi

IFS=$'\t' read -r region domain_name <<<"$(python3 -c '
import json
import sys

config = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]]
app = config["policy_atlas_config"]
print("{}\t{}".format(config["aws_region"], app["domain_name"]))
' "$config_file" "$env_name")"

IFS=$'\t' read -r start_time end_time <<<"$(python3 -c '
import sys
import time

end = int(time.time())
print(f"{end - int(sys.argv[1]) * 86400}\t{end}")
' "$days")"

web_acl_name="policy-atlas-v3-api"
log_group="aws-waf-logs-policy-atlas-v3"

echo "Web ACL"
web_acls="$(aws wafv2 list-web-acls --scope REGIONAL --region "$region" --output json)"
IFS=$'\t' read -r web_acl_id web_acl_arn <<<"$(python3 -c '
import json
import sys

for acl in json.load(sys.stdin).get("WebACLs", []):
    if acl.get("Name") == sys.argv[1]:
        print("{}\t{}".format(acl.get("Id", ""), acl.get("ARN", "")))
        break
' "$web_acl_name" <<<"$web_acls")" || true
if [[ -z "${web_acl_id:-}" ]]; then
    echo "FAIL: web ACL ${web_acl_name} is absent (the firewall may be off or this is the wrong account)" >&2
    exit 1
fi
echo "${web_acl_name} (${web_acl_arn})"

echo "Rules"
web_acl="$(aws wafv2 get-web-acl --scope REGIONAL --region "$region" --name "$web_acl_name" --id "$web_acl_id" --output json)"
# A read loop, not mapfile: macOS ships bash 3.2.
rules=()
while IFS= read -r rule_name; do
    rules+=("$rule_name")
done < <(python3 -c '
import json
import sys
for rule in json.load(sys.stdin).get("WebACL", {}).get("Rules", []):
    print(rule["Name"])
' <<<"$web_acl")
printf '%s\n' "${rules[@]}"

metric_sum() {
    local metric_name="$1" rule_name="$2" response
    response="$(aws cloudwatch get-metric-statistics \
        --namespace AWS/WAFV2 \
        --metric-name "$metric_name" \
        --dimensions "Name=WebACL,Value=${web_acl_name}" "Name=Rule,Value=${rule_name}" "Name=Region,Value=${region}" \
        --statistics Sum \
        --period 86400 \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --region "$region" \
        --output json)"
    python3 -c 'import json, sys; print(sum(point.get("Sum", 0) for point in json.load(sys.stdin).get("Datapoints", [])))' <<<"$response"
}

echo "Metrics (last ${days} days; ${domain_name})"
printf '%-32s %8s %8s %8s\n' "rule" "counted" "blocked" "captcha"
for rule_name in "${rules[@]}" "ALL"; do
    counted="$(metric_sum CountedRequests "$rule_name")"
    blocked="$(metric_sum BlockedRequests "$rule_name")"
    captcha="$(metric_sum CaptchaRequests "$rule_name")"
    printf '%-32s %8s %8s %8s\n' "$rule_name" "$counted" "$blocked" "$captcha"
done

# The live staging check confirms these WAF log field names before operators rely on it.
logs_query='fields httpRequest.uri as path, terminatingRuleId, ruleGroupList.0.terminatingRule.ruleId as g0t, ruleGroupList.0.nonTerminatingMatchingRules.0.ruleId as g0n, ruleGroupList.1.terminatingRule.ruleId as g1t, ruleGroupList.1.nonTerminatingMatchingRules.0.ruleId as g1n, ruleGroupList.2.terminatingRule.ruleId as g2t, ruleGroupList.2.nonTerminatingMatchingRules.0.ruleId as g2n | stats count(*) as requests by coalesce(g0t, g0n, g1t, g1n, g2t, g2n, terminatingRuleId) as rule, path | sort requests desc | limit 100'
if (( addresses )); then
    logs_query='fields httpRequest.uri as path, httpRequest.clientIp as address, terminatingRuleId, ruleGroupList.0.terminatingRule.ruleId as g0t, ruleGroupList.0.nonTerminatingMatchingRules.0.ruleId as g0n, ruleGroupList.1.terminatingRule.ruleId as g1t, ruleGroupList.1.nonTerminatingMatchingRules.0.ruleId as g1n, ruleGroupList.2.terminatingRule.ruleId as g2t, ruleGroupList.2.nonTerminatingMatchingRules.0.ruleId as g2n | stats count(*) as requests by coalesce(g0t, g0n, g1t, g1n, g2t, g2n, terminatingRuleId) as rule, path, address | sort requests desc | limit 100'
fi

echo "Matched requests"
query_start="$(aws logs start-query --log-group-name "$log_group" --start-time "$start_time" --end-time "$end_time" --query-string "$logs_query" --region "$region" --output json)"
query_id="$(python3 -c 'import json, sys; print(json.load(sys.stdin)["queryId"])' <<<"$query_start")"
deadline=$((SECONDS + 60))
while true; do
    query_results="$(aws logs get-query-results --query-id "$query_id" --region "$region" --output json)"
    status="$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("status", ""))' <<<"$query_results")"
    case "$status" in
        Complete) break ;;
        Failed|Cancelled)
            echo "FAIL: Logs Insights query $status" >&2
            exit 1
            ;;
    esac
    if (( SECONDS >= deadline )); then
        echo "FAIL: Logs Insights query did not complete within 60 seconds" >&2
        exit 1
    fi
    sleep 2
done

if ! rendered="$(python3 -c '
import json
import sys

include_address = sys.argv[1] == "1"
rows = json.load(sys.stdin).get("results", [])
if not rows:
    raise SystemExit(1)
print("{:<32} {:>8} {:<40}{}".format("rule", "requests", "path", " address" if include_address else ""))
for row in rows:
    values = {entry["field"]: entry.get("value", "") for entry in row}
    suffix = " " + values.get("address", "") if include_address else ""
    print("{:<32} {:>8} {:<40}{}".format(values.get("rule", ""), values.get("requests", "0"), values.get("path", ""), suffix))
' "$addresses" <<<"$query_results")"; then
    echo "no matched requests in the period"
else
    printf '%s\n' "$rendered"
fi
