"""Measure what production does: search (and screening) recall at the real
depth constants, one Langfuse dataset run per depth.

The sweep (``sweep_record_cap.py``) asks a research question by pushing the
caps far above production. This script asks the operational one: with the
pipeline exactly as deployed, how much of each review's reference list does a
``rapid``, ``standard`` or ``deep`` search find? Run it by hand, locally or
from the Actions tab (``.github/workflows/production-recall.yml``), so the
answer builds up into a history. It records numbers; it does not pass or fail
on them.

How a depth is run (mirrors ``runtime/runner.py``'s round loop, see
``search_eval.run_one_query``):

* ``rapid`` — one search round, no screening. Search recall only.
* ``standard`` / ``deep`` — search, screen the new candidates, then let the
  pipeline's own rule (``search_loop.evaluate_deep_stop``) decide whether to
  search again: it stops at the depth's round cap, or early when a round's
  screening yield collapses. Rounds after the first unlock the reformulate /
  snowball / suggest / diversity arms, which are seeded from the screening
  verdicts, so screening is not optional here. Search recall and screen recall
  are both scored.

Cost: rapid is cheap (at most 25 provider calls x 50 records per review, one
generation LLM call). standard and deep screen every kept candidate each round
— a few hundred screening LLM calls per review per run.

Scores on each dataset item (one review): the sweep's ``SCORE_KEYS``
(search_recall, n_found, n_api_calls, n_failed_calls, ..., screen_recall,
n_screened_in) plus ``rounds_run``. There are no run-level scores of our own:
Langfuse's dataset-runs table shows the mean of each per-review score across
the reviews, and that is the run summary. Check ``n_failed_calls`` before
reading recall — any value above 0 means a provider call failed after retries,
so that review's recall is an undercount caused by the provider, not the code.

Usage (same environment as the sweep; the dataset must already be uploaded
with ``ground_truth_dataset.py``):

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/production_recall.py \\
        [--depths rapid standard deep] [--run-label LABEL] [--reviews TEXT ...]

``--reviews`` restricts the run to the dataset items whose id, review id or
review title contains one of the given texts (case-insensitive) — for trying
an expensive depth on a single review. The run still attaches to the dataset;
it simply has fewer items, so its averages cover only those reviews.
"""

from __future__ import annotations

import argparse
import os
from datetime import date
from typing import Any

from ground_truth_dataset import DEFAULT_DATASET
from langfuse import Evaluation, propagate_attributes
from search_eval import run_one_query
from sweep_record_cap import (
    _git_commit,
    _ground_truth_from_item,
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
# "shared" arm in search_eval.GENERATION_BACKENDS.
GENERATION_BACKEND = "shared"


def item_scores(*, output: dict[str, Any], **_: Any) -> list[Evaluation]:
    """Per-review scores: the sweep's numbers plus how many rounds ran."""
    return [
        *score_summary(output=output),
        Evaluation(name="rounds_run", value=output["rounds_run"]),
    ]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def select_items(items: list[Any], patterns: list[str] | None) -> list[Any]:
    """The dataset items to run: all of them, or those matching ``--reviews``.

    A pattern matches an item when it appears (case-insensitive) in the item's
    id, its ``review_id`` or its ``review_title``.

    Raises:
        ValueError: No item matched, listing what was available.
    """
    if not patterns:
        return items
    wanted = [p.lower() for p in patterns]
    chosen = [
        item
        for item in items
        if any(
            p in text
            for p in wanted
            for text in (
                str(item.id).lower(),
                str(item.metadata.get("review_id", "")).lower(),
                str(item.metadata.get("review_title", "")).lower(),
            )
        )
    ]
    if not chosen:
        available = "\n  ".join(
            f"{item.id}  {item.metadata.get('review_title', '')[:70]}" for item in items
        )
        raise ValueError(
            f"--reviews {patterns} matched no dataset item. Items:\n  {available}"
        )
    return chosen


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
    return (
        f"  {title[:60]}: search_recall={s['search_recall']:.0%} "
        f"({s['n_found']}/{s['n_ground_truth']}){screened}; "
        f"{s['rounds_run']} round(s), stop={s['stop_condition']}{failed}"
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
    screen = depth != "rapid"
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
            "record_cap_per_backend": constants["record_cap_per_backend"],
            "result_cap_per_backend": constants["result_cap_per_backend"],
            "round_cap": constants["round_cap"],
            "call_budget": constants["call_budget"],
            "screening": screen,
            "git_commit": git_commit,
        }.items()
    }
    run_name = f"{label}/{depth}"
    print(
        f"\n=== {run_name} (record_cap={constants['record_cap_per_backend']}, "
        f"result_cap={constants['result_cap_per_backend']}, round_cap={constants['round_cap']}, "
        f"call_budget={constants['call_budget']}, screening {'ON' if screen else 'OFF'}) ==="
    )

    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        ground_truth = _ground_truth_from_item(item)
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
            result,
            ground_truth,
            ground_truth.titles,
            {"review_id": review_id, "depth": depth},
        )
        summary = {
            **_summary(runs),
            "rounds_run": result.rounds_run,
            "stop_condition": result.stop_condition,
        }
        print(_describe(item.metadata.get("review_title", review_id), summary))
        return summary

    # What dataset.run_experiment does, but over our own item list, so --reviews
    # can narrow the run while it still attaches to the dataset (and its version).
    return client.run_experiment(
        name=EXPERIMENT,
        run_name=run_name,
        data=items,
        task=task,
        evaluators=[item_scores],
        max_concurrency=1,  # the providers are rate-limited
        metadata=meta,
        _dataset_version=dataset.version,
    )


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

    git_commit = _git_commit()
    # Langfuse's ``release`` field is its slot for the code version.
    os.environ.setdefault("LANGFUSE_RELEASE", git_commit)
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    dataset = client.get_dataset(args.dataset)
    if not dataset.items:
        parser.error(
            f"dataset {args.dataset!r} has no items — run ground_truth_dataset.py first."
        )
    try:
        items = select_items(dataset.items, args.reviews)
    except ValueError as exc:
        parser.error(str(exc))
    label = args.run_label or f"{date.today().isoformat()}-{git_commit[:7]}"
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
            git_commit=git_commit,
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
