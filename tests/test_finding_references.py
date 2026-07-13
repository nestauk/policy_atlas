"""Cross-schema drift guards for shared finding reference fields."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Text

from policy_atlas.extraction_records import (
    IOFAnchor,
    IOFAnchorWire,
    IOFRecord,
    IOFRecordWire,
    IOFStatistics,
    IOFStatisticsWire,
)
from policy_atlas.finding_references import (
    INTERVENTION_DESC,
    POPULATION_DESC,
    REFERENCE_REQUIREDNESS,
    SHARED_REFERENCE_FIELDS,
    STUDY_DESIGN_DESC,
    STUDY_GEOGRAPHY_DESC,
)
from policy_atlas.implementation_context_records import ICFRecord, ICFRecordWire
from policy_atlas.quote_verify import NULL_LIKE_STRINGS, validate_icf_record, validate_record
from policy_atlas.schema import implementation_context_finding, intervention_outcome_finding
from tests.helpers import make_icf_wire_record


def _iof_wire_with_population(population: str | None) -> IOFRecordWire:
    return IOFRecordWire(
        intervention="home visiting",
        outcome="hospital admissions",
        population=population,
        setting=None,
        comparator="usual care",
        effect_direction="decrease",
        estimate_level="study",
        study_design=None,
        study_geography=None,
        stratum_qualifiers=[],
        statistics=IOFStatisticsWire(
            effect_size=None,
            effect_size_type=None,
            ci_lower=None,
            ci_upper=None,
            standard_error=None,
            p_value=None,
            n=None,
            k=None,
            i_squared=None,
            tau2=None,
        ),
        causality_by_design=None,
        effect_basis=None,
        is_primary=None,
        is_prevalence_only=None,
        anchors=[IOFAnchorWire(segment_id="s1", quote="home visiting reduced admissions")],
    )


def _iof_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "intervention": "home visiting",
        "outcome": "hospital admissions",
        "population": "families",
        "setting": "primary care",
        "comparator": None,
        "effect_direction": "decrease",
        "estimate_level": "study",
        "study_design": "RCT",
        "study_geography": "England",
        "stratum_qualifiers": [],
        "statistics": IOFStatistics(),
        "causality_by_design": None,
        "effect_basis": None,
        "is_primary": None,
        "is_prevalence_only": None,
        "anchors": [IOFAnchor(segment_id="s1", quote="quote")],
    }
    values.update(overrides)
    return values


def _icf_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "context_type": "barrier",
        "claim": "Training gaps slowed delivery.",
        "intervention": "home visiting",
        "outcome": "referral uptake",
        "population": "families",
        "setting": "primary care",
        "study_geography": "England",
        "study_design": "process evaluation",
        "claim_level": "study",
        "claim_basis": "studied",
        "level": "provider",
        "resource_requirements": None,
        "workforce_requirements": "staff training",
        "anchors": [IOFAnchor(segment_id="s1", quote="quote")],
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("field_name", "constant"),
    [
        ("intervention", INTERVENTION_DESC),
        ("population", POPULATION_DESC),
        ("study_geography", STUDY_GEOGRAPHY_DESC),
        ("study_design", STUDY_DESIGN_DESC),
    ],
)
def test_shared_reference_descriptions_are_byte_identical(
    field_name: str, constant: str
) -> None:
    iof_description = IOFRecordWire.model_fields[field_name].description
    icf_description = ICFRecordWire.model_fields[field_name].description

    assert iof_description == constant
    assert icf_description == constant
    assert iof_description == icf_description


@pytest.mark.parametrize("field_name", SHARED_REFERENCE_FIELDS)
def test_shared_reference_columns_are_text_with_pinned_nullability(field_name: str) -> None:
    for schema_name, table in (
        ("iof", intervention_outcome_finding),
        ("icf", implementation_context_finding),
    ):
        column = table.c[field_name]
        assert isinstance(column.type, Text)
        assert column.nullable is (not REFERENCE_REQUIREDNESS[field_name][schema_name])


@pytest.mark.parametrize("field_name", SHARED_REFERENCE_FIELDS)
def test_stored_model_reference_nullability_matches_tables(field_name: str) -> None:
    for schema_name, model, values_factory in (
        ("iof", IOFRecord, _iof_values),
        ("icf", ICFRecord, _icf_values),
    ):
        required = REFERENCE_REQUIREDNESS[field_name][schema_name]
        values = values_factory(**{field_name: None})
        if required:
            with pytest.raises(ValidationError):
                model.model_validate(values)
        else:
            record = model.model_validate(values)
            assert getattr(record, field_name) is None


@pytest.mark.parametrize("token", sorted(NULL_LIKE_STRINGS))
def test_reference_null_like_coercion_uses_shared_rules(token: str) -> None:
    iof = validate_record(_iof_wire_with_population(token))
    icf = validate_icf_record(make_icf_wire_record(population=token))

    assert iof.record is not None
    assert icf.record is not None
    assert iof.record.population is None
    assert icf.record.population is None
    assert iof.field_coverage["population"] == "not_extracted"
    assert icf.field_coverage["population"] == "not_extracted"
    assert iof.coerced_null_fields == ["population"]
    assert icf.coerced_null_fields == ["population"]
