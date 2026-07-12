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
)
from policy_atlas.appraise import AppraiseContext, appraise_sources
from policy_atlas.characterise import CharacteriseContext, CharacteriseFailure, characterise_scope
from policy_atlas.classification_backend import ClassificationBackend, StubClassificationBackend
from policy_atlas.classify import ClassifyContext, classify_sources
from policy_atlas.embeddings import EmbeddingBackend, StubEmbeddingBackend
from policy_atlas.extract import ExtractContext, extract_scope
from policy_atlas.extraction_backend import (
    ExtractionBackend,
    StubExtractionBackend,
    StubICFExtractionBackend,
)
from policy_atlas.facet_grouping import FacetGroupingBackend, StubFacetGroupingBackend
from policy_atlas.finding_vetter import FindingVetterBackend
from policy_atlas.grounding import GroundingError, produce_grounded_block
from policy_atlas.grounding_judge import GroundingJudgeBackend, StubGroundingJudgeBackend
from policy_atlas.group import GroupContext, group_findings
from policy_atlas.grouping import StubThemeGroupingBackend, ThemeGroupingBackend
from policy_atlas.icf_finding_vetter import ICFFindingVetterBackend
from policy_atlas.inference import InferenceProvider
from policy_atlas.ingest_full_text import (
    DocumentFetcher,
    FixtureFetcher,
    IngestFullTextContext,
    ingest_full_text_sources,
)
from policy_atlas.plan import Config
from policy_atlas.ranking import RankingBackend
from policy_atlas.schema import artefact, evidence_scope, runs
from policy_atlas.screen import ScreenContext, screen_sources
from policy_atlas.screening_backend import ScreeningBackend, StubScreeningBackend
from policy_atlas.search_generation import SearchGenerationBackend, StubSearchGenerationBackend
from policy_atlas.search_loop import run_search
from policy_atlas.select import SelectContext, select_scope
from policy_atlas.synthesis_backend import StubSynthesisBackend, SynthesisBackend
from policy_atlas.synthesise import SynthesiseContext, SynthesiseFailure, synthesise_scope

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
    search_generation_backend: SearchGenerationBackend
    document_fetcher: DocumentFetcher
    screening_backend: ScreeningBackend
    classification_backend: ClassificationBackend
    embedding_backend: EmbeddingBackend
    theme_grouping_backend: ThemeGroupingBackend
    ranking_backend: RankingBackend | None
    extraction_backend: ExtractionBackend
    finding_vetter_backend: FindingVetterBackend | None
    icf_extraction_backend: Any
    icf_finding_vetter_backend: ICFFindingVetterBackend | None
    facet_grouping_backend: FacetGroupingBackend
    synthesis_backend: SynthesisBackend
    grounding_judge_backend: GroundingJudgeBackend
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
    context_cls: Callable[..., Any],
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
        run_search,
        backends=state["search_backends"],
        generation_backend=state["search_generation_backend"],
        embedder=state["embedding_backend"],
    )
    return _run_scope_component(state, AcquireContext, sources_fn)


def _run_screen(state: HarnessState) -> HarnessState:
    sources_fn = functools.partial(
        screen_sources, screening_backend=state["screening_backend"]
    )
    return _run_scope_component(state, ScreenContext, sources_fn)


def _run_classify(state: HarnessState) -> HarnessState:
    sources_fn = functools.partial(
        classify_sources, classification_backend=state["classification_backend"]
    )
    return _run_scope_component(state, ClassifyContext, sources_fn)


def _run_appraise(state: HarnessState) -> HarnessState:
    return _run_scope_component(state, AppraiseContext, appraise_sources)


def _run_ingest_full_text(state: HarnessState) -> HarnessState:
    sources_fn = functools.partial(
        ingest_full_text_sources,
        fetcher=state["document_fetcher"],
        embedder=state["embedding_backend"],
    )
    return _run_scope_component(state, IngestFullTextContext, sources_fn)


def _run_select(state: HarnessState) -> HarnessState:
    config = state["config"]
    assert config.characterisation_run_id is not None  # registry-enforced at compile
    context_cls = functools.partial(
        SelectContext, characterisation_run_id=config.characterisation_run_id
    )
    sources_fn = functools.partial(
        select_scope, ranking_backend=state["ranking_backend"]
    )
    return _run_scope_component(state, context_cls, sources_fn)


def _run_extract(state: HarnessState) -> HarnessState:
    config = state["config"]
    assert config.selection_run_id is not None  # registry-enforced at compile
    context_cls = functools.partial(
        ExtractContext, selection_run_id=config.selection_run_id
    )
    sources_fn = functools.partial(
        extract_scope,
        extraction_backend=state["extraction_backend"],
        finding_vetter_backend=state["finding_vetter_backend"],
        icf_extraction_backend=state["icf_extraction_backend"],
        icf_finding_vetter_backend=state["icf_finding_vetter_backend"],
    )
    return _run_scope_component(state, context_cls, sources_fn)


