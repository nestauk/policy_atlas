#!/usr/bin/env python3
"""Task 038 vocabulary sweep: a reviewed, table-driven identifier rename.

The slice renames the product vocabulary across the backend and the frontend
(`project`->`task`, `portfolio`->`project`, `evidence_base`->`evidence_search`,
`orchestrator`/`orchestrate`->`agent`, `OrchestrationPlan`->`TaskPlan`,
`project_source_snapshot`->`task_source_snapshot`, `pss`->`tss`, `oplan`->`plan`).
A prose
search-and-replace is forbidden (plan review P1), so this tool works on two
explicit inputs only:

1. **Identifiers.** Every word-bounded ``[A-Za-z_][A-Za-z0-9_]*`` run is split
   into words (snake and camel), matched against the ordered rule table in
   :data:`RULES` (compound before bare), and rebuilt with the original casing
   and separators. Nothing else in the file is considered.
2. **Path-like string literals.** The handful of shapes the identifier pass
   cannot see -- the hyphenated ``evidence-base`` and the ``orchestration_plan``
   *table string* (which becomes ``plan``, not ``task_plan``) -- are listed in
   :data:`LITERAL_RULES` and scoped to the files that may carry them.

Everything the rules must not touch is enumerated too: :data:`NEVER_MAPPED`
(exact identifiers, optionally phase-scoped), :data:`NEVER_MAPPED_CONTEXTS`
(text spans such as ``uv run --project`` or the Nesta "project page" link), and
:data:`STRING_EXEMPT` (prompt files and copy modules, whose *prose regions* --
string literals and comments -- are hand-edited by the lead).

Modes:

``--scan``
    Walk the phase file set and emit the reviewable markdown report: the
    identifier table, the unmapped identifiers that need a lead decision, the
    collision report, the never-mapped hits and the prose-context occurrences.
    Exits non-zero when any collision remains.
``--apply``
    Rewrite the files. Refuses while a collision remains. It does **not**
    ``git mv`` anything -- the lead moves packages and modules by hand -- but it
    does rewrite every import path and module reference so the moved modules
    resolve.

Idempotence needs a ledger, and here is why. Step 2 *produces* `project`, which
is step 1's source word, so a second textual pass over a swept tree would rename
the Project entity on to `task`. No amount of tokenising can tell a `project`
that was always a Project from one that used to be a Portfolio. So ``--apply``
records the post-sweep SHA-256 of every file it writes in
``scripts/.rename_038_state.json`` (gitignored; with the steps it applied) and skips any file
still carrying that hash for those steps. So a second ``--apply`` reports zero
changes; ``--step 1`` then ``--step 2`` still works; and a file the sweep never
reached -- a module a merge from ``dev`` brought in -- is still swept. A file
that has *changed* since its own sweep is re-swept whole and named in the output;
the collision check catches that only when the file also declares the target
symbol, so never run ``--apply`` on an edited post-038 tree. Rebase by sweeping
the arriving files, not the settled ones.

Step 1 is every rule except ``portfolio``->``project``; step 2 is that rule
alone. ``--step all`` runs step 1 to completion and only then step 2, which is
the collision guard (plan D3): once step 1 has finished, no ``project`` token
survives for step 2 to re-rename.

Usage::

    uv run --project backend python scripts/rename_038.py --scan --phase 3
    python3 scripts/rename_038.py --scan --phase 4 --out scan-frontend.md
    python3 scripts/rename_038.py --apply --phase 3 --step all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# The rule table (plan D1). Order matters: compound before bare.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One token->target rule.

    Attributes:
        step: 1 for every rule but ``portfolio``->``project``, which is step 2.
        source: The word sequence to match, lowercased.
        target: The word sequence to write in its place.
        note: Why the rule exists; reproduced in the scan report.
    """

    step: int
    source: tuple[str, ...]
    target: tuple[str, ...]
    note: str

    @property
    def name(self) -> str:
        return f"{'_'.join(self.source)} -> {'_'.join(self.target)}"


RULES: tuple[Rule, ...] = (
    Rule(
        1,
        ("project", "source", "snapshot"),
        ("task", "source", "snapshot"),
        "compound, before bare",
    ),
    Rule(
        1,
        ("orchestration", "plan"),
        ("task", "plan"),
        "identifier/module; OrchestrationPlan -> TaskPlan",
    ),
    Rule(
        1,
        ("evidence", "base"),
        ("evidence", "search"),
        "capability package, key and stored value",
    ),
    Rule(1, ("pss",), ("tss",), "constraint infix"),
    Rule(1, ("oplan",), ("plan",), "constraint infix (lead ruling, 2026-09-04)"),
    Rule(1, ("orchestrator",), ("agent",), "persona: modules, classes, log/span names, env vars"),
    Rule(1, ("orchestrate",), ("agent",), "module, OrchestrateResult, log orchestrate.start"),
    Rule(1, ("project",), ("task",), "the entity token"),
    Rule(2, ("portfolio",), ("project",), "runs only after step 1 completes"),
)

# Longest word sequence first so `project_source_snapshot` wins over `project`.
ORDERED_RULES: tuple[Rule, ...] = tuple(
    sorted(RULES, key=lambda r: -len(r.source))
)

STEPS: tuple[int, ...] = (1, 2)

# --------------------------------------------------------------------------
# Never mapped (plan D1). Exact identifiers, optionally scoped to a phase.
# --------------------------------------------------------------------------

ALL_PHASES = frozenset({3, 4})

NEVER_MAPPED: dict[str, frozenset[int]] = {
    # Retained frontend exports: the *screen* words, which do not change.
    # `Project`/`Projects`/`Task`/`Tasks` standing alone in the frontend are
    # screen vocabulary in copy and comments, never code identifiers.
    "TASK": frozenset({4}),
    "PROJECT": frozenset({4}),
    "Task": frozenset({4}),
    "Tasks": frozenset({4}),
    "Project": frozenset({4}),
    "Projects": frozenset({4}),
    # Dead export; deleted by hand in phase 8, and `useCreateTask` already
    # exists (plan D4 -- the one predicted collision).
    "useCreateProject": frozenset({4}),
    # Already-correct names that merely contain a target word.
    "agent_judgement_routed": ALL_PHASES,
    "task_count": ALL_PHASES,
    # Extraction profile ids: renaming them would move a fingerprint.
    "eb_iof_base_v1": ALL_PHASES,
    "eb_icf_base_v1": ALL_PHASES,
}

