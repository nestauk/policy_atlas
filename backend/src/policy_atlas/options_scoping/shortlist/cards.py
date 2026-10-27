"""The option cards the shortlist proposal reads (task 055, P4, P7).

A thin bridge to the read model: the card text is built from the same
``OptionOut`` the option card renders (S13). The read-model package imports
the options-scoping package at module import time, so this module imports it
lazily, inside the function, and the scoping package never imports
``policy_atlas.api`` when it loads.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy.engine import Connection

if TYPE_CHECKING:
    from policy_atlas.api.readmodels.card_text import CardText


def option_cards(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_ids: Sequence[uuid.UUID],
    today_year: int,
) -> dict[uuid.UUID, CardText]:
    """Build each option's card text from its card read model.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options, unmerged.
        today_year: The current year, for the maturity rung's modifier.

    Returns:
        The card text by option id; an option the read model cannot find is
        left out.
    """
    from policy_atlas.api.readmodels import repository
    from policy_atlas.api.readmodels.card_text import option_card_text

    cards: dict[uuid.UUID, CardText] = {}
    for option_id in option_ids:
        card = repository.option_out(conn, task_id, option_id)
        if card is not None:
            cards[option_id] = option_card_text(card, today_year=today_year)
    return cards


def fit_option_cards(cards: Sequence[CardText], budget: int) -> tuple[list[str], int]:
    """Fit the cards under the budget (:func:`~policy_atlas.api.readmodels.card_text.fit_cards`).

    Args:
        cards: The cards, in the order the request lists them.
        budget: The characters the cards may take.

    Returns:
        The rendered cards and the number of document lines cut.
    """
    from policy_atlas.api.readmodels.card_text import fit_cards

    return fit_cards(cards, budget)