def _run_group(state: HarnessState) -> HarnessState:
    config = state["config"]
    assert config.extraction_run_id is not None  # registry-enforced at compile
    context_cls = functools.partial(
        GroupContext, extraction_run_id=config.extraction_run_id
    )
    sources_fn = functools.partial(
        group_findings, facet_grouping_backend=state["facet_grouping_backend"]
    )
    return _run_scope_component(state, context_cls, sources_fn)


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
            theme_grouping_backend=state["theme_grouping_backend"],
        )
    except CharacteriseFailure as exc:
        events.append(
            conn, project_id=project_id, run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": exc.error, "coverage": exc.coverage},
        )
        return {**state, "error": exc.error}
    except Exception as exc:
        # str(exc) persists into the event log: provider raise paths inside
        # characterise_scope must keep reducing errors to exception type names
        # (never raw response bodies) before they can reach this handler.
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


def _run_synthesise(state: HarnessState) -> HarnessState:
    """Synthesise node with structured block-aware failure payloads.

    This mirrors ``_run_characterise`` instead of the generic
    ``_run_scope_component`` so ``SynthesiseFailure`` can name any blocks
    already persisted before a post-mint/post-block failure.
    """
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
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    ctx = SynthesiseContext(
        scope_id=row.evidence_scope_id,
        intent=row.intent,
        context=dict(row.context),
        characterisation_run_id=config.characterisation_run_id,
        selection_run_id=config.selection_run_id,
        extraction_run_id=config.extraction_run_id,
        grouping_run_id=config.grouping_run_id,
    )

    try:
        summary = synthesise_scope(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=ctx,
            synthesis_backend=state["synthesis_backend"],
            grounding_judge_backend=state["grounding_judge_backend"],
            embedding_backend=state["embedding_backend"],
        )
    except SynthesiseFailure as exc:
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.failed",
            payload={
                "component": config.component,
                "error": exc.error,
                "blocks_written": exc.blocks_written,
            },
        )
        return {**state, "error": exc.error}
    except Exception as exc:
        # Bounded: unexpected exceptions can carry provider/request detail
        # that must not land in the durable event log verbatim.
        err = f"{type(exc).__name__}: {str(exc)[:200]}"
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.failed",
            payload={"component": config.component, "error": err},
        )
        return {**state, "error": err}

    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
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
    g.add_node("select", _run_select)
    g.add_node("extract", _run_extract)
    g.add_node("group", _run_group)
    g.add_node("synthesise", _run_synthesise)
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
            "select": "select",
            "extract": "extract",
            "group": "group",
            "synthesise": "synthesise",
        },
    )
    g.add_edge("echo", "finish")
    g.add_edge("acquire", "finish")
    g.add_edge("screen", "finish")
    g.add_edge("classify", "finish")
    g.add_edge("appraise", "finish")
    g.add_edge("ingest_full_text", "finish")
    g.add_edge("characterise", "finish")
    g.add_edge("select", "finish")
    g.add_edge("extract", "finish")
    g.add_edge("group", "finish")
    g.add_edge("synthesise", "finish")
    g.add_edge("finish", END)
    return g.compile()


def _default_search_backends(search_backend_scope: str) -> list[SearchBackend]:
    if search_backend_scope == "both":
        backends: list[SearchBackend] = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
        return backends
    if search_backend_scope == "academic_only":
        return [OpenAlexFixtureBackend()]
    if search_backend_scope == "grey_lit_only":
        return [OvertonFixtureBackend()]
    raise ValueError(f"unknown search_backend_scope: {search_backend_scope!r}")


