"""CLI blocking-path pins (task 025, C.4).

The parking-seam design (docs/tasks/025-web-app-foundation/
parking-seam-design.md, §6/§7) puts the pause *disposition* in the IO seam,
not the runner: ``io.pause(...)`` either returns a ``SteeringResponse``
synchronously (blocking — the CLI's ``CliIO``, byte-identical today) or
raises the park control-flow exception (the new API IO). These pins exist so
that work — landing concurrently in ``runner.py`` /
``continuation_state.py`` — cannot silently change CLI behaviour:

(a) a scripted blocking IO receives the pause with the exact deterministic
    render text produced today for a known scripted walk;
(b) the pause -> Continue response path completes the walk with status
    "succeeded", and the walk's ``capability_run`` row is never left/seen at
    "paused" (the park-disposition status — a blocking IO must never trigger
    it);
(c) NullIO walks (the harness/test default) never block or park — they
    auto-continue through every attended pause and finish synchronously.

Walk-scripting idioms are reused from ``tests/runtime/test_orchestrate.py``
(``ScriptedConsole``, ``main``) and ``tests/runtime/test_runner.py``
(``_base_plan``, ``_seed_project``, ``_runner_backends``).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import capability_run
from policy_atlas.runtime.orchestrate import CliIO, main
from policy_atlas.runtime.runner import NullIO, run_plan
from policy_atlas.runtime.steering import build_steer_point_options
from tests.runtime.test_orchestrate import ScriptedConsole, _stub_backends
from tests.runtime.test_orchestrate import _cleanup as _orchestrate_cleanup
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_runner import _cleanup as _runner_cleanup

# --- (a) byte-identical blocking-pause render ------------------------------

# The exact console output ``CliIO.pause`` produces today for a known
# steer-point pause (steer point "synthesis_shape", one fired trigger, a
# compact bundle). Captured from the production render path; any change to
# this string is a CLI-visible behaviour change and must be a deliberate,
# reviewed diff — not a side effect of the park-disposition work.
_GOLDEN_PAUSE_MENU = "\n".join(
    [
        "synthesise: check-in pending",
        "Steer point: synthesis_shape",
        "Triggers fired: thin_coverage",
        "Evidence snapshot:",
        "  covered_strata: 2",
        "  findings: 14",
        "  total_strata: 5",
        "Steering options:",
        "  1) Continue",
        "  2) Synthesise as proposed — Proceed with the proposed synthesis plan "
        "unchanged.",
        "  3) Edit the synthesis sections — Set the synthesis sections yourself. "
        "Provide the section titles and focus.",
        "  4) Boost evidence type / quality tier in synthesis — Weight the "
        "synthesis retrieval toward stronger-appraised evidence (type/tier "
        "boosts; tag boosts are not offered).",
        "  5) Re-group at a different granularity (replaces grouping) — "
        "Re-group findings coarser or finer (D8); replaces the current "
        "grouping.",
        "  6) Re-group with guidance (replaces grouping) — Re-group findings "
        "with your guidance (B3); replaces the current grouping. Provide the "
        "guidance.",
        "  7) Change steering mode",
        "  8) Abort",
        "  (or type your own steering instruction)",
    ]
)


def _known_pause_payload() -> dict[str, Any]:
    """A pause payload shaped exactly as the runner assembles it (2409
    ``_pause_payload``) for the "synthesis_shape" steer point — the same
    shape ``test_orchestrate._steer_point_payload`` builds."""
    return {
        "kind": "steer_point",
        "steer_point": "synthesis_shape",
        "boundary": "before_component",
        "component": "synthesise",
        "options": build_steer_point_options(plan=None, point="synthesis_shape"),
        "triggers": [{"trigger": "thin_coverage", "detail": {"covered_strata": 2}}],
        "bundle": {"covered_strata": 2, "total_strata": 5, "findings": 14},
    }


def test_cli_blocking_pause_render_is_byte_identical() -> None:
    """CliIO.pause renders the known walk's header + steer-point + triggers +
    bundle + numbered options block byte-identically to today's production
    text. This is the pin: the park disposition must not touch this render."""
    console = ScriptedConsole(["1"])
    payload = _known_pause_payload()

    response = CliIO(console).pause(payload, "synthesise: check-in pending")

    # Exactly one menu was printed, and it is the printed message (no prompt
    # message interleaving before it — console.output[0] is the menu).
    assert console.output[0] == _GOLDEN_PAUSE_MENU
    # Continue ("1") maps to the Continue response, unchanged.
    from policy_atlas.runtime.steering import Continue

    assert isinstance(response, Continue)


def test_cli_blocking_pause_header_and_options_substrings() -> None:
    """Stable substring coverage (belt-and-braces alongside the byte-identical
    pin): the header line, steer-point line, trigger line, bundle lines and
    the options/frame lines are all present verbatim."""
    console = ScriptedConsole(["1"])
    payload = _known_pause_payload()

    CliIO(console).pause(payload, "synthesise: check-in pending")

    rendered = console.output[0]
    for expected_line in (
        "synthesise: check-in pending",
        "Steer point: synthesis_shape",
        "Triggers fired: thin_coverage",
        "Evidence snapshot:",
        "  covered_strata: 2",
        "Steering options:",
        "  1) Continue",
        "  7) Change steering mode",
        "  8) Abort",
        "  (or type your own steering instruction)",
    ):
        assert expected_line in rendered, expected_line


# --- (b) pause -> Continue completes; capability_run never "paused" -------


def _capability_run_statuses(engine: Engine, project_id: uuid.UUID) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(capability_run.c.status).where(capability_run.c.project_id == project_id)
        ).fetchall()
    return [row.status for row in rows]


def test_cli_pause_continue_completes_succeeded_no_paused_status(engine: Engine) -> None:
    """A full stub CLI walk answering Continue ("1") at every attended pause
    finishes with status "succeeded", and the walk's capability_run row is
    never left at "paused" — the park disposition (status="paused",
    ended_at left NULL) belongs to the API's park IO, never to CliIO."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",  # intent
                "1",  # pick suggestion 1
                "approve",  # plan review
                # Continue at every lattice pause a moderate deep run may
                # present (P1 fires per search round — two rounds on
                # zero-yield stubs, task 029 — plus P2/P3/P4); extra unused
                # continues are harmless.
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        assert result.exit_code == 0
        assert result.outcome is not None
        assert result.outcome.status == "succeeded"
        assert result.project_id is not None

        statuses = _capability_run_statuses(engine, result.project_id)
        assert statuses, "expected a capability_run row for the walk"
        assert "paused" not in statuses
        assert all(status == "succeeded" for status in statuses)
    finally:
        _orchestrate_cleanup(engine, result.project_id if result else None)


# --- (c) NullIO walks never pause/park -------------------------------------


def test_nullio_walk_never_pauses_and_never_parks(engine: Engine) -> None:
    """The default/harness IO (NullIO) auto-continues through every attended
    pause on a moderate-mode plan (which has attended lattice points) and
    completes synchronously to "succeeded" — it never blocks for input and
    never leaves capability_run at "paused"."""
    project_id, scope_id = _seed_project(engine)
    plan = _base_plan()  # steering_mode="moderate" -> has attended pause points
    try:
        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            plan_row_id=None,
            backends=_runner_backends(),
            io=NullIO(),
        )

        assert outcome.status == "succeeded"
        statuses = _capability_run_statuses(engine, project_id)
        assert statuses, "expected a capability_run row for the walk"
        assert "paused" not in statuses
        assert all(status == "succeeded" for status in statuses)
    finally:
        _runner_cleanup(engine, project_id)
