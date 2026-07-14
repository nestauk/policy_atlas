"""Smoke tests for the extract component (task 011, Task 5).

Core paths only — fresh full-text extraction, memo reuse, abstract basis,
window-failure, no_findings + its memo, empty selection, and the missing-row
structural failure. The full contract suite lands in a later task; these keep to
the trunk so they don't duplicate it. All rows ride the ``conn`` fixture's
per-test rollback.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas import extract_prompt
from policy_atlas.extract import (
    ExtractContext,
    ExtractError,
    _judge_payload_entry,
    extract_scope,
    extraction_fingerprint,
    icf_extraction_fingerprint,
)
from policy_atlas.extraction_backend import StubExtractionBackend
from policy_atlas.extraction_records import (
    SCHEMA_VERSION as IOF_SCHEMA_VERSION,
)
from policy_atlas.extraction_records import (
    IOFAnchor,
    IOFRecord,
    IOFStatistics,
    IOFStratum,
)
from policy_atlas.finding_vetter import FINDING_VETTER_PROMPT_VERSION
from policy_atlas.icf_finding_vetter import (
    ICFFindingVetterResponse,
    ICFFlagClass,
    ICFVetterVerdictWire,
)
from policy_atlas.implementation_context_prompt import ICF_PROMPT_VERSION
from policy_atlas.implementation_context_records import SCHEMA_VERSION as ICF_SCHEMA_VERSION
from policy_atlas.schema import (
    chunk,
    extraction_result,
    implementation_context_finding,
    intervention_outcome_finding,
    project_source_snapshot,
    selection_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
)
from policy_atlas.synthesis_tools import make_findings_reader
from policy_atlas.usage import UsageResult

from .helpers import (
    EVIDENCE_TYPE,
    ICF_PROFILE_ID,
    IOF_PROFILE_ID,
    make_icf_wire_record,
    now,
    profile_counts,
    profile_doc,
    profile_docs,
    profile_findings,
    profile_vetted_out,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_source,
)

# --- Local seeding helpers (reused/extended by the later contract suite) ---


def _stat(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "effect_size": None,
        "effect_size_type": None,
        "ci_lower": None,
        "ci_upper": None,
        "standard_error": None,
        "p_value": None,
        "n": None,
        "k": None,
        "i_squared": None,
        "tau2": None,
    }
    base.update(over)
    return base


def _record(
    *,
    intervention: str,
    outcome: str,
    quote: str,
    segment_id: str | None,
    effect_direction: str = "increase",
    statistics: dict[str, Any] | None = None,
    **over: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "intervention": intervention,
        "outcome": outcome,
        "population": None,
        "setting": None,
        "comparator": None,
        "effect_direction": effect_direction,
        "estimate_level": "study",
        "study_design": None,
        "study_geography": None,
        "stratum_qualifiers": [],
        "statistics": statistics or _stat(),
        "causality_by_design": None,
        "effect_basis": None,
        "is_primary": None,
        "is_prevalence_only": None,
        "anchors": [{"segment_id": segment_id, "quote": quote}],
    }
    record.update(over)
    return record


def _icf_record(
    *,
    claim: str,
    intervention: str,
    quote: str,
    segment_id: str | None,
    context_type: str = "barrier",
    **over: Any,
) -> dict[str, Any]:
    record = make_icf_wire_record(
        context_type=context_type,
        claim=claim,
        intervention=intervention,
        anchors=[{"segment_id": segment_id, "quote": quote}],
        **over,
    )
    return record.model_dump()


def _seed_full_text_doc(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    title: str,
    chunk_content: str,
    chunk_id: uuid.UUID | None = None,
    stub_iof: list[dict[str, Any]] | None = None,
    stub_icf: list[dict[str, Any]] | None = None,
    stub_failed: bool = False,
    evidence_type: str | None = EVIDENCE_TYPE,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a full-text doc (envelope + full-text snapshot + one chunk). Returns (pss, chunk).

    Pass ``chunk_id`` when a ``stub_iof`` anchor must name the chunk (generate it
    first, then reference ``str(chunk_id)`` as the anchor's segment_id).
    """
    envelope_snap = uuid.uuid4()
    ft_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    chunk_id = chunk_id or uuid.uuid4()
    meta: dict[str, Any] = {"title": title, "abstract": f"Abstract for {title}."}
    if stub_iof is not None:
        meta["_stub_iof"] = stub_iof
    if stub_icf is not None:
        meta["_stub_icf"] = stub_icf
    if stub_failed:
        meta["_stub_extract_failed"] = True

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
    conn.execute(chunk.insert().values(
        chunk_id=chunk_id, source_snapshot_id=ft_snap, sequence=0, content=chunk_content,
        content_hash=str(uuid.uuid4()), locator={}, segmentation_policy="manual_v1",
        created_at=now(),
    ))
    if evidence_type is not None:
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(), evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id, project_id=project_id,
            classified_by_run_id=run_id, primary_evidence_type=evidence_type, classified_at=now(),
        ))
    return pss_id, chunk_id


