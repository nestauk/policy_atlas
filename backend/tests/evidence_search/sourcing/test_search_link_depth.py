"""The theory-of-change link search depth (task 054, C27)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext
from policy_atlas.evidence_search.sourcing.search_loop import LINK_PLACE_SUFFIX, run_search
from tests.evidence_search.sourcing.test_search_single_pass import (
    ScriptedBackend,
    ov_record,
)
from tests.helpers import oa_record, seed_scope, seed_task_and_run

SENTENCE = "Fewer ads lead to less snacking"


class NoGeneration:
    """The link depth makes no query-generation call."""

    def generate_queries(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("the link depth must not generate queries")


def test_link_depth_runs_three_calls_and_keeps_every_distinct_result(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    first = [oa_record(f"a{i}") for i in range(20)]
    # The place search repeats the first search's top paper: kept once, as found first.
    place = [oa_record("a0"), *[oa_record(f"b{i}") for i in range(9)]]
    openalex = ScriptedBackend(
        keyed={"search_semantic": {SENTENCE: first, SENTENCE + LINK_PLACE_SUFFIX: place}}
    )
    overton = ScriptedBackend(
        name="overton", keyed={"search": {SENTENCE: [ov_record(f"o{i}") for i in range(10)]}}
    )

    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=scope_id,
            intent=f"{SENTENCE}\nFrom: ads\nTo: snacking",
            context={"search": {"depth": "link", "record_cap": 40}},
        ),
        backends=[openalex, overton],
        generation_backend=NoGeneration(),  # type: ignore[arg-type]
    )

    assert [(c.verb, c.query, c.max_results) for c in openalex.calls] == [
        ("search_semantic", SENTENCE, 20),
        ("search_semantic", SENTENCE + LINK_PLACE_SUFFIX, 10),
    ]
    assert [(c.verb, c.query, c.max_results) for c in overton.calls] == [("search", SENTENCE, 10)]
    assert counts["search"]["generation_calls"] == 0
    assert counts["by_backend"]["openalex"]["acquired"] == 29
    assert counts["by_backend"]["overton"]["acquired"] == 10
    # Each list's rank order survives in the pool rank, per origin.
    acquired = [
        e["payload"] for e in events.read(conn, task_id) if e["event_type"] == "source.acquired"
    ]
    by_origin: dict[str, list[str]] = {}
    for payload in sorted(acquired, key=lambda p: (p["backend"], p["pool_rank"])):
        by_origin.setdefault(payload["query_origin"], []).append(payload["backend_record_id"])
    assert [r.rsplit("W", 1)[-1] for r in by_origin["semantic"]] == [f"a{i}" for i in range(20)]
    assert [r.rsplit("W", 1)[-1] for r in by_origin["semantic_place"]] == [
        f"b{i}" for i in range(9)
    ]
    assert len(by_origin["verbatim"]) == 10
