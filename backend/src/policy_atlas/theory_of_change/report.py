"""The theory's report: the ``toc_report`` step (task 054, C38).

One frontier call (``toc_report_v4``) writes the prose; code does the rest:

- **Inputs.** The plan; the theory with box and connection codes, each
  connection's verdict and evidence sentence; the weakest critical connections;
  the table's rows (:func:`assumption_rows`, one per connection); and the
  numbered sources behind them.
- **Checks.** Every box or connection code the text cites must exist, and every
  ``[n]`` must be a listed source. In a pathway line, a row's reason or a test,
  the source must bear on a connection that text names or that pathway holds;
  in the context and How it could fail, on any connection. Anything else is
  removed and counted; a row the model gave no reason gets a fixed one.
- **Assembly.** Each success pathway gets a strength label (its weakest
  connection's verdict) and the Overview lists them strongest first. Sources
  are renumbered by first citation, uncited ones dropped; code writes the
  source list (with the journal or publishing organisation) and the method
  note.

The assembled report is the step's ``component.completed`` payload, as the
summary's header paragraphs are: the read API serves the latest one.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.api.read_models.repository import _authorships, _url, _venue
from policy_atlas.core.model_routes import route
from policy_atlas.core.schema import event_log
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.sourcing.acquire import normalize_doi
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import sense_check, store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check import (
    PROGRAMME_EVENT,
    _ask,
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
    Judgement,
    Verdict,
    link_verdict,
    lowest,
    weight,
)
from policy_atlas.theory_of_change.proposals import open_proposals
from policy_atlas.theory_of_change.report_prompt import TOC_REPORT_PROMPT_VERSION, ReportResponse

log = structlog.get_logger()

#: A connection on more than this share of the success pathways is central.
CENTRAL_SHARE = 0.5
#: Verdicts at or below this one are weak: a central, weak row is flagged.
WEAK_VERDICT: Verdict = "not_sure_mixed"
#: Sources a table row lists: those its reason cites, filled up with the heaviest.
ROW_SOURCES = 3
#: Weakest links the summary names.
WEAKEST_LINKS = 3
#: What a row says when the model gave it no reason.
ROW_FALLBACK = "See the evidence on this link."
#: Until the accountability ceiling can be moved (increment 2), it sits after outputs.
DIRECTLY_INFLUENCED = "outputs"
#: Words of a source's quote the model sees as its finding.
FINDING_WORDS = 30
#: Verdicts that count as the evidence supporting a step.
SUPPORTED = frozenset({"confident", "leaning_supports"})


def steps_hold_but_programme_does_not(step_verdicts: list[str], programme_verdict: str) -> bool:
    """Every step to the goal is supported, but whole-programme evaluations are not."""
    return (
        bool(step_verdicts)
        and all(v in SUPPORTED for v in step_verdicts)
        and programme_verdict not in SUPPORTED
    )


#: The code citations to a found route's documents are checked against.
EXPAND_CODE = "expand"
#: What to test first: this many items, the most important first.
TESTS_SHOWN = 3
#: A title with letters split from their word ("G reat B ritain", from small
#: capitals in the source's record): a capital other than A or I, a space, then lower case.
_SPLIT_CAPS = re.compile(r"\b([B-HJ-Z]) (?=[a-z]{2,})")

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
    sentence: str
    verdict: Verdict
    evidence_sentence: str | None
    critical: bool
    conditions: list[str]
    on_failure: bool
    on_success: bool
    #: How many kept success pathways the connection is on.
    on_pathways: int = 0


def assumption_rows(
    links: list[LinkFacts], sources_of: dict[str, list[int]], pathways: int
) -> list[dict[str, Any]]:
    """The Assumptions and evidence rows (C38, v4): one per connection on a kept pathway.

    Importance is the share of success pathways the connection is on, or Risk
    for a connection only on failure pathways; evidence is its verdict. A
    central (more than half the pathways) and weak (Mixed or lower) row is
    flagged. The default order (owner, 2026-11-04): risks the evidence supports
    (Supported or Leaning supports) first, as the likeliest ways to fail; then
    the success connections, most central first (flagged before others at the
    same share, then the worst verdict); then the risks with mixed or weak
    support. The reader can re-sort the table.

    Args:
        links: Every connection, in graph order.
        sources_of: Connection code → the numbers of its supporting or refuting sources.
        pathways: The number of kept success pathways.

    Returns:
        Rows with ``key`` (``r1``...), ``code``, ``statement`` (the
        connection's sentence), ``conditions``, ``kind``, ``importance``,
        ``share``, ``verdict`` (label), ``verdict_rank``, ``flag`` and ``sources``.
    """
    weak = VERDICT_ORDER.index(WEAK_VERDICT)
    supported = VERDICT_ORDER.index("leaning_supports")
    ranked: list[tuple[tuple[int, float, bool, int, int], dict[str, Any]]] = []
    for index, link in enumerate(links):
        if not (link.on_pathways or link.on_failure):
            continue
        risk = link.on_pathways == 0
        share = link.on_pathways / pathways if pathways else 0.0
        rank = VERDICT_ORDER.index(link.verdict)
        flag = share > CENTRAL_SHARE and rank <= weak
        ranked.append(
            (
                (
                    (0 if rank >= supported else 2) if risk else 1,
                    -share,
                    not flag,
                    -rank if risk else rank,
                    index,
                ),
                {
                    "code": link.code,
                    "statement": link.sentence,
                    "conditions": list(link.conditions),
                    "kind": "risk" if risk else "assumption",
                    "importance": "Risk" if risk else f"{round(share * 100)}% of pathways",
                    "share": None if risk else share,
                    "verdict": VERDICT_LABELS[link.verdict],
                    "verdict_rank": rank,
                    "flag": flag,
                    "sources": sources_of.get(link.code, []),
                },
            )
        )
    ranked.sort(key=lambda pair: pair[0])
    return [{"key": f"r{i}", **row} for i, (_, row) in enumerate(ranked, start=1)]


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

    Citation order: the Summary (context, question, claim, verdict), the routes,
    How it could fail, the rows (each row's reason, then its source list), the tests.

    Args:
        report: The assembled sections, with ``[n]`` in their texts and
            ``sources`` lists on the rows.
        sources: The numbered sources (``n`` and the rest).
    """
    summary, rows = report["summary"], report["assumptions"]
    texts: list[tuple[dict[str, Any], str]] = [
        (report, key) for key in ("title", "summary_text") if key in report
    ]
    texts += [
        (summary, key)
        for key in ("context", "question", "if_then_because", "weakest_links")
        if summary.get(key)
    ]
    texts += [(report, key) for key in ("verdict_reason", "whole_programme") if report.get(key)]
    texts += [(route, "sentence") for route in report.get("expansions") or []]
    texts += [(p, key) for p in report["pathways"] for key in ("title", "paragraph")]
    texts += [(report, "how_it_could_fail")] if "how_it_could_fail" in report else []
    bullets = report.get("supporting_activities") or []
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
        (t, key)
        for t in report["tests"]
        for key in ("sentence", "question", "indicator", "test_and_learn")
        if t.get(key)
    ]
    for holder, key in tests:
        see(int(n) for n in _CITE.findall(holder[key]))
    for text in bullets:
        see(int(n) for n in _CITE.findall(text))

    def rewrite(text: str) -> str:
        return _CITE.sub(lambda m: f"[{first[int(m.group(1))]}]", text)

    for holder, key in [*texts, *[(row, "why") for row in rows], *tests]:
        holder[key] = rewrite(holder[key])
    if bullets:
        report["supporting_activities"] = [rewrite(text) for text in bullets]
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


