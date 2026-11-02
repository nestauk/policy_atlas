#!/usr/bin/env python3
"""Start the four task 056 fixed questions as fresh tasks on the local app.

What this does
--------------
Task 056 measures cost on four fixed questions (contract O5): three Evidence
search questions at standard analysis depth and one Options scoping question.
Each measurement must start from a brand-new task, so this script creates a
fresh task for every question each time it runs, exactly as the web app does:

1. ``POST /api/v1/tasks`` creates the task.
2. ``POST /api/v1/tasks/{id}/task-agent-turns`` sends the question to the Task
   Agent (the planning chat). If the Task Agent asks a clarifying question
   instead of producing a plan, the script answers "go with your recommended
   choices", up to ``--max-turns`` messages in all.
3. ``GET /api/v1/tasks/{id}/plan`` checks the plan is approved, then
   ``PATCH /api/v1/tasks/{id}/plan`` pins the depth (Evidence search
   ``analysis_depth = standard``; Options scoping ``depth = standard``) and the
   steering mode (default ``unattended``, so the run never stops to wait for a
   person at a check-in; on Options scoping that also means the longlist walk
   opens by itself once the baseline is written).
4. ``POST /api/v1/tasks/{id}/runs`` starts the run.

It prints one line per question: the question, the task id, the run id and
the Langfuse session id. In Policy Atlas the Langfuse session id IS the task id
(every trace of a task, planning and run, is filed under it), so it can be
passed straight to ``scripts/cost_per_run.py`` once the run has finished.

Running it spends real money (live model calls). Use ``--dry-run`` to print
the requests without sending anything.

Before running
--------------
- ``make dev`` (or ``make -C backend dev``) is running, so the API answers on
  http://localhost:8000. The model route (Bedrock or OpenAI direct) is whatever
  that server was started with.
- A sign-in token: by default the script mints one exactly as ``make dev``
  does (``python -m policy_atlas.api.dev_issuer mint`` as ``dev-user`` with
  the keys in ``backend/.dev-issuer``). Pass ``--token`` to use your own.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://localhost:8000"
#: One HTTP request can include a live Task Agent model call, so be patient.
REQUEST_TIMEOUT = 600
FOLLOW_UP = (
    "Please go ahead with your recommended choices for everything you asked about. "
    "Where a choice has no recommendation, such as depth, use standard depth (the fuller "
    "path). Then make the plan ready to start."
)


@dataclass(frozen=True)
class FixedQuestion:
    """One of the contract's fixed questions (task 056, O5)."""

    key: str
    capability: str  # "evidence_search" or "options_scoping"
    question: str


QUESTIONS: tuple[FixedQuestion, ...] = (
    FixedQuestion(
        "neet",
        "evidence_search",
        "What interventions reduce the number of young people aged 16 to 24 who are not "
        "in education, employment or training (NEET) in England?",
    ),
    FixedQuestion(
        "zonal",
        "evidence_search",
        "What is the effect of zonal electricity pricing on energy bills and energy security?",
    ),
    FixedQuestion("obesity", "evidence_search", "What works to reduce childhood obesity?"),
    FixedQuestion(
        "scoping",
        "options_scoping",
        "How do we reduce the potential economic disruption to the labour market caused "
        "by the rise in AI?",
    ),
)


def task_name(question: str, limit: int = 80) -> str:
    """Short task name from the question, as the web app derives it."""
    cleaned = " ".join(question.split()).rstrip("?").strip()
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[:limit]
    space = clipped.rfind(" ")
    return (clipped[:space] if space > limit / 2 else clipped).rstrip() + "…"


def create_task_body(q: FixedQuestion) -> dict[str, Any]:
    """Body for ``POST /api/v1/tasks``."""
    return {
        "name": f"[056 fixed] {task_name(q.question)}"[:200],
        "question": q.question,
        "capability": q.capability,
        "project_ids": [],
        "from_task_ids": [],
    }


def plan_patch_body(q: FixedQuestion, steering: str) -> dict[str, Any]:
    """Body for ``PATCH /api/v1/tasks/{id}/plan``: standard depth and steering.

    Args:
        q: The question.
        steering: A steering mode, or ``keep`` to leave the Task Agent's choice.
    """
    if q.capability == "evidence_search":
        body: dict[str, Any] = {"analysis_depth": "standard"}
        if steering != "keep":
            body["steering_mode"] = steering
        return body
    scoping: dict[str, Any] = {"depth": "standard"}
    if steering != "keep":
        scoping["steering_mode"] = steering
        # An unattended scoping plan must say what to do at the baseline gate;
        # an attended one must not (ScopingPlan validation).
        scoping["steer_point_defaults"] = (
            [{"steer_point": "baseline_confirm", "action": "proceed_flag"}]
            if steering == "unattended"
            else []
        )
    return {"scoping": scoping}


