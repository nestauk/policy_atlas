"""The ``shortlist`` component: Policy Atlas proposes the places (task 055, items 3-5).

ADR 0041; plan P4-P8. The step reads every included option's card (the same
text the user sees), the plan, the baseline, the reader's risk appetite, the
reader's own places, the set-asides, one line per excluded option and the
previous proposal, and makes one judgment-model call
(:mod:`~policy_atlas.options_scoping.shortlist.shortlist_prompt`). It writes the
picks onto the option rows (``shortlist_state = "proposed"`` with a reason),
the note and how it was made onto the task's newest ``longlist_result``, and
one ``shortlist.proposed`` event that records the whole proposal.

It runs at the end of the longlist walk (after ``theme``) and alone in a
shortlist walk (an appetite change or Suggest more). It is not a spine step:
a :class:`ShortlistFailure` ends the walk ``degraded``, and the previous places
stay, because every write of the proposal happens after the model call. The
one earlier write is the clearing of picks whose option was since excluded or
merged (O1), which stands whatever the call does.

Code checks only the hard things (plan P5): every pick is a candidate, none
twice, exactly as many as asked, each reason and the note present and short
enough. A failed check re-asks once with the failures named; a second failure
raises.
"""

from __future__ import annotations

import dataclasses
import json
import random
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import event_log, longlist_result, option
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.longlist.longlist import latest_longlist
from policy_atlas.options_scoping.longlist.longlist_backend import (
    LONGLIST_JUDGMENT_MODEL,
    LonglistBackend,
)
from policy_atlas.options_scoping.shortlist.cards import fit_option_cards, option_cards
from policy_atlas.options_scoping.shortlist.shortlist_prompt import (
    NONE_LINE,
    SHORTLIST_NOTE_MAX_CHARS,
    SHORTLIST_NOTE_MIN_CHARS,
    SHORTLIST_PROMPT_VERSION,
    SHORTLIST_REASON_MAX_CHARS,
    ShortlistWire,
    build_shortlist_messages,
    reask_message,
)
from policy_atlas.options_scoping.suggest.suggest import baseline_sections, walk_plan
from policy_atlas.options_scoping.suggest.suggest_prompt import render_baseline_blocks
from policy_atlas.runtime.scoping_plan import RISK_APPETITE_LABELS, ScopingPlan

log = structlog.get_logger()

#: The places a proposal fills to (S6).
PLACES_TARGET = 5

#: The ceiling on the whole request, system prompt included, in characters
#: (about 100k tokens on the judgment model; A13, PG2). Over it, document
#: lines are cut; still over with none left, the proposal fails.
SHORTLIST_INPUT_CHARS_MAX = 400_000

#: The baseline text the proposal reads, at most (PG2).
SHORTLIST_BASELINE_MAX_CHARS = 20_000

#: The proposal's event: the record of each proposal (A7). Read back as the
#: previous proposal by the next one (a Rebuild inserts a fresh longlist row).
SHORTLIST_PROPOSED = "shortlist.proposed"

#: The two attempts: the call, and one re-ask with the failures named.
_ATTEMPTS = 2

#: How a place's state reads in the previous proposal's lines.
_STATE_WORDS = {"proposed": "Policy Atlas's pick", "added_by_you": "added by you"}

#: The ambition words, as the card says them (``LEVEL_WORDS.ambition``).
_AMBITION_WORDS = {"less": "Smaller", "more": "Bigger"}


class ShortlistFailure(Exception):
    """The proposal could not be made (no longlist, over the ceiling, failed checks)."""


def shuffled[T](items: Sequence[T], *, run_id: uuid.UUID, attempt: int) -> list[T]:
    """The candidates in the order the model reads them (S16).

    Seeded with ``"{run_id}:{attempt}"``, so a run's order can be reproduced.

    Args:
        items: The candidates, in a stable order.
        run_id: This ``shortlist`` run.
        attempt: The attempt the order is for.

    Returns:
        A new, shuffled list.
    """
    out = list(items)
    random.Random(f"{run_id}:{attempt}").shuffle(out)
    return out


