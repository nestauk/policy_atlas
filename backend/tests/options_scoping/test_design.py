"""The specified design (task 045): validation, the intent seam, the wire map."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.option_design_prompt import OptionDesignWire


def _design(**overrides: object) -> OptionDesign:
    values: dict[str, object] = {
        "name": "Youth guarantee",
        "description": "Every young person out of work is offered a job, training or education.",
        "design_features": ["an offer within four months", "an obligation to accept"],
        "outcomes_served": ["the NEET rate"],
        "assumed": ["an obligation to accept"],
    }
    values.update(overrides)
    return OptionDesign.model_validate(values)


def test_as_intent_is_one_deterministic_paragraph() -> None:
    design = _design()
    intent = design.as_intent()
    assert intent == (
        "Youth guarantee. Every young person out of work is offered a job, training "
        "or education. Design features: an offer within four months; an obligation "
        "to accept."
    )
    assert _design().as_intent() == intent
    assert "\n" not in intent


def test_as_intent_leaves_the_outcomes_to_the_screen() -> None:
    assert "NEET" not in _design().as_intent()


def test_a_design_without_a_feature_is_refused() -> None:
    with pytest.raises(ValidationError):
        _design(design_features=[], assumed=[])


def test_an_assumed_feature_must_be_a_design_feature() -> None:
    with pytest.raises(ValidationError):
        _design(assumed=["sanctions"])


def test_a_blank_name_is_refused() -> None:
    with pytest.raises(ValidationError):
        _design(name="  ")


def test_the_design_starts_at_version_one_and_round_trips() -> None:
    design = _design()
    assert design.version == 1
    assert OptionDesign.model_validate(design.model_dump(mode="json")) == design


def test_from_wire_keeps_the_features_and_drops_a_stray_assumed() -> None:
    wire = OptionDesignWire(
        name="Youth guarantee ",
        description="An offer for every young person.",
        design_features=["an offer", " ", "a delivery point\x00"],
        outcomes_served=["the NEET rate"],
        assumed=["a delivery point", "not a feature"],
    )
    design = OptionDesign.from_wire(wire)
    assert design.name == "Youth guarantee"
    assert design.design_features == ["an offer", "a delivery point"]
    assert design.assumed == ["a delivery point"]
    assert design.version == 1
