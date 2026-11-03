"""Coverage for the per-step timeout script (`scripts/step_timeouts.py`, task 057 Phase 0).

The fixture holds 518 synthetic Langfuse observations (timing fields only, no real
run data), designed so every expected number is worked out by hand:

- ``classify:document`` (60 s client): 101 healthy calls of 1.0, 1.1, ..., 11.0 s;
  three ERROR-level calls, one of 65 s and one of exactly 60 s (not healthy), one on
  ``gpt-6-luna`` (OpenAI direct, not Bedrock), one 9999-dated duplicate row and one
  with no end time.
- ``synthesise:section_turn`` (60) and ``synthesise:repair_claims`` (50), one step, all
  2.0 s: n = 110, p99 2.0, proposal hits the 5 s floor.
- numbered ``search_queries_v2_openalex:N`` (40) and
  ``search_reformulate_v2_openalex:r1:N`` (5): prefix matching, n < 100.
- ``synthesise:write_intro`` (30 s client): 99 x 1.0 s, one 29.0 s, one 31.0 s
  (over the timeout): exactly n = 100.
- ``chat:call``: 150 x 4.0 s, exempt (streamed chat).
- two ``mystery:call`` (unmapped) and one EMBEDDING row.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "scripts" / "step_timeouts.py"
_FIXTURE = Path(__file__).resolve().parent / "data" / "step_timeouts_fixture.json"
_SRC = _REPO / "backend" / "src" / "policy_atlas"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("step_timeouts", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


st = _load()


@pytest.fixture
def observations() -> list[dict[str, Any]]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data["observations"])


@pytest.fixture
def table(observations: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = st.derive_table(observations, st.route_steps())
    return result


def _row(table: dict[str, Any], step: str) -> dict[str, Any]:
    return next(r for r in table["rows"] if r["step"] == step)


# --- The site table against the code ---------------------------------------------


def test_every_site_step_is_a_route_step() -> None:
    steps = set(st.route_steps())
    assert {s.step for s in st.SITES} <= steps


def test_every_route_step_has_a_site() -> None:
    # Today every step has a traced generation; a new step without one would show
    # up as "no traced generation" in the report and should be a deliberate change.
    assert set(st.route_steps()) == {s.step for s in st.SITES}


def test_sites_sharing_a_step_share_a_timeout() -> None:
    by_step: dict[str, set[int]] = {}
    for s in st.SITES:
        by_step.setdefault(s.step, set()).add(s.timeout_s)
    assert all(len(v) == 1 for v in by_step.values()), by_step


def test_site_names_are_unique_and_unambiguous() -> None:
    names = [s.name for s in st.SITES]
    assert len(names) == len(set(names))
    for a in names:
        assert not any(b != a and b.startswith(a + ":") for b in names), a


def test_site_names_and_modules_exist_in_the_code() -> None:
    source = "\n".join(p.read_text(encoding="utf-8") for p in _SRC.rglob("*.py"))
    for s in st.SITES:
        assert (_SRC / s.module).is_file(), s.module
        if s.name.startswith("group:"):
            continue  # built as f"group:{stage}" in group_clustering.py
        assert f'"{s.name}' in source, s.name


# --- Matching and the derived table ------------------------------------------------


def test_site_for_matches_exact_names_and_numbered_suffixes() -> None:
    assert st.site_for("classify:document").step == "classify_document"
    assert st.site_for("search_queries_v2_openalex:3").step == "search_queries_v2_openalex"
    assert st.site_for("search_reformulate_v2_overton:r2:1").step == "search_reformulate_v2_overton"
    assert st.site_for("synthesise:repair_claims").step == "synthesise_section_turn"
    assert st.site_for("classify:documentx") is None
    assert st.site_for(None) is None


def test_bedrock_detection() -> None:
    assert st.is_bedrock("global.openai.gpt-6-luna")
    assert st.is_bedrock("eu.cohere.embed-v4:0")
    assert st.is_bedrock("cohere.embed-v4:0")
    assert not st.is_bedrock("gpt-6-luna")
    assert not st.is_bedrock(None)


def test_classify_set_from_p99(table: dict[str, Any]) -> None:
    row = _row(table, "classify_document")
    # 101 values 1.0..11.0; inclusive p99 sits at index 0.99 * 100 = 99 -> 10.9 s.
    assert row["n_healthy"] == 101
    assert row["n_bedrock"] == 107  # 101 + 3 errors + 2 over timeout + 1 no end time
    assert row["p99_s"] == pytest.approx(10.9)
    assert row["proposed_timeout_s"] == 22  # ceil(2 x 10.9)
    assert row["today_timeout_s"] == 60
    assert row["decision"] == "set"


def test_shared_step_and_floor(table: dict[str, Any]) -> None:
    row = _row(table, "synthesise_section_turn")
    assert (row["n_healthy"], row["p99_s"]) == (110, 2.0)
    assert row["proposed_timeout_s"] == 5  # max(5, ceil(4.0))
    assert row["today_timeout_s"] == 120


def test_exactly_one_hundred_is_enough(table: dict[str, Any]) -> None:
    row = _row(table, "synthesise_write_intro")
    # 99 x 1.0 and one 29.0 (the 31.0 is over the 30 s timeout); p99 at index 98.01:
    # 1.0 + 0.01 x 28.0 = 1.28 s; ceil(2.56) = 3, raised to the 5 s floor.
    assert row["n_healthy"] == 100
    assert row["p99_s"] == pytest.approx(1.28)
    assert (row["proposed_timeout_s"], row["decision"]) == (5, "set")


def test_small_steps_keep_today(table: dict[str, Any]) -> None:
    row = _row(table, "search_queries_v2_openalex")
    assert (row["n_healthy"], row["p99_s"], row["proposed_timeout_s"]) == (40, 3.0, None)
    assert row["decision"] == "keep, n<100"
    assert _row(table, "search_reformulate_v2_openalex")["n_healthy"] == 5
    empty = _row(table, "longlist_discover")
    assert (empty["n_healthy"], empty["p99_s"], empty["decision"]) == (0, None, "keep, n<100")


def test_chat_is_exempt(table: dict[str, Any]) -> None:
    row = _row(table, "chat")
    assert row["n_healthy"] == 150
    assert (row["proposed_timeout_s"], row["decision"]) == (None, "keep, exempt (streamed chat)")


def test_unmapped_and_skipped(table: dict[str, Any]) -> None:
    assert table["unmapped"] == {"mystery:call": 2}
    assert table["skipped"] == {
        "not a generation": 1,
        "9999 duplicate row": 1,
        "not bedrock": 1,
        "no end time": 1,
    }


def test_step_without_a_site(observations: list[dict[str, Any]]) -> None:
    result = st.derive_table(observations, ["classify_document", "made_up_step"])
    assert result["rows"][1]["decision"] == "no traced generation"
    assert result["rows"][1]["today_timeout_s"] is None


# --- Output formats ----------------------------------------------------------------


def test_markdown_and_toml(table: dict[str, Any]) -> None:
    md = st.format_markdown(table, "2026-11-02")
    assert "| classify_document | 101 | 10.9 | 22 | 60 | set |" in md
    assert "| chat | 150 | 4.0 |  | 120 | keep, exempt (streamed chat) |" in md
    assert "- `mystery:call`: 2" in md
    toml = st.format_toml(table)
    assert "[routes.bedrock.steps.classify_document]\ntimeout_s = 22\n" in toml
    assert "[routes.bedrock.steps.synthesise_write_intro]\ntimeout_s = 5\n" in toml
    assert "[routes.bedrock.steps.chat]" not in toml
    assert "[routes.bedrock.steps.search_queries_v2_openalex]" not in toml
    assert "# synthesise_write_source_note = 30" in toml


def test_print_sites_lists_every_site() -> None:
    text = st.format_sites()
    assert text.count("\n") == len(st.SITES) + 2
    assert (
        "| `chat:call` | chat | 120 | runtime/chat_backend_openai.py (streamed, exempt) |" in text
    )


def test_in_window(observations: list[dict[str, Any]]) -> None:
    kept = st.in_window(observations, "2026-11-02T10:02:00Z", "2026-11-02T10:03:00Z")
    assert len(kept) == 60  # one observation per second in the fixture
    assert all(o["startTime"].startswith("2026-11-02T10:02:") for o in kept)
