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

# The model and reasoning effort per step after the task 056 switch (D2, D4, D9): the tier the
# step follows and the effort it sends. "medium" is written where nothing was sent
# before (the provider default, probed 2026-11-02); "none" where the route knob gave
# it to Terra; "high" where a module hard-coded it (classify and the two finding vetters
# moved to "medium" in Phase 5 on replay evidence); "low" on the two steps still on the
# frontier tier (longlist_shortlist, longlist_discover) because gpt-6.1-sol refuses
# "none" (owner, 2026-11-01); the other eleven former frontier steps carry the tier and
# effort the owner chose from the frontier replay on 2026-11-02 (Phase 5 step 1b).
# Changing a value here is a deliberate behaviour change, never a side effect.
STEP_TIER_AND_EFFORT: dict[str, tuple[str, str]] = {
    "screen_abstract": ("fast", "medium"),
    "screen_full": ("fast", "medium"),
    "select_rerank": ("fast", "medium"),
    "characterise_discover": ("fast", "medium"),
    "characterise_assign": ("fast", "medium"),
    "group_discover": ("fast", "medium"),
    "group_assign": ("fast", "medium"),
    "extract_iof_findings": ("fast", "medium"),
    "extract_icf_findings": ("fast", "medium"),
    "extract_interventions": ("fast", "medium"),
    "search_generate_queries": ("fast", "medium"),
    "search_reformulate": ("fast", "medium"),
    "search_suggest": ("fast", "medium"),
    "search_queries_v2_openalex": ("fast", "medium"),
    "search_queries_v2_overton": ("fast", "medium"),
    "search_reformulate_v2_openalex": ("fast", "medium"),
    "search_reformulate_v2_overton": ("fast", "medium"),
    "synthesise_write_source_note": ("fast", "medium"),
    "synthesise_write_intro": ("fast", "medium"),
    "judge_grounding": ("fast", "medium"),
    "agent_triage": ("fast", "medium"),
    "agent_gate_sort": ("fast", "medium"),
    "agent_longlist_sort": ("fast", "medium"),
    "longlist_assign": ("fast", "medium"),
    "option_profile_fold": ("fast", "medium"),
    "option_profile_place_sentences": ("fast", "medium"),
    "classify_document": ("fast", "medium"),
    "extract_vet_iof_findings": ("fast", "medium"),
    "extract_vet_icf_findings": ("fast", "medium"),
    "extract_annotate_relevance": ("fast", "high"),
    "synthesise_propose_sections": ("standard", "none"),
    "synthesise_write_block_summary": ("standard", "none"),
    "synthesise_write_artefact_summary": ("standard", "none"),
    "synthesise_judge_summary": ("standard", "none"),
    "synthesise_section_turn": ("standard", "none"),
    "synthesise_section_emit": ("standard", "none"),
    "synthesise_write_key_findings": ("standard", "none"),
    "synthesise_write_case_studies": ("standard", "none"),
    "chat": ("standard", "none"),
    "task_title": ("fast", "low"),
    "shortlist_note": ("standard", "low"),
    "chat_title": ("fast", "low"),
    "agent_route": ("standard", "medium"),
    "agent_decide": ("standard", "medium"),
    "agent_option_design": ("standard", "medium"),
    "agent_suggest": ("standard", "medium"),
    "task_agent_turn": ("standard", "medium"),
    "task_agent_scoping_turn": ("standard", "none"),
    "longlist_discover": ("frontier", "low"),
    "longlist_themes": ("standard", "medium"),
    "longlist_assign_themes": ("fast", "medium"),
    "longlist_type": ("fast", "medium"),
    "longlist_constrain": ("standard", "none"),
    "longlist_distinct": ("standard", "none"),
    "longlist_authority": ("standard", "none"),
    "longlist_shortlist": ("frontier", "low"),
    "option_profile_line": ("standard", "none"),
    "option_profile_potential_impact": ("standard", "none"),
    "option_profile_ambition": ("standard", "none"),
    "option_profile_setting": ("standard", "high"),
}