def _seed_abstract_doc(
    conn: Connection,
    project_id: uuid.UUID,
    *,
    title: str,
    abstract: str,
    stub_iof: list[dict[str, Any]] | None = None,
) -> uuid.UUID:
    """Seed an abstract-only doc (envelope snapshot, no chunks). Returns pss id."""
    envelope_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    meta: dict[str, Any] = {"title": title, "abstract": abstract}
    if stub_iof is not None:
        meta["_stub_iof"] = stub_iof
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=envelope_snap, content_hash=str(uuid.uuid4()),
        text_basis="abstract_only", source_locator="https://example.org/x", metadata=meta,
        created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id, project_id=project_id,
        source_snapshot_id=envelope_snap, origin="acquired", run_id=None, ingested_at=now(),
    ))
    return pss_id


def _seed_selection(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected: list[dict[str, Any]],
) -> None:
    conn.execute(selection_result.insert().values(
        selection_result_id=uuid.uuid4(), project_id=project_id, evidence_scope_id=scope_id,
        run_id=run_id, strategy="coverage_stratified_v1", budget=25,
        selection_provenance={}, selected=selected, excluded={}, flags={}, created_at=now(),
    ))


def _run(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    *,
    profiles: tuple[str, ...] = (IOF_PROFILE_ID,),
) -> tuple[dict[str, Any], uuid.UUID]:
    """Seed a fresh extract run and execute extract_scope; return (summary, run_id)."""
    run_id = seed_run(conn, project_id)
    summary = extract_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=selection_run_id
        ),
        extraction_backend=StubExtractionBackend(),
        profiles=profiles,
    )
    return summary, run_id


def _finding_count(conn: Connection, project_id: uuid.UUID) -> int:
    return int(conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one())


# --- Tests ------------------------------------------------------------------


def test_fresh_full_text_extraction(conn: Connection) -> None:
    """Fresh full-text extraction writes verified findings, a record, and the roll-up."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = "Structured tutoring raised reading scores compared with usual teaching."
    cid = uuid.uuid4()
    pss_id, chunk_id = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Tutoring RCT", chunk_content=content,
        chunk_id=cid,
        stub_iof=[_record(
            intervention="structured tutoring", outcome="reading scores",
            quote="Structured tutoring raised reading scores", segment_id=str(cid),
        )],
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["counts"]["selected"] == 1
    counts = profile_counts(summary)
    count_keys = ("extracted", "no_findings", "failed", "fresh", "reused")
    assert {key: counts[key] for key in count_keys} == {
        "extracted": 1,
        "no_findings": 0,
        "failed": 0,
        "fresh": 1,
        "reused": 0,
    }
    assert counts["findings"]["total"] == 1
    assert isinstance(counts["field_coverage"], dict)
    assert [d["pss_id"] for d in summary["docs"]] == [str(pss_id)]
    doc = profile_doc(summary)
    assert doc["status"] == "extracted" and doc["basis"] == "full_text" and doc["reused"] is False
    assert profile_findings(summary)["total"] == 1

    rows = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).fetchall()
    assert len(rows) == 1
    anchor = rows[0].grounding[0]
    assert anchor["quote_verified"] is True
    assert anchor["chunk_id"] == str(chunk_id)
    assert anchor["spans"] and anchor["spans"][0]["chunk_id"] == str(chunk_id)

    rollup = conn.execute(
        select(extraction_result).where(extraction_result.c.project_id == project_id)
    ).one()
    assert rollup.selection_run_id == sel_run


def test_both_profiles_write_separate_records_and_rollup_shape(conn: Connection) -> None:
    """A both-profile run writes independent records/findings and profile roll-up blocks."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = (
        "Structured tutoring raised reading scores. "
        "Training gaps slowed delivery of structured tutoring."
    )
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Dual doc",
        chunk_content=content,
        chunk_id=cid,
        stub_iof=[
            _record(
                intervention="structured tutoring",
                outcome="reading scores",
                quote="Structured tutoring raised reading scores",
                segment_id=str(cid),
            )
        ],
        stub_icf=[
            _icf_record(
                claim="Training gaps slowed delivery of structured tutoring.",
                intervention="structured tutoring",
                quote="Training gaps slowed delivery of structured tutoring",
                segment_id=str(cid),
            )
        ],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )

    summary, run_id = _run(
        conn, project_id, scope_id, sel_run, profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID)
    )

    assert list(summary["provenance"]["profiles"]) == [IOF_PROFILE_ID, ICF_PROFILE_ID]
    assert list(summary["counts"]["profiles"]) == [IOF_PROFILE_ID, ICF_PROFILE_ID]
    assert set(summary["docs"][0]["profiles"]) == {IOF_PROFILE_ID, ICF_PROFILE_ID}
    assert profile_findings(summary, IOF_PROFILE_ID)["total"] == 1
    assert profile_findings(summary, ICF_PROFILE_ID)["total"] == 1
    assert profile_doc(summary, profile_id=IOF_PROFILE_ID)["status"] == "extracted"
    assert profile_doc(summary, profile_id=ICF_PROFILE_ID)["status"] == "extracted"

    extraction_rows = conn.execute(
        select(
            source_extraction_record.c.extraction_record_id,
            source_extraction_record.c.extraction_fingerprint,
        )
        .where(source_extraction_record.c.project_id == project_id)
        .order_by(source_extraction_record.c.created_at)
    ).fetchall()
    assert len(extraction_rows) == 2
    assert len({row.extraction_fingerprint for row in extraction_rows}) == 2
    assert conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one() == 1
    assert conn.execute(
        select(func.count()).select_from(implementation_context_finding)
        .where(implementation_context_finding.c.project_id == project_id)
    ).scalar_one() == 1

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({})
    assert len(findings["iof_findings"]) == 1
    assert findings["iof_findings"][0]["kind"] == "iof"
    assert len(findings["icf_findings"]) == 1
    assert findings["icf_findings"][0]["kind"] == "icf"

    rollup = conn.execute(
        select(extraction_result.c.counts, extraction_result.c.extraction_provenance)
        .where(extraction_result.c.run_id == run_id)
    ).one()
    assert set(rollup.counts["profiles"]) == {IOF_PROFILE_ID, ICF_PROFILE_ID}
    assert set(rollup.extraction_provenance["profiles"]) == {
        IOF_PROFILE_ID,
        ICF_PROFILE_ID,
    }


