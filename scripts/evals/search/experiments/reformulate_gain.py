"""Does query reformulation add papers the snowball does not? (R&D, task 051)

The production round loop's ``reformulate`` arm has never been measured on its own.
It takes screened exemplars (up to 8 relevant, 4 not relevant), asks the language
model to rewrite the queries anchored to the original question, and sends up to 4 new
OpenAlex queries. This script runs exactly that call, from the seed verdicts the
``screened_seeds.py`` experiment wrote, and asks one question: how many ground-truth
papers do the 4 reformulated queries return that the task 047 pool (seeds, backward
snowball, forward chasing) does not already hold?

The comparison is the cheaper way to spend the same budget: adding 200 more
snowball papers (``snowball_recall.py --expand 400`` on the same seeds). Its gain
is read from that run's ``scores.csv``, not computed here.

Per review the script reports: the new ground-truth papers the reformulated queries
reach (not in the pool at all), how many of those at least one seed cites (so the
specificity ranking could lift them), and the ground-truth hits of each query.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/reformulate_gain.py \\
        --verdicts results/snowball/<screened-seeds run>/verdicts [--model gpt-5.6-luna]

Cost: one reformulation call per review (cached by intent and exemplars), four free
OpenAlex calls per review (cached). Uploads nothing.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import cache_path, make_getter
from evals_search_utils import ground_truth_from_item, normalize_doi, select_items
from snowball_recall import (
    MINI_DATASET,
    PER_CALL_DEFAULT,
    SEED_ARM,
    candidates,
    load_or_expand,
    override_prompt,
    query_page,
    slug,
)

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from policy_atlas.core import tracing
from policy_atlas.evidence_search.sourcing import search_generation
from policy_atlas.evidence_search.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    ExemplarRecord,
    ReformulatePayload,
    validated_queries,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "snowball"
POS_EXEMPLARS, NEG_EXEMPLARS, CONFIDENT_FLOOR, QUERY_CAP = 8, 4, 0.7, 4


def exemplars(
    verdicts: pd.DataFrame,
) -> tuple[list[ExemplarRecord], list[ExemplarRecord]]:
    """Production's selection: 8 confident keeps and 4 drops, as ``_read_exemplars`` does."""
    kept = verdicts[
        (verdicts["kept"] == 1) & (verdicts["confidence_1"] >= CONFIDENT_FLOOR)
    ]
    dropped = verdicts[verdicts["kept"] == 0]

    def records(frame: pd.DataFrame, n: int) -> list[ExemplarRecord]:
        frame = frame.sort_values("confidence_1", ascending=False).head(n)
        return [
            ExemplarRecord(
                tss_id=str(row["doc_id"]),
                title=str(row["title"]),
                abstract=(str(row["abstract_or_summary"]) or None)
                if isinstance(row["abstract_or_summary"], str)
                else None,
                screen_confidence=float(row["confidence_1"]),
            )
            for _, row in frame.iterrows()
        ]

    return records(kept, POS_EXEMPLARS), records(dropped, NEG_EXEMPLARS)


