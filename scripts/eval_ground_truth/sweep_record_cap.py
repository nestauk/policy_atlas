"""Search-only sweep, run as a Langfuse experiment: which query-generation
method, and which ``record_cap_per_backend``, buys recall?

The question this answers: the search stage fetches far more records than it
keeps. ``record_cap_per_backend`` is the number it keeps per backend, and so the
ceiling on recall. How high does that cap have to go before recall stops
improving — and does the way queries are generated change the answer?

The setup:

* depth ``rapid`` — one search round, no reformulation loop.
* ``result_cap_per_backend`` set to 2,000 — 40x the pipeline's own value of
  50, so the number of records a single API call may return stops being the
  limiting factor and the *keep* cap is the only knob. 10,000 was tried first
  and the APIs pushed back: plain page-numbered paging runs out around there
  (OpenAlex requires page x per-page <= 10,000), and 1,000 rapid page requests
  per run is far more traffic than this pipeline normally sends.
* ``record_cap_per_backend`` swept over 50, 100, 250, 500, 1000, 2000.
* The generation backend swept over ``--generation-backends`` — ``shared``
  (one prompt writes both providers' queries) and ``per-provider`` (one prompt
  per provider). See ``search_eval.GENERATION_BACKENDS``; each class names the
  prompt files it reads in ``prompt_files``. Every backend is run at every
  cap, so the two effects can be told apart.
* Screening OFF by default. Retrieval is what is usually being measured, and
  screening every kept candidate is where the LLM bill is. Pass ``--screen`` to
  run it too, which adds a ``screen_recall`` score; the gap between it and
  ``search_recall`` is what screening lost.

Each combination is run ``--repeats`` times because query generation is an LLM
call and gives slightly different queries each time; comparing single runs
would confuse generation-method and cap effects with query luck.

How it is organised in Langfuse:

* The ground truth is a Langfuse **dataset**, one item per review, built from
  the CSVs under ``input/`` by ``ground_truth_dataset.py``. The sweep reads the
  dataset, never the CSVs, so a run is pinned to the dataset version it saw.
* Each generation backend x cap x repeat combination is one **dataset run**,
  named ``<label>/<backend>-cap<cap>-r<repeat>``. ``--run-label`` defaults to
  today's date plus the short git commit, so a sweep repeated next week lands
  in fresh runs instead of appending to these (Langfuse merges runs of the same
  name).
* Every trace carries the cell's configuration in its metadata — generation
  backend, prompt version and hash, both caps, depth, repeat, git commit — so
  the trace list can be filtered on any of them. The git commit also goes in
  Langfuse's ``release`` field, its slot for "which version of the code".
* Recall and the efficiency counts are numeric **scores** on each item trace,
  so the dataset-run comparison view shows them side by side per run.
* Langfuse labels every experiment trace with the environment
  ``sdk-experiment``; filter on that to separate them from app traffic.

Langfuse is therefore required (``LANGFUSE_PUBLIC_KEY`` / ``SECRET_KEY`` /
``HOST``).

Cost warning: one repeat can pull thousands of records from OpenAlex and
Overton — up to 10 pages per OpenAlex call and 40 per Overton call. Reviews x
backends x caps x repeats multiplies that: the defaults are 2 x 6 = 12 runs per
review. Start with ``--repeats 1`` and a single ``--caps`` value.

Usage (needs a real Postgres via DATABASE_URL, plus OPENAI_API_KEY /
OPENALEX_API_KEY / OVERTON_API_KEY, which is what ``--env-file backend/.env``
supplies), after the dataset has been uploaded once:

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/ground_truth_dataset.py
    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/sweep_record_cap.py --repeats 1

Besides the Langfuse runs, writes three CSVs into ``results/``, all joinable on
``run_id`` and all carrying the review's identifier and title:

* ``<name>_runs.csv`` — one row per run x backend, plus a ``backend=all`` row
  per run holding the run's own de-duplicated totals. The scoreboard.
* ``<name>_queries.csv`` — one row per API call: the generated query text, the
  wire parameters it went out with, how many records came back and how many of
  those the review actually cited.
* ``<name>_papers.csv`` — one row per run x reference-list paper: whether an
  API returned it, whether it survived the cap into the candidate set, which
  backend did each, and (with ``--screen``) whether screening kept it. Filter
  to ``reached_db`` for the true positives; the rows where ``returned_by_api``
  is true and ``reached_db`` is false are the papers the cap threw away after
  paying to fetch them.

Cheaper alternative if API volume becomes a problem: acquire keeps the first N
of a fixed candidate stream, so a single run at cap 2000 almost contains the
cap-50, cap-100 ... runs inside it. "Almost" is why this script runs them for
real: the two backends share a de-duplication table, so what OpenAlex keeps
changes what Overton keeps.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from ground_truth import GroundTruth, record_key
from ground_truth_dataset import DEFAULT_DATASET
from inspect_run import call_table, records_table
from langfuse import Evaluation, propagate_attributes
from search_eval import GENERATION_BACKENDS, QueryResult, _keys_of, run_one_query

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.evidence_search.sourcing import search_loop

DEPTH = "rapid"
RECORD_CAPS = [50, 100, 250, 500, 1000, 2000]
# Records ONE API call may return, before dedup and before the keep cap. Note
# the keep cap above is per backend across every call, so it is not the same
# scale: rapid makes up to 20 OpenAlex calls, and each of them may bring 2,000
# records to the keep cap's door. 40x the pipeline's own value of 50 — high
# enough not to bind, without the deep-paging trouble 10,000 caused.
RESULT_CAP_PER_BACKEND = 2_000
EXPERIMENT = "retrieval-cap-prompt-sweep"
# The numbers each run's summary carries into Langfuse as scores. The two
# screening ones are only present when the run screened (``--screen``).
SCORE_KEYS = [
    "search_recall",
    "n_found",
    "n_api_calls",
    "n_failed_calls",
    "n_api_records",
    "n_candidates_kept",
    "screen_recall",
    "n_screened_in",
]


def _apply_caps(record_cap: int) -> dict[str, Any]:
    """Point this process's ``rapid`` depth at one cap pair.

    A copy-and-replace on the in-memory constants only — the committed pipeline
    file is never touched, and nothing here survives the process.
    """
    search_loop.DEPTH_CONSTANTS[DEPTH] = {
        **search_loop.DEPTH_CONSTANTS[DEPTH],
        "result_cap_per_backend": RESULT_CAP_PER_BACKEND,
        "record_cap_per_backend": record_cap,
    }
    return search_loop.DEPTH_CONSTANTS[DEPTH]


def _prompt_identity(variant: str) -> tuple[str, str]:
    """``(prompt_version, prompt_sha)`` for one generation backend.

    The version is the prompt file name(s) minus ``_system`` (the same string
    the generation spans record); the hash covers the files' bytes, so an edit
    to the wording without a rename still shows up as a different prompt. Both
    are derived from the backend class's own ``prompt_files``, so the eval
    cannot drift from what the pipeline actually reads.
    """
    files = GENERATION_BACKENDS[variant].prompt_files
    version = "+".join(f.stem.replace("_system", "") for f in files)
    sha = hashlib.sha256(b"".join(f.read_bytes() for f in files)).hexdigest()[:12]
    return version, sha


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _kept_by_backend(result: QueryResult) -> dict[str, str]:
    """Scoring key -> the backend whose record survived into the candidate set.

    Acquire de-duplicates across backends, so a document both providers
    returned is kept once, under whichever backend reached it first. The key is
    a DOI where the document has one and an Overton document id otherwise, so
    policy documents count (see ``ground_truth.record_key``).
    """
    kept: dict[str, str] = {}
    for doc in result.search_docs:
        key = record_key(doc)
        if key:
            kept[key] = doc.get("backend", "unknown")
    return kept


def _run_frames(
    result: QueryResult,
    ground_truth: GroundTruth,
    titles: dict[str, str],
    meta: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One finished run -> its (runs, queries, papers) rows, all tagged with ``meta``.

    Args:
        result: The finished ``QueryResult``.
        ground_truth: The review's reference list (the recall target).
        titles: Key -> title for the target keys, from the dataset item.
        meta: Identity columns (run_id, review, generation backend, cap, repeat) written
            onto every row of every frame, so the three files join and several
            reviews' sweeps concatenate.
    """
    records = records_table(result.search_calls, ground_truth.keys)
    kept_by_key = _kept_by_backend(result)
    # None when the run did not screen: "not measured", not "nothing survived".
    screened_keys = _keys_of(result.screened_docs) if result.screen_recall is not None else None

    # Which backends' API calls returned each cited document, before any capping.
    returned_by: dict[str, set[str]] = {}
    for row in records[records["in_gt"]].itertuples():
        returned_by.setdefault(row.key, set()).add(row.backend)

    papers = pd.DataFrame(
        [
            {
                **meta,
                "key": key,
                # "doi" or "overton": which half of the target this document is,
                # so OpenAlex and Overton recall can be read separately.
                "space": "doi" if key in ground_truth.dois else "overton",
                "title": titles.get(key),
                "returned_by_api": key in returned_by,
                "returned_by": "+".join(sorted(returned_by.get(key, ()))) or None,
                "reached_db": key in kept_by_key,
                "kept_from": kept_by_key.get(key),
                "screened_in": None if screened_keys is None else key in screened_keys,
            }
            for key in sorted(ground_truth.keys)
        ]
    )

    queries = call_table(result.search_calls, ground_truth.keys)
    queries = queries.assign(**meta)[[*meta, *queries.columns]]

    # One row per backend, plus an "all" row: the backend rows sum the work
    # done, the "all" row is the run's own de-duplicated recall (a paper both
    # backends returned is one hit, not two).
    n_gt = len(ground_truth.keys)
    runs_rows: list[dict[str, Any]] = []
    for backend in [*sorted({call["backend"] for call in result.search_calls}), "all"]:
        calls = [c for c in result.search_calls if backend == "all" or c["backend"] == backend]
        found = {
            key for key, kept in kept_by_key.items() if backend == "all" or kept == backend
        } & ground_truth.keys
        kept_here = [
            doc
            for doc in result.search_docs
            if backend == "all" or doc.get("backend") == backend
        ]
        screened_here = None if screened_keys is None else screened_keys & found
        runs_rows.append(
            {
                **meta,
                "backend": backend,
                "n_api_calls": len(calls),
                # Calls that exhausted their retries and returned nothing. Any
                # value above 0 means this row's recall is an undercount caused
                # by the provider, not by the queries — check before comparing
                # it with another run's.
                "n_failed_calls": sum(1 for c in calls if c.get("error")),
                "n_api_records": sum(c["result_count"] for c in calls),
                "n_candidates_kept": len(kept_here),
                "n_ground_truth": n_gt,
                "n_found": len(found),
                "search_recall": round(len(found) / n_gt, 4) if n_gt else 0.0,
                "n_screened_in": None if screened_here is None else len(screened_here),
                "screen_recall": (
                    None if screened_here is None else round(len(screened_here) / n_gt, 4) if n_gt else 0.0
                ),
            }
        )
    return pd.DataFrame(runs_rows), queries, papers


