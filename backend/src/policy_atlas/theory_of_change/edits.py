"""The user's edits to a theory of change, their History and Undo (task 054, C41, C47, C10).

Every edit is one transaction: it checks the revision the client saw (C10),
writes through :mod:`~policy_atlas.theory_of_change.store`, stamps who edited
and when (``edited_by``, a user id resolved to a name on read), and records
one ``toc.changed`` event with step ``user_edit``, the actor and a
plain-language line. The event's before-states are what Undo puts back.

A delete records the rows the database removes with it (a box's links; a
link's pathway steps, judgements and figures), so Undo restores the evidence
too. Undo applies an event's before-state only to rows nobody changed since:
a row edited later is skipped and named, never overwritten (C10).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Table, select
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    app_user,
    event_log,
    toc_box,
    toc_figure,
    toc_item_evidence,
    toc_link,
    toc_pathway_link,
)
from policy_atlas.theory_of_change import store

#: The step name of every user edit's ``toc.changed`` event.
USER_EDIT = "user_edit"

#: Box fields a user may edit. ``result_criteria`` holds definition and timing.
BOX_FIELDS = frozenset({"text", "layer", "description", "indicator", "result_criteria"})
#: Link fields a user may edit.
LINK_FIELDS = frozenset(
    {"title", "if_text", "for_text", "then_text", "because_text", "conditions", "sentence"}
)
LAYERS = frozenset(store.CODE_PREFIX)

#: Tables in the order Undo re-inserts deleted rows (parents first).
_RESTORE_ORDER = ("toc_box", "toc_link", "toc_pathway_link", "toc_item_evidence", "toc_figure")
_TABLES: dict[str, Table] = {
    "toc_box": toc_box,
    "toc_link": toc_link,
    "toc_pathway_link": toc_pathway_link,
    "toc_item_evidence": toc_item_evidence,
    "toc_figure": toc_figure,
}


class EditRefused(Exception):
    """An edit that cannot apply: a stale revision (409) or an invalid request (422)."""

    def __init__(self, code: str, message: str, *, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class Actor:
    """Who made an edit: the user's token subject."""

    user_id: str


def _now() -> datetime:
    return datetime.now(UTC)


def _row(conn: Connection, table: Table, row_id: uuid.UUID, task_id: uuid.UUID) -> Any:
    key = table.c[store._PRIMARY_KEY[table.name]]
    row = conn.execute(select(table).where(key == row_id, table.c.task_id == task_id)).one_or_none()
    if row is None:
        raise EditRefused("toc_not_found", "that element is not in this theory", status=404)
    return row


def _stale(row: Any, expected_revision: int) -> None:
    if row.revision != expected_revision:
        raise EditRefused(
            "toc_stale_revision",
            "someone changed this since you opened it; reload to see their change",
        )


def _record(
    conn: Connection, *, task_id: uuid.UUID, actor: Actor, log: store.ChangeLog, change: str
) -> None:
    store.record(
        conn,
        task_id=task_id,
        run_id=None,
        step=USER_EDIT,
        log=log,
        changes=[change],
        actor=actor.user_id,
    )


def _update(
    conn: Connection,
    log: store.ChangeLog,
    table: Table,
    row: Any,
    *,
    actor: Actor,
    values: dict[str, Any],
) -> None:
    key = getattr(row, store._PRIMARY_KEY[table.name])
    stamp = {"edited_by": actor.user_id, "edited_at": _now()} if "edited_by" in table.c else {}
    if not store.update(
        conn, log, table, key, observed_revision=row.revision, values={**values, **stamp}
    ):
        raise EditRefused(
            "toc_stale_revision",
            "someone changed this since you opened it; reload to see their change",
        )


def _label(row: Any) -> str:
    return row.code or (row.text[:40] if hasattr(row, "text") else "a connection")


