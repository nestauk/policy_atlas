#!/usr/bin/env bash
# Deploy one configured v3 environment and perform the imperative post-CDK steps.
# This script deliberately never calls sts get-caller-identity: account IDs are
# sensitive operational metadata and must not be printed by deploy tooling.

set -euo pipefail

readonly CERTIFICATE_REGION="us-east-1"
readonly ENV_NAME="${PA_DEPLOY_ENV_NAME:-staging}"
readonly ECS_SERVICE_NAME="policy-atlas-v3-api-service"
readonly OPS_SERVICE_NAME="policy-atlas-v3-ops-service"
readonly SERVICE_STOP_TIMEOUT_SECONDS=600
readonly SERVICE_STOP_POLL_SECONDS=5
# The migration task is polled every 15 s for at most MIGRATION_WAIT_MAX_S seconds
# (default 5,400 = 90 minutes). `aws ecs wait tasks-stopped` gave up after about 10
# minutes, too short for a migration that backfills a large table (task 057).
readonly MIGRATION_POLL_SECONDS=15
readonly MIGRATION_WAIT_MAX_S="${MIGRATION_WAIT_MAX_S:-5400}"

readonly REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# Deployment configuration stays in the committed CDK config files. Resolve the
# small subset needed by this imperative wrapper once, and fail before any AWS call
# when an environment is missing or internally inconsistent.
deploy_config="$(python3 - "$REPO_ROOT/infra" "$ENV_NAME" <<'PY'
import json
import re
import sys
from pathlib import Path

config_dir = Path(sys.argv[1])
env_name = sys.argv[2]
if re.fullmatch(r"[a-z][a-z0-9-]*", env_name) is None:
    raise SystemExit(
        "FAIL: PA_DEPLOY_ENV_NAME must start with a lowercase letter and contain "
        "only lowercase letters, digits, and hyphens"
    )


def environment_config(filename: str) -> dict:
    with (config_dir / filename).open(encoding="utf-8") as config_file:
        environments = json.load(config_file)
    config = environments.get(env_name)
    if not isinstance(config, dict):
        raise SystemExit(
            f"FAIL: deployment environment {env_name!r} is missing from "
            f"infra/{filename}"
        )
    return config


network = environment_config("network_config.json")
database = environment_config("db_config.json")
application = environment_config("pa_config.json")

deploy_analytics = application.get("deploy_analytics", False)
if type(deploy_analytics) is not bool:
    raise SystemExit(
        f"FAIL: {env_name!r} deploy_analytics must be a JSON boolean"
    )

analytics = None
analytics_allowlist_parameter = "-"
metabase_domain = "-"
if deploy_analytics:
    analytics = environment_config("metabase_config.json")

regions = {
    network.get("aws_region"),
    database.get("aws_region"),
    application.get("aws_region"),
}
if analytics is not None:
    regions.add(analytics.get("aws_region"))
if None in regions or len(regions) != 1:
    raise SystemExit(
        f"FAIL: {env_name!r} must use one explicit aws_region across all CDK configs"
    )

app = application.get("policy_atlas_config", {})
backend = app.get("backend", {})
waf = backend.get("waf")
if not isinstance(waf, dict):
    raise SystemExit("FAIL: backend.waf must be an object")
if set(waf) != {"enabled", "mode", "captcha"}:
    raise SystemExit("FAIL: backend.waf must have exactly the keys enabled, mode, captcha")
if type(waf["enabled"]) is not bool:
    raise SystemExit("FAIL: backend.waf.enabled must be a JSON boolean")
if type(waf["captcha"]) is not bool:
    raise SystemExit("FAIL: backend.waf.captcha must be a JSON boolean")
if waf["mode"] not in ("count", "block"):
    raise SystemExit("FAIL: backend.waf.mode must be count or block")
if waf["captcha"] and not waf["enabled"]:
    raise SystemExit("FAIL: backend.waf.captcha requires backend.waf.enabled")
ops = app.get("ops", {})
public_domain = network.get("public_domain_name")
if not public_domain or app.get("domain_name") != public_domain:
    raise SystemExit(
        f"FAIL: {env_name!r} must use the same non-empty domain in network_config.json "
        "and pa_config.json"
    )

