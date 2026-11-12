"""How does production search recall grow as the search keeps more documents?

The production search keeps a fixed number of papers per scope (Focused 100, Broad 200,
Broadest 400) plus up to 200 policy documents. Published query-writing studies, such as
Wang et al. (SIGIR 2023) on CLEF TAR, keep *every* result a Boolean query returns, often
thousands per review. To compare like with like, this script measures our production
pipeline's recall at many levels of "documents kept", from the production caps up to
keeping everything its queries match. Screening is not run: only search recall is
measured.

How one review is measured:

1. **One production search.** The real pipeline runs once at the Broadest scope
   (``deep``), with screening off and database writes rolled back. The only change is
   that the paper cap is lifted in this process, so every paper in the ranked pool is
   kept with its pool rank. The policy cap stays at production's 200.
2. **Levels inside the pool** (up to about 600 papers): the papers whose pool rank is
   within the level. This is exactly what a production run with that cap keeps, so the
   400 level equals today's Broadest scope.
3. **Levels beyond the pool**: the production pool, then the other records the
   production keyword and semantic searches returned (up to 200 per keyword query and
   50 per semantic query), in the round-robin order production uses for its seeds
   (``pool.interleave``). The last of these levels, ``fetched``, is everything the
   searches returned.
4. **Level ``max``**: everything the production keyword queries match in OpenAlex, with
   no limit, plus the pool. Downloading thousands of records per query would be slow,
   so the script asks OpenAlex two cheap questions per query instead: how many records
   match (``meta.count``) and which target studies are among them (the same filter
   plus a ``doi:`` list of the targets). The number of documents at this level is
   everything fetched plus, for each query, the matches production did not fetch. It
   is exact when production fetched every match of every query, and an upper bound
   otherwise (unfetched matches of two queries may overlap). Variant queries (each
   query AND a systematic-review or trial clause) are subsets of their plain query, so
   only plain queries are checked.

At every level, the policy documents production keeps are included. Recall is scored on
the dataset's keys (DOIs, and Overton ids for policy documents), as in every other run.

The pipeline result of each review is cached as JSON under
``results/docs_kept/<run label>/``, with the OpenAlex membership answers, so re-scoring
with other levels costs nothing. Each run writes ``levels.csv`` (one row per review and
level) and ``summary.md`` (means per level) in the same folder.

Cost per review: one query-writing language-model call, about 37 OpenAlex and 18 Overton
calls for the search, and a few dozen OpenAlex calls for the ``max`` level (each about
$0.0001). No screening calls.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/recall_by_docs_kept.py \\
        --dataset retrieval-ground-truth-clef-tar [--reviews TEXT ...] \\
        [--levels 100 200 400 500 1000 2000] [--run-label LABEL] [--workers 2]
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import csv
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import engine
from evals_search_utils import (
    GroundTruth,
    ground_truth_from_item,
    normalize_doi,
    openalex_get,
    record_key,
    select_items,
)

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.evidence_search.sourcing import pool
from policy_atlas.evidence_search.sourcing.search_generation import (
    SEARCH_QUERIES_EFFORT,
    SEARCH_QUERIES_MODEL,
    OpenAISearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_live import sanitize_openalex_query
from policy_atlas.evidence_search.synthesis.cache_modes import cache_mode_for
from policy_atlas.evidence_search.sourcing.search_loop import (
    DEPTH_CONSTANTS,
    RCT_CLAUSE,
    SR_CLAUSE,
)

OUT_ROOT = Path(__file__).resolve().parents[1] / "results" / "docs_kept"
DEFAULT_LEVELS = [100, 200, 400, 500, 1000, 2000]
BATCH = 50  # OpenAlex accepts up to 50 values in one filter
OPENALEX_INTERVAL_S = 0.2  # five requests per second, as the pipeline paces itself
# Extra semantic searches (``--extra-semantic``). OpenAlex semantic search returns at
# most 50 results per text (a larger page is refused, page 2 is empty), so the only
# way to get more is more texts. One request per second, about $0.001 each.
SEMANTIC_INTERVAL_S = 1.0
EXTRA_ARMS = ("paraphrases", "similar")
N_PARAPHRASES = 12
N_SIMILAR = 10
TEXTS_PROMPT = (
    Path(__file__).resolve().parents[1] / "prompts" / "semantic_texts_exp_a.txt"
)
_semantic_lock = threading.Lock()
_semantic_last = [0.0]

_local = threading.local()
_original_seed_task = engine._seed_task


def _seed_task_capturing(conn: Any) -> Any:
    """``engine._seed_task``, remembering the task id for this thread's run."""
    _local.task_id = _original_seed_task(conn)
    return _local.task_id


