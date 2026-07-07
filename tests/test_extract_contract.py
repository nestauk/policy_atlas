"""Contract-bulk test suite for the extract component (task 011, Task 7).

Transcribes the remaining named-test list from
``docs/tasks/011-extract/contract.md``'s "Verification evidence expected"
section, at DB/component level. Core smoke paths (fresh extraction, memo
reuse, abstract basis, window-failure, no_findings memo, empty selection,
missing row, uploaded-envelope chunks) live in ``test_extract.py``; unit-level
verifier/rules/dedup coverage lives in ``test_quote_verify.py``. This file
covers everything else: schema constraint rejections, memo edge semantics,
coverage invariants, quote verification, field rules, claim-keyed dedup,
doc-status rules, windowing, basis rules, the schema/prompt line, edge
scopes, determinism, delete-order integrity and the summary payload shape.
All rows ride the ``conn`` fixture's per-test rollback.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy import func, literal_column, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas import extract
from policy_atlas.extract import ExtractContext, extract_scope, extraction_fingerprint
from policy_atlas.extract_prompt import EXTRACT_SYSTEM_PROMPT
from policy_atlas.extraction_backend import StubExtractionBackend
from policy_atlas.schema import (
    chunk,
    extraction_result,
    intervention_outcome_finding,
    project_source_snapshot,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
)

from .helpers import (
    EVIDENCE_TYPE,
    delete_project_data,
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_source,
)
from .test_extract import (
    _record,
    _run,
    _seed_abstract_doc,
    _seed_full_text_doc,
    _seed_selection,
    _stat,
)

# --- Local seeding / value helpers (extend test_extract.py's) ---------------


def _extraction_record_values(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    pss_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    **over: Any,
) -> dict[str, Any]:
    """A minimal valid ``source_extraction_record`` row, overridable per test."""
    values: dict[str, Any] = {
        "extraction_record_id": uuid.uuid4(),
        "project_id": project_id,
        "source_snapshot_id": snapshot_id,
        "project_source_snapshot_id": pss_id,
        "extraction_fingerprint": "fp-schema-test",
        "status": "extracted",
        "basis": "full_text",
        "error": None,
        "finding_count": 0,
        "run_id": run_id,
        "created_at": now(),
    }
    values.update(over)
    return values


def _insert_extraction_record(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    pss_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    **over: Any,
) -> uuid.UUID:
    values = _extraction_record_values(project_id, run_id, pss_id, snapshot_id, **over)
    conn.execute(source_extraction_record.insert().values(**values))
    return cast("uuid.UUID", values["extraction_record_id"])


def _finding_values(
    project_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **over: Any,
) -> dict[str, Any]:
    """A minimal valid ``intervention_outcome_finding`` row, overridable per test."""
    values: dict[str, Any] = {
        "finding_id": uuid.uuid4(),
        "project_id": project_id,
        "extraction_record_id": extraction_record_id,
        "intervention": "Coaching",
        "outcome": "Test scores",
        "population": None,
        "comparator": None,
        "effect_direction": "positive",
        "estimate_level": "study",
        "study_design": None,
        "stratum_qualifiers": [],
        "statistics": _stat(),
        "causality_by_design": None,
        "is_primary": None,
        "is_prevalence_only": None,
        "field_coverage": {},
        "grounding": [],
        "created_at": now(),
    }
    values.update(over)
    return values


def _seed_multi_chunk_doc(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    title: str,
    contents: list[str],
    stub_iof: list[dict[str, Any]],
    chunk_ids: list[uuid.UUID] | None = None,
    evidence_type: str | None = EVIDENCE_TYPE,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Seed a full-text doc with N ordered chunks on one full-text snapshot.

    Pass ``chunk_ids`` (pre-generated) when a ``stub_iof`` anchor must name one —
    generate them first, then reference ``str(chunk_ids[i])`` as the anchor's
    segment_id. Returns ``(pss_id, chunk_ids)`` in sequence order.
    """
    envelope_snap = uuid.uuid4()
    ft_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    chunk_ids = chunk_ids or [uuid.uuid4() for _ in contents]
    meta: dict[str, Any] = {
        "title": title,
        "abstract": f"Abstract for {title}.",
        "_stub_iof": stub_iof,
    }
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=envelope_snap, content_hash=str(uuid.uuid4()),
        text_basis="full_text", source_locator="test.pdf", metadata=meta, created_at=now(),
    ))
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=ft_snap, content_hash=str(uuid.uuid4()),
        text_basis="full_text", source_locator="test.pdf#full", metadata={}, created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id, project_id=project_id,
        source_snapshot_id=envelope_snap, origin="uploaded", run_id=None, ingested_at=now(),
        full_text_snapshot_id=ft_snap, full_text_status="ingested",
    ))
    for sequence, (chunk_id, content) in enumerate(zip(chunk_ids, contents, strict=True)):
        conn.execute(chunk.insert().values(
            chunk_id=chunk_id, source_snapshot_id=ft_snap, sequence=sequence, content=content,
            content_hash=str(uuid.uuid4()), locator={}, segmentation_policy="manual_v1",
            created_at=now(),
        ))
    if evidence_type is not None:
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(), evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id, project_id=project_id,
            classified_by_run_id=run_id, primary_evidence_type=evidence_type, classified_at=now(),
        ))
    return pss_id, chunk_ids


