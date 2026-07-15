"""Seed the pre-run demo project: run one full live analysis headless.

Usage:
    uv run python -m demo.server.seed "What works to reduce childhood obesity in the UK?" \
        --name "Childhood obesity — what works" --band deeper

Builds a REAL OrchestrationPlan (steering_mode=unattended, so the run never
pauses), walks it through the real runner via the demo driver, prints stage
events as they land, and registers the project in projects.json.
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from demo.server import orchestrator
from demo.server.bus import EventBus
from demo.server.driver import AnalysisDriver, install_log_bridge

from policy_atlas.core.logging import configure_logging
from policy_atlas.runtime.orchestration_plan import NAMED_PAIRINGS, OrchestrationPlan

_SIDECAR = Path(__file__).parent / "projects.json"

_COMPONENTS_BY_DEPTH = {
    "landscape": ["characterise"],
    "standard": ["screen_stage2", "characterise", "select", "extract", "group"],
    "deep": ["screen_stage2", "characterise", "select", "extract", "group"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--name", required=True)
    parser.add_argument("--band", choices=sorted(NAMED_PAIRINGS), default="deeper",
                        help="lighter/standard/deeper — the plan's named "
                        "search-effort × analysis-depth pairing")
    parser.add_argument("--sources", choices=["academic_only", "grey_lit_only", "both"],
                        default="both")
    args = parser.parse_args()

    configure_logging()
    install_log_bridge()

    search_effort, analysis_depth = NAMED_PAIRINGS[args.band]
    plan = OrchestrationPlan.model_validate({
        "title": args.name,
        "question": args.question,
        "backend_scope": args.sources,
        "search_effort": search_effort,
        "analysis_depth": analysis_depth,
        "components": _COMPONENTS_BY_DEPTH[analysis_depth],
        "steering_mode": "unattended",
    })
    project_id = uuid.uuid4()
    bus = EventBus()
    driver = AnalysisDriver(project_id, plan, bus, create_project_row=True)

    _, q = bus.subscribe()
    driver.start()
    while not driver.done or not q.empty():
        try:
            event = q.get(timeout=2)
        except Exception:  # noqa: BLE001 — queue.Empty
            continue
        if event["type"] in ("stage.started", "stage.completed", "stage.failed",
                             "narration", "analysis.completed", "analysis.failed",
                             "analysis.aborted"):
            print(f"[{event['type']}] {json.dumps(event['data'], default=str)[:300]}")

    if driver.failed:
        print(f"FAILED: {driver.failed}")
        sys.exit(1)

    entries = json.loads(_SIDECAR.read_text()) if _SIDECAR.exists() else []
    entries.append({
        "project_id": str(project_id), "name": args.name, "question": args.question,
        "plan": orchestrator.plan_payload(None, plan),
        "approved": plan.model_dump(mode="json"),
        "created_at": datetime.now(UTC).isoformat(),
    })
    _SIDECAR.write_text(json.dumps(entries, indent=1))
    print(f"Seeded project {project_id} ({args.name})")


if __name__ == "__main__":
    main()
