"""Overton recall probes (R&D, task 049).

Overton indexes policy documents, and the current ground truth is a list of paper DOIs
(the product wants both; the ground truth measures the paper side only). So a policy
document can be a hit only when it carries a DOI of its own (about 5% do; those are
counted first). Two Overton routes reach *papers*, and this script measures both, one
plain request per review, no language model:

- ``articles``: Overton's scholarly-article search (``articles.php``), a keyword search
  over the papers that policy documents cite. Returns DOIs directly, with ``citations``
  (how many policy documents cite the paper). Sorted by relevance, and again by policy
  citations (``articles-cited``).
- ``docs-cites``: Overton's policy-document semantic search (``documents.php``,
  ``squery``), then the union of the papers those documents cite (``cites.scholarly``,
  DOIs), ranked by how many of the retrieved documents cite each paper ("in-set
  citations", the same idea as the OpenAlex snowball). Run with ``sort=relevance`` and
  again with Overton's default ``sort=date`` (``docs-cites-date``), which is what the
  pipeline's Overton calls get today because they send no ``sort``.

Both take the review's cutoff as ``published_before``. Results are cached under
``results/cache/overton-<arm>/`` so a second run makes no requests. Overton is a flat
subscription with a one-call-per-second limit. Uploads nothing to Langfuse.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/overton_recall.py \\
        [--dataset retrieval-ground-truth-mini] [--caps 50 100 200 400] \\
        [--docs 100] [--reviews TEXT ...] [--refresh]
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR, openalex_query
from evals_search_utils import (
    DEFAULT_DATASET,
    GroundTruth,
    ground_truth_from_item,
    normalize_doi,
    select_items,
)
from snowball_recall import generated_queries, override_prompt

import argparse
import collections
import csv
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from policy_atlas.core import tracing

HOST = "https://app.overton.io"
PAGE = 50
INTERVAL_S = 1.3
OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "overton"
_last_call = 0.0


def get(path: str, **params: str) -> dict[str, Any]:
    """One paced Overton call; retries once on 429 or a 5xx."""
    global _last_call
    for attempt in range(3):
        wait = INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            response = httpx.get(
                f"{HOST}/{path}",
                params={
                    "format": "json",
                    "api_key": os.environ["OVERTON_API_KEY"],
                    **params,
                },
                timeout=90.0,
            )
        except httpx.TransportError:  # dropped connection, truncated body, timeout
            if attempt == 2:
                raise
            time.sleep(2.0 * (attempt + 1))
            continue
        if response.status_code == 200:
            return response.json()
        if attempt == 2:
            response.raise_for_status()
        time.sleep(2.0 * (attempt + 1))
    raise AssertionError("unreachable")


def pages(path: str, n: int, **params: str) -> list[dict[str, Any]]:
    """Up to ``n`` records from ``path``, following ``page=`` ourselves."""
    out: list[dict[str, Any]] = []
    for page in range(1, (n + PAGE - 1) // PAGE + 1):
        body = get(path, pp=str(PAGE), page=str(page), **params)
        results = body["results"]
        if isinstance(results, dict):  # articles.php nests the list one level down
            results = results["results"]
        out.extend(results)
        if len(results) < PAGE:
            break
    return out[:n]


CACHE_VERSION = "v2"  # 2026-10-08: payloads carry slim docs and cited_without_doi


def cache_file(arm: str, item_id: str, shape: str) -> Path:
    """One cache file per arm, review and request shape (document counts, texts, version).

    Files written before the shape was part of the name (all made with the defaults,
    100 documents and 200 articles) are renamed on first use rather than refetched.
    """
    folder = CACHE_DIR / f"overton-{arm}"
    new = folder / f"{item_id}-{hashlib.sha256(shape.encode()).hexdigest()[:10]}.json"
    old = folder / f"{item_id}.json"
    if old.exists() and not new.exists():
        old.rename(new)
    return new


def cached(
    arm: str, item_id: str, build: Any, refresh: bool, shape: str
) -> dict[str, Any]:
    path = cache_file(arm, item_id, shape)
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    payload = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload


def fetch_articles(intent: str, cutoff: str, *, sort: str, n: int) -> dict[str, Any]:
    records = pages(
        "articles.php",
        n,
        query=openalex_query(intent),
        published_before=cutoff,
        sort=sort,
    )
    return {
        "dois": [normalize_doi(r.get("doi")) for r in records],
        "policy_citations": [r.get("citations") for r in records],
        "titles": [r.get("title") for r in records],
    }


def generated_texts(intent: str) -> dict[str, list[str]]:
    """The pipeline's generated texts for an intent, from the task-047 cache.

    ``paraphrases`` are the two natural-language rewrites the production prompt writes
    for Overton; ``queries`` the five keyword queries written for OpenAlex. Cached per
    prompt hash and model by ``snowball_recall.generated_queries``; a cache miss costs
    one language-model call.
    """
    payload = generated_queries(
        intent,
        source="shared+semantic",
        prompt_sha=override_prompt("shared+semantic", None),
        refresh=False,
    )
    return {"paraphrases": payload["paraphrases"], "queries": payload["queries"]}


def fetch_docs_cites(
    texts: list[str], cutoff: str, *, sort: str, per_text: int, keep: int
) -> dict[str, Any]:
    """Policy documents for each text, merged round-robin, then the papers they cite.

    One text with ``per_text == keep`` is the plain single-search route. Several texts
    are merged as acquire merges calls: the first result of each, then the second, and
    so on, duplicates (same ``policy_document_id``) skipped, the first ``keep`` kept.
    """
    per_text_docs = [
        pages(
            "documents.php",
            per_text,
            squery=text,
            min_similarity="0.3",
            published_before=cutoff,
            sort=sort,
        )
        for text in texts
    ]
    docs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position in range(max(len(d) for d in per_text_docs)):
        for result in per_text_docs:
            if position < len(result):
                doc = result[position]
                if doc.get("policy_document_id") not in seen_ids:
                    seen_ids.add(doc.get("policy_document_id"))
                    docs.append(doc)
    docs = docs[:keep]
    counts: collections.Counter[str] = collections.Counter()
    titles: dict[str, str] = {}
    cited_without_doi: list[str] = []  # titles only; for title matching
    for doc in docs:
        seen: set[str] = set()
        for work in (doc.get("cites") or {}).get("scholarly") or []:
            doi = normalize_doi(work.get("doi"))
            if not doi:
                if work.get("title"):
                    cited_without_doi.append(work["title"])
                continue
            if doi not in seen:
                seen.add(doi)
                counts[doi] += 1
                titles.setdefault(doi, work.get("title") or "")
    ranked = [doi for doi, _ in counts.most_common()]  # ties keep first-seen order
    return {
        "texts": texts,
        "n_docs": len(docs),
        "n_docs_citing": sum(
            1 for d in docs if (d.get("cites") or {}).get("scholarly")
        ),
        "dois": ranked,
        "inset": [counts[d] for d in ranked],
        "titles": [titles[d] for d in ranked],
        "doc_titles": [d.get("title") for d in docs],
        # Slim copy of each policy document (2026-10-07): its own DOI when it has
        # one (``keyed_other_identifiers``), title and date, for seed scoring and
        # for title matching of references without a DOI.
        "docs": [slim_doc(d) for d in docs],
        "cited_without_doi": cited_without_doi,
    }


def slim_doc(doc: dict[str, Any]) -> dict[str, Any]:
    koi = doc.get("keyed_other_identifiers")
    doi = (
        normalize_doi((koi.get("doi") or [None])[0]) if isinstance(koi, dict) else None
    )
    return {
        "id": doc.get("policy_document_id"),
        "doi": doi,
        "title": doc.get("title"),
        "translated_title": doc.get("translated_title") or None,
        "published_on": doc.get("published_on"),
        "document_url": doc.get("document_url"),
        "source_type": (doc.get("source") or {}).get("type"),
    }


def recall(dois: list[str], gt: GroundTruth, cap: int | None) -> tuple[int, float]:
    found = {d for d in (dois if cap is None else dois[:cap]) if d} & gt.keys
    return len(found), (len(found) / len(gt.keys) if gt.keys else 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=DEFAULT_DATASET + "-mini")
    parser.add_argument("--caps", nargs="+", type=int, default=[50, 100, 200, 400])
    parser.add_argument(
        "--docs", type=int, default=100, help="policy documents per review"
    )
    parser.add_argument("--articles", type=int, default=200, help="articles per review")
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument(
        "--arms", nargs="+", default=None, help="arms to run (default all)"
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST"
        )
    items = select_items(client.get_dataset(args.dataset).items, args.reviews)

    # Each arm: (fetch, request shape). The shape goes into the cache file name so a
    # run with other counts cannot be served a stale file (Codex review, 2026-10-08).
    arms = {
        "articles": (
            lambda i, c: fetch_articles(i, c, sort="relevance", n=args.articles),
            f"articles|relevance|n{args.articles}|{CACHE_VERSION}",
        ),
        "articles-cited": (
            lambda i, c: fetch_articles(i, c, sort="citations", n=args.articles),
            f"articles|citations|n{args.articles}|{CACHE_VERSION}",
        ),
        "docs-cites": (
            lambda i, c: fetch_docs_cites(
                [i], c, sort="relevance", per_text=args.docs, keep=args.docs
            ),
            f"docs|intent|relevance|d{args.docs}|{CACHE_VERSION}",
        ),
        "docs-cites-date": (
            lambda i, c: fetch_docs_cites(
                [i], c, sort="date", per_text=args.docs, keep=args.docs
            ),
            f"docs|intent|date|d{args.docs}|{CACHE_VERSION}",
        ),
        # Seed-set variants (2026-10-07): more documents, and the pipeline's generated
        # texts as extra searches, to see whether policy in-set counts rise above one.
        "docs-cites-200": (
            lambda i, c: fetch_docs_cites(
                [i], c, sort="relevance", per_text=200, keep=200
            ),
            f"docs|intent|relevance|d200|{CACHE_VERSION}",
        ),
        "docs-cites-para-200": (
            lambda i, c: fetch_docs_cites(
                [i, *generated_texts(i)["paraphrases"]],
                c,
                sort="relevance",
                per_text=100,
                keep=200,
            ),
            f"docs|intent+para|relevance|p100|k200|{CACHE_VERSION}",
        ),
        "docs-cites-all-200": (
            lambda i, c: fetch_docs_cites(
                [i, *generated_texts(i)["paraphrases"], *generated_texts(i)["queries"]],
                c,
                sort="relevance",
                per_text=50,
                keep=200,
            ),
            f"docs|all8|relevance|p50|k200|{CACHE_VERSION}",
        ),
        "docs-cites-all-400": (
            lambda i, c: fetch_docs_cites(
                [i, *generated_texts(i)["paraphrases"], *generated_texts(i)["queries"]],
                c,
                sort="relevance",
                per_text=100,
                keep=400,
            ),
            f"docs|all8|relevance|p100|k400|{CACHE_VERSION}",
        ),
    }
    if args.arms:
        arms = {name: arms[name] for name in args.arms}
    hit_counts: dict[str, collections.Counter[int]] = collections.defaultdict(
        collections.Counter
    )
    rows: list[dict[str, Any]] = []
    for item in items:
        intent, cutoff = item.input["intent"], item.input["published_before"]
        gt = ground_truth_from_item(item)
        title = item.metadata.get("review_title", str(item.id))
        for arm, (fetch, shape) in arms.items():
            payload = cached(
                arm,
                str(item.id),
                lambda: fetch(intent, cutoff),  # noqa: B023
                args.refresh,
                shape,
            )
            # The policy documents' own DOIs (few: about 5% have one) are direct
            # results and go first, in relevance order, then the cited papers.
            seed_dois = [d["doi"] for d in payload.get("docs", []) if d.get("doi")]
            ranked = seed_dois + [d for d in payload["dois"] if d not in seed_dois]
            row: dict[str, Any] = {
                "review": title[:60],
                "arm": arm,
                "n_target": len(gt.keys),
                "n_returned": len(ranked),
                "n_seed_dois": len(seed_dois),
                "n_docs_citing": payload.get("n_docs_citing"),
            }
            for cap in args.caps:
                row[f"hits@{cap}"], row[f"recall@{cap}"] = recall(ranked, gt, cap)
            row["hits@all"], row["recall@all"] = recall(ranked, gt, None)
            for doi, count in zip(
                payload["dois"], payload.get("inset", []), strict=False
            ):
                if doi in gt.keys:
                    hit_counts[arm][count] += 1
            rows.append(row)
            print(
                f"{arm:16} {title[:50]:50} returned {row['n_returned']:5}  "
                + "  ".join(f"@{c} {row[f'recall@{c}']:5.1%}" for c in args.caps)
                + f"  all {row['recall@all']:5.1%}"
            )

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "scores.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("\nMean recall by arm:")
    for arm in arms:
        sub = [r for r in rows if r["arm"] == arm]
        print(
            f"  {arm:16} "
            + "  ".join(
                f"@{c} {sum(r[f'recall@{c}'] for r in sub) / len(sub):5.1%}"
                for c in args.caps
            )
            + f"  all {sum(r['recall@all'] for r in sub) / len(sub):5.1%}"
            + f"  (mean returned {sum(r['n_returned'] for r in sub) / len(sub):.0f})"
        )
    print("\nGround-truth hits by policy in-set count (all reviews):")
    for arm, counter in hit_counts.items():
        total = sum(counter.values())
        above_one = total - counter[1]
        print(
            f"  {arm:20} hits {total:3}  count 1: {counter[1]:3}  "
            f"2: {counter[2]:3}  3+: {above_one - counter[2]:3}  "
            f"share above one {above_one / total if total else 0:.0%}"
        )
    print(f"\nwrote {args.out / 'scores.csv'}")


if __name__ == "__main__":
    main()
