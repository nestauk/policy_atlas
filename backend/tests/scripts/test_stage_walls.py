"""Coverage for the stage wall-time script (`scripts/stage_walls.py`, task 057 Phase 0).

The fixture is hand-written and synthetic: two Evidence search runs (A and B) and one
Options scoping run (S) with two fan-out child runs, plus server log lines for A's
ingest run in both log formats (console with colour codes, and JSON) mixed with
unknown event names and junk lines. Every expected number below is worked out from
the fixture's timestamps by hand. The script's reproduction of the real 2026-11-02
anatomy (Table 2 and the ingest split, to the second) was a one-time check against
the dev database, recorded in the task's verification notes, not pinned here.
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
