"""Detailed information as a short narrative report: the ``toc_report`` step (task 054, C38).

One frontier call (``toc_report_v1``) writes the prose; code does the rest:

- **Inputs.** The plan; the theory with box and link codes, each link's verdict
  and evidence sentence; the weakest critical links; the assumption rows
  (:func:`assumption_rows`); and the numbered sources behind them.
- **Checks.** Every box or link code the text cites must exist, and every
  ``[n]`` must be a listed source that bears on a link the same paragraph or
  row names, or on a link of that pathway. Anything else is removed and
  counted; a row the model gave no reason gets a fixed one.
- **Assembly.** Sources are renumbered by first citation (Summary, pathways,
  assumption rows, tests), uncited ones dropped; code writes the source list
  and the method note.

The assembled report is the step's ``component.completed`` payload, as the
summary's header paragraphs are: the read API serves the latest one.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.api.readmodels.repository import _authorships, _url, _venue
from policy_atlas.core.model_routes import route
from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check import (
    _call,
    _outcome_value,
    _year,
    appraisals_for,
    counted_judgements,
    link_verdict_of,
    row_judgement,
    screened_documents,
)
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.evidence.grade import (
    VERDICT_LABELS,
    VERDICT_ORDER,
    Verdict,
    weight,
)
from policy_atlas.theory_of_change.report_prompt import TOC_REPORT_PROMPT_VERSION, ReportResponse

log = structlog.get_logger()

#: Assumption rows in the table (C38).
MIN_ROWS = 5
MAX_ROWS = 12
#: Weakest links the summary names.
WEAKEST_LINKS = 3
#: What a row says when the model gave it no reason.
ROW_FALLBACK = "See the evidence on this link."
#: Until the accountability ceiling can be moved (increment 2), it sits after outputs.
DIRECTLY_INFLUENCED = "outputs"
#: Words of a source's quote the model sees as its finding.
FINDING_WORDS = 30

_CODE = re.compile(r"#\d+|\b[APSLIF]\d+\b")
_CITE = re.compile(r"\[(\d+)\]")
_EMPTY_BRACKETS = re.compile(r"\(\s*(?:[→,;-]\s*)*\)")


@dataclass(frozen=True)
class LinkFacts:
    """One link as the report reads it."""

    key: str
    code: str
    source_code: str
    target_code: str
    target_layer: str
    sentence: str
    verdict: Verdict
    evidence_sentence: str | None
    critical: bool
    conditions: list[str]
    on_failure: bool
    on_success: bool


def assumption_rows(
    links: list[LinkFacts], sources_of: dict[str, list[int]]
) -> list[dict[str, Any]]:
    """The Assumptions and evidence rows (C38), 5 to 12, critical first, then worst verdict.

    One row per condition of the critical link and of every link that is not
    Confident (kind ``assumption``), and one per link on a failure pathway
    (kind ``risk``, its sentence). When that gives fewer than five rows, the
    conditions of Confident links fill up to five, in link order.

    Args:
        links: Every link, in graph order.
        sources_of: Link code → the numbers of its supporting or refuting sources.

    Returns:
        Rows with ``key`` (``r1``...), ``code`` (the link, or the failure box
        for a risk), ``link``, ``statement``, ``kind``, ``verdict`` (label)
        and ``sources``.
    """
    order = {link.key: i for i, link in enumerate(links)}

    def row(
        link: LinkFacts, statement: str, kind: str
    ) -> tuple[tuple[int, int, int], dict[str, Any]]:
        code = (
            link.target_code
            if kind == "risk" and link.target_layer == "failure_outcome"
            else link.code
        )
        return (
            (0 if link.critical else 1, VERDICT_ORDER.index(link.verdict), order[link.key]),
            {
                "code": code,
                "link": link.code,
                "statement": statement,
                "kind": kind,
                "verdict": VERDICT_LABELS[link.verdict],
                "sources": sources_of.get(link.code, []),
            },
        )

    main: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    spare: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for link in links:
        target = main if link.critical or link.verdict != "confident" else spare
        target.extend(row(link, condition, "assumption") for condition in link.conditions)
        if link.on_failure:
            main.append(row(link, link.sentence, "risk"))
    chosen = [r for _, r in sorted(main, key=lambda pair: pair[0])]
    chosen += [r for _, r in spare][: max(0, MIN_ROWS - len(chosen))]
    return [{"key": f"r{i}", **r} for i, r in enumerate(chosen[:MAX_ROWS], start=1)]


def weakest_links(links: list[LinkFacts]) -> list[str]:
    """The critical links, then the lowest-verdict links on kept success pathways; 3 at most."""
    rank = {link.key: VERDICT_ORDER.index(link.verdict) for link in links}
    critical = sorted((link for link in links if link.critical), key=lambda link: rank[link.key])
    success = sorted((link for link in links if link.on_success), key=lambda link: rank[link.key])
    return list(dict.fromkeys(link.code for link in [*critical, *success]))[:WEAKEST_LINKS]


@dataclass
class Removals:
    """What the checks took out of the model's text."""

    codes: int = 0
    citations: int = 0
    rows: int = 0

    def payload(self) -> dict[str, int]:
        return {
            "removed_codes": self.codes,
            "removed_citations": self.citations,
            "removed_rows": self.rows,
        }


