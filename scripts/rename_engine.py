#!/usr/bin/env python3
"""Table-driven identifier rename engine, shared by the vocabulary sweeps.

Task 038 built a reviewed rename tool (``scripts/rename_038.py``) whose rule
tables lived in module constants read from every hot path. Task 044 needs the
same machinery with a different table, so the machinery moved here and the
tables became an argument: :class:`RenameTables` carries the rules, the literal
rewrites, the never-mapped sets, the file sets and the exclusions, and
:class:`Engine` does the work.

What the engine does, unchanged from 038:

1. **Identifiers.** Every word-bounded ``[A-Za-z_][A-Za-z0-9_]*`` run is split
   into words (snake and camel), matched against the ordered rule table
   (compound before bare) and rebuilt with the original casing and separators.
2. **Literal rewrites.** The shapes the identifier pass cannot see -- hyphenated
   route segments, table strings, prose phrases, abbreviations -- are listed as
   :class:`LiteralRule` entries and scoped to files, phases and span kinds.
3. **Exclusions.** Exact identifiers (optionally phase-scoped), text contexts
   (prose spans a rename must not touch) and whole files.
4. **Safety.** A same-file collision check (renaming onto an already-declared
   symbol) refuses ``--apply``; a per-file ledger of post-sweep hashes makes
   ``--apply`` idempotent; a per-phase sentinel refuses an already-swept tree
   that carries no ledger.

Modes are ``--scan`` (emit the reviewable markdown report; non-zero exit on any
collision) and ``--apply`` (rewrite the files). Neither ``git mv``s anything:
module and package moves are done by hand, and the sweep rewrites the import
paths so the moved modules resolve.

This module is a library. The runnable tools are ``scripts/rename_038.py`` and
``scripts/rename_044.py``, each of which is a table plus a thin CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

Span = tuple[int, int]

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
WORD_RE = re.compile(r"_+|[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")
MARKDOWN_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One token->target rule.

    Attributes:
        step: Which step the rule belongs to; steps run in order.
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


@dataclass(frozen=True)
class LiteralRule:
    """A literal rewrite scoped to named files, phases and span kinds.

    Attributes:
        step: The step the rule belongs to.
        name: Reported as the rule name.
        pattern: What to match. Named groups interpolate into ``repl``.
        repl: Replacement template; ``{group}`` interpolates a named group.
        paths: Repo-relative paths (or ``*``-globs) the rule applies to; empty
            means every file in the set.
        phases: Phases the rule applies to; ``None`` means every phase.
        where: ``"any"`` (the whole file) or ``"prose"`` (outside the markdown
            code spans; unrestricted for non-markdown files).
    """

    step: int
    name: str
    pattern: re.Pattern[str]
    repl: str
    paths: tuple[str, ...] = ()
    phases: frozenset[int] | None = None
    where: str = "any"


@dataclass
class RenameTables:
    """Everything one sweep's rule table has to say.

    Attributes:
        tool: Repo-relative path of the calling script, for the report and the
            ledger note.
        title: Report heading, e.g. ``"Task 038 sweep scan"``.
        rules: The identifier rules, in any order (the engine orders them
            longest word sequence first, so compound beats bare).
        literal_rules: The literal rewrites.
        steps: The steps, in the order ``--step all`` runs them.
        never_mapped: Exact identifiers that no rule may rewrite, each mapped to
            the phases the exclusion covers.
        never_mapped_contexts: ``(reason, pattern)`` text spans that suppress
            any identifier match overlapping them.
        phase_roots: Per phase, the ``(directory, suffixes)`` pairs to walk.
        phase_extra_files: Per phase, extra repo-relative files to include.
        excluded_dir_names: Directory names never walked into.
        excluded_path_prefixes: Repo-relative prefixes never swept.
        excluded_paths: Exact repo-relative paths never swept.
        always_included_paths: Exact paths that beat every exclusion above.
        phase_excluded_paths: Per phase, extra exact paths to skip.
        string_exempt_all: Files whose every string literal is hand-edited.
        string_exempt_plain: Files whose plainly-quoted strings are hand-edited
            (a Python docstring is documentation, so it is still swept).
        extra_exclude: Optional predicate for any remaining exclusion rule.
        watch_re: Identifiers matching this and mapped by no rule are reported
            as unmapped, for a lead decision.
        watch_exact: Whole words with the same effect (for short infixes that
            would match too much as a substring).
        trigger_re: Cheap pre-filter: an identifier without a hit here cannot
            match any rule.
        scan_re: Cheap pre-filter for the scan, admitting the watched tokens.
        swept_sentinels: Per phase, ``(path, needle)``; the tree already looks
            swept when the path exists (``needle`` ``None``) or contains the
            needle.
        ledger: Repo-relative default ledger path (gitignored).
        phase_labels: Human labels for the phases, for the report heading.
        phase_identifier_suffixes: Per phase, the suffixes the identifier pass
            runs over; a phase absent from the mapping gets every suffix.
        phase_code_span_only_suffixes: Per phase, the suffixes whose identifier
            pass is confined to markdown code spans.
        suppress_unmapped_in_contexts: Whether an unmapped identifier sitting
            inside a never-mapped context is left out of the report.
        watch_label: How the report describes the watched tokens.
        report_intro: A sentence under the report heading.
    """

    tool: str
    title: str
    rules: tuple[Rule, ...]
    literal_rules: tuple[LiteralRule, ...]
    steps: tuple[int, ...]
    never_mapped: dict[str, frozenset[int]]
    never_mapped_contexts: tuple[tuple[str, re.Pattern[str]], ...]
    phase_roots: dict[int, tuple[tuple[str, tuple[str, ...]], ...]]
    phase_extra_files: dict[int, tuple[str, ...]]
    excluded_dir_names: frozenset[str]
    excluded_path_prefixes: tuple[str, ...]
    excluded_paths: frozenset[str]
    phase_excluded_paths: dict[int, frozenset[str]]
    watch_re: re.Pattern[str]
    watch_exact: frozenset[str]
    trigger_re: re.Pattern[str]
    scan_re: re.Pattern[str]
    swept_sentinels: dict[int, tuple[str, str | None]]
    ledger: str
    phase_labels: dict[int, str]
    always_included_paths: frozenset[str] = frozenset()
    string_exempt_all: frozenset[str] = frozenset()
    string_exempt_plain: frozenset[str] = frozenset()
    extra_exclude: Callable[[str], bool] | None = None
    phase_identifier_suffixes: dict[int, tuple[str, ...]] = field(default_factory=dict)
    phase_code_span_only_suffixes: dict[int, tuple[str, ...]] = field(default_factory=dict)
    suppress_unmapped_in_contexts: bool = False
    watch_label: str = "watched"
    report_intro: str = ""

    @property
    def phases(self) -> tuple[int, ...]:
        """Every phase the tables define, sorted."""
        return tuple(sorted(set(self.phase_roots) | set(self.phase_extra_files)))


# --------------------------------------------------------------------------
# Identifier engine (table-free helpers)
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


def infer_separator(items: list[tuple[str, str]], word_count: int, base_style: str) -> str:
    """Guess the separator an expanding rule should insert.

    A rule whose target has more words than its source (``planner`` ->
    ``task_agent``) has no separator of its own to reuse when the source is a
    single word. The identifier's own shape decides: an identifier that already
    uses underscores keeps using them, a camel or Pascal identifier joins with
    nothing, and a lone word falls back to snake case unless it is Pascal.

    Args:
        items: The split identifier.
        word_count: How many words the identifier has.
        base_style: The casing of the matched source word.

    Returns:
        The separator text to insert between the expanded target words.
    """
    # A leading or trailing `_` says nothing about how the words are joined;
    # only a separator *between* two words does (`_ModerateStubPlanner`).
    positions = [i for i, (kind, _) in enumerate(items) if kind == "word"]
    if len(positions) > 1:
        for index in range(positions[0] + 1, positions[-1]):
            if items[index][0] == "sep":
                return items[index][1]
    if word_count > 1:
        return ""
    return "" if base_style == "title" else "_"


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


def markdown_code_spans(text: str) -> list[Span]:
    """The backticked runs of a markdown file: fenced blocks and code spans."""
    return [(match.start(), match.end()) for match in MARKDOWN_CODE_RE.finditer(text)]


def _markdown_spans(text: str) -> tuple[list[Span], list[Span]]:
    """Backticked runs are code; everything else is prose (reported as comment)."""
    comments: list[Span] = []
    cursor = 0
    for start, end in markdown_code_spans(text):
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
# Declarations, for the collision check
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
# Ledger
# --------------------------------------------------------------------------

Ledger = dict[str, tuple[str, frozenset[int]]]


def file_digest(text: str) -> str:
    """SHA-256 of a file's contents, as written."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def write_ledger(path: Path, swept: Ledger, tool: str) -> None:
    """Record the post-sweep hashes so a later run can skip settled files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool": tool,
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


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


class Engine:
    """A sweep: one :class:`RenameTables` plus the machinery that runs it."""

    def __init__(self, tables: RenameTables) -> None:
        self.tables = tables
        # Longest word sequence first so `project_source_snapshot` beats `project`.
        self.ordered_rules: tuple[Rule, ...] = tuple(
            sorted(tables.rules, key=lambda r: -len(r.source))
        )
        self._memo: dict[tuple[str, int], tuple[str, tuple[Rule, ...]]] = {}

    # -- identifiers -------------------------------------------------------

    def rename_identifier(self, ident: str, step: int) -> tuple[str, tuple[Rule, ...]]:
        """Rewrite one identifier under the rules of ``step``.

        Args:
            ident: The identifier as it appears in the source.
            step: One of the table's steps.

        Returns:
            ``(new_identifier, rules_applied)``. ``rules_applied`` is empty when
            nothing matched, in which case the identifier is returned unchanged.
        """
        cached = self._memo.get((ident, step))
        if cached is not None:
            return cached
        result = self._rename_identifier(ident, step)
        self._memo[(ident, step)] = result
        return result

    def _rename_identifier(self, ident: str, step: int) -> tuple[str, tuple[Rule, ...]]:
        if not self.tables.trigger_re.search(ident):
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
            for rule in self.ordered_rules:
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
                base_style = style_of(words[wi])
                if len(targets) > len(seps) + 1:
                    filler = (
                        seps[0]
                        if seps
                        else infer_separator(items, len(words), base_style)
                    )
                    seps = seps + [filler] * (len(targets) - len(seps) - 1)
                if len(targets) == size:
                    styles = [style_of(w) for w in words[wi : wi + size]]
                else:
                    joiner = seps[0] if seps else ""
                    extra = "title" if (base_style == "lower" and joiner == "") else base_style
                    styles = [base_style] + [extra] * (len(targets) - 1)
                styled = [apply_style(t, s) for t, s in zip(targets, styles, strict=True)]
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

    def is_watched(self, ident: str) -> bool:
        """Whether an unmapped identifier is one the lead must rule on."""
        if self.tables.watch_re.search(ident):
            return True
        lowered = ident.lower()
        if not any(word in lowered for word in self.tables.watch_exact):
            return False
        words = {word.lower() for kind, word in split_identifier(ident) if kind == "word"}
        return bool(words & self.tables.watch_exact)

    def mapped_by_any_step(self, ident: str) -> bool:
        """Whether any step maps this identifier (so it is not left behind)."""
        return any(self.rename_identifier(ident, step)[1] for step in self.tables.steps)

    # -- file sets ---------------------------------------------------------

    def is_excluded(self, rel: str) -> bool:
        """Whether a repo-relative path is on the always-excluded list."""
        tables = self.tables
        if rel in tables.always_included_paths:
            return False
        parts = rel.split("/")
        if any(part in tables.excluded_dir_names for part in parts):
            return True
        if rel in tables.excluded_paths:
            return True
        if any(rel.startswith(prefix) for prefix in tables.excluded_path_prefixes):
            return True
        return bool(tables.extra_exclude and tables.extra_exclude(rel))

    def phase_files(self, root: Path, phase: int) -> list[str]:
        """Repo-relative paths the sweep may touch for ``phase``, sorted."""
        tables = self.tables
        found: set[str] = set()
        excluded_here = tables.phase_excluded_paths.get(phase, frozenset())
        for base, suffixes in tables.phase_roots.get(phase, ()):
            base_path = root / base
            if not base_path.is_dir():
                continue
            for path in base_path.rglob("*"):
                if not path.is_file() or path.suffix not in suffixes:
                    continue
                rel = path.relative_to(root).as_posix()
                if self.is_excluded(rel) or rel in excluded_here:
                    continue
                found.add(rel)
        for rel in tables.phase_extra_files.get(phase, ()):
            if (root / rel).is_file() and not self.is_excluded(rel) and rel not in excluded_here:
                found.add(rel)
        return sorted(found)

    def looks_already_swept(self, root: Path, phase: int) -> bool:
        """Whether the tree already carries this phase's post-sweep vocabulary.

        Args:
            root: Repo root.
            phase: The phase to check.

        Returns:
            ``True`` when the phase's sentinel is present.
        """
        rel, needle = self.tables.swept_sentinels[phase]
        path = root / rel
        if needle is None:
            return path.exists()
        if not path.is_file():
            return False
        try:
            return needle in path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False

    # -- planning ----------------------------------------------------------

    def _literal_applies(self, rule: LiteralRule, path: str, phase: int) -> bool:
        if rule.phases is not None and phase not in rule.phases:
            return False
        if not rule.paths:
            return True
        return any(path == pattern or Path(path).match(pattern) for pattern in rule.paths)

    def plan_file(self, path: str, text: str, phase: int, step: int) -> FilePlan:
        """Compute every rewrite ``step`` would make in one file.

        Args:
            path: Repo-relative path (drives suffix, exemption and scoping).
            text: The current file contents.
            phase: The phase; scopes never-mapped entries and file rules.
            step: The step to plan.

        Returns:
            The plan: edits in source order, suppressed matches, unmapped
            identifiers and same-file collisions.
        """
        tables = self.tables
        plan = FilePlan(path=path)
        string_list, comment_list, plain_list = prose_spans(path, text)
        strings, comments = SpanSet(string_list), SpanSet(comment_list)
        lines = LineIndex(text)
        if path in tables.string_exempt_all:
            hand_edited = SpanSet(string_list)
        elif path in tables.string_exempt_plain:
            hand_edited = SpanSet(plain_list)
        else:
            hand_edited = SpanSet([])

        code = SpanSet(markdown_code_spans(text) if path.endswith(".md") else [])
        code_only_suffixes = tables.phase_code_span_only_suffixes.get(phase, ())
        code_only = bool(code_only_suffixes) and path.endswith(code_only_suffixes)
        identifier_suffixes = tables.phase_identifier_suffixes.get(phase)
        identifiers_here = identifier_suffixes is None or path.endswith(identifier_suffixes)

        reasons: list[tuple[Span, str]] = []
        for reason, pattern in tables.never_mapped_contexts:
            for match in pattern.finditer(text):
                reasons.append(((match.start(), match.end()), reason))
        protected = SpanSet([span for span, _ in reasons])

        # 1. Literal rewrites.
        consumed_spans: list[Span] = []
        for lit in tables.literal_rules:
            if lit.step != step or not self._literal_applies(lit, path, phase):
                continue
            for match in lit.pattern.finditer(text):
                if protected.overlaps(match.start(), match.end()):
                    continue
                if lit.where == "prose" and code.overlaps(match.start(), match.end()):
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
        never = {name for name, phases in tables.never_mapped.items() if phase in phases}
        if identifiers_here:
            for match in IDENT_RE.finditer(text):
                ident = match.group(0)
                if not tables.scan_re.search(ident):
                    continue
                start, end = match.start(), match.end()
                if consumed and consumed.overlaps(start, end):
                    continue
                if code_only and not code.contains(start, end):
                    continue
                new, applied = self.rename_identifier(ident, step)
                if not applied:
                    if (
                        self.is_watched(ident)
                        and not self.mapped_by_any_step(ident)
                        and not (
                            tables.suppress_unmapped_in_contexts
                            and protected.overlaps(start, end)
                        )
                    ):
                        plan.unmapped[ident] += 1
                    continue
                line = lines.line(start)
                if ident in never:
                    plan.skips.append(
                        Skip(reason=f"never mapped: `{ident}`", old=ident, line=line)
                    )
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
                if self.is_watched(new) and not self.mapped_by_any_step(new):
                    plan.residual[f"{ident} -> {new}"] += 1
                bare = sum(1 for kind, _ in split_identifier(ident) if kind == "word") == 1
                plan.edits.append(
                    Edit(
                        start=start,
                        end=end,
                        old=ident,
                        new=new,
                        rule=(
                            applied[0].name
                            if len(applied) == 1
                            else " + ".join(r.name for r in applied)
                        ),
                        step=step,
                        context=context,
                        line=line,
                        bare=bare,
                    )
                )

        # 3. Same-file collisions.
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
            # Two source words landing on one target is by design; it is only a
            # clash when two of the sources are module-scope symbols here.
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

    def sweep_text(
        self, path: str, text: str, phase: int, steps: tuple[int, ...]
    ) -> tuple[str, list[FilePlan]]:
        """Run the given steps over one file's text, in order.

        Args:
            path: Repo-relative path.
            text: The starting contents.
            phase: The phase.
            steps: The steps to run, in order.

        Returns:
            ``(new_text, plans)``, one plan per step, each computed against the
            text as it stood at the start of that step.
        """
        plans: list[FilePlan] = []
        current = text
        for step in steps:
            plan = self.plan_file(path, current, phase, step)
            plans.append(plan)
            if plan.collisions:
                break
            current = apply_edits(current, plan)
        return current, plans

    # -- report ------------------------------------------------------------

    def build_report(
        self, root: Path, phase: int, steps: tuple[int, ...], ledger: Ledger | None = None
    ) -> Report:
        """Scan the phase file set and aggregate every finding.

        Args:
            root: Repo root.
            phase: The phase to scan.
            steps: Steps to run, in order.
            ledger: Post-sweep hashes from an earlier ``--apply``; a file still
                carrying its recorded hash is already swept and is skipped.

        Returns:
            The aggregated report.
        """
        settled = ledger or {}
        report = Report(phase=phase, steps=steps)
        for rel in self.phase_files(root, phase):
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
            _, plans = self.sweep_text(rel, text, phase, steps)
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
            # Unmapped is read off the final step: the end state is what matters.
            for ident, count in plans[-1].unmapped.items():
                report.unmapped[ident][rel] += count
            if touched:
                report.files_changed += 1
        return report

    def render_report(self, report: Report, max_rows: int) -> str:
        """Render the scan report as markdown."""
        tables = self.tables
        label = tables.phase_labels.get(report.phase, str(report.phase))
        steps = (
            "all"
            if tuple(report.steps) == tuple(tables.steps)
            else ",".join(str(s) for s in report.steps)
        )
        out: list[str] = []
        out.append(f"# {tables.title} — phase {report.phase} ({label})")
        out.append("")
        intro = (
            f"Generated by `{tables.tool} --scan --phase {report.phase} --step {steps}`. "
            + tables.report_intro
        )
        out.append(intro.strip())
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
            out.append(
                f"| `{old}` | `{new}` | {step} | {sum(files.values())} | {_files_cell(files)} |"
            )
        if len(rows) > max_rows:
            omitted = len(rows) - max_rows
            out.append(f"| … | … | | | _{omitted} further rows omitted (raise `--max-rows`)_ |")
        out.append("")

        out.append("## Unmapped identifiers — lead decision")
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
                f"Renames whose result still carries a watched token ({tables.watch_label})."
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
            "Single-word matches that fall inside a docstring, string literal or comment. "
            "Compound identifiers are omitted — they cannot be prose."
        )
        out.append("")
        out.append(f"### Title-case bare tokens in prose ({len(report.prose_titlecase)})")
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
        out.append(
            f"### Lower-case bare tokens in prose ({sum(report.prose_lower.values())}, by file)"
        )
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

    # -- modes -------------------------------------------------------------

    def run_scan(
        self,
        root: Path,
        phase: int,
        steps: tuple[int, ...],
        out: Path | None,
        max_rows: int,
        ledger: Ledger,
    ) -> int:
        """Emit the scan report. Returns a non-zero exit code on any collision."""
        report = self.build_report(root, phase, steps, ledger)
        text = self.render_report(report, max_rows)
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
        self,
        root: Path,
        phase: int,
        steps: tuple[int, ...],
        ledger_path: Path,
        ledger: Ledger,
        force: bool = False,
    ) -> int:
        """Rewrite the phase file set.

        Refuses while any collision remains, and refuses to sweep a tree that is
        already swept but carries no ledger (a fresh clone, or a branch that
        merged the renamed one).

        Args:
            root: Repo root.
            phase: The phase to sweep.
            steps: Steps to run, in order.
            ledger_path: Where to read and write the post-sweep hashes.
            ledger: The hashes already recorded.
            force: Sweep anyway, past the already-swept guard.

        Returns:
            0 on success, 2 on a refusal.
        """
        if not force and not ledger and self.looks_already_swept(root, phase):
            sentinel, needle = self.tables.swept_sentinels[phase]
            carries = f"{sentinel} contains {needle!r}" if needle else f"{sentinel} exists"
            print(
                f"refusing to apply: this tree already looks swept for phase {phase} "
                f"({carries}) but has no ledger at {ledger_path}.\n"
                "Sweeping it again would rename settled vocabulary a second time. "
                "Run the sweep on the pre-rename branch, or pass --force if you are sure.",
                file=sys.stderr,
            )
            return 2

        report = self.build_report(root, phase, steps, ledger)
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
        for rel in self.phase_files(root, phase):
            path = root / rel
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if is_settled(ledger, rel, text, steps):
                settled += 1
                continue
            new_text, plans = self.sweep_text(rel, text, phase, steps)
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
            write_ledger(ledger_path, swept, self.tables.tool)
        print(f"files changed: {len(changed)}")
        print(f"files already swept (skipped): {settled}")
        print(f"replacements: {sum(per_rule.values())}")
        for (step, rule), count in sorted(per_rule.items(), key=lambda kv: (kv[0][0], -kv[1])):
            print(f"  step {step}  {rule}: {count}")
        if reswept:
            print(
                f"re-swept after changing since the last run ({len(reswept)}) — "
                "review these diffs:"
            )
            for rel in reswept:
                print(f"  {rel}")
        if not changed:
            print("nothing to do — every file in the set is already swept")
        return 0

    # -- CLI ---------------------------------------------------------------

    def build_parser(self, doc: str) -> argparse.ArgumentParser:
        """Build the shared command line for one sweep tool."""
        tables = self.tables
        parser = argparse.ArgumentParser(
            description=doc, formatter_class=argparse.RawDescriptionHelpFormatter
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--scan", action="store_true", help="emit the reviewable identifier table"
        )
        mode.add_argument("--apply", action="store_true", help="rewrite the files")
        parser.add_argument(
            "--phase", type=int, choices=tables.phases, required=True, help="file set"
        )
        step_choices = tuple(str(s) for s in tables.steps) + ("all",)
        parser.add_argument(
            "--step", choices=step_choices, default="all", help="rule step (default: all)"
        )
        parser.add_argument(
            "--root", type=Path, default=None, help="repo root (default: this script's repo)"
        )
        parser.add_argument(
            "--out", type=Path, default=None, help="write the scan report here instead of stdout"
        )
        parser.add_argument(
            "--max-rows", type=int, default=400, help="cap on rows per report table"
        )
        parser.add_argument(
            "--ledger",
            type=Path,
            default=None,
            help=f"post-sweep hash ledger (default: <root>/{tables.ledger})",
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
        return parser

    def run(self, args: argparse.Namespace, default_root: Path) -> int:
        """Dispatch a parsed command line to ``--scan`` or ``--apply``."""
        root = args.root if args.root is not None else default_root
        steps: tuple[int, ...] = (
            self.tables.steps if args.step == "all" else (int(args.step),)
        )
        ledger_path: Path = (
            args.ledger if args.ledger is not None else root / self.tables.ledger
        )
        ledger: Ledger = {} if args.ignore_ledger else read_ledger(ledger_path)
        if args.scan:
            return self.run_scan(root, args.phase, steps, args.out, args.max_rows, ledger)
        return self.run_apply(root, args.phase, steps, ledger_path, ledger, args.force)
