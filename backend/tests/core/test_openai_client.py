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
        timeout_s=45,
    )
    assert parsed == _Answer(text="ok")
    return completions.kwargs


def test_openai_kwargs_off_adds_the_extra_body() -> None:
    assert openai_kwargs("m", reasoning_effort="low", prompt_cache="off", timeout_s=60) == {
        "model": "m",
        "reasoning_effort": "low",
        "timeout": 60,
        "extra_body": _OFF_BODY,
    }


def test_openai_kwargs_breakpoint_adds_the_extra_body_too() -> None:
    """A breakpoint only limits what the provider stores if its own storing is off."""
    assert openai_kwargs("m", reasoning_effort="low", prompt_cache="breakpoint", timeout_s=60) == {
        "model": "m",
        "reasoning_effort": "low",
        "timeout": 60,
        "extra_body": _OFF_BODY,
    }


def test_openai_kwargs_auto_adds_nothing() -> None:
    assert openai_kwargs("m", reasoning_effort="low", prompt_cache="auto", timeout_s=60) == {
        "model": "m",
        "reasoning_effort": "low",
        "timeout": 60,
    }


def test_openai_kwargs_auto_sends_no_extra_body() -> None:
    kwargs = openai_kwargs("m", reasoning_effort="low", prompt_cache="auto", timeout_s=60)
    assert "extra_body" not in kwargs


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


def test_with_system_breakpoint_refuses_a_content_part_system_message() -> None:
    """A parts-list system message would be nested inside a text part and the
    provider would reject the request; fail here instead (review of task 056)."""
    messages = [{"role": "system", "content": [{"type": "text", "text": "parts"}]}]
    with pytest.raises(TypeError, match="plain string"):
        with_system_breakpoint(messages)


def test_parse_structured_breakpoint_sends_the_rewritten_messages() -> None:
    kwargs = _parse("breakpoint")
    assert kwargs["messages"] == with_system_breakpoint(_MESSAGES)
    assert kwargs["extra_body"] == _OFF_BODY
    assert _MESSAGES[1] == {"role": "system", "content": "stable system prompt"}


def test_parse_structured_off_sends_the_extra_body() -> None:
    kwargs = _parse("off")
    assert kwargs["extra_body"] == _OFF_BODY
    assert kwargs["messages"] is _MESSAGES


def test_parse_structured_auto_sends_messages_unchanged() -> None:
    kwargs = _parse("auto")
    assert kwargs["messages"] is _MESSAGES
    assert "extra_body" not in kwargs


def test_parse_structured_sends_the_step_timeout_per_request() -> None:
    """The timeout rides on the request, not the client (task 057, D12)."""
    assert _parse("auto")["timeout"] == 45


def test_cache_mode_for_known_and_unknown_steps() -> None:
    step = next(iter(CACHE_MODES))
    assert cache_mode_for(step) == CACHE_MODES[step]
    with pytest.raises(RuntimeError, match="no_such_step"):
        cache_mode_for("no_such_step")
