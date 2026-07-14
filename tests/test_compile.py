"""Plan → config compile and invalid-config-caught."""

import uuid

import pytest
from pydantic import ValidationError

from policy_atlas.plan import Config, Plan, compile


def test_valid_plan_compiles() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="acquire", evidence_scope_id=scope_id)
    config = compile(plan)
    assert isinstance(config, Config)
    assert config.component == "acquire"
    assert config.evidence_scope_id == scope_id


def test_invalid_component_raises_at_plan_construction() -> None:
    with pytest.raises(ValidationError):
        Plan(component="nonexistent", evidence_scope_id=uuid.uuid4())


def test_invalid_plan_never_reaches_harness() -> None:
    """ValidationError is raised at Plan construction — harness is never invoked."""
    with pytest.raises(ValidationError):
        Plan(component="real-model", evidence_scope_id=uuid.uuid4())


def test_invalid_config_direct_construction_raises() -> None:
    """Config cannot be hand-built with bad values and sneak into the harness."""
    with pytest.raises(ValidationError):
        Config(component="bad-component", evidence_scope_id=uuid.uuid4())


def test_acquire_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="acquire")


def test_acquire_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="acquire", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "acquire"
    assert config.evidence_scope_id == scope_id


def test_screen_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="screen")


def test_screen_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="screen", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "screen"
    assert config.evidence_scope_id == scope_id


def test_classify_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="classify")


def test_classify_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="classify", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "classify"
    assert config.evidence_scope_id == scope_id


def test_appraise_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="appraise")


def test_appraise_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="appraise", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "appraise"
    assert config.evidence_scope_id == scope_id


def test_ingest_full_text_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="ingest_full_text")


def test_ingest_full_text_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="ingest_full_text", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "ingest_full_text"
    assert config.evidence_scope_id == scope_id


def test_characterise_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="characterise")


def test_characterise_valid_with_scope_id() -> None:
    scope_id = uuid.uuid4()
    plan = Plan(component="characterise", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "characterise"
    assert config.evidence_scope_id == scope_id


def test_select_requires_evidence_scope_id_and_characterisation_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="select")


def test_select_requires_characterisation_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="select", evidence_scope_id=uuid.uuid4())


def test_select_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="select", characterisation_run_id=uuid.uuid4())


def test_select_valid_with_scope_id_and_characterisation_run_id() -> None:
    scope_id = uuid.uuid4()
    characterisation_run_id = uuid.uuid4()
    plan = Plan(
        component="select",
        evidence_scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )
    config = compile(plan)
    assert config.component == "select"
    assert config.evidence_scope_id == scope_id
    assert config.characterisation_run_id == characterisation_run_id


def test_characterise_valid_without_characterisation_run_id() -> None:
    """characterisation_run_id is optional for every component except select."""
    scope_id = uuid.uuid4()
    plan = Plan(component="characterise", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.characterisation_run_id is None


def test_extract_requires_evidence_scope_id_and_selection_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="extract")


def test_extract_requires_selection_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="extract", evidence_scope_id=uuid.uuid4())


def test_extract_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="extract", selection_run_id=uuid.uuid4())


def test_extract_valid_with_both() -> None:
    scope_id = uuid.uuid4()
    selection_run_id = uuid.uuid4()
    plan = Plan(
        component="extract",
        evidence_scope_id=scope_id,
        selection_run_id=selection_run_id,
    )
    config = compile(plan)
    assert config.component == "extract"
    assert config.evidence_scope_id == scope_id
    assert config.selection_run_id == selection_run_id


def test_group_requires_evidence_scope_id_and_extraction_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="group")


def test_group_requires_extraction_run_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="group", evidence_scope_id=uuid.uuid4())


def test_group_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="group", extraction_run_id=uuid.uuid4())


def test_group_valid_with_both() -> None:
    scope_id = uuid.uuid4()
    extraction_run_id = uuid.uuid4()
    plan = Plan(
        component="group",
        evidence_scope_id=scope_id,
        extraction_run_id=extraction_run_id,
    )
    config = compile(plan)
    assert config.component == "group"
    assert config.evidence_scope_id == scope_id
    assert config.extraction_run_id == extraction_run_id


def test_synthesise_requires_evidence_scope_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="synthesise")


def test_synthesise_valid_with_scope_id_alone() -> None:
    """All four run references are optional for synthesise."""
    scope_id = uuid.uuid4()
    plan = Plan(component="synthesise", evidence_scope_id=scope_id)
    config = compile(plan)
    assert config.component == "synthesise"
    assert config.evidence_scope_id == scope_id
    assert config.characterisation_run_id is None
    assert config.selection_run_id is None
    assert config.extraction_run_id is None
    assert config.grouping_run_id is None


def test_synthesise_valid_with_characterisation_run_id_alone() -> None:
    scope_id = uuid.uuid4()
    characterisation_run_id = uuid.uuid4()
    plan = Plan(
        component="synthesise",
        evidence_scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )
    config = compile(plan)
    assert config.characterisation_run_id == characterisation_run_id


def test_synthesise_valid_with_selection_run_id_alone() -> None:
    scope_id = uuid.uuid4()
    selection_run_id = uuid.uuid4()
    plan = Plan(
        component="synthesise",
        evidence_scope_id=scope_id,
        selection_run_id=selection_run_id,
    )
    config = compile(plan)
    assert config.selection_run_id == selection_run_id


def test_synthesise_valid_with_extraction_run_id_alone() -> None:
    scope_id = uuid.uuid4()
    extraction_run_id = uuid.uuid4()
    plan = Plan(
        component="synthesise",
        evidence_scope_id=scope_id,
        extraction_run_id=extraction_run_id,
    )
    config = compile(plan)
    assert config.extraction_run_id == extraction_run_id


def test_synthesise_valid_with_grouping_run_id_alone() -> None:
    scope_id = uuid.uuid4()
    grouping_run_id = uuid.uuid4()
    plan = Plan(
        component="synthesise",
        evidence_scope_id=scope_id,
        grouping_run_id=grouping_run_id,
    )
    config = compile(plan)
    assert config.grouping_run_id == grouping_run_id


def test_synthesise_grouping_run_id_survives_compile() -> None:
    """M2 guard: grouping_run_id must not be dropped between Plan and Config."""
    scope_id = uuid.uuid4()
    grouping_run_id = uuid.uuid4()
    plan = Plan(
        component="synthesise",
        evidence_scope_id=scope_id,
        grouping_run_id=grouping_run_id,
    )
    config = compile(plan)
    assert config.grouping_run_id == plan.grouping_run_id == grouping_run_id


def test_unknown_component_still_rejected_with_grouping_run_id_field_present() -> None:
    """Adding grouping_run_id doesn't loosen the unknown-component guard."""
    with pytest.raises(ValidationError):
        Plan(
            component="nonexistent",
            evidence_scope_id=uuid.uuid4(),
            grouping_run_id=uuid.uuid4(),
        )
