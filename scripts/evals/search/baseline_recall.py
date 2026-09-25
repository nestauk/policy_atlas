"""Search recall baselines: one plain search per review on three services.

The pipeline finds a share of each review's reference list (see
``production_recall.py``). This script gives that share something to be compared
with. A **baseline** is the simplest possible search: the review's intent text is sent
once, as it is, to one search service. No language model writes queries, nothing is
screened, and there is no second round. The four **arms** (as in an experiment) are
Semantic Scholar's keyword search, Semantic Scholar's semantic snippet search, Consensus
and OpenAlex. The results are scored
against the same ground truth, with the same recall formula and the same scoring key
(a lowercase DOI, Digital Object Identifier) as the pipeline runs, so the rows sit next
to each other in ``history.py`` and ``results/history.md``.

How it runs, in two stages:

1. **Fetch once.** For each arm and review the script sends one search and reads every
   result page up to 1,000 results. The raw pages are written to a local **cache**, one
   JSON file per arm and review under ``results/cache/``. The cache never holds an API
   key and is ignored by git. A later run reads the cache and makes no service calls,
   unless ``--refresh`` is passed. Consensus is a paid service, so this matters.
2. **Score from the cache.** For each **cap** (50, 100, 200 and 1,000 results) the first
   N results in the service's own order are kept, duplicates on the scoring key are
   removed, and recall is the share of the review's references among them. Each arm
   and cap becomes one Langfuse dataset run with the scores listed in
   ``BASELINE_SCORE_KEYS``. ``api_cost_usd`` is the computed price of fetching that
   cap on its own (from the service's price table), not the money this run spent.

Keys: ``SEMANTIC_SCHOLAR_API_KEY`` (both Semantic Scholar arms) and ``CONSENSUS_API_KEY``
in ``backend/.env``. OpenAlex needs none. Rate limits and retries: one request per second
for Semantic Scholar keyword search and Consensus, one per three seconds for the snippet
arm, five per second for OpenAlex; a 429 or 5xx answer is retried
up to four times, after which the request counts as failed and that review's fetch
stops and is marked incomplete (it is fetched again next run).

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/baseline_recall.py [--arms ...] [--caps ...] \\
        [--reviews TEXT ...] [--run-label LABEL] [--refresh] [--dry-run]

``--dry-run`` still fills missing cache entries, but only prints scores; it uploads
no Langfuse run. Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypeAlias

import httpx
from ground_truth import GroundTruth, openalex_get, record_key
from ground_truth_dataset import DEFAULT_DATASET
from langfuse import Evaluation, propagate_attributes
from production_recall import select_items
from sweep_record_cap import _git_commit, _ground_truth_from_item

from policy_atlas.core import tracing

ARMS = ["semantic-scholar", "semantic-scholar-snippet", "consensus", "openalex-raw"]
SNIPPET = "semantic-scholar-snippet"
BATCH_SIZE = 500  # paper/batch accepts up to 500 ids per call
DEFAULT_CAPS = [50, 100, 200, 1000]
RESULT_CEILING = 1000
EXPERIMENT = "retrieval-baseline"
CACHE_DIR = Path(__file__).parent / "results" / "cache"
# Prices read from the services' documentation on 2026-09-25.
CONSENSUS_USD_PER_CALL = (
    0.05  # our API beta account pays this on every call, no free amount
)
CONSENSUS_PAPERS_PER_CALL = 100
# The free Semantic Scholar tier throttles below one request per second in practice;
# the snippet arm makes only three requests per review, so it can afford to go slowly.
MIN_INTERVAL_S = {
    "semantic-scholar": 1.0,
    SNIPPET: 3.0,
    "consensus": 1.0,
    "openalex-raw": 0.2,
}
KEY_ENV = {
    "semantic-scholar": "SEMANTIC_SCHOLAR_API_KEY",
    SNIPPET: "SEMANTIC_SCHOLAR_API_KEY",
    "consensus": "CONSENSUS_API_KEY",
}
BASELINE_SCORE_KEYS = [
    "search_recall",
    "n_found",
    "n_api_calls",
    "n_failed_calls",
    "n_api_records",
    "n_candidates_kept",
    "api_cost_usd",
]

# get(url, params, headers, json=None): a GET, or a POST with a JSON body when json is given.
Getter: TypeAlias = Callable[..., httpx.Response | None]


@dataclass
class Fetched:
    """Raw pages and fetch metadata for one service search."""

    pages: list[dict[str, Any]]
    request: dict[str, str]
    page_size: int
    n_failed_calls: int
    complete: bool
    fetched_at: str


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def make_getter(
    arm: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    get: Any = httpx.get,
    post: Any = httpx.post,
) -> Getter:
    """Build the rate-limited, retrying HTTP getter for an arm.

    Args:
        arm: Baseline arm name.
        sleep: Injectable wait function, used by self-checks.
        get: Injectable ``httpx.get`` equivalent, used by self-checks.
        post: Injectable ``httpx.post`` equivalent, for the snippet arm's id lookup.

    Returns:
        A getter accepting URL/path, query parameters, and headers.
    """
    last_request: float | None = None

    def getter(
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
    ) -> httpx.Response | None:
        nonlocal last_request
        for attempt in range(4):
            if last_request is not None:
                wait = MIN_INTERVAL_S[arm] - (time.monotonic() - last_request)
                if wait > 0:
                    sleep(wait)
            last_request = time.monotonic()
            try:
                if arm == "openalex-raw":
                    response = openalex_get(url, **params)
                elif json is not None:
                    response = post(
                        url, params=params, headers=headers, json=json, timeout=60.0
                    )
                else:
                    response = get(url, params=params, headers=headers, timeout=30.0)
            except httpx.TransportError:
                response = None
            if (
                response is not None
                and response.status_code != 429
                and not 500 <= response.status_code < 600
            ):
                return response
            if attempt == 3:
                return response
            retry_after = (
                response.headers.get("retry-after") if response is not None else None
            )
            try:
                delay = (
                    float(int(retry_after))
                    if retry_after is not None
                    else float(2**attempt)
                )
            except ValueError:
                delay = float(2**attempt)
            sleep(delay)
            # Every retry delay is at least the arm interval, so it already
            # satisfies the pacing rule without a second, redundant wait.
            last_request = None
        return None

    return getter


def semantic_scholar_cutoff(cutoff: str) -> str:
    """Convert an ISO cutoff into Semantic Scholar's inclusive filter."""
    return f":{cutoff}"


