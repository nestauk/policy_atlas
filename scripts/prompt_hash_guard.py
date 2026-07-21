"""Prompt-family content-hash guard (task 025 C.4, plan pin 11/12).

Product prompt text is taste-bearing, reviewed work — it must never drift as
a side effect of unrelated refactoring (e.g. the runner's parking/
continuation seam, or the web-app foundation build generally). This script
hashes every prompt-bearing module under `backend/src/policy_atlas/` and
compares against a committed hash list (`scripts/prompt_hashes.json`):

    python3 scripts/prompt_hash_guard.py           # verify (exit 1 on drift)
    python3 scripts/prompt_hash_guard.py --update  # rewrite the hash list

The rule: prompt surfaces change only as named, deliberate slice work — task
025 ships no prompt changes. A drifted or missing hash means a prompt module
changed (or was added/removed) without that being the explicit subject of
the commit; re-run with --update only when the prompt change itself is the
reviewed, intentional deliverable.

Stdlib only, no dependency on the synced environment (mirrors
scripts/audit_paths.py).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RULE_MESSAGE = (
    "prompt surfaces change only as named, deliberate slice work — task 025 "
    "ships no prompt changes"
)

HASH_LIST_PATH = Path(__file__).resolve().parent / "prompt_hashes.json"
PROMPT_ROOT = Path(__file__).resolve().parent.parent / "backend" / "src" / "policy_atlas"
REPO_ROOT = Path(__file__).resolve().parent.parent


def prompt_files() -> list[Path]:
    """Every file under backend/src/policy_atlas whose name contains "prompt"."""
    return sorted(
        path for path in PROMPT_ROOT.rglob("*.py") if "prompt" in path.name.lower()
    )


def rel(path: Path) -> str:
    """Repo-root-relative, forward-slash path (stable across platforms)."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def sha256_of(path: Path) -> str:
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
        print(f"prompt-hash-guard: {len(current)} prompt module(s) unchanged")
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
