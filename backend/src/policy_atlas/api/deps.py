"""FastAPI dependency composition root for shared API infrastructure."""

from __future__ import annotations

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import structlog
from fastapi import Request
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.auth import get_current_user, get_optional_user
from policy_atlas.api.settings import Settings
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import (
    EmbeddingBackend,
    OpenAIEmbeddingBackend,
    StubEmbeddingBackend,
)
from policy_atlas.evidence_base.synthesis.grounding_judge import (
    GroundingJudgeBackend,
    OpenAIGroundingJudgeBackend,
    StubGroundingJudgeBackend,
)
from policy_atlas.runtime.chat_backend import ChatBackend, StubChatBackend
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend
from policy_atlas.runtime.orchestrate import live_planner_and_backends
from policy_atlas.runtime.orchestrator_backend import (
    OpenAIOrchestratorBackend,
    OrchestratorBackend,
    StubOrchestratorBackend,
)
from policy_atlas.runtime.planner import PlannerBackend, StubPlannerBackend
from policy_atlas.runtime.runner import RunnerBackends

log = structlog.get_logger()


#: Product-egress keys a fully-live deployment is expected to carry; missing
#: entries degrade coverage silently (the pinned live check ran with
#: OVERTON_API_KEY absent and produced an honest-but-thin evidence base).
_LIVE_SEARCH_KEYS = ("OVERTON_API_KEY", "OPENALEX_API_KEY")


def _live() -> bool:
    """Whether API seams compose live provider backends.

    ``PA_BACKEND_MODE`` makes the posture explicit (review finding adv-M4,
    2026-07-21): ``live`` demands the core key and fails loud without it,
    ``stub`` pins stubs even on a keyed box (demos, load tests, scans),
    and the default ``auto`` preserves the key-presence switch that
    ``orchestrate`` uses.
    """
    mode = os.environ.get("PA_BACKEND_MODE", "auto").strip().lower()
    if mode == "stub":
        return False
    if mode == "live":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "PA_BACKEND_MODE=live requires OPENAI_API_KEY to be configured"
            )
        return True
    return bool(os.environ.get("OPENAI_API_KEY"))


def warn_on_partial_live_keys() -> None:
    """Log loudly at boot when live mode runs with an incomplete search key set."""
    if not _live():
        return
    missing = [key for key in _LIVE_SEARCH_KEYS if not os.environ.get(key)]
    if missing:
        log.warning(
            "api.live_backends_missing_search_keys",
            missing=missing,
            consequence="searches degrade to the keyed subset; coverage will be thin",
        )


def get_settings(request: Request) -> Settings:
    """Return app-scoped settings validated during application creation.

    Args:
        request: Incoming request whose application owns the settings.

    Returns:
        The lifespan-independent application configuration.
    """
    return cast(Settings, request.app.state.settings)


def get_engine(request: Request) -> Engine:
    """Return the process-owned SQLAlchemy engine.

    Args:
        request: Incoming request whose application owns the engine.

    Returns:
        The lifespan-owned SQLAlchemy engine.
    """
    return cast(Engine, request.app.state.engine)


def get_conn(request: Request) -> Generator[Connection, None, None]:
    """Yield a short transaction with atomic commit/rollback semantics.

    Args:
        request: Incoming request whose application owns the engine.

    Yields:
        An open SQLAlchemy connection inside one transaction.
    """
    conn = get_engine(request).connect()
    transaction = conn.begin()
    try:
        yield conn
    except BaseException:
        transaction.rollback()
        raise
    else:
        transaction.commit()
    finally:
        conn.close()


def get_executor(request: Request) -> ThreadPoolExecutor:
    """Return the bounded executor used exclusively for walk execution.

    Args:
        request: Incoming request whose application owns the executor.

    Returns:
        The lifespan-owned walk executor.
    """
    return cast(ThreadPoolExecutor, request.app.state.run_executor)


def get_planner_backend() -> PlannerBackend:
    """Build the planner backend, key-driven exactly like `orchestrate`.

    Returns:
        The live OpenAI planner (Langfuse-traced) when `OPENAI_API_KEY` is
        configured, else the deterministic stub. Tests override this
        dependency with a scripted backend before creating a client.
    """
    if _live():
        planner, _ = live_planner_and_backends(tracing.get_langfuse())
        return planner
    return StubPlannerBackend()


def get_runner_backends() -> RunnerBackends:
    """Build the runner backend bundle, key-driven exactly like `orchestrate`.

    Returns:
        The full live backend set (search transports, OpenAI components,
        document fetcher, tracing) when `OPENAI_API_KEY` is configured, else
        the egress-free harness defaults. Tests override this seam with
        deterministic component doubles.
    """
    if _live():
        _, backends = live_planner_and_backends(tracing.get_langfuse())
        return backends
    return RunnerBackends()


def get_orchestrator_backend() -> OrchestratorBackend:
    """Return the steering-router/watch backend, key-driven like `orchestrate`.

    Returns:
        The live OpenAI orchestrator (the 024 router/watch — free-text
        compilation must go through the real router in live deployments) when
        `OPENAI_API_KEY` is configured, else the deterministic stub.
    """
    if _live():
        return OpenAIOrchestratorBackend(langfuse_client=tracing.get_langfuse())
    return StubOrchestratorBackend()


def get_chat_backend() -> ChatBackend:
    """Return the live streaming chat adapter or deterministic local stub.

    Returns:
        The key-selected chat backend. The component-level chat span owns
        session and trace recording, so this provider stays stateless.
    """
    if _live():
        return OpenAIChatBackend()
    return StubChatBackend()


def get_chat_embedding_backend() -> EmbeddingBackend:
    """Return the retrieval embedder matching the chat provider posture."""
    if _live():
        return OpenAIEmbeddingBackend()
    return StubEmbeddingBackend()


def get_grounding_judge_backend() -> GroundingJudgeBackend:
    """Return the key-selected existing grounding judge backend for chat enrichment."""
    if _live():
        return OpenAIGroundingJudgeBackend(langfuse_client=tracing.get_langfuse())
    return StubGroundingJudgeBackend()


__all__ = [
    "get_conn",
    "get_chat_backend",
    "get_chat_embedding_backend",
    "get_current_user",
    "get_optional_user",
    "get_engine",
    "get_executor",
    "get_grounding_judge_backend",
    "get_orchestrator_backend",
    "get_planner_backend",
    "get_runner_backends",
    "get_settings",
]
