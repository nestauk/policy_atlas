"""Tests for tracing helpers and executor context propagation."""

from __future__ import annotations

import contextvars
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any, cast

from policy_atlas import tracing
from policy_atlas.characterise import _CallBudget, _run_first_assignment_round
from policy_atlas.classify import _ClassifyDoc, _run_classification_calls
from policy_atlas.classify_prompt import ClassifyEnvelopePayload, ClassifyWire
from policy_atlas.extract import _Doc, _iof_profile, _run_windows
from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.extraction_records import ExtractionWindowPayload
from policy_atlas.grouping import GroupingDoc, Theme
from policy_atlas.implementation_context_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.ranking import RankedDoc
from policy_atlas.screen import _run_stage1_reps, _run_stage2_reps, _Stage1Doc
from policy_atlas.screen_prompt import (
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
)
from policy_atlas.select import SelectionCandidate, _rerank_infos, _SignalDoc
from policy_atlas.usage import TokenUsage, UsageResult

_WORKER_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "worker_context", default="missing"
)


def _read_context() -> str:
    return _WORKER_CONTEXT.get()


def test_submit_with_context_propagates_contextvar_into_worker() -> None:
    token = _WORKER_CONTEXT.set("parent-value")
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = tracing.submit_with_context(executor, _read_context)
            assert future.result() == "parent-value"
    finally:
        _WORKER_CONTEXT.reset(token)


class _ContextExtractionBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[Any]:
        del payload
        self.seen.append(_WORKER_CONTEXT.get())
        return SimpleNamespace(findings=[]), TokenUsage(prompt=1, completion=2, total=3)


def test_extract_window_fanout_propagates_context() -> None:
    backend = _ContextExtractionBackend()
    doc = _Doc(
        pss_id=uuid.uuid4(),
        text_basis="abstract_only",
        envelope_snapshot_id=uuid.uuid4(),
        full_text_snapshot_id=None,
        metadata={},
        primary_evidence_type=None,
        chunks=[],
        extractable=True,
        window_payloads=[
            ExtractionWindowPayload(
                pss_id="pss",
                window_index=0,
                title="Title",
                abstract="Abstract",
                primary_evidence_type=None,
                segments=[{"segment_id": "abstract", "content": "Abstract"}],
                metadata={},
            )
        ],
    )

    token = _WORKER_CONTEXT.set("extract-context")
    try:
        _run_windows([doc], profile=_iof_profile(backend, None))
    finally:
        _WORKER_CONTEXT.reset(token)

    assert backend.seen == ["extract-context"]


class _ScoreClient:
    def __init__(self) -> None:
        self.scores: dict[str, float] = {}

    def score_current_trace(
        self, *, name: str, value: float, data_type: str
    ) -> None:
        assert data_type == "NUMERIC"
        self.scores[name] = value


def test_extraction_score_summary_tolerates_old_flat_shape() -> None:
    client = _ScoreClient()

    tracing.extraction_score_summary(
        cast("Any", client),
        {
            "selection_run_id": "sel",
            "counts": {"selected": 2, "no_findings": 1, "failed": 0},
            "findings": {"total": 4, "quote_unverified": 1, "dedup_collapsed": 2},
        },
    )

    assert client.scores == {
        "quote_verified_share": 0.75,
        "no_findings_share": 0.5,
        "extraction_failure_count": 0.0,
        "dedup_collapsed_count": 2.0,
    }


def test_extraction_score_summary_reads_profile_shape() -> None:
    client = _ScoreClient()

    tracing.extraction_score_summary(
        cast("Any", client),
        {
            "selection_run_id": "sel",
            "counts": {
                "selected": 2,
                "basis": {},
                "profiles": {
                    IOF_PROFILE_ID: {
                        "no_findings": 1,
                        "failed": 0,
                        "findings": {
                            "total": 4,
                            "quote_unverified": 1,
                            "dedup_collapsed": 2,
                        },
                    },
                    ICF_PROFILE_ID: {
                        "no_findings": 0,
                        "failed": 1,
                        "findings": {
                            "total": 3,
                            "quote_unverified": 0,
                            "dedup_collapsed": 0,
                        },
                    },
                },
            },
        },
    )

    assert client.scores == {
        "quote_verified_share": 0.75,
        "no_findings_share": 0.5,
        "extraction_failure_count": 1.0,
        "dedup_collapsed_count": 2.0,
        "icf_findings_total": 3.0,
    }


class _ContextScreeningBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.stage1_seen: list[str] = []
        self.stage2_seen: list[str] = []

    def screen_envelope(
        self, payload: ScreenEnvelopePayload, *, rep_index: int = 0
    ) -> UsageResult[ScreenRepWire]:
        del payload, rep_index
        self.stage1_seen.append(_WORKER_CONTEXT.get())
        return ScreenRepWire(decision="relevant", confidence=0.8, reason="Relevant."), None

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        del payload
        self.stage2_seen.append(_WORKER_CONTEXT.get())
        return ScreenRepWire(decision="relevant", confidence=0.8, reason="Relevant."), None


