"""IOF record models — the wire/stored split (task 011, contract decision 3).

The wire models drive the OpenAI structured-output schema *and* generate the
prompt's field documentation — one source of truth, so prompt/schema drift is
structurally impossible (V2 silently discarded three requested fields that way).
Wire grain fields are nullable and numerics string-tolerant so that null-like
strings and unparseable values arrive intact for iof_rules_v3 to coerce and
flag, instead of being silently rejected or model-conformed at the API boundary.
The stored models are the final typed shape after grain validation + field rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict, get_args

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.finding_references import (
    INTERVENTION_DESC,
    POPULATION_DESC,
    STUDY_DESIGN_DESC,
    STUDY_GEOGRAPHY_DESC,
    render_field_sections,
)
from policy_atlas.schema import (
    CAUSALITY_BY_DESIGN,
    EFFECT_BASES,
    EFFECT_DIRECTIONS,
    ESTIMATE_LEVELS,
)

# Fingerprint components (contract decision 2): named constants; any
# output-affecting change bumps a version and thus the extraction fingerprint.
# PROFILE_ID is a stable requirement-family id ("EB's base IOF extraction");
# field-set evolution rides the schema/prompt/rules version components, which
# enter the fingerprint and recorded components map, so field additions do not
# bump the profile.
PROFILE_ID = "eb_iof_base_v1"
SCHEMA_VERSION = "iof_v3"  # covers the wire AND stored model layers

# The segment id carried by an abstract-basis payload; anchors naming it map to
# chunk_id null at write (contract decision 4, abstract-envelope location).
ABSTRACT_SEGMENT_ID = "abstract"

EffectDirection = Literal["increase", "decrease", "no_effect", "mixed", "unclear"]
EffectBasis = Literal["observed", "modelled"]
EstimateLevel = Literal["study", "pooled", "claim"]
CausalityByDesign = Literal["attributable", "plausibly_causal", "associational", "descriptive"]
StratumType = Literal["timepoint", "subgroup", "setting"]

STRATUM_TYPES: tuple[str, ...] = get_args(StratumType)

# The Literal types are the schema CHECK vocabularies — drift fails at import.
assert get_args(EffectDirection) == EFFECT_DIRECTIONS
assert get_args(EffectBasis) == EFFECT_BASES
assert get_args(EstimateLevel) == ESTIMATE_LEVELS
assert get_args(CausalityByDesign) == CAUSALITY_BY_DESIGN


# --- Wire models (drive response_format + prompt field docs) ---


class IOFStratumWire(BaseModel):
    """One stratum qualifier scoping a finding."""

    model_config = ConfigDict(extra="forbid")

    type: StratumType = Field(
        description="The qualifier kind: 'timepoint', 'subgroup' or 'setting'."
    )
    value: str = Field(
        description=(
            "The qualifier value exactly as the document states it "
            "(e.g. '12 months', 'girls', 'primary schools')."
        )
    )


class IOFStatisticsWire(BaseModel):
    """The reported statistics bundle — reported values only."""

    model_config = ConfigDict(extra="forbid")

    effect_size: float | str | None = Field(
        description="The reported effect size value, or null if not reported."
    )
    effect_size_type: str | None = Field(
        description=(
            "What the effect size is, as reported (e.g. 'odds ratio', 'pooled risk "
            "ratio', 'standardised mean difference'), or null if not reported."
        )
    )
    ci_lower: float | str | None = Field(
        description="Lower bound of the reported confidence interval, or null."
    )
    ci_upper: float | str | None = Field(
        description="Upper bound of the reported confidence interval, or null."
    )
    standard_error: float | str | None = Field(
        description="The reported standard error, or null."
    )
    p_value: float | str | None = Field(description="The reported p-value, or null.")
    n: int | str | None = Field(
        description="The reported total sample size N, or null."
    )
    k: int | str | None = Field(
        description="The reported number of pooled studies k, or null."
    )
    i_squared: float | str | None = Field(
        description="The reported I-squared heterogeneity percentage, or null."
    )
    tau2: float | str | None = Field(
        description="The reported tau-squared between-study variance, or null."
    )


class IOFAnchorWire(BaseModel):
    """One grounding anchor: a verbatim supporting quote and where it lives."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str | None = Field(
        description=(
            "The id of the segment the quote is copied from, exactly as given in "
            "the input segment records. Always name the segment you quoted."
        )
    )
    quote: str = Field(
        description=(
            "Exact verbatim text copied from the named segment — never paraphrased, "
            "never stitched together from separate places."
        )
    )


