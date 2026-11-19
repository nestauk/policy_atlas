"""Task 064a Q9: adding ``task_id`` to the effective-screen partition changes no row.

``_legacy_effective_screen_rows`` is the pre-064a expression (partition by scope
and snapshot only), copied here. The fixture has two tasks, each with two scopes
and four documents, rows across two generations and both stages, and some
``failed`` rows; the old and new subqueries must return identical row sets.
"""

from __future__ import annotations

import random
import uuid

from sqlalchemy import Subquery, func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import source_screening_result
from policy_atlas.evidence_search.assess.screen import effective_screen_rows
from tests.helpers import (
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
    seed_task_and_run,
)


def _legacy_effective_screen_rows(*, run_ids: set[uuid.UUID] | None = None) -> Subquery:
    ranked_query = sa_select(
        source_screening_result,
        func.row_number()
        .over(
            partition_by=(
                source_screening_result.c.evidence_scope_id,
                source_screening_result.c.task_source_snapshot_id,
            ),
            order_by=(
                source_screening_result.c.screen_generation.desc(),
                source_screening_result.c.screen_stage.desc(),
            ),
        )
        .label("_screen_rank"),
    ).where(source_screening_result.c.status != "failed")
    if run_ids is not None:
        ranked_query = ranked_query.where(source_screening_result.c.screened_by_run_id.in_(run_ids))
    ranked = ranked_query.subquery("screen_ranked")
    return (
        sa_select(*[getattr(ranked.c, column.name) for column in source_screening_result.columns])
        .where(ranked.c._screen_rank == 1)
        .subquery("effective_screen_rows")
    )


def _seed(conn: Connection) -> tuple[list[uuid.UUID], set[uuid.UUID]]:
    """Seed two tasks; return the task ids and one run id from each task."""
    rng = random.Random(64)
    task_ids: list[uuid.UUID] = []
    some_runs: set[uuid.UUID] = set()
    for _ in range(2):
        task_id, run_a = seed_task_and_run(conn)
        run_b = seed_run(conn, task_id)
        task_ids.append(task_id)
        some_runs.add(run_b)
        docs = [seed_source(conn, task_id, meta={"abstract": "x"})[1] for _ in range(4)]
        for _ in range(2):
            scope_id = seed_scope(conn, task_id)
            for tss_id in docs:
                for generation in (0, 1):
                    for stage in (1, 2):
                        roll = rng.random()
                        if roll < 0.25:
                            continue
                        status = (
                            "failed" if roll < 0.45 else rng.choice(["relevant", "not_relevant"])
                        )
                        seed_screening_result(
                            conn,
                            task_id,
                            rng.choice([run_a, run_b]),
                            scope_id,
                            tss_id,
                            status,
                            screen_stage=stage,
                            screen_basis="full_text" if stage == 2 else "title_abstract",
                            screen_generation=generation,
                        )
    return task_ids, some_runs


def _rows(
    conn: Connection, subquery: Subquery, task_id: uuid.UUID | None = None
) -> set[tuple[object, ...]]:
    query = sa_select(subquery)
    if task_id is not None:
        query = query.where(subquery.c.task_id == task_id)
    return {tuple(row) for row in conn.execute(query)}


def test_task_first_partition_returns_the_same_rows(conn: Connection) -> None:
    task_ids, some_runs = _seed(conn)

    for run_ids in (None, some_runs):
        new = effective_screen_rows(run_ids=run_ids)
        old = _legacy_effective_screen_rows(run_ids=run_ids)
        new_rows = _rows(conn, new)
        assert new_rows == _rows(conn, old)
        for task_id in task_ids:
            assert _rows(conn, new, task_id) == _rows(conn, old, task_id)

    # The fixture is not vacuous: both tasks have effective rows, some of them
    # from generation 1 and stage 2, and failed rows exist that the rule skips.
    full = _rows(conn, effective_screen_rows())
    columns = [c.name for c in source_screening_result.columns]
    by_name = [dict(zip(columns, row, strict=True)) for row in full]
    assert {row["task_id"] for row in by_name} == set(task_ids)
    assert any(row["screen_generation"] == 1 for row in by_name)
    assert any(row["screen_stage"] == 2 for row in by_name)
    assert any(row["screen_generation"] == 0 for row in by_name)
    failed = conn.execute(
        sa_select(func.count()).where(
            source_screening_result.c.status == "failed",
            source_screening_result.c.task_id.in_(task_ids),
        )
    ).scalar_one()
    assert failed > 0
