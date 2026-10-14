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
from pydantic import ValidationError
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
from policy_atlas.options_scoping.option_profile.folding_prompt import FoldingResponse, FoldWire
from policy_atlas.options_scoping.option_profile.lever_typing_prompt import (
    build_lever_typing_messages,
)
from policy_atlas.options_scoping.option_profile.option_profile import (
    TYPING_INVALID_REASON,
    OptionProfileContext,
    OptionProfileFailure,
    _checked_folds,
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
from policy_atlas.options_scoping.option_profile.place_sentences_prompt import (
    PlaceSentencesResponse,
    PlaceSentenceWire,
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
    # The step still succeeds: the profile is written (Phase 12b), and the
    # folding maps at list level (task 046, amendment 3, S21).
    assert set(result.option_profile) == {str(row.option_id), "folds"}


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
    # The folded keys are merged into each option's coverage (S21); the
    # rest is as the build wrote it.
    folded_keys = {"outcome_counts", "place_sentences"}
    assert set(after.coverage) == set(before.coverage)
    for option_id, entry in after.coverage.items():
        assert {k: v for k, v in entry.items() if k not in folded_keys} == {
            k: v for k, v in before.coverage[option_id].items() if k not in folded_keys
        }
        assert folded_keys <= set(entry)
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
        "prompt_version": "option_profile_v3",
        "model": "stub",
        "records_max": 5,
        "calls": 10,
        "retries": 0,
        "marks": dict.fromkeys(PROFILE_LINE_KEYS, no_marks),
        "ambition_marks": no_marks,
        "folding": after.provenance["option_profile"]["folding"],
        "place_sentences": after.provenance["option_profile"]["place_sentences"],
    }
    assert after.provenance["option_profile"]["folding"]["prompt_version"] == "folding_v8"
    # No option has an evaluating document: no place-sentence call (S31).
    assert all(entry["place_sentences"] == [] for entry in after.coverage.values())
    assert after.provenance["option_profile"]["place_sentences"]["calls"] == 0


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
    # The folding maps sit beside them, at list level (S21).
    assert set(column) == {str(first), str(excluded), "folds"}
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


def test_the_who_can_act_texts_reach_the_who_decides_call_and_no_other(conn: Connection) -> None:
    """Task 046, amendment 4 (R89; S35; contract review C1)."""
    texts = ["Only the council can act", "Not the Treasury"]
    constraints = [
        {
            "text": text,
            "kind": "consideration",
            "checked_at": "assessment",
            "origin": "your_call",
            "aspect": "who_decides",
            "hard": True,
        }
        for text in texts
    ]
    walk = _Walk(conn, plan=scoping_plan(constraints=constraints))
    walk.option("Youth guarantee")
    walk.option("Wage subsidy")
    walk.build(_Scripted())
    profiler = StubLonglistBackend()
    _profile(walk, _Scripted(profiler=profiler))

    assert {i["line_key"]: i["considerations"] for i in profiler.line_inputs} == {
        line_key: (texts if line_key == "who_decides" else None) for line_key in PROFILE_LINE_KEYS
    }
    who_decides = next(i for i in profiler.line_inputs if i["line_key"] == "who_decides")
    user = str(
        build_line_messages(
            line_key="who_decides",
            plan=who_decides["plan"],
            where=who_decides["where"],
            baseline_sections=who_decides["baseline_sections"],
            options=who_decides["options"],
            considerations=who_decides["considerations"],
        )[1]["content"]
    )
    assert all(text in user for text in texts)


def test_a_plan_without_a_who_can_act_constraint_sends_no_texts(conn: Connection) -> None:
    walk = _Walk(conn, plan=scoping_plan(where={"text": "Powys", "origin": "your_call"}))
    walk.option("Youth guarantee")
    walk.build(_Scripted())
    profiler = StubLonglistBackend()
    _profile(walk, _Scripted(profiler=profiler))

    assert {i["considerations"] for i in profiler.line_inputs} == {None}
    who_decides = next(i for i in profiler.line_inputs if i["line_key"] == "who_decides")
    with_none = build_line_messages(
        line_key="who_decides",
        plan=who_decides["plan"],
        where=who_decides["where"],
        baseline_sections=who_decides["baseline_sections"],
        options=who_decides["options"],
    )
    assert "in the user's own words" not in str(with_none)


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
    "prompt_versions.typing": "lever_typing_v4",
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
    "prompt_versions.typing": "lever_typing_v4",
    "models.typing": "stub",
    "taxonomy_version": "lever_types_v2",
    "counts.typing_invalid": 2,
    # Counted over this build's valid typings: the kept none-fits is not.
    "counts.none_fits": 0,
}


