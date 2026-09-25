"""Youth Endowment Fund (YEF) evidence and gap map -> ground-truth CSVs.

The YEF Programmes Evidence and Gap Map collects about 3,400 evaluations and
reviews of interventions to prevent children's involvement in violence, each
coded to one "Toolkit strand" (mentoring, hot-spots policing, cash transfers,
and so on). It is published as one large HTML page made with EPPI-Mapper, and
the whole dataset sits inside that page as JSON constants. This script
downloads the page once, reads those constants, and writes:

* ``level = map`` — one row for the whole map (every study is a target).
* ``level = intervention`` — one row per strand with at least ``--min-studies``
  studies. The intent is "<map scope>: <strand>".

Study rows get ``label = content`` (the map's screeners judged them on topic).
The review identifier is the page URL plus ``#strand=<id>``, and
``published_before`` is the 31 December of the latest study year in the row.

Usage:

    uv run --project backend python scripts/evals/search/get_yef.py [--min-studies 20] [--refresh]

If YEF publishes a new edition, change ``PAGE_URL``.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

import httpx

from ground_truth import RAW_DIR, doi_if_valid, write_ground_truth

PAGE_URL = "https://youthendowmentfund.org.uk/wp-content/uploads/2026/08/EGM-April-2026.html"
MAP_SCOPE = "Interventions to prevent children and young people's involvement in violence"
AXIS_TITLE = "Toolkit strand"
RAW = RAW_DIR / "yef" / PAGE_URL.rsplit("/", 1)[-1]


def download_page(refresh: bool) -> str:
    if RAW.exists() and not refresh:
        return RAW.read_text(encoding="utf-8")
    resp = httpx.get(PAGE_URL, timeout=300.0, follow_redirects=True)
    resp.raise_for_status()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(resp.text, encoding="utf-8")
    return resp.text


def embedded_const(html: str, name: str) -> Any:
    """The JSON value assigned to ``const <name> = ...`` in the page's script."""
    marker = f"const {name} = "
    start = html.index(marker) + len(marker)
    value, _ = json.JSONDecoder().raw_decode(html, start)
    return value


def strands(csv_data: dict[str, Any]) -> dict[int, str]:
    """``{attribute id: strand name}`` for the map's strand axis, minus 'Uncategorised'."""
    cells = [cell for row in csv_data["rows"] for cell in row]
    axis = next(c for c in cells if c.get("title") == AXIS_TITLE and not c.get("parentId"))
    return {
        int(c["id"]): re.sub(r"\s+", " ", c["title"]).strip()
        for c in cells
        if c.get("parentId") == axis["id"] and c.get("title", "").strip().lower() != "uncategorised"
    }


def items_by_strand(items: list[dict[str, Any]], strand_ids: set[int]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {sid: [] for sid in strand_ids}
    for item in items:
        for code in item.get("Codes") or []:
            if code.get("AttributeId") in grouped:
                grouped[code["AttributeId"]].append(item)
    return grouped


def _year(value: Any) -> int | None:
    match = re.search(r"\d{4}", str(value or ""))
    return int(match.group(0)) if match else None


def build_rows(
    items: list[dict[str, Any]], strand_names: dict[int, str], min_studies: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped = items_by_strand(items, set(strand_names))
    targets: list[tuple[str, str, str, list[dict[str, Any]]]] = [(MAP_SCOPE, PAGE_URL, "map", items)]
    for sid, name in sorted(strand_names.items(), key=lambda kv: kv[1]):
        if len(grouped[sid]) >= min_studies:
            targets.append((f"{MAP_SCOPE}: {name}", f"{PAGE_URL}#strand={sid}", "intervention", grouped[sid]))

    review_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    for title, url, level, studies in targets:
        years = [y for y in (_year(s.get("Year")) for s in studies) if y]
        with_doi = 0
        for study in studies:
            doi = doi_if_valid(study.get("DOI"))
            with_doi += bool(doi)
            reference_rows.append(
                {
                    "review_title": title,
                    "ref_title": (study.get("Title") or "").strip(),
                    "label": "content",
                    "doi": doi or "",
                    "overton_id": "",
                    "url": study.get("URL") or "",
                    "year": _year(study.get("Year")) or "",
                    "ref_id": f"yef:{study['ItemId']}",
                }
            )
        review_rows.append(
            {
                "title": title,
                "doi": "",
                "url": url,
                "published_before": f"{max(years)}-12-31" if years else "",
                "exclude": "",
                "dataset": "yef",
                "review_id": url,
                "level": level,
                "n_references": len(studies),
                "n_with_doi": with_doi,
                "research_questions": "",
            }
        )
    return review_rows, reference_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-studies", type=int, default=20, help="Keep strands with at least this many studies (default 20).")
    parser.add_argument("--refresh", action="store_true", help="Download the page again even if a copy exists.")
    args = parser.parse_args()

    html = download_page(args.refresh)
    items = embedded_const(html, "referenceData")
    strand_names = strands(embedded_const(html, "csvData"))
    print(f"{len(items)} studies, {len(strand_names)} strands in the page")
    write_ground_truth("yef", *build_rows(items, strand_names, args.min_studies))


if __name__ == "__main__":
    main()