def openalex_cutoff(cutoff: str) -> str:
    """Convert an ISO cutoff into OpenAlex's inclusive filter."""
    return f"to_publication_date:{cutoff}"


def consensus_cutoff(cutoff: str) -> dict[str, str]:
    """Convert an ISO cutoff into Consensus's inclusive year/month filters."""
    return {"year_max": cutoff[:4], "month_max": str(int(cutoff[5:7]))}


def semantic_scholar_query(intent: str) -> str:
    """Apply Semantic Scholar's documented hyphen workaround."""
    return intent.replace("-", " ")


def _failure(
    pages: list[dict[str, Any]], request: dict[str, str], page_size: int
) -> Fetched:
    return Fetched(pages, request, page_size, 1, False, _now())


def fetch_semantic_scholar(
    intent: str, cutoff: str, *, get: Getter, api_key: str
) -> Fetched:
    """Fetch Semantic Scholar result pages through the 1,000-record ceiling.

    Args:
        intent: Dataset search text.
        cutoff: ISO date before which results must have been published.
        get: Rate-limited response getter.
        api_key: Semantic Scholar key.

    Returns:
        Raw pages and completion metadata.
    """
    pages: list[dict[str, Any]] = []
    offset = 0
    request = {
        "query": semantic_scholar_query(intent),
        "fields": "externalIds,title,publicationDate",
        "limit": "100",
        "offset": "0",
        "publicationDateOrYear": semantic_scholar_cutoff(cutoff),
    }
    while offset < RESULT_CEILING:
        params = {**request, "offset": str(offset)}
        response = get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params,
            {"x-api-key": api_key},
        )
        if response is None or response.status_code != 200:
            return _failure(pages, request, 100)
        body = response.json()
        pages.append(body)
        data = body.get("data", [])
        if (
            not data
            or "next" not in body
            or sum(len(p.get("data", [])) for p in pages) >= RESULT_CEILING
        ):
            break
        offset = int(body["next"])
    return Fetched(pages, request, 100, 0, True, _now())


