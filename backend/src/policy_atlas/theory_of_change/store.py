"""Read and write one task's theory-of-change graph (task 054, C1, C9, C10).

Plain SQLAlchemy Core over the ``toc_*`` tables. Every write a step makes goes
through a :class:`ChangeLog`: inserts record the new row ids, updates record
the row as it was before (enough for a later Undo to put it back, C9), and
:func:`record` writes the whole log as one ``toc.changed`` event. Updates
apply only when the row's ``revision`` still equals the one the step read,
so a row the user changed meanwhile is skipped and reported (C10).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.engine import Connection, Row

from policy_atlas.core import events
from policy_atlas.core.schema import (
    event_log,
    source_snapshot,
    task_source_snapshot,
    toc_band_item,
    toc_box,
    toc_link,
    toc_pathway,
    toc_pathway_link,
)
from policy_atlas.theory_of_change.draft_prompt import DraftResponse
from policy_atlas.theory_of_change.graph import Box, Graph, Link, Pathway

#: The event every graph write records (History; C1).
TOC_CHANGED_EVENT = "toc.changed"

_PRIMARY_KEY: dict[str, str] = {
    "toc_box": "box_id",
    "toc_link": "link_id",
    "toc_pathway": "pathway_id",
    "toc_band_item": "item_id",
    "toc_item_evidence": "evidence_id",
}


@dataclass
class GraphRows:
    """The stored rows behind a :class:`Graph`, keyed by row id as text."""

    boxes: dict[str, Row[Any]]
    links: dict[str, Row[Any]]
    pathways: dict[str, Row[Any]]
    band_items: list[Row[Any]]


#: One line of the J5 change list: plain text, or text about one pathway.
Change = str | dict[str, str]


@dataclass
class ChangeLog:
    """What one step wrote: created row ids, before-states and skipped rows."""

    created: list[dict[str, str]] = field(default_factory=list)
    before: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def row_state(row: Row[Any]) -> dict[str, Any]:
    """Return a row as JSON-safe data (the before-state an event carries)."""
    return {key: _jsonable(value) for key, value in row._mapping.items()}


def load_graph(conn: Connection, task_id: uuid.UUID) -> tuple[Graph, GraphRows]:
    """Read a task's whole graph.

    Args:
        conn: Open connection.
        task_id: The task.

    Returns:
        ``(graph, rows)``: the graph keyed by row ids as text, and the rows.
    """
    boxes = {
        str(row.box_id): row
        for row in conn.execute(
            select(toc_box).where(toc_box.c.task_id == task_id).order_by(toc_box.c.created_at)
        )
    }
    links = {
        str(row.link_id): row
        for row in conn.execute(
            select(toc_link).where(toc_link.c.task_id == task_id).order_by(toc_link.c.created_at)
        )
    }
    pathways = {
        str(row.pathway_id): row
        for row in conn.execute(
            select(toc_pathway)
            .where(toc_pathway.c.task_id == task_id)
            .order_by(toc_pathway.c.created_at, toc_pathway.c.label)
        )
    }
    steps: dict[str, list[str]] = {key: [] for key in pathways}
    for row in conn.execute(
        select(toc_pathway_link.c.pathway_id, toc_pathway_link.c.link_id)
        .where(toc_pathway_link.c.task_id == task_id)
        .order_by(toc_pathway_link.c.pathway_id, toc_pathway_link.c.position)
    ):
        steps.setdefault(str(row.pathway_id), []).append(str(row.link_id))
    band_items = list(
        conn.execute(
            select(toc_band_item)
            .where(toc_band_item.c.task_id == task_id)
            .order_by(toc_band_item.c.band, toc_band_item.c.sort_order)
        )
    )
    graph = Graph(
        boxes={key: Box(key=key, layer=row.layer, text=row.text) for key, row in boxes.items()},
        links={key: link_from_row(row) for key, row in links.items()},
        pathways=[
            Pathway(key=key, kind=row.kind, links=steps.get(key, []), status=row.status)
            for key, row in pathways.items()
        ],
    )
    return graph, GraphRows(boxes=boxes, links=links, pathways=pathways, band_items=band_items)


def link_from_row(row: Row[Any]) -> Link:
    """Build a :class:`Link` from a ``toc_link`` row."""
    return Link(
        key=str(row.link_id),
        source=str(row.source_box_id),
        target=str(row.target_box_id),
        sentence=row.sentence or "",
        if_text=row.if_text,
        for_text=row.for_text,
        then_text=row.then_text,
        because_text=row.because_text,
        conditions=list(row.conditions or []),
    )


#: The letter that starts a box's code, by layer (C35). Links use ``#``.
CODE_PREFIX: dict[str, str] = {
    "input": "A",
    "output": "P",
    "outcome_short": "S",
    "outcome_long": "L",
    "impact": "I",
    "failure_outcome": "F",
}


def next_code(
    conn: Connection, log: ChangeLog, table: Table, task_id: uuid.UUID, prefix: str
) -> str:
    """The next unused code for a prefix in one task, e.g. ``S4`` or ``#12`` (C35).

    A code is never reused, even after its row is deleted (an Undo may bring
    the row back). So the number is one more than the highest ever used: on
    live rows, on rows deleted by earlier steps (their before-states sit in
    ``toc.changed`` events) and on rows this step has deleted so far.

    Args:
        conn: Open connection.
        log: The current step's change log.
        table: ``toc_box`` or ``toc_link``.
        task_id: The task.
        prefix: A :data:`CODE_PREFIX` letter, or ``#`` for links.

    Returns:
        The code.
    """
    used = list(conn.execute(select(table.c.code).where(table.c.task_id == task_id)).scalars())
    befores = [
        entry
        for payload in conn.execute(
            select(event_log.c.payload).where(
                event_log.c.task_id == task_id, event_log.c.event_type == TOC_CHANGED_EVENT
            )
        ).scalars()
        for entry in payload.get("before", [])
    ]
    used += [
        entry["row"].get("code")
        for entry in [*befores, *log.before]
        if entry.get("table") == table.name and entry.get("deleted")
    ]
    numbers = [
        int(code[len(prefix) :])
        for code in used
        if code and code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def insert(conn: Connection, log: ChangeLog, table: Table, values: dict[str, Any]) -> None:
    """Insert one graph row, stamped, and note it in the log.

    A box or link without a ``code`` gets the next one (:func:`next_code`).

    Args:
        conn: Open connection.
        log: The step's change log.
        table: A ``toc_*`` table.
        values: The row's values without timestamps.
    """
    if table.name in ("toc_box", "toc_link") and values.get("code") is None:
        prefix = CODE_PREFIX[values["layer"]] if table.name == "toc_box" else "#"
        values = {**values, "code": next_code(conn, log, table, values["task_id"], prefix)}
    now = datetime.now(UTC)
    conn.execute(table.insert().values(**values, created_at=now, updated_at=now))
    key = _PRIMARY_KEY.get(table.name)
    if key is not None:
        log.created.append({"table": table.name, "id": str(values[key])})


def update(
    conn: Connection,
    log: ChangeLog,
    table: Table,
    row_id: uuid.UUID,
    *,
    observed_revision: int,
    values: dict[str, Any],
) -> bool:
    """Update one graph row if nobody changed it since it was read (C10).

    Raises the revision, stamps ``updated_at`` and keeps the before-state.

    Args:
        conn: Open connection.
        log: The step's change log.
        table: A ``toc_*`` table with a single-column key.
        row_id: The row.
        observed_revision: The revision the step read.
        values: The new values.

    Returns:
        Whether the row was updated; a skipped row is noted in the log.
    """
    key = table.c[_PRIMARY_KEY[table.name]]
    current = conn.execute(select(table).where(key == row_id).with_for_update()).one_or_none()
    if current is None or current.revision != observed_revision:
        log.skipped.append({"table": table.name, "id": str(row_id)})
        return False
    conn.execute(
        table.update()
        .where(key == row_id, table.c.revision == observed_revision)
        .values(**values, revision=table.c.revision + 1, updated_at=datetime.now(UTC))
    )
    log.before.append({"table": table.name, "row": row_state(current)})
    return True


def delete(
    conn: Connection,
    log: ChangeLog,
    table: Table,
    row_id: uuid.UUID,
    *,
    observed_revision: int | None = None,
) -> bool:
    """Delete one graph row and keep its before-state, marked deleted (C9).

    Args:
        conn: Open connection.
        log: The step's change log.
        table: A ``toc_*`` table with a single-column key.
        row_id: The row.
        observed_revision: When given, the delete is compare-and-apply (C10): a row
            someone changed since is left alone and logged as skipped.

    Returns:
        Whether the row was deleted.
    """
    key = table.c[_PRIMARY_KEY[table.name]]
    current = conn.execute(select(table).where(key == row_id).with_for_update()).one_or_none()
    if current is None:
        return False
    if observed_revision is not None and current.revision != observed_revision:
        log.skipped.append({"table": table.name, "id": str(row_id)})
        return False
    conn.execute(table.delete().where(key == row_id))
    log.before.append({"table": table.name, "row": row_state(current), "deleted": True})
    return True


def record(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step: str,
    log: ChangeLog,
    changes: list[Change] | None = None,
    actor: str | None = None,
    undoes: str | None = None,
) -> None:
    """Write one ``toc.changed`` event for everything a step wrote.

    Args:
        conn: Open connection.
        task_id: The task.
        run_id: The step's run.
        step: The step name (``toc_draft``, ``toc_merge``, ...).
        log: What the step wrote.
        changes: Plain-language changes for the Task Agent's list (J5). A
            change about one pathway is ``{"text", "pathway_id"}``, so the list
            can leave out a pathway the same check added and then set aside.
        actor: The user who made the change (a user edit or Undo), or ``None``
            for Policy Atlas's own steps.
        undoes: The event an Undo reverses.
    """
    payload = _payload(step, log, changes or [], actor, undoes)
    batch = _BATCH.get()
    if batch is not None and step == "user_edit":
        batch.append(payload)
        return
    events.append(
        conn, task_id=task_id, run_id=run_id, event_type=TOC_CHANGED_EVENT, payload=payload
    )


def _payload(
    step: str,
    log: ChangeLog,
    changes: list[Change],
    actor: str | None = None,
    undoes: str | None = None,
) -> dict[str, Any]:
    """One ``toc.changed`` event's payload."""
    return {
        "step": step,
        "created": log.created,
        "before": log.before,
        "skipped": log.skipped,
        "changes": changes,
        **({"actor": actor} if actor else {}),
        **({"undoes": undoes} if undoes else {}),
    }