def _clear_lost_picks(conn: Connection, task_id: uuid.UUID) -> int:
    """Clear Policy Atlas's picks whose option is now excluded or merged (O1).

    A reader's own place and a set-aside are never touched here.
    """
    cleared = conn.execute(
        option.update()
        .where(option.c.task_id == task_id)
        .where(option.c.shortlist_state == "proposed")
        .where(
            (option.c.state != "included") | option.c.merged_into_option_id.is_not(None)
        )
        .values(shortlist_state=None, shortlist_reason=None)
    )
    return int(cleared.rowcount or 0)


def _previous_proposal(conn: Connection, task_id: uuid.UUID) -> str:
    """The newest ``shortlist.proposed`` event as lines, or :data:`NONE_LINE`."""
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == SHORTLIST_PROPOSED)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping):
        return NONE_LINE
    lines = []
    for place in payload.get("places") or []:
        if not isinstance(place, Mapping):
            continue
        state = _STATE_WORDS.get(str(place.get("state")), str(place.get("state")))
        reason = str(place.get("reason") or "").strip() or "no reason"
        lines.append(f"{_one_line(place.get('name'))} — {state} — {_one_line(reason)}")
    note = str(payload.get("note") or "").strip()
    lines.append(f"Note: {_one_line(note)}" if note else "Note: none")
    return "\n".join(lines)


def _one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def _excluded_line(row: Any) -> str:
    """One excluded option: name · lever type · ambition · why excluded (A11)."""
    exclusion = row.exclusion if isinstance(row.exclusion, Mapping) else {}
    constraint = _one_line(exclusion.get("constraint"))
    reason = _one_line(exclusion.get("reason"))
    why = (
        f"{constraint}: {reason}"
        if constraint and reason
        else (constraint or reason or "no reason")
    )
    return " · ".join(
        [
            _one_line(row.name),
            _one_line(row.primary_lever_type or "no lever fits"),
            _AMBITION_WORDS.get(str(row.ambition), "Middle"),
            why,
        ]
    )


def _plan_json(plan: ScopingPlan) -> str:
    """The plan fields the proposal reads, as JSON text."""
    return json.dumps(
        {
            "question": plan.question,
            "intended_change": plan.intended_change.text,
            "target_unit": plan.target_unit.text,
            "where": plan.where.text,
            "outcomes": [outcome.text for outcome in plan.outcomes],
            "constraints": [
                {"kind": c.kind, "text": c.text, "limit": c.hard} for c in plan.constraints
            ],
            "your_context": [entry.text for entry in plan.your_context],
        },
        ensure_ascii=False,
        indent=2,
    )


def _cards_cut_note(kept: int, total: int) -> str:
    return f" (Policy Atlas read {kept} of {total} document lines)" if kept < total else ""


def _checks(
    wire: ShortlistWire,
    *,
    candidates: set[str],
    kept: set[str],
    set_aside: set[str],
    to_fill: int,
) -> list[str]:
    """The failed checks, in order, one plain line each (plan P5)."""
    failures: list[str] = []
    for pick in wire.picks:
        if pick.option_id in candidates:
            continue
        if pick.option_id in kept:
            failures.append(f"{pick.option_id} is one of the reader's own places (KEEP).")
        elif pick.option_id in set_aside:
            failures.append(f"{pick.option_id} was removed by the reader (DO NOT PROPOSE).")
        else:
            failures.append(f"{pick.option_id} is not a candidate id.")
    seen: set[str] = set()
    for pick in wire.picks:
        if pick.option_id in seen:
            failures.append(f"{pick.option_id} is proposed more than once.")
        seen.add(pick.option_id)
    if len(wire.picks) != to_fill:
        failures.append(f"{len(wire.picks)} picks, where exactly {to_fill} are asked for.")
    for pick in wire.picks:
        reason = pick.reason.strip()
        if not reason:
            failures.append(f"The reason for {pick.option_id} is empty.")
        elif len(reason) > SHORTLIST_REASON_MAX_CHARS:
            failures.append(
                f"The reason for {pick.option_id} is longer than "
                f"{SHORTLIST_REASON_MAX_CHARS} characters."
            )
    note = wire.note.strip()
    if len(note) < SHORTLIST_NOTE_MIN_CHARS:
        failures.append("The note is empty.")
    elif len(note) > SHORTLIST_NOTE_MAX_CHARS:
        failures.append(f"The note is longer than {SHORTLIST_NOTE_MAX_CHARS} characters.")
    return failures


