"""The intervention profile on the selection-free path (task 045 Phase 2.2, S7).

Contract § Acceptance checks, "intervention profile (deliverable 5)": the
profile runs over every screened-in document of a scope with no selection run
and no IOF profile; Non-evidence documents are profiled; a document covering
no intervention is recorded as such; records are memoised per (task,
snapshot, fingerprint) and reused across the longlist and a targeted scope;
comparator records are stored (membership exclusion is the longlist's);
setting and study geography come from the abstract; the IOF/ICF path is
unchanged; the record joins the union view with kind ``interventions``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    extraction_result,
    finding_reference_union,
    intervention_outcome_finding,
    intervention_profile_record,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.extract.extract import (
    ALL_PROFILE_IDS,
    KNOWN_PROFILE_IDS,
    ExtractContext,
    ExtractError,
    _parse_extraction_directive,
    extract_scope,
    extraction_fingerprint,
    icf_extraction_fingerprint,
)
from policy_atlas.evidence_search.extract.extraction_backend import (
    OpenAIInterventionsBackend,
    StubExtractionBackend,
    StubInterventionsBackend,
)
from policy_atlas.evidence_search.extract.interventions_profile import (
    interventions_fingerprint,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    InterventionsRecordCarrier,
    InterventionsResponse,
    dedup_interventions_records,
    validate_interventions_record,
)
from policy_atlas.evidence_search.extract.iof_records import ExtractionWindowPayload
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from policy_atlas.runtime.runner import LLM_BEARING_COMPONENTS, RunnerBackends
from tests.evidence_search.extract.test_extract import (
    _icf_record,
    _record,
    _seed_full_text_doc,
    _seed_selection,
)
from tests.helpers import (
    ICF_PROFILE_ID,
    IOF_PROFILE_ID,
    now,
    profile_counts,
    profile_doc,
    profile_findings,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_task_and_run,
)

NON_EVIDENCE = "Other (Non-evidence documents)"

ABSTRACT = (
    "We evaluated a peer-led walking programme for inactive adults aged 60 to 70 "
    "delivered in community leisure centres in Denmark, compared with usual care."
)


def _wire(intervention: str, quote: str, **over: Any) -> dict[str, Any]:
    record: dict[str, Any] = {"intervention": intervention, "role": "evaluated", "quote": quote}
    record.update(over)
    return record


def _seed_doc(
    conn: Connection,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    title: str = "Walking for health",
    abstract: str | None = ABSTRACT,
    stub: Any = None,
    evidence_type: str | None = None,
    status: str = "relevant",
    extra_meta: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Seed an envelope doc screened into ``scope_id``; return its tss id."""
    envelope = uuid.uuid4()
    tss_id = uuid.uuid4()
    meta: dict[str, Any] = {"title": title}
    if abstract is not None:
        meta["abstract"] = abstract
    if stub is not None:
        meta["_stub_interventions"] = stub
    meta.update(extra_meta or {})
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=envelope, content_hash=str(uuid.uuid4()),
        text_basis="abstract_only", source_locator="https://example.org/doc",
        metadata=meta, created_at=now(),
    ))
    conn.execute(task_source_snapshot.insert().values(
        task_source_snapshot_id=tss_id, task_id=task_id, source_snapshot_id=envelope,
        origin="acquired", run_id=None, ingested_at=now(),
    ))
    seed_screening_result(conn, task_id, run_id, scope_id, tss_id, status)
    if evidence_type is not None:
        _classify(conn, task_id, run_id, scope_id, tss_id, evidence_type)
    return tss_id


def _classify(
    conn: Connection,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    tss_id: uuid.UUID,
    evidence_type: str,
) -> None:
    conn.execute(source_classification_result.insert().values(
        source_classification_result_id=uuid.uuid4(), evidence_scope_id=scope_id,
        task_source_snapshot_id=tss_id, task_id=task_id, classified_by_run_id=run_id,
        primary_evidence_type=evidence_type, classified_at=now(),
    ))


def _profile(
    conn: Connection,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    backend: Any = None,
) -> tuple[dict[str, Any], uuid.UUID]:
    """Run the selection-free intervention profile over ``scope_id``."""
    run_id = seed_run(conn, task_id)
    summary = extract_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=None
        ),
        extraction_backend=StubExtractionBackend(),
        interventions_backend=backend if backend is not None else StubInterventionsBackend(),
        profiles=(INTERVENTIONS_PROFILE_ID,),
    )
    return summary, run_id