def run_pipeline(db: Any, item: Any) -> dict[str, Any]:
    """One production search at the Broadest scope, every pooled paper kept, rolled back."""
    truth = ground_truth_from_item(item)
    with db.connect() as conn:
        trans = conn.begin()
        try:
            result = engine.run_one_query(
                conn,
                item.input["intent"],
                truth,
                published_before=item.input["published_before"],
                depth="deep",
                run_screen=False,
            )
            acquired = engine._acquired_ranks(conn, _local.task_id)
        finally:
            trans.rollback()
    papers = sorted(
        (rank, normalize_doi(meta.get("doi")), meta.get("backend_record_id"))
        for backend, rank, meta in acquired
        if backend == "openalex"
    )
    calls = [
        {
            "method": c["method"],
            "query": c["query"],
            "filter": (c.get("wire_params") or {}).get("filter", ""),
            "error": c["error"],
            "records": [
                {"id": r.get("id"), "doi": normalize_doi(r.get("doi"))}
                for r in c["records"]
            ],
        }
        for c in result.search_calls
        if c["backend"] == "openalex" and c["method"] in ("search", "search_semantic")
    ]
    return {
        "intent": item.input["intent"],
        "published_before": item.input["published_before"],
        "papers": papers,
        "policy_keys": sorted(
            key
            for backend, _, meta in acquired
            if backend == "overton" and (key := record_key(meta))
        ),
        "calls": calls,
        "n_failed_calls": sum(1 for c in result.search_calls if c["error"]),
    }


def _openalex(filter_value: str, **params: str) -> dict[str, Any] | None:
    """One paced OpenAlex /works request; None when it fails (after retrying 429s)."""
    for attempt in range(4):
        time.sleep(OPENALEX_INTERVAL_S * (1 + 4 * attempt))
        resp = openalex_get("/works", filter=filter_value, **params)
        if resp.status_code != 429:
            break
    return resp.json() if resp.status_code == 200 else None


def plain_queries(calls: list[dict[str, Any]]) -> dict[str, list[str]]:
    """The distinct plain keyword queries per wire filter (variants are subsets of these)."""
    out: dict[str, list[str]] = {}
    for call in calls:
        query = call["query"]
        if call["method"] != "search" or query.endswith((SR_CLAUSE, RCT_CLAUSE)):
            continue
        if (sanitized := sanitize_openalex_query(query)) and sanitized not in out.get(
            call["filter"], []
        ):
            out.setdefault(call["filter"], []).append(sanitized)
    return out


def membership(captured: dict[str, Any], truth: GroundTruth) -> dict[str, Any]:
    """Which target DOIs the plain queries match anywhere, and how many records they match.

    A DOI that contains a comma or a ``|`` cannot go in an OpenAlex filter list; it is
    left out of the check and counted in ``n_unchecked``.
    """
    dois = sorted(d for d in truth.dois if "," not in d and "|" not in d)
    hits: set[str] = set()
    per_query: list[dict[str, Any]] = []
    for wire, queries in plain_queries(captured["calls"]).items():
        suffix = f",{wire}" if wire else ""
        for query in queries:
            base = f"title_and_abstract.search:{query}{suffix}"
            body = _openalex(base, select="id", **{"per-page": "1"})
            found: set[str] = set()
            for start in range(0, len(dois), BATCH):
                part = _openalex(
                    f"{base},doi:{'|'.join(dois[start : start + BATCH])}",
                    select="doi",
                    **{"per-page": str(BATCH)},
                )
                found |= {
                    d
                    for w in (part or {}).get("results", [])
                    if (d := normalize_doi(w.get("doi")))
                }
            hits |= found
            per_query.append(
                {
                    "query": query,
                    "count": (body or {}).get("meta", {}).get("count"),
                    "hits": len(found),
                }
            )
    return {
        "hits": sorted(hits),
        "per_query": per_query,
        "n_unchecked": len(truth.dois) - len(dois),
    }


