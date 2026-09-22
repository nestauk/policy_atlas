"""Intervention profile record models — the third extraction profile (task 045).

The wire model drives structured output and prompt field documentation for
the intervention profile: for one document, every intervention its title and
abstract cover, each with a role and its stated design. Nothing here is a
finding of effect (ADR 0039 decision 6): a record says a document *covers*
an intervention, never that the intervention worked. Closed enums are strict
Literals asserted against the schema CHECK vocabularies at import.

Lead-authored field descriptions (prompt-bearing); the stored model, the
fingerprint and the writer are the profile bundle's (Phase 2.2).
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.core.schema import INTERVENTION_ROLES
from policy_atlas.evidence_search.extract.finding_references import render_field_sections

PROFILE_ID = "os_interventions_base_v1"
SCHEMA_VERSION = "interventions_v1"

InterventionRole = Literal["evaluated", "described", "recommended", "comparator", "mentioned"]

# The Literal type is the schema CHECK vocabulary — drift fails at import.
assert get_args(InterventionRole) == INTERVENTION_ROLES


class InterventionsRecordWire(BaseModel):
    """One intervention the document covers, as emitted by the model."""

    model_config = ConfigDict(extra="forbid")

    intervention: str = Field(
        description=(
            "The intervention as this document names it, self-contained for a "
            "reader who has not seen the document: what it is, who delivers it, "
            "to whom ('peer-led 12-week walking programme for inactive adults "
            "aged 60 to 70', never 'the programme' or 'this approach'). Expand "
            "an acronym the abstract defines, keeping the short form in "
            "brackets. Control or comparison arms are recorded with role "
            "'comparator', never as the studied intervention."
        )
    )
    role: InterventionRole = Field(
        description=(
            "What THIS document does with the intervention: 'evaluated' (reports "
            "its effects or implementation results from data — a trial, an "
            "observational evaluation, or a review or meta-analysis reporting "
            "pooled or summarised results for it); 'described' (explains or "
            "catalogues it without reporting results for it); 'recommended' "
            "(proposes or calls for it); 'comparator' (it is the control or "
            "comparison arm); 'mentioned' (named in passing). About the "
            "document's relationship to the intervention, never its merit."
        )
    )
    design_features: list[str] = Field(
        description=(
            "The features the abstract STATES that define this implementation: "
            "who delivers it, to whom, for how long, with what obligation, "
            "sanction or incentive, free or paid, universal or targeted. Short "
            "phrases, copied or closely paraphrased. Empty when the abstract "
            "states none — never guessed."
        )
    )
    is_bundle: bool = Field(
        description=(
            "True when the intervention is a package of several components "
            "delivered together (a whole-system approach, a multi-component "
            "programme)."
        )
    )
    components: list[str] = Field(
        description=(
            "The named components when is_bundle is true, as the abstract names "
            "them; otherwise empty."
        )
    )
    outcome: str | None = Field(
        description=(
            "The outcome the abstract ties to this intervention, as a base "
            "measure with no direction word ('physical activity', 'employment "
            "rate'), or null. When several are named, the one the abstract "
            "treats as primary."
        )
    )
    population: str | None = Field(
        description=(
            "The population this intervention was delivered to, as the abstract names it, or null."
        )
    )
    setting: str | None = Field(
        description=(
            "Where recipients experienced the intervention, exactly as the "
            "abstract names it ('primary schools', 'community leisure centres', "
            "'Jobcentres'), or null. The delivery setting, never the body that "
            "mandated it. Never inferred."
        )
    )
    study_geography: str | None = Field(
        description=(
            "Where the evidence about this intervention was gathered, exactly as "
            "the abstract states it ('United Kingdom', 'Denmark', '12 OECD "
            "countries'), or null. Never inferred from the publisher, journal or "
            "authors."
        )
    )
    study_design: str | None = Field(
        description=(
            "The study design the abstract states ('cluster randomised trial', "
            "'systematic review of 23 studies', 'cost-effectiveness model', "
            "'policy commentary'), or null."
        )
    )
    quote: str = Field(
        description=(
            "A verbatim span copied from the title or abstract that names this "
            "intervention. Exact text — never paraphrased, never stitched from "
            "two places."
        )
    )


class InterventionsResponse(BaseModel):
    """The intervention profile's output for one document."""

    model_config = ConfigDict(extra="forbid")

    records: list[InterventionsRecordWire] = Field(
        description=(
            "Every intervention the title or abstract covers, one record each. "
            "Empty when the document covers none."
        )
    )
    covers_no_intervention: bool = Field(
        description=(
            "True when the document covers no intervention at all — a prevalence "
            "study, a cohort profile, a commentary on the problem. Must agree "
            "with an empty records list."
        )
    )


def render_interventions_field_docs() -> str:
    """Render the prompt's field reference from the wire models.

    Returns:
        A field-by-field reference block generated from the wire model field
        descriptions — the single source of truth for what the model is asked
        to fill.
    """
    return render_field_sections(
        [
            ("Record fields", InterventionsRecordWire),
            ("Response fields", InterventionsResponse),
        ]
    )
