"""The ``option_profile`` component (task 046 amendment 2, Phase 12a; R37, S16, S17, S20).

Lever typing moved out of ``longlist`` into ``option_profile``, a spine step
between ``longlist`` and ``constrain``. The equivalence gate: on the same
fixture, the lever columns, the typing keys and the typing counts are the same
as before the move (the literals below were recorded on the code before it).
The typing tests that ``test_longlist`` held move here with what they assert;
``longlist`` writes no typing; the registry, the harness graph, the plan
mapping, ``LLM_BEARING_COMPONENTS``, the run stream and the stage map know
``option_profile``; a failed ``option_profile`` step fails the walk.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, get_args

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.contract.sse import STAGE_KEYS
from policy_atlas.api.contract.task_agent import PlanStageKey
from policy_atlas.api.routers import sse
from policy_atlas.api.stage_vocabulary import STAGE_BY_REGISTRY, STAGE_PRESENTATION
from policy_atlas.core import events
from policy_atlas.core.schema import longlist_result, option
from policy_atlas.options_scoping.longlist.lever_types import LEVER_TYPE_KEYS, TAXONOMY_VERSION
from policy_atlas.options_scoping.longlist.longlist_backend import StubLonglistBackend
from policy_atlas.options_scoping.option_profile.lever_typing_prompt import (
    build_lever_typing_messages,
)
from policy_atlas.options_scoping.option_profile.option_profile import (
    TYPING_INVALID_REASON,
    OptionProfileContext,
    OptionProfileFailure,
    option_profile_scope,
)
from policy_atlas.options_scoping.option_profile.option_profile_prompt import (
    AmbitionResponse,
    AmbitionWire,
    MarkedLineResponse,
    MarkedLineWire,
    SettingResponse,
    SettingWire,
    StandsOut,
    build_ambition_messages,
    build_line_messages,
    build_setting_messages,
)
from policy_atlas.runtime.harness import build_graph
from policy_atlas.runtime.run_spec import COMPONENT_REGISTRY, Plan, compile
from policy_atlas.runtime.runner import LLM_BEARING_COMPONENTS, NullIO, run_plan
from policy_atlas.runtime.scoping_plan import LONGLIST_CHAIN, PROFILE_LINE_KEYS
from policy_atlas.runtime.task_plan import OPTIONS_SCOPING_STEPS, registry_component_for
from tests.options_scoping.test_longlist import _Scripted, _Walk
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_compose_by_purpose import _set_purpose
from tests.runtime.test_runner import _cleanup, _runner_backends


def _profile(walk: _Walk, backend: Any) -> tuple[uuid.UUID, dict[str, Any]]:
    """One ``option_profile`` run of the walk; returns its run and summary."""
    run_id = walk.run()
    summary = option_profile_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=run_id,
        context=OptionProfileContext(scope_id=walk.scope_id, intent="longlist intent", context={}),
        backend=backend,
    )
    return run_id, summary


class _ProfiledWalk(_Walk):
    """A walk whose build runs ``longlist`` then ``option_profile``, as the chain does.

    ``build`` returns the ``longlist`` run and summary: that run's
    ``longlist_result`` row holds the typing ``option_profile`` merged in.
    """

    def build(self, backend: Any) -> tuple[uuid.UUID, dict[str, Any]]:
        run_id, summary = super().build(backend)
        _profile(self, backend)
        return run_id, summary


def _build(walk: _Walk, backend: Any) -> uuid.UUID:
    """One longlist build, as the walk runs it: ``longlist`` then
    ``option_profile``. Returns the longlist run (its row holds the typing)."""
    run_id, _summary = walk.build(backend)
    _profile(walk, backend)
    return run_id


# --- the equivalence gate -------------------------------------------------------------


def _snapshot(walk: _Walk, run_id: uuid.UUID) -> dict[str, Any]:
    """The typing a build left, with every option id replaced by its name."""
    rows = walk.options()
    names = {str(row.option_id): name for name, row in rows.items()}
    result = walk.result(run_id)
    provenance = result.provenance
    typing = dict(provenance["typing"])
    typing["kept_ids"] = sorted(names[i] for i in typing["kept_ids"])
    return {
        "options": {
            name: [
                row.primary_lever_type,
                list(row.secondary_lever_types),
                row.lever_none_fits_reason,
                row.taxonomy_version,
            ]
            for name, row in sorted(rows.items())
        },
        "lever_reason": {names[k]: v for k, v in provenance["lever_reason"].items()},
        "runner_up": {names[k]: v for k, v in provenance["runner_up"].items()},
        "typing": typing,
        "prompt_versions.typing": provenance["prompt_versions"]["typing"],
        "models.typing": provenance["models"]["typing"],
        "taxonomy_version": provenance["taxonomy_version"],
        "counts.typing_invalid": result.counts["typing_invalid"],
        "counts.none_fits": result.counts["none_fits"],
    }


def test_the_stub_typing_is_the_same_as_before_the_move(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee", origin="added_by_you")
    walk.option("Wage subsidy")
    walk.option("Work trial", state="excluded")
    doc = walk.doc()
    walk.record(doc, "Youth guarantee")
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])

    run_id = _build(walk, StubLonglistBackend())

    assert _snapshot(walk, run_id) == STUB_LITERAL


def test_the_scripted_typing_and_the_keep_previous_rule_are_the_same(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Free bus passes")
    walk.option("A new body")
    walk.option("Garbled")
    walk.option("Blank reason", origin="added_by_you")
    _build(
        walk,
        _Scripted(
            typings={
                "Free bus passes": {
                    "runner_up_lever_type": "inform",
                    "lever_reason": " The council pays the fares. ",
                },
                "A new body": {"primary_lever_type": None, "none_fits_reason": "It sets a mood."},
                "Garbled": {"primary_lever_type": "make it so"},
                "Blank reason": {"lever_reason": "   "},
            }
        ),
    )
    second = _build(
        walk,
        _Scripted(
            typings={
                "Free bus passes": {"primary_lever_type": "make it so"},
                "A new body": {"primary_lever_type": None, "none_fits_reason": None},
                "Blank reason": {
                    "lever_reason": "A grant to each household.",
                    "runner_up_lever_type": "regulate",
                },
            }
        ),
    )

    assert _snapshot(walk, second) == SCRIPTED_LITERAL


# --- typing (moved from test_longlist with what each asserts) --------------------------


def test_typing_one_primary_or_none_fits_the_version_and_the_ambition(
    conn: Connection,
) -> None:
    walk = _ProfiledWalk(conn)
    walk.option("Free bus passes")
    walk.option("A new body")
    walk.option("Garbled")
    walk.option("Wrong band")
    backend = _Scripted(
        typings={
            "Free bus passes": {"runner_up_lever_type": "provide a service"},
            "A new body": {"primary_lever_type": None, "none_fits_reason": "It sets a mood."},
            "Garbled": {"primary_lever_type": "make it so"},
            "Wrong band": {"primary_lever_type": None, "none_fits_reason": None},
        }
    )
    run_id, _ = walk.build(backend)
    options = walk.options()
    bus = options["Free bus passes"]
    assert bus.primary_lever_type in LEVER_TYPE_KEYS
    assert bus.secondary_lever_types == ["inform"]
    assert bus.taxonomy_version == TAXONOMY_VERSION
    # The ambition is the profile's own call now (R40): no mark from the stub.
    assert (bus.ambition, bus.ambition_reason) == (None, "Stub ambition.")
    assert options["A new body"].primary_lever_type is None
    assert options["A new body"].lever_none_fits_reason == "It sets a mood."
    # An invalid typing leaves the columns as they were (task 046, S12): here
    # never typed, so still empty.
    for name in ("Garbled", "Wrong band"):
        assert options[name].primary_lever_type is None
        assert options[name].lever_none_fits_reason is None
        assert options[name].taxonomy_version is None
        assert options[name].ambition is None
    # The two invalid typings count once, under typing_invalid (F14).
    result = walk.result(run_id)
    assert result.counts["none_fits"] == 1
    assert result.counts["typing_invalid"] == 2
    # The runner-up is in the record only; the wire has no reasons for it.
    assert result.provenance["runner_up"] == {
        str(bus.option_id): {"lever_type": "provide a service"}
    }
    # The typing prompt receives the plan and the baseline (item 9).
    typed = backend.calls["type"][0]
    assert typed["plan"]["target_unit"] == "16 to 24 year olds"
    assert typed["baseline_sections"] == []
    assert "runner_up" not in dict(bus._mapping)
    assert "provide a service" not in bus.secondary_lever_types


def test_a_failed_typing_call_is_counted_never_a_crash(conn: Connection) -> None:
    walk = _ProfiledWalk(conn)
    walk.option("Youth guarantee")

    class _Broken(_Scripted):
        def type_options(self, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

    run_id, _ = walk.build(_Broken())
    result = walk.result(run_id)
    assert result.counts["none_fits"] == 0
    assert result.counts["typing_invalid"] == 1
    assert result.provenance["typing"]["failed_batches"] == 1
    # The option's columns are left as they were (task 046, S12).
    row = walk.options()["Youth guarantee"]
    assert (row.lever_none_fits_reason, row.taxonomy_version) == (None, None)
    assert row.lever_none_fits_reason != TYPING_INVALID_REASON
    # The step still succeeds: the profile is written (Phase 12b).
    assert set(result.option_profile) == {str(row.option_id)}


def test_typing_batches_run_in_parallel(conn: Connection) -> None:
    walk = _ProfiledWalk(conn)
    for i in range(41):  # three batches of at most 20
        walk.option(f"Seed option {i}", origin="added_by_you")
    barrier = threading.Barrier(3, timeout=10)

    class _Together(_Scripted):
        def type_options(self, **kwargs: Any) -> Any:
            barrier.wait()  # only passes when the three batches are in flight at once
            return super().type_options(**kwargs)

    backend = _Together()
    run_id, _ = walk.build(backend)
    typing = walk.result(run_id).provenance["typing"]
    assert (typing["calls"], typing["failed_batches"], typing["invalid"]) == (3, 0, 0)
    assert all(row.primary_lever_type == "subsidise" for row in walk.options().values())


def test_an_invalid_typing_keeps_the_previous_values_version_and_runner_up(
    conn: Connection,
) -> None:
    walk = _ProfiledWalk(conn)
    walk.option("Free bus passes")
    walk.build(_Scripted(typings={"Free bus passes": {"runner_up_lever_type": "inform"}}))
    before = walk.options()["Free bus passes"]
    # Typed under the earlier list: the version must survive a failed typing.
    conn.execute(
        option.update()
        .where(option.c.option_id == before.option_id)
        .values(taxonomy_version="lever_types_v1")
    )
    run_id, _ = walk.build(
        _Scripted(typings={"Free bus passes": {"primary_lever_type": "make it so"}})
    )
    after = walk.options()["Free bus passes"]
    assert (after.primary_lever_type, after.ambition, after.ambition_reason) == (
        before.primary_lever_type,
        before.ambition,
        before.ambition_reason,
    )
    assert after.secondary_lever_types == before.secondary_lever_types
    assert after.taxonomy_version == "lever_types_v1"
    result = walk.result(run_id)
    assert result.counts["typing_invalid"] == 1
    assert result.provenance["typing"]["kept_ids"] == [str(before.option_id)]
    assert result.provenance["runner_up"] == {
        str(before.option_id): {"lever_type": "inform", "carried_forward": True}
    }


def test_the_lever_reason_is_stored_and_a_kept_typing_carries_it_forward(
    conn: Connection,
) -> None:
    """R29: each option's lever reason sits beside the runner-up, kept like it."""
    walk = _ProfiledWalk(conn)
    walk.option("Free bus passes")
    walk.option("Blank reason")
    walk.option("Garbled")
    first = walk.build(
        _Scripted(
            typings={
                "Free bus passes": {"lever_reason": " The council pays the fares. "},
                "Blank reason": {"lever_reason": "   "},
                "Garbled": {"primary_lever_type": "make it so"},
            }
        )
    )[0]
    ids = {name: str(row.option_id) for name, row in walk.options().items()}
    # A blank reason is not stored and never makes the typing invalid; an
    # invalid typing stores none.
    assert walk.result(first).provenance["lever_reason"] == {
        ids["Free bus passes"]: "The council pays the fares."
    }
    assert walk.options()["Blank reason"].primary_lever_type == "subsidise"
    # The next build's typing fails for bus passes: its earlier reason stays.
    # A new valid reason replaces the old one.
    second = walk.build(
        _Scripted(
            typings={
                "Free bus passes": {"primary_lever_type": "make it so"},
                "Blank reason": {"lever_reason": "A grant to each household."},
                "Garbled": {"primary_lever_type": "make it so"},
            }
        )
    )[0]
    assert walk.result(second).provenance["lever_reason"] == {
        ids["Free bus passes"]: "The council pays the fares.",
        ids["Blank reason"]: "A grant to each household.",
    }


