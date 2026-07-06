"""Langfuse telemetry wrappers for live model traffic.

Telemetry is the third runtime egress destination in task 009: user-operated
Langfuse instances. By decision 13, traces carry full I/O payloads for eval-ready
spans, while keys remain env-only. Without both Langfuse keys this module is a
no-op, keeping the suite deterministic and egress-free and avoiding SDK auto-init.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any, Literal

from langfuse import Langfuse

from policy_atlas import embeddings, grouping
from policy_atlas.embeddings import EmbeddingBackend
from policy_atlas.grouping import GroupingBackend, GroupingDoc, Theme

_ObservationType = Literal["embedding", "generation", "span"]


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


class TracedGroupingBackend:
    """Langfuse tracing wrapper for a live grouping backend.

    Args:
        backend: Inner grouping backend.
        client: Langfuse client created by ``get_langfuse``.
    """

    def __init__(self, backend: GroupingBackend, client: Langfuse) -> None:
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
    ) -> list[Theme]:
        """Discover themes and trace full generation I/O.

        Args:
            docs: Documents to group.
            intent: Evidence-scope intent.
            min_themes: Requested minimum theme count.
            max_themes: Requested maximum theme count.

        Returns:
            Themes returned by the wrapped backend.
        """
        with _observation(self._client, name="discover", as_type="generation") as span:
            themes = self._backend.discover(
                docs,
                intent=intent,
                min_themes=min_themes,
                max_themes=max_themes,
            )
            span.update(
                input={"intent": intent, "records": list(docs)},
                output={"themes": themes},
                metadata={
                    "prompt_version": grouping.PROMPT_VERSION,
                    "doc_count": len(docs),
                    "min_themes": min_themes,
                    "max_themes": max_themes,
                },
                model=grouping.DISCOVERY_MODEL,
            )
            return themes

    def assign(self, batch: list[GroupingDoc], *, themes: list[Theme]) -> dict[str, str]:
        """Assign documents and trace full generation I/O.

        Args:
            batch: Documents to assign.
            themes: Fixed theme list.

        Returns:
            Assignments returned by the wrapped backend.
        """
        assign_index = self._next_assign_index()
        with _observation(
            self._client,
            name=f"assign:call{assign_index}",
            as_type="generation",
        ) as span:
            assignments = self._backend.assign(batch, themes=themes)
            span.update(
                input={"themes": list(themes), "records": list(batch)},
                output={"assignments": assignments},
                metadata={
                    "prompt_version": grouping.PROMPT_VERSION,
                    "batch_size": len(batch),
                },
                model=grouping.ASSIGNMENT_MODEL,
            )
            return assignments


@contextmanager
def component_span(
    client: Langfuse | None,
    *,
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    component: str,
) -> Iterator[None]:
    """Open run and component spans when tracing is enabled.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        run_id: Current run id.
        project_id: Current project id.
        component: Component name.

    Yields:
        ``None``.
    """
    if client is None:
        yield
        return

    with _observation(client, name=f"run:{run_id}", as_type="span") as run_span:
        run_span.update(metadata={"project_id": str(project_id), "run_id": str(run_id)})
        with _observation(
            client,
            name=f"component:{component}",
            as_type="span",
        ) as component_observation:
            component_observation.update(metadata={"component": component})
            yield


def score_summary(client: Langfuse | None, summary: dict[str, Any]) -> None:
    """Attach summary scores to the current Langfuse trace.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
        summary: Characterise landscape summary.
    """
    if client is None:
        return
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


def flush(client: Langfuse | None) -> None:
    """Flush pending Langfuse telemetry when tracing is enabled.

    Args:
        client: Langfuse client, or ``None`` for no-op tracing.
    """
    if client is not None:
        client.flush()
