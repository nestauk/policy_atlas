"""The ``constrain`` component (task 045 Phase 5.3, S9; task 046 Phase 6.1, S6, S13).

The contract's constrain bullet: a requirement breach excludes with the
constraint named; a setting requirement is judged; the default screens run
and cite (*distinct* by its own call over the whole list, task 046 item 5);
*distinct* never excludes a *part of* row; thin evidence never excludes;
every preference except the transferability preference yields one
capped guess per option, and that one yields none; an inherited document
outside the country group marks its only option no in-scope evidence,
included, with the restriction named; guesses never change state; the
in-scope check makes no backend call. Plus: user state wins on a rebuild; a
malformed batch degrades to ``cannot_check``; judgements are keyed
``(option_id, design_version)``. Task 046: the distinct call receives every
option and feeds the merge rule, drops bad pairs, and degrades to
``cannot_check`` with no merge; no place token reaches the plan data and the
removal is recorded, a requirement naming a place stays verbatim (item 10);
silence passes and a setting break excludes with the requirement named (item
11, stub level); a pathway-only option reaches the prompt and passes (AM6);
the batches run in parallel; no ``where_tried`` in the option payload; the
baseline is passed. Seeded on the transactional ``conn`` fixture through the
longlist component's own fixture and the stub longlist backend.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import timedelta
from typing import Any, Literal

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.api import longlist_actions
from policy_atlas.api.readmodels import repository
from policy_atlas.core.schema import longlist_result, option, option_relation, task_source_snapshot
from policy_atlas.core.usage import UsageResult
from policy_atlas.options_scoping.constrain import constrain as constrain_module
from policy_atlas.options_scoping.constrain.constrain import (
    AUTHORITY_KEY,
    DISTINCT_PASSES_REASON,
    DUPLICATE_KEPT_REASON,
    IN_SCOPE_EVIDENCE_KEY,
    JUDGEMENT_UNAVAILABLE,
    PACKAGE_DISTINCT_REASON,
    ConstrainContext,
    ConstrainFailure,
    _constraint_lists,
    constrain_scope,
)
from policy_atlas.options_scoping.constrain.constrain_prompt import (
    CONSTRAIN_BATCH_SIZE,
    DEFAULT_SCREENS,
    DISTINCT_SCREEN,
    AuthorityLabel,
    AuthorityResponse,
    AuthorityWire,
    ConstrainResponse,
    ConstraintJudgementWire,
    DistinctPairWire,
    DistinctResponse,
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
from policy_atlas.options_scoping.longlist.longlist_cluster_prompt import (
    DiscoveredOptionWire,
    OptionDiscoveryResponse,
)
from policy_atlas.options_scoping.longlist.where_tried import names_place
from policy_atlas.options_scoping.option_profile.option_profile import (
    OptionProfileContext,
    option_profile_scope,
)
from policy_atlas.runtime.scoping_plan import TRANSFERABILITY_DEFAULT, find_default
from tests.helpers import now
from tests.options_scoping.test_longlist import _Walk
from tests.runtime.test_baseline_gate import scoping_plan

# The screens the per-option batches judge (relevant, within scope) ...
SCREEN_IDS = [key for key, _ in DEFAULT_SCREENS]
# ... and every screen a judgement record stores, in the read models' order.
STORED_SCREEN_IDS = ["relevant", "distinct", "in_scope"]
STORED_SCREEN_TEXT = {**dict(DEFAULT_SCREENS), DISTINCT_SCREEN[0]: DISTINCT_SCREEN[1]}


def _requirement(text: str, *, setting: bool = False) -> dict[str, Any]:
    return {
        "text": text,
        "kind": "boundary",
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
    reasons: dict[tuple[uuid.UUID, str], str] | None = None,
    leaning: Literal["likely_meets", "likely_falls_short", "cannot_say"] = "likely_meets",
) -> ConstrainResponse:
    """Every option, every id once; ``verdicts`` overrides ``passes`` per pair,
    ``reasons`` the reason."""
    verdicts = verdicts or {}
    reasons = reasons or {}
    return ConstrainResponse(
        options=[
            OptionConstrainWire(
                option_id=str(oid),
                judgements=[
                    ConstraintJudgementWire(
                        constraint_id=cid,
                        verdict=verdicts.get((oid, cid), "passes"),
                        reason=reasons.get((oid, cid), f"The design decides {cid}."),
                    )
                    for cid in requirement_ids
                ],
                guesses=[
                    ReasonedGuessWire(
                        constraint_id=pid,
                        guess="Likely low cost.",
                        leaning=leaning,
                    )
                    for pid in preference_ids or []
                ],
            )
            for oid in option_ids
        ]
    )


def _pairs(*pairs: tuple[uuid.UUID | str, uuid.UUID | str, str]) -> DistinctResponse:
    """A distinct answer: ``(duplicate, kept, reason)`` per pair."""
    return DistinctResponse(
        duplicates=[
            DistinctPairWire(option_id=str(dup), same_as_option_id=str(kept), reason=reason)
            for dup, kept, reason in pairs
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


def _consideration(text: str, *, aspect: str, hard: bool) -> dict[str, Any]:
    return {
        "text": text,
        "kind": "consideration",
        "checked_at": "assessment",
        "origin": "your_call",
        "aspect": aspect,
        "hard": hard,
    }


def test_a_consideration_reaches_neither_list_and_excludes_nothing(conn: Connection) -> None:
    """Task 046, R34: a consideration, even a hard one, is never a requirement
    or a preference at the longlist; it never excludes an option."""
    base = (_requirement("No benefit sanctions"), _preference("Low cost"))
    hard_limit = _consideration("A budget of at most £2m a year", aspect="cost", hard=True)
    without_plan = scoping_plan(constraints=list(base))
    with_plan = scoping_plan(constraints=[*base, hard_limit])
    assert [c.kind for c in with_plan.constraints].count("consideration") == 1
    assert _constraint_lists(with_plan) == _constraint_lists(without_plan)

    walk = _walk(conn, *base, hard_limit)
    first = walk.option("Youth guarantee")
    second = walk.option("Costly national programme")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend()

    _, summary = _constrain(walk, backend)

    requirements, preferences = _constraint_lists(without_plan)
    sent = backend.constrain_inputs[0]
    assert sent["requirements"] == requirements
    assert sent["preferences"] == preferences
    assert all(hard_limit["text"] not in json.dumps(value, default=str) for value in sent.values())
    assert summary["excluded"] == 0
    assert _row(walk, first).state == "included"
    assert _row(walk, second).state == "included"


def test_the_default_screens_run_and_cite(conn: Connection) -> None:
    walk = _walk(conn)
    off_topic = walk.option("Pension auto-enrolment")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [off_topic], SCREEN_IDS, verdicts={(off_topic, "relevant"): "breaks"}
        )
    )

    _constrain(walk, backend)

    # The plan has no requirement: the batch still carries its two screens;
    # *distinct* is judged by its own call, never in the batch.
    assert backend.constrain_inputs[0]["requirements"] == [
        {"id": key, "text": label} for key, label in DEFAULT_SCREENS
    ]
    assert "distinct" not in SCREEN_IDS
    row = _row(walk, off_topic)
    assert row.state == "excluded"
    assert row.exclusion["constraint"] == STORED_SCREEN_TEXT["relevant"]
    record = _latest(walk).judgements[str(off_topic)]["1"]
    assert {
        key: record[key]["constraint_text"] for key in STORED_SCREEN_IDS
    } == STORED_SCREEN_TEXT
    assert [record[key]["verdict"] for key in STORED_SCREEN_IDS] == [
        "breaks",
        "passes",
        "passes",
    ]
    assert record["distinct"]["reason"] == DISTINCT_PASSES_REASON


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
    backend = StubLonglistBackend(
        distinct_responses=_pairs(
            (duplicate, component, "The same thing as Mentoring."),
            (package, component, "The package is mentoring."),
        )
    )

    _constrain(walk, backend)

    for oid in (component, package):
        assert _row(walk, oid).state == "included"
        distinct = _latest(walk).judgements[str(oid)]["1"]["distinct"]
        assert distinct["verdict"] == "passes"
        assert distinct["reason"] == PACKAGE_DISTINCT_REASON
    # The duplicate is merged into the part it duplicates, not excluded.
    assert _row(walk, duplicate).merged_into_option_id == component
    assert _row(walk, duplicate).state == "included"
    # Both ends of the relation reach both prompts.
    batch = {o["option_id"]: o["relations"] for o in backend.constrain_inputs[0]["options"]}
    sent: dict[Any, Any] = {o["option_id"]: o["relations"] for o in backend.distinct_inputs[0]}
    assert batch == sent
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


def test_distinct_keeps_the_users_option_of_a_duplicate_group(conn: Connection) -> None:
    """Never every member; the user's option is kept even when the call names another."""
    walk = _walk(conn)
    t0 = now()
    first = walk.option("Youth guarantee", created_at=t0)
    users = walk.option(
        "Job guarantee", origin="added_by_you", created_at=t0 + timedelta(seconds=1)
    )
    later = walk.option("Guarantee scheme", created_at=t0 + timedelta(seconds=2))
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        distinct_responses=_pairs(
            # The call names another option as kept: code keeps the user's.
            (users, first, "The same offer as Youth guarantee."),
            (later, first, "Youth guarantee under a new name."),
        )
    )

    _, summary = _constrain(walk, backend)

    assert (_row(walk, users).state, _row(walk, users).exclusion) == ("included", None)
    kept = _latest(walk).judgements[str(users)]["1"]["distinct"]
    assert (kept["verdict"], kept["reason"]) == ("passes", DISTINCT_PASSES_REASON)
    # Merged into the kept option, not excluded (owner ruling 2026-09-24);
    # both pairs named ``first``: the group is kept at ``users``.
    for oid in (first, later):
        assert _row(walk, oid).merged_into_option_id == users
        assert (_row(walk, oid).state, _row(walk, oid).exclusion) == ("included", None)
        distinct = _latest(walk).judgements[str(oid)]["1"]["distinct"]
        assert distinct["verdict"] == "breaks"
        assert distinct["reason"].startswith('The same as "Job guarantee"')
    assert summary["excluded"] == 0
    assert _latest(walk).counts["merged"] == 2
    stats = _latest(walk).provenance["constrain"]["distinct"]
    assert (stats["pairs"], stats["turned"], stats["failed"]) == (2, 2, False)