def test_profile_not_selected_differs_from_selected_zero_findings(conn: Connection) -> None:
    """Absent ICF profile and fired-with-zero ICF profile have distinct payload shapes."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Zero ICF doc",
        chunk_content="Structured tutoring raised reading scores.",
        chunk_id=cid,
        stub_iof=[
            _record(
                intervention="structured tutoring",
                outcome="reading scores",
                quote="Structured tutoring raised reading scores",
                segment_id=str(cid),
            )
        ],
        stub_icf=[],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )

    iof_only, _ = _run(conn, project_id, scope_id, sel_run)
    assert ICF_PROFILE_ID not in iof_only["provenance"]["profiles"]
    assert ICF_PROFILE_ID not in iof_only["counts"]["profiles"]
    assert ICF_PROFILE_ID not in iof_only["docs"][0]["profiles"]

    both, _ = _run(
        conn, project_id, scope_id, sel_run, profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID)
    )
    assert profile_findings(both, ICF_PROFILE_ID)["total"] == 0
    assert profile_counts(both, ICF_PROFILE_ID)["no_findings"] == 1
    assert profile_doc(both, profile_id=ICF_PROFILE_ID)["status"] == "no_findings"


def test_profile_memo_isolated_between_iof_and_icf(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IOF memo reuse never implies ICF reuse; an ICF bump re-extracts ICF only."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = (
        "Home visiting reduced admissions. "
        "Nurse shortages slowed home visiting delivery."
    )
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Memo isolation doc",
        chunk_content=content,
        chunk_id=cid,
        stub_iof=[
            _record(
                intervention="home visiting",
                outcome="admissions",
                effect_direction="decrease",
                quote="Home visiting reduced admissions",
                segment_id=str(cid),
            )
        ],
        stub_icf=[
            _icf_record(
                claim="Nurse shortages slowed home visiting delivery.",
                intervention="home visiting",
                quote="Nurse shortages slowed home visiting delivery",
                segment_id=str(cid),
            )
        ],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )

    first, _ = _run(conn, project_id, scope_id, sel_run)
    first_iof_record_id = profile_doc(first)["extraction_record_id"]

    second, _ = _run(
        conn, project_id, scope_id, sel_run, profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID)
    )
    assert profile_counts(second, IOF_PROFILE_ID)["reused"] == 1
    assert profile_counts(second, ICF_PROFILE_ID)["fresh"] == 1
    assert profile_doc(second, profile_id=IOF_PROFILE_ID)["extraction_record_id"] == (
        first_iof_record_id
    )
    second_icf_record_id = profile_doc(second, profile_id=ICF_PROFILE_ID)[
        "extraction_record_id"
    ]

    with monkeypatch.context() as m:
        m.setattr("policy_atlas.extract.ICF_PROMPT_VERSION", "extract_icf_vNEXT")
        third, _ = _run(
            conn, project_id, scope_id, sel_run, profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID)
        )

    assert profile_counts(third, IOF_PROFILE_ID)["reused"] == 1
    assert profile_counts(third, ICF_PROFILE_ID)["reused"] == 0
    assert profile_counts(third, ICF_PROFILE_ID)["fresh"] == 1
    assert profile_doc(third, profile_id=IOF_PROFILE_ID)["extraction_record_id"] == (
        first_iof_record_id
    )
    assert (
        profile_doc(third, profile_id=ICF_PROFILE_ID)["extraction_record_id"]
        != second_icf_record_id
    )


def test_unknown_and_duplicate_profile_ids_fail_closed(conn: Connection) -> None:
    """Profile selection validates before any writes."""
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    run_id = seed_run(conn, project_id)
    context = ExtractContext(
        scope_id=scope_id,
        intent="unused",
        context={},
        selection_run_id=uuid.uuid4(),
    )

    with pytest.raises(ExtractError, match="unknown extraction profile"):
        extract_scope(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=context,
            extraction_backend=StubExtractionBackend(),
            profiles=("not-a-profile",),
        )
    with pytest.raises(ExtractError, match="duplicate extraction profile"):
        extract_scope(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=context,
            extraction_backend=StubExtractionBackend(),
            profiles=(IOF_PROFILE_ID, IOF_PROFILE_ID),
        )


class _FlaggingICFVetter:
    mode = "stub"

    def __init__(self, flag_class: ICFFlagClass = "recommendation") -> None:
        self.flag_class = flag_class
        self.payloads: list[dict[str, Any]] = []

    def judge(self, payload: dict[str, Any]) -> UsageResult[ICFFindingVetterResponse]:
        self.payloads.append(payload)
        verdicts = [
            ICFVetterVerdictWire(
                finding_index=int(finding["index"]),
                verdict="flagged",
                flag_class=self.flag_class,
                reason="Recommendation-shaped implementation claim.",
            )
            for finding in payload["findings"]
        ]
        return ICFFindingVetterResponse(verdicts=verdicts), None


def test_icf_vetter_excludes_icf_without_affecting_iof(conn: Connection) -> None:
    """ICF vetting is per-profile; a flagged ICF survivor leaves IOF untouched."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="ICF vetter doc",
        chunk_content=(
            "Structured tutoring raised reading scores. "
            "Schools should fund structured tutoring training."
        ),
        chunk_id=cid,
        stub_iof=[
            _record(
                intervention="structured tutoring",
                outcome="reading scores",
                quote="Structured tutoring raised reading scores",
                segment_id=str(cid),
            )
        ],
        stub_icf=[
            _icf_record(
                claim="Schools should fund structured tutoring training.",
                intervention="structured tutoring",
                quote="Schools should fund structured tutoring training",
                segment_id=str(cid),
                claim_basis="author_assertion",
            )
        ],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )
    icf_vetter = _FlaggingICFVetter()
    run_id = seed_run(conn, project_id)

    summary = extract_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id,
            intent="unused",
            context={},
            selection_run_id=sel_run,
        ),
        extraction_backend=StubExtractionBackend(),
        icf_finding_vetter_backend=icf_vetter,
        profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID),
    )

    assert profile_counts(summary, IOF_PROFILE_ID)["extracted"] == 1
    assert profile_findings(summary, IOF_PROFILE_ID)["total"] == 1
    assert profile_counts(summary, ICF_PROFILE_ID)["no_findings"] == 1
    assert profile_findings(summary, ICF_PROFILE_ID)["total"] == 0
    assert profile_doc(summary, profile_id=ICF_PROFILE_ID)["vetted_out"] == 1
    assert profile_vetted_out(summary, ICF_PROFILE_ID)["total"] == 1
    assert conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one() == 1
    assert conn.execute(
        select(func.count()).select_from(implementation_context_finding)
        .where(implementation_context_finding.c.project_id == project_id)
    ).scalar_one() == 0
    assert icf_vetter.payloads[0]["findings"][0]["context_type"] == "barrier"


