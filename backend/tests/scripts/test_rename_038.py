"""Unit tests for the task 038 vocabulary sweep (`scripts/rename_038.py`).

Every test builds a tiny synthetic tree under `tmp_path` and drives the tool
through `--root`, so nothing here reads or writes the real repository, and no
test touches the database.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "rename_038.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rename_038", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rename_038"] = module
    spec.loader.exec_module(module)
    return module


sweep = _load()


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# The identifier engine: case forms, plurals, compound-before-bare
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ident", "expected"),
    [
        # Case preservation across every form the codebase uses.
        ("project_id", "task_id"),
        ("projectId", "taskId"),
        ("ProjectOut", "TaskOut"),
        ("PROJECT", "TASK"),
        ("PROJECT_ID", "TASK_ID"),
        ("projects", "tasks"),
        ("Projects", "Tasks"),
        ("PROJECTS", "TASKS"),
        ("Page_ProjectOut_", "Page_TaskOut_"),
        # Compound before bare.
        ("project_source_snapshot", "task_source_snapshot"),
        ("project_source_snapshot_id", "task_source_snapshot_id"),
        ("uq_pss_id_project", "uq_tss_id_task"),
        ("uq_project_source_snapshot", "uq_task_source_snapshot"),
        # The `oplan` constraint infix follows its table (lead ruling).
        ("ck_oplan_status", "ck_plan_status"),
        ("ck_oplan_payload_object", "ck_plan_payload_object"),
        ("uq_oplan_project_version", "uq_plan_task_version"),
        ("fk_oplan_scope_project", "fk_plan_scope_task"),
        ("OrchestrationPlan", "TaskPlan"),
        ("orchestration_plan", "task_plan"),
        # The persona, in every shape the contract lists.
        ("orchestrator", "agent"),
        ("OpenAIOrchestratorBackend", "OpenAIAgentBackend"),
        ("StubOrchestratorBackend", "StubAgentBackend"),
        ("get_orchestrator_backend", "get_agent_backend"),
        ("_SteerPointOrchestrator", "_SteerPointAgent"),
        ("POLICY_ATLAS_ORCHESTRATOR_MODEL", "POLICY_ATLAS_AGENT_MODEL"),
        ("orchestrate", "agent"),
        ("OrchestrateResult", "AgentResult"),
        ("_orchestrate_cleanup", "_agent_cleanup"),
        ("test_orchestrate", "test_agent"),
        # The capability.
        ("evidence_base", "evidence_search"),
        ("evidence_base_coverage", "evidence_search_coverage"),
        # Already-right names that merely contain a target word.
        ("task_count", "task_count"),
        ("agent_judgement_routed", "agent_judgement_routed"),
        ("eb_iof_base_v1", "eb_iof_base_v1"),
        ("evidence_scope", "evidence_scope"),
        # Near-misses no rule maps.
        ("projection", "projection"),
        ("projected", "projected"),
        ("Orchestration", "Orchestration"),
        ("pyproject", "pyproject"),
    ],
)
def test_step_one_identifier_renames(ident: str, expected: str) -> None:
    assert sweep.rename_identifier(ident, 1)[0] == expected


@pytest.mark.parametrize(
    ("ident", "expected"),
    [
        ("portfolio_id", "project_id"),
        ("portfolioId", "projectId"),
        ("PortfolioOut", "ProjectOut"),
        ("portfolios", "projects"),
        ("PORTFOLIO_ID", "PROJECT_ID"),
        ("usePortfolios", "useProjects"),
        ("portfolio_membership", "project_membership"),
    ],
)
def test_step_two_identifier_renames(ident: str, expected: str) -> None:
    assert sweep.rename_identifier(ident, 2)[0] == expected
    # Step 1 must leave every `portfolio` alone.
    assert sweep.rename_identifier(ident, 1)[0] == ident


def test_step_one_never_produces_a_portfolio_rename() -> None:
    """The two steps are disjoint, so a step-1 result cannot be re-renamed."""
    for ident in ("project_id", "projects", "ProjectOut", "orchestrator"):
        after_one, _ = sweep.rename_identifier(ident, 1)
        assert sweep.rename_identifier(after_one, 2)[0] == after_one


# --------------------------------------------------------------------------
# Whole-file sweeps
# --------------------------------------------------------------------------

SCHEMA_PY = '''"""Table definitions."""

project = Table(
    "project",
    metadata,
    Column("project_id", UUID, primary_key=True),
    UniqueConstraint("project_id", "version", name="uq_pss_id_project"),
)

orchestration_plan = Table(
    "orchestration_plan",
    metadata,
    Column("project_id", UUID),
)

portfolio = Table("portfolio", metadata, Column("portfolio_id", UUID))
'''


def test_schema_sweep_renames_identifiers_and_the_table_string(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/core/schema.py"
    _write(tmp_path, rel, SCHEMA_PY)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    # The entity, its columns and its constraint infix.
    assert 'task = Table(\n    "task",' in out
    assert 'Column("task_id", UUID, primary_key=True)' in out
    assert 'name="uq_tss_id_task"' in out
    # The plan table: identifier -> `task_plan`, table *string* -> `plan`.
    assert 'task_plan = Table(\n    "plan",' in out
    assert "orchestration_plan" not in out
    # Step 2 ran after step 1 and claimed the freed name.
    assert 'project = Table("project", metadata, Column("project_id", UUID))' in out
    assert "portfolio" not in out


def test_apply_is_idempotent(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/core/schema.py"
    _write(tmp_path, rel, SCHEMA_PY)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    first = (tmp_path / rel).read_text(encoding="utf-8")
    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == first


def test_ledger_settles_swept_files_and_still_reaches_new_ones(tmp_path: Path) -> None:
    settled = "backend/src/policy_atlas/core/schema.py"
    _write(tmp_path, settled, SCHEMA_PY)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    ledger = sweep.read_ledger(tmp_path / sweep.DEFAULT_LEDGER)
    assert ledger[settled][1] == frozenset({1, 2})
    after_first = (tmp_path / settled).read_text(encoding="utf-8")

    # A merge from `dev` brings in a file the sweep has never seen. It is
    # swept; the settled file is left exactly as it was.
    arrived = "backend/src/policy_atlas/api/merged.py"
    _write(tmp_path, arrived, "ID = project_id\nOWNER = portfolio_id\n")

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    assert (tmp_path / arrived).read_text(encoding="utf-8") == "ID = task_id\nOWNER = project_id\n"
    assert (tmp_path / settled).read_text(encoding="utf-8") == after_first


def test_an_already_swept_tree_without_a_ledger_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh clone of the renamed branch has no ledger; sweeping it again is a bug."""
    rel = "backend/src/policy_atlas/api/merged.py"
    body = "ID = project_id\n"
    _write(tmp_path, rel, body)
    # The phase-3 sentinel: the package the lead moved by hand in 3.1.
    _write(tmp_path, "backend/src/policy_atlas/evidence_search/__init__.py", "")

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8") == body
    assert "already looks swept" in capsys.readouterr().err

    assert sweep.main(["--apply", "--phase", "3", "--force", "--root", str(tmp_path)]) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == "ID = task_id\n"


