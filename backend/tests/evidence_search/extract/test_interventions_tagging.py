"""The intervention profile's tagging plumbing (task 046 Phase 1; S4, S5, S10).

Contract § Acceptance checks, items 13 and 15 (the document rules) and the
migration bullet's "null tags read correctly": the tagging context enters the
intervention profile's fingerprint and reaches its backend, and nothing else;
with no context the fingerprint is today's; the plan's Where never changes
it; the three tags are stored null until a tagging prompt fills them; a
title-only document costs no call and is counted; a Non-evidence document is
still profiled.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    evidence_scope,
    intervention_profile_record,
    source_extraction_record,
    task_plan,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.extract.extract import (
    ExtractContext,
    ExtractError,
    extract_scope,
)
from policy_atlas.evidence_search.extract.extraction_backend import (
    StubExtractionBackend,
    StubInterventionsBackend,
)
from policy_atlas.evidence_search.extract.interventions_profile import (
    interventions_fingerprint,
    write_interventions_record,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    InterventionsRecord,
    InterventionsRecordCarrier,
    InterventionsResponse,
    TaggingContext,
    validate_interventions_record,
)
from policy_atlas.evidence_search.extract.iof_records import ExtractionWindowPayload
from policy_atlas.options_scoping.longlist_intent import plan_tagging_context
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.evidence_search.extract.test_extract_interventions import (
    NON_EVIDENCE,
    _seed_doc,
    _wire,
)
from tests.helpers import now, seed_run, seed_scope, seed_task_and_run
from tests.runtime.test_baseline_gate import scoping_plan

#: The intervention profile's fingerprint at 046 build-open (before this
#: phase), with no tagging context — pinned so a context-free run keeps
#: reusing every stored record.
PINNED_NO_CONTEXT = {
    "stub": "53737bfa2b095d8e65166a543cf7d992debc9dd89ea45c73ce0e553a29cae253",
    "live": "d97b6c58285fb4aa522eb12de3760e4870dcdf0133262cc4336428e2bf5d408d",
}

CONTEXT = TaggingContext(
    target_unit="refugees and asylum seekers",
    outcomes=("employment rate",),
    intended_change="Increase employment among refugees",
)


class _ContextRecordingBackend(StubInterventionsBackend):
    """The stub, recording each payload and the context it was sent with."""

    def __init__(self) -> None:
        self.calls: list[tuple[ExtractionWindowPayload, TaggingContext | None]] = []

    def extract(
        self, payload: ExtractionWindowPayload, context: TaggingContext | None = None
    ) -> UsageResult[InterventionsResponse]:
        self.calls.append((payload, context))
        return super().extract(payload, context)


def _profile(
    conn: Connection,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    backend: Any = None,
    context: TaggingContext | None = None,
) -> dict[str, Any]:
    return extract_scope(
        conn,
        task_id=task_id,
        run_id=seed_run(conn, task_id),
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=None
        ),
        extraction_backend=StubExtractionBackend(),
        interventions_backend=backend if backend is not None else StubInterventionsBackend(),
        profiles=(INTERVENTIONS_PROFILE_ID,),
        interventions_context=context,
    )


def _provenance(summary: dict[str, Any]) -> dict[str, Any]:
    provenance: dict[str, Any] = summary["provenance"]["profiles"][INTERVENTIONS_PROFILE_ID]
    return provenance


# --- the context and the fingerprint ----------------------------------------------


def test_the_context_hash_is_stable_and_follows_each_field() -> None:
    same = TaggingContext(
        target_unit=CONTEXT.target_unit,
        outcomes=CONTEXT.outcomes,
        intended_change=CONTEXT.intended_change,
    )
    assert same.context_hash == CONTEXT.context_hash
    assert len(CONTEXT.context_hash) == 64
    changed = {
        TaggingContext("older people", CONTEXT.outcomes, CONTEXT.intended_change).context_hash,
        TaggingContext(CONTEXT.target_unit, ("wellbeing",), CONTEXT.intended_change).context_hash,
        TaggingContext(CONTEXT.target_unit, CONTEXT.outcomes, "Reduce isolation").context_hash,
    }
    assert CONTEXT.context_hash not in changed
    assert len(changed) == 3


@pytest.mark.parametrize("mode", ["stub", "live"])
def test_with_no_context_the_fingerprint_is_today_s(mode: str) -> None:
    digest, components = interventions_fingerprint(mode, retry_cap=1)
    assert digest == PINNED_NO_CONTEXT[mode]
    assert "context_hash" not in components
    assert interventions_fingerprint(mode, retry_cap=1, context=None)[0] == digest


def test_the_fingerprint_changes_with_the_tagging_context() -> None:
    base, _ = interventions_fingerprint("stub", retry_cap=1)
    tagged, components = interventions_fingerprint("stub", retry_cap=1, context=CONTEXT)
    other, _ = interventions_fingerprint(
        "stub",
        retry_cap=1,
        context=TaggingContext("older people", CONTEXT.outcomes, CONTEXT.intended_change),
    )
    assert components["context_hash"] == CONTEXT.context_hash
    assert len({base, tagged, other}) == 3


def test_the_fingerprint_does_not_change_with_the_plan_s_where() -> None:
    uk = scoping_plan(where={"text": "United Kingdom", "origin": "your_call"})
    france = scoping_plan(where={"text": "France", "origin": "your_call"})
    assert plan_tagging_context(uk) == plan_tagging_context(france)
    assert (
        interventions_fingerprint("stub", retry_cap=1, context=plan_tagging_context(uk))[0]
        == interventions_fingerprint("stub", retry_cap=1, context=plan_tagging_context(france))[0]
    )


def test_the_plan_s_context_strips_place_from_the_target_unit_and_change_only() -> None:
    plan = scoping_plan(
        where={"text": "United Kingdom", "origin": "your_call"},
        target_unit={
            "text": "refugees and asylum seekers living in Greater Manchester",
            "origin": "your_call",
        },
        intended_change={
            "text": "Raise employment among refugees in the UK",
            "origin": "from_your_question",
        },
        outcomes=[{"text": "employment in Greater Manchester", "origin": "assumed"}],
    )
    context = plan_tagging_context(plan)
    assert context.target_unit == "refugees and asylum seekers"
    assert context.intended_change == "Raise employment among refugees"
    # Outcomes are not stripped.
    assert context.outcomes == ("employment in Greater Manchester",)


# --- the carrier through extract_scope -------------------------------------------


def test_the_context_reaches_the_backend_and_the_memo_key(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = _seed_doc(conn, task_id, run_id, scope_id,
                       stub=[_wire("peer-led walking programme", "peer-led walking programme")])

    untagged = _profile(conn, task_id, scope_id)
    backend = _ContextRecordingBackend()
    tagged = _profile(conn, task_id, scope_id, backend=backend, context=CONTEXT)

    assert "context_hash" not in _provenance(untagged)
    assert _provenance(untagged)["fingerprint"] == PINNED_NO_CONTEXT["stub"]
    assert _provenance(tagged)["context_hash"] == CONTEXT.context_hash
    # A record profiled with no context is not reused under one: a fresh call.
    assert [context for _payload, context in backend.calls] == [CONTEXT]
    fingerprints = set(conn.execute(
        select(source_extraction_record.c.extraction_fingerprint)
        .where(source_extraction_record.c.task_source_snapshot_id == tss_id)
    ).scalars())
    assert fingerprints == {PINNED_NO_CONTEXT["stub"], _provenance(tagged)["fingerprint"]}


def test_with_no_context_the_backend_is_called_as_before(conn: Connection) -> None:
    """A backend whose ``extract`` takes the payload alone still works."""

    class _PayloadOnly(StubInterventionsBackend):
        def extract(self, payload: ExtractionWindowPayload) -> UsageResult[InterventionsResponse]:  # type: ignore[override]
            return super().extract(payload)

    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])

    summary = _profile(conn, task_id, scope_id, backend=_PayloadOnly())

    assert summary["counts"]["profiles"][INTERVENTIONS_PROFILE_ID]["extracted"] == 1


def test_a_context_without_the_intervention_profile_is_refused(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    with pytest.raises(ExtractError, match="intervention profile only"):
        extract_scope(
            conn,
            task_id=task_id,
            run_id=seed_run(conn, task_id),
            context=ExtractContext(
                scope_id=scope_id, intent="unused", context={}, selection_run_id=uuid.uuid4()
            ),
            extraction_backend=StubExtractionBackend(),
            interventions_context=CONTEXT,
        )


# --- the harness -------------------------------------------------------------------


def _attach_plan(conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID, **over: Any) -> None:
    plan_id = uuid.uuid4()
    conn.execute(task_plan.insert().values(
        plan_id=plan_id, task_id=task_id, evidence_scope_id=scope_id, version=1,
        status="approved", payload=scoping_plan(**over).model_dump(mode="json"),
        created_at=now(), created_by="task_agent", approved_at=now(),
    ))
    conn.execute(
        update(evidence_scope)
        .where(evidence_scope.c.evidence_scope_id == scope_id)
        .values(plan_id=plan_id)
    )


def _run_component(conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID) -> dict[str, Any]:
    config = compile(Plan(component="extract_interventions", evidence_scope_id=scope_id))
    outcome = run_harness(
        conn, config=config, task_id=task_id, run_id=seed_run(conn, task_id),
        provider=StubEchoProvider(),
    )
    assert outcome["error"] is None
    summary: dict[str, Any] | None = outcome["summary"]
    assert summary is not None
    return summary


def test_the_harness_passes_the_scope_plan_s_context(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    target = {"text": "refugees living in Greater Manchester", "origin": "your_call"}
    _attach_plan(conn, task_id, scope_id, target_unit=target)
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])

    summary = _run_component(conn, task_id, scope_id)

    expected = plan_tagging_context(scoping_plan(target_unit=target))
    assert expected.target_unit == "refugees"
    assert _provenance(summary)["context_hash"] == expected.context_hash


def test_the_harness_passes_no_context_for_a_scope_with_no_plan(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])

    summary = _run_component(conn, task_id, scope_id)

    assert "context_hash" not in _provenance(summary)
    assert _provenance(summary)["fingerprint"] == PINNED_NO_CONTEXT["stub"]


# --- the tags ------------------------------------------------------------------------


def test_a_present_profile_stores_null_tags_that_read_back_as_none(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id,
              stub=[_wire("peer-led walking programme", "peer-led walking programme")])

    _profile(conn, task_id, scope_id, context=CONTEXT)

    row = conn.execute(
        select(intervention_profile_record)
        .where(intervention_profile_record.c.task_id == task_id)
    ).one()
    assert (row.population_tag, row.outcome_tag, row.object_tag) == (None, None, None)


def _stored_record(**tags: Any) -> InterventionsRecord:
    return InterventionsRecord(
        intervention="Youth guarantee", role="evaluated", design_features=[],
        is_bundle=False, components=[], outcome=None, population=None, setting=None,
        study_geography=None, study_design=None, quote="Youth guarantee",
        covers_no_intervention=False, **tags,
    )


def _extraction_record(conn: Connection, task_id: uuid.UUID) -> uuid.UUID:
    """One profile's ``source_extraction_record`` row, written through the pipeline."""
    run_id = seed_run(conn, task_id)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id)
    _profile(conn, task_id, scope_id)
    record_id: uuid.UUID = conn.execute(
        select(source_extraction_record.c.extraction_record_id)
        .where(source_extraction_record.c.task_id == task_id)
    ).scalar_one()
    return record_id


