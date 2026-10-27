"""The theory-of-change link search depth (task 054, C27)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext
from policy_atlas.evidence_search.sourcing.search_loop import (
    LINK_PLACE_SUFFIX,
    RCT_CLAUSE,
    SR_CLAUSE,
    run_search,
)
from policy_atlas.evidence_search.sourcing.search_prompts import SearchQueriesWire
from tests.evidence_search.sourcing.test_search_single_pass import (
    ScriptedBackend,
    ov_record,
)
from tests.helpers import ScriptedGenerationBackend, oa_record, seed_scope, seed_task_and_run

SENTENCE = "Fewer ads lead to less snacking"


KEYWORD = "advertising AND snacking"
SR = f"({KEYWORD}) AND {SR_CLAUSE}"
RCT = f"({KEYWORD}) AND {RCT_CLAUSE}"


class FailingGeneration:
    """A failed generation call: the link depth still searches by meaning."""

    def generate_queries(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("generation down")


def _generation() -> ScriptedGenerationBackend:
    # Only the first OpenAlex query is used.
    return ScriptedGenerationBackend(
        queries=[SearchQueriesWire(queries=[KEYWORD, "unused"], overton_paraphrases=["p"])]
    )


def test_link_depth_runs_five_calls_and_keeps_every_distinct_result(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    first = [oa_record(f"a{i}") for i in range(20)]
    # The place search repeats the first search's top paper: kept once, as found first.
    place = [oa_record("a0"), *[oa_record(f"b{i}") for i in range(9)]]
    openalex = ScriptedBackend(
        keyed={
            "search_semantic": {SENTENCE: first, SENTENCE + LINK_PLACE_SUFFIX: place},
            # The review search ranks a1 first: kept once, in the list that ranks it higher.
            "search": {
                SR: [oa_record("a1"), *[oa_record(f"s{i}") for i in range(9)]],
                RCT: [oa_record(f"r{i}") for i in range(10)],
            },
        }
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
            context={"search": {"depth": "link", "record_cap": 60}},
        ),
        backends=[openalex, overton],
        generation_backend=_generation(),
    )

    assert [(c.verb, c.query, c.max_results) for c in openalex.calls] == [
        ("search_semantic", SENTENCE, 20),
        ("search_semantic", SENTENCE + LINK_PLACE_SUFFIX, 10),
        ("search", SR, 10),
        ("search", RCT, 10),
    ]
    assert [(c.verb, c.query, c.max_results) for c in overton.calls] == [("search", SENTENCE, 10)]
    assert counts["search"]["generation_calls"] == 1
    assert counts["search"]["queries_executed"] == {"openalex": 4, "overton": 1}
    assert counts["by_backend"]["openalex"]["acquired"] == 29 + 9 + 10
    assert counts["by_backend"]["overton"]["acquired"] == 10
    # Each list's rank order survives in the pool rank, per origin.
    acquired = [
        e["payload"] for e in events.read(conn, task_id) if e["event_type"] == "source.acquired"
    ]
    by_origin: dict[str, list[str]] = {}
    for payload in sorted(acquired, key=lambda p: (p["backend"], p["pool_rank"])):
        by_origin.setdefault(payload["query_origin"], []).append(payload["backend_record_id"])
    assert [r.rsplit("W", 1)[-1] for r in by_origin["semantic"]] == [
        f"a{i}" for i in range(20) if i != 1
    ]
    assert [r.rsplit("W", 1)[-1] for r in by_origin["semantic_place"]] == [
        f"b{i}" for i in range(9)
    ]
    assert len(by_origin["verbatim"]) == 10
    assert [r.rsplit("W", 1)[-1] for r in by_origin["variant_sr"]] == [
        "a1",
        *(f"s{i}" for i in range(9)),
    ]
    assert [r.rsplit("W", 1)[-1] for r in by_origin["variant_rct"]] == [f"r{i}" for i in range(10)]


def test_link_depth_without_a_keyword_query_still_searches_by_meaning(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    openalex = ScriptedBackend(keyed={"search_semantic": {SENTENCE: [oa_record("a0")]}})
    counts = run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=scope_id, intent=SENTENCE, context={"search": {"depth": "link"}}
        ),
        backends=[openalex],
        generation_backend=FailingGeneration(),  # type: ignore[arg-type]
    )
    assert [c.verb for c in openalex.calls] == ["search_semantic", "search_semantic"]
    assert counts["by_backend"]["openalex"]["acquired"] == 1