@dataclass
class TextChecker:
    """Removes unknown codes and citations that do not bear on the text's links."""

    codes: set[str]
    #: Source number → the link codes it bears on.
    sources: dict[int, set[str]]
    removals: Removals = field(default_factory=Removals)

    def __call__(self, text: str, links: Iterable[str] = ()) -> str:
        """Check one paragraph or row.

        Args:
            text: The model's text.
            links: Link codes the text may also cite for (its pathway's or row's).

        Returns:
            The text without unknown codes and unsupported ``[n]`` markers.
        """

        def code(match: re.Match[str]) -> str:
            if match.group() in self.codes:
                return match.group()
            self.removals.codes += 1
            return ""

        text = _CODE.sub(code, text)
        allowed = set(links) | {c for c in _CODE.findall(text) if c.startswith("#")}

        def cite(match: re.Match[str]) -> str:
            if self.sources.get(int(match.group(1)), set()) & allowed:
                return match.group()
            self.removals.citations += 1
            return ""

        text = _CITE.sub(cite, text)
        # Tidy what a removal leaves: "(S1 → )" → "(S1)", "()" → "".
        text = re.sub(r"\s*→\s*\)", ")", re.sub(r"\(\s*→\s*", "(", text))
        text = _EMPTY_BRACKETS.sub("", text)
        return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"\s{2,}", " ", text)).strip()


def renumber(report: dict[str, Any], sources: list[dict[str, Any]]) -> None:
    """Number sources by first citation and keep only cited ones, in place.

    Citation order: the Summary, the pathways, the assumption rows (each row's
    reason, then its source list), the tests.

    Args:
        report: The assembled sections, with ``[n]`` in their texts and
            ``sources`` lists on the rows.
        sources: The numbered sources (``n`` and the rest).
    """
    summary, rows = report["summary"], report["assumptions"]
    texts: list[tuple[dict[str, Any], str]] = [
        (report, key) for key in ("title", "summary_text") if key in report
    ]
    texts += [(summary, key) for key in ("if_then_because", "context", "weakest_links")]
    texts += [(p, key) for p in report["pathways"] for key in ("title", "paragraph")]
    first: dict[int, int] = {}

    def see(numbers: Iterable[int]) -> None:
        for n in numbers:
            first.setdefault(n, len(first) + 1)

    for holder, key in texts:
        see(int(n) for n in _CITE.findall(holder[key]))
    for row in rows:
        see(int(n) for n in _CITE.findall(row["why"]))
        see(row["sources"])
    tests = [
        (t, key) for t in report["tests"] for key in ("question", "indicator", "test_and_learn")
    ]
    for holder, key in tests:
        see(int(n) for n in _CITE.findall(holder[key]))

    def rewrite(text: str) -> str:
        return _CITE.sub(lambda m: f"[{first[int(m.group(1))]}]", text)

    for holder, key in [*texts, *[(row, "why") for row in rows], *tests]:
        holder[key] = rewrite(holder[key])
    for row in rows:
        row["sources"] = [first[n] for n in row["sources"]]
    by_n = {source["n"]: source for source in sources}
    report["sources"] = [
        {**by_n[old], "n": new} for old, new in sorted(first.items(), key=lambda pair: pair[1])
    ]


def method_note(when: datetime, judge_model: str) -> str:
    """The Sources and method note, written by code (C38)."""
    return (
        f"Generated by Policy Atlas with AI on {when.day} {when:%B %Y} from OpenAlex and "
        f"Overton searches for each step; evidence judged by {judge_model}; not yet reviewed "
        "by a person. 'Too little evidence' means none was found in this search, not that "
        "none exists."
    )


def _family(name: str) -> str:
    return name.split()[-1] if name.split() else name


