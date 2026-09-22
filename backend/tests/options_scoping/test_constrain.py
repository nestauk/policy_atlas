"""The ``constrain`` component (task 045 Phase 5.3, S9; contract deliverable 7).

The contract's constrain bullet: a requirement breach excludes with the
constraint named; a setting requirement is judged; the three default screens
run and cite; *distinct* never excludes a *part of* row; thin evidence never
excludes; every preference except the transferability preference yields one
capped guess per option, and that one yields none; an inherited document
outside the country group marks its only option no in-scope evidence,
included, with the restriction named; guesses never change state; the
in-scope check makes no backend call. Plus: user state wins on a rebuild; a
malformed batch degrades to ``cannot_check``; judgements are keyed
``(option_id, design_version)``. Seeded on the transactional ``conn`` fixture
through the longlist component's own fixture and the stub longlist backend.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import longlist_result, option, option_relation, task_source_snapshot
from policy_atlas.core.usage import UsageResult
from policy_atlas.options_scoping.constrain.constrain import (
    IN_SCOPE_EVIDENCE_KEY,
    JUDGEMENT_UNAVAILABLE,
    PACKAGE_DISTINCT_REASON,
    ConstrainContext,
    ConstrainFailure,
    constrain_scope,
)
from policy_atlas.options_scoping.constrain.constrain_prompt import (
    CONSTRAIN_BATCH_SIZE,
    DEFAULT_SCREENS,
    ConstrainResponse,
    ConstraintJudgementWire,
    OptionConstrainWire,
    ReasonedGuessWire,
    Verdict,
)
from policy_atlas.options_scoping.constrain.in_scope import (
    document_countries,
    document_year,
    in_scope_evidence,
)
from policy_atlas.options_scoping.longlist.longlist_backend import StubLonglistBackend
from policy_atlas.runtime.scoping_plan import TRANSFERABILITY_DEFAULT, find_default
from tests.helpers import now
from tests.options_scoping.test_longlist import _Walk
from tests.runtime.test_baseline_gate import scoping_plan

SCREEN_IDS = [key for key, _ in DEFAULT_SCREENS]
SCREEN_TEXT = dict(DEFAULT_SCREENS)


def _requirement(text: str, *, setting: bool = False) -> dict[str, Any]:
    return {
        "text": text,
        "kind": "requirement",
        "checked_at": "longlist",
        "origin": "your_call",
        "setting": setting,
    }


def _preference(text: str) -> dict[str, Any]:
    return {"text": text, "kind": "preference", "checked_at": "assessment", "origin": "your_call"}


def _restriction(text: str, **fields: Any) -> dict[str, Any]:
    return {
        "text": text,
        "kind": "evidence_restriction",
        "checked_at": "retrieval",
        "origin": "your_call",
        **fields,
    }


UK_ONLY = _restriction(
    "Evidence from the United Kingdom only",
    country_group={"label": "United Kingdom", "countries": ["GB"]},
)


def _walk(conn: Connection, *constraints: dict[str, Any]) -> _Walk:
    return _Walk(conn, scoping_plan(constraints=list(constraints)))


def _response(
    option_ids: list[uuid.UUID],
    requirement_ids: list[str],
    preference_ids: list[str] | None = None,
    *,
    verdicts: dict[tuple[uuid.UUID, str], Verdict] | None = None,
    leaning: Literal["likely_meets", "likely_falls_short", "cannot_say"] = "likely_meets",
) -> ConstrainResponse:
    """Every option, every id once; ``verdicts`` overrides ``passes`` per pair."""
    verdicts = verdicts or {}
    return ConstrainResponse(
        options=[
            OptionConstrainWire(
                option_id=str(oid),
                judgements=[
                    ConstraintJudgementWire(
                        constraint_id=cid,
                        verdict=verdicts.get((oid, cid), "passes"),
                        reason=f"The design decides {cid}.",
                    )
                    for cid in requirement_ids
                ],
                guesses=[
                    ReasonedGuessWire(
                        constraint_id=pid,
                        guess="Likely low cost, a guess rather than evidence.",
                        leaning=leaning,
                    )
                    for pid in preference_ids or []
                ],
            )
            for oid in option_ids
        ]
    )


def _constrain(walk: _Walk, backend: Any) -> tuple[uuid.UUID, dict[str, Any]]:
    run_id = walk.run()
    summary = constrain_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=run_id,
        context=ConstrainContext(scope_id=walk.scope_id, intent="longlist intent", context={}),
        backend=backend,
    )
    return run_id, summary


def _latest(walk: _Walk) -> Any:
    return walk.conn.execute(
        select(longlist_result)
        .where(longlist_result.c.task_id == walk.task_id)
        .order_by(longlist_result.c.created_at.desc())
        .limit(1)
    ).one()


def _row(walk: _Walk, option_id: uuid.UUID) -> Any:
    return walk.conn.execute(select(option).where(option.c.option_id == option_id)).one()


# --- requirements and the default screens --------------------------------------------


def test_a_requirement_breach_excludes_with_the_constraint_named(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"))
    kept = walk.option("Youth guarantee")
    broken = walk.option("Sanctioned work search")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [kept, broken], ["req-1", *SCREEN_IDS], verdicts={(broken, "req-1"): "breaks"}
        )
    )

    _, summary = _constrain(walk, backend)

    assert summary == {
        "options": 2,
        "excluded": 1,
        "no_in_scope": 0,
        "cannot_check": 0,
        "guesses": 0,
    }
    row = _row(walk, broken)
    assert row.state == "excluded"
    assert row.exclusion == {
        "constraint": "No benefit sanctions",
        "reason": "The design decides req-1.",
        "by": "constrain",
    }
    assert _row(walk, kept).state == "included" and _row(walk, kept).exclusion is None
    judgement = _latest(walk).judgements[str(broken)]["1"]["req-1"]
    assert judgement == {
        "verdict": "breaks",
        "reason": "The design decides req-1.",
        "constraint_text": "No benefit sanctions",
    }
    counts = _latest(walk).counts
    assert (counts["included"], counts["excluded"], counts["no_in_scope_evidence"]) == (1, 1, 0)


def test_a_setting_requirement_is_judged_like_any_requirement(conn: Connection) -> None:
    walk = _walk(
        conn,
        _requirement("No benefit sanctions"),
        _requirement("Delivered through schools", setting=True),
    )
    elsewhere = walk.option("Job centre coaching")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [elsewhere], ["req-1", "req-2", *SCREEN_IDS], verdicts={(elsewhere, "req-2"): "breaks"}
        )
    )

    _constrain(walk, backend)

    sent = backend.constrain_inputs[0]["requirements"]
    assert sent[:2] == [
        {"id": "req-1", "text": "No benefit sanctions"},
        {"id": "req-2", "text": "Delivered through schools"},
    ]
    assert _row(walk, elsewhere).exclusion["constraint"] == "Delivered through schools"


def test_the_three_default_screens_run_and_cite(conn: Connection) -> None:
    walk = _walk(conn)
    off_topic = walk.option("Pension auto-enrolment")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [off_topic], SCREEN_IDS, verdicts={(off_topic, "relevant"): "breaks"}
        )
    )

    _constrain(walk, backend)

    # The plan has no requirement: the call still carries the three screens.
    assert backend.constrain_inputs[0]["requirements"] == [
        {"id": key, "text": label} for key, label in DEFAULT_SCREENS
    ]
    row = _row(walk, off_topic)
    assert row.state == "excluded"
    assert row.exclusion["constraint"] == SCREEN_TEXT["relevant"]
    record = _latest(walk).judgements[str(off_topic)]["1"]
    assert {key: record[key]["constraint_text"] for key in SCREEN_IDS} == SCREEN_TEXT
    assert [record[key]["verdict"] for key in SCREEN_IDS] == ["breaks", "passes", "passes"]


def test_distinct_never_excludes_a_part_of_row(conn: Connection) -> None:
    walk = _walk(conn)
    component = walk.option("Mentoring")
    package = walk.option("Guarantee package")
    duplicate = walk.option("Youth mentoring")
    conn.execute(
        option_relation.insert().values(
            relation_id=uuid.uuid4(),
            task_id=walk.task_id,
            from_option_id=component,
            to_option_id=package,
            kind="part_of",
            created_by="longlist",
            created_at=now(),
        )
    )
    walk.build(StubLonglistBackend())
    ids = [component, package, duplicate]
    backend = StubLonglistBackend(
        constrain_responses=_response(
            ids, SCREEN_IDS, verdicts={(oid, "distinct"): "breaks" for oid in ids}
        )
    )

    _constrain(walk, backend)

    for oid in (component, package):
        assert _row(walk, oid).state == "included"
        distinct = _latest(walk).judgements[str(oid)]["1"]["distinct"]
        assert distinct["verdict"] == "passes"
        assert distinct["reason"] == PACKAGE_DISTINCT_REASON
    assert _row(walk, duplicate).state == "excluded"
    assert _row(walk, duplicate).exclusion["constraint"] == SCREEN_TEXT["distinct"]
    # Both ends of the relation reach the prompt.
    sent = {o["option_id"]: o["relations"] for o in backend.constrain_inputs[0]["options"]}
    assert sent[str(component)] == [
        {
            "kind": "part_of",
            "role": "component",
            "other_option_id": str(package),
            "other_label": "Guarantee package",
        }
    ]
    assert sent[str(package)][0]["role"] == "package"
    assert sent[str(duplicate)] == []


def test_thin_evidence_never_excludes(conn: Connection) -> None:
    """A zero-document option passes every screen its design passes."""
    walk = _walk(conn, _requirement("No benefit sanctions"))
    empty = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend()  # the default passes every requirement

    _, summary = _constrain(walk, backend)

    assert summary["excluded"] == 0
    row = _row(walk, empty)
    assert (row.state, row.exclusion, row.no_in_scope_evidence) == ("included", None, False)
    coverage = backend.constrain_inputs[0]["options"][0]["coverage"]
    assert coverage["documents"] == 0 and coverage["evaluated"] == 0


# --- reasoned guesses ------------------------------------------------------------------


def test_every_preference_but_transferability_yields_one_guess(conn: Connection) -> None:
    walk = _walk(conn, _preference("Prefer low cost per participant"))
    plan = scoping_plan(constraints=[_preference("Prefer low cost per participant")])
    transferability = find_default(plan, TRANSFERABILITY_DEFAULT)
    assert transferability is not None  # the default is on the plan ...
    first = walk.option("Youth guarantee")
    second = walk.option("Wage subsidy")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend()

    _, summary = _constrain(walk, backend)

    # ... and never reaches the prompt.
    sent = backend.constrain_inputs[0]
    assert sent["preferences"] == [{"id": "pref-1", "text": "Prefer low cost per participant"}]
    assert transferability.text not in repr(sent)
    guesses = _latest(walk).guesses
    for oid in (first, second):
        assert guesses[str(oid)]["1"] == {
            "pref-1": {
                "guess": "May or may not meet it, a guess rather than evidence.",
                "leaning": "cannot_say",
                "constraint_text": "Prefer low cost per participant",
            }
        }
    assert summary["guesses"] == 2
    assert _latest(walk).counts["guesses"] == 2


def test_guesses_never_change_state(conn: Connection) -> None:
    walk = _walk(conn, _preference("Prefer low cost per participant"))
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [oid], SCREEN_IDS, ["pref-1"], leaning="likely_falls_short"
        )
    )

    _constrain(walk, backend)

    assert _row(walk, oid).state == "included"
    assert _latest(walk).guesses[str(oid)]["1"]["pref-1"]["leaning"] == "likely_falls_short"


# --- no in-scope evidence ----------------------------------------------------------------


def _inherited_doc(walk: _Walk, meta: dict[str, Any]) -> uuid.UUID:
    """A document the inherit step copied in (its row carries the inherit run)."""
    tss_id = walk.doc(meta)
    walk.conn.execute(
        update(task_source_snapshot)
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
        .values(run_id=walk.run())
    )
    return tss_id


def test_an_inherited_document_outside_the_group_marks_its_only_option(
    conn: Connection,
) -> None:
    walk = _walk(conn, UK_ONLY)
    oid = walk.option("Youth guarantee")
    french = _inherited_doc(walk, {"publication_country": "FR", "year": 2021})
    walk.record(french, "youth guarantee")
    walk.rollup(walk.scope_id, [french])
    walk.build(StubLonglistBackend())

    _, summary = _constrain(walk, StubLonglistBackend())

    row = _row(walk, oid)
    assert (row.state, row.no_in_scope_evidence) == ("included", True)
    assert summary["no_in_scope"] == 1 and summary["excluded"] == 0
    assert _latest(walk).judgements[str(oid)]["1"][IN_SCOPE_EVIDENCE_KEY] == {
        "restriction": "Evidence from the United Kingdom only",
        "in_scope_documents": 0,
        "documents": 1,
    }
    assert _latest(walk).counts["no_in_scope_evidence"] == 1


def test_a_document_inside_the_group_clears_the_mark(conn: Connection) -> None:
    walk = _walk(conn, UK_ONLY)
    oid = walk.option("Youth guarantee")
    french = _inherited_doc(walk, {"publication_country": "FR"})
    walk.record(french, "youth guarantee")
    walk.rollup(walk.scope_id, [french])
    walk.build(StubLonglistBackend())
    _constrain(walk, StubLonglistBackend())
    assert _row(walk, oid).no_in_scope_evidence is True

    # A rebuild with an Overton document published in the UK ("UK" → GB).
    british = walk.doc({"backend": "overton", "provider_fields": {"source": {"country": "UK"}}})
    walk.record(british, "youth guarantee")
    walk.rollup(walk.scope_id, [french, british])
    walk.build(StubLonglistBackend())
    _constrain(walk, StubLonglistBackend())

    assert _row(walk, oid).no_in_scope_evidence is False
    record = _latest(walk).judgements[str(oid)]["1"][IN_SCOPE_EVIDENCE_KEY]
    assert (record["in_scope_documents"], record["documents"]) == (1, 2)


def test_a_year_bound_outside_marks_and_an_option_with_no_documents_is_not_marked(
    conn: Connection,
) -> None:
    walk = _walk(conn, _restriction("Published from 2015", published_after="2015-01-01"))
    old = walk.option("Youth guarantee")
    empty = walk.option("Wage subsidy")
    doc = _inherited_doc(walk, {"year": 2009})
    walk.record(doc, "youth guarantee")
    walk.rollup(walk.scope_id, [doc])
    walk.build(StubLonglistBackend())

    _constrain(walk, StubLonglistBackend())

    assert _row(walk, old).no_in_scope_evidence is True
    assert _row(walk, empty).no_in_scope_evidence is False


def test_a_plan_without_a_restriction_marks_nothing(conn: Connection) -> None:
    walk = _walk(conn)
    oid = walk.option("Youth guarantee")
    french = _inherited_doc(walk, {"publication_country": "FR"})
    walk.record(french, "youth guarantee")
    walk.rollup(walk.scope_id, [french])
    walk.build(StubLonglistBackend())

    _, summary = _constrain(walk, StubLonglistBackend())

    assert summary["no_in_scope"] == 0
    assert _row(walk, oid).no_in_scope_evidence is False
    assert IN_SCOPE_EVIDENCE_KEY not in _latest(walk).judgements[str(oid)]["1"]


def test_the_in_scope_check_makes_no_backend_call(conn: Connection) -> None:
    """The check reads metadata only: it runs with no backend in reach, and it
    marks correctly when every judgement call fails."""
    walk = _walk(conn, UK_ONLY)
    oid = walk.option("Youth guarantee")
    french = _inherited_doc(walk, {"publication_country": "FR"})
    walk.record(french, "youth guarantee")
    walk.rollup(walk.scope_id, [french])
    walk.build(StubLonglistBackend())
    plan = scoping_plan(constraints=[UK_ONLY])

    backend = StubLonglistBackend()
    checked = in_scope_evidence(conn, task_id=walk.task_id, plan=plan, option_ids=[oid])
    assert checked[oid]["no_in_scope_evidence"] is True
    assert backend.constrain_calls == 0

    class _Down(StubLonglistBackend):
        def constrain(
            self,
            *,
            plan: dict[str, object],
            requirements: list[dict[str, str]],
            preferences: list[dict[str, str]],
            options: list[dict[str, object]],
        ) -> UsageResult[ConstrainResponse]:
            self.constrain_calls += 1
            raise RuntimeError("provider down")

    down = _Down()
    _, summary = _constrain(walk, down)
    assert down.constrain_calls == 2  # the batch and its one retry, nothing else
    assert summary["no_in_scope"] == 1 and summary["cannot_check"] == 1
    assert _row(walk, oid).no_in_scope_evidence is True


def test_the_country_read_maps_overton_names_and_reads_authorships() -> None:
    assert document_countries({"publication_country": "GB"}) == {"GB"}
    assert document_countries(
        {"backend": "overton", "provider_fields": {"source": {"country": "UK"}}}
    ) == {"GB"}
    openalex = {
        "backend": "openalex",
        "provider_fields": {
            "primary_location": {"source": {"country_code": "NL"}},
            "authorships": [{"countries": ["GB", "US"]}, {"countries": []}],
        },
    }
    assert document_countries(openalex) == {"NL", "GB", "US"}
    assert document_countries({}) == frozenset()
    assert document_year({"year": 2020}) == 2020
    assert document_year({"publication_year": 2019, "year": 2020}) == 2019
    assert document_year({"year": "2020"}) is None


# --- user state, degradation, keys, batching ----------------------------------------------


def test_user_state_wins_on_a_rebuild(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"))
    user_out = walk.option(
        "User excluded",
        state="excluded",
        exclusion={"constraint": None, "reason": "Not for us.", "by": "user"},
    )
    user_in = walk.option(
        "Included again",
        state="included",
        exclusion={"constraint": "No benefit sanctions", "reason": "Keep it.", "by": "user"},
    )
    was_out = walk.option(
        "Was excluded",
        state="excluded",
        exclusion={"constraint": "No benefit sanctions", "reason": "Old.", "by": "constrain"},
    )
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [user_out, user_in, was_out],
            ["req-1", *SCREEN_IDS],
            verdicts={(user_in, "req-1"): "breaks"},
        )
    )

    _, summary = _constrain(walk, backend)

    assert _row(walk, user_out).state == "excluded"
    assert _row(walk, user_out).exclusion["by"] == "user"
    assert _row(walk, user_in).state == "included"
    assert _row(walk, user_in).exclusion["reason"] == "Keep it."
    assert (_row(walk, was_out).state, _row(walk, was_out).exclusion) == ("included", None)
    # Every option was judged, the user-held ones too.
    assert _latest(walk).judgements[str(user_in)]["1"]["req-1"]["verdict"] == "breaks"
    assert summary["excluded"] == 1


def test_a_malformed_batch_degrades_to_cannot_check(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"), _preference("Low cost"))
    first = walk.option("Youth guarantee")
    second = walk.option("Wage subsidy")
    walk.build(StubLonglistBackend())
    ids = ["req-1", *SCREEN_IDS]
    missing_option = _response([first], ids, ["pref-1"])
    duplicated_id = _response([first, second], [*ids, "req-1"], ["pref-1"])
    backend = StubLonglistBackend(constrain_responses=[missing_option, duplicated_id])

    _, summary = _constrain(walk, backend)

    assert backend.constrain_calls == 2
    assert summary == {
        "options": 2,
        "excluded": 0,
        "no_in_scope": 0,
        "cannot_check": 2,
        "guesses": 0,
    }
    result = _latest(walk)
    for oid in (first, second):
        record = result.judgements[str(oid)]["1"]
        assert {cid: record[cid]["verdict"] for cid in ids} == dict.fromkeys(ids, "cannot_check")
        assert {record[cid]["reason"] for cid in ids} == {JUDGEMENT_UNAVAILABLE}
        assert _row(walk, oid).state == "included"
    assert result.guesses == {}
    assert result.counts["cannot_check"] == 2
    assert result.provenance["constrain"]["failed_batches"] == 1


def test_a_malformed_batch_is_retried_once(conn: Connection) -> None:
    walk = _walk(conn)
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    wrong_id = _response([uuid.uuid4()], SCREEN_IDS)
    good = _response([oid], SCREEN_IDS, verdicts={(oid, "in_scope"): "breaks"})
    backend = StubLonglistBackend(constrain_responses=[wrong_id, good])

    _constrain(walk, backend)

    assert backend.constrain_calls == 2
    assert _row(walk, oid).exclusion["constraint"] == SCREEN_TEXT["in_scope"]


def test_judgements_are_keyed_by_option_and_design_version(conn: Connection) -> None:
    walk = _walk(conn, _preference("Low cost"))
    oid = walk.option("Youth guarantee", design_version=3)
    walk.build(StubLonglistBackend())

    _constrain(walk, StubLonglistBackend())

    result = _latest(walk)
    assert list(result.judgements[str(oid)]) == ["3"]
    assert list(result.guesses[str(oid)]) == ["3"]


def test_options_are_judged_in_batches(conn: Connection) -> None:
    walk = _walk(conn)
    for i in range(CONSTRAIN_BATCH_SIZE + 2):
        walk.option(f"Option {i}")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend()

    _, summary = _constrain(walk, backend)

    assert [len(call["options"]) for call in backend.constrain_inputs] == [
        CONSTRAIN_BATCH_SIZE,
        2,
    ]
    assert summary["options"] == CONSTRAIN_BATCH_SIZE + 2
    assert len(_latest(walk).judgements) == CONSTRAIN_BATCH_SIZE + 2


def test_constrain_without_a_longlist_fails(conn: Connection) -> None:
    walk = _walk(conn)
    walk.option("Youth guarantee")
    with pytest.raises(ConstrainFailure):
        _constrain(walk, StubLonglistBackend())


def test_the_harness_runs_constrain_on_the_stub_backend(conn: Connection) -> None:
    from policy_atlas.core.inference import StubEchoProvider
    from policy_atlas.runtime.harness import run_harness
    from policy_atlas.runtime.run_spec import Plan, compile

    walk = _walk(conn)
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    outcome = run_harness(
        conn,
        config=compile(Plan(component="constrain", evidence_scope_id=walk.scope_id)),
        task_id=walk.task_id,
        run_id=walk.run(),
        provider=StubEchoProvider(),
    )
    assert outcome["error"] is None
    assert outcome["summary"] == {
        "options": 1,
        "excluded": 0,
        "no_in_scope": 0,
        "cannot_check": 0,
        "guesses": 0,
    }
    assert set(_latest(walk).judgements[str(oid)]["1"]) == set(SCREEN_IDS)
