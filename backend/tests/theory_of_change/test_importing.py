"""Bring your own theory: the reading, the drafter's text and the review pause (task 054, 5)."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pymupdf
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import check_status, toc_graph_out
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.import_prompt import (
    ImportArrowWire,
    ImportBoxWire,
    ImportGroupWire,
    ImportNoteWire,
    ImportResponse,
)
from policy_atlas.theory_of_change.importing import (
    counts,
    pages_of,
    review_message,
    store_import,
    theory_text,
)
from tests.theory_of_change.test_check_steps import Records
from tests.theory_of_change.test_walks import _replies, _start, _walks, seed_toc, toc_plan

BRACKETS = ImportResponse(
    is_theory_of_change=True,
    title="Supported housing",
    boxes=[
        ImportBoxWire(ref="b1", text="LAs assess needs", layer="input", shown_as="Activities"),
        ImportBoxWire(ref="b2", text="LAs understand need", layer="outcome_short", shown_as=None),
        ImportBoxWire(ref="b3", text="Better quality", layer="outcome_long", shown_as=None),
        ImportBoxWire(ref="b4", text="Lower costs", layer="outcome_long", shown_as=None),
        ImportBoxWire(ref="b5", text="Learning spreads", layer="impact", shown_as="Impacts"),
    ],
    arrows=[
        ImportArrowWire(source="b1", target="b2", how="drawn", label="if funded"),
        ImportArrowWire(source="b3", target="b4", how="inferred", label=None),
    ],
    groups=[
        ImportGroupWire(sources=["b2"], targets=["b3", "b4"], drawn_as="a bracket into outcomes")
    ],
    notes=[ImportNoteWire(text="Wider context", kind="context", near=[])],
    unreadable=["One arrow is cut off."],
)


def test_the_drafter_reads_drawn_suggested_and_grouped_connections_apart() -> None:
    text = theory_text(BRACKETS, "housing.png")
    assert text.startswith("The user's own theory of change, read from their diagram (housing.png)")
    assert "- [input] LAs assess needs (shown as: Activities)" in text
    drawn = text.split("Connections drawn in the diagram")[1].split("\n\n")[0]
    assert "“LAs assess needs” → “LAs understand need” (labelled: if funded)" in drawn
    assert "Better quality" not in drawn
    assert "“Better quality” → “Lower costs”" in text.split("layout suggests")[1]
    assert "never join every box to every box" in text
    assert "a bracket into outcomes: from “LAs understand need” to “Better quality”" in text
    # b5 has no connection and is listed for the drafter to place.
    assert "- Learning spreads" in text.split("no connection in the diagram")[1]
    assert "[context] Wider context" in text and "One arrow is cut off." in text
    assert counts(BRACKETS) == {
        "boxes": 5,
        "drawn": 1,
        "inferred": 1,
        "groups": 1,
        "unconnected": 1,
    }


def test_a_pdf_is_read_page_by_page() -> None:
    doc = pymupdf.open()  # type: ignore[no-untyped-call]
    for _ in range(2):
        doc.new_page()
    pages = pages_of(doc.tobytes(), "application/pdf")
    assert len(pages) == 2 and all(p.startswith("data:image/png;base64,") for p in pages)
    assert pages_of(b"\x89PNG", "image/png")[0].startswith("data:image/png;base64,")


def test_the_review_message_names_what_policy_atlas_suggested() -> None:
    message = review_message(
        {"counts": counts(BRACKETS)}, kept=1, suggested=["#2", "#3"], boxes=5, links=3
    )
    assert message.startswith("Here is how I read your diagram: 5 boxes and 1 connections")
    assert "I suggested 2 connections (your diagram joins some boxes as groups" in message
    assert "#2, #3" in message and "Check the evidence" in message


def test_a_draft_waits_for_review_only_when_it_is_an_uploaded_theory() -> None:
    def walk(context: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(status="succeeded", context={"toc_walk": "draft", **context})

    assert check_status(walk({"review_first": True})) == "drafted"
    assert check_status(walk({})) == "checking"


def test_an_uploaded_theory_drafts_then_stops_for_review(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    upload_id = uuid.uuid4()
    plan = toc_plan(
        entry_point="existing_theory",
        existing_theory_text=theory_text(BRACKETS, "housing.png"),
        upload_id=upload_id,
    )
    task_id, plan_row = seed_toc(engine, plan)
    cleanup.append(task_id)
    with engine.begin() as conn:
        store_import(
            conn, task_id=task_id, upload_id=upload_id, file_name="housing.png", response=BRACKETS
        )
    _start(
        engine, task_id, plan_row, RunnerBackends(search_backends=[Records()], toc=StubTocBackend())
    )
    # The draft landed; no check followed it.
    assert [(w.context["toc_walk"], w.status) for w in _walks(engine, task_id)] == [
        ("draft", "succeeded")
    ]
    assert _replies(engine, task_id)[-1].startswith("Here is how I read your diagram")
    with engine.connect() as conn:
        assert toc_graph_out(conn, task_id).check_status == "drafted"


def test_save_stores_the_file_records_it_and_audits(
    engine: Engine, cleanup: list[uuid.UUID], tmp_path: Path
) -> None:
    from sqlalchemy import select

    from policy_atlas.core import uploads
    from policy_atlas.core.schema import event_log
    from policy_atlas.core.uploads import LocalUploadStore
    from tests.helpers import seed_toc_task

    store = LocalUploadStore(tmp_path)
    with engine.begin() as conn:
        task_id = seed_toc_task(conn)["task_id"]
        cleanup.append(task_id)
        saved = uploads.save(
            conn,
            store,
            task_id=task_id,
            purpose="toc_theory",
            file_name="../../my theory.png",
            content_type="image/png",
            data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32,
            user_id="u1",
        )
        audit = conn.execute(
            select(event_log.c.payload).where(
                event_log.c.task_id == task_id, event_log.c.event_type == uploads.UPLOAD_EVENT
            )
        ).scalar_one()
        found = uploads.find(conn, task_id=task_id, upload_id=saved.upload_id)
        elsewhere = uploads.find(conn, task_id=uuid.uuid4(), upload_id=saved.upload_id)
    # The key is the store's; the name is only the file's own name.
    assert saved.object_key == f"tasks/{task_id}/{saved.upload_id}"
    assert saved.file_name == "my theory.png"
    assert store.get(saved.object_key).startswith(b"\x89PNG")
    assert audit["purpose"] == "toc_theory" and audit["by"] == "u1"
    assert found == saved and elsewhere is None


def _users_part_marked() -> Any:
    """The stub draft, with the input, output and short-term outcome from the user's diagram."""
    from policy_atlas.theory_of_change.backend import stub_draft

    draft = stub_draft({})
    mine = {"b1", "b2", "b3"}
    return draft.model_copy(
        update={
            "boxes": [
                box.model_copy(update={"from_user_theory": box.key in mine}) for box in draft.boxes
            ],
            "links": [
                link.model_copy(update={"from_user_theory": link.key in {"l1", "l2"}})
                for link in draft.links
            ],
        }
    )


