"""The liveness hub: coalescing, heartbeats, remembered state and the context helpers (task 058).

Every test drives a ``TickHub`` with a fake clock and no scheduler, calling
``flush()`` and ``sweep()`` by hand. Messages reach a subscriber queue through
its event loop, so each test yields to the loop before draining the queue.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable, Coroutine
from typing import Any, get_args

import pytest

from policy_atlas.api.contract import StageKey
from policy_atlas.core import liveness
from policy_atlas.core.liveness import (
    COALESCE_SECONDS,
    DELTA_COALESCE_SECONDS,
    DRAFT_MAX_CHARS,
    HEARTBEAT_SECONDS,
    MEMORY_TTL_SECONDS,
    HubMessage,
    SectionCard,
    SectionClaim,
    SectionDelta,
    SectionRevising,
    SectionSources,
    SourceNote,
    Tick,
    TickHub,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _run(test: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(test())


async def _drain(queue: asyncio.Queue[HubMessage]) -> list[HubMessage]:
    # Two yields: one for the hub's call_soon_threadsafe callbacks to run.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    out: list[HubMessage] = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


def _ticks(messages: list[HubMessage]) -> list[Tick]:
    assert all(isinstance(m, Tick) for m in messages)
    return [m for m in messages if isinstance(m, Tick)]


def _hub(**kwargs: Any) -> tuple[TickHub, FakeClock]:
    clock = FakeClock()
    return TickHub(clock=clock, schedule=None, **kwargs), clock


TASK = uuid.UUID(int=1)


def test_a_burst_coalesces_to_one_tick_now_and_the_latest_after_the_window() -> None:
    async def body() -> None:
        hub, clock = _hub()
        queue = await hub.subscribe(TASK)
        for i in range(50):
            clock.now = i * 0.3 / 49
            hub.publish_tick(
                TASK, stage="classify", activity=f"line {i}", done=i, total=50, unit="documents"
            )
        first = _ticks(await _drain(queue))
        assert [t.activity for t in first] == ["line 0"]

        hub.flush()  # the window is still open: nothing goes out
        assert await _drain(queue) == []

        clock.now = COALESCE_SECONDS + 0.01
        hub.flush()
        second = _ticks(await _drain(queue))
        assert len(second) == 1
        assert (second[0].activity, second[0].done, second[0].total, second[0].unit) == (
            "line 49",
            49,
            50,
            "documents",
        )
        hub.flush()
        assert await _drain(queue) == []

    _run(body)


def test_two_stages_coalesce_independently() -> None:
    async def body() -> None:
        hub, clock = _hub()
        queue = await hub.subscribe(TASK)
        for i in range(10):
            clock.now = i * 0.01
            hub.publish_tick(TASK, stage="screen", activity=f"screen {i}")
            hub.publish_tick(TASK, stage="classify", activity=f"classify {i}")
        ticks = _ticks(await _drain(queue))
        assert [(t.stage, t.activity) for t in ticks] == [
            ("screen", "screen 0"),
            ("classify", "classify 0"),
        ]

    _run(body)


def test_heartbeats_repeat_the_last_tick_every_ten_seconds_while_a_call_is_open() -> None:
    async def body() -> None:
        hub, clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.call_opened(TASK, "classify")
        hub.publish_tick(TASK, stage="classify", activity="Classifying", done=3, total=9)
        original = _ticks(await _drain(queue))[0]

        beats: list[float] = []
        for at in (10.0, 20.0, 30.0, 35.0):
            clock.now = at
            hub.sweep()
            for tick in _ticks(await _drain(queue)):
                beats.append(at)
                assert tick.heartbeat is True
                assert (tick.stage, tick.activity, tick.done, tick.total, tick.unit) == (
                    original.stage,
                    original.activity,
                    original.done,
                    original.total,
                    original.unit,
                )
        assert beats == [10.0, 20.0, 30.0]

        hub.call_closed(TASK, "classify")
        clock.now = 60.0
        hub.sweep()
        assert await _drain(queue) == []

    _run(body)


def test_a_hook_tick_never_overwrites_a_loop_tick_but_a_loop_tick_overwrites_a_hook() -> None:
    async def body() -> None:
        hub, clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_tick(TASK, stage="classify", activity="3 of 9 documents")
        clock.now = 0.1
        hub.publish_tick(TASK, stage="classify", activity="Classifying", source="hook")
        clock.now = 0.2  # held: the hook still loses to the held loop tick
        hub.publish_tick(TASK, stage="classify", activity="4 of 9 documents")
        hub.publish_tick(TASK, stage="classify", activity="Classifying", source="hook")
        clock.now = 2.0
        hub.flush()
        assert [t.activity for t in _ticks(await _drain(queue))] == [
            "3 of 9 documents",
            "4 of 9 documents",
        ]

        hub.publish_tick(TASK, stage="screen", activity="Screening", source="hook")
        clock.now = 3.0
        hub.publish_tick(TASK, stage="screen", activity="5 of 9 documents")
        assert [t.activity for t in _ticks(await _drain(queue))] == [
            "Screening",
            "5 of 9 documents",
        ]
        _queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        assert [m.activity for m in snapshot if isinstance(m, Tick)] == [
            "4 of 9 documents",
            "5 of 9 documents",
        ]

    _run(body)


def test_snapshot_gives_a_mid_stage_mid_section_client_the_last_ticks_then_the_draft() -> None:
    async def body() -> None:
        hub, clock = _hub()
        hub.publish_tick(TASK, stage="classify", activity="done classifying")
        hub.publish_tick(TASK, stage="synthesise", activity="first", section="Costs")
        clock.now = 1.0
        hub.publish_tick(TASK, stage="synthesise", activity="Writing", section="Costs")
        hub.flush()
        hub.publish_delta(TASK, index=2, text="The first ")
        hub.publish_delta(TASK, index=2, text="sentence.")

        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        assert len(snapshot) == 3
        classify, synthesise, draft = snapshot
        assert isinstance(classify, Tick) and classify.activity == "done classifying"
        assert isinstance(synthesise, Tick) and synthesise.activity == "Writing"
        assert synthesise.heartbeat is False
        assert isinstance(draft, SectionDelta)
        assert (draft.index, draft.text, draft.mode) == (2, "The first sentence.", "replace")

        # Later text reaches the new client as appends after its replace.
        hub.publish_delta(TASK, index=2, text=" More.")
        clock.now = 2.0
        hub.flush()
        later = await _drain(queue)
        assert len(later) == 1 and isinstance(later[0], SectionDelta)
        assert (later[0].text, later[0].mode) == (" More.", "append")

    _run(body)


def test_a_tick_published_during_subscription_lands_exactly_once() -> None:
    async def body() -> None:
        for publish_first in (True, False):
            hub, _clock = _hub()
            barrier = threading.Barrier(2)
            done = threading.Event()

            def publish(
                h: TickHub = hub, b: threading.Barrier = barrier, d: threading.Event = done
            ) -> None:
                b.wait()
                h.publish_tick(TASK, stage="classify", activity="racing")
                d.set()

            thread = threading.Thread(target=publish)
            thread.start()
            if publish_first:
                barrier.wait()
                done.wait(timeout=5)
                queue, snapshot = await hub.subscribe_with_snapshot(TASK)
            else:
                # Hold the hub lock so the publisher blocks inside publish_tick
                # until the subscription has taken its snapshot.
                hub._lock.acquire()
                barrier.wait()
                assert not done.wait(timeout=0.05)
                hub._lock.release()
                queue, snapshot = await hub.subscribe_with_snapshot(TASK)
                done.wait(timeout=5)
            thread.join(timeout=5)
            queued = await _drain(queue)
            seen = [m for m in snapshot + queued if isinstance(m, Tick)]
            assert [t.activity for t in seen] == ["racing"]

    _run(body)


def test_a_publish_racing_the_snapshot_from_a_thread_is_never_lost_or_doubled() -> None:
    async def body() -> None:
        for _ in range(50):
            hub, _clock = _hub()
            start = threading.Barrier(2)

            def publish(h: TickHub = hub, b: threading.Barrier = start) -> None:
                b.wait()
                h.publish_tick(TASK, stage="classify", activity="racing")

            thread = threading.Thread(target=publish)
            thread.start()
            start.wait()
            queue, snapshot = await hub.subscribe_with_snapshot(TASK)
            thread.join(timeout=5)
            queued = await _drain(queue)
            seen = [m for m in snapshot + queued if isinstance(m, Tick)]
            assert [t.activity for t in seen] == ["racing"]

    _run(body)


def test_the_draft_concatenates_resets_and_is_capped_while_the_stream_is_not() -> None:
    async def body() -> None:
        hub, clock = _hub()

        async def draft() -> SectionDelta:
            queue, snapshot = await hub.subscribe_with_snapshot(TASK)
            await hub.unsubscribe(TASK, queue)
            last = snapshot[-1]
            assert isinstance(last, SectionDelta)
            return last

        hub.publish_delta(TASK, index=0, text="Alpha ")
        hub.publish_delta(TASK, index=0, text="beta")
        assert (await draft()).text == "Alpha beta"

        hub.publish_delta(TASK, index=0, text="Fresh", mode="replace")
        assert (await draft()).text == "Fresh"

        hub.publish_delta(TASK, index=1, text="Next section")
        current = await draft()
        assert (current.index, current.text) == (1, "Next section")

        queue = await hub.subscribe(TASK)
        long_text = "x" * (DRAFT_MAX_CHARS + 500)
        hub.publish_delta(TASK, index=3, text=long_text, mode="replace")
        sent = await _drain(queue)
        assert isinstance(sent[-1], SectionDelta) and sent[-1].text == long_text
        await hub.unsubscribe(TASK, queue)
        assert len((await draft()).text) == DRAFT_MAX_CHARS

        clock.now = 10.0
        hub.publish_delta(TASK, index=4, text="y" * (DRAFT_MAX_CHARS + 10))
        hub.publish_delta(TASK, index=4, text="z")
        kept = await draft()
        assert len(kept.text) == DRAFT_MAX_CHARS

    _run(body)


def test_appends_merge_and_replace_and_revising_flush_the_held_append_first() -> None:
    async def body() -> None:
        hub, clock = _hub()
        queue = await hub.subscribe(TASK)
        for i, piece in enumerate(("One ", "two ", "three.")):
            clock.now = i * 0.03
            hub.publish_delta(TASK, index=0, text=piece)
        assert await _drain(queue) == []
        clock.now = DELTA_COALESCE_SECONDS + 0.01
        hub.flush()
        merged = await _drain(queue)
        assert len(merged) == 1 and isinstance(merged[0], SectionDelta)
        assert (merged[0].text, merged[0].mode) == ("One two three.", "append")

        hub.publish_delta(TASK, index=0, text=" Four.")
        hub.publish_delta(TASK, index=0, text="Rewritten.", mode="replace")
        ordered = await _drain(queue)
        assert [(m.text, m.mode) for m in ordered if isinstance(m, SectionDelta)] == [
            (" Four.", "append"),
            ("Rewritten.", "replace"),
        ]

        hub.publish_delta(TASK, index=0, text=" Five.")
        hub.publish_revising(TASK, index=0, spans=[(0, 10)])
        revising = await _drain(queue)
        assert isinstance(revising[0], SectionDelta) and revising[0].text == " Five."
        assert isinstance(revising[1], SectionRevising)
        assert revising[1].spans == ((0, 10),)

    _run(body)


def test_runs_and_stages_clear_only_their_own_memory() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        parent, child = uuid.uuid4(), uuid.uuid4()

        async def snapshot() -> list[HubMessage]:
            queue, messages = await hub.subscribe_with_snapshot(TASK)
            await hub.unsubscribe(TASK, queue)
            return messages

        def fill() -> None:
            hub.publish_tick(TASK, stage="option_searches", activity="2 of 5 searches")
            hub.publish_tick(TASK, stage="synthesise", activity="Writing")
            hub.publish_delta(TASK, index=0, text="Draft", mode="replace")
            hub.call_opened(TASK, "synthesise")

        hub.begin_run(TASK, parent)
        fill()
        assert len(await snapshot()) == 3

        hub.begin_run(TASK, child, parent_run_id=parent)
        assert len(await snapshot()) == 3
        hub.end_run(TASK, child)
        assert len(await snapshot()) == 3

        hub.end_stage(TASK, "option_searches")
        remaining = await snapshot()
        assert [m.stage for m in remaining if isinstance(m, Tick)] == ["synthesise"]
        assert any(isinstance(m, SectionDelta) for m in remaining)

        hub.end_stage(TASK, "synthesise")
        assert await snapshot() == []

        fill()
        hub.end_run(TASK, parent)
        assert await snapshot() == []

        hub.begin_run(TASK, parent)
        fill()
        hub.begin_run(TASK, uuid.uuid4())  # a re-run shows no stale activity
        assert await snapshot() == []
        # Open-call counters went too: no heartbeat follows.
        queue = await hub.subscribe(TASK)
        hub.publish_tick(TASK, stage="synthesise", activity="Writing again")
        await _drain(queue)
        _clock.now = HEARTBEAT_SECONDS * 2
        hub.sweep()
        assert await _drain(queue) == []

    _run(body)


def test_memory_untouched_for_ten_minutes_expires() -> None:
    async def body() -> None:
        hub, clock = _hub()
        hub.publish_tick(TASK, stage="classify", activity="old")
        hub.publish_delta(TASK, index=0, text="old draft", mode="replace")
        clock.now = MEMORY_TTL_SECONDS - 1
        hub.publish_tick(TASK, stage="screen", activity="fresh")

        clock.now = MEMORY_TTL_SECONDS + 1
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        assert [m.activity for m in snapshot if isinstance(m, Tick)] == ["fresh"]
        assert not any(isinstance(m, SectionDelta) for m in snapshot)

        hub.sweep()
        memory = hub._tasks[TASK]
        assert list(memory.stages) == ["screen"]
        assert memory.draft is None

        clock.now = MEMORY_TTL_SECONDS * 3
        hub.sweep()
        assert TASK not in hub._tasks

    _run(body)


def test_memory_holds_one_tick_per_stage_and_one_draft() -> None:
    async def body() -> None:
        hub, clock = _hub()
        stages = get_args(StageKey)
        assert len(stages) == 19
        for round_ in range(20):
            clock.now = round_ * 1.0
            for stage in stages:
                hub.publish_tick(TASK, stage=stage, activity=f"{stage} {round_}")
            hub.publish_delta(TASK, index=round_ % 3, text="more text ")
        hub.flush()
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        ticks = [m for m in snapshot if isinstance(m, Tick)]
        drafts = [m for m in snapshot if isinstance(m, SectionDelta)]
        assert [t.stage for t in ticks] == list(stages)
        assert {t.activity for t in ticks} == {f"{stage} 19" for stage in stages}
        assert len(drafts) == 1
        memory = hub._tasks[TASK]
        assert len(memory.stages) == 19
        assert all(entry.pending is None for entry in memory.stages.values())

    _run(body)


def test_a_full_queue_counts_dropped_messages_and_the_next_tick_carries_the_count() -> None:
    async def body() -> None:
        hub, clock = _hub(queue_size=2)
        await hub.subscribe(TASK)
        for i in range(5):
            clock.now = i * 1.0
            hub.publish_tick(TASK, stage="classify", activity=f"line {i}")
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert hub.dropped(TASK) == 3

        watcher = await hub.subscribe(TASK)
        clock.now = 10.0
        hub.publish_tick(TASK, stage="classify", activity="line 5")
        sixth = _ticks(await _drain(watcher))
        assert sixth[0].dropped == 3

    _run(body)


def test_context_helpers_publish_for_the_bound_task_and_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def body() -> None:
        hub, _clock = _hub()
        monkeypatch.setattr(liveness, "tick_hub", hub)
        queue = await hub.subscribe(TASK)

        liveness.publish_progress(activity="nobody bound")
        liveness.publish_verb("Classifying")
        liveness.model_call_opened()
        assert await _drain(queue) == []
        assert hub._tasks == {}

        with liveness.task_liveness(TASK, stage="classify"):
            assert liveness.current_task_id() == TASK
            assert liveness.current_stage() == "classify"
            liveness.publish_progress(
                activity="3 of 9 documents", done=3, total=9, unit="documents"
            )
            liveness.model_call_opened()
            liveness.model_call_opened()
            assert hub._tasks[TASK].stages["classify"].open_calls == 2
            liveness.model_call_closed()
            assert hub._tasks[TASK].stages["classify"].open_calls == 1
            liveness.model_call_closed()
            assert hub._tasks[TASK].stages["classify"].open_calls == 0
        ticks = _ticks(await _drain(queue))
        assert [(t.stage, t.activity, t.done, t.total, t.unit) for t in ticks] == [
            ("classify", "3 of 9 documents", 3, 9, "documents")
        ]
        assert liveness.current_task_id() is None
        assert liveness.current_stage() is None

        with liveness.task_liveness(TASK):
            liveness.publish_verb("Classifying")
            liveness.model_call_opened()
        assert await _drain(queue) == []
        assert None not in hub._tasks[TASK].stages

    _run(body)


def test_a_held_tick_schedules_one_flush_per_key_and_an_open_call_one_sweep() -> None:
    scheduled: list[tuple[float, Callable[[], None]]] = []
    clock = FakeClock()
    hub = TickHub(clock=clock, schedule=lambda delay, fn: scheduled.append((delay, fn)))

    hub.publish_tick(TASK, stage="classify", activity="first")
    hub.publish_tick(TASK, stage="screen", activity="first")
    assert scheduled == []
    clock.now = 0.1
    for i in range(5):
        hub.publish_tick(TASK, stage="classify", activity=f"held {i}")
        hub.publish_tick(TASK, stage="screen", activity=f"held {i}")
    assert len(scheduled) == 2
    assert all(delay == pytest.approx(COALESCE_SECONDS - 0.1) for delay, _fn in scheduled)

    hub.call_opened(TASK, "classify")
    hub.call_opened(TASK, "screen")
    assert len(scheduled) == 3
    assert scheduled[2][0] == HEARTBEAT_SECONDS

    # A due flush clears the hold; the timer's sweep reschedules while a call is open.
    clock.now = 1.0
    scheduled[0][1]()
    assert hub._tasks[TASK].stages["classify"].pending is None
    scheduled[2][1]()
    assert len(scheduled) == 4 and scheduled[3][0] == HEARTBEAT_SECONDS
    hub.call_closed(TASK, "classify")
    hub.call_closed(TASK, "screen")
    scheduled[3][1]()
    assert len(scheduled) == 4


# --- Evidence shown live (task 058, owner 2026-11-05) -----------------------


def test_sources_grow_as_a_set_in_first_seen_order_and_each_message_carries_all() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_sources(TASK, index=1, sources=[("a", "Smith 2023"), ("b", "DfE 2022")])
        hub.publish_sources(TASK, index=1, sources=[("b", "DfE 2022"), ("c", "Nesta 2021")])
        # A read that adds nothing new sends nothing.
        hub.publish_sources(TASK, index=1, sources=[("a", "Smith 2023")])
        sent = await _drain(queue)
        assert all(isinstance(m, SectionSources) for m in sent)
        assert [[sid for sid, _t in m.sources] for m in sent if isinstance(m, SectionSources)] == [
            ["a", "b"],
            ["a", "b", "c"],
        ]
        assert all(m.index == 1 for m in sent if isinstance(m, SectionSources))

        # The next section starts its own set.
        hub.publish_sources(TASK, index=2, sources=[("c", "Nesta 2021")])
        [fresh] = await _drain(queue)
        assert isinstance(fresh, SectionSources) and fresh.sources == (("c", "Nesta 2021"),)

    _run(body)


def test_a_claim_flushes_the_held_append_first_and_is_remembered() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_delta(TASK, index=0, text="Cost is the barrier.")
        hub.publish_claim(TASK, index=0, start=0, end=20, sources=[("a", "Smith 2023")])
        sent = await _drain(queue)
        assert isinstance(sent[0], SectionDelta) and sent[0].text == "Cost is the barrier."
        assert isinstance(sent[1], SectionClaim)
        assert (sent[1].index, sent[1].start, sent[1].end) == (0, 0, 20)
        assert sent[1].sources == (("a", "Smith 2023"),)
        draft = hub._tasks[TASK].draft
        assert draft is not None and [c.start for c in draft.claims] == [0]

    _run(body)


def test_snapshot_sends_the_draft_then_the_sources_then_each_claim() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        hub.publish_sources(TASK, index=2, sources=[("a", "Smith 2023")])

        # Sources before any text: no empty draft is sent, only the set.
        queue, early = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        assert len(early) == 1 and isinstance(early[0], SectionSources)

        hub.publish_delta(TASK, index=2, text="First. Second.")
        hub.publish_sources(TASK, index=2, sources=[("b", "DfE 2022")])
        hub.publish_claim(TASK, index=2, start=0, end=6, sources=[("a", "Smith 2023")])
        hub.publish_claim(TASK, index=2, start=7, end=14, sources=[("b", "DfE 2022")])

        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        draft, sources, first, second = snapshot
        assert isinstance(draft, SectionDelta) and draft.mode == "replace"
        assert draft.text == "First. Second."
        assert isinstance(sources, SectionSources)
        assert [sid for sid, _t in sources.sources] == ["a", "b"]
        assert isinstance(first, SectionClaim) and (first.start, first.end) == (0, 6)
        assert isinstance(second, SectionClaim) and (second.start, second.end) == (7, 14)

    _run(body)


def test_a_replace_keeps_the_sources_and_drops_the_claims() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        hub.publish_sources(TASK, index=0, sources=[("a", "Smith 2023")])
        hub.publish_delta(TASK, index=0, text="Old text.")
        hub.publish_claim(TASK, index=0, start=0, end=3, sources=[("a", "Smith 2023")])
        # The streamed turn fell back: its draft is reset.
        hub.publish_delta(TASK, index=0, text="", mode="replace")
        draft = hub._tasks[TASK].draft
        assert draft is not None
        assert draft.sources == (("a", "Smith 2023"),)
        assert draft.claims == []

    _run(body)


def test_clear_draft_end_stage_end_run_and_the_sweep_forget_sources_and_claims() -> None:
    async def body() -> None:
        hub, clock = _hub()

        async def snapshot() -> list[HubMessage]:
            queue, messages = await hub.subscribe_with_snapshot(TASK)
            await hub.unsubscribe(TASK, queue)
            return messages

        def fill() -> None:
            hub.publish_sources(TASK, index=0, sources=[("a", "Smith 2023")])
            hub.publish_delta(TASK, index=0, text="Text.")
            hub.publish_claim(TASK, index=0, start=0, end=4, sources=[("a", "Smith 2023")])

        fill()
        assert len(await snapshot()) == 3
        hub.clear_draft(TASK)
        assert await snapshot() == []

        fill()
        hub.end_stage(TASK, "synthesise")
        assert await snapshot() == []

        run = uuid.uuid4()
        hub.begin_run(TASK, run)
        fill()
        hub.end_run(TASK, run)
        assert await snapshot() == []

        fill()
        clock.now = MEMORY_TTL_SECONDS + 1
        assert await snapshot() == []
        hub.sweep()
        assert TASK not in hub._tasks

    _run(body)


def test_sources_and_claims_count_as_dropped_on_a_full_queue() -> None:
    async def body() -> None:
        hub, _clock = _hub(queue_size=1)
        await hub.subscribe(TASK)
        hub.publish_sources(TASK, index=0, sources=[("a", "A 2020")])
        hub.publish_sources(TASK, index=0, sources=[("b", "B 2021")])
        hub.publish_claim(TASK, index=0, start=0, end=1, sources=[("a", "A 2020")])
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert hub.dropped(TASK) == 2

    _run(body)


def test_context_helpers_publish_sources_and_claims_for_the_bound_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def body() -> None:
        hub, _clock = _hub()
        monkeypatch.setattr(liveness, "tick_hub", hub)
        queue = await hub.subscribe(TASK)
        liveness.publish_section_sources(0, [("a", "A 2020")])
        liveness.publish_section_claim(0, 0, 1, [("a", "A 2020")])
        assert await _drain(queue) == []
        with liveness.task_liveness(TASK, stage="synthesise"):
            liveness.publish_section_sources(0, [("a", "A 2020")])
            liveness.publish_section_claim(0, 0, 1, [("a", "A 2020")])
        sent = await _drain(queue)
        assert [type(m) for m in sent] == [SectionSources, SectionClaim]

    _run(body)


# --- Case studies streamed card by card (task 058, round 7) -----------------------


def test_cards_are_sent_and_remembered_in_order_and_a_snapshot_sends_them_after_the_draft() -> (
    None
):
    async def body() -> None:
        hub, _clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_card(TASK, index=1, title="Leeds", prose="Breakfast in every primary.")
        hub.publish_card(TASK, index=1, title="Bristol", prose="Walking buses.")
        sent = await _drain(queue)
        assert [type(m) for m in sent] == [SectionCard, SectionCard]
        assert [(m.index, m.title) for m in sent if isinstance(m, SectionCard)] == [
            (1, "Leeds"),
            (1, "Bristol"),
        ]
        await hub.unsubscribe(TASK, queue)

        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        # No text was streamed for the slot: only the cards, in order.
        assert [m.title for m in snapshot if isinstance(m, SectionCard)] == ["Leeds", "Bristol"]
        assert len(snapshot) == 2

        # A draft for the same slot comes first, then the cards.
        hub.publish_delta(TASK, index=1, text="Some text.")
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        assert isinstance(snapshot[0], SectionDelta) and snapshot[0].mode == "replace"
        assert [type(m) for m in snapshot[1:]] == [SectionCard, SectionCard]

    _run(body)


def test_a_card_for_another_section_starts_a_fresh_draft_and_flushes_held_text() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_delta(TASK, index=2, text="Held text.")
        hub.publish_card(TASK, index=1, title="Leeds", prose="Breakfast.")
        sent = await _drain(queue)
        assert isinstance(sent[0], SectionDelta) and sent[0].text == "Held text."
        assert isinstance(sent[1], SectionCard)
        draft = hub._tasks[TASK].draft
        assert draft is not None and draft.index == 1 and draft.text == ""
        assert [card.title for card in draft.cards] == ["Leeds"]

    _run(body)


def test_a_replace_and_the_forgetting_rules_drop_the_cards() -> None:
    async def body() -> None:
        hub, clock = _hub()

        async def snapshot() -> list[HubMessage]:
            queue, messages = await hub.subscribe_with_snapshot(TASK)
            await hub.unsubscribe(TASK, queue)
            return messages

        def fill() -> None:
            hub.publish_card(TASK, index=1, title="Leeds", prose="Breakfast.")

        fill()
        # The streamed reply fell back: the slot is reset and the cards go.
        hub.publish_delta(TASK, index=1, text="", mode="replace")
        draft = hub._tasks[TASK].draft
        assert draft is not None and draft.cards == []

        fill()
        hub.clear_draft(TASK)
        assert await snapshot() == []

        fill()
        hub.end_stage(TASK, "synthesise")
        assert await snapshot() == []

        run = uuid.uuid4()
        hub.begin_run(TASK, run)
        fill()
        hub.end_run(TASK, run)
        assert await snapshot() == []

        fill()
        clock.now = MEMORY_TTL_SECONDS + 1
        assert await snapshot() == []

    _run(body)


def test_cards_count_as_dropped_on_a_full_queue() -> None:
    async def body() -> None:
        hub, _clock = _hub(queue_size=1)
        await hub.subscribe(TASK)
        hub.publish_card(TASK, index=1, title="A", prose="a")
        hub.publish_card(TASK, index=1, title="B", prose="b")
        hub.publish_card(TASK, index=1, title="C", prose="c")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert hub.dropped(TASK) == 2

    _run(body)


def test_context_helper_publishes_a_card_for_the_bound_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def body() -> None:
        hub, _clock = _hub()
        monkeypatch.setattr(liveness, "tick_hub", hub)
        queue = await hub.subscribe(TASK)
        liveness.publish_section_card(1, "Leeds", "Breakfast.")
        assert await _drain(queue) == []
        with liveness.task_liveness(TASK, stage="synthesise"):
            liveness.publish_section_card(1, "Leeds", "Breakfast.")
        [card] = await _drain(queue)
        assert isinstance(card, SectionCard) and (card.index, card.title) == (1, "Leeds")

    _run(body)


# --- Source notes as they are written (task 058, round 8) --------------------------


def test_source_notes_are_sent_in_order_and_a_snapshot_sends_them_after_the_draft() -> None:
    async def body() -> None:
        hub, _clock = _hub()
        queue = await hub.subscribe(TASK)
        hub.publish_source_note(TASK, source_id="s1", title="Breakfast clubs", note="A trial.")
        hub.publish_source_note(TASK, source_id="s2", title="Walking buses", note="A survey.")
        sent = await _drain(queue)
        assert [type(m) for m in sent] == [SourceNote, SourceNote]
        assert [(m.source_id, m.title, m.note) for m in sent if isinstance(m, SourceNote)] == [
            ("s1", "Breakfast clubs", "A trial."),
            ("s2", "Walking buses", "A survey."),
        ]
        await hub.unsubscribe(TASK, queue)

        # The notes do not belong to a section: a draft comes first, then the notes.
        hub.publish_delta(TASK, index=4, text="The report turns to")
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        assert isinstance(snapshot[0], SectionDelta) and snapshot[0].mode == "replace"
        assert [m.source_id for m in snapshot[1:] if isinstance(m, SourceNote)] == ["s1", "s2"]

        # Finishing a section, or the writing stage, keeps them: they go with the run.
        hub.clear_draft(TASK)
        hub.end_stage(TASK, "synthesise")
        queue, snapshot = await hub.subscribe_with_snapshot(TASK)
        await hub.unsubscribe(TASK, queue)
        assert [type(m) for m in snapshot] == [SourceNote, SourceNote]

    _run(body)


def test_source_notes_are_forgotten_with_the_run_and_when_stale() -> None:
    async def body() -> None:
        hub, clock = _hub()

        async def snapshot() -> list[HubMessage]:
            queue, messages = await hub.subscribe_with_snapshot(TASK)
            await hub.unsubscribe(TASK, queue)
            return messages

        def note() -> None:
            hub.publish_source_note(TASK, source_id="s1", title="T", note="N.")

        run = uuid.uuid4()
        hub.begin_run(TASK, run)
        note()
        assert len(await snapshot()) == 1
        hub.end_run(TASK, run)
        assert await snapshot() == []

        note()
        hub.begin_run(TASK, uuid.uuid4())
        assert await snapshot() == []

        note()
        clock.now = MEMORY_TTL_SECONDS + 1
        assert await snapshot() == []
        hub.sweep()
        memory = hub._tasks.get(TASK)
        assert memory is None or memory.source_notes == []

    _run(body)


def test_source_notes_count_as_dropped_on_a_full_queue() -> None:
    async def body() -> None:
        hub, _clock = _hub(queue_size=1)
        await hub.subscribe(TASK)
        for n in range(3):
            hub.publish_source_note(TASK, source_id=f"s{n}", title="T", note="N.")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert hub.dropped(TASK) == 2

    _run(body)


def test_context_helper_publishes_a_source_note_for_the_bound_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def body() -> None:
        hub, _clock = _hub()
        monkeypatch.setattr(liveness, "tick_hub", hub)
        queue = await hub.subscribe(TASK)
        liveness.publish_source_note("s1", "T", "N.")
        assert await _drain(queue) == []
        with liveness.task_liveness(TASK, stage="synthesise"):
            liveness.publish_source_note("s1", "T", "N.")
        [message] = await _drain(queue)
        assert isinstance(message, SourceNote) and message.source_id == "s1"

    _run(body)
