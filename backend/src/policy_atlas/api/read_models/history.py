"""The History sentences: one plain line per recorded act (task 058, round 10).

The History tab is the record a reader audits, so each line says what
happened, to what, and who did it: "Screening finished: 118 of 435
relevant.", "Ada Lovelace chose “Looks right, assess these” at the
check-in.", "You renamed the task to “School meals”.".

Who did it is resolved here, per reader. A person's act reads "You" only for
that person; everyone else sees the person's display name (never an email,
:mod:`policy_atlas.api.identity`). Policy Atlas's own acts are named
"Policy Atlas"; a step's line needs no subject. The stage words come from
:mod:`policy_atlas.api.stage_vocabulary`, the one place the run page's stage
copy lives, so History and the run page name a step the same way.

All functions here are pure apart from :class:`People`, which reads the
names it needs in one query.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.stage_vocabulary import STAGE_COUNTS, STAGE_PRESENTATION, stage_for_payload
from policy_atlas.core.schema import app_user, task

#: The subject of Policy Atlas's own acts.
POLICY_ATLAS = "Policy Atlas"

#: How many search queries a History line quotes before "and N more".
QUERIES_NAMED = 5

#: Stored ``actor`` words that name a role, not a person. Rows written before
#: task 038 (and some fixtures) carry the bare word ``user``: the act was the
#: task owner's, the only person who may write a task.
_ROLE_WORDS_FOR_OWNER = frozenset({"user"})
_ROLE_WORDS_FOR_SYSTEM = frozenset({"agent", "orchestrator", "standing_default"})

#: The singular of each count noun in :data:`STAGE_COUNTS` that has one; the
#: other nouns ("found", "relevant", "collected") read the same for 1.
_SINGULAR = {
    "themes": "theme",
    "findings": "finding",
    "groups": "group",
    "sections": "section",
    "documents": "document",
    "options": "option",
    "searches": "search",
    "sources": "source",
    "abstracts": "abstract",
    "places": "place",
    "queries": "query",
}


@dataclass(frozen=True)
class Actor:
    """Who did something, as one reader is shown it.

    Args:
        subject: The sentence's subject: "You", a display name, or
            "Policy Atlas".
        display: The person's display name, or ``None`` for Policy Atlas's
            acts and ownerless rows.
        is_viewer: Whether the person is the reader.
    """

    subject: str
    display: str | None
    is_viewer: bool


SYSTEM = Actor(subject=POLICY_ATLAS, display=None, is_viewer=False)


class People:
    """The people one task's History names, read once.

    Args:
        conn: Open database connection.
        task_id: The task whose History is read.
        viewer_user_id: The reader's token subject, or ``None`` when no
            reader is known (then nobody reads as "You").
        actor_ids: Every person id the History's payloads carry.
    """

    def __init__(
        self,
        conn: Connection,
        task_id: uuid.UUID,
        viewer_user_id: str | None,
        actor_ids: Collection[str],
    ) -> None:
        self._viewer = viewer_user_id
        self._owner = conn.execute(
            select(task.c.owner_user_id).where(task.c.task_id == task_id)
        ).scalar_one_or_none()
        wanted = {
            actor
            for actor in actor_ids
            if actor not in _ROLE_WORDS_FOR_OWNER | _ROLE_WORDS_FOR_SYSTEM
        }
        if self._owner is not None:
            wanted.add(self._owner)
        self._names: dict[str, str] = (
            {
                user_id: name
                for user_id, name in conn.execute(
                    select(app_user.c.user_id, app_user.c.display_name).where(
                        app_user.c.user_id.in_(wanted)
                    )
                )
            }
            if wanted
            else {}
        )

    def actor(self, actor_id: object) -> Actor:
        """Resolve a stored actor to the subject this reader is shown.

        Args:
            actor_id: The payload's ``actor`` value. ``None`` or the bare
                word ``user`` reads as the task owner; ``agent`` as Policy
                Atlas.

        Returns:
            The actor as this reader sees it.
        """
        if isinstance(actor_id, str) and actor_id in _ROLE_WORDS_FOR_SYSTEM:
            return SYSTEM
        person = (
            actor_id
            if isinstance(actor_id, str) and actor_id and actor_id not in _ROLE_WORDS_FOR_OWNER
            else self._owner
        )
        if person is None:
            return Actor(subject="Someone", display=None, is_viewer=False)
        display = owner_display_for(person, self._names.get(person))
        if person == self._viewer:
            return Actor(subject="You", display=display, is_viewer=True)
        return Actor(subject=display or "Someone", display=display, is_viewer=False)


def _counted(value: int, noun: str) -> str:
    """``118 sources``, ``1 source``: a count with its noun."""
    return f"{value:,} {_SINGULAR.get(noun, noun) if value == 1 else noun}"


def _int(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _step_label(payload: Mapping[str, Any]) -> str | None:
    """The step's run-page label, or ``None`` when the step has no public stage."""
    if payload.get("component") == "screen_full":
        # The full-text screen shares the Screening row on the run page; here
        # it needs its own words, or two "Screening finished" lines read as a
        # repeat.
        return "Screening the full texts"
    stage = stage_for_payload(dict(payload))
    return STAGE_PRESENTATION[stage][0] if stage is not None else None


