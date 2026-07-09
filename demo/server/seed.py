"""Seed the pre-run demo project: run one full live analysis headless.

Usage:
    uv run python -m demo.server.seed "What works to reduce childhood obesity in the UK?" \
        --name "Childhood obesity — what works" --depth deep

Auto-answers check-ins with the first option; prints stage events as they land;
registers the project in projects.json so the app lists it.
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from demo.server.bus import EventBus
from demo.server.driver import AnalysisDriver, install_log_bridge

from policy_atlas.logging import configure_logging

_SIDECAR = Path(__file__).parent / "projects.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--name", required=True)
    parser.add_argument("--depth", choices=["quick", "deep"], default="deep")
    parser.add_argument("--sources", choices=["academic_only", "grey_lit_only", "both"],
                        default="both")
    args = parser.parse_args()

    configure_logging()
    install_log_bridge()

    plan = {
        "question": args.question,
        "focus": [],
        "search_depth": args.depth,
        "evidence_sources": args.sources,
        "check_in": "minimal",
        "ready": True,
    }
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
        if event["type"] == "checkin":
            driver.answer_checkin(event["data"]["checkin_id"],
                                  event["data"]["options"][0])
            print(f"[checkin auto-answered] {event['data']['text'][:120]}")
        elif event["type"] in ("stage.started", "stage.completed", "narration",
                               "analysis.completed", "analysis.failed"):
            print(f"[{event['type']}] {json.dumps(event['data'], default=str)[:300]}")

    if driver.failed:
        print(f"FAILED: {driver.failed}")
        sys.exit(1)

    entries = json.loads(_SIDECAR.read_text()) if _SIDECAR.exists() else []
    entries.append({
        "project_id": str(project_id), "name": args.name, "question": args.question,
        "plan": plan, "created_at": datetime.now(UTC).isoformat(),
    })
    _SIDECAR.write_text(json.dumps(entries, indent=1))
    print(f"Seeded project {project_id} ({args.name})")


if __name__ == "__main__":
    main()
