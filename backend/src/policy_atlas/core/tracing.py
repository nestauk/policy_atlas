"""Langfuse telemetry wrappers for live model traffic.

Telemetry is the third runtime egress destination in task 009: user-operated
Langfuse instances. By decision 13, traces carry full I/O payloads for eval-ready
spans, while keys remain env-only. Without both Langfuse keys this module is a
no-op, keeping the suite deterministic and egress-free and avoiding SDK auto-init.
"""

from __future__ import annotations

import contextvars
import os
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, Future
from contextlib import contextmanager
from threading import Lock
from typing import Any, Literal

from langfuse import Langfuse, propagate_attributes

from policy_atlas.core import embeddings
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.usage import UsageResult, usage_metadata
from policy_atlas.evidence_search.corpus import theme_grouping
from policy_atlas.evidence_search.corpus.theme_grouping import (
    GroupingDoc,
    Theme,
    ThemeGroupingBackend,
)
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID

_ObservationType = Literal["embedding", "generation", "span"]


def submit_with_context[T](
    executor: Executor, fn: Callable[..., T], *args: Any, **kwargs: Any
) -> Future[T]:
    """Submit a worker under the caller's current contextvars context.

    Capturing at submit time carries both the active Langfuse/OTel observation
    context and structlog's bound contextvars into executor workers.

    Args:
        executor: Executor receiving the work item.
        fn: Callable to run inside the captured context.
        *args: Positional arguments for ``fn``.
        **kwargs: Keyword arguments for ``fn``.

    Returns:
        Future for the submitted call.
    """
    ctx = contextvars.copy_context()
    return executor.submit(ctx.run, fn, *args, **kwargs)