def test_screening_fanouts_propagate_context() -> None:
    backend = _ContextScreeningBackend()
    stage1_doc = _Stage1Doc(
        pss_id=uuid.uuid4(),
        source_snapshot_id=uuid.uuid4(),
        metadata={},
        basis="title_abstract",
        payload=ScreenEnvelopePayload(
            pss_id="pss",
            title="Title",
            abstract="Abstract",
            abstract_source=None,
            intent="Intent",
        ),
    )
    stage2_payload = ScreenFullTextPayload(
        pss_id="pss",
        title="Title",
        intent="Intent",
        window_index=0,
        segments=[{"segment_id": "c1", "content": "Full text."}],
    )

    token = _WORKER_CONTEXT.set("screen-context")
    try:
        _run_stage1_reps([stage1_doc], screening_backend=backend)
        _run_stage2_reps({0: stage2_payload}, screening_backend=backend)
    finally:
        _WORKER_CONTEXT.reset(token)

    assert set(backend.stage1_seen) == {"screen-context"}
    assert backend.stage2_seen == ["screen-context"]


class _ContextClassificationBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def classify(self, payload: ClassifyEnvelopePayload) -> UsageResult[ClassifyWire]:
        del payload
        self.seen.append(_WORKER_CONTEXT.get())
        return (
            ClassifyWire(
                primary_evidence_type="Qualitative & Contextual Evidence",
                tags=[],
                confidence=0.8,
                reason="Context propagated.",
            ),
            None,
        )


def test_classify_fanout_propagates_context() -> None:
    backend = _ContextClassificationBackend()
    docs = [
        _ClassifyDoc(
            pss_id=uuid.uuid4(),
            source_snapshot_id=uuid.uuid4(),
            metadata={},
            payload=ClassifyEnvelopePayload(
                pss_id="pss",
                title="Title",
                abstract="Abstract",
                priors={},
                metadata={},
            ),
        )
    ]

    token = _WORKER_CONTEXT.set("classify-context")
    try:
        _run_classification_calls(docs, classification_backend=backend)
    finally:
        _WORKER_CONTEXT.reset(token)

    assert backend.seen == ["classify-context"]


class _ContextGroupingBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def discover(
        self,
        docs: list[GroupingDoc],
        *,
        intent: str,
        min_themes: int,
        max_themes: int,
    ) -> UsageResult[list[Theme]]:
        del docs, intent, min_themes, max_themes
        return [], None

    def assign(
        self, batch: list[GroupingDoc], *, themes: list[Theme]
    ) -> UsageResult[dict[str, str]]:
        self.seen.append(_WORKER_CONTEXT.get())
        return {doc["id"]: themes[0]["name"] for doc in batch}, None


def test_characterise_assignment_fanout_propagates_context() -> None:
    backend = _ContextGroupingBackend()
    batches: list[list[GroupingDoc]] = [
        [{"id": "a", "title": "A", "abstract": None}],
        [{"id": "b", "title": "B", "abstract": None}],
    ]
    themes: list[Theme] = [{"name": "Theme", "description": "A theme."}]

    token = _WORKER_CONTEXT.set("characterise-context")
    try:
        _run_first_assignment_round(
            backend=backend,
            batches=batches,
            themes=themes,
            budget=_CallBudget(maximum=2, coverage={}),
        )
    finally:
        _WORKER_CONTEXT.reset(token)

    assert backend.seen == ["characterise-context", "characterise-context"]


class _ContextRankingBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def rank(
        self, batch: list[GroupingDoc], *, intent: str
    ) -> UsageResult[list[RankedDoc]]:
        del intent
        self.seen.append(_WORKER_CONTEXT.get())
        return [
            {"doc_id": doc["id"], "score": 5, "reason": "Context propagated."}
            for doc in batch
        ], None


def _signal_doc(pss_id: uuid.UUID) -> _SignalDoc:
    from policy_atlas.characterise import ScreenedSource

    source = ScreenedSource(
        pss_id=pss_id,
        source_snapshot_id=uuid.uuid4(),
        full_text_snapshot_id=None,
        origin="upload",
        full_text_status="not_requested",
        full_text_error=None,
        metadata={"title": f"Doc {pss_id}"},
        source_locator="doc.txt",
        text_basis="abstract_only",
        screen_basis="title_abstract",
        screen_confidence=0.8,
        screen_stage=1,
        primary_evidence_type="Qualitative & Contextual Evidence",
        quality_score=None,
        rubric_version=None,
    )
    return _SignalDoc(
        candidate=SelectionCandidate(source=source, tags=()),
        signals={},
        missing_signals=[],
        composite=0.0,
        boost_multiplier=1.0,
    )


def test_select_rerank_fanout_propagates_context() -> None:
    backend = _ContextRankingBackend()
    contested_ids = [uuid.uuid4(), uuid.uuid4()]
    signal_docs = {pss_id: _signal_doc(pss_id) for pss_id in contested_ids}

    token = _WORKER_CONTEXT.set("select-context")
    try:
        _rerank_infos(
            contested_ids=contested_ids,
            signal_docs=signal_docs,
            ranking_backend=backend,
            intent="Intent",
        )
    finally:
        _WORKER_CONTEXT.reset(token)

    assert backend.seen == ["select-context"]