# Which model each tier names after the switch, per route (gpt-6 family, D2).
TIER_MODELS = {
    "openai-direct": {
        "fast": "gpt-6-luna",
        "standard": "gpt-6.1-terra",
        "frontier": "gpt-6.1-sol",
    },
    "bedrock": {
        "fast": "global.openai.gpt-6-luna",
        "standard": "global.openai.gpt-6.1-terra",
        "frontier": "global.openai.gpt-6.1-sol",
    },
}
TIER_MODELS["bedrock-claude"] = TIER_MODELS["bedrock"]

# Each step's request timeout in [steps] (task 057, D12): the literal its call site's
# client carried in code before task 057, so a route without overrides behaves as
# before. 120 s: the synthesis writer client, the grounding judge, group clustering,
# the long-output extract and vetter steps, and chat; 30 s: the source note and
# intro (their own small client); 60 s: every other step.
STEP_TIMEOUT_S: dict[str, float] = {
    **dict.fromkeys(STEP_TIER_AND_EFFORT, 60.0),
    **dict.fromkeys(
        (
            "group_discover",
            "group_assign",
            "extract_iof_findings",
            "extract_icf_findings",
            "extract_vet_iof_findings",
            "extract_vet_icf_findings",
            "synthesise_propose_sections",
            "synthesise_write_block_summary",
            "synthesise_write_artefact_summary",
            "synthesise_judge_summary",
            "synthesise_section_turn",
            "synthesise_section_emit",
            "synthesise_write_key_findings",
            "synthesise_write_case_studies",
            "judge_grounding",
            "chat",
        ),
        120.0,
    ),
    "synthesise_write_source_note": 30.0,
    "synthesise_write_intro": 30.0,
    "task_title": 20.0,
    "shortlist_note": 30.0,
    "chat_title": 20.0,
}

def _default() -> Route:
    return load_route(ROUTE_FILE, "openai-direct", {})


def test_route_file_ships_inside_the_package() -> None:
    assert ROUTE_FILE.is_file()
    assert "src/policy_atlas" in str(ROUTE_FILE)


@pytest.mark.parametrize("name", ["openai-direct", "bedrock", "bedrock-claude"])
def test_every_step_resolves_todays_model_and_effort_on_every_route(name: str) -> None:
    """Task 056 D4/D9: 56 steps, each with today's model and effort, on all three routes."""
    route = load_route(ROUTE_FILE, name, {})
    assert set(route.steps) == set(STEP_TIER_AND_EFFORT)
    # task 058 adds synthesise_section_emit, task_title, chat_title and shortlist_note
    assert len(route.steps) == 60
    for step, (tier, effort) in STEP_TIER_AND_EFFORT.items():
        assert route.model_for(step) == TIER_MODELS[name][tier], step
        if name == "bedrock" and step == "judge_grounding":
            # Task 057 D14: the grounding judge runs at low effort on the bedrock route.
            assert route.effort_for(step) == "low"
        else:
            assert route.effort_for(step) == effort, step
    # Task 057 D12: the bedrock route carries timeout overrides for nine steps and the
    # judge's low effort (D14); no route overrides a model.
    assert all(exc.model is None for exc in route.step_exceptions.values())
    if name != "bedrock":
        assert route.step_exceptions == {}


def test_every_step_carries_todays_timeout() -> None:
    """Task 057 D12: every [steps] entry has timeout_s > 0, equal to the call site's old literal."""
    route = _default()
    assert set(STEP_TIMEOUT_S) == set(route.steps)
    for step, timeout_s in STEP_TIMEOUT_S.items():
        assert route.steps[step].timeout_s > 0, step
        assert route.steps[step].timeout_s == timeout_s, step
        assert route.timeout_for(step) == timeout_s, step


