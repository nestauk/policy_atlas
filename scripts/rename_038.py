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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rename_engine import (  # noqa: E402
    Edit,
    Engine,
    FilePlan,
    Ledger,
    LineIndex,
    LiteralRule,
    RenameTables,
    Report,
    Rule,
    Skip,
    SpanSet,
    apply_edits,
    apply_style,
    declared_symbols,
    file_digest,
    is_settled,
    prose_spans,
    read_ledger,
    split_identifier,
    style_of,
    write_ledger,
)

__all__ = [
    "Edit",
    "Engine",
    "FilePlan",
    "Ledger",
    "LineIndex",
    "LiteralRule",
    "RenameTables",
    "Report",
    "Rule",
    "Skip",
    "SpanSet",
    "apply_edits",
    "apply_style",
    "declared_symbols",
    "file_digest",
    "is_settled",
    "prose_spans",
    "read_ledger",
    "split_identifier",
    "style_of",
    "write_ledger",
]

# --------------------------------------------------------------------------
# The rule table (plan D1). Order matters: compound before bare.
# --------------------------------------------------------------------------

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
ORDERED_RULES: tuple[Rule, ...] = tuple(sorted(RULES, key=lambda r: -len(r.source)))

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

# Per-checkout state, not a review artefact: gitignored.
DEFAULT_LEDGER = "scripts/.rename_038_state.json"

# A tree that has already been swept, seen from a checkout with no ledger --
# a fresh clone, or an open PR that merged the swept branch. `--apply` there
# would rename the Project entity on to `task`, which the ledger alone cannot
# stop. One cheap sentinel per phase catches it (lead ruling, 2026-09-04).
SWEPT_SENTINELS: dict[int, tuple[str, str | None]] = {
    3: ("backend/src/policy_atlas/evidence_search", None),
    4: ("frontend/src/api/queries.ts", "useTasks("),
}


def _extra_exclude(rel: str) -> bool:
    """Alembic revisions are frozen history; only a new 038 revision is swept."""
    return rel.startswith("backend/alembic/versions/") and "038" not in Path(rel).name


TABLES = RenameTables(
    tool="scripts/rename_038.py",
    title="Task 038 sweep scan",
    rules=RULES,
    literal_rules=LITERAL_RULES,
    steps=STEPS,
    never_mapped=NEVER_MAPPED,
    never_mapped_contexts=NEVER_MAPPED_CONTEXTS,
    phase_roots=PHASE_ROOTS,
    phase_extra_files=PHASE_EXTRA_FILES,
    excluded_dir_names=EXCLUDED_DIR_NAMES,
    excluded_path_prefixes=EXCLUDED_PATH_PREFIXES,
    excluded_paths=EXCLUDED_PATHS,
    phase_excluded_paths=PHASE_EXCLUDED_PATHS,
    string_exempt_all=PROMPT_EXEMPT,
    string_exempt_plain=COPY_EXEMPT,
    extra_exclude=_extra_exclude,
    watch_re=WATCH_RE,
    watch_exact=WATCH_EXACT,
    trigger_re=TRIGGER_RE,
    scan_re=SCAN_RE,
    swept_sentinels=SWEPT_SENTINELS,
    ledger=DEFAULT_LEDGER,
    phase_labels={3: "backend", 4: "frontend"},
    watch_label="`orchestr`/`project`/`portfolio`/`oplan`/`pss`",
    report_intro=(
        "Read with plan § D1–D4: the identifier table below is the reviewed input to "
        "`--apply`; nothing outside it is rewritten."
    ),
)

ENGINE = Engine(TABLES)


# --------------------------------------------------------------------------
# Thin wrappers, kept so the 038 tests and any caller keep their signatures.
# --------------------------------------------------------------------------


def rename_identifier(ident: str, step: int) -> tuple[str, tuple[Rule, ...]]:
    """Rewrite one identifier under the rules of ``step`` (see the engine)."""
    return ENGINE.rename_identifier(ident, step)


def is_excluded(rel: str) -> bool:
    """Whether a repo-relative path is on the always-excluded list (plan D2)."""
    return ENGINE.is_excluded(rel)


def phase_files(root: Path, phase: int) -> list[str]:
    """Repo-relative paths the sweep may touch for ``phase``, sorted."""
    return ENGINE.phase_files(root, phase)


def looks_already_swept(root: Path, phase: int) -> bool:
    """Whether the tree already carries this phase's post-sweep vocabulary."""
    return ENGINE.looks_already_swept(root, phase)


def plan_file(path: str, text: str, phase: int, step: int) -> FilePlan:
    """Compute every rewrite ``step`` would make in one file."""
    return ENGINE.plan_file(path, text, phase, step)


def sweep_text(
    path: str, text: str, phase: int, steps: tuple[int, ...]
) -> tuple[str, list[FilePlan]]:
    """Run the given steps over one file's text, in order."""
    return ENGINE.sweep_text(path, text, phase, steps)


def build_report(
    root: Path, phase: int, steps: tuple[int, ...], ledger: Ledger | None = None
) -> Report:
    """Scan the phase file set and aggregate every finding."""
    return ENGINE.build_report(root, phase, steps, ledger)


def render_report(report: Report, max_rows: int) -> str:
    """Render the scan report as markdown."""
    return ENGINE.render_report(report, max_rows)


def run_scan(
    root: Path,
    phase: int,
    steps: tuple[int, ...],
    out: Path | None,
    max_rows: int,
    ledger: Ledger,
) -> int:
    """Emit the scan report. Returns a non-zero exit code on any collision."""
    return ENGINE.run_scan(root, phase, steps, out, max_rows, ledger)


def run_apply(
    root: Path,
    phase: int,
    steps: tuple[int, ...],
    ledger_path: Path,
    ledger: Ledger,
    force: bool = False,
) -> int:
    """Rewrite the phase file set."""
    return ENGINE.run_apply(root, phase, steps, ledger_path, ledger, force)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    return ENGINE.build_parser(__doc__ or "").parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    return ENGINE.run(args, Path(__file__).resolve().parent.parent)


if __name__ == "__main__":
    raise SystemExit(main())
