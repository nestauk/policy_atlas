"""Ideas 2 and 4 of EXPERIMENTS.md § 6: a longer tail re-ranked before the cut, and a
topic-fenced search for the papers no citation link reaches.

Builds on ``snowball_recall.py`` (same seeds, backward snowball and forward stage) and
asks two questions on top:

1. **Longer tail, better ranker.** Expand the backward snowball to ``--expand`` works
   (800 by default, against 200 in the base configuration), keep the forward stage, and
   rank the whole pool (about 1,200 candidates) with several rules before cutting at
   200 and 400. The rules: the graph-only specificity score used so far; an
   Adamic-Adar variant where a citing seed with a short reference list counts for
   more; the embedding similarity of each candidate's title and abstract to the
   question, using the pipeline's own embedding backend; and two ways of combining
   graph and embedding. If a 400-candidate pool re-ranked by embeddings reaches what
   the graph alone reaches at 600, the screen can see a bigger pool for the same bill.
2. **Topic fence.** Read the seeds' dominant OpenAlex topics (the three most common
   ``primary_topic`` ids), then rerun the generated queries and the question itself
   restricted to those topics. These results have no citation link to the seeds, so
   only the embedding rules can rank them; the question is whether they reach ground
   truth the graph cannot.

Everything fetched is cached under ``results/cache/`` (snowball, forward, abstracts,
topic searches, embeddings), so a rerun makes no requests. Cost per review on a fresh
run: about 16 calls to resolve the longer tail, 28 to fetch abstracts, 10 for topics
and topic searches, all free; and one embedding call per 100 texts on
``text-embedding-3-small`` (about 1,400 texts per review, under a cent).

Usage::

    uv run --project backend --env-file backend/.env python scripts/evals/search/measure/pool_rerank.py \\
        [--queries shared] [--model gpt-5.6-luna] [--prompt-file ...] [--expand 800] \\
        [--forward 200] [--caps 200 400 600]

Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import cache_path, make_getter, openalex_cutoff, openalex_query
from evals_search_utils import (
    GroundTruth,
    ground_truth_from_item,
    normalize_doi,
    select_items,
)
from snowball_recall import (
    MINI_DATASET,
    QUERY_SOURCES,
    candidates,
    load_or_expand,
    override_prompt,
    score,
    short_id,
)

import argparse
import collections
import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing
from policy_atlas.core.embeddings import OpenAIEmbeddingBackend
from policy_atlas.evidence_search.sourcing import search_generation

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "snowball" / "pool"
BATCH = 50
RRF_K = 60


def batched(ids: list[str], *, select: str, get: Any) -> list[dict[str, Any]]:
    works: list[dict[str, Any]] = []
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        response = get(
            "/works",
            {
                "filter": f"openalex_id:{'|'.join(chunk)}",
                "select": select,
                "per-page": str(BATCH),
            },
            {},
        )
        if response is not None and response.status_code == 200:
            works.extend(response.json().get("results", []))
    return works


def cached_json(key: str, build: Any) -> Any:
    path = cache_path("pool", key)
    if path.exists():
        return json.loads(path.read_text())
    value = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def abstract_text(work: dict[str, Any]) -> str:
    """Rebuild the abstract from OpenAlex's inverted index (word -> positions)."""
    index = work.get("abstract_inverted_index") or {}
    positions: dict[int, str] = {}
    for word, places in index.items():
        for place in places:
            positions[place] = word
    return " ".join(positions[i] for i in sorted(positions))


def seed_topics(payload: dict[str, Any], *, item_id: str, get: Any) -> list[str]:
    """The three most common primary-topic ids among the seeds."""
    ids = sorted(short_id(w["id"]) for w in payload["seed_works"] if short_id(w["id"]))

    def build() -> list[str]:
        works = batched(ids, select="id,primary_topic", get=get)
        counter = collections.Counter(
            short_id((w.get("primary_topic") or {}).get("id") or "") for w in works
        )
        counter.pop("", None)
        return [t for t, _ in counter.most_common(3)]

    return cached_json(f"topics|{item_id}|{payload.get('source')}|{len(ids)}", build)


