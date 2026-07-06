"""Fixed LangGraph harness interpreting plan-as-data.

The StateGraph dispatches components by name from the compiled Config.
In-process this slice; durable checkpointer is a deferred seam.
Block-boundary commit is modelled as one event (component.completed + block.written).
"""

import functools
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.acquire import (
    AcquireContext,
    OpenAlexFixtureBackend,
    OvertonFixtureBackend,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.appraise import AppraiseContext, appraise_sources
from policy_atlas.characterise import CharacteriseContext, CharacteriseFailure, characterise_scope
from policy_atlas.classify import ClassifyContext, classify_sources
from policy_atlas.embeddings import EmbeddingBackend, StubEmbeddingBackend
from policy_atlas.grounding import GroundingError, produce_grounded_block
from policy_atlas.grouping import GroupingBackend, StubGroupingBackend
from policy_atlas.inference import InferenceProvider
from policy_atlas.ingest_full_text import (
    DocumentFetcher,
    FixtureFetcher,
    IngestFullTextContext,
    ingest_full_text_sources,
)
from policy_atlas.plan import Config
from policy_atlas.schema import artefact, evidence_scope, runs
from policy_atlas.screen import ScreenContext, screen_sources

log = structlog.get_logger()


class HarnessState(TypedDict):
    """Mutable state threaded through the harness graph nodes."""

    config: Config
    conn: Connection
    project_id: uuid.UUID
    run_id: uuid.UUID
    artefact_id: uuid.UUID | None  # set by _run_echo only; None for scope components
    provider: InferenceProvider
    search_backends: list[SearchBackend]
    document_fetcher: DocumentFetcher
    embedding_backend: EmbeddingBackend
    grouping_backend: GroupingBackend
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

    artefact_id = uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            project_id=project_id,
            title="Walking-skeleton output",
            created_at=datetime.now(UTC),
        )
    )

    if config.source_snapshot_id is None:
        raise RuntimeError("echo component requires source_snapshot_id")
    try:
        ids = produce_grounded_block(
            conn,
            artefact_id=artefact_id,
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
        return {**state, "artefact_id": artefact_id, "error": str(exc)}

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
    return {**state, "artefact_id": artefact_id, "block_ids": ids}


def _run_scope_component(
    state: HarnessState,
    context_cls: type,
    sources_fn: Callable[..., dict[str, Any]],
) -> HarnessState:
    """Shared implementation for the scope-driven harness nodes (screen/classify/appraise)."""
    conn = state["conn"]
    project_id = state["project_id"]
    run_id = state["run_id"]
    config = state["config"]

    events.append(
        conn, project_id=project_id, run_id=run_id,
        event_type="component.started",
        payload={"component": config.component},
    )
    log.info("component.started", component=config.component)

    row = conn.execute(
        select(evidence_scope)
        .where(evidence_scope.c.evidence_scope_id == config.evidence_scope_id)
        .where(evidence_scope.c.project_id == project_id)
    ).one_or_none()
    if row is None:
        err = (
            f"evidence_scope {config.evidence_scope_id!r} "
            f"not found for project {project_id!r}"
        )
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    ctx = context_cls(
        scope_id=row.evidence_scope_id,
        intent=row.intent,
        context=dict(row.context),
    )

    try:
        counts = sources_fn(conn, project_id=project_id, run_id=run_id, context=ctx)
    except Exception as exc:
        err = str(exc)
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    events.append(
        conn, project_id=project_id, run_id=run_id,
        event_type="component.completed",
        payload={"component": config.component, **counts},
    )
    log.info("component.completed", component=config.component, **counts)
    return state


def _run_acquire(state: HarnessState) -> HarnessState:
    sources_fn = functools.partial(
        acquire_sources,
        backends=state["search_backends"],
        embedder=state["embedding_backend"],
    )
    return _run_scope_component(state, AcquireContext, sources_fn)


def _run_screen(state: HarnessState) -> HarnessState:
    return _run_scope_component(state, ScreenContext, screen_sources)


def _run_classify(state: HarnessState) -> HarnessState:
    return _run_scope_component(state, ClassifyContext, classify_sources)


def _run_appraise(state: HarnessState) -> HarnessState:
    return _run_scope_component(state, AppraiseContext, appraise_sources)


def _run_ingest_full_text(state: HarnessState) -> HarnessState:
    sources_fn = functools.partial(
        ingest_full_text_sources,
        fetcher=state["document_fetcher"],
        embedder=state["embedding_backend"],
    )
    return _run_scope_component(state, IngestFullTextContext, sources_fn)


def _run_characterise(state: HarnessState) -> HarnessState:
    """Characterise node — not routed through ``_run_scope_component``: its generic
    except emits only {component, error}, and a ``CharacteriseFailure`` must carry
    coverage in the failure payload."""
    conn = state["conn"]
    project_id = state["project_id"]
    run_id = state["run_id"]
    config = state["config"]

    events.append(
        conn, project_id=project_id, run_id=run_id,
        event_type="component.started",
        payload={"component": config.component},
    )
    log.info("component.started", component=config.component)

    row = conn.execute(
        select(evidence_scope)
        .where(evidence_scope.c.evidence_scope_id == config.evidence_scope_id)
        .where(evidence_scope.c.project_id == project_id)
    ).one_or_none()
    if row is None:
        err = (
            f"evidence_scope {config.evidence_scope_id!r} "
            f"not found for project {project_id!r}"
        )
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    ctx = CharacteriseContext(
        scope_id=row.evidence_scope_id,
        intent=row.intent,
        context=dict(row.context),
    )

    try:
        summary = characterise_scope(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=ctx,
            grouping_backend=state["grouping_backend"],
        )
    except CharacteriseFailure as exc:
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": exc.error, "coverage": exc.coverage},
        )
        return {**state, "error": exc.error}
    except Exception as exc:
        err = str(exc)
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    events.append(
        conn, project_id=project_id, run_id=run_id,
        event_type="component.completed",
        payload={"component": config.component, **summary},
    )
    log.info("component.completed", component=config.component)
    return state


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
    g.add_node("acquire", _run_acquire)
    g.add_node("screen", _run_screen)
    g.add_node("classify", _run_classify)
    g.add_node("appraise", _run_appraise)
    g.add_node("ingest_full_text", _run_ingest_full_text)
    g.add_node("characterise", _run_characterise)
    g.add_node("finish", _finish)

    g.set_entry_point("dispatch")
    g.add_conditional_edges(
        "dispatch",
        _dispatch,
        {
            "echo": "echo",
            "acquire": "acquire",
            "screen": "screen",
            "classify": "classify",
            "appraise": "appraise",
            "ingest_full_text": "ingest_full_text",
            "characterise": "characterise",
        },
    )
    g.add_edge("echo", "finish")
    g.add_edge("acquire", "finish")
    g.add_edge("screen", "finish")
    g.add_edge("classify", "finish")
    g.add_edge("appraise", "finish")
    g.add_edge("ingest_full_text", "finish")
    g.add_edge("characterise", "finish")
    g.add_edge("finish", END)
    return g.compile()