def test_icf_vetter_paraphrased_label_excludes_and_accounts(
    conn: Connection,
) -> None:
    """A paraphrased-label flag uses the same flag-not-drop semantics as IOF."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="ICF label vetter doc",
        chunk_content="Training gaps slowed structured tutoring delivery.",
        chunk_id=cid,
        stub_icf=[
            _icf_record(
                claim="Training gaps slowed structured tutoring delivery.",
                context_label="Staff capability barrier",
                intervention="structured tutoring",
                quote="Training gaps slowed structured tutoring delivery",
                segment_id=str(cid),
            )
        ],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )
    icf_vetter = _FlaggingICFVetter(flag_class="paraphrased_label")
    run_id = seed_run(conn, project_id)

    summary = extract_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id,
            intent="unused",
            context={},
            selection_run_id=sel_run,
        ),
        extraction_backend=StubExtractionBackend(),
        icf_finding_vetter_backend=icf_vetter,
        profiles=(ICF_PROFILE_ID,),
    )

    assert profile_counts(summary, ICF_PROFILE_ID)["no_findings"] == 1
    assert profile_findings(summary, ICF_PROFILE_ID)["total"] == 0
    assert profile_doc(summary, profile_id=ICF_PROFILE_ID)["vetted_out"] == 1
    vetted_out = profile_vetted_out(summary, ICF_PROFILE_ID)
    assert vetted_out["total"] == 1
    assert vetted_out["by_class"] == {"paraphrased_label": 1}
    assert vetted_out["records"][0]["flag_class"] == "paraphrased_label"
    assert conn.execute(
        select(func.count()).select_from(implementation_context_finding)
        .where(implementation_context_finding.c.project_id == project_id)
    ).scalar_one() == 0


def test_memo_reuse(conn: Connection) -> None:
    """A second run over the same scope+selection reuses the first run's record."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = "Home visiting reduced hospital admissions among infants."
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Home visiting", chunk_content=content,
        chunk_id=cid,
        stub_iof=[_record(
            intervention="home visiting", outcome="hospital admissions",
            quote="Home visiting reduced hospital admissions", segment_id=str(cid),
            effect_direction="decrease",
        )],
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    first, _ = _run(conn, project_id, scope_id, sel_run)
    first_record_id = profile_doc(first)["extraction_record_id"]
    findings_after_first = _finding_count(conn, project_id)

    second, _ = _run(conn, project_id, scope_id, sel_run)

    assert profile_counts(second)["reused"] == 1
    assert profile_counts(second)["fresh"] == 0
    assert profile_doc(second)["reused"] is True
    assert profile_doc(second)["extraction_record_id"] == first_record_id
    # No new finding rows were written on the reused run.
    assert _finding_count(conn, project_id) == findings_after_first