def topic_search(
    queries: list[str], topics: list[str], *, cutoff: str, get: Any
) -> list[dict[str, Any]]:
    """The generated queries and the intent, fenced to the seeds' topics."""
    found: dict[str, dict[str, Any]] = {}
    for query in queries:
        key = f"topicsearch|{query}|{'|'.join(topics)}|{cutoff}"

        def build(query: str = query) -> list[dict[str, Any]]:
            response = get(
                "/works",
                {
                    "search": openalex_query(query),
                    "filter": f"primary_topic.id:{'|'.join(topics)},{openalex_cutoff(cutoff)}",
                    "select": "id,doi,display_name,publication_date,cited_by_count",
                    "per-page": "200",
                },
                {},
            )
            if response is None or response.status_code != 200:
                return []
            return response.json().get("results", [])

        for work in cached_json(key, build):
            sid = short_id(work.get("id")) or ""
            if sid and sid not in found:
                found[sid] = work
    return list(found.values())


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def embed_pool(
    rows: list[dict[str, Any]], intent: str, *, key: str, get: Any, embedder: Any
) -> dict[str, float]:
    """Cosine similarity of each candidate (title + abstract) to the question, cached."""
    ids = sorted({r["openalex_id"] for r in rows if r["openalex_id"]})

    def build() -> dict[str, Any]:
        works = batched(ids, select="id,display_name,abstract_inverted_index", get=get)
        texts = {
            short_id(w["id"]): f"{w.get('display_name') or ''}. {abstract_text(w)}"[
                :2000
            ]
            for w in works
            if short_id(w["id"])
        }
        order = sorted(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(order), 100):
            vectors.extend(
                embedder.embed_texts([texts[i] for i in order[start : start + 100]])
            )
        query_vector = embedder.embed_texts([intent])[0]
        return {
            "sims": {
                sid: cosine(query_vector, vec)
                for sid, vec in zip(order, vectors, strict=True)
            },
            "n_with_abstract": sum(
                1 for w in works if w.get("abstract_inverted_index")
            ),
        }

    data = cached_json(key, build)
    return data["sims"]


def adamic_adar(payload: dict[str, Any]) -> dict[str, float]:
    """Backward signal re-weighted: a citing seed with a short reference list counts for more.

    Returned on the scale of a plain count (divided by the mean weight), so it can replace
    the in-set count in the specificity score without changing the balance with coupling.
    """
    weights: dict[str, float] = {}
    for seed in payload["seed_works"]:
        refs = seed.get("referenced_works") or []
        weights[short_id(seed["id"]) or ""] = 1.0 / math.log2(2 + len(refs))
    mean_w = sum(weights.values()) / max(1, len(weights))
    scores: collections.Counter[str] = collections.Counter()
    for seed in payload["seed_works"]:
        w = weights[short_id(seed["id"]) or ""]
        for ref in set(seed.get("referenced_works") or []):
            scores[short_id(ref) or ref] += w
    return {k: v / mean_w for k, v in scores.items()}


