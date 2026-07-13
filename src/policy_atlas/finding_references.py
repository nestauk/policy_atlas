"""Shared source-named reference field semantics for finding schemas.

The shared fields pin meaning and coercion across IOF and ICF, while
stored-model and column requiredness remain per schema. ``outcome`` and
``setting`` carry per-schema description text by design: outcome semantics
differ, and setting shares the inner-setting rule with schema-specific wording.
"""

INTERVENTION_DESC = (
    "The intervention exactly as this document names it (source-named, never "
    "a standardised term). Control or comparison arms are not interventions."
)
POPULATION_DESC = (
    "The study population exactly as the document describes it, or null if "
    "not reported."
)
STUDY_GEOGRAPHY_DESC = (
    "Where the evidence underlying this finding was conducted, exactly as the document "
    "reports it (e.g. 'United Kingdom', '12 OECD countries'), or null if not reported. "
    "This is the study's own setting — never inferred from publisher, venue or author "
    "affiliation. A geographic subgroup that scopes the claim belongs in "
    "stratum_qualifiers; this field records where the underlying study or studies took "
    "place."
)
STUDY_DESIGN_DESC = (
    "The study design underlying this finding, as the document reports it, "
    "or null if not reported."
)

SHARED_REFERENCE_FIELDS = (
    "intervention",
    "outcome",
    "population",
    "setting",
    "study_geography",
    "study_design",
)

# Stored-model / column requiredness per schema; drift guards assert against this.
REFERENCE_REQUIREDNESS = {
    "intervention": {"iof": True, "icf": True},
    "outcome": {"iof": True, "icf": False},
    "population": {"iof": False, "icf": False},
    "setting": {"iof": False, "icf": False},
    "study_geography": {"iof": False, "icf": False},
    "study_design": {"iof": False, "icf": False},
}
