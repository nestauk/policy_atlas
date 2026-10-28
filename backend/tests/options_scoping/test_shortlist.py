"""The ``shortlist`` component and its walks (task 055, items 3-5; plan P4-P8).

Contract acceptance, items 3 and 4: the longlist chain ends in ``shortlist``
after ``theme``; a failed ``shortlist`` ends the walk ``degraded`` with the
themes stored and the previous places kept; the shortlist walk runs the one
component; the checks re-ask once with the failure named, then fail; the
shuffle is reproducible; excluded options are never candidates and reach the
input as one line each; the character ceiling cuts document lines and counts
the cut; the component reads the task-wide newest longlist from a
shortlist-purpose intent record; the event carries the whole proposal; the
places rules at the chain end and at Suggest more.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.readmodels.card_text import CardText
from policy_atlas.core import events
from policy_atlas.core.schema import evidence_scope, longlist_result, option
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.longlist.longlist_backend import StubLonglistBackend
from policy_atlas.options_scoping.shortlist import shortlist as shortlist_module
from policy_atlas.options_scoping.shortlist.shortlist import (
    PLACES_TARGET,
    SHORTLIST_PROPOSED,
    ShortlistFailure,
    shortlist_scope,
    shuffled,
)
from policy_atlas.options_scoping.shortlist.shortlist_prompt import (
    SHORTLIST_PROMPT_VERSION,
    ShortlistPickWire,
    ShortlistWire,
)
from policy_atlas.runtime import harness
from policy_atlas.runtime.runner import NullIO, run_plan
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_CHAIN,
    SHORTLIST_CHAIN,
    SHORTLIST_PURPOSE,
    compose_scoping,
)
from tests.helpers import now
from tests.options_scoping.test_constrain import (
    SCREEN_IDS,
    _constrain,
    _pairs,
    _requirement,
    _response,
)
from tests.options_scoping.test_longlist import _Scripted, _Walk
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_compose_by_purpose import _set_purpose
from tests.runtime.test_runner import _cleanup, _runner_backends

# --- helpers ---------------------------------------------------------------------------


def _listed(walk: _Walk, names: list[str]) -> dict[str, uuid.UUID]:
    """Included options under the given names, and a longlist row built over them."""
    ids = {name: walk.option(name) for name in names}
    walk.build(_Scripted())
    return ids


def _shortlist(
    walk: _Walk, backend: Any, *, suggest: bool = False
) -> tuple[uuid.UUID, dict[str, Any]]:
    """Run ``shortlist`` under its own shortlist-purpose intent record."""
    context: dict[str, Any] = {"suggest": True} if suggest else {}
    scope_id = walk._scope(SHORTLIST_PURPOSE, context)
    run_id = walk.run(walk._walk(scope_id))
    summary = shortlist_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=run_id,
        context=ScopeContext(scope_id=scope_id, intent="shortlist", context=context),
        backend=backend,
    )
    return run_id, summary


def _set(walk: _Walk, option_id: uuid.UUID, **values: Any) -> None:
    walk.conn.execute(option.update().where(option.c.option_id == option_id).values(**values))


def _states(walk: _Walk) -> dict[str, tuple[str | None, str | None]]:
    return {
        row.name: (row.shortlist_state, row.shortlist_reason)
        for row in walk.conn.execute(select(option).where(option.c.task_id == walk.task_id))
    }


def _user_text(backend: StubLonglistBackend, call: int = 0) -> str:
    return str(backend.inputs["shortlist"][call][1]["content"])


def _ids_in_user_order(text: str) -> list[str]:
    block = text[text.index("Candidates (data") :]
    return [line[4:] for line in block.splitlines() if line.startswith("id: o")]


def _name_of(text: str, short_id: str) -> str:
    lines = text.splitlines()
    return lines[lines.index(f"id: {short_id}") + 1].removeprefix("## ")


def _wire(picks: list[tuple[str, str]], note: str = "A note.") -> ShortlistWire:
    return ShortlistWire(
        picks=[ShortlistPickWire(option_id=oid, reason=reason) for oid, reason in picks],
        note=note,
    )


# --- the chains -----------------------------------------------------------------------


def test_the_longlist_chain_ends_in_shortlist_after_theme_not_spine() -> None:
    assert LONGLIST_CHAIN[-2:] == (("theme", False), ("shortlist", False))
    assert SHORTLIST_CHAIN == (("shortlist", False),)
    chain = compose_scoping(scoping_plan(), SHORTLIST_PURPOSE)
    assert chain.components == ["shortlist"]
    assert [step.is_spine for step in chain.steps] == [False]


def test_the_harness_runs_shortlist_on_the_longlist_backend() -> None:
    # The other registration points are checked with theme's and option_profile's
    # in test_theme's registry test.
    assert harness._SCOPING_STEPS["shortlist"] == (shortlist_scope, "longlist_backend")


def test_two_named_seeds_give_two_known_different_orders() -> None:
    first = uuid.UUID("00000000-0000-4000-8000-000000000001")
    second = uuid.UUID("00000000-0000-4000-8000-000000000002")
    items = list("abcdef")
    assert shuffled(items, run_id=first, attempt=1) == ["c", "a", "f", "d", "e", "b"]
    assert shuffled(items, run_id=second, attempt=1) == ["c", "a", "e", "f", "d", "b"]
    assert items == list("abcdef")  # the input is not reordered in place


# --- places ----------------------------------------------------------------------------


def test_with_two_user_places_three_are_filled(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C", "D", "E", "F", "G"])
    _set(walk, ids["A"], shortlist_state="added_by_you")
    _set(walk, ids["B"], shortlist_state="added_by_you")
    backend = StubLonglistBackend()
    _, summary = _shortlist(walk, backend)
    assert summary["filled"] == 3 and summary["kept"] == 2
    states = _states(walk)
    assert states["A"] == states["B"] == ("added_by_you", None)  # user places untouched
    picked = [name for name, (state, _) in states.items() if state == "proposed"]
    assert len(picked) == 3
    assert all(states[name][1] == "stub reason" for name in picked)
    text = _user_text(backend)
    assert "Places to fill (data): 3" in text
    # The kept places reach the input as cards with their own ids, never as candidates.
    assert "id: k1\n## A" in text and "id: k2\n## B" in text
    assert {_name_of(text, sid) for sid in _ids_in_user_order(text)} == {"C", "D", "E", "F", "G"}


def test_with_five_user_places_none_is_filled_and_the_note_is_written(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C", "D", "E", "F"])
    for name in "ABCDE":
        _set(walk, ids[name], shortlist_state="added_by_you")
    backend = StubLonglistBackend()
    _, summary = _shortlist(walk, backend)
    assert summary["filled"] == 0
    assert "Places to fill (data): 0" in _user_text(backend)
    row = walk.conn.execute(
        select(longlist_result.c.shortlist).where(longlist_result.c.task_id == walk.task_id)
    ).scalar_one()
    assert row["note"] == "stub note"
    assert row["provenance"]["to_fill"] == 0


def test_a_previous_pick_not_reproposed_is_cleared_not_set_aside(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C", "D", "E", "F", "G"])
    _set(walk, ids["E"], shortlist_state="set_aside")
    probe = StubLonglistBackend()
    run_id, _ = _shortlist(walk, probe)
    text = _user_text(probe)
    order = _ids_in_user_order(text)
    assert {_name_of(text, sid) for sid in order} == set("ABCDFG")  # never the set-aside
    assert "s1 · E" in text
    # Now F alone holds a pick; the model proposes the five others. Same run
    # id, same candidates: the same order, so the canned ids name them.
    walk.conn.execute(
        option.update()
        .where(option.c.task_id == walk.task_id, option.c.shortlist_state == "proposed")
        .values(shortlist_state=None, shortlist_reason=None)
    )
    _set(walk, ids["F"], shortlist_state="proposed", shortlist_reason="old reason")
    names = {_name_of(text, sid): sid for sid in order}
    backend = StubLonglistBackend(
        shortlist_responses=_wire([(names[n], f"Reason {n}.") for n in "ABCDG"])
    )
    scope_id = walk._scope(SHORTLIST_PURPOSE)
    shortlist_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=run_id,
        context=ScopeContext(scope_id=scope_id, intent="shortlist", context={}),
        backend=backend,
    )
    # F, the released pick, was a candidate again.
    assert "## F" in _user_text(backend)
    states = _states(walk)
    assert states["F"] == (None, None)
    assert states["E"] == ("set_aside", None)
    assert {n for n, (s, _) in states.items() if s == "proposed"} == set("ABCDG")
    assert states["G"] == ("proposed", "Reason G.")


def test_a_pick_whose_option_is_excluded_or_merged_is_cleared_first(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C", "D"])
    _set(walk, ids["A"], shortlist_state="proposed", shortlist_reason="r", state="excluded")
    _set(walk, ids["B"], shortlist_state="proposed", shortlist_reason="r",
         merged_into_option_id=ids["C"])
    _set(walk, ids["D"], shortlist_state="added_by_you", state="excluded")
    _, summary = _shortlist(walk, StubLonglistBackend(), suggest=True)
    assert summary["cleared"] == 2
    states = _states(walk)
    assert states["A"] == (None, None) and states["B"] == (None, None)
    # A user place is never cleared, even when its option is excluded (O1).
    assert states["D"] == ("added_by_you", None)


def test_at_a_rebuild_a_user_place_stays_through_constrain_and_a_lost_pick_is_cleared(
    conn: Connection,
) -> None:
    """O1 end to end: constrain then the chain's ``shortlist`` (stub backends)."""
    walk = _Walk(conn, scoping_plan(constraints=[_requirement("No benefit sanctions")]))
    t0 = now()
    names = ["Mine", "Picked", "Kept", "Merged", "Other"]  # the kept one is the older
    ids = {
        name: walk.option(name, created_at=t0 + timedelta(seconds=i))
        for i, name in enumerate(names)
    }
    walk.build(_Scripted())
    _set(walk, ids["Mine"], shortlist_state="added_by_you")
    _set(walk, ids["Picked"], shortlist_state="proposed", shortlist_reason="r")
    _set(walk, ids["Merged"], shortlist_state="proposed", shortlist_reason="r")
    every = list(ids.values())
    _constrain(
        walk,
        StubLonglistBackend(
            constrain_responses=_response(
                every,
                ["req-1", *SCREEN_IDS],
                verdicts={(ids["Mine"], "req-1"): "breaks", (ids["Picked"], "req-1"): "breaks"},
            ),
            distinct_responses=_pairs((ids["Merged"], ids["Kept"], "The same offer.")),
        ),
    )
    _shortlist(walk, StubLonglistBackend())
    rows = {
        row.name: row
        for row in walk.conn.execute(select(option).where(option.c.task_id == walk.task_id))
    }
    assert (rows["Mine"].state, rows["Mine"].shortlist_state) == ("excluded", "added_by_you")
    assert rows["Mine"].exclusion["by"] == "constrain"
    assert rows["Picked"].state == "excluded"
    assert rows["Picked"].shortlist_state is None
    assert rows["Merged"].merged_into_option_id == ids["Kept"]
    assert rows["Merged"].shortlist_state is None
    # The two included, unmerged options are the new picks.
    assert {rows["Other"].shortlist_state, rows["Kept"].shortlist_state} == {"proposed"}