def get_langfuse() -> Langfuse | None:
    """Create a Langfuse client only when env credentials are present.

    Returns:
        ``Langfuse`` when both ``LANGFUSE_PUBLIC_KEY`` and
        ``LANGFUSE_SECRET_KEY`` are non-empty; otherwise ``None``.

    Raises:
        RuntimeError: When the Langfuse configuration is partial — exactly one
            key set, or both keys set without a host. Without an explicit host
            the SDK silently defaults to Langfuse's SaaS cloud, which would
            send full-I/O traces outside the user-operated boundary.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key and not secret_key:
        return None
    if not public_key or not secret_key:
        raise RuntimeError(
            "Langfuse partially configured: exactly one of LANGFUSE_PUBLIC_KEY / "
            "LANGFUSE_SECRET_KEY is set. Set both (plus LANGFUSE_HOST) or neither."
        )
    host = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
    if not host:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY/SECRET_KEY are set but no LANGFUSE_HOST (or "
            "LANGFUSE_BASE_URL): refusing to fall back to the SDK's SaaS cloud "
            "default for full-I/O traces. Set the user-operated instance host."
        )
    # Traces carry full prompt I/O (acquired third-party text): never over
    # plaintext HTTP except to the local machine.
    if not host.startswith("https://") and not host.startswith(
        ("http://localhost", "http://127.0.0.1")
    ):
        raise RuntimeError(
            f"Langfuse host must be https:// (or http://localhost): got {host!r}. "
            "Full-I/O traces must not travel over plaintext HTTP."
        )
    return Langfuse(host=host)


@contextmanager
def _observation(client: Langfuse, *, name: str, as_type: _ObservationType) -> Iterator[Any]:
    try:
        manager: Any = client.start_as_current_observation(name=name, as_type=as_type)
        span: Any = manager.__enter__()
    except Exception:
        if as_type != "embedding":
            raise
        manager = client.start_as_current_observation(name=name, as_type="span")
        span = manager.__enter__()

    try:
        yield span
    except BaseException as exc:
        suppressed = bool(manager.__exit__(type(exc), exc, exc.__traceback__))
        if not suppressed:
            raise
    else:
        manager.__exit__(None, None, None)


def traced_call[T](
    client: Langfuse | None,
    *,
    name: str,
    as_type: _ObservationType,
    call: Callable[[], T],
    session_id: uuid.UUID | None = None,
    update: Callable[[Any, T], None] | None = None,
    after: Callable[[Any, T], None] | None = None,
) -> T:
    """Run a provider call under an optional Langfuse observation.

    Args:
        client: Langfuse client, or ``None`` for the no-tracing fast path.
        name: Observation name. Callers may compute this before invocation.
        as_type: Langfuse observation type.
        call: Zero-argument function that performs the provider call and returns
            the parsed site-specific result.
        session_id: Optional Langfuse session id to attach to the current trace.
        update: Optional callback that records input/output/model/metadata on
            the open observation.
        after: Optional callback for extra work that must run before the
            observation closes, such as trace scoring derived from the result.

    Returns:
        The value returned by ``call``.
    """
    if client is None:
        return call()

    with _session_scope(session_id), _observation(client, name=name, as_type=as_type) as span:
        result = call()
        if update is not None:
            update(span, result)
        if after is not None:
            after(span, result)
        return result


@contextmanager
def _session_scope(session_id: uuid.UUID | None) -> Iterator[None]:
    """Propagate a Langfuse session id to every observation opened inside the scope.

    SDK 4.13 has no ``update_current_trace`` (the pre-fix code silently no-opped
    on every trace, chat and planning alike — confirmed live, sessionId null
    since 2026-08-09): the v4 seam is ``propagate_attributes``, which only
    reaches observations OPENED while its context is active. Callers must
    therefore wrap the WHOLE observation-creation call in this scope, never
    update a session after the observation already opened.

    Args:
        session_id: Conversation/session id to attach, or ``None`` for a no-op.
    """
    if session_id is None:
        yield
        return
    with propagate_attributes(session_id=str(session_id)):
        yield


class TracedEmbeddingBackend:
    """Langfuse tracing wrapper for a live embedding backend.

    Args:
        backend: Inner embedding backend.
        client: Langfuse client created by ``get_langfuse``.
    """

    def __init__(self, backend: EmbeddingBackend, client: Langfuse) -> None:
        self._backend = backend
        self._client = client
        self._batch_count = 0
        self._lock = Lock()

    @property
    def mode(self) -> str:
        """Return the wrapped backend mode."""
        return self._backend.mode

    def _next_batch_index(self) -> int:
        with self._lock:
            self._batch_count += 1
            return self._batch_count

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts and trace the batch I/O.

        Args:
            texts: Text units to embed.

        Returns:
            Vectors returned by the wrapped backend.
        """
        batch_index = self._next_batch_index()
        with _observation(
            self._client,
            name=f"embed:batch{batch_index}",
            as_type="embedding",
        ) as span:
            vectors = self._backend.embed_texts(texts)
            span.update(
                input={"texts": texts},
                output={
                    "vector_count": len(vectors),
                    "dimensions": embeddings.EMBEDDING_DIMENSIONS,
                },
                metadata={
                    "embedding_profile": embeddings.EMBEDDING_PROFILE,
                    "unit_policy": embeddings.UNIT_POLICY,
                    "model": embeddings.EMBEDDING_MODEL,
                    "text_count": len(texts),
                },
            )
            return vectors


class TracedThemeGroupingBackend:
    """Langfuse tracing wrapper for a live theme grouping backend.

    Args:
        backend: Inner theme grouping backend.
        client: Langfuse client created by ``get_langfuse``.
    """

    def __init__(self, backend: ThemeGroupingBackend, client: Langfuse) -> None:
        self._backend = backend
        self._client = client
        self._assign_count = 0
        self._lock = Lock()

    @property
    def mode(self) -> str:
        """Return the wrapped backend mode."""
        return self._backend.mode

    def _next_assign_index(self) -> int:
        with self._lock:
            self._assign_count += 1
            return self._assign_count

    def discover(
        self,
        docs: list[GroupingDoc],
        *,
        intent: str,
        min_themes: int,
        max_themes: int,
        guidance: list[str] | None = None,
    ) -> UsageResult[list[Theme]]:
        """Discover themes and trace full generation I/O.

        Args:
            docs: Documents to group.
            intent: Evidence-scope intent.
            min_themes: Requested minimum theme count.
            max_themes: Requested maximum theme count.
            guidance: B5 ``characterise.guidance``, forwarded to the wrapped
                backend unchanged.

        Returns:
            Themes and token usage returned by the wrapped backend.
        """
        with _observation(self._client, name="discover", as_type="generation") as span:
            themes, usage = self._backend.discover(
                docs,
                intent=intent,
                min_themes=min_themes,
                max_themes=max_themes,
                guidance=guidance,
            )
            span.update(
                input={"intent": intent, "records": list(docs)},
                output={"themes": themes},
                metadata={
                    "prompt_version": theme_grouping.PROMPT_VERSION,
                    "doc_count": len(docs),
                    "min_themes": min_themes,
                    "max_themes": max_themes,
                    **usage_metadata(usage),
                },
                model=theme_grouping.DISCOVERY_MODEL,
            )
            return themes, usage

    def assign(
        self, batch: list[GroupingDoc], *, themes: list[Theme]
    ) -> UsageResult[dict[str, str]]:
        """Assign documents and trace full generation I/O.

        Args:
            batch: Documents to assign.
            themes: Fixed theme list.

        Returns:
            Assignments and token usage returned by the wrapped backend.
        """
        assign_index = self._next_assign_index()
        with _observation(
            self._client,
            name=f"assign:call{assign_index}",
            as_type="generation",
        ) as span:
            assignments, usage = self._backend.assign(batch, themes=themes)
            span.update(
                input={"themes": list(themes), "records": list(batch)},
                output={"assignments": assignments},
                metadata={
                    "prompt_version": theme_grouping.PROMPT_VERSION,
                    "batch_size": len(batch),
                    **usage_metadata(usage),
                },
                model=theme_grouping.ASSIGNMENT_MODEL,
            )
            return assignments, usage


