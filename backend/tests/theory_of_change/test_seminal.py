"""Seminal works: the check's documents' most-cited works, offered to every pick (task 054)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import event_log
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.seminal import SEMINAL_ORIGIN
from tests.helpers import oa_record
from tests.theory_of_change.test_check_steps import _summary
from tests.theory_of_change.test_walks import ABSTRACT, Records, _start, _walks, seed_toc

POOL_WORK = "https://openalex.org/WPOOL1"
CITED = ["https://openalex.org/WSEM1", "https://openalex.org/WSEM2"]


class _Citing(Records):
    """Every search returns fresh records that cite two outside works and one pool work."""

    def __init__(self, *, fail: bool = False) -> None:
        super().__init__(per_call=12)
        self.fail = fail
        self.lookups: list[tuple[list[str], dict[str, str] | None]] = []

    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        records = super().search(query, **kwargs)
        for record in records:
            record["referenced_works"] = [*CITED, POOL_WORK]
        return [oa_record(rid=POOL_WORK, title="A pool study", abstract=ABSTRACT), *records]

    def lookup_ids(
        self, ids: list[str], *, wire_params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        self.lookups.append((list(ids), wire_params))
        if self.fail:
            raise RuntimeError("OpenAlex down")
        return [
            oa_record(rid=f"https://openalex.org/{i}", title=f"Seminal {i}", abstract=ABSTRACT)
            for i in ids
        ]


def _seminal_events(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            payload
            for payload in conn.execute(
                select(event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == "source.acquired")
            ).scalars()
            if payload.get("query_origin") == SEMINAL_ORIGIN
        ]


def _run(engine: Engine, cleanup: list[uuid.UUID], search: _Citing, toc: StubTocBackend) -> Any:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _start(engine, task_id, plan_row, RunnerBackends(search_backends=[search], toc=toc))
    return task_id


def test_cited_works_are_looked_up_once_and_offered_to_every_pick(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    search, toc = _Citing(), StubTocBackend()
    task_id = _run(engine, cleanup, search, toc)
    # One lookup for the two outside works; the pool work is not fetched again,
    # and the plan's evidence years go on the call.
    assert [sorted(ids) for ids, _ in search.lookups] == [["WSEM1", "WSEM2"]]
    assert "from_publication_date:" in (search.lookups[0][1] or {}).get("filter", "")
    # Stored once each, marked seminal.
    assert len(_seminal_events(engine, task_id)) == 2
    # Offered to every link's pick call.
    picks = toc.inputs["pick"]
    assert len(picks) >= 2
    for call in picks:
        titles = {c["title"] for c in call["candidates"]}
        assert {"Seminal WSEM1", "Seminal WSEM2"} <= titles
    summary = _summary(engine, task_id, "toc_select")
    assert summary["seminal_targets"] == 2 and summary["seminal_resolved"] == 2
    assert summary["seminal_works"] == 2
    assert summary["seminal_offered"] == 2 * summary["links"]
    assert summary["seminal_references_counted"] > 0
    assert not summary["seminal_lookup_failed"]


def test_a_failed_lookup_leaves_the_check_succeeding(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    search = _Citing(fail=True)
    task_id = _run(engine, cleanup, search, StubTocBackend())
    assert len(search.lookups) == 1
    assert [w.status for w in _walks(engine, task_id)] == ["succeeded", "succeeded"]
    summary = _summary(engine, task_id, "toc_select")
    assert summary["seminal_lookup_failed"] and summary["seminal_works"] == 0
    assert not _seminal_events(engine, task_id)