def test_the_clearing_stands_when_the_call_fails_and_the_places_stay(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C"])
    _set(walk, ids["A"], shortlist_state="proposed", shortlist_reason="kept reason")
    _set(walk, ids["B"], shortlist_state="proposed", shortlist_reason="r", state="excluded")
    backend = StubLonglistBackend(shortlist_responses=RuntimeError("provider down"))
    with pytest.raises(RuntimeError):
        _shortlist(walk, backend)
    states = _states(walk)
    assert states["A"] == ("proposed", "kept reason")  # the previous place stays
    assert states["B"] == (None, None)


@pytest.mark.parametrize(("places", "filled"), [(3, 2), (5, 1), (6, 1)])
def test_suggest_more_fills_up_to_five_or_one_more(
    conn: Connection, places: int, filled: int
) -> None:
    walk = _Walk(conn)
    names = [f"Option {i}" for i in range(9)]
    ids = _listed(walk, names)
    for i, name in enumerate(names[:places]):
        _set(
            walk,
            ids[name],
            shortlist_state="added_by_you" if i % 2 else "proposed",
            shortlist_reason=None if i % 2 else "earlier reason",
        )
    backend = StubLonglistBackend()
    _, summary = _shortlist(walk, backend, suggest=True)
    assert summary["filled"] == filled
    states = _states(walk)
    # The earlier picks stay; the candidates were only the options without a place.
    for i, name in enumerate(names[:places]):
        expected = ("added_by_you", None) if i % 2 else ("proposed", "earlier reason")
        assert states[name] == expected
    text = _user_text(backend)
    assert {_name_of(text, sid) for sid in _ids_in_user_order(text)} == set(names[places:])


# --- the checks -------------------------------------------------------------------------


def _check_walk(conn: Connection) -> tuple[_Walk, dict[str, uuid.UUID]]:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C", "D", "E", "F", "G", "H"])
    for name in "AB":
        _set(walk, ids[name], shortlist_state="added_by_you")
    _set(walk, ids["C"], shortlist_state="set_aside")
    return walk, ids


@pytest.mark.parametrize(
    ("picks", "failure"),
    [
        ([("o1", "r"), ("o2", "r"), ("o99", "r")], "o99 is not a candidate id."),
        ([("o1", "r"), ("o2", "r"), ("s1", "r")], "s1 was removed by the reader (DO NOT PROPOSE)."),
        ([("o1", "r"), ("o2", "r"), ("k1", "r")], "k1 is one of the reader's own places (KEEP)."),
        ([("o1", "r"), ("o2", "r")], "2 picks, where exactly 3 are asked for."),
        ([("o1", "r"), ("o2", "r"), ("o3", "  ")], "The reason for o3 is empty."),
        ([("o1", "r"), ("o1", "r"), ("o2", "r")], "o1 is proposed more than once."),
        (
            [("o1", "r"), ("o2", "r"), ("o3", "See https://example.org.")],
            "The reason for o3 contains a link.",
        ),
        (
            [("o1", "r"), ("o2", "r"), ("o3", "Read [the review](review).")],
            "The reason for o3 contains a link.",
        ),
    ],
)
def test_each_failed_check_re_asks_once_naming_it_then_fails(
    conn: Connection, picks: list[tuple[str, str]], failure: str
) -> None:
    walk, _ = _check_walk(conn)
    before = _states(walk)
    backend = StubLonglistBackend(shortlist_responses=_wire(picks))
    with pytest.raises(ShortlistFailure, match="failed its checks twice"):
        _shortlist(walk, backend)
    assert backend.calls["shortlist"] == 2
    first, second = backend.inputs["shortlist"]
    # The second request is the first, then the answer, then the re-ask naming the failure.
    assert second[: len(first)] == first
    assert second[len(first)]["role"] == "assistant"
    reask = second[-1]
    assert reask["role"] == "user" and failure in str(reask["content"])
    assert "exactly 3 picks" in str(reask["content"])
    assert _states(walk) == before  # nothing written


def test_a_note_with_a_link_re_asks_naming_it(conn: Connection) -> None:
    walk, _ = _check_walk(conn)
    picks = [("o1", "r"), ("o2", "r"), ("o3", "r")]
    backend = StubLonglistBackend(shortlist_responses=_wire(picks, note="See www.example.org."))
    with pytest.raises(ShortlistFailure, match="The note contains a link."):
        _shortlist(walk, backend)
    assert backend.calls["shortlist"] == 2


def test_a_good_second_answer_is_written_and_attempts_are_recorded(conn: Connection) -> None:
    walk, _ = _check_walk(conn)
    good = _wire([("o1", "First reason."), ("o2", "Second reason."), ("o3", "Third reason.")])
    backend = StubLonglistBackend(shortlist_responses=[_wire([("o99", "r")]), good])
    _, summary = _shortlist(walk, backend)
    assert summary["attempts"] == 2 and summary["filled"] == 3
    provenance = walk.conn.execute(
        select(longlist_result.c.shortlist).where(longlist_result.c.task_id == walk.task_id)
    ).scalar_one()["provenance"]
    assert provenance["attempts"] == 2
    assert len(provenance["usage"]) == 2
    assert set(provenance["usage"][0]) == {"input_tokens", "output_tokens", "elapsed_ms"}


# --- the input --------------------------------------------------------------------------


def test_excluded_options_are_never_candidates_and_reach_the_input_as_one_line(
    conn: Connection,
) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["Youth guarantee", "Wage subsidy", "Work trial"])
    _set(
        walk,
        ids["Work trial"],
        state="excluded",
        primary_lever_type="subsidise",
        ambition="more",
        exclusion={"constraint": "your decision", "reason": "too costly", "by": "user"},
    )
    backend = StubLonglistBackend()
    _shortlist(walk, backend)
    text = _user_text(backend)
    candidates = {_name_of(text, sid) for sid in _ids_in_user_order(text)}
    assert candidates == {"Youth guarantee", "Wage subsidy"}
    assert text.count("Work trial") == 1
    assert "Work trial · subsidise · Bigger · your decision: too costly" in text
    assert "## Work trial" not in text


