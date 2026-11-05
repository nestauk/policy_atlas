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


def resolve_openai_client(api_key: str | None, *, backend_name: str) -> OpenAI:
    """Resolve the OpenAI API key and construct a client, failing loudly.

    Shared by every live backend so key-resolution policy lives in one place.
    The base address always comes from the selected route, so ``OPENAI_BASE_URL``
    in the environment is never consulted.

    The client never retries on its own (``max_retries=0``) and carries no
    timeout of its own (task 057, D12). Each request sends its step's timeout
    (``openai_kwargs(..., timeout_s=route().timeout_for(step))``), and the retries
    a model call gets (up to ``MODEL_CALL_ATTEMPTS`` attempts, three today; task 057
    review: code-review 9) are made by :func:`policy_atlas.core.tracing.traced_attempts`,
    so every attempt is its own Langfuse generation. Before task 057 the SDK
    retried up to twice, silently and untraced.

    Args:
        api_key: Explicit key, or ``None`` to read the variable the route names
            (``OPENAI_API_KEY`` on ``openai-direct``, ``AWS_BEARER_TOKEN_BEDROCK``
            on the Bedrock routes).
        backend_name: Backend class name for the error message.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """
    resolved_key = api_key or live_api_key()
    if not resolved_key:
        raise RuntimeError(f"{backend_name} requires {route().api_key_env} or an explicit api_key.")
    return OpenAI(
        api_key=resolved_key,
        base_url=route().openai_base_url,
        max_retries=0,
    )


def openai_kwargs(
    model: str, *, reasoning_effort: str, prompt_cache: PromptCache, timeout_s: float
) -> dict[str, Any]:
    """Request kwargs shared by every OpenAI chat-completions call site.

    Every call site states its reasoning effort (task 056, D4) and its timeout
    (task 057, D12): both come from the route file (``route().effort_for(step)``
    and ``route().timeout_for(step)``), never from a literal in code.
    ``"none"`` is sent as the string the provider expects.

    Args:
        model: The model id for this call site's route step.
        reasoning_effort: One of the route file's effort values.
        prompt_cache: The step's prompt-cache mode (:data:`PromptCache`).
            ``"off"`` and ``"breakpoint"`` add the request body that turns
            automatic storing off (``"breakpoint"`` then stores only at the
            breakpoint set on the messages, see :func:`with_system_breakpoint`);
            ``"auto"`` adds nothing.
        timeout_s: Seconds this one request may take before the SDK gives up
            on it (sent as the SDK's per-request ``timeout`` option).

    Returns:
        Keyword arguments for ``chat.completions.create`` / ``parse``.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "timeout": timeout_s,
    }
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
    timeout_s: float,
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
        timeout_s: The step's request timeout (``route().timeout_for(step)``).
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
        **openai_kwargs(
            model,
            reasoning_effort=reasoning_effort,
            prompt_cache=prompt_cache,
            timeout_s=timeout_s,
        ),
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
    step: str,
    reasoning_effort: str,
    timeout_s: float,
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
    """Run :func:`parse_structured` under Langfuse generations, one per attempt.

    The call runs under :func:`policy_atlas.core.tracing.traced_attempts`: a
    timeout or a passing provider failure is tried again, up to
    ``MODEL_CALL_ATTEMPTS`` attempts (three today; task 057 review: code-review 9),
    and each attempt is its own generation carrying the step, the attempt number and a shared
    call id. The successful attempt's span records the messages, the parsed
    output, the model, the prompt version, any extra metadata and the token
    usage (``usage_details``, so Langfuse can price the call).

    Args:
        client: The OpenAI client.
        langfuse_client: Langfuse client, or ``None`` for no tracing.
        messages: Chat messages for the call.
        response_format: The pydantic wire type to parse into.
        model: Model id.
        step: The route step name (recorded on every attempt's generation).
        reasoning_effort: The step's effort (``route().effort_for(step)``).
        timeout_s: The step's request timeout (``route().timeout_for(step)``).
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
            timeout_s=timeout_s,
            max_completion_tokens=max_output_tokens,
        )
        return (clean(parsed) if clean is not None else parsed), usage

    def _update(span: Any, result: UsageResult[T]) -> None:
        parsed, usage = result
        span.update(
            usage_details=usage_details(usage),
            output=parsed.model_dump(),
            metadata={
                "prompt_version": prompt_version,
                "reasoning_effort": reasoning_effort,
                "prompt_cache": prompt_cache,
                **(metadata or {}),
                **usage_metadata(usage),
            },
        )

    return tracing.traced_attempts(
        langfuse_client,
        name=name,
        step=step,
        call=_call,
        session_id=session_id,
        before=lambda span: span.update(input={"messages": messages}, model=model),
        update=_update,
    )


