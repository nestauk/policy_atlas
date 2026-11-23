"""The ToC backend sends the step's reasoning effort and timeout with each call."""

import pytest

from policy_atlas.core.model_routes import route
from policy_atlas.theory_of_change import backend as toc_backend
from policy_atlas.theory_of_change.backend import OpenAITocBackend
from policy_atlas.theory_of_change.check.judge_prompt import JudgeResponse
from tests.helpers import FakeResponsesClient, spy_calls, structured_response


def test_the_judge_call_carries_the_step_s_effort_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = spy_calls(monkeypatch, toc_backend, "traced_parse")
    answer = JudgeResponse(
        support="not_about",
        quote=None,
        relevance=0,
        relevance_reason=None,
        condition=None,
        case_study=None,
        indicator=None,
        robust_model=None,
    )
    backend = OpenAITocBackend.__new__(OpenAITocBackend)
    backend._client = FakeResponsesClient(structured_response(answer))  # type: ignore[assignment]
    backend._langfuse_client = None
    backend._session_id = None
    backend.judge(
        item_text="S.\nFrom: a\nTo: b",
        population="p",
        place="England",
        document_id="d",
        title="t",
        year=2000,
        text="abc",
    )
    [kwargs] = calls
    assert kwargs["model"] == route().model_for("toc_judge")
    assert kwargs["reasoning_effort"] == route().effort_for("toc_judge")
    assert kwargs["timeout_s"] == route().timeout_for("toc_judge")