def test_the_previous_proposal_is_read_from_the_newest_event(conn: Connection) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A", "B"])
    first = StubLonglistBackend()
    _shortlist(walk, first)
    assert 'The previous proposal (data), or "none":\nnone' in _user_text(first)
    second = StubLonglistBackend()
    _shortlist(walk, second)
    text = _user_text(second)
    assert "A — Policy Atlas's pick — stub reason" in text
    assert "B — Policy Atlas's pick — stub reason" in text
    assert "Note: stub note" in text


def test_the_component_reads_the_task_wide_newest_longlist(conn: Connection) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A"])
    run_id, _ = _shortlist(walk, StubLonglistBackend())
    rows = list(
        walk.conn.execute(
            select(longlist_result.c.evidence_scope_id, longlist_result.c.shortlist).where(
                longlist_result.c.task_id == walk.task_id
            )
        )
    )
    assert len(rows) == 1
    # The row is the longlist walk's, written from the shortlist walk's run.
    assert rows[0].evidence_scope_id == walk.scope_id
    assert rows[0].shortlist["provenance"]["run_id"] == str(run_id)


def test_no_longlist_fails(conn: Connection) -> None:
    walk = _Walk(conn)
    walk.option("A")
    with pytest.raises(ShortlistFailure, match="no longlist"):
        _shortlist(walk, StubLonglistBackend())