def test_code_keeps_the_earliest_whichever_option_the_call_names(conn: Connection) -> None:
    """The merge rule of 2026-09-24: of two options of the same kind of origin,
    the earliest created is kept, even when the call names the later one."""
    walk = _walk(conn)
    t0 = now()
    earlier = walk.option("Youth guarantee", created_at=t0)
    later = walk.option("Guarantee scheme", created_at=t0 + timedelta(seconds=1))
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        distinct_responses=_pairs((earlier, later, "The same offer."))
    )

    _, summary = _constrain(walk, backend)

    assert _row(walk, later).merged_into_option_id == earlier
    assert _row(walk, earlier).merged_into_option_id is None
    distinct = _latest(walk).judgements[str(later)]["1"]["distinct"]
    assert (distinct["verdict"], distinct["reason"]) == (
        "breaks",
        'The same as "Youth guarantee": The same offer.',
    )
    kept = _latest(walk).judgements[str(earlier)]["1"]["distinct"]
    assert (kept["verdict"], kept["reason"]) == ("passes", DISTINCT_PASSES_REASON)
    assert summary["excluded"] == 0
    stats = _latest(walk).provenance["constrain"]["distinct"]
    assert (stats["pairs"], stats["turned"]) == (1, 1)


def _duplicate_pair(walk: _Walk, **dup_values: Any) -> tuple[uuid.UUID, uuid.UUID]:
    """``Youth guarantee`` (kept) and a later ``Guarantee scheme``, one document each."""
    t0 = now()
    kept = walk.option("Youth guarantee", created_at=t0)
    dup = walk.option("Guarantee scheme", created_at=t0 + timedelta(seconds=1), **dup_values)
    docs = [walk.doc(), walk.doc()]
    walk.record(docs[0], "Youth guarantee")
    walk.record(docs[1], "Guarantee scheme")
    walk.rollup(walk.scope_id, docs)
    return kept, dup