def _who(authors: list[str], organisation: bool = False) -> str:
    """'Boyland et al.', 'Boyland', or an organisation's whole name ('Public Health Scotland')."""
    if not authors:
        return ""
    first = authors[0] if organisation else (authors[0].split() or [authors[0]])[-1]
    return f"{first} et al." if len(authors) > 1 else first


def publisher(meta: dict[str, Any], authors: list[str]) -> str | None:
    """The journal for a paper, the publishing organisation for a policy document.

    Omitted when it only repeats the sole author (an organisation's own report).
    """
    found = _venue(meta) or (str(meta.get("publisher_org") or "") or None)
    return None if found is not None and authors == [found] else found


def citation(
    *,
    authors: list[str],
    year: int | None,
    title: str,
    venue: str | None,
    kind: str | None,
    organisation: bool = False,
) -> str:
    """ "Boyland et al. (2016) Advertising as a cue to consume. Appetite. Systematic review."."""
    who = _who(authors, organisation)
    when = f"({year})" if year else ""
    head = " ".join(part for part in (who, when) if part)
    parts = [
        f"{head} {title}".strip() if head else title,
        venue,
        kind.capitalize() if kind else None,
    ]
    return " ".join(f"{part.rstrip('.')}." for part in parts if part)


def _short(
    authors: list[str], year: int | None, title: str, venue: str | None, organisation: bool
) -> str:
    who = _who(authors, organisation)
    return ", ".join(part for part in (f"{who} {year or ''}".strip(), title, venue) if part)


