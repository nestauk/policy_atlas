"""Pure logic for the coverage and prominence evaluator: no network, no database.

Everything here is deterministic and testable without keys. The command-line
module (``cli.py``) does the file, model and database work and calls in here.

What lives here:

* the typed shapes of the files (``Reference``, ``RunPackage``, ``Judgement``,
  human ``AnnotationRow``) and the judge's wire reply;
* the approval gate (content hash and status) for a reference;
* the Key findings heading parser, which says whether the section is
  ``present``, ``absent`` or ``unresolved``;
* quote verification, reusing the repository's ``qv_v1`` matcher after
  Unicode NFC normalisation;
* validation of a judge reply against the exact set of expected
  finding-section pairs;
* the coverage metrics and their aggregation;
* the comparison of judge labels with human labels.

Vocabulary:

* **finding**: one expected statement from the published review.
* **section**: ``full_report`` (the whole report) or ``key_findings`` (the
  report's short summary section only).
* **pair**: one (finding, section) combination the judge must label.
* **label**: ``adequate``, ``partial``, ``absent``, ``misrepresented`` or
  ``uncertain``. Only ``adequate`` earns coverage credit.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.evidence_search.extract.quote_verify import (
    QUOTE_VERIFIER_VERSION,
    QuoteMatcher,
    build_basis,
)

LABELS: tuple[str, ...] = ("adequate", "partial", "absent", "misrepresented", "uncertain")
Label = Literal["adequate", "partial", "absent", "misrepresented", "uncertain"]
Section = Literal["full_report", "key_findings"]
Priority = Literal["essential", "supporting"]
Control = Literal["enforced", "not_enforced", "unknown"]
KeyFindingsStatus = Literal["present", "absent", "unresolved"]
DatePrecision = Literal["day", "month", "year", "unknown"]
Pair = tuple[str, str]

KEY_FINDINGS_TITLE = "Key findings"
#: Shortest quote (after normalisation) that counts as evidence of a passage.
MIN_QUOTE_CHARS = 25
#: Name of the documented normalisation used before matching a quote.
NORMALISATION = f"NFC then {QUOTE_VERIFIER_VERSION}"
METRICS: tuple[str, ...] = (
    "full_report_coverage",
    "essential_full_report_coverage",
    "key_findings_coverage",
)


class Strict(BaseModel):
    """Base model that rejects unknown fields, so typos in JSON fail loudly."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Reference (the approved answer key)
# --------------------------------------------------------------------------


class SourcePassage(Strict):
    """Where in ``review.md`` a finding comes from, with the exact excerpt."""

    passage_id: str
    location: str = ""
    excerpt: str


class Finding(Strict):
    """One expected finding. ``priority`` and ``expected_in_key_findings`` are
    ``None`` in a draft and must be set by the human before approval."""

    finding_id: str
    finding_text: str
    necessary_qualifications: list[str] = Field(default_factory=list)
    sources: list[SourcePassage] = Field(default_factory=list)
    priority: Priority | None = None
    priority_rationale: str = ""
    expected_in_key_findings: bool | None = None
    key_findings_rationale: str = ""


class Exclusion(Strict):
    """Something from the review deliberately left out of the reference."""

    text: str
    reason: str


class DatedValue(Strict):
    """A date with its provenance. ``date`` is ISO text or ``None`` when unknown."""

    date: str | None = None
    source: str = ""
    precision: DatePrecision = "unknown"
    note: str = ""


class Approval(Strict):
    """The human approval record. ``content_hash`` freezes the rest of the file."""

    status: Literal["draft", "approved"] = "draft"
    reviewer: str | None = None
    approved_at: str | None = None
    content_hash: str | None = None


class Reference(Strict):
    """The ``reference.json`` file."""

    case_id: str
    review_citation: str
    review_identifier: str = ""
    query: str
    scope: str = ""
    eligibility_criteria: str = ""
    publication_date: DatedValue = Field(default_factory=DatedValue)
    evidence_cutoff: DatedValue = Field(default_factory=DatedValue)
    reference_version: str
    findings: list[Finding]
    exclusions: list[Exclusion] = Field(default_factory=list)
    approval: Approval = Field(default_factory=Approval)
    notes: str = ""


def reference_content_hash(ref: Reference) -> str:
    """SHA-256 of the reference with the approval block removed.

    The JSON is written in one canonical form (sorted keys, no spaces) so key
    order and indentation in the file do not change the hash.
    """
    payload = ref.model_dump(mode="json", exclude={"approval"})
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approval_problems(ref: Reference) -> list[str]:
    """Why this reference may not be used for scoring (empty list = usable)."""
    if ref.approval.status != "approved":
        return ["reference is not approved (approval.status is not 'approved')"]
    actual = reference_content_hash(ref)
    if ref.approval.content_hash != actual:
        return [
            "reference changed since approval: stored hash "
            f"{ref.approval.content_hash} but content hashes to {actual}. "
            "Bump reference_version and approve again."
        ]
    return []


