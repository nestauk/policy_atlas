"""Tests for ``runtime.inherit.linked_context`` (task 044, D4/S8).

These seed directly against SQLAlchemy Core rows on the transactional `conn`
fixture (`tests/conftest.py`), which rolls back at teardown — nothing here
is ever committed, so no ``options_scoping`` task these tests create can
survive to trip the migration round-trip suite's downgrade refusal
(`b5e1d7a4c026`), unlike the HTTP-driven tests in
`tests/api/test_task_links.py`, which commit and so carry their own
autouse cleanup fixture. No cleanup fixture is needed here for the same
reason none would help: there is nothing left behind to clean up.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    artefact,
    block,
    capability_run,
    evidence_scope,
    runs,
    search_coverage_record,
    synthesis_result,
    task,
    task_link,
    task_plan,
)
from policy_atlas.runtime.inherit import linked_context
from policy_atlas.runtime.task_agent_scoping_prompt import LinkedTaskContext
from tests.helpers import now

_REFERENCES_TAIL = (
    "\n\n### References\n\n1. Some Study (2020) — A. Author.\n"
)


def _make_task(conn: Connection, *, name: str, capability: str = "evidence_search") -> uuid.UUID:
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now(),
            name=name,
            status="active",
            updated_at=now(),
            capability=capability,
        )
    )
    return task_id


def _seed_linked_source(
    conn: Connection,
    target_task_id: uuid.UUID,
    *,
    name: str,
    plan_payload: dict[str, object],
    block_specs: list[tuple[str, str]],
    stop_condition: str = "completed",
    adequacy_verdict: str = "adequate",
    link_created_at: object = None,
) -> uuid.UUID:
    """Seed one source task with a finished walk, artefact and coverage; link it to the target.

    ``block_specs`` is ``[(title, content), ...]``, written as artefact blocks in order.
    Returns the link's ``link_id``.
    """
    source_task_id = _make_task(conn, name=name)
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            task_id=source_task_id,
            status="succeeded",
            started_at=now(),
            ended_at=now(),
        )
    )
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=source_task_id,
            intent="es",
            context={},
            created_at=now(),
        )
    )
    plan_id = uuid.uuid4()
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=source_task_id,
            version=1,
            status="approved",
            payload=plan_payload,
            created_at=now(),
            created_by="user",
        )
    )
    capability_run_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=capability_run_id,
            task_id=source_task_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=plan_id,
            plan_version=1,
            status="succeeded",
            started_at=now(),
            ended_at=now(),
        )
    )
    artefact_id = uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            task_id=source_task_id,
            capability_run_id=capability_run_id,
            title="Result",
            created_at=now(),
        )
    )
    blocks_json = []
    for title, content in block_specs:
        block_id = uuid.uuid4()
        conn.execute(
            block.insert().values(
                block_id=block_id,
                artefact_id=artefact_id,
                content=content,
                content_hash=str(uuid.uuid4()),
                created_at=now(),
            )
        )
        blocks_json.append({"block_id": str(block_id), "title": title, "role": "standard"})
    conn.execute(
        synthesis_result.insert().values(
            synthesis_result_id=uuid.uuid4(),
            task_id=source_task_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            artefact_id=artefact_id,
            synthesis_provenance={},
            blocks=blocks_json,
            counts={},
            flags={},
            created_at=now(),
        )
    )
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_id=source_task_id,
            acquired_by_run_id=run_id,
            backends=[{"backend": "openalex", "trust_class": "high", "mode": "live"}],
            scope_filters={},
            stop_condition=stop_condition,
            adequacy_verdict=adequacy_verdict,
            verdict_origin="model",
            created_at=now(),
        )
    )
    link_id = uuid.uuid4()
    conn.execute(
        task_link.insert().values(
            link_id=link_id,
            source_task_id=source_task_id,
            target_task_id=target_task_id,
            source_capability_run_id=capability_run_id,
            created_by="user",
            created_at=link_created_at or now(),
        )
    )
    return link_id


def test_no_links_returns_empty_list(conn: Connection) -> None:
    target_id = _make_task(conn, name="Scoping", capability="options_scoping")
    assert linked_context(conn, target_id) == []


def test_one_link_carries_plan_markdown_and_coverage(conn: Connection) -> None:
    target_id = _make_task(conn, name="Scoping", capability="options_scoping")
    _seed_linked_source(
        conn,
        target_id,
        name="NEET search",
        plan_payload={"question": "What works for NEET?", "components": ["characterise"]},
        block_specs=[("Key findings", f"Something sourced [1,2].{_REFERENCES_TAIL}")],
    )

    [ctx] = linked_context(conn, target_id)

    assert ctx.title == "NEET search"
    assert ctx.plan == {"question": "What works for NEET?", "components": ["characterise"]}
    assert "## Key findings" in ctx.report_markdown
    assert "Something sourced" in ctx.report_markdown
    assert "[1,2]" not in ctx.report_markdown
    assert "[1]" not in ctx.report_markdown
    assert "References" not in ctx.report_markdown
    assert ctx.coverage_text == "Searching completed. Coverage was judged adequate."


def test_two_links_are_returned_in_link_order(conn: Connection) -> None:
    target_id = _make_task(conn, name="Scoping", capability="options_scoping")
    base = now()
    _seed_linked_source(
        conn,
        target_id,
        name="Second linked",
        plan_payload={"question": "b"},
        block_specs=[("Body", "b prose")],
        link_created_at=base + timedelta(seconds=1),
    )
    _seed_linked_source(
        conn,
        target_id,
        name="First linked",
        plan_payload={"question": "a"},
        block_specs=[("Body", "a prose")],
        link_created_at=base,
    )

    contexts = linked_context(conn, target_id)

    assert [ctx.title for ctx in contexts] == ["First linked", "Second linked"]


def test_result_is_byte_stable_across_two_calls(conn: Connection) -> None:
    target_id = _make_task(conn, name="Scoping", capability="options_scoping")
    _seed_linked_source(
        conn,
        target_id,
        name="Stable source",
        plan_payload={"question": "What works?", "outcomes": ["a", "b"]},
        block_specs=[("Findings", "Prose one."), ("Discussion", "Prose two [3].")],
    )

    first = linked_context(conn, target_id)
    second = linked_context(conn, target_id)

    assert first == second

    def _dump(contexts: list[LinkedTaskContext]) -> str:
        return json.dumps(
            [ctx.model_dump(mode="json") for ctx in contexts], sort_keys=True
        )

    assert _dump(first) == _dump(second)


def test_a_walk_whose_artefact_has_no_blocks_renders_an_empty_report(conn: Connection) -> None:
    target_id = _make_task(conn, name="Scoping", capability="options_scoping")
    _seed_linked_source(
        conn,
        target_id,
        name="Empty artefact",
        plan_payload={"question": "What works?"},
        block_specs=[],
    )

    [ctx] = linked_context(conn, target_id)

    assert ctx.report_markdown == ""