def test_the_writer_stores_the_tags_and_nulls(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    record_id = _extraction_record(conn, task_id)
    write_interventions_record(
        conn, task_id, record_id,
        _stored_record(population_tag="adjacent", outcome_tag="employment rate",
                       object_tag="option"),
        [], {}, now(),
    )
    write_interventions_record(conn, task_id, record_id, _stored_record(), [], {}, now())

    rows = conn.execute(
        select(
            intervention_profile_record.c.population_tag,
            intervention_profile_record.c.outcome_tag,
            intervention_profile_record.c.object_tag,
        ).where(intervention_profile_record.c.extraction_record_id == record_id)
    ).all()
    assert {tuple(row) for row in rows} == {
        ("adjacent", "employment rate", "option"),
        (None, None, None),
    }


@pytest.mark.parametrize(
    ("column", "constraint"),
    [("population_tag", "ck_ipr_population_tag"), ("object_tag", "ck_ipr_object_tag")],
)
def test_the_closed_tags_are_checked(conn: Connection, column: str, constraint: str) -> None:
    task_id, _ = seed_task_and_run(conn)
    record_id = _extraction_record(conn, task_id)
    write_interventions_record(conn, task_id, record_id, _stored_record(), [], {}, now())
    with pytest.raises(IntegrityError, match=constraint):
        conn.execute(
            intervention_profile_record.update()
            .where(intervention_profile_record.c.extraction_record_id == record_id)
            .values(**{column: "somewhere"})
        )


def test_validation_carries_the_tags_and_coerces_a_null_like_outcome_tag() -> None:
    base: dict[str, Any] = {
        "intervention": "youth guarantee", "role": "evaluated", "design_features": [],
        "is_bundle": False, "components": [], "outcome": None, "population": None,
        "setting": None, "study_geography": None, "study_design": None,
        "quote": "youth guarantee", "covers_no_intervention": False,
    }
    tagged = validate_interventions_record(InterventionsRecordCarrier(
        **base, population_tag="on_target", outcome_tag=" employment rate ",
        object_tag="plan_object",
    ))
    assert tagged.record is not None
    assert (
        tagged.record.population_tag, tagged.record.outcome_tag, tagged.record.object_tag
    ) == ("on_target", "employment rate", "plan_object")
    assert "population_tag" not in tagged.field_coverage

    untagged = validate_interventions_record(
        InterventionsRecordCarrier(**base, outcome_tag="n/a")
    )
    assert untagged.record is not None
    assert (
        untagged.record.population_tag, untagged.record.outcome_tag, untagged.record.object_tag
    ) == (None, None, None)


# --- title-only documents (S10) --------------------------------------------------


def test_a_title_only_document_costs_no_call_and_a_non_evidence_one_is_profiled(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    title_only = _seed_doc(
        conn, task_id, run_id, scope_id, title="Peer-led walking groups", abstract=None,
        stub=[_wire("peer-led walking groups", "Peer-led walking groups")],
    )
    blank_abstract = _seed_doc(
        conn, task_id, run_id, scope_id, title="Walking groups", abstract="   ",
    )
    non_evidence = _seed_doc(
        conn, task_id, run_id, scope_id, title="Walking strategy",
        stub=[_wire("peer-led walking programme", "peer-led walking programme",
                    role="recommended")],
        evidence_type=NON_EVIDENCE,
    )
    backend = _ContextRecordingBackend()

    summary = _profile(conn, task_id, scope_id, backend=backend)

    assert [payload.tss_id for payload, _ in backend.calls] == [str(non_evidence)]
    assert summary["counts"]["title_only"] == 2
    assert summary["counts"]["selected"] == 1
    assert {doc["tss_id"] for doc in summary["docs"]} == {str(non_evidence)}
    written = set(conn.execute(
        select(source_extraction_record.c.task_source_snapshot_id)
        .where(source_extraction_record.c.task_id == task_id)
    ).scalars())
    assert written == {non_evidence}
    assert title_only not in written and blank_abstract not in written


def test_the_selection_path_counts_no_title_only_documents(conn: Connection) -> None:
    """The IOF/ICF summary shape is untouched: no ``title_only`` key."""
    from tests.evidence_search.extract.test_extract import _seed_full_text_doc, _seed_selection
    from tests.helpers import IOF_PROFILE_ID

    task_id, sel_run = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id, _ = _seed_full_text_doc(
        conn, task_id, sel_run, scope_id, title="Doc", chunk_content="Body text."
    )
    _seed_selection(conn, task_id, sel_run, scope_id,
                    [{"tss_id": str(tss_id), "text_basis": "full_text"}])
    summary = extract_scope(
        conn,
        task_id=task_id,
        run_id=seed_run(conn, task_id),
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=sel_run
        ),
        extraction_backend=StubExtractionBackend(),
        profiles=(IOF_PROFILE_ID,),
    )
    assert "title_only" not in summary["counts"]