def _duplicate_breach(kept: uuid.UUID, dup: uuid.UUID) -> StubLonglistBackend:
    return StubLonglistBackend(distinct_responses=_pairs((dup, kept, "The same offer.")))


def _members(walk: _Walk, option_id: uuid.UUID) -> int:
    return sum(1 for m in walk.memberships() if m.option_id == option_id)


def test_a_duplicate_is_merged_into_the_kept_option_with_its_documents(
    conn: Connection,
) -> None:
    walk = _walk(conn)
    kept, dup = _duplicate_pair(walk)
    walk.build(StubLonglistBackend())
    assert (_members(walk, kept), _members(walk, dup)) == (1, 1)

    _, summary = _constrain(walk, _duplicate_breach(kept, dup))

    row = _row(walk, dup)
    assert row.merged_into_option_id == kept
    assert (row.state, row.exclusion) == ("included", None)  # left as it was
    assert (_members(walk, kept), _members(walk, dup)) == (2, 0)
    latest = _latest(walk)
    assert latest.coverage[str(kept)]["documents"] == 2
    distinct = latest.judgements[str(dup)]["1"]["distinct"]
    assert (distinct["verdict"], distinct["reason"]) == (
        "breaks",
        'The same as "Youth guarantee": The same offer.',
    )
    assert summary["excluded"] == 0
    assert (latest.counts["options"], latest.counts["merged"]) == (1, 1)
    assert latest.counts["included"] == 1

    # The read models: the duplicate leaves the list; the kept card names it.
    longlist = repository.longlist_out(conn, walk.task_id)
    assert longlist is not None
    assert [o.option_id for o in longlist.options] == [kept]
    assert longlist.options[0].also_found_as == ["Guarantee scheme"]
    assert longlist.options[0].document_count == 2
    assert (longlist.counts.options, longlist.counts.excluded) == (1, 0)
    assert dup not in longlist.unthemed_option_ids
    assert all(dup not in theme.option_ids for theme in longlist.themes)
    card = repository.option_out(conn, walk.task_id, dup)  # a link to it still works
    assert card is not None and card.option_id == kept
    assert card.also_found_as == ["Guarantee scheme"]
    assert len(card.documents) == 2
    # No verb reaches the merged duplicate (the chat and the buttons lock through here).
    with pytest.raises(longlist_actions.OptionNotFound):
        longlist_actions._locked_option(conn, task_id=walk.task_id, option_id=dup)


def test_a_merge_recomputes_the_kinds_from_the_stored_maps_and_keeps_the_old_keys(
    conn: Connection,
) -> None:
    """Task 046, amendment 3 (R54, R55; S21): the merge recompute applies the
    list's folding maps, stored by the profile step; constrain's own keys stay."""
    walk = _walk(conn)
    t0 = now()
    kept = walk.option("Youth guarantee", created_at=t0)
    dup = walk.option("Guarantee scheme", created_at=t0 + timedelta(seconds=1))
    docs = [walk.doc(), walk.doc()]
    walk.record(
        docs[0], "Youth guarantee", unit="young people aged 16 to 24", outcome="NEET status"
    )
    walk.record(docs[1], "Guarantee scheme", unit="16 to 24s", outcome="neet rates")
    walk.rollup(walk.scope_id, docs)
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    # The profile step's maps, as a folding call might have written them.
    profile = dict(_latest(walk).option_profile)
    profile["folds"] = {
        "tried_on": {
            "young people aged 16 to 24": "16 to 24 year olds",
            "16 to 24s": "16 to 24 year olds",
        },
        "measures": {"NEET status": "the NEET rate", "neet rates": "the NEET rate"},
    }
    conn.execute(
        update(longlist_result)
        .where(longlist_result.c.longlist_result_id == _latest(walk).longlist_result_id)
        .values(option_profile=profile)
    )
    backend = _duplicate_breach(kept, dup)

    _constrain(walk, backend)

    coverage = _latest(walk).coverage[str(kept)]
    assert coverage["documents"] == 2
    assert coverage["tried_on_kinds"] == [{"kind": "16 to 24 year olds", "documents": 2}]
    assert coverage["measures_kinds"] == [
        {"kind": "the NEET rate", "documents": 2, "evaluated": 2}
    ]
    # Not tagged under this plan's context: both count on the plan outcome's row.
    assert coverage["outcome_counts"]["by_outcome"] == [
        {"outcome": "the NEET rate", "documents": 2, "evaluated": 2}
    ]
    assert coverage["outcome_counts"]["other"] == []
    # The old keys constrain reads stay in the coverage, and in its payload.
    for key in ("tried_on", "units", "settings", "unit_tags"):
        assert key in coverage
    sent = backend.constrain_inputs[0]["options"][0]["coverage"]
    assert set(sent) == {"documents", "evaluated", "roles", "tried_on", "settings"}


def test_a_user_held_duplicate_is_never_merged(conn: Connection) -> None:
    walk = _walk(conn)
    kept, dup = _duplicate_pair(
        walk, exclusion={"constraint": None, "reason": "Keep it.", "by": "user"}
    )
    walk.build(StubLonglistBackend())

    _, summary = _constrain(walk, _duplicate_breach(kept, dup))

    assert _row(walk, dup).merged_into_option_id is None
    assert _row(walk, dup).state == "included"
    assert (_members(walk, kept), _members(walk, dup)) == (1, 1)
    assert _latest(walk).counts["merged"] == 0