def edit_box(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    box_id: uuid.UUID,
    expected_revision: int,
    fields: dict[str, Any],
) -> None:
    """Change a box's text, layer, description, indicator or result criteria.

    Raises:
        EditRefused: On a stale revision, an unknown field or layer.
    """
    unknown = set(fields) - BOX_FIELDS
    if unknown:
        raise EditRefused("toc_invalid", f"cannot edit {sorted(unknown)}", status=422)
    if "layer" in fields and fields["layer"] not in LAYERS:
        raise EditRefused("toc_invalid", f"no layer {fields['layer']!r}", status=422)
    if "text" in fields and not str(fields["text"]).strip():
        raise EditRefused("toc_invalid", "a box needs text", status=422)
    row = _row(conn, toc_box, box_id, task_id)
    _stale(row, expected_revision)
    log = store.ChangeLog()
    _update(conn, log, toc_box, row, actor=actor, values=fields)
    _record(
        conn,
        task_id=task_id,
        actor=actor,
        log=log,
        change=f"Edited {_label(row)}: {', '.join(sorted(fields))}",
    )


def edit_link(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    link_id: uuid.UUID,
    expected_revision: int,
    fields: dict[str, Any],
) -> None:
    """Change a link's title, its if, for, then and because, or its conditions.

    The sentence is rebuilt from the four parts unless it is given.

    Raises:
        EditRefused: On a stale revision or an unknown field.
    """
    unknown = set(fields) - LINK_FIELDS
    if unknown:
        raise EditRefused("toc_invalid", f"cannot edit {sorted(unknown)}", status=422)
    row = _row(conn, toc_link, link_id, task_id)
    _stale(row, expected_revision)
    parts = {
        name: fields.get(name, getattr(row, name))
        for name in ("if_text", "for_text", "then_text", "because_text")
    }
    values = dict(fields)
    if "sentence" not in fields and set(parts) & set(fields):
        values["sentence"] = sentence_of(**parts)
    log = store.ChangeLog()
    _update(conn, log, toc_link, row, actor=actor, values=values)
    _record(
        conn,
        task_id=task_id,
        actor=actor,
        log=log,
        change=f"Edited {_label(row)}: {', '.join(sorted(fields))}",
    )


def sentence_of(*, if_text: str, for_text: str, then_text: str, because_text: str) -> str:
    """'If …, then …, because ….' from a link's parts (the for clause stays on its own)."""
    sentence = f"If {if_text.strip().rstrip('.,')}, then {then_text.strip().rstrip('.,')}"
    if because_text.strip():
        sentence += f", because {because_text.strip().rstrip('.')}"
    return sentence + "."


def create_box(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    layer: str,
    text: str,
    position: dict[str, float] | None = None,
) -> uuid.UUID:
    """Add a box the user wrote. It has no evidence until a check finds some (C41).

    Raises:
        EditRefused: On an unknown layer or empty text.
    """
    if layer not in LAYERS:
        raise EditRefused("toc_invalid", f"no layer {layer!r}", status=422)
    if not text.strip():
        raise EditRefused("toc_invalid", "a box needs text", status=422)
    box_id = uuid.uuid4()
    log = store.ChangeLog()
    store.insert(
        conn,
        log,
        toc_box,
        {
            "box_id": box_id,
            "task_id": task_id,
            "layer": layer,
            "text": text.strip(),
            "result_criteria": {},
            "origin": "user",
            "user_edited": True,
            "position": position,
            "edited_by": actor.user_id,
            "edited_at": _now(),
        },
    )
    code = conn.execute(select(toc_box.c.code).where(toc_box.c.box_id == box_id)).scalar_one()
    _record(conn, task_id=task_id, actor=actor, log=log, change=f"Added box {code}")
    return box_id


