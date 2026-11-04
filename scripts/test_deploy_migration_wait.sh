#!/usr/bin/env bash
# Check deploy.sh's migration waiter (task 057, G10) against a stubbed `aws`.
#
# deploy.sh polls the migration task with `aws ecs describe-tasks` every 15 s until
# ECS reports it STOPPED, up to MIGRATION_WAIT_MAX_S seconds, then fails unless the
# container exited 0. This script runs the real waiter through deploy.sh's
# PA_DEPLOY_MIGRATION_WAIT_ONLY harness with `aws` and `sleep` replaced by shell
# functions, so it needs no AWS account, network or waiting.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deploy_script="$repo_root/scripts/deploy.sh"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/policy-atlas-migration-wait.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

# The stub answers by the --query it is asked: the next status from STUB_STATUSES
# (space-separated; the last one repeats; FAIL makes the call itself fail), the
# exit code, or the stopped reason. Every call is logged to STUB_LOG.
aws() {
    local query="" arg
    for arg in "$@"; do
        case "$arg" in
            tasks\[0\].*) query="$arg" ;;
        esac
    done
    echo "aws $*" >>"$STUB_LOG"
    case "$query" in
        "tasks[0].lastStatus")
            local count statuses index
            count="$(wc -l <"$STUB_LOG.status" 2>/dev/null || echo 0)"
            echo x >>"$STUB_LOG.status"
            read -r -a statuses <<<"$STUB_STATUSES"
            index=$(( count < ${#statuses[@]} ? count : ${#statuses[@]} - 1 ))
            if [[ "${statuses[$index]}" == "FAIL" ]]; then
                echo "An error occurred (ThrottlingException)" >&2
                return 255
            fi
            echo "${statuses[$index]}"
            ;;
        "tasks[0].containers[0].exitCode") echo "$STUB_EXIT_CODE" ;;
        "tasks[0].stoppedReason") echo "$STUB_REASON" ;;
        *) echo "unexpected aws call: $*" >&2; return 1 ;;
    esac
}
sleep() { echo "sleep $*" >>"$STUB_LOG"; }
export -f aws sleep

# run_case NAME STATUSES EXIT_CODE REASON MAX_S -> sets case_status, case_out, case_err
run_case() {
    export STUB_LOG="$work_dir/$1.log"
    export STUB_STATUSES="$2" STUB_EXIT_CODE="$3" STUB_REASON="$4"
    : >"$STUB_LOG"
    set +e
    env -u AWS_REGION -u AWS_DEFAULT_REGION \
        PA_DEPLOY_MIGRATION_WAIT_ONLY=1 MIGRATION_WAIT_MAX_S="$5" \
        CLUSTER_ARN=stub-cluster MIGRATION_TASK_ARN=stub-task \
        bash "$deploy_script" update >"$work_dir/$1.out" 2>"$work_dir/$1.err"
    case_status=$?
    set -e
    case_out="$(cat "$work_dir/$1.out")"
    case_err="$(cat "$work_dir/$1.err")"
}

failures=0
check() {
    local description="$1" condition="$2"
    if eval "$condition"; then
        echo "ok: $description"
    else
        echo "FAIL: $description" >&2
        echo "  stdout: $case_out" >&2
        echo "  stderr: $case_err" >&2
        failures=$((failures + 1))
    fi
}
polls() { grep -c "tasks\[0\].lastStatus" "$STUB_LOG" || true; }
sleeps() { grep -c "^sleep 15$" "$STUB_LOG" || true; }

run_case running_then_stopped "RUNNING RUNNING STOPPED" 0 "Essential container in task exited" 5400
check "RUNNING twice then STOPPED with exit 0 passes" '[[ $case_status -eq 0 ]]'
check "it polled three times and slept twice for 15 s" '[[ $(polls) -eq 3 && $(sleeps) -eq 2 ]]'
check "it reports success" '[[ "$case_out" == *"PASS: migration task completed successfully"* ]]'

run_case stopped_exit_1 "STOPPED" 1 "Essential container in task exited" 5400
check "STOPPED with exit 1 fails" '[[ $case_status -ne 0 ]]'
check "the failure names the exit code and the stopped reason" \
    '[[ "$case_err" == *"exit code 1"* && "$case_err" == *"Essential container in task exited"* ]]'

run_case never_stops "RUNNING" 0 "" 0
check "a task still running at the limit fails" '[[ $case_status -ne 0 ]]'
check "the timeout names the limit, the variable and the last status" \
    '[[ "$case_err" == *"within 0 s (MIGRATION_WAIT_MAX_S)"* && "$case_err" == *"last status: RUNNING"* ]]'

run_case describe_blip "FAIL STOPPED" 0 "Essential container in task exited" 5400
check "a failed describe-tasks call is retried, not fatal" '[[ $case_status -eq 0 && $(polls) -eq 2 ]]'

run_case bad_limit "STOPPED" 0 "" "ninety"
check "a limit that is not a number is refused" \
    '[[ $case_status -ne 0 && "$case_err" == *"MIGRATION_WAIT_MAX_S must be a whole number"* ]]'

if (( failures > 0 )); then
    echo "deploy-migration-wait-test: ${failures} check(s) failed" >&2
    exit 1
fi
echo "deploy-migration-wait-test: PASS"
