"""Decision-20 mapping-layer deltas + the executed-calls counting invariant.

Follows tests/test_acquire.py's patterns (FakeBackend, oa_record/ov_record-style
builders, seed helpers, the ``conn`` DB fixture).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.acquire import (
    REFERENCED_WORKS_RETAIN_CAP,
    AcquireContext,
    _map_openalex_work,
    _map_overton_document,
    acquire_sources,
)
from policy_atlas.schema import (
    project_source_snapshot,
    search_coverage_record,
    source_snapshot,
    source_tag,
)
from tests.helpers import oa_record, seed_project_and_run, seed_scope
from tests.test_acquire import FakeBackend, assert_invariant, ov_record

# --- _map_openalex_work: decision-20 retain-key deltas ---


def test_map_openalex_indexed_in_and_publication_date_retained_when_present() -> None:
    record = oa_record()
    record["indexed_in"] = ["crossref", "doaj"]
    record["publication_date"] = "2020-05-01"
    mapped = _map_openalex_work(record)
    assert mapped is not None
    assert mapped["provider_fields"]["indexed_in"] == ["crossref", "doaj"]
    assert mapped["provider_fields"]["publication_date"] == "2020-05-01"


def test_map_openalex_referenced_works_capped_at_60() -> None:
    record = oa_record()
    record["referenced_works"] = [f"https://example.org/W{i}" for i in range(70)]
    mapped = _map_openalex_work(record)
    assert mapped is not None
    retained = mapped["provider_fields"]["referenced_works"]
    assert len(retained) == REFERENCED_WORKS_RETAIN_CAP == 60
    assert retained == record["referenced_works"][:60]


def test_map_openalex_referenced_works_absent_or_empty_key_absent() -> None:
    mapped = _map_openalex_work(oa_record())
    assert mapped is not None
    assert "referenced_works" not in mapped["provider_fields"]

    record2 = oa_record()
    record2["referenced_works"] = []
    mapped2 = _map_openalex_work(record2)
    assert mapped2 is not None
    assert "referenced_works" not in mapped2["provider_fields"]


def test_map_openalex_title_source_none_absent_from_persisted_metadata(
    conn: Connection,
) -> None:
    """title_source=None follows the None-omission pattern (decision 20)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=[FakeBackend(records=[oa_record()])],
    )
    (meta,) = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == pid)
    ).one()
    assert "title_source" not in meta


# --- _map_overton_document: English-first title cases ---


def test_map_overton_translated_present_native_retained_in_provider_fields() -> None:
    record = ov_record(title="Titre natif")
    record["translated_title"] = "Native title, translated"
    mapped = _map_overton_document(record)
    assert mapped is not None
    assert mapped["envelope"]["title"] == "Native title, translated"
    assert mapped["title_source"] == "translated"
    assert mapped["provider_fields"]["title"] == "Titre natif"


def test_map_overton_translated_empty_string_falls_back_to_native() -> None:
    record = ov_record(title="Native only title")
    record["translated_title"] = ""
    mapped = _map_overton_document(record)
    assert mapped is not None
    assert mapped["envelope"]["title"] == "Native only title"
    assert mapped["title_source"] == "native"


def test_map_overton_both_titles_absent_unusable() -> None:
    record = ov_record(title="")
    record["translated_title"] = ""
    assert _map_overton_document(record) is None


# --- Tags: source_tags -> topic_theme, series -> methodological_structural,
#     keywords never tagged (the deliberate-refusal pin) ---


def test_overton_source_tags_and_series_materialise_as_expected_tag_rows(
    conn: Connection,
) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    record = ov_record(snippet="s")
    record["source_tags"] = ["HOUSING POLICY"]
    record["overton_policy_document_series"] = "Working paper"
    record["llm_document_theme"] = "Affordable housing"

    counts = acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=[
            FakeBackend(
                name="overton", trust_class="grey_literature_aggregator", records=[record]
            )
        ],
    )
    assert counts["acquired"] == 1

    (pss_id,) = conn.execute(
        select(project_source_snapshot.c.project_source_snapshot_id).where(
            project_source_snapshot.c.project_id == pid
        )
    ).one()

    rows = conn.execute(
        select(source_tag.c.tag, source_tag.c.tag_type, source_tag.c.asserted_by).where(
            source_tag.c.project_source_snapshot_id == pss_id
        )
    ).fetchall()
    triples = {(row.tag, row.tag_type, row.asserted_by) for row in rows}
    assert ("HOUSING POLICY", "topic_theme", "overton") in triples
    assert ("Working paper", "methodological_structural", "overton") in triples
    assert ("Affordable housing", "topic_theme", "overton_llm") in triples


