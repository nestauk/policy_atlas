"""Tests for the per-round acquisition cap: merge, dedup, trim, persist.

The cap replaced the standard/deep wall clock as the run's volume brake. Its
contract is: rank-interleave the search fan-out so every query is represented,
dedup *before* trimming so a capped round still yields a full cap of new
documents, cap each backend separately, and never trim targeted verbs.
"""

import uuid
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import project_source_snapshot, source_snapshot
from policy_atlas.evidence_base.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    _Candidate,
    _interleave,
    acquire_sources,
)
from policy_atlas.evidence_base.sourcing.search_loop import ExecutedCall
from tests.helpers import oa_record, seed_project_and_run, seed_run, seed_scope
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend


def _candidate(name: str) -> _Candidate:
    """A candidate carrying only the fields _interleave reads."""
    return _Candidate(
        backend_name="openalex",
        verb="search",
        record={},
        mapped={},
        text=name,
        chash=name,
    )


def _names(candidates: list[_Candidate]) -> list[str]:
    return [candidate.text for candidate in candidates]


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
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    calls: list[ExecutedCall],
    *,
    cap: int | None,
) -> dict[str, Any]:
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    return acquire_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=cast("list[SearchBackend]", backends),
        executed_calls=calls,
        record_cap_per_backend=cap,
    )


def _persisted_titles(conn: Connection, project_id: uuid.UUID) -> set[str]:
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()
    return {row.metadata["title"] for row in rows}


# --- _interleave (pure) ---


def test_interleave_round_robins_by_rank_position() -> None:
    merged = _interleave(
        [
            [_candidate("A1"), _candidate("A2"), _candidate("A3")],
            [_candidate("B1"), _candidate("B2"), _candidate("B3")],
            [_candidate("C1"), _candidate("C2"), _candidate("C3")],
        ]
    )
    assert _names(merged) == ["A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"]


def test_interleave_drains_uneven_calls_without_reordering_the_rest() -> None:
    """A short query stops contributing; the others keep their rank order."""
    merged = _interleave(
        [
            [_candidate("A1")],
            [_candidate("B1"), _candidate("B2"), _candidate("B3")],
        ]
    )
    assert _names(merged) == ["A1", "B1", "B2", "B3"]


def test_interleave_handles_no_calls_and_empty_calls() -> None:
    assert _interleave([]) == []
    assert _interleave([[], []]) == []


# --- Cap behaviour through acquire_sources ---


def test_cap_keeps_the_top_ranked_slice_of_every_query(conn: Connection) -> None:
    """With a cap of 4 across two queries, each contributes its top 2."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [
        _call("openalex", [oa_record(f"a{i}") for i in range(5)], query="q1"),
        _call("openalex", [oa_record(f"b{i}") for i in range(5)], query="q2"),
    ]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=4)

    assert counts["acquired"] == 4
    assert counts["dropped_over_cap"] == 6
    assert counts["results_returned"] == 10
    titles = _persisted_titles(conn, project_id)
    assert titles == {
        "OpenAlex record a0",
        "OpenAlex record a1",
        "OpenAlex record b0",
        "OpenAlex record b1",
    }


def test_cap_is_per_backend(conn: Connection) -> None:
    """OpenAlex breaching its cap does not consume Overton's."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [
        _call("openalex", [oa_record(f"a{i}") for i in range(10)]),
        _call("overton", [_ov_record(f"b{i}") for i in range(10)]),
    ]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=3)

    assert counts["by_backend"]["openalex"]["acquired"] == 3
    assert counts["by_backend"]["overton"]["acquired"] == 3
    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 7
    assert counts["by_backend"]["overton"]["dropped_over_cap"] == 7


def test_dedup_runs_before_the_trim_so_the_cap_is_filled(conn: Connection) -> None:
    """Repeats from an earlier round do not consume cap slots.

    This is the property that makes later deep rounds work as hard as the
    first: capping candidates instead of acquisitions would let a round of
    mostly-repeats acquire far fewer than its budget.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    first = [oa_record(f"a{i}") for i in range(4)]
    _acquire(conn, project_id, run_id, scope_id, [_call("openalex", first)], cap=None)
    assert _persisted_titles(conn, project_id) == {
        f"OpenAlex record a{i}" for i in range(4)
    }

    # Round 2 re-returns all four, then four genuinely new records.
    second = first + [oa_record(f"c{i}") for i in range(4)]
    counts = _acquire(
        conn,
        project_id,
        seed_run(conn, project_id),  # one coverage row per run
        scope_id,
        [_call("openalex", second)],
        cap=4,
    )

    assert counts["already_acquired"] == 4
    assert counts["acquired"] == 4, "the cap should fill with new documents"
    assert counts["dropped_over_cap"] == 0
    assert _persisted_titles(conn, project_id) == {
        f"OpenAlex record a{i}" for i in range(4)
    } | {f"OpenAlex record c{i}" for i in range(4)}


def test_dedup_keeps_the_best_ranked_copy(conn: Connection) -> None:
    """A document ranked highly by one query is not lost to a low-ranked twin.

    Dedup walks the interleaved stream, so the rank-1 copy in the second query
    claims the identity before the rank-5 copy in the first query is reached.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    shared = oa_record("shared")
    calls = [
        _call("openalex", [oa_record(f"a{i}") for i in range(4)] + [shared], query="q1"),
        _call("openalex", [shared, oa_record("b1")], query="q2"),
    ]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=2)

    assert counts["acquired"] == 2
    assert "OpenAlex record shared" in _persisted_titles(conn, project_id)


def test_dropped_records_do_not_claim_identities(conn: Connection) -> None:
    """A record dropped over the cap must not shadow a later backend's copy.

    The identity guards *claim* the keys they check. Running them on a record
    that is about to be trimmed would mark its DOI as seen, and the Overton
    copy of that same document would then be counted already-acquired and
    silently lost — the grey-literature loss this cap exists to prevent,
    reintroduced one layer down.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
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

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=2)

    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 1
    assert counts["by_backend"]["overton"]["acquired"] == 1, (
        "Overton's copy must survive a trimmed OpenAlex twin"
    )
    assert "Overton document twin" in _persisted_titles(conn, project_id)


def test_targeted_verbs_are_never_trimmed(conn: Connection) -> None:
    """Snowball and suggest results are individually chosen; their arms cap upstream."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [
        _call("openalex", [oa_record(f"s{i}") for i in range(5)], verb="fetch_citations"),
        _call("openalex", [oa_record(f"q{i}") for i in range(5)]),
    ]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=1)

    # 5 snowball records kept in full, plus 1 from the capped search fan-out.
    assert counts["acquired"] == 6
    assert counts["dropped_over_cap"] == 4


def test_cap_none_acquires_everything(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(12)])]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=None)

    assert counts["acquired"] == 12
    assert counts["dropped_over_cap"] == 0


def test_results_returned_reports_the_untrimmed_provider_response(
    conn: Connection,
) -> None:
    """The trim must not make the run look like the provider returned less."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(9)])]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=2)

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
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    calls = [_call("openalex", [oa_record(f"a{i}") for i in range(20)])]

    counts = _acquire(conn, project_id, run_id, scope_id, calls, cap=3)

    persisted = conn.execute(
        select(func.count())
        .select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == project_id)
    ).scalar_one()
    assert persisted == 3
    assert counts["embed"]["embedded"] <= 3
