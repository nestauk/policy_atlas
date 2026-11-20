"""The one module that sends model requests to the provider, and the guards around them.

Every live backend sends its model requests through this module: a structured
answer (:func:`parse_structured`), a tool turn (:func:`send_turn`) and a streamed
answer (:func:`stream_turn`). The requests go to the OpenAI Responses endpoint
(``client.responses``) on the route's address (Amazon Bedrock's OpenAI-compatible
host on the Bedrock routes).

In plain terms, call sites still write their requests in the older "chat
completions" vocabulary (a list of ``messages``, ``tools`` in a nested
``function`` block, ``response_format``, ``max_completion_tokens``). This module
translates each request into the Responses vocabulary at the last moment, and
reads the Responses answer back into the small result types below, so no call
site needs to know which endpoint is used. Every request says ``store=False``:
the provider keeps no copy of the input or the answer.

It also holds client construction from an explicit or environment API key, the
request keyword arguments shared across call sites, and the stream decoders that
read one field of a streamed JSON answer.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import openai
from openai import OpenAI
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import BaseModel

from policy_atlas.core.model_routes import live_api_key, route
from policy_atlas.core.usage import (
    TokenUsage,
    UsageResult,
    log_usage,
    token_usage_from_provider,
    usage_details,
    usage_metadata,
)

#: How a call site uses the provider's prompt cache.
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


class AnswerCutOff(RuntimeError):
    """The answer stopped at the output-token limit before it was finished.

    Raised by :func:`parse_structured`, :func:`send_turn` and :class:`TextStream`.
    It is not tried again (the same request would stop at the same limit).

    Attributes:
        label: The call's human-readable label.
        usage: Token counts the provider sent for the cut-off answer (they are
            billed all the same), or ``None`` when it sent none.
    """

    def __init__(self, label: str, usage: TokenUsage | None = None) -> None:
        super().__init__(f"OpenAI {label} answer was cut off at the output-token limit.")
        self.label = label
        self.usage = usage


class ModelRefusal(RuntimeError):
    """The model declined to answer (a refusal), or the provider's content filter stopped it.

    Raised by :func:`parse_structured`, :func:`send_turn` and :class:`TextStream`.
    It is not tried again.

    Attributes:
        label: The call's human-readable label.
        usage: Token counts the provider sent, or ``None`` when it sent none.
    """

    def __init__(
        self, label: str, usage: TokenUsage | None = None, *, why: str = "refused"
    ) -> None:
        super().__init__(f"OpenAI {label} answer was {why}.")
        self.label = label
        self.usage = usage


def _check_finished(response: Any, *, label: str, usage: TokenUsage | None) -> None:
    """Raise the named error for a refused or unfinished answer; do nothing otherwise.

    A refusal content part, or an answer the provider stopped for any reason other
    than the output-token limit (``content_filter`` today), is a
    :class:`ModelRefusal`; an answer stopped at the output-token limit is an
    :class:`AnswerCutOff`.
    """
    if _has_refusal(response):
        raise ModelRefusal(label, usage)
    if getattr(response, "status", None) != "incomplete":
        return
    reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
    if reason == "max_output_tokens":
        raise AnswerCutOff(label, usage)
    raise ModelRefusal(label, usage, why=f"stopped by the provider ({reason or 'no reason given'})")


def _has_refusal(response: Any) -> bool:
    return any(
        getattr(part, "type", None) == "refusal"
        for item in getattr(response, "output", None) or ()
        if getattr(item, "type", None) == "message"
        for part in getattr(item, "content", None) or ()
    )


def _note_request_id(request_id: str | None) -> None:
    # Local import: tracing imports this module (through core.embeddings).
    from policy_atlas.core import tracing

    tracing.note_request_id(request_id)


def _header_request_id(http_response: Any) -> str | None:
    """The provider's request id from raw response headers (``None`` when absent).

    Bedrock sends the same value as ``x-request-id`` and ``x-amzn-requestid``; it is
    the ``requestID`` of AWS's audit log (CloudTrail).
    """
    headers = getattr(http_response, "headers", None)
    if headers is None:
        return None
    found = headers.get("x-request-id") or headers.get("x-amzn-requestid")
    return found if isinstance(found, str) else None


def _create(client: Any, **kwargs: Any) -> Any:
    """Send one request to ``client.responses.create``, noting the provider's request id.

    The id goes into the current :func:`policy_atlas.core.tracing.request_id_scope`
    (if one is open): from the answer (the SDK's ``_request_id``), from a stream's
    response headers, or from an HTTP error status.
    """
    try:
        response = client.responses.create(**kwargs)
    except openai.APIStatusError as exc:
        _note_request_id(exc.request_id or _header_request_id(exc.response))
        raise
    _note_request_id(
        getattr(response, "_request_id", None)
        or _header_request_id(getattr(response, "response", None))
    )
    return response


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
    timeout of its own. Each request sends its step's timeout
    (``openai_kwargs(..., timeout_s=route().timeout_for(step))``), and the retries
    a model call gets (up to ``MODEL_CALL_ATTEMPTS`` attempts, three today) are
    made by :func:`policy_atlas.core.tracing.traced_attempts`, so every attempt
    is its own Langfuse generation; the SDK's own retries would be silent and
    untraced.

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
    """Request keyword arguments shared by every model call site.

    Every call site states its reasoning effort and its timeout:
    both come from the route file (``route().effort_for(step)``
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
        Chat-style keyword arguments for :func:`send_turn` / :func:`stream_turn`
        (this module translates them for the Responses endpoint).
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
    """Ask for one answer that fits a Pydantic class, and parse it.

    Shared by every live backend that asks for a structured answer: the
    request, usage logging and the no-answer / not-parsed raises are identical
    across call sites; only the model, extra request keyword arguments, answer
    schema and error label vary. The answer schema sent is the strict JSON schema
    the OpenAI SDK derives from ``response_format`` (same name, same body, strict).

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
        **parse_kwargs: Additional chat-style request keyword arguments
            (``max_completion_tokens``, ...).

    Returns:
        The parsed structured output plus provider-neutral token usage.

    Raises:
        AnswerCutOff: If the answer stopped at the output-token limit (usage is
            still logged).
        ModelRefusal: If the model refused, or the provider stopped the answer
            for another reason.
        RuntimeError: If the response holds no output at all, or no answer
            text to parse.
        pydantic.ValidationError: If the answer text does not fit the class.
    """
    response = _create(
        client,
        **_responses_request(
            messages=with_system_breakpoint(messages) if prompt_cache == "breakpoint" else messages,
            response_format=type_to_response_format_param(response_format),
            **openai_kwargs(
                model,
                reasoning_effort=reasoning_effort,
                prompt_cache=prompt_cache,
                timeout_s=timeout_s,
            ),
            **parse_kwargs,
        )
    )
    usage = token_usage_from_provider(getattr(response, "usage", None))
    log_usage(usage_event, usage)
    _check_finished(response, label=label, usage=usage)
    if not getattr(response, "output", None):
        raise RuntimeError(f"OpenAI {label} response had no choices.")
    text = _output_text(response)
    if not text:
        raise RuntimeError(f"OpenAI {label} response was not parsed.")
    return response_format.model_validate_json(text), usage


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
    ``MODEL_CALL_ATTEMPTS`` attempts (three today),
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


#: The request keys a call site may pass to :func:`send_turn` and :func:`stream_turn`:
#: exactly the chat-style keyword arguments the sites build.
_REQUEST_KEYS = frozenset(
    {
        "model",
        "messages",
        "reasoning_effort",
        "timeout",
        "extra_body",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "response_format",
        "max_completion_tokens",
        "stream_options",
    }
)


def _check_request(request: Mapping[str, Any]) -> None:
    unknown = sorted(set(request) - _REQUEST_KEYS)
    if unknown:
        raise TypeError(f"Unknown model request key(s): {', '.join(unknown)}")


def _responses_request(**request: Any) -> dict[str, Any]:
    """Translate one chat-style request into ``client.responses.create`` arguments.

    In plain terms: the call sites speak the chat-completions vocabulary; the
    provider is asked through the Responses endpoint. Each key maps one to one
    (``messages`` to ``input``, ``reasoning_effort`` to ``reasoning.effort``,
    ``max_completion_tokens`` to ``max_output_tokens``, ``response_format`` to
    ``text.format``; tools and tool choices are flattened). ``extra_body`` (the
    prompt-cache options) and ``timeout`` pass through unchanged and
    ``stream_options`` is dropped (Responses always sends usage on its last
    event). ``store=False`` is always added, so the provider keeps no copy.

    A :class:`CarriedTurn` in ``messages`` (from :meth:`CarriedTurn.with_results`)
    becomes its items in place: an earlier turn's own output items followed by
    one ``function_call_output`` per tool call. A request with tools and an
    effort above ``"none"`` also asks for the model's reasoning back
    (``include=["reasoning.encrypted_content"]``), so a later turn can carry it.

    Raises:
        TypeError: If the request holds an unknown key, or a message, content
            part, tool or tool choice of a kind this translation does not know.
        ValueError: If a carried turn in ``messages`` has a tool call with no
            result (it did not go through :meth:`CarriedTurn.with_results`).
    """
    _check_request(request)
    out: dict[str, Any] = {"store": False}
    for key, value in request.items():
        if key == "messages":
            out["input"] = [
                item
                for message in value
                for item in (
                    _answered_items(message)
                    if isinstance(message, CarriedTurn)
                    else _input_items(message)
                )
            ]
        elif key == "reasoning_effort":
            out["reasoning"] = {"effort": value}
        elif key == "max_completion_tokens":
            out["max_output_tokens"] = value
        elif key == "tools":
            out["tools"] = [_flat_tool(tool) for tool in value]
        elif key == "tool_choice":
            out["tool_choice"] = _flat_tool_choice(value)
        elif key == "response_format":
            out["text"] = {"format": _text_format(value)}
        elif key != "stream_options":
            out[key] = value
    if request.get("tools") and request.get("reasoning_effort") not in (None, "none"):
        # The provider hands back the model's reasoning (encrypted) only when
        # asked, and with ``store=False`` it is the only way to carry it on.
        out["include"] = ["reasoning.encrypted_content"]
    return out


def _answered_items(turn: CarriedTurn) -> tuple[dict[str, Any], ...]:
    """A carried turn's items, once every tool call in it has its result."""
    answered = {
        item["call_id"] for item in turn.items if item.get("type") == "function_call_output"
    }
    unanswered = [call_id for call_id in turn.call_ids if call_id not in answered]
    if unanswered:
        raise ValueError(f"carried turn sent with unanswered tool calls: {unanswered}")
    return turn.items


def _input_items(message: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One chat message as Responses input items (a message, tool calls, a tool result)."""
    role = message.get("role")
    if role == "tool":
        return [
            {
                "type": "function_call_output",
                "call_id": message["tool_call_id"],
                "output": _require_str(message.get("content"), "a tool message's content"),
            }
        ]
    if role not in ("system", "user", "assistant"):
        raise TypeError(f"Unknown message role for the Responses endpoint: {role!r}")
    items: list[dict[str, Any]] = []
    content = message.get("content")
    if content is not None:
        if not isinstance(content, str):
            content = [_content_part(part, role=role) for part in content]
        items.append({"role": role, "content": content})
    for call in message.get("tool_calls") or ():
        function = call["function"]
        items.append(
            {
                "type": "function_call",
                "call_id": call["id"],
                "name": function["name"],
                "arguments": function["arguments"],
            }
        )
    return items


def _content_part(part: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    kind = part.get("type")
    if kind == "text":
        # Every other key (the prompt-cache breakpoint) stays on the same part.
        return {**part, "type": "output_text" if role == "assistant" else "input_text"}
    if kind == "image_url":
        image = part["image_url"]
        # "auto" is the chat-completions default detail when a part names none.
        detail = image.get("detail", "auto")
        return {"type": "input_image", "image_url": image["url"], "detail": detail}
    raise TypeError(f"Unknown message content part for the Responses endpoint: {kind!r}")


def _flat_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    if tool.get("type") != "function":
        raise TypeError(f"Unknown tool type for the Responses endpoint: {tool.get('type')!r}")
    function = tool["function"]
    flat: dict[str, Any] = {"type": "function", "name": function["name"]}
    if "description" in function:
        flat["description"] = function["description"]
    flat["parameters"] = function.get("parameters")
    # Stated every time: the endpoint reads a missing ``strict`` as true.
    flat["strict"] = bool(function.get("strict", False))
    return flat


def _flat_tool_choice(choice: Any) -> Any:
    if isinstance(choice, str):
        return choice
    kind = choice.get("type")
    if kind == "function":
        return {"type": "function", "name": choice["function"]["name"]}
    if kind == "allowed_tools":
        allowed = choice["allowed_tools"]
        return {
            "type": "allowed_tools",
            "mode": allowed["mode"],
            "tools": [
                {"type": "function", "name": tool["function"]["name"]} for tool in allowed["tools"]
            ],
        }
    raise TypeError(f"Unknown tool choice for the Responses endpoint: {kind!r}")


def _text_format(response_format: Any) -> dict[str, Any]:
    if response_format.get("type") != "json_schema":
        raise TypeError(
            f"Unknown response format for the Responses endpoint: {response_format.get('type')!r}"
        )
    return {"type": "json_schema", **response_format["json_schema"]}


def _require_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{what} must be text, not {type(value).__name__}")
    return value


def _output_text(response: Any) -> str:
    """The answer's text: every ``output_text`` part of the output messages, joined."""
    return "".join(
        part.text
        for item in getattr(response, "output", None) or ()
        if getattr(item, "type", None) == "message"
        for part in getattr(item, "content", None) or ()
        if getattr(part, "type", None) == "output_text"
    )


@dataclass(frozen=True)
class ToolCall:
    """One tool (function) the model asked to run.

    Attributes:
        name: The tool's name.
        arguments: The tool's arguments as the model wrote them: JSON text, not
            yet checked.
        call_id: The id that pairs this call with its result in a later turn.
    """

    name: str
    arguments: str
    call_id: str


@dataclass(frozen=True, repr=False)
class CarriedTurn:
    """What one answer hands on to the next request of the same tool loop.

    In plain terms: when the model reasons before calling a tool, the provider
    returns that reasoning as an encrypted block the app cannot read. Sending the
    turn's own output items back on the next request (instead of a rebuilt copy
    of its tool calls) lets the model keep its reasoning. The items are kept as
    the provider sent them, with the ``status`` field removed from every item
    that is not a message (the form the provider accepts back). A call site
    never reads inside them, and they are never stored, logged or traced: the
    repr shows only the item count.

    Attributes:
        items: The provider's output items for the turn.
    """

    items: tuple[dict[str, Any], ...]

    def __repr__(self) -> str:
        return f"CarriedTurn({len(self.items)} items)"

    @property
    def call_ids(self) -> tuple[str, ...]:
        """The ids of the turn's tool calls, in order."""
        return tuple(
            item["call_id"] for item in self.items if item.get("type") == "function_call"
        )

    def with_results(self, results: Mapping[str, str]) -> CarriedTurn:
        """Pair the turn with one result text for each of its tool calls.

        Args:
            results: The result text for each call, by call id.

        Returns:
            The turn's items followed by one ``function_call_output`` per call,
            to put in a later request's ``messages`` list where the rebuilt
            messages of this turn would have gone. A turn whose calls have no
            results cannot be sent.

        Raises:
            ValueError: If a call has no result, or a result names a call the
                turn did not make.
        """
        call_ids = self.call_ids
        missing = [call_id for call_id in call_ids if call_id not in results]
        unknown = sorted(set(results) - set(call_ids))
        if missing or unknown:
            raise ValueError(
                f"carried turn results do not match its calls: missing {missing}, "
                f"unknown {unknown}"
            )
        outputs = tuple(
            {"type": "function_call_output", "call_id": call_id, "output": results[call_id]}
            for call_id in call_ids
        )
        return CarriedTurn(items=self.items + outputs)


def _carried(response: Any) -> CarriedTurn | None:
    """The response's output items as a :class:`CarriedTurn` (``None`` when there are none)."""
    items: list[dict[str, Any]] = []
    for item in getattr(response, "output", None) or ():
        plain = item.model_dump(exclude_none=True)
        if plain.get("type") != "message":
            plain.pop("status", None)
        items.append(plain)
    return CarriedTurn(items=tuple(items)) if items else None


@dataclass(frozen=True)
class ModelTurn:
    """The answer to one non-streamed model request.

    Attributes:
        text: The answer's text (``""`` when the model only called tools).
        tool_calls: The tool calls the model made, in order (empty when none).
        usage: Token counts for the request (``None`` when the provider sent
            none).
        carried: The answer's output items, for a later request of the same
            tool loop to send back (see :class:`CarriedTurn`).
    """

    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: TokenUsage | None
    carried: CarriedTurn | None = None


class TextStream:
    """A streamed model answer, read piece by piece.

    In plain terms: loop over it to get the answer's text in the order it
    arrives (only text pieces are handed out, never the provider's progress
    events, so the first piece is the first content). Once the loop ends (or
    stops early with an error), :attr:`usage` holds the token counts the
    provider sent, or ``None`` when it sent none. :meth:`close` cuts the stream
    off and may be called from another thread, for example a watchdog that gives
    up waiting; the loop then ends quietly.

    How a stream ends:

    - ``response.completed``: the loop ends normally, with usage.
    - ``response.incomplete`` at the output-token limit: usage is recorded and,
      once the loop ends, :class:`AnswerCutOff` is raised (the text pieces already
      handed out stay handed out). Stopped for another reason (the content filter):
      :class:`ModelRefusal` instead.
    - a refusal (refusal events, or a refusal part in the final answer): usage is
      recorded and :class:`ModelRefusal` is raised once the loop ends.
    - ``response.failed`` or an ``error`` event: raises :class:`openai.APIError`
      (a provider error that is not tried again, as a mid-stream error is not).
    - no final event before the stream stops: raises
      :class:`openai.APIConnectionError` (a dropped connection, which may be
      tried again).

    Attributes:
        label: Human-readable call label.
        usage: Token counts read so far.
        carried: The answer's output items (see :class:`CarriedTurn`), read
            from the final ``response.completed`` event; ``None`` until then.
    """

    def __init__(self, stream: Any, *, label: str) -> None:
        self._stream = stream
        self._closed = False
        self.label = label
        self.usage: TokenUsage | None = None
        self.carried: CarriedTurn | None = None

    def __iter__(self) -> Iterator[str]:
        ended = False
        refused = False
        final: Any = None
        for event in self._stream:
            kind = getattr(event, "type", None)
            if kind == "response.output_text.delta":
                if event.delta:
                    yield event.delta
            elif kind in ("response.refusal.delta", "response.refusal.done"):
                refused = True
            elif kind in ("response.completed", "response.incomplete"):
                final = event.response
                self.usage = token_usage_from_provider(getattr(final, "usage", None))
                ended = True
            elif kind == "response.failed":
                error = getattr(event.response, "error", None)
                self.usage = token_usage_from_provider(getattr(event.response, "usage", None))
                raise self._provider_error(getattr(error, "message", None), error)
            elif kind == "error":
                raise self._provider_error(getattr(event, "message", None), event)
        if not ended:
            if self._closed:
                return
            raise openai.APIConnectionError(
                message=f"OpenAI {self.label} stream stopped before its final event.",
                request=self._request(),
            )
        if refused:
            raise ModelRefusal(self.label, self.usage)
        if final is not None:
            _check_finished(final, label=self.label, usage=self.usage)
            self.carried = _carried(final)

    def _provider_error(self, message: Any, body: Any) -> openai.APIError:
        text = message if isinstance(message, str) and message else "the provider failed the answer"
        details = body.to_dict() if hasattr(body, "to_dict") else None
        return openai.APIError(
            f"OpenAI {self.label} stream failed: {text}", self._request(), body=details
        )

    def _request(self) -> Any:
        # The SDK stream's HTTP request; ``None`` for a test double with no response.
        return getattr(getattr(self._stream, "response", None), "request", None)

    def close(self) -> None:
        """Cancel the underlying stream (safe from another thread)."""
        self._closed = True
        self._stream.close()


def send_turn(client: Any, *, label: str, **request: Any) -> ModelTurn:
    """Send one model request and read its text, tool calls and token usage.

    The request is translated for the Responses endpoint (see the module
    docstring) and otherwise goes out as the call site built it; the site
    applies any prompt-cache breakpoint itself.

    Args:
        client: The OpenAI client.
        label: Human-readable call label.
        **request: The chat-style keyword arguments the site builds
            (``model``, ``messages``, ``reasoning_effort``, ``timeout``,
            ``extra_body``, and where used ``tools``, ``tool_choice``,
            ``parallel_tool_calls``, ``response_format``,
            ``max_completion_tokens``, ``stream_options``).

    Returns:
        The answer's text, tool calls and token usage.

    Raises:
        TypeError: If the request holds a key outside the list above.
        AnswerCutOff: If the answer stopped at the output-token limit.
        ModelRefusal: If the model refused, or the provider stopped the answer
            for another reason.
        RuntimeError: If the response holds no output at all.
    """
    response = _create(client, **_responses_request(**request))
    usage = token_usage_from_provider(getattr(response, "usage", None))
    _check_finished(response, label=label, usage=usage)
    output = getattr(response, "output", None)
    if not output:
        raise RuntimeError(f"OpenAI {label} response had no choices.")
    calls = tuple(
        ToolCall(name=item.name, arguments=item.arguments, call_id=item.call_id)
        for item in output
        if getattr(item, "type", None) == "function_call"
    )
    return ModelTurn(
        text=_output_text(response), tool_calls=calls, usage=usage, carried=_carried(response)
    )


def stream_turn(client: Any, *, label: str, **request: Any) -> TextStream:
    """Send one model request as a stream.

    The request is translated as in :func:`send_turn`, plus ``stream=True``.

    Args:
        client: The OpenAI client.
        label: Human-readable call label.
        **request: The same keyword arguments :func:`send_turn` takes.

    Returns:
        The stream: loop over it for the text pieces.

    Raises:
        TypeError: If the request holds an unknown key (``stream`` included).
    """
    return TextStream(_create(client, stream=True, **_responses_request(**request)), label=label)


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
    piece returns ``""``.

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


class JsonArrayObjectDecoder:
    """Hand back each object of one top-level array field as soon as it closes.

    In plain terms: the section writer's streamed answer is one JSON object,
    ``{"prose": "...", "claims": [{...}, {...}]}``, arriving in small pieces.
    Feed each piece to :meth:`feed`; whenever one object inside the named
    array (``claims``) is complete, its JSON text is returned, so it can be
    read on its own while the rest is still arriving. The scanning follows
    :class:`JsonStringFieldDecoder`: only a key of the outermost object
    counts, and braces, brackets and quotes inside strings (escaped quotes
    included) are text, not structure. The returned text is not checked; the
    caller parses it and skips what does not parse.

    Args:
        field_name: The top-level key whose array of objects to follow.
    """

    def __init__(self, field_name: str) -> None:
        self._field_name = field_name
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._string_is_key = False
        self._raw_key: list[str] = []
        self._expect_key = False
        self._last_key: str | None = None
        self._value_pending = False
        self._in_array = False
        self._object: list[str] | None = None
        self.done = False

    def feed(self, fragment: str) -> list[str]:
        """Consume one piece of the JSON text.

        Args:
            fragment: The next piece of the streamed JSON text.

        Returns:
            The JSON text of each array object that closed in this piece, in
            order (often none).
        """
        closed: list[str] = []
        for char in fragment:
            if self.done:
                break
            if self._object is not None:
                self._object.append(char)
            if self._in_string:
                self._string_char(char)
            else:
                self._structural_char(char, closed)
        return closed

    def _string_char(self, char: str) -> None:
        if self._escape:
            self._escape = False
            if self._string_is_key:
                self._raw_key.append(char)
            return
        if char == "\\":
            self._escape = True
            return
        if char == '"':
            self._in_string = False
            if self._string_is_key:
                self._last_key = "".join(self._raw_key)
                self._expect_key = False
            return
        if self._string_is_key:
            self._raw_key.append(char)

    def _structural_char(self, char: str, closed: list[str]) -> None:
        if char == '"':
            self._in_string = True
            self._string_is_key = self._depth == 1 and self._expect_key
            self._raw_key = []
            if self._depth == 1:
                self._value_pending = False
            return
        if char in "{[":
            opens_array = (
                char == "["
                and self._depth == 1
                and self._value_pending
                and self._last_key == self._field_name
            )
            self._depth += 1
            if self._depth == 1:
                self._expect_key = char == "{"
            if self._depth == 2:
                self._value_pending = False
                self._in_array = opens_array
            elif self._depth == 3 and self._in_array and char == "{":
                self._object = ["{"]
            return
        if char in "}]":
            if self._depth == 3 and self._object is not None and char == "}":
                closed.append("".join(self._object))
                self._object = None
            elif self._depth == 2 and self._in_array:
                self._in_array = False
                self.done = True
            self._depth -= 1
            return
        if char == "," and self._depth == 1:
            self._expect_key = True
        elif char == ":" and self._depth == 1:
            self._value_pending = True
        elif self._depth == 1 and not char.isspace():
            self._value_pending = False


class JsonArrayStringDecoder:
    """Hand back each string of one top-level array field as soon as it closes.

    In plain terms: the same idea as :class:`JsonArrayObjectDecoder`, for an
    array of plain strings (the theory-of-change report's
    ``supporting_activities``). Feed each piece of the streamed JSON
    text to :meth:`feed`; whenever one string inside the named array is
    complete, it is returned already decoded (``\\n`` becomes a line break,
    ``\\u00e9`` becomes ``é``). Only a key of the outermost object counts, and
    quotes or brackets inside strings are text, not structure. Once the
    array closes, :attr:`done` is true and every later piece returns nothing.

    Args:
        field_name: The top-level key whose array of strings to follow.
    """

    def __init__(self, field_name: str) -> None:
        self._field_name = field_name
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._string_is_key = False
        self._raw_key: list[str] = []
        self._expect_key = False
        self._last_key: str | None = None
        self._value_pending = False
        self._in_array = False
        self._item: list[str] | None = None
        self.done = False

    def feed(self, fragment: str) -> list[str]:
        """Consume one piece of the JSON text.

        Args:
            fragment: The next piece of the streamed JSON text.

        Returns:
            Each string of the array that closed in this piece, decoded, in
            order (often none).
        """
        closed: list[str] = []
        for char in fragment:
            if self.done:
                break
            if self._in_string:
                if self._item is not None:
                    self._item.append(char)
                self._string_char(char, closed)
            else:
                self._structural_char(char)
        return closed

    def _string_char(self, char: str, closed: list[str]) -> None:
        if self._escape:
            self._escape = False
            if self._string_is_key:
                self._raw_key.append(char)
            return
        if char == "\\":
            self._escape = True
            return
        if char == '"':
            self._in_string = False
            if self._string_is_key:
                self._last_key = "".join(self._raw_key)
                self._expect_key = False
            elif self._item is not None:
                closed.append(json.loads("".join(self._item)))
                self._item = None
            return
        if self._string_is_key:
            self._raw_key.append(char)

    def _structural_char(self, char: str) -> None:
        if char == '"':
            self._in_string = True
            self._string_is_key = self._depth == 1 and self._expect_key
            self._raw_key = []
            if self._depth == 1:
                self._value_pending = False
            elif self._depth == 2 and self._in_array:
                self._item = ['"']
            return
        if char in "{[":
            opens_array = (
                char == "["
                and self._depth == 1
                and self._value_pending
                and self._last_key == self._field_name
            )
            self._depth += 1
            if self._depth == 1:
                self._expect_key = char == "{"
            if self._depth == 2:
                self._value_pending = False
                self._in_array = opens_array
            return
        if char in "}]":
            if self._depth == 2 and self._in_array:
                self._in_array = False
                self.done = True
            self._depth -= 1
            return
        if char == "," and self._depth == 1:
            self._expect_key = True
        elif char == ":" and self._depth == 1:
            self._value_pending = True
        elif self._depth == 1 and not char.isspace():
            self._value_pending = False


def require_single_tool_call(turn: ModelTurn, *, label: str) -> ToolCall:
    """Return the answer's single tool call or fail loud.

    Args:
        turn: The answer from :func:`send_turn`.
        label: Human-readable call label for the error message.

    Raises:
        RuntimeError: If the answer has no tool call, or more than one.
    """
    tool_calls = turn.tool_calls
    if not tool_calls:
        raise RuntimeError(f"OpenAI {label} response had no tool call.")
    if len(tool_calls) != 1:
        raise RuntimeError(f"OpenAI {label} response had multiple tool calls.")
    return tool_calls[0]
