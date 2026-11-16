#!/usr/bin/env python3
"""Wall time per stage of a Policy Atlas run, read from the local database (task 057, P12).

What this answers
-----------------
"Where did the time go in this run?" A *capability run* is one whole Evidence search
or Options scoping run. It is made of *component runs* (stages such as ``acquire``,
``classify``, ``ingest_full_text`` or ``synthesise``), and every component writes a
``component.timing`` event into the database's ``event_log`` table with its own
stopwatch reading (``wall_clock_s``). This script reads those events and prints, per
run, how many seconds each stage took, and then the median, maximum and minimum per
stage across the runs you selected. It reproduces the per-stage tables of the
2026-11-02 latency anatomy (``40_anatomy.py`` in the gitignored experiment folder)
without Langfuse.

Definitions (the same as the anatomy)
-------------------------------------
- **Component wall** (seconds): the ``component.timing`` event's ``wall_clock_s``.
  When a component has no timing event, the run row's ``ended_at - started_at`` is
  used instead. Only ``synthesise`` differs between the two by more than a few
  seconds: its after-commit summary pass runs after the run row is closed.
- **Total wall**: the capability run's ``ended_at - started_at``.
- **Outside components**: total wall minus the time covered by any component run
  (overlapping intervals counted once; for scoping this includes the child runs of
  the option-search fan-out). It is the time spent between stages: agent turns,
  plan compiles and hand-overs.
- **Fan-out window** (scoping only): from the first child capability run's start to
  the last child's end.
- **Synth post-commit**: ``synthesise``'s component wall minus its run-row wall.
- **Counts**: document counts copied from the ``component.completed`` payloads.

Ingest split (optional, ``--logs``)
-----------------------------------
The database does not say how the ingest stage's time divides between fetching
documents and embedding them, but the server's log file does. Point ``--logs`` at
the uvicorn server's log files (or a folder of them) and the script adds, for the
ingest component run:

- **A** = ``component.started`` to the first embedding request (fetch, parse and
  chunk writes);
- **B** = first embedding request to ``embed.summary`` (the embedding phase);
- **C** = ``embed.summary`` to ``component.completed`` (the tail);
- the number of embedding requests, and the rate-limit sleeps (count and total s).

Events read from the logs: ``component.started``, ``component.completed``,
``embed.summary``, ``embedding.<provider>.request``,
``embedding.<provider>.*rate_limited`` (field ``sleep_s``) and
``ingest.batch_handover`` (fields ``batch``, ``documents``, ``fetch_wall_s``,
``parse_wall_s``, ``idle_gap_s``). Every line that carries a ``run_id`` and whose
event name starts with ``component.``, ``embed``, ``ingest.`` or ``fulltext.`` is
kept; anything else (including event names added by later ingest rewrites) is
ignored, never an error. A missing event leaves its column blank. Both log formats
are read: the coloured console format used locally and one JSON object per line
(``LOG_FORMAT=json``).

Usage
-----
From the repository root, with the dev database running (``make dev``)::

    uv run --project backend python scripts/stage_walls.py --since 2026-11-02
    uv run --project backend python scripts/stage_walls.py --run-id f443179b --run-id 695ed3a1 \\
        --route bedrock --logs /path/to/live-server.log
    uv run --project backend python scripts/stage_walls.py --task-id <task uuid> --format json \\
        --out /tmp/walls.json

``DATABASE_URL`` is read from the environment (``backend/.env`` has the local one)
unless ``--database-url`` is given. Run ids may be the first few characters of the
id. Selection flags of different kinds combine with AND (``--since`` and
``--capability`` narrow ``--task-id``); repeats of one flag combine with OR. Only
top-level capability runs are selected; their child runs (the scoping fan-out) are
pulled in automatically. The script only reads: it opens a read-only transaction.

Stream capture mode (``--capture``, task 058, N25)
--------------------------------------------------
"How long did the page go without being told anything?" ``--capture <file.jsonl>``
reads one recording made by ``scripts/stream_capture.py`` (one JSON line per frame,
keep-alive comment or reconnect, each stamped ``received_at``) and needs no
database. Every time below is ``received_at``: when the page would have seen it.

- **The run measured**: the run the page follows (the web client's rule: a
  ``run.status`` for another run while the followed one is running or paused is a
  child run, such as an option search). When the recording starts with an earlier
  run replayed from history, the last run to be followed is the one measured.
- **Active interval**: its first ``run.status`` to its final one (``succeeded``,
  ``degraded``, ``failed``, ``aborted``, ``interrupted``; the last line of the file
  when there is none, with ``finished`` false), minus the **parked** intervals: from
  ``run.status paused`` or ``checkin.pending`` to the next ``run.status running``.
- **Visible**: every frame, durable or ephemeral (``tick`` frames, heartbeats
  included, and prose deltas), from any run on the task. Keep-alive comments and
  reconnect lines are not visible: the page shows nothing for them.
- **Silent gap**: a stretch of the active interval longer than 30 s with no visible
  frame. Reported as a count, total seconds, share of active seconds, and the same
  per **owning stage**: the stage of the measured run's latest ``stage.started``
  still open (no ``stage.completed`` or ``stage.failed`` yet) when the gap began,
  or "(between stages)".
- **Time to first prose**: from the first ``artefact.section_started`` to the first
  ``artefact.section_delta`` after it, and to the first
  ``artefact.section_completed`` after it.
- **Tick rate per stage**: over each stage's open intervals (``stage.started`` to
  its ``stage.completed`` or ``stage.failed``), the ticks naming that stage, per
  second; heartbeats (ticks with ``heartbeat`` true) counted separately.
- **Dropped ticks**: the last tick's ``dropped`` minus the first's (the server's
  counter only goes up for a task). Blank when no tick carries it.
- **Healthy run**: ``--healthy true|false``, decided by the caller from the run's
  trace (no model-call timeout fired, no fallback ran) and carried into the output.

Recordings made before task 058 have the old tick shape (``note``, ``fetched``,
``parsed``, ``total``); such a tick is read as ``activity = note``, ``done =
parsed``, ``unit`` empty. Usage::

    python3 scripts/stage_walls.py --capture run.capture.jsonl --healthy true \\
        --format json --out /tmp/gaps.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

#: Evidence search component order for the table columns (the anatomy's order).
ES_ORDER = [
    "acquire",
    "screen_abstract",
    "classify",
    "appraise",
    "ingest_full_text",
    "screen_full",
    "characterise",
    "select",
    "synthesise",
]
INGEST_COMPONENT = "ingest_full_text"

# --- Database extract ---------------------------------------------------------

# The same read-only extract as the anatomy's 10_runs.sql; only the selection of
# top-level runs (the ``top`` CTE) is built from the command-line flags.
_EXTRACT_SQL = """
WITH top AS (
  SELECT c.capability_run_id FROM capability_run c
   WHERE c.parent_capability_run_id IS NULL AND {where}
),
sel AS (
  SELECT capability_run_id FROM top
  UNION
  SELECT k.capability_run_id FROM capability_run k
   WHERE k.parent_capability_run_id IN (SELECT capability_run_id FROM top)
),
comp AS (
  SELECT r.capability_run_id, r.run_id, r.status AS run_status, r.started_at AS run_started,
         r.ended_at AS run_ended,
         (SELECT e.payload FROM event_log e WHERE e.run_id = r.run_id
            AND e.event_type = 'run.started' ORDER BY e.sequence LIMIT 1) AS started_payload,
         (SELECT e.payload FROM event_log e WHERE e.run_id = r.run_id
            AND e.event_type = 'component.timing' ORDER BY e.sequence DESC LIMIT 1)
            AS timing_payload,
         (SELECT e.payload FROM event_log e WHERE e.run_id = r.run_id
            AND e.event_type = 'component.completed' ORDER BY e.sequence DESC LIMIT 1)
            AS completed_payload
  FROM runs r WHERE r.capability_run_id IN (SELECT capability_run_id FROM sel)
)
SELECT json_agg(x ORDER BY x.started_at) FROM (
  SELECT c.capability_run_id, c.capability, c.status, c.session_id, c.task_id, c.started_at,
         c.ended_at, c.parent_capability_run_id, t.name AS task_name,
         (SELECT json_agg(json_build_object(
             'run_id', m.run_id, 'run_status', m.run_status,
             'run_started', m.run_started, 'run_ended', m.run_ended,
             'component', m.started_payload->>'component',
             'registry_component', m.started_payload->>'registry_component',
             'timing', m.timing_payload, 'completed', m.completed_payload)
           ORDER BY m.run_started) FROM comp m
           WHERE m.capability_run_id = c.capability_run_id) AS components,
         (SELECT json_agg(json_build_object('event_type', e.event_type,
                                            'occurred_at', e.occurred_at)
                 ORDER BY e.occurred_at)
            FROM event_log e
           WHERE e.task_id = c.task_id
             AND e.occurred_at BETWEEN c.started_at AND coalesce(c.ended_at, now())
             AND e.event_type IN ('run.opened', 'run.parked', 'continuation.requested',
                                  'continuation.claimed', 'run.finished', 'steering.pause',
                                  'run.interrupted', 'run.failed')) AS lifecycle
  FROM capability_run c LEFT JOIN task t ON t.task_id = c.task_id
  WHERE c.capability_run_id IN (SELECT capability_run_id FROM sel)
) x
"""


def build_selection(
    run_ids: list[str], task_ids: list[str], since: str | None, capability: str | None
) -> tuple[str, dict[str, Any]]:
    """Build the WHERE clause that picks the top-level capability runs.

    Args:
        run_ids: Capability run ids or their first characters (OR'd together).
        task_ids: Task ids (OR'd together).
        since: ISO date or timestamp; runs started at or after it.
        capability: ``evidence_search`` or ``options_scoping``, or ``None`` for both.

    Returns:
        The SQL condition (on alias ``c``) and its bound parameters.

    Raises:
        ValueError: If no selection flag was given.
    """
    if not (run_ids or task_ids or since):
        raise ValueError("give at least one of --run-id, --task-id or --since")
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if run_ids:
        clauses.append("c.capability_run_id::text LIKE ANY(CAST(:run_patterns AS text[]))")
        params["run_patterns"] = [f"{r.strip().lower()}%" for r in run_ids]
    if task_ids:
        clauses.append("c.task_id::text = ANY(CAST(:task_ids AS text[]))")
        params["task_ids"] = [t.strip().lower() for t in task_ids]
    if since:
        clauses.append("c.started_at >= CAST(:since AS timestamptz)")
        params["since"] = since
    if capability:
        clauses.append("c.capability = :capability")
        params["capability"] = capability
    return " AND ".join(clauses), params


def fetch_runs(
    database_url: str | None, where: str, params: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the extract in a read-only transaction and return its rows.

    Args:
        database_url: SQLAlchemy URL, or ``None`` to read ``DATABASE_URL``.
        where: Condition from :func:`build_selection`.
        params: Its bound parameters.

    Returns:
        One dict per capability run (top-level and child), oldest first.
    """
    from sqlalchemy import create_engine, text

    if database_url:
        engine = create_engine(database_url)
    else:
        from policy_atlas.core.db import get_engine

        engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        value = conn.execute(text(_EXTRACT_SQL.format(where=where)), params).scalar()
        conn.rollback()
    engine.dispose()
    if value is None:
        return []
    rows = json.loads(value) if isinstance(value, str) else value
    return list(rows)


# --- Server log parsing ---------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_CONSOLE_LINE = re.compile(r"^(\S+) \[\s*\w+\s*\] (\S+)\s*(.*)$")
_KV = re.compile(r"(\w+)=(\S+)")
_KEEP_PREFIXES = ("component.", "embed", "ingest.", "fulltext.")


def _parse_line(raw: str) -> dict[str, Any] | None:
    """Return ``{"ts", "event", fields...}`` for one kept log line, else ``None``."""
    line = _ANSI.sub("", raw.rstrip("\n")).strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        event, ts = obj.get("event"), obj.get("timestamp")
        fields = {k: v for k, v in obj.items() if k not in ("event", "timestamp")}
    else:
        m = _CONSOLE_LINE.match(line)
        if not m:
            return None
        ts, event = m.group(1), m.group(2)
        fields = dict(_KV.findall(m.group(3)))
    if not isinstance(event, str) or not isinstance(ts, str):
        return None
    if not event.startswith(_KEEP_PREFIXES) or not fields.get("run_id"):
        return None
    fields.pop("task_id", None)
    return {"ts": ts, "event": event, **fields}


def parse_log_lines(lines: Iterable[str], source: str = "") -> dict[str, dict[str, Any]]:
    """Group the kept log events by component run id.

    Args:
        lines: Raw log lines (console or JSON format, ANSI colours allowed).
        source: File name recorded against each run id.

    Returns:
        ``{run_id: {"files": [...], "events": [{"ts", "event", fields...}]}}``.
    """
    out: dict[str, dict[str, Any]] = {}
    for raw in lines:
        rec = _parse_line(raw)
        if rec is None:
            continue
        entry = out.setdefault(str(rec["run_id"]), {"files": [], "events": []})
        if source and source not in entry["files"]:
            entry["files"].append(source)
        entry["events"].append(rec)
    return out


def read_logs(paths: list[str]) -> dict[str, dict[str, Any]]:
    """Parse every log file named (folders expand to their ``*.log`` files).

    Args:
        paths: Files or directories.

    Returns:
        The merged :func:`parse_log_lines` result, events in time order per run.
    """
    files: list[Path] = []
    for p in map(Path, paths):
        files.extend(sorted(p.glob("*.log")) if p.is_dir() else [p])
    merged: dict[str, dict[str, Any]] = {}
    for f in files:
        with f.open(errors="replace") as fh:
            for rid, rec in parse_log_lines(fh, f.name).items():
                entry = merged.setdefault(rid, {"files": [], "events": []})
                entry["files"].extend(x for x in rec["files"] if x not in entry["files"])
                entry["events"].extend(rec["events"])
    for entry in merged.values():
        entry["events"].sort(key=lambda e: e["ts"])
    return merged


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ingest_split(log_run: dict[str, Any] | None) -> dict[str, Any] | None:
    """Split one ingest component run's time using its log events (see module doc).

    Args:
        log_run: The run's entry from :func:`read_logs`, or ``None``.

    Returns:
        The A/B/C split, request and sleep counts, and handover batches, or ``None``
        when the run has no log events.
    """
    if not log_run:
        return None
    ev = log_run["events"]

    def first(name: str) -> str | None:
        return next((e["ts"] for e in ev if e["event"] == name), None)

    start, summary, done = (
        first("component.started"),
        first("embed.summary"),
        first("component.completed"),
    )
    requests = [
        e for e in ev if e["event"].startswith("embedding.") and e["event"].endswith(".request")
    ]
    sleeps = [
        _num(e.get("sleep_s")) or 0.0
        for e in ev
        if e["event"].startswith("embedding.") and e["event"].endswith("rate_limited")
    ]
    first_req = requests[0]["ts"] if requests else None
    handovers = [e for e in ev if e["event"] == "ingest.batch_handover"]
    keys = ("batch", "documents", "fetch_wall_s", "parse_wall_s", "idle_gap_s")
    return {
        "log_file": ",".join(log_run.get("files") or []),
        "start_to_first_embed_request_s": secs(start, first_req),
        "first_embed_request_to_embed_summary_s": secs(first_req, summary),
        "embed_summary_to_completed_s": secs(summary, done),
        "embed_requests": len(requests),
        "embed_provider": sorted({e["event"].split(".")[1] for e in requests}),
        "rate_limit_sleeps": len(sleeps),
        "rate_limit_sleep_s_sum": sum(sleeps),
        "handover_batches": [{k: _num(e.get(k)) for k in keys} for e in handovers],
    }


# --- Pure computation -------------------------------------------------------------


def ts(value: str | None) -> datetime | None:
    """Parse an ISO timestamp (``Z`` allowed); ``None`` stays ``None``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def secs(a: str | None, b: str | None) -> float | None:
    """Seconds from ISO timestamp ``a`` to ``b``, or ``None`` if either is missing."""
    ta, tb = ts(a), ts(b)
    return (tb - ta).total_seconds() if ta and tb else None


def union_s(intervals: Iterable[tuple[datetime | None, datetime | None]]) -> float:
    """Total seconds covered by the intervals, overlaps counted once."""
    iv = sorted((a, b) for a, b in intervals if a and b)
    total = 0.0
    cur: list[datetime] | None = None
    for a, b in iv:
        if cur is None or a > cur[1]:
            if cur:
                total += (cur[1] - cur[0]).total_seconds()
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        total += (cur[1] - cur[0]).total_seconds()
    return total


def _counts(by: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def hc(comp: str, key: str) -> Any:
        return ((by.get(comp) or {}).get("completed") or {}).get(key)

    sel = (by.get("select") or {}).get("completed") or {}
    counts: dict[str, Any] = {
        "acquired": hc("acquire", "acquired"),
        "screened_abstract": hc("screen_abstract", "screened"),
        "relevant_abstract": hc("screen_abstract", "relevant"),
        "full_text_eligible": hc(INGEST_COMPONENT, "eligible"),
        "full_text_attempted": hc(INGEST_COMPONENT, "attempted"),
        "ingested": hc(INGEST_COMPONENT, "ingested"),
        "screen_full_screened": hc("screen_full", "stage2_screened"),
        "screen_full_confirmed": hc("screen_full", "confirmed"),
        "selected": (sel.get("selected") or {}).get("count"),
        "extract_component_run": "extract" in by,
    }
    if "extract_interventions" in by:
        ec = (by["extract_interventions"].get("completed") or {}).get("counts") or {}
        prof = (ec.get("profiles") or {}).get("os_interventions_base_v1") or {}
        counts["extract_interventions_docs_fresh"] = prof.get("fresh")
        counts["extract_interventions_docs_extracted"] = prof.get("extracted")
        counts["extract_interventions_findings"] = (prof.get("findings") or {}).get("total")
    return counts


def run_entry(
    c: dict[str, Any],
    kids: list[dict[str, Any]],
    logs: dict[str, dict[str, Any]] | None,
    route: str,
) -> dict[str, Any]:
    """Compute one top-level capability run's walls, counts and ingest split.

    Args:
        c: The capability run row from the extract.
        kids: Its child capability runs (scoping fan-out), possibly empty.
        logs: Parsed server logs (:func:`read_logs`), or ``None``.
        route: Route label to carry in the output (may be empty).

    Returns:
        A JSON-ready dict (the anatomy's per-run entry, without Langfuse fields).
    """
    comps = c.get("components") or []
    rows = []
    for m in comps:
        timing_wall = (m.get("timing") or {}).get("wall_clock_s")
        row_wall = secs(m["run_started"], m["run_ended"])
        rows.append(
            {
                "component": m["component"],
                "run_id": m["run_id"],
                "status": m["run_status"],
                "start": m["run_started"],
                "row_wall_s": row_wall,
                "timing_wall_clock_s": timing_wall,
                "wall_s": timing_wall if timing_wall is not None else row_wall,
            }
        )
    intervals: list[tuple[datetime | None, datetime | None]] = []
    for r in rows:
        start = ts(r["start"])
        if start is not None and r["wall_s"] is not None:
            intervals.append((start, start + timedelta(seconds=r["wall_s"])))
    fan = None
    if kids:
        kid_runs = [m for k in kids for m in (k.get("components") or [])]
        intervals += [(ts(m["run_started"]), ts(m["run_ended"])) for m in kid_runs]
        kid_walls = [w for k in kids if (w := secs(k["started_at"], k["ended_at"])) is not None]
        ends = [k["ended_at"] for k in kids if k["ended_at"]]
        window_start = min(k["started_at"] for k in kids)
        fan = {
            "child_capability_runs": len(kids),
            "child_components": sorted({m["component"] for m in kid_runs if m["component"]}),
            "window_s": secs(window_start, max(ends)) if ends else None,
            "child_wall_median_s": statistics.median(kid_walls) if kid_walls else None,
            "child_wall_max_s": max(kid_walls) if kid_walls else None,
            "window_start": window_start,
        }
    total = secs(c["started_at"], c["ended_at"])
    outside = total - union_s(intervals) if total is not None else None
    by = {m["component"]: m for m in comps}
    syn = [r for r in rows if r["component"] == "synthesise"]
    post_commit = (
        syn[0]["wall_s"] - syn[0]["row_wall_s"]
        if syn and syn[0]["wall_s"] is not None and syn[0]["row_wall_s"] is not None
        else None
    )
    ingest = by.get(INGEST_COMPONENT)
    split = None
    if logs is not None and ingest:
        split = ingest_split(logs.get(ingest["run_id"]))
    return {
        "capability_run_id": c["capability_run_id"],
        "id8": c["capability_run_id"][:8],
        "capability": c["capability"],
        "task_name": c.get("task_name"),
        "status": c.get("status"),
        "route": route,
        "started_at": c["started_at"],
        "total_wall_s": total,
        "outside_components_s": outside,
        "synth_post_commit_s": post_commit,
        "run_parked_events": sum(
            1 for e in (c.get("lifecycle") or []) if e.get("event_type") == "run.parked"
        ),
        "components": rows,
        "fan_out": fan,
        "counts": _counts(by),
        "ingest_log_split": split,
    }


def component_order(capability: str, entries: list[dict[str, Any]]) -> list[str]:
    """Column order: the anatomy's order for Evidence search, else first appearance."""
    seen: list[str] = []
    for e in entries:
        for r in e["components"]:
            if r["component"] not in seen:
                seen.append(r["component"])
    if capability == "evidence_search":
        return ES_ORDER + [c for c in seen if c not in ES_ORDER]
    return seen


def stats(entries: list[dict[str, Any]], order: list[str]) -> list[dict[str, Any]]:
    """Median, max and min per component (summed per run), plus total and outside.

    Args:
        entries: Per-run entries from :func:`run_entry`.
        order: Component order.

    Returns:
        One row per component that appears, then ``total`` and ``outside``, each
        with ``n``, ``median_s``, ``max_s``, ``min_s`` and ``share_of_median_total``
        (the median as a fraction of the median total; ``None`` for the total row).
    """
    out: list[dict[str, Any]] = []
    for comp in order + ["total", "outside"]:
        vals: list[float] = []
        for e in entries:
            if comp == "total":
                v = e["total_wall_s"]
            elif comp == "outside":
                v = e["outside_components_s"]
            else:
                walls = [r["wall_s"] for r in e["components"] if r["component"] == comp]
                v = sum(w for w in walls if w is not None) if walls else None
            if v is not None:
                vals.append(v)
        if vals:
            out.append(
                {
                    "component": comp,
                    "n": len(vals),
                    "median_s": statistics.median(vals),
                    "max_s": max(vals),
                    "min_s": min(vals),
                }
            )
    med_total = next((r["median_s"] for r in out if r["component"] == "total"), None)
    for r in out:
        r["share_of_median_total"] = (
            r["median_s"] / med_total if med_total and r["component"] != "total" else None
        )
    return out


def build_report(
    runs: list[dict[str, Any]],
    logs: dict[str, dict[str, Any]] | None = None,
    route: str = "",
) -> dict[str, Any]:
    """Turn the database extract into per-run entries and per-capability statistics.

    Args:
        runs: The extract's rows (top-level and child capability runs).
        logs: Parsed server logs, or ``None`` for no ingest split.
        route: Route label carried on every run.

    Returns:
        ``{"route", "capabilities": {capability: {"runs": [...], "order": [...],
        "stats": [...]}}}``, runs oldest first.
    """
    children: dict[str, list[dict[str, Any]]] = {}
    for c in runs:
        if c.get("parent_capability_run_id"):
            children.setdefault(c["parent_capability_run_id"], []).append(c)
    by_cap: dict[str, list[dict[str, Any]]] = {}
    for c in runs:
        if c.get("parent_capability_run_id"):
            continue
        entry = run_entry(c, children.get(c["capability_run_id"], []), logs, route)
        by_cap.setdefault(c["capability"], []).append(entry)
    caps: dict[str, Any] = {}
    for cap in sorted(by_cap):
        entries = sorted(by_cap[cap], key=lambda e: e["started_at"])
        order = component_order(cap, entries)
        caps[cap] = {"runs": entries, "order": order, "stats": stats(entries, order)}
    return {"route": route, "capabilities": caps}


# --- Markdown -------------------------------------------------------------------


def f0(x: float | None) -> str:
    """Whole seconds, or blank for ``None``."""
    return "" if x is None else f"{x:.0f}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(r) + " |" for r in rows),
    ]


def format_markdown(report: dict[str, Any]) -> str:
    """Render the report as the anatomy's Table 1 and Table 2 (plus counts and ingest split).

    Args:
        report: Output of :func:`build_report`.

    Returns:
        Markdown text.
    """
    md: list[str] = []
    for cap, block in report["capabilities"].items():
        entries, order = block["runs"], block["order"]
        has_fan = any(e["fan_out"] for e in entries)
        md.append(f"### Table 1. {cap}: wall time per component (seconds)\n")
        md.append(
            "Component wall = `component.timing.wall_clock_s` (falls back to the run row). "
            "'outside' = total wall minus time inside any component. 'synth post-commit' = "
            "the part of synthesise's wall after its `runs.ended_at`.\n"
        )
        header = ["run", "task", "route", "start (UTC)", "total", *order, "outside"]
        header += ["fan-out window", "fan-out children"] if has_fan else []
        header += ["synth post-commit"]
        rows = []
        for e in entries:
            walls: dict[str, list[float | None]] = {}
            for r in e["components"]:
                walls.setdefault(r["component"], []).append(r["wall_s"])
            cells = [
                e["id8"],
                (e["task_name"] or "")[:40].replace("|", "/"),
                e["route"] or "-",
                e["started_at"][:16].replace("T", " "),
                f0(e["total_wall_s"]),
            ]
            cells += ["+".join(f0(x) for x in walls[k]) if k in walls else "-" for k in order]
            cells.append(f0(e["outside_components_s"]))
            if has_fan:
                fan = e["fan_out"] or {}
                cells += [
                    f0(fan.get("window_s")) or "-",
                    str(fan.get("child_capability_runs", "-")),
                ]
            post = e["synth_post_commit_s"]
            cells.append(f0(post) if post is not None else "-")
            rows.append(cells)
        md += _table(header, rows)
        md.append("")
        md.append(f"### Table 2. Median and max per component, {cap}\n")
        md.append(f"#### All {len(entries)} {cap} runs\n")
        stat_rows = [
            [
                s["component"],
                str(s["n"]),
                f"{s['median_s']:.0f}",
                f"{s['max_s']:.0f}",
                f"{s['min_s']:.0f}",
                ""
                if s["share_of_median_total"] is None
                else f"{100 * s['share_of_median_total']:.0f}%",
            ]
            for s in block["stats"]
        ]
        md += _table(
            ["component", "n", "median s", "max s", "min s", "median share of median total"],
            stat_rows,
        )
        md.append("")
        md.append(f"### Counts, {cap} (from component.completed payloads)\n")
        keys = [k for k in entries[0]["counts"] if any(e["counts"].get(k) for e in entries)]
        md += _table(
            ["run", *keys],
            [[e["id8"], *(str(e["counts"].get(k, "")) for k in keys)] for e in entries],
        )
        md.append("")
        splits = [e for e in entries if e["ingest_log_split"]]
        if splits:
            md.append(f"### Ingest split, {cap} (seconds, from the server logs)\n")
            md.append(
                "A = component start to first embedding request (fetch + parse); B = first "
                "embedding request to `embed.summary`; C = `embed.summary` to component end.\n"
            )
            srows = []
            for e in splits:
                s = e["ingest_log_split"]
                wall = sum(
                    r["wall_s"] or 0 for r in e["components"] if r["component"] == INGEST_COMPONENT
                )
                srows.append(
                    [
                        e["id8"],
                        f0(wall),
                        f0(s["start_to_first_embed_request_s"]),
                        f0(s["first_embed_request_to_embed_summary_s"]),
                        f0(s["embed_summary_to_completed_s"]),
                        str(s["embed_requests"]),
                        f"{s['rate_limit_sleeps']} / {s['rate_limit_sleep_s_sum']:.0f}",
                    ]
                )
            md += _table(
                [
                    "run",
                    "ingest wall",
                    "A fetch+parse",
                    "B embedding",
                    "C tail",
                    "embed requests",
                    "rate-limit sleeps (n / sum s)",
                ],
                srows,
            )
            md.append("")
    if not report["capabilities"]:
        md.append("No capability runs matched the selection.")
    return "\n".join(md) + "\n"


# --- Stream capture (task 058, N25) ---------------------------------------------

SILENT_GAP_S = 30.0
TERMINAL_STATUSES = frozenset({"succeeded", "degraded", "failed", "aborted", "interrupted"})
BETWEEN_STAGES = "(between stages)"


def read_capture(path: str) -> tuple[list[dict[str, Any]], int]:
    """Read a ``stream_capture.py`` recording.

    Args:
        path: The ``.jsonl`` file.

    Returns:
        The records in file order, and how many lines could not be read (a
        capture killed mid-write can end in half a line).
    """
    records: list[dict[str, Any]] = []
    unreadable = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                unreadable += 1
                continue
            if isinstance(obj, dict) and isinstance(obj.get("received_at"), str):
                records.append(obj)
            else:
                unreadable += 1
    return records, unreadable


def normalise_tick(data: dict[str, Any]) -> dict[str, Any]:
    """Read a tick body in today's shape, mapping the pre-058 shape onto it.

    A tick with ``note`` and no ``activity`` is the old shape: ``activity`` is the
    note, ``done`` is ``parsed``, ``unit`` is ``None``.

    Args:
        data: The tick frame's body.

    Returns:
        ``stage``, ``activity``, ``done``, ``total``, ``unit``, ``section``,
        ``heartbeat`` (bool) and ``dropped`` (``None`` when the tick has none).
    """
    old = "activity" not in data and "note" in data
    return {
        "stage": data.get("stage"),
        "activity": data.get("note") if old else data.get("activity"),
        "done": data.get("parsed") if old else data.get("done"),
        "total": data.get("total"),
        "unit": None if old else data.get("unit"),
        "section": data.get("section"),
        "heartbeat": bool(data.get("heartbeat", False)),
        "dropped": data.get("dropped"),
    }


def _frames(records: list[dict[str, Any]]) -> list[tuple[datetime, str, dict[str, Any]]]:
    """``(received_at, frame name, body)`` for every frame record, in file order."""
    out = []
    for r in records:
        if r.get("kind") != "frame":
            continue
        body = r.get("data") if isinstance(r.get("data"), dict) else {}
        name = r.get("event") or body.get("type") or ""
        at = ts(r["received_at"])
        if at is not None:
            out.append((at, str(name), body))
    return out


def _measured_walk(frames: list[tuple[datetime, str, dict[str, Any]]]) -> str | None:
    """The last run the page follows (the web client's rule; see the module doc)."""
    walk: str | None = None
    status: str | None = None
    children: set[str] = set()
    for _, name, body in frames:
        if name != "run.status":
            continue
        rid = body.get("capability_run_id")
        live = walk is not None and status in ("running", "paused")
        if rid in children or (live and rid != walk):
            children.add(rid)
            continue
        walk, status = rid, body.get("status")
    return walk


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _share(part: float, whole: float) -> float | None:
    return part / whole if whole > 0 else None


def capture_report(
    records: list[dict[str, Any]], healthy: bool | None = None, unreadable: int = 0
) -> dict[str, Any]:
    """Compute the silent-gap measure and its companions from one recording.

    Args:
        records: The recording's lines (:func:`read_capture`), in file order.
        healthy: The caller's healthy-run verdict, carried as given.
        unreadable: Unreadable line count, carried into ``counts``.

    Returns:
        A JSON-ready dict: the measured run and its active interval, ``silent_gaps``
        (count, total, share, ``by_stage``, each gap), ``first_prose``,
        ``tick_rate`` (per stage), ``dropped_ticks`` and ``counts``.
    """
    frames = _frames(records)
    walk = _measured_walk(frames)
    counts = {
        "frames": len(frames),
        "ticks": 0,
        "heartbeats": 0,
        "comments": sum(1 for r in records if r.get("kind") == "comment"),
        "reconnects": sum(1 for r in records if r.get("kind") == "reconnect"),
        "unreadable_lines": unreadable,
    }
    ticks = [(at, normalise_tick(b)) for at, name, b in frames if name == "tick"]
    dropped_values = [t["dropped"] for _, t in ticks if isinstance(t["dropped"], int)]
    dropped = {
        "first": dropped_values[0] if dropped_values else None,
        "last": dropped_values[-1] if dropped_values else None,
        "delta": dropped_values[-1] - dropped_values[0] if dropped_values else None,
    }
    report: dict[str, Any] = {
        "healthy": healthy,
        "walk": walk,
        "finished": False,
        "final_status": None,
        "active_start": None,
        "active_end": None,
        "wall_s": None,
        "parked_s": None,
        "active_s": None,
        "parked": [],
        "silent_gaps": None,
        "first_prose": None,
        "tick_rate": [],
        "dropped_ticks": dropped,
        "counts": counts,
    }
    mine = [
        (at, b)
        for at, name, b in frames
        if name == "run.status" and b.get("capability_run_id") == walk
    ]
    if walk is None or not mine:
        return report
    start = mine[0][0]
    final = next(((at, b) for at, b in mine if b.get("status") in TERMINAL_STATUSES), None)
    if final is not None:
        end = final[0]
        report["finished"], report["final_status"] = True, final[1].get("status")
    else:
        end = max(t for r in records if (t := ts(r["received_at"])) is not None)
    inside = [(at, name, b) for at, name, b in frames if start <= at <= end]

    # Parked intervals: paused or a waiting check-in, until the run runs again.
    parked: list[tuple[datetime, datetime]] = []
    since: datetime | None = None
    for at, name, b in inside:
        is_mine = name == "run.status" and b.get("capability_run_id") == walk
        pauses = name == "checkin.pending" or (is_mine and b.get("status") == "paused")
        if since is None and pauses:
            since = at
        elif since is not None and is_mine and b.get("status") == "running":
            parked.append((since, at))
            since = None
    if since is not None:
        parked.append((since, end))
    parked_s = sum((b - a).total_seconds() for a, b in parked)
    wall_s = (end - start).total_seconds()
    active_s = wall_s - parked_s

    # The measured run's stage intervals (stage frames of child runs are left out).
    stage_events = [
        (at, name, b)
        for at, name, b in inside
        if name in ("stage.started", "stage.completed", "stage.failed")
        and b.get("capability_run_id") in (walk, None)
    ]
    intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    open_stages: list[tuple[str, datetime]] = []
    for at, name, b in stage_events:
        stage = str(b.get("stage"))
        if name == "stage.started":
            open_stages.append((stage, at))
            intervals.setdefault(stage, [])
            continue
        for i in range(len(open_stages) - 1, -1, -1):
            if open_stages[i][0] == stage:
                intervals[stage].append((open_stages.pop(i)[1], at))
                break
    for stage, opened in open_stages:
        intervals[stage].append((opened, end))

    def owner(moment: datetime) -> str:
        stack: list[str] = []
        for at, name, b in stage_events:
            if at > moment:
                break
            stage = str(b.get("stage"))
            if name == "stage.started":
                stack.append(stage)
            elif stage in stack:
                del stack[len(stack) - 1 - stack[::-1].index(stage)]
        return stack[-1] if stack else BETWEEN_STAGES

    # Silent gaps: split the active interval at the parked intervals, then look
    # for more than 30 s between consecutive visible frames in each piece.
    segments: list[tuple[datetime, datetime]] = []
    cursor = start
    for a, b in parked:
        if a > cursor:
            segments.append((cursor, a))
        cursor = max(cursor, b)
    if end > cursor:
        segments.append((cursor, end))
    visible = sorted(at for at, _, _ in inside)
    gaps: list[dict[str, Any]] = []
    for seg_start, seg_end in segments:
        points = [seg_start, *(t for t in visible if seg_start < t < seg_end), seg_end]
        for a, b in zip(points, points[1:], strict=False):
            seconds = (b - a).total_seconds()
            if seconds > SILENT_GAP_S:
                gaps.append(
                    {"start": _iso(a), "end": _iso(b), "seconds": seconds, "stage": owner(a)}
                )
    total_gap_s = sum(g["seconds"] for g in gaps)
    by_stage: dict[str, dict[str, Any]] = {}
    for g in gaps:
        row = by_stage.setdefault(g["stage"], {"count": 0, "total_s": 0.0})
        row["count"] += 1
        row["total_s"] += g["seconds"]
    for row in by_stage.values():
        row["share_of_active"] = _share(row["total_s"], active_s)

    # Time to first prose.
    first_started = next((at for at, n, _ in inside if n == "artefact.section_started"), None)
    first_prose = None
    if first_started is not None:
        delta = next(
            (at for at, n, _ in inside if n == "artefact.section_delta" and at >= first_started),
            None,
        )
        done = next(
            (
                at
                for at, n, _ in inside
                if n == "artefact.section_completed" and at >= first_started
            ),
            None,
        )
        first_prose = {
            "section_started_at": _iso(first_started),
            "to_first_delta_s": (delta - first_started).total_seconds() if delta else None,
            "to_first_completed_s": (done - first_started).total_seconds() if done else None,
        }

    # Tick rate per stage, over the stage's open intervals.
    live_ticks = [(at, t) for at, t in ticks if start <= at <= end]
    counts["ticks"] = sum(1 for _, t in live_ticks if not t["heartbeat"])
    counts["heartbeats"] = sum(1 for _, t in live_ticks if t["heartbeat"])
    tick_rate = []
    for stage, spans in intervals.items():
        open_s = sum((b - a).total_seconds() for a, b in spans)
        in_stage = [
            t
            for at, t in live_ticks
            if t["stage"] == stage and any(a <= at <= b for a, b in spans)
        ]
        n_ticks = sum(1 for t in in_stage if not t["heartbeat"])
        n_beats = sum(1 for t in in_stage if t["heartbeat"])
        tick_rate.append(
            {
                "stage": stage,
                "open_s": open_s,
                "ticks": n_ticks,
                "heartbeats": n_beats,
                "ticks_per_s": n_ticks / open_s if open_s > 0 else None,
                "heartbeats_per_s": n_beats / open_s if open_s > 0 else None,
            }
        )

    report.update(
        {
            "active_start": _iso(start),
            "active_end": _iso(end),
            "wall_s": wall_s,
            "parked_s": parked_s,
            "active_s": active_s,
            "parked": [{"start": _iso(a), "end": _iso(b)} for a, b in parked],
            "silent_gaps": {
                "threshold_s": SILENT_GAP_S,
                "count": len(gaps),
                "total_s": total_gap_s,
                "share_of_active": _share(total_gap_s, active_s),
                "by_stage": by_stage,
                "gaps": gaps,
            },
            "first_prose": first_prose,
            "tick_rate": tick_rate,
        }
    )
    return report


def _f1(x: float | None) -> str:
    return "" if x is None else f"{x:.1f}"


def _pct(x: float | None) -> str:
    return "" if x is None else f"{100 * x:.1f}%"


def format_capture_markdown(report: dict[str, Any]) -> str:
    """Render :func:`capture_report` as Markdown tables.

    Args:
        report: Output of :func:`capture_report` (``capture`` added by the caller).

    Returns:
        Markdown text.
    """
    healthy = {True: "yes", False: "no", None: "not given"}[report["healthy"]]
    md = [f"### Stream capture: {report.get('capture') or ''}\n"]
    if report["silent_gaps"] is None:
        md.append("No `run.status` frame in the capture: nothing to measure.\n")
        return "\n".join(md)
    gaps, dropped = report["silent_gaps"], report["dropped_ticks"]
    prose = report["first_prose"] or {}
    md += _table(
        ["measure", "value"],
        [
            ["run", str(report["walk"])],
            ["healthy run", healthy],
            ["final status", report["final_status"] or "none (capture ended first)"],
            ["active interval", f"{report['active_start']} to {report['active_end']}"],
            ["wall s / parked s / active s",
             f"{_f1(report['wall_s'])} / {_f1(report['parked_s'])} / {_f1(report['active_s'])}"],
            ["silent gaps (> 30 s)", str(gaps["count"])],
            ["silent s", _f1(gaps["total_s"])],
            ["silent share of active", _pct(gaps["share_of_active"])],
            ["first section started to first delta s", _f1(prose.get("to_first_delta_s"))],
            ["first section started to first completed s",
             _f1(prose.get("to_first_completed_s"))],
            ["dropped ticks", "" if dropped["delta"] is None else str(dropped["delta"])],
        ],
    )
    md.append("")
    md.append("#### Silent gaps by owning stage\n")
    md += _table(
        ["stage", "gaps", "silent s", "share of active"],
        [
            [stage, str(row["count"]), _f1(row["total_s"]), _pct(row["share_of_active"])]
            for stage, row in gaps["by_stage"].items()
        ],
    )
    md.append("")
    md.append("#### Each silent gap\n")
    md += _table(
        ["start", "end", "s", "stage"],
        [[g["start"], g["end"], _f1(g["seconds"]), g["stage"]] for g in gaps["gaps"]],
    )
    md.append("")
    md.append("#### Tick rate per stage\n")
    md += _table(
        ["stage", "open s", "ticks", "ticks/s", "heartbeats", "heartbeats/s"],
        [
            [
                r["stage"],
                _f1(r["open_s"]),
                str(r["ticks"]),
                "" if r["ticks_per_s"] is None else f"{r['ticks_per_s']:.3f}",
                str(r["heartbeats"]),
                "" if r["heartbeats_per_s"] is None else f"{r['heartbeats_per_s']:.3f}",
            ]
            for r in report["tick_rate"]
        ],
    )
    md.append("")
    c = report["counts"]
    md.append(
        f"Lines: {c['frames']} frames ({c['ticks']} ticks and {c['heartbeats']} heartbeats "
        f"in the active interval), {c['comments']} keep-alive comments, {c['reconnects']} "
        f"reconnects, {c['unreadable_lines']} unreadable."
    )
    return "\n".join(md) + "\n"


# --- Command line ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Per-stage wall time of Policy Atlas runs from the local database "
        "(read-only). See the module docstring for the definitions."
    )
    parser.add_argument("--run-id", action="append", default=[], help="capability run id or prefix")
    parser.add_argument("--task-id", action="append", default=[], help="task id")
    parser.add_argument("--since", help="ISO date: runs started at or after it")
    parser.add_argument(
        "--capability", choices=["evidence_search", "options_scoping"], help="only this capability"
    )
    parser.add_argument("--route", default="", help="route label to show, e.g. bedrock")
    parser.add_argument(
        "--logs", action="append", default=[], help="server log file or folder (repeatable)"
    )
    parser.add_argument("--database-url", help="SQLAlchemy URL (default: $DATABASE_URL)")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--out", help="write to this file instead of stdout")
    parser.add_argument(
        "--capture", metavar="FILE", help="a stream_capture.py recording (no database)"
    )
    parser.add_argument(
        "--healthy", choices=["true", "false"], help="with --capture: the run was healthy"
    )
    args = parser.parse_args(argv)
    if args.capture:
        if args.run_id or args.task_id or args.since or args.logs:
            parser.error("--capture reads one recording; drop the database and log flags")
        records, unreadable = read_capture(args.capture)
        healthy = None if args.healthy is None else args.healthy == "true"
        capture = {"capture": Path(args.capture).name}
        capture |= capture_report(records, healthy, unreadable)
        _write(
            json.dumps(capture, indent=1) + "\n"
            if args.format == "json"
            else format_capture_markdown(capture),
            args.out,
        )
        return 0
    if args.healthy is not None:
        parser.error("--healthy goes with --capture")
    try:
        where, params = build_selection(args.run_id, args.task_id, args.since, args.capability)
    except ValueError as exc:
        parser.error(str(exc))
    runs = fetch_runs(args.database_url, where, params)
    for prefix in args.run_id:
        if not any(r["capability_run_id"].startswith(prefix.lower()) for r in runs):
            print(f"warning: no top-level capability run matches {prefix!r}", file=sys.stderr)
    logs = read_logs(args.logs) if args.logs else None
    report = build_report(runs, logs, args.route)
    text = (
        json.dumps(report, indent=1, default=str) + "\n"
        if args.format == "json"
        else format_markdown(report)
    )
    _write(text, args.out)
    return 0


def _write(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