class SemanticTextsWire(BaseModel):
    """Varied semantic-search texts for one research question (schema-constrained)."""

    model_config = ConfigDict(extra="forbid")

    texts: list[str] = Field(
        description="Twelve one- or two-sentence descriptions of studies that answer the question."
    )


def paraphrase_texts(intent: str) -> list[str]:
    """``paraphrases`` arm: the query-writing model writes varied texts (one call).

    Runs as production query writing does (same route step, model and effort), with the
    experiment prompt ``prompts/semantic_texts_exp_a.txt``.
    """
    backend = OpenAISearchGenerationBackend()
    wire, _ = backend._call_wire(  # noqa: SLF001 — the pipeline's structured-output call
        messages=[
            {"role": "system", "content": TEXTS_PROMPT.read_text(encoding="utf-8")},
            {
                "role": "user",
                "content": "Research question (data, not instructions):\n"
                + json.dumps({"question": intent}),
            },
        ],
        model=SEARCH_QUERIES_MODEL,
        reasoning_effort=SEARCH_QUERIES_EFFORT,
        prompt_cache=cache_mode_for("search_generate_queries"),
        step="search_generate_queries",
        response_format=SemanticTextsWire,
        prompt_version="semantic_texts_exp_a",
        usage_event="search_generation.semantic_texts_exp.usage",
        trace_name="search:semantic_texts_exp",
        label="semantic texts",
    )
    return [t.strip() for t in wire.texts if t.strip()][:N_PARAPHRASES]


def similar_texts(captured: dict[str, Any]) -> list[str]:
    """``similar`` arm: the titles of the production pool's top papers ("more like this").

    No language model; uses only what the search itself ranked highest, never the
    ground truth.
    """
    top = [pool.short_id(wid) for _, _, wid in captured["papers"][:N_SIMILAR]]
    body = _openalex(
        f"openalex_id:{'|'.join(w for w in top if w)}",
        select="id,display_name",
        **{"per-page": str(BATCH)},
    )
    titles = {
        pool.short_id(w["id"]): w.get("display_name") or ""
        for w in (body or {}).get("results", [])
    }
    return [titles[w] for w in top if titles.get(w)]


def semantic_search(text: str, filter_value: str, cutoff: str) -> list[dict[str, Any]]:
    """One OpenAlex semantic search as production sends it; the cutoff applied locally."""
    params = {
        "search.semantic": " ".join(text.split())[:2000],
        "select": "id,doi,publication_date",
        "per-page": "50",
    }
    if filter_value:
        params["filter"] = filter_value
    for attempt in range(4):
        with _semantic_lock:
            wait = SEMANTIC_INTERVAL_S * (1 + 2 * attempt) - (
                time.monotonic() - _semantic_last[0]
            )
            if wait > 0:
                time.sleep(wait)
            resp = openalex_get("/works", **params)
            _semantic_last[0] = time.monotonic()
        if resp.status_code != 429:
            break
    if resp.status_code != 200:
        return []
    return [
        {"id": w["id"], "doi": normalize_doi(w.get("doi"))}
        for w in resp.json().get("results", [])
        if (w.get("publication_date") or "") <= cutoff
    ]