class Api:
    """Tiny JSON client for the local Policy Atlas API.

    Args:
        base_url: API address, e.g. ``http://localhost:8000``.
        token: Bearer token (``None`` only in a dry run).
        dry_run: Print each request instead of sending it.
    """

    def __init__(self, base_url: str, token: str | None, dry_run: bool):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.dry_run = dry_run

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        """Send one request and return the decoded JSON (``None`` in a dry run).

        Raises:
            RuntimeError: On an HTTP error, with the status and the API's detail.
        """
        url = f"{self.base_url}{path}"
        if self.dry_run:
            shown = "" if body is None else " " + json.dumps(body, ensure_ascii=False)
            print(f"  {method} {url}{shown}")
            return None
        data = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from None
        return json.loads(raw) if raw else None


def mint_dev_token() -> str:
    """Mint a 4-hour local sign-in token the way ``make dev`` does.

    Raises:
        SystemExit: When minting fails (for example ``backend/.dev-issuer``
            does not exist yet: run ``make dev`` once).
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "policy_atlas.api.dev_issuer",
            "mint",
            "--dir",
            ".dev-issuer",
            "--sub",
            "dev-user",
            "--client-id",
            "policy-atlas-dev",
            "--ttl",
            "14400",
        ],
        cwd=REPO / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        raise SystemExit(f"could not mint a dev token: {result.stderr.strip()[-500:]}")
    return lines[-1]


def start_question(api: Api, q: FixedQuestion, *, steering: str, max_turns: int) -> dict[str, Any]:
    """Create a fresh task for one question, get its plan approved, start the run.

    Returns:
        ``{"key", "question", "task_id", "run_id", "conversation_id",
        "session_id", "status"}``; ``status`` says how far it got.
    """
    placeholder = f"<{q.key}-task-id>"
    task = api.call("POST", "/api/v1/tasks", create_task_body(q))
    task_id = task["task_id"] if task else placeholder
    out: dict[str, Any] = {
        "key": q.key,
        "question": q.question,
        "task_id": task_id,
        "session_id": task_id,
        "conversation_id": None,
        "run_id": None,
        "status": "dry run" if api.dry_run else "started",
    }
    base = f"/api/v1/tasks/{task_id}"
    for turn in range(max_turns):
        message = q.question if turn == 0 else FOLLOW_UP
        reply = api.call(
            "POST",
            f"{base}/task-agent-turns",
            {
                "message": message,
                "client_turn_id": str(uuid.uuid4()) if not api.dry_run else "<new uuid>",
            },
        )
        if reply:
            out["conversation_id"] = reply.get("conversation_id")
        plan = api.call("GET", f"{base}/plan")
        if api.dry_run or (plan and plan.get("status") == "approved"):
            break
    else:
        out["status"] = (
            f"plan not approved after {max_turns} Task Agent turns; finish it in the app"
        )
        return out
    api.call("PATCH", f"{base}/plan", plan_patch_body(q, steering))
    run = api.call("POST", f"{base}/runs", {})
    if run:
        out["run_id"] = run.get("capability_run_id")
    return out


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Create the four task 056 fixed questions as fresh tasks on the local "
            "Policy Atlas API and start each run at standard depth. Spends real "
            "money unless --dry-run is given."
        )
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API address (default {DEFAULT_BASE_URL}, what make dev serves)",
    )
    parser.add_argument(
        "--token", help="sign-in token; default: mint a dev-user token like make dev does"
    )
    parser.add_argument(
        "--steering",
        default="unattended",
        choices=("unattended", "minimal", "moderate", "frequent", "keep"),
        help=(
            "steering mode to pin (default unattended: no check-in waits for a person; "
            "keep = leave the Task Agent's choice)"
        ),
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=3,
        help="Task Agent messages per task before giving up (default 3)",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=[q.key for q in QUESTIONS],
        help="start only this question (repeatable); default: all four",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the requests without sending them"
    )
    args = parser.parse_args(argv)
    chosen = [q for q in QUESTIONS if not args.only or q.key in args.only]

    token = args.token
    if token is None and not args.dry_run:
        token = mint_dev_token()
    api = Api(args.base_url, token, args.dry_run)
    results = []
    failed = False
    for q in chosen:
        if args.dry_run:
            print(f"[{q.key}] {q.capability}")
        try:
            results.append(start_question(api, q, steering=args.steering, max_turns=args.max_turns))
        except RuntimeError as exc:
            failed = True
            print(f"[{q.key}] FAILED: {exc}", file=sys.stderr)
    print()
    for r in results:
        print(
            f"{r['key']:8} task {r['task_id']}  run {r['run_id']}  "
            f"conversation {r['conversation_id']}  "
            f"Langfuse session {r['session_id']}  ({r['status']})\n"
            f"         {r['question']}"
        )
    print(
        "\nThe Langfuse session id is the task id. When a run has finished:\n"
        "  set -a; source backend/.env; set +a\n"
        "  python3 scripts/cost_per_run.py " + " ".join(r["session_id"][:8] for r in results)
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
