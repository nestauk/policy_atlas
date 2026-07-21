"""Monorepo-hoist path audit (make audit-paths).

Task 025 A.2 moved the Python project's tooling paths under `backend/`
(`pyproject.toml`, `uv.lock`, `src/`, `tests/`, `alembic/`, `alembic.ini`,
`.env.example`) while keeping the `policy_atlas` import name untouched. This
gate catches any tracked file that still references one of those paths as
repo-root-relative — a straggler that would silently break once tooling runs
with CWD=`backend/`.

Point-in-time records (task archives, discharged decision logs, past
knowledge entries) are allowed to keep describing the pre-hoist layout
verbatim, since they're dated history, not live instructions — see
ALLOWLIST_PREFIXES below. Everything else that references a hoisted path
must spell it `backend/`-relative.

Stdlib only, no dependency on the synced environment.
"""

import re
import subprocess
import sys
from pathlib import Path

# Line-scoped: a moved-path token preceded by start-of-line, whitespace, a
# quote, a paren/bracket, or `=` — i.e. used as a path, not part of a longer
# identifier (e.g. this excludes `src/policy_atlas` appearing mid-word).
PATTERN = re.compile(
    r"""(^|[\s"'(\[=])(src/policy_atlas|tests/|alembic/|alembic\.ini|pyproject\.toml|uv\.lock|\.env\.example)"""
)

# File kinds the audit scans (tracked files only, via `git ls-files`).
GLOBS = ["Makefile", "*.yml", "*.yaml", "*.toml", "*.md", "*.py", "*.sh", "*.ini"]

# Path prefixes exempt from the sweep: dated, point-in-time records that
# must NOT be rewritten to look like they were always about `backend/`.
ALLOWLIST_PREFIXES = (
    "docs/tasks/",
    "docs/agentic-ops/failure-log.md",
    "docs/agentic-ops/references/",
    "docs/knowledge/",
    "backend/",
    "scripts/audit_paths.py",
    ".claude/",
    ".cursor/",
)


def tracked_files(root: Path) -> list[str]:
    """Return repo-root-relative paths of tracked files matching GLOBS."""
    out = subprocess.run(
        ["git", "ls-files", "--", *GLOBS],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def check(path: Path, rel: str) -> list[str]:
    """Return violation strings ("rel:lineno: line") for one file."""
    violations = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if PATTERN.search(line):
            violations.append(f"{rel}:{lineno}: {line.strip()}")
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = []
    checked = 0
    for rel in sorted(tracked_files(root)):
        if rel.startswith(ALLOWLIST_PREFIXES):
            continue
        checked += 1
        violations.extend(check(root / rel, rel))
    for v in violations:
        print(f"FAIL {v}", file=sys.stderr)
    print(f"audit-paths: {checked} file(s) checked, {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
