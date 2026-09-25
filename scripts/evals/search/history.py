"""Print the headline numbers of every eval run as markdown table rows.

Langfuse holds the detail of each run. This script gives the summary that
Langfuse does not: one row per dataset run, oldest first, with the date,
commit, settings and mean recall, in the column order that
``results/history.md`` uses. It writes nothing.

``history.md`` is curated by hand. It holds only the runs worth keeping (not
smoke tests or partial runs) with a note on each. To add a run: run this
script, copy the row you want, paste it into ``history.md`` and fill in the
note. Pass ``--since YYYY-MM-DD`` to print only recent runs.

The ``variable cost`` column is the run's variable cost, summed over its
reviews. ``api`` means the computed price of the search-service calls
(baseline runs); ``llm`` means the language-model spend Langfuse attributes
to the run's traces (pipeline runs). Neither includes flat subscriptions,
compute or Langfuse itself.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/history.py [--since 2026-09-22]

Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from typing import Any

from ground_truth import iso_date
from ground_truth_dataset import DEFAULT_DATASET
from langfuse.api.core import ApiError

from policy_atlas.core import tracing

HEADER = (
    "| date | commit | experiment | depth | backend | record cap | reviews "
    "| search recall | screen recall | failed calls | variable cost | run | notes |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)


def fetch_runs(
    client: Any, dataset_name: str, since: str | None = None
) -> list[dict[str, Any]]:
    """One row per dataset run, oldest first, with each score averaged over its items.

    ``since`` (YYYY-MM-DD) skips older runs before their items are fetched, so a
    short listing does not pay for every historical run's score and trace lookups.
    """
    dataset = client.api.datasets.get(dataset_name)
    rows = []
    for run in sorted(
        client.api.datasets.get_runs(dataset_name, limit=100).data,
        key=lambda r: r.created_at,
    ):
        if since and run.created_at.strftime("%Y-%m-%d") < since:
            continue
        items = client.api.dataset_run_items.list(
            dataset_id=dataset.id, run_name=run.name, limit=100
        ).data
        values: dict[str, list[float]] = defaultdict(list)
        for item in items:
            # Scores hang off each item's trace. Filtering scores by dataset run
            # id returns nothing on our Langfuse version, so go via the trace.
            for score in client.api.scores.get_many(
                trace_id=item.trace_id, limit=100
            ).data:
                if score.value is not None:
                    values[score.name].append(float(score.value))
        mean = {name: statistics.mean(v) for name, v in values.items()}
        if values.get("api_cost_usd"):
            cost: float | None = sum(values["api_cost_usd"])
            cost_kind: str | None = "api"
        else:
            llm_costs = []
            for item in items:
                try:
                    trace = client.api.trace.get(item.trace_id)
                except ApiError:
                    # A trace pruned by retention must not abort the whole listing.
                    continue
                total_cost = getattr(trace, "total_cost", None)
                if total_cost is not None:
                    llm_costs.append(total_cost)
            cost = sum(llm_costs) if llm_costs else None
            cost_kind = "llm" if llm_costs else None
        meta = run.metadata or {}
        rows.append(
            {
                "date": run.created_at.strftime("%Y-%m-%d"),
                "run": run.name,
                "experiment": meta.get("experiment", "").removeprefix("retrieval-"),
                "commit": meta.get("git_commit", "")[:7],
                "depth": meta.get("depth", ""),
                "backend": meta.get("generation_backend", ""),
                "cap": meta.get("record_cap_per_backend", ""),
                "n_reviews": len(items),
                "search_recall": mean.get("search_recall"),
                "screen_recall": mean.get("screen_recall"),
                "failed_calls": int(sum(values.get("n_failed_calls", []))),
                "cost": cost,
                "cost_kind": cost_kind,
            }
        )
    return rows


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def usd(value: float) -> str:
    """Dollars to two decimals, or four when the amount would otherwise show as $0.00.

    OpenAlex bills fractions of a cent per page, so $0.0004 must not print as $0.00.
    Shared with ``baseline_recall.py`` so both tables format money the same way.
    """
    return f"${value:.2f}" if value == 0 or value >= 0.01 else f"${value:.4f}"


def _cost(r: dict[str, Any]) -> str:
    cost = r.get("cost")
    if cost is None:
        return "n/a"
    return f"{usd(cost)} {r['cost_kind']}"


def render_row(r: dict[str, Any]) -> str:
    """One markdown table row in the ``history.md`` column order, notes left empty."""
    return (
        f"| {r['date']} | {r['commit']} | {r['experiment']} | {r['depth']} | {r['backend']} "
        f"| {r['cap']} | {r['n_reviews']} | {_pct(r['search_recall'])} | {_pct(r['screen_recall'])} "
        f"| {r['failed_calls']} | {_cost(r)} | {r['run']} |  |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument(
        "--since", type=iso_date, help="Only runs on or after this date."
    )
    args = parser.parse_args()

    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "Langfuse is not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST)."
        )
    rows = fetch_runs(client, args.dataset, since=args.since)
    print(HEADER)
    for row in rows:
        print(render_row(row))


if __name__ == "__main__":
    main()
