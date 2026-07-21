"""Pure unit tests for icf_rules_v2 validation and dedup."""

from __future__ import annotations

import pytest

from policy_atlas.evidence_base.extract.icf_records import ICFRecord
from policy_atlas.evidence_base.extract.iof_records import IOFAnchorWire
from policy_atlas.evidence_base.extract.quote_verify import (
    ICF_FIELD_RULES_VERSION,
    dedup_icf_records,
    icf_claim_key,
    validate_icf_record,
)
from tests.helpers import make_icf_wire_record


def _record(**overrides: object) -> ICFRecord:
    result = validate_icf_record(make_icf_wire_record(**overrides))
    assert result.record is not None
    return result.record


def test_version_constant() -> None:
    assert ICF_FIELD_RULES_VERSION == "icf_rules_v2"


def test_icf_coercion_and_non_valid_only_coverage() -> None:
    result = validate_icf_record(
        make_icf_wire_record(
            outcome=None,
            population="N/A",
            setting="primary care",
            resource_requirements=None,
        )
    )

    assert result.record is not None
    assert result.record.population is None
    assert result.record.setting == "primary care"
    assert result.field_coverage["population"] == "not_extracted"
    assert result.field_coverage["outcome"] == "not_extracted"
    assert result.field_coverage["resource_requirements"] == "not_extracted"
    assert "setting" not in result.field_coverage
    assert result.coerced_null_fields == ["population"]


@pytest.mark.parametrize("token", ["n/a", "none", ""])
def test_context_label_null_like_strings_coerce_to_not_extracted(token: str) -> None:
    result = validate_icf_record(make_icf_wire_record(context_label=token))

    assert result.record is not None
    assert result.record.context_label is None
    assert result.field_coverage["context_label"] == "not_extracted"
    assert result.coerced_null_fields == ["context_label"]


def test_context_label_round_trips_to_stored_record() -> None:
    result = validate_icf_record(
        make_icf_wire_record(context_label="Caseload pressure")
    )

    assert result.record is not None
    assert result.record.context_label == "Caseload pressure"
    assert "context_label" not in result.field_coverage


@pytest.mark.parametrize(
    "overrides",
    [
        {"intervention": "N/A"},
        {"claim": "unknown"},
        {"anchors": []},
    ],
)
def test_icf_grain_gate_invalidates_missing_required_grain(
    overrides: dict[str, object]
) -> None:
    result = validate_icf_record(make_icf_wire_record(**overrides))

    assert result.grain_invalid is True
    assert result.record is None


def test_icf_dedup_metadata_twins_collapse_anchors_merge_first_wins() -> None:
    r1 = _record(
        outcome="referral uptake",
        setting="primary care",
        anchors=[IOFAnchorWire(segment_id="s1", quote="quote one")],
    )
    r2 = _record(
        outcome="attendance",
        setting="secondary schools",
        anchors=[IOFAnchorWire(segment_id="s2", quote="quote two")],
    )

    assert icf_claim_key(r1) == icf_claim_key(r2)
    deduped, collapsed = dedup_icf_records([r1, r2])

    assert collapsed == 1
    assert len(deduped) == 1
    assert deduped[0].outcome == "referral uptake"
    assert deduped[0].setting == "primary care"
    assert [anchor.quote for anchor in deduped[0].anchors] == ["quote one", "quote two"]


def test_icf_dedup_context_label_is_not_identity() -> None:
    r1 = _record(
        context_label="Caseload pressure",
        anchors=[IOFAnchorWire(segment_id="s1", quote="quote one")],
    )
    r2 = _record(
        context_label="Staff capacity",
        anchors=[IOFAnchorWire(segment_id="s2", quote="quote two")],
    )

    assert icf_claim_key(r1) == icf_claim_key(r2)
    deduped, collapsed = dedup_icf_records([r1, r2])

    assert collapsed == 1
    assert len(deduped) == 1
    assert deduped[0].context_label == "Caseload pressure"
    assert [anchor.quote for anchor in deduped[0].anchors] == ["quote one", "quote two"]


def test_icf_dedup_differing_context_type_does_not_collapse() -> None:
    r1 = _record(context_type="barrier")
    r2 = _record(context_type="enabler")

    deduped, collapsed = dedup_icf_records([r1, r2])

    assert collapsed == 0
    assert len(deduped) == 2


def test_icf_dedup_study_vs_pooled_claim_level_does_not_collapse() -> None:
    r1 = _record(claim_level="study")
    r2 = _record(claim_level="pooled")

    deduped, collapsed = dedup_icf_records([r1, r2])

    assert collapsed == 0
    assert len(deduped) == 2