def structural_problems(ref: Reference, review_text: str | None) -> list[str]:
    """Checks a human must fix before approval: ids, unfilled fields, excerpts."""
    problems: list[str] = []
    ids = [f.finding_id for f in ref.findings]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate finding ids: {duplicates}")
    if not ref.findings:
        problems.append("no findings")
    matcher = make_matcher(review_text) if review_text is not None else None
    for finding in ref.findings:
        fid = finding.finding_id
        if not finding.finding_text.strip():
            problems.append(f"{fid}: empty finding_text")
        if finding.priority is None:
            problems.append(f"{fid}: priority not set (essential or supporting)")
        if finding.expected_in_key_findings is None:
            problems.append(f"{fid}: expected_in_key_findings not set (true or false)")
        if not finding.sources:
            problems.append(f"{fid}: no source passages")
        if matcher is not None:
            for source in finding.sources:
                if locate_quote(matcher, source.excerpt) is None:
                    problems.append(
                        f"{fid}: excerpt not found in review.md: {source.excerpt[:60]!r}"
                    )
    return problems


class DraftFindingWire(Strict):
    """One item as the drafting model returns it."""

    kind: Literal["finding", "uncertainty", "limitation", "evidence_gap"]
    finding_text: str
    necessary_qualifications: list[str]
    source_passage_ids: list[str]
    source_excerpts: list[str]


class DraftWire(Strict):
    """The drafting model's whole reply."""

    findings: list[DraftFindingWire]


def draft_to_reference(
    wire: DraftWire,
    *,
    case_id: str,
    query: str,
    review_citation: str,
    review_text: str,
) -> tuple[Reference, list[str]]:
    """Turn a model draft into an unapproved ``Reference`` plus warnings.

    Priorities and the Key findings flag are left unset for the human.
    Excerpts that cannot be found in the review are kept but reported, so
    the human fixes them before ``approve`` (which rejects them).
    """
    matcher = make_matcher(review_text)
    warnings: list[str] = []
    findings: list[Finding] = []
    for n, item in enumerate(wire.findings, start=1):
        fid = f"F{n:02d}"
        sources: list[SourcePassage] = []
        ids = item.source_passage_ids or [""] * len(item.source_excerpts)
        for pid, excerpt in zip(ids, item.source_excerpts, strict=False):
            if locate_quote(matcher, excerpt) is None:
                warnings.append(f"{fid}: excerpt not found in review.md: {excerpt[:60]!r}")
            sources.append(SourcePassage(passage_id=pid, location=pid, excerpt=excerpt))
        findings.append(
            Finding(
                finding_id=fid,
                finding_text=item.finding_text,
                necessary_qualifications=item.necessary_qualifications,
                sources=sources,
                priority_rationale=f"DRAFT ({item.kind}): human to decide",
                key_findings_rationale="DRAFT: human to decide",
            )
        )
    ref = Reference(
        case_id=case_id,
        review_citation=review_citation,
        query=query,
        reference_version="draft",
        findings=findings,
        notes="LLM draft. Not approved. Verify every finding, look for omissions, "
        "merge duplicates, set priorities and the Key findings flags, then run approve.",
    )
    return ref, warnings


# --------------------------------------------------------------------------
# Run package (one saved report)
# --------------------------------------------------------------------------


class KeyFindingsSpan(Strict):
    """Where the Key findings section sits in ``report_text`` (character offsets)."""

    status: KeyFindingsStatus
    start: int | None = None
    end: int | None = None
    reason: str = ""


class Generation(Strict):
    """How the report was produced. ``condition`` is a free label for control arms."""

    depth: str = ""
    git_commit: str = ""
    models: dict[str, str] = Field(default_factory=dict)
    date_filter: Control = "unknown"
    reference_review_excluded: Control = "unknown"
    condition: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class RunPackage(Strict):
    """One saved report ready to be judged."""

    case_id: str
    run_id: str
    reference_version: str
    report_text: str
    key_findings: KeyFindingsSpan
    generation: Generation = Field(default_factory=Generation)


def run_package_problems(package: RunPackage) -> list[str]:
    """Input errors that stop a run from being judged at all."""
    problems: list[str] = []
    if not package.report_text.strip():
        problems.append("report_text is empty (missing report text is an input error)")
    span = package.key_findings
    if span.status == "present":
        if span.start is None or span.end is None or not 0 <= span.start < span.end:
            problems.append("key_findings is 'present' but its start/end offsets are invalid")
        elif span.end > len(package.report_text):
            problems.append("key_findings end offset is past the end of report_text")
    return problems


