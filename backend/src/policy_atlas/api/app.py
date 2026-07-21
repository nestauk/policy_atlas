"""FastAPI application factory and shared HTTP boundary behaviour."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, FastAPI, HTTPException, Request
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

log = structlog.get_logger()

_CONFLICT_CODES = {
    "run_active",
    "already_answered",
    "capacity",
    "planning_turn_in_progress",
}


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


def create_app(*, settings: Settings | None = None, routers: Iterable[APIRouter] = ()) -> FastAPI:
    """Create the Policy Atlas HTTP application.

    Args:
        settings: Explicit settings for tests, or validated environment settings.
        routers: Additional authenticated or public routers composed by later tasks.

    Returns:
        A configured FastAPI application factory result.
    """
    app_settings = settings if settings is not None else load_settings()
    app = FastAPI(
        title="Policy Atlas API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan(app_settings),
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
            raise HTTPException(status_code=503, detail="database is unavailable") from None
        return {"status": "ok"}

    # Imported here so resource routers can use ApiConflict without an import
    # cycle during module initialisation.
    from policy_atlas.api.routers.check_ins import router as check_ins_router
    from policy_atlas.api.routers.planning import router as planning_router
    from policy_atlas.api.routers.projects import router as projects_router
    from policy_atlas.api.routers.runs import router as runs_router
    from policy_atlas.api.routers.sse import router as sse_router

    for router in (
        projects_router,
        planning_router,
        runs_router,
        check_ins_router,
        sse_router,
        *routers,
    ):
        app.include_router(router)
    return app


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build the lifespan handler that owns process-wide API resources."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        executor = ThreadPoolExecutor(
            max_workers=settings.run_executor_max,
            thread_name_prefix="policy-atlas-walk",
        )
        http_client = httpx.Client(timeout=httpx.Timeout(5.0), follow_redirects=False)
        app.state.engine = engine
        app.state.run_executor = executor
        app.state.http_client = http_client
        app.state.authenticator = JwtAuthenticator(settings, http_client)
        try:
            report = continuation.startup_sweep(engine)
            for candidate in report.redispatch:
                executor.submit(
                    _claim_and_execute,
                    engine,
                    candidate.project_id,
                    candidate.capability_run_id,
                )
            yield
        finally:
            http_client.close()
            executor.shutdown(wait=True)
            engine.dispose()

    return lifespan


def _claim_and_execute(engine: Engine, project_id: Any, capability_run_id: Any) -> None:
    """Claim one durable continuation then execute it in a walk executor worker."""
    try:
        claim = continuation.claim_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
        )
        if claim is not None:
            continuation.execute_continuation(
                engine,
                project_id=claim.project_id,
                capability_run_id=claim.capability_run_id,
            )
    except Exception:
        log.exception(
            "continuation.startup_dispatch_failed",
            project_id=str(project_id),
            capability_run_id=str(capability_run_id),
        )


def _install_exception_handlers(app: FastAPI) -> None:
    """Install the one contract error-envelope implementation on an app."""

    @app.exception_handler(ApiConflict)
    async def api_conflict_handler(_: Request, exc: ApiConflict) -> JSONResponse:
        return _error_response(409, exc.code, exc.message)

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
            return _error_response(404, "not_found", "resource not found")
        if exc.status_code == 400:
            return _error_response(400, "malformed", "malformed request")
        if exc.status_code == 422:
            return _error_response(422, "validation_error", "request validation failed")
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