def fetch_semantic_scholar_snippet(
    intent: str, cutoff: str, *, get: Getter, api_key: str
) -> Fetched:
    """Fetch Semantic Scholar's semantic (snippet) search, then look up the papers' DOIs.

    ``snippet/search`` ranks passages from title, abstract and body text by meaning, not by
    keyword match, and returns up to 1,000 snippets in one request with no paging. Each
    snippet names its paper by ``corpusId`` only, so a second step maps the unique papers,
    in the order they first appear, to DOIs with ``paper/batch`` (500 ids per call).

    Pages: the snippet response first, then one ``{"batch": [...]}`` page per lookup call,
    each a list aligned with the ids sent. Body-text snippets exist only for open-access
    papers, so this arm leans towards them.

    Args:
        intent: Dataset search text, sent verbatim.
        cutoff: ISO date before which results must have been published.
        get: Rate-limited response getter (also used for the POST lookup).
        api_key: Semantic Scholar key.

    Returns:
        Raw pages and completion metadata.
    """
    request = {
        "query": intent,
        "limit": str(RESULT_CEILING),
        "fields": "snippet.snippetKind",
        "publicationDateOrYear": semantic_scholar_cutoff(cutoff),
    }
    headers = {"x-api-key": api_key}
    response = get(
        "https://api.semanticscholar.org/graph/v1/snippet/search", request, headers
    )
    if response is None or response.status_code != 200:
        return _failure([], request, RESULT_CEILING)
    body = response.json()
    pages: list[dict[str, Any]] = [body]
    unique_ids = list(
        dict.fromkeys(str(hit["paper"]["corpusId"]) for hit in body.get("data", []))
    )
    for start in range(0, len(unique_ids), BATCH_SIZE):
        ids = unique_ids[start : start + BATCH_SIZE]
        lookup = get(
            "https://api.semanticscholar.org/graph/v1/paper/batch",
            {"fields": "externalIds,title"},
            headers,
            json={"ids": [f"CorpusId:{i}" for i in ids]},
        )
        if lookup is None or lookup.status_code != 200:
            return _failure(pages, request, RESULT_CEILING)
        pages.append({"batch": lookup.json(), "ids": ids})
    return Fetched(pages, request, RESULT_CEILING, 0, True, _now())


