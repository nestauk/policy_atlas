"""Theory-of-change read contract (task 054, plan S14).

Two public reads under ``/api/v1/tasks/{task_id}/toc``: the graph with one
evidence verdict per link, link states and the summary (``GET ""``), and every
judged document and case study (``GET /evidence``). Verdicts and link states
are computed on read (C36, C19); nothing here is stored as shown.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

#: One evidence verdict per link (C36, simplified BEAM).
Verdict = Literal["confident", "not_sure_mixed", "not_sure_insufficient", "not_confident"]
Support = Literal["strong", "weak", "mixed", "refutes", "not_about"]
LinkState = Literal["unchecked", "checking", "checked", "pending", "kept", "no_change"]
Origin = Literal["drafted", "found_in_evidence", "imported", "user", "options_scoping"]
CheckStatus = Literal["none", "drafting", "checking", "checked", "failed"]


class TocResultCriteriaOut(BaseModel):
    """Mayne's checks on one box."""

    model_config = ConfigDict(extra="forbid")

    definition: str | None = None
    indicator: str | None = None
    timing: str | None = None


class TocBoxOut(BaseModel):
    """One element in a layer. Boxes are described, not graded (W4)."""

    model_config = ConfigDict(extra="forbid")

    box_id: uuid.UUID
    layer: Literal[
        "input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"
    ]
    #: Short stable label, e.g. ``S3`` (C35); null only on rows written before codes.
    code: str | None
    text: str
    dosage: str | None
    result_criteria: TocResultCriteriaOut
    description: str | None
    origin: Origin
    revision: int


class TocWeightsOut(BaseModel):
    """The numbers behind a link's verdict (C36)."""

    model_config = ConfigDict(extra="forbid")

    #: W: the sum of the documents' weights; 1 is one strong, fully relevant study.
    total_weight: float
    #: S̄: the weight-averaged support, from -2 (refutes) to +2 (strongly supports).
    mean_support: float
    #: R%: the share of the weight that refutes, 0 to 1.
    refute_share: float
    #: Documents that support or refute the link in any way.
    n_documents: int


class TocLinkOut(BaseModel):
    """One causal step, with its evidence verdict and its state."""

    model_config = ConfigDict(extra="forbid")

    link_id: uuid.UUID
    #: Short stable label, e.g. ``#5`` (C35); null only on rows written before codes.
    code: str | None
    source_box_id: uuid.UUID
    target_box_id: uuid.UUID
    sentence: str
    if_text: str
    for_text: str
    then_text: str
    because_text: str
    conditions: list[str]
    assumption_type: str
    critical: bool
    origin: Origin
    revision: int
    state: LinkState
    verdict: Verdict
    #: One more document could change the verdict.
    near_threshold: bool
    weights: TocWeightsOut
    #: What the documents found and whether it holds here (C36).
    evidence_sentence: str | None


class TocPathwayOut(BaseModel):
    """One ordered route of links."""

    model_config = ConfigDict(extra="forbid")

    pathway_id: uuid.UUID
    kind: Literal["success", "failure"]
    status: Literal["kept", "set_aside"]
    label: str
    reason: str | None
    origin: Origin
    link_ids: list[uuid.UUID]
    #: A link is missing between two neighbours (a deletion left a gap).
    broken: bool


class TocSummaryOut(BaseModel):
    """The header paragraphs and the questions for an evaluation (C20)."""

    model_config = ConfigDict(extra="forbid")

    about: str
    evidence_says: str
    evaluation_questions: list[str]


class TocReportSummaryOut(BaseModel):
    """The report's Summary (C38)."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    if_then_because: str
    population: str
    time_horizon: str | None
    #: The accountability ceiling: the last layer the programme directly influences.
    directly_influenced: str
    context: str
    weakest_links: str


class TocReportPathwayOut(BaseModel):
    """How change happens along one pathway: a lead-in title and a paragraph."""

    model_config = ConfigDict(extra="forbid")

    title: str
    paragraph: str


class TocReportAssumptionOut(BaseModel):
    """One row of Assumptions and evidence."""

    model_config = ConfigDict(extra="forbid")

    #: The link's code, or the failure outcome's for a risk.
    code: str
    statement: str
    kind: Literal["assumption", "risk"]
    #: The verdict's label, e.g. "Not sure: mixed".
    verdict: str
    why: str
    #: Numbers in the report's source list.
    sources: list[int]


class TocReportTestOut(BaseModel):
    """One row of What to test and measure."""

    model_config = ConfigDict(extra="forbid")

    link: str
    question: str
    indicator: str
    test_and_learn: str


class TocReportSourceOut(BaseModel):
    """One numbered source, in order of first citation."""

    model_config = ConfigDict(extra="forbid")

    n: int
    citation: str
    url: str | None


class TocReportOut(BaseModel):
    """Detailed information as a short narrative report (C38), written on each check."""

    model_config = ConfigDict(extra="forbid")

    summary: TocReportSummaryOut
    pathways: list[TocReportPathwayOut]
    assumptions: list[TocReportAssumptionOut]
    tests: list[TocReportTestOut]
    sources: list[TocReportSourceOut]
    #: How it was made: written by code, with the date and the judge's model.
    method: str


class TocGradeRuleOut(BaseModel):
    """One row of the verdict rule, generated from the verdict constants (C36)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    rule: str