if analytics is not None:
    container = analytics.get("container", {})
    analytics_database = analytics.get("database", {})
    if analytics.get("domain_name") != public_domain:
        raise SystemExit(
            f"FAIL: {env_name!r} must use the same domain in metabase_config.json"
        )
    subdomain = analytics.get("metabase_subdomain")
    if not isinstance(subdomain, str) or re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain
    ) is None:
        raise SystemExit("FAIL: metabase_subdomain must be a valid DNS label")
    metabase_domain = f"{subdomain}.{public_domain}"
    analytics_allowlist_parameter = analytics.get(
        "allowed_cidrs_parameter_name"
    )
    if not isinstance(analytics_allowlist_parameter, str) or re.fullmatch(
        r"/policy_atlas_v3/metabase/[A-Za-z0-9_.-]+",
        analytics_allowlist_parameter,
    ) is None:
        raise SystemExit(
            "FAIL: allowed_cidrs_parameter_name must be under "
            "/policy_atlas_v3/metabase/"
        )

    exact_image_tag = container.get("image_tag")
    if not isinstance(exact_image_tag, str) or re.fullmatch(
        r"v\d+\.\d+\.\d+\.\d+", exact_image_tag
    ) is None:
        raise SystemExit(
            "FAIL: Metabase image_tag must pin an exact four-part release"
        )

    positive_container_values = {
        "cpu": container.get("cpu"),
        "memory_limit_mib": container.get("memory_limit_mib"),
        "application_connection_pool_size": container.get(
            "application_connection_pool_size"
        ),
        "warehouse_connection_pool_size": container.get(
            "warehouse_connection_pool_size"
        ),
    }
    invalid_container_values = [
        name
        for name, value in positive_container_values.items()
        if type(value) is not int or value <= 0
    ]
    if invalid_container_values:
        raise SystemExit(
            "FAIL: Metabase container values must be positive integers: "
            + ", ".join(invalid_container_values)
        )
    if container.get("desired_count") != 1:
        raise SystemExit(
            "FAIL: Metabase must use desired_count 1 for safe migrations"
        )
    internal_port = container.get("internal_port")
    if type(internal_port) is not int or not 1 <= internal_port <= 65535:
        raise SystemExit("FAIL: Metabase internal_port must be between 1 and 65535")
    if not isinstance(container.get("java_opts"), str) or not container["java_opts"]:
        raise SystemExit("FAIL: Metabase java_opts must be a non-empty string")

    instance_size = analytics_database.get("instance_size")
    if not isinstance(instance_size, str) or re.fullmatch(
        r"[a-z0-9]+\.[a-z0-9]+", instance_size
    ) is None:
        raise SystemExit(
            "FAIL: Metabase database instance_size must omit the db. prefix"
        )
    allocated_storage = analytics_database.get("allocated_storage")
    max_allocated_storage = analytics_database.get("max_allocated_storage")
    backup_days = analytics_database.get("backup_retention_days")
    if type(allocated_storage) is not int or allocated_storage < 20:
        raise SystemExit("FAIL: Metabase allocated_storage must be at least 20 GiB")
    if (
        type(max_allocated_storage) is not int
        or max_allocated_storage < allocated_storage
    ):
        raise SystemExit(
            "FAIL: Metabase max_allocated_storage must cover allocated_storage"
        )
    if type(backup_days) is not int or not 1 <= backup_days <= 35:
        raise SystemExit(
            "FAIL: Metabase backup_retention_days must be between 1 and 35"
        )
    if type(analytics_database.get("multi_az")) is not bool:
        raise SystemExit("FAIL: Metabase multi_az must be a JSON boolean")

required = {
    "backend_subdomain": app.get("backend_subdomain"),
    "cognito_domain_prefix": app.get("cognito_domain_prefix"),
    "backend.secret_name": backend.get("secret_name"),
}
missing = [name for name, value in required.items() if not isinstance(value, str) or not value]
if missing:
    raise SystemExit(
        f"FAIL: {env_name!r} deployment config is missing: {', '.join(missing)}"
    )

ops_subdomain = ops.get("subdomain")
if not isinstance(ops_subdomain, str) or re.fullmatch(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", ops_subdomain
) is None:
    raise SystemExit("FAIL: ops.subdomain must be a valid DNS label")
ops_allowlist_parameter = ops.get("allowed_cidrs_parameter_name")
if not isinstance(ops_allowlist_parameter, str) or re.fullmatch(
    r"/policy_atlas_v3/ops/[A-Za-z0-9_.-]+", ops_allowlist_parameter
) is None:
    raise SystemExit(
        "FAIL: ops.allowed_cidrs_parameter_name must be under /policy_atlas_v3/ops/"
    )
ops_desired_count = ops.get("desired_count")
if ops_desired_count not in (0, 1):
    raise SystemExit("FAIL: ops.desired_count must be 0 or 1")

values = [
    regions.pop(),
    public_domain,
    required["backend_subdomain"],
    required["backend.secret_name"],
    analytics_allowlist_parameter,
    metabase_domain,
    "1" if waf["enabled"] and waf["captcha"] else "0",
    ops_subdomain,
    ops_allowlist_parameter,
    str(ops_desired_count),
]
if any("\t" in value or "\n" in value for value in values):
    raise SystemExit("FAIL: deployment config values may not contain tabs or newlines")
print("\t".join(values))
PY
)"
IFS=$'\t' read -r DEPLOY_REGION PUBLIC_DOMAIN BACKEND_SUBDOMAIN APP_SECRET_NAME METABASE_ALLOWLIST_PARAMETER METABASE_DOMAIN WAF_CAPTCHA OPS_SUBDOMAIN OPS_ALLOWLIST_PARAMETER OPS_DESIRED_COUNT <<< "$deploy_config"
readonly DEPLOY_REGION PUBLIC_DOMAIN BACKEND_SUBDOMAIN APP_SECRET_NAME METABASE_ALLOWLIST_PARAMETER METABASE_DOMAIN OPS_SUBDOMAIN OPS_ALLOWLIST_PARAMETER OPS_DESIRED_COUNT
readonly API_BASE_URL="https://${BACKEND_SUBDOMAIN}.${PUBLIC_DOMAIN}"
readonly OPS_DOMAIN="${OPS_SUBDOMAIN}.${PUBLIC_DOMAIN}"