def _summary(runs: pd.DataFrame) -> dict[str, Any]:
    """The run's de-duplicated totals as plain numbers — the trace output.

    Screening keys are left out when the run did not screen, so no score is
    recorded for a stage that was never measured."""
    total = runs[runs["backend"] == "all"].iloc[0]
    return {
        **{
            key: float(total[key]) if key.endswith("_recall") else int(total[key])
            for key in SCORE_KEYS
            if pd.notna(total[key])
        },
        "n_ground_truth": int(total["n_ground_truth"]),
        "found_by_backend": {
            row.backend: int(row.n_found) for row in runs[runs["backend"] != "all"].itertuples()
        },
    }


def score_summary(*, output: dict[str, Any], **_: Any) -> list[Evaluation]:
    """The experiment evaluator: lift the task's summary numbers into Langfuse scores."""
    return [Evaluation(name=key, value=output[key]) for key in SCORE_KEYS if key in output]


def _ground_truth_from_item(item: Any) -> GroundTruth:
    """Rebuild the recall target from a dataset item's ``expected_output``."""
    keys = set(item.expected_output["keys"])
    overton_ids = {key for key in keys if key.startswith("overton:")}
    return GroundTruth(
        dois=keys - overton_ids,
        overton_ids=overton_ids,
        source=item.metadata.get("source", "doi"),
        titles=item.expected_output.get("titles", {}),
    )


