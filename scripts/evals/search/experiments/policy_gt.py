"""A quick policy-document ground truth from UK government strategies (R&D, task 049).

The paper ground truth (reference lists of systematic reviews, keyed by DOI) holds no
policy documents, so nothing in it can say whether a policy-document ranking is good.
This script builds a small second instrument from Overton itself:

1. **Survey**: gov.uk government documents whose title reads like a strategy, plan,
   white or green paper or evidence review, sorted by how often policy documents cite
   them (six fixed queries, two pages each, cached).
2. **Select**: keep documents with at least 20 references in Overton's data and at
   least 10 cited *policy* documents, drop budgets, statistics reviews and appraisal
   guides by a fixed title rule, take the 15 with the most cited policy documents.
3. **Target**: for each, the policy documents it cites (``cites.policy``, Overton ids)
   and the papers it cites (``cites.scholarly``, DOIs). The intent is the title with
   its report-type tail removed; the cutoff is the document's own date, so it and
   anything later cannot count.
4. **Score**: run the ``policy_rank.py`` build for each intent and score every document
   order on the policy target at the first 25, 50 and 100 documents and over all; paper
   recall over the cited papers of all documents, for information.

Read the caveats in the task-049 write-up before quoting a number: every target is in
Overton by construction, the references of a strategy are selective and skew to the
department's own earlier documents, and the policy snowball is favoured by design.
Relative comparisons between orders are the use; the absolute level is not.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/policy_gt.py [--n 15] [--docs 200] \\
        [--landmarks 15] [--forward 10] [--forward-new 15]

About 12 calls for the survey and 45 per strategy, cached under
``results/cache/overton-policy/``. Uploads nothing.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR
from evals_search_utils import normalize_doi
from overton_recall import get
from policy_rank import RANKINGS, cached_build, order

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "overton" / "policy_gt"
SPECIFIC_CSV = (
    Path(__file__).resolve().parents[1] / "ground_truth" / "policy_gt_specific.csv"
)
# Committed snapshot of the targets (strategy date, cited policy ids, cited DOIs) so the
# numbers can be reproduced after Overton's data moves on. Written on first use.
SPECIFIC_TARGETS = SPECIFIC_CSV.with_name("policy_gt_specific_targets.json")


def slim_target(doc_id: str) -> dict[str, Any]:
    """One document's target lists fetched by id, for a CSV row the survey cache lacks."""
    raw = get("documents.php", policy_document_id=doc_id, pp="1")["results"][0]
    cites = raw.get("cites") or {}
    return {
        "id": doc_id,
        "title": raw.get("title") or "",
        "published_on": raw.get("published_on"),
        "citation_count": raw.get("citation_count") or 0,
        "policy_ids": sorted(
            {p["overton_id"] for p in cites.get("policy") or [] if p.get("overton_id")}
        ),
        "dois": sorted(
            {
                d
                for d in (
                    normalize_doi(w.get("doi")) for w in cites.get("scholarly") or []
                )
                if d
            }
        ),
    }


SURVEY_QUERIES = (
    '"strategy"',
    '"national strategy"',
    '"action plan"',
    '"white paper"',
    '"green paper"',
    '"evidence review"',
)
EXCLUDE = re.compile(
    r"budget|statistics|green book|research excellence|strategic environmental|"
    r"spending review|documents$",
    re.I,
)
TAIL = re.compile(
    r"\s*[:\-–]\s*(final report|interim report|an? (overview|evidence review|"
    r"cross-government strategy)|chapter \d+|.*independent (panel )?review.*|"
    r"documents)$",
    re.I,
)


def survey() -> list[dict[str, Any]]:
    path = CACHE_DIR / "overton-policy" / "survey-govuk.json"
    if path.exists():
        return json.loads(path.read_text())
    seen: dict[str, dict[str, Any]] = {}
    for query in SURVEY_QUERIES:
        for page in ("1", "2"):
            body = get(
                "documents.php",
                query=query,
                source="govuk",
                source_type="government",
                sort="citations",
                published_after="2012-01-01",
                pp="50",
                page=page,
            )
            for raw in body.get("results") or []:
                cites = raw.get("cites") or {}
                seen[raw["policy_document_id"]] = {
                    "id": raw["policy_document_id"],
                    "title": raw.get("title") or "",
                    "published_on": raw.get("published_on"),
                    "citation_count": raw.get("citation_count") or 0,
                    "policy_ids": sorted(
                        {
                            p["overton_id"]
                            for p in cites.get("policy") or []
                            if p.get("overton_id")
                        }
                    ),
                    "dois": sorted(
                        {
                            d
                            for d in (
                                normalize_doi(w.get("doi"))
                                for w in cites.get("scholarly") or []
                            )
                            if d
                        }
                    ),
                }
    rows = list(seen.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows))
    return rows