def _metadata(conn: Connection, task_id: uuid.UUID, ids: set[uuid.UUID]) -> dict[uuid.UUID, Any]:
    return {
        tss: (row.metadata or {}, row.source_locator)
        for tss, row in store.snapshot_meta(conn, task_id, ids).items()
    }


#: The overall verdict's words on the page: the mechanism only when it fails,
#: else what the evidence shows ("plausible" goes without saying).
EVIDENCE_LABELS = {
    "supports": "Evidence supports it",
    "mixed": "Mixed evidence",
    "too_little": "Too little evidence",
    "against": "Evidence against",
}
#: The code citations to the whole programme's sources are checked against.
PROGRAMME_CODE = "programme"


def theory_verdict(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    plan: dict[str, Any],
    facts: list[LinkFacts],
    box_text: dict[str, str],
    pathways: list[dict[str, str]],
    whole: dict[str, Any] | None,
    backend: TocBackend,
    usage: UsageAccumulator,
) -> dict[str, Any] | None:
    """The overall verdict and headline (``toc_verdict_v2``); ``None`` if the call failed.

    Reads every connection's verdict and evidence sentence, how many success
    pathways it is on, the whole programme's verdict and findings, and the
    plan-stage sense check.
    """
    payload: dict[str, object] = {
        "plan": {k: v for k, v in plan.items() if v},
        "connections": [
            {
                "code": f.code,
                "from": f"{f.source_code}: {box_text[f.source_code]}",
                "to": f"{f.target_code}: {box_text[f.target_code]}",
                "verdict": VERDICT_LABELS[f.verdict],
                "evidence": f.evidence_sentence,
                "success_pathways": f.on_pathways,
            }
            for f in facts
        ],
        "pathways": pathways,
        "whole_programme": whole or "not searched in this check",
    }
    found = sense_check.for_verdict(sense_check.latest(conn, task_id))
    response = _ask(
        "toc_verdict",
        lambda: backend.theory_verdict(theory=payload, sense_check=found),
        usage,
    )
    if response is None:
        log.warning("toc_verdict.failed", task_id=str(task_id))
        return None
    return {
        "mechanism": response.mechanism,
        "evidence": response.evidence,
        "label": (
            "Implausible"
            if response.mechanism == "implausible"
            else EVIDENCE_LABELS[response.evidence]
        ),
        "headline": response.headline,
        "reason": response.reason,
        "carrying_step": response.carrying_step,
    }


def mend_title(title: str) -> str:
    """Join capitals split from their words, when it happens at least twice ("G reat B ritain")."""
    return _SPLIT_CAPS.sub(r"\1", title) if len(_SPLIT_CAPS.findall(title)) >= 2 else title


def same_work(meta: dict[str, Any]) -> str | None:
    """A key that two copies of one paper share: its DOI, else its title and year."""
    doi = normalize_doi(meta.get("doi"))
    if doi:
        return doi
    words = re.sub(r"[^a-z0-9]+", " ", str(meta.get("title") or "").lower()).strip()
    return f"{words}|{_year(meta)}" if words else None


def _source_entry(
    n: int,
    meta_locator: tuple[dict[str, Any], str | None],
    kind: str | None,
    *,
    evidence_id: str | None,
    quote: str | None,
) -> dict[str, Any]:
    """One numbered source: its citation, title, authors, year and publisher, and the quote."""
    meta, locator = meta_locator
    authors = [a.name for a in _authorships(meta)]
    title, year = mend_title(str(meta.get("title") or "")), _year(meta)
    venue = publisher(meta, authors)
    organisation = meta.get("backend") == "overton"
    return {
        "n": n,
        "citation": citation(
            authors=authors,
            year=year,
            title=title,
            venue=venue,
            kind=kind,
            organisation=organisation,
        ),
        "short": _short(authors, year, title, venue, organisation),
        "url": _url(meta, locator),
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        # The judgement behind the number: a marker opens its quote in context.
        "evidence_id": evidence_id,
        "quote": quote,
        "finding": " ".join((quote or "").split()[:FINDING_WORDS]),
    }


