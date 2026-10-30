"""Theory-of-change read and write contract (task 054, plan S14; editing C41 to C47).

Two public reads under ``/api/v1/tasks/{task_id}/toc``: the graph with one
evidence verdict per link, link states and the narrative report (``GET ""``), and every
judged document and case study (``GET /evidence``). Verdicts and link states
are computed on read (C36, C19); nothing here is stored as shown.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: One evidence verdict per link (C36, simplified BEAM).
Verdict = Literal[
    "confident",
    "leaning_supports",
    "not_sure_mixed",
    "leaning_against",
    "not_sure_insufficient",
    "not_confident",
]
Support = Literal["strong", "weak", "mixed", "refutes", "not_about"]
LinkState = Literal["unchecked", "checking", "checked", "pending", "kept", "no_change"]
Origin = Literal["drafted", "found_in_evidence", "imported", "user", "options_scoping"]
CheckStatus = Literal["none", "drafting", "checking", "checked", "stopped", "failed"]


class TocResultCriteriaOut(BaseModel):
    """Mayne's checks on one box."""

    model_config = ConfigDict(extra="forbid")

    definition: str | None = None
    indicator: str | None = None
    timing: str | None = None


class TocPositionOut(BaseModel):
    """Where the user dropped a box on the canvas (C47)."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class TocBoxOut(BaseModel):
    """One element in a layer. Boxes are described, not graded (W4)."""

    model_config = ConfigDict(extra="forbid")

    box_id: uuid.UUID
    layer: Literal["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"]
    #: Short stable label, e.g. ``S3`` (C35); null only on rows written before codes.
    code: str | None
    text: str
    dosage: str | None
    result_criteria: TocResultCriteriaOut
    description: str | None
    #: Where the change has been seen, from its case studies, and the documents it cites.
    seen_in: str | None
    seen_in_cites: list[uuid.UUID]
    origin: Origin
    revision: int
    #: Where the user moved the box; null keeps the computed layout (C47).
    position: TocPositionOut | None = None
    #: Who last edited it (a display name) and when; null when nobody has (C41).
    edited_by: str | None = None
    edited_at: datetime | None = None


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
    #: A short title (at most 8 words); null until the check has written one.
    title: str | None
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
    #: The documents (task source snapshot ids) the evidence sentence cites.
    evidence_cites: list[uuid.UUID]
    #: Who last edited it (a display name) and when; null when nobody has (C41).
    edited_by: str | None = None
    edited_at: datetime | None = None
    #: New evidence waiting for the user's Accept (C44), and the verdict if they accept it all.
    pending_count: int = 0
    verdict_if_accepted: Verdict | None = None


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
    #: The verdict's label, e.g. "Leaning supports".
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
    #: The document's title, the judgement behind the number and its quote, so a
    #: marker opens the quote in its passage; null on reports written before.
    title: str | None = None
    evidence_id: uuid.UUID | None = None
    quote: str | None = None
    #: Shown as the Evidence search shows its references: title, then authors,
    #: year and venue; empty or null on reports written before.
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None


class TocReportOut(BaseModel):
    """Detailed information as a short narrative report (C38), written on each check."""

    model_config = ConfigDict(extra="forbid")

    #: The page title (at most 8 words) and the one- or two-sentence summary under it;
    #: null on reports written before ``toc_report_v2``.
    title: str | None = None
    summary_text: str | None = None
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
    grade_rules: list[TocGradeRuleOut]
    #: The theory's confidence: the lowest verdict among its critical links; null without one.
    confidence: Verdict | None
    #: The latest check's narrative report; null until one is written.
    report: TocReportOut | None
    #: Links the 80-link cap left unchecked in the last check walk.
    links_left_out: int
    #: Whether the caller may edit (the task's owner, C50); false for public readers.
    can_edit: bool = False


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
    #: ``support`` and ``relevance`` above are what counts: the user's scores when
    #: they changed them (C42), else the judge's. The judge's own stay here.
    judge_support: Support | None = None
    judge_relevance: int | None = None
    #: Who changed the scores, removed the document from the link, or added it (display names).
    scored_by: str | None = None
    removed_by: str | None = None
    added_by: str | None = None
    #: ``pending`` evidence waits for the user's Accept and does not count yet (C44).
    status: Literal["counted", "pending", "rejected"] = "counted"
    #: The judgement row's revision, for an edit to it (C10).
    revision: int = 1


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
    #: One plain sentence explaining the figure; null on figures found before it existed.
    statement: str | None
    #: The judgement the figure came from: ``GET /toc/evidence/{evidence_id}/context``
    #: shows the quote in its passage.
    evidence_id: uuid.UUID
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

    #: The judgement it came from, for the quote in its passage.
    evidence_id: uuid.UUID
    task_source_snapshot_id: uuid.UUID
    programme: str
    place: str | None
    note: str
    quote: str
    title: str
    #: Author names, or the publishing organisation for a policy document.
    authors: list[str]
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


# --- Writes (C41, C47, C10) -----------------------------------------------------------------


class TocBoxCreate(BaseModel):
    """A box the user adds."""

    model_config = ConfigDict(extra="forbid")

    layer: Literal["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"]
    text: str = Field(min_length=1, max_length=500)
    position: TocPositionOut | None = None


class TocCriteriaIn(BaseModel):
    """How we'd know a box's change happened."""

    model_config = ConfigDict(extra="forbid")

    definition: str | None = None
    indicator: str | None = None
    timing: str | None = None


class TocBoxPatch(BaseModel):
    """A change to one box, with the revision the client saw (C10)."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    text: str | None = Field(default=None, min_length=1, max_length=500)
    layer: (
        Literal["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"]
        | None
    ) = None
    description: str | None = Field(default=None, max_length=2000)
    criteria: TocCriteriaIn | None = None


