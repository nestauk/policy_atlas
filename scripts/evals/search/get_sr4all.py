"""Webis-SR4ALL-26 corpus -> ground-truth CSVs.

SR4ALL is a Zenodo release (doi 10.5281/zenodo.18431942, CC BY 4.0) of about
300,000 systematic reviews found in OpenAlex, one JSON object per line, 1.6 GB.
Each record carries the review's OpenAlex id, DOI, title, discipline
(``field``), the OpenAlex ids of the works it cites (``referenced_works``) and,
for the quarter with parsed full text, the research questions the authors
stated. This script never loads the file into memory: it streams it line by
line and keeps only the records that pass the filter.

Download ``sr4all_full.jsonl`` from Zenodo by hand into
``results/ground_truth/raw/`` first. Then:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/get_sr4all.py [--limit 100] [--min-refs 30] [--fields ...]

The filter keeps English reviews with a DOI, at least one stated research
question, ``--min-refs`` or more references, a title that is not a protocol,
and a ``field`` in ``--fields`` (default: the four social-science fields). The
``--limit`` most-cited survivors are kept, so the selection is repeatable.

Output shape is the same as ``get_campbell.py``: cited works resolved to DOIs
through OpenAlex, ``label`` left EMPTY until a labelling pass separates the
studies a review is about from its background citations. The review's stated
research questions are carried in the ``research_questions`` column, joined by
" | ", for a future eval that starts from a question rather than a title.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ground_truth import (
    NOT_A_REVIEW_TITLE_RE,
    RAW_DIR,
    cached_json,
    months_earlier,
    normalize_doi,
    resolve_openalex_works_cached,
    write_ground_truth,
)

CORPUS = RAW_DIR / "sr4all_full.jsonl"
SELECTED = RAW_DIR / "sr4all" / "selected.json"
DEFAULT_FIELDS = (
    "Social Sciences",
    "Psychology",
    "Economics, Econometrics and Finance",
    "Business, Management and Accounting",
)
KEEP_KEYS = (
    "id", "doi", "title", "year", "field", "subfield", "cited_by_count",
    "referenced_works", "referenced_works_count", "research_questions", "objective", "n_studies_final",
)


def wanted(record: dict[str, Any], fields: set[str], min_refs: int) -> bool:
    return bool(
        record.get("field") in fields
        and record.get("doi")
        and record.get("research_questions")
        and record.get("language") == "en"
        and (record.get("referenced_works_count") or 0) >= min_refs
        and not NOT_A_REVIEW_TITLE_RE.match(record.get("title") or "")
    )


def select_reviews(corpus: Path, fields: set[str], min_refs: int, limit: int) -> list[dict[str, Any]]:
    """Stream the corpus and keep the ``limit`` most-cited records that pass ``wanted``."""
    kept: list[dict[str, Any]] = []
    with corpus.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if wanted(record, fields, min_refs):
                kept.append({k: record.get(k) for k in KEEP_KEYS})
    kept.sort(key=lambda r: (-(r.get("cited_by_count") or 0), r["id"]))
    print(f"{len(kept)} reviews pass the filter; keeping the {min(limit, len(kept))} most cited")
    return kept[:limit]


def build_rows(
    reviews: list[dict[str, Any]], resolved: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    review_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for review in reviews:
        title = review["title"].strip()
        if title.lower() in seen:  # the title is the join key between the two CSVs
            continue
        seen.add(title.lower())
        wid = review["id"].rsplit("/", 1)[-1]
        refs = [resolved.get(r.rsplit("/", 1)[-1]) for r in review.get("referenced_works") or []]
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
        published = (resolved.get(wid) or {}).get("publication_date")
        review_rows.append(
            {
                "title": title,
                "doi": normalize_doi(review["doi"]),
                "url": "",
                "published_before": months_earlier(published, 1) if published else "",
                "exclude": "",
                "dataset": "sr4all",
                "review_id": wid,
                "level": "review",
                "n_references": len(refs),
                "n_with_doi": sum(1 for r in refs if r.get("doi")),
                "research_questions": " | ".join(q.strip() for q in review.get("research_questions") or []),
            }
        )
    return review_rows, reference_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=100, help="How many reviews to keep (default 100).")
    parser.add_argument("--min-refs", type=int, default=30, help="Minimum reference-list length (default 30).")
    parser.add_argument("--fields", nargs="+", default=list(DEFAULT_FIELDS), help="OpenAlex 'field' names to keep.")
    parser.add_argument("--refresh", action="store_true", help="Re-read the corpus and re-query OpenAlex.")
    args = parser.parse_args()
    if not CORPUS.exists():
        parser.error(f"{CORPUS} is missing: download sr4all_full.jsonl from Zenodo (10.5281/zenodo.18431942) into that folder.")

    reviews = cached_json(
        SELECTED, lambda: select_reviews(CORPUS, set(args.fields), args.min_refs, args.limit), args.refresh
    )
    ids = [r["id"] for r in reviews] + [w for r in reviews for w in r.get("referenced_works") or []]
    resolved = resolve_openalex_works_cached(RAW_DIR / "sr4all" / "works.json", ids, args.refresh)
    write_ground_truth("sr4all", *build_rows(reviews, resolved))


if __name__ == "__main__":
    main()
