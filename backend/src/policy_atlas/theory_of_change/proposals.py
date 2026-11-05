"""Edits Policy Atlas proposes, waiting for the user (task 054, C45, C46).

The review after edits and the Task Agent's chat both return edits from one
closed list (:class:`EditOpWire`). They are stored as one ``toc_proposal`` row;
the user accepts or rejects each edit, or all of them. An accepted edit is
applied through :mod:`~policy_atlas.theory_of_change.edits`, as the user's own
edit, so History names the user, Undo works and C10's revision check holds; its
History line says Policy Atlas proposed it.

Edits name boxes and links by their codes (``S3``, ``#5``); a box the same
proposal adds is named by its ``key`` (``n1``) until it exists. An edit that
names a new box the user has not accepted yet is refused with a plain reason.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import toc_box, toc_link, toc_proposal
from policy_atlas.theory_of_change import edits, store
from policy_atlas.theory_of_change.edits import EditRefused
from policy_atlas.theory_of_change.graph import Layer

Op = Literal[
    "add_box",
    "edit_box",
    "delete_box",
    "add_link",
    "edit_link",
    "delete_link",
    "merge_boxes",
    "add_pathway",
    "mark_critical",
]


class EditOpWire(BaseModel):
    """One proposed edit. Unused fields are null."""

    model_config = ConfigDict(extra="forbid")

    op: Op
    reason: str = Field(description="One plain sentence: why this edit, at most 30 words.")
    target: str | None = Field(
        description=(
            "edit_box, delete_box: the box code; edit_link, delete_link, mark_critical: the "
            "link code (#5). Null otherwise."
        )
    )
    key: str | None = Field(
        description="add_box: a key for the new box (n1, n2) that later edits may name. Else null."
    )
    layer: Layer | None = Field(
        description="add_box: the new box's layer; edit_box: a new layer, or null."
    )
    text: str | None = Field(description="add_box, edit_box: the box text, at most 20 words.")
    source: str | None = Field(
        description="add_link: the box it starts from (a code, or a new box's key). Else null."
    )
    dest: str | None = Field(
        description="add_link: the box it leads to (a code, or a new box's key). Else null."
    )
    if_text: str | None = Field(description="add_link, edit_link: the if clause, or null.")
    then_text: str | None = Field(description="add_link, edit_link: the then clause, or null.")
    because_text: str | None = Field(
        description="add_link, edit_link: the because clause, or null."
    )
    boxes: list[str] | None = Field(
        description="merge_boxes: two box codes, the one to keep first. Else null."
    )
    links: list[str] | None = Field(
        description="add_pathway: the link codes in order, from an input to the end. Else null."
    )
    kind: Literal["success", "failure"] | None = Field(
        description="add_pathway: success, or failure for a route where it goes wrong."
    )
    label: str | None = Field(description="add_pathway: a short label, at most 8 words.")
    #: A route found in the evidence: the documents it was found in, as
    #: ``{"tss": ..., "quote": ...}``. Set by code only, so no model sees it.
    evidence: SkipJsonSchema[list[dict[str, str]] | None] = None
    #: The route this edit belongs to (``r1``), when edits are offered a route at a
    #: time: its new boxes, its new connections and the pathway. Set by code only.
    group: SkipJsonSchema[str | None] = None

    @classmethod
    def of(cls, **values: Any) -> EditOpWire:
        """An edit built by code: every field it does not name is null."""
        return cls.model_validate({**dict.fromkeys(cls.model_fields, None), **values})


def describe(op: dict[str, Any]) -> str:
    """One plain line for an edit, as the card and History show it."""
    kind = op["op"]
    if kind == "add_box":
        return f"Add box “{op.get('text')}”"
    if kind == "edit_box":
        return f"Edit {op.get('target')}: “{op.get('text') or op.get('layer')}”"
    if kind == "delete_box":
        return f"Delete box {op.get('target')}"
    if kind == "add_link":
        return f"Connect {op.get('source')} → {op.get('dest')}"
    if kind == "edit_link":
        return f"Reword {op.get('target')}"
    if kind == "delete_link":
        return f"Delete connection {op.get('target')}"
    if kind == "merge_boxes":
        keep, fold = (op.get("boxes") or ["?", "?"])[:2]
        return f"Merge {fold} into {keep}"
    if kind == "add_pathway":
        return f"Add pathway “{op.get('label')}”: {' → '.join(op.get('links') or [])}"
    return f"Mark {op.get('target')} as critical"


def create_proposal(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    source: str,
    summary: str,
    ops: list[EditOpWire],
    report_findings: list[dict[str, str]] | None = None,
) -> uuid.UUID | None:
    """Store a proposal; ``None`` when it proposes nothing."""
    if not ops and not report_findings:
        return None
    proposal_id = uuid.uuid4()
    now = datetime.now(UTC)
    conn.execute(
        toc_proposal.insert().values(
            proposal_id=proposal_id,
            task_id=task_id,
            source=source,
            summary=summary,
            edits=[
                {
                    **op.model_dump(mode="json"),
                    "status": "pending",
                    "line": describe(op.model_dump()),
                }
                for op in ops
            ],
            report_findings=report_findings or [],
            status="open",
            created_at=now,
            updated_at=now,
        )
    )
    return proposal_id


def open_proposals(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    """The task's open proposals, newest first."""
    return list(
        conn.execute(
            select(toc_proposal)
            .where(toc_proposal.c.task_id == task_id, toc_proposal.c.status == "open")
            .order_by(toc_proposal.c.created_at.desc())
        )
    )


