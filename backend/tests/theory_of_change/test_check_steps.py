"""The check walk's steps on stub backends (task 054, step 1.4; C2, C5, C6, C19, C20)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_graph_out
from policy_atlas.core.schema import (
    event_log,
    task_agent_transcript,
    toc_box,
    toc_item_evidence,
    toc_link,
    toc_pathway,
)
from policy_atlas.runtime.capability_registry import THEORY_OF_CHANGE, compose_plan, lattice_for
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.steering import pause_points
from policy_atlas.theory_of_change.backend import StubTocBackend, stub_draft
from policy_atlas.theory_of_change.check import (
    CASE_STUDIES_PER_BOX,
    JUDGE_TOP_K,
    UNSETTLED_SENTENCE,
    critical_link,
    links_to_check,
    neighbour_lines,
    top_case_studies,
)
from policy_atlas.theory_of_change.discover_prompt import (
    CONSOLIDATE_MAX_NEW_SUCCESS,
    ConsolidatedPathwayWire,
    ConsolidateResponse,
    DiscoverResponse,
    EvidenceWire,
    NewBoxWire,
    NewLinkWire,
    ProposalWire,
)
from policy_atlas.theory_of_change.draft_prompt import DraftPathwayWire
from policy_atlas.theory_of_change.evidence.grade import Grade, GradeResult
from policy_atlas.theory_of_change.evidence.judge_prompt import JudgeResponse, StanceWire
from policy_atlas.theory_of_change.graph import Box, Graph, Link, Pathway
from policy_atlas.theory_of_change.summary_prompt import LinkSentencesWire
from tests.theory_of_change.test_walks import (
    Records,
    _start,
    seed_toc,
    toc_plan,
)


def _summary(engine: Engine, task_id: uuid.UUID, component: str) -> dict[str, Any]:
    with engine.connect() as conn:
        payload = conn.execute(
            select(event_log.c.payload)
            .where(event_log.c.task_id == task_id)
            .where(event_log.c.event_type == "component.completed")
            .where(event_log.c.payload["component"].astext == component)
            .order_by(event_log.c.sequence.desc())
            .limit(1)
        ).scalar_one()
    return dict(payload)


def _run(
    engine: Engine, cleanup: list[uuid.UUID], backend: StubTocBackend, per_call: int = 2
) -> uuid.UUID:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    _start(
        engine,
        task_id,
        plan_row,
        RunnerBackends(search_backends=[Records(per_call)], toc=backend),
    )
    return task_id


# --- pure rules -----------------------------------------------------------------


def test_a_toc_walk_never_pauses() -> None:
    for walk in ("draft", "check"):
        chain = compose_plan(
            THEORY_OF_CHANGE, toc_plan(), purpose="toc", context={"toc_walk": walk}
        )
        assert not pause_points("unattended", chain, lattice_for(THEORY_OF_CHANGE))


def test_the_80_link_cap_takes_kept_pathway_links_first() -> None:
    boxes = {f"b{i}": Box(key=f"b{i}", layer="outcome", text=f"box {i}") for i in range(100)}
    links = {
        f"l{i}": Link(key=f"l{i}", source=f"b{i}", target=f"b{i + 1}", conditions=["c"])
        for i in range(90)
    }
    tail = [f"l{i}" for i in range(85, 90)]
    graph = Graph(boxes=boxes, links=links, pathways=[Pathway(key="p", kind="success", links=tail)])
    keys, left_out = links_to_check(graph)
    assert len(keys) == 80 and left_out == 10
    assert keys[:5] == tail


def test_neighbour_lines_name_the_steps_before_and_after() -> None:
    boxes = {k: Box(key=k, layer="outcome", text=k) for k in ("a", "b", "c", "d")}
    links = {
        "ab": Link(key="ab", source="a", target="b", sentence="A leads to B."),
        "bc": Link(key="bc", source="b", target="c", sentence="B leads to C."),
        "cd": Link(key="cd", source="c", target="d"),  # no sentence: the fallback
    }
    graph = Graph(boxes=boxes, links=links, pathways=[])
    assert neighbour_lines(graph, "bc") == "Before: A leads to B.\nAfter: c leads to d"
    assert neighbour_lines(graph, "ab") == "After: B leads to C."
    lone = Graph(boxes=boxes, links={"ab": links["ab"]}, pathways=[])
    assert neighbour_lines(lone, "ab") == ""


def test_each_judge_call_carries_its_neighbouring_steps(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend()
    _run(engine, cleanup, backend)
    sent = {call["neighbours"] for call in backend.inputs["judge"]}
    # Stub draft: l1 b1->b2, l2 b2->b3, l3 b3->b4, l4 b2->b5.
    assert "Before: Step l1 leads on.\nAfter: Step l3 leads on." in sent  # l2
    assert "After: Step l2 leads on.\nAfter: Step l4 leads on." in sent  # l1


def test_case_studies_are_deduplicated_ranked_and_capped() -> None:
    candidates = [
        ("low", "Scheme", "Leeds", 2, True),
        ("dup", "scheme ", "LEEDS", 5, False),  # same programme and place, better score
        ("challenge", "Other", None, 4, False),
        ("support", "Third", None, 4, True),
        *[(f"x{i}", f"P{i}", None, 1, False) for i in range(6)],
    ]
    kept = top_case_studies(candidates)
    assert kept[:3] == ["dup", "support", "challenge"]
    assert "low" not in kept and len(kept) == CASE_STUDIES_PER_BOX
    assert kept[3:] == ["x0", "x1"]


def _grades(pairs: dict[str, tuple[Grade, Grade]]) -> dict[str, tuple[GradeResult, GradeResult]]:
    return {
        key: (
            GradeResult(grade=a, against=0, supports=0),
            GradeResult(grade=b, against=0, supports=0),
        )
        for key, (a, b) in pairs.items()
    }


def test_the_critical_connection_follows_the_c6_rule() -> None:
    boxes = {k: Box(key=k, layer="outcome", text=k) for k in ("a", "b", "c", "d")}
    links = {
        "l1": Link(key="l1", source="a", target="b"),
        "l2": Link(key="l2", source="b", target="c"),
        "l3": Link(key="l3", source="c", target="d"),
    }
    pathways = [
        Pathway(key="p1", kind="success", links=["l1", "l2"]),
        Pathway(key="p2", kind="success", links=["l2", "l3"]),
        Pathway(key="p3", kind="failure", links=["l3"]),
    ]
    graph = Graph(boxes=boxes, links=links, pathways=pathways)
    # Worked elsewhere, weak here: l1 and l2 qualify; l2 is on more pathways.
    grades = _grades({"l1": ("strong", "weak"), "l2": ("medium", "none"), "l3": ("weak", "none")})
    assert critical_link(graph, grades) == "l2"
    # Tie on pathway count: the earlier one in pathway order.
    graph.pathways = [Pathway(key="p1", kind="success", links=["l1", "l3"])]
    grades = _grades({"l1": ("strong", "weak"), "l3": ("medium", "none")})
    assert critical_link(graph, grades) == "l1"
    # None qualifies: the lowest holds-here grade.
    grades = _grades({"l1": ("weak", "medium"), "l3": ("none", "weak")})
    assert critical_link(graph, grades) == "l3"


# --- the walk -------------------------------------------------------------------


class _Unverifiable(StubTocBackend):
    """Every judge quote is a passage the document does not contain."""

    def judge(self, **kwargs: Any) -> Any:
        self._next("judge", kwargs)
        stance = StanceWire(stance="supports", quote="words that appear in no abstract at all")
        response = JudgeResponse(
            worked_elsewhere=stance,
            holds_here=StanceWire(stance="not_about", quote=None),
            condition=None,
            case_study=None,
            indicator=None,
            robust_model=None,
        )
        return response, None


def test_an_unverified_quote_is_dropped_and_counted(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = _Unverifiable()
    task_id = _run(engine, cleanup, backend)
    judge = _summary(engine, task_id, "toc_judge")
    assert judge["unverified_dropped"] == judge["calls"] == backend.calls["judge"] > 0
    with engine.connect() as conn:
        stances = (
            conn.execute(
                select(toc_item_evidence.c.stance_elsewhere).where(
                    toc_item_evidence.c.task_id == task_id
                )
            )
            .scalars()
            .all()
        )
    # Still stored: the row shows the document was read.
    assert stances and set(stances) == {"not_about"}


def test_each_link_reads_at_most_k_documents_of_its_own_search(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, StubTocBackend(), per_call=12)
    with engine.connect() as conn:
        per_link = conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.task_source_snapshot_id).where(
                toc_item_evidence.c.task_id == task_id
            )
        ).all()
    counts: dict[uuid.UUID, int] = {}
    for link_id, _tss in per_link:
        counts[link_id] = counts.get(link_id, 0) + 1
    assert counts and max(counts.values()) == JUDGE_TOP_K
    # Each link read only documents its own search found.
    assert len({tss for _, tss in per_link}) == len(per_link)
    stage = _summary(engine, task_id, "toc_item_searches")
    assert stage["total"] == 4 and stage["failed"] == 0


class _Discovers(StubTocBackend):
    """Proposes one success route through a new outcome box, quoting the first document."""

    conditions: tuple[str, ...] = ("It holds",)

    def discover(self, *, plan: Any, theory: Any, documents: Any) -> Any:
        self._next("discover", {})
        if self.calls["discover"] > 1:  # one proposal, from the first batch only
            return DiscoverResponse(proposals=[]), None
        keys = {box["layer"]: box["key"] for box in theory["boxes"]}
        doc = documents[0]
        quote = " ".join(str(doc["abstract"]).split()[:6])
        link: dict[str, Any] = {
            "sentence": "A new step.",
            "if_text": "if",
            "for_text": "for",
            "then_text": "then",
            "because_text": "because",
            "conditions": list(self.conditions),
        }
        proposal = ProposalWire(
            kind="success",
            label="Found route",
            route=[keys["input"], "n1", keys["impact"]],
            new_boxes=[NewBoxWire(key="n1", layer="outcome", text="Families cook at home")],
            new_links=[
                NewLinkWire(source=keys["input"], target="n1", **link),
                NewLinkWire(source="n1", target=keys["impact"], **link),
            ],
            evidence=[EvidenceWire(document_id=str(doc["id"]), quote=quote)],
        )
        return DiscoverResponse(proposals=[proposal]), None


def test_discovered_links_are_judged_against_the_whole_pool(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _Discovers())
    with engine.connect() as conn:
        found = (
            conn.execute(
                select(toc_link.c.link_id).where(
                    toc_link.c.task_id == task_id, toc_link.c.origin == "found_in_evidence"
                )
            )
            .scalars()
            .all()
        )
        assert len(found) == 2
        pool = (
            conn.execute(
                select(toc_item_evidence.c.task_source_snapshot_id)
                .where(toc_item_evidence.c.task_id == task_id)
                .distinct()
            )
            .scalars()
            .all()
        )
        for link_id in found:
            judged = (
                conn.execute(
                    select(toc_item_evidence.c.task_source_snapshot_id).where(
                        toc_item_evidence.c.link_id == link_id
                    )
                )
                .scalars()
                .all()
            )
            # No search of its own: the whole screened-in pool, up to K.
            assert len(judged) == min(JUDGE_TOP_K, len(pool))
        pathway = conn.execute(
            select(toc_pathway.c.label).where(
                toc_pathway.c.task_id == task_id, toc_pathway.c.origin == "found_in_evidence"
            )
        ).scalar_one()
    assert pathway == "Found route"


class _DiscoversRepeats2(_Discovers):
    """The first batch proposes one route twice, each with its own copy of a box."""

    def discover(self, *, plan: Any, theory: Any, documents: Any) -> Any:
        response, usage = super().discover(plan=plan, theory=theory, documents=documents)
        twice = [response.proposals[0], response.proposals[0]] if response.proposals else []
        return DiscoverResponse(proposals=twice), usage


def _joined(paths: int, *, from_proposals: list[str]) -> Any:
    """A consolidate answer: ``paths`` success routes through one shared new box."""

    def respond(proposals: list[dict[str, Any]]) -> ConsolidateResponse:
        first = proposals[0]
        route = list(first["route"])
        link = {k: v for k, v in first["new_links"][0].items() if k not in ("source", "target")}
        return ConsolidateResponse(
            new_boxes=[NewBoxWire(key="n1", layer="outcome", text="Families cook at home")],
            pathways=[
                ConsolidatedPathwayWire(
                    kind="success",
                    label=f"Joined route {i}",
                    from_proposals=from_proposals,
                    route=[route[0], "n1", route[-1]],
                    new_links=[
                        NewLinkWire(source=route[0], target="n1", **link),
                        NewLinkWire(source="n1", target=route[-1], **link),
                    ],
                )
                for i in range(paths)
            ],
        )

    return respond


class _Consolidates(_DiscoversRepeats2):
    paths = 1
    from_proposals: tuple[str, ...] = ("q1", "q2")

    def consolidate(self, **kwargs: Any) -> Any:
        self._next("consolidate", {"proposals": kwargs["proposals"]})
        respond = _joined(self.paths, from_proposals=list(self.from_proposals))
        return respond(kwargs["proposals"]), None


def _found(engine: Engine, task_id: uuid.UUID) -> tuple[list[str], list[str]]:
    with engine.connect() as conn:
        boxes = conn.execute(
            select(toc_box.c.text).where(
                toc_box.c.task_id == task_id, toc_box.c.origin == "found_in_evidence"
            )
        ).scalars()
        labels = conn.execute(
            select(toc_pathway.c.label).where(
                toc_pathway.c.task_id == task_id, toc_pathway.c.origin == "found_in_evidence"
            )
        ).scalars()
        return list(boxes), sorted(labels)


def test_repeated_proposals_are_joined_into_one_pathway_and_one_box(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = _Consolidates()
    task_id = _run(engine, cleanup, backend)
    # Consolidate saw both proposals, each with its own key for the same box.
    [call] = backend.inputs["consolidate"]
    assert [p["id"] for p in call["proposals"]] == ["q1", "q2"]
    assert {p["route"][1] for p in call["proposals"]} == {"q1n1", "q2n1"}
    assert _found(engine, task_id) == (["Families cook at home"], ["Joined route 0"])


class _ConsolidatesTooMany(_Consolidates):
    paths = CONSOLIDATE_MAX_NEW_SUCCESS + 2


def test_consolidate_adds_at_most_the_new_pathway_limit(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _ConsolidatesTooMany())
    boxes, labels = _found(engine, task_id)
    assert boxes == ["Families cook at home"]  # written once, shared by every route
    assert 1 <= len(labels) <= CONSOLIDATE_MAX_NEW_SUCCESS
    assert _summary(engine, task_id, "toc_discover")["rejected"] >= 2


class _ConsolidatesUnknown(_Consolidates):
    from_proposals = ("q9",)


def test_a_pathway_that_joins_no_checked_proposal_is_dropped(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _ConsolidatesUnknown())
    assert _found(engine, task_id) == ([], [])


class _Conditions(StubTocBackend):
    """Supports record a condition; choose adds every recorded one."""

    def judge(self, **kwargs: Any) -> Any:
        response, usage = super().judge(**kwargs)
        return response.model_copy(update={"condition": "Only where schools take part"}), usage

    def choose(self, **kwargs: Any) -> Any:
        from policy_atlas.theory_of_change.choose_prompt import AddedConditionWire

        response, usage = super().choose(**kwargs)
        added = [
            AddedConditionWire(link=str(item["link"]), condition=str(item["recorded"][0]))
            for item in kwargs["recorded_conditions"]
        ]
        return response.model_copy(update={"added_conditions": added}), usage


class _DiscoversRepeats(_Discovers):
    # One existing condition (stub draft link l1), two new, one over the cap.
    conditions = ("Condition for l1 holds", "It holds", "Third", "Fourth")


def test_a_discovered_link_never_repeats_a_condition_and_keeps_two(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _DiscoversRepeats())
    with engine.connect() as conn:
        found = (
            conn.execute(
                select(toc_link.c.conditions).where(
                    toc_link.c.task_id == task_id, toc_link.c.origin == "found_in_evidence"
                )
            )
            .scalars()
            .all()
        )
    # The first new link drops l1's condition and keeps two; the second takes
    # only the one the first left over.
    assert sorted(found, key=len) == [["Fourth"], ["It holds", "Third"]]


class _ConditionsOverTheRule(StubTocBackend):
    """Choose adds two conditions to one link and repeats one on another."""

    def judge(self, **kwargs: Any) -> Any:
        response, usage = super().judge(**kwargs)
        return response.model_copy(update={"condition": "Recorded"}), usage

    def choose(self, **kwargs: Any) -> Any:
        from policy_atlas.theory_of_change.choose_prompt import AddedConditionWire

        response, usage = super().choose(**kwargs)
        first, second = (str(item["link"]) for item in kwargs["recorded_conditions"][:2])
        added = [
            AddedConditionWire(link=first, condition="Fresh one"),
            AddedConditionWire(link=first, condition="Fresh two"),  # over the cap of 2
            AddedConditionWire(link=second, condition="fresh  ONE"),  # already on first
        ]
        return response.model_copy(update={"added_conditions": added}), usage


def test_choose_keeps_the_conditions_rule_and_counts_what_it_skipped(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _ConditionsOverTheRule())
    choose = _summary(engine, task_id, "toc_choose")
    assert choose["conditions_added"] == 1 and choose["conditions_skipped"] == 2
    with engine.connect() as conn:
        out = toc_graph_out(conn, task_id)
    assert sum("Fresh one" in link.conditions for link in out.links) == 1
    assert all(len(link.conditions) <= 2 for link in out.links)


def test_a_condition_added_by_choose_leaves_the_link_checked(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = _Conditions()
    task_id = _run(engine, cleanup, backend)
    assert backend.calls["choose"] == 1
    with engine.connect() as conn:
        out = toc_graph_out(conn, task_id)
    added = [link for link in out.links if "Only where schools take part" in link.conditions]
    assert added
    assert {link.state for link in added} == {"checked"}


def _many_pathways() -> Any:
    draft = stub_draft({})
    success = [
        DraftPathwayWire(key=f"s{i}", kind="success", label=f"Route {i}", links=["l1", "l2", "l3"])
        for i in range(8)
    ]
    failure = [
        DraftPathwayWire(key=f"f{i}", kind="failure", label=f"Fails {i}", links=["l1", "l4"])
        for i in range(4)
    ]
    return draft.model_copy(update={"pathways": success + failure})


def test_choose_keeps_at_most_six_success_and_three_failure_pathways(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend({"draft": [_many_pathways()]})
    task_id = _run(engine, cleanup, backend)
    assert backend.calls["choose"] == 1
    with engine.connect() as conn:
        rows = conn.execute(
            select(toc_pathway.c.kind, toc_pathway.c.status).where(toc_pathway.c.task_id == task_id)
        ).all()
    kept = [kind for kind, status in rows if status == "kept"]
    assert kept.count("success") == 6 and kept.count("failure") == 3


class _BadCitation(StubTocBackend):
    """Every link sentence cites a document the link never judged."""

    def summarise(self, *, plan: Any, theory: Any) -> Any:
        response, usage = super().summarise(plan=plan, theory=theory)
        links = [
            LinkSentencesWire(
                link=str(link["key"]),
                elsewhere_sentence="A study showed it.",
                elsewhere_cites=[str(uuid.uuid4())],
                here_sentence=None,
                here_cites=[],
            )
            for link in theory["links"]
        ]
        return response.model_copy(update={"links": links}), usage


def test_the_citation_check_replaces_a_bad_sentence(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, _BadCitation())
    assert _summary(engine, task_id, "toc_summarise")["replaced"] > 0
    with engine.connect() as conn:
        sentences = conn.execute(
            select(toc_link.c.elsewhere_sentence, toc_link.c.here_sentence).where(
                toc_link.c.task_id == task_id
            )
        ).all()
    assert {e for e, _ in sentences} == {UNSETTLED_SENTENCE}
    # No document spoke to "holds here": the fixed sentence, without the model.
    assert {h for _, h in sentences} == {"No evidence was found in the documents read."}


def _two_success_draft() -> Any:
    draft = stub_draft({})
    return draft.model_copy(
        update={
            "pathways": [
                *draft.pathways,
                DraftPathwayWire(
                    key="p3", kind="success", label="Second route", links=["l1", "l2", "l3"]
                ),
            ]
        }
    )


def test_merge_keeps_one_of_each_kind_and_the_thread_lists_its_changes(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.api.toc_start import STRESS_TEST_MESSAGE
    from policy_atlas.theory_of_change.merge_prompt import MergeDecisionWire, MergeResponse

    merge = MergeResponse(
        decisions=[
            MergeDecisionWire(pathway="p1", action="set_aside", into=None, reason="Misses it."),
            MergeDecisionWire(pathway="p2", action="set_aside", into=None, reason="Misses it."),
            MergeDecisionWire(pathway="p3", action="merge", into="p1", reason="Same mechanism."),
        ]
    )
    backend = StubTocBackend({"draft": [_two_success_draft()], "merge": [merge]})
    task_id = _run(engine, cleanup, backend)
    with engine.connect() as conn:
        rows = {
            row.label: (row.status, row.reason)
            for row in conn.execute(
                select(toc_pathway.c.label, toc_pathway.c.status, toc_pathway.c.reason).where(
                    toc_pathway.c.task_id == task_id
                )
            )
        }
        replies = (
            conn.execute(
                select(task_agent_transcript.c.reply)
                .where(task_agent_transcript.c.task_id == task_id)
                .order_by(task_agent_transcript.c.turn_index)
            )
            .scalars()
            .all()
        )
    # The model set aside every pathway; code keeps the first of each kind back.
    assert rows["Main route"][0] == "kept" and rows["Low take-up"][0] == "kept"
    assert rows["Second route"] == ("set_aside", "Merged into “Main route”: Same mechanism.")
    assert "Merged pathway “Second route” into “Main route”" in replies[-1]
    assert replies[-1].endswith(STRESS_TEST_MESSAGE)


def _replies(engine: Engine, task_id: uuid.UUID) -> list[str]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(task_agent_transcript.c.reply)
                .where(task_agent_transcript.c.task_id == task_id)
                .order_by(task_agent_transcript.c.turn_index)
            ).scalars()
        )


class _DiscoversThenMerges(_Discovers):
    """The found route is merged into the first success pathway in the same check."""

    def merge(self, *, plan: Any, pathways: Any) -> Any:
        from policy_atlas.theory_of_change.merge_prompt import MergeDecisionWire, MergeResponse

        self._next("merge", {})
        first = next(p for p in pathways if p["kind"] == "success")
        decisions = [
            MergeDecisionWire(
                pathway=str(p["key"]),
                action="merge" if p["label"] == "Found route" else "keep",
                into=str(first["key"]) if p["label"] == "Found route" else None,
                reason="Same mechanism.",
            )
            for p in pathways
        ]
        return MergeResponse(decisions=decisions), None


def test_the_check_message_names_found_pathways_it_kept_once(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    reply = _replies(engine, _run(engine, cleanup, _Discovers()))[-1]
    assert "Added 1 pathway found in the evidence: “Found route”." in reply
    assert "from the evidence: Found route" not in reply


def test_the_check_message_leaves_out_a_found_pathway_merged_in_the_same_check(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    reply = _replies(engine, _run(engine, cleanup, _DiscoversThenMerges()))[-1]
    assert "Found route" not in reply
    assert "Merged pathway" not in reply


def test_an_os_longlist_and_a_toc_check_join_side_by_side(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    import threading

    from policy_atlas.runtime.runner import NullIO, run_plan
    from tests.runtime.test_acquire_only_walk import _FreshRecords
    from tests.runtime.test_option_search import _longlist_plan, _seed_longlist

    plan = _longlist_plan("Youth guarantee", "Wage subsidy")
    os_task, scope_id, plan_id = _seed_longlist(engine, plan)
    cleanup.append(os_task)
    outcomes: dict[str, Any] = {}

    def longlist() -> None:
        outcomes["os"] = run_plan(
            engine,
            task_id=os_task,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=RunnerBackends(search_backends=[_FreshRecords()]),
            io=NullIO(),
            session_id=os_task,
        )

    thread = threading.Thread(target=longlist)
    thread.start()
    toc_task = _run(engine, cleanup, StubTocBackend())
    thread.join(timeout=120)
    assert outcomes["os"].status == "succeeded"
    assert _summary(engine, os_task, "option_searches")["failed"] == 0
    assert _summary(engine, toc_task, "toc_item_searches")["failed"] == 0


def test_judge_candidates_are_reranked_by_select_s_rerank_backend() -> None:
    from policy_atlas.core.usage import UsageAccumulator
    from policy_atlas.evidence_search.corpus.ranking import StubRankingBackend
    from policy_atlas.theory_of_change.check import Document, rerank

    docs = [
        Document(
            tss_id=uuid.uuid4(),
            title=f"t{i}",
            year=None,
            abstract="a",
            evidence_type=None,
            score=None,
        )
        for i in range(12)
    ]
    ranker = StubRankingBackend()
    ranked = rerank(ranker, docs, intent="the step", usage=UsageAccumulator())
    scores, _ = ranker.rank(
        [{"id": str(d.tss_id), "title": d.title, "abstract": d.abstract} for d in docs],
        intent="the step",
    )
    by_id = {item["doc_id"]: item["score"] for item in scores}
    assert [by_id[str(d.tss_id)] for d in ranked] == sorted(by_id.values(), reverse=True)
    # No backend: the candidates' own order.
    assert rerank(None, docs, intent="x", usage=UsageAccumulator()) == docs