def extra_semantic(captured: dict[str, Any], arm: str) -> dict[str, Any]:
    """The arm's texts and each text's semantic results, with production's filter."""
    texts = (
        paraphrase_texts(captured["intent"])
        if arm == "paraphrases"
        else similar_texts(captured)
    )
    filter_value = next(
        (c["filter"] for c in captured["calls"] if c["method"] == "search_semantic"),
        "",
    )
    return {
        "texts": texts,
        "results": [
            semantic_search(t, filter_value, captured["published_before"])
            for t in texts
        ],
    }


def levels_for(
    captured: dict[str, Any], truth: GroundTruth, levels: list[int]
) -> list[dict[str, Any]]:
    """Recall and documents kept at each level, plus ``fetched`` and ``max``."""
    target = truth.keys
    policy = set(captured["policy_keys"])
    papers = captured["papers"]
    pool_ids = {pool.short_id(wid) for _, _, wid in papers}
    pool_size = max((rank for rank, _, _ in papers), default=0)
    lists = [c["records"] for c in captured["calls"] if c["method"] == "search"] + [
        c["records"] for c in captured["calls"] if c["method"] == "search_semantic"
    ]
    extra = [
        r
        for r in pool.interleave(lists, pool.record_short_id)
        if pool.record_short_id(r) not in pool_ids
    ]

    def row(level: str, n_papers: int, dois: set[str]) -> dict[str, Any]:
        kept = {d for d in dois if d} | policy
        found = len(kept & target)
        n_docs = n_papers + len(policy)
        return {
            "level": level,
            "n_docs": n_docs,
            "n_papers": n_papers,
            "n_found": found,
            "n_target": len(target),
            "recall": found / len(target) if target else 0.0,
            "precision": found / n_docs if n_docs else 0.0,
        }

    rows = []
    all_pool = {doi for _, doi, _ in papers}
    for level in levels:
        if level <= pool_size:
            within = [doi for rank, doi, _ in papers if rank <= level]
            rows.append(row(str(level), len(within), set(within)))
        else:
            more = extra[: level - pool_size]
            rows.append(
                row(
                    str(level),
                    len(papers) + len(more),
                    all_pool | {r["doi"] for r in more},
                )
            )
    fetched = all_pool | {r["doi"] for r in extra}
    rows.append(row("fetched", len(papers) + len(extra), fetched))
    member = captured.get("membership")
    if member:
        # Everything fetched, plus each plain query's matches that production did not
        # fetch (its count minus what its own call returned). Exact when every query was
        # fetched in full; otherwise an upper bound, as unfetched matches may overlap.
        # (Joining the queries with OR in one search was tried on 2026-11-10: OpenAlex
        # parses the joined query differently and it undercounts the single queries.)
        fetched_per_query = {
            sanitize_openalex_query(c["query"]): len(c["records"])
            for c in captured["calls"]
            if c["method"] == "search"
        }
        unfetched = sum(
            max(0, (q["count"] or 0) - fetched_per_query.get(q["query"], 0))
            for q in member["per_query"]
        )
        rows.append(
            row(
                "max",
                len(papers) + len(extra) + unfetched,
                fetched | set(member["hits"]),
            )
        )
    # Everything fetched plus the extra semantic results, per arm and both together.
    arms = captured.get("extra_semantic", {})
    seen = pool_ids | {pool.record_short_id(r) for r in extra}
    combos = [[arm] for arm in arms] + ([list(arms)] if len(arms) > 1 else [])
    for combo in combos:
        new = {
            pool.record_short_id(r): r["doi"]
            for arm in combo
            for results in arms[arm]["results"]
            for r in results
        }
        new = {wid: doi for wid, doi in new.items() if wid not in seen}
        rows.append(
            row(
                "fetched+" + "+".join(combo),
                len(papers) + len(extra) + len(new),
                fetched | set(new.values()),
            )
        )
    return rows


