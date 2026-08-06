"""Strict response-format schema regression (task 024 live-check finding).

The OpenAI strict response-format rejects any object node whose
``additionalProperties`` is absent or ``true`` (open ``dict[str, Any]``
fields), and the SDK's local converter does NOT catch it — the 400 only
surfaces live. Every wire model that reaches ``parse_structured`` must
therefore be closed: typed models, or JSON-string transport fields decoded
code-side. This test walks the emitted JSON schema and fails on any open
object node. Typed maps (``dict[str, str]`` → ``additionalProperties:
{"type": "string"}``) are allowed — planner_v5 shipped one live.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from policy_atlas.runtime.orchestrator_prompt import (
    RouterCompileTransport,
    WatchDecisionTransport,
    WatchTriageWire,
)
from policy_atlas.runtime.planner_prompt import PlannerTurnWire


def _open_object_nodes(schema: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" in schema:
            extra = schema.get("additionalProperties", True)
            if extra is True:
                found.append(path)
        elif schema.get("type") == "object" and "properties" not in schema:
            # A bare object (dict[str, Any]) — open unless typed additionalProperties.
            extra = schema.get("additionalProperties")
            if extra is None or extra is True:
                found.append(path)
        for key, value in schema.items():
            found.extend(_open_object_nodes(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            found.extend(_open_object_nodes(value, f"{path}[{index}]"))
    return found


@pytest.mark.parametrize(
    "model",
    [PlannerTurnWire, RouterCompileTransport, WatchDecisionTransport, WatchTriageWire],
)
def test_live_wire_models_carry_no_open_object_nodes(model: type[BaseModel]) -> None:
    open_nodes = _open_object_nodes(model.model_json_schema())
    assert open_nodes == [], f"{model.__name__} has open object nodes: {open_nodes}"


def test_router_transport_decodes_delta_and_demotes_bad_json() -> None:
    transport = RouterCompileTransport.model_validate(
        {
            "fragments": [
                {
                    "fragment_text": "guide the search",
                    "compiles": True,
                    "component": "acquire",
                    "delta_json": '{"search": {"guidance": ["prioritise UK evaluations"]}}',
                    "rerun_mode": "additive",
                    "refusal_reason": None,
                },
                {
                    "fragment_text": "broken",
                    "compiles": True,
                    "component": "acquire",
                    "delta_json": "{not json",
                    "rerun_mode": None,
                    "refusal_reason": None,
                },
            ],
            "summary": "one applies, one broken",
        }
    )
    wire = transport.to_wire()
    assert wire.fragments[0].delta == {"search": {"guidance": ["prioritise UK evaluations"]}}
    assert wire.fragments[1].compiles is False
    assert "validation_failed" in (wire.fragments[1].refusal_reason or "")


def test_decision_transport_decodes_needs_arguments_and_drops_bad_authored() -> None:
    transport = WatchDecisionTransport.model_validate(
        {
            "action": "insufficient",
            "reasoning": "need the dropped stratum",
            "needs": "look up the dropped stratum docs",
            "needs_tool": "lookup",
            "needs_arguments_json": '{"stratum": "rural"}',
            "authored_options": [
                {
                    "label": "ok option",
                    "why": "grounded",
                    "component": "select",
                    "delta_json": '{"selection": {"budget": 20}}',
                },
                {
                    "label": "broken option",
                    "why": "bad json",
                    "component": "select",
                    "delta_json": "nope",
                },
            ],
        }
    )
    wire = transport.to_wire()
    assert wire.needs_arguments == {"stratum": "rural"}
    assert wire.authored_options is not None
    assert len(wire.authored_options) == 1
    assert wire.authored_options[0].delta == {"selection": {"budget": 20}}


def test_decision_transport_keeps_endorsement_with_null_component_and_delta() -> None:
    transport = WatchDecisionTransport.model_validate(
        {
            "action": "author",
            "reasoning": "endorsing the existing option needs no delta",
            "authored_options": [
                {
                    "label": "Keep the current scope",
                    "why": "the canonical option already covers this",
                    "endorses_option_id": "continue",
                    "component": None,
                    "delta_json": None,
                },
                {
                    "label": "broken new suggestion",
                    "why": "not an endorsement, missing a delta",
                    "delta_json": None,
                },
            ],
        }
    )
    wire = transport.to_wire()
    assert wire.authored_options is not None
    assert len(wire.authored_options) == 1
    assert wire.authored_options[0].endorses_option_id == "continue"
    assert wire.authored_options[0].component is None
    assert wire.authored_options[0].delta is None
