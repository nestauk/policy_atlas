"""Prompt-family content-hash guard.

Product prompt text is reviewed work. It must never change as a side effect
of an unrelated refactor. This script hashes every prompt-bearing file under
`backend/src/policy_atlas/` (Python modules with "prompt" in the name, and
every `.txt` file, which is where prompt wordings that are kept out of Python
live) and compares against a committed hash list (`scripts/prompt_hashes.json`):

    python3 scripts/prompt_hash_guard.py           # verify (exit 1 on drift)
    python3 scripts/prompt_hash_guard.py --update  # rewrite the hash list

What is hashed:

- A `.txt` file: its bytes, so any change counts.
- A `.py` file: its syntax tree (the structure Python parses the code into),
  not its bytes. Line numbers, formatting and `#` comments are not part of the
  tree, so editing them does not change the hash. Every string in the code is
  part of the tree, docstrings included, so a change to any text the model can
  see (a prompt string, a `Field(description=...)`, a class docstring that
  becomes a schema description) does change it. The tree is written out in a
  form that is the same on every supported Python version.

The rule: prompt surfaces change only as named, deliberate slice work. A
drifted or missing hash means a prompt file changed (or was added/removed)
without that being the explicit subject of the commit; re-run with --update
only when the prompt change itself is the reviewed, intentional deliverable.

Stdlib only, no dependency on the synced environment (mirrors
scripts/audit_paths.py).
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

RULE_MESSAGE = "prompt surfaces change only as named, deliberate slice work"

HASH_LIST_PATH = Path(__file__).resolve().parent / "prompt_hashes.json"
PROMPT_ROOT = Path(__file__).resolve().parent.parent / "backend" / "src" / "policy_atlas"
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Files that carry model-facing prompt text without "prompt" in the name (repo-relative).
EXTRA_FILES: tuple[str, ...] = (
    # The intervention record's Field descriptions are the model's schema.
    "backend/src/policy_atlas/evidence_search/extract/interventions_records.py",
    # The finding records' Field descriptions and their shared texts, and the
    # grounding judge's field list.
    "backend/src/policy_atlas/evidence_search/extract/iof_records.py",
    "backend/src/policy_atlas/evidence_search/extract/icf_records.py",
    "backend/src/policy_atlas/evidence_search/extract/finding_references.py",
    "backend/src/policy_atlas/evidence_search/synthesis/grounding_judge.py",
    # These hold model-facing text outside the "prompt" file names.
    # The finding vetters' system and user prompts (IOF and ICF).
    "backend/src/policy_atlas/evidence_search/extract/finding_vetter.py",
    # The reranker's system and user prompts.
    "backend/src/policy_atlas/evidence_search/corpus/ranking.py",
    # The theme discovery and assignment prompts.
    "backend/src/policy_atlas/evidence_search/corpus/theme_grouping.py",
    # The facet-group clustering prompts.
    "backend/src/policy_atlas/evidence_search/group/group_clustering.py",
    # The planner prompt substitutes TIME_BANDS from here, so a band edit
    # changes the prompt text.
    "backend/src/policy_atlas/runtime/task_plan.py",
)


def prompt_files() -> list[Path]:
    """Every prompt-bearing file under backend/src/policy_atlas, plus EXTRA_FILES.

    That is every Python module whose name contains "prompt", plus every
    ``.txt`` file: prompt wordings kept out of Python (for example the
    ``search_queries_system_v3.txt`` family) live in text files beside the
    module that reads them, and they must be guarded just the same.
    """
    modules = (path for path in PROMPT_ROOT.rglob("*.py") if "prompt" in path.name.lower())
    texts = PROMPT_ROOT.rglob("*.txt")
    extras = (REPO_ROOT / extra for extra in EXTRA_FILES)
    return sorted({*modules, *texts, *extras})


def rel(path: Path) -> str:
    """Repo-root-relative, forward-slash path (stable across platforms)."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _tree_text(node: object) -> str:
    """Write a syntax tree out as text, leaving out empty fields.

    `ast.dump` prints empty fields on some Python versions and not on others,
    so it would give a different hash on each; this form does not.
    """
    if isinstance(node, ast.AST):
        fields = (
            f"{name}={_tree_text(value)}"
            for name, value in ast.iter_fields(node)
            if value is not None and value != []
        )
        return f"{type(node).__name__}({', '.join(fields)})"
    if isinstance(node, list):
        return "[" + ", ".join(_tree_text(item) for item in node) + "]"
    return repr(node)


def sha256_of(path: Path) -> str:
    """Hash a pinned file: a `.py` file's syntax tree, any other file's bytes."""
    if path.suffix == ".py":
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return hashlib.sha256(_tree_text(tree).encode("utf-8")).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    return {rel(path): sha256_of(path) for path in prompt_files()}


def load_committed() -> dict[str, str]:
    if not HASH_LIST_PATH.exists():
        return {}
    return json.loads(HASH_LIST_PATH.read_text(encoding="utf-8"))


def write_committed(hashes: dict[str, str]) -> None:
    HASH_LIST_PATH.write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    update = "--update" in argv
    current = current_hashes()

    if update:
        write_committed(current)
        print(f"prompt-hash-guard: wrote {len(current)} hash(es) to {HASH_LIST_PATH}")
        return 0

    committed = load_committed()
    drifted = sorted(
        path for path in current if path in committed and current[path] != committed[path]
    )
    missing = sorted(path for path in current if path not in committed)
    removed = sorted(path for path in committed if path not in current)

    if not drifted and not missing and not removed:
        print(f"prompt-hash-guard: {len(current)} prompt file(s) unchanged")
        return 0

    print(f"FAIL prompt-hash-guard: {RULE_MESSAGE}", file=sys.stderr)
    for path in drifted:
        print(f"  drifted: {path}", file=sys.stderr)
    for path in missing:
        print(f"  missing from {HASH_LIST_PATH.name} (new prompt file): {path}", file=sys.stderr)
    for path in removed:
        print(f"  in {HASH_LIST_PATH.name} but file no longer exists: {path}", file=sys.stderr)
    print(
        "If this prompt change is the deliberate, reviewed subject of this "
        "change, run: python3 scripts/prompt_hash_guard.py --update",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