def condition_key(package: RunPackage) -> str:
    """Label that keeps incompatible control conditions apart in summaries."""
    g = package.generation
    return (
        f"condition={g.condition or 'default'};date_filter={g.date_filter};"
        f"reference_review_excluded={g.reference_review_excluded}"
    )


_HEADING = re.compile(r"^## +(.+?) *$", re.MULTILINE)


def find_key_findings(
    text: str, *, expected: bool | None, title: str = KEY_FINDINGS_TITLE
) -> KeyFindingsSpan:
    """Locate the Key findings section from its ``## `` heading.

    Args:
        text: The rendered markdown report.
        expected: What the database says: ``True`` (a key-findings section was
            produced), ``False`` (none was), or ``None`` (unknown, for a report
            imported from a file).
        title: The section title to match, case-insensitively.

    Returns:
        ``present`` with offsets only when exactly one matching heading exists
        and that agrees with ``expected``. A disagreement, or more than one
        heading, is ``unresolved`` with the reason. Zero headings is ``absent``
        only when the database confirms no section was produced.
    """
    headings = [(m.start(), m.group(1).strip()) for m in _HEADING.finditer(text)]
    hits = [i for i, (_, t) in enumerate(headings) if t.casefold() == title.casefold()]

    def present(i: int) -> KeyFindingsSpan:
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        return KeyFindingsSpan(status="present", start=headings[i][0], end=end)

    def unresolved(reason: str) -> KeyFindingsSpan:
        return KeyFindingsSpan(status="unresolved", reason=reason)

    n = len(hits)
    if n > 1:
        return unresolved(f"{n} headings titled {title!r}; cannot tell which is the section")
    if expected is True:
        if n == 1:
            return present(hits[0])
        return unresolved(
            f"the database says a key-findings section exists but no '## {title}' heading was found"
        )
    if expected is False:
        if n == 0:
            return KeyFindingsSpan(status="absent", reason="no key-findings section was produced")
        return unresolved(
            f"the database says no key-findings section exists but a '## {title}' heading was found"
        )
    if n == 1:
        return present(hits[0])
    return unresolved(
        f"no '## {title}' heading found and no database record to confirm absence;"
        " pass --no-key-findings if the report truly has none"
    )


# --------------------------------------------------------------------------
# Quote verification (provenance only, not meaning)
# --------------------------------------------------------------------------


def nfc(text: str) -> str:
    """Unicode NFC form, so composed and decomposed accents compare equal."""
    return unicodedata.normalize("NFC", text)


def make_matcher(text: str) -> QuoteMatcher:
    """A matcher over ``text`` using the documented normalisation."""
    return QuoteMatcher(build_basis([(None, nfc(text))]))


def normalised_length(quote: str) -> int:
    """Length of the quote after normalisation (what the minimum applies to)."""
    return len(build_basis([(None, nfc(quote))]).normalised)


def locate_quote(matcher: QuoteMatcher, quote: str) -> tuple[str, int, int] | None:
    """Find ``quote`` in the matcher's text.

    Returns:
        ``(match_kind, start, end)`` with ``match_kind`` ``"exact"`` or
        ``"normalised"`` and offsets into the NFC text, or ``None`` if the
        quote does not occur.
    """
    match = matcher.find(nfc(quote))
    if match.status == "failed" or not match.spans:
        return None
    return match.status, match.spans[0].start, match.spans[-1].end


# --------------------------------------------------------------------------
# Judge wire shapes and validation
# --------------------------------------------------------------------------


class PassageWire(Strict):
    """A verbatim quote from the report. Offsets are never asked of the model."""

    quote: str


class JudgementWire(Strict):
    """One judgement as returned by the model."""

    finding_id: str
    section: Section
    label: Label
    passages: list[PassageWire]
    missing_or_changed_qualifications: list[str]
    explanation: str


class JudgeResponseWire(Strict):
    """The model's whole reply."""

    judgements: list[JudgementWire]


class Passage(Strict):
    """A verified passage with code-derived offsets into the NFC report text."""

    quote: str
    start: int
    end: int
    match: str


class Judgement(Strict):
    """One validated judgement, denormalised so every row stands alone."""

    case_id: str
    run_id: str
    reference_version: str
    reference_hash: str
    finding_id: str
    section: Section
    label: Label
    passages: list[Passage] = Field(default_factory=list)
    missing_or_changed_qualifications: list[str] = Field(default_factory=list)
    explanation: str = ""
    priority: Priority
    expected_in_key_findings: bool
    source: Literal["judge", "rule"] = "judge"


