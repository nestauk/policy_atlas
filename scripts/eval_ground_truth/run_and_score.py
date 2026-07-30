"""Eval pilot entrypoint: given a systematic review's title + (DOI or URL),
strip its generic review-type suffix (": a systematic review" etc.) to get a
fixed research intent, run it through the real search + screen stages 3 times,
and report stage-attributed recall plus a calibrated precision proxy.

See the plan ("Evaluate search+screen against a systematic review's ground
truth") for the full methodology and why precision is not scored directly
against a single review's bibliography.

Usage (needs a real Postgres via DATABASE_URL, OPENAI_API_KEY,
OPENALEX_API_KEY, OVERTON_API_KEY):

    uv run --project backend python scripts/eval_ground_truth/run_and_score.py \\
        --title "..." --doi "10.xxxx/yyyy"

    uv run --project backend python scripts/eval_ground_truth/run_and_score.py \\
        --title "..." --url "https://.../review.pdf" --published-before 2018-09-01

``--published-before`` (ISO YYYY-MM-DD) is auto-derived from OpenAlex's
publication_date in ``--doi`` mode if omitted — shifted one month earlier
(``_months_earlier()``) since OpenAlex's date filter is inclusive and the
review's own record would otherwise pass its own cutoff and find itself (a
review's literature search also always closes some time before its own
publication date, so this is a conservative approximation of that gap, not
just a bugfix). REQUIRED in ``--url`` mode (no machine-readable date is
available for an arbitrary URL) and used exactly as given there — an explicit
``--published-before`` is never silently adjusted.

Every query runs inside its own rolled-back transaction — nothing this script
does is ever committed to the database.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection

from ground_truth import (
    GroundTruth,
    build_ground_truth_from_doi,
    build_ground_truth_from_url,
    fetch_openalex_work,
    normalize_doi,
)
from relevance_judge import judge_relevance

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.core.schema import evidence_scope, project, project_source_snapshot, runs, source_snapshot
from policy_atlas.evidence_base.assess.screen import ScreenContext, effective_screen_rows, screen_sources
from policy_atlas.evidence_base.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_base.sourcing import search_loop
from policy_atlas.evidence_base.sourcing.acquire import AcquireContext
from policy_atlas.evidence_base.sourcing.search_generation import OpenAISearchGenerationBackend
from policy_atlas.evidence_base.sourcing.search_live import live_search_backends
from policy_atlas.evidence_base.sourcing.search_loop import run_search

QUERY_COUNT = 3
# The LLM-as-a-judge precision proxy is off for now (token cost) while this
# pilot focuses on getting recall right — flip back on when precision matters.
RUN_JUDGE = False

# Trailing review-type clause, anchored to a colon/dash separator at the END
# of the title only — e.g. "...: a systematic review", "...: a scoping review
# of RCTs", "... - A Bibliometric Analysis". Anchoring on the separator is what
# keeps this safe: "Barriers to conducting systematic reviews in LMICs" has no
# such separator before "systematic reviews," so it's left untouched.
_REVIEW_TYPE_SUFFIX_RE = re.compile(
    r"""[:–—-]\s*                       # colon, en/em dash, or hyphen
        (?:an?\s+|the\s+)?              # optional leading article
        (?:
            (?:systematic|scoping|rapid|narrative|literature|umbrella|integrative)
            \s+review(?:\s+and\s+meta-analysis)?
            |
            (?:bibliometric|scientometric)\s+analysis
            |
            meta-analysis
        )
        \s*.*$                          # swallow any trailing clause, e.g. "of RCTs"
    """,
    re.IGNORECASE | re.VERBOSE,
)


def clean_review_title(title: str) -> str:
    """Strip a trailing generic review-type clause, giving a plain research-scope
    statement to use directly as the search intent. No match -> title unchanged.
    """
    stripped = _REVIEW_TYPE_SUFFIX_RE.sub("", title).strip()
    return stripped or title


def _seed_project_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=project_id, created_at=now, name="eval-pilot", status="active", updated_at=now
        )
    )
    run_id = uuid.uuid4()
    conn.execute(runs.insert().values(run_id=run_id, project_id=project_id, status="running", started_at=now))
    return project_id, run_id


def _seed_scope(conn: Connection, project_id: uuid.UUID, intent: str) -> uuid.UUID:
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            project_id=project_id,
            intent=intent,
            context={},
            created_at=datetime.now(UTC),
        )
    )
    return scope_id


def _search_candidate_dois(conn: Connection, project_id: uuid.UUID) -> set[str]:
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(project_source_snapshot, project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()
    return {doi for (metadata,) in rows if (doi := normalize_doi(metadata.get("doi")))}


def _screened_relevant_docs(conn: Connection, project_id: uuid.UUID, scope_id: uuid.UUID) -> list[dict[str, Any]]:
    """Mirrors ``classify._load_relevant_docs``'s join shape over the effective screen rows."""
    effective = effective_screen_rows()
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(
            effective,
            (effective.c.project_source_snapshot_id == project_source_snapshot.c.project_source_snapshot_id)
            & (effective.c.project_id == project_source_snapshot.c.project_id),
        )
        .join(source_snapshot, project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _recall(found: set[str], target: set[str]) -> float:
    if not target:
        return 0.0
    return len(found & target) / len(target)


def partition_screened(
    screened: list[dict[str, Any]], ground_truth_dois: set[str]
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split screened-in docs into: all their DOIs, docs IN the ground-truth
    reference list (judge-calibration sample — known true positives), and docs
    NOT in it (judge-precision-proxy sample).
    """
    screened_dois: set[str] = set()
    in_ground_truth: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    for doc in screened:
        doi = normalize_doi(doc.get("doi"))
        if doi:
            screened_dois.add(doi)
        if doi and doi in ground_truth_dois:
            in_ground_truth.append(doc)
        else:
            unexplained.append(doc)
    return screened_dois, in_ground_truth, unexplained


class _RecordingBackend:
    """Wraps one live ``SearchBackend`` to record every generated query/call and
    its raw returned provider records, for offline diagnosis (e.g. in a
    notebook) of why recall came out low. Pure passthrough otherwise — proxies
    the exact seam ``search_loop.py`` calls on a backend (``acquire.SearchBackend``:
    ``name``/``trust_class``/``mode``/``caps`` plus the 5 fetch/search/lookup
    methods), so it's transparent to the pipeline.
    """

    def __init__(self, inner: Any, calls: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._calls = calls

    @property
    def name(self) -> str:
        return self._inner.name  # type: ignore[no-any-return]

    @property
    def trust_class(self) -> str:
        return self._inner.trust_class  # type: ignore[no-any-return]

    @property
    def mode(self) -> str:
        return self._inner.mode  # type: ignore[no-any-return]

    @property
    def caps(self) -> Any:
        return self._inner.caps

    def _record(
        self, method: str, query: str, wire_params: dict[str, str] | None, records: list[dict[str, Any]]
    ) -> None:
        self._calls.append(
            {
                "backend": self._inner.name,
                "method": method,
                "query": query,
                "wire_params": wire_params,
                "result_count": len(records),
                "records": records,
            }
        )

    def search(
        self, query: str, *, wire_params: dict[str, str] | None = None, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        records = self._inner.search(query, wire_params=wire_params, max_results=max_results)
        self._record("search", query, wire_params, records)
        return records  # type: ignore[no-any-return]

    def fetch_citations(self, record_id: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        records = self._inner.fetch_citations(record_id, max_results=max_results)
        self._record("fetch_citations", record_id, None, records)
        return records  # type: ignore[no-any-return]

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        records = self._inner.fetch_references(record_ids, max_results=max_results)
        self._record("fetch_references", ",".join(record_ids), None, records)
        return records  # type: ignore[no-any-return]

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        records = self._inner.lookup_title(title)
        self._record("lookup_title", title, None, records)
        return records  # type: ignore[no-any-return]

    def lookup_dois(self, dois: list[str], *, max_results: int | None = None) -> list[dict[str, Any]]:
        records = self._inner.lookup_dois(dois, max_results=max_results)
        self._record("lookup_dois", ",".join(dois), None, records)
        return records  # type: ignore[no-any-return]


@dataclass
class QueryResult:
    query: str
    search_candidate_count: int
    screened_relevant_count: int
    search_recall: float
    screen_recall: float
    judge_calibration_rate: float | None
    judge_precision_proxy: float | None
    n_calibration_sampled: int
    n_precision_sampled: int
    search_calls: list[dict[str, Any]]
    """Every generated query + its raw returned provider records, one entry per
    backend call this run made — for offline diagnosis, not scored itself."""


def run_one_query(
    conn: Connection,
    query: str,
    ground_truth: GroundTruth,
    *,
    published_before: str,
    depth: str = "rapid",
    langfuse_client: Langfuse | None = None,
) -> QueryResult:
    project_id, run_id = _seed_project_and_run(conn)
    scope_id = _seed_scope(conn, project_id, query)

    search_context = {
        "search": {
            "depth": depth,
            # Never credit the pipeline for finding sources the review itself
            # could not have cited — the review's own publication date is a
            # hard upper bound on its evidence base, not a suggestion.
            "filters": {"shared": {"published_before": published_before}},
        }
    }
    search_calls: list[dict[str, Any]] = []
    recording_backends = [_RecordingBackend(b, search_calls) for b in live_search_backends()]
    run_search(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=AcquireContext(scope_id=scope_id, intent=query, context=search_context),
        backends=recording_backends,
        generation_backend=OpenAISearchGenerationBackend(langfuse_client=langfuse_client),
    )
    search_dois = _search_candidate_dois(conn, project_id)

    screen_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=ScreenContext(scope_id=scope_id, intent=query, context={}),
        screening_backend=OpenAIScreeningBackend(langfuse_client=langfuse_client),
    )
    screened = _screened_relevant_docs(conn, project_id, scope_id)
    screened_dois, in_ground_truth, unexplained = partition_screened(screened, ground_truth.dois)

    calibration_verdicts = (
        [
            judge_relevance(query, d.get("title") or "", d.get("abstract"), langfuse_client)
            for d in in_ground_truth
        ]
        if RUN_JUDGE
        else []
    )
    precision_verdicts = (
        [judge_relevance(query, d.get("title") or "", d.get("abstract"), langfuse_client) for d in unexplained]
        if RUN_JUDGE
        else []
    )

    return QueryResult(
        query=query,
        search_candidate_count=len(search_dois),
        screened_relevant_count=len(screened_dois),
        search_recall=_recall(search_dois, ground_truth.dois),
        screen_recall=_recall(screened_dois, ground_truth.dois),
        judge_calibration_rate=(
            sum(v.relevant for v in calibration_verdicts) / len(calibration_verdicts)
            if calibration_verdicts
            else None
        ),
        judge_precision_proxy=(
            sum(v.relevant for v in precision_verdicts) / len(precision_verdicts)
            if precision_verdicts
            else None
        ),
        n_calibration_sampled=len(calibration_verdicts),
        n_precision_sampled=len(precision_verdicts),
        search_calls=search_calls,
    )


def _fmt_pct(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "n/a"


def _agg(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values)}


def build_report(
    *,
    title: str,
    identifier: str,
    published_before: str,
    depth: str,
    result_cap_per_backend: int,
    ground_truth: GroundTruth,
    results: list[QueryResult],
) -> dict[str, Any]:
    return {
        "review": {
            "title": title,
            "source": ground_truth.source,
            "identifier": identifier,
            "published_before": published_before,
            "search_depth": depth,
            "result_cap_per_backend": result_cap_per_backend,
        },
        "ground_truth": {
            "n_dois": len(ground_truth.dois),
            "openalex_resolvable_fraction": ground_truth.resolvable_fraction,
            "n_unresolved_citations": len(ground_truth.unresolved),
            "unresolved_citations": ground_truth.unresolved,
        },
        "per_query": [asdict(r) for r in results],
        "aggregate": {
            "search_recall": _agg([r.search_recall for r in results]),
            "screen_recall": _agg([r.screen_recall for r in results]),
            "judge_calibration_rate": _agg(
                [r.judge_calibration_rate for r in results if r.judge_calibration_rate is not None]
            ),
            "judge_precision_proxy": _agg(
                [r.judge_precision_proxy for r in results if r.judge_precision_proxy is not None]
            ),
        },
        "limitations": [
            "Ground truth is the review's FULL reference list, not just its "
            "included/screened studies — background, methods, and theory citations "
            "count toward recall too, even though the pipeline was never going to "
            "retrieve them for a topical research question. Recall here is a "
            "conservative (lower-bound) estimate for that reason.",
            "Precision is still not scored against the reference list directly — a "
            "screened-in result absent from it isn't proven irrelevant (the review "
            "had its own time cutoff and scope). judge_precision_proxy is the actual "
            "precision signal, and is only as trustworthy as judge_calibration_rate "
            "from the same run — a low calibration rate means discount the proxy.",
            "OpenAlex + Overton is the entire search space; recall is bounded above "
            "by ground_truth.openalex_resolvable_fraction.",
            f"Search depth was '{depth}' — 'rapid' means a single round with no "
            "reformulation loop; only 'standard'/'deep' exercise it.",
            f"Search was constrained to sources published before {published_before} "
            "(the review's own publication date) — a candidate the pipeline could "
            "only have found by time-traveling past the review is excluded up front.",
            f"result_cap_per_backend was {result_cap_per_backend} for this run — the max "
            "candidates any single backend can contribute, split across however many "
            "queries search-generation produced. This bounds candidate-pool size "
            "directly; a reference list larger than the candidate pool caps recall "
            "structurally, before search/screen quality even enters into it.",
        ],
    }


def _iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid ISO date (YYYY-MM-DD)") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(f"{value!r} must be a YYYY-MM-DD ISO date")
    return value


def _months_earlier(iso_date: str, months: int) -> str:
    """``iso_date`` shifted back ``months`` calendar months, clamped to the
    target month's actual last day (e.g. 2023-03-31 - 1 month -> 2023-02-28).
    """
    d = date.fromisoformat(iso_date)
    total_months = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total_months, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def run_review(
    engine: Any,
    *,
    title: str,
    identifier: str,
    published_before: str,
    depth: str,
    result_cap_per_backend: int,
    ground_truth: GroundTruth,
    langfuse_client: Langfuse | None,
) -> tuple[dict[str, Any], list[QueryResult]]:
    """Run one review's cleaned-title intent through search+screen
    ``QUERY_COUNT`` times, score against its ground truth. Shared by both
    single-review and ``--corpus`` batch mode — the raw ``QueryResult`` list is
    returned alongside the report so batch mode can pool metrics across reviews.

    ``result_cap_per_backend`` is report-only here — the value that actually
    governs ``run_search()`` is whatever ``main()`` already set on
    ``search_loop.DEPTH_CONSTANTS[depth]`` before calling in; this parameter
    just carries the effective number through to ``build_report()``.
    """
    print(
        f"Ground truth: {len(ground_truth.dois)} reference-list DOIs, "
        f"{ground_truth.resolvable_fraction:.0%} OpenAlex-resolvable, "
        f"{len(ground_truth.unresolved)} unresolved citations"
    )
    print(
        f"Search constrained to depth={depth}, published_before={published_before}, "
        f"result_cap_per_backend={result_cap_per_backend}"
    )

    query = clean_review_title(title)
    queries = [query] * QUERY_COUNT
    print(f"Fixed intent (run {QUERY_COUNT}x): {query}")

    results: list[QueryResult] = []
    for query in queries:
        print(f"\nRunning: {query}")
        with engine.connect() as connection:
            trans = connection.begin()
            try:
                result = run_one_query(
                    connection,
                    query,
                    ground_truth,
                    published_before=published_before,
                    depth=depth,
                    langfuse_client=langfuse_client,
                )
                results.append(result)
                print(
                    f"  search_recall={result.search_recall:.0%} screen_recall={result.screen_recall:.0%} "
                    f"judge_calibration={_fmt_pct(result.judge_calibration_rate)} "
                    f"judge_precision_proxy={_fmt_pct(result.judge_precision_proxy)} "
                    f"({len(result.search_calls)} search calls recorded)"
                )
            finally:
                # Rolled back, never committed — this script's DB writes are pure
                # scaffolding to drive run_search/screen_sources, not data to keep.
                trans.rollback()

    report = build_report(
        title=title,
        identifier=identifier,
        published_before=published_before,
        depth=depth,
        result_cap_per_backend=result_cap_per_backend,
        ground_truth=ground_truth,
        results=results,
    )
    return report, results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default=None, help="Required unless --corpus.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--doi", help="Review DOI — ground truth is built from its OpenAlex record.")
    source_group.add_argument(
        "--url", help="Review URL (webpage or PDF) — for grey-literature reviews with no DOI."
    )
    source_group.add_argument(
        "--corpus",
        help="Path to a corpus JSON built by fetch_review_corpus.py — runs every review in it and "
        "reports per-review plus aggregate-across-reviews metrics.",
    )
    parser.add_argument(
        "--published-before",
        type=_iso_date,
        default=None,
        help="ISO YYYY-MM-DD search cutoff. Auto-derived from OpenAlex in --doi mode if omitted; "
        "REQUIRED in --url mode. Ignored in --corpus mode (each review uses its own publication date).",
    )
    parser.add_argument(
        "--depth", choices=["rapid", "standard", "deep"], default="rapid", help="Search depth (default: rapid)."
    )
    parser.add_argument(
        "--result-cap-per-backend",
        type=int,
        default=None,
        help="Override the chosen depth's max accepted results per backend (default: the depth's "
        "own built-in cap, e.g. 50 for rapid — see search_loop.DEPTH_CONSTANTS). Raises the "
        "candidate-pool ceiling without changing depth's round/reformulation shape.",
    )
    parser.add_argument(
        "--disable-wall-clock",
        action="store_true",
        help="Remove the chosen depth's wall-clock budget (e.g. 30s for rapid) so a raised "
        "--result-cap-per-backend has time to actually fetch/paginate through. Eval-only — "
        "never touches the pipeline file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path in --corpus mode (default results/corpus_eval_report.json). "
        "Ignored in --doi/--url mode, which derives its own filename.",
    )
    args = parser.parse_args()
    if not args.corpus and not args.title:
        parser.error("--title is required unless using --corpus.")

    # Eval-local overrides, applied to this process only — never touches the
    # committed pipeline file. A copy-and-replace, not an in-place mutation.
    overrides: dict[str, Any] = {}
    if args.result_cap_per_backend is not None:
        overrides["result_cap_per_backend"] = args.result_cap_per_backend
    if args.disable_wall_clock:
        overrides["wall_clock_s"] = float("inf")
    if overrides:
        search_loop.DEPTH_CONSTANTS[args.depth] = {
            **search_loop.DEPTH_CONSTANTS[args.depth],
            **overrides,
        }
    result_cap_per_backend = search_loop.DEPTH_CONSTANTS[args.depth]["result_cap_per_backend"]

    langfuse_client = tracing.get_langfuse()
    print(f"Langfuse tracing: {'on' if langfuse_client is not None else 'off (no LANGFUSE_* env vars)'}")
    engine = get_engine()

    if args.corpus:
        corpus = json.loads(Path(args.corpus).read_text())
        reviews = corpus["reviews"]
        print(f"Running eval over {len(reviews)} reviews from {args.corpus}")

        review_reports: list[dict[str, Any]] = []
        all_results: list[QueryResult] = []
        for entry in reviews:
            print(f"\n=== {entry['title']} ===")
            ground_truth = GroundTruth(
                dois=set(entry["ground_truth"]["dois"]),
                resolvable_fraction=entry["ground_truth"]["resolvable_fraction"],
                source="doi",
            )
            report, results = run_review(
                engine,
                title=entry["title"],
                identifier=entry["doi"],
                published_before=_months_earlier(entry["publication_date"], 1),
                depth=args.depth,
                result_cap_per_backend=result_cap_per_backend,
                ground_truth=ground_truth,
                langfuse_client=langfuse_client,
            )
            review_reports.append(report)
            all_results.extend(results)

        combined = {
            "corpus": {"n_reviews": len(review_reports), "query_filter": corpus.get("query_filter")},
            "reviews": review_reports,
            "aggregate_across_reviews": {
                "search_recall": _agg([r.search_recall for r in all_results]),
                "screen_recall": _agg([r.screen_recall for r in all_results]),
            },
        }
        out_path = args.out or Path(__file__).parent / "results" / "corpus_eval_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(combined, indent=2))
        print(f"\nWrote corpus report to {out_path}")
        return

    if args.doi:
        print(f"Building ground truth for: {args.title} ({args.doi})")
        work = fetch_openalex_work(args.doi)
        raw_publication_date = work.get("publication_date")
        if args.published_before:
            published_before = args.published_before
        elif raw_publication_date:
            published_before = _months_earlier(raw_publication_date, 1)
        else:
            published_before = None
        if not published_before:
            parser.error(
                "OpenAlex has no publication_date for this DOI; pass --published-before explicitly."
            )
        ground_truth = build_ground_truth_from_doi(args.doi, work=work)
        identifier = args.doi
    else:
        if not args.published_before:
            parser.error("--published-before is required with --url (no machine-readable date available).")
        print(f"Building ground truth for: {args.title} ({args.url})")
        published_before = args.published_before
        ground_truth = build_ground_truth_from_url(args.url, args.title, langfuse_client)
        identifier = args.url

    report, _results = run_review(
        engine,
        title=args.title,
        identifier=identifier,
        published_before=published_before,
        depth=args.depth,
        result_cap_per_backend=result_cap_per_backend,
        ground_truth=ground_truth,
        langfuse_client=langfuse_client,
    )
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")[:60]
    identifier_slug = re.sub(r"[^a-zA-Z0-9]+", "_", identifier).strip("_")[:80]
    out_path = out_dir / f"{slug}-{identifier_slug}.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nWrote report to {out_path}")


if __name__ == "__main__":
    main()