# Text spans that are prose or tooling, never a product identifier. Any
# identifier match overlapping one of these is skipped.
NEVER_MAPPED_CONTEXTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Only the uv flag: a bare `--project` elsewhere (the ops CLI's `rows assign
    # --project`) is the Task flag and must rename (found mid-sweep in ops/cli.py).
    ("uv run --project", re.compile(r"(?<=uv run )--project\b")),
    ("pyproject [project] table", re.compile(r"^\[project\]", re.MULTILINE)),
    ("nesta 'project page' link", re.compile(r"\bproject page\b")),
    ("Langfuse project", re.compile(r"\bLangfuse project\b")),
    # The phrase for the collection of documents stays (owner ruling).
    ("prose phrase 'evidence base'", re.compile(r"\bevidence base\b", re.IGNORECASE)),
    # "(task NNN)" is the engineering slice, not the product Task.
    ("'(task NNN)' slice reference", re.compile(r"\(task\s+\d+", re.IGNORECASE)),
    # Proposed addition to D1, found by the phase-3 scan: a docstring opening
    # `"""Project a row onto the wire shape"""` uses the English verb, not the
    # entity. The determiner is what separates it from the noun -- `"""Project
    # a/one/the/only ...` is the verb, `"""Project-scoped ...` and `"""Project
    # lifecycle tests` are the entity and must rename. Two verb sites carry no
    # determiner ("Project stored ...", "Project resolvable ...") and are left
    # for the lead. Drop this line to re-expose all of them.
    (
        "docstring-initial verb 'Project'",
        re.compile(r"(?<=\"\"\")Project(?=\s+(?:a|an|one|the|only|per|each|every)\b)"),
    ),
)

# --------------------------------------------------------------------------
# Path-like string literals (plan D1). The only string *contents* edited that
# the identifier pass cannot reach on its own.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LiteralRule:
    """A literal rewrite scoped to named files.

    Attributes:
        step: The step the rule belongs to.
        name: Reported as the rule name.
        pattern: What to match. Group ``keep`` is preserved verbatim.
        repl: Replacement template; ``{keep}`` interpolates the ``keep`` group.
        paths: Repo-relative paths (or ``*``-globs) the rule applies to; empty
            means every file in the set.
    """

    step: int
    name: str
    pattern: re.Pattern[str]
    repl: str
    paths: tuple[str, ...] = ()


LITERAL_RULES: tuple[LiteralRule, ...] = (
    # The table name becomes `plan`, while the identifier/module becomes
    # `task_plan`. Only the schema module and the new 038 revision carry the
    # table *string*.
    LiteralRule(
        step=1,
        name='"orchestration_plan" (table string) -> "plan"',
        pattern=re.compile(r"(?P<q>[\"'])orchestration_plan(?P<tail>\.[a-z_]+)?(?P=q)"),
        repl="{q}plan{tail}{q}",
        paths=(
            "backend/src/policy_atlas/core/schema.py",
            "backend/alembic/versions/*038*.py",
        ),
    ),
    # Hyphenated form: the identifier pass sees `evidence` and `base` as two
    # separate words, so it cannot join them.
    LiteralRule(
        step=1,
        name="evidence-base -> evidence-search",
        pattern=re.compile(r"(?<![\w-])evidence-base(?![\w-])"),
        repl="evidence-search",
    ),
)

# --------------------------------------------------------------------------
# File sets (plan D2).
# --------------------------------------------------------------------------

PHASE_ROOTS: dict[int, tuple[tuple[str, tuple[str, ...]], ...]] = {
    3: (
        ("backend/src", (".py",)),
        ("backend/tests", (".py",)),
    ),
    4: (
        ("frontend/src", (".ts", ".tsx", ".md")),
        ("frontend/e2e", (".ts",)),
    ),
}

PHASE_EXTRA_FILES: dict[int, tuple[str, ...]] = {
    3: ("backend/alembic/env.py",),
    4: (),
}

EXCLUDED_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "cdk.out",
        ".git",
        ".claude",
        ".cursor",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
    }
)

EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "docs/specs/sources/",
    "docs/tasks/",
    "docs/adr/",
    "frontend/src/api/gen/",
    ".github/workflows/",
)

EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "frontend/openapi.json",
        "scripts/rename_038.py",
        "scripts/schema_manifest.py",
        # This tool's own test: its fixtures and assertions are the old
        # vocabulary by construction, so sweeping it would destroy it.
        "backend/tests/scripts/test_rename_038.py",
        "docs/agentic-ops/failure-log.md",
        "backlog.md",
    }
)

# The eleven historical migration tests (plan D9): hand-edited to the
# dual-schema strategy, never swept.
MIGRATION_TESTS: tuple[str, ...] = tuple(
    f"backend/tests/core/{name}"
    for name in (
        "test_capability_run_migration.py",
        "test_effect_direction_migration.py",
        "test_extract_schema_v2_migration.py",
        "test_icf_migration.py",
        "test_migrations_025.py",
        "test_migrations_028.py",
        "test_migrations_029.py",
        "test_planning_transcript_migration.py",
        "test_screen_step_rename_migration.py",
        "test_search_migration.py",
        "test_synthesis_refinement_migration.py",
    )
)

PHASE_EXCLUDED_PATHS: dict[int, frozenset[str]] = {
    # `backend/alembic/versions/*` except a new 038 revision is excluded by
    # `is_excluded`; the eleven migration tests are hand-edited (D9).
    3: frozenset(MIGRATION_TESTS),
    # The whole vocabulary module is rewritten by hand in phase 5a (P1).
    4: frozenset({"frontend/src/lib/vocabulary.ts"}),
}

# Prompt-bearing files: the 13 hash-guarded prompt modules and the 2 inline
# prompts. EVERY string literal (docstrings and prompt bodies alike) is left to
# the lead in phase 3.3 -- prompt text is lead-only per AGENTS.md, and the
# prompt version ids (`"orchestrator_v1"`) must not move under ruling R1. Their
# identifiers, imports and comments ARE swept: excluding whole files would leave
# broken imports behind and would fail invariant I4.
PROMPT_EXEMPT: frozenset[str] = frozenset(
    {
        "backend/src/policy_atlas/core/prompt_fields.py",
        "backend/src/policy_atlas/evidence_base/assess/classify_prompt.py",
        "backend/src/policy_atlas/evidence_base/assess/screen_prompt.py",
        "backend/src/policy_atlas/evidence_base/extract/icf_prompt.py",
        "backend/src/policy_atlas/evidence_base/extract/iof_prompt.py",
        "backend/src/policy_atlas/evidence_base/extract/relevance_prompt.py",
        "backend/src/policy_atlas/evidence_base/sourcing/search_prompts.py",
        "backend/src/policy_atlas/evidence_base/synthesis/summary_prompts.py",
        "backend/src/policy_atlas/evidence_base/synthesis/synthesis_prompts_v6.py",
        "backend/src/policy_atlas/evidence_base/synthesis/voice_prompt.py",
        "backend/src/policy_atlas/runtime/chat_prompt.py",
        "backend/src/policy_atlas/runtime/orchestrator_prompt.py",
        "backend/src/policy_atlas/runtime/planner_prompt.py",
        # The 2 inline prompts.
        "backend/src/policy_atlas/evidence_base/synthesis/synthesis_backend.py",
        "backend/src/policy_atlas/evidence_base/extract/finding_vetter.py",
    }
)