def create_link(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    source_box_id: uuid.UUID,
    target_box_id: uuid.UUID,
    for_text: str = "",
) -> uuid.UUID:
    """Connect two boxes. The sentence starts from the two box texts; the user edits it.

    Raises:
        EditRefused: When a box is missing, the two are the same, or they are
            already connected.
    """
    if source_box_id == target_box_id:
        raise EditRefused("toc_invalid", "a box cannot lead to itself", status=422)
    source = _row(conn, toc_box, source_box_id, task_id)
    target = _row(conn, toc_box, target_box_id, task_id)
    exists = conn.execute(
        select(toc_link.c.link_id).where(
            toc_link.c.task_id == task_id,
            toc_link.c.source_box_id == source_box_id,
            toc_link.c.target_box_id == target_box_id,
        )
    ).first()
    if exists is not None:
        raise EditRefused("toc_duplicate", "these two boxes are already connected", status=409)
    parts = {
        "if_text": source.text,
        "for_text": for_text,
        "then_text": target.text,
        "because_text": "",
    }
    link_id = uuid.uuid4()
    log = store.ChangeLog()
    store.insert(
        conn,
        log,
        toc_link,
        {
            "link_id": link_id,
            "task_id": task_id,
            "source_box_id": source_box_id,
            "target_box_id": target_box_id,
            **parts,
            "sentence": sentence_of(**parts),
            "conditions": [],
            "origin": "user",
            "user_edited": True,
            "edited_by": actor.user_id,
            "edited_at": _now(),
        },
    )
    code = conn.execute(select(toc_link.c.code).where(toc_link.c.link_id == link_id)).scalar_one()
    _record(
        conn,
        task_id=task_id,
        actor=actor,
        log=log,
        change=f"Added connection {code} ({source.code} → {target.code})",
    )
    return link_id


def _snapshot(
    conn: Connection, log: store.ChangeLog, table: Table, column: str, ids: list[uuid.UUID]
) -> None:
    """Keep the rows a delete will cascade away, so Undo can put them back."""
    if not ids:
        return
    for row in conn.execute(select(table).where(table.c[column].in_(ids))):
        log.before.append({"table": table.name, "row": store.row_state(row), "deleted": True})


def _delete_links(conn: Connection, log: store.ChangeLog, link_ids: list[uuid.UUID]) -> None:
    # Children first in the log: Undo restores in _RESTORE_ORDER whatever the log order.
    for table in (toc_pathway_link, toc_item_evidence, toc_figure):
        _snapshot(conn, log, table, "link_id", link_ids)
    for link_id in link_ids:
        store.delete(conn, log, toc_link, link_id)


def delete_link(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    link_id: uuid.UUID,
    expected_revision: int,
) -> None:
    """Delete a link, its pathway steps, judgements and figures (all restorable by Undo)."""
    row = _row(conn, toc_link, link_id, task_id)
    _stale(row, expected_revision)
    log = store.ChangeLog()
    _delete_links(conn, log, [link_id])
    _record(conn, task_id=task_id, actor=actor, log=log, change=f"Deleted connection {row.code}")


def delete_box(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    box_id: uuid.UUID,
    expected_revision: int,
) -> None:
    """Delete a box and every link in or out of it (all restorable by Undo)."""
    row = _row(conn, toc_box, box_id, task_id)
    _stale(row, expected_revision)
    log = store.ChangeLog()
    link_ids = list(
        conn.execute(
            select(toc_link.c.link_id).where(
                toc_link.c.task_id == task_id,
                (toc_link.c.source_box_id == box_id) | (toc_link.c.target_box_id == box_id),
            )
        ).scalars()
    )
    _delete_links(conn, log, link_ids)
    store.delete(conn, log, toc_box, box_id)
    _record(conn, task_id=task_id, actor=actor, log=log, change=f"Deleted box {row.code}")


def set_critical(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    link_id: uuid.UUID,
    expected_revision: int,
) -> None:
    """Mark a link critical, unmarking any other (at most one per task, W10).

    A link the user marks keeps the mark when a check re-picks (C6).
    """
    row = _row(conn, toc_link, link_id, task_id)
    _stale(row, expected_revision)
    log = store.ChangeLog()
    for other in conn.execute(
        select(toc_link).where(
            toc_link.c.task_id == task_id, toc_link.c.critical, toc_link.c.link_id != link_id
        )
    ):
        _update(conn, log, toc_link, other, actor=actor, values={"critical": False})
    _update(conn, log, toc_link, row, actor=actor, values={"critical": True, "user_edited": True})
    _record(conn, task_id=task_id, actor=actor, log=log, change=f"Marked {row.code} as critical")