def _seed_determinism_fixture(
    conn: Connection, project_id: uuid.UUID, run_id: uuid.UUID, scope_id: uuid.UUID
) -> None:
    """Seed an identical 3-doc fixture: one extracted, one abstract, one no_findings."""
    cid = uuid.uuid4()
    pss1, _ = _seed_full_text_doc(
        conn, project_id, run_id, scope_id, title="Det doc one",
        chunk_content="Peer mentoring increased retention among students.",
        chunk_id=cid,
        stub_iof=[_record(
            intervention="peer mentoring", outcome="retention",
            quote="Peer mentoring increased retention", segment_id=str(cid),
        )],
    )
    pss2 = _seed_abstract_doc(
        conn, project_id, title="Det doc two",
        abstract="Community outreach improved vaccination uptake.",
        stub_iof=[_record(
            intervention="community outreach", outcome="vaccination uptake",
            quote="Community outreach improved vaccination uptake", segment_id="abstract",
        )],
    )
    pss3, _ = _seed_full_text_doc(
        conn, project_id, run_id, scope_id, title="Det doc three",
        chunk_content="This document reports no intervention outcome findings.",
    )
    _seed_selection(conn, project_id, run_id, scope_id, [
        {"pss_id": str(pss1), "text_basis": "full_text"},
        {"pss_id": str(pss2), "text_basis": "abstract_only"},
        {"pss_id": str(pss3), "text_basis": "full_text"},
    ])


# --- 1. Schema / constraint rejections ---------------------------------------


def test_ser_status_check_rejected(conn: Connection) -> None:
    """``status`` outside the closed vocabulary is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    with pytest.raises(IntegrityError, match="ck_ser_status"), conn.begin_nested():
        conn.execute(source_extraction_record.insert().values(
            **_extraction_record_values(project_id, run_id, pss_id, snap_id, status="bogus")
        ))


def test_ser_basis_check_rejected(conn: Connection) -> None:
    """``basis`` outside the closed vocabulary is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    with pytest.raises(IntegrityError, match="ck_ser_basis"), conn.begin_nested():
        conn.execute(source_extraction_record.insert().values(
            **_extraction_record_values(project_id, run_id, pss_id, snap_id, basis="bogus")
        ))


def test_ser_error_presence_failed_without_error_rejected(conn: Connection) -> None:
    """``status='extraction_failed'`` with ``error IS NULL`` is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    with pytest.raises(IntegrityError, match="ck_ser_error_presence"), conn.begin_nested():
        conn.execute(source_extraction_record.insert().values(**_extraction_record_values(
            project_id, run_id, pss_id, snap_id, status="extraction_failed", error=None
        )))


def test_ser_error_presence_extracted_with_error_rejected(conn: Connection) -> None:
    """``status='extracted'`` with a non-null ``error`` is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    with pytest.raises(IntegrityError, match="ck_ser_error_presence"), conn.begin_nested():
        conn.execute(source_extraction_record.insert().values(**_extraction_record_values(
            project_id, run_id, pss_id, snap_id, status="extracted", error="should not be here"
        )))


def test_iof_effect_direction_check_rejected(conn: Connection) -> None:
    """``effect_direction`` outside the closed vocabulary is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    record_id = _insert_extraction_record(conn, project_id, run_id, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="ck_iof_direction"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(project_id, record_id, effect_direction="bogus")
        ))


def test_iof_estimate_level_check_rejected(conn: Connection) -> None:
    """``estimate_level`` outside the closed vocabulary (when non-null) is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    record_id = _insert_extraction_record(conn, project_id, run_id, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="ck_iof_estimate_level"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(project_id, record_id, estimate_level="bogus")
        ))


