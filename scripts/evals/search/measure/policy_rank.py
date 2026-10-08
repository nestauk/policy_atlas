"""Ranking policy documents with Overton's own citation graph (R&D, task 049).

Which of the policy documents Overton returns for a question are the *key* ones? The
semantic search orders them by similarity to the question. Every record also carries
the policy documents it cites (``cites.policy``), the papers it cites
(``cites.scholarly``) and how many policy documents cite it (``citation_count``). This
script turns those into four signals and compares the document orders they give:

- **policy in-set citations**: how many of the retrieved documents cite this one. A
  strategy or guideline many of them cite is a landmark. Documents cited by the set but
  not retrieved are the *policy snowball*: the most-cited ones are fetched and added.
- **policy specificity**: in-set citations damped by the global ``citation_count``,
  (in-set) / log10(citation_count + 10), so documents everyone cites rank below the ones
  this topic cites.
- **coupling with the core papers**: the core papers are the 50 papers most cited by the
  retrieved documents; a document's coupling is how many of them it cites. High coupling
  marks an evidence synthesis for this topic rather than a position paper.
- **forward from the core papers** (modest: ``--forward 10`` calls): for the ten most
  cited core papers, ``articles.php?query=<doi>`` lists the policy documents citing them.
  A document's forward score is how many of the ten it cites; documents not retrieved by
  the search are new candidates, and the best of them are fetched and added.

Document rankings compared: ``relevance`` (the search order), ``inset``, ``specific``,
``coupling``, ``forward`` and ``combined`` (coupling + in-set + forward, similarity as
tiebreak).

Two checks. **Against the paper ground truth**: take the first 100 documents of each
order, rank the papers they cite by in-set count, score paper recall at 200 and over
all, so a better document order shows as better paper recall even though the ground
truth holds no policy documents. **By eye**: ``--manual "question"`` writes the top 25
documents of every order with all signals to ``results/overton/policy/<slug>/`` for a
qualitative read.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/measure/policy_rank.py \\
        [--dataset retrieval-ground-truth-mini] [--docs 200] [--landmarks 15] \\
        [--forward 10] [--forward-new 15] [--reviews TEXT ...] [--manual QUESTION]

Calls per question: docs/50 searches + landmarks + forward + forward-new lookups, about
45 at the defaults, one per 1.3 s. Everything is cached under
``results/cache/overton-policy/``. Uploads nothing.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR
from evals_search_utils import (
    DEFAULT_DATASET,
    GroundTruth,
    ground_truth_from_item,
    normalize_doi,
    select_items,
)
from overton_recall import generated_texts, get, pages
from snowball_recall import slug

import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing
from policy_atlas.core.embeddings import OpenAIEmbeddingBackend
from pool_rerank import cosine

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "overton" / "policy"
CORE = 50
RANKINGS = ["relevance", "inset", "specific", "coupling", "forward", "combined"]
SIM_RANKING = (
    "specific-sim"  # added with --embed: (specificity + 0.5) x (similarity + 0.2)
)


def slim(doc: dict[str, Any], origin: str) -> dict[str, Any]:
    """The fields the rankings need, from a raw Overton document record."""
    koi = doc.get("keyed_other_identifiers")
    cites = doc.get("cites") or {}
    source = doc.get("source") or {}
    return {
        "id": doc.get("policy_document_id"),
        "title": doc.get("translated_title") or doc.get("title") or "",
        "published_on": doc.get("published_on"),
        "source": source.get("title"),
        "source_type": source.get("type"),
        "country": source.get("country"),
        "series": doc.get("overton_policy_document_series"),
        "url": doc.get("document_url"),
        "doi": normalize_doi((koi.get("doi") or [None])[0])
        if isinstance(koi, dict)
        else None,
        "citation_count": int(doc.get("citation_count") or 0),
        "es_score": doc.get("es_score"),
        "cites_policy": [
            p.get("overton_id")
            for p in cites.get("policy") or []
            if p.get("overton_id")
        ],
        "cites_policy_titles": {
            p.get("overton_id"): p.get("title")
            for p in cites.get("policy") or []
            if p.get("overton_id")
        },
        "cites_scholarly": sorted(
            {
                d
                for d in (
                    normalize_doi(w.get("doi")) for w in cites.get("scholarly") or []
                )
                if d
            }
        ),
        "origin": origin,
        # Title plus the matching excerpt or the provider's machine-written summary,
        # for the optional similarity term (search results only carry the excerpt).
        "text": " ".join(
            s
            for s in (
                doc.get("translated_title") or doc.get("title") or "",
                doc.get("snippet") or doc.get("llm_document_description") or "",
            )
            if s
        )[:2000],
    }


def lookup(doc_id: str) -> dict[str, Any] | None:
    body = get("documents.php", policy_document_id=doc_id, pp="1")
    results = body.get("results") or []
    return results[0] if results else None


def cited_by(doi: str) -> list[dict[str, Any]]:
    """Policy documents citing one paper, from the scholarly-article endpoint."""
    body = get("articles.php", query=doi, pp="1")
    results = (body.get("results") or {}).get("results") or []
    if not results or normalize_doi(results[0].get("doi")) != doi:
        return []
    return results[0].get("cited_by_documents") or []


def build(
    intent: str,
    cutoff: str | None,
    *,
    n_docs: int,
    n_landmarks: int,
    n_forward: int,
    n_forward_new: int,
    paraphrases: bool = False,
    source_country: str | None = None,
    exclude_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Fetch, snowball, chase and score one question; see the module docstring.

    ``exclude_ids`` are held-out documents (a ground-truth strategy): they are dropped
    from the search results before any signal is computed and are never fetched, so
    their own reference lists cannot feed the snowball, the core papers or the
    forward step (Codex review, 2026-10-08).

    With ``paraphrases`` the intent and the pipeline's two generated paraphrases are
    searched separately, ``n_docs`` split between them, and merged round-robin with
    duplicates skipped, as the better Overton arm in ``overton_recall.py`` does.
    """
    params = {"min_similarity": "0.3", "sort": "relevance"}
    if cutoff:
        params["published_before"] = cutoff
    if source_country:
        params["source_country"] = source_country  # Overton display value, e.g. "UK"
    texts = [intent, *(generated_texts(intent)["paraphrases"] if paraphrases else [])]
    per_text = -(-n_docs // len(texts))  # ceiling division
    per_text_docs = [
        pages("documents.php", per_text, squery=text, **params) for text in texts
    ]
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position in range(per_text):
        for result in per_text_docs:
            if (
                position < len(result)
                and result[position].get("policy_document_id") not in seen_ids
            ):
                seen_ids.add(result[position]["policy_document_id"])
                merged.append(result[position])
    merged = [m for m in merged if m.get("policy_document_id") not in exclude_ids]
    docs = [slim(d, "search") for d in merged[:n_docs]]
    for position, d in enumerate(docs, start=1):
        d["rel_rank"] = position
    ids = {d["id"] for d in docs} | set(exclude_ids)

    def fetch(doc_id: str, origin: str) -> None:
        # Documents fetched by id carry no date fence; drop any dated after the cutoff.
        raw = lookup(doc_id)
        if raw:
            d = slim(raw, origin)
            if after_cutoff(d, cutoff):
                return
            d["rel_rank"] = 10**6
            docs.append(d)
        ids.add(doc_id)

    # Policy snowball: documents the set cites but the search did not return.
    cited = collections.Counter(p for d in docs for p in set(d["cites_policy"]))
    for doc_id in [p for p, _ in cited.most_common() if p not in ids][:n_landmarks]:
        fetch(doc_id, "landmark")

    # Core papers and forward chasing from the ten most cited.
    paper_counts = collections.Counter(
        p for d in docs if d["origin"] == "search" for p in d["cites_scholarly"]
    )
    core = [p for p, _ in paper_counts.most_common(CORE)]
    forward_counts: collections.Counter[str] = collections.Counter()
    forward_meta: dict[str, dict[str, Any]] = {}
    for doi in core[:n_forward]:
        for rec in cited_by(doi):
            doc_id = rec.get("policy_document_id")
            # A citing document after the cutoff must not count for anyone's score.
            if doc_id and not after_cutoff(rec, cutoff):
                forward_counts[doc_id] += 1
                forward_meta.setdefault(doc_id, rec)
    for doc_id in [p for p, _ in forward_counts.most_common() if p not in ids][
        :n_forward_new
    ]:
        fetch(doc_id, "forward")

    core_set = set(core)
    for d in docs:
        d["inset"] = cited.get(d["id"], 0)
        d["specific"] = round(d["inset"] / math.log10(d["citation_count"] + 10), 3)
        d["coupling"] = len(core_set & set(d["cites_scholarly"]))
        d["forward"] = forward_counts.get(d["id"], 0)
    return {
        "intent": intent,
        "cutoff": cutoff,
        "docs": docs,
        "core": core,
        "core_counts": [paper_counts[p] for p in core],
        "n_landmarks_found": sum(1 for d in docs if d["origin"] == "landmark"),
        "n_forward_docs": len(forward_counts),
        "n_forward_new": sum(1 for d in docs if d["origin"] == "forward"),
    }


def order(docs: list[dict[str, Any]], how: str) -> list[dict[str, Any]]:
    keys = {
        "relevance": lambda d: (d["rel_rank"], -d["inset"]),
        "inset": lambda d: (-d["inset"], d["rel_rank"]),
        "specific": lambda d: (-d["specific"], -d["inset"], d["rel_rank"]),
        "coupling": lambda d: (-d["coupling"], -d["inset"], d["rel_rank"]),
        "forward": lambda d: (-d["forward"], -d["coupling"], d["rel_rank"]),
        "combined": lambda d: (
            -(d["coupling"] + d["inset"] + d["forward"]),
            d["rel_rank"],
        ),
        # Task-047 product rule, similarity as a damping term on specificity: an added
        # document that is off the question drops, one on the question keeps its place.
        SIM_RANKING: lambda d: (
            -((d["specific"] + 0.5) * (d.get("sim_norm", 0.0) + 0.2)),
            -d["inset"],
            d["rel_rank"],
        ),
    }
    return sorted(docs, key=keys[how])


def add_similarity(payload: dict[str, Any], key: str) -> None:
    """Cosine similarity of every document's text to the intent, normalised 0..1, cached."""
    path = (
        CACHE_DIR
        / "overton-policy"
        / f"sim-{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"
    )
    docs = payload["docs"]
    if path.exists():
        sims = json.loads(path.read_text())
    else:
        embedder = OpenAIEmbeddingBackend()
        texts = [d.get("text") or d["title"] for d in docs]
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 100):
            vectors.extend(embedder.embed_texts(texts[start : start + 100]))
        query = embedder.embed_texts([payload["intent"]])[0]
        sims = {d["id"]: cosine(query, v) for d, v in zip(docs, vectors, strict=True)}
        path.write_text(json.dumps(sims))
    values = [sims.get(d["id"], 0.0) for d in docs]
    lo, hi = min(values), max(values)
    for d, s in zip(docs, values, strict=True):
        d["sim"] = round(s, 4)
        d["sim_norm"] = (s - lo) / (hi - lo) if hi > lo else 0.0


