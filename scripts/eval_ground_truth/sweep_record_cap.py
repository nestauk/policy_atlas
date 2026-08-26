"""Search-only sweep: which prompt, and which ``record_cap_per_backend``, buys recall?

The question this answers: the search stage fetches far more records than it
keeps. ``record_cap_per_backend`` is the number it keeps per backend, and so the
ceiling on recall. How high does that cap have to go before recall stops
improving — and does the query-generation prompt change the answer?

The setup, and how it differs from ``run_and_score.py``:

* depth ``rapid`` — one search round, no reformulation loop (same as before).
* ``result_cap_per_backend`` set to 2,000 — 40x the pipeline's own value of
  50, so the number of records a single API call may return stops being the
  limiting factor and the *keep* cap is the only knob. 10,000 was tried first
  and the APIs pushed back: plain page-numbered paging runs out around there
  (OpenAlex requires page x per-page <= 10,000), and 1,000 rapid page requests
  per run is far more traffic than this pipeline normally sends.
* ``record_cap_per_backend`` swept over 50, 100, 250, 500, 1000, 2000.
* The query-generation system prompt swept over ``--prompts`` (default v2 and
  v3, the ``search_queries_system_*.txt`` files beside ``search_prompts.py``).
  Every prompt is run at every cap, so the two effects can be told apart.
* Screening OFF. Retrieval is what is being measured here, and screening every
  kept candidate is where the LLM bill is. ``screen_recall`` is not reported.

Each combination is run ``--repeats`` times because query generation is an LLM
call and gives slightly different queries each time; comparing single runs
would confuse prompt and cap effects with query luck.

Cost warning: one repeat can pull thousands of records from OpenAlex and
Overton — up to 10 pages per OpenAlex call and 40 per Overton call. Prompts x
caps x repeats multiplies that: the defaults are already 2 x 6 = 12 runs. Start
with ``--repeats 1`` and one review.

Usage (same environment requirements as run_and_score.py — a real Postgres via
DATABASE_URL, plus OPENAI_API_KEY / OPENALEX_API_KEY / OVERTON_API_KEY, which
is what ``--env-file backend/.env`` supplies):

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/sweep_record_cap.py \\
        --title "..." --doi "10.xxxx/yyyy" --repeats 1

``--url`` replaces ``--doi`` for grey literature with no DOI — a government
evidence review published as a web page, say. There is no ``referenced_works``
API for such a document, so its reference list is fetched, transcribed by an
LLM and resolved citation by citation to DOIs; only the citations that resolve
can be scored, and ``--published-before`` must be given by hand because no
machine-readable publication date exists. Expect a smaller, noisier recall
target than the DOI path gives.

Writes three CSVs into ``results/``, all joinable on ``run_id`` and all
carrying the review's identifier and title so several reviews' sweeps can be
concatenated:

* ``<name>_runs.csv`` — one row per run x backend, plus a ``backend=all`` row
  per run holding the run's own de-duplicated totals. The scoreboard.
* ``<name>_queries.csv`` — one row per API call: the generated query text, the
  wire parameters it went out with, how many records came back and how many of
  those the review actually cited.
* ``<name>_papers.csv`` — one row per run x reference-list paper: whether an
  API returned it, whether it survived the cap into the candidate set, and
  which backend did each. Filter to ``reached_db`` for the true positives; the
  rows where ``returned_by_api`` is true and ``reached_db`` is false are the
  papers the cap threw away after paying to fetch them.

Cheaper alternative if API volume becomes a problem: acquire keeps the first N
of a fixed candidate stream, so a single run at cap 2000 almost contains the
cap-50, cap-100 ... runs inside it. "Almost" is why this script runs them for
real: the two backends share a de-duplication table, so what OpenAlex keeps
changes what Overton keeps.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from ground_truth import (
    GroundTruth,
    build_ground_truth_from_doi,
    build_ground_truth_from_url,
    fetch_openalex_work,
    record_key,
)
from inspect_run import call_table, ground_truth_table, records_table

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.evidence_base.sourcing import search_generation, search_loop, search_prompts
from run_and_score import (
    QueryResult,
    _iso_date,
    _months_earlier,
    clean_review_title,
    run_one_query,
)

DEPTH = "rapid"
RECORD_CAPS = [50, 100, 250, 500, 1000, 2000]
# Records ONE API call may return, before dedup and before the keep cap. Note
# the keep cap above is per backend across every call, so it is not the same
# scale: rapid makes up to 20 OpenAlex calls, and each of them may bring 2,000
# records to the keep cap's door. 40x the pipeline's own value of 50 — high
# enough not to bind, without the deep-paging trouble 10,000 caused.
RESULT_CAP_PER_BACKEND = 2_000

# The query-generation prompts live beside search_prompts.py as
# search_queries_system_<version>.txt. Add a file there and name it in
# --prompts to include it in the sweep; nothing else needs changing.
PROMPT_DIR = Path(search_prompts.__file__).parent
PROMPT_VERSIONS = ["v2", "v3"]


def _prompt_file(version: str) -> Path:
    return PROMPT_DIR / f"search_queries_system_{version}.txt"


def _apply_prompt(version: str) -> None:
    """Point this process's query generation at one prompt file.

    ``build_queries_messages`` reads the system prompt off its module every
    time it assembles a call, so replacing the attribute is enough — no import
    order to worry about. The trace label is a plain constant that
    ``search_generation`` imported by value, so it has to be set on that module
    too, or Langfuse would label every run with the prompt loaded at startup.

    In-memory only: the committed prompt files are read, never written.
    """
    search_prompts.SEARCH_QUERIES_SYSTEM_PROMPT = _prompt_file(version).read_text(encoding="utf-8")
    search_generation.SEARCH_QUERIES_PROMPT_VERSION = f"search_queries_{version}"


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
    gt_titles: pd.DataFrame,
    meta: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One finished run -> its (runs, queries, papers) rows, all tagged with ``meta``.

    Args:
        result: The finished ``QueryResult``.
        ground_truth: The review's reference list (the recall target).
        gt_titles: ``ground_truth_table()`` output — titles for the target keys.
        meta: Identity columns (run_id, review, prompt, cap, repeat) written
            onto every row of every frame, so the three files join and several
            reviews' sweeps concatenate.
    """
    records = records_table(result.search_calls, ground_truth.keys)
    kept_by_key = _kept_by_backend(result)
    title_by_key = dict(zip(gt_titles["key"], gt_titles["title"], strict=True))
    space_by_key = dict(zip(gt_titles["key"], gt_titles["space"], strict=True))
    in_openalex = dict(zip(gt_titles["key"], gt_titles["in_openalex"], strict=True))

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
                "space": space_by_key.get(key),
                "title": title_by_key.get(key),
                "in_openalex": in_openalex.get(key),
                "returned_by_api": key in returned_by,
                "returned_by": "+".join(sorted(returned_by.get(key, ()))) or None,
                "reached_db": key in kept_by_key,
                "kept_from": kept_by_key.get(key),
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
        runs_rows.append(
            {
                **meta,
                "backend": backend,
                "n_api_calls": len(calls),
                "n_api_records": sum(c["result_count"] for c in calls),
                "n_candidates_kept": len(kept_here),
                "n_ground_truth": n_gt,
                "n_found": len(found),
                "search_recall": round(len(found) / n_gt, 4) if n_gt else 0.0,
            }
        )
    return pd.DataFrame(runs_rows), queries, papers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--title", required=True, help="The review's title — cleaned into the search intent.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--doi", help="The review's DOI — ground truth is its OpenAlex reference list."
    )
    source_group.add_argument(
        "--url",
        help="The review's URL (webpage or PDF) — for grey literature with no DOI. Ground "
        "truth is its reference list transcribed from the fetched text by an LLM and "
        "resolved to DOIs, so it is smaller and noisier than the --doi path. Requires "
        "--published-before.",
    )
    parser.add_argument(
        "--published-before",
        type=_iso_date,
        default=None,
        help="ISO YYYY-MM-DD search cutoff. Derived from the review's own OpenAlex "
        "publication date (one month earlier) in --doi mode when omitted; REQUIRED "
        "with --url, where no machine-readable date exists.",
    )
    parser.add_argument(
        "--repeats", type=int, default=1, help="Runs per prompt x cap (default 1). Each repeat is a full search."
    )
    parser.add_argument(
        "--caps",
        type=int,
        nargs="+",
        default=RECORD_CAPS,
        help=f"record_cap_per_backend values to sweep (default: {RECORD_CAPS}).",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=PROMPT_VERSIONS,
        help="Query-generation prompt versions to compare — the <version> part of "
        f"search_queries_system_<version>.txt (default: {PROMPT_VERSIONS}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Base output path; _runs.csv, _queries.csv and _papers.csv are written "
        "beside it (default results/record_cap_sweep).",
    )
    args = parser.parse_args()

    missing = [v for v in args.prompts if not _prompt_file(v).exists()]
    if missing:
        parser.error(f"no prompt file for {missing} — expected {[str(_prompt_file(v)) for v in missing]}")

    langfuse_client = tracing.get_langfuse()
    print(f"Langfuse tracing: {'on' if langfuse_client is not None else 'off (no LANGFUSE_* env vars)'}")

    identifier = args.doi or args.url
    print(f"Building ground truth for: {args.title} ({identifier})")
    if args.doi:
        work = fetch_openalex_work(args.doi)
        published_before = args.published_before or (
            _months_earlier(work["publication_date"], 1) if work.get("publication_date") else None
        )
        if not published_before:
            parser.error("OpenAlex has no publication_date for this DOI; pass --published-before explicitly.")
        ground_truth = build_ground_truth_from_doi(args.doi, work=work)
    else:
        if not args.published_before:
            parser.error("--published-before is required with --url (no machine-readable date available).")
        published_before = args.published_before
        # Fetches the page, has an LLM transcribe its reference list, then
        # resolves each citation to a DOI — the pipeline can only be scored on
        # what OpenAlex and Overton can be asked for.
        ground_truth = build_ground_truth_from_url(args.url, args.title, langfuse_client)
    intent = clean_review_title(args.title)

    print(
        f"Ground truth: {len(ground_truth.keys)} scorable reference-list entries — "
        f"{len(ground_truth.dois)} DOIs ({ground_truth.resolvable_fraction:.0%} "
        f"OpenAlex-resolvable) + {len(ground_truth.overton_ids)} Overton policy "
        f"documents; {len(ground_truth.unresolved)} citations resolved to neither "
        "and are excluded from the target"
    )
    print(f"Intent: {intent}")
    print(
        f"Sweep: depth={DEPTH}, result_cap={RESULT_CAP_PER_BACKEND}, prompts={args.prompts}, "
        f"caps={args.caps}, repeats={args.repeats}, screening OFF "
        f"({len(args.prompts) * len(args.caps) * args.repeats} runs)"
    )

    engine = get_engine()

    # Titles for the reference list: one batched OpenAlex call, reused by every
    # run rather than re-fetched per run.
    gt_titles = ground_truth_table(ground_truth)

    all_runs: list[pd.DataFrame] = []
    all_queries: list[pd.DataFrame] = []
    all_papers: list[pd.DataFrame] = []
    for prompt_version in args.prompts:
        _apply_prompt(prompt_version)
        for record_cap in args.caps:
            constants = _apply_caps(record_cap)
            print(
                f"\n=== prompt={prompt_version} record_cap_per_backend={record_cap} "
                f"(http_budget={constants['http_budget']}) ==="
            )
            for repeat in range(1, args.repeats + 1):
                with engine.connect() as connection:
                    trans = connection.begin()
                    try:
                        result = run_one_query(
                            connection,
                            intent,
                            ground_truth,
                            published_before=published_before,
                            depth=DEPTH,
                            run_screen=False,
                            langfuse_client=langfuse_client,
                        )
                    finally:
                        # Rolled back, never committed — the database writes are
                        # scaffolding to drive the real search stage, not data to keep.
                        trans.rollback()

                meta = {
                    "run_id": f"{prompt_version}-cap{record_cap}-r{repeat}",
                    # DOI or URL, whichever identified the review — with the
                    # source beside it, since the two ground-truth paths differ
                    # in how complete their reference lists are.
                    "review_id": identifier,
                    "review_source": ground_truth.source,
                    "review_title": args.title,
                    "intent": intent,
                    "prompt_version": prompt_version,
                    "record_cap_per_backend": record_cap,
                    "repeat": repeat,
                }
                runs, queries, papers = _run_frames(result, ground_truth, gt_titles, meta)
                all_runs.append(runs)
                all_queries.append(queries)
                all_papers.append(papers)
                # The raw provider records are the memory hog (thousands per run
                # at this fetch cap); the three frames have everything scored.
                del result

                total = runs[runs["backend"] == "all"].iloc[0]
                per_backend = ", ".join(
                    f"{r.backend} {r.n_found}" for r in runs[runs["backend"] != "all"].itertuples()
                )
                print(
                    f"  repeat {repeat}: search_recall={total.search_recall:.0%} "
                    f"({total.n_found}/{total.n_ground_truth}; {per_backend}), "
                    f"{total.n_candidates_kept} candidates kept from "
                    f"{total.n_api_records} records over {total.n_api_calls} calls"
                )

    base = args.out or Path(__file__).parent / "results" / "record_cap_sweep"
    base.parent.mkdir(parents=True, exist_ok=True)
    runs_frame = pd.concat(all_runs, ignore_index=True)
    for name, frame in (
        ("runs", runs_frame),
        ("queries", pd.concat(all_queries, ignore_index=True)),
        ("papers", pd.concat(all_papers, ignore_index=True)),
    ):
        path = base.with_name(f"{base.name}_{name}.csv")
        frame.to_csv(path, index=False)
        print(f"Wrote {path} ({len(frame)} rows)")

    print("\nMean recall (de-duplicated across backends):")
    print(
        runs_frame[runs_frame["backend"] == "all"]
        .pivot_table(
            index="record_cap_per_backend",
            columns="prompt_version",
            values="search_recall",
            aggfunc="mean",
        )
        .to_string(float_format=lambda v: f"{v:.0%}")
    )


if __name__ == "__main__":
    main()