def test_fingerprint_change_extracts_fresh_alongside(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fingerprint bump never reuses old records and never rewrites them.

    The task-020 acceptance pair in one deterministic test (its two halves
    were previously pinned only by composition): records extracted under one
    fingerprint are memo-missed after any component changes — the run
    extracts FRESH, creating a new record and new finding rows ALONGSIDE —
    while the old record and its findings survive byte-untouched
    (upgrades-never-invalidate)."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = "Home visiting reduced hospital admissions among infants."
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Home visiting", chunk_content=content,
        chunk_id=cid,
        stub_iof=[_record(
            intervention="home visiting", outcome="hospital admissions",
            quote="Home visiting reduced hospital admissions", segment_id=str(cid),
            effect_direction="decrease",
        )],
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    first, _ = _run(conn, project_id, scope_id, sel_run)
    first_record_id = profile_doc(first)["extraction_record_id"]
    findings_after_first = _finding_count(conn, project_id)
    old_findings = conn.execute(
        select(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).mappings().all()

    with monkeypatch.context() as m:
        m.setattr("policy_atlas.extract.PROMPT_VERSION", "extract_iof_vNEXT")
        second, _ = _run(conn, project_id, scope_id, sel_run)

    assert profile_counts(second)["reused"] == 0
    assert profile_counts(second)["fresh"] == 1
    assert profile_doc(second)["extraction_record_id"] != first_record_id
    # New finding rows landed alongside; the old rows are byte-identical.
    assert _finding_count(conn, project_id) == 2 * findings_after_first
    surviving = conn.execute(
        select(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.finding_id.in_(
            [row["finding_id"] for row in old_findings]
        ))
    ).mappings().all()
    assert sorted(surviving, key=lambda r: str(r["finding_id"])) == sorted(
        old_findings, key=lambda r: str(r["finding_id"])
    )
    # And the untouched original fingerprint still reuses its own record.
    third, _ = _run(conn, project_id, scope_id, sel_run)
    assert profile_counts(third)["reused"] == 1
    assert profile_doc(third)["extraction_record_id"] == first_record_id


def test_abstract_basis(conn: Connection) -> None:
    """An abstract-only doc extracts from the envelope; anchors carry chunk_id None."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    abstract = "Mentoring improved school attendance for disadvantaged pupils."
    pss_id = _seed_abstract_doc(
        conn, project_id, title="Mentoring", abstract=abstract,
        stub_iof=[_record(
            intervention="mentoring", outcome="school attendance",
            quote="Mentoring improved school attendance", segment_id="abstract",
        )],
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "abstract_only"}])

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert profile_counts(summary)["extracted"] == 1
    assert profile_doc(summary)["basis"] == "abstract_only"
    anchor = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).one().grounding[0]
    assert anchor["quote_verified"] is True
    assert anchor["chunk_id"] is None
    assert anchor["spans"][0]["chunk_id"] is None


def test_window_failure_does_not_fail_component(conn: Connection) -> None:
    """A window-failing doc lands extraction_failed; a sibling proceeds; no raise."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    ok_chunk = uuid.uuid4()
    ok_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Good doc",
        chunk_content="Coaching increased graduation rates in the trial.",
        chunk_id=ok_chunk,
        stub_iof=[_record(
            intervention="coaching", outcome="graduation rates",
            quote="Coaching increased graduation rates", segment_id=str(ok_chunk),
        )],
    )
    fail_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Bad doc",
        chunk_content="Some content here.", stub_failed=True,
    )
    _seed_selection(conn, project_id, sel_run, scope_id, [
        {"pss_id": str(ok_pss), "text_basis": "full_text"},
        {"pss_id": str(fail_pss), "text_basis": "full_text"},
    ])

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert summary["counts"]["selected"] == 2
    assert profile_counts(summary)["extracted"] == 1
    assert profile_counts(summary)["failed"] == 1
    assert "extraction_failures" in summary["flags"]
    by_pss = {d["pss_id"]: d for d in profile_docs(summary)}
    assert by_pss[str(fail_pss)]["status"] == "extraction_failed"
    assert by_pss[str(fail_pss)]["error"] == "window_failed: RuntimeError"
    assert by_pss[str(ok_pss)]["status"] == "extracted"


