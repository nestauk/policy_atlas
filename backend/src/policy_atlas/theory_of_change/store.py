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
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.engine import Connection, Row

from policy_atlas.core import events
from policy_atlas.core.schema import (
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


def insert(conn: Connection, log: ChangeLog, table: Table, values: dict[str, Any]) -> None:
    """Insert one graph row, stamped, and note it in the log.

    Args:
        conn: Open connection.
        log: The step's change log.
        table: A ``toc_*`` table.
        values: The row's values without timestamps.
    """
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


def delete(conn: Connection, log: ChangeLog, table: Table, row_id: uuid.UUID) -> None:
    """Delete one graph row and keep its before-state, marked deleted (C9).

    Args:
        conn: Open connection.
        log: The step's change log.
        table: A ``toc_*`` table with a single-column key.
        row_id: The row.
    """
    key = table.c[_PRIMARY_KEY[table.name]]
    current = conn.execute(select(table).where(key == row_id)).one_or_none()
    if current is None:
        return
    conn.execute(table.delete().where(key == row_id))
    log.before.append({"table": table.name, "row": row_state(current), "deleted": True})


def record(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID | None,
    step: str,
    log: ChangeLog,
    changes: list[Change] | None = None,
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
    """
    events.append(
        conn,
        task_id=task_id,
        run_id=run_id,
        event_type=TOC_CHANGED_EVENT,
        payload={
            "step": step,
            "created": log.created,
            "before": log.before,
            "skipped": log.skipped,
            "changes": changes or [],
        },
    )


def has_graph(conn: Connection, task_id: uuid.UUID) -> bool:
    """Whether the task already has any box."""
    return (
        conn.execute(select(toc_box.c.box_id).where(toc_box.c.task_id == task_id).limit(1)).first()
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
    record(conn, task_id=task_id, run_id=run_id, step="toc_draft", log=log)
    return ids


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
