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
    TOC_DISCOVER_MAX_OUTPUT_TOKENS,
    TOC_DISCOVER_PROMPT_VERSION,
    DiscoverResponse,
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
from policy_atlas.theory_of_change.evidence.judge_prompt import (
    TOC_JUDGE_MAX_OUTPUT_TOKENS,
    TOC_JUDGE_PROMPT_VERSION,
    JudgeResponse,
    StanceWire,
    build_judge_messages,
)
from policy_atlas.theory_of_change.merge_prompt import (
    TOC_MERGE_MAX_OUTPUT_TOKENS,
    TOC_MERGE_PROMPT_VERSION,
    MergeDecisionWire,
    MergeResponse,
    build_merge_messages,
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

    def merge(
        self, *, plan: dict[str, object], pathways: list[dict[str, object]]
    ) -> UsageResult[MergeResponse]:
        """Merge and set aside pathways (``toc_merge_v1``)."""
        ...

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """Judge one link against one document (``toc_judge_v3``).

        Keyword arguments are those of
        :func:`~policy_atlas.theory_of_change.evidence.judge_prompt.build_judge_messages`.
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
        """Choose pathways and name new conditions (``toc_choose_v1``)."""
        ...

    def summarise(
        self, *, plan: dict[str, object], theory: dict[str, object]
    ) -> UsageResult[SummaryResponse]:
        """Write the header paragraphs and sentences (``toc_summary_v1``)."""
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
        return traced_parse(
            self._client,
            self._langfuse_client,
            messages=messages,
            response_format=response_format,
            model=route().model_for(step),
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

    def merge(
        self, *, plan: dict[str, object], pathways: list[dict[str, object]]
    ) -> UsageResult[MergeResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_merge_messages(plan=plan, pathways=pathways),
            response_format=MergeResponse,
            step="toc_merge",
            max_output_tokens=TOC_MERGE_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_MERGE_PROMPT_VERSION,
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
        ("b3", "outcome", "Behaviour changes"),
        ("b4", "impact", change[:120]),
        ("b5", "failure_outcome", "Take-up stays low"),
    ]
    links = [("l1", "b1", "b2"), ("l2", "b2", "b3"), ("l3", "b3", "b4"), ("l4", "b2", "b5")]
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
                key="p1", kind="success", label="Main route", links=["l1", "l2", "l3"]
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
    - ``merge``: keeps every pathway.
    - ``judge``: *worked elsewhere* supports, quoting the first eight words of
      the document text (so the quote check passes); *holds here* not about;
      not about both when the text is empty.
    - ``choose``: keeps every pathway, no new conditions.
    - ``summarise``: plain sentences that cite nothing.

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

    def merge(
        self, *, plan: dict[str, object], pathways: list[dict[str, object]]
    ) -> UsageResult[MergeResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("merge", {"pathways": pathways})
        default = MergeResponse(
            decisions=[
                MergeDecisionWire(
                    pathway=str(p["key"]), action="keep", into=None, reason="Distinct route."
                )
                for p in pathways
            ]
        )
        return (queued or default), None

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """See :class:`StubTocBackend`."""
        queued = self._next("judge", kwargs)
        if queued is not None:
            return queued, None
        words = str(kwargs.get("text") or "").split()
        not_about = StanceWire(stance="not_about", quote=None)
        elsewhere = StanceWire(stance="supports", quote=" ".join(words[:8])) if words else not_about
        return (
            JudgeResponse(
                worked_elsewhere=elsewhere,
                holds_here=not_about,
                condition=None,
                case_study=None,
                indicator=None,
                robust_model=None,
            ),
            None,
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
                about="A drafted theory of change.",
                evidence_says="The evidence check has run.",
                evaluation_questions=["Does the critical connection hold here?"],
                links=[
                    LinkSentencesWire(
                        link=str(link["key"]),
                        elsewhere_sentence="Documents were judged for this step.",
                        elsewhere_cites=[],
                        here_sentence=None,
                        here_cites=[],
                    )
                    for link in links
                ],
                boxes=[
                    BoxDescriptionWire(
                        box=str(box["key"]),
                        description=(
                            "A step in the theory. No case studies were found in the "
                            "documents read."
                        ),
                        cites=[],
                    )
                    for box in boxes
                ],
            ),
            None,
        )