def reformulated_queries(
    backend: OpenAISearchGenerationBackend,
    *,
    intent: str,
    positive: list[ExemplarRecord],
    negative: list[ExemplarRecord],
    model: str,
) -> list[str]:
    """One reformulation call, cached by intent, exemplar ids and model."""
    key = hashlib.sha256(
        json.dumps(
            [intent, [e.tss_id for e in positive], [e.tss_id for e in negative], model]
        ).encode()
    ).hexdigest()[:16]
    path = cache_path("reformulate", key)
    if path.exists():
        return json.loads(path.read_text())["queries"]
    wire, _usage = backend.reformulate(
        ReformulatePayload(
            intent=intent, round_index=2, positive=positive, negative=negative
        )
    )
    queries, _paraphrases = validated_queries(wire)
    queries = queries[:QUERY_CAP]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"queries": queries, "model": model}))
    return queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=MINI_DATASET)
    parser.add_argument("--verdicts", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--expand", type=int, default=200)
    parser.add_argument("--forward", type=int, default=200)
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    search_generation.SEARCH_QUERIES_MODEL = args.model
    search_generation.SEARCH_REFORMULATE_MODEL = args.model
    prompt_sha = override_prompt("shared+semantic", None)
    out = args.out / f"{date.today().isoformat()}-reformulate-{args.model}"
    out.mkdir(parents=True, exist_ok=True)
    get = make_getter(SEED_ARM)
    backend = OpenAISearchGenerationBackend()

    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    items = select_items(list(client.get_dataset(args.dataset).items), args.reviews)

    rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    for item in items:
        title = item.metadata.get("review_title", str(item.id))
        intent, cutoff = item.input["intent"], item.input["published_before"]
        ground_truth = ground_truth_from_item(item)
        verdict_path = args.verdicts / f"{slug(title)}.csv"
        if not verdict_path.exists():
            print(f"{title[:60]}: no verdicts, skipped")
            continue
        positive, negative = exemplars(pd.read_csv(verdict_path))
        payload, _cached = load_or_expand(
            item_id=str(item.id),
            intent=intent,
            cutoff=cutoff,
            n_seeds=args.seeds,
            n_expand=args.expand,
            refresh=False,
            get=get,
            source="shared+semantic",
            prompt_sha=prompt_sha,
            forward=args.forward,
            forward_pages=10,
            forward_max_cites=300,
            forward_top=20,
        )
        pool = candidates(payload)
        pool_keys = {r["doi"] for r in pool if r["doi"]}
        counts = payload["counts"]

        queries = reformulated_queries(
            backend,
            intent=intent,
            positive=positive,
            negative=negative,
            model=args.model,
        )
        new_hits: dict[str, int] = {}
        for query in queries:
            page = query_page(
                query, cutoff=cutoff, per_call=PER_CALL_DEFAULT, get=get, refresh=False
            )
            dois = {
                normalize_doi(r.get("doi")) for r in page["results"] if r.get("doi")
            }
            hits = dois & ground_truth.keys
            fresh = hits - pool_keys
            for record in page["results"]:
                doi = normalize_doi(record.get("doi"))
                if doi in fresh:
                    sid = (record.get("id") or "").rsplit("/", 1)[-1]
                    new_hits[doi] = counts.get(sid, 0)
            query_rows.append(
                {
                    "review": title,
                    "query": query,
                    "ok": page["ok"],
                    "n_results": len(page["results"]),
                    "gt_hits": len(hits),
                    "gt_hits_new": len(fresh),
                }
            )
        n_gt = len(ground_truth.keys)
        rows.append(
            {
                "review": title,
                "n_gt": n_gt,
                "pool_hits": len(pool_keys & ground_truth.keys),
                "pool_recall": len(pool_keys & ground_truth.keys) / n_gt if n_gt else 0,
                "n_queries": len(queries),
                "new_hits": len(new_hits),
                "new_hits_cited_by_a_seed": sum(1 for c in new_hits.values() if c >= 1),
                "new_hits_cited_by_2_seeds": sum(
                    1 for c in new_hits.values() if c >= 2
                ),
                "recall_gain_ceiling": len(new_hits) / n_gt if n_gt else 0,
                "n_positive_exemplars": len(positive),
                "n_negative_exemplars": len(negative),
            }
        )
        print(
            f"{title[:60]}: pool {rows[-1]['pool_hits']}/{n_gt}, reformulated queries add "
            f"{len(new_hits)} new ({rows[-1]['new_hits_cited_by_a_seed']} cited by a seed)"
        )

    for name, data in (("scores.csv", rows), ("queries.csv", query_rows)):
        with (out / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    n = len(rows)
    print(
        f"\n{n} reviews -> {out}\n"
        f"pool recall {sum(r['pool_recall'] for r in rows) / n:.1%}; "
        f"reformulation adds {sum(r['new_hits'] for r in rows)} new ground-truth papers "
        f"(+{sum(r['recall_gain_ceiling'] for r in rows) / n:.1%} recall at the ceiling), "
        f"{sum(r['new_hits_cited_by_a_seed'] for r in rows)} of them cited by at least one seed"
    )


if __name__ == "__main__":
    main()
