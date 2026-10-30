"""User edits, History and Undo (task 054, C41, C47, C10)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.core.schema import toc_box, toc_item_evidence, toc_link, toc_pathway_link
from policy_atlas.theory_of_change import edits
from policy_atlas.theory_of_change.edits import Actor, EditRefused
from tests.helpers import seed_toc_task

ME = Actor("user-ada")


@pytest.fixture
def ids(engine: Engine, cleanup: list[uuid.UUID]) -> dict[str, uuid.UUID]:
    with engine.begin() as conn:
        seeded = seed_toc_task(conn)
    cleanup.append(seeded["task_id"])
    return seeded


def _one(engine: Engine, table: Any, key: str, row_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(select(table).where(table.c[key] == row_id)).one_or_none()


def _count(engine: Engine, table: Any, link_id: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                select(func.count()).select_from(table).where(table.c.link_id == link_id)
            ).scalar_one()
        )


def _last_event(engine: Engine, task_id: uuid.UUID) -> uuid.UUID:
    with engine.connect() as conn:
        return edits.history(conn, task_id)[0].event_id


def test_an_edit_stamps_who_and_refuses_a_stale_revision(engine: Engine, ids: Any) -> None:
    task_id, box = ids["task_id"], ids["source"]
    with engine.begin() as conn:
        edits.edit_box(
            conn,
            task_id=task_id,
            actor=ME,
            box_id=box,
            expected_revision=1,
            fields={"text": "Restrict adverts before 9pm"},
        )
    row = _one(engine, toc_box, "box_id", box)
    assert (row.text, row.revision, row.edited_by) == ("Restrict adverts before 9pm", 2, ME.user_id)
    with pytest.raises(EditRefused) as refused, engine.begin() as conn:
        edits.edit_box(
            conn, task_id=task_id, actor=ME, box_id=box, expected_revision=1, fields={"text": "x"}
        )
    assert refused.value.code == "toc_stale_revision"
    with engine.connect() as conn:
        entry = edits.history(conn, task_id)[0]
    assert entry.undoable and entry.what.startswith("Edited")


def test_a_link_edit_rebuilds_its_sentence(engine: Engine, ids: Any) -> None:
    with engine.begin() as conn:
        edits.edit_link(
            conn,
            task_id=ids["task_id"],
            actor=ME,
            link_id=ids["link"],
            expected_revision=1,
            fields={"then_text": "children see fewer adverts"},
        )
    row = _one(engine, toc_link, "link_id", ids["link"])
    assert row.sentence == "If if, then children see fewer adverts, because because."


def test_new_boxes_and_links_get_codes_and_need_evidence(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    with engine.begin() as conn:
        box = edits.create_box(
            conn, task_id=task_id, actor=ME, layer="outcome_long", text="Children eat less"
        )
        link = edits.create_link(
            conn, task_id=task_id, actor=ME, source_box_id=ids["target"], target_box_id=box
        )
    assert _one(engine, toc_box, "box_id", box).code == "L1"
    with engine.connect() as conn:
        graph = toc_graph_out(conn, task_id)
    added = next(item for item in graph.links if item.link_id == link)
    assert added.state == "unchecked" and added.origin == "user" and added.code
    assert added.sentence.startswith("If output box, then Children eat less")
    with pytest.raises(EditRefused) as refused, engine.begin() as conn:
        edits.create_link(
            conn, task_id=task_id, actor=ME, source_box_id=ids["target"], target_box_id=box
        )
    assert refused.value.code == "toc_duplicate"


def test_undo_restores_a_deleted_box_with_its_link_pathway_step_and_evidence(
    engine: Engine, ids: Any
) -> None:
    task_id, link = ids["task_id"], ids["link"]
    assert _count(engine, toc_item_evidence, link) == 1
    with engine.begin() as conn:
        edits.delete_box(conn, task_id=task_id, actor=ME, box_id=ids["target"], expected_revision=1)
    assert _one(engine, toc_link, "link_id", link) is None
    assert _count(engine, toc_item_evidence, link) == 0
    with engine.begin() as conn:
        skipped = edits.undo(conn, task_id=task_id, actor=ME, event_id=_last_event(engine, task_id))
    assert skipped == []
    assert _one(engine, toc_box, "box_id", ids["target"]) is not None
    assert _one(engine, toc_link, "link_id", link) is not None
    assert _count(engine, toc_pathway_link, link) == 1
    assert _count(engine, toc_item_evidence, link) == 1
    with engine.connect() as conn:
        entries = edits.history(conn, task_id)
    # The Undo is listed; the edit it reversed can no longer be undone.
    assert entries[0].what.startswith("Undid") and not entries[1].undoable
    with pytest.raises(EditRefused), engine.begin() as conn:
        edits.undo(conn, task_id=task_id, actor=ME, event_id=entries[1].event_id)


def test_undo_skips_a_row_changed_since(engine: Engine, ids: Any) -> None:
    task_id, box = ids["task_id"], ids["source"]
    with engine.begin() as conn:
        edits.edit_box(
            conn, task_id=task_id, actor=ME, box_id=box, expected_revision=1, fields={"text": "A"}
        )
    first = _last_event(engine, task_id)
    with engine.begin() as conn:
        edits.edit_box(
            conn, task_id=task_id, actor=ME, box_id=box, expected_revision=2, fields={"text": "B"}
        )
        skipped = edits.undo(conn, task_id=task_id, actor=ME, event_id=first)
    assert len(skipped) == 1 and _one(engine, toc_box, "box_id", box).text == "B"


def test_undo_removes_an_added_link(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    with engine.begin() as conn:
        link = edits.create_link(
            conn,
            task_id=task_id,
            actor=ME,
            source_box_id=ids["target"],
            target_box_id=ids["case_box"],
        )
    with engine.begin() as conn:
        edits.undo(conn, task_id=task_id, actor=ME, event_id=_last_event(engine, task_id))
    assert _one(engine, toc_link, "link_id", link) is None


def test_moving_a_box_saves_its_position_and_reset_clears_it(engine: Engine, ids: Any) -> None:
    task_id, box = ids["task_id"], ids["source"]
    with engine.begin() as conn:
        revision = edits.move_box(
            conn,
            task_id=task_id,
            actor=ME,
            box_id=box,
            expected_revision=1,
            position={"x": 12.5, "y": 300},
        )
    assert revision == 2
    with engine.connect() as conn:
        shown = next(b for b in toc_graph_out(conn, task_id).boxes if b.box_id == box)
    assert shown.position is not None and (shown.position.x, shown.position.y) == (12.5, 300)
    # A move changes no content, so nobody is named as its editor.
    assert shown.edited_by is None
    with engine.begin() as conn:
        assert edits.reset_layout(conn, task_id=task_id, actor=ME) == 1
    assert _one(engine, toc_box, "box_id", box).position is None


def test_marking_a_link_critical_unmarks_the_other(engine: Engine, ids: Any) -> None:
    task_id = ids["task_id"]
    with engine.begin() as conn:
        other = edits.create_link(
            conn,
            task_id=task_id,
            actor=ME,
            source_box_id=ids["target"],
            target_box_id=ids["case_box"],
        )
        conn.execute(
            toc_link.update().where(toc_link.c.link_id == ids["link"]).values(critical=True)
        )
        edits.set_critical(conn, task_id=task_id, actor=ME, link_id=other, expected_revision=1)
    assert _one(engine, toc_link, "link_id", other).critical
    assert not _one(engine, toc_link, "link_id", ids["link"]).critical


# --- Evidence edits (C42, C43) ---------------------------------------------------------------


def _count_seeded(engine: Engine, ids: Any) -> None:
    """Make the seeded link count its judgement, as a check walk would (C19)."""
    with engine.begin() as conn:
        current = conn.execute(
            select(toc_item_evidence.c.item_hash).where(toc_item_evidence.c.link_id == ids["link"])
        ).scalar_one()
        conn.execute(
            toc_link.update().where(toc_link.c.link_id == ids["link"]).values(counted_hash=current)
        )


def test_removing_a_document_takes_it_out_of_the_verdict_and_restore_puts_it_back(
    engine: Engine, ids: Any
) -> None:
    from policy_atlas.theory_of_change.check import counted_judgements

    task_id = ids["task_id"]
    _count_seeded(engine, ids)
    with engine.begin() as conn:
        edits.edit_evidence(
            conn,
            task_id=task_id,
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=1,
            action="remove",
        )
        assert counted_judgements(conn, task_id=task_id) == {}
        edits.edit_evidence(
            conn,
            task_id=task_id,
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=2,
            action="restore",
        )
        assert len(counted_judgements(conn, task_id=task_id)[str(ids["link"])]) == 1


def test_the_users_scores_count_instead_of_the_judges_and_undo_returns_them(
    engine: Engine, ids: Any
) -> None:
    from policy_atlas.api.routers.toc import toc_evidence_out
    from policy_atlas.theory_of_change.check import counted_judgements, row_judgement

    task_id = ids["task_id"]
    _count_seeded(engine, ids)
    with engine.begin() as conn:
        edits.edit_evidence(
            conn,
            task_id=task_id,
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=1,
            action="score",
            support="refutes",
            relevance=3,
        )
        row = counted_judgements(conn, task_id=task_id)[str(ids["link"])][0]
        assert (row_judgement(row).support, row_judgement(row).relevance) == ("refutes", 3)
        doc = next(iter(toc_evidence_out(conn, task_id).links[0].documents))
        # The judge's own scores stay visible next to the user's.
        assert (doc.support, doc.judge_support) == ("refutes", row.support)
        # A user with no profile row shows under a name made from their id.
        assert doc.scored_by is not None and "user-ada" in doc.scored_by
    with engine.begin() as conn:
        edits.undo(conn, task_id=task_id, actor=ME, event_id=_last_event(engine, task_id))
        row = counted_judgements(conn, task_id=task_id)[str(ids["link"])][0]
        assert row.support_override is None


def test_a_score_needs_a_support_and_a_relevance(engine: Engine, ids: Any) -> None:
    with pytest.raises(EditRefused) as refused, engine.begin() as conn:
        edits.edit_evidence(
            conn,
            task_id=ids["task_id"],
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=1,
            action="score",
            support="strong",
        )
    assert refused.value.status == 422


def test_keep_the_evidence_clears_an_edited_links_pending_state(engine: Engine, ids: Any) -> None:
    task_id, link = ids["task_id"], ids["link"]
    with engine.begin() as conn:
        # The seeded link counts the judgement under its current wording.
        current = conn.execute(
            select(toc_item_evidence.c.item_hash).where(toc_item_evidence.c.link_id == link)
        ).scalar_one()
        conn.execute(
            toc_link.update().where(toc_link.c.link_id == link).values(counted_hash=current)
        )
        edits.edit_link(
            conn,
            task_id=task_id,
            actor=ME,
            link_id=link,
            expected_revision=1,
            fields={"then_text": "a new wording"},
        )
        state = next(x for x in toc_graph_out(conn, task_id).links if x.link_id == link).state
        assert state == "pending"
        assert edits.keep_evidence(conn, task_id=task_id, actor=ME, link_ids=[link]) == 1
        state = next(x for x in toc_graph_out(conn, task_id).links if x.link_id == link).state
        assert state == "kept"


def test_an_added_doi_resolves_to_the_tasks_document_and_decisions_carry_over(
    engine: Engine, ids: Any
) -> None:
    from policy_atlas.core.schema import source_snapshot, task_source_snapshot
    from policy_atlas.theory_of_change.check import _studies_by_link, _user_decisions

    task_id = ids["task_id"]
    with engine.begin() as conn:
        snapshot = conn.execute(
            select(task_source_snapshot.c.source_snapshot_id).where(
                task_source_snapshot.c.task_source_snapshot_id == ids["tss"]
            )
        ).scalar_one()
        conn.execute(
            source_snapshot.update()
            .where(source_snapshot.c.source_snapshot_id == snapshot)
            .values(metadata=source_snapshot.c.metadata.op("||")({"doi": "10.1000/Abc.1"}))
        )
        found = _studies_by_link(
            conn, task_id, {str(ids["link"]): ["https://doi.org/10.1000/abc.1"]}
        )
        assert found == {str(ids["link"]): [ids["tss"]]}
        edits.edit_evidence(
            conn,
            task_id=task_id,
            actor=ME,
            evidence_id=ids["evidence"],
            expected_revision=1,
            action="remove",
        )
        carried = _user_decisions(conn, task_id, {str(ids["link"])})
    assert carried[(str(ids["link"]), ids["tss"])]["excluded_by"] == ME.user_id
