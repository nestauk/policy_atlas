"""Tests for the committed model route file and its loader (task 045, contract D3).

The default route must reproduce every pre-045 literal exactly; everything else
is the fail-loud rule, the overlay, and the retired-variable warning.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from policy_atlas.core import model_routes
from policy_atlas.core.model_routes import ROUTE_FILE, Route, load_route

# What the code said before task 045, step by step. The default route must
# give exactly these, so a laptop with nothing set behaves as before.
PRE_045_MODELS = {
    "screen": "gpt-5.6-luna",
    "search_queries": "gpt-5.6-luna",
    "search_reformulate": "gpt-5.6-luna",
    "search_suggest": "gpt-5.6-luna",
    "classify": "gpt-5.4-mini",
    "extract": "gpt-5.4-mini",
    "icf_extract": "gpt-5.4-mini",
    "finding_vetter": "gpt-5.4-mini",
    "icf_finding_vetter": "gpt-5.4-mini",
    "relevance": "gpt-5.4-mini",
    "rerank": "gpt-5.4-mini",
    "theme_discovery": "gpt-5.4-mini",
    "theme_assignment": "gpt-5.4-mini",
    "group_clustering": "gpt-5.4-mini",
    "grounding_judge": "gpt-5.4-mini",
    "mrs_note": "gpt-5.4-mini",
    "full_report_intro": "gpt-5.4-mini",
    "agent_triage": "gpt-5.4-mini",
    "synthesis": "gpt-5.6-terra",
    "case_studies": "gpt-5.6-terra",
    "chat": "gpt-5.6-terra",
    "planner": "gpt-5.5",
    "agent": "gpt-5.5",
}


def _default() -> Route:
    return load_route(ROUTE_FILE, "openai-direct", {})


def test_route_file_ships_inside_the_package() -> None:
    assert ROUTE_FILE.is_file()
    assert "src/policy_atlas" in str(ROUTE_FILE)


def test_default_route_reproduces_every_pre_045_model() -> None:
    route = _default()
    assert set(route.steps) == set(PRE_045_MODELS)
    for step, model in PRE_045_MODELS.items():
        assert route.model_for(step) == model, step
    assert route.openai_base_url == "https://api.openai.com/v1"
    assert route.embeddings.backend == "openai"
    assert route.embeddings.model == "text-embedding-3-small"
    assert route.embeddings.profile == "openai_text_embedding_3_small_v1"
    assert route.search_queries.backend == "openai"
    assert route.reasoning_effort_for("gpt-5.6-terra") == "none"
    assert route.reasoning_effort_for("gpt-5.5") is None


def test_bedrock_local_names_bedrock_models_and_cohere() -> None:
    route = load_route(ROUTE_FILE, "bedrock-local", {})
    assert route.openai_base_url.startswith("https://bedrock-runtime.eu-west-2.")
    assert route.model_for("classify") == "global.openai.gpt-5.6-luna"
    assert route.model_for("screen") == "global.openai.gpt-5.6-luna"
    assert route.model_for("synthesis") == "global.openai.gpt-5.6-terra"
    assert route.model_for("planner") == "global.openai.gpt-5.6-terra"
    assert route.embeddings.backend == "cohere"
    assert route.embeddings.model == "eu.cohere.embed-v4:0"
    assert route.embeddings.profile == "cohere_embed_v4_1536_v1"
    assert route.search_queries.backend == "openai"
    assert route.reasoning_effort_for("global.openai.gpt-5.6-terra") == "none"


def test_bedrock_local_claude_switches_only_query_generation() -> None:
    plain = load_route(ROUTE_FILE, "bedrock-local", {})
    claude = load_route(ROUTE_FILE, "bedrock-local-claude", {})
    assert claude.search_queries.backend == "claude"
    assert claude.search_queries.model == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    for step in PRE_045_MODELS:
        assert claude.model_for(step) == plain.model_for(step), step
    assert claude.embeddings == plain.embeddings


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """\
[steps]
screen = "mini"
synthesis = "standard"

