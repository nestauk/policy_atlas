"""Shared OpenAI client resolution and structured-output guards for backend seams.

These helpers are provider-specific (OpenAI SDK types and error shapes) but
generic across every live backend that calls the chat-completions or
embeddings APIs: client construction from an explicit or environment API key,
request kwargs shared across call sites, and the empty/unparsed-response
guards used after a ``parse`` or ``create`` call.
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


def resolve_openai_client(
    api_key: str | None,
    *,
    backend_name: str,
    timeout: float,
    max_retries: int,
) -> OpenAI:
    """Resolve the OpenAI API key and construct a client, failing loudly.

    Shared by both live backends so key-resolution policy lives in one place.

    Args:
        api_key: Explicit key, or ``None`` to read ``OPENAI_API_KEY``.
        backend_name: Backend class name for the error message.
        timeout: Per-request timeout in seconds.
        max_retries: SDK-level retry cap for transient failures.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_key:
        raise RuntimeError(f"{backend_name} requires OPENAI_API_KEY or an explicit api_key.")
    return OpenAI(api_key=resolved_key, timeout=timeout, max_retries=max_retries)


def openai_kwargs(model: str, *, reasoning_effort: str | None = None) -> dict[str, Any]:
    """Request kwargs shared by OpenAI chat-completions call sites.

    Omits reasoning_effort when None so non-reasoning call sites are byte-identical.
    Provider-neutral by shape: a future Bedrock backend maps or ignores the string.
    """
    kwargs: dict[str, Any] = {"model": model}
    if reasoning_effort is not None:
        kwargs["reasoning_effort"] = reasoning_effort
    return kwargs


def require_parsed(response: Any, *, label: str) -> Any:
    """Return the response's parsed structured output or fail loud.

    Shared by the live chat backends so the empty/unparsed-response checks
    live in one place.

    Args:
        response: A chat-completions ``parse`` response.
        label: Human-readable call label for the error message.

    Raises:
        RuntimeError: If the response has no choices or was not parsed.
    """
    if not response.choices:
        raise RuntimeError(f"OpenAI {label} response had no choices.")
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError(f"OpenAI {label} response was not parsed.")
    return parsed


def require_single_tool_call(response: Any, *, label: str) -> Any:
    """Return the response's single tool call or fail loud.

    Args:
        response: A chat-completions ``create`` response.
        label: Human-readable call label for the error message.

    Raises:
        RuntimeError: If the response has no choices, no tool call, or more
            than one tool call.
    """
    if not response.choices:
        raise RuntimeError(f"OpenAI {label} response had no choices.")
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise RuntimeError(f"OpenAI {label} response had no tool call.")
    if len(tool_calls) != 1:
        raise RuntimeError(f"OpenAI {label} response had multiple tool calls.")
    return tool_calls[0]
