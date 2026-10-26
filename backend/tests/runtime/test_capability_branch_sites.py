"""Every place that branches on the kind of task has a reviewed theory-of-change decision.

Task 054, plan S6. A branch written for two kinds (``== OPTIONS_SCOPING``,
``!= EVIDENCE_SEARCH``, ``purpose == LONGLIST_PURPOSE``, ``isinstance(plan,
ScopingPlan)`` ...) silently sends a theory of change down one side. This test
finds every such branch in ``backend/src`` by AST and fails on one that is not
listed below with a decision. Adding a site: decide what a theory of change
needs there, then add it with that decision.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "policy_atlas"

#: Names and literals whose comparison is a branch on the kind of task or walk.
_COMPARED_NAMES = frozenset({"OPTIONS_SCOPING", "EVIDENCE_SEARCH", "LONGLIST_PURPOSE"})
_COMPARED_LITERALS = frozenset({"options_scoping", "evidence_search", "longlist"})
_PLAN_MODELS = frozenset({"ScopingPlan", "TaskPlan"})

#: (module, function) → (number of branches, the reviewed decision).
SITES: dict[tuple[str, str], tuple[int, str]] = {
    # Done in 054 step 1.2.
    ("runtime/runner.py", "_finish_run"): (
        1, "done 1.2: a toc walk abandons its item-search children, as a longlist walk"
    ),
    ("api/routers/_common.py", "_latest_run_row"): (
        1, "done 1.2: a ToC task's latest run leaves out child walks, as OS"
    ),
    ("runtime/agent.py", "persist_approved_plan"): (
        1, "done 1.2: a TocPlan writes purpose='toc', context.toc_walk='draft'"
    ),
    # Left for later steps.
    ("runtime/runner.py", "_run_plan_impl"): (
        1, "1.4: the toc item-search dispatch and join beside LONGLIST_PURPOSE"
    ),
    ("api/routers/runs.py", "_dispatch_run"): (
        1, "1.3: the draft → check follow-on (S4); longlist follow-on stays OS-only"
    ),
    ("api/routers/task_agent.py", "get_plan"): (
        1, "1.3: a ToC branch (today a ToC task falls to the Evidence search read)"
    ),
    ("api/routers/task_agent.py", "patch_plan"): (
        1, "1.3: a ToC branch (today a ToC task falls to the Evidence search patch)"
    ),
    ("api/routers/task_agent.py", "_paused_gate"): (
        1, "OS-only: a toc walk never pauses; turns during a check are S7 (1.3, 2.2)"
    ),
    ("runtime/runner.py", "leg_directive"): (
        2, "OS-only for now: inherited labels skip classify/appraise; ToC in 7 (C14)"
    ),
    ("api/chat_scope.py", "resolve_terminal_run_components"): (
        1, "increment 4: the discuss scope of a ToC task (today the ES read)"
    ),
    ("api/contract/tasks.py", "reject_links_on_an_evidence_search"): (
        1, "right for ToC until increment 7: a ToC create with from_task_ids is 422"
    ),
    ("api/routers/tasks.py", "_write_task_links"): (
        1, "right for ToC: a source must be an Evidence search; increment 7 adds options"
    ),
    # Right for a theory of change as they stand.
    ("api/routers/_common.py", "task_out"): (1, "OS-only: has_longlist"),
    ("api/longlist_actions.py", "admit_longlist_action"): (1, "OS-only route: ToC refused"),
    ("api/longlist_start.py", "admit_and_mint"): (1, "OS-only route: ToC refused"),
    ("api/longlist_start.py", "longlist_walk_exists"): (1, "OS-only: longlist walks"),
    ("api/longlist_turns.py", "read_longlist_surface"): (1, "OS-only: ToC has no longlist"),
    ("api/routers/check_ins.py", "respond_to_check_in"): (1, "OS-only: a toc walk never pauses"),
    ("api/routers/task_agent.py", "_dispatch_gate_turn"): (2, "OS-only: the baseline gate"),
    ("api/routers/task_agent.py", "_propose_patch_designs"): (1, "OS-only: option designs"),
    ("api/routers/task_agent.py", "confirm_baseline"): (1, "OS-only: ToC refused 422"),
    ("options_scoping/longlist/longlist.py", "current_profile_fingerprints"): (1, "OS module"),
    ("options_scoping/suggest/suggest.py", "walk_plan"): (1, "OS module"),
    ("runtime/capability_registry.py", "expect_task_plan"): (1, "the narrowing itself"),
    ("runtime/capability_registry.py", "expect_scoping_plan"): (1, "the narrowing itself"),
    ("runtime/harness.py", "_scope_tagging_context"): (1, "OS-only step"),
    ("runtime/option_search.py", "unattended_plan"): (1, "OS option search; 1.4 adds ToC's"),
    ("runtime/runner.py", "_section_budget"): (1, "ES-only field; None for ToC"),
    ("runtime/runner.py", "_search_backend_scope"): (1, "ToC searches both backends"),
    ("runtime/runner.py", "_baseline_gate_bundle"): (1, "OS-only: the baseline gate"),
    ("runtime/runner.py", "_watch_observe_boundary"): (1, "ES-only watch; ToC is structural"),
    ("runtime/runner.py", "_watch_header"): (1, "ES-only components; [] for ToC"),
    ("runtime/scoping_plan.py", "compose_scoping"): (1, "OS composer"),
    ("runtime/task_agent_scoping.py", "read_baseline_state"): (3, "OS module"),
    ("runtime/task_agent_scoping.py", "baseline_built_from"): (1, "OS module"),
}


def _is_branch(node: ast.AST) -> bool:
    if isinstance(node, ast.Compare):
        return any(
            (isinstance(n, ast.Name) and n.id in _COMPARED_NAMES)
            or (isinstance(n, ast.Constant) and n.value in _COMPARED_LITERALS)
            for n in ast.walk(node)
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and len(node.args) == 2
    ):
        return any(isinstance(n, ast.Name) and n.id in _PLAN_MODELS for n in ast.walk(node.args[1]))
    return False


def _sites(source: str) -> Counter[str]:
    """Count branch sites per enclosing function (``<module>`` outside one)."""
    found: Counter[str] = Counter()

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = (
                child.name
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                else function
            )
            if _is_branch(child):
                found[name] += 1
            visit(child, name)

    visit(ast.parse(source), "<module>")
    return found


def test_every_capability_branch_has_a_reviewed_theory_of_change_decision() -> None:
    found: dict[tuple[str, str], int] = {}
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        relative = path.relative_to(_SRC_ROOT).as_posix()
        for function, count in _sites(path.read_text()).items():
            found[(relative, function)] = count
    listed = {site: count for site, (count, _decision) in SITES.items()}
    assert found == listed, (
        "a branch on the kind of task was added, moved or removed; decide what a "
        "theory of change needs there and update SITES: "
        f"new or changed {sorted(set(found.items()) - set(listed.items()))}, "
        f"gone {sorted(set(listed.items()) - set(found.items()))}"
    )


def test_the_scanner_finds_each_kind_of_branch() -> None:
    source = """
def f(plan, row, purpose):
    if row["capability"] == OPTIONS_SCOPING: pass
    if purpose in (LONGLIST_PURPOSE, TOC_PURPOSE): pass
    if capability != "evidence_search": pass
    if isinstance(plan, ScopingPlan): pass
    x = LONGLIST_PURPOSE
"""
    assert _sites(source) == Counter({"f": 4})