readonly SSM_CLUSTER_ARN="/policy_atlas_v3/deploy/cluster_arn"
readonly SSM_PRIVATE_SUBNET_IDS="/policy_atlas_v3/deploy/private_subnet_ids"
readonly SSM_MIGRATION_SG_ID="/policy_atlas_v3/deploy/migration_sg_id"
readonly SSM_MIGRATION_TASK_DEF_ARN="/policy_atlas_v3/deploy/migration_task_def_arn"
readonly SSM_FRONTEND_BUCKET_NAME="/policy_atlas_v3/deploy/frontend_bucket_name"
readonly SSM_FONTS_BUCKET_NAME="/policy_atlas_v3/deploy/fonts_bucket_name"
readonly SSM_DISTRIBUTION_ID="/policy_atlas_v3/deploy/distribution_id"
readonly SSM_USER_POOL_ID="/policy_atlas_v3/auth/user_pool_id"
readonly SSM_OIDC_ISSUER="/policy_atlas_v3/auth/issuer"
readonly SSM_OIDC_CLIENT_ID="/policy_atlas_v3/auth/client_id"
readonly SSM_SHARED_LISTENER_ARN="/policy_atlas_v3/shared_alb/https_listener_arn"
readonly SSM_OPS_TARGET_GROUP_ARN="/policy_atlas_v3/deploy/ops_target_group_arn"
readonly SSM_OPS_DB_SECRET_ARN="/policy_atlas_v3/deploy/ops_db_secret_arn"

usage() {
    echo "Usage: $0 {bootstrap|update|check}" >&2
}

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

# Checks echo looked-up values on stdout, so stdout is discarded; stderr carries
# the reason a check failed and is shown so a failed gate is diagnosable from
# the log. Deploy logs are public for this repository, so any 12-digit account
# id an AWS error message may carry (e.g. AccessDenied principal ARNs) is
# redacted first, and the allowlist validator itself never prints addresses.
gate_check() {
    local description="$1"
    shift
    local diagnostics

    if diagnostics="$("$@" 2>&1 >/dev/null)"; then
        echo "PASS: ${description}"
    else
        if [[ -n "$diagnostics" ]]; then
            printf '%s\n' "$diagnostics" | sed -E 's/[0-9]{12}/<account-id>/g' >&2
        fi
        fail "${description}"
    fi
}

# The order-only harness records the irreversible sequence while stubbing its
# external commands. Normal deploy output remains the existing gate messages.
deploy_step() {
    if [[ "${PA_DEPLOY_ORDER_ONLY:-}" == "1" ]]; then
        echo "$1"
    fi
}

# All Systems Manager reads go through this helper so deploy wiring never
# depends on hand-copied identifiers.
ssm_value() {
    local parameter_name="$1"
    aws ssm get-parameter \
        --region "$DEPLOY_REGION" \
        --name "$parameter_name" \
        --query 'Parameter.Value' \
        --output text
}

require_value() {
    local description="$1"
    local value="$2"

    if [[ -z "$value" || "$value" == "None" ]]; then
        fail "${description} is empty"
    fi
}

check_amazon_nameservers() {
    local nameservers
    nameservers="$(dig NS "$PUBLIC_DOMAIN" +short)"
    [[ -n "$nameservers" ]] && \
        printf '%s\n' "$nameservers" | grep -Eqi '\.awsdns-[0-9]+\.(com|net|org|co\.uk)\.?$'
}

check_cdk_bootstrap() {
    local region="$1"
    aws cloudformation describe-stacks \
        --region "$region" \
        --stack-name CDKToolkit >/dev/null
}

check_app_secret() {
    aws secretsmanager get-secret-value \
        --region "$DEPLOY_REGION" \
        --secret-id "$APP_SECRET_NAME" \
        --query SecretString \
        --output text | python3 -c '
import json
import sys

required = {
    "OPENAI_API_KEY",
    "OPENALEX_EMAIL",
    "OPENALEX_API_KEY",
    "OVERTON_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
}
secret = json.load(sys.stdin)
sys.exit(0 if required <= secret.keys() else 1)
'
}

check_cdk_account() {
    [[ -n "${CDK_DEFAULT_ACCOUNT:-}" ]]
}

check_metabase_allowlist_parameter() {
    aws ssm get-parameter \
        --region "$DEPLOY_REGION" \
        --name "$METABASE_ALLOWLIST_PARAMETER" \
        --query Parameter \
        --output json | \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist \
            validate --label "Metabase"
}

metabase_allowlist_size() {
    aws ssm get-parameter \
        --region "$DEPLOY_REGION" \
        --name "$METABASE_ALLOWLIST_PARAMETER" \
        --query Parameter \
        --output json | \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist size
}

check_ops_allowlist_parameter() {
    aws ssm get-parameter \
        --region "$DEPLOY_REGION" \
        --name "$OPS_ALLOWLIST_PARAMETER" \
        --query Parameter \
        --output json | \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist \
            validate --label "ops allowlist"
}

ops_allowlist_size() {
    aws ssm get-parameter \
        --region "$DEPLOY_REGION" \
        --name "$OPS_ALLOWLIST_PARAMETER" \
        --query Parameter \
        --output json | \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist \
            size --label "ops allowlist"
}

# The listener rules read the allowlist through an AWS::SSM::Parameter::Value
# template parameter, so their CIDRs are re-resolved by CloudFormation on every
# stack update (the CDK CLI never skips a stack that carries such a parameter,
# even when the template is unchanged). This check turns that assumption into
# an observed post-condition: after the CDK deploy, the Metabase rules on the
# shared listener must together match the parameter exactly. It prints counts,
# never addresses.
check_metabase_listener_rule_matches_allowlist() {
    local listener_arn allowlist_value
    listener_arn="$(ssm_value "$SSM_SHARED_LISTENER_ARN")"
    allowlist_value="$(ssm_value "$METABASE_ALLOWLIST_PARAMETER")"
    aws elbv2 describe-rules \
        --region "$DEPLOY_REGION" \
        --listener-arn "$listener_arn" \
        --query Rules \
        --output json | \
        METABASE_ALLOWLIST_VALUE="$allowlist_value" \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist \
            verify-rule --host "$METABASE_DOMAIN"
}