@pytest.mark.parametrize("name", ["openai-direct", "bedrock", "bedrock-claude"])
def test_timeout_for_is_the_override_else_the_step_default(name: str) -> None:
    route = load_route(ROUTE_FILE, name, {})
    for step, default in route.steps.items():
        exception = route.step_exceptions.get(step)
        expected = (
            exception.timeout_s
            if exception is not None and exception.timeout_s is not None
            else default.timeout_s
        )
        assert route.timeout_for(step) == expected, step


def test_default_route_names_the_owners_model_choice() -> None:
    route = _default()
    assert route.openai_base_url == "https://api.openai.com/v1"
    assert route.api_key_env == "OPENAI_API_KEY"
    assert route.embeddings.backend == "openai"
    assert route.embeddings.model == "text-embedding-3-small"
    assert route.embeddings.profile == "openai_text_embedding_3_small_v1"
    assert route.search_queries.backend == "openai"
    assert not hasattr(route, "reasoning_effort_for")  # retired by task 056: effort is per step


def test_bedrock_names_bedrock_models_and_cohere() -> None:
    route = load_route(ROUTE_FILE, "bedrock", {})
    assert route.openai_base_url.startswith("https://bedrock-runtime.eu-west-2.")
    assert route.api_key_env == "AWS_BEARER_TOKEN_BEDROCK"
    assert route.model_for("classify_document") == "global.openai.gpt-6-luna"
    assert route.model_for("screen_abstract") == "global.openai.gpt-6-luna"
    assert route.model_for("synthesise_section_turn") == "global.openai.gpt-6.1-terra"
    assert route.model_for("task_agent_turn") == "global.openai.gpt-6.1-terra"
    assert route.model_for("task_agent_scoping_turn") == "global.openai.gpt-6.1-terra"
    assert route.model_for("longlist_shortlist") == "global.openai.gpt-6.1-sol"
    assert route.model_for("longlist_assign") == "global.openai.gpt-6-luna"
    assert route.model_for("agent_decide") == "global.openai.gpt-6.1-terra"
    assert route.embeddings.backend == "cohere"
    assert route.embeddings.model == "eu.cohere.embed-v4:0"
    assert route.embeddings.profile == "cohere_embed_v4_1536_v1"
    assert route.search_queries.backend == "openai"


def test_bedrock_claude_switches_only_query_generation() -> None:
    plain = load_route(ROUTE_FILE, "bedrock", {})
    claude = load_route(ROUTE_FILE, "bedrock-claude", {})
    assert claude.search_queries.backend == "claude"
    assert claude.search_queries.model == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    for step in STEP_TIER_AND_EFFORT:
        assert claude.model_for(step) == plain.model_for(step), step
        if step not in plain.step_exceptions:
            # bedrock-claude is not in use and carries none of bedrock's task 057 step
            # overrides (timeouts, the judge's low effort); it follows the [steps] defaults.
            assert claude.effort_for(step) == plain.effort_for(step), step
    assert claude.embeddings == plain.embeddings


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """\
[steps]
screen = { tier = "mini", reasoning_effort = "medium", timeout_s = 60 }
synthesis = { tier = "standard", reasoning_effort = "none", timeout_s = 120 }

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
    # A bare string changes the model only; the effort stays the step's default.
    assert route.effort_for("screen") == "medium"
    assert route.effort_for("synthesis") == "none"


def test_step_exception_table_form_sets_model_and_or_effort(tmp_path: Path) -> None:
    """Task 056 D4: a route may override a step's effort, its model, or both."""
    path = _write(
        tmp_path,
        "r.toml",
        MINIMAL
        + "[routes.r.steps]\n"
        + 'screen = { reasoning_effort = "high" }\n'
        + 'synthesis = { model = "mini", reasoning_effort = "low" }\n',
    )
    route = load_route(path, "r", {})
    assert route.model_for("screen") == "m-mini"
    assert route.effort_for("screen") == "high"
    assert route.model_for("synthesis") == "m-mini"
    assert route.effort_for("synthesis") == "low"
    # Neither override names a timeout, so both keep the step's own.
    assert route.timeout_for("screen") == 60
    assert route.timeout_for("synthesis") == 120


