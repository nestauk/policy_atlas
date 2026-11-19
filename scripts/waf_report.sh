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

config = json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2])
if config is None:
    raise SystemExit(f"FAIL: environment {sys.argv[2]!r} is missing from infra/pa_config.json")
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

# The log holds matched requests only (the logging filter drops the rest), so the
# records are few: fetch them raw and group in Python, reading every place a rule
# name can appear (a request can match several rules, inside and outside groups).
# ponytail: Logs Insights returns at most 10,000 records per query; a count week
# with more matched requests than that needs a shorter period or paging by day.
logs_query='fields @message | sort @timestamp desc | limit 10000'

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

# One row per (rule, path[, address]); a request that matched several rules is
# counted under each, because the question is per rule. The rule names come from: the
# rules inside each managed group (terminatingRule, nonTerminatingMatchingRules,
# excludedRules of every ruleGroupList entry), the web ACL's own non-terminating
# matches (a count-mode rule such as general-rate), and the terminating rule when
# it is the ACL's own (not Default_Action, not a group whose inner rule is listed).
# Field names per the AWS "log fields" page; the staging live check confirms them.
if ! rendered="$(python3 -c '
import json
import sys
from collections import Counter

include_address = sys.argv[1] == "1"
rows = json.load(sys.stdin).get("results", [])
counts = Counter()
for row in rows:
    message = next((e.get("value") for e in row if e.get("field") == "@message"), None)
    if not message:
        continue
    record = json.loads(message)
    request = record.get("httpRequest", {})
    path = request.get("uri", "")
    address = request.get("clientIp", "") if include_address else None
    names = []
    for group in record.get("ruleGroupList") or []:
        terminating = group.get("terminatingRule") or {}
        if terminating.get("ruleId"):
            names.append(terminating["ruleId"])
        for match in (group.get("nonTerminatingMatchingRules") or []) + (group.get("excludedRules") or []):
            if match.get("ruleId"):
                names.append(match["ruleId"])
    for match in record.get("nonTerminatingMatchingRules") or []:
        if match.get("ruleId"):
            names.append(match["ruleId"])
    terminating_id = record.get("terminatingRuleId")
    if terminating_id and terminating_id != "Default_Action" and record.get("terminatingRuleType") != "MANAGED_RULE_GROUP":
        names.append(terminating_id)
    for name in names:
        counts[(name, path, address)] += 1
if not counts:
    raise SystemExit(1)
header = "{:<32} {:>8} {:<40}".format("rule", "requests", "path") + (" address" if include_address else "")
print(header)
for (name, path, address), n in sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
    print("{:<32} {:>8} {:<40}".format(name, n, path) + (" " + address if include_address else ""))
' "$addresses" <<<"$query_results")"; then
    echo "no matched requests in the period"
else
    printf '%s\n' "$rendered"
fi