check_ops_listener_rule_matches_allowlist() {
    local listener_arn allowlist_value
    listener_arn="$(ssm_value "$SSM_SHARED_LISTENER_ARN")"
    allowlist_value="$(ssm_value "$OPS_ALLOWLIST_PARAMETER")"
    aws elbv2 describe-rules \
        --region "$DEPLOY_REGION" \
        --listener-arn "$listener_arn" \
        --query Rules \
        --output json | \
        METABASE_ALLOWLIST_VALUE="$allowlist_value" \
        PYTHONPATH="$REPO_ROOT/infra" python3 -m infra.metabase_allowlist \
            verify-rule --host "$OPS_DOMAIN" --label "ops allowlist"
}

check_ops_secret() {
    local secret_arn
    secret_arn="$(ssm_value "$SSM_OPS_DB_SECRET_ARN")"
    require_value "ops database secret ARN SSM export" "$secret_arn"
    aws secretsmanager describe-secret --region "$DEPLOY_REGION" --secret-id "$secret_arn" >/dev/null
}

check_ops_service() {
    local status
    status="$(aws ecs describe-services \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --services "$OPS_SERVICE_NAME" \
        --query 'services[0].status' \
        --output text)"
    [[ "$status" == "ACTIVE" ]]
}

check_ops_target_group_export() {
    local target_group_arn
    target_group_arn="$(ssm_value "$SSM_OPS_TARGET_GROUP_ARN")"
    require_value "ops target-group ARN SSM export" "$target_group_arn"
}

check_ops_db_connection_string() {
    local secret_arn
    secret_arn="$(ssm_value "$SSM_OPS_DB_SECRET_ARN")"
    aws secretsmanager get-secret-value \
        --region "$DEPLOY_REGION" \
        --secret-id "$secret_arn" \
        --query SecretString \
        --output text | python3 -c '
import json
import sys

secret = json.load(sys.stdin)
sys.exit(0 if isinstance(secret.get("db_connection_string"), str) and secret["db_connection_string"] else 1)
'
}

check_fonts_uploaded() {
    local listing
    listing="$(aws s3 ls "s3://${FONTS_BUCKET}/")"
    [[ -n "$listing" ]]
}

check_cognito_user_exists() {
    local user_count
    user_count="$(aws cognito-idp list-users \
        --region "$DEPLOY_REGION" \
        --user-pool-id "$USER_POOL_ID" \
        --max-items 1 \
        --query 'length(Users)' \
        --output text)"
    [[ "$user_count" == "1" ]]
}

bootstrap_preconditions() {
    echo "Preconditions gate A"
    gate_check "${PUBLIC_DOMAIN} delegates to Amazon Route 53 nameservers" check_amazon_nameservers
    gate_check "CDKToolkit exists in ${DEPLOY_REGION}" check_cdk_bootstrap "$DEPLOY_REGION"
    gate_check "CDKToolkit exists in ${CERTIFICATE_REGION}" check_cdk_bootstrap "$CERTIFICATE_REGION"
    gate_check "app secret exists and has every required key" check_app_secret
    gate_check "CDK_DEFAULT_ACCOUNT is set" check_cdk_account
}

bootstrap_postconditions() {
    FONTS_BUCKET="$(ssm_value "$SSM_FONTS_BUCKET_NAME")"
    USER_POOL_ID="$(ssm_value "$SSM_USER_POOL_ID")"
    require_value "fonts bucket SSM export" "$FONTS_BUCKET"
    require_value "Cognito user-pool SSM export" "$USER_POOL_ID"

    echo "Preconditions gate B"
    gate_check "fonts bucket contains at least one object" check_fonts_uploaded
    gate_check "Cognito user pool contains at least one user" check_cognito_user_exists
}

# CDK CLI via npx (the repo pins no global cdk binary); cdk.json's app command
# is "python app.py", so the infra venv must lead PATH for synth. Deploys are
# operator-run but non-interactive: the IAM/SG diff was reviewed at code level,
# so --require-approval never keeps the script from hanging on a prompt.
run_cdk() {
    # CLI version pinned (review finding, 026 step 7): an unpinned npx cdk
    # executes whatever npm serves that day with the operator's credentials.
    PATH="$REPO_ROOT/infra/.venv/bin:$PATH" npx cdk@2.1133.0 "$@" --require-approval never
}

deploy_all_stacks() {
    local analytics_context=() ops_context
    if [[ "$METABASE_ALLOWLIST_PARAMETER" != "-" ]]; then
        local allowlist_size
        allowlist_size="$(metabase_allowlist_size)"
        analytics_context=(-c "metabase_allowlist_size=${allowlist_size}")
    fi
    ops_context=(-c "ops_allowlist_size=$(ops_allowlist_size)")
    deploy_step "cdk deploy"
    (
        cd "$REPO_ROOT/infra"
        # app.py requires env_name; stage=all is explicit for reproducible deploys.
        # The `${array[@]+...}` form keeps an empty array safe under `set -u`
        # on the macOS bash 3.2 operators run this from.
        run_cdk deploy -c "env_name=${ENV_NAME}" -c stage=all \
            ${analytics_context[@]+"${analytics_context[@]}"} \
            ${ops_context[@]+"${ops_context[@]}"} --all
    )
    verify_metabase_allowlist_applied
}

