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
from policy_atlas.core.usage import UsageResult, usage_metadata
from policy_atlas.evidence_base.sourcing.search_prompts import (
    SEARCH_GEN_MAX_OUTPUT_TOKENS,
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    SEARCH_REFORMULATE_MODEL,
    SEARCH_REFORMULATE_PROMPT_VERSION,
    SEARCH_SUGGEST_MODEL,
    SEARCH_SUGGEST_PROMPT_VERSION,
    QueriesPayload,
    ReformulatePayload,
    SearchQueriesWire,
    SearchSuggestWire,
    SuggestPayload,
    build_queries_messages,
    build_reformulate_messages,
    build_suggest_messages,
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
            payload: Scope intent payload for the ``search_queries_v1`` prompt.

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
            payload: Scope intent payload for the ``search_queries_v1`` prompt.

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


class StubSearchGenerationBackend:
    """Deterministic zero-egress search-generation backend for tests and local runs."""

    mode = "stub"

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Return a deterministic query set derived from the intent.

        Args:
            payload: Scope intent payload.

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
