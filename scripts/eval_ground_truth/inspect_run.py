"""Unpick one eval run, step by step: what went into each stage and what came
out, with titles and DOIs — not just the counts ``run_and_score.py`` reports.

Every function here is a pure read over data a run already produced
(``QueryResult.search_calls`` and friends), so you can inspect a run that is
already sitting in a notebook kernel without paying for the API calls again.

The pipeline the eval drives, and where each function looks:

    stage                          what it does                     inspect with
    -----------------------------  -------------------------------  -----------------------
    1. ground truth                review DOI -> its reference      ground_truth_table()
                                   list (the recall target)
    2. clean_review_title()        review title -> search intent    (printed in notebook)
    3. search_generation (LLM)     intent -> N keyword queries       call_table() "query" col
    4. backend API calls           query -> raw provider records     call_table(),
                                   (OpenAlex, Overton)               records_table()
    5. acquire_sources()           normalize, dedup, CAP            cap_losses()
                                   -> rows in the database
    6. screen_sources() (LLM)      candidates -> relevant / not      funnel_table()
    7. scoring                     recall vs the ground truth        funnel_table()

Stage 5 is the one the counts hide: a run can pull 483 records from the API and
keep only 50 (``acquire.capped`` in the log). ``cap_losses()` and
``funnel_table()`` show which specific papers were lost there rather than never
found at all — a different problem with a different fix.

Usage in a notebook, after a run has populated ``results``::

    from inspect_run import call_table, records_table, funnel_table
    call_table(results[0].search_calls)
    records_table(results[0].search_calls, ground_truth.keys)
    funnel_table(ground_truth, results[0])

Dev-only pilot tooling, like the rest of this directory. Not part of the
runtime package.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ground_truth import GroundTruth, normalize_doi, record_key

# The pipeline's own provider-record -> normalized-envelope mappers. Imported
# rather than reimplemented (they are private to acquire.py, and this is
# dev-only tooling) precisely so this inspector reports the title/DOI the
# pipeline actually saw. A local copy would drift and quietly lie to you.
from policy_atlas.evidence_base.sourcing.acquire import _MAPPERS

_QUERY_PREVIEW_CHARS = 60


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
                "with_doi": int(mine["doi"].notna().sum()),
                **(
                    {"gt_hits": int(mine["in_gt"].sum())}
                    if ground_truth_keys is not None
                    else {}
                ),
            }
        )
    return pd.DataFrame(rows)


def ground_truth_table(
    ground_truth: GroundTruth, backend: Any | None = None
) -> pd.DataFrame:
    """The recall target with titles attached — what the run was trying to find.

    ``GroundTruth`` carries bare keys, so this makes one batched OpenAlex
    lookup to put titles and years next to the DOI ones. A DOI with no title
    back is not indexed in OpenAlex, which means this pipeline could never have
    found it: that is a ceiling on recall, not a search failure.

    Overton keys (reference-list entries with no DOI) take their title from the
    citation the ground-truth builder transcribed, and their ``in_openalex`` is
    None — OpenAlex indexing has no bearing on a target reached via Overton.

    Args:
        ground_truth: The built ground truth for the review.
        backend: Optional OpenAlex backend to reuse. Defaults to building one
            from the environment keys (the same one the pipeline uses).

    Returns:
        A DataFrame of key, space (doi/overton), title, year, ``in_openalex``.
    """
    if backend is None:
        from policy_atlas.evidence_base.sourcing.search_live import live_search_backends

        backend = live_search_backends()[0]

    dois = sorted(ground_truth.dois)
    found = {
        doi: envelope
        for record in backend.lookup_dois(dois)
        if (envelope := _envelope("openalex", record))
        and (doi := normalize_doi(envelope.get("doi")))
    }
    return pd.DataFrame(
        [
            {
                "key": key,
                "space": "doi" if key in ground_truth.dois else "overton",
                # Overton targets have no OpenAlex record to ask, so their
                # title is the one transcribed from the citation itself.
                "title": found.get(key, {}).get("title") or ground_truth.titles.get(key),
                "year": found.get(key, {}).get("year"),
                # Only meaningful for DOI targets: an Overton target is reached
                # through Overton, so OpenAlex indexing says nothing about it.
                "in_openalex": key in found if key in ground_truth.dois else None,
            }
            for key in sorted(ground_truth.keys)
        ]
    )


def funnel_table(
    ground_truth: GroundTruth,
    result: Any,
    titles: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The recall funnel per reference-list paper: where each one was lost.

    One row per ground-truth DOI with three yes/no gates, in pipeline order:

    - ``returned_by_api``: some API call returned it at all. False here means
      no generated query reached it — a search-generation or coverage problem.
    - ``reached_db``: it survived acquire's dedup and cap into the candidate
      set. False while ``returned_by_api`` is True means the API found it and
      the cap threw it away — raise the cap, do not rewrite the queries.
    - ``screened_in``: the screening LLM marked it relevant. False here means
      the pipeline had the paper in hand and judged it irrelevant.

    Args:
        ground_truth: The built ground truth for the review.
        result: One ``QueryResult``. ``search_docs`` / ``screened_docs`` are
            used when present; a result from an older run without them leaves
            the last two columns as ``None`` rather than failing.
        titles: Optional ``ground_truth_table()`` output, to label rows with
            titles instead of bare keys. Skipped if not passed (it costs an
            API call).

    Returns:
        A DataFrame of one row per ground-truth key, in funnel order.
    """
    api_keys = set(records_table(result.search_calls)["key"].dropna())
    db_keys = _key_set(getattr(result, "search_docs", None))
    screened_keys = _key_set(getattr(result, "screened_docs", None))
    title_by_key = (
        dict(zip(titles["key"], titles["title"], strict=True))
        if titles is not None
        else {}
    )

    frame = pd.DataFrame(
        [
            {
                "key": key,
                "title": title_by_key.get(key),
                "returned_by_api": key in api_keys,
                "reached_db": None if db_keys is None else key in db_keys,
                "screened_in": None if screened_keys is None else key in screened_keys,
            }
            for key in sorted(ground_truth.keys)
        ]
    )
    # Lost-earliest first: the rows at the top are the ones to explain.
    return frame.sort_values(
        ["returned_by_api", "reached_db", "screened_in"], na_position="first"
    ).reset_index(drop=True)