# Removing an address from the allowlist only takes effect once a deploy has
# re-resolved the SSM parameter into the listener rules; fail loudly if the
# rules the deploy left behind differ from the parameter.
verify_metabase_allowlist_applied() {
    if [[ "$METABASE_ALLOWLIST_PARAMETER" == "-" ]]; then
        return 0
    fi
    echo "Postconditions gate: Metabase allowlist"
    gate_check \
        "Metabase listener rules' source-ip conditions match the SSM allowlist" \
        check_metabase_listener_rule_matches_allowlist
}

verify_ops_allowlist_applied() {
    echo "Postconditions gate: ops allowlist"
    gate_check \
        "ops listener rules' source-ip conditions match the SSM allowlist" \
        check_ops_listener_rule_matches_allowlist
}

bootstrap() {
    bootstrap_preconditions

    (
        cd "$REPO_ROOT/infra"
        run_cdk deploy -c "env_name=${ENV_NAME}" -c stage=network PaV3NetworkStack
    )

    deploy_all_stacks
    bootstrap_postconditions
}

# The template pins DesiredCount=0, but CloudFormation only re-asserts it when
# the stack actually changes — a no-change deploy (e.g. frontend-only) leaves
# the scaled-up service running and the stop-wait times out (E.2 finding,
# 2026-07-28). Explicitly aligning to the template value is idempotent and
# keeps stop-old-before-migrate deterministic on every path.
scale_down_service() {
    local service_name="$1"
    aws ecs update-service \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --service "$service_name" \
        --desired-count 0 >/dev/null
}

wait_for_service_to_stop() {
    local service_name="$1" service_label="$2" deadline running_count running_tasks
    deadline=$((SECONDS + SERVICE_STOP_TIMEOUT_SECONDS))

    while true; do
        running_count="$(aws ecs describe-services \
            --region "$DEPLOY_REGION" \
            --cluster "$CLUSTER_ARN" \
            --services "$service_name" \
            --query 'services[0].runningCount' \
            --output text)"
        running_tasks="$(aws ecs list-tasks \
            --region "$DEPLOY_REGION" \
            --cluster "$CLUSTER_ARN" \
            --service-name "$service_name" \
            --desired-status RUNNING \
            --query 'length(taskArns)' \
            --output text)"

        if [[ "$running_count" == "0" && "$running_tasks" == "0" ]]; then
            echo "PASS: ${service_label} service has no running tasks"
            return
        fi

        if (( SECONDS >= deadline )); then
            fail "timed out waiting for the ${service_label} service to stop"
        fi

        sleep "$SERVICE_STOP_POLL_SECONDS"
    done
}

migration_stopped_reason() {
    aws ecs describe-tasks \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --tasks "$MIGRATION_TASK_ARN" \
        --query 'tasks[0].stoppedReason' \
        --output text 2>/dev/null || true
}

# Poll the migration task until ECS reports it STOPPED, or fail loudly once
# MIGRATION_WAIT_MAX_S has passed. A failed describe-tasks call (a network blip or
# API throttling) counts as one more poll, not a failure. On timeout the task is
# left running: a migration stopped half-way is safe to rerun, but the operator
# decides (infra/DEPLOYMENT.md § 4).
wait_for_migration_task() {
    local deadline last_status stopped_reason

    if [[ ! "$MIGRATION_WAIT_MAX_S" =~ ^[0-9]+$ ]]; then
        fail "MIGRATION_WAIT_MAX_S must be a whole number of seconds"
    fi
    deadline=$((SECONDS + MIGRATION_WAIT_MAX_S))

    while true; do
        if ! last_status="$(aws ecs describe-tasks \
            --region "$DEPLOY_REGION" \
            --cluster "$CLUSTER_ARN" \
            --tasks "$MIGRATION_TASK_ARN" \
            --query 'tasks[0].lastStatus' \
            --output text)"; then
            last_status="UNKNOWN (describe-tasks failed)"
        fi

        if [[ "$last_status" == "STOPPED" ]]; then
            return
        fi

        if (( SECONDS >= deadline )); then
            stopped_reason="$(migration_stopped_reason)"
            echo "ERROR: migration task did not stop within ${MIGRATION_WAIT_MAX_S} s (MIGRATION_WAIT_MAX_S); last status: ${last_status}; stoppedReason: ${stopped_reason:-unavailable}; task: ${MIGRATION_TASK_ARN}. The task was left running." >&2
            exit 1
        fi

        echo "migration task status: ${last_status}; waiting"
        sleep "$MIGRATION_POLL_SECONDS"
    done
}

run_migrations() {
    local network_configuration
    network_configuration="awsvpcConfiguration={subnets=[${PRIVATE_SUBNET_IDS}],securityGroups=[${MIGRATION_SG_ID}],assignPublicIp=DISABLED}"

    MIGRATION_TASK_ARN="$(aws ecs run-task \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --task-definition "$MIGRATION_TASK_DEF_ARN" \
        --launch-type FARGATE \
        --count 1 \
        --network-configuration "$network_configuration" \
        --query 'tasks[0].taskArn' \
        --output text)"
    require_value "migration task ARN returned by ECS" "$MIGRATION_TASK_ARN"

    check_migration_task
}

