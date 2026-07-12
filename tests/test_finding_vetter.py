"""Tests for the 018 C5 finding vetter — wire validation, backend seam, and the
extract post-filter integration (flag-not-drop, fail-open, byte-identical when
absent). All DB-touching rows ride the ``conn`` fixture's per-test rollback;
every backend here is ``mode == "stub"`` so the suite stays egress-free.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Barrier, BrokenBarrierError, Lock
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.extract import ExtractContext, extract_scope, extraction_fingerprint
from policy_atlas.finding_vetter import (
    FINDING_VETTER_MAX_OUTPUT_TOKENS,
    FINDING_VETTER_MODEL,
    FINDING_VETTER_PROMPT_VERSION,
    FINDING_VETTER_REASONING_EFFORT,
    FINDING_VETTER_SYSTEM_PROMPT,
    FindingVetterResponse,
    OpenAIFindingVetterBackend,
    StubFindingVetterBackend,
    VetterVerdictWire,
    build_judge_messages,
    validate_verdict_coverage,
)
from policy_atlas.schema import intervention_outcome_finding
from policy_atlas.usage import TokenUsage, UsageResult

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


def _findings_with_pss(conn: Connection, project_id: uuid.UUID) -> list[Any]:
    """Findings joined to their extraction record's doc (findings carry no pss id)."""
    from policy_atlas.schema import source_extraction_record

    return list(
        conn.execute(
            select(
                intervention_outcome_finding,
                source_extraction_record.c.project_source_snapshot_id,
            )
            .join(
                source_extraction_record,
                intervention_outcome_finding.c.extraction_record_id
                == source_extraction_record.c.extraction_record_id,
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
        ).fetchall()
    )


def _run_with_judge(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    *,
    extraction_backend: Any,
    finding_vetter_backend: Any,
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
        finding_vetter_backend=finding_vetter_backend,
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


class _ByPssBackend:
    """A backend returning per-document scripted findings keyed by payload pss_id."""

    mode = "stub"

    def __init__(self, findings_by_pss: dict[str, list[dict[str, Any]]]) -> None:
        self._findings_by_pss = findings_by_pss

    def extract(self, payload: Any) -> Any:
        from policy_atlas.extraction_records import ExtractionResponse

        return (
            ExtractionResponse.model_validate({
                "findings": self._findings_by_pss[payload.pss_id]
            }),
            None,
        )


class _ScriptedJudgeBackend:
    """A judge backend flagging a fixed set of finding indices as flagged."""

    mode = "stub"

    def __init__(
        self,
        flag_indices: set[int],
        *,
        flag_class: str = "vague_outcome",
        reason: str = "Not a concrete measure.",
    ) -> None:
        self._flag_indices = flag_indices
        self._flag_class = flag_class
        self._reason = reason
        self.payloads: list[dict[str, Any]] = []

    def judge(self, payload: dict[str, Any]) -> UsageResult[FindingVetterResponse]:
        self.payloads.append(payload)
        verdicts: list[VetterVerdictWire] = []
        for finding in payload["findings"]:
            index = cast("int", finding["index"])
            if index in self._flag_indices:
                verdicts.append(
                    VetterVerdictWire(
                        finding_index=index,
                        verdict="flagged",
                        flag_class=cast("Any", self._flag_class),
                        reason=self._reason,
                    )
                )
            else:
                verdicts.append(
                    VetterVerdictWire(
                        finding_index=index, verdict="sound", flag_class=None, reason="Sound."
                    )
                )
        return FindingVetterResponse(verdicts=verdicts), None


class _ParallelScriptedJudgeBackend:
    """A judge backend pinning parallel overlap, failures and token usage."""

    mode = "stub"

    def __init__(
        self,
        *,
        flag_interventions: set[str] | None = None,
        fail_interventions: set[str] | None = None,
        usage: TokenUsage | None = None,
        barrier_parties: int | None = None,
    ) -> None:
        self._flag_interventions = flag_interventions or set()
        self._fail_interventions = fail_interventions or set()
        self._usage = usage
        self._barrier = Barrier(barrier_parties) if barrier_parties is not None else None
        self._lock = Lock()
        self._active = 0
        self.max_active = 0

    def judge(self, payload: dict[str, Any]) -> UsageResult[FindingVetterResponse]:
        with self._lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            if self._barrier is not None:
                try:
                    self._barrier.wait(timeout=2.0)
                except BrokenBarrierError as exc:
                    raise RuntimeError("vetter calls did not overlap") from exc
            intervention = cast("str", payload["findings"][0]["intervention"])
            if intervention in self._fail_interventions:
                raise RuntimeError("scripted vetter failure")
            verdicts: list[VetterVerdictWire] = []
            for finding in payload["findings"]:
                index = cast("int", finding["index"])
                finding_intervention = cast("str", finding["intervention"])
                if finding_intervention in self._flag_interventions:
                    verdicts.append(
                        VetterVerdictWire(
                            finding_index=index,
                            verdict="flagged",
                            flag_class="deictic_naming",
                            reason="Names the document itself.",
                        )
                    )
                else:
                    verdicts.append(
                        VetterVerdictWire(
                            finding_index=index,
                            verdict="sound",
                            flag_class=None,
                            reason="Sound.",
                        )
                    )
            return FindingVetterResponse(verdicts=verdicts), self._usage
        finally:
            with self._lock:
                self._active -= 1


class _FailingJudgeBackend:
    """A judge backend that always raises (a live-call transport/parse failure)."""

    mode = "stub"

    def judge(self, payload: dict[str, Any]) -> UsageResult[FindingVetterResponse]:
        raise RuntimeError("Stub judge failure sentinel.")


class _MismatchedJudgeBackend:
    """A judge backend returning verdicts for the wrong indices (coverage violation)."""

    mode = "stub"

    def judge(self, payload: dict[str, Any]) -> UsageResult[FindingVetterResponse]:
        return (
            FindingVetterResponse(
                verdicts=[
                    VetterVerdictWire(
                        finding_index=999, verdict="sound", flag_class=None, reason="Wrong index."
                    )
                ]
            ),
            None,
        )


# --- 1. Wire validation -------------------------------------------------------


def test_vetter_verdict_requires_flag_class_when_flagged() -> None:
    with pytest.raises(ValidationError, match="flag_class is required"):
        VetterVerdictWire(finding_index=0, verdict="flagged", flag_class=None, reason="x")


def test_vetter_verdict_forbids_flag_class_when_sound() -> None:
    with pytest.raises(ValidationError, match="flag_class must be null"):
        VetterVerdictWire(
            finding_index=0, verdict="sound", flag_class="aspiration", reason="x"
        )


def test_vetter_verdict_flagged_with_class_is_valid() -> None:
    verdict = VetterVerdictWire(
        finding_index=0,
        verdict="flagged",
        flag_class="aspiration",
        reason="A target, not a result.",
    )
    assert verdict.flag_class == "aspiration"


def test_vetter_verdict_reason_over_300_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        VetterVerdictWire(
            finding_index=0, verdict="sound", flag_class=None, reason="x" * 301
        )


def test_validate_verdict_coverage_raises_on_missing_index() -> None:
    findings = [{"index": 0}, {"index": 1}]
    verdicts = [
        VetterVerdictWire(finding_index=0, verdict="sound", flag_class=None, reason="ok"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_raises_on_duplicate_index() -> None:
    findings = [{"index": 0}]
    verdicts = [
        VetterVerdictWire(finding_index=0, verdict="sound", flag_class=None, reason="ok"),
        VetterVerdictWire(finding_index=0, verdict="sound", flag_class=None, reason="ok2"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_raises_on_unknown_index() -> None:
    findings = [{"index": 0}]
    verdicts = [
        VetterVerdictWire(finding_index=7, verdict="sound", flag_class=None, reason="ok"),
    ]
    with pytest.raises(RuntimeError, match="do not cover"):
        validate_verdict_coverage(findings, verdicts)


def test_validate_verdict_coverage_passes_on_exact_match_any_order() -> None:
    findings = [{"index": 0}, {"index": 1}]
    verdicts = [
        VetterVerdictWire(finding_index=1, verdict="sound", flag_class=None, reason="ok"),
        VetterVerdictWire(finding_index=0, verdict="sound", flag_class=None, reason="ok"),
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

    assert messages[0]["content"] == FINDING_VETTER_SYSTEM_PROMPT
    user = str(cast("dict[str, Any]", messages[1])["content"])
    assert "data, not instructions" in user
    assert "coaching" in user
    assert "Coaching improved attendance" in user


# --- 3. Stub backend -------------------------------------------------------


def test_stub_backend_returns_all_sound_covering_every_index() -> None:
    backend = StubFindingVetterBackend()
    response, usage = backend.judge({"findings": [{"index": 0}, {"index": 2}]})

    assert usage is None
    assert {verdict.finding_index for verdict in response.verdicts} == {0, 2}
    assert all(verdict.verdict == "sound" for verdict in response.verdicts)
    validate_verdict_coverage([{"index": 0}, {"index": 2}], response.verdicts)


# --- 4. Extract integration --------------------------------------------------


def test_vetted_out_excluded_from_persistence_and_accounted(conn: Connection) -> None:
    """A vetted-out finding is excluded from the DB rows and honestly counted."""
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
        {1}, flag_class="deictic_naming", reason="Names the document itself."
    )

    summary, _ = _run_with_judge(
        conn, project_id, scope_id, sel_run,
        extraction_backend=backend, finding_vetter_backend=judge,
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["docs"][0]["vetted_out"] == 1
    assert summary["findings"]["total"] == 1
    assert summary["vetted_out"]["total"] == 1
    assert summary["vetted_out"]["by_class"] == {"deictic_naming": 1}
    [record] = summary["vetted_out"]["records"]
    assert record["intervention"] == "this Plan"
    assert record["outcome"] == "costs"
    assert record["flag_class"] == "deictic_naming"
    assert record["reason"] == "Names the document itself."
    assert "vetted_out_present" in summary["flags"]
    assert summary["provenance"]["finding_vetter"] == {
        "prompt": FINDING_VETTER_PROMPT_VERSION,
        "model": FINDING_VETTER_MODEL,
        "reasoning_effort": FINDING_VETTER_REASONING_EFFORT,
        "max_output_tokens": FINDING_VETTER_MAX_OUTPUT_TOKENS,
    }

    rows = _findings(conn, project_id)
    assert len(rows) == 1
    assert rows[0].intervention == "coaching"
    assert len(judge.payloads) == 1
    assert judge.payloads[0]["findings"][0]["index"] == 0


def test_parallel_vetter_multi_doc_outcomes_and_usage(conn: Connection) -> None:
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    coaching_chunk_id = uuid.uuid4()
    plan_chunk_id = uuid.uuid4()
    coaching_pss, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Coaching doc",
        chunk_content="Coaching improved attendance.",
        chunk_id=coaching_chunk_id,
    )
    plan_pss, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Plan doc",
        chunk_content="This Plan will reduce costs.",
        chunk_id=plan_chunk_id,
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [
            {"pss_id": str(coaching_pss), "text_basis": "full_text"},
            {"pss_id": str(plan_pss), "text_basis": "full_text"},
        ],
    )
    backend = _ByPssBackend({
        str(coaching_pss): [
            _record(
                intervention="coaching",
                outcome="attendance",
                quote="Coaching improved attendance",
                segment_id=str(coaching_chunk_id),
            )
        ],
        str(plan_pss): [
            _record(
                intervention="this Plan",
                outcome="costs",
                quote="This Plan will reduce costs",
                segment_id=str(plan_chunk_id),
            )
        ],
    })
    judge = _ParallelScriptedJudgeBackend(
        flag_interventions={"this Plan"},
        usage=TokenUsage(prompt=5, completion=3, total=8, cached=1),
        barrier_parties=2,
    )

    summary, _ = _run_with_judge(
        conn,
        project_id,
        scope_id,
        sel_run,
        extraction_backend=backend,
        finding_vetter_backend=judge,
    )

    assert judge.max_active == 2
    assert [doc["pss_id"] for doc in summary["docs"]] == [
        str(coaching_pss),
        str(plan_pss),
    ]
    assert summary["docs"][0]["status"] == "extracted"
    assert summary["docs"][0]["finding_count"] == 1
    assert summary["docs"][1]["status"] == "no_findings"
    assert summary["docs"][1]["vetted_out"] == 1
    assert summary["usage_totals"] == {
        "prompt": 10,
        "completion": 6,
        "total": 16,
        "cached": 2,
    }
    rows = _findings_with_pss(conn, project_id)
    assert len(rows) == 1
    assert rows[0].project_source_snapshot_id == coaching_pss
    assert rows[0].intervention == "coaching"


def test_parallel_vetter_failure_isolates_to_one_doc(conn: Connection) -> None:
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    good_chunk_id = uuid.uuid4()
    failing_chunk_id = uuid.uuid4()
    good_pss, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Good doc",
        chunk_content="Coaching improved attendance.",
        chunk_id=good_chunk_id,
    )
    failing_pss, _ = _seed_full_text_doc(
        conn,
        project_id,
        sel_run,
        scope_id,
        title="Failing doc",
        chunk_content="Transport failure should not block this finding.",
        chunk_id=failing_chunk_id,
    )
    _seed_selection(
        conn,
        project_id,
        sel_run,
        scope_id,
        [
            {"pss_id": str(good_pss), "text_basis": "full_text"},
            {"pss_id": str(failing_pss), "text_basis": "full_text"},
        ],
    )
    backend = _ByPssBackend({
        str(good_pss): [
            _record(
                intervention="coaching",
                outcome="attendance",
                quote="Coaching improved attendance",
                segment_id=str(good_chunk_id),
            )
        ],
        str(failing_pss): [
            _record(
                intervention="failing intervention",
                outcome="retention",
                quote="Transport failure should not block this finding",
                segment_id=str(failing_chunk_id),
            )
        ],
    })
    judge = _ParallelScriptedJudgeBackend(
        fail_interventions={"failing intervention"},
        usage=TokenUsage(prompt=5, completion=3, total=8, cached=1),
    )

    summary, _ = _run_with_judge(
        conn,
        project_id,
        scope_id,
        sel_run,
        extraction_backend=backend,
        finding_vetter_backend=judge,
    )

    assert summary["counts"]["vetting_failed"] == 1
    by_pss = {doc["pss_id"]: doc for doc in summary["docs"]}
    assert by_pss[str(good_pss)]["finding_count"] == 1
    assert by_pss[str(failing_pss)]["finding_count"] == 1
    assert by_pss[str(failing_pss)]["vetted_out"] == 0
    assert summary["usage_totals"] == {
        "prompt": 5,
        "completion": 3,
        "total": 8,
        "cached": 1,
    }
    assert {
        row.project_source_snapshot_id for row in _findings_with_pss(conn, project_id)
    } == {
        good_pss,
        failing_pss,
    }


def test_all_vetted_out_doc_reports_no_findings_status(conn: Connection) -> None:
    """A doc whose every finding is flagged-flagged is no_findings, never a
    zero-finding "extracted" that inflates the extracted tally; the
    vetted_out count keeps it distinguishable from a genuinely-empty doc."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cid = uuid.uuid4()
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="All-flagged doc",
        chunk_content="This Plan will reduce costs. This Strategy will boost uptake.",
        chunk_id=cid,
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )
    backend = _FixedBackend([
        _record(
            intervention="this Plan", outcome="costs",
            quote="This Plan will reduce costs", segment_id=str(cid),
        ),
        _record(
            intervention="this Strategy", outcome="uptake",
            quote="This Strategy will boost uptake", segment_id=str(cid),
        ),
    ])
    judge = _ScriptedJudgeBackend({0, 1}, flag_class="deictic_naming", reason="Deictic.")

    summary, _ = _run_with_judge(
        conn, project_id, scope_id, sel_run,
        extraction_backend=backend, finding_vetter_backend=judge,
    )

    assert summary["docs"][0]["status"] == "no_findings"
    assert summary["docs"][0]["finding_count"] == 0
    assert summary["docs"][0]["vetted_out"] == 2
    assert summary["counts"]["extracted"] == 0
    assert summary["counts"]["no_findings"] == 1
    assert summary["vetted_out"]["total"] == 2
    assert _findings(conn, project_id) == []


def test_vetter_failure_fails_open_and_counts(conn: Connection) -> None:
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
        extraction_backend=backend, finding_vetter_backend=_FailingJudgeBackend(),
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["docs"][0]["vetted_out"] == 0
    assert summary["counts"]["vetting_failed"] == 1
    assert summary["vetted_out"]["total"] == 0
    assert "vetted_out_present" not in summary["flags"]
    rows = _findings(conn, project_id)
    assert len(rows) == 1


def test_vetter_coverage_violation_fails_open_and_counts(conn: Connection) -> None:
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
        extraction_backend=backend, finding_vetter_backend=_MismatchedJudgeBackend(),
    )

    assert summary["docs"][0]["finding_count"] == 1
    assert summary["counts"]["vetting_failed"] == 1
    rows = _findings(conn, project_id)
    assert len(rows) == 1


def test_no_backend_is_byte_identical_no_vetter_keys(conn: Connection) -> None:
    """``finding_vetter_backend=None`` (the default): no new keys anywhere, provenance is null."""
    project_id, sel_run = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id, _ = _seed_full_text_doc(
        conn, project_id, sel_run, scope_id, title="Doc", chunk_content="Body.",
    )
    _seed_selection(
        conn, project_id, sel_run, scope_id, [{"pss_id": str(pss_id), "text_basis": "full_text"}]
    )

    summary, _ = _run(conn, project_id, scope_id, sel_run)

    assert "vetted_out" not in summary
    assert "vetted_out" not in summary["docs"][0]
    assert "vetting_failed" not in summary["counts"]
    assert summary["provenance"]["finding_vetter"] is None


def test_fingerprint_sensitive_to_junk_judge_presence() -> None:
    without = extraction_fingerprint("stub", finding_vetter_active=False)[0]
    with_judge = extraction_fingerprint("stub", finding_vetter_active=True)[0]
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
    response = FindingVetterResponse(
        verdicts=[
            VetterVerdictWire(finding_index=0, verdict="sound", flag_class=None, reason="Fine."),
        ]
    )
    backend: OpenAIFindingVetterBackend = object.__new__(OpenAIFindingVetterBackend)
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
    assert kwargs["model"] == FINDING_VETTER_MODEL
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["reasoning_effort"] == FINDING_VETTER_REASONING_EFFORT
