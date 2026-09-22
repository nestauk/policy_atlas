"""The classify/appraise skip keys and ``leg_directive``'s scoping branch.

Task 045 Phase 4.2 (S6, P10; ADR 0039 decision 9; contract surface-map row 3
as amended): classify and appraise skip documents the label resolver already
answers from a linked task, through one optional, fail-closed directive key
each, computed per step by the runner's ``leg_directive``. Behaviour is
unchanged when the key is absent (the existing classify/appraise suites run
untouched); a stale-rubric inherited appraisal is not skipped.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    evidence_scope,
    source_appraisal_result,
    source_classification_result,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import (
    AppraiseContext,
    AppraiseDirectiveError,
    _parse_appraisal_directive,
    _parse_appraisal_skip,
    appraise_sources,
)
from policy_atlas.evidence_search.assess.classify import (
    SKIP_TSS_KEY,
    ClassifyContext,
    ClassifyDirectiveError,
    _parse_classify_directive,
    classify_sources,
)
from policy_atlas.runtime.runner import leg_directive, resolved_skip_ids
from policy_atlas.runtime.task_plan import ComponentStep
from tests.helpers import now, seed_screening_result, seed_source
from tests.options_scoping.test_labels import (
    RCT,
    _appraise,
    _classify,
    _labelled_source,
    _link,
    _share,
    _Task,
    _task,
)
from tests.runtime.test_baseline_gate import scoping_plan
from tests.runtime.test_runner import _base_plan

NON_EVIDENCE = "Other (Non-evidence documents)"


# --- the parsers -------------------------------------------------------------------


def test_classify_reads_no_directive_when_the_key_is_absent() -> None:
    assert _parse_classify_directive(None) == frozenset()
    assert _parse_classify_directive({}) == frozenset()


def test_classify_parses_the_skip_key() -> None:
    ids = [uuid.uuid4(), uuid.uuid4()]
    assert _parse_classify_directive({SKIP_TSS_KEY: [str(i) for i in ids]}) == frozenset(ids)
    assert _parse_classify_directive({SKIP_TSS_KEY: []}) == frozenset()


@pytest.mark.parametrize(
    "raw",
    [
        "not an object",
        {"other": 1},
        {SKIP_TSS_KEY: "not a list"},
        {SKIP_TSS_KEY: [7]},
        {SKIP_TSS_KEY: ["not-a-uuid"]},
    ],
)
def test_classify_s_directive_fails_closed(raw: Any) -> None:
    with pytest.raises(ClassifyDirectiveError):
        _parse_classify_directive(raw)


def test_appraise_admits_the_skip_key_beside_the_rubric() -> None:
    tss_id = uuid.uuid4()
    only_skip = {SKIP_TSS_KEY: [str(tss_id)]}
    assert _parse_appraisal_directive(only_skip) == {}
    assert _parse_appraisal_skip(only_skip) == frozenset({tss_id})
    both = {"rubric": {RCT: 3}, SKIP_TSS_KEY: [str(tss_id)]}
    assert _parse_appraisal_directive(both) == {RCT: 3}
    assert _parse_appraisal_skip(both) == frozenset({tss_id})
    assert _parse_appraisal_skip({"rubric": {RCT: 3}}) == frozenset()
    assert _parse_appraisal_skip(None) == frozenset()


@pytest.mark.parametrize(
    "raw",
    [{SKIP_TSS_KEY: "x"}, {SKIP_TSS_KEY: ["bad"]}, {SKIP_TSS_KEY: [], "other": 1}],
)
def test_appraise_s_skip_key_fails_closed(raw: Any) -> None:
    with pytest.raises(AppraiseDirectiveError):
        _parse_appraisal_directive(raw)


# --- the components under the key -----------------------------------------------------


def _screened(conn: Connection, owner: _Task) -> uuid.UUID:
    _snapshot, tss_id = seed_source(conn, owner.task_id, meta={"title": "A study"})
    seed_screening_result(conn, owner.task_id, owner.run_id, owner.scope_id, tss_id)
    return tss_id


def _classified_ids(conn: Connection, owner: _Task) -> set[uuid.UUID]:
    return set(
        conn.execute(
            select(source_classification_result.c.task_source_snapshot_id).where(
                source_classification_result.c.evidence_scope_id == owner.scope_id
            )
        ).scalars()
    )


def test_classify_skips_the_listed_documents_and_counts_them(conn: Connection) -> None:
    owner = _task(conn)
    skipped, classified = _screened(conn, owner), _screened(conn, owner)

    summary = classify_sources(
        conn,
        task_id=owner.task_id,
        run_id=owner.run_id,
        context=ClassifyContext(
            scope_id=owner.scope_id,
            intent="",
            context={"classify": {SKIP_TSS_KEY: [str(skipped)]}},
        ),
    )

    assert _classified_ids(conn, owner) == {classified}
    assert summary["classified"] == 1
    assert summary["resolved_elsewhere"] == 1
    assert summary["already_classified"] == 0


def test_classify_without_the_key_reports_no_new_count(conn: Connection) -> None:
    owner = _task(conn)
    both = {_screened(conn, owner), _screened(conn, owner)}

    summary = classify_sources(
        conn,
        task_id=owner.task_id,
        run_id=owner.run_id,
        context=ClassifyContext(scope_id=owner.scope_id, intent="", context={}),
    )

    assert _classified_ids(conn, owner) == both
    assert "resolved_elsewhere" not in summary


def test_appraise_skips_the_listed_documents_and_counts_them(conn: Connection) -> None:
    owner = _task(conn)
    skipped, appraised = _screened(conn, owner), _screened(conn, owner)
    for tss_id in (skipped, appraised):
        _classify(conn, owner, tss_id, RCT)

    summary = appraise_sources(
        conn,
        task_id=owner.task_id,
        run_id=owner.run_id,
        context=AppraiseContext(
            scope_id=owner.scope_id,
            intent="",
            context={"appraisal": {SKIP_TSS_KEY: [str(skipped)]}},
        ),
    )

    rows = set(
        conn.execute(
            select(source_appraisal_result.c.task_source_snapshot_id).where(
                source_appraisal_result.c.evidence_scope_id == owner.scope_id
            )
        ).scalars()
    )
    assert rows == {appraised}
    assert summary["appraised"] == 1
    assert summary["resolved_elsewhere"] == 1


# --- the resolver's skip set -------------------------------------------------------------


class _Pool:
    """A scoping task whose longlist scope holds five kinds of document."""

    def __init__(self, conn: Connection) -> None:
        source, pinned, resolved_snapshot, _ = _labelled_source(conn)
        stale_source_tss = _share(conn, source, _snapshot(conn, source))
        _classify(conn, source, stale_source_tss, RCT)
        _appraise(conn, source, stale_source_tss, 4, rubric="an-old-rubric")
        non_evidence_tss = _share(conn, source, _snapshot(conn, source))
        _classify(conn, source, non_evidence_tss, NON_EVIDENCE)

        self.target = _task(conn)
        _link(conn, source, self.target, pinned)
        self.resolved = _share(conn, self.target, resolved_snapshot)
        self.stale = _share(conn, self.target, _snapshot_of(conn, stale_source_tss))
        self.non_evidence = _share(conn, self.target, _snapshot_of(conn, non_evidence_tss))
        # Own: labelled by this task (its baseline scope), not by the link.
        _own_snapshot, self.own = seed_source(conn, self.target.task_id)
        _classify(conn, self.target, self.own, RCT)
        _appraise(conn, self.target, self.own, 4)
        _unused, self.absent = seed_source(conn, self.target.task_id)

        self.scope_id = uuid.uuid4()
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=self.scope_id,
                task_id=self.target.task_id,
                intent="longlist",
                context={"appraisal": {"rubric": {RCT: 4}}},
                created_at=now(),
                purpose="longlist",
            )
        )
        for tss_id in (self.resolved, self.stale, self.non_evidence, self.own, self.absent):
            seed_screening_result(
                conn, self.target.task_id, self.target.run_id, self.scope_id, tss_id
            )


def _snapshot(conn: Connection, owner: _Task) -> uuid.UUID:
    """A fresh snapshot with no row yet: ``_share`` gives each task its own."""
    snapshot_id, source_tss = seed_source(conn, owner.task_id)
    conn.execute(
        task_source_snapshot.delete().where(
            task_source_snapshot.c.task_source_snapshot_id == source_tss
        )
    )
    return snapshot_id


def _snapshot_of(conn: Connection, tss_id: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        conn.execute(
            select(task_source_snapshot.c.source_snapshot_id).where(
                task_source_snapshot.c.task_source_snapshot_id == tss_id
            )
        ).scalar_one(),
    )


def test_classify_skips_inherited_documents_with_nothing_left_to_appraise(
    conn: Connection,
) -> None:
    pool = _Pool(conn)
    skip = resolved_skip_ids(
        conn, task_id=pool.target.task_id, scope_id=pool.scope_id, component="classify"
    )
    # The stale-rubric one is classified here so appraise can re-appraise it;
    # own and unlabelled documents keep the per-scope discipline.
    assert skip == {pool.resolved, pool.non_evidence}


def test_appraise_skips_resolved_tiers_but_not_a_stale_rubric(conn: Connection) -> None:
    pool = _Pool(conn)
    skip = resolved_skip_ids(
        conn, task_id=pool.target.task_id, scope_id=pool.scope_id, component="appraise"
    )
    assert skip == {pool.resolved}
    assert pool.stale not in skip


# --- leg_directive -------------------------------------------------------------------


class _ConnEngine:
    """Hands ``leg_directive`` the test's transactional connection."""

    def __init__(self, conn: Connection | None) -> None:
        self._conn = conn

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        if self._conn is None:
            raise AssertionError("leg_directive read the database")
        yield self._conn


