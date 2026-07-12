"""ICF record models — implementation-context findings for task 021.

The wire models drive structured output and prompt field documentation for the
ICF profile. Free-text fields are nullable on the wire so null-like strings can
be coerced by ``icf_rules_v1``; closed enums are strict Literals. Stored models
are the final shape after grain validation and field rules.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.extraction_records import IOFAnchor, IOFAnchorWire
from policy_atlas.finding_references import (
    INTERVENTION_DESC,
    POPULATION_DESC,
    STUDY_DESIGN_DESC,
    STUDY_GEOGRAPHY_DESC,
)
from policy_atlas.schema import CLAIM_BASES, CLAIM_LEVELS, CONTEXT_LEVELS, CONTEXT_TYPES

# Fingerprint components for the independent ICF extraction profile.
PROFILE_ID = "eb_icf_base_v1"
SCHEMA_VERSION = "icf_v1"

ContextType = Literal[
    "mechanism",
    "barrier",
    "enabler",
    "implementation_condition",
    "delivery_process",
    "adaptation",
    "fidelity",
]
ClaimLevel = Literal["study", "pooled"]
ClaimBasis = Literal["studied", "author_assertion", "cited_theory"]
ContextLevel = Literal["system", "organisation", "provider", "recipient"]

# The Literal types are the schema CHECK vocabularies — drift fails at import.
assert get_args(ContextType) == CONTEXT_TYPES
assert get_args(ClaimLevel) == CLAIM_LEVELS
assert get_args(ClaimBasis) == CLAIM_BASES
assert get_args(ContextLevel) == CONTEXT_LEVELS


class ICFRecordWire(BaseModel):
    """One implementation-context finding as emitted by the model."""

    model_config = ConfigDict(extra="forbid")

    context_type: ContextType = Field(
        description=(
            "The kind of implementation-context claim: 'mechanism' (why or how "
            "the intervention produces its effects, as the source explains it), "
            "'barrier' (something that hindered delivery or uptake), 'enabler' "
            "(something that helped delivery or uptake), 'implementation_condition' "
            "(a condition the source states the intervention depends on to work), "
            "'delivery_process' (how the intervention was actually delivered or "
            "operated), 'adaptation' (a modification made to the intervention, "
            "including why and whether core elements were kept), or 'fidelity' "
            "(how delivery compared to what was planned — dose, adherence, quality)."
        )
    )
    claim: str | None = Field(
        description=(
            "The implementation-context finding as one self-contained sentence, "
            "stated the way the source states it — a report of what happened or "
            "what the source asserts, never a recommendation, aspiration or target."
        )
    )
    intervention: str | None = Field(
        description=INTERVENTION_DESC
    )
    outcome: str | None = Field(
        description=(
            "The outcome this context claim relates to, exactly as the source names "
            "it, or null — a mechanism may explain a specific outcome; most barriers "
            "and conditions name none."
        )
    )
    population: str | None = Field(
        description=POPULATION_DESC
    )
    setting: str | None = Field(
        description=(
            "The setting where recipients experience the intervention, exactly as "
            "the source names it (e.g. 'primary care', 'secondary schools', "
            "'social housing'), or null if not reported. Use the delivery setting, "
            "not the institution that created or mandated the intervention: if a "
            "parliament passes a school nutrition policy, the setting is the school, "
            "not parliament. Never inferred."
        )
    )
    study_geography: str | None = Field(
        description=STUDY_GEOGRAPHY_DESC
    )
    study_design: str | None = Field(
        description=STUDY_DESIGN_DESC
    )
    claim_level: ClaimLevel | None = Field(
        description=(
            "'study' if this is the source's own observation from its own fieldwork "
            "or data; 'pooled' if the source synthesises the claim across multiple "
            "included studies (e.g. 'the most cited barrier across included trials'); "
            "null if indeterminate."
        )
    )
    claim_basis: ClaimBasis | None = Field(
        description=(
            "'studied' if the claim rests on empirical implementation data — the "
            "source's own fieldwork (a process evaluation, qualitative arm, "
            "implementation data) OR implementation data the source synthesises from "
            "its included studies; 'author_assertion' if the source's authors assert "
            "it in discussion or commentary without empirical grounding; 'cited_theory' "
            "if the source carries it from cited literature or theoretical framing; "
            "null if indeterminate. Never guess. (A review's pooled empirical barrier "
            "is 'studied' + claim_level 'pooled' — the two fields are independent.)"
        )
    )
    level: ContextLevel | None = Field(
        description=(
            "The level the claim operates at, as the source frames it: 'system' "
            "(policy, legal, funding environment), 'organisation' (the delivering "
            "organisation), 'provider' (the staff delivering), 'recipient' (the "
            "people receiving), or null."
        )
    )
    resource_requirements: str | None = Field(
        description=(
            "Costs, funding or material resources the source reports for implementing "
            "the intervention, exactly as reported, or null. Only what the source "
            "states — never estimated or graded."
        )
    )
    workforce_requirements: str | None = Field(
        description=(
            "Staffing, skills or training the source reports the intervention "
            "requires, exactly as reported, or null. Only what the source states — "
            "never estimated or graded."
        )
    )
    anchors: list[IOFAnchorWire] = Field(
        description=(
            "At least one supporting anchor. Every anchor's quote must be exact "
            "verbatim text from the segment its segment_id names."
        )
    )


class ICFExtractionResponse(BaseModel):
    """The full ICF wire response: a possibly-empty findings list.

    An empty list is explicitly legal — "this document reports no
    implementation-context findings" is a valid, expected answer.
    """

    model_config = ConfigDict(extra="forbid")

    findings: list[ICFRecordWire] = Field(
        description=(
            "Every implementation-context finding this document itself reports; "
            "an empty list when it reports none."
        )
    )


class ICFRecord(BaseModel):
    """One stored implementation-context finding — grain fields NOT NULL."""

    model_config = ConfigDict(extra="forbid")

    context_type: ContextType
    claim: str = Field(min_length=1)
    intervention: str = Field(min_length=1)
    outcome: str | None
    population: str | None
    setting: str | None
    study_geography: str | None
    study_design: str | None
    claim_level: ClaimLevel | None
    claim_basis: ClaimBasis | None
    level: ContextLevel | None
    resource_requirements: str | None
    workforce_requirements: str | None
    anchors: list[IOFAnchor] = Field(min_length=1)


def render_field_docs() -> str:
    """Render the ICF prompt's field reference from the wire models.

    Returns:
        A field-by-field reference block generated from the wire model field
        descriptions.
    """
    sections: list[tuple[str, type[BaseModel]]] = [
        ("Finding fields", ICFRecordWire),
        ("anchors entry fields", IOFAnchorWire),
    ]
    lines: list[str] = []
    for heading, model in sections:
        lines.append(f"{heading}:")
        for name, model_field in model.model_fields.items():
            lines.append(f"- {name}: {model_field.description}")
        lines.append("")
    return "\n".join(lines).rstrip()