def test_the_stub_backend_types_every_option(conn: Connection) -> None:
    """The assertions ``test_longlist``'s stub test made on typing, after the move."""
    walk = _ProfiledWalk(conn)
    walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "Youth guarantee")
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])
    walk.build(StubLonglistBackend())
    options = walk.options()
    assert len(options) == 2
    assert all(row.primary_lever_type == "provide a service" for row in options.values())
    assert all(row.ambition is None for row in options.values())
    assert all(row.ambition_reason == "Stub ambition." for row in options.values())


# --- the component --------------------------------------------------------------------


def test_longlist_writes_no_typing(conn: Connection) -> None:
    """S20: ``longlist`` leaves every lever column and the ambition empty and
    writes no typing key; the row reads as an untyped list until the profile."""
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "Youth guarantee")
    walk.record(doc, "something else")
    walk.rollup(walk.scope_id, [doc])
    run_id, summary = walk.build(StubLonglistBackend())
    assert "none_fits" not in summary
    for row in walk.options().values():
        assert (row.primary_lever_type, row.lever_none_fits_reason, row.taxonomy_version) == (
            None,
            None,
            None,
        )
        assert row.secondary_lever_types == []
        assert (row.ambition, row.ambition_reason) == (None, None)
    result = walk.result(run_id)
    for key in ("typing", "runner_up", "lever_reason", "taxonomy_version", "option_profile"):
        assert key not in result.provenance
    assert "typing" not in result.provenance["prompt_versions"]
    assert "typing" not in result.provenance["models"]
    assert "none_fits" not in result.counts and "typing_invalid" not in result.counts
    assert result.option_profile == {}


