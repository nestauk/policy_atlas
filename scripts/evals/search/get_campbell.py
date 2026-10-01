"""Campbell Collaboration reviews -> ground-truth CSVs.

Campbell Systematic Reviews is a journal of social-policy reviews (crime,
education, social welfare, international development). This script lists every
work in that journal through OpenAlex, keeps the ones that look like finished
reviews with a long enough reference list, resolves each cited work to its DOI,
and writes the two CSVs that ``ground_truth_dataset.py`` reads:

* ``results/ground_truth/campbell_reviews.csv`` — one row per review. The
  ``title`` becomes the search intent; ``doi`` identifies the review;
  ``published_before`` is one month before publication, as for the four
  original reviews.
* ``results/ground_truth/campbell_references.csv`` — one row per cited work.
  The ``label`` column is left EMPTY: a reference list mixes the studies the
  review is about with background and methods citations, and only a labelling
  pass (see the ``policy_atlas_gt_labelling`` repo) can tell them apart. Until
  then ``ground_truth_dataset.py`` counts none of these rows.

Raw OpenAlex responses are kept under ``results/ground_truth/raw/campbell/`` and
reused on the next run, so re-running after a code change makes no API calls.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/get_campbell.py [--min-refs 30] [--refresh]
"""

from __future__ import annotations

import argparse
from typing import Any

from ground_truth import (
    NOT_A_REVIEW_TITLE_RE,
    RAW_DIR,
    cached_json,
    months_earlier,
    normalize_doi,
    openalex_get,
    resolve_openalex_works_cached,
    write_ground_truth,
)

SOURCE_ID = "S2739193000"  # OpenAlex id of the journal "Campbell Systematic Reviews"
RAW = RAW_DIR / "campbell"


def list_campbell_works() -> list[dict[str, Any]]:
    """Every work OpenAlex files under the Campbell journal, with its reference ids."""
    works: list[dict[str, Any]] = []
    cursor = "*"
    while cursor:
        resp = openalex_get(
            "/works",
            filter=f"primary_location.source.id:{SOURCE_ID}",
            select="id,doi,title,type,publication_date,publication_year,referenced_works,referenced_works_count",
            cursor=cursor,
            **{"per-page": "200"},
        )
        resp.raise_for_status()
        data = resp.json()
        works.extend(data["results"])
        cursor = data["meta"].get("next_cursor")
    return works


def select_reviews(works: list[dict[str, Any]], min_refs: int) -> list[dict[str, Any]]:
    """Finished reviews with a DOI, a publication date and at least ``min_refs`` references.

    Protocols, errata and the like are dropped by title. A later work with the
    same title as an earlier one (an updated review) is dropped too, because the
    review title is the join key between the two CSVs.
    """
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for work in sorted(works, key=lambda w: (w.get("publication_date") or "", w["id"])):
        title = (work.get("title") or "").strip()
        if (
            not title
            or not work.get("doi")
            or not work.get("publication_date")
            or (work.get("referenced_works_count") or 0) < min_refs
            or NOT_A_REVIEW_TITLE_RE.match(title)
            or title.lower() in seen
        ):
            continue
        seen.add(title.lower())
        kept.append(work)
    return kept


def build_rows(
    reviews: list[dict[str, Any]], resolved: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Shape the two CSVs. ``resolved`` maps a referenced-work id to its OpenAlex record."""
    review_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    for work in reviews:
        title = work["title"].strip()
        refs = [resolved.get(wid.rsplit("/", 1)[-1]) for wid in work.get("referenced_works", [])]
        refs = [r for r in refs if r]
        for ref in refs:
            reference_rows.append(
                {
                    "review_title": title,
                    "ref_title": ref.get("title") or "",
                    "label": "",
                    "doi": normalize_doi(ref.get("doi")) or "",
                    "overton_id": "",
                    "url": "",
                    "year": ref.get("publication_year") or "",
                    "ref_id": ref["id"].rsplit("/", 1)[-1],
                }
            )
        review_rows.append(
            {
                "title": title,
                "doi": normalize_doi(work["doi"]),
                "url": "",
                "published_before": months_earlier(work["publication_date"], 1),
                "exclude": "",
                "dataset": "campbell",
                "review_id": work["id"].rsplit("/", 1)[-1],
                "level": "review",
                "n_references": len(refs),
                "n_with_doi": sum(1 for r in refs if r.get("doi")),
                "research_questions": "",
            }
        )
    return review_rows, reference_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-refs", type=int, default=30, help="Keep reviews with at least this many references (default 30).")
    parser.add_argument("--refresh", action="store_true", help="Ignore the raw cache and call OpenAlex again.")
    args = parser.parse_args()

    works = cached_json(RAW / "works.json", list_campbell_works, args.refresh)
    reviews = select_reviews(works, args.min_refs)
    print(f"{len(works)} Campbell works in OpenAlex, {len(reviews)} kept as reviews with >= {args.min_refs} references")
    ref_ids = [wid for w in reviews for wid in w.get("referenced_works", [])]
    resolved = resolve_openalex_works_cached(RAW / "referenced_works.json", ref_ids, args.refresh)
    write_ground_truth("campbell", *build_rows(reviews, resolved))


if __name__ == "__main__":
    main()
