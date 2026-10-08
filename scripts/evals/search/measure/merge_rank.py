"""Merged ranking of OpenAlex and Overton candidates (R&D, task 049).

Offline experiment. Per review it takes two candidate lists already on disk:

- the OpenAlex pool of a ``snowball_recall.py`` run (seeds, reference-list snowball,
  forward chasing), with the task-047 graph signals: in-set citations, coupling,
  citation count as of the cutoff, specificity;
- the papers cited by the policy documents of the ``overton_recall.py`` ``docs-cites``
  arm, with their in-set policy citations (how many of the retrieved policy documents
  cite each paper).

The lists are joined on DOI. Papers only Overton found are resolved to OpenAlex records
(50 per request, ``filter=doi:``) for their citation count as of the cutoff and their
publication date; those after the cutoff are dropped, those OpenAlex does not know keep
a count of zero. Then the union is ranked several ways and scored at each cap:

- ``oa``: the OpenAlex pool alone in its specificity order (the task-047 control);
- ``ov``: the Overton papers alone by policy in-set citations (the task-049 control);
- ``merged-w<W>``: one specificity score for the union,
  (in-set citations + coupling + W x policy citations) / log10(citations + 10),
  so W says how much one citing policy document is worth against one citing paper;
- ``rrf``: reciprocal rank fusion of the two lists, 1 / (60 + rank) summed;
- ``interleave``: one from each list in turn.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/measure/merge_rank.py \\
        [--run RUN_FOLDER] [--weights 0.5 1 2 3] [--caps 100 200 400 600] \\
        [--reviews TEXT ...]

Free: about 15 OpenAlex list requests per review, cached under
``results/cache/overton-merge/``. Uploads nothing.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR, make_getter
from evals_search_utils import (
    DEFAULT_DATASET,
    ground_truth_from_item,
    normalize_doi,
    openalex_get,
    select_items,
)
from pool_rerank import embed_pool
from snowball_recall import RESOLVE_SELECT, cited_asof, short_id, slug

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing
from policy_atlas.core.embeddings import OpenAIEmbeddingBackend

RESULTS = Path(__file__).resolve().parents[1] / "results"
DEFAULT_RUN = (
    RESULTS / "snowball" / "2026-10-06-shared+semantic-c6e320-s200-k200-f200p10c300t20"
)
OUT_DIR = RESULTS / "overton" / "merge"
BATCH = 50
RRF_K = 60


def resolve(dois: list[str], item_id: str) -> dict[str, dict[str, Any]]:
    """DOI -> OpenAlex record (citation count, counts by year, date), cached per review."""
    path = CACHE_DIR / "overton-merge" / f"{item_id}.json"
    found: dict[str, dict[str, Any]] = (
        json.loads(path.read_text()) if path.exists() else {}
    )
    missing = [d for d in dois if d not in found]
    if missing:
        for start in range(0, len(missing), BATCH):
            chunk = missing[start : start + BATCH]
            response = openalex_get(
                "/works",
                filter="doi:" + "|".join(chunk),
                select=RESOLVE_SELECT,
                **{"per-page": str(BATCH)},
            )
            time.sleep(0.2)
            if response.status_code != 200:
                continue
            for work in response.json().get("results", []):
                doi = normalize_doi(work.get("doi"))
                if doi:
                    found[doi] = work
            for doi in chunk:
                found.setdefault(doi, {})  # asked, not known to OpenAlex
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(found))
    return found


def candidates(
    run: Path, title: str, ov: dict[str, Any], cutoff: str, item_id: str
) -> list[dict[str, Any]]:
    """The union of both lists, one row per DOI, every signal filled."""
    rows: dict[str, dict[str, Any]] = {}
    with (run / "candidates" / f"{slug(title)}.csv").open() as fh:
        for position, r in enumerate(csv.DictReader(fh), start=1):
            doi = normalize_doi(r["doi"])
            if not doi or doi in rows:
                continue
            rows[doi] = {
                "doi": doi,
                "title": r["title"],
                "openalex_id": r["openalex_id"],
                "oa_rank": position,
                "ov_rank": 10**6,
                "inset": int(r["inset"]),
                "coupling": int(r["coupling"]),
                "wcoupling": float(r["wcoupling"]),
                "cites": int(r["cited_by_count"]),
                "policy": 0,
                "origin": "openalex",
            }
    ov_dois = [d for d in ov["dois"] if d]
    only_overton = [d for d in ov_dois if d not in rows]
    records = resolve(only_overton, item_id)
    for position, (doi, policy) in enumerate(
        zip(ov["dois"], ov["inset"], strict=True), start=1
    ):
        if not doi:
            continue
        if doi in rows:
            rows[doi]["policy"] = policy
            rows[doi]["ov_rank"] = min(rows[doi]["ov_rank"], position)
            if rows[doi]["origin"] == "openalex":
                rows[doi]["origin"] = "both"
            continue
        work = records.get(doi) or {}
        if (work.get("publication_date") or "") > cutoff:
            continue
        rows[doi] = {
            "doi": doi,
            "title": work.get("display_name") or "",
            "openalex_id": short_id(work.get("id")),
            "oa_rank": 10**6,
            "ov_rank": position,
            "inset": 0,
            "coupling": 0,
            "wcoupling": 0.0,
            "cites": cited_asof(work, cutoff) if work else 0,
            "policy": policy,
            "origin": "overton",
        }
    return list(rows.values())


def rank(rows: list[dict[str, Any]], how: str) -> list[dict[str, Any]]:
    if how == "oa":
        return sorted(
            (r for r in rows if r["oa_rank"] < 10**6), key=lambda r: r["oa_rank"]
        )
    if how == "ov":
        return sorted(
            (r for r in rows if r["ov_rank"] < 10**6), key=lambda r: r["ov_rank"]
        )
    if how.startswith("merged-w"):
        w = float(how[len("merged-w") :])
        return sorted(
            rows,
            key=lambda r: (
                -(
                    (r["inset"] + r["coupling"] + w * r["policy"])
                    / math.log10(r["cites"] + 10)
                ),
                -r["wcoupling"],
                -r["inset"],
                -r["policy"],
                r["oa_rank"],
            ),
        )
    if how == "rrf":
        return sorted(
            rows,
            key=lambda r: -(1 / (RRF_K + r["oa_rank"]) + 1 / (RRF_K + r["ov_rank"])),
        )
    if how == "interleave":
        oa, ov = rank(rows, "oa"), rank(rows, "ov")
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for pair in zip(oa + [None] * len(ov), ov + [None] * len(oa), strict=False):
            for r in pair:
                if r is not None and r["doi"] not in seen:
                    seen.add(r["doi"])
                    out.append(r)
        return out
    if how == "sim":
        return sorted(rows, key=lambda r: -r["sim"])
    if how.startswith("product-"):
        # Task-047 section 8 rule: (specificity + 0.5) x (normalised similarity + 0.2),
        # on the OpenAlex pool alone (``product-oa``) or on the union with policy
        # citations counted once each (``product-w1``).
        pool = rank(rows, "oa") if how == "product-oa" else rows
        w = 0.0 if how == "product-oa" else 1.0
        return sorted(
            pool,
            key=lambda r: (
                -(
                    (r["inset"] + r["coupling"] + w * r["policy"])
                    / math.log10(r["cites"] + 10)
                    + 0.5
                )
                * (r["sim_norm"] + 0.2)
            ),
        )
    if how.startswith("mix-"):
        # Fixed slot share for Overton: every k-th slot from the Overton list, the rest
        # from the OpenAlex list, duplicates skipped. ``mix-4`` gives Overton one in four.
        k = int(how[len("mix-") :])
        oa, ov = rank(rows, "oa"), rank(rows, "ov")
        out, seen = [], set()
        i = j = 0
        while i < len(oa) or j < len(ov):
            take_ov = (len(out) + 1) % k == 0 and j < len(ov) or i >= len(oa)
            r = ov[j] if take_ov else oa[i]
            if take_ov:
                j += 1
            else:
                i += 1
            if r["doi"] not in seen:
                seen.add(r["doi"])
                out.append(r)
        return out
    raise ValueError(how)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=DEFAULT_DATASET + "-mini")
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--weights", nargs="+", type=float, default=[0.5, 1, 2, 3])
    parser.add_argument("--caps", nargs="+", type=int, default=[100, 200, 400, 600])
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--arm",
        default="docs-cites",
        help="overton_recall.py arm whose cache supplies the Overton papers",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="also embed every candidate (title + abstract) and add the similarity "
        "rankings; about 1,500 texts per review on text-embedding-3-small, cached",
    )
    args = parser.parse_args()
    rankings = [
        "oa",
        "ov",
        *(f"merged-w{w:g}" for w in args.weights),
        "rrf",
        "interleave",
        "mix-8",
        "mix-4",
        "mix-2",
    ]
    if args.embed:
        rankings += ["sim", "product-oa", "product-w1"]
        get = make_getter("openalex-raw")
        embedder = OpenAIEmbeddingBackend()

    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST"
        )
    items = select_items(client.get_dataset(args.dataset).items, args.reviews)

    rows: list[dict[str, Any]] = []
    for item in items:
        gt = ground_truth_from_item(item)
        title = item.metadata.get("review_title", str(item.id))
        folder = CACHE_DIR / f"overton-{args.arm}"
        ov_path = next(
            iter(
                sorted(folder.glob(f"{item.id}-*.json")) or [folder / f"{item.id}.json"]
            )
        )
        ov = json.loads(ov_path.read_text())
        cands = candidates(
            args.run, title, ov, item.input["published_before"], str(item.id)
        )
        if args.embed:
            sims = embed_pool(
                cands,
                item.input["intent"],
                key=f"merge-{args.arm}-{item.id}",
                get=get,
                embedder=embedder,
            )
            for r in cands:
                r["sim"] = sims.get(r["openalex_id"], 0.0)
            lo, hi = min(r["sim"] for r in cands), max(r["sim"] for r in cands)
            for r in cands:
                r["sim_norm"] = (r["sim"] - lo) / (hi - lo) if hi > lo else 0.0
        for how in rankings:
            ranked = rank(cands, how)
            row: dict[str, Any] = {
                "review": title[:60],
                "ranking": how,
                "n_gt": len(gt.keys),
                "n_candidates": len(ranked),
            }
            for cap in [*args.caps, None]:
                top = ranked if cap is None else ranked[:cap]
                hits = [r for r in top if r["doi"] in gt.keys]
                label = "all" if cap is None else str(cap)
                row[f"recall@{label}"] = len(hits) / len(gt.keys) if gt.keys else 0.0
                row[f"hits@{label}"] = len(hits)
                row[f"from_overton_only@{label}"] = sum(
                    1 for r in hits if r["origin"] == "overton"
                )
            rows.append(row)
        print(f"{title[:50]:50} candidates {len(cands)}")

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "scores.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    labels = [*(str(c) for c in args.caps), "all"]
    print(
        "\n| ranking | "
        + " | ".join(f"cap {c}" for c in labels)
        + " | Overton-only hits @200 |"
    )
    print("|---|" + "---:|" * (len(labels) + 1))
    for how in rankings:
        sub = [r for r in rows if r["ranking"] == how]
        cells = [f"{sum(r[f'recall@{c}'] for r in sub) / len(sub):.1%}" for c in labels]
        extra = sum(r["from_overton_only@200"] for r in sub)
        print(f"| {how} | " + " | ".join(cells) + f" | {extra} |")
    print(f"\nwrote {args.out / 'scores.csv'}")


if __name__ == "__main__":
    main()