# Wait for the migration task to stop, then fail loudly unless it exited 0.
check_migration_task() {
    local exit_code stopped_reason

    wait_for_migration_task

    exit_code="$(aws ecs describe-tasks \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --tasks "$MIGRATION_TASK_ARN" \
        --query 'tasks[0].containers[0].exitCode' \
        --output text)"
    if [[ "$exit_code" != "0" ]]; then
        stopped_reason="$(migration_stopped_reason)"
        echo "ERROR: migration task failed with exit code ${exit_code}; stoppedReason: ${stopped_reason:-unavailable}" >&2
        exit 1
    fi

    echo "PASS: migration task completed successfully"
}

scale_up_service() {
    aws ecs update-service \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --service "$ECS_SERVICE_NAME" \
        --desired-count 1 >/dev/null
    aws ecs wait services-stable \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --services "$ECS_SERVICE_NAME"
    # The load balancer now checks /healthz (is the process up?), which no
    # longer proves the database secret works. /readyz opens a database
    # connection, so ask it directly: up to 10 tries, 15 s apart.
    local attempt
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        if curl --fail --silent --output /dev/null "$API_BASE_URL/readyz"; then
            break
        fi
        if [[ "$attempt" == 10 ]]; then
            echo "FAIL: API /readyz never returned 200" >&2
            return 1
        fi
        sleep 15
    done
    echo "PASS: API service scaled to one task and /readyz answers 200"
}

scale_up_ops_service() {
    aws ecs update-service \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --service "$OPS_SERVICE_NAME" \
        --desired-count "$OPS_DESIRED_COUNT" >/dev/null
    aws ecs wait services-stable \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --services "$OPS_SERVICE_NAME"
    if [[ "$OPS_DESIRED_COUNT" == "1" ]]; then
        if [[ "${PA_DEPLOY_OPS_HEALTH:-}" == "1" ]]; then
            curl --fail --silent --output /dev/null "https://${OPS_DOMAIN}/healthz"
            echo "PASS: ops service scaled to one task and /healthz answers 200"
        else
            echo "NOTE: ops health check skipped; set PA_DEPLOY_OPS_HEALTH=1 from an allowlisted network"
        fi
    else
        echo "PASS: ops service remains scaled to zero"
    fi
}

