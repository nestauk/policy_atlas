"""Path-scoped rule file check (make rules-check).

Claude Code loads a file under `.claude/rules/` only when an agent touches a file that
matches one of its `paths:` patterns. A pattern that matches nothing means the rule never
loads, and a path the rule names that no longer exists means the rule has gone out of date.
This check fails on either, for every rule file:

- each `paths:` pattern must match at least one tracked file;
- each repository path the body names in backticks must exist (looked up from the
  repository root, then under `backend/`, `backend/src/policy_atlas/` and `frontend/`).

A backticked token counts as a path when it has a `/` or ends in a common file extension,
and has no spaces or brackets. Stdlib only, no dependency on the synced environment.
"""

import re
import subprocess
import sys
from pathlib import Path

RULES_DIR = ".claude/rules"
# Where a path written in a rule body may start, besides the repository root.
PATH_BASES = ("", "backend/", "backend/src/policy_atlas/", "frontend/")
EXTENSIONS = (".py", ".ts", ".tsx", ".md", ".toml", ".json", ".sh", ".yml", ".yaml", ".ini")
BACKTICK = re.compile(r"`([^`\n]+)`")


def tracked_files(root: Path) -> list[str]:
    """Return repo-root-relative paths of all tracked files."""
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a `paths:` glob: `**` spans folders, `*` and `?` stay inside one."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def split_rule(text: str) -> tuple[list[str], str]:
    """Return the `paths:` patterns from the frontmatter and the body after it."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return [], text
    patterns = []
    in_paths = False
    for line in lines[1:end]:
        if line.strip() == "paths:":
            in_paths = True
        elif in_paths and line.strip().startswith("- "):
            patterns.append(line.strip()[2:].strip().strip("\"'"))
        elif line.strip():
            in_paths = False
    return patterns, "\n".join(lines[end + 1 :])


def is_path_token(token: str) -> bool:
    """Whether a backticked token reads as a repository path."""
    if any(c in token for c in " ()[]{}<>") or token.startswith(("http:", "https:")):
        return False
    return "/" in token or token.endswith(EXTENSIONS)


def path_exists(token: str, known: set[str], names: set[str]) -> bool:
    """Whether a path token names a tracked file or folder from one of PATH_BASES.

    Args:
        token: The backticked text.
        known: Every tracked file and every folder that holds one.
        names: The base names of every tracked file (for a bare file name).
    """
    token = token.rstrip("/")
    if "/" not in token and token in names:
        return True
    return any(base + token in known for base in PATH_BASES)


def check_rule(rel: str, text: str, files: list[str]) -> tuple[list[str], dict[str, int]]:
    """Check one rule file against the tracked files.

    Args:
        rel: The rule file's repo-root-relative path, used in messages.
        text: The rule file's content.
        files: Repo-root-relative paths of every tracked file.

    Returns:
        The violation messages, and how many tracked files each pattern matches.
    """
    violations = []
    counts: dict[str, int] = {}
    patterns, body = split_rule(text)
    for pattern in patterns:
        regex = glob_regex(pattern)
        counts[pattern] = sum(1 for f in files if regex.match(f))
        if counts[pattern] == 0:
            violations.append(f"{rel}: paths pattern matches no tracked file: {pattern}")
    known = set(files) | {f.rsplit("/", i)[0] for f in files for i in range(1, f.count("/") + 1)}
    names = {f.rsplit("/", 1)[-1] for f in files}
    for token in BACKTICK.findall(body):
        if is_path_token(token) and not path_exists(token, known, names):
            violations.append(f"{rel}: body names a path that does not exist: {token}")
    return violations, counts


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    files = tracked_files(root)
    rule_files = sorted((root / RULES_DIR).glob("*.md"))
    violations = []
    for path in rule_files:
        rel = path.relative_to(root).as_posix()
        found, counts = check_rule(rel, path.read_text(encoding="utf-8"), files)
        violations.extend(found)
        total = sum(1 for f in files if any(glob_regex(p).match(f) for p in counts))
        print(f"{rel}: {len(counts)} pattern(s), {total} tracked file(s) matched")
    for v in violations:
        print(f"FAIL {v}", file=sys.stderr)
    print(f"rules-check: {len(rule_files)} rule file(s) checked, {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
