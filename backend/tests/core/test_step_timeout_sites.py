"""Every model request carries its step's timeout and none retries silently (task 057, D12).

A source scan over ``backend/src/policy_atlas`` (Python's own parser, not text
search), so a new call site cannot skip the rule:

- ``resolve_openai_client(...)`` is never given ``timeout=`` or ``max_retries=``
  (the client never retries on its own and has no timeout of its own);
- every ``openai_kwargs(...)``, ``parse_structured(...)`` and ``traced_parse(...)``
  call passes ``timeout_s=`` (and ``traced_parse`` passes ``step=``);
- no ``OpenAI(...)`` client is built outside ``core/openai_client.py``;
- a generation observation is opened only by ``tracing.traced_attempts`` (one
  traced retry, each attempt its own generation), except at the sites listed in
  :data:`NOT_WRAPPED` with the reason. The per-site table is
  ``docs/tasks/057-queued-ingest/call-sites.md``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "policy_atlas"

#: Generation observations deliberately NOT opened through ``traced_attempts``,
#: keyed ``(module path under src/policy_atlas, enclosing class/function path)``.
#:
#: The chat prose stream (``OpenAIChatBackend._stream_then_parse`` step 1) is exempt too
#: (it sends text to the user as it arrives, so a retry would repeat it; its timeout bounds
#: the wait between chunks, contract D12), but it opens no generation observation, so the
#: scan cannot list it. The chat tool turn and final parse are wrapped in ``traced_attempts``.
NOT_WRAPPED: dict[tuple[str, str], str] = {
    # traced_attempts itself opens one generation per attempt.
    ("core/tracing.py", "traced_attempts"): "the wrapper's own per-attempt observation",
    (
        "evidence_search/sourcing/search_generation.py",
        "ClaudeSearchGenerationBackend.generate_queries",
    ): (
        "exempt-boto: ClaudeSearchGenerationBackend's Bedrock converse call; not an OpenAI "
        "request, no route step, only the unused bedrock-claude route selects it. botocore "
        "makes one attempt with a 60 s read timeout (BEDROCK_CLIENT_CONFIG)."
    ),
}


@dataclass(frozen=True)
class _Call:
    module: str
    function: str
    line: int
    callee: str
    keywords: frozenset[str]
    as_type: str | None


def _callee(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _calls() -> list[_Call]:
    found: list[_Call] = []
    for path in sorted(SRC.rglob("*.py")):
        module = path.relative_to(SRC).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        def visit(node: ast.AST, function: str, module: str = module) -> None:
            for child in ast.iter_child_nodes(node):
                name = function
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    name = child.name if function == "<module>" else f"{function}.{child.name}"
                if isinstance(child, ast.Call):
                    as_type = next(
                        (
                            kw.value.value
                            for kw in child.keywords
                            if kw.arg == "as_type"
                            and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                        ),
                        None,
                    )
                    found.append(
                        _Call(
                            module=module,
                            function=function,
                            line=child.lineno,
                            callee=_callee(child),
                            keywords=frozenset(kw.arg for kw in child.keywords if kw.arg),
                            as_type=as_type,
                        )
                    )
                visit(child, name)

        visit(tree, "<module>")
    return found


CALLS = _calls()


def _where(call: _Call) -> str:
    return f"{call.module}:{call.line} ({call.function})"


def test_the_scan_sees_the_sites() -> None:
    """Guard against a scan that silently finds nothing."""
    builders = [c for c in CALLS if c.callee == "resolve_openai_client"]
    assert len(builders) == 21
    assert any(c.callee == "parse_structured" for c in CALLS)
    assert any(c.callee == "traced_parse" for c in CALLS)


def test_no_client_is_given_a_timeout_or_a_retry_count() -> None:
    offenders = [
        _where(c)
        for c in CALLS
        if c.callee == "resolve_openai_client" and c.keywords & {"timeout", "max_retries"}
    ]
    assert offenders == []


@pytest.mark.parametrize("callee", ["openai_kwargs", "parse_structured", "traced_parse"])
def test_every_request_helper_call_passes_its_step_timeout(callee: str) -> None:
    offenders = [
        _where(c)
        for c in CALLS
        if c.callee == callee
        and c.module != "core/openai_client.py"
        and "timeout_s" not in c.keywords
    ]
    assert offenders == []


def test_every_traced_parse_call_names_its_step() -> None:
    offenders = [
        _where(c) for c in CALLS if c.callee == "traced_parse" and "step" not in c.keywords
    ]
    assert offenders == []


def test_no_openai_client_is_built_outside_the_client_module() -> None:
    offenders = [
        _where(c) for c in CALLS if c.callee == "OpenAI" and c.module != "core/openai_client.py"
    ]
    assert offenders == []


def test_only_traced_attempts_opens_generations_outside_the_exempt_sites() -> None:
    offenders = [
        _where(c)
        for c in CALLS
        if c.as_type == "generation" and (c.module, c.function) not in NOT_WRAPPED
    ]
    assert offenders == []


def test_every_exempt_site_still_exists() -> None:
    """A stale exemption would hide a new site behind an old name."""
    present = {(c.module, c.function) for c in CALLS if c.as_type == "generation"}
    assert set(NOT_WRAPPED) <= present
