"""Tests for the committed model route file and its loader (task 053, contract D3).

The default route must name the owner's model choice exactly; everything else
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

# The owner's model choice for the default route (2026-10-22: three tiers; the
# cheap steps on Luna, the writers and agents on Terra, the scoping judgment on
# Sol). Until then the default route reproduced the pre-053 literals.
DEFAULT_ROUTE_MODELS = {
    "screen": "gpt-5.6-luna",
    "search_queries": "gpt-5.6-luna",
    "search_reformulate": "gpt-5.6-luna",
    "search_suggest": "gpt-5.6-luna",
    "classify": "gpt-5.6-luna",
    "extract": "gpt-5.6-luna",
    "icf_extract": "gpt-5.6-luna",
    "finding_vetter": "gpt-5.6-luna",
    "icf_finding_vetter": "gpt-5.6-luna",
    "relevance": "gpt-5.6-luna",
    "rerank": "gpt-5.6-luna",
    "theme_discovery": "gpt-5.6-luna",
    "theme_assignment": "gpt-5.6-luna",
    "group_clustering": "gpt-5.6-luna",
    "grounding_judge": "gpt-5.6-luna",
    "mrs_note": "gpt-5.6-luna",
    "full_report_intro": "gpt-5.6-luna",
    "agent_triage": "gpt-5.6-luna",
    "synthesis": "gpt-5.6-terra",
    "case_studies": "gpt-5.6-terra",
    "chat": "gpt-5.6-terra",
    "task_agent": "gpt-5.6-terra",
    "agent": "gpt-5.6-terra",
    # Options scoping (tasks 044 to 046), as merged into 053.
    "task_agent_scoping": "gpt-5.6-sol",
    "longlist_judgment": "gpt-5.6-sol",
    "longlist_assignment": "gpt-5.6-luna",
    "extract_interventions": "gpt-5.6-luna",
}


def _default() -> Route:
    return load_route(ROUTE_FILE, "openai-direct", {})


def test_route_file_ships_inside_the_package() -> None:
    assert ROUTE_FILE.is_file()
    assert "src/policy_atlas" in str(ROUTE_FILE)


def test_default_route_names_the_owners_model_choice() -> None:
    route = _default()
    assert set(route.steps) == set(DEFAULT_ROUTE_MODELS)
    for step, model in DEFAULT_ROUTE_MODELS.items():
        assert route.model_for(step) == model, step
    assert route.openai_base_url == "https://api.openai.com/v1"
    assert route.api_key_env == "OPENAI_API_KEY"
    assert route.embeddings.backend == "openai"
    assert route.embeddings.model == "text-embedding-3-small"
    assert route.embeddings.profile == "openai_text_embedding_3_small_v1"
    assert route.search_queries.backend == "openai"
    assert route.reasoning_effort_for("gpt-5.6-terra") == "none"
    assert route.reasoning_effort_for("gpt-5.6-sol") is None


def test_bedrock_names_bedrock_models_and_cohere() -> None:
    route = load_route(ROUTE_FILE, "bedrock", {})
    assert route.openai_base_url.startswith("https://bedrock-runtime.eu-west-2.")
    assert route.api_key_env == "AWS_BEARER_TOKEN_BEDROCK"
    assert route.model_for("classify") == "global.openai.gpt-5.6-luna"
    assert route.model_for("screen") == "global.openai.gpt-5.6-luna"
    assert route.model_for("synthesis") == "global.openai.gpt-5.6-terra"
    assert route.model_for("task_agent") == "global.openai.gpt-5.6-terra"
    assert route.model_for("task_agent_scoping") == "global.openai.gpt-5.6-sol"
    assert route.model_for("longlist_assignment") == "global.openai.gpt-5.6-luna"
    assert route.model_for("agent") == "global.openai.gpt-5.6-terra"
    assert route.embeddings.backend == "cohere"
    assert route.embeddings.model == "eu.cohere.embed-v4:0"
    assert route.embeddings.profile == "cohere_embed_v4_1536_v1"
    assert route.search_queries.backend == "openai"
    assert route.reasoning_effort_for("global.openai.gpt-5.6-terra") == "none"


def test_bedrock_claude_switches_only_query_generation() -> None:
    plain = load_route(ROUTE_FILE, "bedrock", {})
    claude = load_route(ROUTE_FILE, "bedrock-claude", {})
    assert claude.search_queries.backend == "claude"
    assert claude.search_queries.model == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    for step in DEFAULT_ROUTE_MODELS:
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
api_key_env = "OPENAI_API_KEY"
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
        '[routes.r]\nopenai_base_url = "https://other.test/v1"\napi_key_env = "OPENAI_API_KEY"\n'
        '[routes.r.text]\n'
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


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (
            MINIMAL.replace('backend = "openai"\nmodel = "e"', 'backend = "cohre"\nmodel = "e"'),
            "embeddings: 'backend' is 'cohre', not one of",
        ),
        (
            MINIMAL.replace(
                '[routes.r.search_queries]\nbackend = "openai"',
                '[routes.r.search_queries]\nbackend = "Claude"\nmodel = "m"',
            ),
            "search_queries: 'backend' is 'Claude', not one of",
        ),
        (
            MINIMAL.replace(
                '[routes.r.text]\nmini = "m-mini"\nstandard = "m-std"\n', 'text = "oops"\n'
            ),
            "'text' must be a table, not str",
        ),
        (MINIMAL + '[routes.r.steps]\nscreen = "mini"\n[[routes.r.steps]]\n', "not valid TOML"),
        (
            MINIMAL.replace('api_key_env = "OPENAI_API_KEY"', 'api_key_env = "OPENAI_KEY"'),
            "'api_key_env' is 'OPENAI_KEY', not one of",
        ),
        (
            MINIMAL.replace(
                'api_key_env = "OPENAI_API_KEY"\n',
                'api_key_env = "OPENAI_API_KEY"\nknobs = "none"\n',
            ),
            "'knobs' must be a table, not str",
        ),
        (
            MINIMAL + '[routes.r.knobs]\nreasoning_effort = "none"\n',
            "knobs: 'reasoning_effort' must be a table, not str",
        ),
    ],
)
def test_unknown_backend_names_and_wrong_shapes_fail_loud(
    tmp_path: Path, text: str, match: str
) -> None:
    path = _write(tmp_path, "bad.toml", text)
    with pytest.raises(RuntimeError, match=match):
        load_route(path, "r", {})


def test_malformed_overlay_fails_loud_naming_the_overlay(tmp_path: Path) -> None:
    base = _write(tmp_path, "r.toml", MINIMAL)
    overlay = _write(tmp_path, "overlay.toml", "routes = [1, 2]\n")
    with pytest.raises(RuntimeError, match="overlay.toml: 'routes' must be a table, not list"):
        load_route(base, "r", {}, overlay_path=overlay)
    # A route that the overlay defines is reported against the overlay, not the base file.
    broken = _write(tmp_path, "broken.toml", '[routes.r2]\nopenai_base_url = "x"\n')
    with pytest.raises(RuntimeError, match=r"broken.toml \[routes.r2\]: missing key 'text'"):
        load_route(base, "r2", {}, overlay_path=broken)


def test_stray_openai_base_url_does_not_move_the_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """F6: the client seam takes its address from the route, never from the environment."""
    from policy_atlas.core.openai_client import resolve_openai_client

    monkeypatch.setenv("OPENAI_BASE_URL", "https://stray.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = resolve_openai_client(None, backend_name="test", timeout=1.0, max_retries=0)
    assert str(client.base_url).rstrip("/") == "https://api.openai.com/v1"


def test_bedrock_route_reads_its_own_key_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both keys may be set at once; a Bedrock route reads the Bedrock one, never the OpenAI one."""
    from policy_atlas.core import model_routes, openai_client

    bedrock = load_route(ROUTE_FILE, "bedrock", {})
    monkeypatch.setattr(model_routes, "route", lambda: bedrock)
    monkeypatch.setattr(openai_client, "route", lambda: bedrock)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    with pytest.raises(RuntimeError, match="requires AWS_BEARER_TOKEN_BEDROCK"):
        openai_client.resolve_openai_client(None, backend_name="t", timeout=1.0, max_retries=0)
    assert model_routes.live_api_key() is None
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-key")
    client = openai_client.resolve_openai_client(None, backend_name="t", timeout=1.0, max_retries=0)
    assert client.api_key == "bedrock-key"
    assert model_routes.live_api_key() == "bedrock-key"


