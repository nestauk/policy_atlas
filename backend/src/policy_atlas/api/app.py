"""FastAPI application factory and shared HTTP boundary behaviour."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from policy_atlas.api import continuation
from policy_atlas.api.auth import JwtAuthenticator
from policy_atlas.api.contract import ErrorBody, ErrorEnvelope
from policy_atlas.api.settings import Settings, load_settings
from policy_atlas.core import tracing
from policy_atlas.core.logging import configure_logging

log = structlog.get_logger()

_CONFLICT_CODES = {
    "no_completed_run",
    "run_active",
    "already_answered",
    "capacity",
    "planning_turn_in_progress",
    "chat_turn_in_progress",
    "stale_turn",
    # 028 strand 3: the approved plan predates the newest completed planning
    # turn — review the demoted draft, re-approve, then start.
    "plan_stale",
    # Task 033 § 6 (i.5): a project in a portfolio carries that portfolio's
    # visibility, so setting the project's own visibility has no honest
    # answer — the two ways out are changing the Project's visibility and
    # leaving the Task out of the Project.
    "visibility_conflict",
}

_CAPACITY_CODES = {"chat_capacity"}


class ApiConflict(Exception):
    """A contract-defined conflict response raised by API service adapters.

    Args:
        code: One of the contract-defined 409 codes.
        message: Human-readable explanation for the caller.
    """

    def __init__(self, code: str, message: str) -> None:
        """Validate and retain the public conflict information.

        Args:
            code: Contract-defined conflict code.
            message: Human-readable response text.

        Raises:
            ValueError: If the code is not a declared 409 contract code.
        """
        if code not in _CONFLICT_CODES:
            raise ValueError(f"unsupported API conflict code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message


class ApiCapacity(Exception):
    """A contract-defined capacity response raised by API service adapters.

    Args:
        code: One of the contract-defined 429 codes.
        message: Human-readable explanation for the caller.
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in _CAPACITY_CODES:
            raise ValueError(f"unsupported API capacity code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message


def create_app(*, settings: Settings | None = None, routers: Iterable[APIRouter] = ()) -> FastAPI:
    """Create the Policy Atlas HTTP application.

    Args:
        settings: Explicit settings for tests, or validated environment settings.
        routers: Additional authenticated or public routers composed by later tasks.

    Returns:
        A configured FastAPI application factory result.
    """
    # The container starts uvicorn against create_app directly (backend
    # Makefile's `dev` target and the deployed image both use
    # `uvicorn ... --factory`), so this is the deployed entrypoint —
    # runtime/orchestrate.py's main() only covers the local CLI path. Must
    # run before anything below can log.
    configure_logging()
    app_settings = settings if settings is not None else load_settings()
    app = FastAPI(
        title="Policy Atlas API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan(app_settings),
        # Every route, including any a later slice adds: the request's log
        # context gains the route template the router just resolved. See
        # `bind_route_template`.
        dependencies=[Depends(bind_route_template)],
    )
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.app_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    _install_exception_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        """Bind the request's identity onto every log line the request emits.

        The admin trace is the only control the privileged read has while the
        privacy notice stands unedited (task 033 § 3a, § 12), and until this
        existed an `admin_read` line carried a row id and nothing about the
        request that produced it — so opening a project card and reading a
        colleague's whole chat transcript were indistinguishable in the log.
        Two `admin_read` lines with the same `kind` and `row_id` are still two
        different actions, and this is what says which.

        Bound here rather than passed to each emission site: `merge_contextvars`
        is already first in the processor chain (`core/logging.py`), so every
        line emitted anywhere under this request — including from the worker
        threads the runner and the SSE tail use, which inherit the context —
        carries these keys with no edit to any log call. That is also why a
        future trace shape gets the context for free.

        The **route template** is bound too, but not here: the router resolves
        the route inside the application, after every middleware has run, so
        `bind_route_template` adds it as an app-level dependency. This binds
        the literal path, which is available now and is the only thing a
        request that never reaches a route (a 404, a 401) can carry.

        Cleared on the way out so a pooled worker task cannot inherit the
        previous request's identity. The streaming responses keep theirs: the
        downstream app runs in its own task with a copied context, and a
        `ContextVar` reset here does not reach it.
        """
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()),
            http_method=request.method,
            http_path=request.url.path,
        )
        try:
            return await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        """Defense-in-depth response headers on the JSON API (review finding)."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Ignored by browsers over plain HTTP (dev); load-bearing behind TLS.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Report process liveness without touching external dependencies."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(request: Request) -> dict[str, str]:
        """Report readiness after verifying the database connection is usable."""
        try:
            with request.app.state.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except SQLAlchemyError:
            # Mapped to code "unavailable" by the envelope handler — a DB-down
            # readiness probe is not an "internal server error" (finding m8).
            raise HTTPException(status_code=503, detail="database is unavailable") from None
        return {"status": "ok"}

    # Imported here so resource routers can use ApiConflict without an import
    # cycle during module initialisation.
    from policy_atlas.api.routers.check_ins import router as check_ins_router
    from policy_atlas.api.routers.conversations import (
        project_router as project_conversations_router,
    )
    from policy_atlas.api.routers.conversations import router as conversations_router
    from policy_atlas.api.routers.me import router as me_router
    from policy_atlas.api.routers.planning import router as planning_router
    from policy_atlas.api.routers.portfolios import router as portfolios_router
    from policy_atlas.api.routers.projects import router as projects_router
    from policy_atlas.api.routers.read_models import router as read_models_router
    from policy_atlas.api.routers.runs import router as runs_router
    from policy_atlas.api.routers.sse import router as sse_router

    for router in (
        me_router,
        projects_router,
        portfolios_router,
        project_conversations_router,
        planning_router,
        runs_router,
        check_ins_router,
        conversations_router,
        sse_router,
        read_models_router,
        *routers,
    ):
        app.include_router(router)
    return app


async def bind_route_template(request: Request) -> None:
    """Add the matched route's path template to the request's log context.

    The other half of :func:`create_app`'s ``request_context`` middleware, and
    a dependency rather than more middleware for one reason: the router
    resolves the route *inside* the application, which is after every HTTP
    middleware has already run. A middleware can only see the literal path
    (which it binds); the template is knowable only once ``scope["route"]``
    exists, and an app-level dependency is the first code that runs with it.

    Pre-matching the route table from the middleware instead would mean
    reimplementing the router's own dispatch against FastAPI's private
    inclusion internals — the included routers are not flat in ``app.routes``
    and carry no public path — so this reads the answer the framework already
    computed.

    Declared on the application (``FastAPI(dependencies=…)``), so it applies to
    every route including ones a later slice adds, adds no request parameter
    and therefore nothing to the OpenAPI document. It writes to the context the
    middleware opened and cleared; nothing here needs to clean up.

    **`async` is load-bearing.** FastAPI runs a *sync* dependency in a worker
    thread, and `anyio` gives that thread a **copy** of the request's context —
    so a `ContextVar` bound there is bound on the copy and the endpoint's own
    log lines never see it. An async dependency runs in the request's task, and
    the binding is what every line under it inherits.

    Args:
        request: The inbound request, after routing.
    """
    template = getattr(request.scope.get("route"), "path", None)
    if isinstance(template, str):
        structlog.contextvars.bind_contextvars(route=template)


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build the lifespan handler that owns process-wide API resources."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
        executor = ThreadPoolExecutor(
            max_workers=settings.run_executor_max,
            thread_name_prefix="policy-atlas-walk",
        )
        http_client = httpx.Client(timeout=httpx.Timeout(5.0), follow_redirects=False)
        # Built once at boot so a bad Langfuse configuration fails the start,
        # not the first traced request. Per-request get_langfuse() calls return
        # this same client (the SDK keeps one client per public key).
        langfuse_client = tracing.get_langfuse()
        app.state.engine = engine
        app.state.run_executor = executor
        app.state.http_client = http_client
        app.state.authenticator = JwtAuthenticator(settings, http_client)
        try:
            from policy_atlas.api.deps import warn_on_partial_live_keys

            warn_on_partial_live_keys()
            report = continuation.startup_sweep(engine)
            for candidate in report.redispatch:
                executor.submit(
                    _claim_and_execute,
                    engine,
                    candidate.project_id,
                    candidate.capability_run_id,
                    claim_first=True,
                )
            for candidate in report.reexecute:
                # Already claimed before the previous process died, never
                # executed — execute directly, the claim is durable.
                executor.submit(
                    _claim_and_execute,
                    engine,
                    candidate.project_id,
                    candidate.capability_run_id,
                    claim_first=False,
                )
            yield
        finally:
            http_client.close()
            executor.shutdown(wait=True)
            if langfuse_client is not None:
                # Drains the span queue inside the ECS 10 s stop window.
                # ponytail: a detached chat thread mid-turn at shutdown can
                # still lose its tail spans; accepted.
                langfuse_client.shutdown()
            engine.dispose()

    return lifespan


def _claim_and_execute(
    engine: Engine, project_id: Any, capability_run_id: Any, *, claim_first: bool
) -> None:
    """Claim (unless pre-claimed) and execute one durable continuation.

    Builds the SAME key-driven backends as the request path (review finding
    codex-1, 2026-07-21: the drainer previously fell through to run_plan's stub
    bundle and NullIO — a redispatched real continuation executed against
    deterministic stubs and auto-continued every subsequent pause).
    """
    from policy_atlas.api.deps import get_orchestrator_backend, get_runner_backends
    from policy_atlas.api.run_io import ParkIO

    try:
        if claim_first:
            claim = continuation.claim_continuation(
                engine,
                project_id=project_id,
                capability_run_id=capability_run_id,
            )
            if claim is None:
                return
        continuation.execute_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            backends=get_runner_backends(),
            io=ParkIO(),
            orchestrator=get_orchestrator_backend(),
        )
    except Exception:
        log.exception(
            "continuation.startup_dispatch_failed",
            project_id=str(project_id),
            capability_run_id=str(capability_run_id),
        )
        continuation.mark_interrupted_best_effort(
            engine, project_id=project_id, capability_run_id=capability_run_id
        )


def _install_exception_handlers(app: FastAPI) -> None:
    """Install the one contract error-envelope implementation on an app."""

    @app.exception_handler(ApiConflict)
    async def api_conflict_handler(_: Request, exc: ApiConflict) -> JSONResponse:
        return _error_response(409, exc.code, exc.message)

    @app.exception_handler(ApiCapacity)
    async def api_capacity_handler(_: Request, exc: ApiCapacity) -> JSONResponse:
        return _error_response(429, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()]
        return _error_response(422, "validation_error", "request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 401:
            return _error_response(
                401,
                "unauthenticated",
                "authentication is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if exc.status_code == 404:
            # Deliberately generic: cross-owner and absent must stay
            # byte-identical (BOLA pin) — never pass router detail through.
            return _error_response(404, "not_found", "resource not found")
        # Router-authored 400/422 details are user-actionable ("change_mode
        # requires a supported new_mode") — surfacing them was the point of
        # raising with a message (review finding m2, 2026-07-21).
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail else None
        if exc.status_code == 400:
            return _error_response(400, "malformed", detail or "malformed request")
        if exc.status_code == 403:
            # Task 033 § 8 spends the 403 that web-api.md § Auth boundary
            # pre-reserved: the row is readable, the action is not. Distinct
            # from 404 by design — hiding a colleague's row from a colleague
            # who can already see it would be theatre.
            return _error_response(403, "forbidden", detail or "action is not permitted")
        if exc.status_code == 422:
            return _error_response(422, "validation_error", detail or "request validation failed")
        if exc.status_code == 503:
            return _error_response(503, "unavailable", detail or "service unavailable")
        return _error_response(exc.status_code, "internal", "internal server error")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("api.unhandled_exception", exception_type=type(exc).__name__)
        return _error_response(500, "internal", "internal server error")


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Serialize a contract error envelope without exposing implementation details."""
    envelope = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(envelope.model_dump(exclude_none=True)),
        headers=headers,
    )
