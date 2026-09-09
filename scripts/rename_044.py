#!/usr/bin/env python3
"""Task 044 phase-one sweep: `planning`/`planner` -> `task_agent`, and EB -> ES.

The tables below are the lead's rule table
(`docs/tasks/044-scoping-shell-baseline/rename-rules.md`), derived from
`rename-manifest.md`. The machinery is `scripts/rename_engine.py`, shared with
`scripts/rename_038.py`; only the tables differ.

Two renames run from one tool:

1. **The Task Agent rename.** The conversation-kind and persona words become the
   product's Task Agent: `planning_transcript` -> `task_agent_transcript`,
   `planner_state` -> `task_agent_state`, the `ptr` constraint infix -> `tat`,
   and bare `planning`/`planner` -> `task_agent`. Casing follows the engine's
   word splitter, so `PlanningPane` -> `TaskAgentPane`,
   `planningComposerPlaceholder` -> `taskAgentComposerPlaceholder` and
   `PLANNER_MODEL` -> `TASK_AGENT_MODEL`. The one hyphenated shape the
   identifier pass cannot see, the route segment `planning-turns`, is a literal
   rule.
2. **The EB -> ES abbreviation sweep** (`--docs`, phase 5), whole-word and
   case-sensitive, everywhere except the exact phrase `EB handoff`, which names
   a frozen source document (rules decision 4).

What is deliberately left alone:

- **The thirteen hash-pinned prompt modules** (every key of
  `scripts/prompt_hashes.json`, read at table-build time) are excluded whole.
  Rubric 13 requires every other pinned hash to stay unchanged, and
  `runtime/planner_prompt.py` moves by `git mv` with a byte-identical interior
  (P2, C14). `runtime/agent_prompt.py`'s docstring mentions of
  `planner_prompt.py` / `planner_v5` therefore stay stale and are flagged, not
  swept.
- **The symbols the prompt module declares** (`PLANNER_SYSTEM_PROMPT`,
  `build_planner_messages`, `PlannerTurnWire`, `PLANNER_PROMPT_VERSION`, the
  `PLANNER_*` constants) are added to the never-mapped set from a
  declared-symbol scan of that file, so callers keep importing them by their old
  names -- from the new module path, which the identifier pass does rewrite
  (`runtime.planner_prompt` -> `runtime.task_agent_prompt`).
- **The wire role literal** `"role": "planner"`, ordinary-English
  `Replanning`/`replanning`, the fixture prose phrases the manifest lists, and
  any `planner_v<N>` version string.

Modes::

    uv run --project backend python scripts/rename_044.py --scan --phase 3
    uv run --project backend python scripts/rename_044.py --scan --docs
    uv run --project backend python scripts/rename_044.py --apply --phase 4

``--scan`` emits the reviewable markdown report (identifier table, unmapped
hits, never-mapped hits, prose contexts, collisions) and exits non-zero on any
collision. ``--apply`` refuses while a collision remains and is idempotent via
the ledger at ``scripts/.rename_044_state.json``. Neither moves a file: the
module and component moves (`runtime/planner.py` -> `runtime/task_agent.py`,
`PlanningPane.tsx` -> `TaskAgentPane.tsx`, …) are `git mv`s done by hand in
phase 1.3, and the sweep rewrites the import paths so they resolve.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rename_engine import (  # noqa: E402
    Engine,
    LiteralRule,
    RenameTables,
    Rule,
    declared_symbols,
)

# --------------------------------------------------------------------------
# Identifier rules (rules § "Identifier rules"). One step; compound before bare.
# --------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    Rule(
        1,
        ("planning", "transcript"),
        ("task", "agent", "transcript"),
        "table, module refs, test names",
    ),
    Rule(1, ("planner", "state"), ("task", "agent", "state"), "column"),
    Rule(1, ("ptr",), ("tat",), "constraint infix (rules decision 1)"),
    Rule(
        1,
        ("planning",),
        ("task", "agent"),
        "conversation-kind sense: planning_turn, PlanningPane, planning_router, 'planning'",
    ),
    Rule(
        1,
        ("planner",),
        ("task", "agent"),
        "persona: PlannerBackend, PLANNER_MODEL, get_planner_backend, 'planner'",
    ),
)

STEPS: tuple[int, ...] = (1,)

ALL_PHASES = frozenset({3, 4, 5})

# --------------------------------------------------------------------------
# Never mapped: exact identifiers (rules § "Never mapped (exact identifiers)").
# --------------------------------------------------------------------------

BASE_NEVER_MAPPED: dict[str, frozenset[int]] = {
    # Stored provenance value: it splits as `planner` + `v11`, so the exact
    # exclusion is what keeps it whole (038 rule R1).
    "planner_v11": ALL_PHASES,
    # Extraction fingerprints and a legacy steer-point id.
    "eb_iof_base_v1": ALL_PHASES,
    "eb_icf_base_v1": ALL_PHASES,
    "evidence_base_coverage": ALL_PHASES,
}

# --------------------------------------------------------------------------
# Never mapped: text contexts (rules § "Never mapped (text contexts)").
# --------------------------------------------------------------------------

NEVER_MAPPED_CONTEXTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # The transcript rehydration role, whose consumer is the kept prompt module
    # (P2). Only the *value* is protected; the surrounding code renames.
    (
        "wire role literal `\"role\": \"planner\"`",
        re.compile(r"[\"']?\brole[\"']?[\)\]]?\s*[:=]=?\s*[\"']planner[\"']"),
    ),
    # The docstring role union describing the kept literal, so the prose stays
    # truthful about what the wire actually carries (lead ruling 2, 2026-09-09).
    ("docstring role union `|\"planner\"`", re.compile(r"\|\s*[\"']planner[\"']")),
    # The bare quoted string `"Planning"`: a stored conversation title and the
    # History category, never a Task Agent label (the screen uses the
    # vocabulary module) and ordinary English (lead ruling 1a, 2026-09-09).
    ("stored title / History category `\"Planning\"`", re.compile(r"[\"']Planning[\"']")),
    # Stored provenance value inside plan payloads
    # (`country_group.authorship` / `CountryGroupAuthorship`). Not in the
    # contract's rewrite list, so it is kept like the fingerprints
    # (lead correction, 2026-09-09).
    ("stored authorship value `planner-proposed`", re.compile(r"\bplanner-proposed\b")),
    # Ordinary English: UI microcopy and a 409 detail string, not the concept.
    ("ordinary English `Replanning`/`replanning`", re.compile(r"\b[Rr]eplanning\b")),
    # Any pinned prompt-version string, not only `planner_v11`.
    ("prompt version string `planner_v<N>`", re.compile(r"\bplanner_v\d+\b")),
    # Ordinary-English `planning` in fixture prose; the engine cannot tell it
    # from the identifier, so the five sites are listed by phrase.
    ("fixture prose `Environmental planning`", re.compile(r"\bEnvironmental planning\b")),
    ("fixture prose `Strategic planning`", re.compile(r"\bStrategic planning\b")),
    ("fixture prose `Planning delays`", re.compile(r"\bPlanning delays\b")),
    ("fixture prose `planning requirements`", re.compile(r"\bplanning requirements\b")),
)

# --------------------------------------------------------------------------
# Docs file lists (manifest § A.5 and § B.1-B.3).
# --------------------------------------------------------------------------

KNOWLEDGE_FILES: tuple[str, ...] = tuple(
    f"docs/knowledge/{name}.md"
    for name in (
        "plan-lineage-by-fencing-not-custody",
        "scope-constraint-fields-projection-surfaces",
        "prompt-honesty-rules-route-around-new-capability",
        "log",
        "overton-filter-values-display-names",
        "structured-output-prompts-pin-key-vocabulary",
        "index",
        "two-phase-retry-terminal-status",
        "live-check-drive-runbook",
        "silent-sdk-guards-and-stub-shaped-tests",
        "jointly-compiled-fields-patch-together",
        "model-output-nul-scrub",
        "orchestrate-stub-smoke",
    )
)

# Manifest § B.1-B.3: the EB -> ES file list.
EB_FILES: tuple[str, ...] = (
    "docs/specs/capabilities/options-scoping/components.md",
    "docs/specs/capabilities/options-scoping/capability.md",
    "docs/specs/capabilities/options-scoping/trust.md",
    "docs/specs/capabilities/evidence-search/capability.md",
    "docs/specs/capabilities/evidence-search/components.md",
    "docs/specs/capabilities/evidence-search/provenance.md",
    "docs/specs/index.md",
    "docs/specs/product.md",
    "docs/specs/system/data-model.md",
    "docs/specs/system/execution-orchestration.md",
    "docs/specs/system/provenance-grounding.md",
    "docs/specs/system/plan-as-object.md",
    "docs/tasks/_templates/contract.md",
    "docs/agentic-ops/spec-authoring.md",
    "docs/agentic-ops/backlog.md",
    "backend/src/policy_atlas/runtime/runner.py",
    "backend/src/policy_atlas/runtime/task_plan.py",
    "backend/src/policy_atlas/runtime/agent.py",
    "backend/src/policy_atlas/evidence_search/synthesis/synthesise.py",
    "backend/src/policy_atlas/evidence_search/extract/iof_records.py",
)

# --------------------------------------------------------------------------
# Literal rules (rules § "Literal rules" and decisions 5 and 9).
# --------------------------------------------------------------------------

DOCS_PHASE = 5

LITERAL_RULES: tuple[LiteralRule, ...] = (
    # The hyphenated route segment: the identifier pass sees `planning` and
    # `turns` as two separate words, so it cannot join them.
    LiteralRule(
        step=1,
        name="planning-turns -> task-agent-turns",
        pattern=re.compile(r"(?<![\w-])planning-turns(?![\w-])"),
        repl="task-agent-turns",
    ),
    # Lead ruling 1b (2026-09-09): the frontend's user-visible `Planning
    # conversation` (the pane's aria-label and the assertions that read it)
    # becomes `Task Agent conversation`, with the space -- nothing renders as
    # `TaskAgent` in copy.
    LiteralRule(
        step=1,
        name="`Planning conversation` -> `Task Agent conversation` (frontend copy)",
        pattern=re.compile(r"\bPlanning conversation\b"),
        repl="Task Agent conversation",
        phases=frozenset({4}),
    ),
    # Decision 9: three prose phrase rules. Markdown only, docs mode only, and
    # outside the backticked code spans -- the `.py` files of manifest § B.3 are
    # in the docs set for the abbreviation sweep alone.
    LiteralRule(
        step=1,
        name="prose `planning turn` -> `Task Agent turn`",
        pattern=re.compile(r"\b[Pp]lanning turn"),
        repl="Task Agent turn",
        paths=("*.md",),
        phases=frozenset({DOCS_PHASE}),
        where="prose",
    ),
    LiteralRule(
        step=1,
        name="prose `planning conversation` -> `Task Agent conversation`",
        pattern=re.compile(r"\b[Pp]lanning conversation"),
        repl="Task Agent conversation",
        paths=("*.md",),
        phases=frozenset({DOCS_PHASE}),
        where="prose",
    ),
    LiteralRule(
        step=1,
        name="prose `the planner` -> `the Task Agent`",
        pattern=re.compile(r"\b(?P<the>[Tt]he) planner\b"),
        repl="{the} Task Agent",
        paths=("*.md",),
        phases=frozenset({DOCS_PHASE}),
        where="prose",
    ),
    # The abbreviation sweep (group B). `EB handoff` names the frozen source
    # document and is kept wherever it appears (decision 4).
    LiteralRule(
        step=1,
        name="EB -> ES (whole word, except `EB handoff`)",
        pattern=re.compile(r"\bEB\b(?!\s+handoff)"),
        repl="ES",
        paths=EB_FILES + ("docs/knowledge/index.md",),
        phases=frozenset({DOCS_PHASE}),
        where="prose",
    ),
    # Decision 5: a pre-existing dead link, fixed in the docs sweep.
    LiteralRule(
        step=1,
        name="stale link `capabilities/evidence-base/` -> `capabilities/evidence-search/`",
        pattern=re.compile(r"capabilities/evidence-base/"),
        repl="capabilities/evidence-search/",
        paths=("docs/tasks/_templates/contract.md",),
        phases=frozenset({DOCS_PHASE}),
    ),
)

# --------------------------------------------------------------------------
# File sets (rules § "File sets").
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
    5: (),
}

PHASE_EXTRA_FILES: dict[int, tuple[str, ...]] = {
    3: (
        "backend/alembic/env.py",
        "scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py",
    ),
    4: (),
    5: ("infra/DEPLOYMENT.md", "docs/specs/system/web-api.md")
    + KNOWLEDGE_FILES
    + EB_FILES,
}

# In `--docs` mode a markdown file's prose belongs to the phrase rules and the
# abbreviation sweep; only its backticked code spans get the identifier pass
# (decision 9). The `.py` files of manifest § B.3 are in the docs set for the
# abbreviation sweep alone -- their identifiers were already swept in phase 3.
PHASE_IDENTIFIER_SUFFIXES: dict[int, tuple[str, ...]] = {DOCS_PHASE: (".md",)}
PHASE_CODE_SPAN_ONLY_SUFFIXES: dict[int, tuple[str, ...]] = {DOCS_PHASE: (".md",)}

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

# Beats every exclusion above: the one `docs/tasks/` file in the set, the
# templates contract whose stale link decision 5 fixes.
ALWAYS_INCLUDED_PATHS: frozenset[str] = frozenset({"docs/tasks/_templates/contract.md"})

# The prompt module whose interior is kept verbatim, before and after its
# `git mv`. Its declared symbols join the never-mapped set.
PROMPT_MODULE_CANDIDATES: tuple[str, ...] = (
    "backend/src/policy_atlas/runtime/planner_prompt.py",
    "backend/src/policy_atlas/runtime/task_agent_prompt.py",
)
EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "frontend/openapi.json",
        "docs/specs/log.md",
        "docs/agentic-ops/failure-log.md",
        "backlog.md",
        "scripts/rename_038.py",
        "scripts/rename_044.py",
        "scripts/rename_engine.py",
        "scripts/schema_manifest.py",
        # Both sweeps' own tests: their fixtures are the old vocabulary by
        # construction, so sweeping them would destroy them.
        "backend/tests/scripts/test_rename_038.py",
        "backend/tests/scripts/test_rename_044.py",
        "backend/tests/scripts/test_rename_044_sweep.py",
    }
    # The kept prompt module, before and after its `git mv`: `prompt_hashes.json`
    # still carries the old key until phase 1.3 re-pins it, so name both.
    | frozenset(PROMPT_MODULE_CANDIDATES)
)

# The historical migration tests: hand-edited to the dual-schema strategy where
# the head catalog is read, and they name the old objects by construction.
MIGRATION_TESTS: tuple[str, ...] = tuple(
    f"backend/tests/core/{name}"
    for name in (
        "test_capability_run_migration.py",
        "test_effect_direction_migration.py",
        "test_extract_schema_v2_migration.py",
        "test_icf_migration.py",
        "test_migration_038.py",
        # This slice's own round-trip test: it names both generations of the
        # catalog by construction, so sweeping it would destroy it.
        "test_migration_044_rename.py",
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
    3: frozenset(MIGRATION_TESTS),
    4: frozenset(),
    5: frozenset(),
}

# `plann(ing|er)` and not bare `plann`: the plan family (`planned`,
# `_PlannedCall`, `unplanned`) is a different concept and would bury the real
# near-misses in noise.
WATCH_RE = re.compile(r"plann(?:ing|er)", re.IGNORECASE)
WATCH_EXACT: frozenset[str] = frozenset({"ptr"})
TRIGGER_RE = re.compile(r"plann(?:ing|er)|ptr", re.IGNORECASE)
SCAN_RE = re.compile(r"plann(?:ing|er)|ptr", re.IGNORECASE)

DEFAULT_LEDGER = "scripts/.rename_044_state.json"

# Content markers, not paths: phase 1.3 `git mv`s the modules *before* it
# sweeps, so "the renamed file exists" would refuse the very first `--apply`.
# What only the sweep can produce is the renamed vocabulary inside the file.
SWEPT_SENTINELS: dict[int, tuple[str, str | None]] = {
    3: ("backend/src/policy_atlas/core/schema.py", "task_agent_transcript"),
    4: ("frontend/src/views/workspace/TaskAgentPane.tsx", "TaskAgentPane"),
    # Not `infra/DEPLOYMENT.md`: phase 1.3 renames that one env-var row by hand,
    # so the docs sweep would refuse itself. `web-api.md` is swept only by
    # `--docs`.
    5: ("docs/specs/system/web-api.md", "task-agent-turns"),
}

PROMPT_HASHES = "scripts/prompt_hashes.json"


def _extra_exclude(rel: str) -> bool:
    """Alembic revisions are frozen history; only a new 044 revision is swept."""
    return rel.startswith("backend/alembic/versions/") and "044" not in Path(rel).name


def pinned_prompt_modules(root: Path) -> frozenset[str]:
    """The hash-pinned prompt modules, read from `scripts/prompt_hashes.json`.

    Reading the pin file rather than a hard-coded list means a newly pinned
    prompt module is excluded from the sweep automatically, which is what
    rubric 13 (every other pinned hash unchanged) needs.

    Args:
        root: Repo root.

    Returns:
        The repo-relative module paths, or an empty set when the pin file is
        absent (a synthetic tree in a test).
    """
    path = root / PROMPT_HASHES
    if not path.is_file():
        return frozenset()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(loaded, dict):
        return frozenset()
    return frozenset(str(key) for key in loaded)


def prompt_module_symbols(root: Path) -> frozenset[str]:
    """Symbols the kept prompt module declares, which no rule may rewrite.

    The module is excluded from the sweep whole, so callers keep importing
    `PLANNER_SYSTEM_PROMPT`, `build_planner_messages`, `PlannerTurnWire` and the
    `PLANNER_*` constants by their old names; only the module path in the import
    statement moves.

    Args:
        root: Repo root.

    Returns:
        The declared names a rule would otherwise rename.
    """
    for rel in PROMPT_MODULE_CANDIDATES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        return frozenset(
            name for name in declared_symbols(rel, text) if TRIGGER_RE.search(name)
        )
    return frozenset()


def build_tables(root: Path) -> RenameTables:
    """Assemble the 044 tables against one checkout.

    Two entries are computed rather than listed: the pinned prompt modules
    (from `scripts/prompt_hashes.json`) and the kept prompt module's declared
    symbols (from a declared-symbol scan of the file itself).

    Args:
        root: Repo root the sweep will run over.

    Returns:
        The tables to hand to :class:`rename_engine.Engine`.
    """
    never_mapped = dict(BASE_NEVER_MAPPED)
    for name in prompt_module_symbols(root):
        never_mapped[name] = ALL_PHASES
    return RenameTables(
        tool="scripts/rename_044.py",
        title="Task 044 sweep scan",
        rules=RULES,
        literal_rules=LITERAL_RULES,
        steps=STEPS,
        never_mapped=never_mapped,
        never_mapped_contexts=NEVER_MAPPED_CONTEXTS,
        phase_roots=PHASE_ROOTS,
        phase_extra_files=PHASE_EXTRA_FILES,
        excluded_dir_names=EXCLUDED_DIR_NAMES,
        excluded_path_prefixes=EXCLUDED_PATH_PREFIXES,
        excluded_paths=EXCLUDED_PATHS | pinned_prompt_modules(root),
        always_included_paths=ALWAYS_INCLUDED_PATHS,
        phase_excluded_paths=PHASE_EXCLUDED_PATHS,
        extra_exclude=_extra_exclude,
        watch_re=WATCH_RE,
        watch_exact=WATCH_EXACT,
        trigger_re=TRIGGER_RE,
        scan_re=SCAN_RE,
        swept_sentinels=SWEPT_SENTINELS,
        ledger=DEFAULT_LEDGER,
        phase_labels={3: "backend", 4: "frontend", 5: "docs"},
        phase_identifier_suffixes=PHASE_IDENTIFIER_SUFFIXES,
        phase_code_span_only_suffixes=PHASE_CODE_SPAN_ONLY_SUFFIXES,
        suppress_unmapped_in_contexts=True,
        watch_label="`planning`/`planner`/`ptr`",
        report_intro=(
            "Read with `docs/tasks/044-scoping-shell-baseline/rename-rules.md`: the "
            "identifier table below is the reviewed input to `--apply`; nothing outside "
            "it is rewritten."
        ),
    )


DEFAULT_ROOT = Path(__file__).resolve().parent.parent
TABLES = build_tables(DEFAULT_ROOT)
ENGINE = Engine(TABLES)


def _normalise(argv: list[str] | None) -> list[str]:
    """Expand ``--docs`` into ``--phase 5``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--docs" in args:
        args = [a for a in args if a != "--docs"] + ["--phase", str(DOCS_PHASE)]
    return args


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = ENGINE.build_parser(__doc__ or "").parse_args(_normalise(argv))
    root: Path = args.root if args.root is not None else DEFAULT_ROOT
    engine = ENGINE if root == DEFAULT_ROOT else Engine(build_tables(root))
    return engine.run(args, DEFAULT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
