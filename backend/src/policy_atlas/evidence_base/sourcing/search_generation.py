"""Generation backend seam for live-search query, reformulation, and suggestion calls.

The default stub is deterministic and zero-egress. The live backend mirrors the
screening backend posture: OpenAI structured-output parsing, optional Langfuse
full-I/O tracing, token-usage logging, and loud failures when parsing fails.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.usage import TokenUsage, UsageAccumulator, UsageResult, usage_metadata
from policy_atlas.evidence_base.sourcing.search_prompts import (
    MAX_PARAPHRASES,
    N_QUERIES,
    SEARCH_GEN_MAX_OUTPUT_TOKENS,
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION,
    SEARCH_REFORMULATE_MODEL,
    SEARCH_REFORMULATE_PROMPT_VERSION,
    SEARCH_SUGGEST_MODEL,
    SEARCH_SUGGEST_PROMPT_VERSION,
    QueriesPayload,
    ReformulatePayload,
    SearchQueriesWire,
    SearchSuggestWire,
    SuggestPayload,
    build_v2_openalex_queries_messages,
    build_v2_openalex_reformulate_messages,
    build_v2_overton_queries_messages,
    build_v2_overton_reformulate_messages,
    build_queries_messages,
    build_reformulate_messages,
    build_suggest_messages,
    validated_queries,
)

WireT = TypeVar("WireT", bound=BaseModel)


class SearchGenerationBackend(Protocol):
    """The generation seam for depth-graded search strategy calls."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Generate rapid/deep round-1 query fan-out candidates.

        Args:
            payload: Refined research-question payload for the ``search_queries_v1`` prompt.

        Returns:
            Parsed query wire output plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce parsed structured output.
        """
        ...

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        """Generate later-round reformulated queries.

        Args:
            payload: Intent plus bounded screened exemplars.

        Returns:
            Parsed reformulation wire output plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce parsed structured output.
        """
        ...

    def suggest(self, payload: SuggestPayload) -> UsageResult[SearchSuggestWire]:
        """Suggest likely papers for grounding.

        Args:
            payload: Intent plus positive screened exemplars.

        Returns:
            Parsed suggestion wire output plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce parsed structured output.
        """
        ...


class OpenAISearchGenerationBackend:
    """Live OpenAI implementation of the search-generation seam.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is read
            from the environment; keys are never read from persistent config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op and no Langfuse object is created.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    mode = "live"

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key,
            backend_name="OpenAISearchGenerationBackend",
            timeout=120.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _parse_once(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        model: str,
        response_format: type[WireT],
        usage_event: str,
        label: str,
    ) -> UsageResult[WireT]:
        return parse_structured(
            self._client,
            messages=messages,
            response_format=response_format,
            usage_event=usage_event,
            label=label,
            model=model,
            max_completion_tokens=SEARCH_GEN_MAX_OUTPUT_TOKENS,
        )

    def _call_wire(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        model: str,
        response_format: type[WireT],
        prompt_version: str,
        usage_event: str,
        trace_name: str,
        label: str,
    ) -> UsageResult[WireT]:
        langfuse_client = self._langfuse_client

        def _update(span: Any, result: UsageResult[WireT]) -> None:
            wire, usage = result
            span.update(
                input={"messages": messages},
                output=wire.model_dump(),
                model=model,
                metadata={
                    "prompt_version": prompt_version,
                    **usage_metadata(usage),
                },
            )

        wire, usage = tracing.traced_call(
            langfuse_client,
            name=trace_name,
            as_type="generation",
            call=lambda: self._parse_once(
                messages=messages,
                model=model,
                response_format=response_format,
                usage_event=usage_event,
                label=label,
            ),
            update=_update,
        )
        return wire, usage

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Generate query fan-out candidates through structured OpenAI output.

        Args:
            payload: Refined research-question payload for the ``search_queries_v1`` prompt.

        Returns:
            Parsed query wire output plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        return self._call_wire(
            messages=build_queries_messages(payload),
            model=SEARCH_QUERIES_MODEL,
            response_format=SearchQueriesWire,
            prompt_version=SEARCH_QUERIES_PROMPT_VERSION,
            usage_event="search_generation.queries.usage",
            trace_name="search_queries",
            label="search query-generation",
        )

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        """Generate reformulated queries through structured OpenAI output.

        Args:
            payload: Intent plus bounded screened exemplars.

        Returns:
            Parsed reformulation wire output plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        return self._call_wire(
            messages=build_reformulate_messages(payload),
            model=SEARCH_REFORMULATE_MODEL,
            response_format=SearchQueriesWire,
            prompt_version=SEARCH_REFORMULATE_PROMPT_VERSION,
            usage_event="search_generation.reformulate.usage",
            trace_name=f"search_reformulate:r{payload.round_index}",
            label="search reformulation",
        )

    def suggest(self, payload: SuggestPayload) -> UsageResult[SearchSuggestWire]:
        """Generate paper suggestions through structured OpenAI output.

        Args:
            payload: Intent plus positive screened exemplars.

        Returns:
            Parsed suggestion wire output plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        return self._call_wire(
            messages=build_suggest_messages(payload),
            model=SEARCH_SUGGEST_MODEL,
            response_format=SearchSuggestWire,
            prompt_version=SEARCH_SUGGEST_PROMPT_VERSION,
            usage_event="search_generation.suggest.usage",
            trace_name="search_suggest",
            label="search suggestion",
        )


class V2SingleQueryWire(BaseModel):
    """One generated query string from a provider-specific V2 prompt call."""

    query: str