def move_box(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: Actor,
    box_id: uuid.UUID,
    expected_revision: int,
    position: dict[str, float],
) -> int:
    """Save where the user dropped a box (C47); returns the new revision."""
    if not {"x", "y"} <= set(position):
        raise EditRefused("toc_invalid", "a position needs x and y", status=422)
    row = _row(conn, toc_box, box_id, task_id)
    _stale(row, expected_revision)
    log = store.ChangeLog()
    # A move does not stamp edited_by: it changes no content.
    if not store.update(
        conn,
        log,
        toc_box,
        box_id,
        observed_revision=row.revision,
        values={"position": {"x": float(position["x"]), "y": float(position["y"])}},
    ):
        _stale(row, -1)
    _record(conn, task_id=task_id, actor=actor, log=log, change=f"Moved {row.code}")
    return int(row.revision) + 1


def reset_layout(conn: Connection, *, task_id: uuid.UUID, actor: Actor) -> int:
    """Return every moved box to the computed layout; returns how many moved."""
    log = store.ChangeLog()
    rows = list(
        conn.execute(
            select(toc_box).where(toc_box.c.task_id == task_id, toc_box.c.position.isnot(None))
        )
    )
    for row in rows:
        store.update(
            conn,
            log,
            toc_box,
            row.box_id,
            observed_revision=row.revision,
            values={"position": None},
        )
    if rows:
        _record(conn, task_id=task_id, actor=actor, log=log, change="Reset the layout")
    return len(rows)


def _typed(table: Table, state: dict[str, Any]) -> dict[str, Any]:
    """A before-state's JSON values back as the column types expect."""
    values: dict[str, Any] = {}
    for name, value in state.items():
        column = table.c.get(name)
        if column is None:
            continue
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(column.type, PgUUID):
            value = uuid.UUID(str(value))
        values[name] = value
    return values


def undo(conn: Connection, *, task_id: uuid.UUID, actor: Actor, event_id: uuid.UUID) -> list[str]:
    """Put back the state before one user edit (C9, C10).

    Rows the edit created are deleted; rows it changed get their before-state
    back; rows it deleted are inserted again, parents first. A row changed by
    anyone after the edit is left alone and named in the result.

    Returns:
        The elements skipped because they changed since, as codes or ids.

    Raises:
        EditRefused: When the event is not a user edit of this task, or was
            already undone.
    """
    event = conn.execute(
        select(event_log).where(event_log.c.event_id == event_id, event_log.c.task_id == task_id)
    ).one_or_none()
    payload = event.payload if event is not None else None
    if (
        event is None
        or payload is None
        or event.event_type != store.TOC_CHANGED_EVENT
        or payload.get("step") != USER_EDIT
    ):
        raise EditRefused("toc_not_found", "there is no such edit to undo", status=404)
    if _undone(conn, task_id, event_id):
        raise EditRefused("toc_already_undone", "this edit was already undone")
    log = store.ChangeLog()
    skipped: list[str] = []
    for created in payload.get("created", []):
        table = _TABLES.get(created["table"])
        if table is None:
            continue
        key = table.c[store._PRIMARY_KEY[table.name]]
        current = conn.execute(select(table).where(key == uuid.UUID(created["id"]))).one_or_none()
        if current is None:
            continue
        if current.revision != 1:
            skipped.append(current.code or created["id"])
            continue
        if table is toc_link:
            _delete_links(conn, log, [current.link_id])
        elif table is toc_box:
            links = list(
                conn.execute(
                    select(toc_link.c.link_id).where(
                        (toc_link.c.source_box_id == current.box_id)
                        | (toc_link.c.target_box_id == current.box_id)
                    )
                ).scalars()
            )
            _delete_links(conn, log, links)
            store.delete(conn, log, toc_box, current.box_id)
    deleted = [entry for entry in payload.get("before", []) if entry.get("deleted")]
    for name in _RESTORE_ORDER:
        table = _TABLES[name]
        for entry in deleted:
            if entry["table"] != name:
                continue
            values = _typed(table, entry["row"])
            conn.execute(table.insert().values(**values))
            if name in store._PRIMARY_KEY:
                log.created.append({"table": name, "id": str(values[store._PRIMARY_KEY[name]])})
    for entry in payload.get("before", []):
        if entry.get("deleted") or entry["table"] not in ("toc_box", "toc_link"):
            continue
        table = _TABLES[entry["table"]]
        before = _typed(table, entry["row"])
        key_name = store._PRIMARY_KEY[table.name]
        current = conn.execute(
            select(table).where(table.c[key_name] == before[key_name])
        ).one_or_none()
        # The edit raised the revision by one; anything higher means a later change.
        if current is None or current.revision != before["revision"] + 1:
            skipped.append(before.get("code") or str(before[key_name]))
            continue
        restore = {
            name: value
            for name, value in before.items()
            if name not in (key_name, "task_id", "revision", "created_at", "updated_at")
        }
        store.update(
            conn, log, table, before[key_name], observed_revision=current.revision, values=restore
        )
    store.record(
        conn,
        task_id=task_id,
        run_id=None,
        step="user_undo",
        log=log,
        changes=[f"Undid: {', '.join(payload.get('changes') or ['an edit'])}"],
        actor=actor.user_id,
        undoes=str(event_id),
    )
    return skipped