def rankers(
    rows: list[dict[str, Any]], aa: dict[str, float], sims: dict[str, float]
) -> dict[str, list[dict[str, Any]]]:
    for r in rows:
        r["sim"] = sims.get(r["openalex_id"], 0.0)
        r["aa_spec"] = (aa.get(r["openalex_id"], 0.0) + r["coupling"]) / math.log10(
            r["cited_by_count"] + 10
        )
    by_spec = sorted(
        rows, key=lambda r: (-r["specificity"], -r["wcoupling"], r["raw_rank"])
    )
    by_sim = sorted(rows, key=lambda r: -r["sim"])
    fused: dict[int, float] = collections.defaultdict(float)
    for ordered in (by_spec, by_sim):
        for position, r in enumerate(ordered, start=1):
            fused[id(r)] += 1.0 / (RRF_K + position)
    sims_sorted = sorted(r["sim"] for r in rows)
    lo, hi = sims_sorted[0], sims_sorted[-1]
    for r in rows:
        r["sim_norm"] = (r["sim"] - lo) / (hi - lo) if hi > lo else 0.0
    shortlist = by_spec[:400]
    return {
        "graph: specificity (current)": by_spec,
        "graph: Adamic-Adar specificity": sorted(
            rows, key=lambda r: (-r["aa_spec"], -r["wcoupling"], r["raw_rank"])
        ),
        "embedding similarity only": by_sim,
        "fusion: reciprocal rank of specificity and similarity": sorted(
            rows, key=lambda r: -fused[id(r)]
        ),
        "product: specificity x normalised similarity": sorted(
            rows, key=lambda r: -(r["specificity"] + 0.5) * (r["sim_norm"] + 0.2)
        ),
        "shortlist 400 by specificity, re-ranked by similarity": sorted(
            shortlist, key=lambda r: -r["sim"]
        )
        + by_spec[400:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=MINI_DATASET)
    parser.add_argument(
        "--queries", choices=[k for k in QUERY_SOURCES if k != "raw"], default="shared"
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--expand", type=int, default=800)
    parser.add_argument("--forward", type=int, default=200)
    parser.add_argument("--forward-top", type=int, default=20)
    parser.add_argument("--forward-pages", type=int, default=10)
    parser.add_argument("--caps", nargs="+", type=int, default=[200, 400, 600])
    parser.add_argument(
        "--no-topics", action="store_true", help="skip the topic-fenced search"
    )
    parser.add_argument("--reviews", nargs="+", default=None)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    if args.model:
        search_generation.SEARCH_QUERIES_MODEL = args.model
    prompt_sha = override_prompt(args.queries, args.prompt_file)
    label = args.label or (
        f"{date.today().isoformat()}-{args.queries}-{prompt_sha[:6]}"
        + (f"-{args.model}" if args.model else "")
        + f"-s{args.seeds}-k{args.expand}-f{args.forward}"
    )
    out = OUT_DIR / label
    get = make_getter("openalex-raw")
    embedder = OpenAIEmbeddingBackend()
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    items = select_items(list(client.get_dataset(args.dataset).items), args.reviews)

    rows_out: list[dict[str, Any]] = []
    pool_stats = collections.Counter()
    for item in items:
        title = item.metadata.get("review_title", str(item.id))
        intent, cutoff = item.input["intent"], item.input["published_before"]
        gt: GroundTruth = ground_truth_from_item(item)
        payload, _ = load_or_expand(
            item_id=str(item.id),
            intent=intent,
            cutoff=cutoff,
            n_seeds=args.seeds,
            n_expand=args.expand,
            refresh=False,
            get=get,
            source=args.queries,
            prompt_sha=prompt_sha,
            forward=args.forward,
            forward_pages=args.forward_pages,
            forward_top=args.forward_top,
        )
        rows = candidates(payload)
        in_pool = {r["doi"] for r in rows} - {None}
        topics: list[str] = []
        n_topic_new_gt = 0
        if not args.no_topics:
            topics = seed_topics(payload, item_id=str(item.id), get=get)
            queries = list(payload["generation"]["queries"]) + [intent]
            topic_works = topic_search(queries, topics, cutoff=cutoff, get=get)
            have = {r["openalex_id"] for r in rows}
            counts = payload["counts"]
            for w in topic_works:
                sid = short_id(w["id"]) or ""
                if sid in have:
                    continue
                doi = normalize_doi(w.get("doi"))
                if doi in gt.dois and doi not in in_pool:
                    n_topic_new_gt += 1
                rows.append(
                    {
                        "openalex_id": sid,
                        "doi": doi,
                        "backend": "openalex",
                        "title": w.get("display_name"),
                        "year": (w.get("publication_date") or "")[:4],
                        "cited_by_count": w.get("cited_by_count") or 0,
                        "inset": counts.get(sid, 0),
                        "coupling": 0,
                        "wcoupling": 0.0,
                        "specificity": round(
                            counts.get(sid, 0)
                            / math.log10((w.get("cited_by_count") or 0) + 10),
                            3,
                        ),
                        "source": "topic",
                        "raw_rank": 10**6,
                        "forward_rank": 10**6,
                    }
                )
        gt_in_pool = len({r["doi"] for r in rows if r["doi"] in gt.dois})
        pool_stats["pool"] += len(rows)
        pool_stats["gt_in_pool"] += gt_in_pool
        pool_stats["gt"] += len(gt.dois)
        pool_stats["topic_new_gt"] += n_topic_new_gt
        pool_stats["topic_rows"] += sum(1 for r in rows if r["source"] == "topic")
        sims = embed_pool(
            rows,
            intent,
            key=f"emb|{item.id}|{payload.get('source')}|{prompt_sha}|k{args.expand}|f{args.forward}|t{int(not args.no_topics)}",
            get=get,
            embedder=embedder,
        )
        aa = adamic_adar(payload)
        for name, ranked in rankers(rows, aa, sims).items():
            for cap in args.caps:
                s = score(ranked, gt, cap, set())
                s["n_from_topic"] = sum(
                    1
                    for r in ranked[:cap]
                    if r["source"] == "topic" and r["doi"] in gt.dois
                )
                rows_out.append(
                    {
                        "review": title,
                        "ranker": name,
                        "cap": cap,
                        "pool": len(rows),
                        "gt_in_pool": gt_in_pool,
                        "topics": "|".join(topics),
                        **s,
                    }
                )
        print(
            f"{title[:55]}: pool {len(rows)} ({sum(1 for r in rows if r['source'] == 'topic')} topic-fenced), ground truth in pool {gt_in_pool}/{len(gt.dois)}, new via topics {n_topic_new_gt}"
        )

    out.mkdir(parents=True, exist_ok=True)
    with (out / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_out[0]))
        writer.writeheader()
        writer.writerows(rows_out)
    n = len(items)
    print(f"\n{n} reviews -> {out}")
    print(
        f"pool per review {pool_stats['pool'] / n:.0f} candidates; ground truth in pool {pool_stats['gt_in_pool'] / pool_stats['gt']:.1%} "
        f"(the ceiling); topic-fenced rows per review {pool_stats['topic_rows'] / n:.0f}, ground truth reached only through them {pool_stats['topic_new_gt'] / pool_stats['gt']:.1%}"
    )

    def mean(key: str, rs: list[dict[str, Any]]) -> float:
        return sum(r[key] for r in rs) / len(rs) if rs else 0.0

    print(
        f"\n{'ranker':58s} "
        + " ".join(
            f"{'cap ' + str(c):>8s} {'seed':>4s} {'snow':>4s} {'fwd':>4s} {'topic':>5s}"
            for c in args.caps
        )
    )
    for name in dict.fromkeys(r["ranker"] for r in rows_out):
        cells = []
        for cap in args.caps:
            cell = [r for r in rows_out if r["ranker"] == name and r["cap"] == cap]
            cells.append(
                f"{mean('recall', cell):8.1%} {mean('n_from_seed', cell):4.1f} {mean('n_from_snowball', cell):4.1f} {mean('n_from_forward', cell):4.1f} {mean('n_from_topic', cell):5.1f}"
            )
        print(f"{name:58s} " + " ".join(cells))


if __name__ == "__main__":
    main()
