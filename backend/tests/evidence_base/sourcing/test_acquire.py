"""Tests for the acquire component — mappings, dedup, events, coverage record, fixtures."""

import json
import re
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    chunk,
    metadata,
    project,
    project_source_snapshot,
    search_coverage_record,
    source_snapshot,
)
from policy_atlas.evidence_base.assess.appraise import AppraiseContext, appraise_sources
from policy_atlas.evidence_base.assess.classify import ClassifyContext, classify_sources
from policy_atlas.evidence_base.assess.screen import ScreenContext, screen_sources
from policy_atlas.evidence_base.sourcing.acquire import (
    AcquireContext,
    BackendCaps,
    SearchBackend,
    _map_openalex_work,
    _map_overton_document,
    _normalize_doi,
    _reconstruct_abstract,
    acquire_sources,
)
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    delete_project_data,
    executed_calls_for,
    now,
    oa_record,
    seed_project_and_run,
    seed_run,
    seed_scope,
)
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend

# --- Test doubles / builders ---


class FakeBackend:
    """Configurable in-test backend: fixed records or a raised exception."""

    def __init__(
        self,
        name: str = "openalex",
        trust_class: str = "academic_aggregator",
        mode: str = "fixture",
        records: list[dict[str, Any]] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.name = name
        self.trust_class = trust_class
        self.mode = mode
        self.caps = BackendCaps(has_snowball=False, has_title_lookup=False)
        self._records = records or []
        self._exc = exc

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        if self._exc is not None:
            raise self._exc
        records = self._records
        return records if max_results is None else records[:max_results]

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("FakeBackend caps.has_snowball=False")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("FakeBackend caps.has_snowball=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        raise NotImplementedError("FakeBackend caps.has_title_lookup=False")

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("FakeBackend caps.has_doi_lookup=False")


def ov_record(
    rid: str = "org-abc123",
    title: str | None = "Cobalt harbor juniper",
    snippet: str = "",
    llm_description: str = "",
    doi: str | None = None,
) -> dict[str, Any]:
    return {
        "policy_document_id": rid,
        "pdf_document_id": rid + "-pdf",
        "title": title,
        "translated_title": "",
        "snippet": snippet,
        "llm_document_description": llm_description,
        "published_on": "2021-06-01",
        "keyed_other_identifiers": {"doi": [doi]} if doi else [],
        "source": {"title": "Marble Agency", "type": "government"},
        "document_url": "https://example.org/doc1",
        "overton_url": "https://example.org/ov1",
        "languages": ["eng"],
        "authors": [],
        "topics": [],
    }


def make_context(scope_id: uuid.UUID) -> AcquireContext:
    return AcquireContext(scope_id=scope_id, intent="Test intent", context={})


def acquire(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    backends: list[Any] | None = None,
) -> dict[str, Any]:
    context = make_context(scope_id)
    resolved_backends = (
        backends if backends is not None
        else [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    )
    return acquire_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=context,
        backends=cast("list[SearchBackend]", resolved_backends),
        executed_calls=executed_calls_for(resolved_backends, context.intent),
    )


def assert_invariant(counts: dict[str, Any]) -> None:
    """acquired + already_acquired + skipped_unusable == results_returned, at both levels."""
    assert (
        counts["acquired"] + counts["already_acquired"] + counts["skipped_unusable"]
        == counts["results_returned"]
    )
    for b in counts["by_backend"].values():
        assert (
            b["acquired"] + b["already_acquired"] + b["skipped_unusable"]
            == b["results_returned"]
        )


# --- Schema / structure ---


def test_acquire_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 30


def seed_coverage_row(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    **overrides: Any,
) -> None:
    values: dict[str, Any] = {
        "search_coverage_record_id": uuid.uuid4(),
        "evidence_scope_id": scope_id,
        "project_id": project_id,
        "acquired_by_run_id": run_id,
        "backends": [{"backend": "openalex", "trust_class": "academic_aggregator",
                      "mode": "fixture"}],
        "scope_filters": {},
        "stop_condition": "breadth_truncated",
        "adequacy_verdict": "adequate",
        "verdict_origin": "model",
        "created_at": now(),
    }
    values.update(overrides)
    conn.execute(search_coverage_record.insert().values(**values))


@pytest.mark.parametrize(
    ("constraint", "overrides"),
    [
        # 'saturated' is deliberately not accepted — saturation stopping is a deferred seam
        ("ck_scov_stop_condition", {"stop_condition": "saturated"}),
        ("ck_scov_verdict", {"adequacy_verdict": "partial"}),
        ("ck_scov_verdict_origin", {"verdict_origin": "oracle"}),
        ("ck_scov_backends_array", {"backends": {"backend": "openalex"}}),
        ("ck_scov_filters_object", {"scope_filters": []}),
    ],
)
def test_scov_check_constraints(
    conn: Connection, constraint: str, overrides: dict[str, Any]
) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    with pytest.raises(IntegrityError, match=constraint):
        seed_coverage_row(conn, pid, rid, scope_id, **overrides)


def test_scov_cross_project_fk_rejected(conn: Connection) -> None:
    pid_a, rid_a = seed_project_and_run(conn)
    pid_b, _ = seed_project_and_run(conn)
    scope_b = seed_scope(conn, pid_b)
    # scope from project B with project A's id/run: composite FK must reject
    with pytest.raises(IntegrityError, match="fk_scov_scope_project"):
        seed_coverage_row(conn, pid_a, rid_a, scope_b)


def test_scov_one_record_per_run(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_coverage_row(conn, pid, rid, scope_id)
    with pytest.raises(IntegrityError, match="uq_scov_run"):
        seed_coverage_row(conn, pid, rid, scope_id)


# --- Mapping layer (pure Python, no DB) ---


def test_reconstruct_abstract_multi_position() -> None:
    assert _reconstruct_abstract({"b": [1], "a": [0, 2]}) == "a b a"


def test_reconstruct_abstract_empty_and_missing() -> None:
    assert _reconstruct_abstract({}) is None
    assert _reconstruct_abstract(None) is None


def test_reconstruct_abstract_from_committed_fixture() -> None:
    """A structurally real inverted index (recorded shape) reconstructs in order."""
    records = OpenAlexFixtureBackend().search("any")
    indexed = [r for r in records if r.get("abstract_inverted_index")]
    assert indexed, "fixture must carry at least one real inverted index"
    multi = [
        r for r in indexed
        if any(len(p) > 1 for p in r["abstract_inverted_index"].values())
    ]
    assert multi, "fixture must carry a multi-position token"
    index = multi[0]["abstract_inverted_index"]
    text = _reconstruct_abstract(index)
    assert text is not None
    tokens = text.split(" ")
    total_positions = sum(len(p) for p in index.values())
    assert len(tokens) == total_positions
    for token, positions in index.items():
        for pos in positions:
            assert tokens[pos] == token


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://doi.org/10.99999/AbC", "10.99999/abc"),
        ("http://doi.org/10.99999/x", "10.99999/x"),
        ("https://dx.doi.org/10.99999/y", "10.99999/y"),
        ("  10.99999/Z  ", "10.99999/z"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_doi(raw: str | None, expected: str | None) -> None:
    assert _normalize_doi(raw) == expected


def test_map_openalex_envelope() -> None:
    mapped = _map_openalex_work(
        oa_record(index={"quartz": [0]}, doi="https://doi.org/10.99999/QQ")
    )
    assert mapped is not None
    env = mapped["envelope"]
    assert env["title"] == "Quartz meadow lantern"
    assert env["abstract"] == "quartz"
    assert env["year"] == 2020
    assert env["doi"] == "10.99999/qq"
    assert env["language"] == "en"
    assert env["backend"] == "openalex"
    assert env["backend_record_id"] == "https://example.org/W1"
    assert env["record_type"] == "article"
    assert env["publisher_org"] == "Willow Journal"
    assert mapped["abstract_source"] == "publisher_abstract"
    assert mapped["source_locator"] == "https://example.org/W1"


def test_map_openalex_no_title_unusable() -> None:
    assert _map_openalex_work(oa_record(title=None)) is None
    assert _map_openalex_work({}) is None


def test_map_openalex_no_id_unusable() -> None:
    """No id -> no locator, no re-run identity: unusable, never a NOT NULL crash."""
    rec = oa_record()
    rec["id"] = None
    assert _map_openalex_work(rec) is None


def test_map_openalex_missing_abstract() -> None:
    mapped = _map_openalex_work(oa_record(index=None))
    assert mapped is not None
    assert mapped["envelope"]["abstract"] is None
    assert mapped["abstract_source"] == "none"


def test_map_overton_envelope_snippet() -> None:
    mapped = _map_overton_document(
        ov_record(snippet="A quartz snippet.", llm_description="LLM text",
                  doi="10.99999/OV")
    )
    assert mapped is not None
    env = mapped["envelope"]
    assert env["abstract"] == "A quartz snippet."
    assert mapped["abstract_source"] == "snippet"
    assert env["doi"] == "10.99999/ov"  # from keyed_other_identifiers.doi[0], normalized
    assert env["year"] == 2021
    assert env["backend"] == "overton"
    assert env["backend_record_id"] == "org-abc123"
    assert env["record_type"] == "government"
    assert env["publisher_org"] == "Marble Agency"
    assert mapped["source_locator"] == "https://example.org/doc1"


def test_map_overton_llm_description_fallback() -> None:
    """Empty-string snippet is absent; the LLM summary is used and marked as such."""
    mapped = _map_overton_document(ov_record(snippet="", llm_description="Machine words"))
    assert mapped is not None
    assert mapped["envelope"]["abstract"] == "Machine words"
    assert mapped["abstract_source"] == "llm_description"


def test_map_overton_neither_summary() -> None:
    mapped = _map_overton_document(ov_record())
    assert mapped is not None
    assert mapped["envelope"]["abstract"] is None
    assert mapped["abstract_source"] == "none"


def test_map_overton_title_fallback_and_unusable() -> None:
    rec = ov_record(title="")
    rec["translated_title"] = "Translated quartz"
    mapped = _map_overton_document(rec)
    assert mapped is not None
    assert mapped["envelope"]["title"] == "Translated quartz"
    rec2 = ov_record(title="")
    assert _map_overton_document(rec2) is None  # neither title nor translated title


def test_map_overton_string_or_list_shapes() -> None:
    """authors/topics arrive as string or list (v2-confirmed) — both tolerated."""
    rec = ov_record(snippet="s")
    rec["authors"] = "Alex Sampleton"
    rec["topics"] = "Affordable housing"
    assert _map_overton_document(rec) is not None
    rec2 = ov_record(snippet="s")
    rec2["authors"] = ["Alex Sampleton"]
    rec2["topics"] = ["Affordable housing"]
    assert _map_overton_document(rec2) is not None


def test_map_overton_absent_shapes_tolerated() -> None:
    """Absence of doi/source/urls/authors/topics is authentic data, not an error."""
    mapped = _map_overton_document(
        {"policy_document_id": "org-x", "title": "Quartz", "overton_url":
         "https://example.org/o"}
    )
    assert mapped is not None
    env = mapped["envelope"]
    assert env["doi"] is None
    assert env["record_type"] is None
    assert env["publisher_org"] is None
    assert env["year"] is None
    assert mapped["source_locator"] == "https://example.org/o"  # document_url fallback


def test_map_overton_no_locator_unusable() -> None:
    """Neither document_url nor overton_url -> unusable, never a NOT NULL crash."""
    rec = ov_record()
    rec["document_url"] = ""
    rec["overton_url"] = ""
    assert _map_overton_document(rec) is None


def test_map_overton_empty_string_language_absent() -> None:
    """languages=[''] is Overton's absence pattern -> envelope language is None."""
    rec = ov_record(snippet="s")
    rec["languages"] = [""]
    mapped = _map_overton_document(rec)
    assert mapped is not None
    assert mapped["envelope"]["language"] is None


def test_map_overton_empty_source_locator_falls_back() -> None:
    rec = ov_record()
    rec["document_url"] = ""
    mapped = _map_overton_document(rec)
    assert mapped is not None
    assert mapped["source_locator"] == "https://example.org/ov1"


# --- Round-trip: fixtures -> snapshots ---


def test_acquire_round_trip_both_backends(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    counts = acquire(conn, pid, rid, scope_id)

    assert counts["by_backend"]["openalex"]["acquired"] == 12
    assert counts["by_backend"]["overton"]["acquired"] == 12
    assert counts["acquired"] == 24
    assert_invariant(counts)

    rows = conn.execute(
        select(project_source_snapshot, source_snapshot)
        .join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        )
        .where(project_source_snapshot.c.project_id == pid)
    ).fetchall()
    assert len(rows) == 24
    for row in rows:
        assert row.origin == "acquired"
        assert row.run_id == rid
        assert row.text_basis == "abstract_only"
        assert row.source_locator
        assert row.metadata["abstract_source"] in (
            "publisher_abstract", "snippet", "llm_description", "none"
        )
        assert "provider_fields" in row.metadata
        chunks = conn.execute(
            select(chunk).where(chunk.c.source_snapshot_id == row.source_snapshot_id)
        ).fetchall()
        assert len(chunks) == 1
        assert chunks[0].segmentation_policy == "metadata_envelope_v1"
        assert chunks[0].content_hash == content_hash(chunks[0].content)
        assert row.content_hash == content_hash(chunks[0].content)
        assert chunks[0].content.startswith(row.metadata["title"])


def test_acquired_metadata_provider_fields_url_oa_block(conn: Connection) -> None:
    """URL/OA block retained at minimum (required by slice 008)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(project_source_snapshot.join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        ))
        .where(project_source_snapshot.c.project_id == pid)
    ).fetchall()
    for (meta,) in rows:
        pf = meta["provider_fields"]
        if meta["backend"] == "openalex":
            assert "primary_location" in pf or "open_access" in pf
            assert "authorships" in pf
        else:
            assert "document_url" in pf or "pdf_url" in pf
            assert "source" in pf


def test_abstract_source_four_cases_persisted(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)
    sources = {
        meta["abstract_source"]
        for (meta,) in conn.execute(
            select(source_snapshot.c.metadata)
            .select_from(project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ))
            .where(project_source_snapshot.c.project_id == pid)
        )
    }
    assert sources == {"publisher_abstract", "snippet", "llm_description", "none"}


def test_absent_envelope_values_not_persisted_as_null(conn: Connection) -> None:
    """None-valued envelope keys persist as absent — the shape _stub_screen fail-opens on."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)
    metas = [
        meta for (meta,) in conn.execute(
            select(source_snapshot.c.metadata)
            .select_from(project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ))
            .where(project_source_snapshot.c.project_id == pid)
        )
    ]
    abstract_less = [m for m in metas if m["abstract_source"] == "none"]
    assert abstract_less, "fixtures must include abstract-less records"
    for m in abstract_less:
        assert "abstract" not in m
    for m in metas:
        assert all(v is not None for v in m.values() if not isinstance(v, dict))


# --- Idempotency + identity guards ---


def test_acquire_idempotent_rerun(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    first = acquire(conn, pid, rid, scope_id)
    assert_invariant(first)

    second = acquire(conn, pid, seed_run(conn, pid), scope_id)
    assert second["acquired"] == 0
    assert second["already_acquired"] == first["acquired"] + first["already_acquired"]
    assert_invariant(second)

    n_snapshots = conn.execute(
        select(sa.func.count()).select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == pid)
    ).scalar_one()
    assert n_snapshots == first["acquired"]

    # coverage records are per-run audit state, never deduped
    n_cov = conn.execute(
        select(sa.func.count()).select_from(search_coverage_record)
        .where(search_coverage_record.c.project_id == pid)
    ).scalar_one()
    assert n_cov == 2
    assert second["coverage_record_id"] != first["coverage_record_id"]


def test_identity_guards_each_separately(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)

    def fresh_run() -> uuid.UUID:
        return seed_run(conn, pid)

    # guard (a): backend_record_id — same id, changed content
    acquire(conn, pid, rid, scope_id, backends=[
        FakeBackend(records=[oa_record(rid="https://example.org/W9", title="First words")])
    ])
    counts = acquire(conn, pid, fresh_run(), scope_id, backends=[
        FakeBackend(records=[oa_record(rid="https://example.org/W9", title="Changed words")])
    ])
    assert counts["already_acquired"] == 1 and counts["acquired"] == 0

    # guard (b): normalized DOI across backends — prefixed vs bare, mixed case
    acquire(conn, pid, fresh_run(), scope_id, backends=[
        FakeBackend(records=[
            oa_record(rid="https://example.org/W10", title="Doi carrier",
                      doi="https://doi.org/10.99999/DUP")
        ])
    ])
    counts = acquire(conn, pid, fresh_run(), scope_id, backends=[
        FakeBackend(
            name="overton",
            trust_class="grey_literature_aggregator",
            records=[ov_record(rid="org-dup", title="Different title",
                               snippet="s", doi="10.99999/dup")],
        )
    ])
    assert counts["already_acquired"] == 1 and counts["acquired"] == 0

    # guard (c): content hash — same text, no shared id or doi
    acquire(conn, pid, fresh_run(), scope_id, backends=[
        FakeBackend(records=[oa_record(rid="https://example.org/W11", title="Same text")])
    ])
    counts = acquire(conn, pid, fresh_run(), scope_id, backends=[
        FakeBackend(records=[oa_record(rid="https://example.org/W12", title="Same text")])
    ])
    assert counts["already_acquired"] == 1 and counts["acquired"] == 0


def test_cross_backend_doi_dedup_deterministic_winner(conn: Connection) -> None:
    """Two records sharing a DOI, one per backend -> one snapshot, list-order winner."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    oa = FakeBackend(records=[
        oa_record(rid="https://example.org/W1", title="Academic version",
                  doi="https://doi.org/10.99999/SHARED")
    ])
    ov = FakeBackend(
        name="overton",
        trust_class="grey_literature_aggregator",
        records=[ov_record(rid="org-shared", title="Policy version", snippet="s",
                           doi="10.99999/shared")],
    )
    counts = acquire(conn, pid, rid, scope_id, backends=[oa, ov])
    assert counts["acquired"] == 1
    assert counts["already_acquired"] == 1
    assert counts["by_backend"]["openalex"]["acquired"] == 1  # fixed order: OpenAlex wins
    assert counts["by_backend"]["overton"]["already_acquired"] == 1
    assert_invariant(counts)

    (meta,) = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(project_source_snapshot.join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        ))
        .where(project_source_snapshot.c.project_id == pid)
    ).one()
    assert meta["backend"] == "openalex"


def test_cross_project_dedup_isolation(conn: Connection) -> None:
    """Project B acquiring the same fixtures still gets its own links; A untouched."""
    pid_a, rid_a = seed_project_and_run(conn)
    scope_a = seed_scope(conn, pid_a)
    counts_a = acquire(conn, pid_a, rid_a, scope_a)

    pid_b, rid_b = seed_project_and_run(conn)
    scope_b = seed_scope(conn, pid_b)
    counts_b = acquire(conn, pid_b, rid_b, scope_b)

    assert counts_b["acquired"] == counts_a["acquired"] == 24
    assert counts_b["already_acquired"] == 0  # dedup never consults project A's rows

    for pid, expected in ((pid_a, 24), (pid_b, 24)):
        n = conn.execute(
            select(sa.func.count()).select_from(project_source_snapshot)
            .where(project_source_snapshot.c.project_id == pid)
        ).scalar_one()
        assert n == expected


def test_unknown_backend_name_rejected_upfront(conn: Connection) -> None:
    """A backend with no registered mapper is a wiring error — loud, before any work."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    stranger = FakeBackend(name="semantic_scholar", records=[oa_record()])
    with pytest.raises(ValueError, match="no mapper registered"):
        acquire(conn, pid, rid, scope_id, backends=[stranger])


def test_duplicate_backend_names_rejected_upfront(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    with pytest.raises(ValueError, match="duplicate backend names"):
        acquire(conn, pid, rid, scope_id, backends=[FakeBackend(), FakeBackend()])


def test_doi_guard_normalizes_persisted_uploaded_doi(conn: Connection) -> None:
    """An uploaded snapshot with a prefixed/mixed-case DOI still blocks re-acquisition."""
    from policy_atlas.evidence_base.sourcing.ingest_upload import ingest_upload

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    ingest_upload(
        conn,
        project_id=pid,
        chunks=["Uploaded text, different from any fixture."],
        source_locator="upload.pdf",
        metadata={"doi": "https://doi.org/10.99999/UPLOADED"},
        text_basis="full_text",
    )
    counts = acquire(conn, pid, rid, scope_id, backends=[
        FakeBackend(records=[oa_record(doi="10.99999/uploaded", title="Acquired twin")])
    ])
    assert counts["already_acquired"] == 1 and counts["acquired"] == 0


# --- Events ---


def test_search_executed_event_per_backend(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)
    searched = [e for e in events.read(conn, pid) if e["event_type"] == "search.executed"]
    assert len(searched) == 2
    by_backend = {e["payload"]["backend"]: e["payload"] for e in searched}
    assert set(by_backend) == {"openalex", "overton"}
    assert by_backend["openalex"]["trust_class"] == "academic_aggregator"
    assert by_backend["overton"]["trust_class"] == "grey_literature_aggregator"
    for payload in by_backend.values():
        assert payload["mode"] == "fixture"
        assert payload["query"] == "Test intent"
        assert payload["filters"] == {}
        assert payload["status"] == "ok"
        assert payload["result_count"] == 12
        assert payload["error"] is None
        assert payload["evidence_scope_id"] == str(scope_id)


def test_source_acquired_events(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)
    acquired_events = [
        e for e in events.read(conn, pid) if e["event_type"] == "source.acquired"
    ]
    assert len(acquired_events) == 24
    for e in acquired_events:
        payload = e["payload"]
        assert set(payload) == {
            "source_snapshot_id", "project_source_snapshot_id",
            "evidence_scope_id", "backend", "backend_record_id",
        }
        assert payload["evidence_scope_id"] == str(scope_id)

    # second run: skips/dedups emit no source.acquired
    acquire(conn, pid, seed_run(conn, pid), scope_id)
    acquired_events_after = [
        e for e in events.read(conn, pid) if e["event_type"] == "source.acquired"
    ]
    assert len(acquired_events_after) == 24


# --- Coverage record + adequacy verdict ---


def read_coverage(conn: Connection, run_id: uuid.UUID) -> Any:
    return conn.execute(
        select(search_coverage_record)
        .where(search_coverage_record.c.acquired_by_run_id == run_id)
    ).one()


def test_coverage_adequate_both_ok(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    counts = acquire(conn, pid, rid, scope_id)
    row = read_coverage(conn, rid)
    assert counts["adequacy_verdict"] == row.adequacy_verdict == "adequate"
    assert counts["stop_condition"] == row.stop_condition == "completed"
    assert row.verdict_origin == "model"
    assert row.scope_filters == {}
    assert row.backends == [
        {
            "backend": "openalex",
            "trust_class": "academic_aggregator",
            "mode": "fixture",
            "depth": "rapid",
        },
        {"backend": "overton", "trust_class": "grey_literature_aggregator",
         "mode": "fixture", "depth": "rapid"},
    ]


def test_coverage_inadequate_on_backend_error(conn: Connection) -> None:
    """A raising backend -> inadequate + error, run completes with healthy results."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    boom = FakeBackend(exc=RuntimeError("backend exploded"))
    counts = acquire(
        conn, pid, rid, scope_id, backends=[boom, OvertonFixtureBackend()]
    )
    assert counts["adequacy_verdict"] == "inadequate"
    assert counts["stop_condition"] == "error"
    assert counts["by_backend"]["openalex"]["status"] == "error"
    assert "backend exploded" in counts["by_backend"]["openalex"]["error"]
    assert counts["by_backend"]["overton"]["status"] == "ok"
    assert counts["by_backend"]["overton"]["acquired"] == 12  # healthy backend kept
    assert_invariant(counts)

    row = read_coverage(conn, rid)  # coverage record written even on error runs
    assert row.adequacy_verdict == "inadequate"
    assert row.stop_condition == "error"
    assert len(row.backends) == 2  # the errored backend stays in the search-space boundary

    err_events = [
        e["payload"] for e in events.read(conn, pid)
        if e["event_type"] == "search.executed" and e["payload"]["status"] == "error"
    ]
    assert len(err_events) == 1
    assert err_events[0]["backend"] == "openalex"
    assert err_events[0]["result_count"] == 0
    assert "backend exploded" in err_events[0]["error"]


def test_coverage_adequate_with_empty_but_successful_backend(conn: Connection) -> None:
    """Empty-but-successful beside a productive one is honest coverage, not inadequacy."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    empty = FakeBackend(records=[])
    counts = acquire(
        conn, pid, rid, scope_id, backends=[empty, OvertonFixtureBackend()]
    )
    assert counts["adequacy_verdict"] == "adequate"
    assert counts["stop_condition"] == "completed"


def test_coverage_inadequate_on_zero_usable(conn: Connection) -> None:
    """A page of title-less records counts for nothing -> inadequate."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    unusable = FakeBackend(records=[oa_record(title=None), oa_record(title=None)])
    counts = acquire(conn, pid, rid, scope_id, backends=[unusable])
    assert counts["skipped_unusable"] == 2
    assert counts["acquired"] == 0
    assert counts["adequacy_verdict"] == "inadequate"
    assert counts["stop_condition"] == "completed"  # no error occurred
    assert_invariant(counts)


def test_coverage_wall_clock_exceeded_when_breached_and_no_error(conn: Connection) -> None:
    """Honest stop attribution (task 019 item 5): a wall-clock breach with no
    backend error reports 'wall_clock_exceeded', not 'completed' or 'error'."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    context = make_context(scope_id)
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    counts = acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=context,
        backends=cast("list[SearchBackend]", backends),
        executed_calls=executed_calls_for(backends, context.intent),
        wall_clock_breached=True,
    )
    assert counts["adequacy_verdict"] == "adequate"
    assert counts["stop_condition"] == "wall_clock_exceeded"
    row = read_coverage(conn, rid)
    assert row.stop_condition == "wall_clock_exceeded"


def test_coverage_error_wins_over_wall_clock_breached(conn: Connection) -> None:
    """A backend error always reports 'error', even if the wall clock also breached."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    context = make_context(scope_id)
    boom = FakeBackend(exc=RuntimeError("backend exploded"))
    counts = acquire_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=context,
        backends=[boom],
        executed_calls=executed_calls_for([boom], context.intent),
        wall_clock_breached=True,
    )
    assert counts["stop_condition"] == "error"


# --- Harness integration ---


def test_harness_acquire_component(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    config = compile(Plan(component="acquire", evidence_scope_id=scope_id))
    run_harness(
        conn,
        config=config,
        project_id=pid,
        run_id=rid,
        provider=StubEchoProvider(),
        # Fixture pair injected explicitly: harness defaults are empty since the
        # provider fixtures moved to tests/ (task 023 owner rider).
        search_backends=[OpenAlexFixtureBackend(), OvertonFixtureBackend()],
    )

    n = conn.execute(
        select(sa.func.count()).select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == pid)
    ).scalar_one()
    assert n == 24  # fixture pair

    assert read_coverage(conn, rid) is not None
    log = events.read(conn, pid)
    assert sum(1 for e in log if e["event_type"] == "search.executed") == 2
    completed = [
        e["payload"] for e in log
        if e["event_type"] == "component.completed"
        and e["payload"].get("component") == "acquire"
    ]
    assert len(completed) == 1
    assert completed[0]["acquired"] == 24
    assert set(completed[0]["by_backend"]) == {"openalex", "overton"}
    assert completed[0]["coverage_record_id"]


def test_harness_acquire_completes_on_backend_error(conn: Connection) -> None:
    """Backend failure is component-visible, not component-fatal."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    config = compile(Plan(component="acquire", evidence_scope_id=scope_id))
    run_harness(
        conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider(),
        search_backends=[FakeBackend(exc=RuntimeError("down")), OvertonFixtureBackend()],
    )
    log = events.read(conn, pid)
    types = [e["event_type"] for e in log]
    assert "component.completed" in types
    assert "component.failed" not in types
    assert "run.completed" in types


# --- Downstream flow: acquire -> screen -> classify -> appraise ---


def test_full_chain_over_both_fixture_corpora(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquired = acquire(conn, pid, rid, scope_id)
    assert acquired["acquired"] == 24

    screened = screen_sources(
        conn, project_id=pid, run_id=rid,
        context=ScreenContext(scope_id=scope_id, intent="Test intent", context={}),
    )
    assert screened["screened"] == 24
    assert screened["failed"] == 0
    assert screened["title_only"] > 0  # abstract-less records fail open, not fail
    assert screened["title_abstract"] > 0
    assert screened["title_only"] + screened["title_abstract"] == 24

    # abstract-less -> title_only at confidence 0.7 (fail-open path)
    from policy_atlas.core.schema import source_screening_result as ssr
    title_only_rows = conn.execute(
        select(ssr.c.screen_decision_confidence)
        .where(ssr.c.project_id == pid)
        .where(ssr.c.screen_basis == "title_only")
    ).fetchall()
    assert title_only_rows
    # approx: the persisted value is a 3-rep consensus mean (task 014), so
    # 0.7 arrives with float-mean noise.
    assert all(row[0] == pytest.approx(0.7) for row in title_only_rows)

    classified = classify_sources(
        conn, project_id=pid, run_id=rid,
        context=ClassifyContext(scope_id=scope_id, intent="Test intent", context={}),
    )
    # no sentinels in real metadata: everything lands Unknown
    assert classified["by_type"] == {
        "Unknown / Insufficient information": classified["classified"]
    }

    appraised = appraise_sources(
        conn, project_id=pid, run_id=rid,
        context=AppraiseContext(scope_id=scope_id, intent="Test intent", context={}),
    )
    assert appraised["appraised"] == 0
    assert appraised["skipped_unknown"] == classified["classified"]


# --- Cleanup helper ---


def test_delete_project_data_removes_acquired_rows(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    acquire(conn, pid, rid, scope_id)

    delete_project_data(conn, pid)

    for table in (project_source_snapshot, search_coverage_record):
        n = conn.execute(
            select(sa.func.count()).select_from(table)
            .where(table.c.project_id == pid)
        ).scalar_one()
        assert n == 0
    n_projects = conn.execute(
        select(sa.func.count()).select_from(project).where(project.c.project_id == pid)
    ).scalar_one()
    assert n_projects == 0


# --- Committed fixtures: leak guard + provenance + quirk coverage ---

FIXTURE_FILES = ("openalex_works.json", "overton_documents.json")


def load_fixture_file(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "provider_records" / name).read_text()
    )
    return data


@pytest.mark.parametrize("name", FIXTURE_FILES)
def test_fixture_leak_guard(name: str) -> None:
    """Deterministic leak guard: fake-DOI prefix + example.org URLs only."""
    text = json.dumps(load_fixture_file(name)["records"])
    for url in re.findall(r"https?://[^\s\"\\]+", text):
        assert url.startswith(("https://example.org/", "https://doi.org/10.99999/")), url
    for doi in re.findall(r"\b10\.\d[\d.]*/[^\s\"\\]+", text):
        assert doi.startswith("10.99999/"), doi
    # grant/award IDs are unique indexed identifiers — must be hashed, never raw
    for record in load_fixture_file(name)["records"]:
        for award in record.get("awards") or []:
            for key in ("funder_award_id", "award_id"):
                if award.get(key):
                    assert re.fullmatch(r"[0-9a-f]{8}", award[key]), award[key]


@pytest.mark.parametrize("name", FIXTURE_FILES)
def test_fixture_meta_block(name: str) -> None:
    meta = load_fixture_file(name)["_meta"]
    assert meta["backend"] in ("openalex", "overton")
    assert meta["recorder_query"]
    assert meta["recorded_at"]
    assert meta["record_count"] == len(load_fixture_file(name)["records"])
    assert meta["sanitizer_version"]
    assert meta["quirk_coverage"]


def test_openalex_fixture_quirk_coverage() -> None:
    records = load_fixture_file("openalex_works.json")["records"]
    assert any(r.get("abstract_inverted_index") is None for r in records)
    assert any(r.get("publication_year") is None for r in records)
    assert any(r.get("type") not in (None, "article") for r in records)
    assert any(r.get("language") not in (None, "en") for r in records)
    assert any(
        any(len(p) > 1 for p in (r.get("abstract_inverted_index") or {}).values())
        for r in records
    )


def test_overton_fixture_quirk_coverage() -> None:
    records = load_fixture_file("overton_documents.json")["records"]

    def koi_doi(r: dict[str, Any]) -> bool:
        koi = r.get("keyed_other_identifiers")
        return isinstance(koi, dict) and bool(koi.get("doi"))

    assert any(not koi_doi(r) for r in records)  # the common no-DOI case
    assert any(koi_doi(r) for r in records)
    assert any(
        r.get("snippet") == "" and r.get("llm_document_description") for r in records
    )
    assert any(
        not r.get("snippet") and not r.get("llm_document_description") for r in records
    )
    assert any(isinstance(r.get("authors"), str) and r["authors"] for r in records)
    assert any(isinstance(r.get("authors"), list) and r["authors"] for r in records)
    assert any(isinstance(r.get("topics"), str) and r["topics"] for r in records)
    assert any(isinstance(r.get("topics"), list) and r["topics"] for r in records)
    assert any((r.get("source") or {}).get("type") == "government" for r in records)
    assert any((r.get("source") or {}).get("type") == "igo" for r in records)
    assert any(r.get("translated_title") for r in records)
    assert any((r.get("grouped_pdf_ids_in_result_count") or 0) > 1 for r in records)


# --- Zero-egress guard ---


def test_acquire_module_has_no_http_client() -> None:
    """No package module but the live transports carries HTTP client usage.

    Task 015 extension (contract decision 1): ``search_live.py`` is a
    sanctioned HTTP home; task 016 extension (contract decision 1, the same
    pattern): ``fetch_live.py`` is the other. Task 025 extension (auth
    strand): ``api/auth.py`` fetches the OIDC issuer's JWKS (RS256
    verification is the contract-approved auth boundary) and ``api/app.py``
    owns the process-singleton HTTP client in the lifespan — both are
    auth-plane egress to the identity provider, never search/model egress.
    Every other module stays HTTP-import-free (``urllib.parse`` is pure URL
    parsing, not a client, and stays allowed), ``acquire.py`` must never
    import its live module, and ``ingest_full_text.py`` must never import
    ``fetch_live`` — fixture defaults stay zero-egress by construction.
    """
    src_dir = Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
    forbidden = re.compile(
        r"^\s*(import|from)\s+(urllib(?!\.parse\b)|requests|httpx|aiohttp|http\.client|socket)\b",
        re.MULTILINE,
    )
    api_http_homes = (src_dir / "api" / "auth.py", src_dir / "api" / "app.py")
    for module in src_dir.rglob("*.py"):
        if module.name in ("search_live.py", "fetch_live.py") or module in api_http_homes:
            continue
        assert not forbidden.search(module.read_text()), f"HTTP client import in {module}"

    live_import = re.compile(
        r"^\s*(import|from)\s+policy_atlas\.evidence_base\.sourcing\.search_live\b|"
        r"^\s*from\s+policy_atlas\.evidence_base\.sourcing\s+import\s+.*\bsearch_live\b",
        re.MULTILINE,
    )
    acquire_text = (src_dir / "evidence_base" / "sourcing" / "acquire.py").read_text()
    assert not live_import.search(acquire_text), "acquire.py imports the live module"

    fetch_live_import = re.compile(
        r"^\s*(import|from)\s+policy_atlas\.evidence_base\.sourcing\.fetch_live\b|"
        r"^\s*from\s+policy_atlas\.evidence_base\.sourcing\s+import\s+.*\bfetch_live\b",
        re.MULTILINE,
    )
    ingest_text = (src_dir / "evidence_base" / "sourcing" / "ingest_full_text.py").read_text()
    assert not fetch_live_import.search(ingest_text), (
        "ingest_full_text.py imports the live fetch module"
    )


def test_recorder_scripts_not_imported_by_package() -> None:
    src_dir = Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
    for module in src_dir.rglob("*.py"):
        text = module.read_text()
        assert "record_openalex_fixtures" not in text
        assert "record_overton_fixtures" not in text
        assert "import scripts" not in text and "from scripts" not in text


# --- Review-stack fixes (task 009 step 7): provider tag bounds ---


def test_provider_tag_bounds() -> None:
    from policy_atlas.evidence_base.sourcing.acquire import TAG_MAX_LENGTH, _normalize_tag

    assert _normalize_tag("  Fine   Tag ") == "Fine Tag"
    assert _normalize_tag("x" * (TAG_MAX_LENGTH + 1)) is None
    assert _normalize_tag("bad\x1b[31mtag") is None
    assert _normalize_tag(42) is None
