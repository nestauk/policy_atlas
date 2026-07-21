"""FastAPI dependency composition root for shared API infrastructure."""

from __future__ import annotations

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from fastapi import Request
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.auth import get_current_user
from policy_atlas.api.settings import Settings
from policy_atlas.core import tracing
from policy_atlas.runtime.orchestrate import live_planner_and_backends
from policy_atlas.runtime.orchestrator_backend import (
    OpenAIOrchestratorBackend,
    OrchestratorBackend,
    StubOrchestratorBackend,
)
from policy_atlas.runtime.planner import PlannerBackend, StubPlannerBackend
from policy_atlas.runtime.runner import RunnerBackends


def _live() -> bool:
    """Key presence is live intent — the same switch `orchestrate` uses."""
    return bool(os.environ.get("OPENAI_API_KEY"))


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


__all__ = [
    "get_conn",
    "get_current_user",
    "get_engine",
    "get_executor",
    "get_orchestrator_backend",
    "get_planner_backend",
    "get_runner_backends",
    "get_settings",
]