def test_no_findings_and_memo(conn: Connection) -> None:
    """No sentinel yields no_findings; the second run reuses that record."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Silent doc",
        chunk_content="This document reports no intervention outcome findings.",
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    first, _ = _run(conn, project_id, scope_id, sel_run)
    assert profile_counts(first)["no_findings"] == 1
    assert profile_doc(first)["status"] == "no_findings"

    second, _ = _run(conn, project_id, scope_id, sel_run)
    assert profile_counts(second)["reused"] == 1
    assert profile_doc(second)["reused"] is True
    assert profile_doc(second)["status"] == "no_findings"


def test_empty_selection(conn: Connection) -> None:
    """An empty selection writes a zero-doc roll-up flagged empty_selection."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_selection(conn, project_id, sel_run, scope_id, [])

    summary, run_id = _run(conn, project_id, scope_id, sel_run)

    assert summary["flags"] == ["empty_selection"]
    assert summary["counts"]["selected"] == 0
    counts = profile_counts(summary)
    count_keys = ("extracted", "no_findings", "failed", "fresh", "reused")
    assert {key: counts[key] for key in count_keys} == {
        "extracted": 0,
        "no_findings": 0,
        "failed": 0,
        "fresh": 0,
        "reused": 0,
    }
    assert counts["findings"]["total"] == 0
    assert counts["field_coverage"] == {}
    assert conn.execute(
        select(func.count()).select_from(extraction_result)
        .where(extraction_result.c.run_id == run_id)
    ).scalar_one() == 1


def test_missing_selection_row_raises(conn: Connection) -> None:
    """A missing selection row is a structural ExtractError."""
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    run_id = seed_run(conn, project_id)
    try:
        extract_scope(
            conn, project_id=project_id, run_id=run_id,
            context=ExtractContext(
                scope_id=scope_id, intent="unused", context={}, selection_run_id=uuid.uuid4()
            ),
            extraction_backend=StubExtractionBackend(),
        )
    except ExtractError as exc:
        assert "no selection row" in str(exc)
    else:
        raise AssertionError("expected ExtractError for a missing selection row")


def test_uploaded_full_text_doc_extracts_from_envelope_chunks(conn: Connection) -> None:
    """An uploaded doc carries its chunks on the envelope snapshot (008 model):
    full_text basis resolves to the envelope, never a false basis_mismatch."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    envelope_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    cid = uuid.uuid4()
    content = "Breakfast clubs improved school attendance across the pilot sites."
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=envelope_snap, content_hash=str(uuid.uuid4()),
        text_basis="full_text", source_locator="upload-001",
        metadata={
            "title": "Breakfast clubs", "abstract": "An uploaded report.",
            "_stub_iof": [_record(
                intervention="breakfast clubs", outcome="school attendance",
                quote="Breakfast clubs improved school attendance", segment_id=str(cid),
            )],
        },
        created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id, project_id=project_id,
        source_snapshot_id=envelope_snap, origin="uploaded", run_id=None, ingested_at=now(),
    ))
    conn.execute(chunk.insert().values(
        chunk_id=cid, source_snapshot_id=envelope_snap, sequence=0, content=content,
        content_hash=str(uuid.uuid4()), locator={}, segmentation_policy="manual_v1",
        created_at=now(),
    ))
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    doc = profile_doc(summary)
    assert doc["status"] == "extracted"
    assert doc["basis"] == "full_text"
    assert doc["error"] is None
    assert profile_findings(summary)["total"] == 1
    grounding = conn.execute(
        select(intervention_outcome_finding.c.grounding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()
    assert grounding[0]["quote_verified"] is True
    assert grounding[0]["chunk_id"] == str(cid)


def test_nul_bearing_model_output_is_scrubbed(conn: Connection) -> None:
    """A model-emitted NUL (\\u0000) is scrubbed at the backend boundary —
    Postgres rejects it in TEXT/JSONB and it aborted the first live run.
    Delivered via a misbehaving backend: a NUL can't ride the DB-stored stub
    sentinel for the same reason."""
    from policy_atlas.extraction_records import (
        ExtractionResponse,
        ExtractionWindowPayload,
        IOFRecordWire,
    )

    class _NulBackend:
        mode = "stub"

        def extract(
            self, payload: ExtractionWindowPayload
        ) -> UsageResult[ExtractionResponse]:
            record = _record(
                intervention="free school\x00 meals", outcome="absence rates",
                quote="Free school meals reduced absence rates",
                segment_id=payload.segments[0]["segment_id"],
                population="pupils\x00",
            )
            return ExtractionResponse(findings=[IOFRecordWire.model_validate(record)]), None

    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = "Free school meals reduced absence rates in the trial."
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="NUL doc", chunk_content=content,
    )
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "full_text"}])

    run_id = seed_run(conn, project_id)
    summary = extract_scope(
        conn, project_id=project_id, run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=sel_run
        ),
        extraction_backend=_NulBackend(),
    )

    assert profile_doc(summary)["status"] == "extracted"
    row = conn.execute(
        select(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).one()
    assert row.intervention == "free school meals"
    assert row.population == "pupils"
    assert "\x00" not in str(row.grounding)


# --- Evidence-type call provenance (task 020) -------------------------------


def test_evidence_type_provenance_recorded_on_attempted_call(conn: Connection) -> None:
    """A doc extracted via an attempted call records its classification value
    on source_extraction_record.primary_evidence_type; a doc with no live
    classification records the sentinel 'Unclassified' — the value actually
    sent to the prompt, which may legitimately diverge from the live
    classification read elsewhere."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    classified_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Classified doc",
        chunk_content="Coaching increased graduation rates in the trial.",
        chunk_id=cid, evidence_type="RCTs and Quasi-Experimental Studies",
        stub_iof=[_record(
            intervention="coaching", outcome="graduation rates",
            quote="Coaching increased graduation rates", segment_id=str(cid),
        )],
    )
    unclassified_pss, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Unclassified doc",
        chunk_content="Home visiting reduced admissions in the trial.",
        evidence_type=None,
    )
    _seed_selection(conn, project_id, sel_run, scope_id, [
        {"pss_id": str(classified_pss), "text_basis": "full_text"},
        {"pss_id": str(unclassified_pss), "text_basis": "full_text"},
    ])

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    assert profile_counts(summary)["failed"] == 0

    rows = {
        row.project_source_snapshot_id: row.primary_evidence_type
        for row in conn.execute(
            select(source_extraction_record).where(
                source_extraction_record.c.project_id == project_id
            )
        )
    }
    assert rows[classified_pss] == "RCTs and Quasi-Experimental Studies"
    assert rows[unclassified_pss] == extract_prompt.UNCLASSIFIED_EVIDENCE_TYPE