class _RestatingBackend(StubLonglistBackend):
    """Discovers an option named like the merged duplicate."""

    def discover(self, **kwargs: Any) -> Any:
        del kwargs
        wire = DiscoveredOptionWire(
            label="Guarantee scheme",
            description="The scheme again.",
            design_features=["an offer"],
        )
        return OptionDiscoveryResponse(options=[wire], folds=[]), None


def test_a_rebuild_keeps_the_merge(conn: Connection) -> None:
    walk = _walk(conn)
    kept, dup = _duplicate_pair(walk)
    walk.build(StubLonglistBackend())
    _constrain(walk, _duplicate_breach(kept, dup))

    run_id, _ = walk.build(_RestatingBackend())
    _, summary = _constrain(walk, StubLonglistBackend())

    row = _row(walk, dup)  # never deleted, still merged
    assert row.merged_into_option_id == kept
    result = walk.result(run_id)
    assert str(dup) not in result.provenance["seed_ids"]
    assert result.provenance["clustering"]["restated_seeds_dropped"] == 1
    assert [r.option_id for r in walk.options().values() if r.name == "Guarantee scheme"] == [dup]
    assert _members(walk, dup) == 0
    assert str(dup) not in _latest(walk).judgements  # not judged again
    assert summary["options"] == len(walk.options()) - 1


def test_a_duplicate_whose_kept_option_is_excluded_stays_on_the_list(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"))
    kept, dup = _duplicate_pair(walk)
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [kept, dup], ["req-1", *SCREEN_IDS], verdicts={(kept, "req-1"): "breaks"}
        ),
        distinct_responses=_pairs((dup, kept, "The same offer.")),
    )

    _, summary = _constrain(walk, backend)

    assert _row(walk, kept).state == "excluded"
    row = _row(walk, dup)
    assert (row.merged_into_option_id, row.state) == (None, "included")
    distinct = _latest(walk).judgements[str(dup)]["1"]["distinct"]
    assert (distinct["verdict"], distinct["reason"]) == ("passes", DUPLICATE_KEPT_REASON)
    assert (summary["excluded"], _latest(walk).counts["merged"]) == (1, 0)


def test_unknown_same_repeated_and_chain_pairs_are_dropped_and_counted(
    conn: Connection,
) -> None:
    walk = _walk(conn)
    t0 = now()
    a, b, c, d = (
        walk.option(name, created_at=t0 + timedelta(seconds=i))
        for i, name in enumerate(["Option A", "Option B", "Option C", "Option D"])
    )
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        distinct_responses=_pairs(
            (a, uuid.uuid4(), "Names an option not on the list."),
            ("not-an-id", b, "Names nothing."),
            (c, c, "The same id twice."),
            (b, a, "B is A."),  # kept: a merge
            (b, d, "B again."),  # repeated
            (d, b, "D is B."),  # chain: B is itself a duplicate
        )
    )

    _, summary = _constrain(walk, backend)

    assert _row(walk, b).merged_into_option_id == a
    for oid in (a, c, d):
        row = _row(walk, oid)
        assert (row.merged_into_option_id, row.state) == (None, "included")
        distinct = _latest(walk).judgements[str(oid)]["1"]["distinct"]
        assert (distinct["verdict"], distinct["reason"]) == ("passes", DISTINCT_PASSES_REASON)
    assert summary["excluded"] == 0
    stats = _latest(walk).provenance["constrain"]["distinct"]
    assert stats["pairs"] == 1
    assert stats["dropped"] == {"unknown_id": 2, "same_id": 1, "repeated": 1, "chain": 1}


def test_the_distinct_call_receives_every_option_before_the_batches(conn: Connection) -> None:
    walk = _walk(conn)
    t0 = now()
    ids = [
        walk.option(f"Option {i}", created_at=t0 + timedelta(seconds=i))
        for i in range(CONSTRAIN_BATCH_SIZE + 2)
    ]
    users = walk.option("Your option", origin="added_by_you", created_at=t0)
    walk.build(StubLonglistBackend())
    calls: list[str] = []

    class _Ordered(StubLonglistBackend):
        def distinct(self, *, options: list[dict[str, object]]) -> Any:
            calls.append("distinct")
            return super().distinct(options=options)

        def constrain(self, **kwargs: Any) -> Any:
            calls.append("batch")
            return super().constrain(**kwargs)

    backend = _Ordered()

    _constrain(walk, backend)

    assert backend.distinct_calls == 1
    assert calls == ["distinct", "batch", "batch"]
    sent = backend.distinct_inputs[0]
    assert {o["option_id"] for o in sent} == {str(oid) for oid in [*ids, users]}
    assert set(sent[0]) == {
        "option_id",
        "label",
        "description",
        "design_features",
        "origin",
        "relations",
    }
    origins = {o["option_id"]: o["origin"] for o in sent}
    assert origins[str(users)] == "added by you"
    assert origins[str(ids[0])] == "suggested by Policy Atlas"


def test_a_failed_distinct_call_gives_cannot_check_and_no_merge(conn: Connection) -> None:
    walk = _walk(conn)
    kept, dup = _duplicate_pair(walk)
    walk.build(StubLonglistBackend())

    class _DistinctDown(StubLonglistBackend):
        def distinct(self, *, options: list[dict[str, object]]) -> Any:
            self.distinct_calls += 1
            raise RuntimeError("malformed answer")

    backend = _DistinctDown()

    _, summary = _constrain(walk, backend)

    assert backend.distinct_calls == 2  # the call and its one retry
    for oid in (kept, dup):
        row = _row(walk, oid)
        assert (row.merged_into_option_id, row.state) == (None, "included")
        distinct = _latest(walk).judgements[str(oid)]["1"]["distinct"]
        assert (distinct["verdict"], distinct["reason"]) == (
            "cannot_check",
            JUDGEMENT_UNAVAILABLE,
        )
    assert summary["cannot_check"] == 2 and summary["excluded"] == 0
    latest = _latest(walk)
    assert latest.counts["merged"] == 0
    assert latest.provenance["constrain"]["distinct"]["failed"] is True
    assert (_members(walk, kept), _members(walk, dup)) == (1, 1)