def test_the_profile_merges_into_the_row_and_types_every_option_not_merged(
    conn: Connection,
) -> None:
    """S16, S17: every option not merged, included or not, in created order;
    the typing keys merged into the row, its other keys kept."""
    walk = _Walk(conn)
    first = walk.option("Youth guarantee")
    excluded = walk.option("Wage subsidy", state="excluded")
    merged = walk.option("Work trial", merged_into_option_id=first)
    run_id, _ = walk.build(_Scripted())
    before = walk.result(run_id)
    backend = _Scripted()
    profile_run, summary = _profile(walk, backend)
    assert summary == {"options": 2, "typed": 2, "kept": 0, "invalid": 0, "profiled": 2}
    typed = [option_["unit_id"] for call in backend.calls["type"] for option_ in call["options"]]
    assert typed == [str(first), str(excluded)]
    rows = {row.option_id: row for row in walk.options().values()}
    assert rows[merged].primary_lever_type is None
    assert rows[excluded].primary_lever_type == "subsidise"
    after = walk.result(run_id)
    assert after.coverage == before.coverage
    assert after.counts == {
        **before.counts,
        "none_fits": 0,
        "typing_invalid": 0,
        "profiled": 2,
    }
    assert after.provenance["seed_ids"] == before.provenance["seed_ids"]
    assert after.provenance["prompt_versions"]["cluster"] == (
        before.provenance["prompt_versions"]["cluster"]
    )
    assert set(after.provenance["models"]) == {"discovery", "assignment", "typing"}
    no_marks = {"less": 0, "more": 0, "none": 2}
    assert after.provenance["option_profile"] == {
        "run_id": str(profile_run),
        "backend_mode": "stub",
        "usage_totals": after.provenance["option_profile"]["usage_totals"],
        "prompt_version": "option_profile_v1",
        "model": "stub",
        "records_max": 5,
        "calls": 10,
        "retries": 0,
        "marks": dict.fromkeys(PROFILE_LINE_KEYS, no_marks),
        "ambition_marks": no_marks,
    }


