"""The theory-of-change model seam (task 054): one backend for every ToC step.

Each method makes one call with its lead-authored prompt and returns the parsed
wire with token usage; the step that calls it owns every semantic check (the
structure checks, the quote check, the citation check). :class:`StubTocBackend`
is deterministic and makes no call, so tests and keyless local runs work.
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from typing import Any, Protocol, cast

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import resolve_openai_client, traced_parse
from policy_atlas.core.usage import UsageResult
from policy_atlas.theory_of_change.choose_prompt import (
    TOC_CHOOSE_MAX_OUTPUT_TOKENS,
    TOC_CHOOSE_PROMPT_VERSION,
    ChooseDecisionWire,
    ChooseResponse,
    build_choose_messages,
)
from policy_atlas.theory_of_change.discover_prompt import (
    TOC_CONSOLIDATE_MAX_OUTPUT_TOKENS,
    TOC_CONSOLIDATE_PROMPT_VERSION,
    TOC_DISCOVER_MAX_OUTPUT_TOKENS,
    TOC_DISCOVER_PROMPT_VERSION,
    ConsolidatedPathwayWire,
    ConsolidateResponse,
    DiscoverResponse,
    NewBoxWire,
    NewLinkWire,
    build_consolidate_messages,
    build_discover_messages,
)
from policy_atlas.theory_of_change.draft_prompt import (
    TOC_DRAFT_MAX_OUTPUT_TOKENS,
    TOC_DRAFT_PROMPT_VERSION,
    DraftBoxWire,
    DraftLinkWire,
    DraftPathwayWire,
    DraftResponse,
    ResultCriteriaWire,
    build_draft_messages,
)
from policy_atlas.theory_of_change.evidence.figures_prompt import (
    TOC_FIGURES_MAX_OUTPUT_TOKENS,
    TOC_FIGURES_PROMPT_VERSION,
    FiguresResponse,
    build_figures_messages,
)
from policy_atlas.theory_of_change.evidence.judge_prompt import (
    TOC_JUDGE_MAX_OUTPUT_TOKENS,
    TOC_JUDGE_PROMPT_VERSION,
    JudgeResponse,
    build_judge_messages,
)
from policy_atlas.theory_of_change.evidence.pick_prompt import (
    PICK_N,
    TOC_PICK_MAX_OUTPUT_TOKENS,
    TOC_PICK_PROMPT_VERSION,
    PickResponse,
    build_pick_messages,
)
from policy_atlas.theory_of_change.merge_prompt import (
    TOC_MERGE_MAX_OUTPUT_TOKENS,
    TOC_MERGE_PROMPT_VERSION,
    MergeDecisionWire,
    MergeResponse,
    build_merge_messages,
)
from policy_atlas.theory_of_change.report_prompt import (
    TOC_REPORT_MAX_OUTPUT_TOKENS,
    TOC_REPORT_PROMPT_VERSION,
    AssumptionReasonWire,
    PathwayParagraphWire,
    ReportResponse,
    TestRowWire,
    build_report_messages,
)
from policy_atlas.theory_of_change.review_prompt import (
    TOC_REVIEW_MAX_OUTPUT_TOKENS,
    TOC_REVIEW_PROMPT_VERSION,
    ReportFindingWire,
    ReviewResponse,
    build_review_messages,
)
from policy_atlas.theory_of_change.summary_prompt import (
    TOC_SUMMARY_MAX_OUTPUT_TOKENS,
    TOC_SUMMARY_PROMPT_VERSION,
    BoxDescriptionWire,
    LinkSentencesWire,
    SummaryResponse,
    build_summary_messages,
)


class TocBackend(Protocol):
    """The model seam of the theory-of-change steps."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``."""
        ...

    def draft(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
    ) -> UsageResult[DraftResponse]:
        """Write the first draft (``toc_draft_v1``)."""
        ...

    def discover(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        documents: list[dict[str, object]],
    ) -> UsageResult[DiscoverResponse]:
        """Propose routes from one batch of documents (``toc_discover_v1``)."""
        ...

    def consolidate(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        proposals: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ConsolidateResponse]:
        """Join every batch's proposals into a few new pathways (``toc_consolidate_v1``)."""
        ...

    def merge(
        self,
        *,
        plan: dict[str, object],
        boxes: list[dict[str, object]],
        pathways: list[dict[str, object]],
    ) -> UsageResult[MergeResponse]:
        """Fold repeated boxes, then merge and set aside pathways (``toc_merge_v2``)."""
        ...

    def pick(
        self, *, item_text: str, candidates: list[dict[str, object]]
    ) -> UsageResult[PickResponse]:
        """Pick the documents the judge reads for one link (``toc_pick_v1``)."""
        ...

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """Judge one link against one document (``toc_judge_v4``).

        Keyword arguments are those of
        :func:`~policy_atlas.theory_of_change.evidence.judge_prompt.build_judge_messages`.
        """
        ...

    def figures(self, **kwargs: Any) -> UsageResult[FiguresResponse]:
        """Find the size of change behind one link in one document (``toc_figures_v1``).

        Keyword arguments are those of
        :func:`~policy_atlas.theory_of_change.evidence.figures_prompt.build_figures_messages`.
        """
        ...

    def choose(
        self,
        *,
        plan: dict[str, object],
        pathways: list[dict[str, object]],
        recorded_conditions: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ChooseResponse]:
        """Choose pathways and name new conditions (``toc_choose_v3``)."""
        ...

    def summarise(
        self, *, plan: dict[str, object], theory: dict[str, object]
    ) -> UsageResult[SummaryResponse]:
        """Write the header paragraphs and sentences (``toc_summary_v2``)."""
        ...

    def report(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
    ) -> UsageResult[ReportResponse]:
        """Write the narrative Detailed information (``toc_report_v1``)."""
        ...

    def review(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        edits: list[str],
        report: dict[str, object] | None,
    ) -> UsageResult[ReviewResponse]:
        """Review the theory's shape after the user's edits (``toc_review_v1``, C45)."""
        ...