def test_the_frontend_already_swept_sentinel_is_the_renamed_hook(tmp_path: Path) -> None:
    _write(tmp_path, "frontend/src/api/queries.ts", "export function useProjects() {}\n")
    assert not sweep.looks_already_swept(tmp_path, 4)

    _write(tmp_path, "frontend/src/api/queries.ts", "export function useTasks() {}\n")
    assert sweep.looks_already_swept(tmp_path, 4)
    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 2


def test_a_swept_file_that_changed_is_refused_rather_than_double_renamed(tmp_path: Path) -> None:
    """The step-2 output re-enters step 1's domain, so a blind re-sweep is unsafe."""
    rel = "backend/src/policy_atlas/core/schema.py"
    _write(tmp_path, rel, SCHEMA_PY)
    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0

    swept = (tmp_path / rel).read_text(encoding="utf-8")
    (tmp_path / rel).write_text(swept + 'MERGED = "portfolio_id"\n', encoding="utf-8")

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8").endswith('MERGED = "portfolio_id"\n')


def test_imports_and_module_paths_are_rewritten(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/runner.py"
    _write(
        tmp_path,
        rel,
        "from policy_atlas.core.schema import orchestration_plan, project\n"
        "from policy_atlas.runtime.orchestration_plan import OrchestrationPlan\n"
        "from policy_atlas.runtime.orchestrator_backend import get_orchestrator_backend\n"
        "from policy_atlas.evidence_base.sourcing import search_loop\n"
        "from policy_atlas.runtime.orchestrate import live_planner_and_backends\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert "from policy_atlas.core.schema import task_plan, task" in out
    assert "from policy_atlas.runtime.task_plan import TaskPlan" in out
    assert "from policy_atlas.runtime.agent_backend import get_agent_backend" in out
    assert "from policy_atlas.evidence_search.sourcing import search_loop" in out
    assert "from policy_atlas.runtime.agent import live_planner_and_backends" in out


PROSE_PY = '''"""Runner docs."""

# Run this with `uv run --project backend pytest` (task 022).
NOTE = "the evidence base is thin here"


def load(project_id: str) -> None:
    """Read a run.

    Args:
        project_id: Project owning the run.

    The run's owning project is the scope of every read.
    """
    log.info("orchestrator.start", project_id=project_id)
    span = "orchestrator:plan"
    path = "/api/v1/projects/{id}/runs"
    key = "evidence_base"
    doc = "evidence-base.md"
rows = [project]
[project]
parser.add_argument("--project")
'''


def test_path_literals_change_and_free_prose_does_not(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/loader.py"
    _write(tmp_path, rel, PROSE_PY)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    # Path-like literals and log/span names are rewritten.
    assert '"agent.start"' in out
    assert 'span = "agent:plan"' in out
    assert 'path = "/api/v1/tasks/{id}/runs"' in out
    assert 'key = "evidence_search"' in out
    assert 'doc = "evidence-search.md"' in out
    # The docstring's code word is the entity and changes with it.
    assert "task_id: Task owning the run." in out
    # A code word in a docstring possessive is still a code word.
    assert "The run's owning task is the scope of every read." in out
    # Free prose is untouched.
    assert "uv run --project backend" in out
    assert "(task 022)" in out
    # A list literal `[project]` is code; only a line-initial TOML header is the table.
    assert "rows = [task]" in out
    assert "\n[project]\n" in out
    # Only uv's `--project` is protected; the ops CLI flag is the Task flag.
    assert 'add_argument("--task")' in out
    assert "the evidence base is thin here" in out


def test_copy_module_strings_are_left_to_the_lead_but_docstrings_are_swept(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/api/stage_vocabulary.py"
    assert rel in sweep.COPY_EXEMPT
    _write(
        tmp_path,
        rel,
        '"""Stage copy for one project."""\n'
        "\n"
        "STAGE_LABELS = {\n"
        '    "synthesise": "Writing the project report",\n'
        "}\n"
        "\n"
        "\n"
        "def label(project_id: str) -> str:\n"
        '    """Look up a label for one project."""\n'
        "    return STAGE_LABELS[project_id]\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    # The user-facing string survives; identifiers and docstrings are swept
    # (invariant I4 greps docstrings too).
    assert '"Writing the project report"' in out
    assert '"""Stage copy for one task."""' in out
    assert '"""Look up a label for one task."""' in out
    assert "def label(task_id: str) -> str:" in out
    assert "return STAGE_LABELS[task_id]" in out


def test_prompt_files_keep_every_string_including_the_version_id(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/orchestrator_prompt.py"
    assert rel in sweep.PROMPT_EXEMPT
    _write(
        tmp_path,
        rel,
        '"""The ``orchestrator_v1`` prompt family."""\n'
        "\n"
        "from policy_atlas.runtime.orchestrate import shape\n"
        "\n"
        'AGENT_PROMPT_VERSION = "orchestrator_v1"\n'
        'ORCHESTRATOR_PROMPT = """You are the orchestrator of Policy Atlas,\n'
        'grounded in the project\'s committed evidence."""\n'
        "# The router moment of the orchestrator.\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    # Prompt text and version ids are the lead's, in phase 3.3 (ruling R1).
    assert '"""The ``orchestrator_v1`` prompt family."""' in out
    assert 'AGENT_PROMPT_VERSION = "orchestrator_v1"' in out
    assert "You are the orchestrator of Policy Atlas," in out
    assert "grounded in the project's committed evidence." in out
    # Imports, module paths, comments and the constant's own name still move.
    assert "from policy_atlas.runtime.agent import shape" in out
    assert "AGENT_PROMPT = " in out
    assert "# The router moment of the agent." in out


def test_hand_edited_and_generated_files_are_out_of_the_set(tmp_path: Path) -> None:
    vocabulary = "frontend/src/lib/vocabulary.ts"
    generated = "frontend/src/api/gen/types.ts"
    migration = "backend/tests/core/test_migrations_029.py"
    body = 'export const PROJECT = { one: "Project", key: "project_id" };\n'
    for rel in (vocabulary, generated):
        _write(tmp_path, rel, body)
    _write(tmp_path, migration, 'TABLE = "orchestration_plan"\n')

    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 0
    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0

    assert (tmp_path / vocabulary).read_text(encoding="utf-8") == body
    assert (tmp_path / generated).read_text(encoding="utf-8") == body
    assert (tmp_path / migration).read_text(encoding="utf-8") == 'TABLE = "orchestration_plan"\n'


def test_retained_frontend_exports_are_never_mapped(tmp_path: Path) -> None:
    rel = "frontend/src/views/AppShell.tsx"
    _write(
        tmp_path,
        rel,
        'import { PROJECT, TASK } from "@/lib/vocabulary";\n'
        "\n"
        "export function AppShell({ projectId }: { projectId: string }) {\n"
        "  const label = PROJECT.one + TASK.one;\n"
        '  return <a href={`/projects/${projectId}`}>{label}</a>;\n'
        "}\n",
    )

    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert "import { PROJECT, TASK }" in out
    assert "const label = PROJECT.one + TASK.one;" in out
    assert "export function AppShell({ taskId }: { taskId: string })" in out
    assert "`/tasks/${taskId}`" in out


def test_dom_ids_query_keys_and_search_params(tmp_path: Path) -> None:
    rel = "frontend/src/views/NewTaskView.tsx"
    _write(
        tmp_path,
        rel,
        'const ids = ["new-portfolio-name", "new-task-portfolio"];\n'
        'const keys = ["projects", "portfolios"];\n'
        'const href = "/portfolios?portfolio=" + portfolioId;\n'
        'const cap = "evidence_base";\n',
    )

    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert '["new-project-name", "new-task-project"]' in out
    assert '["tasks", "projects"]' in out
    assert '"/projects?project=" + projectId' in out
    assert '"evidence_search"' in out


# --------------------------------------------------------------------------
# Collisions and ordering
# --------------------------------------------------------------------------


def test_refuses_to_rename_onto_an_existing_symbol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rel = "backend/src/policy_atlas/api/routers/things.py"
    body = "def task_row():\n    return 1\n\n\ndef project_row():\n    return 2\n"
    _write(tmp_path, rel, body)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8") == body
    assert "collision" in capsys.readouterr().err

    assert sweep.main(["--scan", "--phase", "3", "--root", str(tmp_path)]) == 1


def test_step_two_collision_is_reported_before_it_is_written(tmp_path: Path) -> None:
    """`portfolio` may only claim `project` once step 1 has vacated it."""
    rel = "frontend/src/api/mutations.ts"
    body = (
        "export function useCreateProject() {}\n"
        "export function useCreatePortfolio() {}\n"
    )
    _write(tmp_path, rel, body)

    # `useCreateProject` is never mapped (dead export, deleted by hand), so
    # step 2 would collide with it.
    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8") == body


def test_step_one_then_step_two_ordering(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/api/routers/scope.py"
    _write(
        tmp_path,
        rel,
        "def scope(project_id: str, portfolio_id: str) -> tuple[str, str]:\n"
        "    return project_id, portfolio_id\n",
    )

    # Step 1 alone: `project_id` moves, `portfolio_id` waits.
    assert sweep.main(["--apply", "--phase", "3", "--step", "1", "--root", str(tmp_path)]) == 0
    after_one = (tmp_path / rel).read_text(encoding="utf-8")
    assert "task_id: str, portfolio_id: str" in after_one

    # Step 2 then claims the vacated `project_id`, and does not touch `task_id`.
    assert sweep.main(["--apply", "--phase", "3", "--step", "2", "--root", str(tmp_path)]) == 0
    after_two = (tmp_path / rel).read_text(encoding="utf-8")
    assert "task_id: str, project_id: str" in after_two
    assert "portfolio" not in after_two


def test_scan_reports_the_table_the_unmapped_and_zero_collisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        tmp_path,
        "backend/src/policy_atlas/runtime/agentic.py",
        "PLAN = OrchestrationPlan\n"
        "KIND = Orchestration\n"
        "ID = project_id\n"
        "NAME = ck_oplan_status\n",
    )

    assert sweep.main(["--scan", "--phase", "3", "--root", str(tmp_path)]) == 0
    report = capsys.readouterr().out

    assert "| `OrchestrationPlan` | `TaskPlan` | 1 |" in report
    assert "| `project_id` | `task_id` | 1 |" in report
    assert "**None.** No proposed target already exists" in report
    # `Orchestration` and the `oplan` infix have no rule: lead decisions.
    assert "`Orchestration`" in report
    assert "`ck_oplan_status`" in report


# --------------------------------------------------------------------------
# Supporting machinery
# --------------------------------------------------------------------------


def test_prose_spans_separate_code_from_strings_and_comments() -> None:
    text = 'x = "project"  # a project note\n'
    strings, comments, plain = sweep.prose_spans("a.py", text)
    assert text[strings[0][0] : strings[0][1]] == '"project"'
    assert text[comments[0][0] : comments[0][1]] == "# a project note"
    assert plain == strings

    doc = '"""Project docs."""\nLABEL = "a project"\n'
    doc_strings, _, doc_plain = sweep.prose_spans("a.py", doc)
    # A docstring is documentation, so it is not on the copy-module hand list.
    assert len(doc_strings) == 2
    assert [doc[start:end] for start, end in doc_plain] == ['"a project"']

    ts = "const a = `/projects/${projectId}`; // portfolio note\n"
    ts_strings, ts_comments, _ = sweep.prose_spans("a.ts", ts)
    # The `${...}` hole is code, not string, so identifiers inside it are swept.
    assert any(ts[start:end] == "`/projects/" for start, end in ts_strings)
    assert ts[ts_comments[0][0] : ts_comments[0][1]] == "// portfolio note"


def test_phase_file_sets_respect_the_always_excluded_list(tmp_path: Path) -> None:
    for rel in (
        "backend/src/policy_atlas/core/schema.py",
        "backend/tests/core/test_schema.py",
        "backend/tests/core/test_migrations_025.py",
        "backend/alembic/env.py",
        "backend/alembic/versions/b2f6a9d4c1e7_earlier.py",
        "backend/alembic/versions/aaa038_vocabulary.py",
        "frontend/src/views/AppShell.tsx",
        "frontend/src/lib/vocabulary.ts",
        "frontend/src/api/gen/types.ts",
        "frontend/e2e/journey.spec.ts",
        "frontend/node_modules/pkg/index.ts",
        "docs/specs/sources/vocabulary/frozen.md",
        "scripts/rename_038.py",
        "backend/tests/scripts/test_rename_038.py",
    ):
        _write(tmp_path, rel, "project_id\n")

    backend = sweep.phase_files(tmp_path, 3)
    assert "backend/src/policy_atlas/core/schema.py" in backend
    assert "backend/tests/core/test_schema.py" in backend
    assert "backend/alembic/env.py" in backend
    assert "backend/tests/core/test_migrations_025.py" not in backend
    assert "backend/alembic/versions/b2f6a9d4c1e7_earlier.py" not in backend
    assert "scripts/rename_038.py" not in backend
    # This file's own fixtures are the old vocabulary by construction.
    assert "backend/tests/scripts/test_rename_038.py" not in backend

    frontend = sweep.phase_files(tmp_path, 4)
    assert frontend == ["frontend/e2e/journey.spec.ts", "frontend/src/views/AppShell.tsx"]
