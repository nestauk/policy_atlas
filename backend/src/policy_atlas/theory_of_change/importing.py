"""Bring your own theory: read an uploaded diagram into the drafter's input (task 054, increment 5).

1. **Pages.** A PNG or JPEG is one page; a PDF's first 10 pages are rendered to
   PNG with PyMuPDF (C8).
2. **Read.** One frontier vision call (``toc_import_v1``) transcribes boxes,
   layers, connections (drawn, inferred, or grouped by a bracket), and notes.
3. **Store.** The transcription is a ``toc.import`` event on the task; the
   Task Agent's next plan takes its text as the existing theory, with the
   upload's id.
4. **Draft input.** :func:`theory_text` writes it as plain text the drafter
   keeps word for word: drawn connections are the user's; inferred ones and
   the groups are where the drafter proposes connections, marked as its own.

After the draft, the walk pauses for the user to compare the canvas with their
original before the evidence check (:func:`review_message`). A diagram uploaded
once the theory is drafted becomes a suggestion instead: what it has that the
canvas does not (:func:`suggest_from_diagram`).
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import pymupdf
import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import event_log, toc_box, toc_link
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.draft import _norm
from policy_atlas.theory_of_change.import_prompt import ImportResponse

log = structlog.get_logger()

IMPORT_EVENT = "toc.import"
#: PDF pages read (C8).
MAX_PAGES = 10
#: PDF rendering resolution: legible box text without huge images.
PDF_DPI = 150


class NotATheory(ValueError):
    """The image is not a theory of change, or has no boxes."""


def pages_of(data: bytes, content_type: str) -> list[str]:
    """The upload as image data URLs, one per page (a PDF's first 10)."""
    if content_type != "application/pdf":
        return [f"data:{content_type};base64,{base64.b64encode(data).decode()}"]
    with pymupdf.open(stream=data, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        return [
            "data:image/png;base64,"
            + base64.b64encode(page.get_pixmap(dpi=PDF_DPI).tobytes("png")).decode()
            for page in list(doc)[:MAX_PAGES]
        ]


def transcribe(data: bytes, content_type: str, backend: TocBackend) -> ImportResponse:
    """Read the diagram (the slow vision call; run it outside any transaction).

    Raises:
        NotATheory: When the image is not a theory of change or has no boxes.
    """
    response, _usage = backend.import_theory(pages=pages_of(data, content_type))
    if not response.is_theory_of_change or not response.boxes:
        raise NotATheory("This does not look like a theory of change diagram.")
    return response


def store_import(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_name: str,
    response: ImportResponse,
) -> dict[str, Any]:
    """Store a transcription for the plan.

    Returns:
        The stored payload: ``upload_id``, ``file_name``, ``transcription``,
        ``text`` (the drafter's input) and ``counts``.
    """
    payload: dict[str, Any] = {
        "upload_id": str(upload_id),
        "file_name": file_name,
        "transcription": response.model_dump(),
        "text": theory_text(response, file_name),
        "counts": counts(response),
    }
    events.append(conn, task_id=task_id, run_id=None, event_type=IMPORT_EVENT, payload=payload)
    log.info("toc_import.done", task_id=str(task_id), **payload["counts"])
    return payload


def _joined(response: ImportResponse) -> set[str]:
    """The boxes an arrow or a group connects."""
    joined = {ref for a in response.arrows for ref in (a.source, a.target)}
    return joined | {ref for g in response.groups for ref in (*g.sources, *g.targets)}


def counts(response: ImportResponse) -> dict[str, int]:
    """Boxes; drawn and inferred connections; groups; boxes with no connection."""
    joined = _joined(response)
    return {
        "boxes": len(response.boxes),
        "drawn": sum(a.how == "drawn" for a in response.arrows),
        "inferred": sum(a.how == "inferred" for a in response.arrows),
        "groups": len(response.groups),
        "unconnected": sum(b.ref not in joined for b in response.boxes),
    }


def theory_text(response: ImportResponse, file_name: str) -> str:
    """The transcription as the drafter's existing-theory text."""
    text = {b.ref: b.text for b in response.boxes}

    def name(ref: str) -> str:
        return f"“{text.get(ref, ref)}”"

    lines = [
        f"The user's own theory of change, read from their diagram ({file_name})"
        + (f": {response.title}." if response.title else "."),
        "",
        "Boxes (the user's words; the layer the diagram places them in):",
        *(
            f"- [{b.layer}] {b.text}" + (f" (shown as: {b.shown_as})" if b.shown_as else "")
            for b in response.boxes
        ),
    ]
    drawn = [a for a in response.arrows if a.how == "drawn"]
    inferred = [a for a in response.arrows if a.how == "inferred"]
    if drawn:
        lines += [
            "",
            "Connections drawn in the diagram (the user's; keep each, as from_user_theory):",
            *(
                f"- {name(a.source)} → {name(a.target)}"
                + (f" (labelled: {a.label})" if a.label else "")
                for a in drawn
            ),
        ]
    if inferred:
        lines += [
            "",
            "Connections the layout suggests but no arrow draws (propose them if they "
            "hold, as yours, not the user's):",
            *(f"- {name(a.source)} → {name(a.target)}" for a in inferred),
        ]
    if response.groups:
        lines += [
            "",
            "Groups the diagram joins without saying which box leads to which (propose "
            "the specific connections that hold, as yours, not the user's; never join "
            "every box to every box):",
            *(
                f"- {g.drawn_as}: from {', '.join(name(r) for r in g.sources)} "
                f"to {', '.join(name(r) for r in g.targets)}"
                for g in response.groups
            ),
        ]
    joined = _joined(response)
    loose = [b for b in response.boxes if b.ref not in joined]
    if loose:
        lines += [
            "",
            "Boxes with no connection in the diagram (connect them where they fit, as yours):",
            *(f"- {b.text}" for b in loose),
        ]
    if response.notes:
        lines += ["", "Notes in the diagram:", *(f"- [{n.kind}] {n.text}" for n in response.notes)]
    if response.unreadable:
        lines += ["", "Could not be read:", *(f"- {u}" for u in response.unreadable)]
    return "\n".join(lines)


def latest_import(conn: Connection, task_id: uuid.UUID) -> dict[str, Any] | None:
    """The task's latest stored import, or ``None``."""
    return conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id, event_log.c.event_type == IMPORT_EVENT)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()


def review_message(
    imported: dict[str, Any],
    *,
    kept: int,
    suggested: list[str],
    boxes: int,
    links: int,
    completes: str | None = None,
) -> str:
    """What the Task Agent says when the imported draft lands: check it, then start the check.

    Args:
        imported: The stored import.
        kept: Connections from the user's diagram on the canvas.
        suggested: Codes of the connections Policy Atlas suggested.
        boxes: Boxes on the canvas.
        links: Connections on the canvas.
        completes: The suggestion that would complete the theory, when the draft made one.
    """
    c = imported["counts"]
    parts = [
        f"Here is how I read your diagram: {c['boxes']} boxes and {c['drawn']} connections "
        f"drawn as arrows. The canvas has {boxes} boxes and {links} connections; {kept} come "
        "from your diagram."
    ]
    if suggested:
        reasons = []
        if c["groups"]:
            reasons.append("your diagram joins some boxes as groups")
        if c["inferred"]:
            reasons.append("some arrows don't point at a box")
        if c["unconnected"]:
            reasons.append(f"{c['unconnected']} boxes had no connection")
        why = f" ({'; '.join(reasons)})" if reasons else ""
        parts.append(
            f"I suggested {len(suggested)} connections{why}: {', '.join(suggested)}. "
            "Check each one, and edit or delete any that are wrong."
        )
    if completes:
        parts.append(
            f"The canvas shows your diagram as you drew it. {completes.rstrip('.')}: these "
            "wait under Suggestions beside the canvas, for you to add or leave out."
        )
    parts.append(
        "Compare it with your original in the plan, then press Check the evidence on the "
        "Result tab."
    )
    return "\n\n".join(parts)


def suggest_from_diagram(
    conn: Connection, *, task_id: uuid.UUID, response: ImportResponse, file_name: str
) -> str:
    """Offer what a diagram uploaded after the draft adds to the canvas (owner, 2026-11-05).

    A box is on the canvas when a box there has the same text (case and
    spacing ignored); the diagram's other boxes, and its drawn arrows the
    canvas lacks, wait as one suggestion. Nothing on the canvas changes until
    the user accepts.

    Returns:
        The Task Agent's reply about it.
    """
    from policy_atlas.theory_of_change.proposals import EditOpWire, create_proposal

    rows = list(
        conn.execute(
            select(toc_box.c.box_id, toc_box.c.code, toc_box.c.text).where(
                toc_box.c.task_id == task_id
            )
        )
    )
    code_of_text = {_norm(row.text): row.code for row in rows}
    code_of_id = {row.box_id: row.code for row in rows}
    joined = {
        (code_of_id.get(link.source_box_id), code_of_id.get(link.target_box_id))
        for link in conn.execute(
            select(toc_link.c.source_box_id, toc_link.c.target_box_id).where(
                toc_link.c.task_id == task_id
            )
        )
    }

    def op(**values: object) -> EditOpWire:
        return EditOpWire.of(**{"reason": f"In your diagram ({file_name}).", **values})

    ref: dict[str, str] = {}
    ops: list[EditOpWire] = []
    for box in response.boxes:
        code = code_of_text.get(_norm(box.text))
        ref[box.ref] = code if code is not None else f"d{box.ref}"
        if code is None:
            ops.append(op(op="add_box", key=ref[box.ref], layer=box.layer, text=box.text))
    new_boxes = len(ops)
    for arrow in response.arrows:
        source, target = ref.get(arrow.source), ref.get(arrow.target)
        if arrow.how != "drawn" or source is None or target is None or source == target:
            continue
        if (source, target) in joined:
            continue
        joined.add((source, target))
        ops.append(
            op(op="add_link", key=f"d{arrow.source}-{arrow.target}", source=source, dest=target)
        )
    new_links = len(ops) - new_boxes
    if not ops:
        return (
            f"I read your diagram ({file_name}): everything in it is already on the canvas, "
            "so I have nothing to add."
        )

    found = " and ".join(
        part
        for part in (
            f"{new_boxes} {'box' if new_boxes == 1 else 'boxes'}" if new_boxes else "",
            f"{new_links} {'connection' if new_links == 1 else 'connections'}" if new_links else "",
        )
        if part
    )
    create_proposal(
        conn,
        task_id=task_id,
        source="chat",
        summary=f"From your diagram ({file_name}): {found} the canvas does not have",
        ops=ops,
    )
    return (
        f"I read your diagram ({file_name}). It has {found} the canvas does not have. They "
        "wait under Suggestions beside the canvas: hover over one to see it there, then accept "
        "or reject it. Accepted connections get their evidence check."
    )
