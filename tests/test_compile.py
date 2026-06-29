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