#: User edits recorded inside :func:`one_change`, written there as one event.
_BATCH: ContextVar[list[dict[str, Any]] | None] = ContextVar("toc_change_batch", default=None)


@contextmanager
def one_change(
    conn: Connection, *, task_id: uuid.UUID, actor: str, change: str | None = None
) -> Iterator[list[dict[str, Any]]]:
    """Record every user edit made inside as one ``toc.changed`` event.

    So History shows one line, and one Undo reverses it all: an accepted
    route's boxes, connections and pathway (owner, 2026-11-05). Nothing is
    written when the block raises.

    Args:
        conn: Open connection.
        task_id: The task.
        actor: The user who made the edits.
        change: The History line; ``None`` joins the edits' own lines.

    Yields:
        The edits recorded so far; a caller that rolls back a savepoint cuts
        this list back to its length before.
    """
    batch: list[dict[str, Any]] = []
    token = _BATCH.set(batch)
    try:
        yield batch
    finally:
        _BATCH.reset(token)
    if not batch:
        return
    merged = ChangeLog(
        *([row for edit in batch for row in edit[key]] for key in ("created", "before", "skipped"))
    )
    changes = [change] if change else [c for edit in batch for c in edit["changes"]]
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=TOC_CHANGED_EVENT,
        payload=_payload("user_edit", merged, changes, actor),
    )