def test_iof_causality_check_rejected(conn: Connection) -> None:
    """``causality_by_design`` outside the closed vocabulary (when non-null) is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    record_id = _insert_extraction_record(conn, project_id, run_id, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="ck_iof_causality"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(project_id, record_id, causality_by_design="bogus")
        ))


def test_iof_stratum_qualifiers_non_array_rejected(conn: Connection) -> None:
    """A non-array ``stratum_qualifiers`` JSONB value is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    record_id = _insert_extraction_record(conn, project_id, run_id, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="ck_iof_strata_array"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(
                project_id, record_id, stratum_qualifiers={"type": "timepoint", "value": "x"}
            )
        ))


def test_iof_grounding_non_array_rejected(conn: Connection) -> None:
    """A non-array ``grounding`` JSONB value is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    record_id = _insert_extraction_record(conn, project_id, run_id, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="ck_iof_grounding_array"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(project_id, record_id, grounding={"quote": "x"})
        ))


def test_ser_memo_partial_unique_success_states_only(conn: Connection) -> None:
    """The memo key blocks a second success row but never a failed attempt."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)
    fp = "fp-memo-partial-unique"
    _insert_extraction_record(
        conn, project_id, run_id, pss_id, snap_id, status="extracted", extraction_fingerprint=fp
    )
    with pytest.raises(IntegrityError, match="uq_ser_memo"), conn.begin_nested():
        conn.execute(source_extraction_record.insert().values(**_extraction_record_values(
            project_id, run_id, pss_id, snap_id, status="extracted", extraction_fingerprint=fp
        )))
    # Failures insert freely alongside a success row, and alongside each other.
    _insert_extraction_record(
        conn, project_id, run_id, pss_id, snap_id,
        status="extraction_failed", error="boom-1", extraction_fingerprint=fp,
    )
    _insert_extraction_record(
        conn, project_id, run_id, pss_id, snap_id,
        status="extraction_failed", error="boom-2", extraction_fingerprint=fp,
    )
    count = conn.execute(
        select(func.count()).select_from(source_extraction_record)
        .where(source_extraction_record.c.project_id == project_id)
    ).scalar_one()
    assert count == 3


def test_iof_cross_project_composite_fk_rejected(conn: Connection) -> None:
    """A finding naming an extraction record from ANOTHER project is rejected."""
    project_a, run_a = seed_project_and_run(conn)
    project_b, _run_b = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_a)
    record_id = _insert_extraction_record(conn, project_a, run_a, pss_id, snap_id)
    with pytest.raises(IntegrityError, match="fk_iof_record_project"), conn.begin_nested():
        conn.execute(intervention_outcome_finding.insert().values(
            **_finding_values(project_b, record_id)
        ))


def test_extraction_result_unique_scope_run_rejected(conn: Connection) -> None:
    """A second ``extraction_result`` row for the same (scope, run) is rejected."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    conn.execute(extraction_result.insert().values(
        extraction_result_id=uuid.uuid4(), project_id=project_id, evidence_scope_id=scope_id,
        run_id=run_id, selection_run_id=uuid.uuid4(), extraction_provenance={},
        docs=[], counts={}, flags=[], created_at=now(),
    ))
    with pytest.raises(IntegrityError, match="uq_exr_scope_run"), conn.begin_nested():
        conn.execute(extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(), project_id=project_id, evidence_scope_id=scope_id,
            run_id=run_id, selection_run_id=uuid.uuid4(), extraction_provenance={},
            docs=[], counts={}, flags=[], created_at=now(),
        ))


# --- 2. Memo semantics beyond the smoke tests --------------------------------


def test_fingerprint_stub_vs_live_distinct_and_hex(conn: Connection) -> None:
    """Stub and live fingerprints differ and are both full 64-char sha256 hex."""
    stub_fp, _ = extraction_fingerprint("stub")
    live_fp, _ = extraction_fingerprint("live")
    assert stub_fp != live_fp
    for fp in (stub_fp, live_fp):
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


def test_failed_extraction_never_blocks_or_satisfies_memo(conn: Connection) -> None:
    """A failed record never blocks or satisfies the memo — retry in a new run extracts fresh."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = "Some content mentioning coaching improved graduation outcomes."
    cid = uuid.uuid4()
    pss_id, chunk_id = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Flaky doc", chunk_content=content,
        chunk_id=cid, stub_failed=True,
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    first, _ = _run(conn, project_id, scope_id, sel_run)
    assert first["docs"][0]["status"] == "extraction_failed"

    # Drop the failure sentinel, add a findings sentinel, on the envelope's metadata.
    envelope_snap_id = conn.execute(
        select(project_source_snapshot.c.source_snapshot_id)
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
    ).scalar_one()
    new_meta: dict[str, Any] = {
        "title": "Flaky doc",
        "abstract": "Abstract for Flaky doc.",
        "_stub_iof": [_record(
            intervention="coaching", outcome="graduation outcomes",
            quote="coaching improved graduation outcomes", segment_id=str(chunk_id),
        )],
    }
    conn.execute(
        update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == envelope_snap_id)
        .values(metadata=new_meta)
    )

    second, _ = _run(conn, project_id, scope_id, sel_run)
    assert second["docs"][0]["reused"] is False
    assert second["docs"][0]["status"] == "extracted"

    count = conn.execute(
        select(func.count()).select_from(source_extraction_record)
        .where(source_extraction_record.c.project_id == project_id)
    ).scalar_one()
    assert count == 2