def test_live_mode_switch_reads_the_route_key_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The web API's live switch and the dev CLI read the same helper as the client."""
    from policy_atlas.api import deps
    from policy_atlas.core import model_routes

    bedrock = load_route(ROUTE_FILE, "bedrock", {})
    monkeypatch.setattr(model_routes, "route", lambda: bedrock)
    monkeypatch.setattr(deps, "route", lambda: bedrock)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("PA_BACKEND_MODE", raising=False)
    assert deps._live() is False
    monkeypatch.setenv("PA_BACKEND_MODE", "live")
    with pytest.raises(RuntimeError, match="requires AWS_BEARER_TOKEN_BEDROCK"):
        deps._live()
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-key")
    assert deps._live() is True


def test_every_module_constant_equals_the_default_route() -> None:
    """Rubric item 10: the 29 constants the sweep rewired, each under the default route."""
    from policy_atlas.core import embeddings
    from policy_atlas.evidence_search.assess import classify_prompt, screen_prompt
    from policy_atlas.evidence_search.corpus import ranking, theme_grouping
    from policy_atlas.evidence_search.extract import (
        extract_interventions_prompt,
        finding_vetter,
        icf_prompt,
        iof_prompt,
        relevance_annotator,
    )
    from policy_atlas.evidence_search.group import group_clustering
    from policy_atlas.evidence_search.sourcing import search_prompts
    from policy_atlas.evidence_search.synthesis import grounding_judge, synthesis_backend
    from policy_atlas.options_scoping.longlist import longlist_backend
    from policy_atlas.runtime import agent_backend, chat_prompt, task_agent, task_agent_scoping

    luna, terra, sol = "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"
    expected = {
        (classify_prompt, "CLASSIFY_MODEL"): luna,
        (screen_prompt, "SCREEN_MODEL"): luna,
        (ranking, "RERANK_MODEL"): luna,
        (theme_grouping, "DISCOVERY_MODEL"): luna,
        (theme_grouping, "ASSIGNMENT_MODEL"): luna,
        (finding_vetter, "FINDING_VETTER_MODEL"): luna,
        (finding_vetter, "ICF_FINDING_VETTER_MODEL"): luna,
        (icf_prompt, "ICF_EXTRACTION_MODEL"): luna,
        (iof_prompt, "EXTRACTION_MODEL"): luna,
        (relevance_annotator, "RELEVANCE_ANNOTATOR_MODEL"): luna,
        (group_clustering, "GROUP_CLUSTERING_MODEL"): luna,
        (search_prompts, "SEARCH_QUERIES_MODEL"): luna,
        (search_prompts, "SEARCH_REFORMULATE_MODEL"): luna,
        (search_prompts, "SEARCH_SUGGEST_MODEL"): luna,
        (grounding_judge, "JUDGE_MODEL"): luna,
        (synthesis_backend, "SYNTHESIS_MODEL"): terra,
        (synthesis_backend, "CASE_STUDIES_MODEL"): terra,
        (synthesis_backend, "MRS_NOTE_MODEL"): luna,
        (synthesis_backend, "FULL_REPORT_INTRO_MODEL"): luna,
        (agent_backend, "AGENT_MODEL"): terra,
        (agent_backend, "AGENT_TRIAGE_MODEL"): luna,
        (chat_prompt, "CHAT_MODEL"): terra,
        (task_agent, "TASK_AGENT_MODEL"): terra,
        (task_agent_scoping, "TASK_AGENT_SCOPING_MODEL"): sol,
        (longlist_backend, "LONGLIST_JUDGMENT_MODEL"): sol,
        (longlist_backend, "LONGLIST_ASSIGNMENT_MODEL"): luna,
        (extract_interventions_prompt, "INTERVENTIONS_MODEL"): luna,
        (embeddings, "EMBEDDING_MODEL"): "text-embedding-3-small",
        (embeddings, "EMBEDDING_PROFILE"): "openai_text_embedding_3_small_v1",
    }
    assert len(expected) == 29
    for (module, constant), value in expected.items():
        assert getattr(module, constant) == value, f"{module.__name__}.{constant}"


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
    assert _resolve_in_subprocess({"POLICY_ATLAS_MODEL_ROUTE": "bedrock"}) == [
        "global.openai.gpt-5.6-luna",
        "cohere_embed_v4_1536_v1",
    ]


def test_route_is_cached_per_process() -> None:
    assert model_routes.route() is model_routes.route()