def snapshot_meta(
    conn: Connection, task_id: uuid.UUID, ids: Iterable[uuid.UUID] | None = None
) -> dict[uuid.UUID, Row[Any]]:
    """Each document's stored record: ``source_snapshot_id``, ``metadata``, ``source_locator``.

    Args:
        conn: Open connection.
        task_id: The task; another task's documents are never read.
        ids: The documents (``task_source_snapshot_id``), or ``None`` for every
            document the task holds.

    Returns:
        Document id → its row; ``metadata`` may be ``None``.
    """
    query = (
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .where(task_source_snapshot.c.task_id == task_id)
    )
    if ids is not None:
        wanted = list(ids)
        if not wanted:
            return {}
        query = query.where(task_source_snapshot.c.task_source_snapshot_id.in_(wanted))
    return {row.task_source_snapshot_id: row for row in conn.execute(query)}


def has_graph(conn: Connection, task_id: uuid.UUID) -> bool:
    """Whether a draft is on the canvas: a box Policy Atlas drafted or read from the user's theory.

    Boxes the user drew themselves before any draft (origin ``user``) do not
    count: they are the user's own theory, which the draft keeps (owner,
    2026-11-05). The draft marks them as from the user's theory.
    """
    return (
        conn.execute(
            select(toc_box.c.box_id)
            .where(toc_box.c.task_id == task_id, toc_box.c.origin != "user")
            .limit(1)
        ).first()
        is not None
    )