# --- 3. Coverage invariants at the payload boundary --------------------------


def test_coverage_invariants_at_payload_boundary(conn: Connection) -> None:
    """A 3-doc run (extracted + no_findings + failed) covers exactly the selected set."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    extracted_cid = uuid.uuid4()
    extracted_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc A",
        chunk_content="Coaching increased grades in the study.", chunk_id=extracted_cid,
        stub_iof=[_record(
            intervention="coaching", outcome="grades",
            quote="Coaching increased grades", segment_id=str(extracted_cid),
        )],
    )
    no_findings_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc B",
        chunk_content="This document reports nothing shaped like a finding.",
    )
    failed_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc C",
        chunk_content="Some content.", stub_failed=True,
    )
    selected_ids = {str(extracted_pss), str(no_findings_pss), str(failed_pss)}
    _seed_selection(conn, project_id, sel_run, scope_id, [
        {"pss_id": str(extracted_pss), "text_basis": "full_text"},
        {"pss_id": str(no_findings_pss), "text_basis": "full_text"},
        {"pss_id": str(failed_pss), "text_basis": "full_text"},
    ])

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert {d["pss_id"] for d in summary["docs"]} == selected_ids
    counts = summary["counts"]
    assert counts["selected"] == 3
    assert counts["extracted"] + counts["no_findings"] + counts["failed"] == counts["selected"]
    assert counts["fresh"] + counts["reused"] == counts["selected"]

    record_ids = [
        row.extraction_record_id
        for row in conn.execute(
            select(intervention_outcome_finding.c.extraction_record_id)
            .where(intervention_outcome_finding.c.project_id == project_id)
        ).fetchall()
    ]
    assert record_ids  # the extracted doc wrote at least one finding
    owning_pss = conn.execute(
        select(source_extraction_record.c.project_source_snapshot_id)
        .where(source_extraction_record.c.extraction_record_id.in_(record_ids))
    ).fetchall()
    for row in owning_pss:
        assert str(row.project_source_snapshot_id) in selected_ids


# --- 4. Quote verification through the component -----------------------------


def test_fabricated_quote_kept_and_flagged(conn: Connection) -> None:
    """A fabricated quote is flagged quote_unverified, kept, never dropped."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Fab doc",
        chunk_content="Tutoring improved reading scores among pupils.", chunk_id=cid,
        stub_iof=[_record(
            intervention="tutoring", outcome="reading scores",
            quote="This quote does not appear anywhere in the document.",
            segment_id=str(cid),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["counts"]["extracted"] == 1
    assert summary["findings"]["quote_unverified"] == 1
    grounding = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    anchor = grounding[0]
    assert anchor["quote_verified"] is False
    assert anchor["match_status"] == "failed"
    assert anchor["spans"] == []


def test_boundary_spanning_quote_verifies_across_chunks(conn: Connection) -> None:
    """A quote spanning two chunks verifies against the concatenated basis, >=2 spans."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    chunk1 = "Structured coaching increased"
    chunk2 = "graduation rates significantly across the pilot sites."
    quote = "Structured coaching increased graduation rates significantly"
    seeded_chunk_ids = [uuid.uuid4(), uuid.uuid4()]
    pss_id, chunk_ids = _seed_multi_chunk_doc(
        conn, project_id, sel_run, scope_id, title="Two-chunk doc", contents=[chunk1, chunk2],
        chunk_ids=seeded_chunk_ids,
        stub_iof=[_record(
            intervention="structured coaching", outcome="graduation rates",
            quote=quote, segment_id=str(seeded_chunk_ids[0]),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["counts"]["extracted"] == 1
    grounding = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    anchor = grounding[0]
    assert anchor["quote_verified"] is True
    assert len(anchor["spans"]) >= 2
    span_chunk_ids = {span["chunk_id"] for span in anchor["spans"]}
    assert span_chunk_ids == {str(cid) for cid in chunk_ids}


def test_verified_anchor_match_location_fidelity(conn: Connection) -> None:
    """A verified anchor carries non-empty int spans (start < end) and a graded status."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Loc doc",
        chunk_content="Mentoring boosted attendance across the cohort.", chunk_id=cid,
        stub_iof=[_record(
            intervention="mentoring", outcome="attendance",
            quote="Mentoring boosted attendance", segment_id=str(cid),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    assert summary["counts"]["extracted"] == 1

    grounding = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    anchor = grounding[0]
    assert anchor["match_status"] in {"exact", "normalised"}
    assert anchor["spans"]
    for span in anchor["spans"]:
        assert isinstance(span["start"], int)
        assert isinstance(span["end"], int)
        assert span["start"] < span["end"]


# --- 5. Field rules through the component ------------------------------------


def test_field_rules_out_of_bounds_marks_unclear(conn: Connection) -> None:
    """Out-of-bounds p_value / inverted CI flag unclear, void the field, keep the finding."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Bounds doc",
        chunk_content="The trial reported an effect on test scores.", chunk_id=cid,
        stub_iof=[_record(
            intervention="tutoring", outcome="test scores",
            quote="reported an effect on test scores", segment_id=str(cid),
            statistics=_stat(p_value=1.5, ci_lower=2.0, ci_upper=1.0),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    assert summary["counts"]["extracted"] == 1

    row = conn.execute(
        select(
            intervention_outcome_finding.c.field_coverage,
            intervention_outcome_finding.c.statistics,
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).one()
    assert row.field_coverage["p_value"] == "unclear"
    assert row.field_coverage["ci_lower"] == "unclear"
    assert row.field_coverage["ci_upper"] == "unclear"
    assert row.statistics["p_value"] is None
    assert row.statistics["ci_lower"] is None
    assert row.statistics["ci_upper"] is None


def test_null_like_string_coerced_to_null_and_marked(conn: Connection) -> None:
    """A null-like statistics string ('null') coerces to real null + not_extracted."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Null-like doc",
        chunk_content="The report described the sample without a stated N.", chunk_id=cid,
        stub_iof=[_record(
            intervention="tutoring", outcome="sample",
            quote="described the sample without a stated N", segment_id=str(cid),
            statistics=_stat(n="null"),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    assert summary["counts"]["extracted"] == 1

    row = conn.execute(
        select(
            intervention_outcome_finding.c.field_coverage,
            intervention_outcome_finding.c.statistics,
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).one()
    assert row.field_coverage["n"] == "not_extracted"
    assert row.statistics["n"] is None


def test_estimate_level_not_applicable_markers(conn: Connection) -> None:
    """estimate_level coherence marks the wrong-shape stats not_applicable / not_extracted."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    content = (
        "Programme A improved literacy. Programme B changed numeracy. "
        "Meta-analysis pooled programme C data on wellbeing."
    )
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Estimate doc",
        chunk_content=content, chunk_id=cid,
        stub_iof=[
            _record(
                intervention="Programme A", outcome="literacy",
                quote="Programme A improved literacy", segment_id=str(cid),
                estimate_level="study",
            ),
            _record(
                intervention="Programme B", outcome="numeracy",
                quote="Programme B changed numeracy", segment_id=str(cid),
                estimate_level="claim",
            ),
            _record(
                intervention="Programme C", outcome="wellbeing",
                quote="Meta-analysis pooled programme C data on wellbeing", segment_id=str(cid),
                estimate_level="pooled",
            ),
        ],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    assert summary["counts"]["extracted"] == 1

    rows = conn.execute(
        select(
            intervention_outcome_finding.c.intervention,
            intervention_outcome_finding.c.field_coverage,
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).fetchall()
    coverage_by_intervention = {r.intervention: r.field_coverage for r in rows}

    study_cov = coverage_by_intervention["Programme A"]
    assert study_cov["k"] == "not_applicable"
    assert study_cov["i_squared"] == "not_applicable"
    assert study_cov["tau2"] == "not_applicable"

    claim_cov = coverage_by_intervention["Programme B"]
    for field_name in (
        "effect_size", "ci_lower", "ci_upper", "standard_error",
        "p_value", "n", "k", "i_squared", "tau2",
    ):
        assert claim_cov[field_name] == "not_applicable"

    pooled_cov = coverage_by_intervention["Programme C"]
    assert pooled_cov["k"] == "not_extracted"


# --- 6. Claim-keyed dedup through the component ------------------------------


def test_claim_keyed_dedup_merges_anchors(conn: Connection) -> None:
    """Two records with an identical claim but different genuine quotes collapse to one."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    content = (
        "Coaching raised graduation rates. Later the report reaffirmed "
        "coaching raised graduation rates for seniors."
    )
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Dedup doc",
        chunk_content=content, chunk_id=cid,
        stub_iof=[
            _record(
                intervention="coaching", outcome="graduation rates",
                quote="Coaching raised graduation rates", segment_id=str(cid),
            ),
            _record(
                intervention="coaching", outcome="graduation rates",
                quote="coaching raised graduation rates for seniors", segment_id=str(cid),
            ),
        ],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["findings"]["dedup_collapsed"] == 1
    assert summary["counts"]["extracted"] == 1
    rows = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).fetchall()
    assert len(rows) == 1
    assert len(rows[0].grounding) == 2


def test_claim_dedup_distinct_effect_size_stays_separate(conn: Connection) -> None:
    """Two records differing only by effect_size are NOT collapsed."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    content = (
        "Coaching raised graduation rates by 5 points in cohort one. "
        "Coaching raised graduation rates by 9 points in cohort two."
    )
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="No dedup doc",
        chunk_content=content, chunk_id=cid,
        stub_iof=[
            _record(
                intervention="coaching", outcome="graduation rates",
                quote="Coaching raised graduation rates by 5 points in cohort one",
                segment_id=str(cid), statistics=_stat(effect_size=5.0),
            ),
            _record(
                intervention="coaching", outcome="graduation rates",
                quote="Coaching raised graduation rates by 9 points in cohort two",
                segment_id=str(cid), statistics=_stat(effect_size=9.0),
            ),
        ],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["findings"]["dedup_collapsed"] == 0
    assert summary["counts"]["extracted"] == 1
    count = conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    assert count == 2


# --- 7. Doc-status rules ------------------------------------------------------


def test_all_grain_invalid_doc_extraction_failed(conn: Connection) -> None:
    """Every candidate record grain-invalid -> extraction_failed(invalid_records), 0 findings."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Invalid doc",
        chunk_content="Some plain content here.", chunk_id=cid,
        stub_iof=[_record(
            intervention="null", outcome="reading scores",
            quote="Some plain content here", segment_id=str(cid),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = summary["docs"][0]
    assert doc["status"] == "extraction_failed"
    assert doc["error"] == "invalid_records"
    assert summary["findings"]["total"] == 0
    count = conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    assert count == 0


def test_mixed_valid_invalid_records_drops_invalid(conn: Connection) -> None:
    """One valid + one grain-invalid record -> extracted, invalid dropped-and-counted."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    content = "Coaching improved graduation rates in the pilot."
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Mixed doc",
        chunk_content=content, chunk_id=cid,
        stub_iof=[
            _record(
                intervention="coaching", outcome="graduation rates",
                quote="Coaching improved graduation rates", segment_id=str(cid),
            ),
            _record(
                intervention="null", outcome="something",
                quote="graduation rates in the pilot", segment_id=str(cid),
            ),
        ],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = summary["docs"][0]
    assert doc["status"] == "extracted"
    assert doc["finding_count"] == 1
    assert summary["findings"]["invalid_dropped"] == 1


# --- 8. Windowing --------------------------------------------------------------


def test_windowing_multi_window_doc_extracts(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A budget small enough to force multiple windows still extracts; baseline matches."""
    monkeypatch.setattr(extract, "WINDOW_CHAR_BUDGET", 50)
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    contents = [
        "Coaching one improved test scores in trials.",
        "Coaching two improved attendance across schools.",
        "Coaching three improved wellbeing among pupils.",
    ]
    seeded_chunk_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    pss_id, chunk_ids = _seed_multi_chunk_doc(
        conn, project_id, sel_run, scope_id, title="Windowed doc", contents=contents,
        chunk_ids=seeded_chunk_ids,
        stub_iof=[_record(
            intervention="coaching one", outcome="test scores",
            quote="Coaching one improved test scores", segment_id=str(seeded_chunk_ids[0]),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    # Greedy windowing with each chunk <=50 chars but any pair >50: every chunk
    # lands in its own window -> 3 windows, no real 1-segment overlap possible.
    assert summary["provenance"]["call_budget"]["baseline"] == 3
    assert summary["docs"][0]["status"] == "extracted"
    assert summary["findings"]["total"] == 1


def test_oversize_chunk_subsegment_split(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An oversize chunk is char-split into subsegments; the full read still processes."""
    monkeypatch.setattr(extract, "WINDOW_CHAR_BUDGET", 50)
    # The module default overlap (1_000) exceeds this test's 50-char budget, which
    # would starve _split_oversize's advance step; shrink it in lockstep so the
    # split still terminates (only WINDOW_CHAR_BUDGET is asserted on above).
    monkeypatch.setattr(extract, "OVERSIZE_SUBSEGMENT_OVERLAP", 10)
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    content = (
        "Structured tutoring for at-risk pupils raised reading scores across "
        "every participating school in the trial cohort."
    )
    assert len(content) > 100  # oversize relative to the 50-char test budget
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Oversize doc",
        chunk_content=content, chunk_id=cid,
        stub_iof=[_record(
            intervention="structured tutoring", outcome="reading scores",
            quote="Structured tutoring for at-risk pupils",
            segment_id=f"{cid}#p0",
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["docs"][0]["status"] == "extracted"
    grounding = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    anchor = grounding[0]
    assert anchor["chunk_id"] == str(cid)
    assert anchor["quote_verified"] is True


# --- 9. Basis rules beyond smoke ------------------------------------------------


def test_full_text_basis_mismatch_no_snapshot_no_chunks(conn: Connection) -> None:
    """full_text selection with no full-text snapshot and no envelope chunks -> basis_mismatch."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _snap_id, pss_id = seed_source(
        conn, project_id, meta={"title": "No text doc", "abstract": "An abstract."}
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = summary["docs"][0]
    assert doc["status"] == "extraction_failed"
    assert doc["error"] == "basis_mismatch"


def test_abstract_only_missing_abstract_is_empty_basis(conn: Connection) -> None:
    """A title-only abstract_only doc -> extraction_failed(empty_basis), NEVER no_findings."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Title only doc"})
    _seed_selection(
        conn, project_id, sel_run, scope_id,
        [{"pss_id": str(pss_id), "text_basis": "abstract_only"}],
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = summary["docs"][0]
    assert doc["status"] == "extraction_failed"
    assert doc["error"] == "empty_basis"


def test_ingested_full_text_zero_chunks_is_empty_basis(conn: Connection) -> None:
    """An ingested full-text snapshot with zero chunk rows -> extraction_failed(empty_basis)."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    envelope_snap = uuid.uuid4()
    ft_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=envelope_snap, content_hash=str(uuid.uuid4()),
        text_basis="full_text", source_locator="test.pdf",
        metadata={"title": "Empty ft doc", "abstract": "An abstract."}, created_at=now(),
    ))
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=ft_snap, content_hash=str(uuid.uuid4()),
        text_basis="full_text", source_locator="test.pdf#full", metadata={}, created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id, project_id=project_id,
        source_snapshot_id=envelope_snap, origin="uploaded", run_id=None, ingested_at=now(),
        full_text_snapshot_id=ft_snap, full_text_status="ingested",
    ))
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = summary["docs"][0]
    assert doc["status"] == "extraction_failed"
    assert doc["error"] == "empty_basis"


# --- 10. Schema line ------------------------------------------------------------


def test_schema_has_no_enrichment_columns() -> None:
    """No enrichment column (normalised magnitude, causal weight, is-beneficial) in the schema."""
    columns = set(intervention_outcome_finding.c.keys())
    assert not columns & {"normalised_magnitude", "causal_weight", "is_beneficial"}


def test_prompt_carries_negative_rules() -> None:
    """The built prompt states its explicit negative rules verbatim."""
    for phrase in (
        "never emit normalised magnitudes",
        "Nothing this document does not itself report",
        "Never force effect fields",
        "Control or comparison arms are not interventions",
        "exact verbatim text",
    ):
        assert phrase in EXTRACT_SYSTEM_PROMPT


# --- 11. Edge scope: same-run re-execution loud ---------------------------------


def test_same_run_reexecution_raises(conn: Connection) -> None:
    """Calling extract_scope twice with the SAME run_id raises on the second call."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_selection(conn, project_id, sel_run, scope_id, [])
    run_id = seed_run(conn, project_id)
    ctx = ExtractContext(
        scope_id=scope_id, intent="unused", context={}, selection_run_id=sel_run
    )
    extract_scope(
        conn, project_id=project_id, run_id=run_id, context=ctx,
        extraction_backend=StubExtractionBackend(),
    )
    with pytest.raises(IntegrityError, match="uq_exr_scope_run"), conn.begin_nested():
        extract_scope(
            conn, project_id=project_id, run_id=run_id, context=ctx,
            extraction_backend=StubExtractionBackend(),
        )


# --- 12. Determinism -------------------------------------------------------------


def test_determinism_across_identical_projects(conn: Connection) -> None:
    """Two identical fixtures in separate projects produce identical summary columns."""
    project_a, run_a = seed_project_and_run(conn)
    scope_a = seed_scope(conn, project_a)
    _seed_determinism_fixture(conn, project_a, run_a, scope_a)
    summary_a, _ = _run(conn, project_a, scope_a, run_a)

    project_b, run_b = seed_project_and_run(conn)
    scope_b = seed_scope(conn, project_b)
    _seed_determinism_fixture(conn, project_b, run_b, scope_b)
    summary_b, _ = _run(conn, project_b, scope_b, run_b)

    assert summary_a["counts"] == summary_b["counts"]
    assert summary_a["findings"] == summary_b["findings"]
    assert summary_a["basis"] == summary_b["basis"]
    assert summary_a["flags"] == summary_b["flags"]
    assert summary_a["field_coverage"] == summary_b["field_coverage"]
    assert summary_a["provenance"] == summary_b["provenance"]

    def _doc_sequence(summary: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in doc.items() if k not in {"pss_id", "extraction_record_id"}}
            for doc in summary["docs"]
        ]

    assert _doc_sequence(summary_a) == _doc_sequence(summary_b)


def test_parallel_vs_serial_same_write_order(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serial (MAX_CONCURRENT_EXTRACT=1) and default-parallel runs write the same finding order."""
    project_default, run_default = seed_project_and_run(conn)
    scope_default = seed_scope(conn, project_default)
    _seed_determinism_fixture(conn, project_default, run_default, scope_default)
    summary_default, _ = _run(conn, project_default, scope_default, run_default)

    monkeypatch.setattr(extract, "MAX_CONCURRENT_EXTRACT", 1)
    project_serial, run_serial = seed_project_and_run(conn)
    scope_serial = seed_scope(conn, project_serial)
    _seed_determinism_fixture(conn, project_serial, run_serial, scope_serial)
    summary_serial, _ = _run(conn, project_serial, scope_serial, run_serial)

    assert summary_default["counts"] == summary_serial["counts"]

    def _ordered_pairs(project_id: uuid.UUID) -> list[tuple[str, str]]:
        # Rows are inserted sequentially within one transaction with no
        # concurrent writers, so physical (ctid) order reflects insertion
        # order — the property under test (writes happen in selected-set
        # order in the parent, regardless of fan-out completion order).
        rows = conn.execute(
            select(
                intervention_outcome_finding.c.intervention,
                intervention_outcome_finding.c.outcome,
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
            .order_by(literal_column("ctid"))
        ).fetchall()
        return [(r.intervention, r.outcome) for r in rows]

    expected = [("peer mentoring", "retention"), ("community outreach", "vaccination uptake")]
    assert _ordered_pairs(project_default) == expected
    assert _ordered_pairs(project_serial) == expected


# --- 13. Delete-order integrity ---------------------------------------------------


def test_delete_project_data_removes_task011_rows(conn: Connection) -> None:
    """delete_project_data removes all three task-011 tables' rows without an IntegrityError."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Delete doc",
        chunk_content="Coaching raised scores in the pilot.", chunk_id=cid,
        stub_iof=[_record(
            intervention="coaching", outcome="scores",
            quote="Coaching raised scores", segment_id=str(cid),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )
    _run(conn, project_id, scope_id, sel_run)

    delete_project_data(conn, project_id)

    for table in (intervention_outcome_finding, source_extraction_record, extraction_result):
        count = conn.execute(
            select(func.count()).select_from(table).where(table.c.project_id == project_id)
        ).scalar_one()
        assert count == 0


# --- 14. Summary payload shape -----------------------------------------------------


def test_summary_payload_shape(conn: Connection) -> None:
    """The summary, its per-doc entries and its provenance carry exactly the contracted keys."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Shape doc",
        chunk_content="Coaching improved grades broadly.", chunk_id=cid,
        stub_iof=[_record(
            intervention="coaching", outcome="grades",
            quote="Coaching improved grades", segment_id=str(cid),
        )],
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert set(summary.keys()) == {
        "docs", "counts", "findings", "basis", "field_coverage",
        "selection_run_id", "flags", "provenance",
    }
    for doc in summary["docs"]:
        assert set(doc.keys()) == {
            "pss_id", "status", "basis", "finding_count", "reused", "error",
            "extraction_record_id",
        }
    assert set(summary["provenance"].keys()) == {
        "profile", "schema", "prompt", "model", "mode", "field_rules", "verifier",
        "window", "max_output_tokens", "retry_cap", "fingerprint", "pass_count",
        "call_budget", "retry_count",
    }