def test_step_exception_may_override_only_the_timeout(tmp_path: Path) -> None:
    """Task 057 D12: a route may shorten one step's timeout and change nothing else."""
    path = _write(
        tmp_path,
        "r.toml",
        MINIMAL + "[routes.r.steps]\nscreen = { timeout_s = 7.5 }\n",
    )
    route = load_route(path, "r", {})
    assert route.timeout_for("screen") == 7.5
    assert route.model_for("screen") == "m-mini"
    assert route.effort_for("screen") == "medium"
    assert route.timeout_for("synthesis") == 120
    # A bare-string exception changes the model only, never the timeout.
    bare = _write(tmp_path, "bare.toml", MINIMAL + '[routes.r.steps]\nscreen = "standard"\n')
    assert load_route(bare, "r", {}).timeout_for("screen") == 60


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (MINIMAL.replace(", timeout_s = 60", ""), "missing key 'timeout_s'"),
        (MINIMAL.replace("timeout_s = 60", "timeout_s = 0"), "must be above zero"),
        (MINIMAL.replace("timeout_s = 60", "timeout_s = -5"), "must be above zero"),
        (MINIMAL.replace("timeout_s = 60", 'timeout_s = "60"'), "must be a number of seconds"),
        (MINIMAL.replace("timeout_s = 60", "timeout_s = true"), "must be a number of seconds"),
        (MINIMAL + "[routes.r.steps]\nscreen = { timeout_s = 0 }\n", "must be above zero"),
        (MINIMAL + '[routes.r.steps]\nscreen = { timeout_s = "x" }\n', "number of seconds"),
        (MINIMAL + "[routes.r.steps]\nscreen = { timeout = 5 }\n", "unknown key"),
    ],
)
def test_timeout_shapes_fail_loud(tmp_path: Path, text: str, match: str) -> None:
    path = _write(tmp_path, "bad.toml", text)
    with pytest.raises(RuntimeError, match=match):
        load_route(path, "r", {})


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (MINIMAL.replace('reasoning_effort = "medium"', 'reasoning_effort = "max"'), "not one of"),
        (MINIMAL.replace(', reasoning_effort = "medium"', ""), "missing key 'reasoning_effort'"),
        (
            MINIMAL.replace(
                'screen = { tier = "mini", reasoning_effort = "medium", timeout_s = 60 }',
                'screen = "mini"',
            ),
            "must be a table",
        ),
        (MINIMAL.replace('tier = "mini",', 'tier = "mini", temperature = 1,'), "unknown key"),
        (MINIMAL + '[routes.r.steps]\nscreen = { reasoning_effort = "max" }\n', "not one of"),
        (MINIMAL + '[routes.r.steps]\nscreen = { model = "mini", extra = 1 }\n', "unknown key"),
        (MINIMAL + '[routes.r.steps]\nscreen = {}\n', "empty table"),
        (MINIMAL + '[routes.r.steps]\nscreen = ""\n', "empty model"),
        (MINIMAL + '[routes.r.steps]\nscreen = { model = "" }\n', "'model' is empty"),
        (MINIMAL + '[routes.r.knobs]\nreasoning_effort = "none"\n', "'knobs' was retired"),
    ],
)
def test_effort_shapes_fail_loud(tmp_path: Path, text: str, match: str) -> None:
    path = _write(tmp_path, "bad.toml", text)
    with pytest.raises(RuntimeError, match=match):
        load_route(path, "r", {})


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
            "'knobs' was retired",
        ),
    ],
)
def test_unknown_backend_names_and_wrong_shapes_fail_loud(
    tmp_path: Path, text: str, match: str
) -> None:
    path = _write(tmp_path, "bad.toml", text)
    with pytest.raises(RuntimeError, match=match):
        load_route(path, "r", {})