_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class JsonStringFieldDecoder:
    """Follow one top-level string field of a JSON object as it streams in.

    In plain terms: a streamed structured answer arrives as JSON text in small
    pieces, and one field of it (the planner's ``reply``, say) is the part the
    user should read while the rest is still being written. Feed each piece to
    :meth:`feed`; it returns the newly readable characters of that one field,
    already decoded (``\\n`` becomes a line break, ``\\u00e9`` becomes ``é``).
    Only a key of the outermost object counts, so the same name nested deeper,
    or written inside another string, is ignored. An escape split across two
    pieces is held until it is complete, and a ``\\uXXXX`` surrogate pair
    becomes one character. Once the field's closing quote arrives, every later
    piece returns ``""``. Task 058, N9.

    Args:
        field_name: The top-level key whose string value to follow.
    """

    def __init__(self, field_name: str) -> None:
        self._field_name = field_name
        self._depth = 0
        self._in_string = False
        self._string_is_key = False
        self._string_is_target = False
        self._raw_key: list[str] = []
        self._expect_key = False
        self._last_key: str | None = None
        self._value_pending = False
        self._escape = ""
        self._high_surrogate: int | None = None
        self.done = False

    def feed(self, fragment: str) -> str:
        """Consume one piece of the JSON text.

        Args:
            fragment: The next piece of the streamed JSON text.

        Returns:
            The field's newly decoded characters, or ``""`` when this piece
            holds none of them.
        """
        out: list[str] = []
        for char in fragment:
            if self.done:
                break
            if self._in_string:
                self._string_char(char, out)
            else:
                self._structural_char(char)
        return "".join(out)

    def _structural_char(self, char: str) -> None:
        if char == '"':
            self._in_string = True
            self._string_is_key = self._depth == 1 and self._expect_key
            self._string_is_target = (
                self._depth == 1
                and self._value_pending
                and self._last_key == self._field_name
            )
            self._raw_key = []
            if self._depth == 1:
                self._value_pending = False
            return
        if char in "{[":
            self._depth += 1
            self._expect_key = self._depth == 1 and char == "{"
            if self._depth == 2:
                self._value_pending = False
        elif char in "}]":
            self._depth -= 1
        elif char == "," and self._depth == 1:
            self._expect_key = True
        elif char == ":" and self._depth == 1:
            self._value_pending = True
        elif self._depth == 1 and not char.isspace():
            # A number, true, false or null value: not a string, so not ours.
            self._value_pending = False

    def _string_char(self, char: str, out: list[str]) -> None:
        if self._escape:
            self._escape += char
            if self._escape.startswith("\\u") and len(self._escape) < 6:
                return
            self._emit_escape(self._escape, out)
            self._escape = ""
            return
        if char == "\\":
            self._escape = "\\"
            return
        if char == '"':
            self._flush_surrogate(out)
            self._in_string = False
            if self._string_is_key:
                self._last_key = "".join(self._raw_key)
                self._expect_key = False
            elif self._string_is_target:
                self.done = True
            return
        self._flush_surrogate(out)
        self._keep(char, out)

    def _keep(self, text: str, out: list[str]) -> None:
        if self._string_is_target:
            out.append(text)
        elif self._string_is_key:
            self._raw_key.append(text)

    def _emit_escape(self, escape: str, out: list[str]) -> None:
        if not escape.startswith("\\u"):
            self._flush_surrogate(out)
            self._keep(_SIMPLE_ESCAPES.get(escape[1], escape[1]), out)
            return
        codepoint = int(escape[2:], 16)
        if 0xDC00 <= codepoint <= 0xDFFF and self._high_surrogate is not None:
            high = self._high_surrogate
            self._high_surrogate = None
            self._keep(chr(0x10000 + ((high - 0xD800) << 10) + (codepoint - 0xDC00)), out)
            return
        self._flush_surrogate(out)
        if 0xD800 <= codepoint <= 0xDBFF:
            self._high_surrogate = codepoint
            return
        self._keep(chr(codepoint), out)

    def _flush_surrogate(self, out: list[str]) -> None:
        """Pass a high surrogate that no low surrogate followed, as ``json`` does."""
        if self._high_surrogate is not None:
            self._keep(chr(self._high_surrogate), out)
            self._high_surrogate = None


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
