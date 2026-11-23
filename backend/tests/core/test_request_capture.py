"""Every model call site sends the request recorded in the committed capture.

``capture_requests.py`` drives each call site with fixed inputs and records the
HTTP request it sends (address path, JSON body, timeout) on the ``bedrock`` route.
The capture is committed as ``request_capture_responses.json`` in a short form:
the settings of each request (model, effort, limits, timeout, tool choice, cache
options) are kept as sent, and its long parts (each input item, each tool, the
answer schema) are kept as fingerprints. The script's output, put in the same
form, must equal it, so a failing test names the step and the part that changed;
the changed words are in the diff of the prompt, tool or schema code.
It runs in a child process: this suite's ``conftest.py`` removes the route
variable, and many model ids and efforts are read from the route when their
modules are first imported, so the route must be set before any import.

Refresh the capture deliberately with ``REQUEST_CAPTURE_UPDATE=1``; the
diff is then the review artefact.
"""

from __future__ import annotations

import hashlib
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
    entries: list[dict[str, Any]] = json.loads(out.read_text(encoding="utf-8"))
    if os.environ.get(UPDATE_ENV):
        short = [_short(entry) for entry in entries]
        RESPONSES.write_text(json.dumps(short, indent=1) + "\n", encoding="utf-8")
    return entries


def _key(entry: dict[str, Any]) -> str:
    return f"{entry['step']}/{entry['variant']}"


def _load(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return entries


def _fingerprint(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _short(entry: dict[str, Any]) -> dict[str, Any]:
    """The committed form of a captured request: settings as sent, long parts fingerprinted.

    Args:
        entry: One captured request (step, variant, path, timeout, body).

    Returns:
        The entry with each input item as ``"<role or type>:<fingerprint>"``, each
        tool as ``name -> fingerprint`` and the answer schema as one fingerprint.
    """
    body = dict(entry["body"])
    if "input" in body:
        body["input"] = [
            f"{item.get('role') or item.get('type')}:{_fingerprint(item)}" for item in body["input"]
        ]
    if "tools" in body:
        body["tools"] = {tool["name"]: _fingerprint(tool) for tool in body["tools"]}
    if "text" in body:
        body["text"] = _fingerprint(body["text"])
    return {**entry, "body": body}


def test_every_request_matches_the_committed_capture(captured: list[dict[str, Any]]) -> None:
    committed = _load(RESPONSES)
    assert [_key(entry) for entry in captured] == [_key(entry) for entry in committed]
    for now, then in zip(captured, committed, strict=True):
        assert _short(now) == then, _key(now)


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


def test_every_request_goes_to_the_responses_endpoint_unstored_with_allowed_keys(
    captured: list[dict[str, Any]],
) -> None:
    for entry in captured:
        body = entry["body"]
        assert entry["path"].endswith("/responses"), _key(entry)
        assert body.get("store") is False, _key(entry)
        assert not set(body) - _ALLOWED_KEYS - {"include"}, _key(entry)


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