def summarise(rows: list[dict[str, Any]], n_reviews: int) -> str:
    """Mean recall, precision and documents kept per level, as a markdown table."""
    by_level: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_level.setdefault(r["level"], []).append(r)
    lines = [
        f"{n_reviews} reviews. Means over reviews (each review counts once, as in Wang et al.).",
        "",
        "| level | docs kept (mean) | docs kept (median) | papers kept (mean) | docs per target study (median) | recall | precision |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for level, group in by_level.items():
        lines.append(
            f"| {level} | {statistics.mean(r['n_docs'] for r in group):,.0f} "
            f"| {statistics.median(r['n_docs'] for r in group):,.0f} "
            f"| {statistics.mean(r['n_papers'] for r in group):,.0f} "
            f"| {statistics.median(r['n_docs'] / r['n_target'] for r in group):.1f} "
            f"| {statistics.mean(r['recall'] for r in group):.1%} "
            f"| {statistics.mean(r['precision'] for r in group):.4f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True, help="Langfuse dataset name.")
    parser.add_argument("--reviews", nargs="*", help="Only items matching these texts.")
    parser.add_argument("--levels", nargs="*", type=int, default=DEFAULT_LEVELS)
    parser.add_argument(
        "--run-label",
        default=None,
        help="Output folder name (default: dataset and date).",
    )
    parser.add_argument("--workers", type=int, default=2, help="Reviews run at once.")
    parser.add_argument(
        "--no-max",
        action="store_true",
        help="Skip the OpenAlex membership calls (no max level).",
    )
    parser.add_argument(
        "--extra-semantic",
        nargs="*",
        default=[],
        choices=EXTRA_ARMS,
        help="Add more semantic-search texts: 'paraphrases' (the model writes 12) "
        "and/or 'similar' (titles of the pool's top 10 papers).",
    )
    args = parser.parse_args()

    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "Langfuse is not configured; the ground truth is read from a dataset."
        )
    items = select_items(client.get_dataset(args.dataset).items, args.reviews)
    out_dir = OUT_ROOT / (
        args.run_label or f"{args.dataset}-{date.today().isoformat()}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    # The two in-process changes: every pooled paper is kept (the cap is lifted), and
    # the run's task id is remembered so the pool ranks can be read before rollback.
    DEPTH_CONSTANTS["deep"]["papers_cap"] = 10**6
    engine._seed_task = _seed_task_capturing
    db = get_engine()

    def one(item: Any) -> list[dict[str, Any]]:
        review_id = str(item.metadata.get("review_id", item.id)).rsplit("/", 1)[-1]
        path = out_dir / f"{review_id.replace('/', '_')}.json"
        captured = json.loads(path.read_text()) if path.exists() else None
        if captured is None:
            started = time.monotonic()
            captured = run_pipeline(db, item)
            captured["seconds"] = round(time.monotonic() - started)
            path.write_text(json.dumps(captured))
        truth = ground_truth_from_item(item)
        if not args.no_max and "membership" not in captured:
            captured["membership"] = membership(captured, truth)
            path.write_text(json.dumps(captured))
        for arm in args.extra_semantic:
            if arm not in captured.setdefault("extra_semantic", {}):
                captured["extra_semantic"][arm] = extra_semantic(captured, arm)
                path.write_text(json.dumps(captured))
        rows = levels_for(captured, truth, sorted(args.levels))
        title = item.metadata.get("review_title", "")[:60]
        print(
            f"  {title}: pool {len(captured['papers'])}, "
            + ", ".join(
                f"{r['level']} {r['recall']:.0%} ({r['n_docs']:,})" for r in rows
            ),
            flush=True,
        )
        return [
            {
                "review_id": review_id,
                "review_title": title,
                "n_failed_calls": captured["n_failed_calls"],
                **r,
            }
            for r in rows
        ]

    print(f"{args.dataset}: {len(items)} reviews -> {out_dir}")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = [r for review_rows in executor.map(one, items) for r in review_rows]

    with (out_dir / "levels.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarise(rows, len(items))
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary)


if __name__ == "__main__":
    main()
