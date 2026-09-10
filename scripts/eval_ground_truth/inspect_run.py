"""Per-call and per-record views over one eval run's raw provider output, with
titles and DOIs — not just the counts the sweep reports.

Both functions are pure reads over ``QueryResult.search_calls`` (every API
call the run made and the raw records it returned), so a run can be inspected
without paying for the API calls again. The sweep uses them to build its
queries CSV and to find which API calls returned each cited paper; the
per-paper funnel (returned by the API? survived the cap? screened in?) is the
sweep's papers CSV.

Usage in a notebook, with a ``QueryResult`` in ``result``::

    from inspect_run import call_table, records_table
    call_table(result.search_calls, ground_truth.keys)
    records_table(result.search_calls, ground_truth.keys)

Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ground_truth import normalize_doi, record_key

# The pipeline's own provider-record -> normalized-envelope mappers. Imported
# rather than reimplemented (they are private to acquire.py, and this is
# dev-only tooling) precisely so this inspector reports the title/DOI the
# pipeline actually saw. A local copy would drift and quietly lie to you.
from policy_atlas.evidence_search.sourcing.acquire import _MAPPERS


def _envelope(backend: str, record: dict[str, Any]) -> dict[str, Any] | None:
    """One raw provider record -> the pipeline's normalized envelope.

    Returns ``None`` for a record ``acquire`` would itself reject as unusable
    (no title, or no locator) — those never reach the database, so they are
    worth seeing as rejects rather than as candidates.
    """
    mapper = _MAPPERS.get(backend)
    if mapper is None:
        return None
    mapped = mapper(record)
    return mapped["envelope"] if mapped else None


def records_table(
    search_calls: list[dict[str, Any]], ground_truth_keys: set[str] | None = None
) -> pd.DataFrame:
    """Every record returned by every API call, one row each — the main view.

    This is the raw provider output, BEFORE dedup and before the acquire cap.
    Expect the same paper to appear on several rows when several generated
    queries found it.

    Args:
        search_calls: ``QueryResult.search_calls`` from one run.
        ground_truth_keys: Optional ``GroundTruth.keys``; adds an ``in_gt``
            column flagging records that are in the review's reference list.
            Pass ``.keys``, not ``.dois`` — ``.dois`` alone scores no policy
            document that lacks a DOI.

    Returns:
        A DataFrame with one row per returned record: which call it came from,
        the query that found it, and its title, DOI and year as the pipeline
        normalized them. ``usable`` is False for records acquire would drop for
        having no title or no locator.
    """
    rows: list[dict[str, Any]] = []
    for call_index, call in enumerate(search_calls):
        for record in call["records"]:
            envelope = _envelope(call["backend"], record)
            doi = normalize_doi((envelope or {}).get("doi"))
            # The key the ground truth is matched on: the DOI when there is
            # one, else the Overton document id. A policy document with no DOI
            # is still scorable — see ground_truth.record_key.
            key = record_key(envelope)
            rows.append(
                {
                    "call": call_index,
                    "backend": call["backend"],
                    "method": call["method"],
                    "query": call["query"],
                    "title": (envelope or {}).get("title"),
                    "doi": doi,
                    "key": key,
                    "year": (envelope or {}).get("year"),
                    "usable": envelope is not None,
                    **(
                        {"in_gt": bool(key) and key in ground_truth_keys}
                        if ground_truth_keys is not None
                        else {}
                    ),
                }
            )
    return pd.DataFrame(rows)


def call_table(
    search_calls: list[dict[str, Any]], ground_truth_keys: set[str] | None = None
) -> pd.DataFrame:
    """One row per API call: the query sent, and how much it brought back.

    Use this to see which generated queries earned their keep. A query with
    ``gt_hits`` of 0 across a whole run found nothing the review cited.

    Args:
        search_calls: ``QueryResult.search_calls`` from one run.
        ground_truth_keys: Optional ``GroundTruth.keys``; adds ``gt_hits``.

    Returns:
        A DataFrame indexed by call, with the backend, method, full query text,
        result count, how many results carried a DOI, and (with a ground truth)
        how many were reference-list papers.
    """
    records = records_table(search_calls, ground_truth_keys)
    rows: list[dict[str, Any]] = []
    for call_index, call in enumerate(search_calls):
        mine = records[records["call"] == call_index]
        rows.append(
            {
                "call": call_index,
                "backend": call["backend"],
                "method": call["method"],
                "query": call["query"],
                "wire_params": call["wire_params"],
                "results": call["result_count"],
                # None on a call that succeeded. Anything else is a call that
                # failed after its retries: it returned no records, so it drags
                # recall down without being a search-quality problem. Filter on
                # this before reading a run's recall as a real result.
                "error": call.get("error"),
                "with_doi": int(mine["doi"].notna().sum()),
                **(
                    {"gt_hits": int(mine["in_gt"].sum())}
                    if ground_truth_keys is not None
                    else {}
                ),
            }
        )
    return pd.DataFrame(rows)


def demo() -> None:
    """Self-check on synthetic data — no network, no database."""
    calls = [
        {
            "backend": "openalex",
            "method": "search",
            "query": "parental leave mental health",
            "wire_params": None,
            "result_count": 2,
            "records": [
                {
                    "id": "https://openalex.org/W1",
                    "display_name": "Parental leave and depression",
                    "doi": "https://doi.org/10.1000/HIT",
                    "publication_year": 2015,
                },
                {  # no title -> acquire would reject it
                    "id": "https://openalex.org/W2",
                    "doi": "https://doi.org/10.1000/junk",
                },
            ],
        },
        # An Overton policy document with no DOI: scorable on its document id,
        # and invisible to any DOI-only measurement.
        {
            "backend": "overton",
            "method": "search",
            "query": "loneliness characteristics",
            "wire_params": None,
            "result_count": 1,
            "records": [
                {
                    "policy_document_id": "P9",
                    "title": "Loneliness - what characteristics are associated with feeling lonely",
                    "document_url": "https://ons.gov.uk/loneliness",
                }
            ],
        },
    ]
    keys = {"10.1000/hit", "10.1000/missed", "overton:P9"}

    records = records_table(calls, keys)
    assert len(records) == 3, records
    hit = records[records["doi"] == "10.1000/hit"].iloc[0]
    assert hit["title"] == "Parental leave and depression"
    assert hit["in_gt"] and hit["usable"]
    # DOI is normalized to bare lowercase, matching the ground-truth key.
    assert records["usable"].tolist() == [True, False, True]
    # The Overton record has no DOI at all, and is still matched.
    policy = records[records["backend"] == "overton"].iloc[0]
    assert pd.isna(policy["doi"]) and policy["key"] == "overton:P9"
    assert policy["in_gt"]

    calls_summary = call_table(calls, keys)
    assert calls_summary.loc[0, "gt_hits"] == 1
    assert calls_summary.loc[0, "with_doi"] == 1  # the untitled record maps to None
    assert calls_summary.loc[1, "gt_hits"] == 1  # the Overton call earned its keep

    print("inspect_run demo: ok")


if __name__ == "__main__":
    demo()