def _run_cell(
    engine: Any,
    dataset: Any,
    client: Any,
    *,
    variant: str,
    record_cap: int,
    repeat: int,
    label: str,
    git_commit: str,
    screen: bool,
    sink: tuple[list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]],
) -> Any:
    """Run one generation backend x cap x repeat cell over every dataset item.

    Returns:
        The SDK's ``ExperimentResult``. The three pandas frames per item are
        appended to ``sink`` rather than returned through Langfuse — anything the
        task returns is serialised onto the trace, and these are far too big.
    """
    constants = _apply_caps(record_cap)
    prompt_version, prompt_sha = _prompt_identity(variant)
    # Flat and stringly: Langfuse coerces metadata values to strings anyway.
    meta = {
        key: str(value)
        for key, value in {
            "experiment": EXPERIMENT,
            "generation_backend": variant,
            "prompt_version": prompt_version,
            "prompt_sha": prompt_sha,
            "record_cap_per_backend": record_cap,
            "result_cap_per_backend": constants["result_cap_per_backend"],
            "depth": DEPTH,
            "screening": screen,
            "repeat": repeat,
            "git_commit": git_commit,
        }.items()
    }
    run_name = f"{label}/{variant}-cap{record_cap}-r{repeat}"
    print(f"\n=== {run_name} (call_budget={constants['call_budget']}) ===")

    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        ground_truth = _ground_truth_from_item(item)
        intent = item.input["intent"]
        published_before = item.input["published_before"]
        # propagate_attributes is what puts the cell's configuration on the
        # trace itself (filterable in the trace list); run_experiment's own
        # metadata= lands on the dataset run and the root observation.
        with propagate_attributes(metadata=meta), engine.connect() as connection:
            trans = connection.begin()
            try:
                result = run_one_query(
                    connection,
                    intent,
                    ground_truth,
                    published_before=published_before,
                    depth=DEPTH,
                    run_screen=screen,
                    langfuse_client=client,
                    generation_backend_variant=variant,
                )
            finally:
                # Rolled back, never committed — the database writes are
                # scaffolding to drive the real search stage, not data to keep.
                trans.rollback()

        review_id = item.metadata["review_id"]
        row_meta = {
            # Carries the review too, so run_ids stay unique across reviews.
            "run_id": f"{review_id}|{variant}-cap{record_cap}-r{repeat}",
            "review_id": review_id,
            "review_source": ground_truth.source,
            "review_title": item.metadata.get("review_title"),
            "intent": intent,
            "generation_backend": variant,
            "record_cap_per_backend": record_cap,
            "repeat": repeat,
        }
        frames = _run_frames(result, ground_truth, ground_truth.titles, row_meta)
        for bucket, frame in zip(sink, frames, strict=True):
            bucket.append(frame)

        summary = _summary(frames[0])
        per_backend = ", ".join(f"{b} {n}" for b, n in summary["found_by_backend"].items())
        failed = (
            f", {summary['n_failed_calls']} CALLS FAILED — recall is an undercount"
            if summary["n_failed_calls"]
            else ""
        )
        screened = (
            f"screen_recall={summary['screen_recall']:.0%} ({summary['n_screened_in']} screened in) "
            if "screen_recall" in summary
            else ""
        )
        print(
            f"  {item.metadata.get('review_title', review_id)[:60]}: "
            f"search_recall={summary['search_recall']:.0%} "
            f"({summary['n_found']}/{summary['n_ground_truth']}; {per_backend}), {screened}"
            f"{summary['n_candidates_kept']} candidates kept from "
            f"{summary['n_api_records']} records over {summary['n_api_calls']} calls{failed}"
        )
        return summary

    return dataset.run_experiment(
        name=EXPERIMENT,
        run_name=run_name,
        task=task,
        evaluators=[score_summary],
        # Serial on purpose: _apply_caps mutates module-level constants, and
        # the providers are rate-limited.
        max_concurrency=1,
        metadata=meta,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Langfuse dataset holding the reviews and their reference lists (default "
        f"{DEFAULT_DATASET}; upload it with ground_truth_dataset.py).",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Prefix for every dataset run name this sweep creates (default: today's date "
        "plus the short git commit). Reusing a label appends to the existing runs.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Runs per generation backend x cap (default 1). Each repeat is a full search.",
    )
    parser.add_argument(
        "--caps",
        type=int,
        nargs="+",
        default=RECORD_CAPS,
        help=f"record_cap_per_backend values to sweep (default: {RECORD_CAPS}).",
    )
    parser.add_argument(
        "--generation-backends",
        nargs="+",
        choices=list(GENERATION_BACKENDS),
        default=list(GENERATION_BACKENDS),
        help="Query-generation methodologies to compare: 'shared' = one prompt writes "
        "both providers' queries; 'per-provider' = one prompt per provider. Each "
        "class names its prompt files in prompt_files. Default: both.",
    )
    parser.add_argument(
        "--screen",
        action="store_true",
        help="Also run the screening stage and score screen_recall. Every kept candidate "
        "is an LLM call, so this multiplies the bill by the cap — start with one small cap.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Base output path; _runs.csv, _queries.csv and _papers.csv are written "
        "beside it (default results/record_cap_sweep).",
    )
    args = parser.parse_args()

    git_commit = _git_commit()
    # Langfuse's ``release`` field is its slot for the code version; the SDK
    # reads it from this variable when the client is built.
    os.environ.setdefault("LANGFUSE_RELEASE", git_commit)
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "this sweep records Langfuse experiment runs and needs LANGFUSE_PUBLIC_KEY, "
            "LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    dataset = client.get_dataset(args.dataset)
    if not dataset.items:
        parser.error(f"dataset {args.dataset!r} has no items — run ground_truth_dataset.py first.")
    label = args.run_label or f"{date.today().isoformat()}-{git_commit[:7]}"

    print(f"Dataset: {args.dataset} ({len(dataset.items)} reviews); runs labelled {label}/...")
    print(
        f"Sweep: depth={DEPTH}, result_cap={RESULT_CAP_PER_BACKEND}, "
        f"generation_backends={args.generation_backends}, caps={args.caps}, "
        f"repeats={args.repeats}, screening {'ON' if args.screen else 'OFF'}, git_commit={git_commit[:7]}"
    )

    engine = get_engine()
    sink: tuple[list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]] = ([], [], [])
    skipped: list[str] = []
    for variant in args.generation_backends:
        for record_cap in args.caps:
            for repeat in range(1, args.repeats + 1):
                result = _run_cell(
                    engine,
                    dataset,
                    client,
                    variant=variant,
                    record_cap=record_cap,
                    repeat=repeat,
                    label=label,
                    git_commit=git_commit,
                    screen=args.screen,
                    sink=sink,
                )
                # The SDK isolates failures: a review whose search raised is
                # logged to stderr and silently missing from item_results, and a
                # broken evaluator yields a run with no scores at all.
                dropped = len(dataset.items) - len(result.item_results)
                if dropped:
                    skipped.append(f"{result.run_name}: {dropped} review(s) failed — see the errors above")
                if result.item_results and not result.item_results[0].evaluations:
                    raise RuntimeError("no scores were recorded — the evaluator failed (see the errors above)")
                print(f"  -> {result.dataset_run_url}")

    if not sink[0]:
        parser.error("no run produced any results — nothing to write.")
    _write_and_summarise(
        args.out or Path(__file__).parent / "results" / "record_cap_sweep", *sink, skipped
    )
    tracing.flush(client)


def _write_and_summarise(
    base: Path,
    all_runs: list[pd.DataFrame],
    all_queries: list[pd.DataFrame],
    all_papers: list[pd.DataFrame],
    skipped: list[str],
) -> None:
    """Write the three CSVs and print the recall tables."""
    base.parent.mkdir(parents=True, exist_ok=True)
    runs_frame = pd.concat(all_runs, ignore_index=True)
    for name, frame in (
        ("runs", runs_frame),
        ("queries", pd.concat(all_queries, ignore_index=True)),
        ("papers", pd.concat(all_papers, ignore_index=True)),
    ):
        path = base.with_name(f"{base.name}_{name}.csv")
        frame.to_csv(path, index=False)
        print(f"\nWrote {path} ({len(frame)} rows)")

    # One row per run: the de-duplicated total across both backends.
    totals = runs_frame[runs_frame["backend"] == "all"]
    n_reviews = totals["review_id"].nunique()
    pct = lambda v: f"{v:.0%}"  # noqa: E731 - pandas float_format wants a callable

    print("\n" + "=" * 72)
    print("Recall per review (rows = record_cap_per_backend, columns = generation backend)")
    for review_id, group in totals.groupby("review_id", sort=False):
        print(f"\n{group['review_title'].iloc[0]}")
        print(f"  {review_id} — {group['n_ground_truth'].iloc[0]} scorable references")
        table = group.pivot_table(
            index="record_cap_per_backend",
            columns="generation_backend",
            values=[c for c in ("search_recall", "screen_recall") if group[c].notna().any()],
            aggfunc="mean",
        )
        print("\n".join("  " + line for line in table.to_string(float_format=pct).splitlines()))

    if n_reviews > 1:
        print("\n" + "=" * 72)
        print(f"Across all {n_reviews} reviews")
        # Mean and median side by side: mean moves with one review that has a
        # much larger reference list, median does not. A wide gap between them
        # means one review is carrying the result.
        print(
            totals.pivot_table(
                index="record_cap_per_backend",
                columns="generation_backend",
                values="search_recall",
                aggfunc=["mean", "median"],
            ).to_string(float_format=pct)
        )

    failed_calls = int(totals["n_failed_calls"].sum())
    if failed_calls:
        print(
            f"\nWARNING: {failed_calls} API call(s) failed after all retries. Those runs "
            "returned fewer records than they should have, so their recall is an "
            "undercount — see the 'error' column in the queries CSV."
        )
    if skipped:
        print(f"\nWARNING: {len(skipped)} run(s) lost reviews and are NOT complete in these numbers:")
        for line in skipped:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
