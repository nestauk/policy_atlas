"""The intervention profile's tag rules and the v2 wiring (task 046 Phase 4; S4).

With no tagging context the three tags are stored null whatever the model
returned; an outcome tag with other case or spacing is repaired to the plan
outcome's text; an unknown one becomes ``other`` and is counted in the extract
summary; a comparator's object tag is ``neither``. A tag never removes a
record. The live backend sends the context in its user message.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import intervention_profile_record
from policy_atlas.evidence_search.extract import extraction_backend as backend_module
from policy_atlas.evidence_search.extract.extract import ExtractContext, extract_scope
from policy_atlas.evidence_search.extract.extraction_backend import (
    OpenAIInterventionsBackend,
    StubExtractionBackend,
    StubInterventionsBackend,
)
from policy_atlas.evidence_search.extract.interventions_profile import (
    InterventionsWindowAdapter,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    InterventionsRecordWire,
    InterventionsResponse,
    TaggingContext,
    apply_tagging_rules,
)
from policy_atlas.evidence_search.extract.iof_records import ExtractionWindowPayload
from tests.evidence_search.extract.test_extract_interventions import _seed_doc, _wire
from tests.helpers import seed_run, seed_scope, seed_task_and_run

CONTEXT = TaggingContext(
    target_unit="young people aged 16 to 24",
    outcomes=("employment rate at 12 months", "time spent not in work"),
    intended_change="Reduce the number of young people not in work",
)

_TAGS = ("unit_tag", "outcome_tag", "object_tag")


def _record(**over: Any) -> InterventionsRecordWire:
    values: dict[str, Any] = {
        "intervention": "youth guarantee",
        "role": "evaluated",
        "design_features": [],
        "is_bundle": False,
        "components": [],
        "outcome": "employment rate",
        "unit": "young people",
        "programme_name": None,
        "setting": None,
        "study_geography": None,
        "study_country": None,
        "study_design": None,
        "quote": "youth guarantee",
        "unit_tag": "on_target",
        "outcome_tag": "employment rate at 12 months",
        "object_tag": "option",
    }
    values.update(over)
    return InterventionsRecordWire.model_validate(values)


def _tags(record: InterventionsRecordWire) -> tuple[Any, ...]:
    return tuple(getattr(record, tag) for tag in _TAGS)


# --- the rules -----------------------------------------------------------------------


def test_with_no_context_the_three_tags_are_none_whatever_the_model_said() -> None:
    tagged = apply_tagging_rules(_record(), None)
    assert _tags(tagged.record) == (None, None, None)
    assert tagged.outcome_tag_repaired is False


@pytest.mark.parametrize("tag", ["employment rate at 12 months", "time spent not in work", "other"])
def test_an_exact_outcome_tag_or_other_is_kept(tag: str) -> None:
    tagged = apply_tagging_rules(_record(outcome_tag=tag), CONTEXT)
    assert tagged.record.outcome_tag == tag
    assert tagged.outcome_tag_repaired is False


@pytest.mark.parametrize(
    "tag", ["Employment Rate at 12 Months", "  employment  rate at 12 months.", "OTHER"]
)
def test_an_outcome_tag_with_other_case_or_spacing_takes_the_plan_s_text(tag: str) -> None:
    tagged = apply_tagging_rules(_record(outcome_tag=tag), CONTEXT)
    expected = "other" if tag == "OTHER" else "employment rate at 12 months"
    assert tagged.record.outcome_tag == expected
    assert tagged.outcome_tag_repaired is False


def test_an_unknown_outcome_tag_becomes_other_and_is_a_repair() -> None:
    tagged = apply_tagging_rules(_record(outcome_tag="wellbeing"), CONTEXT)
    assert tagged.record.outcome_tag == "other"
    assert tagged.outcome_tag_repaired is True


def test_a_null_outcome_tag_under_a_context_stays_not_tagged() -> None:
    tagged = apply_tagging_rules(_record(outcome_tag=None), CONTEXT)
    assert tagged.record.outcome_tag is None
    assert tagged.outcome_tag_repaired is False


def test_a_comparator_s_object_tag_is_neither() -> None:
    tagged = apply_tagging_rules(_record(role="comparator", object_tag="option"), CONTEXT)
    assert tagged.record.object_tag == "neither"
    assert tagged.record.role == "comparator"
    untouched = apply_tagging_rules(_record(object_tag="plan_object"), CONTEXT)
    assert untouched.record.object_tag == "plan_object"


def test_the_adapter_counts_repairs_and_keeps_every_record() -> None:
    class _Fixed(StubInterventionsBackend):
        def extract(
            self, payload: ExtractionWindowPayload, context: TaggingContext | None = None
        ) -> Any:
            records = [
                _record(outcome_tag="wellbeing"),
                _record(intervention="standard support", role="comparator", outcome_tag="x"),
                _record(intervention="wage subsidy", unit_tag="other",
                        object_tag="neither"),
            ]
            return InterventionsResponse(records=records, covers_no_intervention=False), None

    adapter = InterventionsWindowAdapter(_Fixed(), CONTEXT)
    payload = ExtractionWindowPayload(
        tss_id="t", window_index=0, title="T", abstract="A",
        primary_evidence_type=None, segments=[], metadata={},
    )
    response, _ = adapter.extract(payload)
    assert len(response.findings) == 3  # a tag never removes a record
    assert [r.outcome_tag for r in response.findings] == [
        "other",
        "other",
        "employment rate at 12 months",
    ]
    assert response.findings[1].object_tag == "neither"
    assert adapter.outcome_tag_repairs == 2


# --- through extract_scope --------------------------------------------------------------


def _profile(
    conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID, context: TaggingContext | None
) -> dict[str, Any]:
    return extract_scope(
        conn,
        task_id=task_id,
        run_id=seed_run(conn, task_id),
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=None
        ),
        extraction_backend=StubExtractionBackend(),
        interventions_backend=StubInterventionsBackend(),
        profiles=(INTERVENTIONS_PROFILE_ID,),
        interventions_context=context,
    )


_STUB = [
    _wire("peer-led walking programme", "peer-led walking programme",
          unit_tag="adjacent", outcome_tag="Employment rate at 12 months.",
          object_tag="option"),
    _wire("usual care", "usual care", role="comparator",
          unit_tag="on_target", outcome_tag="physical activity", object_tag="option"),
]


def _stored(conn: Connection, task_id: uuid.UUID) -> dict[str, tuple[Any, ...]]:
    rows = conn.execute(
        select(intervention_profile_record).where(intervention_profile_record.c.task_id == task_id)
    ).all()
    return {row.intervention: tuple(getattr(row, c) for c in _TAGS) for row in rows}


def test_extract_stores_the_settled_tags_and_counts_the_repairs(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id, stub=_STUB)

    summary = _profile(conn, task_id, scope_id, CONTEXT)

    assert _stored(conn, task_id) == {
        "peer-led walking programme": ("adjacent", "employment rate at 12 months", "option"),
        "usual care": ("on_target", "other", "neither"),
    }
    assert summary["counts"]["outcome_tag_repairs"] == 1


def test_extract_with_no_context_stores_null_tags_and_counts_none(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_doc(conn, task_id, run_id, scope_id, stub=_STUB)

    summary = _profile(conn, task_id, scope_id, None)

    assert _stored(conn, task_id) == {
        "peer-led walking programme": (None, None, None),
        "usual care": (None, None, None),
    }
    assert summary["counts"]["outcome_tag_repairs"] == 0


# --- the live backend ---------------------------------------------------------------------


@pytest.mark.parametrize("context", [CONTEXT, None])
def test_the_live_backend_sends_the_context_in_the_user_message(
    monkeypatch: pytest.MonkeyPatch, context: TaggingContext | None
) -> None:
    sent: list[Any] = []

    def _parse(client: Any, *, messages: Any, **kwargs: Any) -> Any:
        sent.append(messages)
        return InterventionsResponse(records=[], covers_no_intervention=True), None

    monkeypatch.setattr(backend_module, "parse_structured", _parse)
    backend = OpenAIInterventionsBackend(api_key="sk-test")
    payload = ExtractionWindowPayload(
        tss_id="t", window_index=0, title="T", abstract="A",
        primary_evidence_type=None, segments=[], metadata={},
    )
    backend.extract(payload, context=context)

    user = sent[0][1]["content"]
    fenced = user.split("or null:\n", 1)[1].strip()
    if context is None:
        assert fenced == "null"
    else:
        assert json.loads(fenced) == {
            "target_unit": CONTEXT.target_unit,
            "outcomes": list(CONTEXT.outcomes),
            "intended_change": CONTEXT.intended_change,
        }
