"""Only the shared OpenAI module may send model requests."""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SHARED_MODULE = REPO / "backend/src/policy_atlas/core/openai_client.py"


def test_only_the_shared_module_touches_the_openai_request_api() -> None:
    """No other Python file reads ``.chat.completions`` or ``.responses``.

    Reads each file as a syntax tree, so comments and docstrings never count.
    """
    hits = []
    for root in (REPO / "backend/src", REPO / "scripts"):
        for path in sorted(root.rglob("*.py")):
            if path == SHARED_MODULE:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Attribute):
                    continue
                chat_completions = (
                    node.attr == "completions"
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "chat"
                )
                if chat_completions or node.attr == "responses":
                    hits.append(f"{path.relative_to(REPO)}:{node.lineno}")
    assert not hits, "Model requests must go through core/openai_client.py:\n" + "\n".join(hits)
