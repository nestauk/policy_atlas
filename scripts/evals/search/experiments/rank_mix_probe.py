"""Try other orderings of the paper pool on one question, offline, and see where a
few named papers land.

The production search ranks the paper pool by one score, "specificity" (citation
links to the seed set, damped by the paper's global citation count), then cuts
at the scope's cap. This script runs the real search once (OpenAlex only, no
screening, database writes rolled back), captures the pool and every query's
result list, and then re-orders the same pool five ways:

* ``baseline``  — production order.
* ``reserve``   — the first 50 keyword results in their own order, then the rest in
                  production order (deferred seam D6, "relevance reserve").
* ``hits``      — most distinct queries returning the paper first, then specificity.
* ``rrf``       — reciprocal rank fusion over every keyword and semantic result list
                  (Cormack, Clarke and Buettcher 2009), then specificity for papers
                  no query returned.
* ``mix``       — the production order since task 052 (``pool.rank_mix``): round-robin
                  over three strata: relevant (rank fusion over every query list plus
                  the pool ordered by "cites the seeds", counted three times), seminal
                  (most cited by the seed set, then globally), novel (last five years,
                  fused ones first). Guarantees a mix at every cut. Called here so the
                  script checks the shipped code.
* ``mix_q``     — the same with the "cites the seeds" order left out of the fusion
                  (``coupling_lists=0``): what shipped first on 2026-10-12.
* ``mix_f1``    — the same with that order counted once (``coupling_lists=1``).
* ``mix_c``     — an earlier try: "cites the seeds" added to the relevant score
                  outside the fusion, each part scaled to 0..1. Kept for the record.
* ``blend``     — one score: rrf and specificity each scaled to 0..1 and added.

Every ordering first drops duplicate copies of a paper (OpenAlex often holds a
preprint and the journal copy): same title and same authors, the more-cited copy
kept (``pool.dedupe_papers``).

It does not score against ground truth. It reports where named probe papers rank
and what the top of each ordering looks like.

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/rank_mix_probe.py \\
        "QUESTION" OUT_PREFIX [--depth rapid] [--probe "Title" ...]

The captured pool is saved as ``OUT_PREFIX.pool.json`` (ids, titles, years, author
names and the graph signals; no abstracts) and reused on the next run, so a new
ordering can be tried without a new search. Delete it to search again.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "checks"))
import _bootstrap  # noqa: E402,F401
from engine import (  # noqa: E402
    GENERATION_BACKENDS,
    _RecordingBackend,
    _seed_run,
    _seed_scope,
    _seed_task,
)

from policy_atlas.core import tracing  # noqa: E402
from policy_atlas.core.db import get_engine  # noqa: E402
from policy_atlas.evidence_search.sourcing import pool, search_loop  # noqa: E402
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext  # noqa: E402
from policy_atlas.evidence_search.sourcing.search_live import live_search_backends  # noqa: E402

RESERVE = 50
HITS: dict[str, int] = {}
RRF: dict[str, float] = {}
REL: dict[str, float] = {}
RRF_K = 60
NOVEL_FROM_YEAR = 2020
TOP = 100
DEFAULT_PROBES = [
    "Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks",
    "Neuronal avalanches in neocortical circuits",
    "Being critical of criticality in the brain",
    "Avalanches and edge-of-chaos learning in neuromorphic nanowire networks",
    "Neuronal avalanches imply maximum dynamic range in cortical networks at criticality",
]


def resolve_probe(title: str) -> tuple[str, str] | None:
    """Look a probe paper up by title on OpenAlex; return (short id, title)."""
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {
            "search": pool.normalised_title(title),
            "select": "id,display_name",
            "per-page": 1,
        }
    )
    for attempt in range(
        3
    ):  # the lookup is one small call; OpenAlex sometimes answers 429
        try:
            with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
                results = json.load(response)["results"]
            break
        except urllib.error.HTTPError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    if not results:
        return None
    return pool.short_id(results[0]["id"]) or "", results[0]["display_name"]


def run_search_capturing(
    question: str, depth: str
) -> tuple[list[Any], list[dict[str, Any]]]:
    captured: dict[str, list[Any]] = {}
    real_rank = pool.rank_papers

    def spy(cands: list[Any]) -> list[Any]:
        captured["cands"] = list(cands)
        return real_rank(cands)

    search_loop.pool.rank_papers = spy
    client = tracing.get_langfuse()
    engine = get_engine()
    calls: list[dict[str, Any]] = []
    lock = threading.Lock()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            task_id = _seed_task(conn)
            scope_id = _seed_scope(conn, task_id, question)
            backends = [
                _RecordingBackend(b, calls, client, lock=lock)
                for b in live_search_backends()
                if b.name == "openalex"
            ]
            search_loop.run_search(
                conn,
                task_id=task_id,
                run_id=_seed_run(conn, task_id),
                context=AcquireContext(
                    scope_id=scope_id,
                    intent=question,
                    context={"search": {"depth": depth, "filters": {}}},
                ),
                backends=backends,
                generation_backend=GENERATION_BACKENDS["shared"](
                    langfuse_client=client
                ),
            )
        finally:
            trans.rollback()  # scaffolding only, never kept
    tracing.flush(client)
    return captured["cands"], calls


def slim(record: dict[str, Any]) -> dict[str, Any]:
    """Keep only the record fields the orderings read: no abstract, no locations."""
    return {
        "id": record.get("id"),
        "doi": record.get("doi"),
        "display_name": record.get("display_name"),
        "publication_year": record.get("publication_year"),
        "cited_by_count": record.get("cited_by_count"),
        "authorships": [
            {"author": {"display_name": (a.get("author") or {}).get("display_name")}}
            for a in record.get("authorships") or []
        ],
    }


def orderings(cands: list[Any], calls: list[dict[str, Any]]) -> dict[str, list[Any]]:
    cands = pool.dedupe_papers(cands)
    by_id = {c.openalex_id: c for c in cands if c.openalex_id}
    query_calls = [c for c in calls if c["method"] in ("search", "search_semantic")]
    keyword_lists = [c["records"] for c in query_calls if c["method"] == "search"]
    hits: dict[str, set[int]] = defaultdict(set)
    rrf: dict[str, float] = defaultdict(float)
    for index, call in enumerate(query_calls):
        for rank, record in enumerate(call["records"] or []):
            work_id = pool.record_short_id(record)
            if work_id in by_id:
                hits[work_id].add(index)
                rrf[work_id] += 1.0 / (RRF_K + rank + 1)
    for c in cands:
        HITS[c.openalex_id] = len(hits.get(c.openalex_id, ()))
        RRF[c.openalex_id] = round(rrf.get(c.openalex_id, 0.0), 5)

    baseline = pool.rank_papers(cands)
    reserve_ids = [
        pool.record_short_id(r)
        for r in pool.interleave(keyword_lists, pool.record_short_id)
    ]
    reserve_ids = [i for i in reserve_ids if i in by_id][:RESERVE]
    reserve = [by_id[i] for i in reserve_ids] + [
        c for c in baseline if c.openalex_id not in set(reserve_ids)
    ]
    hits_order = sorted(baseline, key=lambda c: (-HITS[c.openalex_id], -c.specificity))
    rrf_order = sorted(baseline, key=lambda c: (-RRF[c.openalex_id], -c.specificity))

    seminal = sorted(baseline, key=lambda c: (-c.inset, -c.cited_by_count))
    novel = [
        c
        for c in rrf_order
        if (c.record.get("publication_year") or 0) >= NOVEL_FROM_YEAR
        and HITS[c.openalex_id] > 0
    ]
    novel += [
        c
        for c in baseline
        if (c.record.get("publication_year") or 0) >= NOVEL_FROM_YEAR
        and HITS[c.openalex_id] == 0
    ]

    def round_robin(strata: list[list[Any]], slots: list[int]) -> list[Any]:
        out: list[Any] = []
        seen: set[str] = set()
        cursors = [iter(s) for s in strata]
        exhausted = [False] * len(strata)
        while not all(exhausted):
            for i, cursor in enumerate(cursors):
                if exhausted[i]:
                    continue
                taken = 0
                for c in cursor:
                    if c.openalex_id not in seen:
                        seen.add(c.openalex_id)
                        out.append(c)
                        taken += 1
                        if taken == slots[i]:
                            break
                else:
                    exhausted[i] = True
        return out + [c for c in baseline if c.openalex_id not in seen]

    # mix_c: the relevant stratum also credits "cites the seeds" (weighted coupling),
    # each part scaled to 0..1; papers no query returned enter it when they couple.
    max_rrf_c = max(RRF.values()) or 1.0
    max_wc = max(c.wcoupling for c in cands) or 1.0
    for c in cands:
        REL[c.openalex_id] = round(
            RRF[c.openalex_id] / max_rrf_c + c.wcoupling / max_wc, 4
        )
    relevant_c = sorted(
        (c for c in baseline if REL[c.openalex_id] > 0),
        key=lambda c: -REL[c.openalex_id],
    )
    novel_c = [
        c
        for c in relevant_c
        if (c.record.get("publication_year") or 0) >= NOVEL_FROM_YEAR
    ]
    novel_c += [c for c in novel if c not in novel_c]
    mix_c = round_robin([relevant_c, seminal, novel_c], [1, 1, 1])
    query_lists = [c["records"] for c in query_calls]
    mixes = {
        name: pool.rank_mix(
            cands, query_lists, novel_from_year=NOVEL_FROM_YEAR, coupling_lists=w
        )
        for name, w in (("mix_q", 0), ("mix_f1", 1), ("mix", pool.COUPLING_LISTS))
    }
    max_rrf = max(RRF.values()) or 1.0
    max_spec = max(c.specificity for c in cands) or 1.0
    blend = sorted(
        baseline,
        key=lambda c: -(RRF[c.openalex_id] / max_rrf + c.specificity / max_spec),
    )
    return {
        "baseline": baseline,
        "reserve": reserve,
        "hits": hits_order,
        "rrf": rrf_order,
        "blend": blend,
        "mix_c": mix_c,
        **mixes,
    }


def describe(order: list[Any]) -> dict[str, Any]:
    top = order[:TOP]
    years = [c.record.get("publication_year") or 0 for c in top]
    origins: dict[str, int] = defaultdict(int)
    for c in top:
        origins[c.origin] += 1
    return {
        "origins": dict(origins),
        "median_year": statistics.median(years),
        "share_from_2020": round(
            sum(y >= NOVEL_FROM_YEAR for y in years) / len(top), 2
        ),
        "median_cited_by": statistics.median(c.cited_by_count for c in top),
        "share_two_plus_queries": round(
            sum(HITS[c.openalex_id] >= 2 for c in top) / len(top), 2
        ),
        "share_no_query": round(
            sum(HITS[c.openalex_id] == 0 for c in top) / len(top), 2
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out_prefix")
    parser.add_argument("--depth", default="rapid")
    parser.add_argument("--probe", action="append", default=None)
    args = parser.parse_args()
    cache = Path(args.out_prefix).with_suffix(".pool.json")
    if cache.exists():
        saved = json.loads(cache.read_text())
        cands = [pool.PaperCandidate(**c) for c in saved["cands"]]
        calls = saved["calls"]
        print(f"reusing the captured pool in {cache}")
    else:
        cands, calls = run_search_capturing(args.question, args.depth)
        cache.write_text(
            json.dumps(
                {
                    "cands": [
                        {
                            **{
                                f: getattr(c, f)
                                for f in pool.PaperCandidate.__dataclass_fields__
                            },
                            "record": slim(c.record),
                        }
                        for c in cands
                    ],
                    "calls": [
                        {
                            "method": c["method"],
                            "query": c["query"],
                            "records": [
                                {"id": r.get("id")} for r in c.get("records") or []
                            ],
                        }
                        for c in calls
                    ],
                },
                default=str,
            )
        )
    # A probe is looked up in the pool by title first; the OpenAlex lookup (rate
    # limited without a key) is the fallback for a probe the pool does not hold.
    probes = []
    for text in args.probe or DEFAULT_PROBES:
        key = pool.normalised_title(text)
        matches = [
            c
            for c in cands
            if pool.normalised_title(c.record.get("display_name")).startswith(key)
        ]
        match = max(matches, key=lambda c: c.cited_by_count, default=None)
        if match is not None:
            probes.append(
                (match.openalex_id or "", match.record.get("display_name") or "")
            )
        elif (found := resolve_probe(text)) is not None:
            probes.append(found)
    orders = orderings(cands, calls)
    cap = search_loop.DEPTH_CONSTANTS[args.depth]["papers_cap"]
    position = {
        name: {c.openalex_id: i + 1 for i, c in enumerate(order)}
        for name, order in orders.items()
    }
    baseline_top = {c.openalex_id for c in orders["baseline"][:TOP]}

    lines = [f"# Pool orderings: {args.question}\n"]
    lines.append(
        f"Run {datetime.now(UTC).isoformat(timespec='seconds')}. Depth `{args.depth}`, cap {cap}. "
        f"Pool {len(cands)} papers ({len(pool.dedupe_papers(cands))} distinct papers) from {len([c for c in calls if c['method'] in ('search', 'search_semantic')])} "
        "query calls. No ground truth; this compares orderings of one pool.\n"
    )
    lines.append("## Where the probe papers rank\n")
    lines.append(
        "| paper | " + " | ".join(orders) + " |\n|---|" + "---:|" * len(orders)
    )
    for work_id, title in probes:
        cells = [str(position[n].get(work_id, "—")) for n in orders]
        lines.append(f"| {title[:70]} | " + " | ".join(cells) + " |")
    lines.append(
        f"\nA number at or under {cap} means the paper survives the cut at this scope.\n"
    )
    lines.append(f"## What the top {TOP} looks like\n")
    keys = [
        "median_year",
        "share_from_2020",
        "median_cited_by",
        "share_two_plus_queries",
        "share_no_query",
    ]
    lines.append(
        "| ordering | overlap with baseline | "
        + " | ".join(keys)
        + " | origins |\n|---|---:|"
        + "---:|" * len(keys)
        + "---|"
    )
    for name, order in orders.items():
        d = describe(order)
        overlap = len(baseline_top & {c.openalex_id for c in order[:TOP]})
        lines.append(
            f"| {name} | {overlap} | "
            + " | ".join(str(d[k]) for k in keys)
            + f" | {d['origins']} |"
        )
    for name, order in orders.items():
        lines.append(f"\n## Top 15 under `{name}`\n")
        for i, c in enumerate(order[:15]):
            r = c.record
            lines.append(
                f"{i + 1}. {r.get('publication_year')} · {r.get('display_name')} · cited {c.cited_by_count} · "
                f"queries {HITS[c.openalex_id]} · inset {c.inset} · wcoup {c.wcoupling} · spec {c.specificity} · {c.origin}"
            )
    out = Path(args.out_prefix)
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    out.with_suffix(".json").write_text(
        json.dumps(
            {
                "question": args.question,
                "depth": args.depth,
                "probes": probes,
                "orderings": {
                    name: [
                        {
                            "id": c.openalex_id,
                            "title": c.record.get("display_name"),
                            "year": c.record.get("publication_year"),
                            "cited_by": c.cited_by_count,
                            "queries": HITS[c.openalex_id],
                            "inset": c.inset,
                            "specificity": c.specificity,
                            "rrf": RRF[c.openalex_id],
                            "wcoupling": c.wcoupling,
                            "rel_c": REL.get(c.openalex_id),
                            "origin": c.origin,
                        }
                        for c in order[:TOP]
                    ]
                    for name, order in orders.items()
                },
            },
            indent=1,
        )
    )
    print("\n".join(lines[: 12 + len(probes)]))


if __name__ == "__main__":
    main()