# --- the folding calls (task 046, amendment 3, R54, R55; S21) -------------------------


def _folding_walk(walk: _Walk) -> dict[str, uuid.UUID]:
    """Two options; seven records under the first (more than the profile's five),
    one under the second. Units and outcomes as the folding calls read them."""
    ids = {"yg": walk.option("Youth guarantee"), "ws": walk.option("Wage subsidy")}
    first, second, third = walk.doc(), walk.doc(), walk.doc()
    rows: list[tuple[uuid.UUID, str, str | None, str | None, str | None, str]] = [
        (first, "youth guarantee 0", "16 to 24 Year Olds", "NEET rate", "other", "evaluated"),
        (first, "youth guarantee 1", "young adults", "neet status", None, "evaluated"),
        (first, "youth guarantee 2", "Young adults", "employment", "other", "described"),
        (second, "youth guarantee 3", "school leavers", "employment", "other", "evaluated"),
        (second, "youth guarantee 4", "parents", "wellbeing", "the NEET rate", "described"),
        (second, "youth guarantee 5", "employers", None, None, "mentioned"),
        (second, "youth guarantee 6", "graduates", "earnings", "other", "recommended"),
        (third, "wage subsidy", "firms", "the neet rate", "other", "evaluated"),
    ]
    for doc, intervention, unit, outcome, outcome_tag, role in rows:
        walk.record(
            doc, intervention, unit=unit, outcome=outcome, outcome_tag=outcome_tag, role=role
        )
    walk.rollup(walk.scope_id, [first, second, third])
    return ids


def _folding_routes() -> _Scripted:
    routes = {f"youth guarantee {i}": ("Youth guarantee", False) for i in range(7)}
    routes["wage subsidy"] = ("Wage subsidy", False)
    return _Scripted(routes=routes)


def _fold_response(**kinds: str) -> FoldingResponse:
    """A folding answer (the ``folding_v3`` wire): the distinct kinds listed
    once, each word answered by its kind's index."""
    listed = list(dict.fromkeys(kinds.values()))
    return FoldingResponse(
        kinds=listed,
        folds=[
            FoldWire(word_id=word_id, kind=listed.index(kind)) for word_id, kind in kinds.items()
        ],
    )


def test_the_folding_calls_read_every_member_s_words_not_five(conn: Connection) -> None:
    walk = _Walk(conn)
    _folding_walk(walk)
    backend = _folding_routes()
    walk.build(backend)
    _profile(walk, backend)
    inputs = {i["facet"]: i for i in backend.profiler.fold_inputs}
    assert backend.profiler.fold_calls == {"tried_on": 1, "measures": 1}
    # Every member of every option, sorted, one spelling per case-folded word;
    # the bare mention ("employers") is thinned away, so it is no member.
    assert inputs["tried_on"]["words"] == {
        "w1": "16 to 24 Year Olds",
        "w2": "firms",
        "w3": "graduates",
        "w4": "parents",
        "w5": "school leavers",
        "w6": "Young adults",
    }
    assert inputs["measures"]["words"] == {
        "w1": "earnings",
        "w2": "employment",
        "w3": "NEET rate",
        "w4": "neet status",
        "w5": "the neet rate",
        "w6": "wellbeing",
    }
    # The plan as the other calls read it (place stripped): target unit and outcomes.
    assert inputs["measures"]["plan"]["target_unit"] == "16 to 24 year olds"
    assert inputs["measures"]["plan"]["outcomes"] == ["the NEET rate"]


