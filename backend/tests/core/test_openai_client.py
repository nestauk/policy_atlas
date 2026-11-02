"""Prompt-cache modes on the shared OpenAI request helpers (task 056, contract D3)."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from policy_atlas.core.openai_client import (
    openai_kwargs,
    parse_structured,
    with_system_breakpoint,
)
from policy_atlas.evidence_search.synthesis.cache_modes import CACHE_MODES, cache_mode_for

_OFF_BODY = {"prompt_cache_options": {"mode": "explicit"}}
_MESSAGES = [
    {"role": "user", "content": "before"},
    {"role": "system", "content": "stable system prompt"},
    {"role": "user", "content": "the question"},
    {"role": "system", "content": "a second system message"},
]


class _Answer(BaseModel):
    text: str


class _RecordingCompletions:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        message = SimpleNamespace(parsed=_Answer(text="ok"))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


def _parse(prompt_cache: Any) -> dict[str, Any]:
    completions = _RecordingCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    parsed, _usage = parse_structured(
        client,
        messages=_MESSAGES,
        response_format=_Answer,
        usage_event="test_usage",
        label="test",
        model="gpt-test",
        reasoning_effort="low",
        prompt_cache=prompt_cache,
    )
    assert parsed == _Answer(text="ok")
    return completions.kwargs


def test_openai_kwargs_off_adds_the_extra_body() -> None:
    assert openai_kwargs("m", reasoning_effort="low", prompt_cache="off") == {
        "model": "m",
        "reasoning_effort": "low",
        "extra_body": _OFF_BODY,
    }


@pytest.mark.parametrize("mode", ["auto", "breakpoint"])
def test_openai_kwargs_auto_and_breakpoint_add_nothing(mode: Any) -> None:
    assert openai_kwargs("m", reasoning_effort="low", prompt_cache=mode) == {
        "model": "m",
        "reasoning_effort": "low",
    }


def test_openai_kwargs_defaults_to_auto() -> None:
    assert "extra_body" not in openai_kwargs("m", reasoning_effort="low")


def test_with_system_breakpoint_rewrites_only_the_first_system_message() -> None:
    before = copy.deepcopy(_MESSAGES)
    rewritten = with_system_breakpoint(_MESSAGES)
    assert before == _MESSAGES
    assert rewritten is not _MESSAGES
    assert rewritten[1] == {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": "stable system prompt",
                "prompt_cache_breakpoint": {"mode": "explicit"},
            }
        ],
    }
    assert rewritten[0] is _MESSAGES[0]
    assert rewritten[2] is _MESSAGES[2]
    assert rewritten[3] is _MESSAGES[3]


def test_with_system_breakpoint_without_a_system_message_is_a_copy() -> None:
    messages = [{"role": "user", "content": "hi"}]
    rewritten = with_system_breakpoint(messages)
    assert rewritten == messages
    assert rewritten is not messages


def test_parse_structured_breakpoint_sends_the_rewritten_messages() -> None:
    kwargs = _parse("breakpoint")
    assert kwargs["messages"] == with_system_breakpoint(_MESSAGES)
    assert "extra_body" not in kwargs
    assert _MESSAGES[1] == {"role": "system", "content": "stable system prompt"}


def test_parse_structured_off_sends_the_extra_body() -> None:
    kwargs = _parse("off")
    assert kwargs["extra_body"] == _OFF_BODY
    assert kwargs["messages"] is _MESSAGES


def test_parse_structured_auto_sends_messages_unchanged() -> None:
    kwargs = _parse("auto")
    assert kwargs["messages"] is _MESSAGES
    assert "extra_body" not in kwargs


def test_cache_mode_for_known_and_unknown_steps() -> None:
    step = next(iter(CACHE_MODES))
    assert cache_mode_for(step) == CACHE_MODES[step]
    with pytest.raises(RuntimeError, match="no_such_step"):
        cache_mode_for("no_such_step")
