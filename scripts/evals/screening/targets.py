"""Questions the screening eval scores, one published review or gap map each.

This file is the catalogue: which review or map each question is, and the
data file its labels come from. The question text itself (``query``) and the
published criteria (``criteria``) are in ``targets.json``, built from the
published sources by ``build_targets.py``; ``select_targets`` merges the two.

``query_v1`` is the hand-written question used before 2026-10-08 (questions
v1). It is kept so the first runs can be read; no run uses it now.

Every run scores all 30 questions by default; the dataset size (``mini`` or
``full`` in ``adapter.SIZES``) sets how many documents each one contributes.
``--targets`` picks a few questions by name, for a pilot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

TARGETS_JSON = Path(__file__).resolve().parent / "targets.json"


class Target(TypedDict):
    """One labelled screening question in the catalogue."""

    id: str
    name: str
    query_v1: str
    dataset_source: str


CSMED_TARGETS: list[Target] = [
    {
        "id": "CD010254",
        "name": "Clinical_Rosuvastatin",
        "query_v1": (
            "Assess the effects of various doses of rosuvastatin on serum total "
            "cholesterol and LDL-cholesterol in participants with and without "
            "cardiovascular disease."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD010901",
        "name": "Policy_DrugOffenders",
        "query_v1": (
            "Effectiveness of interventions for drug-using offenders with "
            "co-occurring mental health problems in reducing criminal activity "
            "or drug use."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD011737",
        "name": "PublicHealth_SaturatedFat",
        "query_v1": (
            "Effect of reducing saturated fat intake and replacing it with "
            "carbohydrate, polyunsaturated or monounsaturated fat on mortality "
            "and cardiovascular morbidity."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD007228",
        "name": "Systems_TelemonitoringHF",
        "query_v1": (
            "Structured telephone support or non-invasive home telemonitoring "
            "compared to standard practice for people with heart failure."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD005563",
        "name": "Hospital_DeliriumPrevention",
        "query_v1": (
            "Effectiveness of interventions for preventing delirium in "
            "hospitalised non-Intensive Care Unit (non-ICU) patients."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD010534",
        "name": "Family_ParentInfantPsych",
        "query_v1": (
            "Effectiveness of parent-infant psychotherapy (PIP) in improving "
            "parental and infant mental health and the parent-infant relationship."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD001191",
        "name": "Aging_AlzheimersDrug",
        "query_v1": (
            "Clinical efficacy and safety of rivastigmine for patients with "
            "dementia of Alzheimer's type."
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD007714",
        "name": "Respiratory_NIV_COPD",
        "query_v1": (
            "Does adding non-invasive ventilation during pulmonary rehabilitation "
            "enable people with COPD to exercise at higher intensities and improve "
            "health-related quality of life compared with exercise training alone?"
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD006612",
        "name": "Cardio_Homocysteine",
        "query_v1": (
            "Do homocysteine-lowering therapies (folate, vitamin B12, vitamin B6 "
            "or combination therapy) reduce cardiovascular events compared with "
            "placebo or usual care in high-risk adults?"
        ),
        "dataset_source": "CSMeD",
    },
    {
        "id": "CD008729",
        "name": "Psych_OncologySupport",
        "query_v1": (
            "Which psychological interventions reduce distress and improve coping "
            "or quality of life for women with non-metastatic breast cancer during "
            "or after active treatment?"
        ),
        "dataset_source": "CSMeD",
    },
]

SYNERGY_TARGETS: list[Target] = [
    {
        "id": "van_Dis_2020",
        "name": "Psych_CBT_Anxiety",
        "query_v1": (
            "What are the long-term outcomes of Cognitive Behavioral Therapy (CBT) "
            "for anxiety-related disorders?"
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "van_de_Schoot_2018",
        "name": "Psych_PTSD_Trajectories",
        "query_v1": (
            "Studies identifying or reporting on latent trajectories of PTSD "
            "symptoms in diverse populations."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Hall_2012",
        "name": "CS_FaultPrediction",
        "query_v1": (
            "Predicting faults in software units using code metrics and models: "
            "a systematic review of performance."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Radjenovic_2013",
        "name": "CS_SoftwareMetrics",
        "query_v1": (
            "Software fault prediction metrics and systematic literature reviews "
            "in software engineering."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Appenzeller-Herzog_2019",
        "name": "Clinical_WilsonDisease",
        "query_v1": (
            "Comparative effectiveness of common therapies (e.g., chelators, zinc) "
            "for Wilson disease."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Bos_2018",
        "name": "Clinical_SmallVesselDisease",
        "query_v1": (
            "Association between cerebral small vessel disease (CSVD) structures "
            "and the risk of dementia or cognitive decline."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Wolters_2018",
        "name": "Clinical_HeartBrain",
        "query_v1": (
            "Association between coronary heart disease or heart failure and the "
            "subsequent risk of dementia or cognitive impairment."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "Oud_2018",
        "name": "Psych_BPD_Therapies",
        "query_v1": (
            "Effectiveness of psychotherapies such as schema-focused, "
            "mentalization-based, dialectical behaviour or supportive therapy for "
            "adults diagnosed with borderline personality disorder."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "van_der_Valk_2021",
        "name": "Endocrine_StressBiomarkers",
        "query_v1": (
            "Associations between hypothalamic–pituitary–adrenal axis biomarkers "
            "(e.g., cortisol, copeptin, hair cortisol) and metabolic or psychiatric "
            "outcomes in adult humans."
        ),
        "dataset_source": "SYNERGY",
    },
    {
        "id": "van_der_Waal_2022",
        "name": "Oncology_SharedDecisions",
        "query_v1": (
            "Barriers, facilitators and digital supports influencing shared "
            "decision-making, treatment preferences and clinician–patient "
            "communication for people with cancer."
        ),
        "dataset_source": "SYNERGY",
    },
]

THREE_IE_TARGETS: list[Target] = [
    {
        "id": "3ie_EGM_Climate_2024",
        "name": "Enviro_ClimateBiodiversity",
        "query_v1": (
            "What are the effects of climate change and biodiversity interventions "
            "on environmental and human wellbeing outcomes?"
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_Governance_2023",
        "name": "Gov_GoodGovernance",
        "query_v1": (
            "Interventions to strengthen governance effectiveness, rule of law, "
            "and accountability in low- and middle-income countries."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_Migration_2023",
        "name": "Policy_IrregularMigration",
        "query_v1": (
            "Interventions that address the root causes and drivers of irregular "
            "migration, such as economic opportunities and conflict resilience."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_FoodSystems_2024",
        "name": "Agri_FoodSystems",
        "query_v1": (
            "Effects of food systems interventions (production, supply chain, food "
            "environment) on food security and nutrition outcomes."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_SRHR_2024",
        "name": "Health_SexualReproRights",
        "query_v1": (
            "Impact of interventions to promote sexual and reproductive health and "
            "rights (SRHR) and women's empowerment."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_WASH_2023",
        "name": "Infra_WaterSanitation",
        "query_v1": (
            "What is the association between WASH interventions (water access, "
            "sanitation facilities) and development outcomes like health and prosperity?"
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_Anaemia_2024",
        "name": "Health_AnaemiaReduction",
        "query_v1": (
            "Effectiveness of interventions to reduce anaemia (fortification, "
            "supplementation, disease control) in low- and middle-income countries."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_Energy_2024",
        "name": "Infra_SustainableEnergy",
        "query_v1": (
            "Impact of interventions to promote sustainable energy access, "
            "renewables, and efficient technologies in developing countries."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_LandUse_2024",
        "name": "Enviro_LandUseForestry",
        "query_v1": (
            "Effects of land-use change and forestry programmes (conservation, "
            "restoration, management) on environmental and socio-economic outcomes."
        ),
        "dataset_source": "3ie",
    },
    {
        "id": "3ie_EGM_Resilience_2023",
        "name": "Social_ResilienceShocks",
        "query_v1": (
            "Interventions to strengthen resilience against covariate shocks, "
            "stressors, and recurring crises in low- and middle-income countries."
        ),
        "dataset_source": "3ie",
    },
]

ALL_EVAL_TARGETS: list[Target] = CSMED_TARGETS + SYNERGY_TARGETS + THREE_IE_TARGETS


def select_targets(names: list[str] | None) -> list[dict]:
    """Pick the questions a run will score, with their text from ``targets.json``.

    Args:
        names: Target ``name`` values. ``None`` selects every question.

    Returns:
        The selected targets, in catalogue order for ``None`` and in the
        order of ``names`` otherwise. Each has the catalogue fields plus
        ``query``, ``criteria`` and their sources.

    Raises:
        ValueError: If a name is not in the catalogue.
        FileNotFoundError: If ``targets.json`` has not been built.
    """
    built = {
        entry["name"]: entry
        for entry in json.loads(TARGETS_JSON.read_text(encoding="utf-8"))
    }
    merged = [{**target, **built[target["name"]]} for target in ALL_EVAL_TARGETS]
    if names is None:
        return merged
    chosen = list(names)
    by_name = {target["name"]: target for target in merged}
    missing = [name for name in chosen if name not in by_name]
    if missing:
        known = ", ".join(sorted(by_name))
        raise ValueError(
            f"Unknown target(s): {', '.join(missing)}. Known names: {known}"
        )
    return [by_name[name] for name in chosen]
