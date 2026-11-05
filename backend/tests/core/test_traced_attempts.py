"""Tests for ``tracing.traced_attempts``: one traced retry per model call (task 057, D12).

A fake Langfuse client records every observation it opens and every ``update``
made on it, in order, so a test can read back what each attempt carried. A fake
``sleep`` records the waits instead of waiting.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import botocore.exceptions
import httpx
import openai
import pytest
from structlog.testing import capture_logs

from policy_atlas.core import liveness, tracing

_REQUEST = httpx.Request("POST", "https://provider.test/v1/chat/completions")


class _FakeSpan:
    def __init__(self, name: str, as_type: str) -> None:
        self.name = name
        self.as_type = as_type
        self.updates: list[dict[str, Any]] = []
        self.closed = False

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def metadata(self) -> dict[str, Any]:
        """Every metadata key set on the span, merged key by key (as the SDK does)."""
        merged: dict[str, Any] = {}
        for update in self.updates:
            merged.update(update.get("metadata") or {})
        return merged

    def field(self, key: str) -> Any:
        values = [update[key] for update in self.updates if key in update]
        return values[-1] if values else None


class _FakeLangfuse:
    def __init__(self) -> None:
        self.spans: list[_FakeSpan] = []

    @contextmanager
    def _observe(self, name: str, as_type: str) -> Iterator[_FakeSpan]:
        span = _FakeSpan(name, as_type)
        self.spans.append(span)
        try:
            yield span
        finally:
            span.closed = True

    def start_as_current_observation(self, *, name: str, as_type: str) -> Any:
        return self._observe(name, as_type)


class _Script:
    """A ``call`` that raises the scripted errors in turn, then returns ``"ok"``."""

    def __init__(self, *errors: BaseException) -> None:
        self._errors = list(errors)
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return "ok"


class _RecordingHub:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish_tick(self, task_id: uuid.UUID, **kwargs: Any) -> None:
        self.events.append(("verb", {"task_id": task_id, **kwargs}))

    def call_opened(self, task_id: uuid.UUID, stage: str) -> None:
        self.events.append(("opened", {"task_id": task_id, "stage": stage}))

    def call_closed(self, task_id: uuid.UUID, stage: str) -> None:
        self.events.append(("closed", {"task_id": task_id, "stage": stage}))


def _timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=_REQUEST)


def _rate_limited(retry_after: str | None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    response = httpx.Response(429, headers=headers, request=_REQUEST)
    return openai.RateLimitError("rate limited", response=response, body=None)


def _status(code: int) -> openai.APIStatusError:
    response = httpx.Response(code, request=_REQUEST)
    return openai.APIStatusError(f"status {code}", response=response, body=None)


def _run(
    call: _Script,
    client: _FakeLangfuse | None = None,
    *,
    step: str = "select_rerank",
    **kwargs: Any,
) -> tuple[str, list[float]]:
    waits: list[float] = []
    result = tracing.traced_attempts(
        client,  # type: ignore[arg-type]
        name="select:rerank",
        step=step,
        call=call,
        sleep=waits.append,
        **kwargs,
    )
    return result, waits


def test_a_timeout_then_success_makes_two_traced_attempts() -> None:
    langfuse = _FakeLangfuse()
    call = _Script(_timeout())
    seen: list[str] = []

    def _update(span: Any, result: str) -> None:
        span.update(output=result, metadata={"prompt_version": "v1"})

    def _after(_span: Any, result: str) -> None:
        seen.append(result)

    with capture_logs() as logs:
        result, waits = _run(call, langfuse, update=_update, after=_after)

    assert result == "ok"
    assert call.calls == 2
    assert waits == [tracing.DEFAULT_RETRY_WAIT_S]
    first, second = langfuse.spans
    assert [span.name for span in langfuse.spans] == ["select:rerank", "select:rerank"]
    assert {span.as_type for span in langfuse.spans} == {"generation"}
    assert first.closed and second.closed
    # The step, attempt and shared id are set before the request goes out ...
    assert first.updates[0] == {
        "metadata": {
            "step": "select_rerank",
            "attempt": 1,
            "logical_call_id": first.metadata()["logical_call_id"],
        }
    }
    assert second.updates[0]["metadata"]["attempt"] == 2
    assert first.metadata()["logical_call_id"] == second.metadata()["logical_call_id"]
    assert len(first.metadata()["logical_call_id"]) == 12
    # ... the failed attempt is marked ERROR with the error class ...
    assert first.field("level") == "ERROR"
    assert first.field("status_message").startswith("APITimeoutError: ")
    assert first.field("output") is None
    # ... and the successful one keeps the pre-call keys beside the update's own.
    assert second.field("level") is None
    assert second.field("output") == "ok"
    assert second.metadata() == {
        "step": "select_rerank",
        "attempt": 2,
        "logical_call_id": first.metadata()["logical_call_id"],
        "prompt_version": "v1",
    }
    assert seen == ["ok"]
    [retry] = [entry for entry in logs if entry["event"] == "model_call.retry"]
    assert retry["step"] == "select_rerank"
    assert retry["attempt"] == 1
    assert retry["error"] == "APITimeoutError"
    assert retry["wait_s"] == tracing.DEFAULT_RETRY_WAIT_S


@pytest.mark.parametrize(
    "error",
    [
        openai.APIConnectionError(request=_REQUEST),
        _status(500),
        _status(503),
        _rate_limited(None),
        # task 057 review (code-review 1): the botocore failures of the Bedrock routes.
        *(
            botocore.exceptions.ClientError({"Error": {"Code": code}}, "Converse")
            for code in (
                "ThrottlingException",
                "TooManyRequestsException",
                "ServiceUnavailableException",
                "ModelNotReadyException",
            )
        ),
        botocore.exceptions.ReadTimeoutError(endpoint_url="https://bedrock"),
        botocore.exceptions.ConnectTimeoutError(endpoint_url="https://bedrock"),
        botocore.exceptions.EndpointConnectionError(endpoint_url="https://bedrock"),
    ],
    ids=[
        "connection", "500", "503", "429", "bedrock-throttling", "bedrock-too-many",
        "bedrock-unavailable", "bedrock-not-ready", "bedrock-read-timeout",
        "bedrock-connect-timeout", "bedrock-endpoint",
    ],
)
def test_passing_failures_are_retried_once(error: BaseException) -> None:
    langfuse = _FakeLangfuse()
    result, waits = _run(_Script(error), langfuse)
    assert result == "ok"
    assert len(langfuse.spans) == 2
    assert waits == [tracing.DEFAULT_RETRY_WAIT_S]


@pytest.mark.parametrize(
    "error",
    [
        _status(400),
        _status(401),
        RuntimeError("OpenAI ranking response was not parsed."),
        botocore.exceptions.ClientError({"Error": {"Code": "ValidationException"}}, "Converse"),
    ],
    ids=["400", "401", "unparsed", "bedrock-validation"],
)
def test_a_failure_not_worth_retrying_raises_after_one_attempt(error: BaseException) -> None:
    langfuse = _FakeLangfuse()
    call = _Script(error)
    with pytest.raises(type(error)):
        _run(call, langfuse)
    assert call.calls == 1
    [span] = langfuse.spans
    assert span.field("level") == "ERROR"
    assert span.metadata()["attempt"] == 1


def test_every_attempt_cut_raises_after_one_observation_each() -> None:
    langfuse = _FakeLangfuse()
    call = _Script(*[_timeout() for _ in range(tracing.MODEL_CALL_ATTEMPTS)])
    waits: list[float] = []
    with pytest.raises(openai.APITimeoutError):
        tracing.traced_attempts(
            langfuse,  # type: ignore[arg-type]
            name="judge:grounding",
            step="judge_grounding",
            call=call,
            sleep=waits.append,
        )
    assert call.calls == tracing.MODEL_CALL_ATTEMPTS
    attempts = list(range(1, tracing.MODEL_CALL_ATTEMPTS + 1))
    assert [span.metadata()["attempt"] for span in langfuse.spans] == attempts
    assert [span.field("level") for span in langfuse.spans] == ["ERROR"] * len(attempts)
    assert len({span.metadata()["logical_call_id"] for span in langfuse.spans}) == 1
    assert waits == [tracing.DEFAULT_RETRY_WAIT_S] * (tracing.MODEL_CALL_ATTEMPTS - 1)


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [("7", 7.0), ("90", tracing.RETRY_AFTER_CAP_S), ("0.5", 0.5), ("soon", 1.0)],
)
def test_rate_limit_waits_for_retry_after_up_to_the_cap(retry_after: str, expected: float) -> None:
    result, waits = _run(_Script(_rate_limited(retry_after)), _FakeLangfuse())
    assert result == "ok"
    assert waits == [expected]


def test_without_langfuse_the_same_attempts_run_untraced() -> None:
    call = _Script(_timeout())
    result, waits = _run(call, None)
    assert result == "ok"
    assert call.calls == 2
    assert waits == [tracing.DEFAULT_RETRY_WAIT_S]
    with pytest.raises(ValueError):
        _run(_Script(ValueError("bad")), None)


def test_the_two_calls_get_different_ids() -> None:
    langfuse = _FakeLangfuse()
    _run(_Script(), langfuse)
    _run(_Script(), langfuse)
    ids = [span.metadata()["logical_call_id"] for span in langfuse.spans]
    assert len(set(ids)) == 2


def test_liveness_hooks_publish_the_step_verb_and_bracket_the_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _RecordingHub()
    task_id = uuid.uuid4()
    monkeypatch.setattr(liveness, "tick_hub", hub)

    with liveness.task_liveness(task_id, stage="classify"):
        result, waits = _run(_Script(), _FakeLangfuse(), step="classify_document")

    assert result == "ok"
    assert waits == []
    assert [event for event, _payload in hub.events] == ["verb", "opened", "closed"]
    assert hub.events[0][1] == {
        "task_id": task_id,
        "stage": "classify",
        "activity": "Categorising",
        "source": "hook",
    }
    assert all("done" not in payload for _event, payload in hub.events)
    assert all("total" not in payload for _event, payload in hub.events)


def test_liveness_hooks_bracket_every_retry_without_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _RecordingHub()
    monkeypatch.setattr(liveness, "tick_hub", hub)

    with liveness.task_liveness(uuid.uuid4(), stage="classify"):
        result, waits = _run(
            _Script(_timeout()), _FakeLangfuse(), step="classify_document"
        )

    assert result == "ok"
    assert waits == [tracing.DEFAULT_RETRY_WAIT_S]
    assert [event for event, _payload in hub.events] == [
        "verb",
        "opened",
        "closed",
        "verb",
        "opened",
        "closed",
    ]
    assert all("done" not in payload for _event, payload in hub.events)
    assert all("total" not in payload for _event, payload in hub.events)


def test_liveness_hooks_publish_nothing_outside_a_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _RecordingHub()
    monkeypatch.setattr(liveness, "tick_hub", hub)

    _run(_Script(), _FakeLangfuse(), step="classify_document")

    assert hub.events == []


def test_before_runs_on_every_traced_attempt_before_the_call() -> None:
    langfuse = _FakeLangfuse()
    call = _Script(_timeout())
    seen: list[_FakeSpan] = []

    def _before(span: _FakeSpan) -> None:
        seen.append(span)
        span.update(input={"messages": ["hello"]}, model="model-id")

    _run(call, langfuse, before=_before)

    assert seen == langfuse.spans
    assert [span.metadata()["attempt"] for span in seen] == [1, 2]
    assert [span.field("input") for span in seen] == [
        {"messages": ["hello"]},
        {"messages": ["hello"]},
    ]
    assert [span.field("model") for span in seen] == ["model-id", "model-id"]


def test_without_langfuse_the_liveness_hooks_still_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _RecordingHub()
    monkeypatch.setattr(liveness, "tick_hub", hub)

    with liveness.task_liveness(uuid.uuid4(), stage="classify"):
        result, waits = _run(_Script(), None, step="classify_document")

    assert result == "ok"
    assert waits == []
    assert [event for event, _payload in hub.events] == ["verb", "opened", "closed"]
