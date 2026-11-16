"""Coverage for the stage wall-time script (`scripts/stage_walls.py`, task 057 Phase 0).

The fixture is hand-written and synthetic: two Evidence search runs (A and B) and one
Options scoping run (S) with two fan-out child runs, plus server log lines for A's
ingest run in both log formats (console with colour codes, and JSON) mixed with
unknown event names and junk lines. Every expected number below is worked out from
the fixture's timestamps by hand. The script's reproduction of the real 2026-11-02
anatomy (Table 2 and the ingest split, to the second) was a one-time check against
the dev database, recorded in the task's verification notes, not pinned here.

The ``--capture`` tests (task 058, N25) read a second hand-written fixture,
``data/stream_capture_fixture.jsonl``: one recording in the shape
``scripts/stream_capture.py`` writes. Their numbers are worked out in
:func:`test_capture_measure_on_the_fixture`.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "stage_walls.py"
_FIXTURE = Path(__file__).resolve().parent / "data" / "stage_walls_fixture.json"
INGEST_A = "a1000000-0057-4000-8000-000000000002"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage_walls", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sw = _load()


@pytest.fixture
def fixture() -> dict[str, Any]:
    return copy.deepcopy(json.loads(_FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture
def report(fixture: dict[str, Any]) -> dict[str, Any]:
    logs = sw.parse_log_lines(fixture["log_lines"], "server.log")
    result: dict[str, Any] = sw.build_report(fixture["runs"], logs, "bedrock")
    return result


def _run(report: dict[str, Any], cap: str, id8: str) -> dict[str, Any]:
    return next(e for e in report["capabilities"][cap]["runs"] if e["id8"] == id8)


def test_selection_needs_a_flag_and_ands_kinds() -> None:
    with pytest.raises(ValueError):
        sw.build_selection([], [], None, None)
    where, params = sw.build_selection(["AAAA"], ["t1"], "2026-11-02", "evidence_search")
    assert where.count(" AND ") == 3
    assert params == {
        "run_patterns": ["aaaa%"],
        "task_ids": ["t1"],
        "since": "2026-11-02",
        "capability": "evidence_search",
    }


def test_only_top_level_runs_are_reported(report: dict[str, Any]) -> None:
    caps = report["capabilities"]
    assert [e["id8"] for e in caps["evidence_search"]["runs"]] == ["aaaaaaaa", "bbbbbbbb"]
    assert [e["id8"] for e in caps["options_scoping"]["runs"]] == ["cccccccc"]


def test_run_a_walls(report: dict[str, Any]) -> None:
    a = _run(report, "evidence_search", "aaaaaaaa")
    assert a["route"] == "bedrock"
    assert a["total_wall_s"] == 600  # 10:00:00 -> 10:10:00
    # Components cover 10:00:01 -> 10:09:51 (synthesise's timing runs 50 s past its row).
    assert a["outside_components_s"] == pytest.approx(10)
    assert a["synth_post_commit_s"] == pytest.approx(50)  # 290 timing - 240 row
    assert a["run_parked_events"] == 0
    assert a["fan_out"] is None
    assert a["counts"]["acquired"] == 100
    assert a["counts"]["ingested"] == 30


def test_run_b_fallback_and_repeated_component(report: dict[str, Any]) -> None:
    b = _run(report, "evidence_search", "bbbbbbbb")
    walls = {r["run_id"][-1]: r["wall_s"] for r in b["components"]}
    assert walls["1"] == 120  # no timing event: run row 11:00 -> 11:02
    assert b["total_wall_s"] == 1200
    assert b["outside_components_s"] == pytest.approx(70)  # covered 11:00:00 -> 11:18:50
    assert b["synth_post_commit_s"] == pytest.approx(20)
    assert b["run_parked_events"] == 1
    assert b["ingest_log_split"] is None  # logs given, but none for B's ingest run


def test_scoping_fan_out(report: dict[str, Any]) -> None:
    s = _run(report, "options_scoping", "cccccccc")
    assert s["fan_out"] == {
        "child_capability_runs": 2,
        "child_components": ["acquire"],
        "window_s": 900,  # 12:05 -> 12:20
        "child_wall_median_s": 720,  # (600 + 840) / 2
        "child_wall_max_s": 840,
        "window_start": "2026-11-01T12:05:00+00:00",
    }
    # Covered: 12:00-12:05, 12:05-12:20 (children), 12:25-12:29 = 1440 of 1800 s.
    assert s["outside_components_s"] == pytest.approx(360)
    assert s["synth_post_commit_s"] is None


def test_stats_evidence_search(report: dict[str, Any]) -> None:
    block = report["capabilities"]["evidence_search"]
    rows = {r["component"]: r for r in block["stats"]}
    # Components absent from every run get no row.
    assert list(rows) == [
        "acquire",
        "classify",
        "ingest_full_text",
        "synthesise",
        "total",
        "outside",
    ]
    assert (rows["acquire"]["median_s"], rows["acquire"]["max_s"], rows["acquire"]["min_s"]) == (
        90,
        120,
        60,
    )
    assert rows["classify"]["n"] == 1 and rows["classify"]["median_s"] == 90  # 60 + 30 summed
    assert rows["ingest_full_text"]["median_s"] == 420
    assert rows["synthesise"]["median_s"] == 305
    assert rows["total"]["median_s"] == 900 and rows["total"]["share_of_median_total"] is None
    assert rows["outside"]["median_s"] == pytest.approx(40)
    assert rows["ingest_full_text"]["share_of_median_total"] == pytest.approx(420 / 900)


def test_markdown_layout(report: dict[str, Any]) -> None:
    md = sw.format_markdown(report)
    assert "| acquire | 2 | 90 | 120 | 60 | 10% |" in md
    assert "| ingest_full_text | 2 | 420 | 600 | 240 | 47% |" in md
    assert "| total | 2 | 900 | 1200 | 600 |  |" in md
    assert "| outside | 2 | 40 | 70 | 10 | 4% |" in md
    # Table 1, run B: repeated classify shown as a sum, untouched stages as "-".
    assert (
        "| bbbbbbbb | Synthetic run B | bedrock | 2026-11-01 11:00 | 1200 | 120 | - | 60+30 | - "
        "| 600 | - | - | - | 320 | 70 | 20 |" in md
    )
    # Scoping: fan-out columns.
    assert (
        "| cccccccc | Synthetic scoping run S | bedrock | 2026-11-01 12:00 | 1800 | 300 | 240 "
        in md
    )
    assert "| 360 | 900 | 2 | - |" in md
    # Ingest split for A only.
    assert "| aaaaaaaa | 240 | 100 | 130 | 10 | 2 | 2 / 5 |" in md


def test_ingest_split_from_mixed_logs(report: dict[str, Any]) -> None:
    split = _run(report, "evidence_search", "aaaaaaaa")["ingest_log_split"]
    assert split["start_to_first_embed_request_s"] == 100  # 10:01:01 -> 10:02:41
    assert split["first_embed_request_to_embed_summary_s"] == 130  # -> 10:04:51
    assert split["embed_summary_to_completed_s"] == 10  # -> 10:05:01 (JSON line)
    assert split["embed_requests"] == 2
    assert split["embed_provider"] == ["cohere"]
    assert (split["rate_limit_sleeps"], split["rate_limit_sleep_s_sum"]) == (2, 5.0)
    assert split["handover_batches"] == [
        {"batch": 0, "documents": 20, "fetch_wall_s": 50.5, "parse_wall_s": 30.0, "idle_gap_s": 1.0}
    ]


def test_log_parser_is_tolerant(fixture: dict[str, Any]) -> None:
    logs = sw.parse_log_lines(fixture["log_lines"], "server.log")
    assert list(logs) == [INGEST_A]  # the line without a run_id is dropped
    events = [e["event"] for e in logs[INGEST_A]["events"]]
    assert "ingest.document_queued" in events  # unknown ingest event kept, not an error
    assert "http.request" not in events  # outside the kept prefixes
    assert all("task_id" not in e for e in logs[INGEST_A]["events"])


def test_read_logs_from_file_and_folder(fixture: dict[str, Any], tmp_path: Path) -> None:
    lines = fixture["log_lines"]
    (tmp_path / "a.log").write_text("\n".join(lines[:5]) + "\n", encoding="utf-8")
    (tmp_path / "b.log").write_text("\n".join(lines[5:]) + "\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text(lines[0] + "\n", encoding="utf-8")
    from_folder = sw.read_logs([str(tmp_path)])
    assert from_folder[INGEST_A]["files"] == ["a.log", "b.log"]
    assert len(from_folder[INGEST_A]["events"]) == len(
        sw.parse_log_lines(lines)[INGEST_A]["events"]
    )
    split = sw.ingest_split(from_folder[INGEST_A])
    assert split["first_embed_request_to_embed_summary_s"] == 130


def test_report_is_json_ready(report: dict[str, Any]) -> None:
    again = json.loads(json.dumps(report))
    assert again["capabilities"]["evidence_search"]["stats"][0]["component"] == "acquire"


# --- Stream capture mode (task 058, N25) -------------------------------------------

_CAPTURE = Path(__file__).resolve().parent / "data" / "stream_capture_fixture.jsonl"
WALK = "c0580000-0058-4000-8000-000000000001"


@pytest.fixture
def capture() -> dict[str, Any]:
    records, unreadable = sw.read_capture(str(_CAPTURE))
    result: dict[str, Any] = sw.capture_report(records, True, unreadable)
    return result


def test_capture_measure_on_the_fixture(capture: dict[str, Any]) -> None:
    """Every number below, worked out by hand from ``stream_capture_fixture.jsonl``.

    Times are seconds after 10:00:00 (``received_at``). The recording: run.status
    running 0; acquire started 2; ticks 5 (dropped 0), 15 (heartbeat, dropped 0) and
    60 (dropped 1); a keep-alive comment at 20; acquire completed 82;
    checkin.pending 85; run.status paused 86; keep-alive 100; run.status running
    126; synthesise started 130; skeleton 131; section_started 132; tick 135
    (dropped 2); section_delta 139; heartbeat 150 (dropped 2); section_completed
    168; synthesise completed 170; run.status succeeded 175.

    - Wall 0 to 175 = 175 s. Parked 85 (checkin.pending) to 126 (running) = 41 s.
      Active = 175 - 41 = 134 s.
    - Active pieces: 0 to 85 and 126 to 175. Visible frames in the first: 0, 2, 5,
      15, 60, 82, 85; steps 2, 3, 10, 45, 22, 3, so one silent gap, 15 to 60 = 45 s
      (the comment at 20 does not break it). Its owner: acquire (started at 2, not
      completed until 82). Second piece: 126, 130, 131, 132, 135, 139, 150, 168,
      170, 175; steps 4, 1, 1, 3, 4, 11, 18, 2, 5: none over 30 s. The 40 s from
      86 to 126 is parked, so not a gap.
    - Silent: count 1, 45 s, share 45 / 134 = 0.33582...; by stage: acquire only.
    - First prose: section_started 132; first delta 139 (7 s); first completed
      168 (36 s).
    - Tick rate: acquire open 2 to 82 = 80 s, ticks 5 and 60 = 2 (0.025 /s),
      heartbeat 15 = 1 (0.0125 /s); synthesise open 130 to 170 = 40 s, tick 135 = 1
      (0.025 /s), heartbeat 150 = 1 (0.025 /s).
    - Dropped ticks: first tick 0, last tick 2, delta 2.
    - Counts: 18 frames, 3 ticks, 2 heartbeats, 2 comments, 0 reconnects.
    """
    c = capture
    assert c["walk"] == WALK and c["healthy"] is True
    assert c["finished"] is True and c["final_status"] == "succeeded"
    assert (c["active_start"], c["active_end"]) == (
        "2026-11-05T10:00:00.000Z",
        "2026-11-05T10:02:55.000Z",
    )
    assert (c["wall_s"], c["parked_s"], c["active_s"]) == (175, 41, 134)
    assert c["parked"] == [
        {"start": "2026-11-05T10:01:25.000Z", "end": "2026-11-05T10:02:06.000Z"}
    ]
    gaps = c["silent_gaps"]
    assert (gaps["count"], gaps["total_s"]) == (1, 45)
    assert gaps["share_of_active"] == pytest.approx(45 / 134)
    assert gaps["gaps"] == [
        {
            "start": "2026-11-05T10:00:15.000Z",
            "end": "2026-11-05T10:01:00.000Z",
            "seconds": 45,
            "stage": "acquire",
        }
    ]
    assert gaps["by_stage"] == {
        "acquire": {"count": 1, "total_s": 45, "share_of_active": pytest.approx(45 / 134)}
    }
    assert c["first_prose"] == {
        "section_started_at": "2026-11-05T10:02:12.000Z",
        "to_first_delta_s": 7,
        "to_first_completed_s": 36,
    }
    assert c["tick_rate"] == [
        {
            "stage": "acquire",
            "open_s": 80,
            "ticks": 2,
            "heartbeats": 1,
            "ticks_per_s": pytest.approx(0.025),
            "heartbeats_per_s": pytest.approx(0.0125),
        },
        {
            "stage": "synthesise",
            "open_s": 40,
            "ticks": 1,
            "heartbeats": 1,
            "ticks_per_s": pytest.approx(0.025),
            "heartbeats_per_s": pytest.approx(0.025),
        },
    ]
    assert c["dropped_ticks"] == {"first": 0, "last": 2, "delta": 2}
    assert c["counts"] == {
        "frames": 18,
        "ticks": 3,
        "heartbeats": 2,
        "comments": 2,
        "reconnects": 0,
        "unreadable_lines": 0,
    }


def test_capture_markdown(capture: dict[str, Any]) -> None:
    md = sw.format_capture_markdown({"capture": "fixture.jsonl", **capture})
    assert "| healthy run | yes |" in md
    assert "| wall s / parked s / active s | 175.0 / 41.0 / 134.0 |" in md
    assert "| silent share of active | 33.6% |" in md
    assert "| first section started to first delta s | 7.0 |" in md
    assert "| dropped ticks | 2 |" in md
    assert "| acquire | 1 | 45.0 | 33.6% |" in md
    assert "| acquire | 80.0 | 2 | 0.025 | 1 | 0.013 |" in md


def test_capture_command_line(tmp_path: Path) -> None:
    out = tmp_path / "gaps.json"
    code = sw.main(
        ["--capture", str(_CAPTURE), "--healthy", "false", "--format", "json", "--out", str(out)]
    )
    assert code == 0
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["capture"] == "stream_capture_fixture.jsonl"
    assert saved["healthy"] is False
    assert saved["silent_gaps"]["count"] == 1
    with pytest.raises(SystemExit):
        sw.main(["--capture", str(_CAPTURE), "--since", "2026-11-05"])
    with pytest.raises(SystemExit):
        sw.main(["--since", "2026-11-05", "--healthy", "true"])


def _line(second: int, event: str | None, data: Any = None, kind: str = "frame") -> dict[str, Any]:
    return {
        "received_at": f"2026-11-05T10:{second // 60:02d}:{second % 60:02d}.000Z",
        "kind": kind,
        "event": event,
        "id": None,
        "data": data,
    }


def _status(second: int, walk: str, status: str) -> dict[str, Any]:
    return _line(second, "run.status", {"capability_run_id": walk, "status": status})


def _stage(second: int, event: str, stage: str, walk: str | None = WALK) -> dict[str, Any]:
    return _line(second, event, {"capability_run_id": walk, "stage": stage})


def test_capture_gap_between_stages_and_reconnects_are_not_visible() -> None:
    records = [
        _status(0, WALK, "running"),
        _stage(1, "stage.started", "acquire"),
        _stage(10, "stage.completed", "acquire"),
        _line(30, None, {"cursor": 3, "reason": "dropped"}, kind="reconnect"),
        _stage(50, "stage.started", "classify"),  # 10 -> 50: 40 s between stages
        _stage(55, "stage.failed", "classify"),
    ]
    report = sw.capture_report(records)
    assert report["finished"] is False and report["final_status"] is None
    assert report["active_s"] == 55  # no final status: the last line ends it
    assert [(g["seconds"], g["stage"]) for g in report["silent_gaps"]["gaps"]] == [
        (40, "(between stages)")
    ]
    assert report["counts"]["reconnects"] == 1
    assert report["healthy"] is None


def test_capture_measures_the_last_followed_run_not_history_or_children() -> None:
    old, child = "00000000-0000-4000-8000-0000000000a0", "00000000-0000-4000-8000-0000000000c0"
    records = [
        # An earlier run, replayed from history in one burst.
        _status(0, old, "running"),
        _status(0, old, "succeeded"),
        # The live run, with a child run (an option search) inside it.
        _status(1, WALK, "running"),
        _stage(2, "stage.started", "option_searches"),
        _status(3, child, "running"),
        _stage(4, "stage.started", "acquire", walk=child),
        _stage(60, "stage.completed", "acquire", walk=child),  # 4 -> 60: 56 s
        _status(61, child, "succeeded"),
        _stage(62, "stage.completed", "option_searches"),
        _status(63, WALK, "succeeded"),
        _status(64, child, "failed"),  # a child's late final frame changes nothing
    ]
    report = sw.capture_report(records)
    assert report["walk"] == WALK
    assert report["final_status"] == "succeeded"
    assert report["active_s"] == 62  # 1 -> 63
    # The child's stage frames are visible, but the gap belongs to the parent's stage.
    assert [(g["seconds"], g["stage"]) for g in report["silent_gaps"]["gaps"]] == [
        (56, "option_searches")
    ]
    assert [r["stage"] for r in report["tick_rate"]] == ["option_searches"]


def test_capture_old_tick_shape_is_mapped() -> None:
    old = {"type": "tick", "stage": "ingest", "note": "Fetching", "fetched": 4, "parsed": 3,
           "total": 9}
    assert sw.normalise_tick(old) == {
        "stage": "ingest",
        "activity": "Fetching",
        "done": 3,
        "total": 9,
        "unit": None,
        "section": None,
        "heartbeat": False,
        "dropped": None,
    }
    report = sw.capture_report(
        [_status(0, WALK, "running"), _line(5, "tick", old), _status(9, WALK, "succeeded")]
    )
    assert report["dropped_ticks"] == {"first": None, "last": None, "delta": None}
    assert report["counts"]["ticks"] == 1


def test_capture_without_a_run_status_measures_nothing(tmp_path: Path) -> None:
    path = tmp_path / "half.jsonl"
    path.write_text(
        json.dumps(_line(0, "tick", {"stage": "acquire", "activity": "x", "dropped": 0}))
        + "\n\n{\"received_at\": \"2026-11-05T10:0",
        encoding="utf-8",
    )
    records, unreadable = sw.read_capture(str(path))
    assert (len(records), unreadable) == (1, 1)
    report = sw.capture_report(records, None, unreadable)
    assert report["walk"] is None and report["silent_gaps"] is None
    assert report["counts"]["unreadable_lines"] == 1
    assert "nothing to measure" in sw.format_capture_markdown(report)
