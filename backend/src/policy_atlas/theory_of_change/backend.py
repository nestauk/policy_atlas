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
from collections.abc import Callable, Iterable, Iterator
from typing import Any, Protocol, cast

from langfuse import Langfuse
from openai.lib._parsing._completions import type_to_response_format_param
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core import tracing
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import (
    openai_kwargs,
    resolve_openai_client,
    traced_parse,
    with_system_breakpoint,
)
from policy_atlas.core.usage import (
    UsageResult,
    log_usage,
    token_usage_from_provider,
    usage_details,
    usage_metadata,
)
from policy_atlas.evidence_search.synthesis.cache_modes import cache_mode_for
from policy_atlas.theory_of_change.check.choose_prompt import (
    TOC_CHOOSE_MAX_OUTPUT_TOKENS,
    TOC_CHOOSE_PROMPT_VERSION,
    ChooseDecisionWire,
    ChooseResponse,
    build_choose_messages,
)
from policy_atlas.theory_of_change.check.discover_prompt import (
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
from policy_atlas.theory_of_change.check.figures_prompt import (
    TOC_FIGURES_MAX_OUTPUT_TOKENS,
    TOC_FIGURES_PROMPT_VERSION,
    FiguresResponse,
    build_figures_messages,
)
from policy_atlas.theory_of_change.check.judge_prompt import (
    TOC_JUDGE_MAX_OUTPUT_TOKENS,
    TOC_JUDGE_PROMPT_VERSION,
    JudgeResponse,
    build_judge_messages,
)
from policy_atlas.theory_of_change.check.merge_prompt import (
    TOC_MERGE_MAX_OUTPUT_TOKENS,
    TOC_MERGE_PROMPT_VERSION,
    MergeDecisionWire,
    MergeResponse,
    build_merge_messages,
)
from policy_atlas.theory_of_change.check.pick_prompt import (
    PICK_N,
    TOC_PICK_MAX_OUTPUT_TOKENS,
    TOC_PICK_PROMPT_VERSION,
    PickResponse,
    build_pick_messages,
)
from policy_atlas.theory_of_change.check.summary_prompt import (
    TOC_SUMMARY_MAX_OUTPUT_TOKENS,
    TOC_SUMMARY_PROMPT_VERSION,
    BoxDescriptionWire,
    LinkSentencesWire,
    SummaryResponse,
    build_summary_messages,
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
from policy_atlas.theory_of_change.import_prompt import (
    TOC_IMPORT_MAX_OUTPUT_TOKENS,
    TOC_IMPORT_PROMPT_VERSION,
    ImportArrowWire,
    ImportBoxWire,
    ImportResponse,
    build_import_messages,
)
from policy_atlas.theory_of_change.plausibility_prompt import (
    PLAUSIBILITY_MAX_OUTPUT_TOKENS,
    TOC_SENSE_CHECK_PROMPT_VERSION,
    TOC_VERDICT_PROMPT_VERSION,
    SenseCheckResponse,
    TheoryVerdictResponse,
    build_sense_check_messages,
    build_verdict_messages,
)
from policy_atlas.theory_of_change.report_prompt import (
    TOC_REPORT_MAX_OUTPUT_TOKENS,
    TOC_REPORT_PROMPT_VERSION,
    ConnectionReasonWire,
    FoundRouteWire,
    PathwayLineWire,
    ReportResponse,
    WhatToTestWire,
    build_report_messages,
)
from policy_atlas.theory_of_change.report_stream import REPORT_STEP, StreamFailed, consume
from policy_atlas.theory_of_change.review_prompt import (
    TOC_REVIEW_MAX_OUTPUT_TOKENS,
    TOC_REVIEW_PROMPT_VERSION,
    ReportFindingWire,
    ReviewResponse,
    build_review_messages,
)

#: The route step the draft call uses.
DRAFT_STEP = "toc_draft"

#: What a stub report stream may be scripted with: text pieces, with an
#: exception among them to fail mid-stream.
type ScriptedStream = Iterable[str | BaseException]


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

    def draft_stream(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[DraftResponse]:
        """Write the same draft as :meth:`draft`, streamed (task 054, S12).

        One call, never retried. Each piece of the answer's JSON text goes to
        ``on_text`` as it arrives; the whole text is then parsed into
        :class:`DraftResponse` as :meth:`draft` parses it.

        Raises:
            FirstContentTimeout: If no words came within ``first_content_s``.
            Exception: On any stream or parse failure; the caller falls back. The
                live backend raises :class:`StreamFailed` (the original error as
                its cause), carrying the tokens the stream used.
        """
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
        self, *, item_text: str, candidates: list[dict[str, object]], n: int = PICK_N
    ) -> UsageResult[PickResponse]:
        """Pick the ``n`` documents the judge reads for one link (``toc_pick_v1``)."""
        ...

    def judge(self, **kwargs: Any) -> UsageResult[JudgeResponse]:
        """Judge one link against one document (``toc_judge_v4``).

        Keyword arguments are those of
        :func:`~policy_atlas.theory_of_change.check.judge_prompt.build_judge_messages`.
        """
        ...

    def figures(self, **kwargs: Any) -> UsageResult[FiguresResponse]:
        """Find the size of change behind one link in one document (``toc_figures_v1``).

        Keyword arguments are those of
        :func:`~policy_atlas.theory_of_change.check.figures_prompt.build_figures_messages`.
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
        """Choose pathways and name new conditions (``toc_choose_v4``)."""
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

    def report_stream(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[ReportResponse]:
        """Write the same report as :meth:`report`, streamed (task 054's 058 alignment, S4).

        One call, never retried. Each piece of the answer's JSON text goes to
        ``on_text`` as it arrives; the whole text is then parsed into
        :class:`ReportResponse` as :meth:`report` parses it.

        Raises:
            FirstContentTimeout: If no words came within ``first_content_s``.
            Exception: On any stream or parse failure; the caller falls back. The
                live backend raises :class:`StreamFailed` (the original error as
                its cause), carrying the tokens the stream used.
        """
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

    def sense_check(
        self, *, plan: dict[str, object], documents: list[dict[str, str]]
    ) -> UsageResult[SenseCheckResponse]:
        """Judge whether the intervention could credibly cause the goal (``toc_sense_check_v1``)."""
        ...

    def theory_verdict(
        self, *, theory: dict[str, object], sense_check: dict[str, object] | None
    ) -> UsageResult[TheoryVerdictResponse]:
        """Give the checked theory one overall verdict and a headline (``toc_verdict_v1``)."""
        ...

    def import_theory(self, *, pages: list[str]) -> UsageResult[ImportResponse]:
        """Transcribe an uploaded diagram (``toc_import_v1``, increment 5)."""
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
        self._client = resolve_openai_client(api_key, backend_name="OpenAITocBackend")
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
            step=step,
            # The step's effort (Terra: "none"); the judge was measured at it,
            # and without it Terra's default gave unstable stances.
            reasoning_effort=route().effort_for(step),
            timeout_s=route().timeout_for(step),
            prompt_cache=cache_mode_for(step),
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
            step=DRAFT_STEP,
            max_output_tokens=TOC_DRAFT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_DRAFT_PROMPT_VERSION,
        )

    def draft_stream_request(self, messages: list[ChatCompletionMessageParam]) -> dict[str, Any]:
        """The streamed draft call's request: :meth:`draft`'s request, streamed (task 054, S12).

        Args:
            messages: The draft call's messages (:func:`build_draft_messages`).

        Returns:
            Keyword arguments for ``chat.completions.create``.
        """
        return self._stream_request(
            messages,
            step=DRAFT_STEP,
            response_format=DraftResponse,
            max_output_tokens=TOC_DRAFT_MAX_OUTPUT_TOKENS,
        )

    def draft_stream(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[DraftResponse]:
        """See :class:`TocBackend`. Traced as one Langfuse generation, attempt 1."""
        return self._stream_parse(
            build_draft_messages(plan, existing_theory=existing_theory, problems=problems),
            step=DRAFT_STEP,
            response_format=DraftResponse,
            max_output_tokens=TOC_DRAFT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_DRAFT_PROMPT_VERSION,
            on_text=on_text,
            first_content_s=first_content_s,
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
        self, *, item_text: str, candidates: list[dict[str, object]], n: int = PICK_N
    ) -> UsageResult[PickResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_pick_messages(item_text=item_text, candidates=candidates, n=n),
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

    def sense_check(
        self, *, plan: dict[str, object], documents: list[dict[str, str]]
    ) -> UsageResult[SenseCheckResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_sense_check_messages(plan, documents),
            response_format=SenseCheckResponse,
            step="toc_sense_check",
            max_output_tokens=PLAUSIBILITY_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_SENSE_CHECK_PROMPT_VERSION,
        )

    def theory_verdict(
        self, *, theory: dict[str, object], sense_check: dict[str, object] | None
    ) -> UsageResult[TheoryVerdictResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_verdict_messages(theory, sense_check),
            response_format=TheoryVerdictResponse,
            step="toc_verdict",
            max_output_tokens=PLAUSIBILITY_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_VERDICT_PROMPT_VERSION,
        )

    def import_theory(self, *, pages: list[str]) -> UsageResult[ImportResponse]:
        """See :class:`TocBackend`."""
        return self._call(
            build_import_messages(pages),
            response_format=ImportResponse,
            step="toc_import",
            max_output_tokens=TOC_IMPORT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_IMPORT_PROMPT_VERSION,
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

    def report_stream_request(
        self, messages: list[ChatCompletionMessageParam]
    ) -> dict[str, Any]:
        """The streamed report call's request: :meth:`report`'s request, streamed (A12).

        Args:
            messages: The report call's messages (:func:`build_report_messages`).

        Returns:
            Keyword arguments for ``chat.completions.create``.
        """
        return self._stream_request(
            messages,
            step=REPORT_STEP,
            response_format=ReportResponse,
            max_output_tokens=TOC_REPORT_MAX_OUTPUT_TOKENS,
        )

    def report_stream(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[ReportResponse]:
        """See :class:`TocBackend`. Traced as one Langfuse generation, attempt 1."""
        return self._stream_parse(
            build_report_messages(plan=plan, theory=theory, rows=rows, sources=sources),
            step=REPORT_STEP,
            response_format=ReportResponse,
            max_output_tokens=TOC_REPORT_MAX_OUTPUT_TOKENS,
            prompt_version=TOC_REPORT_PROMPT_VERSION,
            on_text=on_text,
            first_content_s=first_content_s,
        )

    def _stream_request(
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        step: str,
        response_format: type[BaseModel],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        """A step's ordinary request, streamed.

        The same keyword arguments ``chat.completions.parse`` sends for the
        step (the route step's model, effort, timeout and cache mode, the
        messages, the token cap, and the strict JSON schema that ``parse``
        derives from the answer format), plus ``stream`` and ``stream_options``.
        """
        cache = cache_mode_for(step)
        return {
            "messages": with_system_breakpoint(messages) if cache == "breakpoint" else messages,
            "response_format": type_to_response_format_param(response_format),
            **openai_kwargs(
                route().model_for(step),
                reasoning_effort=route().effort_for(step),
                prompt_cache=cache,
                timeout_s=route().timeout_for(step),
            ),
            "max_completion_tokens": max_output_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

    def _stream_parse[T: BaseModel](
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        step: str,
        response_format: type[T],
        max_output_tokens: int,
        prompt_version: str,
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[T]:
        """Make one streamed call and parse its whole text as the ordinary call does.

        Each text piece goes to ``on_text`` on this thread (:func:`consume`);
        the call is traced as one Langfuse generation, attempt 1, under the
        task's session.

        Raises:
            StreamFailed: On any stream or parse failure (the original error is
                its ``__cause__``), carrying the tokens the stream reported.
        """
        request = self._stream_request(
            messages,
            step=step,
            response_format=response_format,
            max_output_tokens=max_output_tokens,
        )
        model = route().model_for(step)
        metadata = {
            "step": step,
            "attempt": 1,
            "streamed": True,
            "prompt_version": prompt_version,
            "reasoning_effort": route().effort_for(step),
            "prompt_cache": cache_mode_for(step),
        }
        held: dict[str, Any] = {}

        def pieces() -> Iterator[str]:
            completions: Any = self._client.chat.completions
            stream = completions.create(**request)
            held["stream"] = stream
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if choices:
                    fragment = getattr(getattr(choices[0], "delta", None), "content", None)
                    if isinstance(fragment, str) and fragment:
                        yield fragment
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    held["usage"] = chunk_usage

        def cancel() -> None:
            stream = held.get("stream")
            if stream is not None:
                stream.close()

        def run(span: Any | None) -> UsageResult[T]:
            if span is not None:
                span.update(input={"messages": messages}, model=model, metadata=metadata)
            try:
                text = consume(
                    pieces(), first_content_s=first_content_s, on_fragment=on_text, cancel=cancel
                )
                log_usage(f"{step}.usage", held.get("usage"))
                wire = response_format.model_validate_json(text)
            except Exception as exc:
                # The tokens used so far go with the failure, so the step's cost counts them.
                raise StreamFailed(token_usage_from_provider(held.get("usage"))) from exc
            usage = token_usage_from_provider(held.get("usage"))
            if span is not None:
                span.update(
                    usage_details=usage_details(usage),
                    output=wire.model_dump(),
                    metadata={**metadata, **usage_metadata(usage)},
                )
            return wire, usage

        if self._langfuse_client is None:
            return run(None)
        # Under the task's Langfuse session, as :func:`traced_parse` opens the ordinary call.
        with (
            tracing.trace_scope(session_id=self._session_id),
            tracing._observation(
                self._langfuse_client,
                name=f"toc:{step.removeprefix('toc_')}",
                as_type="generation",
            ) as span,
        ):
            return run(span)


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


#: Characters per piece of the stub's streamed report and draft.
STUB_PIECE = 40


def _pieces(script: ScriptedStream) -> Iterator[str]:
    """A scripted stream's text pieces; an exception among them is raised there."""
    for piece in script:
        if isinstance(piece, BaseException):
            raise piece
        yield piece


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
    - ``report_stream``: the ``report`` answer as JSON in small pieces, or
      the queued script (see :meth:`report_stream`).
    - ``draft_stream``: the ``draft`` answer the same way (see :meth:`draft_stream`).
    - ``sense_check``: plausible, too little evidence, no warning or note.
    - ``theory_verdict``: plausible, too little evidence.
    - ``import_theory``: a three-box chain with two drawn arrows.

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

    def draft_stream(
        self,
        *,
        plan: dict[str, object],
        existing_theory: str | None,
        problems: list[str] | None = None,
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[DraftResponse]:
        """See :class:`StubTocBackend`.

        A queued ``draft_stream`` item scripts the stream as one for
        :meth:`report_stream` does. With nothing queued, :meth:`draft`'s
        answer is sent as JSON in small pieces, so a keyless run shows the
        draft being drawn.
        """
        script = self._script(
            "draft_stream",
            lambda: self.draft(plan=plan, existing_theory=existing_theory, problems=problems)[0],
        )
        text = consume(_pieces(script), first_content_s=first_content_s, on_fragment=on_text)
        return DraftResponse.model_validate_json(text), None

    def _script(self, name: str, answer: Callable[[], BaseModel]) -> ScriptedStream:
        """A stream's pieces: the queued script under ``name``, else ``answer()`` in pieces."""
        with self._lock:
            self.calls[name] += 1
            queue = self._queues.get(name)
            item = queue.pop(0) if queue else None
        if isinstance(item, BaseException):
            raise item
        if item is None:
            text = answer().model_dump_json()
            return [text[at : at + STUB_PIECE] for at in range(0, len(text), STUB_PIECE)]
        return cast(ScriptedStream, item() if callable(item) else item)

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
        self, *, item_text: str, candidates: list[dict[str, object]], n: int = PICK_N
    ) -> UsageResult[PickResponse]:
        """See :class:`StubTocBackend`: by default, the first ``n`` ids."""
        queued = self._next("pick", {"item_text": item_text, "candidates": candidates})
        default = PickResponse(ids=[str(c["id"]) for c in candidates[:n]])
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

    def sense_check(
        self, *, plan: dict[str, object], documents: list[dict[str, str]]
    ) -> UsageResult[SenseCheckResponse]:
        """See :class:`StubTocBackend`: plausible, too little evidence, no warning or note."""
        queued = self._next("sense_check", {"plan": plan, "documents": documents})
        return (
            queued
            or SenseCheckResponse(
                active_ingredient="What the plan changes.",
                best_route="Through the plan's own route.",
                mechanism="plausible",
                mechanism_reason="A credible route exists.",
                evidence="too_little",
                evidence_reason="No document evaluates it.",
                warning=None,
                note=None,
                quotes=[],
            )
        ), None

    def theory_verdict(
        self, *, theory: dict[str, object], sense_check: dict[str, object] | None
    ) -> UsageResult[TheoryVerdictResponse]:
        """See :class:`StubTocBackend`: plausible, too little evidence."""
        queued = self._next("theory_verdict", {"theory": theory, "sense_check": sense_check})
        return (
            queued
            or TheoryVerdictResponse(
                carrying_step="#1",
                mechanism="plausible",
                evidence="too_little",
                reason="The carrying step is credible but thinly evidenced.",
                headline="Too little evidence was found that the key steps happen.",
            )
        ), None

    def import_theory(self, *, pages: list[str]) -> UsageResult[ImportResponse]:
        """See :class:`StubTocBackend`: a three-box chain with two drawn arrows."""
        queued = self._next("import_theory", {"pages": pages})
        return (
            queued
            or ImportResponse(
                is_theory_of_change=True,
                title="An uploaded theory",
                boxes=[
                    ImportBoxWire(
                        ref="b1", text="Fund the programme", layer="input", shown_as="Inputs"
                    ),
                    ImportBoxWire(
                        ref="b2", text="People take part", layer="output", shown_as="Outputs"
                    ),
                    ImportBoxWire(
                        ref="b3", text="Lives improve", layer="impact", shown_as="Impact"
                    ),
                ],
                arrows=[
                    ImportArrowWire(source="b1", target="b2", how="drawn", label=None),
                    ImportArrowWire(source="b2", target="b3", how="drawn", label=None),
                ],
                groups=[],
                notes=[],
                unreadable=[],
            )
        ), None

    def report_stream(
        self,
        *,
        plan: dict[str, object],
        theory: dict[str, object],
        rows: list[dict[str, object]],
        sources: list[dict[str, object]],
        on_text: Callable[[str], None],
        first_content_s: float | None,
    ) -> UsageResult[ReportResponse]:
        """See :class:`StubTocBackend`.

        A queued ``report_stream`` item scripts the stream: an exception is
        raised at once; a callable is called for the pieces; anything else is
        the pieces (an exception among them fails the stream there). With
        nothing queued, :meth:`report`'s answer is sent as JSON in small
        pieces, so a keyless run shows the report being written.
        """
        script = self._script(
            "report_stream",
            lambda: self.report(plan=plan, theory=theory, rows=rows, sources=sources)[0],
        )
        text = consume(_pieces(script), first_content_s=first_content_s, on_fragment=on_text)
        return ReportResponse.model_validate_json(text), None

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
            for code in cast(list[str], source["connections"])
        }

        def line(path: dict[str, Any]) -> PathwayLineWire:
            first = str((path.get("connections") or ["?"])[0])
            return PathwayLineWire(
                pathway=str(path["key"]),
                title=str(path["label"]),
                sentence=f"The route starts at {first}.{cited.get(first, '')}",
            )

        weakest = cast(list[str], theory.get("weakest_critical_connections") or [])
        return (
            ReportResponse(
                title="A drafted theory of change",
                summary="What the theory says, and where its evidence is weakest.",
                if_then_because=f"If {plan.get('intervention') or 'it'} happens, then "
                f"{plan.get('goal')}, because of the mechanism.",
                context="The setting matters.",
                question="This report asks whether the intervention reaches its goal.",
                verdict_reason=(
                    "The evidence is thin."
                    + (
                        " Evaluations of the whole programme were found."
                        + cited.get("programme", "")
                        if theory.get("whole_programme")
                        else ""
                    )
                ),
                pathways=[line(path) for path in pathways if path.get("kind") == "success"],
                how_it_could_fail=(
                    f"The weakest connection is {weakest[0]}." if weakest else "None stands out."
                ),
                connection_reasons=[
                    ConnectionReasonWire(connection=str(row["code"]), why="The evidence is thin.")
                    for row in rows
                ],
                found_routes=[
                    FoundRouteWire(
                        route=str(found["key"]),
                        sentence=f"The evidence describes this route.{cited.get('expand', '')}",
                    )
                    for found in cast(list[dict[str, Any]], theory.get("found_routes") or [])
                ],
                supporting_activities=[
                    f"{text}.{cited.get('programme', '')}"
                    for text in cast(list[str], theory.get("supporting_activities") or [])
                ],
                tests=[
                    WhatToTestWire(
                        connection=code,
                        sentence="Find out whether this step happens, from routine data.",
                    )
                    for code in weakest
                ],
            ),
            None,
        )
