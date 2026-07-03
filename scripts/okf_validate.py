"""OKF bundle conformance gate (make okf-validate).

Checks the repo's two OKF bundles against the v0.1 conformance rules
(docs/agentic-ops/references/open-knowledge-format.md §9): every
non-reserved .md file needs a parseable frontmatter block with a
non-empty `type`. docs/specs/sources/ is exempt — raw frozen sources,
not concepts (backlog: "OKF lanes", 2026-06-24).

Stdlib only, no YAML dependency.
"""

import re
import sys
from pathlib import Path

BUNDLES = ["docs/specs", "docs/knowledge"]
RESERVED = {"index.md", "log.md"}
EXEMPT_PREFIX = "docs/specs/sources/"


def check(path: Path) -> str | None:
    """Return a violation message for one concept file, or None if conformant."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return "missing frontmatter block"
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return "unterminated frontmatter block"
    # ponytail: regex over a YAML parser — `type:` at top level is all v0.1 requires
    for line in lines[1:end]:
        m = re.match(r"^type:\s*(\S.*)$", line)
        if m:
            return None
    return "frontmatter has no non-empty `type`"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = []
    checked = 0
    for bundle in BUNDLES:
        for path in sorted((root / bundle).rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            if path.name in RESERVED or rel.startswith(EXEMPT_PREFIX):
                continue
            checked += 1
            problem = check(path)
            if problem:
                violations.append(f"{rel}: {problem}")
    for v in violations:
        print(f"FAIL {v}", file=sys.stderr)
    print(f"okf-validate: {checked} concepts checked, {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