def _box_id(conn: Connection, task_id: uuid.UUID, ref: str | None, created: dict[str, str]) -> Any:
    if ref is None:
        raise EditRefused("toc_invalid", "the suggestion names no box", status=422)
    if ref in created:
        return uuid.UUID(created[ref])
    row = conn.execute(
        select(toc_box.c.box_id).where(toc_box.c.task_id == task_id, toc_box.c.code == ref)
    ).scalar_one_or_none()
    if row is None:
        raise EditRefused(
            "toc_invalid",
            f"{ref} is not on the canvas: accept the suggestion that adds it first",
            status=422,
        )
    return row


def _link_row(conn: Connection, task_id: uuid.UUID, ref: str | None) -> Any:
    row = conn.execute(
        select(toc_link).where(toc_link.c.task_id == task_id, toc_link.c.code == ref)
    ).one_or_none()
    if row is None:
        raise EditRefused("toc_invalid", f"connection {ref} is not on the canvas", status=422)
    return row


def apply_op(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: str,
    op: dict[str, Any],
    created: dict[str, str],
) -> None:
    """Apply one accepted edit as the user's own (C45).

    Args:
        conn: Open transaction.
        task_id: The task.
        actor: The user who accepted it.
        op: The stored edit.
        created: New-box key → box id, from edits of this proposal already accepted;
            updated here when this edit adds a box.

    Raises:
        EditRefused: When it names something not on the canvas, or the edit refuses.
    """
    kind = op["op"]
    link_fields = {
        name: op[name] for name in ("if_text", "then_text", "because_text") if op.get(name)
    }

    def box_revision(box: uuid.UUID) -> int:
        return int(
            conn.execute(select(toc_box.c.revision).where(toc_box.c.box_id == box)).scalar_one()
        )

    if kind == "add_box":
        box_id = edits.create_box(
            conn, task_id=task_id, actor=actor, layer=op["layer"], text=op["text"] or ""
        )
        if op.get("key"):
            created[op["key"]] = str(box_id)
    elif kind == "edit_box":
        box = _box_id(conn, task_id, op.get("target"), created)
        edits.edit_box(
            conn,
            task_id=task_id,
            actor=actor,
            box_id=box,
            expected_revision=box_revision(box),
            fields={name: op[name] for name in ("text", "layer") if op.get(name)},
        )
    elif kind == "delete_box":
        box = _box_id(conn, task_id, op.get("target"), created)
        edits.delete_box(
            conn, task_id=task_id, actor=actor, box_id=box, expected_revision=box_revision(box)
        )
    elif kind == "add_link":
        link_id = edits.create_link(
            conn,
            task_id=task_id,
            actor=actor,
            source_box_id=_box_id(conn, task_id, op.get("source"), created),
            target_box_id=_box_id(conn, task_id, op.get("dest"), created),
        )
        if op.get("key"):
            # A pathway the same proposal adds names this connection by its key.
            created[op["key"]] = str(link_id)
        if link_fields:
            edits.edit_link(
                conn,
                task_id=task_id,
                actor=actor,
                link_id=link_id,
                expected_revision=1,
                fields=link_fields,
            )
    elif kind == "edit_link":
        row = _link_row(conn, task_id, op.get("target"))
        edits.edit_link(
            conn,
            task_id=task_id,
            actor=actor,
            link_id=row.link_id,
            expected_revision=row.revision,
            fields=link_fields,
        )
    elif kind == "delete_link":
        row = _link_row(conn, task_id, op.get("target"))
        edits.delete_link(
            conn, task_id=task_id, actor=actor, link_id=row.link_id, expected_revision=row.revision
        )
    elif kind == "mark_critical":
        row = _link_row(conn, task_id, op.get("target"))
        edits.set_critical(
            conn, task_id=task_id, actor=actor, link_id=row.link_id, expected_revision=row.revision
        )
    elif kind == "merge_boxes":
        _merge(conn, task_id=task_id, actor=actor, op=op, created=created)
    elif kind == "add_pathway":
        _add_pathway(conn, task_id=task_id, actor=actor, op=op, created=created)
    else:
        raise EditRefused("toc_invalid", f"no edit {kind!r}", status=422)