class TocGraphOut(BaseModel):
    """The whole theory as the Result page reads it."""

    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    check_status: CheckStatus
    boxes: list[TocBoxOut]
    links: list[TocLinkOut]
    pathways: list[TocPathwayOut]
    context: list[str]
    supporting_activities: list[str]
    summary: TocSummaryOut | None
    grade_rules: list[TocGradeRuleOut]
    #: The theory's confidence: the lowest verdict among its critical links; null without one.
    confidence: Verdict | None
    #: The latest check's narrative report; null until one is written.
    report: TocReportOut | None
    #: Links the 80-link cap left unchecked in the last check walk.
    links_left_out: int


class TocDocumentOut(BaseModel):
    """One judged document of one link, with what it adds to the verdict (C36)."""

    model_config = ConfigDict(extra="forbid")

    #: The judgement row; ``GET /toc/evidence/{evidence_id}/context`` shows its quote.
    evidence_id: uuid.UUID
    task_source_snapshot_id: uuid.UUID
    title: str
    #: Author display names, as the Evidence search references show them; empty when unknown.
    authors: list[str]
    year: int | None
    url: str | None
    source_type: Literal["academic", "policy", "web"]
    evidence_type: str | None
    appraisal_score: int | None
    support: Support
    quote: str | None
    #: R, 0 to 3: how well the finding carries over to this population and place.
    relevance: int
    relevance_reason: str | None
    #: Q, 1 to 3, from the appraisal score (web pages and models capped).
    quality: int
    #: Q × R ÷ 9; ignored in the verdict when support is not_about.
    weight: float
    condition: str | None
    #: True when the judgement was made for an earlier wording of the link.
    previous_wording: bool


class TocFigureOut(BaseModel):
    """One number a document reports about a link's cause or effect (C37), with its source."""

    model_config = ConfigDict(extra="forbid")

    figure_id: uuid.UUID
    #: source / target: a level of that box; link: the link's effect.
    box: Literal["source", "target", "link"]
    measure: str
    #: As reported, and parsed (null when not a plain number). Never pooled.
    value_text: str
    value: float | None
    ci_lower_text: str | None
    ci_lower: float | None
    ci_upper_text: str | None
    ci_upper: float | None
    unit: str | None
    effect_size_type: Literal[
        "absolute_change", "relative_change", "standardised", "ratio", "level"
    ]
    population: str | None
    place: str | None
    #: When the data were collected, as reported.
    year: str | None
    n: int | None
    k: int | None
    quote: str
    # The source document's short citation, as the documents carry it.
    task_source_snapshot_id: uuid.UUID
    source_title: str
    source_authors: list[str]
    source_year: int | None
    #: The journal or publisher, when known.
    source_venue: str | None
    source_type: Literal["academic", "policy", "web"]
    evidence_type: str | None
    url: str | None


class TocLinkEvidenceOut(BaseModel):
    """Every document judged for one link, and the figures they give."""

    model_config = ConfigDict(extra="forbid")

    link_id: uuid.UUID
    documents: list[TocDocumentOut]
    #: The size of change (C37), for the link's current wording.
    figures: list[TocFigureOut]


class TocCaseStudyOut(BaseModel):
    """Where one box was seen (or, for an input, put in place)."""

    model_config = ConfigDict(extra="forbid")

    task_source_snapshot_id: uuid.UUID
    programme: str
    place: str | None
    note: str
    quote: str
    title: str
    year: int | None
    url: str | None
    source_type: Literal["academic", "policy", "web"]


class TocBoxEvidenceOut(BaseModel):
    """A box's case studies, the indicators its documents used, and its figures."""

    model_config = ConfigDict(extra="forbid")

    box_id: uuid.UUID
    case_studies: list[TocCaseStudyOut]
    indicators: list[str]
    #: Levels of this box (a baseline, a prevalence) its links' documents report (C37).
    figures: list[TocFigureOut]


class TocEvidenceOut(BaseModel):
    """Every judged document and case study of the theory."""

    model_config = ConfigDict(extra="forbid")

    links: list[TocLinkEvidenceOut]
    boxes: list[TocBoxEvidenceOut]
