"""3ie evidence gap maps -> ground-truth CSVs.

3ie (the International Initiative for Impact Evaluation) runs the Development
Evidence Portal. Its systematic-review records do NOT list their included
studies, but its evidence gap maps do: every map is a grid of intervention
rows by outcome columns, and each cell lists the impact evaluations and
reviews coded into it, with title, year, DOI and URL.

This script pulls every map hosted on the portal itself through the two JSON
calls the map page makes (``project_details`` and ``get_map_data``, no login
needed) and turns each map into ground truth at two levels:

* ``level = map`` — one row per map: the map's title is the intent and every
  study in the map is a target. A broad-scope test.
* ``level = intervention`` — one row per intervention row with at least
  ``--min-studies`` studies. The intent is "<map title>: <intervention>", and
  the targets are the studies coded into that row across all outcomes.

The review identifier is the map URL (plus ``#intervention=<id>`` for a row),
so ``published_before`` must be given: it is the 31 December of the latest
publication year among the row's studies, the last date a study could carry
and still be in the map.

Every study row gets ``label = content``: the map's screeners already judged
it on topic. About a quarter of studies are grey literature with no DOI; those
rows keep their URL and cannot be scored until an Overton id is filled in.

Raw map JSON is kept under ``results/ground_truth/raw/3ie/`` and reused.

Usage:

    uv run --project backend python scripts/evals/search/get_3ie.py [--min-studies 20] [--refresh]

3ie's terms of use allow non-commercial use with attribution. Cite the portal
in anything that reuses these lists.
"""

from __future__ import annotations

import argparse
import re
import time
from collections.abc import Iterable, Iterator
from typing import Any

import httpx

from ground_truth import RAW_DIR, cached_json, clean_review_title, doi_if_valid, write_ground_truth

API = "https://api.developmentevidence.3ieimpact.org"
PORTAL_MAP_PREFIX = "https://developmentevidence.3ieimpact.org/egm/"
RAW = RAW_DIR / "3ie"
PAGE = 40  # the search endpoint rejects larger pages


def post_json(path: str, payload: dict[str, Any]) -> Any:
    """POST JSON to the portal's API, retrying transient failures three times."""
    for attempt in range(3):
        try:
            resp = httpx.post(f"{API}{path}", json=payload, timeout=120.0)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()
        except httpx.TransportError:
            if attempt == 2:
                raise
        time.sleep(2**attempt)
    resp.raise_for_status()
    raise AssertionError("unreachable")


def graphql(query: str) -> dict[str, Any]:
    data = post_json("/graphql", {"query": query})
    if data.get("errors"):
        raise RuntimeError(f"3ie GraphQL error: {data['errors'][0].get('message')}")
    return data["data"]


def list_maps() -> list[dict[str, Any]]:
    """Every evidence-gap-map record whose interactive map lives on the portal.

    Older maps point at ``gapmaps.3ieimpact.org``, a different site with no
    JSON feed; those are skipped and counted in the printed summary.
    """
    ids: list[str] = []
    start = 0
    while True:
        page = graphql(
            f'{{ keywordSearch(data:{{keyword:"*", from:{start}, size:{PAGE}, '
            'filters:{product_type:[egm]}}) { search_result { id } } }'
        )["keywordSearch"]["search_result"]
        ids.extend(hit["id"] for hit in page)
        if len(page) < PAGE:
            break
        start += PAGE
    fields = "{ title year_of_publication egm_url }"
    details = graphql("{" + " ".join(f'r{i}: recordDetail(id:"{pid}") {fields}' for i, pid in enumerate(ids)) + "}")
    maps: list[dict[str, Any]] = []
    skipped = 0
    for record in details.values():
        url = (record or {}).get("egm_url") or ""
        if not url.startswith(PORTAL_MAP_PREFIX):
            skipped += 1
            continue
        maps.append({"title": record["title"].strip(), "year": record["year_of_publication"], "url": url, "slug": url[len(PORTAL_MAP_PREFIX) :].strip("/")})
    print(f"{len(ids)} gap-map records, {len(maps)} hosted on the portal, {skipped} on the old site (skipped)")
    return maps


