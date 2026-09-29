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

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.core.schema import INTERVENTION_ROLES, OBJECT_TAGS, POPULATION_TAGS
from policy_atlas.evidence_search.extract.finding_references import render_field_sections
from policy_atlas.evidence_search.extract.quote_verify import NULL_LIKE_STRINGS

PROFILE_ID = "os_interventions_base_v1"
SCHEMA_VERSION = "interventions_v1"

InterventionRole = Literal["evaluated", "described", "recommended", "comparator", "mentioned"]

# The Literal type is the schema CHECK vocabulary — drift fails at import.
assert get_args(InterventionRole) == INTERVENTION_ROLES

#: The plan-relative tags (task 046, S5). Null on a record means "not tagged".
PopulationTag = Literal["on_target", "adjacent", "other"]
ObjectTag = Literal["plan_object", "option", "neither"]

assert get_args(PopulationTag) == POPULATION_TAGS
assert get_args(ObjectTag) == OBJECT_TAGS


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
            "The KIND of place where recipients meet the intervention, as a "
            "common noun from the abstract ('primary schools', 'home', "
            "'workplace', 'primary care', 'community leisure centres'), or "
            "null. Never a country, region, city or town; never a named "
            "organisation or building; never the body that mandated it; never "
            "the intervention itself. Null for an instrument that acts on a "
            "whole system (a tax, a price rule, a national regulation). Never "
            "inferred."
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
    population_tag: PopulationTag | None = Field(
        description=(
            "A sorting label against the policy context's target_unit: "
            "'on_target' (the same kind of people or bodies as the target "
            "unit, or a part of them), 'adjacent' (a wider group that "
            "contains it, or a neighbouring group the same kind of action "
            "reaches), 'other' (no such link, or no group can be read from "
            "the document). The place of the study never decides it. Null "
            "only when the policy context is null."
        )
    )
    outcome_tag: str | None = Field(
        description=(
            "A sorting label: the ONE entry of the policy context's outcomes "
            "that this record bears on — its outcome is that outcome measured "
            "in any way, or leads to it on a pathway — copied character for "
            "character; 'other' only when it bears on no entry. Null only "
            "when the policy context is null."
        )
    )
    object_tag: ObjectTag | None = Field(
        description=(
            "A sorting label: 'plan_object' (the recorded intervention is the "
            "thing the policy context's intended_change wants taken up — a "
            "technology, a product, a practice — studied for how it "
            "performs; never used when intended_change names no such thing), "
            "'option' (something a government, a public body or a provider "
            "does to bring the change about), 'neither' (a comparator arm, or "
            "anything else). Null only when the policy context is null."
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


# --- The profile bundle's stored shape (task 045 Phase 2.2) ------------------
#
# Everything below the wire models is pipeline code, not prompt text: the
# record carried through the shared extract pipeline, the stored record, the
# field rules and the dedup key. The fingerprint and the table writer live in
# ``interventions_profile`` (it imports the prompt module, which imports this
# one).

#: The field-rule set the validator below applies; a fingerprint component.
INTERVENTIONS_FIELD_RULES_VERSION = "interventions_rules_v1"

_NULLABLE_TEXT_FIELDS = ("outcome", "population", "setting", "study_geography", "study_design")


@dataclass(frozen=True)
class TaggingContext:
    """The plan fields the intervention profile tags each record against (task 046, S4).

    Built by the scoping side from the approved plan, with the place strip
    applied to the target unit and the intended change (never to the
    outcomes). It reaches the profile through ``extract_scope``'s
    ``interventions_context`` keyword; the IOF and ICF profiles never see it.

    Attributes:
        target_unit: The plan's target unit, place stripped.
        outcomes: The plan's outcome texts, in plan order.
        intended_change: The plan's intended change, place stripped.
    """

    target_unit: str
    outcomes: tuple[str, ...]
    intended_change: str

    @property
    def context_hash(self) -> str:
        """Full sha256 hex over the canonical JSON of the three fields.

        Stable across processes: the same context always gives the same
        hash. The intervention profile's fingerprint carries it, so a record
        tagged under one context is never reused under another.
        """
        canonical = json.dumps(
            {
                "target_unit": self.target_unit,
                "outcomes": list(self.outcomes),
                "intended_change": self.intended_change,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


#: The outcome tag for a record whose outcome serves no plan outcome.
OTHER_OUTCOME_TAG = "other"


def _fold_outcome(text: str) -> str:
    """Fold one outcome text for the tag match: case, whitespace, final full stop."""
    folded = " ".join(text.split()).casefold()
    return folded.removesuffix(".").rstrip()


@dataclass(frozen=True)
class TaggedRecord:
    """One wire record after the tag rules, with whether its outcome tag was repaired.

    Attributes:
        record: The wire record with its three tags settled.
        outcome_tag_repaired: True when the model's outcome tag matched no
            plan outcome (nor ``other``) even folded, and became ``other``.
    """

    record: InterventionsRecordWire
    outcome_tag_repaired: bool


def apply_tagging_rules(
    record: InterventionsRecordWire, context: TaggingContext | None
) -> TaggedRecord:
    """Settle one record's three plan-relative tags against the run's context.

    Rules (task 046, S4): with no context the three tags are ``None``
    whatever the model returned. With a context, an ``outcome_tag`` that is
    exactly one of the context's outcomes, or ``other``, is kept; otherwise it
    is matched with case and whitespace folded and a final full stop removed,
    and takes the plan's own text; no match becomes ``other`` and is a
    counted repair. A null tag stays null ("not tagged", as for the other
    two tags). A ``comparator`` record's
    ``object_tag`` is ``neither``. A tag never removes a record.

    Args:
        record: One wire record as the backend returned it.
        context: The run's tagging context, or ``None``.

    Returns:
        The record with its tags settled, and whether the outcome tag was
        repaired to ``other``.
    """
    if context is None:
        return TaggedRecord(
            record=record.model_copy(
                update={"population_tag": None, "outcome_tag": None, "object_tag": None}
            ),
            outcome_tag_repaired=False,
        )
    update: dict[str, object] = {}
    repaired = False
    raw_outcome = record.outcome_tag
    allowed = (*context.outcomes, OTHER_OUTCOME_TAG)
    if raw_outcome is not None and raw_outcome not in allowed:
        folded = _fold_outcome(raw_outcome)
        matched = next(
            (candidate for candidate in allowed if _fold_outcome(candidate) == folded), None
        )
        if matched is None:
            matched = OTHER_OUTCOME_TAG
            repaired = True
        update["outcome_tag"] = matched
    if record.role == "comparator" and record.object_tag != "neither":
        update["object_tag"] = "neither"
    return TaggedRecord(
        record=record.model_copy(update=update) if update else record,
        outcome_tag_repaired=repaired,
    )


class InterventionsRecordCarrier(InterventionsRecordWire):
    """One wire record with its document's ``covers_no_intervention`` attached.

    Pipeline-internal, never a model-facing schema: the shared extract
    pipeline handles records one by one, so the document-level flag rides on
    each record to reach the table, which carries it per row. The three
    plan-relative tags (task 046, S5) ride here too, defaulted to ``None``
    ("not tagged") so a record built without them stays valid; the window
    adapter settles them by :func:`apply_tagging_rules` first.
    """

    covers_no_intervention: bool
    population_tag: PopulationTag | None = None
    outcome_tag: str | None = None
    object_tag: ObjectTag | None = None


class InterventionsRecord(BaseModel):
    """One stored intervention profile record — a coverage fact, not an effect."""

    model_config = ConfigDict(extra="forbid")

    intervention: str = Field(min_length=1)
    role: InterventionRole
    design_features: list[str]
    is_bundle: bool
    components: list[str]
    outcome: str | None
    population: str | None
    setting: str | None
    study_geography: str | None
    study_design: str | None
    quote: str
    covers_no_intervention: bool
    population_tag: PopulationTag | None = None
    outcome_tag: str | None = None
    object_tag: ObjectTag | None = None


@dataclass
class ValidatedInterventionsRecord:
    """The outcome of validating one carried record.

    Attributes:
        record: The stored record, or ``None`` when the grain is invalid.
        field_coverage: Per-field coverage markers; a present field is absent
            from the map, an absent or null-like one is ``not_extracted``.
        coerced_null_fields: Fields whose null-like value was coerced to None.
        grain_invalid: True when the intervention names nothing.
    """

    record: InterventionsRecord | None
    field_coverage: dict[str, str]
    coerced_null_fields: list[str]
    grain_invalid: bool


def _coerce(value: str | None) -> str | None:
    """Return ``value`` stripped, or ``None`` when it is absent or null-like."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped.casefold() in NULL_LIKE_STRINGS:
        return None
    return stripped


def _clean_list(values: list[str]) -> list[str]:
    """Strip each phrase and drop the empty or null-like ones, keeping order."""
    cleaned: list[str] = []
    for value in values:
        coerced = _coerce(value)
        if coerced is not None:
            cleaned.append(coerced)
    return cleaned


def validate_interventions_record(
    wire: InterventionsRecordCarrier,
) -> ValidatedInterventionsRecord:
    """Validate one carried record under ``interventions_rules_v1``.

    Rules: null-like free text is coerced to ``None`` and marked
    ``not_extracted`` (the ICF rule); the design-feature and component lists
    lose blank entries; the grain is the intervention alone — a record whose
    intervention names nothing is invalid. The quote is kept verbatim, even
    when empty: a quote that does not locate earns a failed grounding, never a
    dropped record. The plan-relative tags are carried as they are (the
    closed two by their Literal types; a null-like ``outcome_tag`` becomes
    ``None``) and enter no coverage marker: an absent tag is "not tagged".

    Args:
        wire: The carried wire record, after NUL scrubbing.

    Returns:
        The validated record (``None`` when grain-invalid) plus coverage.
    """
    coverage: dict[str, str] = {}
    coerced: list[str] = []
    text_values: dict[str, str | None] = {}
    for field_name in _NULLABLE_TEXT_FIELDS:
        raw = getattr(wire, field_name)
        value = _coerce(raw)
        if value is None:
            coverage[field_name] = "not_extracted"
            if raw is not None:
                coerced.append(field_name)
        text_values[field_name] = value

    intervention = _coerce(wire.intervention)
    if intervention is None:
        return ValidatedInterventionsRecord(
            record=None,
            field_coverage=coverage,
            coerced_null_fields=coerced,
            grain_invalid=True,
        )

    design_features = _clean_list(wire.design_features)
    if not design_features:
        coverage["design_features"] = "not_extracted"
    record = InterventionsRecord(
        intervention=intervention,
        role=wire.role,
        design_features=design_features,
        is_bundle=wire.is_bundle,
        components=_clean_list(wire.components),
        outcome=text_values["outcome"],
        population=text_values["population"],
        setting=text_values["setting"],
        study_geography=text_values["study_geography"],
        study_design=text_values["study_design"],
        quote=wire.quote,
        covers_no_intervention=wire.covers_no_intervention,
        population_tag=wire.population_tag,
        outcome_tag=_coerce(wire.outcome_tag),
        object_tag=wire.object_tag,
    )
    return ValidatedInterventionsRecord(
        record=record,
        field_coverage=coverage,
        coerced_null_fields=coerced,
        grain_invalid=False,
    )


def _canonical(text: str) -> str:
    """Whitespace-normalise and casefold one key component."""
    return " ".join(text.split()).casefold()


def interventions_claim_key(record: InterventionsRecord) -> tuple[object, ...]:
    """The dedup key: one record per (intervention, role, stated design).

    Args:
        record: A stored intervention profile record.

    Returns:
        A hashable key over the canonical intervention, the role and the
        sorted canonical design features — two records naming one
        intervention with different stated designs stay two records.
    """
    return (
        _canonical(record.intervention),
        record.role,
        tuple(sorted(_canonical(feature) for feature in record.design_features)),
    )


def dedup_interventions_records(
    records: list[InterventionsRecord],
) -> tuple[list[InterventionsRecord], int]:
    """Collapse records with the same key; the first occurrence wins whole.

    A record carries one quote, so nothing merges: a later duplicate is
    absorbed and counted.

    Args:
        records: Stored records in emission order.

    Returns:
        ``(survivors, collapsed_count)``, survivors in first-occurrence order.
    """
    seen: set[tuple[object, ...]] = set()
    survivors: list[InterventionsRecord] = []
    collapsed = 0
    for record in records:
        key = interventions_claim_key(record)
        if key in seen:
            collapsed += 1
            continue
        seen.add(key)
        survivors.append(record.model_copy(deep=True))
    return survivors, collapsed
