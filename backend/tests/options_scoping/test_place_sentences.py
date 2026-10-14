"""The place sentences' code (task 046, amendment 4, R80; S31; rubric box 76).

The grouping and its order, the call input's short ids, the template and its
plural forms (contract review C7), and the trace check over a seeded fixture
set of valid and invalid sentences, each with its expected verdict
(contract review C2, C3; plan review PA4-8).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from policy_atlas.options_scoping.labels import DocumentLabels
from policy_atlas.options_scoping.option_profile.place_sentences import (
    NO_SINGLE_PLACE,
    PlaceDocument,
    PlaceGroup,
    call_input,
    from_membership,
    group_places,
    plural,
    template_sentence,
    trace_check,
    type_word,
    vocabulary_from_folds,
)
from policy_atlas.options_scoping.option_profile.place_sentences_prompt import (
    PLACE_DOCUMENTS_MAX,
    build_place_sentences_messages,
)
from tests.options_scoping.test_longlist_coverage_046 import _member


def _doc(key: str, **values: Any) -> PlaceDocument:
    fields: dict[str, Any] = {
        "doc_key": f"doc:{key}",
        "role": "evaluated",
        "place": "United Kingdom",
        "programme_name": None,
        "unit": None,
        "tried_on_kind": None,
        "setting": None,
        "outcome": None,
        "measured": None,
        "study_geography": None,
        "place_detail": None,
        "tier": None,
        "quality_score": None,
        "evidence_type": None,
        "year": None,
        "title": f"Title {key}",
    }
    fields.update(values)
    return PlaceDocument(**fields)


def _group(*docs: PlaceDocument) -> PlaceGroup:
    (group,) = group_places(docs, where_country="United Kingdom")
    return group


# --- the grouping ---------------------------------------------------------------------


def test_the_where_country_leads_then_count_then_name_and_no_single_place_is_last() -> None:
    docs = [
        _doc("fr1", place="France"),
        _doc("ca1", place="Canada", quality_score=2, tier="Limited"),
        _doc("multi", place="multiple countries"),
        _doc("fr2", place="France"),
        _doc("uk1", place="United Kingdom"),
        _doc("ca2", place="Canada", quality_score=5, tier="Very strong"),
        _doc("none", place="not stated"),
        _doc("other", place="other"),
        _doc("de1", place="Germany", role="described"),
        _doc("us1", place="United States"),
        _doc("us2", place="United States"),
        _doc("us3", place="United States"),
    ]
    groups = group_places(docs, where_country="United Kingdom")
    assert [(g.place_id, g.place, g.is_where, g.documents_total) for g in groups] == [
        ("p1", "United Kingdom", True, 1),
        ("p2", "United States", False, 3),
        ("p3", "Canada", False, 2),
        ("p4", "France", False, 2),
        ("p5", NO_SINGLE_PLACE, False, 3),
    ]
    # Inside a group: quality score descending, unrated last, then title.
    assert [d.doc_key for d in groups[2].documents] == ["doc:ca2", "doc:ca1"]
    # A describing document makes no line.
    assert all(d.doc_key != "doc:de1" for g in groups for d in g.documents)


def test_no_where_country_orders_by_count_and_an_empty_no_single_place_is_absent() -> None:
    groups = group_places(
        [_doc("a", place="France"), _doc("b", place="Canada"), _doc("c", place="Canada")],
        where_country=None,
    )
    assert [(g.place, g.is_where) for g in groups] == [("Canada", False), ("France", False)]
    assert group_places([], where_country="United Kingdom") == []


def test_from_membership_reads_the_first_record_the_labels_and_resolves_the_place() -> None:
    uk, twin, ca, described = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    members = [
        # One document, DOI twins together; its evaluated record leads.
        _member(
            "",
            doc_key="doi:10.1/a",
            tss_id=uk,
            role="described",
            unit="parents",
            programme_name="Change 4 Life",
            study_country="UK",
        ),
        _member(
            "",
            doc_key="doi:10.1/a",
            tss_id=twin,
            unit="Year 6 pupils",
            outcome="BMI",
            outcome_tag="the obesity rate",
            setting="schools",
            programme_name="Change4Life",
            study_country="UK",
            study_geography="Leeds",
        ),
        _member("ca", tss_id=ca, unit="families", outcome="diet", study_country="Canada"),
        _member("described", tss_id=described, role="described", study_country="France"),
    ]
    labels = {
        twin: DocumentLabels(
            evidence_type="Observational Research Studies",
            quality_score=3,
            rubric_version="v1",
            provenance="own",
        ),
    }
    folds = {"tried_on": {"Year 6 pupils": "children"}, "measures": {"diet": "diet quality"}}
    docs = from_membership(
        members,
        labels=labels,
        folds=folds,
        plan_outcomes=["The obesity rate"],
        year_by_tss={twin: 2019},
        title_by_tss={twin: "A study"},
    )
    assert [d.doc_key for d in docs] == ["doc:ca", "doi:10.1/a"]
    canada, uk_doc = docs
    assert (uk_doc.place, uk_doc.place_detail, uk_doc.study_geography) == (
        "United Kingdom",
        "Leeds",
        "Leeds",
    )
    assert (uk_doc.unit, uk_doc.tried_on_kind, uk_doc.setting, uk_doc.outcome) == (
        "Year 6 pupils",
        "children",
        "schools",
        "BMI",
    )
    assert uk_doc.measured == "The obesity rate"
    assert (uk_doc.tier, uk_doc.quality_score, uk_doc.evidence_type) == (
        "Moderate",
        3,
        "Observational Research Studies",
    )
    assert (uk_doc.year, uk_doc.title) == (2019, "A study")
    # The programme name is the first record's, folded over the option.
    assert uk_doc.programme_name in {"Change4Life", "Change 4 Life"}
    assert (canada.place, canada.tried_on_kind, canada.measured, canada.tier) == (
        "Canada",
        "families",
        "diet quality",
        None,
    )


def test_the_call_input_numbers_places_and_documents_across_the_option() -> None:
    many = [_doc(f"uk{i:02}", quality_score=i % 5 + 1) for i in range(PLACE_DOCUMENTS_MAX + 1)]
    groups = group_places(
        [*many, _doc("ca", place="Canada", unit="pupils", year=2020)],
        where_country="United Kingdom",
    )
    data = call_input(
        "Youth guarantee",
        "A guaranteed offer.",
        {"target_unit": "16 to 24 year olds", "outcomes": ["the NEET rate"], "question": "q"},
        vocabulary_from_folds({"tried_on": {"a": "pupils", "b": "Pupils"}, "measures": {}}),
        groups,
    )
    assert data["option"] == {"name": "Youth guarantee", "description": "A guaranteed offer."}
    assert data["plan"] == {
        "target_unit": "16 to 24 year olds",
        "target_unit_short": "16 to 24 year olds",
        "outcomes": ["the NEET rate"],
    }
    assert data["vocabulary"] == {"tried_on_kinds": ["pupils"], "measures_kinds": []}
    uk, ca = data["places"]
    assert (uk["place_id"], uk["place"], uk["documents_total"]) == ("p1", "United Kingdom", 13)
    assert len(uk["documents"]) == PLACE_DOCUMENTS_MAX
    assert [d["id"] for d in uk["documents"]] == [f"d{i}" for i in range(1, 13)]
    assert ca["documents"] == [
        {
            "id": "d13",
            "programme_name": None,
            "unit": "pupils",
            "tried_on_kind": None,
            "setting": None,
            "outcome": None,
            "measured": None,
            "study_geography": None,
            "tier": None,
            "evidence_type": None,
            "year": 2020,
        }
    ]
    # The prompt builder takes it as it is.
    assert len(build_place_sentences_messages(**data)) == 2


# --- the template (C7) ----------------------------------------------------------------


def test_the_template_drops_each_null_clause_down_to_n_documents() -> None:
    change4life = _group(
        *(
            _doc(
                str(i),
                programme_name="Change4Life",
                tier="Moderate",
                quality_score=3,
                evidence_type="Local evaluation",
                tried_on_kind="children aged 4 to 11",
                place_detail="England",
                measured="prevalence of obesity at reception",
            )
            for i in range(3)
        )
    )
    assert template_sentence(change4life) == (
        "Change4Life: 3 moderate local evaluations with children aged 4 to 11 in England, "
        "measuring prevalence of obesity at reception."
    )
    review = _group(
        _doc(
            "r",
            tier="Strong",
            quality_score=4,
            evidence_type="Systematic Review and Meta-Analysis",
            tried_on_kind="families",
            measured="diet quality",
        )
    )
    assert template_sentence(review) == (
        "1 strong systematic review with families, measuring diet quality."
    )
    assert template_sentence(_group(_doc("a"), _doc("b"))) == "2 documents."
    henry = _group(
        _doc("h", programme_name="HENRY", evidence_type="Local evaluation", measured="diet quality")
    )
    assert template_sentence(henry) == "HENRY: 1 local evaluation measuring diet quality."


def test_the_template_s_programme_strength_and_type_rules() -> None:
    # Two programmes, or one document without a name: no programme.
    assert template_sentence(
        _group(_doc("a", programme_name="HENRY"), _doc("b", programme_name="Change4Life"))
    ) == "2 documents."
    assert template_sentence(_group(_doc("a", programme_name="HENRY"), _doc("b"))) == (
        "2 documents."
    )
    # A tie leaves the strength and the type out; Unknown reads as documents.
    tied = _group(
        _doc("a", tier="Strong", evidence_type="RCTs and Quasi-Experimental Studies"),
        _doc("b", tier="Weak", evidence_type="Policy Syntheses & Guidance Documents"),
    )
    assert template_sentence(tied) == "2 documents."
    unknown = _group(
        _doc("a", tier="Weak", evidence_type="Unknown / Insufficient information"),
        _doc("b", tier="Weak", evidence_type="Unknown / Insufficient information"),
        _doc("c", evidence_type="Expert Opinion and Commentary"),
    )
    assert template_sentence(unknown) == "3 weak documents."
    trials = _group(
        _doc("a", evidence_type="RCTs and Quasi-Experimental Studies"),
        _doc("b", evidence_type="RCTs and Quasi-Experimental Studies", place_detail="Leeds"),
    )
    assert template_sentence(trials) == "2 trials."
    first_detail = _group(_doc("a", place_detail="Leeds", measured="diet quality"))
    assert template_sentence(first_detail) == "1 document in Leeds, measuring diet quality."


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("policy analysis", "policy analyses"),
        ("observational study", "observational studies"),
        ("commentary", "commentaries"),
        ("survey", "surveys"),
        ("trial", "trials"),
        ("local evaluation", "local evaluations"),
    ],
)
def test_the_plural_forms(word: str, expected: str) -> None:
    assert plural(word) == expected


def test_the_type_words() -> None:
    assert type_word("Systematic Review and Meta-Analysis") == "systematic review"
    assert type_word("Modelling & Simulation") == "modelling study"
    assert type_word("Other (Non-evidence documents)") is None
    assert type_word("Unknown / Insufficient information") is None
    assert type_word("Local evaluation") == "local evaluation"
    assert type_word(None) is None


# --- the trace check (S31; PA4-8; C2, C3) ---------------------------------------------

#: The fixed place every fixture below is checked against: four evaluating
#: documents in the United Kingdom.
_FIXED = _group(
    _doc(
        "1",
        tier="Strong",
        quality_score=4,
        evidence_type="RCTs and Quasi-Experimental Studies",
        programme_name="Strong Start",
        unit="9-to-10-year-olds",
        tried_on_kind="children",
        measured="diet quality",
        study_geography="Leeds and Sheffield",
        place_detail="Leeds and Sheffield",
    ),
    _doc(
        "2",
        tier="Strong",
        quality_score=4,
        evidence_type="RCTs and Quasi-Experimental Studies",
        programme_name="Strong Start",
        unit="9-to-10-year-olds",
        tried_on_kind="children",
        measured="diet quality",
        study_geography="Leeds",
        place_detail="Leeds",
    ),
    _doc(
        "3",
        tier="Moderate",
        quality_score=3,
        evidence_type="Local evaluation",
        programme_name="Change4Life",
        unit="families",
        tried_on_kind="families",
        measured="moderate-to-vigorous physical activity",
        study_geography="England",
        place_detail="England",
    ),
    _doc(
        "4",
        evidence_type="Observational Research Studies",
        unit="year 6 pupils",
        tried_on_kind="children",
        measured="prevalence of obesity at reception",
    ),
)
_PLAN_OUTCOMES = ["prevalence of obesity at reception", "diet quality"]
_VOCABULARY = {
    "tried_on_kinds": ["children", "families"],
    "measures_kinds": ["diet quality", "physical activity"],
}

#: The valid sentences over the fixed place: each passes (verdict ``None``).
_VALID: list[tuple[str, str | None]] = [
    # A second sentence after a full stop starts with a number word (review of
    # task 046, 2026-10-12: the live obesity run lost two accurate sentences
    # to the name rule on "… year 6. One was …").
    (
        "Two strong trials of Strong Start measured diet quality in children. "
        "One was in England.",
        None,
    ),
    # "Strong Start" as a programme name; a sub-count by tier; a unit with digits.
    (
        "Four evaluations: two strong trials of Strong Start in Leeds and Sheffield "
        "measured diet quality in 9-to-10-year-olds.",
        None,
    ),
    ("Two strong trials of Strong Start measured diet quality in children.", None),
    # A number word equal to the total, as digits.
    (
        "4 evaluations measured diet quality, physical activity and prevalence of obesity "
        "at reception.",
        None,
    ),
    # A strength word inside an outcome the sentence holds whole.
    (
        "One moderate local evaluation of Change4Life in England measured "
        "moderate-to-vigorous physical activity in families.",
        None,
    ),
    # The total minus a sub-count; a sentence starting with a number word.
    ("Three of the four evaluations measured diet quality in children.", None),
    # A generic word at position 0; a place below the country.
    ("Evaluations in Leeds measured diet quality in 9-to-10-year-olds.", None),
    # "not rated" for the document with no tier; "6" beside its word in a unit.
    (
        "One not rated observational study measured prevalence of obesity at reception "
        "in year 6 pupils.",
        None,
    ),
    (
        "Two strong trials and one moderate local evaluation measured diet quality and "
        "moderate-to-vigorous physical activity.",
        None,
    ),
    # A preposition at position 0 inside a capitalised run.
    (
        "In England, one moderate local evaluation of Change4Life measured "
        "moderate-to-vigorous physical activity.",
        None,
    ),
    # An article at position 0; a strength word standing alone.
    ("The Strong Start trials, two of them strong, measured diet quality.", None),
    # The count of distinct programme names.
    ("Two programmes, Strong Start and Change4Life, were evaluated in children.", None),
]

#: The invalid sentences over the fixed place, each with the rule it fails.
_INVALID: list[tuple[str, str | None]] = [
    # An invented name at the start of a second sentence.
    ("Two strong trials of Strong Start measured diet quality. Bristol ran one.", "name"),
    # An invented acronym.
    ("Four evaluations, including NCMP data, measured diet quality.", "name"),
    # An invented name at position 0.
    ("Bristol's two trials of Strong Start measured diet quality.", "name"),
    # A count that matches nothing.
    ("Seven evaluations measured diet quality.", "number"),
    ("Five evaluations measured diet quality in children.", "number"),
    # "very strong" when only "strong" is carried.
    ("Two very strong trials of Strong Start measured diet quality.", "strength"),
    # A strength no document carries.
    ("One weak local evaluation of Change4Life measured physical activity.", "strength"),
    # A sample size.
    ("Two strong trials measured diet quality in 1,200 children.", "number"),
    # A number from no count and no text.
    ("Two strong trials of Strong Start measured diet quality in 12 schools.", "number"),
    ("Four evaluations measured diet quality at 6 months.", "number"),
    # A year.
    ("A 2019 trial of Strong Start measured diet quality.", "number"),
    # Invented places and programmes.
    ("Two strong trials in Manchester measured diet quality.", "name"),
    ("Two strong trials of Healthy Start measured diet quality.", "name"),
    ("Two trials in the UK measured diet quality.", "name"),
]


@pytest.mark.parametrize(("sentence", "verdict"), _VALID + _INVALID)
def test_the_seeded_fixture_set(sentence: str, verdict: str | None) -> None:
    assert (
        trace_check(sentence, _FIXED, plan_outcomes=_PLAN_OUTCOMES, vocabulary=_VOCABULARY)
        == verdict
    )


def test_strong_with_no_strong_document_fails() -> None:
    no_strong = _group(
        _doc("3", tier="Moderate", evidence_type="Local evaluation", programme_name="Change4Life"),
        _doc("4", evidence_type="Observational Research Studies"),
    )
    sentence = "One strong local evaluation of Change4Life measured physical activity."
    assert trace_check(sentence, no_strong, plan_outcomes=[], vocabulary={}) == "strength"
    sentence = "One moderate local evaluation of Change4Life measured physical activity."
    assert trace_check(sentence, no_strong, plan_outcomes=[], vocabulary={}) is None


def test_the_prompt_s_two_example_sentences_pass_on_their_own_places() -> None:
    four = _group(
        _doc(
            "a",
            tier="Strong",
            quality_score=4,
            evidence_type="Systematic Review and Meta-Analysis",
            measured="Prevalence of obesity at reception",
            tried_on_kind="children aged 4 to 11",
        ),
        _doc(
            "b",
            tier="Moderate",
            quality_score=3,
            evidence_type="Local evaluation",
            programme_name="Change4Life",
            study_geography="England",
            place_detail="England",
            measured="Prevalence of obesity at reception",
            tried_on_kind="children aged 4 to 11",
        ),
        _doc(
            "c",
            tier="Limited",
            quality_score=2,
            evidence_type="RCTs and Quasi-Experimental Studies",
            measured="diet quality",
            tried_on_kind="families",
        ),
        _doc(
            "d",
            evidence_type="Observational Research Studies",
            measured="physical activity",
            tried_on_kind="families",
        ),
    )
    assert (
        trace_check(
            "Four evaluations: a strong systematic review and a moderate local evaluation of "
            "Change4Life in England measured prevalence of obesity at reception in children "
            "aged 4 to 11; two others measured diet quality and physical activity in families.",
            four,
            plan_outcomes=["Prevalence of obesity at reception"],
            vocabulary={},
        )
        is None
    )
    henry = _group(
        _doc(
            "h",
            tier="Moderate",
            quality_score=3,
            evidence_type="Local evaluation",
            programme_name="HENRY",
            measured="diet quality",
            tried_on_kind="families with children under five",
        )
    )
    assert (
        trace_check(
            "One moderate local evaluation of HENRY measured diet quality in families with "
            "children under five.",
            henry,
            plan_outcomes=[],
            vocabulary={},
        )
        is None
    )


def test_the_stub_sentence_passes_the_trace_check() -> None:
    sentence = "4 evaluations in United Kingdom."
    assert trace_check(sentence, _FIXED, plan_outcomes=[], vocabulary={}) is None
    no_single = group_places([_doc("m", place="multiple countries")], where_country=None)[0]
    assert (
        trace_check("1 evaluations in No single place.", no_single, plan_outcomes=[], vocabulary={})
        is None
    )


def test_the_head_phrase_cuts_a_target_unit_at_its_qualifying_clause() -> None:
    from policy_atlas.options_scoping.option_profile.place_sentences import head_phrase

    long = "Children aged 4 to 11 living in the most deprived fifth of areas"
    assert head_phrase(long) == "Children aged 4 to 11"
    assert head_phrase("Adults granted refugee status in the last two years") == (
        "Adults granted refugee status"
    )
    firms = "Energy-intensive manufacturing firms"
    assert head_phrase(firms) == firms
    neet = "16 to 24 year olds not in education, employment or training"
    assert head_phrase(neet) == neet  # "not in …" is the head's own clause
    assert head_phrase("Young people not in work who live in Leeds") == "Young people not in work"
    assert head_phrase(None) is None
    doc = _doc(
        "a", tier="Strong", evidence_type="RCTs and Quasi-Experimental Studies", tried_on_kind=long
    )
    group = group_places([doc], where_country=None)[0]
    sentence = template_sentence(group, target_unit=long)
    assert sentence.startswith("1 strong trial with children aged 4 to 11")