def found_routes(conn: Connection, task_id: uuid.UUID) -> list[dict[str, Any]]:
    """The routes found in the evidence that wait as suggestions (an as-drawn diagram).

    Each: a key (``r1``), its label and kind, the new boxes' texts, the codes of
    the existing boxes it joins, and its documents (``tss`` and ``quote``).
    """
    routes: list[dict[str, Any]] = []
    for proposal in open_proposals(conn, task_id):
        if proposal.source != "discover":
            continue
        boxes: list[str] = []
        joins: list[str] = []
        for op in proposal.edits:
            if op.get("op") == "add_box":
                boxes.append(str(op.get("text")))
            elif op.get("op") == "add_link":
                joins += [
                    ref
                    for ref in (op.get("source"), op.get("dest"))
                    if ref and _CODE.fullmatch(ref)
                ]
            elif op.get("op") == "add_pathway":
                routes.append(
                    {
                        "key": f"r{len(routes) + 1}",
                        "label": op.get("label"),
                        "kind": op.get("kind") or "success",
                        "new_boxes": boxes,
                        "joins": list(dict.fromkeys(joins)),
                        "documents": [
                            {"tss": uuid.UUID(item["tss"]), "quote": item.get("quote") or ""}
                            for item in op.get("evidence") or []
                        ],
                    }
                )
                boxes, joins = [], []
    return routes