def _records(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    return list(conn.execute(
        select(intervention_profile_record)
        .where(intervention_profile_record.c.task_id == task_id)
        .order_by(intervention_profile_record.c.intervention)
    ).fetchall())


def _counts(summary: dict[str, Any]) -> dict[str, Any]:
    return profile_counts(summary, INTERVENTIONS_PROFILE_ID)


class _RecordingBackend(StubInterventionsBackend):
    """The stub, recording every payload it was sent."""

    def __init__(self) -> None:
        self.payloads: list[ExtractionWindowPayload] = []

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[InterventionsResponse]:
        self.payloads.append(payload)
        return super().extract(payload)


# --- the selection-free path ------------------------------------------------------


def test_the_profile_runs_over_every_screened_in_document_with_no_selection(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    kept = _seed_doc(
        conn, task_id, run_id, scope_id,
        stub=[_wire("peer-led walking programme", "peer-led walking programme")],
        evidence_type="RCTs and Quasi-Experimental Studies",
    )
    non_evidence = _seed_doc(
        conn, task_id, run_id, scope_id, title="Walking strategy",
        stub=[_wire("peer-led walking programme", "peer-led walking programme",
                    role="recommended")],
        evidence_type=NON_EVIDENCE,
    )
    _seed_doc(conn, task_id, run_id, scope_id, status="not_relevant",
              stub=[_wire("never profiled", "walking programme")])

    summary, extract_run = _profile(conn, task_id, scope_id)

    assert summary["counts"]["selected"] == 2
    assert {doc["tss_id"] for doc in summary["docs"]} == {str(kept), str(non_evidence)}
    assert list(summary["counts"]["profiles"]) == [INTERVENTIONS_PROFILE_ID]
    assert _counts(summary)["extracted"] == 2
    assert summary["selection_run_id"] is None
    # No IOF profile ran: no IOF record or finding exists.
    assert conn.execute(
        select(func.count()).select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.task_id == task_id)
    ).scalar_one() == 0
    rollup = conn.execute(
        select(extraction_result).where(extraction_result.c.run_id == extract_run)
    ).one()
    assert rollup.selection_run_id is None
    # Non-evidence documents are profiled (a mention, never evidence — ruling 43).
    rows = _records(conn, task_id)
    assert len(rows) == 2
    sent_types = conn.execute(
        select(source_extraction_record.c.primary_evidence_type)
        .where(source_extraction_record.c.task_source_snapshot_id == non_evidence)
    ).scalar_one()
    assert sent_types == NON_EVIDENCE


def test_the_profile_never_reads_full_text(conn: Connection) -> None:
    """``abstract_only`` by construction, even for a document with full text."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id, _ = _seed_full_text_doc(
        conn, task_id, run_id, scope_id, title="Full text doc",
        chunk_content="FULL TEXT BODY that the profile must never read.",
    )
    seed_screening_result(conn, task_id, run_id, scope_id, tss_id)
    backend = _RecordingBackend()

    summary, _ = _profile(conn, task_id, scope_id, backend=backend)

    assert len(backend.payloads) == 1
    payload = backend.payloads[0]
    assert payload.abstract == "Abstract for Full text doc."
    assert "FULL TEXT BODY" not in repr(payload.segments)
    doc = profile_doc(summary, profile_id=INTERVENTIONS_PROFILE_ID)
    assert doc["basis"] == "abstract_only"
    record = conn.execute(
        select(source_extraction_record)
        .where(source_extraction_record.c.task_source_snapshot_id == tss_id)
    ).one()
    envelope = conn.execute(
        select(task_source_snapshot.c.source_snapshot_id)
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
    ).scalar_one()
    # The memo key is the envelope snapshot, never the full-text snapshot.
    assert record.basis == "abstract_only"
    assert record.source_snapshot_id == envelope


def test_a_document_covering_no_intervention_is_recorded_as_such(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    none_doc = _seed_doc(
        conn, task_id, run_id, scope_id, title="Prevalence of inactivity",
        stub={"records": [], "covers_no_intervention": True},
    )
    some_doc = _seed_doc(
        conn, task_id, run_id, scope_id,
        stub=[_wire("peer-led walking programme", "peer-led walking programme")],
    )

    summary, _ = _profile(conn, task_id, scope_id)

    statuses = {
        row.task_source_snapshot_id: (row.status, row.finding_count, row.error)
        for row in conn.execute(
            select(source_extraction_record).where(source_extraction_record.c.task_id == task_id)
        )
    }
    assert statuses[none_doc] == ("no_findings", 0, None)
    assert statuses[some_doc] == ("extracted", 1, None)
    assert _counts(summary)["no_findings"] == 1
    (row,) = _records(conn, task_id)
    assert row.covers_no_intervention is False


def test_records_are_memoised_and_reused_across_the_longlist_and_a_targeted_scope(
    conn: Connection,
) -> None:
    """One profile of a document serves every scope of the task (A21)."""
    task_id, run_id = seed_task_and_run(conn)
    longlist_scope = seed_scope(conn, task_id)
    targeted_scope = seed_scope(conn, task_id)
    tss_id = _seed_doc(
        conn, task_id, run_id, longlist_scope,
        stub=[_wire("peer-led walking programme", "peer-led walking programme")],
    )
    seed_screening_result(conn, task_id, run_id, targeted_scope, tss_id)
    backend = _RecordingBackend()

    first, _ = _profile(conn, task_id, longlist_scope, backend=backend)
    second, _ = _profile(conn, task_id, targeted_scope, backend=backend)

    assert len(backend.payloads) == 1  # the targeted scope made no call
    assert _counts(first)["fresh"] == 1 and _counts(first)["reused"] == 0
    assert _counts(second)["fresh"] == 0 and _counts(second)["reused"] == 1
    first_doc = profile_doc(first, profile_id=INTERVENTIONS_PROFILE_ID)
    second_doc = profile_doc(second, profile_id=INTERVENTIONS_PROFILE_ID)
    assert second_doc["extraction_record_id"] == first_doc["extraction_record_id"]
    assert second_doc["status"] == "extracted" and second_doc["finding_count"] == 1
    assert conn.execute(
        select(func.count()).select_from(source_extraction_record)
        .where(source_extraction_record.c.task_id == task_id)
    ).scalar_one() == 1
    assert len(_records(conn, task_id)) == 1


def test_comparator_records_are_stored_with_their_role(conn: Connection) -> None:
    """Records exist for comparators; excluding them from membership is the longlist's."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id, stub=[
        _wire("peer-led walking programme", "peer-led walking programme"),
        _wire("usual care", "compared with usual care", role="comparator"),
    ])

    _profile(conn, task_id, scope_id)

    roles = {row.intervention: row.role for row in _records(conn, task_id)}
    assert roles == {"peer-led walking programme": "evaluated", "usual care": "comparator"}