# The eleven copy modules: their *user-visible strings* are the V3/V6 copy
# tables, applied by hand. In Python that means the plainly-quoted strings only
# -- a triple-quoted docstring is documentation, and invariant I4 requires it to
# be swept like any other comment.
COPY_EXEMPT: frozenset[str] = frozenset(
    {
        "backend/src/policy_atlas/api/stage_vocabulary.py",
        "backend/src/policy_atlas/runtime/steering.py",
        "frontend/src/lib/errors.ts",
        "frontend/src/views/decisionsPresentation.ts",
        "frontend/src/views/findingsVocabulary.ts",
        "frontend/src/views/historyPresentation.ts",
        "frontend/src/views/landingPresentation.ts",
        "frontend/src/views/sourcesPresentation.ts",
        "frontend/src/views/workspace/checkInPresentation.ts",
        "frontend/src/views/workspace/journey/presentation.ts",
        "frontend/src/views/workspace/planVocabulary.ts",
    }
)

STRING_EXEMPT: frozenset[str] = PROMPT_EXEMPT | COPY_EXEMPT

# Words that must never be left behind unmapped without a lead decision.
# `evidence` is deliberately absent: `evidence_base` is the only mapped form and
# every other `evidence_*` name (`evidence_scope`, `evidence_type`) is already
# right, so watching it would bury the real near-misses in noise.
WATCH_RE = re.compile(r"orchestr|project|portfolio", re.IGNORECASE)
WATCH_EXACT: frozenset[str] = frozenset({"pss", "oplan"})
# Cheap pre-filters. TRIGGER_RE: an identifier without one of these cannot
# match any rule. SCAN_RE additionally admits the watched-but-unmapped tokens.
TRIGGER_RE = re.compile(r"orchestr|project|portfolio|evidence|pss|oplan", re.IGNORECASE)
SCAN_RE = re.compile(r"orchestr|project|portfolio|evidence|pss|oplan", re.IGNORECASE)

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
WORD_RE = re.compile(r"_+|[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")

Span = tuple[int, int]


# --------------------------------------------------------------------------
# Identifier engine
# --------------------------------------------------------------------------


def split_identifier(ident: str) -> list[tuple[str, str]]:
    """Split an identifier into ``("word"|"sep", text)`` items.

    Args:
        ident: A ``[A-Za-z_][A-Za-z0-9_]*`` run.

    Returns:
        The items in order; concatenating their texts rebuilds ``ident``.
    """
    items: list[tuple[str, str]] = []
    for match in WORD_RE.finditer(ident):
        text = match.group(0)
        items.append(("sep" if text[0] == "_" else "word", text))
    return items


