#!/usr/bin/env bash
# Deploy the staging v3 stacks and perform the imperative post-CDK steps.
# This script deliberately never calls sts get-caller-identity: account IDs are
# sensitive operational metadata and must not be printed by deploy tooling.

set -euo pipefail

readonly DEPLOY_REGION="eu-west-2"
readonly CERTIFICATE_REGION="us-east-1"
readonly ENV_NAME="staging"
readonly ECS_SERVICE_NAME="policy-atlas-v3-api-service"
readonly SERVICE_STOP_TIMEOUT_SECONDS=600
readonly SERVICE_STOP_POLL_SECONDS=5

readonly APP_SECRET_NAME="policy_atlas_v3/app"
readonly API_BASE_URL="https://api.v3.policyatlas.uk"

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

readonly REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    echo "Usage: $0 {bootstrap|update}" >&2
}

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

gate_check() {
    local description="$1"
    shift

    if "$@" >/dev/null 2>&1; then
        echo "PASS: ${description}"
    else
        fail "${description}"
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
    nameservers="$(dig NS v3.policyatlas.uk +short)"
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
    gate_check "v3.policyatlas.uk delegates to Amazon Route 53 nameservers" check_amazon_nameservers
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
    PATH="$REPO_ROOT/infra/.venv/bin:$PATH" npx cdk "$@" --require-approval never
}

deploy_all_stacks() {
    (
        cd "$REPO_ROOT/infra"
        # app.py requires env_name; stage=all is explicit for reproducible deploys.
        run_cdk deploy -c "env_name=${ENV_NAME}" -c stage=all --all
    )
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
    aws ecs update-service \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --service "$ECS_SERVICE_NAME" \
        --desired-count 0 >/dev/null
}

wait_for_service_to_stop() {
    local deadline running_count running_tasks
    deadline=$((SECONDS + SERVICE_STOP_TIMEOUT_SECONDS))

    while true; do
        running_count="$(aws ecs describe-services \
            --region "$DEPLOY_REGION" \
            --cluster "$CLUSTER_ARN" \
            --services "$ECS_SERVICE_NAME" \
            --query 'services[0].runningCount' \
            --output text)"
        running_tasks="$(aws ecs list-tasks \
            --region "$DEPLOY_REGION" \
            --cluster "$CLUSTER_ARN" \
            --service-name "$ECS_SERVICE_NAME" \
            --desired-status RUNNING \
            --query 'length(taskArns)' \
            --output text)"

        if [[ "$running_count" == "0" && "$running_tasks" == "0" ]]; then
            echo "PASS: API service has no running tasks"
            return
        fi

        if (( SECONDS >= deadline )); then
            fail "timed out waiting for the API service to stop"
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

run_migrations() {
    local network_configuration exit_code stopped_reason
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

    if ! aws ecs wait tasks-stopped \
        --region "$DEPLOY_REGION" \
        --cluster "$CLUSTER_ARN" \
        --tasks "$MIGRATION_TASK_ARN"; then
        stopped_reason="$(migration_stopped_reason)"
        echo "ERROR: migration task did not reach stopped state; stoppedReason: ${stopped_reason:-unavailable}" >&2
        exit 1
    fi

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
    echo "PASS: API service scaled to one task"
}

require_production_build_environment() {
    local missing=()

    [[ -n "${VITE_API_BASE_URL:-}" && "${VITE_API_BASE_URL:-}" != "None" ]] || missing+=("VITE_API_BASE_URL")
    [[ -n "${VITE_OIDC_AUTHORITY:-}" && "${VITE_OIDC_AUTHORITY:-}" != "None" ]] || missing+=("VITE_OIDC_AUTHORITY")
    [[ -n "${VITE_OIDC_CLIENT_ID:-}" && "${VITE_OIDC_CLIENT_ID:-}" != "None" ]] || missing+=("VITE_OIDC_CLIENT_ID")

    if (( ${#missing[@]} > 0 )); then
        echo "ERROR: refusing production frontend build; missing: ${missing[*]}" >&2
        exit 1
    fi
}

publish_frontend() {
    local font_file
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

    aws s3 sync "$REPO_ROOT/frontend/dist/" "s3://${FRONTEND_BUCKET}/" --delete
    aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" >/dev/null
    echo "PASS: frontend published and invalidated"
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

    scale_down_service
    wait_for_service_to_stop
    run_migrations
    scale_up_service
    publish_frontend
}

if (( $# != 1 )); then
    usage
    exit 2
fi

case "$1" in
    bootstrap|update)
        mode="$1"
        ;;
    *)
        usage
        exit 2
        ;;
esac

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
if [[ "${PA_DEPLOY_GUARD_ONLY:-}" == "1" ]]; then
    require_production_build_environment
    exit 0
fi

if [[ "$mode" == "bootstrap" ]]; then
    bootstrap
else
    deploy_all_stacks
fi

common_tail