class OpenAITocBackend:
    """Live implementation of :class:`TocBackend` on the selected model route.

    Args:
        api_key: Optional API key; the route's key variable otherwise.
        langfuse_client: Optional Langfuse client; tracing is a no-op without one.
        session_id: Optional Langfuse session id.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """

    mode = "live"

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
        session_id: uuid.UUID | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key, backend_name="OpenAITocBackend", timeout=300.0, max_retries=2
        )
        self._langfuse_client = langfuse_client
        self._session_id = session_id

    def _call[T: BaseModel](
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        response_format: type[T],
        step: str,
        max_output_tokens: int,
        prompt_version: str,
    ) -> UsageResult[T]:
        model = route().model_for(step)
        return traced_parse(
            self._client,
            self._langfuse_client,
            messages=messages,
            response_format=response_format,
            model=model,
            # The route's setting for the model (Terra: "none"); the judge was
            # measured at it, and without it Terra's default gave unstable stances.
            reasoning_effort=route().reasoning_effort_for(model),
            max_output_tokens=max_output_tokens,
            usage_event=f"{step}.usage",
            label=step,
            name=f"toc:{step.removeprefix('toc_')}",
            prompt_version=prompt_version,
            session_id=self._session_id,
        )

    def draft(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
    ) -> UsageResult[DraftResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_draft_messages(plan, existing_theory=existing_theory, problems=problems),
            response_format=DraftResponse,
            step="toc_draft",
            max_output_tokens=TOC_DRAFT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_DRAFT_PROMPT_VERSION,
        )

    def discover(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        documents: list[dict[str, object]],
    ) -> UsageResult[DiscoverResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_discover_messages(plan=plan, theory=theory, documents=documents),
            response_format=DiscoverResponse,
            step="toc_discover",
            max_output_tokens=TOC_DISCOVER_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_DISCOVER_PROMPT_VERSION,
        )

    def consolidate(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        proposals: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ConsolidateResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_consolidate_messages(
                plan=plan,
                theory=theory,
                proposals=proposals,
                max_success=max_success,
                max_failure=max_failure,
            ),
            response_format=ConsolidateResponse,
            step="toc_merge",
            max_output_tokens=TOC_CONSOLIDATE_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_CONSOLIDATE_PROMPT_VERSION,
        )

    def merge(
        self,
        *,
        plan: dict[str, object],
        boxes: list[dict[str, object]],
        pathways: list[dict[str, object]],
    ) -> UsageResult[MergeResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_merge_messages(plan=plan, boxes=boxes, pathways=pathways),
            response_format=MergeResponse,
            step="toc_merge",
            max_output_tokens=TOC_MERGE_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_MERGE_PROMPT_VERSION,
        )

    def pick(
        self, *, item_text: str, candidates: list[dict[str, object]]
    ) -> UsageResult[PickResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_pick_messages(item_text=item_text, candidates=candidates),
            response_format=PickResponse,
            step="toc_pick",
            max_output_tokens=TOC_PICK_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_PICK_PROMPT_VERSION,
        )

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_judge_messages(**kwargs),
            response_format=JudgeResponse,
            step="toc_judge",
            max_output_tokens=TOC_JUDGE_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_JUDGE_PROMPT_VERSION,
        )

    def figures(self, **kwargs: Any) -> UsageResult[FiguresResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_figures_messages(**kwargs),
            response_format=FiguresResponse,
            step="toc_figures",
            max_output_tokens=TOC_FIGURES_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_FIGURES_PROMPT_VERSION,
        )

    def choose(
        self,
        *,
        plan: dict[str, object],
        pathways: list[dict[str, object]],
        recorded_conditions: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ChooseResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_choose_messages(
                plan=plan,
                pathways=pathways,
                recorded_conditions=recorded_conditions,
                max_success=max_success,
                max_failure=max_failure,
            ),
            response_format=ChooseResponse,
            step="toc_choose",
            max_output_tokens=TOC_CHOOSE_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_CHOOSE_PROMPT_VERSION,
        )

    def summarise(
        self, *, plan: dict[str, object], theory: dict[str, object]
    ) -> UsageResult[SummaryResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_summary_messages(plan=plan, theory=theory),
            response_format=SummaryResponse,
            step="toc_summarise",
            max_output_tokens=TOC_SUMMARY_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_SUMMARY_PROMPT_VERSION,
        )

    def review(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        edits: list[str],
        report: dict[str, object] | None,
    ) -> UsageResult[ReviewResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_review_messages(plan=plan, theory=theory, edits=edits, report=report),
            response_format=ReviewResponse,
            step="toc_review",
            max_output_tokens=TOC_REVIEW_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_REVIEW_PROMPT_VERSION,
        )

    def report(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
    ) -> UsageResult[ReportResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_report_messages(plan=plan, theory=theory, rows=rows, sources=sources),
            response_format=ReportResponse,
            step="toc_report",
            max_output_tokens=TOC_REPORT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_REPORT_PROMPT_VERSION,
        )