def write_draft(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID | None,
    draft: DraftResponse,
) -> dict[str, uuid.UUID]:
    """Write a checked draft as the task's graph, with one event.

    Elements the draft kept from the user's own theory are ``imported``;
    the rest ``drafted``. The draft's critical link is marked critical.

    Args:
        conn: Open connection.
        task_id: The task.
        run_id: The ``toc_draft`` run.
        draft: A draft that passed :func:`~policy_atlas.theory_of_change.graph.check_graph`.

    Returns:
        Local key → row id, for boxes, links and pathways.

    Raises:
        ValueError: If the task already has a graph (redraft is increment 2).
    """
    if has_graph(conn, task_id):
        raise ValueError("this task already has a theory of change")
    log = ChangeLog()
    ids: dict[str, uuid.UUID] = {}

    def origin(from_user: bool) -> str:
        return "imported" if from_user else "drafted"

    for box in draft.boxes:
        ids[box.key] = uuid.uuid4()
        criteria = box.result_criteria
        insert(
            conn,
            log,
            toc_box,
            {
                "box_id": ids[box.key],
                "task_id": task_id,
                "layer": box.layer,
                "text": box.text,
                "dosage": box.dosage,
                "result_criteria": {"definition": criteria.definition, "timing": criteria.timing},
                "indicator": criteria.indicator,
                "origin": origin(box.from_user_theory),
            },
        )
    for link in draft.links:
        ids[link.key] = uuid.uuid4()
        insert(
            conn,
            log,
            toc_link,
            {
                "link_id": ids[link.key],
                "task_id": task_id,
                "source_box_id": ids[link.source],
                "target_box_id": ids[link.target],
                "sentence": link.sentence,
                "if_text": link.if_text,
                "for_text": link.for_text,
                "then_text": link.then_text,
                "because_text": link.because_text,
                "conditions": list(link.conditions),
                "critical": link.key == draft.critical_link,
                "origin": origin(link.from_user_theory),
            },
        )
    for pathway in draft.pathways:
        ids[pathway.key] = uuid.uuid4()
        insert_pathway(
            conn,
            log,
            task_id=task_id,
            pathway_id=ids[pathway.key],
            kind=pathway.kind,
            label=pathway.label,
            link_ids=[ids[key] for key in pathway.links],
            origin="drafted",
        )
    insert_bands(conn, log, task_id=task_id, draft=draft)
    record(conn, task_id=task_id, run_id=run_id, step="toc_draft", log=log)
    return ids


def insert_bands(
    conn: Connection, log: ChangeLog, *, task_id: uuid.UUID, draft: DraftResponse
) -> None:
    """Insert the draft's context and supporting activities."""
    for band, texts in (("context", draft.context), ("supporting", draft.supporting_activities)):
        for order, text in enumerate(texts):
            insert(
                conn,
                log,
                toc_band_item,
                {
                    "item_id": uuid.uuid4(),
                    "task_id": task_id,
                    "band": band,
                    "text": text,
                    "sort_order": order,
                    "origin": "drafted",
                },
            )


def insert_pathway(
    conn: Connection,
    log: ChangeLog,
    *,
    task_id: uuid.UUID,
    pathway_id: uuid.UUID,
    kind: str,
    label: str,
    link_ids: list[uuid.UUID],
    origin: str,
) -> None:
    """Insert one kept pathway and its ordered steps."""
    insert(
        conn,
        log,
        toc_pathway,
        {
            "pathway_id": pathway_id,
            "task_id": task_id,
            "kind": kind,
            "status": "kept",
            "label": label,
            "origin": origin,
        },
    )
    for position, link_id in enumerate(link_ids):
        insert(
            conn,
            log,
            toc_pathway_link,
            {
                "pathway_id": pathway_id,
                "task_id": task_id,
                "position": position,
                "link_id": link_id,
            },
        )
