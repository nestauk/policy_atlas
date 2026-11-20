"""Every model call site sends the request recorded in the committed capture.

``capture_requests.py`` drives each call site with fixed inputs and records the
HTTP request it sends (address path, JSON body, timeout) on the ``bedrock`` route.
Two captures are committed:

- ``request_capture_baseline.json``: the requests as they were sent to the older
  chat-completions endpoint. It is a frozen record and never refreshed.
- ``request_capture_responses.json``: the requests as they are sent now, to the
  Responses endpoint. The script's output must equal it.

A comparison test checks, for every step and variant, that the Responses request
carries the same content as the baseline one: the model sees the same messages,
tools, schema and settings, and nothing was added.
It runs in a child process: this suite's ``conftest.py`` removes the route
variable, and many model ids and efforts are read from the route when their
modules are first imported, so the route must be set before any import.

Refresh the Responses capture deliberately with ``REQUEST_CAPTURE_UPDATE=1``; the
diff is then the review artefact.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from policy_atlas.core import model_routes
from policy_atlas.evidence_search.synthesis.cache_modes import CACHE_MODES

SCRIPT = Path(__file__).parent / "capture_requests.py"
BASELINE = Path(__file__).parent / "data" / "request_capture_baseline.json"
RESPONSES = Path(__file__).parent / "data" / "request_capture_responses.json"
UPDATE_ENV = "REQUEST_CAPTURE_UPDATE"
#: The body the provider reads as "store nothing on your own" (cache modes off and breakpoint).
EXPLICIT_CACHE = {"mode": "explicit"}


@pytest.fixture(scope="module")
def captured(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, Any]]:
    """Run the capture script once in a clean child process and read what it wrote."""
    out = tmp_path_factory.mktemp("capture") / "capture.json"
    env = {
        model_routes.ROUTE_ENV: "bedrock",
        "AWS_BEARER_TOKEN_BEDROCK": "throwaway-request-capture-key",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(out)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    if os.environ.get(UPDATE_ENV):
        RESPONSES.write_bytes(out.read_bytes())
    entries: list[dict[str, Any]] = json.loads(out.read_text(encoding="utf-8"))
    return entries


def _key(entry: dict[str, Any]) -> str:
    return f"{entry['step']}/{entry['variant']}"


def _load(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return entries


def test_every_request_matches_the_committed_capture(captured: list[dict[str, Any]]) -> None:
    committed = _load(RESPONSES)
    assert [_key(entry) for entry in captured] == [_key(entry) for entry in committed]
    for now, then in zip(captured, committed, strict=True):
        assert now == then, _key(now)


#: The only top-level keys a Responses request may carry.
_ALLOWED_KEYS = {
    "model",
    "input",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "text",
    "reasoning",
    "max_output_tokens",
    "store",
    "stream",
    "prompt_cache_options",
}
#: Every top-level key a baseline request carries; each has its counterpart checked below.
_BASELINE_KEYS = {
    "model",
    "messages",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "response_format",
    "reasoning_effort",
    "max_completion_tokens",
    "stream",
    "stream_options",
    "prompt_cache_options",
}


def _old_parts(content: Any) -> Any:
    if isinstance(content, str):
        return content
    parts: list[tuple[Any, ...]] = []
    for part in content:
        if part["type"] == "text":
            parts.append(("text", part["text"], part.get("prompt_cache_breakpoint")))
        elif part["type"] == "image_url":
            image = part["image_url"]
            parts.append(("image", image["url"], image.get("detail", "auto")))
        else:
            parts.append(("unknown", part))
    return parts


def _new_parts(content: Any, role: str, problems: list[str]) -> Any:
    if isinstance(content, str):
        return content
    text_type = "output_text" if role == "assistant" else "input_text"
    parts: list[tuple[Any, ...]] = []
    for part in content:
        if part["type"] == text_type and set(part) <= {"type", "text", "prompt_cache_breakpoint"}:
            parts.append(("text", part["text"], part.get("prompt_cache_breakpoint")))
        elif part["type"] == "input_image" and set(part) == {"type", "image_url", "detail"}:
            parts.append(("image", part["image_url"], part["detail"]))
        else:
            problems.append(f"unexpected content part on a {role} message: {sorted(part)}")
    return parts


def _old_items(messages: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """The baseline messages as (kind, ...) tuples in the order the model reads them."""
    items: list[tuple[Any, ...]] = []
    for message in messages:
        if message["role"] == "tool":
            items.append(("tool result", message["tool_call_id"], message["content"]))
            continue
        if message.get("content") is not None:
            items.append(("message", message["role"], _old_parts(message["content"])))
        for call in message.get("tool_calls") or ():
            function = call["function"]
            items.append(("tool call", call["id"], function["name"], function["arguments"]))
    return items


def _new_items(items: list[dict[str, Any]], problems: list[str]) -> list[tuple[Any, ...]]:
    """The Responses input items as the same (kind, ...) tuples."""
    out: list[tuple[Any, ...]] = []
    for item in items:
        kind = item.get("type")
        if kind == "function_call_output" and set(item) == {"type", "call_id", "output"}:
            out.append(("tool result", item["call_id"], item["output"]))
        elif kind == "function_call" and set(item) == {"type", "call_id", "name", "arguments"}:
            out.append(("tool call", item["call_id"], item["name"], item["arguments"]))
        elif kind is None and set(item) == {"role", "content"}:
            role = item["role"]
            out.append(("message", role, _new_parts(item["content"], role, problems)))
        else:
            problems.append(f"unexpected input item: {sorted(item)}")
    return out


def _expected_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool["function"]
    expected = {
        "type": "function",
        "name": function["name"],
        "parameters": function["parameters"],
        "strict": function.get("strict", False),
    }
    if "description" in function:
        expected["description"] = function["description"]
    return expected


def _expected_tool_choice(choice: Any) -> Any:
    if isinstance(choice, str):
        return choice
    if choice["type"] == "function":
        return {"type": "function", "name": choice["function"]["name"]}
    allowed = choice["allowed_tools"]
    return {
        "type": "allowed_tools",
        "mode": allowed["mode"],
        "tools": [{"type": "function", "name": t["function"]["name"]} for t in allowed["tools"]],
    }


def content_differences(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Every way a Responses request differs in content from its baseline request.

    In plain terms: the model must see the same thing through both endpoints. The
    messages (roles, text, images, the cache marker's place), the tool history, the
    tools (with ``strict`` stated, ``False`` where the baseline tool had none), the
    tool choice, the answer schema, the model, effort, output limit, timeout and
    cache options must all carry over; ``store`` must be ``False``; and no key
    outside the allowed list may appear.

    Args:
        old: The baseline (chat-completions) capture entry.
        new: The Responses capture entry for the same step and variant.

    Returns:
        One line per difference, each naming the step and variant; empty when
        the two requests match.
    """
    where = f"{old['step']}/{old['variant'] or '(default)'}"
    then, now = old["body"], new["body"]
    problems: list[str] = []

    def check(ok: bool, what: str) -> None:
        if not ok:
            problems.append(what)

    check(new["path"].endswith("/responses"), f"path is {new['path']}")
    check(set(then) <= _BASELINE_KEYS, f"baseline key not compared: {set(then) - _BASELINE_KEYS}")
    check(set(now) <= _ALLOWED_KEYS, f"key outside the allowed list: {set(now) - _ALLOWED_KEYS}")
    check(now.get("store") is False, f"store is {now.get('store')!r}, not false")
    # Messages and tool history, in order.
    old_items = _old_items(then["messages"])
    new_items = _new_items(now.get("input", []), problems)
    check(len(old_items) == len(new_items), f"{len(old_items)} input items became {len(new_items)}")
    for index, (a, b) in enumerate(zip(old_items, new_items, strict=False)):
        check(a == b, f"input item {index}: {a!r} became {b!r}")
    # Tools and tool choice.
    old_tools = [_expected_tool(tool) for tool in then.get("tools", [])]
    check(old_tools == now.get("tools", []), "tools differ (name, description, parameters, strict)")
    check(
        ("tool_choice" in then) == ("tool_choice" in now)
        and _expected_tool_choice(then.get("tool_choice", "")) == now.get("tool_choice", ""),
        f"tool choice {then.get('tool_choice')!r} became {now.get('tool_choice')!r}",
    )
    check(
        then.get("parallel_tool_calls") == now.get("parallel_tool_calls"),
        "parallel_tool_calls differs",
    )
    # Answer schema.
    if "response_format" in then:
        schema = then["response_format"]
        expected_text = {"format": {"type": "json_schema", **schema["json_schema"]}}
        check(schema["type"] == "json_schema", f"baseline response format {schema['type']!r}")
        check(now.get("text") == expected_text, "text.format differs (name, schema, strict)")
    else:
        check("text" not in now, "text sent where the baseline had no response format")
    # Scalars.
    check(now.get("model") == then["model"], "model differs")
    check(now.get("reasoning") == {"effort": then["reasoning_effort"]}, "reasoning effort differs")
    check(
        now.get("max_output_tokens") == then.get("max_completion_tokens"),
        f"output limit {then.get('max_completion_tokens')} became {now.get('max_output_tokens')}",
    )
    check(bool(now.get("stream")) == bool(then.get("stream")), "streaming differs")
    check(new["timeout"] == old["timeout"], f"timeout {old['timeout']} became {new['timeout']}")
    check(
        now.get("prompt_cache_options") == then.get("prompt_cache_options"),
        "prompt cache options differ",
    )
    return [f"{where}: {problem}" for problem in problems]


