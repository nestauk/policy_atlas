"""The pool hand-off into ``acquire_sources`` (task 051, contract D7).

The search hands acquire one ranked pool per backend and one cap per backend.
Acquire maps, dedups in pool order, cuts at the cap, persists and embeds only
what it keeps, and counts every returned record exactly once.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_search.sourcing.search_loop import ExecutedCall
from tests.helpers import oa_record, seed_scope, seed_task_and_run
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend

Entry = tuple[dict[str, Any], str, str]


class CountingEmbedder(StubEmbeddingBackend):
    """Stub embedder that counts the texts it was asked to embed."""

    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return super().embed_texts(texts)


def _ov(suffix: str) -> dict[str, Any]:
    return {
        "policy_document_id": f"ov-{suffix}",
        "pdf_document_id": f"ov-{suffix}-pdf",
        "title": f"Overton document {suffix}",
        "translated_title": "",
        "snippet": "grey literature body",
        "llm_document_description": "",
        "published_on": "2021-06-01",
        "keyed_other_identifiers": {},
        "source": {"title": "Marble Agency", "type": "government", "country": "UK"},
        "document_url": f"https://example.org/doc/{suffix}",
        "overton_url": f"https://example.org/ov/{suffix}",
        "languages": ["eng"],
        "topics": [],
    }


def _call(
    backend: str,
    records: list[dict[str, Any]],
    *,
    verb: str = "search",
    origin: str = "generated",
    query: str = "q",
) -> ExecutedCall:
    return ExecutedCall(
        backend_name=backend,
        verb=cast("Any", verb),
        query=query,
        query_origin=cast("Any", origin),
        wire_params={},
        records=records,
        status="ok",
        error=None,
    )


def _entries(call: ExecutedCall) -> list[Entry]:
    return [(record, call.query_origin, call.verb) for record in call.records]


def _acquire(
    conn: Connection,
    scope_id: uuid.UUID,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    calls: list[ExecutedCall],
    pools: dict[str, list[Entry]] | None,
    caps: dict[str, int] | None,
    *,
    embedder: CountingEmbedder | None = None,
) -> dict[str, Any]:
    return acquire_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(scope_id=scope_id, intent="Test intent", context={}),
        backends=cast("list[SearchBackend]", [OpenAlexFixtureBackend(), OvertonFixtureBackend()]),
        executed_calls=calls,
        pools=pools,
        caps=caps,
        embedder=embedder,
    )


def _titles(conn: Connection, task_id: uuid.UUID) -> list[str]:
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .order_by(task_source_snapshot.c.ingested_at)
    ).fetchall()
    return [row.metadata["title"] for row in rows]


def _assert_invariant(counts: dict[str, Any]) -> None:
    for scope in (counts, *counts["by_backend"].values()):
        assert (
            scope["acquired"]
            + scope["already_acquired"]
            + scope["skipped_unusable"]
            + scope["dropped_over_cap"]
            == scope["results_returned"]
        )


def test_the_two_caps_cut_the_two_pools_independently(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    papers = _call("openalex", [oa_record(f"p{i}") for i in range(5)])
    policy = _call("overton", [_ov(f"d{i}") for i in range(4)], origin="verbatim")

    counts = _acquire(
        conn,
        scope_id,
        task_id,
        run_id,
        [papers, policy],
        {"openalex": _entries(papers), "overton": _entries(policy)},
        {"openalex": 2, "overton": 3},
    )

    assert counts["by_backend"]["openalex"]["acquired"] == 2
    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 3
    assert counts["by_backend"]["overton"]["acquired"] == 3
    assert counts["by_backend"]["overton"]["dropped_over_cap"] == 1
    assert set(_titles(conn, task_id)) == {
        "OpenAlex record p0",
        "OpenAlex record p1",
        "Overton document d0",
        "Overton document d1",
        "Overton document d2",
    }
    _assert_invariant(counts)


def test_pool_order_decides_which_copy_is_kept_and_the_rest_is_counted(
    conn: Connection,
) -> None:
    """The best-ranked copy claims the identity; later copies and unusable
    records are counted, never silently lost."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    shared_semantic = oa_record("shared")
    shared_keyword = oa_record("shared")
    untitled = oa_record("untitled", title=None)
    keyword = _call("openalex", [shared_keyword, untitled], origin="generated")
    semantic = _call("openalex", [shared_semantic], verb="search_semantic", origin="semantic")
    # Ranked: the semantic copy first; then the keyword copy and the unusable record.
    pools = {
        "openalex": [
            (shared_semantic, "semantic", "search_semantic"),
            (shared_keyword, "generated", "search"),
            (untitled, "generated", "search"),
        ]
    }

    counts = _acquire(conn, scope_id, task_id, run_id, [keyword, semantic], pools, {"openalex": 10})

    by_backend = counts["by_backend"]["openalex"]
    assert by_backend["results_returned"] == 3
    assert by_backend["acquired"] == 1
    assert by_backend["already_acquired"] == 1
    assert by_backend["skipped_unusable"] == 1
    acquired = [
        event["payload"]
        for event in events.read(conn, task_id)
        if event["event_type"] == "source.acquired"
    ]
    assert [payload["query_origin"] for payload in acquired] == ["semantic"]
    _assert_invariant(counts)


