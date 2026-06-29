"""Fixed LangGraph harness interpreting plan-as-data.

The StateGraph dispatches components by name from the compiled Config.
In-process this slice; durable checkpointer is a deferred seam.
Block-boundary commit is modelled as one event (component.completed + block.written).
"""

import uuid
from datetime import UTC, datetime
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.grounding import GroundingError, produce_grounded_block
from policy_atlas.inference import InferenceProvider
from policy_atlas.plan import Config
from policy_atlas.schema import artefact, runs

log = structlog.get_logger()


class HarnessState(TypedDict):
    """Mutable state threaded through the harness graph nodes."""

    config: Config
    conn: Connection
    project_id: uuid.UUID
    run_id: uuid.UUID
    artefact_id: uuid.UUID
    provider: InferenceProvider
    block_ids: dict[str, Any]
    error: str | None


def _run_echo(state: HarnessState) -> HarnessState:
    conn = state["conn"]
    project_id = state["project_id"]
    run_id = state["run_id"]
    config = state["config"]

    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="component.started",
        payload={"component": config.component},
    )
    log.info("component.started", component=config.component)

    try:
        ids = produce_grounded_block(
            conn,
            artefact_id=state["artefact_id"],
            source_snapshot_id=config.source_snapshot_id,
            provider=state["provider"],
        )
    except GroundingError as exc:
        log.warning("grounding.failed", error=str(exc))
        fail_payload: dict[str, Any] = {"component": config.component, "error": str(exc)}
        if exc.block_id is not None:
            fail_payload["block_id"] = str(exc.block_id)
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.failed",
            payload=fail_payload,
        )
        return {**state, "error": str(exc)}

    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="component.completed",
        payload={"component": config.component},
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="block.written",
        payload={"block_id": str(ids["block_id"])},
    )
    log.info("block.written", block_id=str(ids["block_id"]))
    return {**state, "block_ids": ids}


def _dispatch(state: HarnessState) -> str:
    return state["config"].component


def _finish(state: HarnessState) -> HarnessState:
    conn = state["conn"]
    project_id = state["project_id"]
    run_id = state["run_id"]
    now = datetime.now(UTC)

    if state.get("error"):
        status = "failed"
        event_type = "run.failed"
        payload: dict[str, Any] = {"error": state["error"]}
    else:
        status = "succeeded"
        event_type = "run.completed"
        payload = {}

    result = conn.execute(
        runs.update()
        .where(runs.c.run_id == run_id)
        .values(status=status, ended_at=now)
    )
    assert result.rowcount == 1, f"Expected 1 run row updated, got {result.rowcount}"
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type=event_type,
        payload=payload,
    )
    log.info(event_type, run_id=str(run_id))
    return state


def build_graph() -> Any:
    """Build and compile the fixed StateGraph that dispatches components by name.

    Returns:
        The compiled LangGraph graph ready to ``invoke``.
    """
    g: StateGraph[HarnessState] = StateGraph(HarnessState)
    g.add_node("dispatch", lambda s: s)           # entry — routes by component name
    g.add_node("echo", _run_echo)
    g.add_node("finish", _finish)

    g.set_entry_point("dispatch")
    g.add_conditional_edges("dispatch", _dispatch, {"echo": "echo"})
    g.add_edge("echo", "finish")
    g.add_edge("finish", END)
    return g.compile()


def run_harness(
    conn: Connection,
    *,
    config: Config,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    provider: InferenceProvider,
) -> dict[str, Any]:
    """Run the compiled harness graph for one run, persisting its output.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        config: Compiled execution spec naming the component and source.
        project_id: Owning project; must match the run's stored project.
        run_id: Pre-created run row to execute.
        provider: Inference provider used by the grounding leg.

    Returns:
        Persisted IDs (``artefact_id`` plus any block IDs); only ``artefact_id``
        if the run failed before a block was written.

    Raises:
        ValueError: If ``run_id`` is unknown or belongs to another project.
    """
    # Guard: verify run belongs to this project before any write
    stored_pid = conn.execute(
        select(runs.c.project_id).where(runs.c.run_id == run_id)
    ).scalar_one_or_none()
    if stored_pid is None:
        raise ValueError(f"run_id {run_id!r} not found")
    if stored_pid != project_id:
        raise ValueError(
            f"run_id {run_id!r} belongs to project {stored_pid!r}, not {project_id!r}"
        )

    # Create artefact record
    artefact_id = uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            project_id=project_id,
            title="Walking-skeleton output",
            created_at=datetime.now(UTC),
        )
    )

    graph = build_graph()
    initial: HarnessState = {
        "config": config,
        "conn": conn,
        "project_id": project_id,
        "run_id": run_id,
        "artefact_id": artefact_id,
        "provider": provider,
        "block_ids": {},
        "error": None,
    }
    final: HarnessState = graph.invoke(initial)
    return {
        "artefact_id": artefact_id,
        **final.get("block_ids", {}),
    }
