"""Eval pilot entrypoint: given a systematic review's title + (DOI or URL),
strip its generic review-type suffix (": a systematic review" etc.) to get a
fixed research intent, run it through the real search + screen stages 3 times,
and report stage-attributed recall plus a calibrated precision proxy.

See the plan ("Evaluate search+screen against a systematic review's ground
truth") for the full methodology and why precision is not scored directly
against a single review's bibliography.

Usage (needs a real Postgres via DATABASE_URL, OPENAI_API_KEY,
OPENALEX_API_KEY, OVERTON_API_KEY). ``--env-file backend/.env`` is REQUIRED:
nothing in the code loads a .env, so without it every one of those variables is
unset (see backend/Makefile — ``uv run --env-file`` is the one place local env
loading happens, which keeps settings on pure os.environ):

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/run_and_score.py \\
        --title "..." --doi "10.xxxx/yyyy"

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/run_and_score.py \\
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

Two separate caps bound how many candidates a run collects, and confusing them
wastes a lot of time. Both are reported in every run's JSON:

* ``result_cap_per_backend`` — records requested per HTTP call. With the depth's
  ``http_budget`` (number of calls allowed), this bounds what a backend can be
  *asked* for.
* ``record_cap_per_backend`` — candidates acquire *keeps* per backend, applied
  after dedup, before persisting. This is the ``acquire.capped`` log line, and
  normally the tighter of the two: records past it were fetched and paid for,
  then discarded. This is the cap that sets the recall ceiling.

This eval overrides the second one to ``RECORD_CAP_PER_BACKEND`` (see the
constant for the measurement behind that choice). Both overrides are applied to
this process only and never touch the committed pipeline file.
"""

from __future__ import annotations

import argparse
import calendar
import json
import re
import statistics
import uuid
from collections.abc import Callable
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
    record_key,
)
from relevance_judge import judge_relevance

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.core.schema import evidence_scope, project, project_source_snapshot, runs, source_snapshot
from policy_atlas.evidence_base.assess.screen import ScreenContext, effective_screen_rows, screen_sources
from policy_atlas.evidence_base.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_base.sourcing import search_loop
from policy_atlas.evidence_base.sourcing.acquire import AcquireContext
from policy_atlas.evidence_base.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
)
from policy_atlas.evidence_base.sourcing.search_live import live_search_backends
from policy_atlas.evidence_base.sourcing.search_loop import run_search

QUERY_COUNT = 3
# How many candidates acquire keeps per backend, overriding the depth's own
# value for this eval. rapid ships 50; measured on
# 10.1016/S2468-2667(22)00311-5, the API calls returned 23 of the review's 60
# cited papers and this cap discarded 18 of them — the papers were fetched and
# paid for, then dropped. 200 is a deliberate experiment knob, not a pipeline
# recommendation: raising it also grows the screening LLM bill roughly in
# proportion, since every kept candidate gets screened.
RECORD_CAP_PER_BACKEND = 200
# The LLM-as-a-judge precision proxy is off for now (token cost) while this
# pilot focuses on getting recall right — flip back on when precision matters.
RUN_JUDGE = False

# The two query-generation methodologies this eval compares:
#
# * ``v1`` — one shared prompt writes both the OpenAlex keyword queries and the
#   Overton paraphrases (``search_queries_system_v3.txt``).
# * ``v2`` — one prompt per provider (``search_queries_openalex_system_v2.txt``
#   and ``search_queries_overton_system_v2.txt``), each called once per query.
#
# Both read their prompts from the committed files beside ``search_prompts.py``,
# so picking a variant is the whole choice — there is nothing to swap at
# runtime.
GENERATION_BACKENDS = {
    "v1": OpenAISearchGenerationBackend,
    "v2": V2SearchGenerationBackend,
}

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


