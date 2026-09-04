"""Live multi-round search check (task 029) — drives the REAL production path.

Runs one live plan through the runner (`run_plan`, the same walk the API
dispatches), which is where the round loop now lives: standard and deep repeat
the acquire → screen pair up to their round cap. Afterwards it reads the event
log and coverage rows back and prints, per round: which arms fired, what each
backend returned/kept, documents screened, new confident-relevant, and the
final stop condition.

Usage, from the repo root:

    uv run --project backend python scripts/scratchpad/run_live_deep.py
    uv run --project backend python scripts/scratchpad/run_live_deep.py --depth standard
    uv run --project backend python scripts/scratchpad/run_live_deep.py --intent "..."

Needs OPENALEX_API_KEY, OVERTON_API_KEY, OPENAI_API_KEY in the repo .env.
Writes real rows to whatever DATABASE_URL points at (your dev DB, at alembic
head) and spends real money: a deep run screens up to 3 rounds x 400 docs at
3 model calls each, plus embeddings. It prints an estimate and asks before
running. See README.md in this directory.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "src"))
load_dotenv(REPO / ".env")

import os  # noqa: E402

from sqlalchemy import select  # noqa: E402

from policy_atlas.core import events, tracing  # noqa: E402
from policy_atlas.core.db import get_engine  # noqa: E402
from policy_atlas.core.logging import configure_logging  # noqa: E402
from policy_atlas.core.schema import search_coverage_record  # noqa: E402
from policy_atlas.evidence_search.assess.screen_prompt import SCREEN_REPS  # noqa: E402
from policy_atlas.evidence_search.sourcing.search_loop import (  # noqa: E402
    DEPTH_CONSTANTS,
    confident_relevant_count,
    new_confident_relevant_for_run,
)
from policy_atlas.runtime.agent import (  # noqa: E402
    _write_plan_row,
    live_planner_and_backends,
)
from policy_atlas.runtime.runner import NullIO, run_plan  # noqa: E402
from policy_atlas.runtime.task_plan import TaskPlan  # noqa: E402

DEFAULT_INTENT = (
    "interventions to reduce consumption of high fat, sugar, and salt (HFSS) foods"
)

ARM_LABELS = {
    ("search", "generated"): "fan-out / reformulate",
    ("search", "variant_sr"): "fan-out (SR variant)",
    ("search", "variant_rct"): "fan-out (RCT variant)",
    ("search", "verbatim"): "verbatim / diversity",
    ("search", "paraphrase"): "Overton paraphrase",
    ("search", "fallback_verbatim"): "fallback verbatim",
    ("fetch_citations", "snowball_forward"): "snowball forward",
    ("fetch_references", "snowball_backward"): "snowball backward",
    ("lookup_dois", "suggestion_doi"): "suggest (DOI grounding)",
    ("lookup_title", "suggestion_title"): "suggest (title grounding)",
}


def _plan(intent: str, depth: str) -> TaskPlan:
    return TaskPlan.model_validate(
        {
            "title": f"live-check-029 {depth}",
            "question": intent,
            "scoping_notes": ["Live multi-round search check (task 029)"],
            "screening_criteria": ["Include empirical or policy-analysis sources"],
            "backend_scope": "both",
            "scope_constraints": {},
            "search_effort": depth,
            # landscape = the shallowest analysis rung; the search rounds are
            # the subject here, not the deep analysis components.
            "analysis_depth": "landscape",
            "components": [],
            "component_rationale": {},
            "grouping_facets": None,
            "steering_mode": "unattended",
            "steer_point_defaults": [],
            "assumptions": ["Live check drives search rounds only"],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", default="deep", choices=["rapid", "standard", "deep"])
    parser.add_argument("--intent", default=DEFAULT_INTENT)
    parser.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    args = parser.parse_args()

    configure_logging()
    missing = [
        key
        for key in ("OPENALEX_API_KEY", "OVERTON_API_KEY", "OPENAI_API_KEY")
        if not os.environ.get(key)
    ]
    if missing:
        print(f"MISSING keys in .env: {missing}")
        return 2

    constants = DEPTH_CONSTANTS[args.depth]
    cap, rounds = constants["record_cap_per_backend"], constants["round_cap"]
    worst_docs = cap * 2 * rounds
    print(f"depth={args.depth}  rounds<={rounds}  cap={cap}/backend/round")
    print(
        f"worst case ~{worst_docs} docs screened x {SCREEN_REPS} reps "
        f"= ~{worst_docs * SCREEN_REPS} screening calls, plus embeddings"
    )
    print(f"database: {(os.environ.get('DATABASE_URL') or 'UNSET').rsplit('/', 1)[-1]}")
    if not args.yes and input("continue? [y/N] ").strip().lower() != "y":
        return 1

    engine = get_engine()
    langfuse = tracing.get_langfuse()
    _planner, backends = live_planner_and_backends(langfuse)
    plan = _plan(args.intent, args.depth)
    task_id, scope_id, plan_id = _write_plan_row(engine, plan=plan)
    print(f"\ntask_id = {task_id}\nscope_id   = {scope_id}\nrunning …\n")

    started = time.monotonic()
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=backends,
        io=NullIO(),
    )
    elapsed = time.monotonic() - started

    # ---- read back per-round evidence -------------------------------------
    with engine.connect() as conn:
        coverage = list(
            conn.execute(
                select(search_coverage_record)
                .where(search_coverage_record.c.task_id == task_id)
                .order_by(search_coverage_record.c.created_at)
            )
        )
        confident = confident_relevant_count(
            conn, task_id=task_id, scope_id=scope_id
        )
        screen_runs = [
            step.run_id
            for step in outcome.steps
            if step.component == "screen_abstract" and step.status == "succeeded"
        ]
        per_round_confident = [
            new_confident_relevant_for_run(
                conn, task_id=task_id, scope_id=scope_id, run_id=run_id
            )
            for run_id in screen_runs
            if run_id is not None
        ]
        arms: dict[int, dict[str, dict[str, int]]] = defaultdict(dict)
        for round_index, row in enumerate(coverage, start=1):
            entries = events.read_for_run(conn, task_id, row.acquired_by_run_id)
            for entry in entries:
                if entry["event_type"] != "search.executed":
                    continue
                payload: dict[str, Any] = entry["payload"]
                label = ARM_LABELS.get(
                    (payload["verb"], payload["query_origin"]),
                    f'{payload["verb"]}/{payload["query_origin"]}',
                )
                bucket = arms[round_index].setdefault(
                    label, {"calls": 0, "records": 0}
                )
                bucket["calls"] += 1
                bucket["records"] += payload.get("result_count") or 0

    print(f"run status = {outcome.status}   wall clock = {elapsed / 60:.1f} min")
    print(
        "search steps:",
        [s.component for s in outcome.steps if s.component in ("acquire", "screen_abstract")],
    )
    print(f"\nROUNDS ({len(coverage)}):")
    for round_index, row in enumerate(coverage, start=1):
        print(f"  round {round_index}: stop={row.stop_condition}  adequacy={row.adequacy_verdict}")
        for label, bucket in sorted(arms[round_index].items()):
            print(f"    {label:28s} {bucket['calls']:3d} calls  {bucket['records']:5d} records")
        if round_index - 1 < len(per_round_confident):
            print(f"    new confident-relevant this round: {per_round_confident[round_index - 1]}")

    print(f"\nconfident-relevant total: {confident}")
    print("checks:")
    expected_rounds = rounds if args.depth != "rapid" else 1
    print(f"  rounds ran           : {len(coverage)} (cap {expected_rounds})")
    arm_verbs_seen = {
        label for by_label in arms.values() for label in by_label
    }
    for needed in ("snowball forward", "suggest (DOI grounding)"):
        note = "yes" if needed in arm_verbs_seen else "NO (needs confident OpenAlex seeds / groundable suggestions)"
        if args.depth == "deep":
            print(f"  {needed:21s}: {note}")
    print(f"\nLangfuse traces (if configured): task {task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