def test_evidence_type_provenance_null_on_pre_prompt_failure(conn: Connection) -> None:
    """A pre-prompt basis failure (empty_basis) never attempts a backend call,
    so its extraction record's primary_evidence_type stays NULL — never the
    'Unclassified' sentinel, which would falsely claim a call was made."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = _seed_abstract_doc(conn, project_id, title="Empty abstract doc", abstract="")
    _seed_selection(conn, project_id, sel_run, scope_id,
                    [{"pss_id": str(pss_id), "text_basis": "abstract_only"}])

    summary, _ = _run(conn, project_id, scope_id, sel_run)
    doc = profile_doc(summary)
    assert doc["status"] == "extraction_failed"
    assert doc["error"] == "empty_basis"

    stored = conn.execute(
        select(source_extraction_record.c.primary_evidence_type).where(
            source_extraction_record.c.project_id == project_id
        )
    ).scalar_one()
    assert stored is None


def test_extraction_fingerprint_components_v3() -> None:
    """The fingerprint's component map pins the v3 schema/field-rules names
    and the live prompt version — pure, no DB."""
    _fingerprint, components = extraction_fingerprint("stub")
    assert components["profile"] == "eb_iof_base_v1"
    assert components["schema"] == "iof_v3"
    assert components["field_rules"] == "iof_rules_v3"
    assert components["prompt"] == extract_prompt.PROMPT_VERSION


def test_icf_fingerprint_v2_isolated_from_iof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ICF rider bumps only the ICF fingerprint component block."""
    iof_fingerprint, iof_components = extraction_fingerprint(
        "stub", finding_vetter_active=True
    )
    icf_fingerprint, icf_components = icf_extraction_fingerprint(
        "stub", finding_vetter_active=True
    )

    assert icf_components["schema"] == ICF_SCHEMA_VERSION == "icf_v2"
    assert icf_components["prompt"] == ICF_PROMPT_VERSION == "extract_icf_v2"
    assert isinstance(icf_components["finding_vetter"], dict)
    assert (
        icf_components["finding_vetter"]["prompt"]
        == "extract_icf_vetter_v2"
    )
    assert iof_components["schema"] == IOF_SCHEMA_VERSION
    assert iof_components["prompt"] == extract_prompt.PROMPT_VERSION
    assert isinstance(iof_components["finding_vetter"], dict)
    assert (
        iof_components["finding_vetter"]["prompt"]
        == FINDING_VETTER_PROMPT_VERSION
    )

    with monkeypatch.context() as m:
        m.setattr("policy_atlas.extract.ICF_SCHEMA_VERSION", "icf_v1")
        m.setattr("policy_atlas.extract.ICF_PROMPT_VERSION", "extract_icf_v1")
        m.setattr(
            "policy_atlas.extract.ICF_FINDING_VETTER_PROMPT_VERSION",
            "extract_icf_vetter_v1",
        )
        icf_v1_fingerprint, _ = icf_extraction_fingerprint(
            "stub", finding_vetter_active=True
        )
        iof_after_fingerprint, iof_after_components = extraction_fingerprint(
            "stub", finding_vetter_active=True
        )

    assert icf_fingerprint != icf_v1_fingerprint
    assert iof_after_fingerprint == iof_fingerprint
    assert iof_after_components == iof_components


