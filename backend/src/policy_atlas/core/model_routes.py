"""Which AI model each step of the app uses, read from one committed file.

The file is ``model_routes.toml`` at the package root. It names every step once
with a default tier, and for each named *route* says which model each tier is,
plus provider knobs, the embedding model, the search-queries backend and which
environment variable holds the route's API key (so one secret can hold both the
OpenAI key and a Bedrock key, and switching route never edits the secret). One
environment variable, ``POLICY_ATLAS_MODEL_ROUTE``, picks the route; unset means
``openai-direct``, which reproduces the pre-053 behaviour exactly. An optional
second file named by ``POLICY_ATLAS_MODEL_ROUTE_FILE`` can replace or add routes
by name without touching the committed file (for evaluations).

Design: task 053 contract D3 and ADR 0041. Every lookup fails loud: an unknown
route, step, tier or backend name, or a file of the wrong shape, raises at import
rather than falling back to anything. One value is taken as written: a step
exception that is not a tier name is sent to the provider as a model id.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

ROUTE_FILE = Path(__file__).resolve().parent.parent / "model_routes.toml"
DEFAULT_ROUTE = "openai-direct"
EMBEDDING_BACKENDS = ("openai", "cohere")
SEARCH_QUERIES_BACKENDS = ("openai", "claude")
API_KEY_ENVS = ("OPENAI_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")
ROUTE_ENV = "POLICY_ATLAS_MODEL_ROUTE"
OVERLAY_ENV = "POLICY_ATLAS_MODEL_ROUTE_FILE"

#: Per-step model variables retired by task 053. They used to override one
#: step's model each; the route file is now the only mechanism. Setting one is
#: logged once and ignored, never silently honoured.
RETIRED_ENV = (
    "POLICY_ATLAS_AGENT_MODEL",
    "POLICY_ATLAS_AGENT_TRIAGE_MODEL",
    "POLICY_ATLAS_CHAT_MODEL",
    "POLICY_ATLAS_SYNTHESIS_MODEL",
    "POLICY_ATLAS_CASE_STUDIES_MODEL",
    "POLICY_ATLAS_MRS_NOTE_MODEL",
    "POLICY_ATLAS_FULL_REPORT_INTRO_MODEL",
    "POLICY_ATLAS_RELEVANCE_MODEL",
    # Options scoping (tasks 044 to 046), retired when that branch merged into 053.
    "POLICY_ATLAS_TASK_AGENT_MODEL",
    "POLICY_ATLAS_TASK_AGENT_SCOPING_MODEL",
    "POLICY_ATLAS_LONGLIST_JUDGMENT_MODEL",
    "POLICY_ATLAS_LONGLIST_ASSIGNMENT_MODEL",
)


@dataclass(frozen=True)
class Embeddings:
    """The embedding section of a route."""

    backend: str
    model: str
    profile: str


@dataclass(frozen=True)
class SearchQueries:
    """The search-queries section of a route: which backend, and its model if Claude."""

    backend: str
    model: str | None


@dataclass(frozen=True)
class Route:
    """One resolved route: everything the code needs to pick a model.

    Args:
        name: The route name, as selected.
        openai_base_url: Where the OpenAI client sends requests.
        api_key_env: The environment variable that holds this route's API key.
            The OpenAI client and the live-mode switch read it; ``boto3`` always
            reads ``AWS_BEARER_TOKEN_BEDROCK`` on its own.
        tiers: Tier name to model id.
        steps: Step name to default tier (from the committed ``[steps]`` table).
        step_exceptions: Step name to a tier name or a model id, for this route.
        reasoning_effort: Model id to the ``reasoning_effort`` value it needs.
        embeddings: The embedding section.
        search_queries: The search-queries section.
    """

    name: str
    openai_base_url: str
    api_key_env: str
    tiers: Mapping[str, str]
    steps: Mapping[str, str]
    step_exceptions: Mapping[str, str]
    reasoning_effort: Mapping[str, str]
    embeddings: Embeddings
    search_queries: SearchQueries

    def model_for(self, step: str) -> str:
        """Return the model id for a step on this route.

        Args:
            step: A step name from the ``[steps]`` table.

        Returns:
            The model id to send to the provider.

        A step exception on this route wins over the step's default tier. Its value
        is a tier name when it matches one, else it is sent as a model id as written.

        Raises:
            RuntimeError: If the step is not in the ``[steps]`` table.
        """
        if step not in self.steps:
            raise RuntimeError(f"{ROUTE_FILE}: step {step!r} is not in the [steps] table")
        value = self.step_exceptions.get(step, self.steps[step])
        return self.tiers.get(value, value)

    def reasoning_effort_for(self, model: str) -> str | None:
        """Return the ``reasoning_effort`` a model needs on this route, or ``None``."""
        return self.reasoning_effort.get(model)


def _require(table: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise RuntimeError(f"{where}: missing key {key!r}")
    return table[key]


def _table(table: Mapping[str, Any], key: str, where: str) -> Mapping[str, Any]:
    value = _require(table, key, where)
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{where}: {key!r} must be a table, not {type(value).__name__}")
    return value


def _choice(table: Mapping[str, Any], key: str, where: str, allowed: tuple[str, ...]) -> str:
    value = _require(table, key, where)
    if value not in allowed:
        raise RuntimeError(f"{where}: {key!r} is {value!r}, not one of {list(allowed)}")
    return str(value)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise RuntimeError(f"route file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"{path}: not valid TOML: {exc}") from exc


def load_route(
    path: Path,
    name: str,
    environ: Mapping[str, str],
    overlay_path: Path | None = None,
) -> Route:
    """Read the route file (and an optional overlay) and resolve one route.

    Pure: reads only the files and the mapping it is given, so tests can pass
    fixture files and a fake environment.

    Args:
        path: The committed route file.
        name: The route to resolve.
        environ: The process environment (only read for the retired-variable warning).
        overlay_path: An optional second file whose ``[routes.*]`` replace or add
            routes by name. It may not carry a ``[steps]`` table.

    Returns:
        The resolved route.

    Raises:
        RuntimeError: On a missing or malformed file, a section that is not a
            table, an unknown route, a route missing a section, a step default
            naming an undefined tier, a step exception naming an unknown step, a
            backend name the code does not implement, or an overlay that tries to
            change ``[steps]``.
    """
    data = _read_toml(path)
    steps: dict[str, str] = dict(_table(data, "steps", str(path)))
    routes: dict[str, Any] = dict(_table(data, "routes", str(path)))
    source = dict.fromkeys(routes, path)

    if overlay_path is not None:
        overlay = _read_toml(overlay_path)
        if "steps" in overlay:
            raise RuntimeError(f"{overlay_path}: an overlay may not change [steps]")
        overlay_routes = _table(overlay, "routes", str(overlay_path))
        routes.update(overlay_routes)
        source.update(dict.fromkeys(overlay_routes, overlay_path))

    if name not in routes:
        raise RuntimeError(f"{path}: route {name!r} is not defined (known: {sorted(routes)})")
    where = f"{source[name]} [routes.{name}]"
    table = _table(routes, name, f"{source[name]} [routes]")
    tiers = dict(_table(table, "text", where))
    for step, tier in steps.items():
        if tier not in tiers:
            raise RuntimeError(f"{where}: step {step!r} needs tier {tier!r}, not defined")
    exceptions = dict(_table(table, "steps", where)) if "steps" in table else {}
    for step in exceptions:
        if step not in steps:
            raise RuntimeError(f"{where}.steps: unknown step {step!r}")
    embeddings_table = _table(table, "embeddings", where)
    search_table = _table(table, "search_queries", where)
    search_backend = _choice(
        search_table, "backend", f"{where}.search_queries", SEARCH_QUERIES_BACKENDS
    )
    if search_backend == "claude":
        _require(search_table, "model", f"{where}.search_queries")

    retired = sorted(key for key in RETIRED_ENV if environ.get(key))
    if retired:
        log.warning(
            "model_routes.retired_env_ignored",
            keys=retired,
            use_instead=str(path),
        )

    return Route(
        name=name,
        openai_base_url=_require(table, "openai_base_url", where),
        api_key_env=_choice(table, "api_key_env", where, API_KEY_ENVS),
        tiers=tiers,
        steps=steps,
        step_exceptions=exceptions,
        reasoning_effort=dict(table.get("knobs", {}).get("reasoning_effort", {})),
        embeddings=Embeddings(
            backend=_choice(embeddings_table, "backend", f"{where}.embeddings", EMBEDDING_BACKENDS),
            model=_require(embeddings_table, "model", f"{where}.embeddings"),
            profile=_require(embeddings_table, "profile", f"{where}.embeddings"),
        ),
        search_queries=SearchQueries(
            backend=search_backend,
            model=search_table.get("model"),
        ),
    )


@cache
def route() -> Route:
    """The route selected for this process, read once from the committed file."""
    overlay = os.environ.get(OVERLAY_ENV)
    return load_route(
        ROUTE_FILE,
        os.environ.get(ROUTE_ENV) or DEFAULT_ROUTE,
        os.environ,
        overlay_path=Path(overlay) if overlay else None,
    )


def live_api_key() -> str | None:
    """The API key for the selected route, or ``None`` when it is not set.

    Reads the variable the route names (``api_key_env``), so a Bedrock route
    never picks up the OpenAI key by accident and the two can coexist.
    """
    return os.environ.get(route().api_key_env)