class JudgeValidationError(ValueError):
    """The judge's reply is unusable. Carries every problem found, not just the first."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def expected_pairs(findings: Sequence[Finding], kf_status: KeyFindingsStatus) -> set[Pair]:
    """The exact finding-section pairs the judge must return.

    Every finding gets a ``full_report`` pair. Findings required in Key
    findings get a ``key_findings`` pair only when that section is present:
    when it is absent, code assigns the label; when unresolved, nothing is
    asked.
    """
    pairs: set[Pair] = {(f.finding_id, "full_report") for f in findings}
    if kf_status == "present":
        pairs |= {(f.finding_id, "key_findings") for f in findings if f.expected_in_key_findings}
    return pairs


def validate_response(
    wire: JudgeResponseWire,
    *,
    expected: set[Pair],
    report_text: str,
    key_findings: KeyFindingsSpan,
) -> list[tuple[JudgementWire, list[Passage]]]:
    """Check a reply against the expected pairs and verify every quote.

    Raises:
        JudgeValidationError: Listing every problem: missing, extra or
            duplicate pairs; passages on an ``absent`` label; no passage on a
            label that needs one; quotes too short; quotes not found in the
            right text (the whole report, or only the Key findings slice).
    """
    problems: list[str] = []
    seen: Counter[Pair] = Counter((j.finding_id, j.section) for j in wire.judgements)
    duplicates = sorted(p for p, n in seen.items() if n > 1)
    if duplicates:
        problems.append(f"duplicate pairs: {duplicates}")
    missing = sorted(expected - set(seen))
    if missing:
        problems.append(f"missing pairs: {missing}")
    extra = sorted(set(seen) - expected)
    if extra:
        problems.append(f"unexpected pairs: {extra}")

    report_matcher = make_matcher(report_text)
    kf_matcher: QuoteMatcher | None = None
    kf_offset = 0
    if key_findings.status == "present" and key_findings.start is not None:
        kf_offset = key_findings.start
        kf_matcher = make_matcher(report_text[key_findings.start : key_findings.end])

    located: list[tuple[JudgementWire, list[Passage]]] = []
    for j in wire.judgements:
        tag = f"{j.finding_id}/{j.section}"
        if j.label == "absent" and j.passages:
            problems.append(f"{tag}: label 'absent' must not carry passages")
        if j.label in ("adequate", "partial", "misrepresented") and not j.passages:
            problems.append(f"{tag}: label {j.label!r} needs at least one passage")
        passages: list[Passage] = []
        for p in j.passages:
            if normalised_length(p.quote) < MIN_QUOTE_CHARS:
                problems.append(f"{tag}: quote shorter than {MIN_QUOTE_CHARS} chars: {p.quote!r}")
                continue
            if j.section == "key_findings":
                if kf_matcher is None:
                    problems.append(f"{tag}: key_findings judgement but the section is not present")
                    continue
                hit = locate_quote(kf_matcher, p.quote)
                if hit is None:
                    problems.append(
                        f"{tag}: quote not inside the Key findings section: {p.quote[:60]!r}"
                    )
                    continue
                kind, start, end = hit
                passages.append(
                    Passage(quote=p.quote, start=start + kf_offset, end=end + kf_offset, match=kind)
                )
            else:
                hit = locate_quote(report_matcher, p.quote)
                if hit is None:
                    problems.append(f"{tag}: quote not found in the report: {p.quote[:60]!r}")
                    continue
                kind, start, end = hit
                passages.append(Passage(quote=p.quote, start=start, end=end, match=kind))
        located.append((j, passages))
    if problems:
        raise JudgeValidationError(problems)
    return located


def rule_judgements_for_absent_section(
    findings: Sequence[Finding], context: dict[str, Any]
) -> list[Judgement]:
    """When the Key findings section is genuinely absent, every required finding is absent there."""
    return [
        Judgement(
            **context,
            finding_id=f.finding_id,
            section="key_findings",
            label="absent",
            explanation="Key findings section is absent from the report (assigned by rule).",
            priority=f.priority or "supporting",
            expected_in_key_findings=True,
            source="rule",
        )
        for f in findings
        if f.expected_in_key_findings
    ]


def to_judgements(
    located: Iterable[tuple[JudgementWire, list[Passage]]],
    findings: Sequence[Finding],
    context: dict[str, Any],
) -> list[Judgement]:
    """Attach run context and finding metadata to validated judgements."""
    by_id = {f.finding_id: f for f in findings}
    out: list[Judgement] = []
    for wire, passages in located:
        f = by_id[wire.finding_id]
        out.append(
            Judgement(
                **context,
                finding_id=wire.finding_id,
                section=wire.section,
                label=wire.label,
                passages=passages,
                missing_or_changed_qualifications=wire.missing_or_changed_qualifications,
                explanation=wire.explanation,
                priority=f.priority or "supporting",
                expected_in_key_findings=bool(f.expected_in_key_findings),
            )
        )
    return out


def cache_key(
    messages: list[dict[str, Any]], parse_kwargs: dict[str, Any], schema: dict[str, Any]
) -> str:
    """Stable key for one judge call: the full messages, settings and reply schema."""
    payload = json.dumps(
        {"messages": messages, "kwargs": parse_kwargs, "schema": schema},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


class Rate(Strict):
    """A coverage rate with everything needed to recompute it by hand."""

    numerator: int | None
    denominator: int
    rate: float | None
    reason: str | None = None
    label_counts: dict[str, int] = Field(default_factory=dict)
    ids_by_label: dict[str, list[str]] = Field(default_factory=dict)


class RunScores(Strict):
    """Scores for one run of one case."""

    case_id: str
    run_id: str
    reference_version: str
    condition: str
    key_findings_status: KeyFindingsStatus
    full_report_coverage: Rate
    essential_full_report_coverage: Rate
    key_findings_coverage: Rate
    essential_absent_ids: list[str]
    prominence_gap_ids: list[str]
    unresolved: list[str]


def _rate(ids: Sequence[str], labels: dict[str, str], *, null_reason: str | None) -> Rate:
    if null_reason is not None:
        return Rate(numerator=None, denominator=len(ids), rate=None, reason=null_reason)
    if not ids:
        return Rate(numerator=None, denominator=0, rate=None, reason="denominator is zero")
    counts: Counter[str] = Counter(labels[i] for i in ids)
    by_label: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        by_label[labels[i]].append(i)
    adequate = counts.get("adequate", 0)
    return Rate(
        numerator=adequate,
        denominator=len(ids),
        rate=adequate / len(ids),
        label_counts={label: counts.get(label, 0) for label in LABELS},
        ids_by_label={label: by_label.get(label, []) for label in LABELS},
    )


def score_run(
    ref: Reference,
    judgements: Sequence[Judgement],
    key_findings: KeyFindingsSpan,
    *,
    condition: str,
) -> RunScores:
    """Turn labels into the three coverage rates plus the diagnostic id lists.

    Only ``adequate`` counts. ``partial`` and ``uncertain`` stay in the
    denominator and earn nothing. A zero denominator, or an unresolved Key
    findings section, gives ``None`` with a reason.
    """
    full = {j.finding_id: j.label for j in judgements if j.section == "full_report"}
    kf = {j.finding_id: j.label for j in judgements if j.section == "key_findings"}
    all_ids = [f.finding_id for f in ref.findings]
    missing = [i for i in all_ids if i not in full]
    if missing:
        raise JudgeValidationError([f"no full_report judgement for {missing}"])
    essential_ids = [f.finding_id for f in ref.findings if f.priority == "essential"]
    required_ids = [f.finding_id for f in ref.findings if f.expected_in_key_findings]

    kf_null: str | None = None
    if key_findings.status == "unresolved":
        kf_null = f"Key findings section unresolved: {key_findings.reason}"
    elif required_ids and any(i not in kf for i in required_ids):
        raise JudgeValidationError(
            [f"no key_findings judgement for {[i for i in required_ids if i not in kf]}"]
        )
    if not required_ids and kf_null is None:
        kf_null = "no findings are required in Key findings"

    unresolved = [f"{i}:full_report" for i in all_ids if full[i] == "uncertain"]
    unresolved += [f"{i}:key_findings" for i in required_ids if kf.get(i) == "uncertain"]
    return RunScores(
        case_id=ref.case_id,
        run_id=judgements[0].run_id if judgements else "",
        reference_version=ref.reference_version,
        condition=condition,
        key_findings_status=key_findings.status,
        full_report_coverage=_rate(all_ids, full, null_reason=None),
        essential_full_report_coverage=_rate(essential_ids, full, null_reason=None),
        key_findings_coverage=_rate(required_ids, kf, null_reason=kf_null),
        essential_absent_ids=[i for i in essential_ids if full[i] == "absent"],
        prominence_gap_ids=[
            i
            for i in required_ids
            if full[i] == "adequate" and kf.get(i) in ("partial", "absent", "misrepresented")
        ],
        unresolved=unresolved,
    )


class MetricSummary(Strict):
    """Mean of one metric over a set of units, with the counts behind it."""

    mean: float | None
    n_scored: int
    n_null: int


class CaseSummary(Strict):
    case_id: str
    group: str
    n_runs: int
    n_failed_runs: int
    metrics: dict[str, MetricSummary]


class GroupSummary(Strict):
    """Reviews weighted equally: each case's runs are averaged first."""

    group: str
    cases: list[str]
    n_runs: int
    n_failed_runs: int
    metrics: dict[str, MetricSummary]