@contextmanager
def component_span(
    client: Langfuse | None,
    *,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    component: str,
    session_id: uuid.UUID | None = None,
) -> Iterator[Any]:
    """Open run and component spans when tracing is enabled.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        run_id: Current run id.
        task_id: Current task id.
        component: Component name.
        session_id: Optional Langfuse session id shared across one conversation.

    Yields:
        The root ``run:{component}:{run_id}`` span (trace-level input/output
        derive from the root observation in the OTel SDK; the component in the
        name makes the Langfuse trace list scannable without opening traces),
        or ``None`` when tracing is off.
    """
    if client is None:
        yield None
        return

    with (
        _session_scope(session_id),
        _observation(client, name=f"run:{component}:{run_id}", as_type="span") as run_span,
    ):
        run_span.update(metadata={"task_id": str(task_id), "run_id": str(run_id)})
        with _observation(
            client,
            name=f"component:{component}",
            as_type="span",
        ) as component_observation:
            component_observation.update(metadata={"component": component})
            yield run_span


def _trace_root(root_span: Any, *, input: dict[str, Any], output: Any) -> None:
    """Update the root span with trace input/output, when one exists.

    Shared preamble for every ``*_score_summary`` function below; callers
    check ``client is None`` themselves first, since that check also gates
    whether the rest of the function's scoring calls run.

    Args:
        root_span: The ``run:{component}:{run_id}`` root span, or ``None``.
        input: Trace input payload.
        output: Trace output payload (the component summary).
    """
    if root_span is not None:
        root_span.update(input=input, output=output)