def test_every_responses_request_carries_the_baseline_content() -> None:
    baseline = _load(BASELINE)
    responses = _load(RESPONSES)
    assert [_key(entry) for entry in responses] == [_key(entry) for entry in baseline]
    problems = [
        problem
        for old, new in zip(baseline, responses, strict=True)
        for problem in content_differences(old, new)
    ]
    assert not problems, "\n".join(problems)


def test_every_route_step_has_a_cache_mode() -> None:
    assert sorted(CACHE_MODES) == sorted(model_routes.route().steps)


def _system_shape(body: dict[str, Any]) -> str | None:
    """How the first system message is sent: plain text, or parts carrying a breakpoint."""
    for message in body.get("messages", body.get("input", [])):
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return "text"
        if any(isinstance(part, dict) and "prompt_cache_breakpoint" in part for part in content):
            return "parts+breakpoint"
        return "parts"
    return None


def test_every_request_sends_its_steps_cache_mode(captured: list[dict[str, Any]]) -> None:
    """``auto`` sends no cache options and a plain system message (or none); ``off`` sends
    the explicit cache options; ``breakpoint`` sends them too, with the first system
    message as parts carrying the breakpoint."""
    expected_by_mode: dict[str, tuple[Any, set[str | None]]] = {
        "auto": (None, {"text", None}),
        "off": (EXPLICIT_CACHE, {"text", None}),
        "breakpoint": (EXPLICIT_CACHE, {"parts+breakpoint"}),
    }
    for entry in captured:
        mode = CACHE_MODES[entry["step"]]
        options, shapes = expected_by_mode[mode]
        assert entry["body"].get("prompt_cache_options") == options, (_key(entry), mode)
        assert _system_shape(entry["body"]) in shapes, (_key(entry), mode)
