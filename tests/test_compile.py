"""Plan → config compile and invalid-config-caught."""

import uuid

import pytest
from pydantic import ValidationError

from policy_atlas.plan import Config, Plan, compile


def test_valid_plan_compiles() -> None:
    snapshot_id = uuid.uuid4()
    plan = Plan(component="echo", source_snapshot_id=snapshot_id)
    config = compile(plan)
    assert isinstance(config, Config)
    assert config.component == "echo"
    assert config.source_snapshot_id == snapshot_id


def test_invalid_component_raises_at_plan_construction() -> None:
    with pytest.raises(ValidationError):
        Plan(component="nonexistent", source_snapshot_id=uuid.uuid4())


def test_invalid_plan_never_reaches_harness() -> None:
    """ValidationError is raised at Plan construction — harness is never invoked."""
    with pytest.raises(ValidationError):
        Plan(component="real-model", source_snapshot_id=uuid.uuid4())


def test_invalid_config_direct_construction_raises() -> None:
    """Config cannot be hand-built with bad values and sneak into the harness."""
    with pytest.raises(ValidationError):
        Config(component="bad-component", source_snapshot_id=uuid.uuid4())


def test_echo_requires_source_snapshot_id() -> None:
    with pytest.raises(ValidationError):
        Plan(component="echo")


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
