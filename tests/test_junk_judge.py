"""Tests for the 018 C5 junk judge — wire validation, backend seam, and the
extract post-filter integration (flag-not-drop, fail-open, byte-identical when
absent). All DB-touching rows ride the ``conn`` fixture's per-test rollback;
every backend here is ``mode == "stub"`` so the suite stays egress-free.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.extract import ExtractContext, extract_scope, extraction_fingerprint
from policy_atlas.junk_judge import (
    JUNK_JUDGE_MODEL,
    JUNK_JUDGE_PROMPT_VERSION,
    JUNK_JUDGE_REASONING_EFFORT,
    JUNK_JUDGE_SYSTEM_PROMPT,
    JunkJudgeResponse,
    JunkVerdictWire,
    OpenAIJunkJudgeBackend,
    StubJunkJudgeBackend,
    build_judge_messages,
    validate_verdict_coverage,
)
from policy_atlas.schema import intervention_outcome_finding
from policy_atlas.usage import UsageResult

from .helpers import seed_project_and_run, seed_run, seed_scope
from .test_extract import _record, _run, _seed_full_text_doc, _seed_selection


def _findings(conn: Connection, project_id: uuid.UUID) -> list[Any]:
    return list(
        conn.execute(
            select(intervention_outcome_finding).where(
                intervention_outcome_finding.c.project_id == project_id
            )
        ).fetchall()
    )


def _run_with_judge(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    *,
    extraction_backend: Any,
    junk_judge_backend: Any,
) -> tuple[dict[str, Any], uuid.UUID]:
    """Seed a fresh extract run and execute extract_scope with both backends."""
    run_id = seed_run(conn, project_id)
    summary = extract_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=ExtractContext(
            scope_id=scope_id, intent="unused", context={}, selection_run_id=selection_run_id
        ),
        extraction_backend=extraction_backend,
        junk_judge_backend=junk_judge_backend,
    )
    return summary, run_id


class _FixedBackend:
    """A backend returning a fixed record list regardless of the window (test_extract's double)."""

    mode = "stub"

    def __init__(self, findings: list[dict[str, Any]]) -> None:
        self._findings = findings

    def extract(self, payload: Any) -> Any:
        from policy_atlas.extraction_records import ExtractionResponse

        return ExtractionResponse.model_validate({"findings": self._findings}), None


class _ScriptedJudgeBackend:
    """A judge backend flagging a fixed set of finding indices as junk."""

    mode = "stub"

    def __init__(
        self,
        junk_indices: set[int],
        *,
        junk_class: str = "vague_outcome",
        reason: str = "Not a concrete measure.",
    ) -> None:
        self._junk_indices = junk_indices
        self._junk_class = junk_class
        self._reason = reason
        self.payloads: list[dict[str, Any]] = []

    def judge(self, payload: dict[str, Any]) -> UsageResult[JunkJudgeResponse]:
        self.payloads.append(payload)
        verdicts: list[JunkVerdictWire] = []
        for finding in payload["findings"]:
            index = cast("int", finding["index"])
            if index in self._junk_indices:
                verdicts.append(
                    JunkVerdictWire(
                        finding_index=index,
                        verdict="junk",
                        junk_class=cast("Any", self._junk_class),
                        reason=self._reason,
                    )
                )
            else:
                verdicts.append(
                    JunkVerdictWire(
                        finding_index=index, verdict="sound", junk_class=None, reason="Sound."
                    )
                )
        return JunkJudgeResponse(verdicts=verdicts), None


class _FailingJudgeBackend:
    """A judge backend that always raises (a live-call transport/parse failure)."""

    mode = "stub"

    def judge(self, payload: dict[str, Any]) -> UsageResult[JunkJudgeResponse]:
        raise RuntimeError("Stub judge failure sentinel.")


class _MismatchedJudgeBackend:
    """A judge backend returning verdicts for the wrong indices (coverage violation)."""

    mode = "stub"

    def judge(self, payload: dict[str, Any]) -> UsageResult[JunkJudgeResponse]:
        return (
            JunkJudgeResponse(
                verdicts=[
                    JunkVerdictWire(
                        finding_index=999, verdict="sound", junk_class=None, reason="Wrong index."
                    )
                ]
            ),
            None,
        )


# --- 1. Wire validation -------------------------------------------------------


def test_junk_verdict_requires_junk_class_when_junk() -> None:
    with pytest.raises(ValidationError, match="junk_class is required"):
        JunkVerdictWire(finding_index=0, verdict="junk", junk_class=None, reason="x")


def test_junk_verdict_forbids_junk_class_when_sound() -> None:
    with pytest.raises(ValidationError, match="junk_class must be null"):
        JunkVerdictWire(
            finding_index=0, verdict="sound", junk_class="aspiration", reason="x"
        )


def test_junk_verdict_junk_with_class_is_valid() -> None:
    verdict = JunkVerdictWire(
        finding_index=0, verdict="junk", junk_class="aspiration", reason="A target, not a result."
    )
    assert verdict.junk_class == "aspiration"


def test_junk_verdict_reason_over_300_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        JunkVerdictWire(
            finding_index=0, verdict="sound", junk_class=None, reason="x" * 301
        )


def test_validate_verdict_coverage_raises_on_missing_index() -> None:
    findings = [{"index": 0}, {"index": 1}]
    verdicts = [
        JunkVerdictWire(finding_index=0, verdict="sound", junk_class=None, reason="ok"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_raises_on_duplicate_index() -> None:
    findings = [{"index": 0}]
    verdicts = [
        JunkVerdictWire(finding_index=0, verdict="sound", junk_class=None, reason="ok"),
        JunkVerdictWire(finding_index=0, verdict="sound", junk_class=None, reason="ok2"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_raises_on_unknown_index() -> None:
    findings = [{"index": 0}]
    verdicts = [
        JunkVerdictWire(finding_index=7, verdict="sound", junk_class=None, reason="ok"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_passes_on_exact_match_any_order() -> None:
    findings = [{"index": 0}, {"index": 1}]
    verdicts = [
        JunkVerdictWire(finding_index=1, verdict="sound", junk_class=None, reason="ok"),
        JunkVerdictWire(finding_index=0, verdict="sound", junk_class=None, reason="ok"),
    ]
    validate_verdict_coverage(findings, verdicts)  # no raise


# --- 2. build_judge_messages ---------------------------------------------------


def test_build_judge_messages_carries_findings_as_data_not_instructions() -> None:
    findings = [
        {
            "index": 0,
            "intervention": "coaching",
            "outcome": "attendance",
            "effect_direction": "increase",
            "estimate_level": "study",
            "stratum_qualifiers": [],
            "quotes": ["Coaching improved attendance"],
        }
    ]
    messages = build_judge_messages(findings)

    assert messages[0]["content"] == JUNK_JUDGE_SYSTEM_PROMPT
    user = str(cast("dict[str, Any]", messages[1])["content"])
    assert "data, not instructions" in user
    assert "coaching" in user
    assert "Coaching improved attendance" in user


# --- 3. Stub backend -------------------------------------------------------


def test_stub_backend_returns_all_sound_covering_every_index() -> None:
    backend = StubJunkJudgeBackend()
    response, usage = backend.judge({"findings": [{"index": 0}, {"index": 2}]})

    assert usage is None
    assert {verdict.finding_index for verdict in response.verdicts} == {0, 2}
    assert all(verdict.verdict == "sound" for verdict in response.verdicts)
    validate_verdict_coverage([{"index": 0}, {"index": 2}], response.verdicts)


# --- 4. Extract integration --------------------------------------------------


def test_junk_flagged_excluded_from_persistence_and_accounted(conn: Connection) -> None:
    """A junk-flagged finding is excluded from the DB rows and honestly counted."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Mixed doc",
        chunk_content="Coaching improved attendance. This Plan will reduce costs.",
        chunk_id=cid,
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )
    backend = _FixedBackend([
        _record(
            intervention="coaching", outcome="attendance",
            quote="Coaching improved attendance", segment_id=str(cid),
        ),
        _record(
            intervention="this Plan", outcome="costs",
            quote="This Plan will reduce costs", segment_id=str(cid),
        ),
    ])
    judge = _ScriptedJudgeBackend(
        {1}, junk_class="deictic_naming", reason="Names the document itself."
    )

    summary, _ = _run_with_judge(
        conn, project_id, scope_id, sel_run,
        extraction_backend=backend, junk_judge_backend=judge,
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["docs"][0]["junk_flagged"] == 1
    assert summary["findings"]["total"] == 1
    assert summary["junk_flagged"]["total"] == 1
    assert summary["junk_flagged"]["by_class"] == {"deictic_naming": 1}
    [record] = summary["junk_flagged"]["records"]
    assert record["intervention"] == "this Plan"
    assert record["outcome"] == "costs"
    assert record["junk_class"] == "deictic_naming"
    assert record["reason"] == "Names the document itself."
    assert "junk_flagged_present" in summary["flags"]
    assert summary["provenance"]["junk_judge"] == JUNK_JUDGE_PROMPT_VERSION

    rows = _findings(conn, project_id)
    assert len(rows) == 1
    assert rows[0].intervention == "coaching"
    assert len(judge.payloads) == 1
    assert judge.payloads[0]["findings"][0]["index"] == 0


def test_junk_judge_failure_fails_open_and_counts(conn: Connection) -> None:
    """A judge call failure never blocks extraction: the doc persists unfiltered."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc", chunk_content="Body.", chunk_id=cid,
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )
    backend = _FixedBackend([
        _record(intervention="coaching", outcome="attendance", quote="Body.", segment_id=str(cid)),
    ])

    summary, _ = _run_with_judge(
        conn, project_id, scope_id, sel_run,
        extraction_backend=backend, junk_judge_backend=_FailingJudgeBackend(),
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["docs"][0]["junk_flagged"] == 0
    assert summary["counts"]["junk_judge_failed"] == 1
    assert summary["junk_flagged"]["total"] == 0
    assert "junk_flagged_present" not in summary["flags"]
    rows = _findings(conn, project_id)
    assert len(rows) == 1


def test_junk_judge_coverage_violation_fails_open_and_counts(conn: Connection) -> None:
    """A coverage-violating response is a judge failure too — fail-open, not a crash."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc", chunk_content="Body.", chunk_id=cid,
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )
    backend = _FixedBackend([
        _record(intervention="coaching", outcome="attendance", quote="Body.", segment_id=str(cid)),
    ])

    summary, _ = _run_with_judge(
        conn, project_id, scope_id, sel_run,
        extraction_backend=backend, junk_judge_backend=_MismatchedJudgeBackend(),
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["counts"]["junk_judge_failed"] == 1
    rows = _findings(conn, project_id)
    assert len(rows) == 1


def test_no_backend_is_byte_identical_no_junk_keys(conn: Connection) -> None:
    """``junk_judge_backend=None`` (the default): no new keys anywhere, provenance is null."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc", chunk_content="Body.",
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert "junk_flagged" not in summary
    assert "junk_flagged" not in summary["docs"][0]
    assert "junk_judge_failed" not in summary["counts"]
    assert summary["provenance"]["junk_judge"] is None


def test_fingerprint_sensitive_to_junk_judge_presence() -> None:
    without = extraction_fingerprint("stub", junk_judge_active=False)[0]
    with_judge = extraction_fingerprint("stub", junk_judge_active=True)[0]
    assert without != with_judge
    assert without == extraction_fingerprint("stub")[0]  # default is off


# --- 5. Fake-client kwargs passthrough (OpenAI backend) -----------------------


@dataclass
class _FakeParsedMessage:
    parsed: Any


@dataclass
class _FakeChoice:
    message: _FakeParsedMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: None = None


class _FakeCompletions:
    def __init__(self, parsed: Any) -> None:
        self._parsed = parsed
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(choices=[_FakeChoice(message=_FakeParsedMessage(self._parsed))])


class _FakeChat:
    def __init__(self, parsed: Any) -> None:
        self.completions = _FakeCompletions(parsed)


class _FakeOpenAIClient:
    def __init__(self, parsed: Any) -> None:
        self.chat = _FakeChat(parsed)


def test_openai_junk_judge_backend_passes_model_and_reasoning_effort() -> None:
    response = JunkJudgeResponse(
        verdicts=[
            JunkVerdictWire(finding_index=0, verdict="sound", junk_class=None, reason="Fine."),
        ]
    )
    backend: OpenAIJunkJudgeBackend = object.__new__(OpenAIJunkJudgeBackend)
    fake_client = _FakeOpenAIClient(response)
    cast("Any", backend)._client = fake_client
    cast("Any", backend)._langfuse_client = None

    result, usage = backend.judge(
        {
            "findings": [
                {
                    "index": 0,
                    "intervention": "coaching",
                    "outcome": "attendance",
                    "effect_direction": "increase",
                    "estimate_level": "study",
                    "stratum_qualifiers": [],
                    "quotes": ["Coaching improved attendance"],
                }
            ]
        }
    )

    assert result.verdicts[0].verdict == "sound"
    assert usage is None
    [kwargs] = fake_client.chat.completions.calls
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["model"] == JUNK_JUDGE_MODEL
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["reasoning_effort"] == JUNK_JUDGE_REASONING_EFFORT