class IOFRecordWire(BaseModel):
    """One intervention–outcome finding as emitted by the model."""

    model_config = ConfigDict(extra="forbid")

    intervention: str | None = Field(
        description=INTERVENTION_DESC
    )
    outcome: str | None = Field(
        description=(
            "The outcome as the base measure only, exactly as the document names it "
            "(e.g. 'BMI', never 'BMI at 12 months'). Timepoint, subgroup and setting "
            "belong in stratum_qualifiers."
        )
    )
    population: str | None = Field(
        description=POPULATION_DESC
    )
    setting: str | None = Field(
        description=(
            "The setting where the intervention underlying this finding was "
            "delivered, exactly as the document reports it (e.g. 'primary care', "
            "'secondary schools'), or null if not reported. Use the delivery setting, "
            "not the mandating institution. A setting-scoped subgroup estimate belongs "
            "in stratum_qualifiers; this field records where the underlying evidence "
            "was conducted — they can coexist."
        )
    )
    comparator: str | None = Field(
        description=(
            "What the effect is measured against (control, usual care, another arm), "
            "exactly as the document names it, or null if not reported."
        )
    )
    effect_direction: EffectDirection = Field(
        description=(
            "Direction of the reported effect on the outcome measure relative to the "
            "comparator: 'increase' (the outcome increased), 'decrease' (the outcome "
            "decreased), 'no_effect' (a reported null result — a finding, not a "
            "gap), 'mixed' (direction differs within this single reported claim), "
            "'unclear' (an effect is reported but its direction cannot be "
            "determined). This is movement, never desirability."
        )
    )
    estimate_level: EstimateLevel | None = Field(
        description=(
            "'pooled' for a meta-analytic estimate across studies (k, I-squared, "
            "tau-squared expected where reported); 'study' for a single study's own "
            "estimate (N expected where reported); 'claim' for a stated finding "
            "with no accompanying estimate; null if indeterminate."
        )
    )
    study_design: str | None = Field(
        description=STUDY_DESIGN_DESC
    )
    study_geography: str | None = Field(
        description=STUDY_GEOGRAPHY_DESC
    )
    stratum_qualifiers: list[IOFStratumWire] = Field(
        description=(
            "Qualifiers that scope this finding (timepoint, subgroup, setting), each "
            "as its own entry; an empty list if the finding is unqualified."
        )
    )
    statistics: IOFStatisticsWire = Field(
        description=(
            "The reported statistics for this finding — reported values only, never "
            "computed, inferred or approximated by you."
        )
    )
    causality_by_design: CausalityByDesign | None = Field(
        description=(
            "Derived only from the reported design: 'attributable' (randomised "
            "designs, including pooled randomised trials), 'plausibly_causal' "
            "(quasi-experimental designs with credible identification), "
            "'associational' (observational designs), 'descriptive' (descriptive, "
            "qualitative or modelling reports without causal identification); null "
            "if the design is unknown."
        )
    )
    effect_basis: EffectBasis | None = Field(
        description=(
            "Whether this finding's effect was observed ('observed' — measured after something "
            "happened: trial results, administrative or monitoring data, evaluation "
            "measurements) or modelled ('modelled' — projected, simulated or forecast: model "
            "outputs, scenario projections, calibrated estimates of what would happen), or null "
            "if the document does not make this determinable. A modelled estimate is still "
            "'modelled' even when built on observed inputs."
        )
    )
    is_primary: bool | None = Field(
        description=(
            "True if the document presents this finding as a primary or headline "
            "result, false if clearly secondary, null if indeterminate."
        )
    )
    is_prevalence_only: bool | None = Field(
        description=(
            "True if this record reports how common something is rather than an "
            "intervention effect. If unsure whether a comparison is an effect "
            "estimate or mere prevalence, set true."
        )
    )
    anchors: list[IOFAnchorWire] = Field(
        description=(
            "At least one supporting anchor. Every anchor's quote must be exact "
            "verbatim text from the segment its segment_id names."
        )
    )


