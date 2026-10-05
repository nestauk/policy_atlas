"""Tests for the runner's trace score/IO attachment (`_attach_trace_scores`).

The skeleton-era wiring these tests guard was dead between task 023 (skeleton
retirement) and its restoration: nothing filled the ``run:{component}:{run_id}``
trace input/output or the trace-level quality scores.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from policy_atlas.runtime.runner import _attach_trace_scores


class _ScoreClient:
    def __init__(self) -> None:
        self.scores: dict[str, float] = {}

    def score_current_trace(self, *, name: str, value: float, data_type: str) -> None:
        assert data_type == "NUMERIC"
        self.scores[name] = value


class _RootSpan:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


class _IntentConn:
    """Fake connection returning a fixed evidence-scope intent."""

    def __init__(self, intent: str) -> None:
        self._intent = intent

    def execute(self, statement: Any) -> Any:
        class _Result:
            def __init__(self, intent: str) -> None:
                self._intent = intent

            def scalar_one_or_none(self) -> str:
                return self._intent

        return _Result(self._intent)


def test_classify_summary_dispatches_scores_and_root_io() -> None:
    client = _ScoreClient()
    root_span = _RootSpan()

    _attach_trace_scores(
        client,
        cast("Any", _IntentConn("unused")),
        registry_component="classify",
        evidence_scope_id=uuid.uuid4(),
        summary={
            "classified": 4,
            "failed": 0,
            "by_type": {"Unknown / Insufficient information": 1},
            "tags_rejected": 2,
        },
        root_span=root_span,
    )

    assert "classify_failure_count" in client.scores
    assert root_span.updates and root_span.updates[0]["output"]["classified"] == 4


def test_characterise_dispatch_reads_intent_for_trace_input() -> None:
    client = _ScoreClient()
    root_span = _RootSpan()

    _attach_trace_scores(
        client,
        cast("Any", _IntentConn("childcare costs")),
        registry_component="characterise",
        evidence_scope_id=uuid.uuid4(),
        summary={"unclustered": {"count": 1, "share": 0.1}, "flags": []},
        root_span=root_span,
    )

    assert client.scores["unclustered_share"] == 0.1
    assert root_span.updates[0]["input"] == {
        "component": "characterise",
        "intent": "childcare costs",
    }


def test_component_without_scorer_still_gets_trace_io() -> None:
    client = _ScoreClient()
    root_span = _RootSpan()

    _attach_trace_scores(
        client,
        cast("Any", _IntentConn("unused")),
        registry_component="acquire",
        evidence_scope_id=uuid.uuid4(),
        summary={"screened": 12},
        root_span=root_span,
    )

    assert client.scores == {}
    assert root_span.updates == [
        {"input": {"component": "acquire"}, "output": {"screened": 12}}
    ]


def test_scorer_failure_never_raises() -> None:
    """A drifted summary shape must be logged, not fail a committed component."""
    _attach_trace_scores(
        _ScoreClient(),
        cast("Any", _IntentConn("unused")),
        registry_component="extract",
        evidence_scope_id=uuid.uuid4(),
        summary={},  # missing every key extraction_score_summary indexes
        root_span=_RootSpan(),
    )


def test_none_client_is_a_no_op() -> None:
    root_span = _RootSpan()
    _attach_trace_scores(
        None,
        cast("Any", _IntentConn("unused")),
        registry_component="classify",
        evidence_scope_id=uuid.uuid4(),
        summary={"classified": 1},
        root_span=root_span,
    )
    assert root_span.updates == []