def style_of(word: str) -> str:
    """Classify a word's casing as ``upper``, ``title`` or ``lower``."""
    letters = [c for c in word if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 1:
        return "upper"
    if word[:1].isupper():
        return "title"
    return "lower"


def apply_style(word: str, style: str) -> str:
    """Re-case ``word`` into ``style``."""
    if style == "upper":
        return word.upper()
    if style == "title":
        return word[:1].upper() + word[1:]
    return word


def _match_rule(words: list[str], index: int, rule: Rule) -> bool | None:
    """Return whether ``rule`` matches at ``index``; ``True`` if plural.

    Args:
        words: Lowercased words of the identifier.
        index: Where to try the match.
        rule: The rule to try.

    Returns:
        ``None`` when the rule does not match, ``True`` when it matches with a
        trailing plural ``s`` on the last word, ``False`` otherwise.
    """
    size = len(rule.source)
    if index + size > len(words):
        return None
    for offset in range(size - 1):
        if words[index + offset] != rule.source[offset]:
            return None
    last = words[index + size - 1]
    tail = rule.source[-1]
    if last == tail:
        return False
    if last == tail + "s":
        return True
    return None


def rename_identifier(ident: str, step: int) -> tuple[str, tuple[Rule, ...]]:
    """Rewrite one identifier under the rules of ``step``.

    Args:
        ident: The identifier as it appears in the source.
        step: 1 or 2.

    Returns:
        ``(new_identifier, rules_applied)``. ``rules_applied`` is empty when
        nothing matched, in which case the identifier is returned unchanged.
    """
    if not TRIGGER_RE.search(ident):
        return ident, ()
    items = split_identifier(ident)
    word_positions = [i for i, (kind, _) in enumerate(items) if kind == "word"]
    words = [items[i][1] for i in word_positions]
    lowered = [w.lower() for w in words]

    out: list[str] = []
    applied: list[Rule] = []
    wi = 0
    item_cursor = 0
    while wi < len(words):
        matched = False
        for rule in ORDERED_RULES:
            if rule.step != step:
                continue
            plural = _match_rule(lowered, wi, rule)
            if plural is None:
                continue
            size = len(rule.source)
            first_item = word_positions[wi]
            last_item = word_positions[wi + size - 1]
            # Emit anything (separators) between the cursor and the match.
            out.extend(text for _, text in items[item_cursor:first_item])
            targets = list(rule.target)
            if plural:
                targets[-1] = targets[-1] + "s"
            styles = (
                [style_of(w) for w in words[wi : wi + size]]
                if len(targets) == size
                else [style_of(words[wi])] * len(targets)
            )
            styled = [apply_style(t, s) for t, s in zip(targets, styles, strict=True)]
            # Reuse the separators that sat between the matched words.
            seps = [
                "".join(
                    text
                    for _, text in items[
                        word_positions[wi + k] + 1 : word_positions[wi + k + 1]
                    ]
                )
                for k in range(size - 1)
            ]
            if len(styled) > len(seps) + 1:
                seps = seps + [seps[0] if seps else ""] * (len(styled) - len(seps) - 1)
            for k, piece in enumerate(styled):
                out.append(piece)
                if k < len(styled) - 1:
                    out.append(seps[k])
            item_cursor = last_item + 1
            wi += size
            applied.append(rule)
            matched = True
            break
        if not matched:
            wi += 1
    out.extend(text for _, text in items[item_cursor:])
    return "".join(out), tuple(applied)


# --------------------------------------------------------------------------
# Lexers: string and comment spans, used for exemptions and for the report
# --------------------------------------------------------------------------


def _python_spans(text: str) -> tuple[list[Span], list[Span], list[Span]]:
    strings: list[Span] = []
    comments: list[Span] = []
    plain: list[Span] = []
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char == "#":
            end = text.find("\n", i)
            end = n if end < 0 else end
            comments.append((i, end))
            i = end
            continue
        if char in "\"'":
            triple = text[i : i + 3]
            is_triple = triple in ('"""', "'''")
            if is_triple:
                end = text.find(triple, i + 3)
                end = n if end < 0 else end + 3
            else:
                j = i + 1
                end = n
                while j < n:
                    if text[j] == "\\":
                        j += 2
                        continue
                    if text[j] == "\n":
                        end = j
                        break
                    if text[j] == char:
                        end = j + 1
                        break
                    j += 1
                else:
                    end = n
            strings.append((i, end))
            if not is_triple:
                plain.append((i, end))
            i = end
            continue
        i += 1
    return strings, comments, plain


def _ts_spans(text: str) -> tuple[list[Span], list[Span]]:
    strings: list[Span] = []
    comments: list[Span] = []
    i, n = 0, len(text)
    while i < n:
        two = text[i : i + 2]
        if two == "//":
            end = text.find("\n", i)
            end = n if end < 0 else end
            comments.append((i, end))
            i = end
            continue
        if two == "/*":
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            comments.append((i, end))
            i = end
            continue
        char = text[i]
        if char in "\"'":
            j = i + 1
            end = n
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "\n":
                    end = j
                    break
                if text[j] == char:
                    end = j + 1
                    break
                j += 1
            strings.append((i, end))
            i = end
            continue
        if char == "`":
            start = i
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "`":
                    j += 1
                    strings.append((start, j))
                    break
                if text[j : j + 2] == "${":
                    strings.append((start, j))
                    depth = 1
                    k = j + 2
                    while k < n and depth:
                        if text[k] == "{":
                            depth += 1
                        elif text[k] == "}":
                            depth -= 1
                        k += 1
                    j = k
                    start = k
                    continue
                j += 1
            else:
                strings.append((start, n))
                j = n
            i = j
            continue
        i += 1
    return strings, comments


def _markdown_spans(text: str) -> tuple[list[Span], list[Span]]:
    """Backticked runs are code; everything else is prose (reported as comment)."""
    code: list[Span] = []
    for match in re.finditer(r"```.*?```|`[^`\n]*`", text, re.DOTALL):
        code.append((match.start(), match.end()))
    comments: list[Span] = []
    cursor = 0
    for start, end in code:
        if start > cursor:
            comments.append((cursor, start))
        cursor = end
    if cursor < len(text):
        comments.append((cursor, len(text)))
    return [], comments


def prose_spans(path: str, text: str) -> tuple[list[Span], list[Span], list[Span]]:
    """Return ``(strings, comments, plain_strings)`` for a source file.

    Args:
        path: Repo-relative path; only its suffix is used.
        text: The file contents.

    Returns:
        Three lists of half-open ``(start, end)`` character spans. ``strings``
        covers every string literal; ``plain_strings`` drops Python's
        triple-quoted ones, which are documentation rather than user copy.
    """
    if path.endswith(".py"):
        return _python_spans(text)
    if path.endswith((".ts", ".tsx", ".js", ".jsx")):
        strings, comments = _ts_spans(text)
        return strings, comments, strings
    if path.endswith(".md"):
        strings, comments = _markdown_spans(text)
        return strings, comments, strings
    return [], [], []


class SpanSet:
    """A sorted, merged set of half-open spans with O(log n) lookups."""

    def __init__(self, spans: list[Span]) -> None:
        merged: list[list[int]] = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self._spans: list[Span] = [(a, b) for a, b in merged]
        self._starts: list[int] = [a for a, _ in self._spans]

    def contains(self, pos: int, end: int) -> bool:
        """Whether ``[pos, end)`` sits wholly inside one span."""
        index = bisect_right(self._starts, pos) - 1
        return index >= 0 and self._spans[index][1] >= end

    def overlaps(self, pos: int, end: int) -> bool:
        """Whether ``[pos, end)`` touches any span."""
        index = bisect_right(self._starts, pos) - 1
        if index >= 0 and self._spans[index][1] > pos:
            return True
        nxt = index + 1
        return nxt < len(self._spans) and self._spans[nxt][0] < end

    def __bool__(self) -> bool:
        return bool(self._spans)


# --------------------------------------------------------------------------
# Declarations, for the collision check (plan D3/D4)
# --------------------------------------------------------------------------

_PY_DECL = (
    re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)", re.MULTILINE),
    re.compile(r"^[ \t]*class[ \t]+([A-Za-z_]\w*)", re.MULTILINE),
    re.compile(r"^([A-Za-z_]\w*)[ \t]*(?::[^=\n]+)?=", re.MULTILINE),
)
_PY_IMPORT_PAREN = re.compile(r"^from[ \t]+[\w.]+[ \t]+import[ \t]*\(([^)]*)\)", re.MULTILINE)
_PY_IMPORT_FLAT = re.compile(r"^from[ \t]+[\w.]+[ \t]+import[ \t]+([^\n(]+)$", re.MULTILINE)
_PY_LOCAL = re.compile(r"^[ \t]+([A-Za-z_]\w*)[ \t]*(?::[^=\n]+)?=[^=]", re.MULTILINE)
_TS_DECL = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?(?:async[ \t]+)?"
    r"(?:function|class|interface|type|enum|const|let|var)[ \t]+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)


def declared_symbols(path: str, text: str) -> set[str]:
    """Module-scope names a textual rename could silently collide with.

    Args:
        path: Repo-relative path; only its suffix is used.
        text: The file contents.

    Returns:
        The set of declared names (defs, classes, top-level bindings, imports
        for Python; the top-level declaration keywords for TypeScript).
    """
    names: set[str] = set()
    if path.endswith(".py"):
        for pattern in _PY_DECL:
            names.update(pattern.findall(text))
        bodies: list[str] = _PY_IMPORT_PAREN.findall(text) + _PY_IMPORT_FLAT.findall(text)
        for body in bodies:
            for piece in body.split(","):
                name = piece.strip().split(" as ")[-1].strip()
                if re.fullmatch(r"[A-Za-z_]\w*", name):
                    names.add(name)
    elif path.endswith((".ts", ".tsx", ".js", ".jsx")):
        names.update(_TS_DECL.findall(text))
    return names


