"""The case record: one published theory of change (ToC) in one shape (task 060).

Every case lives in ``cases/<case_id>/case.json``. ``extract.py`` writes a draft
(``case.draft.json``); a person checks every box and link against the figure and saves
the checked copy as ``case.json``.

``cases/<case_id>/brief.json`` holds the short brief, written by hand (``ShortBrief``).

Run ``python schema.py`` to check every ``cases/*/case*.json`` (ids unique, every link
and assumption points at something that exists) and every ``brief.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

#: Canonical layers (as in v1). ``input`` and ``activity`` are scored as one layer.
Layer = Literal[
    "input", "activity", "output", "outcome_short", "outcome_long", "impact", "vision", "context"
]
#: One scale for every source's verdict words. ``partly`` = mixed or some support.
Scale = Literal["supports", "partly", "insufficient", "against", "not_assessed"]
Timing = Literal["prospective", "retrospective", "reconstructed", "synthesis"]


class Verdict(BaseModel):
    """What the source says about the evidence for one link, assumption or the whole theory."""

    raw: str = Field(description="The source's own verdict words, quoted")
    scale: Scale
    quote: str = Field("", description="A short quote that carries the verdict")
    page: int | None = None
    studies: list[str] = Field(
        default_factory=list, description="Studies the source cites for it: DOI or short citation"
    )


class Meta(BaseModel):
    id: str
    title: str
    organisation: str
    year: int
    country: str
    topic: str
    intervention_type: Literal["programme", "policy", "regulation", "fund", "service"]
    timing: Timing
    doc_url: str
    landing_url: str = ""
    licence: str = ""
    figure_pages: list[int]
    evidence_level: Literal["A", "B", "C"]
    verdict_source: Literal["ex_post_evaluation", "evidence_synthesis", "ex_ante_design", "none"]
    split: Literal["dev", "test", ""] = ""


class Brief(BaseModel):
    """What a person would know before drawing the theory. Never the theory itself."""

    intended_change: str
    population: str
    place: str
    time_horizon: str = ""
    intervention: str = Field(description="What is done, with the dosage where known")
    context: str = ""
    outcome_first: str = Field(description="A first message for the app that starts from the change")
    intervention_first: str = Field(
        description="A first message for the app that starts from the intervention"
    )


class ShortBrief(BaseModel):
    """The main test input, in ``cases/<id>/brief.json``: what a user would type on day one.

    Written by hand from the source, not by the extraction model, and kept apart from the
    draft so a new extraction never overwrites it. No proper names (they let the evidence
    search find the source itself); the type of setting and the country stay.
    """

    intervention_first: str
    outcome_first: str
    written_by: str
    date: str
    based_on: str = Field(description="What was read to write it, e.g. 'pp. 4-6, section 2'")
    notes: str = ""


class Container(BaseModel):
    """A group of boxes drawn as one (an arrow to it means an arrow to its members)."""

    id: str
    label: str
    layer: Layer


class Box(BaseModel):
    id: str
    label: str = Field(description="The source's words")
    layer: Layer
    container: str | None = None
    verdict: Verdict | None = Field(
        None, description="Only when the source judges the box itself (e.g. outcome achieved)"
    )


class Link(BaseModel):
    id: str
    source: str = Field(description="A box or container id")
    target: str = Field(description="A box or container id")
    two_way: bool = False
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in our reading of the arrow, not in the evidence"
    )
    verdict: Verdict | None = None


class Assumption(BaseModel):
    """An assumption or a risk, placed on links or between two layers."""

    id: str
    kind: Literal["assumption", "risk"]
    text: str
    links: list[str] = Field(default_factory=list)
    from_layer: Layer | None = None
    to_layer: Layer | None = None
    verdict: Verdict | None = None


class KeyClaim(BaseModel):
    """A causal claim a good theory for this case must contain, with the source's verdict.

    The unit of scoring: the app's theory is checked claim by claim, not box by box. It also
    holds every finding of the source, including findings on panels or tables that are not
    transcribed as boxes, so no verdict is lost.
    """

    id: str
    claim: str = Field(description="Plain words, e.g. 'Savings accounts build economic assets'")
    refs: list[str] = Field(
        default_factory=list, description="Box, container, link or assumption ids it covers"
    )
    where: str = Field("", description="Where the source tests it, e.g. 'Figure 5; Table 4'")
    verdict: Verdict | None = None


class Conclusions(BaseModel):
    overall: Verdict | None = None
    weakest_links: list[str] = Field(default_factory=list, description="Link or assumption ids")
    strongest_links: list[str] = Field(default_factory=list)
    summary: str = Field("", description="The source's main conclusions, close to its words")
    recommendations: list[str] = Field(default_factory=list)


class Transcription(BaseModel):
    """How the record was made. ``extract.py`` fills the provenance fields, not the model."""

    method: str = Field(description="e.g. 'gpt-6.1-sol draft, checked by hand against p.12'")
    checked_by: str = ""
    date: str = ""
    open_questions: list[str] = Field(default_factory=list)
    source_sha256: str = Field("", description="Checksum of the exact PDF that was read")
    prompt_sha256: str = Field("", description="Checksum of the extraction prompt used")


class Case(BaseModel):
    meta: Meta
    brief: Brief
    containers: list[Container] = Field(default_factory=list)
    boxes: list[Box]
    links: list[Link]
    assumptions: list[Assumption] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list, description="External factors")
    key_claims: list[KeyClaim] = Field(default_factory=list)
    conclusions: Conclusions = Conclusions()
    transcription: Transcription

    @model_validator(mode="after")
    def _refs(self) -> Case:
        ends = {c.id for c in self.containers} | {b.id for b in self.boxes}
        ids = [*ends, *(lk.id for lk in self.links), *(a.id for a in self.assumptions),
               *(k.id for k in self.key_claims)]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes or len(ends) != len(self.containers) + len(self.boxes):
            raise ValueError(f"duplicate ids: {sorted(dupes)}")
        containers = {c.id for c in self.containers}
        if bad := [b.id for b in self.boxes if b.container and b.container not in containers]:
            raise ValueError(f"boxes in unknown containers: {bad}")
        if bad := [lk.id for lk in self.links if {lk.source, lk.target} - ends]:
            raise ValueError(f"links to unknown boxes: {bad}")
        link_ids = {lk.id for lk in self.links}
        if bad := [a.id for a in self.assumptions if set(a.links) - link_ids]:
            raise ValueError(f"assumptions on unknown links: {bad}")
        known = ends | {lk.id for lk in self.links} | {a.id for a in self.assumptions}
        if bad := [k.id for k in self.key_claims if set(k.refs) - known]:
            raise ValueError(f"key claims refer to unknown ids: {bad}")
        named = set(self.conclusions.weakest_links + self.conclusions.strongest_links)
        if bad := named - link_ids - {a.id for a in self.assumptions}:
            raise ValueError(f"conclusions name unknown links: {sorted(bad)}")
        return self


def check(paths: list[Path]) -> int:
    """Validate case files; print one line each. Returns the number that failed."""
    failed = 0
    for p in paths:
        try:
            if p.name == "brief.json":
                ShortBrief.model_validate(json.loads(p.read_text()))
                print(f"ok   {p}: short brief")
                continue
            c = Case.model_validate(json.loads(p.read_text()))
            judged = sum(k.verdict is not None for k in c.key_claims)
            print(f"ok   {p}: {len(c.boxes)} boxes, {len(c.links)} links, "
                  f"{len(c.key_claims)} key claims ({judged} with verdicts)")
        except Exception as e:  # noqa: BLE001 - report every bad file, then fail
            failed += 1
            print(f"FAIL {p}: {e}")
    return failed


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    files = [Path(a) for a in sys.argv[1:]] or sorted(here.glob("cases/*/case*.json")) + sorted(
        here.glob("cases/*/brief.json")
    )
    sys.exit(1 if check(files) else 0)