def _undone(conn: Connection, task_id: uuid.UUID, event_id: uuid.UUID) -> bool:
    return (
        conn.execute(
            select(event_log.c.event_id).where(
                event_log.c.task_id == task_id,
                event_log.c.event_type == store.TOC_CHANGED_EVENT,
                event_log.c.payload["undoes"].astext == str(event_id),
            )
        ).first()
        is not None
    )


@dataclass(frozen=True)
class HistoryEntry:
    """One line of History: when, who, what, and whether Undo applies."""

    event_id: uuid.UUID
    at: datetime
    who: str
    what: str
    undoable: bool


#: Names for Policy Atlas's own steps in History.
_STEP_WHO = "Policy Atlas"


def history(conn: Connection, task_id: uuid.UUID, *, limit: int = 200) -> list[HistoryEntry]:
    """The task's changes, newest first: user edits (undoable once) and Policy Atlas's steps."""
    rows = list(
        conn.execute(
            select(event_log.c.event_id, event_log.c.occurred_at, event_log.c.payload)
            .where(
                event_log.c.task_id == task_id,
                event_log.c.event_type == store.TOC_CHANGED_EVENT,
            )
            .order_by(event_log.c.sequence.desc())
            .limit(limit)
        )
    )
    undone = {str(row.payload.get("undoes")) for row in rows if row.payload.get("undoes")}
    actors = {row.payload.get("actor") for row in rows if row.payload.get("actor")}
    names = names_of(conn, actors)
    entries = []
    for row in rows:
        payload = row.payload
        step = payload.get("step", "")
        actor = payload.get("actor")
        changes = [
            c if isinstance(c, str) else c.get("text", "") for c in payload.get("changes", [])
        ]
        what = "; ".join(c for c in changes if c) or _STEP_TEXT.get(step, step)
        entries.append(
            HistoryEntry(
                event_id=row.event_id,
                at=row.occurred_at,
                who=names.get(actor, actor) if actor else _STEP_WHO,
                what=what,
                undoable=step == USER_EDIT and str(row.event_id) not in undone,
            )
        )
    return entries


_STEP_TEXT = {
    "toc_draft": "Drafted the theory",
    "toc_merge": "Merged similar boxes and pathways",
    "toc_choose": "Chose the pathways to keep",
    "toc_discover": "Added pathways found in the evidence",
    "toc_summarise": "Wrote titles and evidence sentences",
}


def names_of(conn: Connection, user_ids: set[str] | Any) -> dict[str, str]:
    """User id → display name, from ``app_user``; a missing row falls back to the id."""
    from policy_atlas.api.identity import sub_display

    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    known: dict[str, str] = {
        uid: name
        for uid, name in conn.execute(
            select(app_user.c.user_id, app_user.c.display_name).where(app_user.c.user_id.in_(ids))
        ).all()
    }
    return {uid: known.get(uid) or sub_display(uid) for uid in ids}
