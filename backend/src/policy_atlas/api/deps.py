"""FastAPI dependency composition root for shared API infrastructure."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from fastapi import Request
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.auth import get_current_user
from policy_atlas.api.settings import Settings
from policy_atlas.runtime.orchestrator_backend import OrchestratorBackend, StubOrchestratorBackend
from policy_atlas.runtime.planner import OpenAIPlannerBackend, PlannerBackend
from policy_atlas.runtime.runner import RunnerBackends


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
    """Build the production planner backend at the API boundary.

    Returns:
        The runtime planner implementation. Tests override this dependency with
        a scripted backend before creating a client.
    """
    return OpenAIPlannerBackend()


def get_runner_backends() -> RunnerBackends:
    """Build the runtime runner backend bundle for a dispatched walk.

    Returns:
        A lazily-resolved runtime backend bundle. Tests override this seam with
        deterministic component doubles.
    """
    return RunnerBackends()


def get_orchestrator_backend() -> OrchestratorBackend:
    """Return the steering-router backend used for free-text compilation.

    Returns:
        A deterministic runtime router unless deployment composition replaces
        this dependency with its configured backend.
    """
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