def _criteria(definition: str, indicator: str | None) -> ResultCriteriaWire:
    return ResultCriteriaWire(definition=definition, indicator=indicator, timing="within 2 years")


def stub_draft(plan: dict[str, object]) -> DraftResponse:
    """The stub's deterministic draft: one success and one failure pathway.

    Args:
        plan: The plan fields as data.

    Returns:
        A draft that passes the structure checks.
    """
    intervention = str(plan.get("intervention") or "the intervention")
    change = str(plan.get("intended_change") or "the intended change")
    boxes = [
        ("b1", "input", f"Deliver {intervention}"[:120]),
        ("b2", "output", "The intervention reaches its population"),
        ("b3", "outcome_short", "Behaviour changes"),
        ("b4", "impact", change[:120]),
        ("b5", "failure_outcome", "Take-up stays low"),
        ("b6", "outcome_long", "The new behaviour lasts"),
    ]
    links = [
        ("l1", "b1", "b2"),
        ("l2", "b2", "b3"),
        ("l3", "b3", "b6"),
        ("l4", "b2", "b5"),
        ("l5", "b6", "b4"),
    ]
    return DraftResponse(
        boxes=[
            DraftBoxWire(
                key=key,
                layer=layer,  # type: ignore[arg-type]
                text=text,
                dosage=None,
                result_criteria=_criteria(
                    f"{text} happens.", None if layer == "input" else "A rate"
                ),
                from_user_theory=False,
            )
            for key, layer, text in boxes
        ],
        links=[
            DraftLinkWire(
                key=key,
                source=source,
                target=target,
                sentence=f"Step {key} leads on.",
                if_text="this happens",
                for_text="the population",
                then_text="the next step follows",
                because_text="of the mechanism",
                conditions=[f"Condition for {key} holds"],
                from_user_theory=False,
            )
            for key, source, target in links
        ],
        pathways=[
            DraftPathwayWire(
                key="p1", kind="success", label="Main route", links=["l1", "l2", "l3", "l5"]
            ),
            DraftPathwayWire(key="p2", kind="failure", label="Low take-up", links=["l1", "l4"]),
        ],
        context=["Other policies in place"],
        supporting_activities=["Set-up and training"],
        critical_link="l2",
    )


