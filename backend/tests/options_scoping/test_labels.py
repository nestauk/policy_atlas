"""The label resolver (task 045, D23 / S5; ADR 0039 decision 9).

Four cases carry the resolver — own, inherited, absent, and an inherited
appraisal under a stale rubric — and two rules carry its reach: an Evidence
search task's readers reach no other task, and a link grants no read to a
task it does not target. The last tests pin the readers: Sources shows an
inherited tier, the Result's landscape counts an inherited type, and the
source dossier says the same thing the table does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.api.readmodels.repository import (
    evidence_page,
    landscape_out,
    source_dossier_out,
)
from policy_atlas.core.schema import (
    capability_run,
    source_appraisal_result,
    source_classification_result,
    task_link,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import DEFAULT_RUBRIC_VERSION, SCORE_LABELS
from policy_atlas.options_scoping.labels import labels_for_snapshots
from tests.helpers import now, seed_scope, seed_screening_result, seed_source, seed_task_and_run

RCT = "RCTs and Quasi-Experimental Studies"
REVIEW = "Systematic Review and Meta-Analysis"


@dataclass(frozen=True)
class _Task:
    task_id: uuid.UUID
    run_id: uuid.UUID
    scope_id: uuid.UUID


def _task(conn: Connection) -> _Task:
    task_id, run_id = seed_task_and_run(conn)
    return _Task(task_id, run_id, seed_scope(conn, task_id))


def _walk(conn: Connection, owner: _Task) -> uuid.UUID:
    """A finished walk of ``owner`` under its scope — a link's pin."""
    plan_id = uuid.uuid4()
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=owner.task_id,
            version=1,
            status="approved",
            payload={},
            created_at=now(),
            created_by="test",
        )
    )
    walk_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=walk_id,
            task_id=owner.task_id,
            evidence_scope_id=owner.scope_id,
            capability="evidence_search",
            plan_id=plan_id,
            plan_version=1,
            status="succeeded",
            started_at=now(),
        )
    )
    return walk_id


def _classify(conn: Connection, owner: _Task, tss_id: uuid.UUID, evidence_type: str) -> None:
    conn.execute(
        source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=owner.scope_id,
            task_source_snapshot_id=tss_id,
            task_id=owner.task_id,
            classified_by_run_id=owner.run_id,
            primary_evidence_type=evidence_type,
            classified_at=now(),
        )
    )


def _appraise(
    conn: Connection,
    owner: _Task,
    tss_id: uuid.UUID,
    score: int,
    rubric: str = DEFAULT_RUBRIC_VERSION,
) -> None:
    conn.execute(
        source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=owner.scope_id,
            task_source_snapshot_id=tss_id,
            task_id=owner.task_id,
            appraised_by_run_id=owner.run_id,
            quality_score=score,
            rubric_version=rubric,
            appraised_at=now(),
        )
    )


def _share(conn: Connection, owner: _Task, snapshot_id: uuid.UUID) -> uuid.UUID:
    """Give ``owner`` its own row for an existing content-addressed snapshot."""
    tss_id = uuid.uuid4()
    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=tss_id,
            task_id=owner.task_id,
            source_snapshot_id=snapshot_id,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    return tss_id


def _link(conn: Connection, source: _Task, target: _Task, pinned: uuid.UUID) -> None:
    conn.execute(
        task_link.insert().values(
            link_id=uuid.uuid4(),
            source_task_id=source.task_id,
            target_task_id=target.task_id,
            source_capability_run_id=pinned,
            created_by="test",
            created_at=now(),
        )
    )


def _labelled_source(conn: Connection, *, rubric: str = DEFAULT_RUBRIC_VERSION) -> tuple[
    _Task, uuid.UUID, uuid.UUID, uuid.UUID
]:
    """An Evidence search task with one labelled document and a finished walk.

    Returns the task, its pinned walk, the shared snapshot id and its own row.
    """
    source = _task(conn)
    snapshot_id, source_tss = seed_source(conn, source.task_id, meta={"title": "A trial"})
    _classify(conn, source, source_tss, RCT)
    _appraise(conn, source, source_tss, 4, rubric)
    return source, _walk(conn, source), snapshot_id, source_tss


# --- the four cases -------------------------------------------------------------


def test_own_rows_resolve_as_own(conn: Connection) -> None:
    owner = _task(conn)
    _snap, tss_id = seed_source(conn, owner.task_id)
    _classify(conn, owner, tss_id, REVIEW)
    _appraise(conn, owner, tss_id, 5)
    label = labels_for_snapshots(conn, task_id=owner.task_id, tss_ids=[tss_id])[tss_id]
    assert (label.evidence_type, label.quality_score, label.provenance) == (REVIEW, 5, "own")
    assert label.rubric_version == DEFAULT_RUBRIC_VERSION
    assert label.source_task_id is None and label.stale_rubric is False


def test_a_linked_task_s_labels_resolve_as_inherited(conn: Connection) -> None:
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn)
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    label = labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])[tss_id]
    assert (label.evidence_type, label.quality_score, label.provenance) == (RCT, 4, "inherited")
    assert (label.source_task_id, label.source_run_id) == (source.task_id, pinned)
    assert label.stale_rubric is False


def test_a_document_nobody_labelled_resolves_as_absent(conn: Connection) -> None:
    source, pinned, _snapshot_id, _source_tss = _labelled_source(conn)
    target = _task(conn)
    _link(conn, source, target, pinned)
    _other_snapshot, tss_id = seed_source(conn, target.task_id)
    label = labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])[tss_id]
    assert label.provenance == "absent"
    assert (label.evidence_type, label.quality_score, label.rubric_version) == (None, None, None)