def _engine(conn: Connection | None) -> Engine:
    return cast(Engine, _ConnEngine(conn))


def test_an_evidence_search_step_is_returned_unchanged_without_a_read() -> None:
    step = ComponentStep(component="classify", directive_delta={"x": {"y": 1}})
    delta = leg_directive(
        _base_plan(),
        step,
        {},
        engine=_engine(None),
        task_id=uuid.uuid4(),
        evidence_scope_id=uuid.uuid4(),
    )
    assert delta == {"x": {"y": 1}}


def test_a_scoping_step_other_than_classify_or_appraise_reads_nothing() -> None:
    step = ComponentStep(component="screen_abstract", directive_delta={"screening": {}})
    delta = leg_directive(
        scoping_plan(),
        step,
        {},
        engine=_engine(None),
        task_id=uuid.uuid4(),
        evidence_scope_id=uuid.uuid4(),
    )
    assert delta == {"screening": {}}


def test_a_baseline_walk_gets_no_skip_key(conn: Connection) -> None:
    pool = _Pool(conn)
    conn.execute(
        update(evidence_scope)
        .where(evidence_scope.c.evidence_scope_id == pool.scope_id)
        .values(purpose="baseline")
    )
    delta = leg_directive(
        scoping_plan(),
        ComponentStep(component="classify", directive_delta={}),
        {},
        engine=_engine(conn),
        task_id=pool.target.task_id,
        evidence_scope_id=pool.scope_id,
    )
    assert delta == {}


def test_a_longlist_walk_gets_the_skip_keys_merged_over_the_scope_s_directive(
    conn: Connection,
) -> None:
    pool = _Pool(conn)
    kwargs: dict[str, Any] = {
        "engine": _engine(conn),
        "task_id": pool.target.task_id,
        "evidence_scope_id": pool.scope_id,
    }

    classify = leg_directive(
        scoping_plan(), ComponentStep(component="classify", directive_delta={}), {}, **kwargs
    )
    appraise = leg_directive(
        scoping_plan(), ComponentStep(component="appraise", directive_delta={}), {}, **kwargs
    )

    assert classify == {
        "classify": {SKIP_TSS_KEY: sorted(str(i) for i in (pool.resolved, pool.non_evidence))}
    }
    # The scope's own appraisal directive survives the merge (the runner's
    # directive application is a shallow merge per key).
    assert appraise == {
        "appraisal": {"rubric": {RCT: 4}, SKIP_TSS_KEY: [str(pool.resolved)]}
    }
    assert _parse_appraisal_directive(appraise["appraisal"]) == {RCT: 4}
