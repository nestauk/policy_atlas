#!/usr/bin/env python3
"""Cost of one Policy Atlas run (one Langfuse session), by stage and by call name.

What this answers
-----------------
"How many dollars did this run spend on model calls, and where?" Every run of
Policy Atlas is recorded in Langfuse (our self-hosted tracing tool) as one
*session*: a group of *traces* (one per stage of the run, such as
``run:classify`` or ``run:synthesise``), each holding *observations* (one per
model call, with the model name and the token counts the provider reported).

The script does not trust the dollar figure Langfuse stores, because that
depends on which price rows existed in Langfuse on the day the call was made.
It recomputes the cost from the token counts and the list prices in
``PRICES`` below, so two runs months apart are priced the same way.

Token buckets (Langfuse already nets them, so each token is in exactly one):

- ``input``: prompt tokens read at the full input price.
- ``input_cached_tokens``: prompt tokens served from the provider's prompt
  cache (a "cache read"), at the cheaper cached price.
- ``input_cache_write_tokens``: prompt tokens written into the cache on a miss
  (a "cache write"), charged at 1.25 x the input price.
- ``output``: answer tokens, at the output price.
- ``output_reasoning_tokens``: the model's hidden "thinking" tokens, charged
  at the output price.

Runs recorded before task 056 have only input / cached / output / total.

Usage
-----
Set the Langfuse address and keys in your shell first (the script never reads
``.env`` itself), for example from the repository root::

    set -a; source backend/.env; set +a
    python3 scripts/cost_per_run.py 0e8f8431 7c930ede
    python3 scripts/cost_per_run.py 0e8f8431 --json
    python3 scripts/cost_per_run.py 0e8f8431 --save-fixture /tmp/run.json
    python3 scripts/cost_per_run.py 0e8f8431 --fixture /tmp/run.json

A session id may be the first few characters of the full id (as Langfuse
shows it). Two totals are printed per session: the **session total** (every
trace, including the Task Agent's planning turns and other helper traces) and
the **run total** (only the ``run:*`` stage traces). The run total is the
definition the 2026-10-30 cost baseline used, so it is the one to compare with
the task 056 contract's § Goal table.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# --- Prices ---------------------------------------------------------------
# US dollars per MILLION tokens: (input, cached read, output). Read on
# 2026-10-27 from OpenAI's pricing page and Langfuse's default price file
# (worker/src/constants/default-model-prices.json at commit 0c531be); the
# Bedrock route charges the same first-party rates. Embedding models are
# input-only. Cache WRITE = CACHE_WRITE_MULTIPLIER x input; reasoning = output.
PRICES_READ_ON = "2026-10-27"
PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
    "gpt-5.6-sol": (4.00, 0.40, 20.00),
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.5": (5.00, 0.50, 30.00),
    "text-embedding-3-small": (0.02, 0.0, 0.0),
    "eu.cohere.embed-v4:0": (0.12, 0.0, 0.0),
}
INPUT_ONLY_MODELS = frozenset({"text-embedding-3-small", "eu.cohere.embed-v4:0"})
CACHE_WRITE_MULTIPLIER = 1.25
MODEL_PREFIX = "global.openai."  # Bedrock's name for the same OpenAI models

BUCKETS = ("input", "cached", "cache_write", "output", "reasoning")
USAGE_KEYS = {
    "input": "input",
    "cached": "input_cached_tokens",
    "cache_write": "input_cache_write_tokens",
    "output": "output",
    "reasoning": "output_reasoning_tokens",
}
KEPT_TYPES = frozenset({"GENERATION", "EMBEDDING"})
TRACE_FIELDS = ("id", "name", "timestamp", "sessionId")
OBSERVATION_FIELDS = (
    "id",
    "traceId",
    "name",
    "type",
    "model",
    "startTime",
    "usageDetails",
)
DEFAULT_FROM = "2026-10-01"
PAGE_LIMIT = 100
_UUID_SUFFIX = re.compile(r":[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# --- Fetching -------------------------------------------------------------


class LangfuseClient:
    """Minimal read-only client for the Langfuse public API (version 1 lists).

    Args:
        host: Langfuse base address, e.g. ``https://langfuse.example``.
        public_key: Project public key (HTTP basic-auth user name).
        secret_key: Project secret key (HTTP basic-auth password).
        timeout: Seconds to wait for one HTTP response.
    """

    def __init__(self, host: str, public_key: str, secret_key: str, timeout: float = 180):
        self.host = host.rstrip("/")
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self._auth = f"Basic {token}"
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> LangfuseClient:
        """Build a client from ``LANGFUSE_HOST``/``_PUBLIC_KEY``/``_SECRET_KEY``.

        Raises:
            SystemExit: If any of the three variables is missing.
        """
        names = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            raise SystemExit(
                f"missing environment variable(s): {', '.join(missing)} "
                "(try: set -a; source backend/.env; set +a)"
            )
        host, public_key, secret_key = (os.environ[n] for n in names)
        return cls(host, public_key, secret_key)

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET ``/api/public/<path>`` and return the decoded JSON, retrying twice.

        Raises:
            urllib.error.URLError: When the third attempt still fails.
        """
        url = f"{self.host}/api/public/{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"Authorization": self._auth})
        last: Exception | None = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)  # type: ignore[no-any-return]
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise
                last = exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
        assert last is not None
        raise last

    def pages(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return every row of a paged list, following ``meta.totalPages``."""
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get(path, {**params, "limit": PAGE_LIMIT, "page": page})
            rows.extend(data["data"])
            if page >= int(data["meta"].get("totalPages") or 1):
                return rows
            page += 1


def _trim(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Keep only the public-safe fields (no prompts, answers or metadata)."""
    return {f: row.get(f) for f in fields}


def _is_placeholder(timestamp: str | None) -> bool:
    """True for Langfuse's 9999-dated duplicate rows, which are skipped."""
    return (timestamp or "").startswith("9999")


def fetch_sessions(
    client: LangfuseClient, wanted: list[str], from_timestamp: str
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Fetch the traces and model-call observations of each wanted session.

    Args:
        client: Langfuse client.
        wanted: Full session ids or prefixes.
        from_timestamp: Earliest trace date to list (``YYYY-MM-DD`` or ISO).

    Returns:
        ``{full_session_id: {"traces": [...], "observations": [...]}}`` with
        only the public-safe fields kept.
    """
    if len(from_timestamp) == 10:
        from_timestamp += "T00:00:00Z"
    traces = [
        _trim(t, TRACE_FIELDS)
        for t in client.pages("traces", {"fromTimestamp": from_timestamp})
        if t.get("sessionId") and not _is_placeholder(t.get("timestamp"))
    ]
    known = sorted({t["sessionId"] for t in traces})
    resolved = {w: resolve_session_id(w, known) for w in wanted}
    sessions: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for full in dict.fromkeys(resolved.values()):
        own = sorted((t for t in traces if t["sessionId"] == full), key=_trace_key)
        with ThreadPoolExecutor(max_workers=8) as pool:
            per_trace = pool.map(lambda t: client.pages("observations", {"traceId": t["id"]}), own)
            observations = [
                _trim(o, OBSERVATION_FIELDS)
                for rows in per_trace
                for o in rows
                if o.get("type") in KEPT_TYPES and not _is_placeholder(o.get("startTime"))
            ]
        observations.sort(key=lambda o: (o.get("startTime") or "", o.get("id") or ""))
        sessions[full] = {"traces": own, "observations": observations}
    return sessions


def _trace_key(trace: dict[str, Any]) -> tuple[str, str]:
    return (trace.get("timestamp") or "", trace.get("id") or "")


def resolve_session_id(wanted: str, known: list[str]) -> str:
    """Return the one known session id that starts with ``wanted``.

    Raises:
        SystemExit: When no session or more than one session matches.
    """
    matches = [s for s in known if s.startswith(wanted)]
    if not matches:
        raise SystemExit(f"no session starts with {wanted!r}")
    if len(matches) > 1:
        raise SystemExit(f"{wanted!r} is ambiguous: {', '.join(matches)}")
    return matches[0]


def load_fixture(path: str, wanted: list[str]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Read sessions saved by ``--save-fixture`` and pick the wanted ones."""
    with open(path, encoding="utf-8") as handle:
        saved: dict[str, Any] = json.load(handle)["sessions"]
    known = sorted(saved)
    return {
        full: saved[full] for full in dict.fromkeys(resolve_session_id(w, known) for w in wanted)
    }


def save_fixture(path: str, sessions: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """Write sessions with only the public-safe fields, for tests and replays."""
    safe = {
        sid: {
            "traces": [_trim(t, TRACE_FIELDS) for t in data["traces"]],
            "observations": [_trim(o, OBSERVATION_FIELDS) for o in data["observations"]],
        }
        for sid, data in sorted(sessions.items())
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"sessions": safe}, handle, indent=1, sort_keys=True)
        handle.write("\n")


# --- Pricing --------------------------------------------------------------


def normalise_model(model: str | None) -> str:
    """Strip the Bedrock ``global.openai.`` prefix so both routes share a price."""
    name = model or ""
    return name[len(MODEL_PREFIX) :] if name.startswith(MODEL_PREFIX) else name


def usage_buckets(model: str, usage: dict[str, Any] | None) -> dict[str, int]:
    """Read the five token buckets from Langfuse ``usageDetails``.

    An embedding row that reports only ``total`` is counted as input.
    """
    usage = usage or {}
    buckets = {b: int(usage.get(key) or 0) for b, key in USAGE_KEYS.items()}
    if model in INPUT_ONLY_MODELS and not usage.get("input"):
        buckets["input"] = int(usage.get("total") or 0)
    return buckets


def bucket_cost(model: str, buckets: dict[str, int]) -> float | None:
    """Dollar cost of one call's buckets, or ``None`` when the model is unpriced."""
    price = PRICES.get(model)
    if price is None:
        return None
    per_input, per_cached, per_output = (p / 1_000_000 for p in price)
    return (
        buckets["input"] * per_input
        + buckets["cached"] * per_cached
        + buckets["cache_write"] * CACHE_WRITE_MULTIPLIER * per_input
        + buckets["output"] * per_output
        + buckets["reasoning"] * per_output
    )


# --- Report ---------------------------------------------------------------


def stage_name(trace_name: str | None) -> str:
    """Trace name without the ``run:`` prefix or a trailing walk id."""
    name = _UUID_SUFFIX.sub("", trace_name or "(unnamed)")
    return name[4:] if name.startswith("run:") else name


def run_type(trace_names: list[str]) -> str:
    """Classify a session the way the 2026-10-30 baseline did.

    "scoping" if a ``run:longlist`` trace exists, "ES deep" if ``run:extract``,
    "ES standard" if ``run:screen_full``, else "ES landscape" (ES = Evidence
    search).
    """
    stages = {stage_name(n) for n in trace_names if (n or "").startswith("run:")}
    if "longlist" in stages:
        return "scoping"
    if "extract" in stages:
        return "ES deep"
    if "screen_full" in stages:
        return "ES standard"
    return "ES landscape"


def _empty_row() -> dict[str, Any]:
    return {"calls": 0, **{b: 0 for b in BUCKETS}, "cost_usd": 0.0}


def _finish(
    rows: dict[tuple[str, ...], dict[str, Any]], keys: tuple[str, ...], total: float
) -> list[dict[str, Any]]:
    out = []
    for key, row in rows.items():
        prompt = row["input"] + row["cached"] + row["cache_write"]
        row = {
            **dict(zip(keys, key, strict=True)),
            **row,
            "cost_usd": round(row["cost_usd"], 6),
            "share": round(row["cost_usd"] / total, 4) if total else 0.0,
            "cache_read_share": round(row["cached"] / prompt, 4) if prompt else 0.0,
            "cache_write_share": round(row["cache_write"] / prompt, 4) if prompt else 0.0,
        }
        out.append(row)
    out.sort(key=lambda r: (-r["cost_usd"], *(r[k] or "" for k in keys)))
    return out


def session_report(session_id: str, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Price one session and group the cost by stage and by call name.

    Args:
        session_id: Full Langfuse session id.
        data: ``{"traces": [...], "observations": [...]}`` as fetched.

    Returns:
        A JSON-ready dict: totals, run type, ``by_stage``, ``by_call`` and
        ``unknown_models`` (calls on a model with no price, costed at 0).
    """
    traces = {t["id"]: t for t in data["traces"]}
    by_stage: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_empty_row)
    by_call: dict[tuple[str, ...], dict[str, Any]] = defaultdict(_empty_row)
    unknown: dict[str, dict[str, int]] = {}
    total = run_total = 0.0
    for obs in data["observations"]:
        trace = traces.get(obs.get("traceId") or "")
        if trace is None:
            continue
        model = normalise_model(obs.get("model"))
        buckets = usage_buckets(model, obs.get("usageDetails"))
        cost = bucket_cost(model, buckets)
        if cost is None and any(buckets.values()):
            entry = unknown.setdefault(model or "(none)", {"calls": 0, "tokens": 0})
            entry["calls"] += 1
            entry["tokens"] += sum(buckets.values())
        cost = cost or 0.0
        total += cost
        if (trace.get("name") or "").startswith("run:"):
            run_total += cost
        for rows, key in (
            (by_stage, (stage_name(trace.get("name")),)),
            (by_call, (obs.get("name") or "(unnamed)", model or "(none)")),
        ):
            row = rows[key]
            row["calls"] += 1
            row["cost_usd"] += cost
            for b in BUCKETS:
                row[b] += buckets[b]
    stamps = sorted(t["timestamp"] for t in data["traces"] if t.get("timestamp"))
    return {
        "session_id": session_id,
        "date": stamps[0][:10] if stamps else None,
        "run_type": run_type([t.get("name") or "" for t in data["traces"]]),
        "session_total_usd": round(total, 6),
        "run_total_usd": round(run_total, 6),
        "by_stage": _finish(by_stage, ("stage",), total),
        "by_call": _finish(by_call, ("name", "model"), total),
        "unknown_models": dict(sorted(unknown.items())),
    }


def summary(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Median, minimum and maximum per run type, over run and session totals."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in reports:
        groups[r["run_type"]].append(r)
    out = []
    for kind in sorted(groups):
        rows = sorted(groups[kind], key=lambda r: (r["date"] or "", r["session_id"]))
        entry: dict[str, Any] = {"run_type": kind, "runs": len(rows)}
        for label in ("run_total_usd", "session_total_usd"):
            values = [r[label] for r in rows]
            entry[label] = {
                "median": round(statistics.median(values), 6),
                "min": round(min(values), 6),
                "max": round(max(values), 6),
            }
        entry["sessions"] = [r["session_id"][:8] for r in rows]
        out.append(entry)
    return out


def build_report(sessions: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    """The whole report for the given sessions, as a JSON-ready dict."""
    reports = [session_report(sid, data) for sid, data in sessions.items()]
    report: dict[str, Any] = {"prices_read_on": PRICES_READ_ON, "sessions": reports}
    if len(reports) > 1:
        report["summary"] = summary(reports)
    return report


# --- Text output ----------------------------------------------------------


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def _table(headers: list[str], rows: list[list[str]], left: int) -> str:
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)
    ]
    lines = []
    for cells in [headers, *rows]:
        parts = [
            c.ljust(w) if i < left else c.rjust(w)
            for i, (c, w) in enumerate(zip(cells, widths, strict=True))
        ]
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines)


def format_text(report: dict[str, Any]) -> str:
    """Render the report as plain-text tables."""
    blocks = [f"Prices: list prices read {report['prices_read_on']}, USD."]
    for s in report["sessions"]:
        blocks.append(
            f"\n=== Session {s['session_id']}  {s['date']}  {s['run_type']}\n"
            f"Session total ${s['session_total_usd']:.4f}   "
            f"run total (run:* traces only) ${s['run_total_usd']:.4f}"
        )
        stage_rows = [
            [
                r["stage"],
                str(r["calls"]),
                *(_fmt_tokens(r[b]) for b in BUCKETS),
                f"${r['cost_usd']:.4f}",
                f"{r['share']:.1%}",
            ]
            for r in s["by_stage"]
        ]
        blocks.append(
            "\nBy stage\n"
            + _table(["stage", "calls", *BUCKETS, "cost", "share"], stage_rows, left=1)
        )
        call_rows = [
            [
                r["name"],
                r["model"],
                str(r["calls"]),
                *(_fmt_tokens(r[b]) for b in BUCKETS),
                f"{r['cache_read_share']:.0%}",
                f"{r['cache_write_share']:.0%}",
                f"${r['cost_usd']:.4f}",
                f"{r['share']:.1%}",
            ]
            for r in s["by_call"]
        ]
        blocks.append(
            "\nBy call name\n"
            + _table(
                ["call", "model", "calls", *BUCKETS, "read%", "write%", "cost", "share"],
                call_rows,
                left=2,
            )
        )
        for model, info in s["unknown_models"].items():
            blocks.append(
                f"UNPRICED model {model!r}: {info['calls']} calls, "
                f"{info['tokens']:,} tokens, costed at $0"
            )
    if "summary" in report:
        rows = []
        for g in report["summary"]:
            run, ses = g["run_total_usd"], g["session_total_usd"]
            rows.append(
                [
                    g["run_type"],
                    str(g["runs"]),
                    f"${run['median']:.2f}",
                    f"${run['min']:.2f} to ${run['max']:.2f}",
                    f"${ses['median']:.2f}",
                    f"${ses['min']:.2f} to ${ses['max']:.2f}",
                    " ".join(g["sessions"]),
                ]
            )
        per = [
            [
                s["run_type"],
                s["session_id"][:8],
                s["date"] or "",
                f"${s['run_total_usd']:.2f}",
                f"${s['session_total_usd']:.2f}",
            ]
            for s in sorted(
                report["sessions"], key=lambda s: (s["run_type"], s["date"] or "", s["session_id"])
            )
        ]
        blocks.append(
            "\n=== Summary across sessions (run total = run:* traces, the baseline's definition)\n"
            + _table(["run type", "session", "date", "run total", "session total"], per, left=3)
            + "\n\n"
            + _table(
                [
                    "run type",
                    "runs",
                    "run median",
                    "run range",
                    "session median",
                    "session range",
                    "sessions",
                ],
                rows,
                left=2,
            )
        )
    return "\n".join(blocks) + "\n"


# --- Command line ---------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Cost of Policy Atlas runs from Langfuse token counts at list prices "
            "(not Langfuse's stored cost). Needs LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY "
            "and LANGFUSE_SECRET_KEY in the environment unless --fixture is given."
        )
    )
    parser.add_argument(
        "session_ids",
        nargs="+",
        metavar="SESSION_ID",
        help="full Langfuse session id or its first characters",
    )
    parser.add_argument(
        "--fixture",
        metavar="PATH",
        help="read sessions from a file saved by --save-fixture instead of Langfuse",
    )
    parser.add_argument(
        "--save-fixture",
        metavar="PATH",
        help="also save the fetched sessions (ids, names, times, models, token counts only)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON instead of tables"
    )
    parser.add_argument(
        "--from-timestamp",
        default=DEFAULT_FROM,
        help=f"earliest trace date searched when resolving session ids (default {DEFAULT_FROM})",
    )
    args = parser.parse_args(argv)
    if args.fixture:
        sessions = load_fixture(args.fixture, args.session_ids)
    else:
        sessions = fetch_sessions(LangfuseClient.from_env(), args.session_ids, args.from_timestamp)
    if args.save_fixture:
        save_fixture(args.save_fixture, sessions)
    report = build_report(sessions)
    for s in report["sessions"]:
        for model, info in s["unknown_models"].items():
            print(
                f"warning: session {s['session_id'][:8]}: no price for model {model!r} "
                f"({info['calls']} calls, {info['tokens']:,} tokens); costed at $0",
                file=sys.stderr,
            )
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        sys.stdout.write(format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
