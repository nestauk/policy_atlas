"""Coverage for the prompt hash guard (`scripts/prompt_hash_guard.py`).

A pinned Python file is hashed by its syntax tree, so a `#` comment or a
formatting change keeps its hash and a change to any string changes it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "prompt_hash_guard.py"

_SOURCE = '''"""A pinned module."""

SYSTEM = "You are a careful reviewer."  # the system prompt


def build(question: str) -> str:
    return SYSTEM + question
'''


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prompt_hash_guard", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def _hash(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return guard.sha256_of(path)


def test_comment_and_formatting_edits_keep_the_hash(tmp_path: Path) -> None:
    edited = (
        _SOURCE.replace("  # the system prompt", "  # the reviewer's system prompt")
        .replace("def build", "# Joins the prompt.\n\n\ndef build")
        .replace("return SYSTEM + question", "return (SYSTEM\n            + question)")
    )

    assert _hash(tmp_path, "a.py", _SOURCE) == _hash(tmp_path, "b.py", edited)


def test_string_and_docstring_edits_change_the_hash(tmp_path: Path) -> None:
    base = _hash(tmp_path, "a.py", _SOURCE)
    prompt_edit = _SOURCE.replace("careful reviewer", "careful editor")
    docstring_edit = _SOURCE.replace("A pinned module.", "A pinned prompt module.")

    assert _hash(tmp_path, "b.py", prompt_edit) != base
    assert _hash(tmp_path, "c.py", docstring_edit) != base


def test_text_files_are_hashed_by_their_bytes(tmp_path: Path) -> None:
    base = _hash(tmp_path, "a.txt", "Answer the question.\n")

    assert _hash(tmp_path, "b.txt", "Answer the question. \n") != base