class TocLinkCreate(BaseModel):
    """Two boxes the user connects."""

    model_config = ConfigDict(extra="forbid")

    source_box_id: uuid.UUID
    target_box_id: uuid.UUID


class TocLinkPatch(BaseModel):
    """A change to one link, with the revision the client saw (C10)."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    title: str | None = Field(default=None, max_length=200)
    if_text: str | None = Field(default=None, max_length=1000)
    for_text: str | None = Field(default=None, max_length=1000)
    then_text: str | None = Field(default=None, max_length=1000)
    because_text: str | None = Field(default=None, max_length=1000)
    conditions: list[str] | None = None
    critical: Literal[True] | None = None


class TocRevisionIn(BaseModel):
    """The revision the client saw, for a delete (C10)."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int


class TocMoveIn(BaseModel):
    """Where the user dropped a box."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    x: float
    y: float


class TocCreatedOut(BaseModel):
    """The id of what was added."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID


class TocRevisionOut(BaseModel):
    """The row's revision after a write."""

    model_config = ConfigDict(extra="forbid")

    revision: int


class TocHistoryEntryOut(BaseModel):
    """One change in History (C41)."""

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    at: datetime
    who: str
    what: str
    undoable: bool


class TocUndoOut(BaseModel):
    """What Undo could not put back because it changed since (C10)."""

    model_config = ConfigDict(extra="forbid")

    skipped: list[str]


class TocCheckIn(BaseModel):
    """Check named links (C40): new items, or the ones the user picked."""

    model_config = ConfigDict(extra="forbid")

    link_ids: list[uuid.UUID] = Field(min_length=1, max_length=80)
    mode: Literal["new_items", "check_again", "find_more", "rest"] = "new_items"


class TocCheckOut(BaseModel):
    """The check walk that started."""

    model_config = ConfigDict(extra="forbid")

    capability_run_id: uuid.UUID


class TocEvidencePatch(BaseModel):
    """Change how one judged document counts for its link (C42), with its revision (C10)."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    action: Literal["remove", "restore", "score", "unscore", "accept", "reject"]
    support: Support | None = None
    relevance: int | None = Field(default=None, ge=0, le=3)


class TocLinksIn(BaseModel):
    """Links to act on (Keep the evidence, C43)."""

    model_config = ConfigDict(extra="forbid")

    link_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class TocCountOut(BaseModel):
    """How many items an action changed."""

    model_config = ConfigDict(extra="forbid")

    count: int


class TocStudyIn(BaseModel):
    """A study the user adds to a link: a DOI or a web address (C42)."""

    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=4, max_length=2000)


class TocDecideIn(BaseModel):
    """Accept or reject every pending document on one link (C44)."""

    model_config = ConfigDict(extra="forbid")

    accept: bool