def run_harness(
    conn: Connection,
    *,
    config: Config,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    provider: InferenceProvider,
    search_backends: list[SearchBackend] | None = None,
    search_generation_backend: SearchGenerationBackend | None = None,
    document_fetcher: DocumentFetcher | None = None,
    screening_backend: ScreeningBackend | None = None,
    classification_backend: ClassificationBackend | None = None,
    embedding_backend: EmbeddingBackend | None = None,
    theme_grouping_backend: ThemeGroupingBackend | None = None,
    ranking_backend: RankingBackend | None = None,
    extraction_backend: ExtractionBackend | None = None,
    finding_vetter_backend: FindingVetterBackend | None = None,
    icf_extraction_backend: Any | None = None,
    icf_finding_vetter_backend: ICFFindingVetterBackend | None = None,
    facet_grouping_backend: FacetGroupingBackend | None = None,
    synthesis_backend: SynthesisBackend | None = None,
    grounding_judge_backend: GroundingJudgeBackend | None = None,
) -> dict[str, Any]:
    """Run the compiled harness graph for one run, persisting its output.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        config: Compiled execution spec naming the component and source.
        project_id: Owning project; must match the run's stored project.
        run_id: Pre-created run row to execute.
        provider: Inference provider used by the grounding leg.
        search_backends: Backends for the acquire component, searched in list
            order; when omitted, the compiled ``search_backend_scope`` selects
            the fixture backend set. The default remains both backends.
        search_generation_backend: Generation backend for search fan-out;
            defaults to ``StubSearchGenerationBackend()`` — no default egress.
        document_fetcher: Fetcher for the ingest_full_text component; defaults
            to ``FixtureFetcher()`` — the same injection pattern as
            ``search_backends`` (approved gated change 3, task 008).
        screening_backend: Screening backend for the screen component;
            defaults to ``StubScreeningBackend()`` — no default egress, the
            extraction backend pattern (approved gated change 2, task 014).
        classification_backend: Classification backend for the classify
            component; defaults to ``StubClassificationBackend()`` — no
            default egress, the extraction backend pattern (approved gated
            change 2, task 014).
        embedding_backend: Embedding backend threaded through state; defaults
            to ``StubEmbeddingBackend()`` — no default egress, same injection
            pattern as ``search_backends``.
        theme_grouping_backend: Theme grouping backend for the characterise component;
            defaults to ``StubThemeGroupingBackend()`` — no default egress, same
            injection pattern as ``search_backends``.
        ranking_backend: Ranking backend for the select component. This is
            passed straight through to the initial state; no stub is resolved
            here. ``None`` IS the deterministic ``coverage_stratified_v1``
            routing and stays ``None``; passing a backend selects
            ``llm_rerank_v1``. No default egress.
        extraction_backend: Extraction backend for the extract component;
            defaults to ``StubExtractionBackend()`` — no default egress, the
            theme grouping backend pattern (approved gated change 2, task 011).
        finding_vetter_backend: Post-extract finding vetter for the extract component
            (018 C5). Unlike the other backends this stays ``None`` by default
            with NO stub substitution — ``None`` means judging is off, so a
            caller that does not pass one gets byte-identical extract output
            to the pre-018-C5 pipeline.
        icf_extraction_backend: ICF extraction backend for the extract component;
            defaults to ``StubICFExtractionBackend()`` — no default egress.
        icf_finding_vetter_backend: Post-extract ICF finding vetter. ``None``
            means judging is off for ICF.
        facet_grouping_backend: Facet grouping backend for the group component;
            defaults to ``StubFacetGroupingBackend()`` — no default egress,
            approved gated change 2, task 012.
        synthesis_backend: Synthesis backend for the synthesise component;
            defaults to ``StubSynthesisBackend()`` — no default egress.
        grounding_judge_backend: Grounding judge backend for the synthesise component;
            defaults to ``StubGroundingJudgeBackend()`` — no default egress.

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
            else _default_search_backends(config.search_backend_scope)
        ),
        "search_generation_backend": (
            search_generation_backend
            if search_generation_backend is not None
            else StubSearchGenerationBackend()
        ),
        "document_fetcher": (
            document_fetcher if document_fetcher is not None else FixtureFetcher()
        ),
        "screening_backend": (
            screening_backend if screening_backend is not None else StubScreeningBackend()
        ),
        "classification_backend": (
            classification_backend
            if classification_backend is not None
            else StubClassificationBackend()
        ),
        # Consumed by the acquire/ingest_full_text partials (their embed passes);
        # characterise reads only theme_grouping_backend.
        "embedding_backend": (
            embedding_backend if embedding_backend is not None else StubEmbeddingBackend()
        ),
        "theme_grouping_backend": (
            theme_grouping_backend
            if theme_grouping_backend is not None
            else StubThemeGroupingBackend()
        ),
        "ranking_backend": ranking_backend,
        "extraction_backend": (
            extraction_backend if extraction_backend is not None else StubExtractionBackend()
        ),
        # No stub substitution (unlike every other backend key): None must
        # mean judging OFF, so extract_scope's own None default stays reachable.
        "finding_vetter_backend": finding_vetter_backend,
        "icf_extraction_backend": (
            icf_extraction_backend
            if icf_extraction_backend is not None
            else StubICFExtractionBackend()
        ),
        "icf_finding_vetter_backend": icf_finding_vetter_backend,
        "facet_grouping_backend": (
            facet_grouping_backend
            if facet_grouping_backend is not None
            else StubFacetGroupingBackend()
        ),
        "synthesis_backend": (
            synthesis_backend if synthesis_backend is not None else StubSynthesisBackend()
        ),
        "grounding_judge_backend": (
            grounding_judge_backend
            if grounding_judge_backend is not None
            else StubGroundingJudgeBackend()
        ),
        "block_ids": {},
        "error": None,
    }
    # Bind run/component correlation once for every log call this component
    # execution makes (structlog's merge_contextvars processor picks these up),
    # instead of hand-threading project_id/run_id through each log call. This is
    # the innermost boundary that sees exactly one component execution: each
    # run_harness call dispatches to exactly one node (routed by config.component),
    # and it's the direct caller of node-level log events (e.g. component.started,
    # grounding.failed) that today never carry project_id/run_id.
    with structlog.contextvars.bound_contextvars(
        project_id=str(project_id), run_id=str(run_id), component=config.component,
    ):
        final: HarnessState = graph.invoke(initial)
    return {
        "artefact_id": final.get("artefact_id"),
        **final.get("block_ids", {}),
    }
