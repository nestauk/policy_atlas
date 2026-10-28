"""Theory-of-change read contract (task 054, plan S14).

Two public reads under ``/api/v1/tasks/{task_id}/toc``: the graph with both
grades, link states and the summary (``GET ""``), and every judged document
and case study (``GET /evidence``). Grades and link states are computed on
read (C4, C19); nothing here is stored as shown.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

Grade = Literal["strong", "medium", "weak", "none"]
LinkState = Literal["unchecked", "checking", "checked", "pending", "kept", "no_change"]
Origin = Literal["drafted", "found_in_evidence", "imported", "user", "options_scoping"]
CheckStatus = Literal["none", "drafting", "checking", "checked", "failed"]
Stance = Literal["supports", "challenges", "not_about"]


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


class TocGradeOut(BaseModel):
    """One question's grade (C4)."""

    model_config = ConfigDict(extra="forbid")

    grade: Grade
    against: int
    supports: int


class TocLinkOut(BaseModel):
    """One causal step, with both grades and its state."""

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
    elsewhere: TocGradeOut
    here: TocGradeOut
    lower_grade: Grade
    elsewhere_sentence: str | None
    here_sentence: str | None
    #: Every judged document answers both questions the same way: one paragraph.
    merged: bool


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


class TocGradeRuleOut(BaseModel):
    """One row of the grade rule, generated from the grade constants (C4)."""

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
    #: Links the 80-link cap left unchecked in the last check walk.
    links_left_out: int


class TocStanceOut(BaseModel):
    """One question's stance on one document."""

    model_config = ConfigDict(extra="forbid")

    stance: Stance
    quote: str | None


class TocDocumentOut(BaseModel):
    """One judged document of one link, listed once even when it answers both."""

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
    elsewhere: TocStanceOut
    here: TocStanceOut
    condition: str | None
    #: True when the judgement was made for an earlier wording of the link.
    previous_wording: bool


class TocLinkEvidenceOut(BaseModel):
    """Every document judged for one link."""

    model_config = ConfigDict(extra="forbid")

    link_id: uuid.UUID
    documents: list[TocDocumentOut]


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
    """A box's case studies and the indicators its documents used."""

    model_config = ConfigDict(extra="forbid")

    box_id: uuid.UUID
    case_studies: list[TocCaseStudyOut]
    indicators: list[str]


class TocEvidenceOut(BaseModel):
    """Every judged document and case study of the theory."""

    model_config = ConfigDict(extra="forbid")

    links: list[TocLinkEvidenceOut]
    boxes: list[TocBoxEvidenceOut]