def _step_counts(payload: Mapping[str, Any]) -> str | None:
    """The count clause of a finished step: ``118 of 435 relevant``."""
    component = payload.get("component")
    if component in {"screen", "screen_full"}:
        relevant = _int(payload, "relevant")
        if relevant is None:
            return None
        screened = _int(payload, "screened")
        if screened is None:
            not_relevant = _int(payload, "not_relevant")
            screened = relevant + not_relevant if not_relevant is not None else None
        return (
            f"{relevant:,} of {screened:,} relevant"
            if screened is not None
            else f"{relevant:,} relevant"
        )
    stage = stage_for_payload(dict(payload))
    if stage == "acquire":
        acquired = _int(payload, "acquired")
        return f"{_counted(acquired, 'sources')} found" if acquired is not None else None
    if stage == "classify":
        classified = _int(payload, "classified")
        return _counted(classified, "sources") if classified is not None else None
    if stage == "ingest":
        ingested = _int(payload, "ingested")
        if ingested is None:
            return None
        failed = (_int(payload, "fetch_failed") or 0) + (_int(payload, "parse_failed") or 0)
        return f"{ingested:,} collected" + (f", {failed:,} failed" if failed else "")
    if stage is None:
        return None
    parts = [
        _counted(value, noun)
        for key, noun in STAGE_COUNTS.get(stage, ())
        if (value := _int(payload, key)) is not None
    ]
    return ", ".join(parts) if parts else None


def step_sentence(event_type: str, payload: Mapping[str, Any]) -> str:
    """One line for a step's end: finished with its counts, skipped, or failed.

    Args:
        event_type: ``component.completed``, ``component.skipped`` or
            ``component.failed``.
        payload: The event's payload.

    Returns:
        E.g. "Screening finished: 118 of 435 relevant.", "Shortlisting
        skipped.", "Writing didn't complete.".
    """
    label = _step_label(payload)
    if event_type == "component.skipped":
        return f"{label} skipped." if label else "A step was skipped."
    if event_type == "component.failed":
        return f"{label} didn't complete." if label else "A step didn't complete."
    if label is None:
        return "A step finished."
    counts = _step_counts(payload)
    return f"{label} finished: {counts}." if counts else f"{label} finished."


def search_sentence(queries: Sequence[str]) -> str:
    """One line for a run's searches, quoting the first few queries.

    Args:
        queries: The distinct queries, in the order they were sent.

    Returns:
        E.g. "Searched with 55 queries: “a”, “b”, “c”, “d”, “e” and 50 more."
    """
    count = len(queries)
    if count == 0:
        return "Searched the databases."
    quoted = [f"“{query}”" for query in queries[:QUERIES_NAMED]]
    rest = count - len(quoted)
    if rest > 0:
        listed = f"{', '.join(quoted)} and {rest:,} more"
    elif len(quoted) > 1:
        listed = f"{', '.join(quoted[:-1])} and {quoted[-1]}"
    else:
        listed = quoted[0]
    return f"Searched with {_counted(count, 'queries')}: {listed}."


