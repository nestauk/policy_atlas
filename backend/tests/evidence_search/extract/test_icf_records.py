"""Unit tests for ICF record models and generated field docs."""

from __future__ import annotations

from typing import get_args

from policy_atlas.core.schema import CLAIM_BASES, CLAIM_LEVELS, CONTEXT_LEVELS, CONTEXT_TYPES
from policy_atlas.evidence_search.extract.icf_records import (
    PROFILE_ID,
    SCHEMA_VERSION,
    ClaimBasis,
    ClaimLevel,
    ContextLevel,
    ContextType,
    ICFExtractionResponse,
    ICFRecordWire,
    render_field_docs,
)
from policy_atlas.evidence_search.extract.iof_records import IOFAnchorWire
from policy_atlas.evidence_search.extract.quote_verify import validate_icf_record
from tests.helpers import make_icf_wire_record


def test_version_constants() -> None:
    assert PROFILE_ID == "eb_icf_base_v1"
    assert SCHEMA_VERSION == "icf_v2"


def test_literal_vocabularies_match_schema_checks() -> None:
    assert get_args(ContextType) == CONTEXT_TYPES
    assert get_args(ClaimLevel) == CLAIM_LEVELS
    assert get_args(ClaimBasis) == CLAIM_BASES
    assert get_args(ContextLevel) == CONTEXT_LEVELS


def test_wire_to_stored_round_trip() -> None:
    wire = make_icf_wire_record(
        context_type="mechanism",
        claim="The visits built trust, which helped families take up referrals.",
        context_label="Trusted relationships",
        outcome="referral uptake",
        claim_level="pooled",
        claim_basis="studied",
        level="recipient",
    )

    result = validate_icf_record(wire)

    assert result.record is not None
    assert result.record.context_type == "mechanism"
    assert result.record.context_label == "Trusted relationships"
    assert result.record.claim_level == "pooled"
    assert result.record.claim_basis == "studied"
    assert result.record.outcome == "referral uptake"
    assert result.record.anchors[0].quote == wire.anchors[0].quote
    assert result.grain_invalid is False


def test_render_field_docs_contains_every_wire_field() -> None:
    docs = render_field_docs()
    for field_name in ICFRecordWire.model_fields:
        assert f"- {field_name}:" in docs
    for field_name in IOFAnchorWire.model_fields:
        assert f"- {field_name}:" in docs


def test_response_accepts_empty_findings_list() -> None:
    response = ICFExtractionResponse(findings=[])

    assert response.findings == []
