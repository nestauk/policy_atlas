"""PostHog AI Observability context shared by live model backends.

The application already centralises OpenAI client construction in
:mod:`policy_atlas.core.openai_client` and opens user/session scopes in
:mod:`policy_atlas.core.tracing`. This module joins those two seams so every
wrapped OpenAI call and local tool execution shares the same AI session, trace,
and authenticated subject without changing model request semantics.
"""

from __future__ import annotations

import atexit
import contextvars
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import structlog
from posthog import Posthog
from posthog.ai.openai import OpenAI as PostHogOpenAI

log = structlog.get_logger()


@dataclass(frozen=True)
class AIContext:
    """The identifiers that group one product operation in AI Observability."""

    session_id: str
    trace_id: str
    distinct_id: str | None


_context: contextvars.ContextVar[AIContext | None] = contextvars.ContextVar(
    "posthog_ai_context", default=None
)
_client: Posthog | None = None
_fallback_client_created = False
_bedrock_instrumented = False
_bedrock_provider: Any | None = None


def configure_posthog_client(client: Posthog | None) -> None:
    """Reuse the process-scoped PostHog client created by the application factory."""
    global _client
    if client is not None:
        _client = client


def _configured_client() -> Posthog | None:
    """Return the shared client, creating a CLI/worker client only when configured."""
    global _client, _fallback_client_created
    if _client is not None:
        return _client
    token = os.environ.get("POSTHOG_PROJECT_TOKEN")
    host = os.environ.get("POSTHOG_HOST")
    if not token or not host:
        return None
    client = Posthog(token, host=host, privacy_mode=False)
    _client = client
    if not _fallback_client_created:
        atexit.register(client.shutdown)
        _fallback_client_created = True
    return client


def openai_client(*, api_key: str, base_url: str | None, max_retries: int) -> Any:
    """Build the PostHog OpenAI wrapper when analytics is configured.

    A missing PostHog configuration retains the app's existing OpenAI client
    and request behaviour; analytics must never make a model call fail.
    """
    client = _configured_client()
    if client is None:
        from openai import OpenAI

        return OpenAI(api_key=api_key, base_url=base_url, max_retries=max_retries)
    return PostHogOpenAI(
        api_key=api_key,
        base_url=base_url,
        max_retries=max_retries,
        posthog_client=client,
    )


def _default_context() -> AIContext:
    """Return a process-scoped session for work without a product conversation."""
    context = _context.get()
    if context is not None:
        return context
    context = AIContext(
        session_id=f"process-{os.getpid()}",
        trace_id=str(uuid.uuid4()),
        distinct_id=None,
    )
    _context.set(context)
    return context


@contextmanager
def context(*, session_id: uuid.UUID | str | None, user_id: str | None) -> Iterator[None]:
    """Set a stable AI session and one trace for the enclosing product operation."""
    parent = _context.get()
    resolved_session = str(session_id) if session_id is not None else (
        parent.session_id if parent is not None else f"process-{os.getpid()}"
    )
    resolved_user = user_id if user_id is not None else (parent.distinct_id if parent else None)
    state = AIContext(
        session_id=resolved_session,
        trace_id=parent.trace_id if parent is not None else str(uuid.uuid4()),
        distinct_id=resolved_user,
    )
    token = _context.set(state)
    client = _configured_client()
    try:
        if client is None:
            yield
        else:
            with client.new_context():
                if state.distinct_id is not None:
                    client.identify_context(state.distinct_id)
                client.tag("$ai_session_id", state.session_id)
                yield
    finally:
        _context.reset(token)


def call_kwargs() -> dict[str, Any]:
    """Return wrapper-only arguments for the current AI operation."""
    if _configured_client() is None:
        return {}
    state = _default_context()
    result: dict[str, Any] = {
        "posthog_trace_id": state.trace_id,
        "posthog_properties": {"$ai_session_id": state.session_id},
    }
    if state.distinct_id is not None:
        result["posthog_distinct_id"] = state.distinct_id
    return result


def capture_tool_span(
    name: str, input_state: Any, output_state: Any, latency_s: float
) -> None:
    """Record a local read-tool execution as a child span without affecting work."""
    client = _configured_client()
    if client is None:
        return
    state = _default_context()
    try:
        client.capture(
            distinct_id=state.distinct_id or state.session_id,
            event="$ai_span",
            properties={
                "$ai_trace_id": state.trace_id,
                "$ai_session_id": state.session_id,
                "$ai_span_id": str(uuid.uuid4()),
                "$ai_span_name": name,
                "$ai_input_state": input_state,
                "$ai_output_state": output_state,
                "$ai_latency": latency_s,
            },
        )
    except Exception:
        log.warning("posthog.ai_tool_span_failed", tool_name=name)


def configure_bedrock_observability() -> None:
    """Instrument Bedrock before its boto3 client is constructed when available."""
    global _bedrock_instrumented, _bedrock_provider
    if _bedrock_instrumented or _configured_client() is None:
        return
    token = os.environ.get("POSTHOG_PROJECT_TOKEN")
    host = os.environ.get("POSTHOG_HOST")
    if not token or not host:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from posthog.ai.otel import PostHogSpanProcessor

        provider = TracerProvider(Resource.create({SERVICE_NAME: "policy-atlas"}))
        provider.add_span_processor(PostHogSpanProcessor(api_key=token, host=host))
        trace.set_tracer_provider(provider)
        BotocoreInstrumentor().instrument()
        _bedrock_provider = provider
        _bedrock_instrumented = True
    except ImportError:
        log.warning("posthog.bedrock_instrumentation_unavailable")


def flush_bedrock_observability() -> None:
    """Flush buffered Bedrock spans during the application's normal shutdown."""
    if _bedrock_provider is None:
        return
    try:
        _bedrock_provider.force_flush(timeout_millis=5_000)
    except Exception:
        log.warning("posthog.bedrock_flush_failed")