def test_the_event_carries_the_whole_proposal(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B"])
    _set(walk, ids["A"], shortlist_state="added_by_you")
    run_id, summary = _shortlist(walk, StubLonglistBackend())
    log = [e for e in events.read(walk.conn, walk.task_id) if e["event_type"] == SHORTLIST_PROPOSED]
    assert len(log) == 1
    payload = log[0]["payload"]
    assert payload["places"] == [
        {"option_id": str(ids["A"]), "name": "A", "state": "added_by_you", "reason": None},
        {"option_id": str(ids["B"]), "name": "B", "state": "proposed", "reason": "stub reason"},
    ]
    assert payload["note"] == "stub note"
    assert payload["appetite"] == "mostly_tried"
    assert payload["plan_version"] == 2
    assert payload["prompt_version"] == SHORTLIST_PROMPT_VERSION
    assert payload["model"] == "stub"
    assert payload["run_id"] == str(run_id)
    assert payload["actor"] == "agent"
    assert summary == {
        "filled": 1,
        "kept": 1,
        "set_aside": 0,
        "cleared": 0,
        "input_chars": summary["input_chars"],
        "document_lines_cut": 0,
        "baseline_chars_cut": 0,
        "attempts": 1,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def test_a_longlist_rebuilt_during_the_call_refuses_the_write(conn: Connection) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A", "B"])

    class _Rebuilds(StubLonglistBackend):
        def propose_shortlist(self, *, messages: Any) -> Any:
            walk.build(_Scripted())  # a fresh longlist row lands while the call runs
            return super().propose_shortlist(messages=messages)

    with pytest.raises(ShortlistFailure, match="longlist changed"):
        _shortlist(walk, _Rebuilds())
    assert all(state is None for state, _ in _states(walk).values())


@pytest.mark.parametrize(
    ("suggest", "flipped_to"),
    [(True, "set_aside"), (True, "proposed"), (False, "added_by_you"), (False, "set_aside")],
)
def test_a_place_changed_during_the_call_refuses_the_write(
    conn: Connection, suggest: bool, flipped_to: str
) -> None:
    """The late check: each pick still has the place the snapshot assumed."""
    walk = _Walk(conn)
    ids = _listed(walk, ["A"])

    class _Flips(StubLonglistBackend):
        def propose_shortlist(self, *, messages: Any) -> Any:
            _set(walk, ids["A"], shortlist_state=flipped_to)  # the reader acts mid-call
            return super().propose_shortlist(messages=messages)

    with pytest.raises(ShortlistFailure, match="places changed"):
        _shortlist(walk, _Flips(), suggest=suggest)
    assert _states(walk)["A"] == (flipped_to, None)


def test_the_side_blocks_are_scrubbed_of_control_characters(conn: Connection) -> None:
    walk = _Walk(conn)
    ids = _listed(walk, ["A", "B", "C"])
    _set(walk, ids["B"], shortlist_state="set_aside", name="Set\u202easide\x1b one")
    _set(
        walk,
        ids["C"],
        state="excluded",
        exclusion={"constraint": "your decision", "reason": "too\u2066 costly\x07", "by": "user"},
    )
    backend = StubLonglistBackend()
    _shortlist(walk, backend)
    text = _user_text(backend)
    assert "s1 · Setaside one" in text
    assert "your decision: too costly" in text
    assert not any(char in text for char in "\u202e\u2066\x1b\x07")


# --- the ceiling ------------------------------------------------------------------------


def _fake_cards(lines: int) -> Any:
    def fake(conn: Any, *, task_id: Any, option_ids: Any, today_year: int) -> Any:
        del conn, task_id, today_year
        return {
            oid: CardText(
                fixed=f"## card {i}",
                document_lines=[
                    (2000 + n, f"- document {i}.{n} " + "x" * 80) for n in range(lines)
                ],
            )
            for i, oid in enumerate(option_ids)
        }

    return fake


def test_the_ceiling_cuts_document_lines_and_counts_the_cut(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A", "B", "C"])
    monkeypatch.setattr(shortlist_module, "option_cards", _fake_cards(lines=10))
    _, uncut = _shortlist(walk, StubLonglistBackend())
    assert uncut["document_lines_cut"] == 0
    ceiling = uncut["input_chars"] - 300
    monkeypatch.setattr(shortlist_module, "SHORTLIST_INPUT_CHARS_MAX", ceiling)
    backend = StubLonglistBackend()
    _, summary = _shortlist(walk, backend)
    assert summary["document_lines_cut"] > 0
    request = backend.inputs["shortlist"][0]
    total = sum(len(str(message["content"])) for message in request)
    assert total == summary["input_chars"] <= ceiling
    kept = 30 - summary["document_lines_cut"]
    assert f"Policy Atlas read {kept} of 30 document lines" in str(request[1]["content"])
    # The stored provenance carries the count and the total, for the view's footer.
    stored = walk.conn.execute(
        select(longlist_result.c.shortlist)
        .where(longlist_result.c.task_id == walk.task_id)
        .order_by(longlist_result.c.created_at.desc())
        .limit(1)
    ).scalar_one()
    provenance = stored["provenance"]
    assert provenance["document_lines_total"] == 30
    assert provenance["document_lines_cut"] == summary["document_lines_cut"]
    assert set(provenance) == {
        "prompt_version", "model", "appetite", "plan_version", "run_id", "input_chars",
        "document_lines_cut", "document_lines_total", "baseline_chars_cut", "to_fill",
        "attempts", "usage",
    }
    # Oldest first: every card loses its 2000 line before any loses its 2001 line.
    text = str(request[1]["content"])
    assert ".0 x" not in text


def test_over_the_ceiling_with_every_line_cut_fails(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A"])
    monkeypatch.setattr(shortlist_module, "option_cards", _fake_cards(lines=2))
    monkeypatch.setattr(shortlist_module, "SHORTLIST_INPUT_CHARS_MAX", 1_000)
    backend = StubLonglistBackend()
    with pytest.raises(ShortlistFailure, match="input over ceiling"):
        _shortlist(walk, backend)
    assert backend.calls["shortlist"] == 0


def test_a_long_baseline_is_cut_and_counted(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    walk = _Walk(conn)
    _listed(walk, ["A"])
    monkeypatch.setattr(shortlist_module, "SHORTLIST_BASELINE_MAX_CHARS", 10)
    backend = StubLonglistBackend()
    _, summary = _shortlist(walk, backend)
    full = len("No baseline sections.")
    assert summary["baseline_chars_cut"] == full - 10
    assert f"cut at 10 characters ({full - 10} not shown)" in _user_text(backend)


# --- the walks --------------------------------------------------------------------------


def _longlist_walk(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, Any]:
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
    return task_id, plan_id, outcome


def test_the_longlist_walk_ends_with_the_proposal(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, _, outcome = _longlist_walk(engine)
        assert outcome.status == "succeeded"
        assert [step.component for step in outcome.steps][-2:] == ["theme", "shortlist"]
        with engine.connect() as conn:
            states = [
                row.shortlist_state
                for row in conn.execute(select(option).where(option.c.task_id == task_id))
            ]
            result = conn.execute(
                select(longlist_result).where(longlist_result.c.task_id == task_id)
            ).one()
        assert states == ["proposed"]  # the stub walk's one option, at most five places
        assert result.shortlist["note"] == "stub note"
        assert PLACES_TARGET == 5
    finally:
        _cleanup(engine, task_id)


def test_a_failed_shortlist_degrades_the_walk_and_keeps_themes_and_places(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, plan_id, first = _longlist_walk(engine)
        assert first.status == "succeeded"
        with engine.connect() as conn:
            before = {
                row.option_id: (row.shortlist_state, row.shortlist_reason)
                for row in conn.execute(select(option).where(option.c.task_id == task_id))
            }

        def _down(self: Any, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

        monkeypatch.setattr(StubLonglistBackend, "propose_shortlist", _down)
        task_id_2, _, outcome = _longlist_walk(engine)
        try:
            assert outcome.status == "degraded"
            statuses = {step.component: step.status for step in outcome.steps}
            assert statuses["theme"] == "succeeded"
            assert statuses["shortlist"] == "failed"
            with engine.connect() as conn:
                result = conn.execute(
                    select(longlist_result).where(longlist_result.c.task_id == task_id_2)
                ).one()
            assert result.counts["themes"] == len(result.themes) == 1
            assert result.shortlist == {}
        finally:
            _cleanup(engine, task_id_2)

        # A shortlist walk that fails keeps the first walk's places.
        outcome = _shortlist_walk(engine, task_id=task_id, plan_id=plan_id)
        assert outcome.status == "degraded"
        with engine.connect() as conn:
            after = {
                row.option_id: (row.shortlist_state, row.shortlist_reason)
                for row in conn.execute(select(option).where(option.c.task_id == task_id))
            }
        assert after == before and ("proposed", "stub reason") in after.values()
    finally:
        _cleanup(engine, task_id)


def _shortlist_walk(
    engine: Engine, *, task_id: uuid.UUID, plan_id: uuid.UUID, suggest: bool = False
) -> Any:
    scope_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=task_id,
                intent="shortlist",
                context={"suggest": True} if suggest else {},
                created_at=now(),
                purpose=SHORTLIST_PURPOSE,
                plan_id=plan_id,
            )
        )
    return run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=scoping_plan(steering_mode="moderate"),
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
    )


def test_the_shortlist_walk_runs_the_one_component(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, plan_id, _ = _longlist_walk(engine)
        with engine.begin() as conn:
            conn.execute(
                update(option)
                .where(option.c.task_id == task_id)
                .values(shortlist_state=None, shortlist_reason=None)
            )
        outcome = _shortlist_walk(engine, task_id=task_id, plan_id=plan_id, suggest=True)
        assert outcome.status == "succeeded"
        assert [(s.component, s.status) for s in outcome.steps] == [("shortlist", "succeeded")]
        with engine.connect() as conn:
            states = [
                row.shortlist_state
                for row in conn.execute(select(option).where(option.c.task_id == task_id))
            ]
            proposals = [
                e for e in events.read(conn, task_id) if e["event_type"] == SHORTLIST_PROPOSED
            ]
        assert states == ["proposed"]
        assert len(proposals) == 2  # the longlist walk's, then this walk's
    finally:
        _cleanup(engine, task_id)