def test_thin_evidence_never_excludes(conn: Connection) -> None:
    """A zero-document option passes every screen its design passes."""
    walk = _walk(conn, _requirement("No benefit sanctions"))
    empty = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    # What a silent design with no documents yields: nothing checkable.
    ids = ["req-1", *SCREEN_IDS]
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [empty], ids, verdicts={(empty, cid): "cannot_check" for cid in ids}
        )
    )

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
                "guess": "May or may not meet it.",
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


@pytest.mark.parametrize("bare_first", [True, False])
def test_doi_twins_keep_the_snapshot_with_the_most_metadata(
    conn: Connection, bare_first: bool
) -> None:
    """Whatever the row order, the twin that names a country is the one read."""
    walk = _walk(conn, UK_ONLY)
    oid = walk.option("Youth guarantee")
    bare = {"doi": "10.1000/twin"}
    french = {"doi": "https://doi.org/10.1000/TWIN", "publication_country": "FR"}
    metas = [bare, french] if bare_first else [french, bare]
    docs = [_inherited_doc(walk, meta) for meta in metas]
    for doc in docs:
        walk.record(doc, "youth guarantee")
    walk.rollup(walk.scope_id, docs)
    walk.build(StubLonglistBackend())

    plan = scoping_plan(constraints=[UK_ONLY])
    checked = in_scope_evidence(conn, task_id=walk.task_id, plan=plan, option_ids=[oid])

    assert checked[oid]["documents"] == 1
    assert checked[oid]["no_in_scope_evidence"] is True


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
            baseline_sections: list[tuple[str, str]],
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