def fetch_consensus(intent: str, cutoff: str, *, get: Getter, api_key: str) -> Fetched:
    """Fetch Consensus result pages through the 1,000-record ceiling.

    Args:
        intent: Dataset search text, sent verbatim.
        cutoff: ISO date before which results must have been published.
        get: Rate-limited response getter.
        api_key: Consensus key.

    Returns:
        Raw pages and completion metadata.
    """
    pages: list[dict[str, Any]] = []
    page, page_size = 0, 1000
    echoed_first = 1000
    request = {
        "query": intent,
        "page": "0",
        "page_size": "1000",
        **consensus_cutoff(cutoff),
    }
    while True:
        params = {
            "query": intent,
            "page": str(page),
            "page_size": str(page_size),
            **consensus_cutoff(cutoff),
        }
        response = get(
            "https://api.consensus.app/v1/search", params, {"x-api-key": api_key}
        )
        if response is None or response.status_code != 200:
            return _failure(pages, request, echoed_first)
        body = response.json()
        pages.append(body)
        results = body.get("results", [])
        # An empty first page with no echoed size would make a zero page size.
        echoed = int(body.get("page_size") or len(results) or 1)
        if len(pages) == 1:
            page_size = echoed_first = echoed
        # Positions covered so far in the service's ranked list. A page can hold a few
        # results fewer than its size, so count positions, not results.
        covered = (page + 1) * page_size
        if not results or body.get("is_end", False) or covered >= RESULT_CEILING:
            break
        page = int(
            body.get("next_page") if body.get("next_page") is not None else page + 1
        )
        if (page + 1) * page_size > RESULT_CEILING:
            # Consensus rejects a page that would pass 1,000 results with a 400, and
            # sends no next_page at that point. At page size 300 that leaves positions
            # 900-999 unreachable at this size, so the last request asks for exactly the
            # remaining slice at a smaller size: page 9 at size 100 (750 -> page 3 at 250).
            remaining = RESULT_CEILING - covered
            if remaining <= 0 or covered % remaining:
                break
            page, page_size = covered // remaining, remaining
    return Fetched(pages, request, echoed_first, 0, True, _now())


def fetch_openalex_raw(intent: str, cutoff: str, *, get: Getter) -> Fetched:
    """Fetch OpenAlex raw-search pages through the 1,000-record ceiling.

    Args:
        intent: Dataset search text, sent verbatim.
        cutoff: ISO date before which results must have been published.
        get: Rate-limited response getter.

    Returns:
        Raw pages and completion metadata.
    """
    pages: list[dict[str, Any]] = []
    request = {
        "search": intent,
        "select": "id,doi,display_name,publication_date",
        "per-page": "200",
        "page": "1",
        "filter": openalex_cutoff(cutoff),
    }
    for page in range(1, 6):
        params = {**request, "page": str(page)}
        response = get("/works", params, {})
        if response is None or response.status_code != 200:
            return _failure(pages, request, 200)
        body = response.json()
        pages.append(body)
        if len(body.get("results", [])) < 200:
            break
    return Fetched(pages, request, 200, 0, True, _now())


FETCHERS: dict[str, Callable[..., Fetched]] = {
    "semantic-scholar": fetch_semantic_scholar,
    SNIPPET: fetch_semantic_scholar_snippet,
    "consensus": fetch_consensus,
    "openalex-raw": fetch_openalex_raw,
}


def cache_path(arm: str, item_id: str, cache_dir: Path = CACHE_DIR) -> Path:
    """Return the deterministic local cache path for one arm and dataset item."""
    digest = hashlib.sha256(item_id.encode()).hexdigest()[:16]
    return cache_dir / arm / f"{digest}.json"


