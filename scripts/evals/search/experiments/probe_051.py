"""Live probes for task 051, run once before the build (plan Phase 0b).

Three questions the contract pins before any transport code is written:

(a) Which of the plan's OpenAlex filters does the semantic endpoint
    (``search.semantic``) accept? One request per filter key the directive grammar can
    emit (``openalex_wire_params``), with a harmless value, at one request per second.
    A 200 means accepted, a 400 means rejected. The accepted set becomes
    ``SEMANTIC_ACCEPTED_FILTER_KEYS`` in ``search_loop.py`` (contract D13). One extra
    request checks how many results one keyword page of 200 is served with, because
    OpenAlex's documented page maximum has changed before (contract D3, D12).
(b) Does Overton ``documents.php`` with ``sort=relevance`` return a different, score-
    descending order from the default date order? (contract P1, D8)
(c) Does Overton ``documents.php?policy_document_id=<id>`` return one record with its
    ``cites.policy`` list? (contract D8, the landmark fetch)

The script writes sanitised excerpts (no key, no abstract, no full text, no snippet) to
``backend/tests/data/probes_051/`` and prints the table that goes into
``verification.md`` § Probes.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/probe_051.py [--text TEXT]

About 14 OpenAlex requests (the semantic ones cost about $0.001 each) and 4 Overton
requests. Nothing is uploaded.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from policy_atlas.evidence_search.sourcing.search_loop import openalex_wire_params

OPENALEX = "https://api.openalex.org/works"
OVERTON = "https://app.overton.io/documents.php"
OUT_DIR = (
    Path(__file__).resolve().parents[4] / "backend" / "tests" / "data" / "probes_051"
)
DEFAULT_TEXT = "interventions to reduce loneliness in older adults"

# One harmless value per directive key. The wire part each key emits is computed by the
# production mapper, so the probe sends exactly what a run would send.
DIRECTIVE_SAMPLES: dict[str, Any] = {
    "published_after": "2015-01-01",
    "published_before": "2024-12-31",
    "sdgs": [3],
    "types": ["article"],
    "languages": ["en"],
    "exclude_retracted": True,
    "exclude_paratext": True,
    "oa_status": ["gold"],
    "author_affiliation_countries": ["GB"],
}


def _openalex(params: dict[str, str]) -> httpx.Response:
    auth = {"api_key": os.environ["OPENALEX_API_KEY"]}
    if os.environ.get("OPENALEX_EMAIL"):
        auth["mailto"] = os.environ["OPENALEX_EMAIL"]
    return httpx.get(OPENALEX, params={**auth, **params}, timeout=60.0)


def _overton(params: dict[str, str]) -> httpx.Response:
    return httpx.get(
        OVERTON,
        params={"format": "json", "api_key": os.environ["OVERTON_API_KEY"], **params},
        timeout=90.0,
    )


def _error_excerpt(response: httpx.Response) -> str:
    # The excerpt lands in a public fixture; a provider may echo the request
    # URL, key included, in an error body (review finding, 2026-10-09).
    try:
        text = json.dumps(response.json())[:300]
    except ValueError:
        text = response.text[:200]
    return re.sub(r"(api_key|mailto)=[^&\"\s]+", r"\1=REDACTED", text)


def probe_semantic_filters(text: str) -> list[dict[str, Any]]:
    """(a): one semantic request per directive key; 200 = accepted, 400 = rejected."""
    rows: list[dict[str, Any]] = []
    cases: list[tuple[str, str]] = [("(none)", "")]
    for key, value in DIRECTIVE_SAMPLES.items():
        cases.append((key, openalex_wire_params({key: value})["filter"]))
    # Not a directive key today: the experiment sent it and found it accepted. Kept as a
    # reference row so the date-filter rejection can be read against it.
    cases.append(("publication_year (reference)", "publication_year:<2025"))
    # Reference rows for a year fence on both sides (the D13 owner decision needs them):
    # a closed range and a lower bound.
    cases.append(("publication_year range (reference)", "publication_year:2015-2024"))
    cases.append(("publication_year lower bound (reference)", "publication_year:>2014"))
    for key, part in cases:
        params = {"search.semantic": text, "select": "id", "per-page": "5"}
        if part:
            params["filter"] = part
        time.sleep(1.0)
        response = _openalex(params)
        rows.append(
            {
                "directive_key": key,
                "wire_filter": part,
                "status": response.status_code,
                "accepted": response.status_code == 200,
                "n_results": len(response.json().get("results", []))
                if response.status_code == 200
                else None,
                "error": None
                if response.status_code == 200
                else _error_excerpt(response),
            }
        )
    return rows


def probe_keyword_page_size(text: str) -> dict[str, Any]:
    """(a, extra): how many results one keyword page of 200 is served with."""
    time.sleep(1.0)
    response = _openalex(
        {
            "filter": f"title_and_abstract.search:{text}",
            "select": "id",
            "per-page": "200",
            "page": "1",
        }
    )
    body = response.json() if response.status_code == 200 else {}
    return {
        "status": response.status_code,
        "requested_per_page": 200,
        "served_per_page": (body.get("meta") or {}).get("per_page"),
        "n_results": len(body.get("results", [])),
        "total_count": (body.get("meta") or {}).get("count"),
    }


def _slim_overton(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    cites = record.get("cites") or {}
    return {
        "policy_document_id": record.get("policy_document_id"),
        "title": (record.get("translated_title") or record.get("title") or "")[:120],
        "published_on": record.get("published_on"),
        "es_score": record.get("es_score"),
        "citation_count": record.get("citation_count"),
        "source_country": source.get("country"),
        "n_cites_policy": len(cites.get("policy") or []),
    }


def probe_overton_sort(text: str) -> dict[str, Any]:
    """(b): the first page in relevance order against the default order."""
    base = {"squery": text, "min_similarity": "0.3", "pp": "10"}
    time.sleep(1.2)
    default = _overton(base)
    time.sleep(1.2)
    relevance = _overton({**base, "sort": "relevance"})
    default_rows = [_slim_overton(r) for r in default.json().get("results", [])]
    relevance_rows = [_slim_overton(r) for r in relevance.json().get("results", [])]
    scores = [r["es_score"] for r in relevance_rows if r["es_score"] is not None]
    return {
        "status_default": default.status_code,
        "status_relevance": relevance.status_code,
        "default_order": default_rows,
        "relevance_order": relevance_rows,
        "relevance_scores_descend": scores == sorted(scores, reverse=True),
        "first_result_differs": bool(default_rows and relevance_rows)
        and default_rows[0]["policy_document_id"]
        != relevance_rows[0]["policy_document_id"],
        "default_dates_descend": [r["published_on"] for r in default_rows]
        == sorted((r["published_on"] for r in default_rows), reverse=True),
    }


def probe_overton_fetch_by_id(record_id: str) -> dict[str, Any]:
    """(c): one record by id, with its cited policy documents."""
    time.sleep(1.2)
    response = _overton({"policy_document_id": record_id, "pp": "1"})
    results = response.json().get("results", []) if response.status_code == 200 else []
    record = results[0] if results else {}
    cites = (record.get("cites") or {}).get("policy") or []
    return {
        "status": response.status_code,
        "n_results": len(results),
        "record": _slim_overton(record) if record else None,
        "cites_policy_sample": [
            {"overton_id": c.get("overton_id"), "title": (c.get("title") or "")[:100]}
            for c in cites[:5]
        ],
        "id_matches": bool(record) and record.get("policy_document_id") == record_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument(
        "--id",
        default=None,
        help="Overton policy_document_id for probe (c); default: the first relevance result that cites policy documents",
    )
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    filters = probe_semantic_filters(args.text)
    page = probe_keyword_page_size(args.text)
    sort = probe_overton_sort(args.text)
    first_id = next(
        (
            r["policy_document_id"]
            for r in sort["relevance_order"]
            if r["n_cites_policy"]
        ),
        sort["relevance_order"][0]["policy_document_id"]
        if sort["relevance_order"]
        else "",
    )
    first_id = args.id or first_id
    by_id = probe_overton_fetch_by_id(first_id)

    (OUT_DIR / "openalex_semantic_filters.json").write_text(
        json.dumps({"text": args.text, "rows": filters, "keyword_page": page}, indent=2)
        + "\n"
    )
    (OUT_DIR / "overton_sort_relevance.json").write_text(
        json.dumps({"text": args.text, **sort}, indent=2) + "\n"
    )
    (OUT_DIR / "overton_fetch_by_id.json").write_text(
        json.dumps(by_id, indent=2) + "\n"
    )

    print("\n(a) OpenAlex search.semantic with each directive filter\n")
    print("| directive key | wire filter | status | accepted |")
    print("|---|---|---:|---|")
    for row in filters:
        print(
            f"| {row['directive_key']} | `{row['wire_filter'] or '-'}` | {row['status']} | "
            f"{'yes' if row['accepted'] else 'no'} |"
        )
    accepted = sorted(
        r["directive_key"]
        for r in filters
        if r["accepted"] and r["directive_key"] in DIRECTIVE_SAMPLES
    )
    print(f"\nSEMANTIC_ACCEPTED_FILTER_KEYS = {accepted}")
    print(
        f"\nkeyword page: requested 200, served {page['served_per_page']} "
        f"({page['n_results']} results, status {page['status']})"
    )
    print(
        f"\n(b) Overton sort=relevance: status {sort['status_relevance']}, scores descend "
        f"{sort['relevance_scores_descend']}, first result differs from date order "
        f"{sort['first_result_differs']}, default order is by date {sort['default_dates_descend']}"
    )
    print(
        f"\n(c) Overton fetch by id {first_id}: status {by_id['status']}, {by_id['n_results']} "
        f"result, id matches {by_id['id_matches']}, cites.policy "
        f"{by_id['record']['n_cites_policy'] if by_id['record'] else None}"
    )
    print(f"\nwrote {OUT_DIR}")


if __name__ == "__main__":
    main()