def _input_chars(messages: Sequence[ChatCompletionMessageParam]) -> int:
    return sum(len(str(message.get("content") or "")) for message in messages)


def shortlist_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Propose the shortlist's places over every included option's card, and write them.

    The newest ``longlist_result`` of the task is read, whatever walk wrote
    it (a shortlist walk's own intent record has none; A5). At the end of a
    longlist walk and in an appetite walk (no ``suggest`` in the intent
    record's context) Policy Atlas's picks are released and refilled up to
    :data:`PLACES_TARGET` beside the reader's own places; with
    ``{"suggest": true}`` (Suggest more) the picks stay and the call fills up
    to five, or one more at five or above (S8).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``shortlist`` run.
        context: The walk's intent record.
        backend: The model seam (the longlist backend's proposal call).

    Returns:
        ``{"filled", "kept", "set_aside", "cleared", "input_chars",
        "document_lines_cut", "baseline_chars_cut", "attempts", "input_tokens",
        "output_tokens"}``; the runner adds ``"component": "shortlist"`` to the
        ``component.completed`` event.

    Raises:
        ShortlistFailure: If the task has no longlist, the request is over
            the ceiling with every document line cut, the proposal fails its
            checks twice, or the longlist changed while the call ran.
    """
    plan, plan_version = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)

    baseline_full = render_baseline_blocks(baseline_sections(conn, task_id))
    baseline_chars_cut = max(0, len(baseline_full) - SHORTLIST_BASELINE_MAX_CHARS)
    baseline_text = baseline_full[:SHORTLIST_BASELINE_MAX_CHARS]
    baseline_cut_note = (
        f", cut at {SHORTLIST_BASELINE_MAX_CHARS} characters ({baseline_chars_cut} not shown)"
        if baseline_chars_cut
        else ""
    )

    result_row = latest_longlist(conn, task_id=task_id)
    if result_row is None:
        raise ShortlistFailure("shortlist: no longlist exists for this task")

    cleared = _clear_lost_picks(conn, task_id)

    rows = list(
        conn.execute(
            select(option)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_(None))
            .order_by(option.c.created_at, option.c.option_id)
        )
    )
    included = [row for row in rows if row.state == "included"]
    kept_rows = sorted(
        (row for row in rows if row.shortlist_state == "added_by_you"), key=lambda r: r.name
    )
    set_aside_rows = sorted(
        (row for row in rows if row.shortlist_state == "set_aside"), key=lambda r: r.name
    )
    excluded_rows = sorted(
        (row for row in rows if row.state == "excluded" and row.shortlist_state != "added_by_you"),
        key=lambda r: r.name,
    )
    proposed_rows = [row for row in included if row.shortlist_state == "proposed"]

    suggest = bool(context.context.get("suggest"))
    if suggest:
        places = len(proposed_rows) + len(kept_rows)
        to_fill = PLACES_TARGET - places if places < PLACES_TARGET else 1
        candidate_rows = [row for row in included if row.shortlist_state is None]
    else:
        to_fill = max(0, PLACES_TARGET - len(kept_rows))
        candidate_rows = [
            row for row in included if row.shortlist_state not in ("added_by_you", "set_aside")
        ]

    cards = option_cards(
        conn,
        task_id=task_id,
        option_ids=[row.option_id for row in (*candidate_rows, *kept_rows)],
        today_year=datetime.now(UTC).year,
    )
    candidate_rows = [row for row in candidate_rows if row.option_id in cards]
    to_fill = min(to_fill, len(candidate_rows))

    ordered = shuffled(candidate_rows, run_id=run_id, attempt=1)
    candidate_ids = {f"o{i}": row for i, row in enumerate(ordered, start=1)}
    kept_ids = {
        f"k{i}": row for i, row in enumerate(kept_rows, start=1) if row.option_id in cards
    }
    set_aside_ids = {f"s{i}": row for i, row in enumerate(set_aside_rows, start=1)}

    labelled = [
        dataclasses.replace(cards[row.option_id], fixed=f"id: {sid}\n{cards[row.option_id].fixed}")
        for sid, row in (*kept_ids.items(), *candidate_ids.items())
    ]
    lines_total = sum(len(card.document_lines) for card in labelled)

    def messages_for(
        kept_block: str, candidates_block: str, cards_cut_note: str
    ) -> list[ChatCompletionMessageParam]:
        return build_shortlist_messages(
            to_fill=to_fill,
            appetite=plan.risk_appetite,
            appetite_label=RISK_APPETITE_LABELS[plan.risk_appetite],
            plan_json=_plan_json(plan),
            baseline_text=baseline_text,
            baseline_cut_note=baseline_cut_note,
            kept_block=kept_block,
            set_aside_block="\n".join(
                f"{sid} · {_one_line(row.name)}" for sid, row in set_aside_ids.items()
            )
            or NONE_LINE,
            excluded_block="\n".join(_excluded_line(row) for row in excluded_rows) or NONE_LINE,
            previous_block=_previous_proposal(conn, task_id),
            candidates_block=candidates_block,
            cards_cut_note=cards_cut_note,
        )

    # The fixed parts first (PR20): everything but the cards, with the longest
    # cut note the cards could need; what is left is the cards' budget.
    fixed_chars = _input_chars(messages_for("", "", ""))
    longest_note = len(_cards_cut_note(lines_total - 1, lines_total)) if lines_total else 0
    budget = SHORTLIST_INPUT_CHARS_MAX - fixed_chars - longest_note - 2 * len(NONE_LINE)
    texts, lines_cut = fit_option_cards(labelled, budget)
    kept_texts, candidate_texts = texts[: len(kept_ids)], texts[len(kept_ids) :]
    messages = messages_for(
        "\n\n".join(kept_texts) or NONE_LINE,
        "\n\n".join(candidate_texts) or NONE_LINE,
        _cards_cut_note(lines_total - lines_cut, lines_total),
    )
    input_chars = _input_chars(messages)
    if input_chars > SHORTLIST_INPUT_CHARS_MAX:
        raise ShortlistFailure("shortlist: input over ceiling")

    usage: list[dict[str, int]] = []
    request = messages
    attempts = 0
    wire: ShortlistWire | None = None
    failures: list[str] = []
    for attempt in range(1, _ATTEMPTS + 1):
        attempts = attempt
        started = time.monotonic()
        wire, tokens = backend.propose_shortlist(messages=request)
        usage.append(
            {
                "input_tokens": (tokens.prompt or 0) if tokens is not None else 0,
                "output_tokens": (tokens.completion or 0) if tokens is not None else 0,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        )
        failures = _checks(
            wire,
            candidates=set(candidate_ids),
            kept=set(kept_ids),
            set_aside=set(set_aside_ids),
            to_fill=to_fill,
        )
        if not failures:
            break
        log.warning("shortlist.checks_failed", attempt=attempt, failures=failures)
        # The re-ask keeps the first attempt's order and ids, so the failures
        # it names refer to the ids the model was shown.
        request = [
            *messages,
            {"role": "assistant", "content": wire.model_dump_json()},
            reask_message(failures=failures, to_fill=to_fill),
        ]
    if failures or wire is None:
        raise ShortlistFailure(
            "shortlist: the proposal failed its checks twice: " + " ".join(failures)
        )

    picks = [(candidate_ids[pick.option_id], pick.reason.strip()) for pick in wire.picks]

    # Lock late (PR25): the newest row, re-checked, then the one write.
    newest = conn.execute(
        select(longlist_result.c.longlist_result_id)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if newest != result_row.longlist_result_id:
        raise ShortlistFailure("shortlist: longlist changed")
    picked_ids = [row.option_id for row, _ in picks]
    still = (
        set(
            conn.execute(
                select(option.c.option_id)
                .where(option.c.task_id == task_id)
                .where(option.c.option_id.in_(picked_ids))
                .where(option.c.state == "included")
                .where(option.c.merged_into_option_id.is_(None))
            ).scalars()
        )
        if picked_ids
        else set()
    )
    if still != set(picked_ids):
        raise ShortlistFailure("shortlist: longlist changed")

    now = datetime.now(UTC)
    if not suggest:
        conn.execute(
            option.update()
            .where(option.c.task_id == task_id)
            .where(option.c.shortlist_state == "proposed")
            .values(shortlist_state=None, shortlist_reason=None, updated_at=now)
        )
    for row, reason in picks:
        conn.execute(
            option.update()
            .where(option.c.task_id == task_id, option.c.option_id == row.option_id)
            .values(shortlist_state="proposed", shortlist_reason=reason, updated_at=now)
        )
    note = wire.note.strip()
    model = LONGLIST_JUDGMENT_MODEL if backend.mode == "live" else "stub"
    provenance = {
        "prompt_version": SHORTLIST_PROMPT_VERSION,
        "model": model,
        "appetite": plan.risk_appetite,
        "plan_version": plan_version,
        "run_id": str(run_id),
        "input_chars": input_chars,
        "document_lines_cut": lines_cut,
        # Before any cut, so the view can say "read N of M document lines".
        "document_lines_total": lines_total,
        "baseline_chars_cut": baseline_chars_cut,
        "to_fill": to_fill,
        "attempts": attempts,
        "usage": usage,
    }
    conn.execute(
        longlist_result.update()
        .where(
            longlist_result.c.longlist_result_id == result_row.longlist_result_id,
            longlist_result.c.task_id == task_id,
        )
        .values(shortlist={"note": note, "provenance": provenance})
    )
    current_places = conn.execute(
        select(
            option.c.option_id,
            option.c.name,
            option.c.shortlist_state,
            option.c.shortlist_reason,
        )
        .where(option.c.task_id == task_id)
        .where(option.c.merged_into_option_id.is_(None))
        .where(option.c.shortlist_state.in_(("added_by_you", "proposed")))
        .order_by(option.c.shortlist_state, option.c.name)
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type=SHORTLIST_PROPOSED,
        payload={
            "actor": "agent",
            "places": [
                {
                    "option_id": str(place.option_id),
                    "name": place.name,
                    "state": place.shortlist_state,
                    "reason": place.shortlist_reason,
                }
                for place in current_places
            ],
            "note": note,
            "appetite": plan.risk_appetite,
            "plan_version": plan_version,
            "prompt_version": SHORTLIST_PROMPT_VERSION,
            "model": model,
            "run_id": str(run_id),
        },
    )
    # The runner writes ``component`` into the ``component.completed`` payload
    # itself (and logs it as a keyword), so the summary must not carry it.
    summary = {
        "filled": len(picks),
        "kept": len(kept_rows),
        "set_aside": len(set_aside_rows),
        "cleared": cleared,
        "input_chars": input_chars,
        "document_lines_cut": lines_cut,
        "baseline_chars_cut": baseline_chars_cut,
        "attempts": attempts,
        "input_tokens": sum(entry["input_tokens"] for entry in usage),
        "output_tokens": sum(entry["output_tokens"] for entry in usage),
    }
    log.info("shortlist.done", **summary)
    return summary