def citation(
    *, authors: list[str], year: int | None, title: str, venue: str | None, kind: str | None
) -> str:
    """ "Boyland et al. (2016) Advertising as a cue to consume. Appetite. Systematic review."."""
    who = (
        f"{_family(authors[0])} et al."
        if len(authors) > 1
        else (_family(authors[0]) if authors else "")
    )
    when = f"({year})" if year else ""
    head = " ".join(part for part in (who, when) if part)
    parts = [
        f"{head} {title}".strip() if head else title,
        venue,
        kind.capitalize() if kind else None,
    ]
    return " ".join(f"{part.rstrip('.')}." for part in parts if part)


def _short(authors: list[str], year: int | None, title: str, venue: str | None) -> str:
    who = (
        f"{_family(authors[0])} et al."
        if len(authors) > 1
        else (_family(authors[0]) if authors else "")
    )
    return ", ".join(part for part in (f"{who} {year or ''}".strip(), title, venue) if part)


def _metadata(conn: Connection, task_id: uuid.UUID, ids: set[uuid.UUID]) -> dict[uuid.UUID, Any]:
    if not ids:
        return {}
    return {
        tss: (metadata or {}, locator)
        for tss, metadata, locator in conn.execute(
            select(
                task_source_snapshot.c.task_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(task_source_snapshot.c.task_source_snapshot_id.in_(ids))
        )
    }


def toc_report_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Write Detailed information as a short narrative report (C38).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        now: The clock the method note reads (a test can fix it).

    Returns:
        ``report`` (the five sections, assembled), the removal counts, the
        prompt version and the usage totals.

    Raises:
        RuntimeError: If the report call failed.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, rows = store.load_graph(conn, task_id)
    counted = counted_judgements(conn, task_id=task_id)
    every = [row for group in counted.values() for row in group]
    appraisals = appraisals_for(conn, task_id=task_id, evidence_rows=every)
    kept = [p for p in graph.pathways if p.status == "kept"]
    on_failure = {key for p in kept if p.kind == "failure" for key in p.links}
    on_success = {key for p in kept if p.kind == "success" for key in p.links}
    box_code = {key: rows.boxes[key].code or key for key in graph.boxes}
    facts = [
        LinkFacts(
            key=key,
            code=rows.links[key].code or key,
            source_code=box_code[link.source],
            target_code=box_code[link.target],
            target_layer=graph.boxes[link.target].layer,
            sentence=link.sentence,
            verdict=link_verdict_of(counted.get(key, []), appraisals).verdict,
            evidence_sentence=rows.links[key].evidence_sentence,
            critical=bool(rows.links[key].critical),
            conditions=list(link.conditions),
            on_failure=key in on_failure,
            on_success=key in on_success,
        )
        for key, link in graph.links.items()
    ]
    by_code = {f.code: f for f in facts}
    fact_of = {f.key: f for f in facts}
    path_links = {p.key: [fact_of[k].code for k in p.links if k in fact_of] for p in kept}

    # Sources: documents that support or refute the rows' and pathways' links, heaviest first.
    preliminary = assumption_rows(facts, {})
    link_order = list(
        dict.fromkeys(
            [row["link"] for row in preliminary] + [c for p in kept for c in path_links[p.key]]
        )
    )
    metadata = _metadata(conn, task_id, {row.task_source_snapshot_id for row in every})
    types = {
        doc.tss_id: doc.evidence_type
        for doc in screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    }
    numbers: dict[uuid.UUID, int] = {}
    bears: dict[int, set[str]] = {}
    sources: list[dict[str, Any]] = []
    for code in link_order:
        group = [
            r for r in counted.get(by_code[code].key, []) if row_judgement(r).support != "not_about"
        ]
        group.sort(
            key=lambda r: -weight(appraisals.get(str(r.task_source_snapshot_id)), row_judgement(r))
        )
        for r in group:
            tss = r.task_source_snapshot_id
            if tss not in numbers:
                meta, locator = metadata.get(tss, ({}, None))
                authors = [a.name for a in _authorships(meta)]
                title, year, venue = str(meta.get("title") or ""), _year(meta), _venue(meta)
                numbers[tss] = len(numbers) + 1
                sources.append(
                    {
                        "n": numbers[tss],
                        "citation": citation(
                            authors=authors,
                            year=year,
                            title=title,
                            venue=venue,
                            kind=types.get(tss),
                        ),
                        "short": _short(authors, year, title, venue),
                        "url": _url(meta, locator),
                        "title": title,
                        "authors": authors,
                        "year": year,
                        "venue": venue,
                        # The judgement behind the number: a marker opens its quote in context.
                        "evidence_id": str(r.evidence_id),
                        "quote": r.quote,
                        "finding": " ".join((r.quote or "").split()[:FINDING_WORDS]),
                    }
                )
            bears.setdefault(numbers[tss], set()).add(code)
    sources_of: dict[str, list[int]] = {}
    for n, codes in bears.items():
        for code in codes:
            sources_of.setdefault(code, []).append(n)
    table = assumption_rows(facts, {code: sorted(ns) for code, ns in sources_of.items()})

    pkey = {p.key: f"p{i}" for i, p in enumerate(kept, start=1)}
    theory = {
        "boxes": [
            {"code": box_code[key], "layer": box.layer, "text": box.text}
            for key, box in graph.boxes.items()
        ],
        "links": [
            {
                "code": f.code,
                "from": f.source_code,
                "to": f.target_code,
                "sentence": f.sentence,
                "verdict": VERDICT_LABELS[f.verdict],
                "evidence_sentence": f.evidence_sentence,
                "critical": f.critical,
            }
            for f in facts
        ],
        "pathways": [
            {
                "key": pkey[p.key],
                "kind": p.kind,
                "label": rows.pathways[p.key].label,
                "links": path_links[p.key],
            }
            for p in kept
        ],
        "weakest_critical_links": weakest_links(facts),
    }
    plan_fields = {
        "goal": plan.intended_change,
        "intervention": plan.intervention,
        "population": plan.target_population,
        "place": plan.where,
        "time_horizon": plan.time_horizon,
        "setting": plan.context,
    }
    usage = UsageAccumulator()
    response: ReportResponse | None = _outcome_value(
        _call(
            "toc_report",
            lambda: backend.report(
                plan={k: v for k, v in plan_fields.items() if v},
                theory=theory,
                rows=[
                    {k: row[k] for k in ("key", "link", "statement", "kind", "verdict", "sources")}
                    for row in table
                ],
                sources=[
                    {
                        "n": s["n"],
                        "citation": s["short"],
                        "links": sorted(bears[s["n"]]),
                        "finding": s["finding"],
                    }
                    for s in sources
                ],
            ),
            "toc_report",
        ),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_report: the report call failed")

    check = TextChecker(codes=set(box_code.values()) | set(by_code), sources=bears)
    links_of = {pkey[p.key]: path_links[p.key] for p in kept}
    failure_links = [c for p in kept if p.kind == "failure" for c in path_links[p.key]]
    kind_of = {pkey[p.key]: p.kind for p in kept}
    pathways = []
    for item in response.pathways:
        if item.pathway not in links_of:
            check.removals.rows += 1
            continue
        # Failure pathways may share one "How it could fail" paragraph.
        allowed = failure_links if kind_of[item.pathway] == "failure" else links_of[item.pathway]
        pathways.append(
            {"title": check(item.title, allowed), "paragraph": check(item.paragraph, allowed)}
        )
    reasons = {item.row: item.why for item in response.assumption_reasons}
    assumptions = []
    for row in table:
        why = check(reasons.get(row["key"], ""), [row["link"]])
        assumptions.append(
            {
                "code": row["code"],
                "statement": row["statement"],
                "kind": row["kind"],
                "verdict": row["verdict"],
                "why": why or ROW_FALLBACK,
                "sources": list(row["sources"]),
            }
        )
    tests = []
    for test in response.tests:
        if test.link not in by_code:
            check.removals.rows += 1
            continue
        tests.append(
            {
                "link": test.link,
                "question": check(test.question, [test.link]),
                "indicator": check(test.indicator, [test.link]),
                "test_and_learn": check(test.test_and_learn, [test.link]),
            }
        )
    report: dict[str, Any] = {
        "title": check(response.title),
        "summary_text": check(response.summary),
        "summary": {
            "goal": plan.intended_change,
            "if_then_because": check(response.if_then_because),
            "population": plan.target_population,
            "time_horizon": plan.time_horizon,
            "directly_influenced": DIRECTLY_INFLUENCED,
            "context": check(response.context),
            "weakest_links": check(response.weakest_links),
        },
        "pathways": pathways,
        "assumptions": assumptions,
        "tests": tests,
    }
    renumber(report, sources)
    report["sources"] = [
        {
            key: s[key]
            for key in (
                "n",
                "citation",
                "url",
                "title",
                "authors",
                "year",
                "venue",
                "evidence_id",
                "quote",
            )
        }
        for s in report["sources"]
    ]
    report["method"] = method_note(now(), route().model_for("toc_judge"))
    summary = {
        "report": report,
        **check.removals.payload(),
        "prompt_version": TOC_REPORT_PROMPT_VERSION,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_report.done", **check.removals.payload(), sources=len(report["sources"]))
    return summary
