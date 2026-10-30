"""Suggestions from the review and the chat, clarifications (task 054, C45, C46, C49)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import toc_box, toc_link, toc_pathway, toc_proposal
from policy_atlas.theory_of_change import proposals
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.edits import Actor, history
from policy_atlas.theory_of_change.proposals import EditOpWire
from policy_atlas.theory_of_change.review import run_review
from policy_atlas.theory_of_change.review_prompt import ReportFindingWire, ReviewResponse
from tests.helpers import seed_toc_task

ME = Actor("user-ada")


def op(name: str, /, **fields: Any) -> EditOpWire:
    """A suggested edit with every unused field null."""
    empty = {field: None for field in EditOpWire.model_fields if field not in ("op", "reason")}
    return EditOpWire(**{**empty, "op": name, "reason": "Because.", **fields})


@pytest.fixture
def ids(engine: Engine, cleanup: list[uuid.UUID]) -> dict[str, uuid.UUID]:
    with engine.begin() as conn:
        seeded = seed_toc_task(conn)
        codes = {"source": "A1", "target": "P1", "case_box": "S1"}
        for key, code in codes.items():
            conn.execute(toc_box.update().where(toc_box.c.box_id == seeded[key]).values(code=code))
        conn.execute(
            toc_link.update().where(toc_link.c.link_id == seeded["link"]).values(code="#1")
        )
    cleanup.append(seeded["task_id"])
    return seeded


def _proposal(engine: Engine, task_id: uuid.UUID, ops: list[EditOpWire]) -> uuid.UUID:
    with engine.begin() as conn:
        made = proposals.create_proposal(
            conn, task_id=task_id, source="review", summary="Two steps.", ops=ops
        )
    assert made is not None
    return made


def test_accepted_edits_apply_in_order_and_a_new_box_must_come_first(
    engine: Engine, ids: Any
) -> None:
    task_id = ids["task_id"]
    proposal = _proposal(
        engine,
        task_id,
        [
            op("add_box", key="n1", layer="outcome_long", text="Children eat less"),
            op("add_link", source="S1", dest="n1"),
        ],
    )
    with engine.begin() as conn:
        # The link names the new box, which is not on the canvas yet.
        problems = proposals.decide(
            conn, task_id=task_id, actor=ME, proposal_id=proposal, index=1, accept=True
        )
    assert problems and "n1" in problems[0]
    with engine.begin() as conn:
        assert (
            proposals.decide(
                conn, task_id=task_id, actor=ME, proposal_id=proposal, index=None, accept=True
            )
            == []
        )
        row = conn.execute(select(toc_proposal).where(toc_proposal.c.proposal_id == proposal)).one()
        added = conn.execute(
            select(toc_box).where(
                toc_box.c.task_id == task_id, toc_box.c.text == "Children eat less"
            )
        ).one()
        linked = conn.execute(
            select(toc_link).where(toc_link.c.target_box_id == added.box_id)
        ).one_or_none()
        lines = [entry.what for entry in history(conn, task_id)]
    assert [edit["status"] for edit in row.edits] == ["accepted", "accepted"]
    assert row.status == "closed" and linked is not None
    assert any(line.startswith("Added box") for line in lines)


def test_a_rejected_edit_changes_nothing(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    proposal = _proposal(engine, task_id, [op("delete_link", target="#1")])
    with engine.begin() as conn:
        proposals.decide(
            conn, task_id=task_id, actor=ME, proposal_id=proposal, index=0, accept=False
        )
        assert conn.execute(select(toc_link).where(toc_link.c.code == "#1")).first() is not None


def test_merge_and_add_pathway_apply(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    proposal = _proposal(
        engine,
        task_id,
        [
            op("add_box", key="n1", layer="outcome_short", text="Same as S1"),
            op("merge_boxes", boxes=["S1", "n1"]),
            op("add_link", source="P1", dest="S1"),
        ],
    )
    with engine.begin() as conn:
        assert (
            proposals.decide(
                conn, task_id=task_id, actor=ME, proposal_id=proposal, index=None, accept=True
            )
            == []
        )
        assert conn.execute(select(toc_box).where(toc_box.c.text == "Same as S1")).first() is None
        new_link = conn.execute(
            select(toc_link.c.code).where(toc_link.c.task_id == task_id, toc_link.c.code != "#1")
        ).scalar_one()
    pathway = _proposal(
        engine,
        task_id,
        [op("add_pathway", links=["#1", new_link], kind="success", label="Through S1")],
    )
    with engine.begin() as conn:
        proposals.decide(
            conn, task_id=task_id, actor=ME, proposal_id=pathway, index=None, accept=True
        )
        labels = list(
            conn.execute(
                select(toc_pathway.c.label).where(toc_pathway.c.task_id == task_id)
            ).scalars()
        )
    assert "Through S1" in labels


def test_the_review_stores_its_suggestions(engine: Engine, ids: Any) -> None:
    from policy_atlas.runtime.agent import persist_approved_plan
    from tests.theory_of_change.test_walks import toc_plan

    task_id = ids["task_id"]
    with engine.begin() as conn:
        persist_approved_plan(conn, task_id=task_id, plan=toc_plan())
    backend = StubTocBackend(
        {
            "review": [
                ReviewResponse(
                    summary="One box leads nowhere.",
                    edits=[op("add_link", source="P1", dest="S1")],
                    report_findings=[ReportFindingWire(section="tests", why="A link changed.")],
                )
            ]
        }
    )
    proposal = run_review(engine, task_id=task_id, backend=backend)
    assert proposal is not None
    # The review read the theory by its codes.
    sent = backend.inputs["review"][0]
    assert {box["code"] for box in sent["theory"]["boxes"]} == {"A1", "P1", "S1"}
    with engine.connect() as conn:
        (shown,) = proposals.open_proposals(conn, task_id)
    assert shown.report_findings == [{"section": "tests", "why": "A link changed."}]


def test_a_clarification_reaches_the_plan_every_step_reads(engine: Engine, ids: Any) -> None:
    from policy_atlas.runtime.task_agent_toc import toc_after_turn
    from policy_atlas.runtime.toc_plan import TocPlan
    from policy_atlas.theory_of_change.draft import with_clarifications

    task_id = ids["task_id"]
    turn = SimpleNamespace(
        proposed_edits=[op("mark_critical", target="#1")], clarification="Only England."
    )
    note = toc_after_turn(engine, task_id, turn, "user-ada")
    assert note is not None and "Suggestions" in note
    plan = TocPlan.model_construct(context="Rules in force since 2026.")
    with engine.connect() as conn:
        clarified = with_clarifications(conn, task_id, plan)
        (chat,) = proposals.open_proposals(conn, task_id)
    assert clarified.context is not None and clarified.context.endswith("Only England.")
    assert chat.source == "chat" and chat.edits[0]["op"] == "mark_critical"
