"""The option card as text (task 055, P7; contract A12, A13).

The golden test renders one ``OptionOut`` with every conditional block and
checks each block's words appear exactly once, and that no link material
(ids, URLs) and none of the left-out blocks reach the text. The cut tests
check :func:`fit_cards`: nothing is cut under the budget; over it, one
document line per card per round, oldest year first, counted.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from policy_atlas.api.contract.read_models import OptionOut
from policy_atlas.api.readmodels.card_text import CardText, fit_cards, option_card_text

_FIXTURE = Path(__file__).parent / "fixtures" / "option_out_full.json"


def _fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_FIXTURE.read_text())
    return data


def _text() -> str:
    return option_card_text(OptionOut.model_validate(_fixture()), today_year=2026).render()


@pytest.mark.parametrize(
    "words",
    [
        # Header: name, description, lever, origin, relation, also found as, signal.
        "## Wage subsidy for first jobs",
        "Employers receive part of a young recruit's wage for six months.",
        "Subsidise · from your evidence search · Employer incentives section",
        "part of Youth guarantee package",
        "also found as: Hiring subsidy",
        "2 documents evaluated it · 1 more describe it · Evaluated in the United Kingdom "
        "and Denmark · Measures 1 of your 2 outcomes",
        # The two lines, in their words.
        "none of its 3 documents pass documents published after 2015. It stays on the "
        "longlist until the scope changes.",
        "Its own evidence search is still running.",
        # The constraint callouts, in words.
        'Breaks "Must cost under 10 million a year". A national scheme costs more.',
        'Cannot check "Must start within a year". Set-up time is not stated.',
        'May fall short: "Prefer low admin". Claims add some admin for employers.',
        'Cannot check "Prefer local delivery". Delivery is national.',
        # How it works.
        "### How it works",
        "Lever: Subsidise, with Regulate.",
        "Pays employers to take on young recruits.",
        "Delivered at work. It typically involves:",
        "- Six-month wage top-up",
        # What it would take: ambition, the nine lines, marks only where present.
        "### What it would take",
        "Ambition: Covers every young jobseeker nationally. (Bigger)",
        "Cost: Costs about a fifth of a wage per recruit. (Costlier)",
        "Time to set up: Needs a payment scheme set up.\n",
        "Time to effect: Hiring responds within months. (Quicker)",
        "Workforce requirements: Needs a small claims team.\n",
        "Who decides: The employment ministry sets the scheme. (Needs action by the Treasury)",
        "Dependencies: Depends on employers taking it up.\n",
        "Coordination requirements: Needs the tax office to share wage data. (Higher)",
        "Delivery complexity: Simple claims, but fraud checks. (Simpler)",
        "Potential impact: Moderate if it works: more first jobs through lower hiring costs.\n",
        # Evidence: opener, your outcomes, place sentences, the rung and modifiers.
        "### Evidence",
        "Evaluated in 2 documents. 1 more describes or recommends it.",
        "- the NEET rate: 2 evaluations",
        "- earnings at age 25: none · not a target of this option",
        "- United Kingdom: One trial with young jobseekers in Manchester.",
        "- Denmark: One national evaluation of unemployed youth.",
        "Maturity: Evaluated · 1 RCT, 1 Quasi-experimental · none in your setting · "
        "most recent evaluation before 2021",
        # The document lines.
        "Documents · 3 · read from titles and abstracts only",
        "- Randomised trial of hiring subsidies · Kickstart · United Kingdom (Manchester) · "
        "young jobseekers · the NEET rate · High · RCT · 2012 (evaluated it)",
        "- Danish wage subsidy evaluation · Denmark · unemployed youth · employment · "
        "Moderate · Quasi-experimental (evaluated it)",
        "- Policy brief on youth hiring · 2020 (describes or recommends it)",
    ],
)
def test_every_block_of_the_card_appears_once(words: str) -> None:
    assert _text().count(words) == 1


def test_no_link_and_no_left_out_block_reaches_the_text() -> None:
    text = _text()
    fixture = _fixture()
    ids = [
        fixture["option_id"],
        fixture["run_id"],
        fixture["capability_run_id"],
        *(r["other_option_id"] for r in fixture["relations"]),
        *(
            d["task_source_snapshot_id"]
            for d in fixture["documents"]
            if d["task_source_snapshot_id"]
        ),
    ]
    for value in ids:
        assert str(uuid.UUID(value)) not in text
    assert "http" not in text
    # The exclusion block, the place on the shortlist, passes and built-in checks.
    for hidden in (
        "Zanzibar",
        "Quokka",
        "Narwhal",
        "Ocelot",
        "Lemur",
        "Built-in check",
        "Hidden programme",  # a linked finding's programme is not shown
    ):
        assert hidden not in text


def test_a_card_with_no_profile_and_no_documents_says_so() -> None:
    data = _fixture() | {
        "profile": None,
        "documents": [],
        "document_count": 0,
        "evaluated_count": 0,
        "place_sentences": [],
        "maturity": {"rung": "proposal_only"},
    }
    card = option_card_text(OptionOut.model_validate(data), today_year=2026)
    assert "### What it would take" not in card.fixed
    assert "No document names this option yet." in card.fixed
    assert "Maturity: Proposal only" in card.fixed
    assert card.document_lines == []


# --- the cut -----------------------------------------------------------------------------


def _card(name: str, years: list[int | None]) -> CardText:
    return CardText(
        fixed=f"## {name}",
        document_lines=[(year, f"- {name} doc {year}") for year in years],
    )


def test_nothing_is_cut_under_the_budget() -> None:
    cards = [_card("A", [2010, 2020]), _card("B", [None])]
    texts, cut = fit_cards(cards, budget=10_000)
    assert cut == 0
    assert texts == [card.render() for card in cards]


def test_the_cut_is_oldest_first_one_per_card_per_round_and_counted() -> None:
    a = _card("A", [2020, 2010, 2015])
    b = _card("B", [2018, None])
    full = sum(len(card.render()) for card in (a, b)) + 2
    # Room for everything but three lines: round 1 cuts A's 2010 and B's None,
    # round 2 cuts A's 2015.
    a_2010 = len("\n- A doc 2010")
    b_none = len("\n- B doc None")
    a_2015 = len("\n- A doc 2015")
    texts, cut = fit_cards([a, b], budget=full - a_2010 - b_none - a_2015)
    assert cut == 3
    assert texts == ["## A\n- A doc 2020", "## B\n- B doc 2018"]
    # One line over the budget cuts exactly one line: the first card's oldest.
    texts, cut = fit_cards([a, b], budget=full - 1)
    assert cut == 1
    assert "- A doc 2010" not in texts[0] and texts[1] == b.render()


def test_with_every_line_cut_the_texts_are_returned_for_the_caller_to_refuse() -> None:
    texts, cut = fit_cards([_card("A", [2001]), _card("B", [2002])], budget=1)
    assert cut == 2
    assert texts == ["## A", "## B"]