# --------------------------------------------------------------------------
# File-set walking
# --------------------------------------------------------------------------


def is_excluded(rel: str) -> bool:
    """Whether a repo-relative path is on the always-excluded list (plan D2)."""
    parts = rel.split("/")
    if any(part in EXCLUDED_DIR_NAMES for part in parts):
        return True
    if rel in EXCLUDED_PATHS:
        return True
    if any(rel.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return True
    return rel.startswith("backend/alembic/versions/") and "038" not in Path(rel).name


# Per-checkout state, not a review artefact: gitignored.
DEFAULT_LEDGER = "scripts/.rename_038_state.json"


def file_digest(text: str) -> str:
    """SHA-256 of a file's contents, as written."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


Ledger = dict[str, tuple[str, frozenset[int]]]


def read_ledger(path: Path) -> Ledger:
    """Load the post-sweep hashes and steps recorded by an earlier ``--apply``."""
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    entries = loaded.get("swept", {})
    return {
        str(key): (str(value["sha256"]), frozenset(int(s) for s in value["steps"]))
        for key, value in entries.items()
    }


def write_ledger(path: Path, swept: Ledger) -> None:
    """Record the post-sweep hashes so a later run can skip settled files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool": "scripts/rename_038.py",
        "note": (
            "post-sweep sha256 and applied steps per file; a file whose hash still "
            "matches and whose recorded steps cover the requested ones is skipped"
        ),
        "swept": {
            rel: {"sha256": sha, "steps": sorted(steps)}
            for rel, (sha, steps) in sorted(swept.items())
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_settled(ledger: Ledger, rel: str, text: str, steps: tuple[int, ...]) -> bool:
    """Whether ``rel`` has already been swept for every requested step."""
    entry = ledger.get(rel)
    if entry is None:
        return False
    sha, done = entry
    return sha == file_digest(text) and set(steps) <= done


# A tree that has already been swept, seen from a checkout with no ledger --
# a fresh clone, or an open PR that merged the swept branch. `--apply` there
# would rename the Project entity on to `task`, which the ledger alone cannot
# stop. One cheap sentinel per phase catches it (lead ruling, 2026-09-04).
SWEPT_SENTINELS: dict[int, tuple[str, str | None]] = {
    3: ("backend/src/policy_atlas/evidence_search", None),
    4: ("frontend/src/api/queries.ts", "useTasks("),
}


def looks_already_swept(root: Path, phase: int) -> bool:
    """Whether the tree already carries this phase's post-sweep vocabulary.

    Args:
        root: Repo root.
        phase: 3 (backend) or 4 (frontend).

    Returns:
        ``True`` when the phase's sentinel is present -- the renamed package for
        the backend, the renamed hook for the frontend.
    """
    rel, needle = SWEPT_SENTINELS[phase]
    path = root / rel
    if needle is None:
        return path.is_dir()
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def phase_files(root: Path, phase: int) -> list[str]:
    """Repo-relative paths the sweep may touch for ``phase``, sorted."""
    found: set[str] = set()
    for base, suffixes in PHASE_ROOTS[phase]:
        base_path = root / base
        if not base_path.is_dir():
            continue
        for path in base_path.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            rel = path.relative_to(root).as_posix()
            if is_excluded(rel) or rel in PHASE_EXCLUDED_PATHS.get(phase, frozenset()):
                continue
            found.add(rel)
    for rel in PHASE_EXTRA_FILES[phase]:
        if (root / rel).is_file() and not is_excluded(rel):
            found.add(rel)
    return sorted(found)


# --------------------------------------------------------------------------
# Per-file planning
# --------------------------------------------------------------------------


@dataclass
class Edit:
    """One planned rewrite inside a file."""

    start: int
    end: int
    old: str
    new: str
    rule: str
    step: int
    context: str
    line: int
    bare: bool


@dataclass
class Skip:
    """One match a never-mapped entry suppressed."""

    reason: str
    old: str
    line: int


@dataclass
class FilePlan:
    """The edits, skips and unmapped identifiers found in one file."""

    path: str
    edits: list[Edit] = field(default_factory=list)
    skips: list[Skip] = field(default_factory=list)
    unmapped: Counter[str] = field(default_factory=Counter)
    residual: Counter[str] = field(default_factory=Counter)
    collisions: list[tuple[str, str, str]] = field(default_factory=list)
    converging: list[tuple[str, str]] = field(default_factory=list)
    shadowing: list[tuple[str, str]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.edits)


class LineIndex:
    """Character offset -> 1-based line number, in O(log n)."""

    def __init__(self, text: str) -> None:
        self._starts: list[int] = [0]
        for match in re.finditer("\n", text):
            self._starts.append(match.end())

    def line(self, pos: int) -> int:
        return bisect_right(self._starts, pos)


def _literal_applies(rule: LiteralRule, path: str) -> bool:
    if not rule.paths:
        return True
    return any(path == pattern or Path(path).match(pattern) for pattern in rule.paths)


def plan_file(path: str, text: str, phase: int, step: int) -> FilePlan:
    """Compute every rewrite ``step`` would make in one file.

    Args:
        path: Repo-relative path (drives suffix, exemption and literal scoping).
        text: The current file contents.
        phase: 3 (backend) or 4 (frontend); scopes :data:`NEVER_MAPPED`.
        step: 1 or 2.

    Returns:
        The plan: edits in source order, suppressed matches, unmapped
        identifiers and same-file collisions.
    """
    plan = FilePlan(path=path)
    string_list, comment_list, plain_list = prose_spans(path, text)
    strings, comments = SpanSet(string_list), SpanSet(comment_list)
    lines = LineIndex(text)
    # Prompt files hand the lead every string; copy modules hand over only the
    # plainly-quoted ones (a Python docstring is documentation, not copy).
    # Comments are always swept -- invariant I4 greps them.
    if path in PROMPT_EXEMPT:
        hand_edited = SpanSet(string_list)
    elif path in COPY_EXEMPT:
        hand_edited = SpanSet(plain_list)
    else:
        hand_edited = SpanSet([])

    reasons: list[tuple[Span, str]] = []
    for reason, pattern in NEVER_MAPPED_CONTEXTS:
        for match in pattern.finditer(text):
            reasons.append(((match.start(), match.end()), reason))
    protected = SpanSet([span for span, _ in reasons])

    # 1. Path-like string literals.
    consumed_spans: list[Span] = []
    for lit in LITERAL_RULES:
        if lit.step != step or not _literal_applies(lit, path):
            continue
        for match in lit.pattern.finditer(text):
            if protected.overlaps(match.start(), match.end()):
                continue
            groups = {key: (value or "") for key, value in match.groupdict().items()}
            new = lit.repl.format(**groups)
            if new == match.group(0):
                continue
            consumed_spans.append((match.start(), match.end()))
            plan.edits.append(
                Edit(
                    start=match.start(),
                    end=match.end(),
                    old=match.group(0),
                    new=new,
                    rule=lit.name,
                    step=step,
                    context="literal",
                    line=lines.line(match.start()),
                    bare=False,
                )
            )
    consumed = SpanSet(consumed_spans)

    # 2. Identifiers.
    never = {name for name, phases in NEVER_MAPPED.items() if phase in phases}
    for match in IDENT_RE.finditer(text):
        ident = match.group(0)
        if not SCAN_RE.search(ident):
            continue
        start, end = match.start(), match.end()
        if consumed and consumed.overlaps(start, end):
            continue
        new, applied = rename_identifier(ident, step)
        if not applied:
            if _is_watched(ident) and not _mapped_by_any_step(ident):
                plan.unmapped[ident] += 1
            continue
        line = lines.line(start)
        if ident in never:
            plan.skips.append(Skip(reason=f"never mapped: `{ident}`", old=ident, line=line))
            continue
        if protected.overlaps(start, end):
            blocking = next(r for span, r in reasons if span[0] < end and start < span[1])
            plan.skips.append(Skip(reason=blocking, old=ident, line=line))
            continue
        context = "code"
        if strings.contains(start, end):
            context = "string"
        elif comments.contains(start, end):
            context = "comment"
        if hand_edited and hand_edited.contains(start, end):
            plan.skips.append(
                Skip(reason="string literal of a hand-edited file", old=ident, line=line)
            )
            continue
        if _is_watched(new) and not _mapped_by_any_step(new):
            plan.residual[f"{ident} -> {new}"] += 1
        bare = sum(1 for kind, _ in split_identifier(ident) if kind == "word") == 1
        plan.edits.append(
            Edit(
                start=start,
                end=end,
                old=ident,
                new=new,
                rule=applied[0].name if len(applied) == 1 else " + ".join(r.name for r in applied),
                step=step,
                context=context,
                line=line,
                bare=bare,
            )
        )

    # 3. Same-file collisions (plan D3/D4).
    declared = declared_symbols(path, text)
    locals_here = set(_PY_LOCAL.findall(text)) if path.endswith(".py") else set()
    targets: dict[str, set[str]] = defaultdict(set)
    for edit in plan.edits:
        if edit.context == "literal":
            continue
        targets[edit.new].add(edit.old)
    for target, sources in sorted(targets.items()):
        if target in declared and target not in sources:
            plan.collisions.append(
                (sorted(sources)[0], target, "already declared in the same file")
            )
            continue
        # `orchestrator` and `orchestrate` both land on `agent` by design
        # (contract V4). Convergence is only a clash when two of the sources
        # are module-scope symbols of this file.
        clashing = sorted(source for source in sources if source in declared)
        if len(clashing) > 1:
            plan.collisions.append(
                (", ".join(clashing), target, "two declared symbols, one target")
            )
        elif len(sources) > 1:
            plan.converging.append((", ".join(sorted(sources)), target))
        if target in locals_here and target not in declared:
            plan.shadowing.append((sorted(targets[target])[0], target))

    plan.edits.sort(key=lambda e: e.start)
    return plan


def _is_watched(ident: str) -> bool:
    if WATCH_RE.search(ident):
        return True
    lowered = ident.lower()
    if not any(word in lowered for word in WATCH_EXACT):
        return False
    words = {word.lower() for kind, word in split_identifier(ident) if kind == "word"}
    return bool(words & WATCH_EXACT)


def _mapped_by_any_step(ident: str) -> bool:
    """Whether any step maps this identifier (so it is not left behind)."""
    return any(rename_identifier(ident, step)[1] for step in STEPS)


def apply_edits(text: str, plan: FilePlan) -> str:
    """Splice a plan's edits into the text."""
    out: list[str] = []
    cursor = 0
    for edit in plan.edits:
        out.append(text[cursor : edit.start])
        out.append(edit.new)
        cursor = edit.end
    out.append(text[cursor:])
    return "".join(out)


def sweep_text(
    path: str, text: str, phase: int, steps: tuple[int, ...]
) -> tuple[str, list[FilePlan]]:
    """Run the given steps over one file's text, in order.

    Args:
        path: Repo-relative path.
        text: The starting contents.
        phase: 3 or 4.
        steps: The steps to run, in order (``(1, 2)`` for ``--step all``).

    Returns:
        ``(new_text, plans)``, one plan per step, each computed against the
        text as it stood at the start of that step.
    """
    plans: list[FilePlan] = []
    current = text
    for step in steps:
        plan = plan_file(path, current, phase, step)
        plans.append(plan)
        if plan.collisions:
            break
        current = apply_edits(current, plan)
    return current, plans


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


@dataclass
class Report:
    """Aggregated scan results across the file set."""

    phase: int
    steps: tuple[int, ...]
    files_scanned: int = 0
    files_changed: int = 0
    files_settled: int = 0
    pairs: dict[tuple[str, str, int], Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    pair_rule: dict[tuple[str, str, int], str] = field(default_factory=dict)
    rule_counts: Counter[tuple[int, str]] = field(default_factory=Counter)
    unmapped: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    residual: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    skips: Counter[str] = field(default_factory=Counter)
    collisions: list[tuple[str, str, str, str]] = field(default_factory=list)
    converging: Counter[str] = field(default_factory=Counter)
    shadowing: list[tuple[str, str, str]] = field(default_factory=list)
    prose_titlecase: list[tuple[str, int, str, str]] = field(default_factory=list)
    prose_lower: Counter[str] = field(default_factory=Counter)


def _files_cell(counter: Counter[str], limit: int = 4) -> str:
    names = [name for name, _ in counter.most_common()]
    head = ", ".join(f"`{n}`" for n in names[:limit])
    if len(names) > limit:
        head += f" (+{len(names) - limit} more)"
    return head


def build_report(
    root: Path, phase: int, steps: tuple[int, ...], ledger: Ledger | None = None
) -> Report:
    """Scan the phase file set and aggregate every finding.

    Args:
        root: Repo root.
        phase: 3 (backend) or 4 (frontend).
        steps: Steps to run, in order.
        ledger: Post-sweep hashes from an earlier ``--apply``; a file still
            carrying its recorded hash is already swept and is skipped.

    Returns:
        The aggregated report.
    """
    settled = ledger or {}
    report = Report(phase=phase, steps=steps)
    for rel in phase_files(root, phase):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_settled(settled, rel, text, steps):
            report.files_settled += 1
            continue
        report.files_scanned += 1
        source_lines = text.splitlines()
        _, plans = sweep_text(rel, text, phase, steps)
        touched = False
        for plan in plans:
            for edit in plan.edits:
                touched = True
                key = (edit.old, edit.new, edit.step)
                report.pairs[key][rel] += 1
                report.pair_rule[key] = edit.rule
                report.rule_counts[(edit.step, edit.rule)] += 1
                if not edit.bare or edit.context == "code":
                    continue
                index = edit.line - 1
                snippet = source_lines[index].strip() if 0 <= index < len(source_lines) else ""
                if edit.old[:1].isupper():
                    report.prose_titlecase.append((rel, edit.line, edit.old, snippet[:130]))
                else:
                    report.prose_lower[rel] += 1
            for pair, count in plan.residual.items():
                report.residual[pair][rel] += count
            for skip in plan.skips:
                report.skips[skip.reason] += 1
            for source, target, why in plan.collisions:
                report.collisions.append((rel, source, target, why))
            for sources, target in plan.converging:
                report.converging[f"{sources} -> {target}"] += 1
            for source, target in plan.shadowing:
                report.shadowing.append((rel, source, target))
        # Unmapped is read off the final step: it is the end state that matters.
        for ident, count in plans[-1].unmapped.items():
            report.unmapped[ident][rel] += count
        if touched:
            report.files_changed += 1
    return report


def render_report(report: Report, max_rows: int) -> str:
    """Render the scan report as markdown."""
    label = {3: "backend", 4: "frontend"}.get(report.phase, str(report.phase))
    steps = "all" if report.steps == STEPS else ",".join(str(s) for s in report.steps)
    out: list[str] = []
    out.append(f"# Task 038 sweep scan — phase {report.phase} ({label})")
    out.append("")
    out.append(
        f"Generated by `scripts/rename_038.py --scan --phase {report.phase} --step {steps}`. "
        "Read with plan § D1–D4: the identifier table below is the reviewed input to "
        "`--apply`; nothing outside it is rewritten."
    )
    out.append("")
    out.append(f"- Files in the set: **{report.files_scanned}**")
    if report.files_settled:
        out.append(f"- Files already swept (ledger): **{report.files_settled}**")
    out.append(f"- Files the sweep would change: **{report.files_changed}**")
    total = sum(report.rule_counts.values())
    out.append(f"- Replacements: **{total}**")
    out.append(f"- Distinct identifier renames: **{len(report.pairs)}**")
    out.append(f"- Collisions: **{len(report.collisions)}**")
    out.append("")

    out.append("## Replacements per rule")
    out.append("")
    out.append("| step | rule | replacements |")
    out.append("|---|---|---|")
    for key, count in sorted(report.rule_counts.items(), key=lambda kv: (kv[0][0], -kv[1])):
        out.append(f"| {key[0]} | `{key[1]}` | {count} |")
    out.append("")

    out.append("## Identifier table")
    out.append("")
    out.append("| identifier | proposed target | step | occurrences | files |")
    out.append("|---|---|---|---|---|")
    rows = sorted(
        report.pairs.items(),
        key=lambda kv: (kv[0][2], -sum(kv[1].values()), kv[0][0]),
    )
    for (old, new, step), files in rows[:max_rows]:
        out.append(f"| `{old}` | `{new}` | {step} | {sum(files.values())} | {_files_cell(files)} |")
    if len(rows) > max_rows:
        omitted = len(rows) - max_rows
        out.append(f"| … | … | | | _{omitted} further rows omitted (raise `--max-rows`)_ |")
    out.append("")

    out.append("## Unmapped identifiers — lead decision (plan D1)")
    out.append("")
    if not report.unmapped:
        out.append("None.")
    else:
        out.append("Identifiers carrying a watched token that no rule maps.")
        out.append("")
        out.append("| identifier | occurrences | files |")
        out.append("|---|---|---|")
        for ident, files in sorted(
            report.unmapped.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])
        ):
            out.append(f"| `{ident}` | {sum(files.values())} | {_files_cell(files)} |")
    out.append("")

    out.append("## Residual tokens after rename — lead decision")
    out.append("")
    if not report.residual:
        out.append("None.")
    else:
        out.append(
            "Renames whose result still carries a watched token "
            "(`orchestr`/`project`/`portfolio`/`oplan`/`pss`)."
        )
        out.append("")
        out.append("| rename | occurrences | files |")
        out.append("|---|---|---|")
        for pair, files in sorted(
            report.residual.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])
        ):
            out.append(f"| `{pair}` | {sum(files.values())} | {_files_cell(files)} |")
    out.append("")

    out.append("## Collisions")
    out.append("")
    if not report.collisions:
        out.append(
            "**None.** No proposed target already exists as a declared symbol in the same file."
        )
    else:
        out.append("| file | identifier | target | why |")
        out.append("|---|---|---|---|")
        for rel, source, target, why in report.collisions:
            out.append(f"| `{rel}` | `{source}` | `{target}` | {why} |")
    out.append("")
    out.append("### Shadowing watch (advisory, not blocking)")
    out.append("")
    out.append(
        "The target is bound by an indented Python assignment somewhere in the file. "
        "Module scope is unaffected; `mypy`/`ruff` catch a real shadow at the gate."
    )
    out.append("")
    if not report.shadowing:
        out.append("None.")
    else:
        out.append("| file | identifier | target |")
        out.append("|---|---|---|")
        for rel, source, target in report.shadowing:
            out.append(f"| `{rel}` | `{source}` | `{target}` |")
    out.append("")
    out.append("### Converging renames (by design, not collisions)")
    out.append("")
    if not report.converging:
        out.append("None.")
    else:
        out.append("| sources -> target | files |")
        out.append("|---|---|")
        for pair, count in report.converging.most_common():
            out.append(f"| `{pair}` | {count} |")
    out.append("")

    out.append("## Never-mapped hits (suppressed)")
    out.append("")
    out.append("| exclusion | suppressed matches |")
    out.append("|---|---|")
    for reason, count in report.skips.most_common():
        out.append(f"| {reason} | {count} |")
    if not report.skips:
        out.append("| _none_ | 0 |")
    out.append("")

    out.append("## Prose-context review")
    out.append("")
    out.append(
        "Single-word matches (`project`, `Project`, `portfolio`, `orchestrator`, …) that fall "
        "inside a docstring, string literal or comment. Compound identifiers are omitted — they "
        "cannot be prose. In this repo a backend docstring's `project` is the *code word* and "
        "renaming it is correct; the risk is the English noun or verb."
    )
    out.append("")
    out.append(f"### Title-case `Project`/`Portfolio`/… in prose ({len(report.prose_titlecase)})")
    out.append("")
    out.append(
        "The ambiguous set: `project_id: Project owning the run` is the code word and must "
        "change, `\"\"\"Project a row onto the wire shape\"\"\"` is the English verb and must not."
    )
    out.append("")
    if not report.prose_titlecase:
        out.append("None.")
    else:
        out.append("| file:line | token | line |")
        out.append("|---|---|---|")
        for rel, line, token, snippet in report.prose_titlecase[:max_rows]:
            clean = snippet.replace("|", "\\|")
            out.append(f"| `{rel}:{line}` | `{token}` | `{clean}` |")
        if len(report.prose_titlecase) > max_rows:
            out.append(f"| … | | _{len(report.prose_titlecase) - max_rows} more_ |")
    out.append("")
    out.append(f"### Lower-case bare tokens in prose ({sum(report.prose_lower.values())}, by file)")
    out.append("")
    if not report.prose_lower:
        out.append("None.")
    else:
        out.append("| file | bare single-word matches in prose |")
        out.append("|---|---|")
        for rel, count in report.prose_lower.most_common(max_rows):
            out.append(f"| `{rel}` | {count} |")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def run_scan(
    root: Path,
    phase: int,
    steps: tuple[int, ...],
    out: Path | None,
    max_rows: int,
    ledger: Ledger,
) -> int:
    """Emit the scan report. Returns a non-zero exit code on any collision."""
    report = build_report(root, phase, steps, ledger)
    text = render_report(report, max_rows)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    if report.collisions:
        print(
            f"COLLISIONS: {len(report.collisions)} — refusing to bless this table",
            file=sys.stderr,
        )
        return 1
    return 0


