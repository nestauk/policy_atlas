"""Shared OpenAI client resolution and structured-output guards for backend seams.

These helpers are provider-specific (OpenAI SDK types and error shapes) but
generic across every live backend that calls the chat-completions or
embeddings APIs: client construction from an explicit or environment API key,
request kwargs shared across call sites, and the empty/unparsed-response
guards used after a ``parse`` or ``create`` call.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel

from policy_atlas.core.model_routes import live_api_key, route
from policy_atlas.core.usage import (
    UsageResult,
    log_usage,
    token_usage_from_provider,
    usage_details,
    usage_metadata,
)

#: How a call site uses the provider's prompt cache (task 056, contract D3).
#:
#: In plain terms, the provider can store the start (the "prefix") of a prompt and
#: bill it far more cheaply when a later call starts with the same text:
#:
#: - ``"auto"``: the provider's default. On every call over 1,024 tokens whose
#:   prefix is not already stored, it stores the prefix at 1.25 times the normal
#:   input price; when the prefix repeats, it reads it back at 5 to 10% of the price.
#: - ``"off"``: no storing and no reading. For one-shot prompts that never repeat,
#:   this saves the 25% storing surcharge. Measured caveat (GPT-6 re-test,
#:   2026-11-02): on OpenAI direct this is a true off; on Bedrock it stops the
#:   store (the cache write) being reported, but identical requests can still
#:   read a stored prefix.
#: - ``"breakpoint"``: store and read only the stable prefix (the system message).
#:   For sites whose system prompt repeats across calls but whose user message
#:   never does. It sends the same request body as ``"off"`` (explicit mode, so the
#:   provider stores nothing on its own) plus one breakpoint on the system message
#:   (the one place it may store). Without explicit mode the provider would still
#:   store every whole request at 1.25x, which is what the per-site measurement
#:   (``experiments/cache-modes-per-site-2026-11-02``) was careful not to send.
#:
#: The per-step table is ``evidence_search.synthesis.cache_modes.CACHE_MODES``,
#: which re-exports this type (it lives here so ``core`` never imports
#: ``evidence_search`` when it loads).
PromptCache = Literal["auto", "off", "breakpoint"]

@dataclass
class CallBudget:
    """Pre-run call ceiling; every call (initial or retry) reserves one slot.

    Shared bool-reserve call-budget counter for backend seams (extract,
    screen, select); the raise-on-exceed variant used by the clustering
    engine and characterise stays separate (different failure posture).
    """

    maximum: int
    used: int = 0

    def reserve(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


def resolve_openai_client(
    api_key: str | None,
    *,
    backend_name: str,
    timeout: float,
    max_retries: int,
) -> OpenAI:
    """Resolve the OpenAI API key and construct a client, failing loudly.

    Shared by both live backends so key-resolution policy lives in one place.
    The base address always comes from the selected route, so ``OPENAI_BASE_URL``
    in the environment is never consulted.

    Args:
        api_key: Explicit key, or ``None`` to read the variable the route names
            (``OPENAI_API_KEY`` on ``openai-direct``, ``AWS_BEARER_TOKEN_BEDROCK``
            on the Bedrock routes).
        backend_name: Backend class name for the error message.
        timeout: Per-request timeout in seconds.
        max_retries: SDK-level retry cap for transient failures.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """
    resolved_key = api_key or live_api_key()
    if not resolved_key:
        raise RuntimeError(f"{backend_name} requires {route().api_key_env} or an explicit api_key.")
    return OpenAI(
        api_key=resolved_key,
        base_url=route().openai_base_url,
        timeout=timeout,
        max_retries=max_retries,
    )


def openai_kwargs(
    model: str, *, reasoning_effort: str, prompt_cache: PromptCache
) -> dict[str, Any]:
    """Request kwargs shared by every OpenAI chat-completions call site.

    Every call site states its reasoning effort (task 056, D4): the value comes
    from the route file (``route().effort_for(step)``), never from a literal in
    code. ``"none"`` is sent as the string the provider expects.

    Args:
        model: The model id for this call site's route step.
        reasoning_effort: One of the route file's effort values.
        prompt_cache: The step's prompt-cache mode (:data:`PromptCache`).
            ``"off"`` and ``"breakpoint"`` add the request body that turns
            automatic storing off (``"breakpoint"`` then stores only at the
            breakpoint set on the messages, see :func:`with_system_breakpoint`);
            ``"auto"`` adds nothing.
    """
    kwargs: dict[str, Any] = {"model": model, "reasoning_effort": reasoning_effort}
    if prompt_cache in ("off", "breakpoint"):
        kwargs["extra_body"] = {"prompt_cache_options": {"mode": "explicit"}}
    return kwargs


def with_system_breakpoint(messages: list[Any]) -> list[Any]:
    """Return the messages with a cache breakpoint on the first system message.

    The breakpoint tells the provider to store and read only the prompt up to the
    end of the system message (the ``"breakpoint"`` mode). The first system
    message is rewritten into the content-part shape carrying the breakpoint;
    every other message is passed through untouched. The caller's list and
    message objects are never changed: a new list is returned.

    Args:
        messages: Chat messages; the first ``system`` message must hold its text
            as a plain string.

    Returns:
        A new list with the first system message rewritten (or an unchanged copy
        when there is no system message).
    """
    rewritten = list(messages)
    for index, message in enumerate(rewritten):
        if isinstance(message, Mapping) and message.get("role") == "system":
            if not isinstance(message.get("content"), str):
                raise TypeError(
                    "with_system_breakpoint: the first system message must hold its text "
                    f"as a plain string, not {type(message.get('content')).__name__}"
                )
            rewritten[index] = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": message["content"],
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ],
            }
            break
    return rewritten


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


def parse_structured[T: BaseModel](
    client: Any,
    *,
    messages: list[Any],
    response_format: type[T],
    usage_event: str,
    label: str,
    model: str,
    reasoning_effort: str,
    prompt_cache: PromptCache,
    **parse_kwargs: Any,
) -> UsageResult[T]:
    """Run one ``chat.completions.parse`` call and apply the shared guards.

    Shared by every live backend that calls structured-output parsing: the
    request, usage logging, and the no-choices/unparsed-response raises are
    identical across call sites; only the model, extra request kwargs,
    response schema, and error label vary.

    Args:
        client: The OpenAI client.
        messages: Chat messages for the call.
        response_format: The pydantic wire type to parse into.
        usage_event: structlog event name for usage logging.
        label: Human-readable call label used in guard error messages.
        model: The model id for this call site's route step.
        reasoning_effort: The step's effort (``route().effort_for(step)``).
        prompt_cache: The step's prompt-cache mode (:data:`PromptCache`);
            ``"breakpoint"`` sends the messages through
            :func:`with_system_breakpoint`.
        **parse_kwargs: Additional keyword arguments forwarded to
            ``chat.completions.parse`` (``max_completion_tokens``, ...).

    Returns:
        The parsed structured output plus provider-neutral token usage.

    Raises:
        RuntimeError: If the response has no choices or was not parsed.
    """
    response = client.chat.completions.parse(
        messages=with_system_breakpoint(messages) if prompt_cache == "breakpoint" else messages,
        response_format=response_format,
        **openai_kwargs(model, reasoning_effort=reasoning_effort, prompt_cache=prompt_cache),
        **parse_kwargs,
    )
    log_usage(usage_event, response.usage)
    parsed: T = require_parsed(response, label=label)
    return parsed, token_usage_from_provider(response.usage)


def traced_parse[T: BaseModel](
    client: Any,
    langfuse_client: Any,
    *,
    messages: list[Any],
    response_format: type[T],
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    usage_event: str,
    label: str,
    name: str,
    prompt_version: str,
    session_id: uuid.UUID | None = None,
    metadata: Mapping[str, Any] | None = None,
    clean: Callable[[T], T] | None = None,
    prompt_cache: PromptCache,
) -> UsageResult[T]:
    """Run :func:`parse_structured` under one Langfuse generation.

    The span records the messages, the parsed output, the model, the prompt
    version, any extra metadata and the token usage (``usage_details``, so
    Langfuse can price the call).

    Args:
        client: The OpenAI client.
        langfuse_client: Langfuse client, or ``None`` for no tracing.
        messages: Chat messages for the call.
        response_format: The pydantic wire type to parse into.
        model: Model id.
        reasoning_effort: The step's effort (``route().effort_for(step)``).
        max_output_tokens: Completion token cap.
        usage_event: structlog event name for usage logging.
        label: Call label used in guard error messages.
        name: Static Langfuse observation name.
        prompt_version: Recorded in the span metadata.
        session_id: Optional Langfuse session id.
        metadata: Extra span metadata, after the prompt version.
        clean: Optional step applied to the parsed output before it is
            traced and returned (for example a NUL scrub).
        prompt_cache: The step's prompt-cache mode (:data:`PromptCache`),
            forwarded to :func:`parse_structured` and recorded in the span
            metadata.

    Returns:
        The parsed (and cleaned) output plus token usage.

    Raises:
        RuntimeError: If the response has no choices or was not parsed.
    """
    # Local import: tracing imports this module (through core.embeddings).
    from policy_atlas.core import tracing

    def _call() -> UsageResult[T]:
        parsed, usage = parse_structured(
            client,
            messages=messages,
            response_format=response_format,
            usage_event=usage_event,
            label=label,
            model=model,
            reasoning_effort=reasoning_effort,
            prompt_cache=prompt_cache,
            max_completion_tokens=max_output_tokens,
        )
        return (clean(parsed) if clean is not None else parsed), usage

    def _update(span: Any, result: UsageResult[T]) -> None:
        parsed, usage = result
        span.update(
            usage_details=usage_details(usage),
            input={"messages": messages},
            output=parsed.model_dump(),
            model=model,
            metadata={
                "prompt_version": prompt_version,
                "reasoning_effort": reasoning_effort,
                "prompt_cache": prompt_cache,
                **(metadata or {}),
                **usage_metadata(usage),
            },
        )

    return tracing.traced_call(
        langfuse_client,
        name=name,
        as_type="generation",
        call=_call,
        session_id=session_id,
        update=_update,
    )


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