def run_sentence(event_type: str, payload: Mapping[str, Any]) -> str:
    """One line for a run opening, parking or ending.

    Args:
        event_type: ``run.opened``, ``run.parked``, ``run.finished`` or
            ``run.interrupted``.
        payload: The event's payload (``status`` on ``run.finished``).

    Returns:
        The line, with Policy Atlas as the subject where it acted.
    """
    if event_type == "run.opened":
        return f"{POLICY_ATLAS} started the run."
    if event_type == "run.parked":
        return f"{POLICY_ATLAS} paused for a check-in."
    if event_type == "run.interrupted":
        return "The run was interrupted."
    status = payload.get("status")
    if status == "failed":
        return "The run didn't complete."
    if status == "aborted":
        return "The run was stopped."
    if status == "interrupted":
        return "The run was interrupted."
    return f"{POLICY_ATLAS} finished the run."


def lifecycle_sentence(kind: str, payload: Mapping[str, Any], actor: Actor) -> str:
    """One line for a rename, archive or public-sharing change.

    Args:
        kind: The bare lifecycle kind (``renamed``, ``archived``,
            ``shared_publicly``, ``unshared``).
        payload: The event's payload (``name_to`` on a rename).
        actor: Who did it.

    Returns:
        E.g. "You renamed the task to “School meals”.".
    """
    if kind == "renamed":
        name = payload.get("name_to")
        if isinstance(name, str) and name.strip():
            return f"{actor.subject} renamed the task to “{name.strip()}”."
        return f"{actor.subject} renamed the task."
    return {
        "archived": f"{actor.subject} archived the task.",
        "shared_publicly": f"{actor.subject} made the task public.",
        "unshared": f"{actor.subject} stopped sharing the task publicly.",
    }[kind]


def option_sentence(verb: str, name: str, reason: object, actor: Actor) -> str:
    """One line for a person's change to the longlist or shortlist.

    Args:
        verb: ``added``, ``excluded``, ``included``, ``shortlisted``,
            ``unshortlisted`` or ``gave a reason``.
        name: The option's name.
        reason: The reason given, if any (kept on an exclusion line).
        actor: Who did it.

    Returns:
        E.g. "You excluded the option “Mentoring”: too costly".
    """
    subject = actor.subject
    if verb == "gave a reason":
        # A reason after the person's own exclusion (round 13): its own line.
        words = str(reason or "").strip()
        return f"{subject} gave a reason for setting aside \u201c{name}\u201d: {words}"
    if verb == "shortlisted":
        return f"{subject} added “{name}” to the shortlist."
    if verb == "unshortlisted":
        return f"{subject} removed “{name}” from the shortlist."
    again = " again" if verb == "included" else ""
    sentence = f"{subject} {verb} the option “{name}”{again}."
    if isinstance(reason, str) and reason.strip():
        sentence = f"{sentence[:-1]}: {reason.strip()}"
    return sentence


def check_in_sentence(payload: Mapping[str, Any], option_label: str | None, actor: Actor) -> str:
    """One line for a check-in answer: what was chosen, and by whom.

    Args:
        payload: The ``steering.decision`` payload.
        option_label: The chosen option's label as the card showed it, when
            the decision names one.
        actor: Who answered (Policy Atlas for a routed or standing answer).

    Returns:
        E.g. "You chose “Looks right, assess these” at the check-in.".
    """
    subject = actor.subject
    decided_by = payload.get("decided_by")
    if decided_by == "standing_default":
        return f"{POLICY_ATLAS} applied the standing choice at the check-in."
    if option_label:
        return f"{subject} chose “{option_label}” at the check-in."
    if payload.get("confirmed") is False:
        return f"{subject} declined the proposed change at the check-in."
    user_text = payload.get("user_text")
    if isinstance(user_text, str) and user_text.strip():
        return f"{subject} asked for a change at the check-in: “{user_text.strip()}”."
    response = payload.get("response")
    if response == "abort":
        return f"{subject} stopped the run at the check-in."
    if response in {"adjust", "mode_change"}:
        return f"{subject} changed the plan at the check-in."
    if actor is SYSTEM:
        return f"{POLICY_ATLAS} answered the check-in."
    return f"{subject} carried on from the check-in."


def option_labels(pause_payload: Mapping[str, Any]) -> dict[str, str]:
    """Option id → label, as a check-in card offered them.

    Args:
        pause_payload: A ``steering.pause`` payload.

    Returns:
        The labels by option id; an option with no label is left out.
    """
    options = pause_payload.get("options")
    if not isinstance(options, list):
        return {}
    return {
        option["id"]: option["label"]
        for option in options
        if isinstance(option, Mapping)
        and isinstance(option.get("id"), str)
        and isinstance(option.get("label"), str)
        and option["label"].strip()
    }
