"""The link pick, box folds, Crossref abstracts and the cost line (task 054, C28 to C30)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    event_log,
    source_snapshot,
    toc_box,
    toc_link,
    toc_pathway_link,
)
from policy_atlas.evidence_search.sourcing.search_live import crossref_abstracts
from policy_atlas.theory_of_change import check, store
from policy_atlas.theory_of_change.backend import StubTocBackend, stub_draft
from policy_atlas.theory_of_change.check import (
    LINK_LISTS,
    LinkCandidate,
    fold_box,
    fold_problem,
    picked_ids,
)
from policy_atlas.theory_of_change.cost import usd
from policy_atlas.theory_of_change.draft_prompt import DraftLinkWire, DraftPathwayWire
from policy_atlas.theory_of_change.evidence.pick_prompt import PICK_N
from policy_atlas.theory_of_change.merge_prompt import BoxMergeWire, MergeResponse
from tests.helpers import seed_source, seed_task_and_run
from tests.theory_of_change.test_check_steps import _replies, _run, _summary
from tests.theory_of_change.test_walks import seed_toc

# --- the pick (C28) ---------------------------------------------------------------


def _cands(n: int) -> list[LinkCandidate]:
    q1 = LINK_LISTS[0]
    return [LinkCandidate(uuid.UUID(int=i), q1, i, abstract="a") for i in range(1, n + 1)]


def test_pick_ids_map_back_drop_unknown_and_top_up() -> None:
    cands = _cands(15)
    chosen = picked_ids(["d3", "zz", "d3", "d12"], cands)
    # d3 and d12 first; the unknown and the repeat dropped; topped up in round-robin order.
    assert [t.int for t in chosen] == [3, 12, 1, 2, 4, 5, 6, 7, 8, 9]
    assert len(chosen) == PICK_N


def test_each_link_with_more_than_ten_documents_gets_one_pick_call(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend()
    task_id = _run(engine, cleanup, backend, per_call=12)
    summary = _summary(engine, task_id, "toc_select")
    assert summary["pick_calls"] == 5 and summary["failed_pick_calls"] == 0
    assert summary["relevant"] == 5 * PICK_N
    shown = backend.inputs["pick"][0]["candidates"]
    assert [c["id"] for c in shown[:3]] == ["d1", "d2", "d3"]
    assert "usage_totals" in summary


def test_a_failed_pick_call_falls_back_to_round_robin(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = StubTocBackend({"pick": [RuntimeError("down")] * 10})
    task_id = _run(engine, cleanup, backend, per_call=12)
    summary = _summary(engine, task_id, "toc_select")
    assert summary["failed_pick_calls"] == 5
    # Round-robin picks 10 per link; with the shared pool two links may pick one document.
    assert all(len(ids) == PICK_N for ids in _picks(engine, task_id).values())
    assert summary["relevant"] <= 5 * PICK_N


# --- box folds (C29) --------------------------------------------------------------


def _fold_draft(*, user_wrote_b7: bool = False, self_loop: bool = False) -> Any:
    """The stub draft plus b7, a short-term outcome box repeating b3 ("Behaviour changes")."""
    draft = stub_draft({})
    b3 = next(box for box in draft.boxes if box.key == "b3")
    b7 = b3.model_copy(
        update={"key": "b7", "text": "Behaviour shifts", "from_user_theory": user_wrote_b7}
    )
    l2 = next(link for link in draft.links if link.key == "l2")

    def link(key: str, source: str, target: str) -> DraftLinkWire:
        return l2.model_copy(
            update={"key": key, "source": source, "target": target, "sentence": f"Step {key}."}
        )

    links = [*draft.links, link("l6", "b2", "b7"), link("l7", "b7", "b6")]
    if self_loop:
        links.append(link("l8", "b7", "b3"))
    return draft.model_copy(
        update={
            "boxes": [*draft.boxes, b7],
            "links": links,
            "pathways": [
                *draft.pathways,
                DraftPathwayWire(
                    key="p3",
                    kind="success",
                    label="Second route",
                    links=["l1", "l6", "l8", "l3", "l5"] if self_loop else ["l1", "l6", "l7", "l5"],
                ),
            ],
        }
    )


def _graph(
    engine: Engine, cleanup: list[uuid.UUID], draft: Any
) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    task_id, _ = seed_toc(engine)
    cleanup.append(task_id)
    with engine.begin() as conn:
        ids = store.write_draft(conn, task_id=task_id, run_id=None, draft=draft)
    return task_id, ids


def test_a_fold_repoints_links_and_joins_a_doubled_link(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, ids = _graph(engine, cleanup, _fold_draft(self_loop=True))
    with engine.begin() as conn:
        log_ = store.ChangeLog()
        assert fold_box(conn, log_, task_id=task_id, box=str(ids["b7"]), into=str(ids["b3"]))
        boxes = set(
            conn.execute(select(toc_box.c.box_id).where(toc_box.c.task_id == task_id)).scalars()
        )
        links = {
            row.link_id: (row.source_box_id, row.target_box_id)
            for row in conn.execute(select(toc_link).where(toc_link.c.task_id == task_id))
        }
        steps = conn.execute(
            select(toc_pathway_link.c.pathway_id, toc_pathway_link.c.link_id)
            .where(toc_pathway_link.c.task_id == task_id)
            .order_by(toc_pathway_link.c.pathway_id, toc_pathway_link.c.position)
        ).all()
    assert ids["b7"] not in boxes
    assert all(ids["b7"] not in pair for pair in links.values())
    # b2→b7 became b2→b3, which l2 already was: the older link, l2, is kept.
    assert ids["l6"] not in links and links[ids["l2"]] == (ids["b2"], ids["b3"])
    # b7→b3 became b3→b3: dropped from its pathway and deleted.
    assert ids["l8"] not in links
    # One link per pair; every pathway step points at a link that exists.
    assert len(set(links.values())) == len(links)
    assert all(link_id in links for _, link_id in steps)
    p3 = [link_id for pid, link_id in steps if pid == ids["p3"]]
    assert p3 == [ids["l1"], ids["l2"], ids["l3"], ids["l5"]]
    assert any(entry.get("deleted") for entry in log_.before)


def test_codes_follow_the_layer_and_a_deleted_code_is_never_reused(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, ids = _graph(engine, cleanup, _fold_draft())
    with engine.begin() as conn:
        codes = {
            row.box_id: row.code
            for row in conn.execute(select(toc_box).where(toc_box.c.task_id == task_id))
        }
        assert {key: codes[ids[key]] for key in ("b1", "b2", "b3", "b4", "b5", "b6", "b7")} == {
            "b1": "A1", "b2": "P1", "b3": "S1", "b4": "I1", "b5": "F1", "b6": "L1", "b7": "S2"
        }
        link_codes = conn.execute(
            select(toc_link.c.code).where(toc_link.c.task_id == task_id)
        ).scalars()
        assert sorted(link_codes) == sorted(f"#{n}" for n in range(1, 8))
        # Fold away S2 (the highest S) and record the step: a new box gets S3, not S2.
        log_ = store.ChangeLog()
        assert fold_box(conn, log_, task_id=task_id, box=str(ids["b7"]), into=str(ids["b3"]))
        store.record(conn, task_id=task_id, run_id=None, step="toc_merge", log=log_)
        new_box = uuid.uuid4()
        store.insert(
            conn,
            store.ChangeLog(),
            toc_box,
            {"box_id": new_box, "task_id": task_id, "layer": "outcome_short", "text": "New",
             "result_criteria": {}, "origin": "user"},
        )
        assert conn.execute(
            select(toc_box.c.code).where(toc_box.c.box_id == new_box)
        ).scalar_one() == "S3"


def test_a_fold_keeps_the_user_edited_copy_of_a_doubled_link(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, ids = _graph(engine, cleanup, _fold_draft())
    with engine.begin() as conn:
        conn.execute(
            toc_link.update().where(toc_link.c.link_id == ids["l7"]).values(user_edited=True)
        )
        assert fold_box(
            conn, store.ChangeLog(), task_id=task_id, box=str(ids["b7"]), into=str(ids["b3"])
        )
        links = {
            row.link_id: (row.source_box_id, row.target_box_id)
            for row in conn.execute(select(toc_link).where(toc_link.c.task_id == task_id))
        }
    # b7→b6 became b3→b6, as l3 is: the user-edited l7 is kept, though newer.
    assert ids["l3"] not in links and links[ids["l7"]] == (ids["b3"], ids["b6"])


def test_a_fold_across_layers_or_from_a_user_box_is_refused(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id, ids = _graph(engine, cleanup, _fold_draft(user_wrote_b7=True))
    with engine.begin() as conn:
        _, rows = store.load_graph(conn, task_id)
        b = {key: str(ids[key]) for key in ("b1", "b3", "b4", "b7")}
        assert fold_problem(rows, b["b3"], b["b4"]) == "the boxes are in different layers"
        assert fold_problem(rows, b["b3"], b["b3"]) == "it is the same box"
        assert fold_problem(rows, b["b7"], b["b3"]) is not None  # user box into a drafted one
        assert fold_problem(rows, b["b3"], b["b7"]) is None  # the other way is fine
        assert not fold_box(conn, store.ChangeLog(), task_id=task_id, box=b["b7"], into=b["b3"])
        assert not fold_box(conn, store.ChangeLog(), task_id=task_id, box=b["b1"], into=b["b4"])
        remaining = set(
            conn.execute(select(toc_box.c.box_id).where(toc_box.c.task_id == task_id)).scalars()
        )
    assert ids["b7"] in remaining and ids["b1"] in remaining


def test_merge_folds_boxes_first_and_the_thread_lists_it(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    merge = MergeResponse(box_merges=[BoxMergeWire(box="b7", into="b3")], decisions=[])
    backend = StubTocBackend({"draft": [_fold_draft()], "merge": [merge]})
    task_id = _run(engine, cleanup, backend)
    sent = backend.inputs["merge"][0]["boxes"]
    assert {box["key"] for box in sent} >= {"b3", "b7"}
    assert _summary(engine, task_id, "toc_merge")["box_folds"] == 1
    assert "Merged box “Behaviour shifts” into “Behaviour changes”" in _replies(engine, task_id)[-1]


# --- Crossref abstracts (C30) ------------------------------------------------------


def test_crossref_abstracts_strip_jats_and_skip_failures(monkeypatch: Any) -> None:
    monkeypatch.setenv("OPENALEX_EMAIL", "team@example.org")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "10.1/ok" in str(request.url):
            body = {
                "message": {
                    "abstract": "<jats:p>Ads fell &amp; <jats:italic>so</jats:italic>"
                    " did snacking.</jats:p>"
                }
            }
            return httpx.Response(200, content=json.dumps(body))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert crossref_abstracts(["10.1/ok", "10.1/missing"], client=client) == {
        "10.1/ok": "Ads fell & so did snacking."
    }
    assert crossref_abstracts([], client=client) == {}
    assert len(seen) == 2


def test_found_abstracts_are_stored_on_the_snapshot(conn: Connection, monkeypatch: Any) -> None:
    task_id, _ = seed_task_and_run(conn)
    snap_id, tss_id = seed_source(conn, task_id, {"title": "A trial", "doi": "10.1/x"})
    monkeypatch.setattr(check, "crossref_abstracts", lambda dois: {"10.1/x": "An abstract."})
    cand = LinkCandidate(
        tss_id, LINK_LISTS[0], 1, title="A trial", doi="10.1/x", snapshot_id=snap_id
    )
    filled = check._fill_abstracts(conn, {"l": [cand]})
    assert filled["l"][0].abstract == "An abstract."
    metadata = conn.execute(
        select(source_snapshot.c.metadata).where(source_snapshot.c.source_snapshot_id == snap_id)
    ).scalar_one()
    assert metadata["abstract"] == "An abstract." and metadata["abstract_source"] == "crossref"


# --- the cost line (C30) ----------------------------------------------------------


def test_cost_prices_known_models_and_leaves_others_unpriced() -> None:
    tokens = {"prompt": 1_000_000, "cached": 400_000, "completion": 100_000}
    # 600k input at 1.00, 400k cached at 0.05, 100k output at 5.00.
    assert usd("gpt-6.1-terra", tokens) == 0.6 + 0.02 + 0.5
    assert usd("some-new-model", tokens) is None


def test_a_toc_walk_records_its_cost_on_its_finish_event(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    task_id = _run(engine, cleanup, StubTocBackend())
    with engine.connect() as conn:
        finished = (
            conn.execute(
                select(event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == "run.finished")
            )
            .scalars()
            .all()
        )
    costs = [payload["cost"] for payload in finished if "cost" in payload]
    assert costs and all({"steps", "usd", "unpriced"} <= set(cost) for cost in costs)


# --- round 3 (C31) ----------------------------------------------------------------


def _picks(engine: Engine, task_id: uuid.UUID) -> dict[str, list[str]]:
    with engine.connect() as conn:
        return dict(
            conn.execute(
                select(event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == check.PICKED_EVENT)
            ).scalar_one()
        )


class _PicksTheShared(StubTocBackend):
    """Picks the last 10 candidates: the shared ones from other links' searches."""

    def pick(self, *, item_text: str, candidates: list[dict[str, object]]) -> Any:
        from policy_atlas.theory_of_change.evidence.pick_prompt import PickResponse

        self._next("pick", {"candidates": candidates})
        return PickResponse(ids=[str(c["id"]) for c in candidates[-PICK_N:]]), None


