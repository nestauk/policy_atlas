#!/usr/bin/env python3
"""Per-step client timeouts for the Bedrock route, derived from Langfuse (task 057, P1).

What this answers
-----------------
"How long should we wait for each kind of model call before giving up and trying
again?" Today every model call site waits a fixed 30, 60 or 120 seconds (the
``timeout=`` its OpenAI client is built with). A call that hangs at the provider
holds the whole run for that long. Task 057 sets a timeout per *route step* (one
named model call site in ``backend/src/policy_atlas/model_routes.toml``) from what
healthy calls of that step actually took.

Method (plan decision P1)
-------------------------
1. Read every GENERATION observation (one per model call) that Langfuse (our
   self-hosted tracing tool) recorded since ``--since`` (default 2026-11-02, the
   switch to GPT-6). Keep only Bedrock calls: the model name starts with
   ``global.openai.``, ``eu.`` or ``cohere`` (Amazon Bedrock's names for the
   models). Langfuse's 9999-dated duplicate rows are dropped.
2. Map each observation to its route step with :data:`SITES` (built from the code;
   names with a numeric suffix such as ``search_queries_v2_openalex:3`` match by
   prefix).
3. A *healthy* call is one with no ``ERROR`` level whose duration (end minus start)
   is shorter than its site's current client timeout. This is the historical
   stand-in for "a first attempt that succeeded": a call that timed out and was
   retried inside the SDK shows up as one observation longer than the timeout.
4. Per step: ``n`` healthy calls and the 99th percentile (p99) of their
   durations, by linear interpolation between the two nearest values
   (``statistics.quantiles(..., n=100, method="inclusive")``, the same as
   numpy's default). Proposed ``timeout_s``: twice the p99, rounded up to a whole
   multiple of ``--round-to`` seconds (default 1, so plain ``ceil``), then raised to
   at least ``--floor`` seconds (default 5), so
   ``max(floor, ceil(2 x p99 / round_to) x round_to)``. A step gets a proposal only
   when it has at least ``--min-n`` healthy calls (default 100); otherwise it keeps
   today's value. Streamed chat is exempt (plan P1) and keeps its value. (Task 057
   review, contract verifier 5: options described here.)

Outputs (``--format``)
----------------------
- ``md`` (default): the verification table (step, n healthy, p99 s, proposed
  timeout_s, today's timeout_s, decision) and any observation names the site
  table does not know.
- ``toml``: the lines to paste under ``[routes.bedrock.steps.<step>]`` for the
  "set" rows, then today's value for every step as comments (the base values
  for ``[steps]``).
- ``json``: the same numbers.

``--print-sites`` prints the site table itself (observation name, step, today's
timeout, module) and exits; no Langfuse access is needed.

Usage
-----
From the repository root (keys come from ``backend/.env``; the script never
prints or saves them)::

    set -a; source backend/.env; set +a
    python3 scripts/step_timeouts.py --cache /tmp/obs.json          # fetch, save, report
    python3 scripts/step_timeouts.py --from-cache /tmp/obs.json --format toml
    python3 scripts/step_timeouts.py --print-sites

The cache holds only id, trace id, name, type, model, level, start and end time
per observation: no prompts or answers.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import sys
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parents[1]
ROUTE_FILE = REPO / "backend" / "src" / "policy_atlas" / "model_routes.toml"
DEFAULT_SINCE = "2026-11-02"
MIN_N = 100
FLOOR_S = 5
P99_MULTIPLIER = 2
BEDROCK_PREFIXES = ("global.openai.", "eu.", "cohere")
CACHE_FIELDS = ("id", "traceId", "name", "type", "model", "level", "startTime", "endTime")


class Site(NamedTuple):
    """One model call site: its Langfuse observation name, route step and timeout today.

    Attributes:
        name: Observation name; also matches ``name:<suffix>`` (numbered calls).
        step: The ``[steps]`` name in ``model_routes.toml``.
        timeout_s: The ``timeout=`` its OpenAI client is built with today.
        module: Where the call lives (under ``backend/src/policy_atlas``).
        exempt: True for streamed chat, which keeps its timeout (plan P1).
    """

    name: str
    step: str
    timeout_s: int
    module: str
    exempt: bool = False


# Module paths for the site table (under backend/src/policy_atlas).
CLASSIFY = "evidence_search/assess/classification_backend.py"
SCREEN = "evidence_search/assess/screening_backend.py"
RANKING = "evidence_search/corpus/ranking.py"
THEMES = "evidence_search/corpus/theme_grouping.py"
GROUP = "evidence_search/group/group_clustering.py"
EXTRACT = "evidence_search/extract/extraction_backend.py"
VETTER = "evidence_search/extract/finding_vetter.py"
ANNOTATOR = "evidence_search/extract/relevance_annotator.py"
SEARCH = "evidence_search/sourcing/search_generation.py"
SYNTH = "evidence_search/synthesis/synthesis_backend.py"
JUDGE = "evidence_search/synthesis/grounding_judge.py"
CHAT = "runtime/chat_backend_openai.py"
AGENT = "runtime/agent_backend.py"
TASK_AGENT = "runtime/task_agent.py"
TASK_AGENT_SCOPING = "runtime/task_agent_scoping.py"
SCOPING = "options_scoping/scoping_backend.py"

# Every traced model call site, read from the code on 2026-11-03 (task 057 Phase 0).
# Module paths are under backend/src/policy_atlas; the timeout is the one passed to
# resolve_openai_client for the client the call uses. Phase 1 reuses this table.
SITES: tuple[Site, ...] = (
    # --- Evidence search: assess ---
    Site("classify:document", "classify_document", 60, CLASSIFY),
    Site("screen:abstract", "screen_abstract", 60, SCREEN),
    Site("screen:full", "screen_full", 60, SCREEN),
    # --- Evidence search: corpus, group ---
    Site("select:rerank", "select_rerank", 60, RANKING),
    # characterise: client in corpus/theme_grouping.py, traced by core/tracing.py
    # (TracedThemeGroupingBackend)
    Site("characterise:discover", "characterise_discover", 60, THEMES),
    Site("characterise:assign", "characterise_assign", 60, THEMES),
    Site("group:discover", "group_discover", 120, GROUP),
    Site("group:assign", "group_assign", 120, GROUP),
    # --- Evidence search: extract ---
    Site("extract:iof_findings", "extract_iof_findings", 120, EXTRACT),
    Site("extract:icf_findings", "extract_icf_findings", 120, EXTRACT),
    Site("extract:interventions", "extract_interventions", 60, EXTRACT),
    Site("extract:vet_iof_findings", "extract_vet_iof_findings", 120, VETTER),
    Site("extract:vet_icf_findings", "extract_vet_icf_findings", 120, VETTER),
    Site("extract:annotate_relevance", "extract_annotate_relevance", 60, ANNOTATOR),
    # --- Evidence search: search (one client, sourcing/search_generation.py) ---
    # search:generate_queries is also the name of the Claude (boto3) variant, used only
    # on the unused bedrock-claude route; the bedrock route uses the OpenAI client.
    Site("search:generate_queries", "search_generate_queries", 60, SEARCH),
    Site("search:reformulate", "search_reformulate", 60, SEARCH),
    Site("search:suggest", "search_suggest", 60, SEARCH),
    Site("search_queries_v2_openalex", "search_queries_v2_openalex", 60, SEARCH),
    Site("search_queries_v2_overton", "search_queries_v2_overton", 60, SEARCH),
    Site("search_reformulate_v2_openalex", "search_reformulate_v2_openalex", 60, SEARCH),
    Site("search_reformulate_v2_overton", "search_reformulate_v2_overton", 60, SEARCH),
    # --- Evidence search: synthesise (shared 120 s client, synthesis/synthesis_backend.py) ---
    Site("synthesise:propose_sections", "synthesise_propose_sections", 120, SYNTH),
    Site("synthesise:write_block_summary", "synthesise_write_block_summary", 120, SYNTH),
    Site("synthesise:write_artefact_summary", "synthesise_write_artefact_summary", 120, SYNTH),
    Site("synthesise:judge_summary", "synthesise_judge_summary", 120, SYNTH),
    Site("synthesise:section_turn", "synthesise_section_turn", 120, SYNTH),
    # the claim repair shares the section-turn step (route file comment, D10)
    Site("synthesise:repair_claims", "synthesise_section_turn", 120, SYNTH),
    # the streamed final turn (task 058, D1): one generation, no retry loop
    Site("synthesise:section_emit", "synthesise_section_emit", 120, SYNTH),
    Site("synthesise:write_key_findings", "synthesise_write_key_findings", 120, SYNTH),
    Site("synthesise:write_case_studies", "synthesise_write_case_studies", 120, SYNTH),
    # source note and intro build their own 30 s client (max_retries=1)
    Site("synthesise:write_source_note", "synthesise_write_source_note", 30, SYNTH),
    Site("synthesise:write_intro", "synthesise_write_intro", 30, SYNTH),
    Site("judge:grounding", "judge_grounding", 120, JUDGE),
    # --- Conversation and agents ---
    # chat: streamed (runtime/chat_backend_openai.py client, 120 s); the observation is
    # opened in api/answer_core.py. Exempt from the new timeouts (plan P1).
    Site("chat:call", "chat", 120, CHAT, exempt=True),
    Site("agent:route", "agent_route", 60, AGENT),
    Site("agent:triage", "agent_triage", 60, AGENT),
    Site("agent:decide", "agent_decide", 60, AGENT),
    Site("agent:gate_sort", "agent_gate_sort", 60, AGENT),
    Site("agent:longlist_sort", "agent_longlist_sort", 60, AGENT),
    Site("agent:option_design", "agent_option_design", 60, AGENT),
    Site("agent:suggest", "agent_suggest", 60, AGENT),
    # round 14: the two title calls (runtime/agent_backend.py write_title)
    Site("task_agent:title", "task_title", 20, AGENT),
    Site("chat:title", "chat_title", 20, AGENT),
    Site("task_agent:turn", "task_agent_turn", 60, TASK_AGENT),
    # the scoping profile runs on the same OpenAITaskAgentBackend client (runtime/task_agent.py)
    Site("task_agent_scoping:turn", "task_agent_scoping_turn", 60, TASK_AGENT_SCOPING),
    # --- Options scoping (one 60 s client; step = name with ":" as "_") ---
    Site("longlist:discover", "longlist_discover", 60, SCOPING),
    Site("longlist:assign", "longlist_assign", 60, SCOPING),
    Site("longlist:themes", "longlist_themes", 60, SCOPING),
    Site("longlist:assign_themes", "longlist_assign_themes", 60, SCOPING),
    Site("longlist:type", "longlist_type", 60, SCOPING),
    Site("longlist:constrain", "longlist_constrain", 60, SCOPING),
    Site("longlist:distinct", "longlist_distinct", 60, SCOPING),
    Site("longlist:authority", "longlist_authority", 60, SCOPING),
    Site("longlist:shortlist", "longlist_shortlist", 60, SCOPING),
    # round 14: the shortlist note's one writer (scoping_backend.py shortlist_note)
    Site("shortlist:note", "shortlist_note", 30, SCOPING),
    Site("option_profile:line", "option_profile_line", 60, SCOPING),
    Site("option_profile:potential_impact", "option_profile_potential_impact", 60, SCOPING),
    Site("option_profile:ambition", "option_profile_ambition", 60, SCOPING),
    Site("option_profile:setting", "option_profile_setting", 60, SCOPING),
    Site("option_profile:fold", "option_profile_fold", 60, SCOPING),
    Site("option_profile:place_sentences", "option_profile_place_sentences", 60, SCOPING),
)


# --- Pure computation -------------------------------------------------------------


def route_steps(route_file: Path = ROUTE_FILE) -> list[str]:
    """Return the step names of the route file's ``[steps]`` table, in file order."""
    with route_file.open("rb") as fh:
        return list(tomllib.load(fh)["steps"])