def test_kept_counts_only_an_option_that_was_typed_before(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Free bus passes")
    _build(walk, _Scripted())
    walk.option("A new option")
    failing = _Scripted(
        typings={
            "Free bus passes": {"primary_lever_type": "make it so"},
            "A new option": {"primary_lever_type": "make it so"},
        }
    )
    walk.build(failing)
    _, summary = _profile(walk, failing)
    # Both typings are invalid; only the option typed before keeps a typing,
    # the new one's lever columns stay null.
    assert summary == {"options": 2, "typed": 0, "kept": 1, "invalid": 2, "profiled": 2}
    assert walk.options()["A new option"].primary_lever_type is None
    assert walk.options()["Free bus passes"].primary_lever_type == "subsidise"


def test_option_profile_without_a_longlist_fails(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    with pytest.raises(OptionProfileFailure):
        _profile(walk, StubLonglistBackend())


# --- the lines, the ambition and the setting (Phase 12b; R36, R40, R41, S16, S17) ------


def _column(walk: _Walk, run_id: uuid.UUID) -> dict[str, Any]:
    column: dict[str, Any] = walk.result(run_id).option_profile
    return column


def _marked(**marks: StandsOut) -> MarkedLineResponse:
    """A marked line response; ``marks`` maps a short id to its ``stands_out``."""
    return MarkedLineResponse(
        options=[
            MarkedLineWire(option_id=short_id, answer=f" Line for {short_id}. ", stands_out=mark)
            for short_id, mark in marks.items()
        ]
    )


def _three(walk: _Walk) -> dict[str, uuid.UUID]:
    """Three options, o1 to o3 in created order."""
    return {
        "o1": walk.option("Free bus passes"),
        "o2": walk.option("A new body"),
        "o3": walk.option("Work trial"),
    }


def test_each_line_is_written_for_every_option_not_merged(conn: Connection) -> None:
    walk = _Walk(conn)
    first = walk.option("Youth guarantee")
    excluded = walk.option("Wage subsidy", state="excluded")
    merged = walk.option("Work trial", merged_into_option_id=first)
    run_id, _ = walk.build(_Scripted())
    _, summary = _profile(walk, StubLonglistBackend())
    column = _column(walk, run_id)
    # An excluded option gets its profile; a merged one gets none (final § 2.3).
    assert set(column) == {str(first), str(excluded)}
    assert str(merged) not in column
    for option_id in (first, excluded):
        entry = column[str(option_id)]
        assert list(entry) == ["1"]  # the design version
        lines = entry["1"]["lines"]
        # JSONB keeps no key order: the reader orders by PROFILE_LINE_KEYS.
        assert set(lines) == set(PROFILE_LINE_KEYS)
        for line_key, line in lines.items():
            assert line == {"sentence": f"Stub {line_key} sentence.", "mark": None}
        assert entry["1"]["setting"] == {"main": "stub setting", "second": None}
    result = walk.result(run_id)
    assert summary["profiled"] == result.counts["profiled"] == 2


def test_the_marks_are_stored_as_given_and_two_lines_never_carry_one(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _three(walk)
    run_id, _ = walk.build(_Scripted())
    everyone_more = _marked(o1="more", o2="more", o3="more")
    backend = StubLonglistBackend(
        line_responses={
            "cost": _marked(o1="less", o2="more", o3="no"),
            "who_decides": everyone_more,
            "dependencies": everyone_more,
        }
    )
    _profile(walk, backend)
    column = _column(walk, run_id)
    cost = {short: column[str(ids[short])]["1"]["lines"]["cost"] for short in ids}
    assert cost == {
        "o1": {"sentence": "Line for o1.", "mark": "less"},
        "o2": {"sentence": "Line for o2.", "mark": "more"},
        "o3": {"sentence": "Line for o3.", "mark": None},
    }
    for option_id in ids.values():
        lines = column[str(option_id)]["1"]["lines"]
        assert lines["who_decides"]["mark"] is None
        assert lines["dependencies"]["mark"] is None
    marks = walk.result(run_id).provenance["option_profile"]["marks"]
    assert marks["cost"] == {"less": 1, "more": 1, "none": 1}
    assert marks["who_decides"] == marks["dependencies"] == {"less": 0, "more": 0, "none": 3}
    assert marks["workforce"] == {"less": 0, "more": 0, "none": 3}


def test_the_ambition_is_less_more_or_null_with_the_reason_on_every_option(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _three(walk)
    run_id, _ = walk.build(_Scripted())
    backend = StubLonglistBackend(
        ambition_responses=AmbitionResponse(
            options=[
                AmbitionWire(option_id="o1", reason=" A small change. ", stands_out="less"),
                AmbitionWire(option_id="o2", reason="A new system.", stands_out="more"),
                AmbitionWire(option_id="o3", reason="Something new beside.", stands_out="no"),
            ]
        )
    )
    _profile(walk, backend)
    rows = {row.option_id: row for row in walk.options().values()}
    assert [(rows[ids[s]].ambition, rows[ids[s]].ambition_reason) for s in ("o1", "o2", "o3")] == [
        ("less", "A small change."),
        ("more", "A new system."),
        (None, "Something new beside."),
    ]
    provenance = walk.result(run_id).provenance["option_profile"]
    assert provenance["ambition_marks"] == {"less": 1, "more": 1, "none": 1}


def test_the_setting_is_lower_cased_and_a_null_main_setting_gives_two_nulls(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _three(walk)
    run_id, _ = walk.build(_Scripted())
    backend = StubLonglistBackend(
        setting_responses=SettingResponse(
            options=[
                SettingWire(option_id="o1", main_setting=" School ", second_setting="Home"),
                SettingWire(option_id="o2", main_setting=None, second_setting=None),
                SettingWire(option_id="o3", main_setting="GP surgery", second_setting=None),
            ]
        )
    )
    _profile(walk, backend)
    column = _column(walk, run_id)
    assert [column[str(ids[s])]["1"]["setting"] for s in ("o1", "o2", "o3")] == [
        {"main": "school", "second": "home"},
        {"main": None, "second": None},
        {"main": "gp surgery", "second": None},
    ]


def test_where_reaches_the_who_decides_call_and_no_other(conn: Connection) -> None:
    where = "Powys"
    walk = _Walk(conn, plan=scoping_plan(where={"text": where, "origin": "your_call"}))
    walk.option("Youth guarantee")
    walk.option("Wage subsidy")
    walk.build(_Scripted())
    profiler = StubLonglistBackend()
    backend = _Scripted(profiler=profiler)
    _profile(walk, backend)

    assert sorted(profiler.line_calls) == sorted(PROFILE_LINE_KEYS)
    assert {i["line_key"]: i["where"] for i in profiler.line_inputs} == {
        line_key: (where if line_key == "who_decides" else None) for line_key in PROFILE_LINE_KEYS
    }
    # The built messages: Where is in the who_decides call and in no other.
    by_line = {
        i["line_key"]: build_line_messages(
            line_key=i["line_key"],
            plan=i["plan"],
            where=i["where"],
            baseline_sections=i["baseline_sections"],
            options=i["options"],
        )
        for i in profiler.line_inputs
    }
    assert where in str(by_line.pop("who_decides"))
    others: list[Any] = list(by_line.values())
    others.append(build_ambition_messages(**profiler.ambition_inputs[0]))
    others.append(build_setting_messages(**profiler.setting_inputs[0]))
    others.extend(
        build_lever_typing_messages(
            options=call["options"], plan=call["plan"], baseline_sections=call["baseline_sections"]
        )
        for call in backend.calls["type"]
    )
    for messages in others:
        assert where not in str(messages)


def test_the_option_list_holds_only_the_named_keys_and_five_records_in_role_order(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    walk.option("Wage subsidy")
    doc = walk.doc()
    long_text = "youth guarantee " + "x" * 120
    roles = ["mentioned", "recommended", "described", "evaluated", "mentioned", "evaluated"]
    for index, role in enumerate(roles):
        walk.record(
            doc,
            long_text if index == 3 else f"youth guarantee {index}",
            role=role,
            design_features=["a", "b", "c", "d"],
            study_geography="Denmark",
            unit="young people",
        )
    walk.rollup(walk.scope_id, [doc])
    routes = {f"youth guarantee {i}": ("Youth guarantee", False) for i in range(len(roles))}
    routes[long_text] = ("Youth guarantee", False)
    walk.build(_Scripted(routes=routes))
    profiler = StubLonglistBackend()
    _profile(walk, profiler)

    inputs = [
        *(i["options"] for i in profiler.line_inputs),
        *(i["options"] for i in profiler.ambition_inputs),
        *(i["options"] for i in profiler.setting_inputs),
    ]
    assert len(inputs) == 10
    assert all(payload == inputs[0] for payload in inputs)  # one list for all ten calls
    payload = inputs[0]
    assert [o["option_id"] for o in payload] == ["o1", "o2"]
    assert [o["label"] for o in payload] == ["Youth guarantee", "Wage subsidy"]
    for option_ in payload:
        assert set(option_) == {
            "option_id",
            "label",
            "description",
            "design_features",
            "evidence_records",
        }
        for record in option_["evidence_records"]:
            assert set(record) == {"intervention", "role", "features"}
    records = payload[0]["evidence_records"]
    assert [r["role"] for r in records] == [
        "evaluated",
        "evaluated",
        "described",
        "recommended",
        "mentioned",
    ]
    assert records[0]["intervention"] == long_text[:100]
    assert all(r["features"] == ["a", "b", "c"] for r in records)
    assert payload[1]["evidence_records"] == []


_BAD_LINES: dict[str, Any] = {
    "a missing option": _marked(o1="no", o2="no"),
    "an option twice": MarkedLineResponse(
        options=[*_marked(o1="no", o2="no", o3="no").options, *_marked(o1="no").options]
    ),
    "another id": _marked(o1="no", o2="no", o3="no", o4="no"),
    "a blank sentence": MarkedLineResponse(
        options=[
            MarkedLineWire(option_id=s, answer="  " if s == "o2" else "A line.", stands_out="no")
            for s in ("o1", "o2", "o3")
        ]
    ),
}


@pytest.mark.parametrize("bad", list(_BAD_LINES))
def test_a_line_call_malformed_twice_fails_the_step_and_writes_nothing(
    conn: Connection, bad: str
) -> None:
    walk = _Walk(conn)
    _three(walk)
    run_id, _ = walk.build(_Scripted())
    _profile(walk, StubLonglistBackend())
    before_column = _column(walk, run_id)
    before_rows = {name: tuple(row) for name, row in walk.options().items()}
    before_result = walk.result(run_id)

    backend = StubLonglistBackend(
        line_responses={"coordination": _BAD_LINES[bad]},
        ambition_responses=AmbitionResponse(
            options=[
                AmbitionWire(option_id=s, reason="Bigger.", stands_out="more")
                for s in ("o1", "o2", "o3")
            ]
        ),
    )
    with pytest.raises(OptionProfileFailure, match="coordination"):
        _profile(walk, backend)
    assert backend.line_calls["coordination"] == 2
    assert _column(walk, run_id) == before_column
    assert {name: tuple(row) for name, row in walk.options().items()} == before_rows
    after_result = walk.result(run_id)
    assert (after_result.counts, after_result.provenance) == (
        before_result.counts,
        before_result.provenance,
    )


@pytest.mark.parametrize(
    "bad_setting",
    [
        SettingWire(option_id="o3", main_setting="  ", second_setting=None),
        SettingWire(option_id="o3", main_setting=None, second_setting="home"),
        SettingWire(option_id="o3", main_setting="school", second_setting=" "),
    ],
)
def test_a_malformed_setting_fails_the_step(conn: Connection, bad_setting: SettingWire) -> None:
    walk = _Walk(conn)
    _three(walk)
    walk.build(_Scripted())
    good = [
        SettingWire(option_id=s, main_setting="school", second_setting=None) for s in ("o1", "o2")
    ]
    backend = StubLonglistBackend(
        setting_responses=SettingResponse(options=[*good, bad_setting])
    )
    with pytest.raises(OptionProfileFailure, match="setting"):
        _profile(walk, backend)
    assert backend.setting_calls == 2


def test_a_call_malformed_once_then_right_succeeds_with_the_retry_counted(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _three(walk)
    run_id, _ = walk.build(_Scripted())
    backend = StubLonglistBackend(
        line_responses={
            "cost": [_BAD_LINES["a missing option"], _marked(o1="less", o2="no", o3="no")]
        }
    )
    _profile(walk, backend)
    assert backend.line_calls["cost"] == 2
    assert all(backend.line_calls[k] == 1 for k in PROFILE_LINE_KEYS if k != "cost")
    assert walk.result(run_id).provenance["option_profile"]["retries"] == 1
    assert _column(walk, run_id)[str(ids["o1"])]["1"]["lines"]["cost"]["mark"] == "less"


def test_a_call_that_raises_once_is_tried_again(conn: Connection) -> None:
    walk = _Walk(conn)
    _three(walk)
    run_id, _ = walk.build(_Scripted())

    class _FlakyAmbition(StubLonglistBackend):
        raised = False

        def profile_ambition(self, **kwargs: Any) -> Any:
            if not self.raised:
                self.raised = True
                raise RuntimeError("provider down")
            return super().profile_ambition(**kwargs)

    _profile(walk, _FlakyAmbition())
    assert walk.result(run_id).provenance["option_profile"]["retries"] == 1


def test_a_call_that_raises_twice_fails_the_step(conn: Connection) -> None:
    walk = _Walk(conn)
    _three(walk)
    walk.build(_Scripted())

    class _Down(StubLonglistBackend):
        def profile_setting(self, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

    with pytest.raises(OptionProfileFailure, match="setting"):
        _profile(walk, _Down())


# --- the registries -------------------------------------------------------------------


def test_the_registry_the_graph_the_plan_mapping_and_the_stream_know_option_profile() -> None:
    assert COMPONENT_REGISTRY["option_profile"] == {"requires": ["evidence_scope_id"]}
    compile(Plan(component="option_profile", evidence_scope_id=uuid.uuid4()))
    assert "option_profile" in OPTIONS_SCOPING_STEPS
    assert registry_component_for("option_profile") == "option_profile"
    assert "option_profile" in build_graph().get_graph().nodes
    assert "option_profile" in LLM_BEARING_COMPONENTS
    assert STAGE_BY_REGISTRY["option_profile"] == "option_profile"
    assert "option_profile" in STAGE_KEYS
    assert "option_profile" in get_args(PlanStageKey)
    assert STAGE_PRESENTATION["option_profile"] == (
        "Writing what each option would take",
        "What each option would take, and what kind of action it is.",
    )
    chain = [component for component, _ in LONGLIST_CHAIN]
    assert chain[-4:] == ["longlist", "option_profile", "constrain", "theme"]
    assert dict(LONGLIST_CHAIN)["option_profile"] is True


# --- the walk -------------------------------------------------------------------------


def _longlist_walk(engine: Engine) -> tuple[uuid.UUID, Any]:
    task_id, scope_id = seed_scoping_task(engine)
    _set_purpose(engine, scope_id, "longlist")
    plan = scoping_plan(steering_mode="moderate")
    plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
    )
    return task_id, outcome


def test_option_profile_runs_between_longlist_and_constrain(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, outcome = _longlist_walk(engine)
        assert outcome.status == "succeeded"
        components = [step.component for step in outcome.steps]
        assert components[-4:] == ["longlist", "option_profile", "constrain", "theme"]
        step = outcome.steps[-3]
        assert step.status == "succeeded"
        with engine.connect() as conn:
            result = conn.execute(
                select(longlist_result).where(longlist_result.c.task_id == task_id)
            ).one()
            log = events.read(conn, task_id)
            rows = [entry for entry in log if entry["run_id"] == step.run_id]
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert result.provenance["option_profile"]["run_id"] == str(step.run_id)
        assert result.provenance["typing"]["invalid"] == 0
        stages = [(frame["type"], frame.get("stage")) for frame in frames]
        assert ("stage.started", "option_profile") in stages
        assert ("stage.completed", "option_profile") in stages
    finally:
        _cleanup(engine, task_id)


def test_a_failed_option_profile_step_fails_the_walk(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spine step (S20): the walk fails and no later step runs."""

    def _down(*args: Any, **kwargs: Any) -> Any:
        raise OptionProfileFailure("option_profile: down")

    monkeypatch.setattr("policy_atlas.runtime.harness.option_profile_scope", _down)
    task_id: uuid.UUID | None = None
    try:
        task_id, outcome = _longlist_walk(engine)
        assert outcome.status == "failed"
        statuses = {step.component: step.status for step in outcome.steps}
        assert statuses["longlist"] == "succeeded"
        assert statuses["option_profile"] == "failed"
        assert "constrain" not in statuses and "theme" not in statuses
    finally:
        _cleanup(engine, task_id)


# The literals, recorded on the code before the move (Phase 12a). Phase 12b
# took the ambition columns out of them (ambition is the profile's own call,
# R40) and moved the typing prompt to ``lever_typing_v3``.
_STUB_ROW: list[Any] = ["provide a service", [], None, "lever_types_v2"]

STUB_LITERAL: dict[str, Any] = {
    "options": {
        "Stub discovered option": _STUB_ROW,
        "Wage subsidy": _STUB_ROW,
        "Work trial": _STUB_ROW,
        "Youth guarantee": _STUB_ROW,
    },
    "lever_reason": {
        "Stub discovered option": "Stub lever reason.",
        "Wage subsidy": "Stub lever reason.",
        "Work trial": "Stub lever reason.",
        "Youth guarantee": "Stub lever reason.",
    },
    "runner_up": {},
    "typing": {
        "calls": 1,
        "batch_size": 20,
        "max_concurrent": 4,
        "failed_batches": 0,
        "invalid": 0,
        "kept_ids": [],
    },
    "prompt_versions.typing": "lever_typing_v3",
    "models.typing": "stub",
    "taxonomy_version": "lever_types_v2",
    "counts.typing_invalid": 0,
    "counts.none_fits": 0,
}

SCRIPTED_LITERAL: dict[str, Any] = {
    "options": {
        "A new body": [None, ["inform"], "It sets a mood.", "lever_types_v2"],
        "Blank reason": ["subsidise", ["inform"], None, "lever_types_v2"],
        "Free bus passes": ["subsidise", ["inform"], None, "lever_types_v2"],
        "Garbled": ["subsidise", ["inform"], None, "lever_types_v2"],
    },
    "lever_reason": {
        "A new body": "The council pays for the scheme.",
        "Blank reason": "A grant to each household.",
        "Free bus passes": "The council pays the fares.",
        "Garbled": "The council pays for the scheme.",
    },
    "runner_up": {
        "Blank reason": {"lever_type": "regulate"},
        "Free bus passes": {"lever_type": "inform", "carried_forward": True},
    },
    "typing": {
        "calls": 1,
        "batch_size": 20,
        "max_concurrent": 4,
        "failed_batches": 0,
        "invalid": 2,
        "kept_ids": ["A new body", "Free bus passes"],
    },
    "prompt_versions.typing": "lever_typing_v3",
    "models.typing": "stub",
    "taxonomy_version": "lever_types_v2",
    "counts.typing_invalid": 2,
    # Counted over this build's valid typings: the kept none-fits is not.
    "counts.none_fits": 0,
}
