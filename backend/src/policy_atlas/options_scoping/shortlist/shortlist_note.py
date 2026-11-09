"""The shortlist's not-covered note, kept true to the places (task 058, round 14).

The shortlist step writes its note with its picks and, since round 14, the
places it was written against (``places_at`` in ``longlist_result.shortlist``).
The note has one writer, :func:`write_shortlist_note` and the
``shortlist_note`` step (owner, 2026-11-08: one implementation): the shortlist
step calls it after its picks, with the proposal's changes; when the reader
then adds or removes places by hand the note goes stale (:func:`note_stale`)
and ``POST /tasks/{id}/shortlist/note`` calls it again with no changes. It
reads the plan's outcomes, the option list and the places, never a document
line.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import longlist_result, option
from policy_atlas.options_scoping.shortlist.shortlist_note_prompt import (
    SHORTLIST_NOTE_MAX_CHARS,
    SHORTLIST_NOTE_PROMPT_VERSION,
)
from policy_atlas.options_scoping.text import clean_text

if TYPE_CHECKING:
    from policy_atlas.options_scoping.scoping_backend import LonglistBackend

log = structlog.get_logger()

#: The shortlist states that hold a place.
PLACE_STATES = ("proposed", "added_by_you")

#: What marks a link in the note; the card shows none (plan P5). The same
#: marks the proposal's reasons are checked for (``shortlist._LINK_MARKS``;
#: that module imports this one, so the tuple is not imported from there).
_LINK_MARKS = ("http://", "https://", "www.", "](")
#: A Markdown link, ``[words](address)``: its words are kept.
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def current_places(conn: Connection, task_id: uuid.UUID) -> list[uuid.UUID]:
    """The options now on the shortlist, in a stable order (name, then id)."""
    return list(
        conn.execute(
            select(option.c.option_id)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_(None))
            .where(option.c.shortlist_state.in_(PLACE_STATES))
            .order_by(option.c.name, option.c.option_id)
        ).scalars()
    )


def note_stale(shortlist: Mapping[str, Any], places: Iterable[uuid.UUID]) -> bool:
    """Whether the stored note was written against other places than these.

    A note stored without ``places_at`` (before round 14) counts as stale: the
    places it was written against are unknown. A proposal whose note failed
    (no note beside its provenance) is stale too, so a refresh can write it;
    with no proposal at all there is nothing to refresh.
    """
    note = shortlist.get("note")
    if not isinstance(note, str) or not note.strip():
        return bool(shortlist.get("provenance"))
    places_at = shortlist.get("places_at")
    if not isinstance(places_at, list):
        return True
    return {str(value) for value in places_at} != {str(value) for value in places}


def _note_inputs(
    conn: Connection, task_id: uuid.UUID, places: Sequence[uuid.UUID]
) -> tuple[list[dict[str, object]], list[str], dict[uuid.UUID, str]]:
    """The option list and the places, as the note call reads them.

    Options carry short ids (``o1 … oN``, in name order) so the call never
    sees a database id; the places use the same ids.
    """
    rows = conn.execute(
        select(
            option.c.option_id,
            option.c.name,
            option.c.primary_lever_type,
            option.c.secondary_lever_types,
            option.c.ambition,
            option.c.state,
            option.c.exclusion,
        )
        .where(option.c.task_id == task_id)
        .where(option.c.merged_into_option_id.is_(None))
        .order_by(option.c.name, option.c.option_id)
    ).all()
    short: dict[uuid.UUID, str] = {}
    options: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        short[row.option_id] = f"o{index}"
        secondary = row.secondary_lever_types if isinstance(row.secondary_lever_types, list) else []
        exclusion = row.exclusion if isinstance(row.exclusion, dict) else {}
        excluded = row.state == "excluded"
        options.append(
            {
                "id": short[row.option_id],
                "name": clean_text(row.name),
                "lever_types": [
                    value
                    for value in [row.primary_lever_type, *secondary]
                    if isinstance(value, str) and value
                ],
                "ambition": row.ambition,
                "excluded": excluded,
                "excluded_reason": clean_text(str(exclusion.get("reason") or "")) or None
                if excluded
                else None,
            }
        )
    return options, [short[place] for place in places if place in short], short


def without_links(text: str) -> str:
    """The note with every link taken out (plan P5: the card shows none).

    A Markdown link keeps its words; any other word carrying a link mark
    (``http://``, ``https://``, ``www.``) is dropped. Task 058 review: the
    proposal re-asked a note with a link once; the note's own step has no
    re-ask wording, so the link is taken out instead.
    """
    unlinked = _MARKDOWN_LINK.sub(r"\1", text)
    return " ".join(
        word
        for word in unlinked.split()
        if not any(mark in word.lower() for mark in _LINK_MARKS)
    )


def bounded_note(text: str) -> str:
    """The note as stored: cleaned onto plain text and cut to the bound on a word."""
    note = clean_text(text) or ""
    if len(note) <= SHORTLIST_NOTE_MAX_CHARS:
        return note
    cut = note[: SHORTLIST_NOTE_MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip()
    return f"{cut}…"


def write_shortlist_note(
    conn: Connection,
    task_id: uuid.UUID,
    backend: LonglistBackend,
    *,
    outcomes: Sequence[str],
    changes: Sequence[Mapping[str, object]] = (),
) -> str:
    """Write the not-covered note for the places as they stand, with the places.

    Runs the ``shortlist_note`` step and stores ``note`` and ``places_at`` on
    the latest ``longlist_result.shortlist``, beside what is there.

    Args:
        conn: The caller's transaction (it holds the task row lock).
        task_id: The options-scoping task.
        backend: The scoping backend (its ``shortlist_note``).
        outcomes: The plan's outcomes.
        changes: The proposal's changes when the shortlist step has just run:
            one per place added or removed (``option_id``, ``name``,
            ``change``: ``added`` | ``removed``, ``reason``); none on a refresh.

    Returns:
        The note written.

    Raises:
        LookupError: When the task has no longlist.
        Exception: The step's failure; nothing is written.
    """
    row = conn.execute(
        select(longlist_result.c.longlist_result_id, longlist_result.c.shortlist)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise LookupError(f"no longlist for task {task_id}")
    places = current_places(conn, task_id)
    options, short_places, short = _note_inputs(conn, task_id, places)
    data_changes = [
        {
            "id": short.get(uuid.UUID(str(change["option_id"])), str(change["option_id"])),
            "name": change.get("name"),
            "change": change.get("change"),
            "reason": change.get("reason"),
        }
        for change in changes
    ]
    wire, _usage = backend.shortlist_note(
        outcomes=list(outcomes), options=options, places=short_places, changes=data_changes
    )
    unlinked = without_links(wire.note)
    if unlinked != " ".join(wire.note.split()):
        log.warning("shortlist.note_link_removed", task_id=str(task_id))
    note = bounded_note(unlinked)
    stored = dict(row.shortlist) if isinstance(row.shortlist, Mapping) else {}
    conn.execute(
        longlist_result.update()
        .where(longlist_result.c.longlist_result_id == row.longlist_result_id)
        .values(
            shortlist={
                **stored,
                "note": note,
                "places_at": [str(place) for place in places],
                "note_prompt_version": SHORTLIST_NOTE_PROMPT_VERSION,
            }
        )
    )
    return note