def paper_recall(docs: list[dict[str, Any]], gt: GroundTruth, cap: int | None) -> float:
    """Papers cited by these documents, ranked by in-set count, scored at ``cap``."""
    counts = collections.Counter(p for d in docs for p in d["cites_scholarly"])
    ranked = [p for p, _ in counts.most_common()]
    found = set(ranked if cap is None else ranked[:cap]) & gt.keys
    return len(found) / len(gt.keys) if gt.keys else 0.0


def after_cutoff(doc: dict[str, Any], cutoff: str | None) -> bool:
    """True when the document is dated after the cutoff (undated documents are kept)."""
    return bool(cutoff) and (doc.get("published_on") or "")[:10] > cutoff


CACHE_VERSION = "v2"  # bumped 2026-10-08: exclusions and date fences applied at build


def cached_build(key: str, **kwargs: Any) -> dict[str, Any]:
    """Build once per key; the key carries every knob and the cache version."""
    exclude = kwargs.get("exclude_ids")
    key = f"{CACHE_VERSION}|{key}|x{sorted(exclude) if exclude else ''}"
    path = (
        CACHE_DIR
        / "overton-policy"
        / f"{hashlib.sha256(key.encode()).hexdigest()[:16]}.json"
    )
    if path.exists():
        return json.loads(path.read_text())
    payload = build(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload


def write_manual(payload: dict[str, Any], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "origin",
        "inset",
        "specific",
        "coupling",
        "forward",
        "sim",
        "citation_count",
        "rel_rank",
        "published_on",
        "source_type",
        "source",
        "series",
        "title",
        "url",
    ]
    for how in [*RANKINGS, *([SIM_RANKING] if "sim" in payload["docs"][0] else [])]:
        with (folder / f"{how}.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for position, d in enumerate(order(payload["docs"], how)[:25], start=1):
                writer.writerow({**d, "rank": position})
    titles = {}
    for d in payload["docs"]:
        titles.update(d["cites_policy_titles"])
    with (folder / "core_papers.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["in_set_citations", "doi"])
        writer.writerows(zip(payload["core_counts"], payload["core"], strict=True))
    print(f"\nwrote {folder}")
    shown = ["relevance", "specific", "combined"] + (
        [SIM_RANKING] if "sim" in payload["docs"][0] else []
    )
    for how in shown:
        print(f"\n== {how}: top 15 ==")
        for position, d in enumerate(order(payload["docs"], how)[:15], start=1):
            print(
                f"{position:2} [{d['origin'][:4]}] in-set {d['inset']:2} coup {d['coupling']:2} "
                f"fwd {d['forward']:2} sim {d.get('sim_norm', 0):.2f} cited {d['citation_count']:3}  {d['published_on'] or '':10} "
                f"{(d['source_type'] or '')[:10]:10} {d['title'][:75]}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=DEFAULT_DATASET + "-mini")
    parser.add_argument("--docs", type=int, default=200)
    parser.add_argument("--landmarks", type=int, default=15)
    parser.add_argument("--forward", type=int, default=10)
    parser.add_argument("--forward-new", type=int, default=15)
    parser.add_argument(
        "--top", type=int, default=100, help="documents per order for the paper check"
    )
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument("--manual", default=None, metavar="QUESTION")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--embed",
        action="store_true",
        help="add the similarity-damped specificity order (one embedding call per 100 documents)",
    )
    parser.add_argument(
        "--paraphrases",
        action="store_true",
        help="search the intent and its two generated paraphrases, merged round-robin",
    )
    parser.add_argument(
        "--source-country",
        default=None,
        help="Overton source_country filter, by display value (e.g. UK)",
    )
    args = parser.parse_args()
    knobs = {
        "n_docs": args.docs,
        "n_landmarks": args.landmarks,
        "n_forward": args.forward,
        "n_forward_new": args.forward_new,
        **({"paraphrases": True} if args.paraphrases else {}),
        **({"source_country": args.source_country} if args.source_country else {}),
    }

    if args.manual:
        payload = cached_build(
            f"manual|{args.manual}|{knobs}", intent=args.manual, cutoff=None, **knobs
        )
        print(
            f"{len(payload['docs'])} documents: search {args.docs}, landmarks "
            f"{payload['n_landmarks_found']}, forward-new {payload['n_forward_new']} "
            f"(forward reached {payload['n_forward_docs']} documents)"
        )
        if args.embed:
            add_similarity(payload, f"manual|{args.manual}|{knobs}")
        write_manual(payload, args.out / slug(args.manual))
        return

    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST"
        )
    items = select_items(client.get_dataset(args.dataset).items, args.reviews)
    rows: list[dict[str, Any]] = []
    for item in items:
        intent, cutoff = item.input["intent"], item.input["published_before"]
        gt = ground_truth_from_item(item)
        title = item.metadata.get("review_title", str(item.id))
        payload = cached_build(
            f"{item.id}|{intent}|{cutoff}|{knobs}",
            intent=intent,
            cutoff=cutoff,
            **knobs,
        )
        for how in RANKINGS:
            top = order(payload["docs"], how)[: args.top]
            rows.append(
                {
                    "review": title[:60],
                    "ranking": how,
                    "n_docs": len(payload["docs"]),
                    "landmarks": payload["n_landmarks_found"],
                    "forward_new": payload["n_forward_new"],
                    "recall@200": paper_recall(top, gt, 200),
                    "recall@all": paper_recall(top, gt, None),
                    "n_from_added": sum(1 for d in top if d["origin"] != "search"),
                }
            )
        print(
            f"{title[:50]:50} docs {len(payload['docs'])} landmarks {payload['n_landmarks_found']} forward-new {payload['n_forward_new']}"
        )

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "scores.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"\nPaper recall from the first {args.top} documents of each order (mean over reviews):"
    )
    print("| order | recall@200 | recall@all | added documents in the top |")
    print("|---|---:|---:|---:|")
    for how in RANKINGS:
        sub = [r for r in rows if r["ranking"] == how]
        print(
            f"| {how} | {sum(r['recall@200'] for r in sub) / len(sub):.1%} | "
            f"{sum(r['recall@all'] for r in sub) / len(sub):.1%} | "
            f"{sum(r['n_from_added'] for r in sub) / len(sub):.1f} |"
        )
    print(f"\nwrote {args.out / 'scores.csv'}")


if __name__ == "__main__":
    main()