def write_cache(
    path: Path, *, arm: str, intent: str, cutoff: str, fetched: Fetched
) -> None:
    """Write one raw fetch without storing authentication headers or keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"arm": arm, "intent": intent, "cutoff": cutoff, **asdict(fetched)}
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_cache(path: Path) -> Fetched | None:
    """Read one cached fetch, or return None when it has not been fetched."""
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return Fetched(**{key: value[key] for key in Fetched.__dataclass_fields__})


def load_or_fetch(
    arm: str,
    *,
    item_id: str,
    intent: str,
    cutoff: str,
    refresh: bool = False,
    cache_dir: Path = CACHE_DIR,
    fetcher: Callable[[str, str], Fetched] | None = None,
) -> tuple[Fetched, bool]:
    """Load a complete cache entry or fetch and replace it.

    Args:
        arm: Baseline arm name.
        item_id: Dataset item identity used for the cache filename.
        intent: Dataset search text.
        cutoff: ISO publication cutoff.
        refresh: Whether to bypass a complete cache entry.
        cache_dir: Root directory for cached raw pages.
        fetcher: Optional test or custom fetch function.

    Returns:
        The fetched pages and whether they came from cache.
    """
    path = cache_path(arm, item_id, cache_dir)
    cached = read_cache(path)
    if cached is not None and cached.complete and not refresh:
        return cached, True
    if fetcher is None:
        key_name = KEY_ENV.get(arm)
        if key_name and not os.environ.get(key_name):
            raise SystemExit(f"{key_name} is not set; cannot fetch {arm}")
        getter = make_getter(arm)
        if arm == "openalex-raw":

            def fetcher(search: str, before: str) -> Fetched:
                return fetch_openalex_raw(search, before, get=getter)
        else:
            assert key_name is not None
            key = os.environ[key_name]  # guarded above

            def fetcher(search: str, before: str) -> Fetched:
                return FETCHERS[arm](search, before, get=getter, api_key=key)

    fetched = fetcher(intent, cutoff)
    write_cache(path, arm=arm, intent=intent, cutoff=cutoff, fetched=fetched)
    return fetched, False


def _snippet_records(fetched: Fetched) -> list[dict[str, Any]]:
    """Unique papers in the order their best snippet was ranked, with DOIs from the lookup."""
    externals: dict[str, dict[str, Any]] = {}
    for page in fetched.pages[1:]:
        for corpus_id, paper in zip(
            page.get("ids", []), page.get("batch", []), strict=False
        ):
            if paper:
                externals[str(corpus_id)] = paper
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in fetched.pages[0].get("data", []) if fetched.pages else []:
        corpus_id = str(hit["paper"]["corpusId"])
        if corpus_id in seen:
            continue
        seen.add(corpus_id)
        paper = externals.get(corpus_id, {})
        records.append(
            {
                "doi": (paper.get("externalIds") or {}).get("DOI"),
                "backend": SNIPPET,
                "backend_record_id": corpus_id,
                "title": hit["paper"].get("title"),
            }
        )
    return records


def _page_records(arm: str, page: dict[str, Any]) -> int:
    """How many results one raw page holds (snippets count; id-lookup pages hold none)."""
    if arm == "semantic-scholar" or arm == SNIPPET:
        return len(page.get("data", []))
    return len(page.get("results", []))


def records_of(arm: str, fetched: Fetched) -> list[dict[str, Any]]:
    """Flatten raw service pages into the shared scoring envelope."""
    if arm == SNIPPET:
        return _snippet_records(fetched)
    records: list[dict[str, Any]] = []
    for page in fetched.pages:
        source = (
            page.get("data", [])
            if arm == "semantic-scholar"
            else page.get("results", [])
        )
        for item in source:
            if arm == "semantic-scholar":
                records.append(
                    {
                        "doi": (item.get("externalIds") or {}).get("DOI"),
                        "backend": arm,
                        "backend_record_id": item.get("paperId"),
                        "title": item.get("title"),
                    }
                )
            elif arm == "consensus":
                records.append(
                    {
                        "doi": item.get("doi"),
                        "backend": arm,
                        "backend_record_id": item.get("paper_id"),
                        "title": item.get("title"),
                    }
                )
            else:
                records.append(
                    {
                        "doi": item.get("doi"),
                        "backend": arm,
                        "backend_record_id": item.get("id"),
                        "title": item.get("display_name"),
                    }
                )
            if len(records) >= RESULT_CEILING:
                return records
    return records


def slice_at_cap(records: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Keep the first cap records, then remove duplicate scoring keys."""
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records[:cap]:
        key = record_key(record)
        if key is None or key not in seen:
            kept.append(record)
            if key is not None:
                seen.add(key)
    return kept


def pages_for_cap(fetched: Fetched, cap: int) -> list[dict[str, Any]]:
    """Return only the pages needed to reach an independently fetched cap."""
    return fetched.pages[: min(len(fetched.pages), math.ceil(cap / fetched.page_size))]