def test_only_kept_records_are_persisted_and_embedded(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    call = _call("openalex", [oa_record(f"p{i}", abstract=f"abstract {i}") for i in range(20)])
    embedder = CountingEmbedder()

    counts = _acquire(
        conn,
        scope_id,
        task_id,
        run_id,
        [call],
        {"openalex": _entries(call)},
        {"openalex": 3},
        embedder=embedder,
    )

    persisted = conn.execute(
        select(func.count())
        .select_from(task_source_snapshot)
        .where(task_source_snapshot.c.task_id == task_id)
    ).scalar_one()
    assert persisted == 3
    assert len(embedder.texts) == 3
    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 17


def test_events_carry_the_origin_and_verb_of_every_call(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    keyword = _call("openalex", [oa_record("k0")], origin="generated")
    backward = _call(
        "openalex", [oa_record("b0")], verb="fetch_references", origin="snowball_backward"
    )
    landmark = _call("overton", [_ov("l0")], verb="fetch_by_id", origin="landmark")
    pools = {
        "openalex": _entries(backward) + _entries(keyword),
        "overton": _entries(landmark),
    }

    _acquire(conn, scope_id, task_id, run_id, [keyword, backward, landmark], pools, None)

    log = events.read(conn, task_id)
    executed = [e["payload"] for e in log if e["event_type"] == "search.executed"]
    assert [(p["verb"], p["query_origin"]) for p in executed] == [
        ("search", "generated"),
        ("fetch_references", "snowball_backward"),
        ("fetch_by_id", "landmark"),
    ]
    acquired = [e["payload"] for e in log if e["event_type"] == "source.acquired"]
    assert sorted(p["query_origin"] for p in acquired) == [
        "generated",
        "landmark",
        "snowball_backward",
    ]


def test_without_pools_every_call_is_consumed_in_order_uncapped(conn: Connection) -> None:
    """A caller that only has executed calls gets them all, in call order."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    first = _call("openalex", [oa_record("a"), oa_record("b")])
    second = _call("openalex", [oa_record("c")], verb="search_semantic", origin="semantic")
    failed = ExecutedCall(
        backend_name="openalex",
        verb="search",
        query="boom",
        query_origin="generated",
        wire_params={},
        records=[oa_record("never")],
        status="error",
        error="scripted failure",
    )

    counts = _acquire(conn, scope_id, task_id, run_id, [first, second, failed], None, None)

    assert sorted(_titles(conn, task_id)) == [
        "OpenAlex record a",
        "OpenAlex record b",
        "OpenAlex record c",
    ]
    assert counts["by_backend"]["openalex"]["acquired"] == 3
    assert counts["by_backend"]["openalex"]["dropped_over_cap"] == 0
    _assert_invariant(counts)