def test_setting_and_geography_come_from_the_abstract_and_quotes_are_grounded(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id, title="Walking for health in Denmark", stub=[
        _wire(
            "peer-led walking programme", "peer-led walking programme",
            setting="community leisure centres", study_geography="Denmark",
            design_features=["peer-led", " ", "null"], outcome="n/a",
        ),
        _wire("walking for health", "Walking for health", role="mentioned"),
        _wire("free swimming", "free swimming for older adults", role="mentioned"),
    ])

    summary, _ = _profile(conn, task_id, scope_id)

    rows = {row.intervention: row for row in _records(conn, task_id)}
    walking = rows["peer-led walking programme"]
    assert walking.setting == "community leisure centres"
    assert walking.study_geography == "Denmark"
    assert walking.design_features == ["peer-led"]
    assert walking.outcome is None
    assert walking.field_coverage["outcome"] == "not_extracted"
    (anchor,) = walking.grounding
    assert anchor["quote_verified"] is True and anchor["match_status"] == "exact"
    assert anchor["chunk_id"] is None
    (span,) = anchor["spans"]
    assert span["segment"] == "abstract"
    assert ABSTRACT[span["start"]:span["end"]] == "peer-led walking programme"
    # A quote only the title carries is located in the title.
    (title_anchor,) = rows["walking for health"].grounding
    assert title_anchor["quote_verified"] is True
    assert title_anchor["spans"][0]["segment"] == "title"
    # A quote that does not locate keeps its record, with a failed grounding, counted.
    (failed,) = rows["free swimming"].grounding
    assert failed["quote_verified"] is False and failed["match_status"] == "failed"
    assert failed["spans"] == []
    assert profile_findings(summary, INTERVENTIONS_PROFILE_ID)["quote_unverified"] == 1
    assert profile_findings(summary, INTERVENTIONS_PROFILE_ID)["total"] == 3


