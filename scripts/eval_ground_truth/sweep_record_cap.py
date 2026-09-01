"""Search-only sweep: which query-generation method, and which
``record_cap_per_backend``, buys recall?

The question this answers: the search stage fetches far more records than it
keeps. ``record_cap_per_backend`` is the number it keeps per backend, and so the
ceiling on recall. How high does that cap have to go before recall stops
improving — and does the way queries are generated change the answer?

The setup, and how it differs from ``run_and_score.py``:

* depth ``rapid`` — one search round, no reformulation loop (same as before).
* ``result_cap_per_backend`` set to 2,000 — 40x the pipeline's own value of
  50, so the number of records a single API call may return stops being the
  limiting factor and the *keep* cap is the only knob. 10,000 was tried first
  and the APIs pushed back: plain page-numbered paging runs out around there
  (OpenAlex requires page x per-page <= 10,000), and 1,000 rapid page requests
  per run is far more traffic than this pipeline normally sends.
* ``record_cap_per_backend`` swept over 50, 100, 250, 500, 1000, 2000.
* The generation backend swept over ``--generation-backends`` — ``v1`` (one
  shared prompt) and ``v2`` (one prompt per provider). See
  ``run_and_score.GENERATION_BACKENDS`` for which prompt files each one reads.
  Every backend is run at every cap, so the two effects can be told apart.
* Screening OFF. Retrieval is what is being measured here, and screening every
  kept candidate is where the LLM bill is. ``screen_recall`` is not reported.

Each combination is run ``--repeats`` times because query generation is an LLM
call and gives slightly different queries each time; comparing single runs
would confuse generation-method and cap effects with query luck.

Cost warning: one repeat can pull thousands of records from OpenAlex and
Overton — up to 10 pages per OpenAlex call and 40 per Overton call. Reviews x
backends x caps x repeats multiplies that: the defaults are 2 x 6 = 12 runs per
review, so a 5-review CSV is 60 runs. Start with ``--repeats 1``, one review,
and a single ``--caps`` value.

Usage (same environment requirements as run_and_score.py — a real Postgres via
DATABASE_URL, plus OPENAI_API_KEY / OPENALEX_API_KEY / OVERTON_API_KEY, which
is what ``--env-file backend/.env`` supplies). One review:

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/sweep_record_cap.py \\
        --title "..." --doi "10.xxxx/yyyy" --repeats 1

Or a batch of reviews from a CSV, which also reports mean and median recall
across them:

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/sweep_record_cap.py \\
        --reviews scripts/eval_ground_truth/input/gt_reviews.csv --repeats 1

The CSV's columns are described in ``_load_reviews``: ``title`` plus one of
``doi``/``url``, an optional ``published_before``, and an ``exclude`` flag.
Every row is validated before any network call, so a malformed sheet fails in a
second rather than part-way through an expensive run. A review whose ground
truth cannot be built is reported and skipped, not fatal — the reviews already
swept are still written out.

``url`` replaces ``doi`` for grey literature with no DOI — a government
evidence review published as a web page, say. There is no ``referenced_works``
API for such a document, so its reference list is fetched, transcribed by an
LLM and resolved citation by citation to DOIs; only the citations that resolve
can be scored, and ``published_before`` must be given by hand because no
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
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from langfuse import Langfuse
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
from policy_atlas.evidence_base.sourcing import search_loop
from run_and_score import (
    GENERATION_BACKENDS,
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
        meta: Identity columns (run_id, review, generation backend, cap, repeat) written
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
            }
        )
    return pd.DataFrame(runs_rows), queries, papers


@dataclass
class ReviewSpec:
    """One review to sweep, from the CSV or from the single-review flags.

    Exactly one of ``doi``/``url`` is set. ``published_before`` is the search
    cutoff: optional for a DOI (derived from OpenAlex) and required for a URL,
    where no machine-readable publication date exists.
    """

    title: str
    doi: str | None = None
    url: str | None = None
    published_before: str | None = None

    @property
    def identifier(self) -> str:
        return self.doi or self.url or ""


def _load_reviews(path: Path) -> list[ReviewSpec]:
    """Read the review list from a CSV, validating it before any network call.

    Recognised columns (case-insensitive, extras ignored):

    * ``title`` — required; cleaned into the search intent.
    * ``doi`` — bare (``10.xxxx/yyyy``) or as a ``https://doi.org/...`` URL.
    * ``url`` — used only when ``doi`` is empty, for grey literature.
    * ``published_before`` — ISO ``YYYY-MM-DD``. Optional for a DOI row, and
      REQUIRED for a URL row.
    * ``exclude`` — any non-empty value skips the row.

    Validation happens here, up front, so a bad row fails in a second rather
    than after an hour of sweeping the rows before it.

    Raises:
        ValueError: With every problem found, one per line, so a broken sheet is
            fixed in one pass instead of one row at a time.
    """
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} has no rows.")

    reviews: list[ReviewSpec] = []
    problems: list[str] = []
    for line_no, raw in enumerate(rows, start=2):  # start=2: row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if row.get("exclude"):
            print(f"  row {line_no}: skipped (exclude={row['exclude']!r})")
            continue
        title, doi, url = row.get("title", ""), row.get("doi", ""), row.get("url", "")
        published_before = row.get("published_before", "")
        if not title:
            problems.append(f"row {line_no}: no title")
            continue
        if not doi and not url:
            problems.append(f"row {line_no} ({title[:50]}): neither doi nor url")
            continue
        if published_before:
            try:
                _iso_date(published_before)
            except argparse.ArgumentTypeError as exc:
                problems.append(f"row {line_no} ({title[:50]}): {exc}")
                continue
        elif not doi:
            problems.append(
                f"row {line_no} ({title[:50]}): a url row needs a published_before date "
                "(ISO YYYY-MM-DD) — there is no machine-readable publication date to "
                "derive one from. Add a 'published_before' column, or set 'exclude' to "
                "skip this review."
            )
            continue
        reviews.append(
            ReviewSpec(
                title=title,
                # A DOI wins when both are present: its reference list comes
                # straight from OpenAlex, rather than via LLM transcription.
                doi=doi or None,
                url=None if doi else (url or None),
                published_before=published_before or None,
            )
        )

    if problems:
        raise ValueError(f"{path} has {len(problems)} unusable row(s):\n  " + "\n  ".join(problems))
    if not reviews:
        raise ValueError(f"{path} has no usable rows (every row excluded?).")
    return reviews


def _build_ground_truth(
    spec: ReviewSpec, langfuse_client: Langfuse | None
) -> tuple[GroundTruth, str]:
    """Build one review's recall target, and settle its search cutoff.

    Returns:
        ``(ground_truth, published_before)``.

    Raises:
        ValueError: If a DOI has no OpenAlex publication date and the spec gives
            no explicit cutoff.
    """
    if spec.doi:
        work = fetch_openalex_work(spec.doi)
        published_before = spec.published_before or (
            _months_earlier(work["publication_date"], 1) if work.get("publication_date") else None
        )
        if not published_before:
            raise ValueError(
                f"OpenAlex has no publication_date for {spec.doi}; give this row an "
                "explicit published_before date."
            )
        return build_ground_truth_from_doi(spec.doi, work=work), published_before
    # Fetches the page, has an LLM transcribe its reference list, then resolves
    # each citation to a DOI — the pipeline can only be scored on what OpenAlex
    # and Overton can be asked for.
    assert spec.url and spec.published_before  # guaranteed by _load_reviews
    return (
        build_ground_truth_from_url(spec.url, spec.title, langfuse_client),
        spec.published_before,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--title",
        help="The review's title — cleaned into the search intent. Required with "
        "--doi/--url; ignored with --reviews, which carries its own titles.",
    )
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
    source_group.add_argument(
        "--reviews",
        type=Path,
        help="Path to a CSV of reviews to sweep together, with columns title, doi, url, "
        "published_before and exclude (see _load_reviews). Every review is swept at "
        "every cap and generation backend, and the summary adds mean and median "
        "recall across reviews.",
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
        help="Query-generation methodologies to compare: v1 = one shared prompt "
        "(search_queries_system_v3.txt); v2 = one prompt per provider "
        "(search_queries_openalex_system_v2.txt + "
        "search_queries_overton_system_v2.txt). Default: both.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Base output path; _runs.csv, _queries.csv and _papers.csv are written "
        "beside it (default results/record_cap_sweep).",
    )
    args = parser.parse_args()
    if not args.reviews and not args.title:
        parser.error("--title is required with --doi/--url.")

    if args.reviews:
        print(f"Reading reviews from {args.reviews}")
        try:
            reviews = _load_reviews(args.reviews)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"{len(reviews)} review(s) to sweep")
    else:
        if args.url and not args.published_before:
            parser.error("--published-before is required with --url (no machine-readable date available).")
        reviews = [
            ReviewSpec(
                title=args.title,
                doi=args.doi,
                url=args.url,
                published_before=args.published_before,
            )
        ]

    langfuse_client = tracing.get_langfuse()
    print(f"Langfuse tracing: {'on' if langfuse_client is not None else 'off (no LANGFUSE_* env vars)'}")
    print(
        f"Sweep: depth={DEPTH}, result_cap={RESULT_CAP_PER_BACKEND}, "
        f"generation_backends={args.generation_backends}, caps={args.caps}, "
        f"repeats={args.repeats}, screening OFF"
    )

    engine = get_engine()

    all_runs: list[pd.DataFrame] = []
    all_queries: list[pd.DataFrame] = []
    all_papers: list[pd.DataFrame] = []
    skipped: list[str] = []
    for review_index, spec in enumerate(reviews, start=1):
        print(f"\n########## [{review_index}/{len(reviews)}] {spec.title} ##########")
        print(f"Building ground truth from {spec.identifier}")
        try:
            ground_truth, published_before = _build_ground_truth(spec, langfuse_client)
        except Exception as exc:
            # One unreachable review must not throw away the hours already spent
            # on the reviews before it. Note it and carry on; the skipped list is
            # reprinted at the end so it cannot be missed.
            print(f"  SKIPPED — could not build ground truth: {exc}")
            skipped.append(f"{spec.title} ({spec.identifier}): {exc}")
            continue
        if not ground_truth.keys:
            print("  SKIPPED — ground truth is empty, so recall is undefined")
            skipped.append(f"{spec.title} ({spec.identifier}): empty ground truth")
            continue

        intent = clean_review_title(spec.title)
        print(
            f"Ground truth: {len(ground_truth.keys)} scorable reference-list entries — "
            f"{len(ground_truth.dois)} DOIs ({ground_truth.resolvable_fraction:.0%} "
            f"OpenAlex-resolvable) + {len(ground_truth.overton_ids)} Overton policy "
            f"documents; {len(ground_truth.unresolved)} citations resolved to neither "
            "and are excluded from the target"
        )
        print(f"Intent: {intent}")
        print(f"Search cutoff: published_before={published_before}")

        runs, queries, papers = _sweep_review(
            engine,
            spec=spec,
            intent=intent,
            ground_truth=ground_truth,
            published_before=published_before,
            caps=args.caps,
            generation_backends=args.generation_backends,
            repeats=args.repeats,
            langfuse_client=langfuse_client,
        )
        all_runs.extend(runs)
        all_queries.extend(queries)
        all_papers.extend(papers)

    if not all_runs:
        parser.error("no review produced any results — nothing to write.")

    _write_and_summarise(
        args.out or Path(__file__).parent / "results" / "record_cap_sweep",
        all_runs,
        all_queries,
        all_papers,
        skipped,
    )


def _sweep_review(
    engine: Any,
    *,
    spec: ReviewSpec,
    intent: str,
    ground_truth: GroundTruth,
    published_before: str,
    caps: list[int],
    generation_backends: list[str],
    repeats: int,
    langfuse_client: Langfuse | None,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]]:
    """Sweep one review over every generation backend x cap x repeat.

    Returns:
        ``(runs, queries, papers)`` frame lists, each row tagged with this
        review's identity so several reviews concatenate into one table.
    """
    # Titles for the reference list: one batched OpenAlex call, reused by every
    # run rather than re-fetched per run.
    gt_titles = ground_truth_table(ground_truth)

    all_runs: list[pd.DataFrame] = []
    all_queries: list[pd.DataFrame] = []
    all_papers: list[pd.DataFrame] = []
    for generation_backend_variant in generation_backends:
        for record_cap in caps:
            constants = _apply_caps(record_cap)
            print(
                f"\n=== generation_backend={generation_backend_variant} "
                f"record_cap_per_backend={record_cap} "
                f"(http_budget={constants['http_budget']}) ==="
            )
            for repeat in range(1, repeats + 1):
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
                            generation_backend_variant=generation_backend_variant,
                        )
                    finally:
                        # Rolled back, never committed — the database writes are
                        # scaffolding to drive the real search stage, not data to keep.
                        trans.rollback()

                meta = {
                    # Carries the review too, so run_ids stay unique when
                    # several reviews land in one file.
                    "run_id": (
                        f"{spec.identifier}|{generation_backend_variant}"
                        f"-cap{record_cap}-r{repeat}"
                    ),
                    # DOI or URL, whichever identified the review — with the
                    # source beside it, since the two ground-truth paths differ
                    # in how complete their reference lists are.
                    "review_id": spec.identifier,
                    "review_source": ground_truth.source,
                    "review_title": spec.title,
                    "intent": intent,
                    "generation_backend_variant": generation_backend_variant,
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
                failed = (
                    f", {total.n_failed_calls} CALLS FAILED — recall is an undercount"
                    if total.n_failed_calls
                    else ""
                )
                print(
                    f"  repeat {repeat}: search_recall={total.search_recall:.0%} "
                    f"({total.n_found}/{total.n_ground_truth}; {per_backend}), "
                    f"{total.n_candidates_kept} candidates kept from "
                    f"{total.n_api_records} records over {total.n_api_calls} calls{failed}"
                )

    return all_runs, all_queries, all_papers


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
            columns="generation_backend_variant",
            values="search_recall",
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
                columns="generation_backend_variant",
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
        print(f"\nWARNING: {len(skipped)} review(s) skipped and NOT in these numbers:")
        for line in skipped:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