class Summary(Strict):
    cases: list[CaseSummary]
    groups: list[GroupSummary]
    failed_runs: list[dict[str, str]]


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate(scores: Sequence[RunScores], failed: Sequence[dict[str, str]]) -> Summary:
    """Per-case means, then per-group means with equal case weight.

    A group is one reference version under one control condition; groups are
    never averaged together. ``failed`` rows carry ``case_id``, ``run_id`` and
    ``error`` for runs that produced no scores.
    """
    by_case: dict[tuple[str, str], list[RunScores]] = defaultdict(list)
    for s in scores:
        by_case[(f"{s.reference_version} / {s.condition}", s.case_id)].append(s)
    failed_by_case: Counter[str] = Counter(f["case_id"] for f in failed)

    cases: list[CaseSummary] = []
    for (group, case_id), runs in sorted(by_case.items()):
        metrics: dict[str, MetricSummary] = {}
        for name in METRICS:
            rates = [getattr(r, name).rate for r in runs]
            scored = [x for x in rates if x is not None]
            metrics[name] = MetricSummary(
                mean=_mean(scored), n_scored=len(scored), n_null=len(rates) - len(scored)
            )
        cases.append(
            CaseSummary(
                case_id=case_id,
                group=group,
                n_runs=len(runs),
                n_failed_runs=failed_by_case.get(case_id, 0),
                metrics=metrics,
            )
        )

    groups: list[GroupSummary] = []
    for group in sorted({c.group for c in cases}):
        members = [c for c in cases if c.group == group]
        metrics = {}
        for name in METRICS:
            means = [c.metrics[name].mean for c in members]
            scored = [m for m in means if m is not None]
            metrics[name] = MetricSummary(
                mean=_mean(scored), n_scored=len(scored), n_null=len(means) - len(scored)
            )
        groups.append(
            GroupSummary(
                group=group,
                cases=[c.case_id for c in members],
                n_runs=sum(c.n_runs for c in members),
                n_failed_runs=sum(c.n_failed_runs for c in members),
                metrics=metrics,
            )
        )
    return Summary(cases=cases, groups=groups, failed_runs=list(failed))


