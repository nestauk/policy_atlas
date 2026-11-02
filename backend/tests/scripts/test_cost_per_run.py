"""Coverage for the cost-per-run script (`scripts/cost_per_run.py`, task 056 Phase 0).

The fixture holds one hand-written synthetic session ``5e7e7e7e`` with only ids,
names, timestamps, models and token counts (no prompts, answers or metadata): cache
writes, reasoning tokens, GPT-6 models, a Bedrock model name, an embedding priced on
``total``, an observation in the old usage shape (input / cached / output / total
only), a non-run trace and an unpriced model. The script's reproduction of the real
2026-10-30 baseline session (``0e8f8431``, $1.99 to the cent) was a one-time check and
is recorded in ``docs/tasks/056-cost-latency/verification.md``, not pinned here: the
real session was 789 rows that pinned the price table of one day (owner, 2026-11-02).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "cost_per_run.py"
_FIXTURE = Path(__file__).resolve().parent / "data" / "cost_per_run_fixture.json"
SYNTHETIC = "5e7e7e7e-0056-4000-8000-000000000001"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cost_per_run", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpr = _load()


@pytest.fixture
def sessions() -> dict[str, Any]:
    return copy.deepcopy(json.loads(_FIXTURE.read_text(encoding="utf-8"))["sessions"])


def test_synthetic_session_total_by_hand(sessions: dict[str, Any]) -> None:
    # USD per million tokens; cache write = 1.25 x input, reasoning = output.
    screen_full = (
        10_000 * 0.10 + 50_000 * 0.01 + 2_000 * 1.25 * 0.10 + 1_000 * 0.50 + 500 * 0.50
    ) / 1e6
    section_turn = (20_000 * 1.00 + 80_000 * 0.05 + 8_000 * 1.25 * 1.00 + 3_000 * 5.00) / 1e6
    judge = (4_000 * 2.00 + 200 * 10.00 + 1_800 * 10.00) / 1e6
    embed = 50_000 * 0.12 / 1e6  # only "total" reported: priced as input
    task_agent = (1_000 * 1.00 + 3_000 * 0.05 + 500 * 5.00) / 1e6  # non-run trace
    assert (screen_full, section_turn, judge, embed, task_agent) == pytest.approx(
        (0.0025, 0.049, 0.028, 0.006, 0.00365)
    )
    report = cpr.session_report(SYNTHETIC, sessions[SYNTHETIC])
    assert report["session_total_usd"] == pytest.approx(0.08915)
    assert report["run_total_usd"] == pytest.approx(0.08915 - task_agent)
    assert report["run_type"] == "ES standard"
    assert report["date"] == "2026-11-02"
    # The embedding row carries no cost of its own beyond the "total" bucket, and the
    # non-run trace (the Task Agent's turn) sits in the session total, not the run total.
    embed_row = next(r for r in report["by_call"] if r["name"] == "embed:batch")
    assert embed_row["cost_usd"] == pytest.approx(embed)
    assert report["unknown_models"] == {"mystery-model-1": {"calls": 1, "tokens": 110}}
    stages = {r["stage"]: r for r in report["by_stage"]}
    assert set(stages) == {"synthesise", "acquire", "task_agent:turn", "screen_full"}
    assert stages["synthesise"]["cost_usd"] == pytest.approx(section_turn + judge)
    assert [r["stage"] for r in report["by_stage"]] == [
        "synthesise",
        "acquire",
        "task_agent:turn",
        "screen_full",
    ]


def test_cache_write_and_reasoning_buckets() -> None:
    only_write = {"input": 0, "cached": 0, "cache_write": 1_000_000, "output": 0, "reasoning": 0}
    only_reasoning = {
        "input": 0,
        "cached": 0,
        "cache_write": 0,
        "output": 0,
        "reasoning": 1_000_000,
    }
    assert cpr.bucket_cost("gpt-6.1-terra", only_write) == pytest.approx(1.25)
    assert cpr.bucket_cost("gpt-6.1-terra", only_reasoning) == pytest.approx(5.00)
    assert cpr.bucket_cost("gpt-6-luna", only_write) == pytest.approx(0.125)
    assert cpr.bucket_cost("mystery-model-1", only_write) is None
    assert cpr.normalise_model("global.openai.gpt-6.1-sol") == "gpt-6.1-sol"
    buckets = cpr.usage_buckets(
        "gpt-6.1-terra",
        {
            "input": 5,
            "input_cached_tokens": 6,
            "input_cache_write_tokens": 7,
            "output": 8,
            "output_reasoning_tokens": 9,
            "total": 35,
        },
    )
    assert buckets == {"input": 5, "cached": 6, "cache_write": 7, "output": 8, "reasoning": 9}
    assert cpr.usage_buckets("eu.cohere.embed-v4:0", {"total": 40})["input"] == 40


def test_cache_shares_in_call_table(sessions: dict[str, Any]) -> None:
    report = cpr.session_report(SYNTHETIC, sessions[SYNTHETIC])
    turn = next(r for r in report["by_call"] if r["name"] == "synthesise:section_turn")
    assert turn["model"] == "gpt-6.1-terra"  # Bedrock prefix stripped
    assert turn["cache_read_share"] == round(80_000 / 108_000, 4)
    assert turn["cache_write_share"] == round(8_000 / 108_000, 4)


def test_prefix_resolution_against_fixture() -> None:
    assert list(cpr.load_fixture(str(_FIXTURE), ["5e7e"])) == [SYNTHETIC]
    # A full id and a prefix of the same session resolve to the one session.
    assert list(cpr.load_fixture(str(_FIXTURE), [SYNTHETIC, "5e7e7e7e"])) == [SYNTHETIC]
    with pytest.raises(SystemExit, match="no session starts with"):
        cpr.load_fixture(str(_FIXTURE), ["ffff"])
    with pytest.raises(SystemExit, match="ambiguous"):
        cpr.resolve_session_id("ab", ["abc1", "abd2"])


def test_run_type_classification() -> None:
    assert (
        cpr.run_type(["run:acquire", "run:longlist", "run:extract", "run:screen_full"]) == "scoping"
    )
    assert cpr.run_type(["run:extract", "run:screen_full"]) == "ES deep"
    assert cpr.run_type(["run:screen_full", "run:synthesise"]) == "ES standard"
    assert cpr.run_type(["run:screen_abstract", "run:synthesise"]) == "ES landscape"
    # A non-run trace never classifies; extract_interventions is not extract.
    assert cpr.run_type(["longlist:fold", "run:extract_interventions"]) == "ES landscape"
    assert cpr.stage_name("run:synthesise:0f0f0f0f-1111-4222-8333-444444444444") == "synthesise"
    assert cpr.stage_name("planner:turn") == "planner:turn"


def test_json_output_round_trips(
    sessions: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cpr.main(["5e7e", "--fixture", str(_FIXTURE), "--json"]) == 0
    out, err = capsys.readouterr()
    parsed = json.loads(out)
    assert parsed == cpr.build_report({SYNTHETIC: sessions[SYNTHETIC]})
    assert [s["session_id"] for s in parsed["sessions"]] == [SYNTHETIC]
    assert "summary" not in parsed  # the by-run-type summary needs two or more sessions
    assert "mystery-model-1" in err
    # Same input, same output.
    assert cpr.main(["5e7e", "--fixture", str(_FIXTURE), "--json"]) == 0
    assert capsys.readouterr().out == out


def test_text_output_and_saved_fixture_are_public_safe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saved = tmp_path / "saved.json"
    assert cpr.main(["5e7e", "--fixture", str(_FIXTURE), "--save-fixture", str(saved)]) == 0
    text = capsys.readouterr().out
    assert "By stage" in text and "By call name" in text and "Session total $0.089" in text
    for data in json.loads(saved.read_text(encoding="utf-8"))["sessions"].values():
        assert all(set(t) == set(cpr.TRACE_FIELDS) for t in data["traces"])
        assert all(set(o) == set(cpr.OBSERVATION_FIELDS) for o in data["observations"])
    committed = json.loads(_FIXTURE.read_text(encoding="utf-8"))["sessions"]
    for data in committed.values():
        assert all(set(t) == set(cpr.TRACE_FIELDS) for t in data["traces"])
        assert all(set(o) == set(cpr.OBSERVATION_FIELDS) for o in data["observations"])