require_production_build_environment() {
    local missing=()

    [[ -n "${VITE_API_BASE_URL:-}" && "${VITE_API_BASE_URL:-}" != "None" ]] || missing+=("VITE_API_BASE_URL")
    [[ -n "${VITE_OIDC_AUTHORITY:-}" && "${VITE_OIDC_AUTHORITY:-}" != "None" ]] || missing+=("VITE_OIDC_AUTHORITY")
    [[ -n "${VITE_OIDC_CLIENT_ID:-}" && "${VITE_OIDC_CLIENT_ID:-}" != "None" ]] || missing+=("VITE_OIDC_CLIENT_ID")

    if [[ "$WAF_CAPTCHA" == "1" ]]; then
        [[ -n "${VITE_WAF_CAPTCHA_SCRIPT_URL:-}" && "${VITE_WAF_CAPTCHA_SCRIPT_URL:-}" != "None" ]] || missing+=("VITE_WAF_CAPTCHA_SCRIPT_URL")
        [[ -n "${VITE_WAF_CAPTCHA_API_KEY:-}" && "${VITE_WAF_CAPTCHA_API_KEY:-}" != "None" ]] || missing+=("VITE_WAF_CAPTCHA_API_KEY")
    fi

    if (( ${#missing[@]} > 0 )); then
        echo "ERROR: refusing production frontend build; missing: ${missing[*]}" >&2
        exit 1
    fi
}

# Resolve the public CAPTCHA browser values before any AWS state changes. A missing
# permission or API key must fail the deploy before CDK can alter the environment.
resolve_waf_captcha_values() {
    local api_keys_json captcha_values script_url api_key

    if ! api_keys_json="$(aws wafv2 list-api-keys \
        --scope REGIONAL \
        --region "$DEPLOY_REGION" \
        --output json)"; then
        fail "deploy role needs wafv2:ListAPIKeys"
    fi
    if ! captcha_values="$(python3 -c '
import json
import sys

document = json.load(sys.stdin)
domain = sys.argv[1]
url = document.get("ApplicationIntegrationURL")
for summary in document.get("APIKeySummaries", []):
    # A key whose domain list includes ours works for the page; the hand step
    # creates it with one domain, but an operator may add more.
    if domain in (summary.get("TokenDomains") or []) and summary.get("APIKey"):
        if not isinstance(url, str) or not url:
            raise SystemExit(1)
        print("{}\t{}".format(url, summary["APIKey"]))
        raise SystemExit(0)
raise SystemExit(1)
' "$PUBLIC_DOMAIN" <<<"$api_keys_json")"; then
        fail "no WAF API key for ${PUBLIC_DOMAIN}; run: aws wafv2 create-api-key --scope REGIONAL --token-domains ${PUBLIC_DOMAIN} (infra/DEPLOYMENT.md § 2)"
    fi
    IFS=$'\t' read -r script_url api_key <<< "$captcha_values"
    export VITE_WAF_CAPTCHA_SCRIPT_URL="$script_url"
    export VITE_WAF_CAPTCHA_API_KEY="$api_key"
    echo "PASS: resolved WAF CAPTCHA API key for ${PUBLIC_DOMAIN}"
}

# Give the frontend build its CAPTCHA values, or none. The unset matters: Vite
# bundles any VITE_* value in the environment, so a stale value inherited from
# the caller's shell would show a puzzle the firewall is not asking for.
apply_waf_captcha_values() {
    if [[ "$WAF_CAPTCHA" == "1" ]]; then
        resolve_waf_captcha_values
    else
        unset VITE_WAF_CAPTCHA_SCRIPT_URL VITE_WAF_CAPTCHA_API_KEY
    fi
}

# Resolve and validate everything publish_frontend needs. Called from
# common_tail BEFORE the outage-inducing steps (review finding, 026 step 7): a
# publish-config problem discovered after stop→migrate would strand a stale
# SPA on a freshly migrated backend.
resolve_frontend_publish_config() {
    FRONTEND_BUCKET="$(ssm_value "$SSM_FRONTEND_BUCKET_NAME")"
    FONTS_BUCKET="$(ssm_value "$SSM_FONTS_BUCKET_NAME")"
    DISTRIBUTION_ID="$(ssm_value "$SSM_DISTRIBUTION_ID")"
    VITE_OIDC_AUTHORITY="$(ssm_value "$SSM_OIDC_ISSUER")"
    VITE_OIDC_CLIENT_ID="$(ssm_value "$SSM_OIDC_CLIENT_ID")"
    VITE_API_BASE_URL="$API_BASE_URL"

    require_production_build_environment
    require_value "frontend bucket SSM export" "$FRONTEND_BUCKET"
    require_value "fonts bucket SSM export" "$FONTS_BUCKET"
    require_value "CloudFront distribution SSM export" "$DISTRIBUTION_ID"
    export VITE_API_BASE_URL VITE_OIDC_AUTHORITY VITE_OIDC_CLIENT_ID
    # Options scoping is built up to the longlist only. Show it on staging for
    # colleagues to test; keep it hidden (listed as planned) in production
    # until shortlist + assessment land. Drop this once the capability is done.
    # Theory of change (task 054) likewise: on staging only, while the API's
    # POLICY_ATLAS_THEORY_OF_CHANGE (infra/pa_config.json) is on there too.
    if [[ "$ENV_NAME" == "staging" ]]; then
        export VITE_OPTIONS_SCOPING=1
        export VITE_THEORY_OF_CHANGE=1
    fi
}

publish_frontend() {
    local font_file invalidation_id

    aws s3 sync "s3://${FONTS_BUCKET}/" "$REPO_ROOT/frontend/public/fonts/"
    if ! font_file="$(find "$REPO_ROOT/frontend/public/fonts" -type f -print -quit)"; then
        fail "cannot inspect frontend/public/fonts after fonts sync"
    fi
    if [[ -z "$font_file" ]]; then
        fail "fonts sync completed but frontend/public/fonts is empty"
    fi

    (
        cd "$REPO_ROOT/frontend"
        pnpm install --frozen-lockfile
        pnpm build
    )

    # Publish without --delete first: an edge still serving the previous cached
    # index.html can request the previous hashed chunks until the invalidation
    # propagates — deleting them up front turns that window into broken loads.
    # Prune the old assets only after the invalidation completes.
    aws s3 sync "$REPO_ROOT/frontend/dist/" "s3://${FRONTEND_BUCKET}/"
    invalidation_id="$(aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --query 'Invalidation.Id' --output text)"
    aws cloudfront wait invalidation-completed \
        --distribution-id "$DISTRIBUTION_ID" \
        --id "$invalidation_id"
    aws s3 sync "$REPO_ROOT/frontend/dist/" "s3://${FRONTEND_BUCKET}/" --delete
    echo "PASS: frontend published and invalidated"
}

build_ops_pages() {
    (
        cd "$REPO_ROOT/frontend"
        pnpm install --frozen-lockfile
        # The ops client always calls the page's own origin (plan P2), so no
        # API base is set here: the generated paths already carry /api/v1.
        VITE_OIDC_AUTHORITY="$VITE_OIDC_AUTHORITY" \
            VITE_OIDC_CLIENT_ID="$VITE_OIDC_CLIENT_ID" \
            pnpm build:ops
    )
}

check_ops_pages_bundle() {
    [[ -f "$REPO_ROOT/backend/ops-ui/index.html" ]]
}

prepare_ops_deploy() {
    deploy_step "check ops allowlist"
    gate_check \
        "ops allowlist SSM parameter contains one to eight valid IPv4 CIDRs" \
        check_ops_allowlist_parameter
    if [[ "$mode" == "bootstrap" ]]; then
        # The bundle embeds the Cognito issuer and client id, which the first
        # deploy is about to create. The image ships an empty ops-ui directory
        # and the ops service stays at zero; the next update builds the pages.
        echo "NOTE: ops pages are built on the next update deploy (no OIDC exports yet)"
        return 0
    fi
    # This validates the OIDC exports before the build that embeds them. The
    # public frontend later reuses these same resolved values unchanged.
    resolve_frontend_publish_config
    deploy_step "build ops pages"
    gate_check "ops pages build and bundle contains index.html" build_ops_pages
    gate_check "ops pages bundle exists" check_ops_pages_bundle
}

common_tail() {
    CLUSTER_ARN="$(ssm_value "$SSM_CLUSTER_ARN")"
    PRIVATE_SUBNET_IDS="$(ssm_value "$SSM_PRIVATE_SUBNET_IDS")"
    MIGRATION_SG_ID="$(ssm_value "$SSM_MIGRATION_SG_ID")"
    MIGRATION_TASK_DEF_ARN="$(ssm_value "$SSM_MIGRATION_TASK_DEF_ARN")"

    require_value "cluster ARN SSM export" "$CLUSTER_ARN"
    require_value "private subnet IDs SSM export" "$PRIVATE_SUBNET_IDS"
    require_value "migration security-group ID SSM export" "$MIGRATION_SG_ID"
    require_value "migration task-definition ARN SSM export" "$MIGRATION_TASK_DEF_ARN"

    # Re-resolved here so a bootstrap (which skipped the ops build) still has
    # the publish settings; on an update this repeats the earlier reads.
    resolve_frontend_publish_config

    deploy_step "check ops secret"
    gate_check "ops database secret exists" check_ops_secret
    deploy_step "check ops service"
    gate_check "ops ECS service is ACTIVE" check_ops_service
    gate_check "ops target-group ARN SSM export is present" check_ops_target_group_export
    verify_ops_allowlist_applied

    # The same stop → migrate → start order applies to a downgrade: stop both
    # services, run the downgrade, start the API, then start the ops service.
    deploy_step "stop api"
    scale_down_service "$ECS_SERVICE_NAME"
    wait_for_service_to_stop "$ECS_SERVICE_NAME" "API"
    deploy_step "stop ops"
    scale_down_service "$OPS_SERVICE_NAME"
    wait_for_service_to_stop "$OPS_SERVICE_NAME" "ops"
    deploy_step "migrate"
    run_migrations
    gate_check "ops database secret carries db_connection_string" check_ops_db_connection_string
    deploy_step "start api"
    scale_up_service
    deploy_step "start ops"
    scale_up_ops_service
    deploy_step "publish frontend"
    publish_frontend
}

if (( $# != 1 )); then
    usage
    exit 2
fi

case "$1" in
    bootstrap|update|check)
        mode="$1"
        ;;
    *)
        usage
        exit 2
        ;;
esac

if [[ "$mode" == "check" ]]; then
    echo "PASS: deployment configuration '${ENV_NAME}' is complete and internally consistent"
    exit 0
fi

if [[ -n "${AWS_REGION:-}" && "$AWS_REGION" != "$DEPLOY_REGION" ]]; then
    fail "AWS_REGION must be ${DEPLOY_REGION}"
fi
if [[ -n "${AWS_DEFAULT_REGION:-}" && "$AWS_DEFAULT_REGION" != "$DEPLOY_REGION" ]]; then
    fail "AWS_DEFAULT_REGION must be ${DEPLOY_REGION}"
fi
export AWS_REGION="$DEPLOY_REGION"
export AWS_DEFAULT_REGION="$DEPLOY_REGION"

# A side-effect-free harness for the direct build-guard contract test. It
# invokes the exact production guard before CDK/AWS commands, with no parsing
# or extracted copy of its logic in the test itself.
# The two harnesses below may override the CAPTCHA flag so the tests cover both
# cases whatever the committed config says; a real deploy never reads the override.
if [[ "${PA_DEPLOY_GUARD_ONLY:-}" == "1" || "${PA_DEPLOY_WAF_KEYS_ONLY:-}" == "1" ]]; then
    WAF_CAPTCHA="${PA_DEPLOY_GUARD_WAF_CAPTCHA:-$WAF_CAPTCHA}"
fi
if [[ "${PA_DEPLOY_GUARD_ONLY:-}" == "1" ]]; then
    require_production_build_environment
    exit 0
fi

# This harness runs the production lookup with the caller's (usually stubbed) aws,
# or the unset path, and prints what the frontend build would see.
if [[ "${PA_DEPLOY_WAF_KEYS_ONLY:-}" == "1" ]]; then
    apply_waf_captcha_values
    echo "VITE_WAF_CAPTCHA_SCRIPT_URL=${VITE_WAF_CAPTCHA_SCRIPT_URL:-}"
    echo "VITE_WAF_CAPTCHA_API_KEY=${VITE_WAF_CAPTCHA_API_KEY:-}"
    exit 0
fi

# The same kind of harness for the migration waiter (task 057): runs the real
# wait-and-exit-code steps of run_migrations against a task ARN and cluster the
# caller supplies, so scripts/test_deploy_migration_wait.sh can drive them with a
# stubbed `aws`. Starts no task.
if [[ "${PA_DEPLOY_MIGRATION_WAIT_ONLY:-}" == "1" ]]; then
    CLUSTER_ARN="${CLUSTER_ARN:?set CLUSTER_ARN}"
    MIGRATION_TASK_ARN="${MIGRATION_TASK_ARN:?set MIGRATION_TASK_ARN}"
    check_migration_task
    exit 0
fi

if [[ "$METABASE_ALLOWLIST_PARAMETER" != "-" ]]; then
    gate_check \
        "Metabase allowlist SSM parameter contains one to eight valid IPv4 CIDRs" \
        check_metabase_allowlist_parameter
fi

# Contract W7: the CAPTCHA values are resolved before anything touches AWS
# state, so a missing key or permission fails with nothing changed. Both
# bootstrap and update publish the frontend, so both need them.
apply_waf_captcha_values
prepare_ops_deploy

if [[ "$mode" == "bootstrap" ]]; then
    bootstrap
else
    deploy_all_stacks
fi

common_tail