class StubTocBackend:
    """Deterministic zero-egress ToC backend for tests and keyless runs.

    Each method answers from its own FIFO queue when one is given (a queued
    exception is raised, so a test can fail a call), else deterministically:

    - ``draft``: :func:`stub_draft`.
    - ``discover``: no proposals.
    - ``consolidate``: each proposal as it came.
    - ``merge``: folds no boxes and keeps every pathway.
    - ``pick``: the first :data:`PICK_N` candidates, in order.
    - ``judge``: weakly supports at relevance 2, quoting the first eight words
      of the document text (so the quote check passes); not about when the
      text is empty.
    - ``figures``: none.
    - ``choose``: keeps every pathway, no new conditions.
    - ``summarise``: a title per link and a plain sentence citing its first
      judged document; plain box descriptions with no "seen in".
    - ``report``: a plain report: each pathway's paragraph names its first
      link and cites that link's first source; a reason for every row.

    Calls are counted in :attr:`calls` and their keyword inputs kept in
    :attr:`inputs`, both under a lock (judge runs in a thread pool).

    Args:
        responses: Step name → canned responses or exceptions, in call order.
    """

    mode = "stub"

    def __init__(self, responses: dict[str, list[Any]] | None = None) -> None:
        self._queues = {name: list(items) for name, items in (responses or {}).items()}
        self._lock = threading.Lock()
        self.calls: dict[str, int] = defaultdict(int)
        self.inputs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def _next(self, name: str, inputs: dict[str, Any]) -> Any:
        with self._lock:
            self.calls[name] += 1
            self.inputs[name].append(inputs)
            queue = self._queues.get(name)
            item = queue.pop(0) if queue else None
        if isinstance(item, Exception):
            raise item
        return item

    def draft(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
    ) -> UsageResult[DraftResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("draft", {"plan": plan, "existing_theory": existing_theory})
        return (queued or stub_draft(plan)), None

    def discover(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        documents: list[dict[str, object]],
    ) -> UsageResult[DiscoverResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("discover", {"theory": theory, "documents": documents})
        return (queued or DiscoverResponse(proposals=[])), None

    def consolidate(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        proposals: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ConsolidateResponse]:
        """See :class:`StubTocBackend`: by default, each proposal as it came."""
        queued = self._next("consolidate", {"proposals": proposals})
        if queued is not None:
            return queued, None
        boxes: list[NewBoxWire] = []
        pathways: list[ConsolidatedPathwayWire] = []
        for proposal in proposals:
            boxes.extend(NewBoxWire.model_validate(b) for b in proposal["new_boxes"])  # type: ignore[attr-defined]
            pathways.append(
                ConsolidatedPathwayWire(
                    kind=proposal["kind"],  # type: ignore[arg-type]
                    label=str(proposal["label"]),
                    from_proposals=[str(proposal["id"])],
                    route=list(proposal["route"]),  # type: ignore[call-overload]
                    new_links=[
                        NewLinkWire.model_validate(link)
                        for link in proposal["new_links"]  # type: ignore[attr-defined]
                    ],
                )
            )
        return ConsolidateResponse(new_boxes=boxes, pathways=pathways), None

    def merge(
        self,
        *,
        plan: dict[str, object],
        boxes: list[dict[str, object]],
        pathways: list[dict[str, object]],
    ) -> UsageResult[MergeResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("merge", {"boxes": boxes, "pathways": pathways})
        default = MergeResponse(
            box_merges=[],
            decisions=[
                MergeDecisionWire(
                    pathway=str(p["key"]), action="keep", into=None, reason="Distinct route."
                )
                for p in pathways
            ],
        )
        return (queued or default), None

    def pick(
        self, *, item_text: str, candidates: list[dict[str, object]]
    ) -> UsageResult[PickResponse]:
        """See :class:`StubTocBackend`: by default, the first :data:`PICK_N` ids."""
        queued = self._next("pick", {"item_text": item_text, "candidates": candidates})
        default = PickResponse(ids=[str(c["id"]) for c in candidates[:PICK_N]])
        return (queued or default), None

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("judge", kwargs)
        if queued is not None:
            return queued, None
        words = str(kwargs.get("text") or "").split()
        return (
            JudgeResponse(
                support="weak" if words else "not_about",
                quote=" ".join(words[:8]) if words else None,
                relevance=2 if words else 0,
                relevance_reason="A similar population elsewhere." if words else None,
                condition=None,
                case_study=None,
                indicator=None,
                robust_model=None,
            ),
            None,
        )

    def figures(self, **kwargs: Any) -> UsageResult[FiguresResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("figures", kwargs)
        return (queued or FiguresResponse(figures=[])), None

    def choose(
        self,
        *,
        plan: dict[str, object],
        pathways: list[dict[str, object]],
        recorded_conditions: list[dict[str, object]],
        max_success: int,
        max_failure: int,
    ) -> UsageResult[ChooseResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next(
            "choose", {"pathways": pathways, "recorded_conditions": recorded_conditions}
        )
        default = ChooseResponse(
            pathways=[
                ChooseDecisionWire(pathway=str(p["key"]), keep=True, reason="Kept.")
                for p in pathways
            ],
            added_conditions=[],
        )
        return (queued or default), None

    def summarise(
        self, *, plan: dict[str, object], theory: dict[str, object]
    ) -> UsageResult[SummaryResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("summarise", {"theory": theory})
        if queued is not None:
            return queued, None
        links = cast(list[dict[str, Any]], theory.get("links") or [])
        boxes = cast(list[dict[str, Any]], theory.get("boxes") or [])
        return (
            SummaryResponse(
                links=[
                    LinkSentencesWire(
                        link=str(link["key"]),
                        title=f"Step {link['key']}",
                        sentence="Documents were judged for this step.",
                        # The first judged document, so citations show.
                        cites=[str(doc["id"]) for doc in (link.get("documents") or [])[:1]],
                    )
                    for link in links
                ],
                boxes=[
                    BoxDescriptionWire(
                        box=str(box["key"]),
                        description="A step in the theory.",
                        seen_in=None,
                        cites=[],
                    )
                    for box in boxes
                ],
            ),
            None,
        )

    def review(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        edits: list[str],
        report: dict[str, object] | None,
    ) -> UsageResult[ReviewResponse]:
        """See :class:`StubTocBackend`: no edits; flags How change happens after any edit."""
        inputs = {"plan": plan, "theory": theory, "edits": edits, "report": report}
        queued = self._next("review", inputs)
        if queued is not None:
            return queued, None
        return (
            ReviewResponse(
                summary="The theory's shape holds after the edits.",
                edits=[],
                report_findings=(
                    [ReportFindingWire(section="how_change_happens", why="A step changed.")]
                    if edits and report
                    else []
                ),
            ),
            None,
        )

    def report(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
    ) -> UsageResult[ReportResponse]:
        """See :class:`StubTocBackend`."""
        inputs = {"plan": plan, "theory": theory, "rows": rows, "sources": sources}
        queued = self._next("report", inputs)
        if queued is not None:
            return queued, None
        pathways = cast(list[dict[str, Any]], theory.get("pathways") or [])
        cited = {
            str(code): f" [{source['n']}]"
            for source in reversed(sources)
            for code in cast(list[str], source["links"])
        }

        def paragraph(path: dict[str, Any]) -> PathwayParagraphWire:
            first = str((path.get("links") or ["?"])[0])
            return PathwayParagraphWire(
                pathway=str(path["key"]),
                title=str(path["label"]),
                paragraph=f"The route starts at {first}.{cited.get(first, '')}",
            )

        weakest = cast(list[str], theory.get("weakest_critical_links") or [])
        return (
            ReportResponse(
                title="A drafted theory of change",
                summary="What the theory says, and where its evidence is weakest.",
                if_then_because=f"If {plan.get('intervention') or 'it'} happens, then "
                f"{plan.get('goal')}, because of the mechanism.",
                context="The setting matters.",
                weakest_links=(
                    f"The weakest link is {weakest[0]}." if weakest else "None stands out."
                ),
                pathways=[paragraph(path) for path in pathways],
                assumption_reasons=[
                    AssumptionReasonWire(row=str(row["key"]), why="The evidence is thin.")
                    for row in rows
                ],
                tests=[
                    TestRowWire(
                        link=code,
                        question="Does this step happen?",
                        indicator="A count from routine data",
                        test_and_learn="Compare before and after",
                    )
                    for code in weakest
                ],
            ),
            None,
        )