def _pct(value: float | None) -> str:
    return "null" if value is None else f"{value:.0%}"


def render_summary_md(scores: Sequence[RunScores], summary: Summary) -> str:
    """A short readable report of the scores."""
    lines = ["# Coverage and prominence scores", ""]
    lines += [
        "Only `adequate` earns credit. `partial` and `uncertain` stay in the denominator.",
        "`null` means the denominator was zero or the Key findings section was unresolved.",
        "",
        "## Per run",
        "",
        "| case | run | full report | essential | key findings | KF section "
        "| essential absent | prominence gaps | unresolved |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:

        def cell(rate: Rate) -> str:
            if rate.rate is None:
                return f"null ({rate.reason})"
            return f"{rate.numerator}/{rate.denominator} = {rate.rate:.0%}"

        lines.append(
            f"| {s.case_id} | {s.run_id} | {cell(s.full_report_coverage)} | "
            f"{cell(s.essential_full_report_coverage)} | {cell(s.key_findings_coverage)} | "
            f"{s.key_findings_status} | {', '.join(s.essential_absent_ids) or '-'} | "
            f"{', '.join(s.prominence_gap_ids) or '-'} | {', '.join(s.unresolved) or '-'} |"
        )
    lines += ["", "## Per case (mean over runs)", ""]
    lines += [
        "| group | case | runs | failed | full report | essential | key findings |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in summary.cases:
        m = c.metrics
        lines.append(
            f"| {c.group} | {c.case_id} | {c.n_runs} | {c.n_failed_runs} | "
            f"{_pct(m['full_report_coverage'].mean)} | "
            f"{_pct(m['essential_full_report_coverage'].mean)} | "
            f"{_pct(m['key_findings_coverage'].mean)} "
            f"(null in {m['key_findings_coverage'].n_null}) |"
        )
    lines += ["", "## Per group (cases weighted equally)", ""]
    lines += [
        "| group | cases | runs | failed | full report | essential | key findings |",
        "|---|---|---|---|---|---|---|",
    ]
    for g in summary.groups:
        m = g.metrics
        lines.append(
            f"| {g.group} | {len(g.cases)} | {g.n_runs} | {g.n_failed_runs} | "
            f"{_pct(m['full_report_coverage'].mean)} | "
            f"{_pct(m['essential_full_report_coverage'].mean)} | "
            f"{_pct(m['key_findings_coverage'].mean)} "
            f"(null in {m['key_findings_coverage'].n_null} cases) |"
        )
    if summary.failed_runs:
        lines += ["", "## Failed runs (evaluation errors, not report failures)", ""]
        for f in summary.failed_runs:
            lines.append(f"- {f['case_id']} / {f['run_id']}: {f['error']}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Comparison with human labels
# --------------------------------------------------------------------------


class AnnotationRow(Strict):
    """One human label. ``annotator`` is ``adjudication`` for the agreed label."""

    case_id: str
    run_id: str
    reference_version: str
    finding_id: str
    section: Section
    label: Label
    report_quote: str = ""
    explanation: str = ""
    annotator: str
    status: str = "final"


PairKey = tuple[str, str, str, str]
ADJUDICATION = "adjudication"


def _key(row: Any) -> PairKey:
    return (row.case_id, row.run_id, row.finding_id, row.section)


def select_gold(
    annotations: Sequence[AnnotationRow], judged_versions: dict[tuple[str, str], str]
) -> tuple[dict[PairKey, AnnotationRow], list[dict[str, str]]]:
    """Pick one human label per pair and flag what could not be used.

    The adjudicated label wins when present. Otherwise exactly one annotator
    row is accepted. Two annotators without adjudication is a flagged
    disagreement, and two rows from one annotator is a flagged duplicate.
    Rows whose reference version differs from the judged run's are flagged.
    """
    flags: list[dict[str, str]] = []
    gold: dict[PairKey, AnnotationRow] = {}
    grouped: dict[PairKey, list[AnnotationRow]] = defaultdict(list)
    for row in annotations:
        if row.status not in ("final", "adjudicated"):
            flags.append({"kind": "not_final", "pair": "/".join(_key(row)), "detail": row.status})
            continue
        judged = judged_versions.get((row.case_id, row.run_id))
        if judged is not None and judged != row.reference_version:
            flags.append(
                {
                    "kind": "version_mismatch",
                    "pair": "/".join(_key(row)),
                    "detail": f"annotation {row.reference_version} vs judged {judged}",
                }
            )
            continue
        grouped[_key(row)].append(row)
    for key, rows in grouped.items():
        adjudicated = [r for r in rows if r.annotator == ADJUDICATION]
        if len(adjudicated) == 1:
            gold[key] = adjudicated[0]
            continue
        if len(adjudicated) > 1:
            flags.append(
                {"kind": "duplicate", "pair": "/".join(key), "detail": "several adjudications"}
            )
            continue
        annotators = Counter(r.annotator for r in rows)
        if any(n > 1 for n in annotators.values()):
            flags.append(
                {"kind": "duplicate", "pair": "/".join(key), "detail": str(dict(annotators))}
            )
            continue
        if len(rows) > 1:
            flags.append(
                {
                    "kind": "unadjudicated_disagreement",
                    "pair": "/".join(key),
                    "detail": ", ".join(f"{r.annotator}={r.label}" for r in rows),
                }
            )
            continue
        gold[key] = rows[0]
    return gold, flags


def _detection(positives: set[PairKey], predicted: set[PairKey]) -> dict[str, Any]:
    hits = positives & predicted
    return {
        "human_positive": len(positives),
        "llm_positive": len(predicted),
        "detected": len(hits),
        "missed": sorted("/".join(k) for k in positives - predicted),
        "false_alarms": sorted("/".join(k) for k in predicted - positives),
        "recall": len(hits) / len(positives) if positives else None,
        "precision": len(hits) / len(predicted) if predicted else None,
    }


def compare(
    judgements: Sequence[Judgement], annotations: Sequence[AnnotationRow]
) -> dict[str, Any]:
    """Agreement between judge and human labels, per section, with denominators.

    ``uncertain`` is kept as its own label in the confusion matrices. For the
    omission and prominence-gap detection counts an ``uncertain`` label on
    either side counts as "not flagged", and the abstention counts say how
    often that happened. Rows assigned by rule (Key findings section absent)
    are not judge output and are left out.
    """
    n_rule = sum(1 for j in judgements if j.source == "rule")
    judgements = [j for j in judgements if j.source == "judge"]
    judged_versions = {(j.case_id, j.run_id): j.reference_version for j in judgements}
    gold, flags = select_gold(annotations, judged_versions)
    llm = {_key(j): j for j in judgements}
    already_flagged = {f["pair"] for f in flags}
    for key in sorted(set(llm) - set(gold)):
        if "/".join(key) not in already_flagged:
            flags.append({"kind": "missing_human", "pair": "/".join(key), "detail": ""})
    for key in sorted(set(gold) - set(llm)):
        flags.append({"kind": "missing_llm", "pair": "/".join(key), "detail": ""})
    common = sorted(set(gold) & set(llm))

    sections: dict[str, Any] = {}
    for section in ("full_report", "key_findings"):
        keys = [k for k in common if k[3] == section]
        matrix: Counter[tuple[str, str]] = Counter((gold[k].label, llm[k].label) for k in keys)
        per_label: dict[str, Any] = {}
        for label in LABELS:
            tp = matrix[(label, label)]
            human_n = sum(n for (h, _), n in matrix.items() if h == label)
            llm_n = sum(n for (_, m), n in matrix.items() if m == label)
            per_label[label] = {
                "human_count": human_n,
                "llm_count": llm_n,
                "precision": tp / llm_n if llm_n else None,
                "recall": tp / human_n if human_n else None,
            }
        agree = sum(n for (h, m), n in matrix.items() if h == m)
        sections[section] = {
            "n_pairs": len(keys),
            "agreement": agree / len(keys) if keys else None,
            "confusion": {f"{h}->{m}": n for (h, m), n in sorted(matrix.items())},
            "per_label": per_label,
            "abstentions": {
                "human_uncertain": sum(1 for k in keys if gold[k].label == "uncertain"),
                "llm_uncertain": sum(1 for k in keys if llm[k].label == "uncertain"),
            },
        }

    essential = [k for k in common if k[3] == "full_report" and llm[k].priority == "essential"]
    omissions = _detection(
        {k for k in essential if gold[k].label == "absent"},
        {k for k in essential if llm[k].label == "absent"},
    )

    def gaps(labels: dict[PairKey, Any]) -> set[PairKey]:
        out: set[PairKey] = set()
        for k in common:
            if k[3] != "key_findings":
                continue
            full_key = (k[0], k[1], k[2], "full_report")
            if full_key not in labels:
                continue
            if labels[full_key].label == "adequate" and labels[k].label in (
                "partial",
                "absent",
                "misrepresented",
            ):
                out.add(k)
        return out

    return {
        "n_judgements": len(judgements),
        "n_rule_rows_skipped": n_rule,
        "n_annotations": len(annotations),
        "n_compared": len(common),
        "flags": flags,
        "sections": sections,
        "essential_omissions": omissions,
        "prominence_gaps": _detection(gaps(gold), gaps(llm)),
        "note": (
            "Findings from the same review are related, not independent test items. "
            "uncertain is a label in the matrices; in the detection counts it means 'not flagged'."
        ),
    }


def render_comparison_md(result: dict[str, Any]) -> str:
    """Readable version of :func:`compare`."""
    lines = ["# Judge versus human labels", ""]
    lines.append(
        f"Compared {result['n_compared']} pairs "
        f"({result['n_judgements']} judge rows, {result['n_annotations']} human rows)."
    )
    lines += ["", result["note"], ""]
    for section, s in result["sections"].items():
        lines += [f"## {section}", ""]
        agreement = s["agreement"]
        lines.append(
            f"Pairs: {s['n_pairs']}. Agreement: {_pct(agreement)}. "
            f"Abstentions: human uncertain {s['abstentions']['human_uncertain']}, "
            f"judge uncertain {s['abstentions']['llm_uncertain']}."
        )
        lines += [
            "",
            "| human \\ judge | " + " | ".join(LABELS) + " |",
            "|---|" + "---|" * len(LABELS),
        ]
        for h in LABELS:
            cells = [str(s["confusion"].get(f"{h}->{m}", 0)) for m in LABELS]
            lines.append(f"| {h} | " + " | ".join(cells) + " |")
        lines += ["", "| label | human n | judge n | precision | recall |", "|---|---|---|---|---|"]
        for label, p in s["per_label"].items():
            lines.append(
                f"| {label} | {p['human_count']} | {p['llm_count']} | "
                f"{_pct(p['precision'])} | {_pct(p['recall'])} |"
            )
        lines.append("")
    for name, d in (
        ("Essential omissions", result["essential_omissions"]),
        ("Prominence gaps", result["prominence_gaps"]),
    ):
        lines += [f"## {name}", ""]
        lines.append(
            f"Human flagged {d['human_positive']}, judge flagged {d['llm_positive']}, "
            f"both {d['detected']}. Recall {_pct(d['recall'])}, precision {_pct(d['precision'])}."
        )
        if d["missed"]:
            lines.append(f"Missed by judge: {', '.join(d['missed'])}")
        if d["false_alarms"]:
            lines.append(f"False alarms: {', '.join(d['false_alarms'])}")
        lines.append("")
    if result["flags"]:
        lines += ["## Flags (rows not compared)", ""]
        for f in result["flags"]:
            lines.append(f"- {f['kind']}: {f['pair']} {f['detail']}".rstrip())
        lines.append("")
    return "\n".join(lines)