def fetch_map(slug: str) -> dict[str, Any]:
    """The whole map as the page receives it: layout, cells and every study record."""
    details = post_json("/api/project_details", {"url": slug})["data"]
    data = post_json("/api/get_map_data", {"project_id": details["project_id"], "lang": "en"})
    data["project_name"] = details.get("project_name")
    return data


def leaf_groups(groups: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """The innermost intervention rows: a map nests rows one or two levels deep."""
    for group in groups:
        subs = group.get("sub_levels") or []
        if subs:
            yield from leaf_groups(subs)
        else:
            yield group


def studies_in_cells(cells: dict[str, Any]) -> set[str]:
    """Study ids across one row's cells (each cell holds one 'bubble' per study type)."""
    return {
        str(record["id"])
        for cell in cells.values()
        for bubble in cell.get("bubbles") or []
        for record in bubble.get("records") or []
    }


def map_rows(data: dict[str, Any]) -> list[tuple[str, str, set[str]]]:
    """``(group_id, intervention title, study ids)`` for every leaf intervention row."""
    grid = data.get("interventions_outcomes") or {}
    rows = []
    for group in leaf_groups(data.get("interventions") or []):
        gid = str(group["map_layout_group_id"])
        rows.append((gid, re.sub(r"\s+", " ", group["map_layout_group_title"]).strip(), studies_in_cells(grid.get(gid) or {})))
    return rows


def _year(value: Any) -> int | None:
    match = re.search(r"\d{4}", str(value or ""))
    return int(match.group(0)) if match else None


def build_rows(
    egm: dict[str, Any], data: dict[str, Any], min_studies: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One map -> its review rows (map level plus qualifying intervention rows) and reference rows."""
    records: dict[str, dict[str, Any]] = {str(k): v for k, v in (data.get("project_records") or {}).items()}
    map_title = clean_review_title(egm["title"])
    targets: list[tuple[str, str, str, set[str]]] = [(map_title, egm["url"], "map", set(records))]
    for gid, row_title, ids in map_rows(data):
        if len(ids) >= min_studies:
            targets.append((f"{map_title}: {row_title}", f"{egm['url']}#intervention={gid}", "intervention", ids))

    review_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    for title, url, level, ids in targets:
        studies = [records[i] for i in sorted(ids) if i in records]
        years = [y for y in (_year(s.get("year_of_publication")) for s in studies) if y]
        latest = max(years) if years else _year(egm["year"])
        with_doi = 0
        for study in studies:
            doi = doi_if_valid(study.get("doi"))
            with_doi += bool(doi)
            reference_rows.append(
                {
                    "review_title": title,
                    "ref_title": (study.get("title") or "").strip(),
                    "label": "content",
                    "doi": doi or "",
                    "overton_id": "",
                    "url": study.get("url") or study.get("record_url") or "",
                    "year": _year(study.get("year_of_publication")) or "",
                    "ref_id": f"3ie:{study['id']}",
                }
            )
        review_rows.append(
            {
                "title": title,
                "doi": "",
                "url": url,
                "published_before": f"{latest}-12-31" if latest else "",
                "exclude": "",
                "dataset": "3ie",
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
    parser.add_argument("--min-studies", type=int, default=20, help="Keep intervention rows with at least this many studies (default 20).")
    parser.add_argument("--refresh", action="store_true", help="Ignore the raw cache and call the portal again.")
    args = parser.parse_args()

    maps = cached_json(RAW / "maps.json", list_maps, args.refresh)
    reviews: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for egm in maps:
        data = cached_json(RAW / f"{egm['slug']}.json", lambda slug=egm["slug"]: fetch_map(slug), args.refresh)
        if not data.get("project_records"):
            print(f"  {egm['slug']}: no studies, skipped")
            continue
        r, refs = build_rows(egm, data, args.min_studies)
        print(f"  {egm['slug']}: {len(data['project_records'])} studies, {len(r) - 1} intervention rows kept")
        reviews.extend(r)
        references.extend(refs)
    write_ground_truth("3ie", reviews, references)


if __name__ == "__main__":
    main()