def test_a_title_only_document_is_profiled_and_an_empty_one_fails(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    title_only = _seed_doc(
        conn, task_id, run_id, scope_id, title="Peer-led walking groups", abstract=None,
        stub=[_wire("peer-led walking groups", "Peer-led walking groups")],
    )
    empty = _seed_doc(conn, task_id, run_id, scope_id, title="", abstract=None)

    summary, _ = _profile(conn, task_id, scope_id)

    outcome = {
        row.task_source_snapshot_id: (row.status, row.error)
        for row in conn.execute(
            select(source_extraction_record).where(source_extraction_record.c.task_id == task_id)
        )
    }
    assert outcome[title_only] == ("extracted", None)
    assert outcome[empty] == ("extraction_failed", "empty_basis")
    assert _counts(summary)["failed"] == 1
    assert "extraction_failures" in summary["flags"]


def test_a_failing_call_is_coverage_not_component_failure(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    failing = _seed_doc(conn, task_id, run_id, scope_id,
                        extra_meta={"_stub_interventions_failed": True})

    summary, _ = _profile(conn, task_id, scope_id)

    row = conn.execute(
        select(source_extraction_record)
        .where(source_extraction_record.c.task_source_snapshot_id == failing)
    ).one()
    assert row.status == "extraction_failed"
    assert row.error == "window_failed: RuntimeError"
    assert summary["provenance"]["profiles"][INTERVENTIONS_PROFILE_ID]["retry_count"] == 1


def test_duplicate_and_empty_records_are_collapsed_and_dropped(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id, stub=[
        _wire("peer-led walking programme", "peer-led walking programme"),
        _wire("Peer-led  walking programme", "walking programme"),
        _wire("  ", "usual care"),
    ])

    summary, _ = _profile(conn, task_id, scope_id)

    findings = profile_findings(summary, INTERVENTIONS_PROFILE_ID)
    assert findings["dedup_collapsed"] == 1
    assert findings["invalid_dropped"] == 1
    assert len(_records(conn, task_id)) == 1


# --- refusals ------------------------------------------------------------------


def test_the_selection_free_path_runs_the_intervention_profile_only(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    with pytest.raises(ExtractError, match="selection-free path"):
        extract_scope(
            conn,
            task_id=task_id,
            run_id=seed_run(conn, task_id),
            context=ExtractContext(
                scope_id=scope_id, intent="unused", context={}, selection_run_id=None
            ),
            extraction_backend=StubExtractionBackend(),
            profiles=(IOF_PROFILE_ID,),
        )


def test_a_missing_interventions_backend_fails_loudly(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    with pytest.raises(ExtractError, match="no interventions backend"):
        extract_scope(
            conn,
            task_id=task_id,
            run_id=seed_run(conn, task_id),
            context=ExtractContext(
                scope_id=scope_id, intent="unused", context={}, selection_run_id=None
            ),
            extraction_backend=StubExtractionBackend(),
            profiles=(INTERVENTIONS_PROFILE_ID,),
        )


def test_an_es_directive_naming_icf_alone_is_still_refused() -> None:
    """The IOF-mandatory rule is not lifted (plan P9)."""
    with pytest.raises(ExtractError, match="must include"):
        _parse_extraction_directive({"profiles": [ICF_PROFILE_ID]})


def test_an_es_directive_cannot_name_the_intervention_profile() -> None:
    """The ES grammar is unchanged: the profile is reachable only by component."""
    assert KNOWN_PROFILE_IDS == (IOF_PROFILE_ID, ICF_PROFILE_ID)
    assert ALL_PROFILE_IDS == (IOF_PROFILE_ID, ICF_PROFILE_ID, INTERVENTIONS_PROFILE_ID)
    with pytest.raises(ExtractError, match="unknown profile id"):
        _parse_extraction_directive(
            {"profiles": [IOF_PROFILE_ID, INTERVENTIONS_PROFILE_ID]}
        )


# --- the IOF/ICF path is unchanged -------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "vetted", "iof", "icf"),
    [
        (
            "stub", False,
            "46bd743bd8f3c8db962ca535e2feadf93c096f6d0fd79228191919805eb30c68",
            "1815928b64649d522a536bd9a824482877aae9e9d093bf478d491cca69773287",
        ),
        (
            "stub", True,
            "d0d192c0d514895b980af063075e898759a86e233eab1a2976e470fffc5d9f43",
            "535de28cc0c8c74932c1eced414a4c5d86384e439f81a0287a991a9f77d312f8",
        ),
        (
            "live", False,
            "e1a0b88e5b71b19a31e4761ee387d104acf2906cfe8d478e4f5fa6b4d00e8e8c",
            "75cdc09cedb14a59af9730f9b645626bcc8dedcec83122636bcf3955c4f782af",
        ),
        (
            "live", True,
            "4222751b9dda0c362e4db1a7a14e5559ddd4d73f9bc9e931dba82afe65d48b7a",
            "995e4490f2ed050a45774d47c3fa3cc648998ff551d89138c5e82c453c1335ca",
        ),
    ],
)
def test_the_iof_and_icf_fingerprints_are_pinned(
    mode: str, vetted: bool, iof: str, icf: str
) -> None:
    """Pinned at 045 HEAD ``e093ce34``: the third profile moved no IOF/ICF memo key."""
    assert extraction_fingerprint(mode, finding_vetter_active=vetted)[0] == iof
    assert icf_extraction_fingerprint(mode, finding_vetter_active=vetted)[0] == icf


def test_the_intervention_fingerprint_names_its_components() -> None:
    digest, components = interventions_fingerprint("stub", retry_cap=1)
    assert len(digest) == 64
    assert components["profile"] == INTERVENTIONS_PROFILE_ID
    assert components["schema"] == "interventions_v1"
    assert components["prompt"] == "extract_interventions_v1"
    assert components["finding_vetter"] is None
    assert "window" not in components
    assert digest != interventions_fingerprint("live", retry_cap=1)[0]
    assert digest not in {
        extraction_fingerprint("stub")[0], icf_extraction_fingerprint("stub")[0]
    }


# --- the union view ---------------------------------------------------------------


def test_the_union_view_returns_the_three_kinds(conn: Connection) -> None:
    task_id, sel_run = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    content = (
        "Structured tutoring raised reading scores. "
        "Training gaps slowed delivery of structured tutoring."
    )
    cid = uuid.uuid4()
    tss_id, _ = _seed_full_text_doc(
        conn, task_id, sel_run, scope_id, title="Dual doc", chunk_content=content,
        chunk_id=cid,
        stub_iof=[_record(
            intervention="structured tutoring", outcome="reading scores",
            quote="Structured tutoring raised reading scores", segment_id=str(cid),
        )],
        stub_icf=[_icf_record(
            claim="Training gaps slowed delivery of structured tutoring.",
            intervention="structured tutoring",
            quote="Training gaps slowed delivery of structured tutoring",
            segment_id=str(cid),
        )],
    )
    _seed_selection(conn, task_id, sel_run, scope_id,
                    [{"tss_id": str(tss_id), "text_basis": "full_text"}])
    extract_scope(
        conn,
        task_id=task_id,
        run_id=seed_run(conn, task_id),
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=sel_run
        ),
        extraction_backend=StubExtractionBackend(),
        profiles=(IOF_PROFILE_ID, ICF_PROFILE_ID),
    )
    _seed_doc(conn, task_id, sel_run, scope_id, stub=[_wire(
        "peer-led walking programme", "peer-led walking programme",
        setting="community leisure centres", study_geography="Denmark",
    )])
    _profile(conn, task_id, scope_id)

    rows = conn.execute(
        select(finding_reference_union)
        .where(finding_reference_union.c.task_id == task_id)
    ).fetchall()
    assert sorted(row.kind for row in rows) == ["icf", "interventions", "iof"]
    (profiled,) = [row for row in rows if row.kind == "interventions"]
    record = conn.execute(
        select(intervention_profile_record)
        .where(intervention_profile_record.c.task_id == task_id)
    ).one()
    assert profiled.finding_id == record.record_id
    assert profiled.extraction_record_id == record.extraction_record_id
    assert (profiled.setting, profiled.study_geography) == ("community leisure centres", "Denmark")


# --- the component --------------------------------------------------------------


def test_the_component_runs_through_the_harness_with_a_scope_alone(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])
    component_run = seed_run(conn, task_id)
    config = compile(Plan(component="extract_interventions", evidence_scope_id=scope_id))

    outcome = run_harness(
        conn, config=config, task_id=task_id, run_id=component_run,
        provider=StubEchoProvider(),
    )

    assert outcome["error"] is None
    summary = outcome["summary"]
    assert summary["selection_run_id"] is None
    assert list(summary["counts"]["profiles"]) == [INTERVENTIONS_PROFILE_ID]
    assert len(_records(conn, task_id)) == 1


def test_the_component_ignores_an_es_extraction_directive(conn: Connection) -> None:
    """The profiles kwarg decides, never the scope's ES directive (P9)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(
        conn, task_id, context={"extraction": {"profiles": [ICF_PROFILE_ID]}}
    )
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])
    config = compile(Plan(component="extract_interventions", evidence_scope_id=scope_id))

    outcome = run_harness(
        conn, config=config, task_id=task_id, run_id=seed_run(conn, task_id),
        provider=StubEchoProvider(),
    )

    assert outcome["error"] is None
    assert list(outcome["summary"]["counts"]["profiles"]) == [INTERVENTIONS_PROFILE_ID]


def test_the_runner_knows_the_component_and_its_backend() -> None:
    assert "extract_interventions" in LLM_BEARING_COMPONENTS
    assert RunnerBackends().interventions is None


# --- the bundle's pure parts ----------------------------------------------------


def test_validation_coerces_null_like_text_and_keeps_an_empty_quote() -> None:
    wire = InterventionsRecordCarrier(
        intervention=" youth guarantee ", role="evaluated", design_features=["", "universal"],
        is_bundle=False, components=[], outcome="None", population=None, setting="unknown",
        study_geography="Denmark", study_design=None, quote="", covers_no_intervention=False,
    )
    validated = validate_interventions_record(wire)
    assert validated.grain_invalid is False
    assert validated.record is not None
    assert validated.record.intervention == "youth guarantee"
    assert validated.record.design_features == ["universal"]
    assert validated.record.outcome is None and validated.record.setting is None
    assert validated.record.quote == ""
    assert sorted(validated.coerced_null_fields) == ["outcome", "setting"]
    assert validated.field_coverage == {
        "outcome": "not_extracted",
        "population": "not_extracted",
        "setting": "not_extracted",
        "study_design": "not_extracted",
    }


def test_dedup_keeps_distinct_stated_designs_apart() -> None:
    def _stored(**over: Any) -> Any:
        base: dict[str, Any] = {
            "intervention": "youth guarantee", "role": "evaluated", "design_features": [],
            "is_bundle": False, "components": [], "outcome": None, "population": None,
            "setting": None, "study_geography": None, "study_design": None, "quote": "q",
            "covers_no_intervention": False,
        }
        base.update(over)
        record = validate_interventions_record(InterventionsRecordCarrier(**base)).record
        assert record is not None
        return record

    survivors, collapsed = dedup_interventions_records([
        _stored(design_features=["benefit sanction"]),
        _stored(design_features=["no sanction"]),
        _stored(intervention="Youth  Guarantee", design_features=["Benefit sanction"]),
        _stored(role="comparator"),
    ])
    assert collapsed == 1
    assert [(s.design_features, s.role) for s in survivors] == [
        (["benefit sanction"], "evaluated"),
        (["no sanction"], "evaluated"),
        ([], "comparator"),
    ]


def test_the_stub_backend_defaults_and_sentinels() -> None:
    backend = StubInterventionsBackend()

    def _payload(meta: dict[str, Any]) -> ExtractionWindowPayload:
        return ExtractionWindowPayload(
            tss_id="t", window_index=0, title="T", abstract="A",
            primary_evidence_type=None, segments=[], metadata=meta,
        )

    empty, usage = backend.extract(_payload({}))
    assert usage is None
    assert empty.records == [] and empty.covers_no_intervention is True
    listed, _ = backend.extract(_payload({"_stub_interventions": [_wire("x", "A")]}))
    assert listed.covers_no_intervention is False
    assert listed.records[0].design_features == [] and listed.records[0].setting is None
    with pytest.raises(RuntimeError):
        backend.extract(_payload({"_stub_interventions_failed": True}))
    assert backend.mode == "stub"


def test_the_live_backend_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        OpenAIInterventionsBackend()
    assert OpenAIInterventionsBackend(api_key="sk-test").mode == "live"
