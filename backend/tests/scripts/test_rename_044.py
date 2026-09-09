"""Unit tests for the task 044 vocabulary sweep (`scripts/rename_044.py`).

Every test builds a tiny synthetic tree under `tmp_path` and drives the tool
through `--root`, so nothing here reads or writes the real repository, and no
test touches the database. The shared machinery lives in
`scripts/rename_engine.py`; the 038 suite (`test_rename_038.py`) is the real
guard that the extraction kept that tool's behaviour, and one case here pins
the engine against the 038 tables as a canary.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sweep = _load("rename_044")
sweep_038 = _load("rename_038")


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# The identifier engine: case forms, compound before bare
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ident", "expected"),
    [
        # The manifest's ⚠ rows: the casing cases that needed a human check.
        ("planningComposerPlaceholder", "taskAgentComposerPlaceholder"),
        ("PlanningPane", "TaskAgentPane"),
        ("PLANNER_MODEL", "TASK_AGENT_MODEL"),
        ("planner_state", "task_agent_state"),
        ("uq_ptr_task_client_turn", "uq_tat_task_client_turn"),
        ("planning_transcript", "task_agent_transcript"),
        ("OpenAIPlannerBackend", "OpenAITaskAgentBackend"),
        ("planningTurns", "taskAgentTurns"),
        ("planningOpen", "taskAgentOpen"),
        ("plannerText", "taskAgentText"),
        ("latestPlanning", "latestTaskAgent"),
        ("PlannerBubble", "TaskAgentBubble"),
        # A leading underscore is not a word separator.
        ("_ModerateStubPlanner", "_ModerateStubTaskAgent"),
        # Every bare shape.
        ("planner", "task_agent"),
        ("Planner", "TaskAgent"),
        ("PLANNER", "TASK_AGENT"),
        ("planning", "task_agent"),
        ("Planning", "TaskAgent"),
        # The compound rules, and the module path the four moves need.
        ("planner_prompt", "task_agent_prompt"),
        ("planning_transcript_task_id_fkey", "task_agent_transcript_task_id_fkey"),
        ("PlanningTranscriptTurnOut", "TaskAgentTranscriptTurnOut"),
        ("ck_ptr_suggestions_array", "ck_tat_suggestions_array"),
        ("uq_conversation_one_active_planning", "uq_conversation_one_active_task_agent"),
        ("POLICY_ATLAS_PLANNER_MODEL", "POLICY_ATLAS_TASK_AGENT_MODEL"),
        ("planning_turn_in_progress", "task_agent_turn_in_progress"),
        ("PLANNING_TAB_ID", "TASK_AGENT_TAB_ID"),
        ("usePlanningTurns", "useTaskAgentTurns"),
        ("isPlanning", "isTaskAgent"),
        # The plan family is a different concept and no rule maps it.
        ("plan", "plan"),
        ("TaskPlan", "TaskPlan"),
        ("PlanDraft", "PlanDraft"),
        ("plan_id", "plan_id"),
        ("planned", "planned"),
        ("_PlannedCall", "_PlannedCall"),
        # Ordinary English, and the stored provenance value.
        ("Replanning", "Replanning"),
        ("replanning", "replanning"),
    ],
)
def test_identifier_renames(ident: str, expected: str) -> None:
    assert sweep.ENGINE.rename_identifier(ident, 1)[0] == expected


@pytest.mark.parametrize(
    ("ident", "expected"),
    [
        ("project_id", "task_id"),
        ("PortfolioOut", "PortfolioOut"),
        ("OrchestrationPlan", "TaskPlan"),
        ("uq_pss_id_project", "uq_tss_id_task"),
    ],
)
def test_the_engine_still_runs_the_038_tables(ident: str, expected: str) -> None:
    """Canary for the extraction; `test_rename_038.py` is the real guard."""
    assert sweep_038.rename_identifier(ident, 1)[0] == expected


# --------------------------------------------------------------------------
# Whole-file sweeps: backend
# --------------------------------------------------------------------------


def test_backend_sweep_renames_identifiers_routes_and_module_paths(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/api/routers/planning.py"
    _write(
        tmp_path,
        rel,
        "from policy_atlas.runtime.planner import PlannerBackend, get_planner_backend\n"
        "from policy_atlas.api.contract.planning import PlanningTurnOut\n"
        "\n"
        '@router.post("/api/v1/tasks/{task_id}/planning-turns")\n'
        "async def create_planning_turn(planner: PlannerBackend) -> PlanningTurnOut:\n"
        '    log.info("planner.turn.usage", kind="planning")\n'
        "    return PlanningTurnOut()\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert "from policy_atlas.runtime.task_agent import TaskAgentBackend" in out
    assert "get_task_agent_backend" in out
    assert "from policy_atlas.api.contract.task_agent import TaskAgentTurnOut" in out
    # The hyphenated route segment is a literal rule.
    assert '"/api/v1/tasks/{task_id}/task-agent-turns"' in out
    assert "async def create_task_agent_turn(task_agent: TaskAgentBackend)" in out
    assert '"task_agent.turn.usage"' in out
    assert 'kind="task_agent"' in out


def test_the_wire_role_literal_is_kept_but_the_tracing_label_renames(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/planner.py"
    _write(
        tmp_path,
        rel,
        'HISTORY = [{"role": "planner", "text": reply}]\n'
        'def emit(turn: dict[str, str]) -> None:\n'
        '    if turn["role"] == "planner":\n'
        '        span.set_attribute(label="planner")\n',
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert '{"role": "planner", "text": reply}' in out
    assert 'if turn["role"] == "planner":' in out
    # A tracing label is not the wire role: it renames with the module (D8).
    assert 'label="task_agent"' in out


def test_the_version_string_and_the_fixture_prose_are_kept(tmp_path: Path) -> None:
    rel = "backend/tests/runtime/test_planner.py"
    _write(
        tmp_path,
        rel,
        'VERSION = "planner_v11"\n'
        'OLD = "planner_v5"\n'
        'planner_v11 = VERSION\n'
        'SUBJECTS = ["Environmental planning", "Strategic planning"]\n'
        'FINDING = "Planning delays slowed the heat-pump rollout."\n'
        'RULES = "bans, licensing or planning requirements"\n'
        'def test_planner_reply() -> None:\n'
        "    assert VERSION\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert '"planner_v11"' in out
    assert '"planner_v5"' in out
    assert "planner_v11 = VERSION" in out
    assert '["Environmental planning", "Strategic planning"]' in out
    assert '"Planning delays slowed the heat-pump rollout."' in out
    assert '"bans, licensing or planning requirements"' in out
    # Everything else in the file still moves.
    assert "def test_task_agent_reply() -> None:" in out


def test_the_stored_authorship_value_is_kept(tmp_path: Path) -> None:
    """`planner-proposed` is a stored `country_group.authorship` value (kept)."""
    rel = "backend/src/policy_atlas/runtime/task_plan.py"
    _write(
        tmp_path,
        rel,
        'Authorship = Literal["pinned-table", "planner-proposed", "user-amended"]\n'
        'def default_planner_authorship() -> str:\n'
        '    return "planner-proposed"\n',
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert out.count('"planner-proposed"') == 2
    # The identifier around it still moves.
    assert "def default_task_agent_authorship() -> str:" in out


def test_replanning_is_ordinary_english_and_stays(tmp_path: Path) -> None:
    rel = "frontend/src/views/workspace/PlanningPane.tsx"
    _write(
        tmp_path,
        rel,
        'const label = replanning ? "Replanning…" : plannerText;\n'
        "export function PlanningPane() { return null; }\n",
    )

    assert sweep.main(["--apply", "--phase", "4", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert 'const label = replanning ? "Replanning…" : taskAgentText;' in out
    assert "export function TaskAgentPane()" in out


# --------------------------------------------------------------------------
# The kept prompt module
# --------------------------------------------------------------------------

PROMPT_MODULE = "backend/src/policy_atlas/runtime/planner_prompt.py"

PROMPT_BODY = '''"""The ``planner_v11`` prompt family."""

PLANNER_PROMPT_VERSION = "planner_v11"
PLANNER_SYSTEM_PROMPT = """You are the planner."""
PLANNER_TURN_MAX = 40


class PlannerTurnWire:
    pass


def build_planner_messages() -> list[str]:
    return []
'''


def _write_prompt_module(root: Path) -> None:
    _write(root, PROMPT_MODULE, PROMPT_BODY)
    _write(root, "scripts/prompt_hashes.json", json.dumps({PROMPT_MODULE: "0" * 64}) + "\n")


def test_the_pinned_prompt_module_is_excluded_whole(tmp_path: Path) -> None:
    _write_prompt_module(tmp_path)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0

    assert (tmp_path / PROMPT_MODULE).read_text(encoding="utf-8") == PROMPT_BODY


def test_a_caller_keeps_the_prompt_symbols_and_moves_the_module_path(tmp_path: Path) -> None:
    _write_prompt_module(tmp_path)
    rel = "backend/src/policy_atlas/runtime/planner.py"
    _write(
        tmp_path,
        rel,
        "from policy_atlas.runtime.planner_prompt import (\n"
        "    PLANNER_PROMPT_VERSION,\n"
        "    PLANNER_SYSTEM_PROMPT,\n"
        "    PlannerTurnWire,\n"
        "    build_planner_messages,\n"
        ")\n"
        "\n"
        "PLANNER_MODEL = 'gpt'\n"
        "\n"
        "\n"
        "class OpenAIPlannerBackend:\n"
        "    def run(self) -> PlannerTurnWire:\n"
        "        return build_planner_messages()\n",
    )

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    # The module path moves...
    assert "from policy_atlas.runtime.task_agent_prompt import (" in out
    # ...and every symbol the prompt module declares keeps its old name.
    for kept in (
        "PLANNER_PROMPT_VERSION",
        "PLANNER_SYSTEM_PROMPT",
        "PlannerTurnWire",
        "build_planner_messages",
    ):
        assert kept in out
    # Names the prompt module does not declare still rename.
    assert "TASK_AGENT_MODEL = 'gpt'" in out
    assert "class OpenAITaskAgentBackend:" in out


# --------------------------------------------------------------------------
# Docs mode
# --------------------------------------------------------------------------


def test_docs_mode_sweeps_code_spans_prose_phrases_and_the_abbreviation(
    tmp_path: Path,
) -> None:
    web_api = "docs/specs/system/web-api.md"
    _write(
        tmp_path,
        web_api,
        "## Planning turns\n"
        "\n"
        "`POST /api/v1/tasks/{id}/planning-turns` appends a planning turn to\n"
        "the planning conversation. The `planning_transcript` table stores it,\n"
        "and the reply comes from the planner. Re-planning visibility is unchanged.\n",
    )

    assert sweep.main(["--apply", "--docs", "--root", str(tmp_path)]) == 0
    out = (tmp_path / web_api).read_text(encoding="utf-8")

    # Code spans get the identifier pass (and the literal route rule).
    assert "`POST /api/v1/tasks/{id}/task-agent-turns`" in out
    assert "`task_agent_transcript`" in out
    # Prose gets the three phrase rules.
    assert "## Task Agent turns" in out
    assert "appends a Task Agent turn" in out
    assert "the Task Agent conversation" in out
    assert "the reply comes from the Task Agent." in out
    # Other prose uses of the word are left for the lead to read.
    assert "Re-planning visibility is unchanged." in out


def test_docs_mode_renames_eb_but_never_the_eb_handoff_citation(tmp_path: Path) -> None:
    rel = "docs/specs/index.md"
    _write(
        tmp_path,
        rel,
        "The EB specs distil the EB handoff §2. An EB run ends in synthesise.\n"
        "`eb_iof_base_v1` is a fingerprint; EBITDA and DEBT are not the abbreviation.\n",
    )

    assert sweep.main(["--apply", "--docs", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert "The ES specs distil the EB handoff §2. An ES run ends in synthesise." in out
    assert "EBITDA and DEBT are not the abbreviation." in out
    assert "`eb_iof_base_v1`" in out


def test_docs_mode_fixes_the_stale_capability_link(tmp_path: Path) -> None:
    rel = "docs/tasks/_templates/contract.md"
    _write(
        tmp_path,
        rel,
        "See [the capability](../../specs/capabilities/evidence-base/capability.md)\n"
        "for a non-EB slice.\n",
    )

    assert sweep.main(["--apply", "--docs", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert "../../specs/capabilities/evidence-search/capability.md" in out
    assert "for a non-ES slice." in out


def test_docs_mode_leaves_python_identifiers_to_phase_three(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/runner.py"
    _write(
        tmp_path,
        rel,
        '"""The EB capability-runner."""\n'
        "\n"
        "from policy_atlas.runtime.planner import PlannerBackend\n",
    )

    assert sweep.main(["--apply", "--docs", "--root", str(tmp_path)]) == 0
    out = (tmp_path / rel).read_text(encoding="utf-8")

    assert '"""The ES capability-runner."""' in out
    assert "from policy_atlas.runtime.planner import PlannerBackend" in out


# --------------------------------------------------------------------------
# File sets, idempotence and collisions
# --------------------------------------------------------------------------


def test_phase_file_sets_respect_the_exclusion_list(tmp_path: Path) -> None:
    _write_prompt_module(tmp_path)
    for rel in (
        "backend/src/policy_atlas/api/routers/planning.py",
        "backend/tests/api/test_planning_router.py",
        "backend/tests/core/test_migration_038.py",
        "backend/tests/core/test_planning_transcript_migration.py",
        "backend/alembic/env.py",
        "backend/alembic/versions/e9a7c3d1f6b4_planning.py",
        "backend/tests/scripts/test_rename_044.py",
        "scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py",
        "frontend/src/views/workspace/PlanningPane.tsx",
        "frontend/src/api/gen/types.ts",
        "frontend/e2e/journey.spec.ts",
        "frontend/node_modules/pkg/index.ts",
    ):
        _write(tmp_path, rel, "planner_id\n")

    # Tables built against this tree, so the prompt-module exclusion comes from
    # the `prompt_hashes.json` written above rather than the real repo's.
    engine = sweep.Engine(sweep.build_tables(tmp_path))
    backend = engine.phase_files(tmp_path, 3)
    assert "backend/src/policy_atlas/api/routers/planning.py" in backend
    assert "backend/tests/api/test_planning_router.py" in backend
    assert "backend/alembic/env.py" in backend
    assert "scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py" in backend
    assert "backend/tests/core/test_migration_038.py" not in backend
    assert "backend/tests/core/test_planning_transcript_migration.py" not in backend
    assert "backend/alembic/versions/e9a7c3d1f6b4_planning.py" not in backend
    assert "backend/tests/scripts/test_rename_044.py" not in backend
    # The pinned prompt module is excluded whole, read from prompt_hashes.json.
    assert PROMPT_MODULE not in backend

    frontend = engine.phase_files(tmp_path, 4)
    assert frontend == [
        "frontend/e2e/journey.spec.ts",
        "frontend/src/views/workspace/PlanningPane.tsx",
    ]


def test_apply_is_idempotent(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/runtime/planner.py"
    _write(tmp_path, rel, "PLANNER_MODEL = 'gpt'\nplanning_transcript = table\n")

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    first = (tmp_path / rel).read_text(encoding="utf-8")
    assert "TASK_AGENT_MODEL" in first

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == first

    ledger = sweep.ENGINE.tables.ledger
    assert (tmp_path / ledger).is_file()


def test_an_already_swept_tree_without_a_ledger_is_refused(tmp_path: Path) -> None:
    rel = "backend/src/policy_atlas/api/deps.py"
    body = "planner = None\n"
    _write(tmp_path, rel, body)
    _write(tmp_path, "backend/src/policy_atlas/core/schema.py", "task_agent_transcript = 1\n")

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8") == body

    assert sweep.main(["--apply", "--phase", "3", "--force", "--root", str(tmp_path)]) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == "task_agent = None\n"


def test_refuses_to_rename_onto_an_existing_symbol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rel = "backend/src/policy_atlas/api/deps.py"
    body = "def task_agent_row():\n    return 1\n\n\ndef planner_row():\n    return 2\n"
    _write(tmp_path, rel, body)

    assert sweep.main(["--apply", "--phase", "3", "--root", str(tmp_path)]) == 2
    assert (tmp_path / rel).read_text(encoding="utf-8") == body
    assert "collision" in capsys.readouterr().err

    assert sweep.main(["--scan", "--phase", "3", "--root", str(tmp_path)]) == 1


def test_scan_reports_the_table_and_zero_collisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        tmp_path,
        "backend/src/policy_atlas/runtime/planner.py",
        "PANE = PlanningPane\nID = planner_state\nNAME = ck_ptr_status\n",
    )

    assert sweep.main(["--scan", "--phase", "3", "--root", str(tmp_path)]) == 0
    report = capsys.readouterr().out

    assert "| `PlanningPane` | `TaskAgentPane` | 1 |" in report
    assert "| `planner_state` | `task_agent_state` | 1 |" in report
    assert "| `ck_ptr_status` | `ck_tat_status` | 1 |" in report
    assert "**None.** No proposed target already exists" in report