def test_embedding_pool_cap_defaults_to_8_and_is_strict(tmp_path: Path) -> None:
    """Task 057 (D6): ``pool_cap`` is optional (8), a whole number of at least 1,
    and the embeddings table takes no other unknown key."""
    assert load_route(_write(tmp_path, "r.toml", MINIMAL), "r", {}).embeddings.pool_cap == 8
    # The two Cohere routes run a wider pool (12); the legacy OpenAI route keeps 8.
    for name, cap in (("openai-direct", 8), ("bedrock", 12), ("bedrock-claude", 12)):
        assert load_route(ROUTE_FILE, name, {}).embeddings.pool_cap == cap, name
    with_cap = MINIMAL.replace('profile = "p"\n', 'profile = "p"\npool_cap = 3\n')
    assert load_route(_write(tmp_path, "c.toml", with_cap), "r", {}).embeddings.pool_cap == 3
    for bad, match in (
        ("pool_cap = 0", "'pool_cap' is 0; it must be at least 1"),
        ('pool_cap = "8"', "'pool_cap' must be a whole number, not str"),
        ("pool_cap = 2.5", "'pool_cap' must be a whole number, not float"),
        ("pool_cap = true", "'pool_cap' must be a whole number, not bool"),
        ("pool_size = 8", r"embeddings: unknown key\(s\) \['pool_size'\]"),
    ):
        text = MINIMAL.replace('profile = "p"\n', f'profile = "p"\n{bad}\n')
        with pytest.raises(RuntimeError, match=match):
            load_route(_write(tmp_path, "bad.toml", text), "r", {})


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
    client = resolve_openai_client(None, backend_name="test")
    assert str(client.base_url).rstrip("/") == "https://api.openai.com/v1"


def test_client_never_retries_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 057 D12: the one retry is traced_attempts', never the SDK's silent one."""
    from policy_atlas.core.openai_client import resolve_openai_client

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    assert resolve_openai_client(None, backend_name="test").max_retries == 0


def test_bedrock_route_reads_its_own_key_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both keys may be set at once; a Bedrock route reads the Bedrock one, never the OpenAI one."""
    from policy_atlas.core import model_routes, openai_client

    bedrock = load_route(ROUTE_FILE, "bedrock", {})
    monkeypatch.setattr(model_routes, "route", lambda: bedrock)
    monkeypatch.setattr(openai_client, "route", lambda: bedrock)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    with pytest.raises(RuntimeError, match="requires AWS_BEARER_TOKEN_BEDROCK"):
        openai_client.resolve_openai_client(None, backend_name="t")
    assert model_routes.live_api_key() is None
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-key")
    client = openai_client.resolve_openai_client(None, backend_name="t")
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
        finding_vetter,
        icf_prompt,
        interventions_prompt,
        iof_prompt,
        relevance_annotator,
    )
    from policy_atlas.evidence_search.group import group_clustering
    from policy_atlas.evidence_search.sourcing import search_prompts
    from policy_atlas.evidence_search.synthesis import grounding_judge, synthesis_backend
    from policy_atlas.options_scoping import scoping_backend
    from policy_atlas.runtime import agent_backend, chat_prompt, task_agent, task_agent_scoping

    luna, terra, sol = "gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"
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
        (task_agent_scoping, "TASK_AGENT_SCOPING_MODEL"): terra,  # task 056 P5 1b (owner)
        (scoping_backend, "LONGLIST_JUDGMENT_MODEL"): sol,
        (scoping_backend, "LONGLIST_ASSIGNMENT_MODEL"): luna,
        (interventions_prompt, "INTERVENTIONS_MODEL"): luna,
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
        "print(r.model_for('search_generate_queries'))\n"
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
    assert _resolve_in_subprocess({}) == ["gpt-6-luna", "openai_text_embedding_3_small_v1"]
    assert _resolve_in_subprocess({"POLICY_ATLAS_MODEL_ROUTE": "bedrock"}) == [
        "global.openai.gpt-6-luna",
        "cohere_embed_v4_1536_v1",
    ]


def test_route_is_cached_per_process() -> None:
    assert model_routes.route() is model_routes.route()
