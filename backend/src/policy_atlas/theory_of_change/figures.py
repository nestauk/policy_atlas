"""The size of change behind each link: the ``toc_figures`` step (task 054, C37).

After the judge, one small call (``toc_figures_v1``, fast tier) per judgement
that supports or refutes a link reads the same title and abstract the judge
read and returns at most three figures. Code keeps a figure only when its quote
is in the text and its number is in the quote, parses the numbers with the
Evidence search's rules (``quote_verify._parse_numeric``) and drops a range
whose lower end is above its upper end (``quote_verify._apply_bounds``). A
judgement whose call succeeded is stamped, so a later walk does not ask again
for the same wording. Figures are stored as reported and never pooled.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    source_snapshot,
    task_source_snapshot,
    toc_figure,
    toc_item_evidence,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.extract.quote_verify import _apply_bounds, _parse_numeric
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check import (
    Document,
    _call,
    _map_traced,
    _outcome_value,
    _year,
    neighbour_lines,
    quote_found,
)
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.evidence.figures_prompt import (
    FIGURES_PER_DOCUMENT,
    FiguresResponse,
    FigureWire,
)
from policy_atlas.theory_of_change.graph import item_hash

log = structlog.get_logger()

#: Figures calls in flight at once (small calls, like the judge's).
FIGURES_WORKERS = 16

# Thousands separators between digits: "40,000", "40 000", "40 000".
_THOUSANDS = re.compile(r"(?<=\d)[,\s   ](?=\d{3}(?!\d))")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def canonical_numbers(text: str) -> str:
    """Text with numbers written one way: ``-`` for the unicode minus, ``.`` for
    the middle dot ("1·05"), no thousands separators, no ``%``."""
    text = text.replace("−", "-").replace("·", ".")
    return _THOUSANDS.sub("", text).replace("%", "")


def _trim(number: str) -> str:
    """``60.0`` → ``60``, ``1.50`` → ``1.5``."""
    return number.rstrip("0").rstrip(".") if "." in number else number


def number_in_quote(value: float | int | str, quote: str) -> bool:
    """Whether the figure's number appears in its quote (C37).

    Both sides are normalised (:func:`canonical_numbers`, spaces, a trailing
    ``.0``) and compared as whole numbers, without sign, so "6" does not match
    inside "60" and "-0.3" matches "fell by 0.3".

    Args:
        value: The number as the model gave it.
        quote: The figure's quote.

    Returns:
        True when the quote contains the number.
    """
    found = _NUMBER.search(canonical_numbers(str(value)).replace(" ", ""))
    if found is None:
        return False
    return _trim(found.group()) in {_trim(n) for n in _NUMBER.findall(canonical_numbers(quote))}


def _as_text(raw: float | int | str | None) -> str | None:
    if raw is None or isinstance(raw, bool):
        return None
    text = raw.strip() if isinstance(raw, str) else _trim(str(raw))
    return text or None


def _parsed(field: str, raw: float | int | str | None) -> float | int | None:
    """One numeric field by the Evidence search's rule, after the same normalising."""
    if isinstance(raw, str):
        raw = canonical_numbers(raw).replace(" ", "")
    return _parse_numeric(field, raw, {}, [], [])


@dataclass(frozen=True)
class CheckedFigure:
    """A figure that passed the checks, ready to store, and whether its range was dropped."""

    values: dict[str, Any]
    range_dropped: bool


def check_figure(figure: FigureWire, text: str) -> CheckedFigure | str:
    """Check one figure against the text the judge read.

    Args:
        figure: The model's figure.
        text: The document's title and abstract.

    Returns:
        The values to store, or the reason it was dropped: ``quote`` (not in
        the text) or ``number`` (the number is not in the quote).
    """
    if not quote_found(text, figure.quote):
        return "quote"
    if not number_in_quote(figure.effect_size, figure.quote):
        return "number"
    stats: dict[str, float | int | None] = {
        "effect_size": _parsed("effect_size", figure.effect_size),
        "ci_lower": _parsed("ci_lower", figure.ci_lower),
        "ci_upper": _parsed("ci_upper", figure.ci_upper),
        "n": _parsed("n", figure.n),
        "k": _parsed("k", figure.k),
        "p_value": None,
        "i_squared": None,
        "tau2": None,
    }
    unclear: list[str] = []
    _apply_bounds(stats, {}, unclear)
    dropped = "ci_lower" in unclear
    return CheckedFigure(
        values={
            "box": figure.box,
            "measure": figure.measure.strip(),
            "value_text": _as_text(figure.effect_size) or "",
            "value": stats["effect_size"],
            "ci_lower_text": None if dropped else _as_text(figure.ci_lower),
            "ci_lower": stats["ci_lower"],
            "ci_upper_text": None if dropped else _as_text(figure.ci_upper),
            "ci_upper": stats["ci_upper"],
            "unit": _as_text(figure.unit),
            "effect_size_type": figure.effect_size_type,
            "population": _as_text(figure.population),
            "place": _as_text(figure.place),
            "year": _as_text(figure.year),
            "n": stats["n"],
            "k": stats["k"],
            "quote": figure.quote,
            "statement": _as_text(figure.statement),
        },
        range_dropped=dropped,
    )