def site_for(name: str | None, sites: tuple[Site, ...] = SITES) -> Site | None:
    """Return the site whose name equals ``name`` or prefixes it before a ``:``."""
    if not name:
        return None
    for site in sites:
        if name == site.name or name.startswith(site.name + ":"):
            return site
    return None


def is_bedrock(model: str | None) -> bool:
    """True when the model name is one of Amazon Bedrock's (see module doc)."""
    return bool(model) and str(model).startswith(BEDROCK_PREFIXES)


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def duration_s(obs: dict[str, Any]) -> float | None:
    """End minus start in seconds, or ``None`` when either time is missing."""
    start, end = obs.get("startTime"), obs.get("endTime")
    if not start or not end:
        return None
    return (_ts(end) - _ts(start)).total_seconds()


def p99(values: list[float]) -> float:
    """99th percentile by linear interpolation (numpy's default method)."""
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[98]


def today_by_step(sites: tuple[Site, ...] = SITES) -> dict[str, Site]:
    """One site per step (the first listed); sites sharing a step share a timeout."""
    out: dict[str, Site] = {}
    for site in sites:
        out.setdefault(site.step, site)
    return out


def derive_table(
    observations: list[dict[str, Any]],
    steps: list[str],
    sites: tuple[Site, ...] = SITES,
    *,
    min_n: int = MIN_N,
    floor_s: int = FLOOR_S,
    round_to: int = 1,
) -> dict[str, Any]:
    """Compute the per-step timeout table from observation dicts.

    Args:
        observations: Langfuse observations (``name``, ``type``, ``model``,
            ``level``, ``startTime``, ``endTime``).
        steps: Every route step, in the order to report them.
        sites: The observation-name to step table.

    Returns:
        ``{"rows": [...], "unmapped": {name: count}, "skipped": {...}}``. Each row
        has ``step``, ``n_healthy``, ``n_bedrock`` (all Bedrock calls of the step),
        ``p99_s``, ``proposed_timeout_s``, ``today_timeout_s`` and ``decision``
        (``set``, ``keep, n<100``, ``keep, exempt (streamed chat)`` or
        ``no traced generation``).
    """
    healthy: dict[str, list[float]] = {}
    total: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for obs in observations:
        if (obs.get("type") or "GENERATION") != "GENERATION":
            skipped["not a generation"] += 1
            continue
        if str(obs.get("startTime") or "").startswith("9999"):
            skipped["9999 duplicate row"] += 1
            continue
        if not is_bedrock(obs.get("model")):
            skipped["not bedrock"] += 1
            continue
        site = site_for(obs.get("name"), sites)
        if site is None:
            unmapped[str(obs.get("name"))] += 1
            continue
        total[site.step] += 1
        dur = duration_s(obs)
        if dur is None:
            skipped["no end time"] += 1
            continue
        if obs.get("level") == "ERROR" or dur >= site.timeout_s:
            continue
        healthy.setdefault(site.step, []).append(dur)
    by_step = today_by_step(sites)
    rows = []
    for step in steps:
        site = by_step.get(step)
        values = healthy.get(step, [])
        row: dict[str, Any] = {
            "step": step,
            "n_healthy": len(values),
            "n_bedrock": total[step],
            "p99_s": p99(values) if values else None,
            "proposed_timeout_s": None,
            "today_timeout_s": site.timeout_s if site else None,
        }
        if site is None:
            row["decision"] = "no traced generation"
        elif site.exempt:
            row["decision"] = "keep, exempt (streamed chat)"
        elif len(values) >= min_n:
            raw = P99_MULTIPLIER * row["p99_s"]
            row["proposed_timeout_s"] = max(floor_s, math.ceil(raw / round_to) * round_to)
            row["decision"] = "set"
        else:
            row["decision"] = f"keep, n<{min_n}"
        rows.append(row)
    return {
        "rows": rows,
        "unmapped": dict(unmapped),
        "skipped": dict(skipped),
        "min_n": min_n,
        "floor_s": floor_s,
    }


# --- Formatting -------------------------------------------------------------------


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def format_sites(sites: tuple[Site, ...] = SITES) -> str:
    """The site table as markdown (``--print-sites``)."""
    rows = [
        [
            f"`{s.name}`",
            s.step,
            str(s.timeout_s),
            s.module + (" (streamed, exempt)" if s.exempt else ""),
        ]
        for s in sites
    ]
    return _md_table(["observation name", "step", "today timeout s", "module"], rows) + "\n"


def format_markdown(table: dict[str, Any], since: str) -> str:
    """The verification table, then unmapped names and skipped-row counts."""
    rows = [
        [
            r["step"],
            str(r["n_healthy"]),
            "" if r["p99_s"] is None else f"{r['p99_s']:.1f}",
            "" if r["proposed_timeout_s"] is None else str(r["proposed_timeout_s"]),
            "" if r["today_timeout_s"] is None else str(r["today_timeout_s"]),
            r["decision"],
        ]
        for r in table["rows"]
    ]
    out = [
        f"### Per-step client timeouts, Bedrock generations since {since}\n",
        f"Healthy = no ERROR level and shorter than today's timeout. Proposed = "
        f"max({table.get('floor_s', FLOOR_S)}, ceil({P99_MULTIPLIER} x p99)), only when "
        f"n >= {table.get('min_n', MIN_N)}.\n",
        _md_table(
            ["step", "n healthy", "p99 s", "proposed timeout_s", "today timeout_s", "decision"],
            rows,
        ),
        "",
    ]
    if table["unmapped"]:
        out.append("Observation names not in the site table (not counted):\n")
        out += [f"- `{n}`: {c}" for n, c in sorted(table["unmapped"].items())]
        out.append("")
    if table["skipped"]:
        out.append(
            "Skipped rows: " + ", ".join(f"{k} {v}" for k, v in sorted(table["skipped"].items()))
        )
    return "\n".join(out) + "\n"


def format_toml(table: dict[str, Any]) -> str:
    """Route-file lines for the ``set`` rows, then today's base value per step."""
    out = ["# Bedrock overrides (task 057 P1): paste under model_routes.toml"]
    for r in table["rows"]:
        if r["decision"] == "set":
            out += [
                "",
                f"[routes.bedrock.steps.{r['step']}]",
                f"timeout_s = {r['proposed_timeout_s']}",
            ]
    out += ["", "# Today's per-site value, the base `timeout_s` for each [steps] entry:"]
    for r in table["rows"]:
        today = r["today_timeout_s"]
        out.append(f"# {r['step']} = {today if today is not None else '(no traced generation)'}")
    return "\n".join(out) + "\n"


# --- Fetching ---------------------------------------------------------------------


def _client() -> Any:
    spec = importlib.util.spec_from_file_location(
        "cost_per_run", REPO / "scripts" / "cost_per_run.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LangfuseClient.from_env()


def fetch_observations(since: str, until: str | None) -> list[dict[str, Any]]:
    """Fetch every GENERATION observation since ``since`` (timing fields only).

    Args:
        since: ISO date or timestamp (``fromStartTime``).
        until: Optional ISO date or timestamp (``toStartTime``).

    Returns:
        Observation dicts trimmed to :data:`CACHE_FIELDS`, 9999-dated rows dropped,
        de-duplicated by id.
    """
    client = _client()
    params: dict[str, Any] = {"type": "GENERATION", "fromStartTime": _iso(since), "limit": 100}
    if until:
        params["toStartTime"] = _iso(until)
    first = client.get("observations", {**params, "page": 1})
    pages = int(first["meta"].get("totalPages") or 1)
    print(
        f"fetching {first['meta'].get('totalItems')} observations, {pages} pages", file=sys.stderr
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        rest = list(
            pool.map(
                lambda p: client.get("observations", {**params, "page": p}), range(2, pages + 1)
            )
        )
    seen: dict[str, dict[str, Any]] = {}
    for data in [first, *rest]:
        for o in data["data"]:
            if str(o.get("startTime") or "").startswith("9999"):
                continue
            seen[o.get("id") or str(len(seen))] = {f: o.get(f) for f in CACHE_FIELDS}
    return list(seen.values())


def in_window(
    observations: list[dict[str, Any]], since: str, until: str | None
) -> list[dict[str, Any]]:
    """Keep observations that started at or after ``since`` and before ``until``."""
    lo = _ts(_iso(since))
    hi = _ts(_iso(until)) if until else None
    return [
        o
        for o in observations
        if o.get("startTime")
        and _ts(o["startTime"]) >= lo
        and (hi is None or _ts(o["startTime"]) < hi)
    ]


def _iso(value: str) -> str:
    return value if "T" in value else f"{value}T00:00:00Z"


# --- Command line -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Per-step client timeouts from Langfuse generation durations (task 057 P1)."
    )
    parser.add_argument("--since", default=DEFAULT_SINCE, help=f"default {DEFAULT_SINCE}")
    parser.add_argument("--until", help="optional end date or timestamp")
    parser.add_argument("--cache", help="save the fetched observations here (timing fields only)")
    parser.add_argument("--from-cache", help="read observations from a saved cache, no network")
    parser.add_argument("--format", choices=["md", "json", "toml"], default="md")
    parser.add_argument("--print-sites", action="store_true", help="print the site table and exit")
    parser.add_argument("--out", help="write to this file instead of stdout")
    parser.add_argument("--min-n", type=int, default=MIN_N, help=f"smallest healthy sample (default {MIN_N})")
    parser.add_argument("--floor", type=int, default=FLOOR_S, help=f"smallest timeout in seconds (default {FLOOR_S})")
    parser.add_argument("--round-to", type=int, default=1, help="round each timeout up to a multiple of this many seconds (default 1)")
    args = parser.parse_args(argv)
    if args.print_sites:
        text = format_sites()
    else:
        if args.from_cache:
            observations = json.loads(Path(args.from_cache).read_text(encoding="utf-8"))
            observations = in_window(observations, args.since, args.until)
        else:
            observations = fetch_observations(args.since, args.until)
            if args.cache:
                Path(args.cache).write_text(json.dumps(observations), encoding="utf-8")
        table = derive_table(
            observations, route_steps(), min_n=args.min_n, floor_s=args.floor, round_to=args.round_to
        )
        if args.format == "json":
            text = json.dumps({"since": args.since, **table}, indent=1) + "\n"
        elif args.format == "toml":
            text = format_toml(table)
        else:
            text = format_markdown(table, args.since)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