def _merge(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: str,
    op: dict[str, Any],
    created: dict[str, str],
) -> None:
    from policy_atlas.theory_of_change.check import fold_box, fold_problem

    keep_ref, fold_ref = (op.get("boxes") or [None, None])[:2]
    keep = _box_id(conn, task_id, keep_ref, created)
    fold = _box_id(conn, task_id, fold_ref, created)
    _, rows = store.load_graph(conn, task_id)
    problem = fold_problem(rows, str(fold), str(keep), by_user=True)
    log = store.ChangeLog()
    if problem is not None or not fold_box(
        conn, log, task_id=task_id, box=str(fold), into=str(keep), by_user=True
    ):
        raise EditRefused(
            "toc_invalid",
            f"{fold_ref} cannot be merged into {keep_ref}: {problem or 'it changed meanwhile'}",
            status=422,
        )
    edits._record(
        conn,
        task_id=task_id,
        actor=actor,
        log=log,
        change=f"Merged {fold_ref} into {keep_ref} (suggested by Policy Atlas)",
    )


def _add_pathway(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: str,
    op: dict[str, Any],
    created: dict[str, str],
) -> None:
    # A connection is named by its code, or by the key of one this proposal added.
    link_ids = [
        uuid.UUID(created[ref]) if ref in created else _link_row(conn, task_id, ref).link_id
        for ref in op.get("links") or []
    ]
    if not link_ids:
        raise EditRefused("toc_invalid", "a pathway needs its connections", status=422)
    log = store.ChangeLog()
    store.insert_pathway(
        conn,
        log,
        task_id=task_id,
        pathway_id=uuid.uuid4(),
        kind=op.get("kind") or "success",
        label=op.get("label") or "Suggested pathway",
        link_ids=link_ids,
        origin="user",
    )
    edits._record(
        conn,
        task_id=task_id,
        actor=actor,
        log=log,
        change=f"Added pathway “{op.get('label')}” (suggested by Policy Atlas)",
    )


@dataclass(frozen=True)
class Decided:
    """What a decision did: edits that could not apply, and the connections it added."""

    problems: list[str]
    new_link_ids: list[uuid.UUID]