[routes.r]
openai_base_url = "https://example.test/v1"
[routes.r.text]
mini = "m-mini"
standard = "m-std"
[routes.r.embeddings]
backend = "openai"
model = "e"
profile = "p"
[routes.r.search_queries]
backend = "openai"
"""


def test_step_exception_may_name_a_tier_or_a_model(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "r.toml",
        MINIMAL + '[routes.r.steps]\nscreen = "standard"\nsynthesis = "exact-model"\n',
    )
    route = load_route(path, "r", {})
    assert route.model_for("screen") == "m-std"
    assert route.model_for("synthesis") == "exact-model"


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (MINIMAL.replace('mini = "m-mini"\n', ""), "needs tier 'mini'"),
        (MINIMAL + '[routes.r.steps]\nnope = "mini"\n', "unknown step 'nope'"),
        (
            MINIMAL.replace("[routes.r.embeddings]\n", "[routes.r.embeddingz]\n"),
            "missing key 'embeddings'",
        ),
        (
            MINIMAL.replace('backend = "openai"\n', 'backend = "claude"\n', 1).replace(
                '[routes.r.search_queries]\nbackend = "openai"',
                '[routes.r.search_queries]\nbackend = "claude"',
            ),
            "missing key",
        ),
        ("this is not = toml [", "not valid TOML"),
    ],
)
def test_malformed_route_files_fail_loud(tmp_path: Path, text: str, match: str) -> None:
    path = _write(tmp_path, "bad.toml", text)
    with pytest.raises(RuntimeError, match=match):
        load_route(path, "r", {})


def test_unknown_route_and_unknown_step_fail_loud(tmp_path: Path) -> None:
    path = _write(tmp_path, "r.toml", MINIMAL)
    with pytest.raises(RuntimeError, match="route 'missing' is not defined"):
        load_route(path, "missing", {})
    with pytest.raises(RuntimeError, match="step 'nope' is not in the \\[steps\\] table"):
        load_route(path, "r", {}).model_for("nope")


def test_missing_file_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="route file not found"):
        load_route(tmp_path / "absent.toml", "r", {})


def test_overlay_replaces_and_adds_routes_but_not_steps(tmp_path: Path) -> None:
    base = _write(tmp_path, "r.toml", MINIMAL)
    overlay = _write(
        tmp_path,
        "overlay.toml",
        MINIMAL.replace("[routes.r]", "[routes.r2]")
        .replace("[routes.r.", "[routes.r2.")
        .replace('mini = "m-mini"', 'mini = "m-mini-2"')
        .split("[steps]")[1]
        .split("\n", 3)[3],  # drop the [steps] table: overlays may not carry one
    )
    # Replace: an overlay route with the same name wins.
    replaced = _write(
        tmp_path,
        "replace.toml",
        '[routes.r]\nopenai_base_url = "https://other.test/v1"\n[routes.r.text]\n'
        'mini = "m-mini-x"\nstandard = "m-std"\n[routes.r.embeddings]\nbackend = "openai"\n'
        'model = "e"\nprofile = "p"\n[routes.r.search_queries]\nbackend = "openai"\n',
    )
    assert load_route(base, "r", {}, overlay_path=replaced).model_for("screen") == "m-mini-x"
    # Add: a new route name becomes selectable.
    assert load_route(base, "r2", {}, overlay_path=overlay).model_for("screen") == "m-mini-2"
    # The committed route is untouched when the overlay only adds.
    assert load_route(base, "r", {}, overlay_path=overlay).model_for("screen") == "m-mini"
    # An overlay may not carry [steps].
    with_steps = _write(tmp_path, "steps.toml", '[steps]\nscreen = "mini"\n[routes.r3]\n')
    with pytest.raises(RuntimeError, match="may not change \\[steps\\]"):
        load_route(base, "r", {}, overlay_path=with_steps)
    with pytest.raises(RuntimeError, match="route file not found"):
        load_route(base, "r", {}, overlay_path=tmp_path / "absent.toml")


def test_retired_variables_change_nothing_and_are_named(tmp_path: Path) -> None:
    from structlog.testing import capture_logs

    path = _write(tmp_path, "r.toml", MINIMAL)
    with capture_logs() as logs:
        route = load_route(path, "r", {"POLICY_ATLAS_SYNTHESIS_MODEL": "gpt-9"})
    assert route.model_for("synthesis") == "m-std"
    [event] = [entry for entry in logs if entry["event"] == "model_routes.retired_env_ignored"]
    assert event["keys"] == ["POLICY_ATLAS_SYNTHESIS_MODEL"]
    with capture_logs() as logs:
        load_route(path, "r", {})
    assert not [entry for entry in logs if entry["event"] == "model_routes.retired_env_ignored"]


def test_stray_openai_base_url_does_not_move_a_route() -> None:
    route = load_route(ROUTE_FILE, "openai-direct", {"OPENAI_BASE_URL": "https://stray.test"})
    assert route.openai_base_url == "https://api.openai.com/v1"


def _resolve_in_subprocess(env_extra: dict[str, str]) -> list[str]:
    """Import the loader in a fresh interpreter and print two resolved values."""
    code = (
        "from policy_atlas.core.model_routes import route\n"
        "r = route()\n"
        "print(r.model_for('search_queries'))\n"
        "print(r.embeddings.profile)\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("POLICY_ATLAS_MODEL_ROUTE")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={**env, **env_extra},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def test_import_time_selection_follows_the_variable() -> None:
    assert _resolve_in_subprocess({}) == ["gpt-5.6-luna", "openai_text_embedding_3_small_v1"]
    assert _resolve_in_subprocess({"POLICY_ATLAS_MODEL_ROUTE": "bedrock-local"}) == [
        "global.openai.gpt-5.6-luna",
        "cohere_embed_v4_1536_v1",
    ]


def test_route_is_cached_per_process() -> None:
    assert model_routes.route() is model_routes.route()