def test_the_stub_folds_each_word_to_itself_lower_cased_or_to_its_plan_text() -> None:
    backend = StubLonglistBackend()
    plan: dict[str, object] = {"target_unit": "16 to 24 year olds", "outcomes": ["the NEET rate"]}
    words = {"w1": "16 To 24 Year Olds", "w2": "Young Adults", "w3": "THE neet RATE"}
    response, _ = backend.fold(facet="tried_on", plan=plan, words=words)
    assert response.kinds == ["16 to 24 year olds", "young adults", "the NEET rate"]
    assert [(f.word_id, f.kind) for f in response.folds] == [("w1", 0), ("w2", 1), ("w3", 2)]
    again, _ = backend.fold(facet="tried_on", plan=plan, words=words)
    assert again == response


def test_the_maps_are_stored_at_list_level_and_the_kinds_merged_into_coverage(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _folding_walk(walk)
    backend = _folding_routes()
    run_id, _ = walk.build(backend)
    before = walk.result(run_id)
    _profile(walk, backend)
    after = walk.result(run_id)
    column = after.option_profile
    assert set(column) == {str(ids["yg"]), str(ids["ws"]), "folds"}
    # The stub: each word lower-cased, a plan text where one matches.
    assert column["folds"] == {
        "tried_on": {
            "16 to 24 Year Olds": "16 to 24 year olds",
            "firms": "firms",
            "graduates": "graduates",
            "parents": "parents",
            "school leavers": "school leavers",
            "Young adults": "young adults",
        },
        "measures": {
            "earnings": "earnings",
            "employment": "employment",
            "NEET rate": "neet rate",
            "neet status": "neet status",
            "the neet rate": "the NEET rate",
            "wellbeing": "wellbeing",
        },
    }
    coverage = after.coverage[str(ids["yg"])]
    # The old keys stay as the build wrote them (constrain reads them).
    for key in ("tried_on", "settings"):
        assert coverage[key] == before.coverage[str(ids["yg"])][key]
    # These records carry no tag of this plan's context (read as not tagged):
    # every kind that is not the plan outcome is an ``other`` row.
    assert coverage["outcome_counts"]["other"] == [
        {"kind": "employment", "documents": 2, "evaluated": 1},
        {"kind": "earnings", "documents": 1, "evaluated": 0},
        {"kind": "neet rate", "documents": 1, "evaluated": 1},
        {"kind": "neet status", "documents": 1, "evaluated": 1},
        {"kind": "wellbeing", "documents": 1, "evaluated": 0},
    ]
    assert coverage["outcome_counts"]["by_outcome"] == [
        {"outcome": "the NEET rate", "documents": 0, "evaluated": 0}
    ]
    wage = after.coverage[str(ids["ws"])]
    # An ``other`` record whose kind is the plan outcome counts on its row, not
    # under ``other``.
    assert wage["outcome_counts"]["by_outcome"] == [
        {"outcome": "the NEET rate", "documents": 1, "evaluated": 1}
    ]
    assert wage["outcome_counts"]["other"] == []
    folding = after.provenance["option_profile"]["folding"]
    assert folding == {
        "prompt_version": "folding_v8",
        "model": "stub",
        "calls": 2,
        "retries": 0,
        "words": {"tried_on": 6, "measures": 6},
        "kinds": {"tried_on": 6, "measures": 6},
        "kinds_returned": {"tried_on": 6, "measures": 6},
        "guard_rewrites": {"tried_on": 0, "measures": 0},
        "slash_cuts": {"tried_on": 0, "measures": 0},
        "catch_all": {"tried_on": False, "measures": False},
    }


def test_a_missing_word_keeps_its_text_an_unknown_id_is_dropped_and_a_plan_kind_is_exact(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    _folding_walk(walk)
    routes = _folding_routes()
    run_id, _ = walk.build(routes)
    profiler = StubLonglistBackend(
        fold_responses={
            # w1 is left out; w9 is not in the input; the plan outcome comes
            # back in another case.
            "measures": _fold_response(
                w2="Jobs", w3="THE NEET RATE", w4="the neet rate", w9="made up"
            ),
        }
    )
    _profile(walk, _Scripted(routes=routes.routes, profiler=profiler))
    folds = walk.result(run_id).option_profile["folds"]["measures"]
    assert folds == {
        "earnings": "earnings",
        "employment": "Jobs",
        "NEET rate": "the NEET rate",
        "neet status": "the NEET rate",
        # Left out, and the plan outcome in its own words: the plan's text.
        "the neet rate": "the NEET rate",
        "wellbeing": "wellbeing",
    }
    assert "made up" not in folds.values()


def test_a_folding_call_invalid_twice_fails_the_step_and_writes_nothing(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    _folding_walk(walk)
    routes = _folding_routes()
    run_id, _ = walk.build(routes)
    _profile(walk, routes)
    before = walk.result(run_id)
    before_rows = {name: tuple(row) for name, row in walk.options().items()}
    # One id, two indexes: invalid; so is an answer with no input id.
    conflicting = FoldingResponse(
        kinds=["a", "b"],
        folds=[FoldWire(word_id="w1", kind=0), FoldWire(word_id="w1", kind=1)],
    )
    profiler = StubLonglistBackend(
        fold_responses={"tried_on": [conflicting, _fold_response(w99="b")]}
    )
    with pytest.raises(OptionProfileFailure, match="tried_on folding"):
        _profile(walk, _Scripted(routes=routes.routes, profiler=profiler))
    assert profiler.fold_calls["tried_on"] == 2
    after = walk.result(run_id)
    assert (after.option_profile, after.coverage, after.provenance, after.counts) == (
        before.option_profile,
        before.coverage,
        before.provenance,
        before.counts,
    )
    assert {name: tuple(row) for name, row in walk.options().items()} == before_rows


def test_a_folding_call_invalid_once_then_right_succeeds(conn: Connection) -> None:
    walk = _Walk(conn)
    _folding_walk(walk)
    routes = _folding_routes()
    run_id, _ = walk.build(routes)
    profiler = StubLonglistBackend(
        fold_responses={"measures": [_fold_response(w42="x"), _fold_response(w2="jobs")]}
    )
    _profile(walk, _Scripted(routes=routes.routes, profiler=profiler))
    assert profiler.fold_calls["measures"] == 2
    result = walk.result(run_id)
    assert result.option_profile["folds"]["measures"]["employment"] == "jobs"
    assert result.provenance["option_profile"]["folding"]["retries"] == 1
    assert result.provenance["option_profile"]["retries"] == 0


def test_an_index_out_of_range_or_a_blank_kind_keeps_the_word_s_text(conn: Connection) -> None:
    walk = _Walk(conn)
    _folding_walk(walk)
    routes = _folding_routes()
    run_id, _ = walk.build(routes)
    answer = FoldingResponse(
        kinds=["jobs", "  "],
        folds=[
            FoldWire(word_id="w1", kind=7),  # out of range
            FoldWire(word_id="w2", kind=0),
            FoldWire(word_id="w6", kind=1),  # a blank kind
            FoldWire(word_id="w4", kind=-1),  # out of range
        ],
    )
    profiler = StubLonglistBackend(fold_responses={"measures": answer})
    _profile(walk, _Scripted(routes=routes.routes, profiler=profiler))
    folds = walk.result(run_id).option_profile["folds"]["measures"]
    assert folds == {
        "earnings": "earnings",
        "employment": "jobs",
        "NEET rate": "NEET rate",
        "neet status": "neet status",
        "the neet rate": "the NEET rate",
        "wellbeing": "wellbeing",
    }


def _guard_answer(*kinds: str) -> FoldingResponse:
    """One word per kind: ``w1`` answered by the first kind, and so on."""
    return FoldingResponse(
        kinds=list(kinds),
        folds=[FoldWire(word_id=f"w{i}", kind=i - 1) for i in range(1, len(kinds) + 1)],
    )


def test_the_guard_maps_a_kind_holding_a_plan_outcome_to_it_on_the_measures_facet() -> None:
    """Task 046, amendment 4 (R86; S34; contract review C12): the survey's case."""
    outcome = "Prevalence of obesity at reception"
    answer = _guard_answer("prevalence of obesity at reception rates", "obesity measures")
    checked = _checked_folds(
        answer, {"w1": "a", "w2": "b"}, [outcome], facet="measures"
    )
    assert checked is not None
    assert checked["folds"] == {"a": outcome, "b": "obesity measures"}
    assert checked["guard_rewrites"] == 1


def test_the_guard_matches_whole_words_and_takes_the_longest_outcome() -> None:
    """C12: ``employment`` is not inside ``unemployment``; two matches, the longer wins."""
    answer = _guard_answer("unemployment", "youth employment outcomes", "employment rates")
    checked = _checked_folds(
        answer,
        {"w1": "a", "w2": "b", "w3": "c"},
        ["employment", "youth employment"],
        facet="measures",
    )
    assert checked is not None
    assert checked["folds"] == {"a": "unemployment", "b": "youth employment", "c": "employment"}
    assert checked["guard_rewrites"] == 2


def test_the_guard_never_runs_on_the_tried_on_facet() -> None:
    answer = _guard_answer("children aged 5")
    checked = _checked_folds(answer, {"w1": "a"}, ["children"], facet="tried_on")
    assert checked is not None
    assert checked["folds"] == {"a": "children aged 5"}
    assert checked["guard_rewrites"] == 0


def test_an_answer_over_twelve_kinds_is_refused_by_the_wire() -> None:
    """20L round 3: the ceiling is a schema constraint (``kinds`` at most 12), not a rule the
    model may ignore; an answer with 13 kinds never parses, so the call is retried as invalid."""
    with pytest.raises(ValidationError):
        FoldingResponse(
            kinds=[f"kind {i}" for i in range(13)],
            folds=[FoldWire(word_id=f"w{i}", kind=i) for i in range(1, 7)],
        )
    assert FoldingResponse.model_fields["kinds"].metadata[0].max_length == 12

def _catch_all_answer(words: dict[str, str], kind: str = "people") -> FoldingResponse:
    """Every word folded to one kind (a catch-all answer)."""
    return FoldingResponse(kinds=[kind], folds=[FoldWire(word_id=w, kind=0) for w in words])


def test_a_catch_all_fold_is_flagged_on_twenty_words_or_more() -> None:
    words = {f"w{i}": f"unit {i}" for i in range(1, 21)}
    checked = _checked_folds(_catch_all_answer(words), words, [], facet="tried_on")
    assert checked is not None
    assert checked["catch_all"] is True
    # Below the minimum, or below the share, it is not a catch-all.
    few = {f"w{i}": f"unit {i}" for i in range(1, 6)}
    checked = _checked_folds(_catch_all_answer(few), few, [], facet="tried_on")
    assert checked is not None and checked["catch_all"] is False
    half = FoldingResponse(
        kinds=["a", "b"],
        folds=[FoldWire(word_id=w, kind=i % 2) for i, w in enumerate(words)],
    )
    checked = _checked_folds(half, words, [], facet="tried_on")
    assert checked is not None and checked["catch_all"] is False


def test_a_kind_joined_by_slashes_is_cut_at_the_first_and_counted() -> None:
    """Task 046, amendment 4 (the folding loop's round 7): the mini model answers
    a cap with "obesity / overweight / BMI"; the first member names the kind,
    and the cut is counted in provenance (review of task 046, 2026-10-12)."""
    words = {"w1": "obesity", "w2": "bmi"}
    answer = FoldingResponse(
        kinds=["obesity / overweight / BMI", "weight"],
        folds=[FoldWire(word_id="w1", kind=0), FoldWire(word_id="w2", kind=1)],
    )
    checked = _checked_folds(answer, words, [], facet="measures")
    assert checked is not None
    assert checked["folds"] == {"obesity": "obesity", "bmi": "weight"}
    assert checked["slash_cuts"] == 1


def test_a_catch_all_answer_is_tried_once_more_and_the_retry_is_kept(conn: Connection) -> None:
    """Task 046, amendment 4 (the folding loop's round 9): one retry, then the
    answer stands whatever it holds; the step never fails on a catch-all."""
    walk = _Walk(conn)
    ids = {"yg": walk.option("Youth guarantee")}
    docs = [walk.doc() for _ in range(20)]
    for index, doc in enumerate(docs):
        walk.record(
            doc, f"youth guarantee {index}", unit=f"unit {index}", outcome=None, role="evaluated"
        )
    walk.rollup(walk.scope_id, docs)
    routes = {f"youth guarantee {i}": ("Youth guarantee", False) for i in range(20)}
    backend = _Scripted(routes=routes)
    run_id, _summary = walk.build(backend)
    words = {f"w{i}": f"unit {i - 1}" for i in range(1, 21)}
    # The first answer is a catch-all; the second folds every word to itself.
    backend.profiler._fold_queues["tried_on"] = [
        _catch_all_answer(words),
        FoldingResponse(
            kinds=[f"kind {k}" for k in range(12)],
            folds=[FoldWire(word_id=w, kind=i % 12) for i, w in enumerate(words)],
        ),
    ]
    _profile(walk, backend)
    folding = walk.result(run_id).provenance["option_profile"]["folding"]
    assert backend.profiler.fold_calls["tried_on"] == 2
    assert folding["retries"] == 1
    assert folding["catch_all"]["tried_on"] is False
    assert folding["kinds"]["tried_on"] == 12
    assert ids["yg"] is not None


def test_a_catch_all_answer_twice_is_kept_and_recorded(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("Youth guarantee")
    docs = [walk.doc() for _ in range(20)]
    for index, doc in enumerate(docs):
        walk.record(
            doc, f"youth guarantee {index}", unit=f"unit {index}", outcome=None, role="evaluated"
        )
    walk.rollup(walk.scope_id, docs)
    backend = _Scripted(
        routes={f"youth guarantee {i}": ("Youth guarantee", False) for i in range(20)}
    )
    run_id, _summary = walk.build(backend)
    words = {f"w{i}": f"unit {i - 1}" for i in range(1, 21)}
    backend.profiler._fold_queues["tried_on"] = [_catch_all_answer(words), _catch_all_answer(words)]
    _profile(walk, backend)
    folding = walk.result(run_id).provenance["option_profile"]["folding"]
    assert backend.profiler.fold_calls["tried_on"] == 2
    assert folding["retries"] == 1
    assert folding["catch_all"]["tried_on"] is True
    assert folding["kinds"]["tried_on"] == 1


# --- the place sentences (task 046, amendment 4, R80; S31; rubric box 76) ------------


class _Placed(_Scripted):
    """The scripted backend with the place-sentence call (the stub's) as well."""

    def place_sentences(self, **kwargs: Any) -> Any:
        return self.profiler.place_sentences(**kwargs)


def _place_walk(walk: _Walk, *, france: bool = False) -> dict[str, uuid.UUID]:
    """Two options. "Youth guarantee": evaluated in the United Kingdom (two
    documents) and Canada, described in Germany (and evaluated in France when
    asked). "Wage subsidy": described only."""
    ids = {"yg": walk.option("Youth guarantee"), "ws": walk.option("Wage subsidy")}
    uk_trial, uk_eval, canada, germany = walk.doc(), walk.doc(), walk.doc(), walk.doc()
    wage = walk.doc()
    walk.classify(uk_trial, "RCTs and Quasi-Experimental Studies", 4)
    walk.classify(uk_eval, "Observational Research Studies", 3)
    rows: list[tuple[uuid.UUID, str, dict[str, Any]]] = [
        (
            uk_trial,
            "youth guarantee 0",
            {
                "study_country": "UK",
                "study_geography": "Leeds",
                "unit": "16 to 24 year olds",
                "outcome": "NEET rate",
                "programme_name": "Youth Guarantee Trial",
            },
        ),
        (
            uk_eval,
            "youth guarantee 1",
            {"study_country": "United Kingdom", "unit": "school leavers"},
        ),
        (canada, "youth guarantee 2", {"study_country": "Canada", "outcome": "employment"}),
        (germany, "youth guarantee 3", {"study_country": "Germany", "role": "described"}),
        (wage, "wage subsidy", {"study_country": "France", "role": "described"}),
    ]
    docs = [uk_trial, uk_eval, canada, germany, wage]
    if france:
        paris = walk.doc()
        docs.append(paris)
        rows.append((paris, "youth guarantee 4", {"study_country": "France"}))
    for doc, intervention, values in rows:
        walk.record(doc, intervention, **values)
    walk.rollup(walk.scope_id, docs)
    return ids


def _place_backend(responses: Any = None) -> _Placed:
    routes = {f"youth guarantee {i}": ("Youth guarantee", False) for i in range(5)}
    routes["wage subsidy"] = ("Wage subsidy", False)
    return _Placed(
        routes=routes, profiler=StubLonglistBackend(place_sentence_responses=responses)
    )


def _place_stats(**counts: int) -> dict[str, int]:
    return {
        "generated": 0,
        "template": 0,
        "failed_trace": 0,
        "failed_length": 0,
        "failed_call": 0,
        **counts,
    }


def test_the_place_sentences_are_stored_in_the_card_order_with_their_provenance(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _place_walk(walk)
    backend = _place_backend()
    run_id, _ = walk.build(backend)
    _profile(walk, backend)
    after = walk.result(run_id)
    # One call: the option with no evaluating document gets none and no lines.
    assert backend.profiler.place_sentence_calls == 1
    (sent,) = backend.profiler.place_sentence_inputs
    assert sent["option"]["name"] == "Youth guarantee"
    assert sent["plan"] == {
        "target_unit": "16 to 24 year olds",
        "target_unit_short": "16 to 24 year olds",
        "outcomes": ["the NEET rate"],
    }
    assert set(sent["vocabulary"]) == {"tried_on_kinds", "measures_kinds"}
    # The plan's Where (the United Kingdom) first; the describing document absent;
    # short ids across the option.
    assert [(p["place_id"], p["place"], p["documents_total"]) for p in sent["places"]] == [
        ("p1", "United Kingdom", 2),
        ("p2", "Canada", 1),
    ]
    assert [d["id"] for p in sent["places"] for d in p["documents"]] == ["d1", "d2", "d3"]
    first = sent["places"][0]["documents"][0]
    assert first == {
        "id": "d1",
        "programme_name": "Youth Guarantee Trial",
        "unit": "16 to 24 year olds",
        "tried_on_kind": "16 to 24 year olds",
        "setting": None,
        "outcome": "NEET rate",
        "measured": "neet rate",
        "study_geography": "Leeds",
        "tier": "Strong",
        "evidence_type": "trial",
        "year": None,
    }
    assert after.coverage[str(ids["yg"])]["place_sentences"] == [
        {
            "place": "United Kingdom",
            "sentence": "2 evaluations in United Kingdom.",
            "generated": True,
            "where": True,
            "reason": None,
        },
        {
            "place": "Canada",
            "sentence": "1 evaluations in Canada.",
            "generated": True,
            "where": False,
            "reason": None,
        },
    ]
    assert after.coverage[str(ids["ws"])]["place_sentences"] == []
    stats = after.provenance["option_profile"]["place_sentences"]
    assert isinstance(stats.pop("seconds"), float)
    assert stats == {
        "prompt_version": "place_sentences_v5",
        "model": "stub",
        "calls": 1,
        "retries": 0,
        "options_without_evaluations": 1,
        **_place_stats(generated=2),
    }
    # Remade on a rebuild: the next profile run writes its own sentences.
    backend.profiler._place_sentence_queue = [
        PlaceSentencesResponse(
            places=[
                PlaceSentenceWire(
                    place_id="p1", sentence="Two evaluations in Leeds and elsewhere."
                ),
                PlaceSentenceWire(place_id="p2", sentence="One evaluation."),
            ]
        )
    ]
    _profile(walk, backend)
    remade = walk.result(run_id).coverage[str(ids["yg"])]["place_sentences"]
    assert [entry["sentence"] for entry in remade] == [
        "Two evaluations in Leeds and elsewhere.",
        "One evaluation.",
    ]


def test_an_invalid_answer_after_one_retry_leaves_templates_and_the_step_writes(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _place_walk(walk)
    duplicate = PlaceSentencesResponse(
        places=[
            PlaceSentenceWire(place_id="p1", sentence="2 evaluations."),
            PlaceSentenceWire(place_id="p1", sentence="2 evaluations."),
        ]
    )
    backend = _place_backend(["not a response", duplicate])
    run_id, _ = walk.build(backend)
    _profile(walk, backend)
    after = walk.result(run_id)
    assert backend.profiler.place_sentence_calls == 2
    entries = after.coverage[str(ids["yg"])]["place_sentences"]
    assert [entry["generated"] for entry in entries] == [False, False]
    assert entries[1]["sentence"] == "1 document measuring employment."
    stats = after.provenance["option_profile"]["place_sentences"]
    assert (stats["calls"], stats["retries"]) == (1, 1)
    assert {key: stats[key] for key in _place_stats()} == _place_stats(template=2, failed_call=1)
    # The step's other writes land.
    assert str(ids["yg"]) in after.option_profile
    assert walk.options()["Youth guarantee"].ambition_reason == "Stub ambition."


def test_a_call_that_raises_twice_leaves_templates_and_never_fails_the_step(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _place_walk(walk)
    backend = _place_backend(RuntimeError("provider down"))
    run_id, _ = walk.build(backend)
    _summary = _profile(walk, backend)
    after = walk.result(run_id)
    entries = after.coverage[str(ids["yg"])]["place_sentences"]
    assert [entry["place"] for entry in entries] == ["United Kingdom", "Canada"]
    assert not any(entry["generated"] for entry in entries)
    stats = after.provenance["option_profile"]["place_sentences"]
    assert stats["failed_call"] == 1 and stats["retries"] == 1


def test_a_call_that_scripted_backends_lack_is_a_failed_call(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _place_walk(walk)
    routes = {f"youth guarantee {i}": ("Youth guarantee", False) for i in range(5)}
    backend = _Scripted(routes={**routes, "wage subsidy": ("Wage subsidy", False)})
    run_id, _ = walk.build(backend)
    _profile(walk, backend)
    after = walk.result(run_id)
    assert after.provenance["option_profile"]["place_sentences"]["failed_call"] == 1
    assert len(after.coverage[str(ids["yg"])]["place_sentences"]) == 2


def test_a_place_left_out_an_unknown_id_a_long_and_an_untraced_sentence(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _place_walk(walk, france=True)
    answer = PlaceSentencesResponse(
        places=[
            PlaceSentenceWire(place_id="p1", sentence="Two evaluations " + "x" * 220 + "."),
            PlaceSentenceWire(place_id="p2", sentence="  Seven evaluations measured employment. "),
            PlaceSentenceWire(place_id="p9", sentence="1 evaluations in Spain."),
            # p3 (France) is left out.
        ]
    )
    backend = _place_backend(answer)
    run_id, _ = walk.build(backend)
    _profile(walk, backend)
    after = walk.result(run_id)
    entries = after.coverage[str(ids["yg"])]["place_sentences"]
    assert [(entry["place"], entry["generated"]) for entry in entries] == [
        ("United Kingdom", False),
        ("Canada", False),
        ("France", False),
    ]
    assert entries[2]["sentence"] == "1 document."
    stats = after.provenance["option_profile"]["place_sentences"]
    assert {key: stats[key] for key in _place_stats()} == _place_stats(
        template=3, failed_length=1, failed_trace=1
    )
    # The over-length sentence was refused once and the retry's answer kept.
    assert stats["retries"] == 1
    # Each template entry says why it stands (review of task 046, 2026-10-12).
    assert [entry["reason"] for entry in entries] == ["length", "number", "missing"]
    # A sentence within the ceiling that passes is kept, stripped.
    backend.profiler._place_sentence_queue = [
        PlaceSentencesResponse(
            places=[
                PlaceSentenceWire(
                    place_id="p2", sentence="  One evaluation measured employment. "
                )
            ]
        )
    ]
    _profile(walk, backend)
    entries = walk.result(run_id).coverage[str(ids["yg"])]["place_sentences"]
    assert entries[1] == {
        "place": "Canada",
        "sentence": "One evaluation measured employment.",
        "generated": True,
        "where": False,
        "reason": None,
    }