def programme_judgements(
    conn: Connection, task_id: uuid.UUID
) -> tuple[Verdict, list[dict[str, Any]]] | None:
    """The whole programme's verdict and judgements from the latest full check, or ``None``.

    Weighed like a connection's evidence: the same quality (from classify and
    appraise) and relevance, the same rule.
    """
    payload = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id, event_log.c.event_type == PROGRAMME_EVENT)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not payload:
        return None
    walk = uuid.UUID(payload["walk_id"])
    rows = payload["judgements"]
    appraisals = appraisals_for(
        conn,
        task_id=task_id,
        evidence_rows=[
            SimpleNamespace(capability_run_id=walk, task_source_snapshot_id=uuid.UUID(j["tss"]))
            for j in rows
        ],
    )
    verdict = link_verdict(
        [Judgement(j["tss"], j["support"], j["relevance"], j.get("robust_model")) for j in rows],
        appraisals,
    ).verdict
    about = [j for j in rows if j["support"] != "not_about"]
    about.sort(
        key=lambda j: (
            -weight(
                appraisals.get(j["tss"]),
                Judgement(j["tss"], j["support"], j["relevance"], j.get("robust_model")),
            )
        )
    )
    return verdict, about


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
    success = [p for p in kept if p.kind == "success"]
    on_success = {key for p in success for key in p.links}
    box_code = {key: rows.boxes[key].code or key for key in graph.boxes}
    facts = [
        LinkFacts(
            key=key,
            code=rows.links[key].code or key,
            source_code=box_code[link.source],
            target_code=box_code[link.target],
            sentence=link.sentence,
            verdict=link_verdict_of(counted.get(key, []), appraisals).verdict,
            evidence_sentence=rows.links[key].evidence_sentence,
            critical=bool(rows.links[key].critical),
            conditions=list(link.conditions),
            on_failure=key in on_failure,
            on_success=key in on_success,
            on_pathways=sum(1 for p in success if key in p.links),
        )
        for key, link in graph.links.items()
    ]
    by_code = {f.code: f for f in facts}
    fact_of = {f.key: f for f in facts}
    path_links = {p.key: [fact_of[k].code for k in p.links if k in fact_of] for p in kept}

    # Sources: documents that support or refute the rows' and pathways' links, heaviest first.
    preliminary = assumption_rows(facts, {}, len(success))
    link_order = list(
        dict.fromkeys(
            [row["code"] for row in preliminary] + [c for p in kept for c in path_links[p.key]]
        )
    )
    metadata = _metadata(conn, task_id, {row.task_source_snapshot_id for row in every})
    types = {
        doc.tss_id: doc.evidence_type
        for doc in screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    }
    numbers: dict[uuid.UUID, int] = {}
    by_work: dict[str, int] = {}
    bears: dict[int, set[str]] = {}
    sources_of: dict[str, list[int]] = {}
    sources: list[dict[str, Any]] = []

    def number(
        tss: uuid.UUID, code: str, *, evidence_id: str | None, quote: str | None, works: bool = True
    ) -> int:
        """Number a source once and note what it bears on; ``works``: one number per work."""
        work = same_work(metadata.get(tss, ({}, None))[0]) if works else None
        if tss not in numbers and work is not None and work in by_work:
            # The same paper found twice (two copies, or a preprint): one number.
            numbers[tss] = by_work[work]
        if tss not in numbers:
            numbers[tss] = len(sources) + 1
            if work is not None:
                by_work[work] = numbers[tss]
            sources.append(
                _source_entry(
                    numbers[tss],
                    metadata.get(tss, ({}, None)),
                    types.get(tss),
                    evidence_id=evidence_id,
                    quote=quote,
                )
            )
        bears.setdefault(numbers[tss], set()).add(code)
        return numbers[tss]

    for code in link_order:
        group = [
            r for r in counted.get(by_code[code].key, []) if row_judgement(r).support != "not_about"
        ]
        group.sort(
            key=lambda r: -weight(appraisals.get(str(r.task_source_snapshot_id)), row_judgement(r))
        )
        for r in group:
            n = number(
                r.task_source_snapshot_id, code, evidence_id=str(r.evidence_id), quote=r.quote
            )
            # Each connection's sources, heaviest first.
            if n not in sources_of.setdefault(code, []):
                sources_of[code].append(n)
    table = assumption_rows(facts, sources_of, len(success))
    # The whole programme's evaluations (red team): numbered after the connections' sources.
    programme = programme_judgements(conn, task_id)
    whole: dict[str, Any] | None = None
    if programme is not None:
        programme_verdict, programme_rows = programme
        found = [uuid.UUID(j["tss"]) for j in programme_rows]
        metadata.update(_metadata(conn, task_id, set(found) - set(metadata)))
        listed = []
        for j, tss in zip(programme_rows, found, strict=True):
            listed.append(
                {
                    "n": number(tss, PROGRAMME_CODE, evidence_id=None, quote=j["quote"]),
                    "support": j["support"],
                    "finding": " ".join((j["quote"] or "").split()[:FINDING_WORDS]),
                }
            )
        whole = {"verdict": VERDICT_LABELS[programme_verdict], "documents": listed}

    # Routes found in the evidence that an as-drawn diagram does not show (owner,
    # 2026-11-04): their documents are numbered after the others, code "expand".
    expandable = found_routes(conn, task_id)
    documents = {item["tss"] for way in expandable for item in way["documents"]}
    metadata.update(_metadata(conn, task_id, documents - set(metadata)))
    for way in expandable:
        for item in way["documents"]:
            item["n"] = number(
                item["tss"], EXPAND_CODE, evidence_id=None, quote=item["quote"], works=False
            )

    pkey = {p.key: f"p{i}" for i, p in enumerate(kept, start=1)}
    theory = {
        "boxes": [
            {"code": box_code[key], "layer": box.layer, "text": box.text}
            for key, box in graph.boxes.items()
        ],
        "connections": [
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
                "connections": path_links[p.key],
            }
            for p in kept
        ],
        "weakest_critical_connections": weakest_links(facts),
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
    # Can the theory work at all? One overall verdict before the prose, which must agree with it.
    verdict = theory_verdict(
        conn,
        task_id=task_id,
        plan=plan_fields,
        facts=facts,
        box_text={box_code[key]: box.text for key, box in graph.boxes.items()},
        pathways=[{"label": rows.pathways[p.key].label, "kind": p.kind} for p in kept],
        whole=whole,
        backend=backend,
        usage=usage,
    )
    if verdict is not None:
        theory["overall_verdict"] = {k: verdict[k] for k in ("label", "headline", "reason")}
    if whole is not None:
        theory["whole_programme"] = whole
        # Every step on the routes holds, but the whole programme's evaluations do not
        # find the effect (owner, 2026-11-04): the report must say so, and why.
        if steps_hold_but_programme_does_not(
            [fact_of[key].verdict for key in on_success if key in fact_of], programme_verdict
        ):
            theory["steps_hold_but_programme_does_not"] = True
    if expandable:
        theory["found_routes"] = [
            {
                "key": way["key"],
                "label": way["label"],
                "kind": way["kind"],
                "new_boxes": way["new_boxes"],
                "joins": way["joins"],
                "documents": [
                    {"n": item["n"], "finding": " ".join(item["quote"].split()[:FINDING_WORDS])}
                    for item in way["documents"]
                ],
            }
            for way in expandable
        ]
    supporting = [row.text for row in rows.band_items if row.band == "supporting"]
    if supporting:
        theory["supporting_activities"] = supporting
    response: ReportResponse | None = _ask(
        "toc_report",
        lambda: backend.report(
            plan={k: v for k, v in plan_fields.items() if v},
            theory=theory,
            rows=[
                {
                    k: row[k]
                    for k in (
                        "code",
                        "statement",
                        "conditions",
                        "importance",
                        "verdict",
                        "sources",
                    )
                }
                for row in table
            ],
            sources=[
                {
                    "n": s["n"],
                    "citation": s["short"],
                    "connections": sorted(bears[s["n"]]),
                    "finding": s["finding"],
                }
                for s in sources
            ],
        ),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_report: the report call failed")

    check = TextChecker(codes=set(box_code.values()) | set(by_code), sources=bears)
    every_code = list(by_code)
    links_of = {pkey[p.key]: path_links[p.key] for p in success}
    id_of = {pkey[p.key]: p.key for p in success}
    # A pathway is as strong as its weakest connection.
    strength: dict[str, Verdict] = {
        pkey[p.key]: lowest(fact_of[k].verdict for k in p.links if k in fact_of)
        or "not_sure_insufficient"
        for p in success
    }
    pathways = []
    for item in response.pathways:
        if item.pathway not in links_of:
            check.removals.rows += 1
            continue
        pathways.append(
            {
                "pathway_id": id_of[item.pathway],
                "title": check(item.title, links_of[item.pathway]),
                "paragraph": check(item.sentence, links_of[item.pathway]),
                "strength": VERDICT_LABELS[strength[item.pathway]],
            }
        )
    # Strongest first; a tie keeps the model's order.
    pathways.sort(key=lambda line: -VERDICT_ORDER.index(strength[pkey[line["pathway_id"]]]))
    reasons = {item.connection: item.why for item in response.connection_reasons}
    assumptions = []
    for row in table:
        why = check(reasons.get(row["code"], ""), [row["code"]])
        # The Sources column: what the reason cites, then the heaviest, to ROW_SOURCES.
        cited = [int(n) for n in _CITE.findall(why)]
        shown = list(dict.fromkeys([*cited, *row["sources"]]))[: max(ROW_SOURCES, len(cited))]
        assumptions.append(
            {
                **{k: row[k] for k in ("code", "statement", "conditions", "kind")},
                **{k: row[k] for k in ("importance", "share", "verdict", "verdict_rank", "flag")},
                "why": why or ROW_FALLBACK,
                "sources": shown,
            }
        )
    # What to test first: flagged connections, then the most central, then the weakest.
    priority = sorted(
        table, key=lambda row: (not row["flag"], -(row["share"] or 0), row["verdict_rank"])
    )
    place = {row["code"]: at for at, row in enumerate(priority)}
    tests: list[dict[str, str]] = []
    for test in sorted(response.tests, key=lambda t: place.get(t.connection, len(place))):
        if test.connection not in by_code or any(t["link"] == test.connection for t in tests):
            check.removals.rows += 1
            continue
        tests.append({"link": test.connection, "sentence": check(test.sentence, [test.connection])})
    tests = tests[:TESTS_SHOWN]
    # One sentence per found route, citing what it was found in.
    sentence_of = {item.route: item.sentence for item in response.found_routes}
    expansions = [
        {
            "label": way["label"],
            "kind": way["kind"],
            "sentence": check(sentence_of.get(way["key"], ""), [EXPAND_CODE]),
        }
        for way in expandable
    ]
    report: dict[str, Any] = {
        "title": check(response.title),
        "summary_text": check(response.summary, every_code),
        "summary": {
            "goal": plan.intended_change,
            # A summarised setting, grounded in any listed source.
            "context": check(response.context, every_code),
            "question": check(response.question, every_code),
            "if_then_because": check(response.if_then_because, every_code),
            "population": plan.target_population,
            "time_horizon": plan.time_horizon,
            "directly_influenced": DIRECTLY_INFLUENCED,
        },
        # Why the overall verdict, with what the whole programme's evaluations found.
        "verdict_reason": check(response.verdict_reason, [*every_code, PROGRAMME_CODE]),
        "pathways": pathways,
        "how_it_could_fail": check(response.how_it_could_fail, every_code),
        "assumptions": assumptions,
        "tests": tests,
        # One bullet per supporting activity, citing what bears on it (owner, 2026-11-04).
        "supporting_activities": [
            check(text, [*every_code, PROGRAMME_CODE])
            for text in response.supporting_activities[: len(supporting)]
            if text.strip()
        ],
        "verdict": verdict,
        "expansions": expansions,
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