def test_openalex_keywords_never_produce_tag_rows(conn: Connection) -> None:
    """Deliberate refusal (decision 20): 'keywords' promotion produced disambiguation noise."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    record = oa_record()
    record["keywords"] = [{"display_name": "Stock (firearms)"}, {"display_name": "Housing"}]

    counts = acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=[FakeBackend(records=[record])],
    )
    assert counts["acquired"] == 1

    (pss_id,) = conn.execute(
        select(project_source_snapshot.c.project_source_snapshot_id).where(
            project_source_snapshot.c.project_id == pid
        )
    ).one()
    rows = conn.execute(
        select(source_tag.c.tag).where(source_tag.c.project_source_snapshot_id == pss_id)
    ).fetchall()
    tags = {row.tag for row in rows}
    assert "Stock (firearms)" not in tags
    assert "Housing" not in tags


# --- Counting invariant on the executed-calls path ---


@dataclass(frozen=True)
class _ExecutedCallStub:
    """A minimal ``ExecutedSearchCall``-shaped stand-in, built by hand for this test."""

    backend_name: str
    verb: str
    query: str
    query_origin: str
    wire_params: dict[str, str]
    records: list[dict[str, Any]]
    status: str
    error: str | None
    post_filter_excluded: int | None = None


def test_counting_invariant_across_executed_calls_and_backends(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)

    shared_doi = "https://doi.org/10.99999/SHARED-CALL"
    oa_ok = _ExecutedCallStub(
        backend_name="openalex",
        verb="search",
        query="q1",
        query_origin="generated",
        wire_params={"filter": "type:article"},
        records=[oa_record(rid="https://example.org/Wcall", doi=shared_doi)],
        status="ok",
        error=None,
    )
    oa_error = _ExecutedCallStub(
        backend_name="openalex",
        verb="fetch_citations",
        query="https://example.org/Wcall",
        query_origin="snowball_forward",
        wire_params={},
        records=[],
        status="error",
        error="boom",
    )
    ov_ok = _ExecutedCallStub(
        backend_name="overton",
        verb="search",
        query="q2",
        query_origin="verbatim",
        wire_params={"squery": "q2", "min_similarity": "0.3"},
        records=[ov_record(rid="org-dup", snippet="s", doi="10.99999/shared-call")],
        status="ok",
        error=None,
    )

    scope_wire_params = {
        "openalex": {"filter": "type:article"},
        "overton": {"squery": "q2", "min_similarity": "0.3"},
    }
    counts = acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=[
            FakeBackend(name="openalex", trust_class="academic_aggregator"),
            FakeBackend(name="overton", trust_class="grey_literature_aggregator"),
        ],
        executed_calls=[oa_ok, oa_error, ov_ok],
        depth="deep",
        scope_wire_params=scope_wire_params,
    )

    assert_invariant(counts)
    assert counts["acquired"] == 1
    assert counts["already_acquired"] == 1  # ov_ok's record is a cross-backend DOI dup
    assert counts["by_backend"]["openalex"]["acquired"] == 1
    assert counts["by_backend"]["openalex"]["results_returned"] == 1
    assert counts["by_backend"]["overton"]["already_acquired"] == 1
    assert counts["by_backend"]["overton"]["results_returned"] == 1

    # backend with one ok + one error call keeps status "ok"
    assert counts["by_backend"]["openalex"]["status"] == "ok"
    assert counts["by_backend"]["openalex"]["error"] is not None
    assert "boom" in counts["by_backend"]["openalex"]["error"]
    assert counts["by_backend"]["overton"]["status"] == "ok"

    searched = [e for e in events.read(conn, pid) if e["event_type"] == "search.executed"]
    assert len(searched) == 3
    for payload in (e["payload"] for e in searched):
        assert {"query_origin", "verb", "depth", "filters"} <= set(payload)
        assert payload["depth"] == "deep"

    row = conn.execute(
        select(search_coverage_record.c.backends, search_coverage_record.c.scope_filters).where(
            search_coverage_record.c.acquired_by_run_id == rid
        )
    ).one()
    assert all(entry["depth"] == "deep" for entry in row.backends)
    assert row.scope_filters == scope_wire_params

    assert counts["acquired_pss_by_verb"].keys() == {"search"}
    assert len(counts["acquired_pss_by_verb"]["search"]) == 1