def test_pre_existing_icf_v1_row_reader_keeps_context_label_coverage_absent(
    conn: Connection,
) -> None:
    """An icf_v1 row remains readable; no context_label coverage key is backfilled."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "ICF v1 doc"})
    _seed_selection(
        conn,
        project_id,
        run_id,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )
    extraction_record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=extraction_record_id,
            project_id=project_id,
            source_snapshot_id=snap_id,
            project_source_snapshot_id=pss_id,
            extraction_fingerprint="fp-icf-v1-row",
            status="extracted",
            basis="full_text",
            error=None,
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=finding_id,
            project_id=project_id,
            extraction_record_id=extraction_record_id,
            context_type="barrier",
            claim="Training gaps slowed delivery.",
            intervention="home visiting",
            outcome=None,
            population=None,
            setting=None,
            study_geography=None,
            study_design=None,
            claim_level="study",
            claim_basis="studied",
            level="provider",
            resource_requirements=None,
            workforce_requirements="staff training",
            field_coverage={"outcome": "not_extracted"},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=run_id,
            extraction_provenance={
                "profiles": {
                    ICF_PROFILE_ID: {
                        "fingerprint": "fp-icf-v1-row",
                        "schema": "icf_v1",
                        "prompt": "extract_icf_v1",
                        "finding_vetter": {
                            "prompt": "extract_icf_vetter_v1",
                        },
                    }
                },
                "pass_count": 1,
            },
            docs=[
                {
                    "pss_id": str(pss_id),
                    "basis": "full_text",
                    "profiles": {
                        ICF_PROFILE_ID: {
                            "status": "extracted",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(extraction_record_id),
                        }
                    },
                }
            ],
            counts={},
            flags=[],
            created_at=now(),
        )
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({"kinds": ["icf"]})["icf_findings"]

    assert len(findings) == 1
    assert findings[0]["finding_id"] == str(finding_id)
    assert findings[0]["field_coverage"] == {"outcome": "not_extracted"}
    assert "context_label" not in findings[0]["field_coverage"]


def test_stub_icf_extract_writes_context_label_and_defaults_missing_to_null(
    conn: Connection,
) -> None:
    """Stub-backed ICF extraction stores emitted labels and NULL for omitted keys."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    content = (
        "The barrier table named Caseload pressure and said caseloads slowed "
        "home visiting. Training gaps slowed home visiting delivery."
    )
    cid = uuid.uuid4()
    missing_label_record = _icf_record(
        claim="Training gaps slowed home visiting delivery.",
        intervention="home visiting",
        quote="Training gaps slowed home visiting delivery",
        segment_id=str(cid),
    )
    missing_label_record.pop("context_label")
    pss_id, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="ICF context label doc",
        chunk_content=content,
        chunk_id=cid,
        stub_icf=[
            _icf_record(
                claim="Caseloads slowed home visiting.",
                context_label="Caseload pressure",
                intervention="home visiting",
                quote=(
                    "The barrier table named Caseload pressure and said "
                    "caseloads slowed home visiting"
                ),
                segment_id=str(cid),
            ),
            missing_label_record,
        ],
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [{"pss_id": str(pss_id), "text_basis": "full_text"}],
    )

    summary, _ = _run(
        conn, project_id, scope_id, sel_run, profiles=(ICF_PROFILE_ID,)
    )

    assert profile_findings(summary, ICF_PROFILE_ID)["total"] == 2
    rows = conn.execute(
        select(
            implementation_context_finding.c.claim,
            implementation_context_finding.c.context_label,
            implementation_context_finding.c.field_coverage,
        )
        .where(implementation_context_finding.c.project_id == project_id)
        .order_by(implementation_context_finding.c.claim)
    ).fetchall()
    assert {
        row.claim: row.context_label
        for row in rows
    } == {
        "Caseloads slowed home visiting.": "Caseload pressure",
        "Training gaps slowed home visiting delivery.": None,
    }
    coverage_by_claim = {row.claim: row.field_coverage for row in rows}
    assert "context_label" not in coverage_by_claim["Caseloads slowed home visiting."]
    assert (
        coverage_by_claim["Training gaps slowed home visiting delivery."][
            "context_label"
        ]
        == "not_extracted"
    )


def test_judge_payload_entry_key_set_excludes_effect_basis_and_study_geography() -> None:
    """Vetter payload shape-snapshot (owner gate decision 2, task 020): the
    payload deliberately does NOT carry ``effect_basis``/``study_geography``
    even though the record itself does — self-label bias risk (the vetter's
    verdict must not be swayed by a field it never itself judged). Pure,
    no DB; pins the exact key set so a future ``IOFRecord`` field addition
    can't silently leak into the judge payload."""
    record = IOFRecord(
        intervention="Coaching",
        outcome="Test scores",
        population=None,
        setting=None,
        comparator=None,
        effect_direction="increase",
        estimate_level="study",
        study_design="RCT",
        study_geography="England",
        stratum_qualifiers=[IOFStratum(type="subgroup", value="Girls")],
        statistics=IOFStatistics(),
        causality_by_design=None,
        effect_basis="observed",
        is_primary=None,
        is_prevalence_only=None,
        anchors=[IOFAnchor(segment_id="seg-1", quote="scores rose")],
    )

    entry = _judge_payload_entry(0, record)

    assert set(entry.keys()) == {
        "index",
        "intervention",
        "outcome",
        "effect_direction",
        "estimate_level",
        "stratum_qualifiers",
        "quotes",
    }