def select(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    keep = [
        r
        for r in rows
        if len(r["policy_ids"]) >= 10
        and len(r["policy_ids"]) + len(r["dois"]) >= 20
        and not EXCLUDE.search(r["title"])
    ]
    keep.sort(key=lambda r: (-len(r["policy_ids"]), r["id"]))
    return keep[:n]


def intent_of(title: str) -> str:
    return TAIL.sub("", title).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n", type=int, default=15)
    parser.add_argument("--docs", type=int, default=200)
    parser.add_argument("--landmarks", type=int, default=15)
    parser.add_argument("--forward", type=int, default=10)
    parser.add_argument("--forward-new", type=int, default=15)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--set",
        choices=["omnibus", "specific"],
        default="omnibus",
        help="omnibus: the 15 most-citing strategies by rule; specific: the hand-picked "
        "topic-specific documents and questions in ground_truth/policy_gt_specific.csv",
    )
    parser.add_argument(
        "--paraphrases",
        action="store_true",
        help="search intent plus generated paraphrases",
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
    rows_survey = survey()
    if args.set == "specific":
        snapshot = (
            {s["id"]: s for s in json.loads(SPECIFIC_TARGETS.read_text())["targets"]}
            if SPECIFIC_TARGETS.exists()
            else {}
        )
        by_id = {r["id"]: r for r in rows_survey}
        strategies = []
        with SPECIFIC_CSV.open() as fh:
            for r in csv.DictReader(fh):
                if r["id"] in snapshot:
                    s = dict(snapshot[r["id"]])
                else:
                    s = (
                        dict(by_id[r["id"]])
                        if r["id"] in by_id
                        else slim_target(r["id"])
                    )
                s["intent"] = r["intent"]
                strategies.append(s)
        if not SPECIFIC_TARGETS.exists():
            keys = (
                "id",
                "title",
                "published_on",
                "citation_count",
                "policy_ids",
                "dois",
            )
            SPECIFIC_TARGETS.write_text(
                json.dumps(
                    {
                        "fetched_on": date.today().isoformat(),
                        "targets": [{k: s[k] for k in keys} for s in strategies],
                    },
                    indent=1,
                )
            )
        args.out = args.out.parent / (
            "policy_gt_specific"
            + (f"-{args.source_country}" if args.source_country else "")
        )
    else:
        strategies = select(rows_survey, args.n)
        for s in strategies:
            s["intent"] = intent_of(s["title"])
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "strategies.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["id", "published_on", "n_policy_refs", "n_dois", "intent", "title"]
        )
        for s in strategies:
            writer.writerow(
                [
                    s["id"],
                    s["published_on"],
                    len(s["policy_ids"]),
                    len(s["dois"]),
                    s["intent"],
                    s["title"],
                ]
            )

    caps = [25, 50, 100, 200]
    rows: list[dict[str, Any]] = []
    for s in strategies:
        intent, cutoff = s["intent"], s["published_on"]
        target = set(s["policy_ids"])
        payload = cached_build(
            f"gt|{s['id']}|{intent}|{cutoff}|{knobs}",
            intent=intent,
            cutoff=cutoff,
            exclude_ids=frozenset({s["id"]}),  # held out before any signal is computed
            **knobs,
        )
        docs = [d for d in payload["docs"] if d["id"] != s["id"]]
        in_pool = {d["id"] for d in docs} & target
        all_dois = {p for d in docs for p in d["cites_scholarly"]}
        for how in RANKINGS:
            ranked = order(docs, how)
            row: dict[str, Any] = {
                "strategy": s["title"][:50],
                "ranking": how,
                "n_target_policy": len(target),
                "n_target_dois": len(s["dois"]),
                "pool_ceiling": len(in_pool) / len(target),
            }
            for cap in caps:
                row[f"policy_recall@{cap}"] = len(
                    {d["id"] for d in ranked[:cap]} & target
                ) / len(target)
            row["paper_recall@all"] = (
                len(all_dois & set(s["dois"])) / len(s["dois"]) if s["dois"] else 0.0
            )
            rows.append(row)
        print(
            f"{s['title'][:55]:55} target {len(target):3} in pool {len(in_pool):3} "
            f"docs {len(docs)}  relevance@25 {rows[-6]['policy_recall@25']:.0%}  "
            f"inset@25 {rows[-5]['policy_recall@25']:.0%}  combined@25 {rows[-1]['policy_recall@25']:.0%}"
        )

    with (args.out / "scores.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nPolicy recall, mean over {len(strategies)} strategies:")
    print("| order | @25 | @50 | @100 | @200 | pool ceiling |")
    print("|---|---:|---:|---:|---:|---:|")
    for how in RANKINGS:
        sub = [r for r in rows if r["ranking"] == how]
        cells = [
            f"{sum(r[f'policy_recall@{c}'] for r in sub) / len(sub):.1%}" for c in caps
        ]
        print(
            f"| {how} | "
            + " | ".join(cells)
            + f" | {sum(r['pool_ceiling'] for r in sub) / len(sub):.1%} |"
        )
    print(f"\nwrote {args.out / 'scores.csv'}")


if __name__ == "__main__":
    main()