def _documents(
    conn: Connection, task_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, Document]:
    """The judged text (title and abstract) of each document, by id."""
    if not ids:
        return {}
    rows = conn.execute(
        select(task_source_snapshot.c.task_source_snapshot_id, source_snapshot.c.metadata)
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(ids))
    )
    out: dict[uuid.UUID, Document] = {}
    for tss, metadata in rows:
        meta = metadata or {}
        out[tss] = Document(
            tss_id=tss,
            title=str(meta.get("title") or ""),
            year=_year(meta),
            abstract=str(meta.get("abstract") or ""),
            evidence_type=None,
            score=None,
        )
    return out


@dataclass(frozen=True)
class _Job:
    evidence_id: uuid.UUID
    link_id: uuid.UUID
    item_hash: str
    source: str
    target: str
    #: The link sentence, the judge's support and quote, and the steps around it (fit review).
    step: str
    support: str
    judge_quote: str
    neighbours: str
    document: Document


def toc_figures_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Find the size of change behind each judged link (C37).

    Reads every judgement of a link's current wording that supports or
    refutes it and has no figures stamp yet; one call each, in parallel.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        Call and figure counts, the drops by reason, and the usage totals.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, _rows = store.load_graph(conn, task_id)
    current = {
        key: item_hash(link, graph.boxes[link.source].text, graph.boxes[link.target].text)
        for key, link in graph.links.items()
    }
    judged = [
        row
        for row in conn.execute(
            select(
                toc_item_evidence.c.evidence_id,
                toc_item_evidence.c.link_id,
                toc_item_evidence.c.task_source_snapshot_id,
                toc_item_evidence.c.item_hash,
                toc_item_evidence.c.figures_checked_at,
                toc_item_evidence.c.support,
                toc_item_evidence.c.quote,
            )
            .where(toc_item_evidence.c.task_id == task_id)
            .where(toc_item_evidence.c.support != "not_about")
            .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
        )
        if current.get(str(row.link_id)) == row.item_hash
    ]
    todo = [row for row in judged if row.figures_checked_at is None]
    documents = _documents(conn, task_id, {row.task_source_snapshot_id for row in todo})
    jobs = [
        _Job(
            evidence_id=row.evidence_id,
            link_id=row.link_id,
            item_hash=row.item_hash,
            source=graph.boxes[graph.links[str(row.link_id)].source].text,
            target=graph.boxes[graph.links[str(row.link_id)].target].text,
            step=graph.links[str(row.link_id)].sentence,
            support=row.support,
            judge_quote=row.quote or "",
            neighbours=neighbour_lines(graph, str(row.link_id)),
            document=documents[row.task_source_snapshot_id],
        )
        for row in todo
        if row.task_source_snapshot_id in documents
    ]

    def run_job(job: _Job) -> Any:
        return _call(
            "toc_figures",
            lambda: backend.figures(
                source=job.source,
                target=job.target,
                step=job.step,
                support=job.support,
                judge_quote=job.judge_quote,
                neighbours=job.neighbours,
                population=plan.target_population,
                place=plan.where or "not stated",
                title=job.document.title,
                year=job.document.year,
                text=job.document.text,
            ),
            "toc_figures",
        )

    usage = UsageAccumulator()
    outcomes = _map_traced(run_job, jobs, FIGURES_WORKERS)
    now = datetime.now(UTC)
    stored = failed = no_quote = no_number = ranges_dropped = 0
    for job, outcome in zip(jobs, outcomes, strict=True):
        response: FiguresResponse | None = _outcome_value(outcome, usage)
        if response is None:
            failed += 1  # not stamped: the next walk asks again
            continue
        for figure in response.figures[:FIGURES_PER_DOCUMENT]:
            checked = check_figure(figure, job.document.text)
            if checked == "quote":
                no_quote += 1
                continue
            if checked == "number":
                no_number += 1
                continue
            assert isinstance(checked, CheckedFigure)
            ranges_dropped += checked.range_dropped
            conn.execute(
                toc_figure.insert().values(
                    figure_id=uuid.uuid4(),
                    task_id=task_id,
                    link_id=job.link_id,
                    task_source_snapshot_id=job.document.tss_id,
                    item_hash=job.item_hash,
                    created_at=now,
                    **checked.values,
                )
            )
            stored += 1
        conn.execute(
            update(toc_item_evidence)
            .where(toc_item_evidence.c.evidence_id == job.evidence_id)
            .values(figures_checked_at=now)
        )
    summary = {
        "calls": len(jobs),
        "failed_calls": failed,
        "already_done": len(judged) - len(todo),
        "figures": stored,
        "dropped_quote_not_in_text": no_quote,
        "dropped_number_not_in_quote": no_number,
        "ranges_dropped": ranges_dropped,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_figures.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary
