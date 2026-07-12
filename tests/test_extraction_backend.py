"""Tests for the extraction backend seam."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from policy_atlas.extraction_backend import (
    ExtractionBackend,
    OpenAIExtractionBackend,
    StubExtractionBackend,
)
from policy_atlas.extraction_records import (
    ExtractionWindowPayload,
    IOFAnchorWire,
    IOFRecordWire,
    IOFStatisticsWire,
)


def _valid_wire_record() -> dict[str, Any]:
    return IOFRecordWire(
        intervention="structured home-visiting programmes",
        outcome="unplanned child hospital admissions",
        population=None,
        comparator="usual care",
        effect_direction="decrease",
        estimate_level="pooled",
        study_design="pooled analysis of randomised trials",
        study_geography=None,
        stratum_qualifiers=[],
        statistics=IOFStatisticsWire(
            effect_size=0.82,
            effect_size_type="pooled risk ratio",
            ci_lower=0.71,
            ci_upper=0.94,
            standard_error=None,
            p_value=None,
            n=4213,
            k=12,
            i_squared=41.0,
            tau2=None,
        ),
        causality_by_design="attributable",
        effect_basis=None,
        is_primary=True,
        is_prevalence_only=False,
        anchors=[
            IOFAnchorWire(
                segment_id="s1",
                quote="structured home-visiting programmes reduced unplanned admissions",
            )
        ],
    ).model_dump()


def _payload(
    window_index: int = 0, metadata: dict[str, Any] | None = None
) -> ExtractionWindowPayload:
    return ExtractionWindowPayload(
        pss_id="doc-0000000000000000",
        window_index=window_index,
        title="T",
        abstract="A",
        primary_evidence_type=None,
        segments=[{"segment_id": "s1", "content": "text"}],
        metadata=metadata or {},
    )


def test_stub_backend_satisfies_protocol() -> None:
    backend: ExtractionBackend = StubExtractionBackend()
    assert backend.mode == "stub"


def test_openai_backend_satisfies_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend: ExtractionBackend = OpenAIExtractionBackend(api_key="sk-test")
    assert backend.mode == "live"


def test_openai_extraction_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIExtractionBackend()


def test_stub_determinism() -> None:
    backend = StubExtractionBackend()
    payload = _payload(metadata={"_stub_iof": [_valid_wire_record()]})

    first, first_usage = backend.extract(payload)
    second, second_usage = backend.extract(payload)

    assert first_usage is None
    assert second_usage is None
    assert [f.model_dump() for f in first.findings] == [f.model_dump() for f in second.findings]


def test_no_sentinel_returns_empty_findings() -> None:
    backend = StubExtractionBackend()
    payload = _payload(metadata={})

    result, usage = backend.extract(payload)

    assert usage is None
    assert result.findings == []


def test_stub_extract_failed_sentinel_raises() -> None:
    backend = StubExtractionBackend()
    payload = _payload(metadata={"_stub_extract_failed": True})

    with pytest.raises(RuntimeError, match="Stub extraction failure sentinel."):
        backend.extract(payload)


def test_stub_iof_sentinel_only_on_window_zero() -> None:
    backend = StubExtractionBackend()
    record = _valid_wire_record()

    window_zero, zero_usage = backend.extract(
        _payload(window_index=0, metadata={"_stub_iof": [record]})
    )
    window_one, one_usage = backend.extract(
        _payload(window_index=1, metadata={"_stub_iof": [record]})
    )

    assert zero_usage is None
    assert one_usage is None
    assert [f.model_dump() for f in window_zero.findings] == [record]
    assert window_one.findings == []


def test_stub_iof_windows_sentinel_routes_per_window_index() -> None:
    backend = StubExtractionBackend()
    record_zero = _valid_wire_record()
    record_one = _valid_wire_record()
    record_one["intervention"] = "a different intervention"
    metadata = {"_stub_iof_windows": {"0": [record_zero], "1": [record_one]}}

    window_zero, zero_usage = backend.extract(_payload(window_index=0, metadata=metadata))
    window_one, one_usage = backend.extract(_payload(window_index=1, metadata=metadata))
    window_two, two_usage = backend.extract(_payload(window_index=2, metadata=metadata))

    assert zero_usage is None
    assert one_usage is None
    assert two_usage is None
    assert [f.model_dump() for f in window_zero.findings] == [record_zero]
    assert [f.model_dump() for f in window_one.findings] == [record_one]
    assert window_two.findings == []


def test_malformed_sentinel_raises_validation_error() -> None:
    backend = StubExtractionBackend()
    malformed_record = _valid_wire_record()
    del malformed_record["intervention"]
    payload = _payload(metadata={"_stub_iof": [malformed_record]})

    with pytest.raises(ValidationError):
        backend.extract(payload)


def test_mode_strings() -> None:
    assert StubExtractionBackend().mode == "stub"
    assert OpenAIExtractionBackend(api_key="sk-test").mode == "live"
