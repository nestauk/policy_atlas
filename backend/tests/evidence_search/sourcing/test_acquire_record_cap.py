"""Tests for the acquisition cap: pool order, dedup, trim, persist.

The cap is the run's volume brake. Its contract (task 051, D7): the caller
hands ``acquire_sources`` one ranked pool per backend; acquire dedups *before*
trimming so a capped run still yields a full cap of new documents, caps each
backend separately, and keeps ``results_returned`` as the raw provider count.
These tests build their pools with ``pool.interleave`` (rank round-robin over
the calls), the order the search uses for seeds.
"""

import uuid
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing import pool
from policy_atlas.evidence_search.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_search.sourcing.search_loop import ExecutedCall
from tests.helpers import oa_record, seed_run, seed_scope, seed_task_and_run
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend


def _ov_record(suffix: str) -> dict[str, Any]:
    """Overton record with a distinct title, so dedup keys differ per record."""
    return {
        "policy_document_id": f"org-{suffix}",
        "pdf_document_id": f"org-{suffix}-pdf",
        "title": f"Overton document {suffix}",
        "translated_title": "",
        "snippet": f"grey literature body {suffix}",
        "llm_document_description": "",
        "published_on": "2021-06-01",
        "keyed_other_identifiers": [],
        "source": {"title": "Marble Agency", "type": "government"},
        "document_url": f"https://example.org/doc/{suffix}",
        "overton_url": f"https://example.org/ov/{suffix}",
        "languages": ["eng"],
        "authors": [],
        "topics": [],
    }


def _call(
    backend_name: str,
    records: list[dict[str, Any]],
    *,
    verb: str = "search",
    query: str = "q",
) -> ExecutedCall:
    return ExecutedCall(
        backend_name=backend_name,
        verb=cast("Any", verb),
        query=query,
        query_origin="verbatim",
        wire_params={},
        records=records,
        status="ok",
        error=None,
    )


def _acquire(
    conn: Connection,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    calls: list[ExecutedCall],
    *,
    cap: int | None,
) -> dict[str, Any]:
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    return acquire_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=cast("list[SearchBackend]", backends),
        executed_calls=calls,
        pools=_pools(calls),
        caps=({"openalex": cap, "overton": cap} if cap is not None else None),
    )


def _pools(calls: list[ExecutedCall]) -> dict[str, list[tuple[dict[str, Any], str, str]]]:
    """Rank-interleave each backend's calls, then list every other copy after."""
    pools: dict[str, list[tuple[dict[str, Any], str, str]]] = {}
    for name in {call.backend_name for call in calls}:
        mine = [call for call in calls if call.backend_name == name]
        key = (
            (lambda r: r.get("id"))
            if name == "openalex"
            else (lambda r: r.get("policy_document_id"))
        )
        ranked = pool.interleave([call.records for call in mine], key)
        placed = {id(record) for record in ranked}
        origin = {id(r): (call.query_origin, call.verb) for call in mine for r in call.records}
        entries: list[tuple[dict[str, Any], str, str]] = [
            (record, *origin[id(record)]) for record in ranked
        ]
        for call in mine:
            for record in call.records:
                if id(record) not in placed:
                    placed.add(id(record))
                    entries.append((record, *origin[id(record)]))
        pools[name] = entries
    return pools


def _persisted_titles(conn: Connection, task_id: uuid.UUID) -> set[str]:
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    return {row.metadata["title"] for row in rows}


# --- Cap behaviour through acquire_sources ---


