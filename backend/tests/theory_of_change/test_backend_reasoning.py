"""The ToC backend sends the route's reasoning setting with each call."""

from types import SimpleNamespace
from typing import Any

from policy_atlas.core.model_routes import route
from policy_atlas.theory_of_change.backend import OpenAITocBackend
from policy_atlas.theory_of_change.evidence.judge_prompt import JudgeResponse


class _Client:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        parsed = JudgeResponse(
            support="not_about",
            quote=None,
            relevance=0,
            relevance_reason=None,
            condition=None,
            case_study=None,
            indicator=None,
            robust_model=None,
        )
        message = SimpleNamespace(parsed=parsed, refusal=None)
        self._response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self._response


def test_the_judge_call_carries_the_route_s_reasoning_setting() -> None:
    client = _Client()
    backend = OpenAITocBackend.__new__(OpenAITocBackend)
    backend._client = client
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
    model = route().model_for("toc_judge")
    assert client.kwargs["model"] == model
    expected = route().reasoning_effort_for(model)
    assert client.kwargs.get("reasoning_effort") == expected
