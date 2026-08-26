"""Build a batch ground-truth corpus from an OpenAlex OQL query.

Discovers recent, well-cited, open-access systematic/rapid-evidence reviews
via OpenAlex, then builds each one's reference-list ground truth via the
existing DOI path (``ground_truth.build_ground_truth_from_doi`` — every OQL
candidate already has a DOI, so no full-text fetch or LLM extraction is
needed here; that path stays reserved for grey-literature reviews with no
DOI, as in ``run_and_score.py --url`` mode).

The OQL query this corpus is built from:

    works where title/abstract has (systematic review and policy)
      and year > (2022)
      and title has (
        systematic review
        or rapid evidence
        or evidence assessment
        or evidence review
      )
      and citation count > (50)
      and open access is (true)

Hand-translated below to OpenAlex's own ``filter=`` REST syntax (verified
live against api.openalex.org, whose own debug ``x_query.oql`` field echoes
it back as equivalent) — this is one concrete query, not a general OQL
parser (OpenAlex has its own LLM-backed one server-side for that).

Usage (no DB/OPENAI_API_KEY needed — this is pure OpenAlex metadata):

```
    uv run --project backend python scripts/eval_ground_truth/fetch_review_corpus.py \\
        --limit 15
        
```
The limit is set to 15 by default to keep costs low - for each systematic review, we run 
the full Policy Atlas search & screen processes, i.e. using LLM calls to screen search 
results for relevance. Ideally we would also like to:
- do repeats of this process and average results, in order to account for LLM stochasticity a bit 
    (rather than just doing 1 run per systematic review) 
- to get a proxy for precision, add an extra LLM-as-judge that judges relevance and is blind to whether
    the result was in the ground truth or not. This would be a lot of extra LLM calls, so we are 
    not doing it for now, but it is a good idea for future work.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ground_truth import build_ground_truth_from_doi, decode_abstract, normalize_doi, openalex_get

OPENALEX_HOST = "https://api.openalex.org"

QUERY_FILTER = (
    'title_and_abstract.search:"systematic review" AND policy,'
    'title.search:"systematic review" OR "rapid evidence" OR "evidence assessment" OR "evidence review",'
    "publication_year:>2022,cited_by_count:>50,is_oa:true"
)
_SELECT = "id,doi,title,publication_date,abstract_inverted_index,cited_by_count,referenced_works"
_PER_PAGE_CAP = 200


def fetch_candidates(limit: int) -> list[dict[str, Any]]:
    """Top-``limit`` OQL candidates by citation count, most-cited first."""
    resp = openalex_get(
        "/works",
        filter=QUERY_FILTER,
        select=_SELECT,
        sort="cited_by_count:desc",
        per_page=str(min(limit, _PER_PAGE_CAP)),
    )
    resp.raise_for_status()
    return resp.json().get("results", [])[:limit]


def build_corpus(limit: int) -> dict[str, Any]:
    candidates = fetch_candidates(limit)
    reviews: list[dict[str, Any]] = []
    n_skipped_no_doi = 0
    n_errored = 0

    for work in candidates:
        doi = normalize_doi(work.get("doi"))
        title = work.get("title") or "(untitled)"
        if not doi:
            print(f"  skip (no DOI): {title}")
            n_skipped_no_doi += 1
            continue
        try:
            gt = build_ground_truth_from_doi(doi, work=work)
        except Exception as exc:  # noqa: BLE001 - one bad review must not abort the batch
            print(f"  error building ground truth for {doi} ({title}): {exc}")
            n_errored += 1
            continue
        print(f"  {title} — {len(gt.dois)} reference DOIs, {gt.resolvable_fraction:.0%} OpenAlex-resolvable")
        reviews.append(
            {
                "title": title,
                "doi": doi,
                "publication_date": work.get("publication_date"),
                "abstract": decode_abstract(work),
                "ground_truth": {
                    "dois": sorted(gt.dois),
                    "resolvable_fraction": gt.resolvable_fraction,
                    "n_unresolved": len(gt.unresolved),
                },
            }
        )
        time.sleep(0.1)  # polite pacing across the OpenAlex calls build_ground_truth_from_doi makes

    print(
        f"\nBuilt corpus: {len(reviews)} reviews "
        f"({n_skipped_no_doi} skipped for no DOI, {n_errored} errored)"
    )
    return {
        "query_filter": QUERY_FILTER,
        "generated_at": datetime.now(UTC).isoformat(),
        "reviews": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=15, help="Top-N candidates by citation count (default 15).")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "results" / "corpus.json",
        help="Output path for the corpus JSON (default results/corpus.json).",
    )
    args = parser.parse_args()

    print(f"Fetching top {args.limit} OQL candidates from OpenAlex...")
    corpus = build_corpus(args.limit)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, indent=2))
    print(f"Wrote corpus to {args.out}")


if __name__ == "__main__":
    main()
