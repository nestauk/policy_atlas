"""Measure what production does: search (and screening) recall at the real
depth constants, one Langfuse dataset run per depth.

The sweep (``experiments/sweep_record_cap.py``) asks a research question by pushing the
caps far above production. This script asks the operational question: with
the pipeline exactly as deployed, how much of each review's reference list
does a ``rapid``, ``standard`` or ``deep`` search find? Run it by hand,
locally, so the answers build up into a history over time. (A GitHub Actions
version is parked in ``.github/workflows-disabled/`` until the open questions
about cost and gating are settled.) It records numbers. It does not pass or
fail on them.

How a depth is run (see ``engine.run_one_query``): one search pass, then one
screening pass, at every depth (task 051, ADR 0038). The depths differ only in
the two caps the pass cuts at (``papers_cap`` / ``policy_cap``: rapid 100 / 50,
standard 200 / 100, deep 400 / 200). Search recall and screen recall are both
scored at every depth.

Cost: about 37 OpenAlex and 18 Overton provider calls per review plus one
generation LLM call, then about 1.3 screening LLM calls per kept document
(roughly 150 / 300 / 600 documents per review at the three depths).

Scores on each dataset item (one review): the sweep's ``SCORE_KEYS``
(search_recall, n_found, n_api_calls, n_failed_calls, ..., screen_recall,
n_screened_in) plus ``rounds_run``. There are no run-level scores of our own.
Langfuse's dataset-runs table shows the mean of each per-review score across
the reviews, and that is the run summary. Check ``n_failed_calls`` before
reading recall. Any value above 0 means a provider call failed after retries,
so that review's recall is an undercount caused by the provider, not the code.

Usage (same environment as the sweep; the dataset must already be uploaded
with ``ground_truth/upload.py``):

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/checks/production_recall.py \\
        [--depths rapid standard deep] [--run-label LABEL] [--reviews TEXT ...]

``--reviews`` restricts the run to the dataset items whose id, review id or
review title contains one of the given texts (case-insensitive). Use it to
try an expensive depth on a single review. The run still attaches to the
dataset. It simply has fewer items, so its averages cover only those reviews.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from evals_search_utils import (
    DEFAULT_DATASET,
    git_commit,
    ground_truth_from_item,
    select_items,
)

import argparse
import os
from datetime import date
from typing import Any

from langfuse import Evaluation, propagate_attributes
from engine import run_one_query
from sweep_record_cap import (
    _prompt_identity,
    _run_frames,
    _summary,
    score_summary,
)

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.evidence_search.sourcing.search_loop import DEPTH_CONSTANTS

EXPERIMENT = "retrieval-production-recall"
DEPTHS = ["rapid", "standard", "deep"]
# What the app wires (runtime/agent.py): OpenAISearchGenerationBackend, the
# "shared" arm in engine.GENERATION_BACKENDS.
GENERATION_BACKEND = "shared"


def item_scores(*, output: dict[str, Any], **_: Any) -> list[Evaluation]:
    """Per-review scores: the sweep's numbers, how many rounds ran, and what the
    smaller depths would have scored on this run's pool (``search_recall_at_rapid``
    and so on; see ``engine.recall_at_smaller_caps``)."""
    return [
        *score_summary(output=output),
        Evaluation(name="rounds_run", value=output["rounds_run"]),
        *(
            Evaluation(name=f"{key}_at_{smaller}", value=value)
            for smaller, scores in output.get("recall_at", {}).items()
            for key, value in scores.items()
        ),
    ]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _describe(title: str, s: dict[str, Any]) -> str:
    screened = (
        f", screen_recall={s['screen_recall']:.0%} ({s['n_screened_in']} screened in)"
        if "screen_recall" in s
        else ""
    )
    failed = (
        f", {s['n_failed_calls']} CALLS FAILED — recall is an undercount"
        if s["n_failed_calls"]
        else ""
    )
    at = "".join(
        f"; at {smaller}: {r['search_recall']:.0%} / {r['screen_recall']:.0%}"
        for smaller, r in s.get("recall_at", {}).items()
    )
    return (
        f"  {title[:60]}: search_recall={s['search_recall']:.0%} "
        f"({s['n_found']}/{s['n_ground_truth']}){screened}; "
        f"{s['rounds_run']} round(s), stop={s['stop_condition']}{failed}{at}"
    )


def _run_depth(
    engine: Any,
    dataset: Any,
    items: list[Any],
    client: Any,
    *,
    depth: str,
    label: str,
    git_commit: str,
) -> Any:
    """One dataset run: the chosen reviews at one depth, pipeline constants untouched."""
    constants = DEPTH_CONSTANTS[depth]
    screen = True  # every depth screens once (task 051)
    prompt_version, prompt_sha = _prompt_identity(GENERATION_BACKEND)
    # Flat and stringly: Langfuse coerces metadata values to strings anyway.
    meta = {
        key: str(value)
        for key, value in {
            "experiment": EXPERIMENT,
            "depth": depth,
            "generation_backend": GENERATION_BACKEND,
            "prompt_version": prompt_version,
            "prompt_sha": prompt_sha,
            "papers_cap": constants["papers_cap"],
            "policy_cap": constants["policy_cap"],
            "call_budget": constants["call_budget"],
            "screening": screen,
            "git_commit": git_commit,
        }.items()
    }
    run_name = f"{label}/{depth}"
    print(
        f"\n=== {run_name} (papers_cap={constants['papers_cap']}, "
        f"policy_cap={constants['policy_cap']}, call_budget={constants['call_budget']}, "
        f"screening {'ON' if screen else 'OFF'}) ==="
    )

    summaries: list[dict[str, Any]] = []

    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        ground_truth = ground_truth_from_item(item)
        intent, published_before = item.input["intent"], item.input["published_before"]
        with propagate_attributes(metadata=meta), engine.connect() as connection:
            trans = connection.begin()
            try:
                result = run_one_query(
                    connection,
                    intent,
                    ground_truth,
                    published_before=published_before,
                    depth=depth,
                    run_screen=screen,
                    langfuse_client=client,
                    generation_backend_variant=GENERATION_BACKEND,
                )
            finally:
                # Rolled back, never committed — the database writes are
                # scaffolding to drive the real pipeline, not data to keep.
                trans.rollback()
        review_id = item.metadata["review_id"]
        runs, _queries, _papers = _run_frames(
            result, ground_truth, {"review_id": review_id, "depth": depth}
        )
        summary = {
            **_summary(runs),
            "rounds_run": result.rounds_run,
            "stop_condition": result.stop_condition,
            "recall_at": result.recall_at,
        }
        print(_describe(item.metadata.get("review_title", review_id), summary))
        summaries.append(summary)
        return summary

    # What dataset.run_experiment does, but over our own item list, so --reviews
    # can narrow the run while it still attaches to the dataset (and its version).
    experiment = client.run_experiment(
        name=EXPERIMENT,
        run_name=run_name,
        data=items,
        task=task,
        evaluators=[item_scores],
        max_concurrency=1,  # the providers are rate-limited
        metadata=meta,
        _dataset_version=dataset.version,
    )
    for smaller in DEPTHS:
        scores = [
            s["recall_at"][smaller]
            for s in summaries
            if smaller in s.get("recall_at", {})
        ]
        if scores:
            print(
                f"  derived {smaller} from this run's pool over {len(scores)} reviews: "
                f"search_recall {_mean([r['search_recall'] for r in scores]):.1%}, "
                f"screen_recall {_mean([r['screen_recall'] for r in scores]):.1%}"
            )
    return experiment


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Langfuse dataset (default {DEFAULT_DATASET}).",
    )
    parser.add_argument(
        "--depths",
        nargs="+",
        choices=DEPTHS,
        default=DEPTHS,
        help="Depths to measure, one dataset run each (default: all three).",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Prefix for the run names, <label>/<depth> (default: today's date plus the short "
        "git commit; CI passes dev-<commit>). Reusing a label appends to the existing runs.",
    )
    parser.add_argument(
        "--reviews",
        nargs="+",
        default=None,
        metavar="TEXT",
        help="Only run dataset items whose id, review id or review title contains one of "
        "these texts (case-insensitive). Default: every review.",
    )
    args = parser.parse_args()

    commit = git_commit()
    # Langfuse's ``release`` field is its slot for the code version.
    os.environ.setdefault("LANGFUSE_RELEASE", commit)
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    dataset = client.get_dataset(args.dataset)
    if not dataset.items:
        parser.error(
            f"dataset {args.dataset!r} has no items — run ground_truth/upload.py first."
        )
    try:
        items = select_items(dataset.items, args.reviews)
    except ValueError as exc:
        parser.error(str(exc))
    label = args.run_label or f"{date.today().isoformat()}-{commit[:7]}"
    print(
        f"Dataset: {args.dataset} ({len(items)} of {len(dataset.items)} reviews); "
        f"depths {args.depths}; runs labelled {label}/..."
    )
    for item in items:
        print(f"  {item.id}  {item.metadata.get('review_title', '')[:70]}")

    engine = get_engine()
    rows: list[str] = []
    warnings: list[str] = []
    for depth in args.depths:
        result = _run_depth(
            engine,
            dataset,
            items,
            client,
            depth=depth,
            label=label,
            git_commit=commit,
        )
        # The SDK isolates failures: a review whose run raised is logged to
        # stderr and silently missing from item_results.
        dropped = len(items) - len(result.item_results)
        if dropped:
            warnings.append(
                f"{result.run_name}: {dropped} review(s) failed — see the errors above; "
                "the run's averages leave them out"
            )
        if result.item_results and not result.item_results[0].evaluations:
            raise RuntimeError(
                "no scores were recorded — the evaluator failed (see the errors above)"
            )
        outputs = [r.output for r in result.item_results if isinstance(r.output, dict)]
        failed = sum(o["n_failed_calls"] for o in outputs)
        if failed:
            warnings.append(
                f"{result.run_name}: {failed} provider call(s) failed after retries — "
                "recall is an undercount caused by the provider, not the code"
            )
        # The same averages Langfuse shows in its dataset-runs table.
        search = _mean([o["search_recall"] for o in outputs])
        screen = _mean([o["screen_recall"] for o in outputs if "screen_recall" in o])
        rows.append(
            f"{depth:<10}"
            f"{(f'{search:.1%}' if search is not None else 'n/a'):>20}"
            f"{(f'{screen:.1%}' if screen is not None else 'not measured'):>20}"
            f"{failed:>14}   {result.dataset_run_url}"
        )
        print(f"  -> {result.dataset_run_url}")

    print("\n" + "=" * 72)
    print(
        f"{'depth':<10}{'mean search_recall':>20}{'mean screen_recall':>20}{'failed_calls':>14}"
    )
    print("\n".join(rows))
    for line in warnings:
        print(f"\nWARNING: {line}")
    tracing.flush(client)


if __name__ == "__main__":
    main()