def run_harness(
    conn: Connection,
    *,
    config: Config,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    provider: InferenceProvider,
    search_backends: list[SearchBackend] | None = None,
    document_fetcher: DocumentFetcher | None = None,
    embedding_backend: EmbeddingBackend | None = None,
    grouping_backend: GroupingBackend | None = None,
) -> dict[str, Any]:
    """Run the compiled harness graph for one run, persisting its output.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        config: Compiled execution spec naming the component and source.
        project_id: Owning project; must match the run's stored project.
        run_id: Pre-created run row to execute.
        provider: Inference provider used by the grounding leg.
        search_backends: Backends for the acquire component, searched in list
            order; defaults to the fixture pair (OpenAlex, Overton) — the same
            injection pattern as ``provider``.
        document_fetcher: Fetcher for the ingest_full_text component; defaults
            to ``FixtureFetcher()`` — the same injection pattern as
            ``search_backends`` (approved gated change 3, task 008).
        embedding_backend: Embedding backend threaded through state; defaults
            to ``StubEmbeddingBackend()`` — no default egress, same injection
            pattern as ``search_backends``.
        grouping_backend: Grouping backend for the characterise component;
            defaults to ``StubGroupingBackend()`` — no default egress, same
            injection pattern as ``search_backends``.

    Returns:
        Persisted IDs; ``artefact_id`` is None for non-echo components that do
        not write artefacts.

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

    graph = build_graph()
    initial: HarnessState = {
        "config": config,
        "conn": conn,
        "project_id": project_id,
        "run_id": run_id,
        "artefact_id": None,
        "provider": provider,
        "search_backends": (
            search_backends
            if search_backends is not None
            else [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
        ),
        "document_fetcher": (
            document_fetcher if document_fetcher is not None else FixtureFetcher()
        ),
        # Consumed by the acquire/ingest_full_text partials (their embed passes);
        # characterise reads only grouping_backend.
        "embedding_backend": (
            embedding_backend if embedding_backend is not None else StubEmbeddingBackend()
        ),
        "grouping_backend": (
            grouping_backend if grouping_backend is not None else StubGroupingBackend()
        ),
        "block_ids": {},
        "error": None,
    }
    final: HarnessState = graph.invoke(initial)
    return {
        "artefact_id": final.get("artefact_id"),
        **final.get("block_ids", {}),
    }
