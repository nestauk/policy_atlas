"""The round-14 model calls trace under the pipeline's names (task 058, round 14).

``task_agent:title`` (step ``task_title``), ``chat:title`` (step ``chat_title``)
and ``shortlist:note`` (step ``shortlist_note``), each through the shared
``traced_parse`` (``tracing.traced_attempts``), with the session it is given.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from policy_atlas.options_scoping import scoping_backend
from policy_atlas.options_scoping.shortlist.shortlist_note_prompt import ShortlistNoteWire
from policy_atlas.runtime import agent_backend
from policy_atlas.runtime.title_prompt import TitleWire


def _capture(monkeypatch: pytest.MonkeyPatch, module: Any, answer: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake(_client: Any, _langfuse: Any, **kwargs: Any) -> tuple[Any, None]:
        calls.append(kwargs)
        return answer, None

    monkeypatch.setattr(module, "traced_parse", fake)
    return calls


def test_the_title_calls_are_named_for_their_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture(monkeypatch, agent_backend, TitleWire(title="A title"))
    backend = agent_backend.OpenAIAgentBackend(api_key="sk-test")
    task_id, conversation_id = uuid.uuid4(), uuid.uuid4()
    assert backend.write_title("task", "What works?", session_id=task_id) == "A title"
    assert backend.write_title("chat", "Which trials?", session_id=conversation_id) == "A title"
    assert [(c["name"], c["step"], c["session_id"]) for c in calls] == [
        ("task_agent:title", "task_title", task_id),
        ("chat:title", "chat_title", conversation_id),
    ]
    assert [c["prompt_version"] for c in calls] == ["task_title_v1", "chat_title_v1"]


def test_the_shortlist_note_call_is_named_shortlist_note(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture(monkeypatch, scoping_backend, ShortlistNoteWire(note="A note."))
    backend = scoping_backend.OpenAILonglistBackend("sk-test")
    wire, _ = backend.shortlist_note(outcomes=["NEET rate"], options=[], places=[], changes=[])
    assert wire.note == "A note."
    [call] = calls
    assert (call["name"], call["step"], call["prompt_version"]) == (
        "shortlist:note",
        "shortlist_note",
        "shortlist_note_v1",
    )