def test_a_failed_batch_keeps_the_prior_state(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"))
    prior = {"constraint": "No benefit sanctions", "reason": "Old.", "by": "constrain"}
    was_out = walk.option("Was excluded", state="excluded", exclusion=prior)
    was_in = walk.option("Was included")
    walk.build(StubLonglistBackend())
    malformed = _response([uuid.uuid4()], ["req-1", *SCREEN_IDS])
    backend = StubLonglistBackend(constrain_responses=malformed)

    _, summary = _constrain(walk, backend)

    assert (_row(walk, was_out).state, _row(walk, was_out).exclusion) == ("excluded", prior)
    assert (_row(walk, was_in).state, _row(walk, was_in).exclusion) == ("included", None)
    assert summary["excluded"] == 1
    assert _latest(walk).counts["excluded"] == 1


def test_a_breach_with_a_blank_reason_makes_the_batch_malformed(conn: Connection) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"))
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    blank = _response(
        [oid],
        ["req-1", *SCREEN_IDS],
        verdicts={(oid, "req-1"): "breaks"},
        reasons={(oid, "req-1"): "  "},
    )
    backend = StubLonglistBackend(constrain_responses=blank)

    _constrain(walk, backend)

    assert backend.constrain_calls == 2
    assert _row(walk, oid).state == "included"
    record = _latest(walk).judgements[str(oid)]["1"]["req-1"]
    assert (record["verdict"], record["reason"]) == ("cannot_check", JUDGEMENT_UNAVAILABLE)
    assert _latest(walk).provenance["constrain"]["failed_batches"] == 1


def test_a_malformed_batch_is_retried_once(conn: Connection) -> None:
    walk = _walk(conn)
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    wrong_id = _response([uuid.uuid4()], SCREEN_IDS)
    good = _response([oid], SCREEN_IDS, verdicts={(oid, "in_scope"): "breaks"})
    backend = StubLonglistBackend(constrain_responses=[wrong_id, good])

    _constrain(walk, backend)

    assert backend.constrain_calls == 2
    assert _row(walk, oid).exclusion["constraint"] == STORED_SCREEN_TEXT["in_scope"]


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

    # The batches run in parallel, so they may answer in either order.
    assert sorted(len(call["options"]) for call in backend.constrain_inputs) == [
        2,
        CONSTRAIN_BATCH_SIZE,
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
    assert set(_latest(walk).judgements[str(oid)]["1"]) == set(STORED_SCREEN_IDS)


# --- task 046: place, the payload, the baseline, the kind of action, parallel ------------


def test_no_place_reaches_the_plan_data_and_the_removal_is_recorded(conn: Connection) -> None:
    """Item 10 (R4, AM7): the plan fields hold no token the where-tried matcher
    recognises; a requirement that names a place reaches the prompt verbatim."""
    council = "Only options a council in England can run"
    plan = scoping_plan(
        question="What could reduce the number of young people not in work in Greater Manchester?",
        intended_change={
            "text": "Reduce the number of young people not in work in the UK",
            "origin": "from_your_question",
        },
        constraints=[_requirement(council)],
    )
    raw = json.dumps([plan.question, plan.intended_change.text])
    assert names_place(raw)  # the plan names places ...
    walk = _Walk(conn, plan)
    walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    sent = backend.constrain_inputs[0]
    # ... and none reaches the prompt's plan data.
    assert not names_place(json.dumps(sent["plan"], ensure_ascii=False))
    assert sent["plan"] == {
        "question": "What could reduce the number of young people not in work?",
        "target_unit": "16 to 24 year olds",
        "intended_change": "Reduce the number of young people not in work",
        "outcomes": ["the NEET rate"],
    }
    assert _latest(walk).provenance["constrain"]["place_removed"] == [
        "in Greater Manchester",
        "in the UK",
    ]
    assert sent["requirements"][0] == {"id": "req-1", "text": council}


def test_the_option_payload_has_no_where_tried(conn: Connection) -> None:
    """AM7: ``where_tried`` leaves the payload; the role counts and *tried on* stay."""
    walk = _walk(conn)
    oid = walk.option("Youth guarantee")
    doc = walk.doc()
    walk.record(doc, "Youth guarantee")
    walk.rollup(walk.scope_id, [doc])
    walk.build(StubLonglistBackend())
    assert "where_tried" in _latest(walk).coverage[str(oid)]  # the build still writes it
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    coverage = backend.constrain_inputs[0]["options"][0]["coverage"]
    assert set(coverage) == {"documents", "evaluated", "roles", "tried_on", "settings"}
    assert coverage["documents"] == 1
    assert "where_tried" not in repr(backend.constrain_inputs)


def test_the_baseline_reaches_the_batches(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    walk = _walk(conn)
    walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    sections = [("What is in place now", "A national youth guarantee runs today.")]
    seen: list[uuid.UUID] = []

    def _baseline(_conn: Connection, task_id: uuid.UUID) -> list[tuple[str, str]]:
        seen.append(task_id)
        return sections

    monkeypatch.setattr(constrain_module, "baseline_sections", _baseline)
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    assert seen == [walk.task_id]
    assert backend.constrain_inputs[0]["baseline_sections"] == sections


def test_silence_passes_and_a_setting_break_excludes_with_the_requirement_named(
    conn: Connection,
) -> None:
    """Item 11 (R21), stub level: the component keeps a silent design, excludes a
    kind of action that cannot be delivered through the setting with the
    requirement named, and keeps a ``cannot_check``."""
    setting = "Delivered through health visiting, midwifery or family hub services"
    walk = _walk(conn, _requirement(setting, setting=True))
    silent = walk.option("Parenting support")
    tax = walk.option("National sugar tax")
    unknown = walk.option("Infant feeding advice")
    walk.build(StubLonglistBackend())
    reason = "A national tax cannot be delivered through health visiting."
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [silent, tax, unknown],
            ["req-1", *SCREEN_IDS],
            verdicts={(tax, "req-1"): "breaks", (unknown, "req-1"): "cannot_check"},
            reasons={
                (silent, "req-1"): "The design names no setting.",
                (tax, "req-1"): reason,
            },
        )
    )

    _, summary = _constrain(walk, backend)

    assert (_row(walk, silent).state, _row(walk, silent).exclusion) == ("included", None)
    assert _row(walk, tax).state == "excluded"
    assert _row(walk, tax).exclusion == {"constraint": setting, "reason": reason, "by": "constrain"}
    assert _latest(walk).judgements[str(tax)]["1"]["req-1"] == {
        "verdict": "breaks",
        "reason": reason,
        "constraint_text": setting,
    }
    assert (_row(walk, unknown).state, _row(walk, unknown).exclusion) == ("included", None)
    assert (summary["excluded"], summary["cannot_check"]) == (1, 1)


def test_a_pathway_only_option_reaches_the_prompt_and_passes_relevant(conn: Connection) -> None:
    """AM6: no listed outcome, members reporting only a pathway outcome; the design
    and the description still reach the prompt, and ``passes`` keeps it."""
    walk = _walk(conn)
    design = {
        "name": "Sugar reformulation",
        "description": "Producers cut the sugar in everyday foods.",
        "design_features": ["voluntary targets for producers"],
        "outcomes_served": [],
    }
    oid = walk.option(
        "Sugar reformulation",
        outcomes=[],
        design=design,
        description=design["description"],
    )
    doc = walk.doc()
    walk.record(doc, "Sugar reformulation", outcome="sugar intake")
    walk.rollup(walk.scope_id, [doc])
    walk.build(StubLonglistBackend())
    backend = StubLonglistBackend(
        constrain_responses=_response(
            [oid],
            SCREEN_IDS,
            reasons={(oid, "relevant"): "Less sugar leads to lower obesity prevalence."},
        )
    )

    _constrain(walk, backend)

    sent = backend.constrain_inputs[0]["options"][0]
    assert sent["outcomes_served"] == []
    assert sent["description"] == "Producers cut the sugar in everyday foods."
    assert sent["design_features"] == ["voluntary targets for producers"]
    assert (_row(walk, oid).state, _row(walk, oid).exclusion) == ("included", None)
    assert _latest(walk).judgements[str(oid)]["1"]["relevant"]["verdict"] == "passes"


def test_the_batches_run_in_parallel(conn: Connection) -> None:
    walk = _walk(conn)
    for i in range(2 * CONSTRAIN_BATCH_SIZE + 1):
        walk.option(f"Option {i}")
    walk.build(StubLonglistBackend())
    barrier = threading.Barrier(3, timeout=10)

    class _Barrier(StubLonglistBackend):
        def constrain(self, **kwargs: Any) -> Any:
            barrier.wait()  # only passes when the three batches are in flight at once
            return super().constrain(**kwargs)

    backend = _Barrier()

    _, summary = _constrain(walk, backend)

    assert backend.constrain_calls == 3
    assert summary["options"] == 2 * CONSTRAIN_BATCH_SIZE + 1
    assert _latest(walk).provenance["constrain"]["failed_batches"] == 0


# --- task 046, amendment 2: the authority label (R38, S18) --------------------------------

WHO_CAN_ACT = "Only the council can act; it cannot change national law"


def _who_decides(text: str = WHO_CAN_ACT, *, hard: bool = True) -> dict[str, Any]:
    return _consideration(text, aspect="who_decides", hard=hard)


def _run_profile(walk: _Walk) -> None:
    """One ``option_profile`` run on the stub: every option not merged gets the
    ``who_decides`` sentence ``"Stub who_decides sentence."``."""
    option_profile_scope(
        walk.conn,
        task_id=walk.task_id,
        run_id=walk.run(),
        context=OptionProfileContext(scope_id=walk.scope_id, intent="longlist intent", context={}),
        backend=StubLonglistBackend(),
    )


def _set_who_decides(walk: _Walk, sentences: dict[uuid.UUID, tuple[int, str]]) -> None:
    """Write the latest row's ``option_profile``: per option, ``(design version,
    who_decides sentence)``; the other lines are left out (constrain reads one)."""
    profile = {
        str(oid): {str(version): {"lines": {"who_decides": {"sentence": text, "mark": None}}}}
        for oid, (version, text) in sentences.items()
    }
    walk.conn.execute(
        update(longlist_result)
        .where(longlist_result.c.longlist_result_id == _latest(walk).longlist_result_id)
        .values(option_profile=profile)
    )


def _labels(
    *entries: tuple[uuid.UUID, AuthorityLabel, str | None, str],
) -> AuthorityResponse:
    """An authority answer: ``(option, label, body, reason)`` per option."""
    return AuthorityResponse(
        options=[
            AuthorityWire(option_id=str(oid), label=label, body=body, reason=reason)
            for oid, label, body, reason in entries
        ]
    )


def test_no_consideration_on_who_decides_makes_no_call_and_no_label(conn: Connection) -> None:
    walk = _walk(conn, _consideration("At most £2m a year", aspect="cost", hard=True))
    oids = [walk.option("Youth guarantee"), walk.option("Wage subsidy")]
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    assert backend.authority_calls == 0
    latest = _latest(walk)
    assert all(AUTHORITY_KEY not in latest.judgements[str(oid)]["1"] for oid in oids)
    assert latest.provenance["constrain"]["authority"] == {"calls": 0}
    assert latest.counts["authority_labelled"] == 0


def test_one_authority_call_holds_every_profiled_option_and_the_users_texts(
    conn: Connection,
) -> None:
    second = "The combined authority can also act"
    walk = _walk(conn, _who_decides(), _who_decides(second, hard=False))
    oids = [walk.option(f"Option {i}") for i in range(CONSTRAIN_BATCH_SIZE + 2)]
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    backend = StubLonglistBackend()

    _, summary = _constrain(walk, backend)

    assert backend.authority_calls == 1  # one call over the whole list, never per batch
    sent = backend.authority_inputs[0]
    assert sent["considerations"] == [WHO_CAN_ACT, second]
    assert sorted(o["option_id"] for o in sent["options"]) == sorted(str(o) for o in oids)
    for entry in sent["options"]:
        assert set(entry) == {
            "option_id",
            "label",
            "description",
            "design_features",
            "who_decides",
        }
        assert entry["who_decides"] == "Stub who_decides sentence."
    latest = _latest(walk)
    for oid in oids:
        assert latest.judgements[str(oid)]["1"][AUTHORITY_KEY] == {
            "label": "unclear",
            "body": None,
            "reason": "Stub: unclear.",
            "consideration_text": f"{WHO_CAN_ACT} · {second}",
        }
    assert latest.counts["authority_labelled"] == len(oids)
    assert latest.provenance["constrain"]["authority"] == {
        "calls": 1,
        "retries": 0,
        "failed": False,
        "options": len(oids),
        "labels": {"within_your_power": 0, "needs_action_by": 0, "unclear": len(oids)},
    }
    # The label is not a check: the summary reads as it did.
    assert summary["cannot_check"] == 0 and summary["excluded"] == 0


def test_each_label_is_stored_with_its_reason_and_a_body_only_when_needed(
    conn: Connection,
) -> None:
    walk = _walk(conn, _who_decides())
    ours = walk.option("Council youth hub")
    theirs = walk.option("National sugar tax")
    unknown = walk.option("Wage subsidy")
    walk.build(StubLonglistBackend())
    _set_who_decides(
        walk,
        {
            ours: (1, "The local council decides."),
            theirs: (1, "HM Treasury decides, in the United Kingdom."),
            unknown: (1, "A council or the national government could decide."),
        },
    )
    backend = StubLonglistBackend(
        authority_responses=_labels(
            # A body on another label is dropped.
            (ours, "within_your_power", "The council", "The council decides."),
            (theirs, "needs_action_by", " HM Treasury ", "HM Treasury sets the tax."),
            (unknown, "unclear", None, "Either body could run it."),
        )
    )

    _constrain(walk, backend)

    judgements = _latest(walk).judgements
    stored = {oid: judgements[str(oid)]["1"][AUTHORITY_KEY] for oid in (ours, theirs, unknown)}
    assert {oid: (e["label"], e["body"], e["reason"]) for oid, e in stored.items()} == {
        ours: ("within_your_power", None, "The council decides."),
        theirs: ("needs_action_by", "HM Treasury", "HM Treasury sets the tax."),
        unknown: ("unclear", None, "Either body could run it."),
    }
    assert {e["consideration_text"] for e in stored.values()} == {WHO_CAN_ACT}
    assert _latest(walk).provenance["constrain"]["authority"]["labels"] == {
        "within_your_power": 1,
        "needs_action_by": 1,
        "unclear": 1,
    }


def test_no_exclusion_comes_from_the_label_or_from_any_consideration(conn: Connection) -> None:
    walk = _walk(
        conn,
        _who_decides(hard=True),
        _consideration("A budget of at most £2m a year", aspect="cost", hard=True),
    )
    oids = [walk.option("National sugar tax"), walk.option("Universal credit uplift")]
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    backend = StubLonglistBackend(
        authority_responses=_labels(
            *((oid, "needs_action_by", "HM Treasury", "Needs HM Treasury.") for oid in oids)
        )
    )

    _, summary = _constrain(walk, backend)

    assert all(_row(walk, oid).state == "included" for oid in oids)
    assert all(_row(walk, oid).exclusion is None for oid in oids)
    latest = _latest(walk)
    assert summary["excluded"] == 0 and latest.counts["excluded"] == 0
    assert latest.counts["included"] == len(oids)
    assert latest.counts["authority_labelled"] == len(oids)
    # Neither consideration is a requirement: the batches judge the screens only.
    assert backend.constrain_inputs[0]["requirements"] == [
        {"id": key, "text": label} for key, label in DEFAULT_SCREENS
    ]


def test_the_batches_and_the_distinct_call_get_no_who_decides_line_and_no_where(
    conn: Connection,
) -> None:
    where = "Scotland"
    plan = scoping_plan(
        where={"text": where, "origin": "your_call"},
        question="What could reduce the number of young people not in work in Scotland?",
        constraints=[_who_decides()],
    )
    walk = _Walk(conn, plan)
    first = walk.option("Youth guarantee")
    second = walk.option("Wage subsidy")
    walk.build(StubLonglistBackend())
    sentences = {
        first: (1, "The Scottish Government decides, in Scotland."),
        second: (1, "HM Treasury decides, in the United Kingdom."),
    }
    _set_who_decides(walk, sentences)
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    # The authority call reads the line (the one place exception) ...
    assert {o["who_decides"] for o in backend.authority_inputs[0]["options"]} == {
        text for _, text in sentences.values()
    }
    # ... and nothing else does.
    others = json.dumps(
        [backend.constrain_inputs, backend.distinct_inputs], ensure_ascii=False, default=str
    )
    assert "who_decides" not in others
    for _, text in sentences.values():
        assert text not in others
    assert where not in others
    assert "United Kingdom" not in others
    assert not names_place(json.dumps(backend.constrain_inputs[0]["plan"]))


def test_an_authority_call_malformed_twice_gives_no_label_and_the_step_succeeds(
    conn: Connection,
) -> None:
    walk = _walk(conn, _requirement("No benefit sanctions"), _who_decides())
    kept = walk.option("Youth guarantee")
    broken = walk.option("Sanctioned work search")
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    missing_option = _labels((kept, "unclear", None, "Either body."))
    no_body = _labels(
        (kept, "within_your_power", None, "The council decides."),
        (broken, "needs_action_by", "  ", "Another body decides."),
    )
    backend = StubLonglistBackend(
        authority_responses=[missing_option, no_body],
        constrain_responses=_response(
            [kept, broken], ["req-1", *SCREEN_IDS], verdicts={(broken, "req-1"): "breaks"}
        ),
    )

    _, summary = _constrain(walk, backend)

    assert backend.authority_calls == 2  # the call and its one retry
    latest = _latest(walk)
    assert all(AUTHORITY_KEY not in latest.judgements[str(oid)]["1"] for oid in (kept, broken))
    authority = latest.provenance["constrain"]["authority"]
    assert (authority["calls"], authority["retries"], authority["failed"]) == (2, 1, True)
    assert latest.counts["authority_labelled"] == 0
    # The verdicts are stored and act as before.
    assert latest.judgements[str(broken)]["1"]["req-1"]["verdict"] == "breaks"
    assert _row(walk, broken).state == "excluded"
    assert _row(walk, kept).state == "included"
    assert summary["excluded"] == 1


def test_an_authority_call_that_raises_is_tried_once_more(conn: Connection) -> None:
    walk = _walk(conn, _who_decides())
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    _run_profile(walk)

    class _Flaky(StubLonglistBackend):
        def authority(self, **kwargs: Any) -> Any:
            if self.authority_calls == 0:
                self.authority_calls += 1
                raise RuntimeError("provider down")
            return super().authority(**kwargs)

    backend = _Flaky()

    _constrain(walk, backend)

    assert backend.authority_calls == 2
    assert _latest(walk).judgements[str(oid)]["1"][AUTHORITY_KEY]["label"] == "unclear"
    authority = _latest(walk).provenance["constrain"]["authority"]
    assert (authority["retries"], authority["failed"]) == (1, False)


def test_the_option_read_model_lists_the_same_judgements_with_a_label(conn: Connection) -> None:
    assert repository.LONGLIST_AUTHORITY_KEY == AUTHORITY_KEY
    walk = _walk(conn, _requirement("No benefit sanctions"), _who_decides())
    oid = walk.option("Youth guarantee")
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    _constrain(walk, StubLonglistBackend())
    latest = _latest(walk)
    assert AUTHORITY_KEY in latest.judgements[str(oid)]["1"]

    with_label = repository.option_out(conn, walk.task_id, oid)
    listed = repository.longlist_out(conn, walk.task_id)
    stripped = {
        key: {"1": {k: v for k, v in record["1"].items() if k != AUTHORITY_KEY}}
        for key, record in latest.judgements.items()
    }
    conn.execute(
        update(longlist_result)
        .where(longlist_result.c.longlist_result_id == latest.longlist_result_id)
        .values(judgements=stripped)
    )
    without_label = repository.option_out(conn, walk.task_id, oid)

    assert with_label is not None and without_label is not None
    assert with_label.judgements == without_label.judgements
    assert [j.constraint_id for j in with_label.judgements] == ["req-1", *STORED_SCREEN_IDS]
    assert listed is not None and listed.options[0].option_id == oid


def test_an_option_with_no_profile_entry_is_not_sent_and_gets_no_label(
    conn: Connection,
) -> None:
    walk = _walk(conn, _who_decides())
    profiled = walk.option("Youth guarantee")
    added = walk.option("Added by you", origin="added_by_you")
    redesigned = walk.option("Wage subsidy", design_version=2)
    walk.build(StubLonglistBackend())
    # ``added`` has no entry; ``redesigned`` has one for an older design only.
    _set_who_decides(
        walk,
        {profiled: (1, "The council decides."), redesigned: (1, "The council decides.")},
    )
    backend = StubLonglistBackend()

    _constrain(walk, backend)

    assert [o["option_id"] for o in backend.authority_inputs[0]["options"]] == [str(profiled)]
    judgements = _latest(walk).judgements
    assert AUTHORITY_KEY in judgements[str(profiled)]["1"]
    assert AUTHORITY_KEY not in judgements[str(added)]["1"]
    assert AUTHORITY_KEY not in judgements[str(redesigned)]["2"]
    assert _latest(walk).counts["authority_labelled"] == 1


def test_a_duplicate_merged_in_this_run_gets_no_label(conn: Connection) -> None:
    walk = _walk(conn, _who_decides())
    kept, dup = _duplicate_pair(walk)
    walk.build(StubLonglistBackend())
    _run_profile(walk)
    backend = _duplicate_breach(kept, dup)

    _constrain(walk, backend)

    assert _row(walk, dup).merged_into_option_id == kept
    judgements = _latest(walk).judgements
    assert AUTHORITY_KEY in judgements[str(kept)]["1"]
    assert AUTHORITY_KEY not in judgements[str(dup)]["1"]
    assert _latest(walk).counts["authority_labelled"] == 1