def decide(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    actor: str,
    proposal_id: uuid.UUID,
    index: int | None,
    accept: bool,
    group: str | None = None,
) -> Decided:
    """Accept or reject one edit of a proposal, a route's edits, or every pending one.

    ``group`` names a route (``r1``): accepting it applies the route's edits and
    any still-pending edits they build on (a box another route introduced);
    rejecting it leaves those shared ones for the other routes. ``index`` None
    and no ``group``: every pending edit.

    Accepted edits apply in order; one that cannot apply is left pending and
    its reason returned, so the user sees why. The proposal closes when no edit
    is pending and it has no report findings (those close it through
    :func:`close`).

    Returns:
        The reasons edits could not apply (empty when all applied), and the
        connections the accepted edits added, for their evidence check.
    """
    row = conn.execute(
        select(toc_proposal)
        .where(toc_proposal.c.proposal_id == proposal_id, toc_proposal.c.task_id == task_id)
        .with_for_update()
    ).one_or_none()
    if row is None or row.status != "open":
        raise EditRefused("toc_not_found", "that suggestion is no longer open", status=404)
    ops = [dict(op) for op in row.edits]
    created: dict[str, str] = {}
    for op in ops:
        if op.get("status") == "accepted" and op.get("created_id") and op.get("key"):
            created[op["key"]] = op["created_id"]
    chosen: list[int] | range = (
        _route_edits(ops, group, accept)
        if group is not None
        else range(len(ops))
        if index is None
        else [index]
    )
    problems: list[str] = []
    links_before = set(
        conn.execute(select(toc_link.c.link_id).where(toc_link.c.task_id == task_id)).scalars()
    )
    route = next(
        (op for op in ops if op.get("group") == group and op.get("op") == "add_pathway"), None
    )
    change = (
        f"Added the suggested route “{route.get('label')}”"
        if accept and route is not None and group is not None
        else None
    )
    # One History line and one Undo for everything this accept adds.
    with store.one_change(conn, task_id=task_id, actor=actor, change=change) as batch:
        for i in chosen:
            if not 0 <= i < len(ops) or ops[i].get("status") != "pending":
                continue
            if not accept:
                ops[i]["status"] = "rejected"
                continue
            mark = len(batch)
            try:
                with conn.begin_nested():
                    apply_op(conn, task_id=task_id, actor=actor, op=ops[i], created=created)
            except EditRefused as exc:
                del batch[mark:]  # the savepoint rolled these edits back
                problems.append(f"{ops[i].get('line')}: {exc.message}")
                continue
            ops[i]["status"] = "accepted"
            if ops[i].get("key") in created:
                ops[i]["created_id"] = created[ops[i]["key"]]
    # Report findings keep it open until the report is updated or the card dismissed.
    still_open = any(op.get("status") == "pending" for op in ops) or bool(row.report_findings)
    conn.execute(
        toc_proposal.update()
        .where(toc_proposal.c.proposal_id == proposal_id)
        .values(
            edits=ops,
            status="open" if still_open else "closed",
            updated_at=datetime.now(UTC),
            revision=toc_proposal.c.revision + 1,
        )
    )
    links_after = conn.execute(
        select(toc_link.c.link_id).where(toc_link.c.task_id == task_id)
    ).scalars()
    return Decided(
        problems=problems, new_link_ids=[i for i in links_after if i not in links_before]
    )


def _refs(op: dict[str, Any]) -> list[str]:
    """The keys an edit builds on: its link's two boxes, or its pathway's links."""
    return [
        ref
        for ref in [op.get("source"), op.get("dest"), *(op.get("links") or [])]
        if isinstance(ref, str)
    ]


def _route_edits(ops: list[dict[str, Any]], group: str, accept: bool) -> list[int]:
    """The pending edits a route's Accept or Reject applies to, in order.

    Accept: the route's own edits and, first, any pending edit they build on.
    Reject: the route's own edits, except those another pending route needs.
    """
    pending = [i for i, op in enumerate(ops) if op.get("status") == "pending"]
    by_key = {ops[i]["key"]: i for i in pending if ops[i].get("key")}
    own = [i for i in pending if ops[i].get("group") == group]
    if not accept:
        others = {
            ref
            for i in pending
            if ops[i].get("group") not in (group, None)
            for ref in _refs(ops[i])
        }
        return [i for i in own if ops[i].get("key") not in others]
    needed: set[int] = set()
    todo = list(own)
    while todo:
        i = todo.pop()
        if i in needed:
            continue
        needed.add(i)
        todo += [by_key[ref] for ref in _refs(ops[i]) if ref in by_key]
    return sorted(needed)


def close(conn: Connection, *, task_id: uuid.UUID, proposal_id: uuid.UUID) -> None:
    """Close a proposal, e.g. once its report findings were acted on."""
    conn.execute(
        toc_proposal.update()
        .where(toc_proposal.c.proposal_id == proposal_id, toc_proposal.c.task_id == task_id)
        .values(status="closed", updated_at=datetime.now(UTC))
    )
