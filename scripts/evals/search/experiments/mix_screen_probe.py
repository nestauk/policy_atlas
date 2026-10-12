"""Search then screen one question with the production order, and report how each
stratum of the mix fares at screening.

The paper pool is ordered by ``pool.rank_mix`` (task 052): a round-robin over three
strata, relevant (rank fusion over the query result lists and the "cites the seeds"
order), seminal (most cited by the seed set) and novel (the last five years). This
script runs the real search (OpenAlex only), notes which stratum placed each paper
that made the cut, runs the real screen, and reports the screened-in share per
stratum, per origin and per year band. The question it answers: are the novel
papers noise, or do they pass the screen like the rest?

Every database write is rolled back. No abstracts are saved; the screen's own
one-line reasons are.

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/mix_screen_probe.py \\
        "QUESTION" OUT_PREFIX [--depth rapid]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "checks"))
import _bootstrap  # noqa: E402,F401
from engine import (  # noqa: E402
    GENERATION_BACKENDS,
    _RecordingBackend,
    _seed_run,
    _seed_scope,
    _seed_task,
)
from sqlalchemy import select  # noqa: E402

from policy_atlas.core import tracing  # noqa: E402
from policy_atlas.core.db import get_engine  # noqa: E402
from policy_atlas.core.schema import event_log, source_snapshot, task_source_snapshot  # noqa: E402
from policy_atlas.evidence_search.assess.screen import (  # noqa: E402
    ScreenContext,
    effective_screen_rows,
    screen_sources,
)
from policy_atlas.evidence_search.assess.screening_backend import OpenAIScreeningBackend  # noqa: E402
from policy_atlas.evidence_search.sourcing import pool, search_loop  # noqa: E402
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext  # noqa: E402
from policy_atlas.evidence_search.sourcing.search_live import live_search_backends  # noqa: E402

STRATA = ("relevant", "seminal", "novel")


def placed_by(
    cands: list[Any], lists: list[list[dict[str, Any]]], year: int
) -> dict[str, str]:
    """Replay the mix's round-robin and name the stratum that placed each paper."""
    strata = pool.mix_strata(cands, lists, novel_from_year=year)
    placed: dict[str, str] = {}
    seen: set[int] = set()
    cursors = [
        (name, iter(stratum)) for name, stratum in zip(STRATA, strata, strict=True)
    ]
    while cursors:
        for item in list(cursors):
            name, cursor = item
            for candidate in cursor:
                if id(candidate) not in seen:
                    seen.add(id(candidate))
                    placed[candidate.openalex_id or ""] = name
                    break
            else:
                cursors.remove(item)
    return placed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("out_prefix")
    parser.add_argument("--depth", default="rapid")
    args = parser.parse_args()

    captured: dict[str, Any] = {}
    real_mix = pool.rank_mix

    def spy(
        cands: list[Any], lists: list[list[dict[str, Any]]], **kw: Any
    ) -> list[Any]:
        captured["placed"] = placed_by(cands, lists, kw["novel_from_year"])
        captured["signals"] = {
            c.openalex_id: {
                "queries": sum(
                    any(pool.record_short_id(r) == c.openalex_id for r in records)
                    for records in lists
                ),
                "inset": c.inset,
                "wcoupling": c.wcoupling,
                "cited_by": c.cited_by_count,
            }
            for c in cands
        }
        return real_mix(cands, lists, **kw)

    search_loop.pool.rank_mix = spy
    client = tracing.get_langfuse()
    engine = get_engine()
    calls: list[dict[str, Any]] = []
    lock = threading.Lock()
    started = time.monotonic()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            task_id = _seed_task(conn)
            scope_id = _seed_scope(conn, task_id, args.question)
            counts = search_loop.run_search(
                conn,
                task_id=task_id,
                run_id=_seed_run(conn, task_id),
                context=AcquireContext(
                    scope_id=scope_id,
                    intent=args.question,
                    context={"search": {"depth": args.depth, "filters": {}}},
                ),
                backends=[
                    _RecordingBackend(b, calls, client, lock=lock)
                    for b in live_search_backends()
                    if b.name == "openalex"
                ],
                generation_backend=GENERATION_BACKENDS["shared"](
                    langfuse_client=client
                ),
            )
            searched = time.monotonic()
            screen_sources(
                conn,
                task_id=task_id,
                run_id=_seed_run(conn, task_id),
                context=ScreenContext(
                    scope_id=scope_id, intent=args.question, context={}
                ),
                screening_backend=OpenAIScreeningBackend(langfuse_client=client),
            )
            screened = time.monotonic()
            rows_q = effective_screen_rows()
            rows = conn.execute(
                select(
                    task_source_snapshot.c.task_source_snapshot_id,
                    source_snapshot.c.metadata,
                    rows_q.c.status,
                    rows_q.c.screen_decision_confidence,
                )
                .join(
                    source_snapshot,
                    source_snapshot.c.source_snapshot_id
                    == task_source_snapshot.c.source_snapshot_id,
                )
                .outerjoin(
                    rows_q,
                    (
                        rows_q.c.task_source_snapshot_id
                        == task_source_snapshot.c.task_source_snapshot_id
                    )
                    & (rows_q.c.evidence_scope_id == scope_id),
                )
                .where(task_source_snapshot.c.task_id == task_id)
            ).all()
            events = conn.execute(
                select(event_log.c.event_type, event_log.c.payload)
                .where(event_log.c.task_id == task_id)
                .where(
                    event_log.c.event_type.in_(("source.acquired", "source.screened"))
                )
                .order_by(event_log.c.sequence)
            ).all()
        finally:
            trans.rollback()  # scaffolding only, never kept
    tracing.flush(client)

    origin: dict[str, str | None] = {}
    reason: dict[str, str | None] = {}
    for event_type, payload in events:
        key = str(payload.get("task_source_snapshot_id"))
        if event_type == "source.acquired":
            origin[key] = payload.get("query_origin")
        else:
            reps = payload.get("reps") or []
            reason[key] = reps[0].get("reason") if reps else None

    placed = captured["placed"]
    signals = captured["signals"]
    papers = []
    for tss, metadata, status, confidence in rows:
        work_id = pool.short_id(metadata.get("backend_record_id")) or ""
        papers.append(
            {
                "id": work_id,
                "title": metadata.get("title"),
                "year": metadata.get("year"),
                "stratum": placed.get(work_id, "tail"),
                "found_by": origin.get(str(tss)),
                **signals.get(work_id, {}),
                "screen": status,
                "confidence": confidence,
                "reason": reason.get(str(tss)),
            }
        )

    def share(rows_: list[dict[str, Any]]) -> str:
        if not rows_:
            return "—"
        kept = sum(r["screen"] == "relevant" for r in rows_)
        return f"{kept}/{len(rows_)} ({100 * kept / len(rows_):.0f}%)"

    novel_year = date.today().year - pool.NOVEL_YEARS
    by_stratum = defaultdict(list)
    by_origin = defaultdict(list)
    by_band = defaultdict(list)
    for p in papers:
        by_stratum[p["stratum"]].append(p)
        by_origin[p["found_by"]].append(p)
        band = "novel years" if (p["year"] or 0) >= novel_year else "older"
        by_band[band].append(p)

    lines = [f"# Mix strata at the screen: {args.question}\n"]
    lines.append(
        f"Run {datetime.now(UTC).isoformat(timespec='seconds')}. Depth `{args.depth}`; "
        f"{len(papers)} papers acquired (OpenAlex only), search {searched - started:.0f} s, "
        f"screen {screened - searched:.0f} s. Screened in overall: {share(papers)}.\n"
    )
    lines.append("## Screened in, by the stratum that placed the paper\n")
    lines.append(
        "| stratum | screened in | median queries | median in-set |\n|---|---:|---:|---:|"
    )
    for name in (*STRATA, "tail"):
        rows_ = by_stratum.get(name, [])
        if rows_:
            qs = sorted(r.get("queries", 0) for r in rows_)
            ins = sorted(r.get("inset", 0) for r in rows_)
            lines.append(
                f"| {name} | {share(rows_)} | {qs[len(qs) // 2]} | {ins[len(ins) // 2]} |"
            )
    lines.append("\n## Screened in, by publication year band\n")
    lines.append("| band | screened in |\n|---|---:|")
    for name, rows_ in sorted(by_band.items()):
        lines.append(f"| {name} | {share(rows_)} |")
    lines.append("\n## Screened in, by the call that first returned the paper\n")
    lines.append("| origin | screened in |\n|---|---:|")
    for name, rows_ in sorted(by_origin.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {name} | {share(rows_)} |")
    lines.append("\n## The novel stratum, paper by paper\n")
    for p in sorted(
        by_stratum.get("novel", []), key=lambda r: r["screen"] != "relevant"
    ):
        mark = "✅" if p["screen"] == "relevant" else "❌"
        lines.append(
            f"- {mark} {p['year']} · {p['title']} · queries {p.get('queries')} · "
            f"in-set {p.get('inset')} · {p['found_by']} — {p['reason']}"
        )
    lines.append("\n## Screened out, by stratum\n")
    for name in (*STRATA, "tail"):
        outs = [p for p in by_stratum.get(name, []) if p["screen"] != "relevant"]
        if outs:
            lines.append(f"\n### {name}\n")
            for p in outs:
                lines.append(
                    f"- {p['year']} · {p['title']} · {p['found_by']} — {p['reason']}"
                )

    out = Path(args.out_prefix)
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    out.with_suffix(".json").write_text(
        json.dumps(
            {
                "question": args.question,
                "depth": args.depth,
                "search": counts.get("search"),
                "usage": counts.get("usage_totals"),
                "papers": papers,
            },
            indent=1,
            default=str,
        )
    )
    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main()