def test_the_canvas_shows_the_diagram_as_drawn_and_suggests_the_rest() -> None:
    from policy_atlas.theory_of_change.draft import drawn_part

    drawn = drawn_part(_users_part_marked())
    assert drawn is not None
    assert [box.key for box in drawn.boxes] == ["b1", "b2", "b3"]
    assert [link.key for link in drawn.links] == ["l1", "l2"]
    # One route per chain of the user's links; it may stop short of the impact.
    assert [(p.kind, p.links) for p in drawn.pathways] == [("success", ["l1", "l2"])]
    # A diagram with no connection keeps the whole draft.
    from policy_atlas.theory_of_change.backend import stub_draft

    assert drawn_part(stub_draft({})) is None


def test_an_uploaded_draft_suggests_what_completes_it_and_accepting_builds_it(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from sqlalchemy import func, select

    from policy_atlas.core.schema import toc_box, toc_link, toc_pathway
    from policy_atlas.theory_of_change import proposals
    from policy_atlas.theory_of_change import edits
    from policy_atlas.theory_of_change.edits import Actor

    upload_id = uuid.uuid4()
    plan = toc_plan(
        entry_point="existing_theory",
        existing_theory_text=theory_text(BRACKETS, "housing.png"),
        upload_id=upload_id,
    )
    task_id, plan_row = seed_toc(engine, plan)
    cleanup.append(task_id)
    with engine.begin() as conn:
        store_import(
            conn, task_id=task_id, upload_id=upload_id, file_name="housing.png", response=BRACKETS
        )
    backend = StubTocBackend({"draft": [_users_part_marked()]})
    _start(engine, task_id, plan_row, RunnerBackends(search_backends=[Records()], toc=backend))

    def count(table: Any) -> int:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    select(func.count()).select_from(table).where(table.c.task_id == task_id)
                ).scalar_one()
            )

    assert (count(toc_box), count(toc_link), count(toc_pathway)) == (3, 2, 1)
    with engine.connect() as conn:
        [complete] = [p for p in proposals.open_proposals(conn, task_id) if p.source == "draft"]
    assert [op["op"] for op in complete.edits].count("add_pathway") == 2
    assert complete.summary == (
        "To complete your theory: 1 more route to the goal and 1 way it could go wrong"
    )
    assert "To complete your theory" in _replies(engine, task_id)[-1]
    # The page can read it (the API names its source).
    from policy_atlas.api.routers.toc import proposal_out

    assert proposal_out(complete).source == "draft"
    # Offered a route at a time: r1 the route to the goal, r2 the way it could go wrong.
    groups = {op["group"] for op in complete.edits}
    assert groups == {"r1", "r2"}

    def accept(group: str) -> list[str]:
        with engine.begin() as conn:
            decided = proposals.decide(
                conn,
                task_id=task_id,
                actor=Actor(user_id="test-user"),
                proposal_id=complete.proposal_id,
                index=None,
                accept=True,
                group=group,
            )
            return decided.problems

    # The way it could go wrong alone: its box, its link and its pathway.
    assert accept("r2") == []
    assert (count(toc_box), count(toc_link), count(toc_pathway)) == (4, 3, 2)
    assert accept("r1") == []
    assert (count(toc_box), count(toc_link), count(toc_pathway)) == (6, 5, 3)
    # One History line per accepted route; its Undo takes the whole route away.
    with engine.connect() as conn:
        newest = edits.history(conn, task_id)[0]
    assert newest.what.startswith("Added the suggested route")
    with engine.begin() as conn:
        assert (
            edits.undo(
                conn, task_id=task_id, actor=Actor(user_id="test-user"), event_id=newest.event_id
            )
            == []
        )
    assert (count(toc_box), count(toc_link), count(toc_pathway)) == (4, 3, 2)


def test_a_route_brings_a_shared_box_along_and_rejecting_leaves_it_for_the_other() -> None:
    from policy_atlas.theory_of_change.proposals import _route_edits

    ops = [
        {"op": "add_box", "key": "n1", "group": "r1", "status": "pending"},
        {
            "op": "add_link",
            "key": "l1",
            "source": "A1",
            "dest": "n1",
            "group": "r1",
            "status": "pending",
        },
        {"op": "add_pathway", "links": ["l1"], "group": "r1", "status": "pending"},
        {
            "op": "add_link",
            "key": "l2",
            "source": "n1",
            "dest": "I1",
            "group": "r2",
            "status": "pending",
        },
        {"op": "add_pathway", "links": ["l2"], "group": "r2", "status": "pending"},
    ]
    # Accepting r2 alone brings the box r1 introduced.
    assert _route_edits(ops, "r2", accept=True) == [0, 3, 4]
    # Rejecting r1 keeps the box r2 still needs.
    assert _route_edits(ops, "r1", accept=False) == [1, 2]