class V2SearchGenerationBackend(OpenAISearchGenerationBackend):
    """Live split-prompt generation backend (OpenAlex and Overton separately).

    This backend preserves the ``SearchGenerationBackend`` protocol and returns
    the same ``SearchQueriesWire`` shape as V1. The difference is methodology:
    it runs separate prompt calls for OpenAlex Boolean generation and Overton
    semantic generation, for both round-1 generation and reformulation.
    """

    def _combine_usage(self, usages: list[TokenUsage | None]) -> TokenUsage | None:
        """Aggregate token usage from multiple internal prompt calls."""
        accumulator = UsageAccumulator()
        saw_usage = False
        for usage in usages:
            if usage is not None:
                saw_usage = True
            accumulator.add(usage)
        if not saw_usage:
            return None
        totals = accumulator.payload()
        return TokenUsage(
            prompt=totals["prompt"],
            completion=totals["completion"],
            total=totals["total"],
            cached=totals["cached"],
        )

    @staticmethod
    def _build_wire(
        *,
        queries: list[str],
        overton_paraphrases: list[str],
    ) -> SearchQueriesWire:
        """Normalize provider outputs into the shared wire schema."""
        cleaned_queries, cleaned_paraphrases = validated_queries(
            SearchQueriesWire(
                queries=queries,
                overton_paraphrases=overton_paraphrases,
            )
        )
        return SearchQueriesWire(
            queries=cleaned_queries,
            overton_paraphrases=cleaned_paraphrases,
        )

    def _generate_many(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        count: int,
        model: str,
        prompt_version: str,
        usage_event: str,
        trace_prefix: str,
        label: str,
    ) -> UsageResult[list[str]]:
        """Run repeated single-query calls and collect outputs plus usage."""
        queries: list[str] = []
        usages: list[TokenUsage | None] = []
        for index in range(count):
            wire, usage = self._call_wire(
                messages=messages,
                model=model,
                response_format=V2SingleQueryWire,
                prompt_version=prompt_version,
                usage_event=usage_event,
                trace_name=f"{trace_prefix}:{index + 1}",
                label=label,
            )
            queries.append(wire.query)
            usages.append(usage)
        return queries, self._combine_usage(usages)

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Generate round-1 queries via separate OpenAlex and Overton prompts.

        Args:
            payload: Refined research question and optional search guidance.

        Returns:
            Shared query wire output plus aggregated token usage.
        """
        openalex_queries, openalex_usage = self._generate_many(
            messages=build_v2_openalex_queries_messages(payload),
            count=N_QUERIES,
            model=SEARCH_QUERIES_MODEL,
            prompt_version=SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
            usage_event="search_generation.v2.openalex.queries.usage",
            trace_prefix="search_queries_v2_openalex",
            label="v2 openalex query-generation",
        )
        overton_queries, overton_usage = self._generate_many(
            messages=build_v2_overton_queries_messages(payload),
            count=MAX_PARAPHRASES,
            model=SEARCH_QUERIES_MODEL,
            prompt_version=SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION,
            usage_event="search_generation.v2.overton.queries.usage",
            trace_prefix="search_queries_v2_overton",
            label="v2 overton query-generation",
        )
        return (
            self._build_wire(
                queries=openalex_queries,
                overton_paraphrases=overton_queries,
            ),
            self._combine_usage([openalex_usage, overton_usage]),
        )

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        """Generate reformulated queries with separate OpenAlex and Overton prompts.

        Args:
            payload: Research question plus this round's screened exemplars.

        Returns:
            Shared reformulation wire output plus aggregated token usage.
        """
        openalex_queries, openalex_usage = self._generate_many(
            messages=build_v2_openalex_reformulate_messages(payload),
            count=N_QUERIES,
            model=SEARCH_REFORMULATE_MODEL,
            prompt_version=SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
            usage_event="search_generation.v2.openalex.reformulate.usage",
            trace_prefix=f"search_reformulate_v2_openalex:r{payload.round_index}",
            label="v2 openalex reformulation",
        )
        overton_queries, overton_usage = self._generate_many(
            messages=build_v2_overton_reformulate_messages(payload),
            count=MAX_PARAPHRASES,
            model=SEARCH_REFORMULATE_MODEL,
            prompt_version=SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION,
            usage_event="search_generation.v2.overton.reformulate.usage",
            trace_prefix=f"search_reformulate_v2_overton:r{payload.round_index}",
            label="v2 overton reformulation",
        )
        return (
            self._build_wire(
                queries=openalex_queries,
                overton_paraphrases=overton_queries,
            ),
            self._combine_usage([openalex_usage, overton_usage]),
        )


class StubSearchGenerationBackend:
    """Deterministic zero-egress search-generation backend for tests and local runs."""

    mode = "stub"

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Return a deterministic query set derived from the intent.

        Args:
            payload: Refined research-question payload.

        Returns:
            Deterministic query wire output plus no token usage.
        """
        intent = payload.intent.strip()
        return (
            SearchQueriesWire(
                queries=[intent, f"{intent} evidence", f"{intent} evaluation"][:3],
                overton_paraphrases=[f"Evidence about {intent}"],
            ),
            None,
        )

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        """Return a deterministic later-round query variation.

        Args:
            payload: Intent plus bounded screened exemplars.

        Returns:
            Deterministic reformulation wire output plus no token usage.
        """
        intent = payload.intent.strip()
        return (
            SearchQueriesWire(
                queries=[f"{intent} further evidence", f"{intent} additional studies"],
                overton_paraphrases=[f"Further evidence about {intent}"],
            ),
            None,
        )

    def suggest(self, payload: SuggestPayload) -> UsageResult[SearchSuggestWire]:
        """Return no suggestions.

        Args:
            payload: Intent plus positive screened exemplars; ignored by the stub.

        Returns:
            Empty suggestion wire output plus no token usage.
        """
        return SearchSuggestWire(papers=[]), None