def cap_losses(
    ground_truth: GroundTruth, result: Any, titles: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Just the reference-list papers an API call returned but the cap dropped.

    A shortcut into the interesting slice of ``funnel_table()``: recall these
    cost nothing to recover except a higher cap.
    """
    frame = funnel_table(ground_truth, result, titles)
    return frame[frame["returned_by_api"] & (frame["reached_db"] == False)]  # noqa: E712


def unexplained_screened(result: Any, ground_truth: GroundTruth) -> pd.DataFrame:
    """Papers the run screened IN that the review did not cite.

    Not errors: a review's bibliography is not an exhaustive list of the
    relevant literature, which is why precision is never scored directly
    against it (see ``run_and_score.py``). Read this as the precision proxy's
    raw material — skim the titles and judge for yourself.
    """
    docs = getattr(result, "screened_docs", None)
    if docs is None:
        return pd.DataFrame(columns=["title", "doi", "year"])
    return pd.DataFrame(
        [
            {"title": d.get("title"), "doi": normalize_doi(d.get("doi")), "year": d.get("year")}
            for d in docs
            if record_key(d) not in ground_truth.keys
        ]
    )


def _key_set(docs: list[dict[str, Any]] | None) -> set[str] | None:
    """Scoring keys from a list of metadata dicts; ``None`` in, ``None`` out (so
    an older ``QueryResult`` without the field reads as "not recorded", which is
    not the same as "empty")."""
    if docs is None:
        return None
    return {key for d in docs if (key := record_key(d))}


def summarize(
    ground_truth: GroundTruth, result: Any, titles: pd.DataFrame | None = None
) -> None:
    """Print the funnel as counts, so the per-stage drop is visible at a glance."""
    frame = funnel_table(ground_truth, result, titles)
    total = len(frame)
    print(f"ground-truth references:        {total}")
    print(f"  returned by some API call:    {int(frame['returned_by_api'].sum())}")
    if frame["reached_db"].notna().any():
        print(f"  survived dedup + cap to DB:   {int(frame['reached_db'].sum())}")
    if frame["screened_in"].notna().any():
        print(f"  screened in as relevant:      {int(frame['screened_in'].sum())}")
    print(f"\napi calls made: {len(result.search_calls)}")
    print(f"records returned (with repeats): {sum(c['result_count'] for c in result.search_calls)}")


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
        }
    ]
    # An Overton policy document with no DOI: scorable on its document id, and
    # invisible to any DOI-only measurement.
    calls.append(
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
        }
    )
    gt = GroundTruth(
        dois={"10.1000/hit", "10.1000/missed"},
        resolvable_fraction=1.0,
        source="url",
        overton_ids={"overton:P9"},
        titles={"overton:P9": "Loneliness - what characteristics"},
    )

    records = records_table(calls, gt.keys)
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

    calls_summary = call_table(calls, gt.keys)
    assert calls_summary.loc[0, "gt_hits"] == 1
    assert calls_summary.loc[0, "with_doi"] == 1  # the untitled record maps to None
    assert calls_summary.loc[1, "gt_hits"] == 1  # the Overton call earned its keep

    class _Result:
        search_calls = calls
        search_docs = [
            {"doi": "10.1000/hit", "backend": "openalex", "title": "Parental leave and depression"},
            {"backend": "overton", "backend_record_id": "P9", "title": "Loneliness"},
        ]
        screened_docs: list[dict[str, Any]] = []

    funnel = funnel_table(gt, _Result())
    by_key = funnel.set_index("key")
    assert by_key.loc["10.1000/hit", "returned_by_api"]
    assert by_key.loc["10.1000/hit", "reached_db"]
    assert not by_key.loc["10.1000/hit", "screened_in"]
    assert not by_key.loc["10.1000/missed", "returned_by_api"]
    assert by_key.loc["overton:P9", "reached_db"]
    # Lost earliest sorts first.
    assert funnel.loc[0, "key"] == "10.1000/missed"

    # A result with no search_docs recorded reads as "not recorded", not "empty".
    class _Old:
        search_calls = calls

    assert funnel_table(gt, _Old())["reached_db"].isna().all()

    print("inspect_run demo: ok")


if __name__ == "__main__":
    demo()