def test_a_link_can_pick_and_judge_a_study_another_link_found(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.core.schema import toc_item_evidence

    task_id = _run(engine, cleanup, _PicksTheShared(), per_call=12)
    assert _summary(engine, task_id, "toc_select")["shared_candidates"] == 5 * PICK_N
    picks = _picks(engine, task_id)
    with engine.connect() as conn:
        walk_id = conn.execute(
            select(toc_item_evidence.c.capability_run_id).where(
                toc_item_evidence.c.task_id == task_id
            )
        ).first()[0]  # type: ignore[index]
        own = check._own_search_documents(conn, task_id=task_id, walk_id=walk_id)
        judged = conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.task_source_snapshot_id).where(
                toc_item_evidence.c.task_id == task_id
            )
        ).all()
    for link_id, ids in picks.items():
        # Every pick came from other links' searches, and the judge read exactly those.
        assert not {uuid.UUID(i) for i in ids} & own[link_id]
        assert {tss for lid, tss in judged if str(lid) == link_id} == {uuid.UUID(i) for i in ids}


class _JudgesHalfOffTopic(StubTocBackend):
    """Not about the step for documents whose id ends in an even hex digit."""

    def judge(self, **kwargs: Any) -> Any:
        from policy_atlas.theory_of_change.evidence.judge_prompt import JudgeResponse, StanceWire

        if int(str(kwargs["document_id"])[-1], 16) % 2 == 0:
            self._next("judge", kwargs)
            off = StanceWire(stance="not_about", quote=None)
            return JudgeResponse(
                worked_elsewhere=off,
                holds_here=off,
                condition=None,
                case_study=None,
                indicator=None,
                robust_model=None,
            ), None
        return super().judge(**kwargs)