def score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    intent: str | None = None,
    root_span: Any = None,
) -> None:
    """Attach summary scores and trace-level I/O to the current Langfuse trace.

    Trace input/output derive from the root observation, making the run legible
    from the trace *list* view; the full per-call payloads stay on the nested
    observations.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Characterise landscape summary — becomes the trace output.
        intent: Evidence-scope intent — becomes the trace input.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(root_span, input={"component": "characterise", "intent": intent}, output=summary)
    client.score_current_trace(
        name="unclustered_share",
        value=float(summary["unclustered"]["share"]),
        data_type="NUMERIC",
    )
    client.score_current_trace(
        name="grouping_repair_taken",
        value=1.0 if "repair_path_taken" in summary.get("flags", []) else 0.0,
        data_type="NUMERIC",
    )


def extraction_score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    root_span: Any = None,
) -> None:
    """Attach the extract run's grounding scores to the current Langfuse trace.

    The 009 ``score_summary`` pattern; task 011 rev 1.4 — extraction quality
    measurable from the first live run.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Extract component summary payload — becomes the trace output.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(
        root_span,
        input={"component": "extract", "selection_run_id": summary["selection_run_id"]},
        output=summary,
    )
    counts = summary["counts"]
    profiles = counts["profiles"]
    iof_counts = profiles.get(IOF_PROFILE_ID, {})
    iof_findings = iof_counts.get("findings")
    findings = iof_findings if isinstance(iof_findings, dict) else {}
    total = findings.get("total", 0)
    if total > 0:
        client.score_current_trace(
            name="quote_verified_share",
            value=1.0 - findings.get("quote_unverified", 0) / total,
            data_type="NUMERIC",
        )
    selected = counts.get("selected", 0)
    if selected > 0 and iof_counts:
        client.score_current_trace(
            name="no_findings_share",
            value=iof_counts.get("no_findings", 0) / selected,
            data_type="NUMERIC",
        )
    failure_count = sum(
        block.get("failed", 0)
        for block in profiles.values()
        if isinstance(block, dict)
    )
    client.score_current_trace(
        name="extraction_failure_count",
        value=float(failure_count),
        data_type="NUMERIC",
    )
    client.score_current_trace(
        name="dedup_collapsed_count",
        value=float(findings.get("dedup_collapsed", 0)),
        data_type="NUMERIC",
    )
    icf_block = profiles.get(ICF_PROFILE_ID)
    icf_counts = icf_block if isinstance(icf_block, dict) else {}
    icf_findings = icf_counts.get("findings")
    if isinstance(icf_findings, dict):
        client.score_current_trace(
            name="icf_findings_total",
            value=float(icf_findings.get("total", 0)),
            data_type="NUMERIC",
        )


def grouping_score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    root_span: Any = None,
) -> None:
    """Attach the group run's partition scores to the current Langfuse trace.

    The 009 ``score_summary`` pattern, mirroring ``extraction_score_summary``
    (task 012).

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Group component summary payload — becomes the trace output.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(
        root_span,
        input={"component": "group", "facets": summary.get("facets", [])},
        output=summary,
    )
    # Reaching component.completed means the partition validated; a failed
    # partition raises before this point, so 0.0 is unreachable here.
    client.score_current_trace(
        name="partition_valid",
        value=1.0,
        data_type="NUMERIC",
    )
    counts = summary.get("counts", {})
    if isinstance(counts, dict):
        finding_counts = [
            value
            for value in counts.values()
            if isinstance(value, dict) and "eligible_base" in value
        ]
        findings_total = sum(int(value.get("eligible_base", 0)) for value in finding_counts)
        ungrouped = sum(int(value.get("ungrouped", 0)) for value in finding_counts)
        no_value = sum(int(value.get("no_value", 0)) for value in finding_counts)
        group_count = sum(int(value.get("groups", 0)) for value in finding_counts)
    else:
        findings_total = 0
        ungrouped = 0
        no_value = 0
        group_count = 0
    if findings_total > 0:
        client.score_current_trace(
            name="ungrouped_share",
            value=ungrouped / findings_total,
            data_type="NUMERIC",
        )
        client.score_current_trace(
            name="no_value_share",
            value=no_value / findings_total,
            data_type="NUMERIC",
        )
    else:
        client.score_current_trace(
            name="ungrouped_share",
            value=0.0,
            data_type="NUMERIC",
        )
        client.score_current_trace(
            name="no_value_share",
            value=0.0,
            data_type="NUMERIC",
        )
    client.score_current_trace(
        name="group_count",
        value=float(group_count),
        data_type="NUMERIC",
    )


def synthesis_score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    root_span: Any = None,
) -> None:
    """Attach the synthesise run's claim/citation scores to the current Langfuse trace.

    The 009 ``score_summary`` pattern, mirroring ``grouping_score_summary``
    (task 012).

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Synthesise component summary payload — becomes the trace output.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(
        root_span,
        input={"component": "synthesise", "artefact_id": summary["artefact_id"]},
        output=summary,
    )
    counts = summary["counts"]
    claims_total = sum(counts["claims_total"].values())
    unsupported = counts["claims_by_verdict_lane"].get("unsupported_mis_cited", 0)
    if claims_total > 0:
        client.score_current_trace(
            name="claims_valid_share",
            value=(claims_total - unsupported) / claims_total,
            data_type="NUMERIC",
        )
        client.score_current_trace(
            name="unsupported_share",
            value=unsupported / claims_total,
            data_type="NUMERIC",
        )
    else:
        client.score_current_trace(
            name="claims_valid_share",
            value=0.0,
            data_type="NUMERIC",
        )
        client.score_current_trace(
            name="unsupported_share",
            value=0.0,
            data_type="NUMERIC",
        )
    # Per-anchor counts on both sides — citations_verified (citation rows)
    # and citations_unverified (flagged claims) count different units and
    # cannot form an honest ratio.
    anchors_verified = counts.get("anchors_verified", 0)
    anchors_unverified = counts.get("anchors_unverified", 0)
    anchors_seen = anchors_verified + anchors_unverified
    if anchors_seen > 0:
        client.score_current_trace(
            name="citation_verified_share",
            value=anchors_verified / anchors_seen,
            data_type="NUMERIC",
        )
    else:
        client.score_current_trace(
            name="citation_verified_share",
            value=0.0,
            data_type="NUMERIC",
        )
    chunk_claims_total = counts["claims_total"].get("chunk", 0)
    chunk_claims_rejected = counts["chunk_claims_rejected"]
    chunk_denominator = chunk_claims_total + chunk_claims_rejected
    if chunk_denominator > 0:
        client.score_current_trace(
            name="chunk_rejection_share",
            value=chunk_claims_rejected / chunk_denominator,
            data_type="NUMERIC",
        )
    else:
        client.score_current_trace(
            name="chunk_rejection_share",
            value=0.0,
            data_type="NUMERIC",
        )


