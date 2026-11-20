"""Every model call site still sends the request recorded in the committed capture.

``capture_requests.py`` drives each call site with fixed inputs and records the
HTTP request it sends (address path, JSON body, timeout) on the ``bedrock`` route.
It runs in a child process: this suite's ``conftest.py`` removes the route
variable, and many model ids and efforts are read from the route when their
modules are first imported, so the route must be set before any import.

Refresh the committed capture deliberately with ``REQUEST_CAPTURE_UPDATE=1``; the
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
        BASELINE.write_bytes(out.read_bytes())
    entries: list[dict[str, Any]] = json.loads(out.read_text(encoding="utf-8"))
    return entries


def _key(entry: dict[str, Any]) -> str:
    return f"{entry['step']}/{entry['variant']}"


def test_every_request_matches_the_committed_capture(captured: list[dict[str, Any]]) -> None:
    baseline: list[dict[str, Any]] = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert [_key(entry) for entry in captured] == [_key(entry) for entry in baseline]
    for now, then in zip(captured, baseline, strict=True):
        assert now == then, _key(now)


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
