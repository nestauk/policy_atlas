"""Coverage for the knowledge bundle check (`scripts/okf_validate.py`)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "okf_validate.py"

_LEGACY = """---
type: Convention
description: A note: written with the 0.1 forms
timestamp: 2026-01-01
---

# Rule

# Citations

- `core/events.py`
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("okf_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle(tmp_path: Path, version: str, concept: str) -> Path:
    tmp_path.mkdir()
    (tmp_path / "index.md").write_text(f'---\nokf_version: "{version}"\n---\n\n# Index\n')
    (tmp_path / "concept.md").write_text(concept)
    return tmp_path


def test_a_bundle_is_checked_against_the_version_its_index_declares(tmp_path: Path) -> None:
    okf = _load()
    old = _bundle(tmp_path / "old", "0.1", _LEGACY)
    new = _bundle(tmp_path / "new", "0.2", _LEGACY)

    assert okf.bundle_version(old) == (0, 1)
    assert okf.check(old / "concept.md", okf.bundle_version(old)) is None
    assert okf.bundle_version(new) == (0, 2)
    assert okf.check(new / "concept.md", okf.bundle_version(new)) == (
        "frontmatter `description` has ': ' or ' #' in a plain value; quote the value"
    )


def test_a_0_2_concept_fails_on_each_unsafe_value_and_each_legacy_form(tmp_path: Path) -> None:
    okf = _load()
    cases = {
        "description: `code` first\n": "frontmatter `description` starts with '`'; quote the value",
        'description: "Quoted" then text\n': (
            "frontmatter `description` starts with '\"'; quote the value"
        ),
        "description: call #1 is cut off\n": (
            "frontmatter `description` has ': ' or ' #' in a plain value; quote the value"
        ),
        "timestamp: 2026-01-01\n": "`timestamp` is the 0.1 form; use `generated: {by, at}`",
    }
    for line, expected in cases.items():
        path = tmp_path / "concept.md"
        path.write_text(f"---\ntype: Convention\n{line}---\n\n# Rule\n")
        assert okf.check(path, (0, 2)) == expected, line

    path.write_text("---\ntype: Convention\n---\n\n# Citations\n\n- `core/events.py`\n")
    assert okf.check(path, (0, 2)) == (
        "`# Citations` is the 0.1 form; list them under `sources` in the frontmatter"
    )


def test_a_0_2_concept_with_quoted_values_and_v0_2_families_passes(tmp_path: Path) -> None:
    path = tmp_path / "concept.md"
    path.write_text(
        "---\ntype: Convention\ntitle: 'A note: quoted'\n"
        'description: "`code` first, then: text"\ntags: [a, "b"]\n'
        "generated:\n  by: human:someone\n  at: 2026-01-01\n"
        'sources:\n  - resource: "core/events.py"\n---\n\n# Rule\n'
    )
    assert _load().check(path, (0, 2)) is None