class ExtractionResponse(BaseModel):
    """The full wire response: a possibly-empty findings list.

    An empty list is explicitly legal — "this document reports no
    intervention–outcome findings" is a valid, expected answer.
    """

    model_config = ConfigDict(extra="forbid")

    findings: list[IOFRecordWire] = Field(
        description=(
            "Every intervention–outcome finding this document itself reports; an "
            "empty list when it reports none."
        )
    )


# --- Stored models (the final typed shape after grain validation + iof_rules_v3) ---


class IOFStratum(BaseModel):
    """A validated stratum qualifier."""

    model_config = ConfigDict(extra="forbid")

    type: StratumType
    value: str


class IOFStatistics(BaseModel):
    """The validated statistics bundle — real numerics, nulls real."""

    model_config = ConfigDict(extra="forbid")

    effect_size: float | None = None
    effect_size_type: str | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    standard_error: float | None = None
    p_value: float | None = None
    n: int | None = None
    k: int | None = None
    i_squared: float | None = None
    tau2: float | None = None


class IOFAnchor(BaseModel):
    """A validated anchor; segment_id null means the envelope abstract.

    An empty quote is representable — it fails verification and rides the
    finding flagged, per flag-not-drop.
    """

    model_config = ConfigDict(extra="forbid")

    segment_id: str | None
    quote: str


class IOFRecord(BaseModel):
    """One stored intervention–outcome finding — grain fields NOT NULL."""

    model_config = ConfigDict(extra="forbid")

    intervention: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    population: str | None
    setting: str | None
    comparator: str | None
    effect_direction: EffectDirection
    estimate_level: EstimateLevel | None
    study_design: str | None
    study_geography: str | None
    stratum_qualifiers: list[IOFStratum]
    statistics: IOFStatistics
    causality_by_design: CausalityByDesign | None
    effect_basis: EffectBasis | None
    is_primary: bool | None
    is_prevalence_only: bool | None
    anchors: list[IOFAnchor] = Field(min_length=1)


# --- The extraction window payload (the ExtractionBackend seam's unit of work) ---


class SegmentRecord(TypedDict):
    """One id-keyed segment record entering the prompt as data."""

    segment_id: str
    content: str


@dataclass(frozen=True)
class ExtractionWindowPayload:
    """One window of one document's basis text, ready for one backend call.

    ``metadata`` is the envelope snapshot metadata — carried for the stub's
    ``_stub_*`` sentinels only; it never enters the live prompt.
    """

    pss_id: str
    window_index: int
    title: str
    abstract: str | None
    primary_evidence_type: str | None
    segments: list[SegmentRecord]
    metadata: dict[str, Any] = field(default_factory=dict)


def render_field_docs() -> str:
    """Render the prompt's field reference from the wire models.

    Returns:
        A field-by-field reference block generated from the wire model field
        descriptions — the single source of truth for what the model is asked
        to fill.
    """
    return render_field_sections(
        [
            ("Finding fields", IOFRecordWire),
            ("statistics object fields", IOFStatisticsWire),
            ("stratum_qualifiers entry fields", IOFStratumWire),
            ("anchors entry fields", IOFAnchorWire),
        ]
    )