def screening_score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    root_span: Any = None,
) -> None:
    """Attach the screen run's consensus/demotion scores to the current Langfuse trace.

    The 009 ``score_summary`` pattern, mirroring ``grouping_score_summary``
    (task 014). ``summary`` may be a stage-1 (envelope) or stage-2 (full-text)
    screen component summary; the stage-specific scores are only emitted when
    the corresponding keys are present.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Screen component summary payload — becomes the trace output.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(root_span, input={"component": "screen"}, output=summary)
    client.score_current_trace(
        name="screen_failure_count",
        value=float(summary.get("failed", 0)),
        data_type="NUMERIC",
    )
    if "relevant" in summary and "not_relevant" in summary:
        decided = summary["relevant"] + summary["not_relevant"]
        if decided > 0:
            client.score_current_trace(
                name="non_unanimous_share",
                value=summary.get("non_unanimous", 0) / decided,
                data_type="NUMERIC",
            )
            client.score_current_trace(
                name="tie_broken_count",
                value=float(summary.get("tie_broken", 0)),
                data_type="NUMERIC",
            )
    if "stage2_screened" in summary:
        stage2_screened = summary["stage2_screened"]
        demoted_share = (
            summary.get("demoted", 0) / stage2_screened if stage2_screened > 0 else 0.0
        )
        client.score_current_trace(
            name="stage2_demoted_share",
            value=demoted_share,
            data_type="NUMERIC",
        )
        client.score_current_trace(
            name="stage2_failure_count",
            value=float(summary.get("failed", 0)),
            data_type="NUMERIC",
        )


def classification_score_summary(
    client: Langfuse | None,
    summary: dict[str, Any],
    *,
    root_span: Any = None,
) -> None:
    """Attach the classify run's evidence-type scores to the current Langfuse trace.

    The 009 ``score_summary`` pattern, mirroring ``grouping_score_summary``
    (task 014).

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Classify component summary payload — becomes the trace output.
        root_span: The ``run:{component}:{run_id}`` root span yielded by
            ``component_span``.
    """
    if client is None:
        return
    _trace_root(root_span, input={"component": "classify"}, output=summary)
    client.score_current_trace(
        name="classify_failure_count",
        value=float(summary.get("failed", 0)),
        data_type="NUMERIC",
    )
    classified = summary.get("classified", 0)
    by_type = summary.get("by_type", {})
    unknown_share = (
        by_type.get("Unknown / Insufficient information", 0) / classified
        if classified > 0
        else 0.0
    )
    client.score_current_trace(
        name="unknown_share",
        value=unknown_share,
        data_type="NUMERIC",
    )
    client.score_current_trace(
        name="tags_rejected_count",
        value=float(summary.get("tags_rejected", 0)),
        data_type="NUMERIC",
    )


def flush(client: Langfuse | None) -> None:
    """Flush pending Langfuse telemetry when tracing is enabled.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
    """
    if client is not None:
        client.flush()
