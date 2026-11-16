"""Which AI model each step of the app uses, read from one committed file.

The file is ``model_routes.toml`` at the package root. It names every step once
(one step is one named model call site) with a default tier, a reasoning
effort and a timeout (how many seconds one request may take before it is cut
off), and for each named *route* says which model each tier is, plus the
embedding model, the search-queries backend and which environment variable
holds the route's API key (so one secret can hold both the OpenAI key and a
Bedrock key, and switching route never edits the secret). One environment
variable, ``POLICY_ATLAS_MODEL_ROUTE``, picks the route; unset means
``openai-direct``. An optional second file named by
``POLICY_ATLAS_MODEL_ROUTE_FILE`` can replace or add routes by name without
touching the committed file (for evaluations).

Design: task 053 contract D3 and ADR 0041; task 056 contract D4 and D9 and
ADR 0042 (one step per call site, reasoning effort per step); task 057
contract D12 and ADR 0043 (a timeout per step). Every lookup fails loud: an
unknown route, step, tier, effort or backend name, a stray key, a missing or
non-positive timeout, or a file of the wrong shape, raises at import rather
than falling back to anything. One value is taken as written: a step
exception's model that is not a tier name is sent to the provider as a model id.
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
#: The ``reasoning_effort`` values the providers accept. ``none`` means the model
#: answers without thinking first; Sol-class models refuse it.
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh")
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
class Step:
    """One step's defaults from the committed ``[steps]`` table.

    Args:
        tier: The tier name the step follows unless a route says otherwise.
        reasoning_effort: The ``reasoning_effort`` the step sends unless a
            route says otherwise.
        timeout_s: How many seconds one request of this step may take before
            the client gives up on it, unless a route says otherwise. Applied
            per request (task 057, D12).
        first_content_s: For a streamed step only: how many seconds the app
            waits for the first words of the answer before it gives up on the
            stream and falls back to the ordinary call (task 054's 058
            alignment, A11). ``None`` when the step sets no such limit.
    """

    tier: str
    reasoning_effort: str
    timeout_s: float
    first_content_s: float | None = None


@dataclass(frozen=True)
class StepException:
    """One route's override for one step (``[routes.<name>.steps]``).

    Args:
        model: A tier name or a model id, or ``None`` to keep the step's tier.
        reasoning_effort: An effort value, or ``None`` to keep the step's effort.
        timeout_s: A request timeout in seconds, or ``None`` to keep the step's.
        first_content_s: A time-to-first-content limit in seconds, or ``None``
            to keep the step's.
    """

    model: str | None
    reasoning_effort: str | None
    timeout_s: float | None = None
    first_content_s: float | None = None


#: Embedding requests the stage may keep in flight at most (task 057, D6), when a
#: route's ``[routes.<name>.embeddings]`` table does not set ``pool_cap``.
DEFAULT_EMBEDDING_POOL_CAP = 8


@dataclass(frozen=True)
class Embeddings:
    """The embedding section of a route.

    Attributes:
        backend: ``openai`` or ``cohere``.
        model: The embedding model id.
        profile: The profile name stamped on each stored vector.
        pool_cap: The most embedding requests kept in flight at once (task 057,
            D6); the adaptive pool climbs towards it while the provider does not
            throttle. ``pool_cap`` in the route file, default 8.
    """

    backend: str
    model: str
    profile: str
    pool_cap: int = DEFAULT_EMBEDDING_POOL_CAP


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
        steps: Step name to its defaults (from the committed ``[steps]`` table).
        step_exceptions: Step name to this route's override.
        embeddings: The embedding section.
        search_queries: The search-queries section.
    """

    name: str
    openai_base_url: str
    api_key_env: str
    tiers: Mapping[str, str]
    steps: Mapping[str, Step]
    step_exceptions: Mapping[str, StepException]
    embeddings: Embeddings
    search_queries: SearchQueries

    def _step(self, step: str) -> Step:
        if step not in self.steps:
            raise RuntimeError(f"{ROUTE_FILE}: step {step!r} is not in the [steps] table")
        return self.steps[step]

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
        default = self._step(step)
        exception = self.step_exceptions.get(step)
        value = exception.model if exception is not None and exception.model else default.tier
        return self.tiers.get(value, value)

    def effort_for(self, step: str) -> str:
        """Return the ``reasoning_effort`` a step sends on this route.

        Args:
            step: A step name from the ``[steps]`` table.

        Returns:
            One of :data:`REASONING_EFFORTS`; never ``None`` (every step says
            what it sends, task 056 D4).

        Raises:
            RuntimeError: If the step is not in the ``[steps]`` table.
        """
        default = self._step(step)
        exception = self.step_exceptions.get(step)
        if exception is not None and exception.reasoning_effort:
            return exception.reasoning_effort
        return default.reasoning_effort

    def timeout_for(self, step: str) -> float:
        """Return how many seconds one request of a step may take on this route.

        Args:
            step: A step name from the ``[steps]`` table.

        Returns:
            The route's override for the step when it sets ``timeout_s``, else
            the step's own ``timeout_s`` from ``[steps]``. Always above zero.

        Raises:
            RuntimeError: If the step is not in the ``[steps]`` table.
        """
        default = self._step(step)
        exception = self.step_exceptions.get(step)
        if exception is not None and exception.timeout_s is not None:
            return exception.timeout_s
        return default.timeout_s

    def first_content_for(self, step: str) -> float | None:
        """Return how long a streamed step waits for its first words on this route.

        In plain terms: a streamed call that has sent nothing readable after
        this many seconds is abandoned, and the step makes its ordinary
        (non-streamed) call instead. The step's ``timeout_s`` still bounds the
        wait between pieces once words arrive.

        Args:
            step: A step name from the ``[steps]`` table.

        Returns:
            The route's override for the step when it sets ``first_content_s``,
            else the step's own ``first_content_s``, else ``None`` (no limit).

        Raises:
            RuntimeError: If the step is not in the ``[steps]`` table.
        """
        default = self._step(step)
        exception = self.step_exceptions.get(step)
        if exception is not None and exception.first_content_s is not None:
            return exception.first_content_s
        return default.first_content_s


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