def _search_candidate_docs(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Metadata for every candidate that reached the database — i.e. what
    survived acquire's dedup and cap, not everything the APIs returned."""
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(project_source_snapshot, project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _keys_of(docs: list[dict[str, Any]]) -> set[str]:
    """Scoring keys for a set of documents: DOI where there is one, else the
    Overton document id (see ``ground_truth.record_key``). Documents with
    neither cannot be matched against the ground truth and are dropped."""
    return {key for d in docs if (key := record_key(d))}


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
    screened: list[dict[str, Any]], ground_truth_keys: set[str]
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split screened-in docs into: all their scoring keys, docs IN the
    ground-truth reference list (judge-calibration sample — known true
    positives), and docs NOT in it (judge-precision-proxy sample).

    Keys are DOIs where a document has one and Overton document ids otherwise,
    so a screened-in policy document is matched rather than silently treated as
    unexplained (see ``ground_truth.record_key``).
    """
    screened_dois: set[str] = set()
    in_ground_truth: list[dict[str, Any]] = []
    unexplained: list[dict[str, Any]] = []
    for doc in screened:
        key = record_key(doc)
        if key:
            screened_dois.add(key)
        if key and key in ground_truth_keys:
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
        self,
        method: str,
        query: str,
        wire_params: dict[str, str] | None,
        call: Callable[[], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Run one backend call and record it, whether it succeeds or fails.

        A failed call is recorded with zero records and the error text, then
        re-raised so the pipeline behaves exactly as it would without this
        wrapper (``search_loop`` catches it and marks the call errored). Without
        this, a query that 500ed was invisible: it never reached the recorded
        call list, so the queries CSV silently omitted it and the run looked
        like it had simply found less.
        """
        try:
            records = call()
        except Exception as exc:
            self._calls.append(
                {
                    "backend": self._inner.name,
                    "method": method,
                    "query": query,
                    "wire_params": wire_params,
                    "result_count": 0,
                    "records": [],
                    "error": str(exc),
                }
            )
            raise
        self._calls.append(
            {
                "backend": self._inner.name,
                "method": method,
                "query": query,
                "wire_params": wire_params,
                "result_count": len(records),
                "records": records,
                "error": None,
            }
        )
        return records

    def search(
        self, query: str, *, wire_params: dict[str, str] | None = None, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        return self._record(
            "search",
            query,
            wire_params,
            lambda: self._inner.search(query, wire_params=wire_params, max_results=max_results),
        )

    def fetch_citations(self, record_id: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        return self._record(
            "fetch_citations",
            record_id,
            None,
            lambda: self._inner.fetch_citations(record_id, max_results=max_results),
        )

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        return self._record(
            "fetch_references",
            ",".join(record_ids),
            None,
            lambda: self._inner.fetch_references(record_ids, max_results=max_results),
        )

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        return self._record(
            "lookup_title", title, None, lambda: self._inner.lookup_title(title)
        )

    def lookup_dois(self, dois: list[str], *, max_results: int | None = None) -> list[dict[str, Any]]:
        return self._record(
            "lookup_dois",
            ",".join(dois),
            None,
            lambda: self._inner.lookup_dois(dois, max_results=max_results),
        )


@dataclass
class QueryResult:
    query: str
    search_candidate_count: int
    screened_relevant_count: int
    search_recall: float
    screen_recall: float | None
    """None when the run skipped screening (``run_screen=False``) — screening
    was not measured, which is different from screening scoring zero."""
    judge_calibration_rate: float | None
    judge_precision_proxy: float | None
    n_calibration_sampled: int
    n_precision_sampled: int
    search_calls: list[dict[str, Any]]
    """Every generated query + its raw returned provider records, one entry per
    backend call this run made — for offline diagnosis, not scored itself."""
    search_docs: list[dict[str, Any]]
    """Metadata for every candidate that survived acquire's dedup + cap into the
    database. Diagnosis only: lets you tell "the API never returned it" from
    "the cap threw it away" (see inspect_run.funnel_table)."""
    screened_docs: list[dict[str, Any]]
    """Metadata for every candidate the screening LLM marked relevant.
    Diagnosis only — the scored numbers above are counts over these."""


def run_one_query(
    conn: Connection,
    query: str,
    ground_truth: GroundTruth,
    *,
    published_before: str,
    depth: str = "rapid",
    run_screen: bool = True,
    langfuse_client: Langfuse | None = None,
    generation_backend_variant: str = "v1",
) -> QueryResult:
    """Run one intent through search (and optionally screening), and score it.

    Args:
        run_screen: False skips the screening stage entirely — no screening LLM
            calls, no screening bill. Use it when the experiment is about search
            retrieval only; ``screen_recall`` comes back None.
    """
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
        generation_backend=GENERATION_BACKENDS[generation_backend_variant](
            langfuse_client=langfuse_client
        ),
    )
    search_docs = _search_candidate_docs(conn, project_id)
    search_dois = _keys_of(search_docs)

    if run_screen:
        screen_sources(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=ScreenContext(scope_id=scope_id, intent=query, context={}),
            screening_backend=OpenAIScreeningBackend(langfuse_client=langfuse_client),
        )
        screened = _screened_relevant_docs(conn, project_id, scope_id)
    else:
        screened = []
    screened_dois, in_ground_truth, unexplained = partition_screened(screened, ground_truth.keys)

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
        search_recall=_recall(search_dois, ground_truth.keys),
        screen_recall=_recall(screened_dois, ground_truth.keys) if run_screen else None,
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
        search_docs=search_docs,
        screened_docs=screened,
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
    record_cap_per_backend: int,
    generation_backend_variant: str,
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
            "record_cap_per_backend": record_cap_per_backend,
            "generation_backend_variant": generation_backend_variant,
        },
        "ground_truth": {
            "n_dois": len(ground_truth.dois),
            # The recall target itself, not just its size — without it a saved
            # report cannot be re-scored or unpicked offline (inspect_run.py).
            "dois": sorted(ground_truth.dois),
            "openalex_resolvable_fraction": ground_truth.resolvable_fraction,
            # Reference-list entries with no DOI that Overton does hold — the
            # policy-document half of the target. Empty in --doi mode.
            "n_overton_ids": len(ground_truth.overton_ids),
            "overton_ids": sorted(ground_truth.overton_ids),
            "n_target_keys": len(ground_truth.keys),
            "n_unresolved_citations": len(ground_truth.unresolved),
            "unresolved_citations": ground_truth.unresolved,
        },
        "per_query": [asdict(r) for r in results],
        "aggregate": {
            "search_recall": _agg([r.search_recall for r in results]),
            "screen_recall": _agg([r.screen_recall for r in results if r.screen_recall is not None]),
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
            "OpenAlex + Overton is the entire search space. DOI-keyed targets are "
            "bounded above by ground_truth.openalex_resolvable_fraction; Overton-keyed "
            "targets exist in the ground truth only because a title lookup found them "
            "in Overton, so their ceiling is 100% by construction — a cited policy "
            "document Overton does not hold is unresolvable and left out of the target "
            "entirely, which flatters neither backend but does narrow what is measured.",
            f"Search depth was '{depth}' — 'rapid' means a single round with no "
            "reformulation loop; only 'standard'/'deep' exercise it.",
            f"Search was constrained to sources published before {published_before} "
            "(the review's own publication date) — a candidate the pipeline could "
            "only have found by time-traveling past the review is excluded up front.",
            f"result_cap_per_backend was {result_cap_per_backend} for this run — the "
            "number of records requested per HTTP call (search_loop trims each "
            "response to it). With the depth's http_budget, this bounds how much a "
            "backend can be ASKED for.",
            f"record_cap_per_backend was {record_cap_per_backend} for this run — the "
            "number of search-arm candidates acquire KEEPS per backend, applied after "
            "dedup and before persisting (the 'acquire.capped' log line). This is the "
            "tighter of the two caps and the one that bounds candidate-pool size: "
            "records beyond it were fetched, paid for, and then discarded. A reference "
            "list larger than the candidate pool caps recall structurally, before "
            "search/screen quality even enters into it.",
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
    record_cap_per_backend: int,
    ground_truth: GroundTruth,
    langfuse_client: Langfuse | None,
    run_screen: bool = True,
    generation_backend_variant: str = "v1",
) -> tuple[dict[str, Any], list[QueryResult]]:
    """Run one review's cleaned-title intent through search+screen
    ``QUERY_COUNT`` times, score against its ground truth. Shared by both
    single-review and ``--corpus`` batch mode — the raw ``QueryResult`` list is
    returned alongside the report so batch mode can pool metrics across reviews.

    Both cap arguments are report-only here — the values that actually govern
    ``run_search()`` are whatever ``main()`` already set on
    ``search_loop.DEPTH_CONSTANTS[depth]`` before calling in; these parameters
    just carry the effective numbers through to ``build_report()``.
    """
    print(
        f"Ground truth: {len(ground_truth.keys)} scorable entries — "
        f"{len(ground_truth.dois)} DOIs ({ground_truth.resolvable_fraction:.0%} "
        f"OpenAlex-resolvable) + {len(ground_truth.overton_ids)} Overton policy documents, "
        f"{len(ground_truth.unresolved)} unresolved citations"
    )
    print(
        f"Search constrained to depth={depth}, published_before={published_before}, "
        f"generation_backend_variant={generation_backend_variant}, "
        f"result_cap_per_backend={result_cap_per_backend} (per HTTP call), "
        f"record_cap_per_backend={record_cap_per_backend} (kept per backend)"
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
                    run_screen=run_screen,
                    langfuse_client=langfuse_client,
                    generation_backend_variant=generation_backend_variant,
                )
                results.append(result)
                print(
                    f"  search_recall={result.search_recall:.0%} "
                    f"screen_recall={_fmt_pct(result.screen_recall)} "
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
        record_cap_per_backend=record_cap_per_backend,
        generation_backend_variant=generation_backend_variant,
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
        "--generation-backend",
        choices=list(GENERATION_BACKENDS),
        default="v1",
        help="Query-generation methodology: v1 = one shared prompt "
        "(search_queries_system_v3.txt); v2 = one prompt per provider "
        "(search_queries_openalex_system_v2.txt + "
        "search_queries_overton_system_v2.txt). Default: v1.",
    )
    parser.add_argument(
        "--result-cap-per-backend",
        type=int,
        default=None,
        help="Override how many records are requested per HTTP call (default: the depth's own "
        "value, e.g. 50 for rapid — see search_loop.DEPTH_CONSTANTS). With the depth's "
        "http_budget this bounds how much a backend can be ASKED for. Usually NOT the cap "
        "you want: see --record-cap-per-backend.",
    )
    parser.add_argument(
        "--record-cap-per-backend",
        type=int,
        default=RECORD_CAP_PER_BACKEND,
        help="Override how many search-arm candidates acquire KEEPS per backend, applied "
        f"after dedup (the 'acquire.capped' log line). Defaults to {RECORD_CAP_PER_BACKEND} "
        "for this eval, above rapid's built-in 50, because 50 was measured discarding "
        "reference-list papers the APIs had already returned. This is the cap that bounds "
        "the candidate pool, and so the recall ceiling. Pass 0 to use the depth's own value.",
    )
    parser.add_argument(
        "--no-screen",
        action="store_true",
        help="Skip the screening stage — search only, no screening LLM calls and no "
        "screening bill. screen_recall is reported as n/a. Use when the experiment is "
        "about search retrieval.",
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
    if args.record_cap_per_backend:  # 0 means "leave the depth's own value alone"
        overrides["record_cap_per_backend"] = args.record_cap_per_backend
    if overrides:
        search_loop.DEPTH_CONSTANTS[args.depth] = {
            **search_loop.DEPTH_CONSTANTS[args.depth],
            **overrides,
        }
    # Read both back from DEPTH_CONSTANTS, not from args, so the report always
    # states the value the run actually used — including when no override applied.
    constants = search_loop.DEPTH_CONSTANTS[args.depth]
    result_cap_per_backend = constants["result_cap_per_backend"]
    record_cap_per_backend = constants["record_cap_per_backend"]

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
                record_cap_per_backend=record_cap_per_backend,
                ground_truth=ground_truth,
                langfuse_client=langfuse_client,
                run_screen=not args.no_screen,
                generation_backend_variant=args.generation_backend,
            )
            review_reports.append(report)
            all_results.extend(results)

        combined = {
            "corpus": {"n_reviews": len(review_reports), "query_filter": corpus.get("query_filter")},
            "reviews": review_reports,
            "aggregate_across_reviews": {
                "search_recall": _agg([r.search_recall for r in all_results]),
                "screen_recall": _agg(
                    [r.screen_recall for r in all_results if r.screen_recall is not None]
                ),
            },
            "generation_backend_variant": args.generation_backend,
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
        record_cap_per_backend=record_cap_per_backend,
        ground_truth=ground_truth,
        langfuse_client=langfuse_client,
        run_screen=not args.no_screen,
        generation_backend_variant=args.generation_backend,
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
