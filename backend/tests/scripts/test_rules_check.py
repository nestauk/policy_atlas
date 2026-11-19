"""Coverage for the rule file check (`scripts/rules_check.py`)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "rules_check.py"

_FILES = [
    "backend/alembic/env.py",
    "backend/src/policy_atlas/core/tracing.py",
    "frontend/src/api/sseFrame.ts",
]

_RULE = """---
paths:
  - "backend/src/policy_atlas/core/**"
  - "frontend/src/store/**"
---

# Title

- A fact naming `core/tracing.py`, `backend/alembic/env.py`, `tracing.py` and a symbol
  `scrub_nul()`, plus a path that is gone: `core/retired.py`.
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rules_check", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flags_a_pattern_that_matches_nothing_and_a_path_that_is_gone() -> None:
    violations, counts = _load().check_rule("rule.md", _RULE, _FILES)

    assert counts == {"backend/src/policy_atlas/core/**": 1, "frontend/src/store/**": 0}
    assert violations == [
        "rule.md: paths pattern matches no tracked file: frontend/src/store/**",
        "rule.md: body names a path that does not exist: core/retired.py",
    ]