def run_apply(
    root: Path,
    phase: int,
    steps: tuple[int, ...],
    ledger_path: Path,
    ledger: Ledger,
    force: bool = False,
) -> int:
    """Rewrite the phase file set.

    Refuses while any collision remains, and refuses to sweep a tree that is
    already swept but carries no ledger (a fresh clone, or a branch that merged
    the renamed one). Rebase by running the sweep on the pre-038 branch.

    Args:
        root: Repo root.
        phase: 3 (backend) or 4 (frontend).
        steps: Steps to run, in order.
        ledger_path: Where to read and write the post-sweep hashes.
        ledger: The hashes already recorded.
        force: Sweep anyway, past the already-swept guard.

    Returns:
        0 on success, 2 on a refusal.
    """
    if not force and not ledger and looks_already_swept(root, phase):
        sentinel, needle = SWEPT_SENTINELS[phase]
        carries = f"{sentinel} contains {needle!r}" if needle else f"{sentinel} exists"
        print(
            f"refusing to apply: this tree already looks swept for phase {phase} "
            f"({carries}) but has no ledger at {ledger_path}.\n"
            "Sweeping it again would rename the Project entity on to `task`. "
            "Run the sweep on the pre-038 branch, or pass --force if you are sure.",
            file=sys.stderr,
        )
        return 2

    report = build_report(root, phase, steps, ledger)
    if report.collisions:
        for rel, source, target, why in report.collisions:
            print(f"collision: {rel}: {source} -> {target} ({why})", file=sys.stderr)
        print("refusing to apply while collisions remain", file=sys.stderr)
        return 2

    per_rule: Counter[tuple[int, str]] = Counter()
    swept: Ledger = dict(ledger)
    changed: list[str] = []
    reswept: list[str] = []
    settled = 0
    for rel in phase_files(root, phase):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_settled(ledger, rel, text, steps):
            settled += 1
            continue
        new_text, plans = sweep_text(rel, text, phase, steps)
        if new_text == text:
            continue
        for plan in plans:
            for edit in plan.edits:
                per_rule[(edit.step, edit.rule)] += 1
        path.write_text(new_text, encoding="utf-8")
        done = ledger[rel][1] if rel in ledger else frozenset()
        swept[rel] = (file_digest(new_text), done | set(steps))
        changed.append(rel)
        if rel in ledger and ledger[rel][0] != file_digest(text):
            reswept.append(rel)

    if changed:
        write_ledger(ledger_path, swept)
    print(f"files changed: {len(changed)}")
    print(f"files already swept (skipped): {settled}")
    print(f"replacements: {sum(per_rule.values())}")
    for (step, rule), count in sorted(per_rule.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print(f"  step {step}  {rule}: {count}")
    if reswept:
        print(f"re-swept after changing since the last run ({len(reswept)}) — review these diffs:")
        for rel in reswept:
            print(f"  {rel}")
    if not changed:
        print("nothing to do — every file in the set is already swept")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scan", action="store_true", help="emit the reviewable identifier table")
    mode.add_argument("--apply", action="store_true", help="rewrite the files")
    parser.add_argument("--phase", type=int, choices=(3, 4), required=True, help="D2 file set")
    parser.add_argument(
        "--step", choices=("1", "2", "all"), default="all", help="rule step (default: all)"
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="repo root (default: this script's repo)"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write the scan report here instead of stdout"
    )
    parser.add_argument("--max-rows", type=int, default=400, help="cap on rows per report table")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help=f"post-sweep hash ledger (default: <root>/{DEFAULT_LEDGER})",
    )
    parser.add_argument(
        "--ignore-ledger",
        action="store_true",
        help="scan or sweep every file, even ones the ledger calls settled",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="sweep past the already-swept guard (no ledger on a renamed tree)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    root = args.root if args.root is not None else Path(__file__).resolve().parent.parent
    steps: tuple[int, ...] = STEPS if args.step == "all" else (int(args.step),)
    ledger_path: Path = args.ledger if args.ledger is not None else root / DEFAULT_LEDGER
    ledger: Ledger = {} if args.ignore_ledger else read_ledger(ledger_path)
    if args.scan:
        return run_scan(root, args.phase, steps, args.out, args.max_rows, ledger)
    return run_apply(root, args.phase, steps, ledger_path, ledger, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