def _timeout(value: Any, where: str, key: str = "timeout_s") -> float:
    """Check a ``timeout_s`` (or ``first_content_s``) value: a number of seconds above zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RuntimeError(
            f"{where}: {key!r} must be a number of seconds, not {type(value).__name__}"
        )
    if not value > 0:
        raise RuntimeError(f"{where}: {key!r} is {value!r}; it must be above zero")
    return float(value)


def _first_content(table: Mapping[str, Any], where: str) -> float | None:
    """Read an optional ``first_content_s``: ``None`` when absent."""
    value = table.get("first_content_s")
    return None if value is None else _timeout(value, where, "first_content_s")


def _pool_cap(table: Mapping[str, Any], where: str) -> int:
    """Check ``pool_cap``: a whole number of requests, at least 1 (default 8)."""
    value = table.get("pool_cap", DEFAULT_EMBEDDING_POOL_CAP)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(
            f"{where}: 'pool_cap' must be a whole number, not {type(value).__name__}"
        )
    if value < 1:
        raise RuntimeError(f"{where}: 'pool_cap' is {value!r}; it must be at least 1")
    return value


def _no_stray_keys(table: Mapping[str, Any], allowed: tuple[str, ...], where: str) -> None:
    stray = sorted(set(table) - set(allowed))
    if stray:
        raise RuntimeError(f"{where}: unknown key(s) {stray}; allowed: {list(allowed)}")


def _parse_steps(raw: Mapping[str, Any], where: str) -> dict[str, Step]:
    steps: dict[str, Step] = {}
    for name, value in raw.items():
        if not isinstance(value, Mapping):
            raise RuntimeError(
                f"{where}: step {name!r} must be a table with tier, reasoning_effort "
                f"and timeout_s, not {type(value).__name__}"
            )
        here = f"{where} step {name!r}"
        _no_stray_keys(
            value, ("tier", "reasoning_effort", "timeout_s", "first_content_s"), here
        )
        steps[name] = Step(
            tier=str(_require(value, "tier", here)),
            reasoning_effort=_choice(value, "reasoning_effort", here, REASONING_EFFORTS),
            timeout_s=_timeout(_require(value, "timeout_s", here), here),
            first_content_s=_first_content(value, here),
        )
    return steps


def _parse_exception(name: str, value: Any, where: str) -> StepException:
    if isinstance(value, str):
        if not value:
            raise RuntimeError(f"{where}: step {name!r} names an empty model; remove it")
        return StepException(model=value, reasoning_effort=None)
    if not isinstance(value, Mapping):
        raise RuntimeError(
            f"{where}: step {name!r} must be a string or a table, not {type(value).__name__}"
        )
    here = f"{where} step {name!r}"
    _no_stray_keys(
        value, ("model", "reasoning_effort", "timeout_s", "first_content_s"), here
    )
    if not value:
        raise RuntimeError(f"{here}: an empty table changes nothing; remove it")
    effort = value.get("reasoning_effort")
    if effort is not None and effort not in REASONING_EFFORTS:
        raise RuntimeError(
            f"{here}: 'reasoning_effort' is {effort!r}, not one of {list(REASONING_EFFORTS)}"
        )
    model = value.get("model")
    if model is not None and not model:
        raise RuntimeError(f"{here}: 'model' is empty; name a tier or a model id, or drop the key")
    timeout = value.get("timeout_s")
    return StepException(
        model=str(model) if model is not None else None,
        reasoning_effort=str(effort) if effort is not None else None,
        timeout_s=_timeout(timeout, here) if timeout is not None else None,
        first_content_s=_first_content(value, here),
    )


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
            table, an unknown route, a route missing a section, a step without a
            tier, effort or timeout, a timeout that is not a number above zero,
            an effort value the providers do not accept, a step
            default naming an undefined tier, a step exception naming an unknown
            step or carrying a stray key, a leftover ``knobs`` table (retired by
            task 056), a backend name the code does not implement, or an overlay
            that tries to change ``[steps]``.
    """
    data = _read_toml(path)
    steps = _parse_steps(_table(data, "steps", str(path)), f"{path} [steps]")
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
    if "knobs" in table:
        raise RuntimeError(
            f"{where}: 'knobs' was retired by task 056; reasoning effort lives per step "
            "in [steps] and [routes.<name>.steps]"
        )
    tiers = dict(_table(table, "text", where))
    for step_name, step in steps.items():
        if step.tier not in tiers:
            raise RuntimeError(f"{where}: step {step_name!r} needs tier {step.tier!r}, not defined")
    raw_exceptions = dict(_table(table, "steps", where)) if "steps" in table else {}
    exceptions: dict[str, StepException] = {}
    for step_name, value in raw_exceptions.items():
        if step_name not in steps:
            raise RuntimeError(f"{where}.steps: unknown step {step_name!r}")
        exceptions[step_name] = _parse_exception(step_name, value, f"{where}.steps")
    embeddings_table = _table(table, "embeddings", where)
    _no_stray_keys(
        embeddings_table, ("backend", "model", "profile", "pool_cap"), f"{where}.embeddings"
    )
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
        embeddings=Embeddings(
            backend=_choice(embeddings_table, "backend", f"{where}.embeddings", EMBEDDING_BACKENDS),
            model=_require(embeddings_table, "model", f"{where}.embeddings"),
            profile=_require(embeddings_table, "profile", f"{where}.embeddings"),
            pool_cap=_pool_cap(embeddings_table, f"{where}.embeddings"),
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