def cost_usd(arm: str, pages: list[dict[str, Any]]) -> float:
    """Compute the documented variable API cost for these raw pages."""
    if arm in ("semantic-scholar", SNIPPET):
        return 0.0
    if arm == "consensus":
        total = sum(
            max(1, math.ceil(len(page.get("results", [])) / CONSENSUS_PAPERS_PER_CALL))
            * CONSENSUS_USD_PER_CALL
            for page in pages
        )
    else:
        total = sum(float(page.get("meta", {}).get("cost_usd", 0.0)) for page in pages)
    return round(total, 4)


def score_arm(
    arm: str, fetched: Fetched, ground_truth: GroundTruth, cap: int
) -> dict[str, Any]:
    """Score one cached arm at one candidate cap against a review's target."""
    # The snippet arm is one search plus its id lookups; every cap needs all of them.
    pages = fetched.pages if arm == SNIPPET else pages_for_cap(fetched, cap)
    sliced = slice_at_cap(records_of(arm, fetched), cap)
    found = {
        key for record in sliced if (key := record_key(record)) is not None
    } & ground_truth.keys
    n_records = sum(_page_records(arm, page) for page in pages)
    return {
        "search_recall": len(found) / len(ground_truth.keys)
        if ground_truth.keys
        else 0.0,
        "n_found": len(found),
        "n_api_calls": len(pages),
        "n_failed_calls": fetched.n_failed_calls,
        "n_api_records": n_records,
        "n_candidates_kept": len(sliced),
        "api_cost_usd": cost_usd(arm, pages),
        "n_ground_truth": len(ground_truth.keys),
    }


def score_baseline(*, output: dict[str, Any], **_: Any) -> list[Evaluation]:
    """Lift baseline output values into Langfuse per-review evaluations."""
    return [
        Evaluation(name=key, value=output[key])
        for key in BASELINE_SCORE_KEYS
        if key in output
    ]


def _usd(value: float) -> str:
    """Dollars to two decimals, or four when the amount would otherwise show as $0.00."""
    return f"${value:.2f}" if value == 0 or value >= 0.01 else f"${value:.4f}"


def _describe(title: str, score: dict[str, Any]) -> str:
    failed = (
        f", {score['n_failed_calls']} REQUESTS FAILED — recall is an undercount"
        if score["n_failed_calls"]
        else ""
    )
    return f"  {title[:60]}: search_recall={score['search_recall']:.0%} ({score['n_found']}/{score['n_ground_truth']}); kept={score['n_candidates_kept']}, requests={score['n_api_calls']}, cost={_usd(score['api_cost_usd'])}{failed}"


def run_baseline(
    client: Any,
    dataset: Any,
    items: list[Any],
    *,
    arm: str,
    cap: int,
    label: str,
    git_commit: str,
    cache_dir: Path,
    dry_run: bool,
) -> dict[str, Any]:
    """Score and optionally upload one arm/cap dataset run from the local cache."""
    fetched_values = [
        read_cache(cache_path(arm, str(item.id), cache_dir)) for item in items
    ]
    if any(value is None for value in fetched_values):
        raise RuntimeError(f"missing cache entries for {arm}")
    fetched_at = min(value.fetched_at for value in fetched_values if value is not None)
    meta = {
        key: str(value)
        for key, value in {
            "experiment": EXPERIMENT,
            "depth": "single-call",
            "generation_backend": arm,
            "record_cap_per_backend": cap,
            "git_commit": git_commit,
            "fetched_at": fetched_at,
        }.items()
    }
    outputs: list[dict[str, Any]] = []

    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        fetched = read_cache(cache_path(arm, str(item.id), cache_dir))
        assert fetched is not None
        score = score_arm(arm, fetched, _ground_truth_from_item(item), cap)
        outputs.append(score)
        print(_describe(item.metadata.get("review_title", str(item.id)), score))
        return score

    if dry_run:
        for item in items:
            task(item=item)
        url = "dry-run"
    else:

        def attributed_task(*, item: Any, **_: Any) -> dict[str, Any]:
            with propagate_attributes(metadata=meta):
                return task(item=item)

        result = client.run_experiment(
            name=EXPERIMENT,
            run_name=f"{label}/{arm}-cap{cap}",
            data=items,
            task=attributed_task,
            evaluators=[score_baseline],
            metadata=meta,
            max_concurrency=1,
            _dataset_version=dataset.version,
        )
        url = result.dataset_run_url
    return {
        "arm": arm,
        "cap": cap,
        "mean_recall": sum(s["search_recall"] for s in outputs) / len(outputs)
        if outputs
        else 0.0,
        "kept": sum(s["n_candidates_kept"] for s in outputs),
        "requests": sum(s["n_api_calls"] for s in outputs),
        "failed": sum(s["n_failed_calls"] for s in outputs),
        "cost": sum(s["api_cost_usd"] for s in outputs),
        "fetched_at": fetched_at,
        "url": url,
    }


