"""OKF bundle conformance gate (make okf-validate).

Checks the repo's two Open Knowledge Format (OKF) bundles. Each bundle is checked against the
version its root `index.md` declares (`okf_version`, default "0.1"):

- every version: every non-reserved .md file needs a frontmatter block with a non-empty `type`;
- version 0.2 and later, also: the frontmatter is safe YAML at the top level (a plain value has
  no `: `, no ` #` and does not start with a quote or a backtick, so a YAML reader reads it as
  written), and no concept keeps the 0.1 forms the 0.2 format replaced (`timestamp`, a
  `# Citations` section).

docs/specs/sources/ is exempt: raw frozen sources, not concepts. Stdlib only, no YAML dependency.
"""

import re
import sys
from pathlib import Path

BUNDLES = ["docs/specs", "docs/knowledge"]
RESERVED = {"index.md", "log.md"}
EXEMPT_PREFIX = "docs/specs/sources/"

TOP_KEY = re.compile(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$")
VERSION = re.compile(r"""^okf_version:\s*["']?([0-9.]+)["']?\s*$""", re.MULTILINE)
CITATIONS = re.compile(r"^#{1,6}[ \t]+Citations[ \t]*$", re.MULTILINE)


def bundle_version(bundle: Path) -> tuple[int, ...]:
    """Return the `okf_version` the bundle's root index declares, as a tuple; (0, 1) if none."""
    index = bundle / "index.md"
    text = index.read_text(encoding="utf-8") if index.exists() else ""
    m = VERSION.search(text.split("\n---", 1)[0]) if text.startswith("---") else None
    return tuple(int(p) for p in (m.group(1) if m else "0.1").split("."))


def plain_value_problem(value: str) -> str | None:
    """Return why a top-level YAML value would not read as written, or None."""
    if value[0] in "[{|>&*!" or value.startswith(("'", '"')) and value[-1] == value[0]:
        return None  # flow collection, block scalar, anchor, or a closed quoted string
    if value[0] in "`@\"'%":
        return f"starts with {value[0]!r}; quote the value"
    if ": " in value or " #" in value:
        return "has ': ' or ' #' in a plain value; quote the value"
    return None


def check(path: Path, version: tuple[int, ...] = (0, 1)) -> str | None:
    """Return a violation message for one concept file, or None if conformant."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "missing frontmatter block"
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return "unterminated frontmatter block"
    keys = {}
    for line in lines[1:end]:
        m = TOP_KEY.match(line)
        if m:
            keys[m.group(1)] = (m.group(2) or "").strip()
    if not keys.get("type"):
        return "frontmatter has no non-empty `type`"
    if version < (0, 2):
        return None
    for key, value in keys.items():
        problem = value and plain_value_problem(value)
        if problem:
            return f"frontmatter `{key}` {problem}"
    if "timestamp" in keys:
        return "`timestamp` is the 0.1 form; use `generated: {by, at}`"
    if CITATIONS.search("\n".join(lines[end + 1 :])):
        return "`# Citations` is the 0.1 form; list them under `sources` in the frontmatter"
    return None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = []
    checked = 0
    for bundle in BUNDLES:
        version = bundle_version(root / bundle)
        for path in sorted((root / bundle).rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            if path.name in RESERVED or rel.startswith(EXEMPT_PREFIX):
                continue
            checked += 1
            problem = check(path, version)
            if problem:
                violations.append(f"{rel}: {problem}")
    for v in violations:
        print(f"FAIL {v}", file=sys.stderr)
    print(f"okf-validate: {checked} concepts checked, {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