def test_cap_keeps_the_top_ranked_slice_of_every_query(conn: Connection) -> None:
    """With a cap of 4 across two queries, each contributes its top 2."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    calls = [
        _call("openalex", [oa_record(f"a{i}") for i in range(5)], query="q1"),
        _call("openalex", [oa_record(f"b{i}") for i in range(5)], query="q2"),
    ]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=4)

    assert counts["acquired"] == 4
    assert counts["dropped_over_cap"] == 6
    assert counts["results_returned"] == 10
    titles = _persisted_titles(conn, task_id)
    assert titles == {
        "OpenAlex record a0",
        "OpenAlex record a1",
        "OpenAlex record b0",
        "OpenAlex record b1",
    }


def test_dedup_runs_before_the_trim_so_the_cap_is_filled(conn: Connection) -> None:
    """Repeats from an earlier round do not consume cap slots.

    This is the property that makes later deep rounds work as hard as the
    first: capping candidates instead of acquisitions would let a round of
    mostly-repeats acquire far fewer than its budget.
    """
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    first = [oa_record(f"a{i}") for i in range(4)]
    _acquire(conn, task_id, run_id, scope_id, [_call("openalex", first)], cap=None)
    assert _persisted_titles(conn, task_id) == {f"OpenAlex record a{i}" for i in range(4)}

    # Round 2 re-returns all four, then four genuinely new records.
    second = first + [oa_record(f"c{i}") for i in range(4)]
    counts = _acquire(
        conn,
        task_id,
        seed_run(conn, task_id),  # one coverage row per run
        scope_id,
        [_call("openalex", second)],
        cap=4,
    )

    assert counts["already_acquired"] == 4
    assert counts["acquired"] == 4, "the cap should fill with new documents"
    assert counts["dropped_over_cap"] == 0
    assert _persisted_titles(conn, task_id) == {f"OpenAlex record a{i}" for i in range(4)} | {
        f"OpenAlex record c{i}" for i in range(4)
    }


def test_dedup_keeps_the_best_ranked_copy(conn: Connection) -> None:
    """A document ranked highly by one query is not lost to a low-ranked twin.

    Dedup walks the interleaved stream, so the rank-1 copy in the second query
    claims the identity before the rank-5 copy in the first query is reached.
    """
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    shared = oa_record("shared")
    calls = [
        _call("openalex", [oa_record(f"a{i}") for i in range(4)] + [shared], query="q1"),
        _call("openalex", [shared, oa_record("b1")], query="q2"),
    ]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=2)

    assert counts["acquired"] == 2
    assert "OpenAlex record shared" in _persisted_titles(conn, task_id)


def test_dropped_records_do_not_claim_identities(conn: Connection) -> None:
    """A record dropped over the cap must not shadow a later backend's copy.

    The identity guards *claim* the keys they check. Running them on a record
    that is about to be trimmed would mark its DOI as seen, and the Overton
    copy of that same document would then be counted already-acquired and
    silently lost — the grey-literature loss this cap exists to prevent,
    reintroduced one layer down.
    """
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    shared_doi = "10.1234/shared-doc"
    overton_twin = _ov_record("twin")
    overton_twin["keyed_other_identifiers"] = {"doi": [shared_doi]}
    calls = [
        # The twin sits past OpenAlex's cap of 2, so it is dropped.
        _call(
            "openalex",
            [oa_record("a0"), oa_record("a1"), oa_record("a2", doi=shared_doi)],
        ),
        _call("overton", [overton_twin]),
    ]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=2)

    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 1
    assert counts["by_backend"]["overton"]["acquired"] == 1, (
        "Overton's copy must survive a trimmed OpenAlex twin"
    )
    assert "Overton document twin" in _persisted_titles(conn, task_id)


def test_every_pool_entry_counts_toward_the_cap(conn: Connection) -> None:
    """Citation-found records are pool members like any other (task 051, D7):
    the old exemption for targeted verbs is gone, the cap bounds the pool."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    calls = [
        _call("openalex", [oa_record(f"s{i}") for i in range(5)], verb="fetch_citations"),
        _call("openalex", [oa_record(f"q{i}") for i in range(5)]),
    ]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=1)

    assert counts["acquired"] == 1
    assert counts["dropped_over_cap"] == 9


def test_cap_none_acquires_everything(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(12)])]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=None)

    assert counts["acquired"] == 12
    assert counts["dropped_over_cap"] == 0


def test_results_returned_reports_the_untrimmed_provider_response(
    conn: Connection,
) -> None:
    """The trim must not make the run look like the provider returned less."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(9)])]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=2)

    assert counts["results_returned"] == 9
    assert (
        counts["acquired"]
        + counts["already_acquired"]
        + counts["skipped_unusable"]
        + counts["dropped_over_cap"]
        == counts["results_returned"]
    )


def test_dropped_records_are_not_persisted_or_embedded(conn: Connection) -> None:
    """Trimmed candidates cost nothing: no snapshot row, so no chunk to embed."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(20)])]

    counts = _acquire(conn, task_id, run_id, scope_id, calls, cap=3)

    persisted = conn.execute(
        select(func.count())
        .select_from(task_source_snapshot)
        .where(task_source_snapshot.c.task_id == task_id)
    ).scalar_one()
    assert persisted == 3
    assert counts["embed"]["embedded"] <= 3