def test_classify_reads_only_what_the_judge_found_on_topic(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.core.schema import source_classification_result, toc_item_evidence

    task_id = _run(engine, cleanup, _JudgesHalfOffTopic(), per_call=12)
    judge = _summary(engine, task_id, "toc_judge")
    assert judge["screened_out_not_about"] > 0
    with engine.connect() as conn:
        on_topic = set(
            conn.execute(
                select(toc_item_evidence.c.task_source_snapshot_id)
                .where(toc_item_evidence.c.task_id == task_id)
                .where(toc_item_evidence.c.stance_elsewhere == "supports")
            ).scalars()
        )
        classified = set(
            conn.execute(
                select(source_classification_result.c.task_source_snapshot_id).where(
                    source_classification_result.c.task_id == task_id
                )
            ).scalars()
        )
    assert on_topic and classified == on_topic


def test_crossref_retries_once_after_a_429() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=json.dumps({"message": {"abstract": "Found."}}))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert crossref_abstracts(["10.1/a"], client=client) == {"10.1/a": "Found."}
    assert len(calls) == 2


# --- the links discovery adds get their own search (C32) --------------------------


def test_a_discovered_link_gets_its_own_search_pick_and_judgement(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    from policy_atlas.core.schema import capability_run, evidence_scope, toc_item_evidence, toc_link
    from policy_atlas.runtime.option_search import TOC_NEW_LINK_SEARCHES_STAGE
    from tests.theory_of_change.test_check_steps import _Discovers

    task_id = _run(engine, cleanup, _Discovers())
    assert _summary(engine, task_id, TOC_NEW_LINK_SEARCHES_STAGE)["total"] == 2
    new = _summary(engine, task_id, "toc_search_new")
    assert new["links"] == 2
    picks = _picks_latest(engine, task_id)
    with engine.connect() as conn:
        found = {
            str(link_id)
            for link_id in conn.execute(
                select(toc_link.c.link_id).where(
                    toc_link.c.task_id == task_id, toc_link.c.origin == "found_in_evidence"
                )
            ).scalars()
        }
        searched = {
            str((context or {}).get("link_id"))
            for context in conn.execute(
                select(evidence_scope.c.context)
                .join(
                    capability_run,
                    capability_run.c.evidence_scope_id == evidence_scope.c.evidence_scope_id,
                )
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.parent_capability_run_id.is_not(None))
            ).scalars()
        }
        judged = conn.execute(
            select(toc_item_evidence.c.link_id, toc_item_evidence.c.task_source_snapshot_id).where(
                toc_item_evidence.c.task_id == task_id
            )
        ).all()
    assert len(found) == 2 and found <= searched
    # The earlier links' picks are kept beside the new ones.
    assert found < set(picks) and len(picks) > len(found)
    for link_id in found:
        assert picks[link_id]
        # The judge read the discovered link's picks.
        assert {tss for lid, tss in judged if str(lid) == link_id} == {
            uuid.UUID(i) for i in picks[link_id]
        }


def _picks_latest(engine: Engine, task_id: uuid.UUID) -> dict[str, list[str]]:
    with engine.connect() as conn:
        return dict(
            conn.execute(
                select(event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(event_log.c.event_type == check.PICKED_EVENT)
                .order_by(event_log.c.sequence.desc())
                .limit(1)
            ).scalar_one()
        )