def main() -> None:
    """Fetch baselines once, then score selected record caps from the cache."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Langfuse dataset (default {DEFAULT_DATASET}).",
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=ARMS,
        default=ARMS,
        help="Services to run (default: all three).",
    )
    parser.add_argument(
        "--caps",
        nargs="+",
        type=int,
        default=DEFAULT_CAPS,
        help="Result caps to score, one Langfuse run per arm and cap (default: 50 100 200 1000).",
    )
    parser.add_argument(
        "--reviews",
        nargs="+",
        default=None,
        metavar="TEXT",
        help="Only reviews whose id or title contains one of these texts (default: every review).",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Prefix for the run names, <label>/<arm>-cap<cap> (default: today's date plus the "
        "short git commit).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the cache and call the services again (Consensus calls cost money).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch or load, score and print, but upload nothing to Langfuse.",
    )
    args = parser.parse_args()
    git_commit = _git_commit()
    os.environ.setdefault("LANGFUSE_RELEASE", git_commit)
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    dataset = client.get_dataset(args.dataset)
    try:
        items = select_items(dataset.items, args.reviews)
    except ValueError as exc:
        parser.error(str(exc))
    label = args.run_label or f"{date.today().isoformat()}-{git_commit[:7]}"
    ceilings = {
        "semantic-scholar": "at most 10 requests per review, free",
        SNIPPET: "3 requests per review (one search, two id lookups), free",
        "openalex-raw": "at most 5 requests per review, free",
        "consensus": "at most 10 calls per review at $0.05 per call, billed on every call",
    }
    for arm in args.arms:
        needed = sum(
            cached is None or not cached.complete or args.refresh
            for item in items
            for cached in [read_cache(cache_path(arm, str(item.id)))]
        )
        print(f"{arm}: {needed} review(s) need a fetch; {ceilings[arm]}")
    for arm in args.arms:
        for item in items:
            started = time.monotonic()
            fetched, from_cache = load_or_fetch(
                arm,
                item_id=str(item.id),
                intent=item.input["intent"],
                cutoff=item.input["published_before"],
                refresh=args.refresh,
            )
            if not from_cache:
                count = len(records_of(arm, fetched))
                print(
                    f"  {arm} {item.id}: {len(fetched.pages)} pages, {count} results, {fetched.n_failed_calls} failed requests, {time.monotonic() - started:.1f}s"
                )
    rows = [
        run_baseline(
            client,
            dataset,
            items,
            arm=arm,
            cap=cap,
            label=label,
            git_commit=git_commit,
            cache_dir=CACHE_DIR,
            dry_run=args.dry_run,
        )
        for arm in args.arms
        for cap in args.caps
    ]
    print(
        f"{'arm':<18}{'cap':>6}{'mean recall':>14}{'kept':>8}{'requests':>11}{'failed':>8}{'api cost':>11}  fetched_at  run"
    )
    for row in rows:
        print(
            f"{row['arm']:<18}{row['cap']:>6}{row['mean_recall']:>14.1%}{row['kept']:>8}{row['requests']:>11}{row['failed']:>8}{_usd(row['cost']):>11}  {row['fetched_at']}  {row['url']}"
        )
    tracing.flush(client)


if __name__ == "__main__":
    main()