def test_an_inherited_appraisal_under_another_rubric_is_withheld(conn: Connection) -> None:
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn, rubric="v1-old-rubric")
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    label = labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])[tss_id]
    assert label.stale_rubric is True
    assert label.quality_score is None
    assert label.rubric_version == "v1-old-rubric"
    # Classification is read as is (D23): only the tier waits for re-appraisal.
    assert label.evidence_type == RCT
    assert label.provenance == "inherited"


def test_a_re_appraised_document_keeps_its_inherited_type_and_its_own_tier(
    conn: Connection,
) -> None:
    """Each field resolves own first: re-appraisal replaces the tier only."""
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn, rubric="v1-old-rubric")
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    _appraise(conn, target, tss_id, 3)
    label = labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])[tss_id]
    assert (label.evidence_type, label.quality_score) == (RCT, 3)
    assert label.stale_rubric is False
    assert label.provenance == "inherited"


def test_only_the_pinned_walk_s_scope_is_read(conn: Connection) -> None:
    """A source task that runs again must not change what its link carries."""
    source, pinned, snapshot_id, source_tss = _labelled_source(conn)
    rerun_scope = seed_scope(conn, source.task_id)
    conn.execute(
        source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=rerun_scope,
            task_source_snapshot_id=source_tss,
            task_id=source.task_id,
            classified_by_run_id=source.run_id,
            primary_evidence_type=REVIEW,
            classified_at=now(),
        )
    )
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    label = labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])[tss_id]
    assert label.evidence_type == RCT


def test_the_resolver_writes_nothing(conn: Connection) -> None:
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn)
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    labels_for_snapshots(conn, task_id=target.task_id, tss_ids=[tss_id])
    for table in (source_classification_result, source_appraisal_result):
        assert (
            conn.execute(select(table.c.task_id).where(table.c.task_id == target.task_id)).first()
            is None
        )


# --- reach ------------------------------------------------------------------------


def test_an_evidence_search_task_reaches_no_other_task(conn: Connection) -> None:
    """Same content-addressed snapshot, no link: the other task's labels stay put."""
    _source, _pinned, snapshot_id, _source_tss = _labelled_source(conn)
    es_task = _task(conn)
    tss_id = _share(conn, es_task, snapshot_id)
    label = labels_for_snapshots(conn, task_id=es_task.task_id, tss_ids=[tss_id])[tss_id]
    assert label.provenance == "absent"


def test_a_link_grants_no_read_to_a_task_it_does_not_target(conn: Connection) -> None:
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn)
    linked = _task(conn)
    _link(conn, source, linked, pinned)
    bystander = _task(conn)
    tss_id = _share(conn, bystander, snapshot_id)
    # The bystander is the SOURCE of its own link elsewhere; still no reach.
    _link(conn, bystander, linked, _walk(conn, bystander))
    label = labels_for_snapshots(conn, task_id=bystander.task_id, tss_ids=[tss_id])[tss_id]
    assert label.provenance == "absent"


def test_another_task_s_row_ids_resolve_to_nothing(conn: Connection) -> None:
    source, _pinned, _snapshot_id, source_tss = _labelled_source(conn)
    other = _task(conn)
    label = labels_for_snapshots(conn, task_id=other.task_id, tss_ids=[source_tss])[source_tss]
    assert label.provenance == "absent"
    assert source.task_id != other.task_id


# --- the readers --------------------------------------------------------------------


def _linked_target_with_screened_doc(conn: Connection) -> tuple[_Task, uuid.UUID]:
    source, pinned, snapshot_id, _source_tss = _labelled_source(conn)
    target = _task(conn)
    tss_id = _share(conn, target, snapshot_id)
    _link(conn, source, target, pinned)
    seed_screening_result(conn, target.task_id, target.run_id, target.scope_id, tss_id)
    return target, tss_id


def test_sources_shows_an_inherited_tier(conn: Connection) -> None:
    target, tss_id = _linked_target_with_screened_doc(conn)
    page = evidence_page(conn, target.task_id, 1, 50)
    item = next(item for item in page.data if item.source_id == tss_id)
    assert item.evidence_type == RCT
    assert item.appraisal_tier == SCORE_LABELS[4]
    dossier = source_dossier_out(conn, target.task_id, tss_id)
    assert dossier is not None
    assert (dossier.evidence_type, dossier.appraisal_tier) == (RCT, SCORE_LABELS[4])


def test_the_landscape_counts_an_inherited_type(conn: Connection) -> None:
    target, _tss_id = _linked_target_with_screened_doc(conn)
    assert landscape_out(conn, target.task_id).evidence_types == {RCT: 1}


def test_an_evidence_search_task_s_sources_are_unchanged(conn: Connection) -> None:
    """Own rows only: the same labels the readers showed before the resolver."""
    owner = _task(conn)
    _snap, tss_id = seed_source(conn, owner.task_id)
    seed_screening_result(conn, owner.task_id, owner.run_id, owner.scope_id, tss_id)
    _classify(conn, owner, tss_id, REVIEW)
    _appraise(conn, owner, tss_id, 5, "test-rubric")
    item = next(
        item for item in evidence_page(conn, owner.task_id, 1, 50).data if item.source_id == tss_id
    )
    # An own appraisal is shown whatever its rubric: the rule binds inherited rows.
    assert (item.evidence_type, item.appraisal_tier) == (REVIEW, SCORE_LABELS[5])
