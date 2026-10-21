"""Generation backend seam for live-search query, reformulation, and suggestion calls.

The default stub is deterministic and zero-egress. The live backend mirrors the
screening backend posture: OpenAI structured-output parsing, optional Langfuse
full-I/O tracing, token-usage logging, and loud failures when parsing fails.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol, TypeVar

import boto3
import structlog
from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from policy_atlas.core import tracing
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.usage import (
    TokenUsage,
    UsageAccumulator,
    UsageResult,
    usage_details,
    usage_metadata,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    MAX_PARAPHRASES,
    N_QUERIES,
    SEARCH_GEN_MAX_OUTPUT_TOKENS,
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_FILE,
    SEARCH_QUERIES_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OPENALEX_PROMPT_FILE,
    SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OVERTON_PROMPT_FILE,
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
    build_queries_messages,
    build_reformulate_messages,
    build_suggest_messages,
    build_v2_openalex_queries_messages,
    build_v2_openalex_reformulate_messages,
    build_v2_overton_queries_messages,
    build_v2_overton_reformulate_messages,
    validated_queries,
)

WireT = TypeVar("WireT", bound=BaseModel)

log = structlog.get_logger()

SEARCH_QUERIES_CLAUDE_PROMPT_FILE = Path(__file__).parent / "search_queries_system_claude_v1.txt"
SEARCH_QUERIES_CLAUDE_PROMPT_VERSION = SEARCH_QUERIES_CLAUDE_PROMPT_FILE.stem.replace(
    "_system", ""
)
SEARCH_QUERIES_CLAUDE_SYSTEM_PROMPT = SEARCH_QUERIES_CLAUDE_PROMPT_FILE.read_text(encoding="utf-8")
CLAUDE_QUERY_TOOL_NAME = "emit_search_queries"


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
        api_key: Optional OpenAI API key. If omitted, the route's key variable is read
            from the environment; keys are never read from persistent config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op and no Langfuse object is created.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    mode = "live"
    # The committed prompt file(s) round-1 query generation reads, so an eval
    # can record exactly which wording produced a run.
    prompt_files: tuple[Path, ...] = (SEARCH_QUERIES_PROMPT_FILE,)

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
        metadata: dict[str, Any] | None = None,
    ) -> UsageResult[WireT]:
        langfuse_client = self._langfuse_client

        def _update(span: Any, result: UsageResult[WireT]) -> None:
            wire, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=wire.model_dump(),
                model=model,
                metadata={
                    "prompt_version": prompt_version,
                    **(metadata or {}),
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
            trace_name="search:generate_queries",
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
            trace_name="search:reformulate",
            label="search reformulation",
            metadata={"round_index": payload.round_index},
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
            trace_name="search:suggest",
            label="search suggestion",
        )


class ClaudeSearchGenerationBackend:
    """Live Bedrock Converse implementation for query generation.

    Args:
        api_key: Optional OpenAI API key passed to the inner backend.
        langfuse_client: Optional Langfuse client for generation tracing.
        client: Optional Bedrock Runtime client, primarily for tests.
        inner: Optional backend for reformulation and suggestion, primarily for tests.
    """

    mode = "live"
    prompt_files: tuple[Path, ...] = (SEARCH_QUERIES_CLAUDE_PROMPT_FILE,)

    def __init__(
        self,
        *,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
        client: Any | None = None,
        inner: OpenAISearchGenerationBackend | None = None,
    ) -> None:
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION") or "eu-west-2",
        )
        self._inner = inner or OpenAISearchGenerationBackend(
            api_key,
            langfuse_client=langfuse_client,
        )
        self._langfuse_client = langfuse_client
        model = route().search_queries.model
        if not model:
            raise RuntimeError(
                "ClaudeSearchGenerationBackend needs a search_queries model in the route file."
            )
        self._model: str = model

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        """Generate query fan-out candidates with Claude tool use.

        Args:
            payload: Refined research-question payload for query generation.

        Returns:
            Parsed query wire output plus Bedrock token usage.

        Raises:
            RuntimeError: If Bedrock returns invalid tool output or usage.
        """
        messages = build_queries_messages(payload)
        user_text = messages[1]["content"]
        model = self._model
        tool = {
            "toolSpec": {
                "name": CLAUDE_QUERY_TOOL_NAME,
                "description": "Return the generated search queries for the research question.",
                "inputSchema": {"json": SearchQueriesWire.model_json_schema()},
            }
        }
        bedrock_messages: Any = [{"role": "user", "content": [{"text": user_text}]}]
        tool_config: Any = {
            "tools": [tool],
            "toolChoice": {"tool": {"name": CLAUDE_QUERY_TOOL_NAME}},
        }

        def _call() -> UsageResult[SearchQueriesWire]:
            response = self._client.converse(
                modelId=model,
                system=[{"text": SEARCH_QUERIES_CLAUDE_SYSTEM_PROMPT}],
                messages=bedrock_messages,
                inferenceConfig={"maxTokens": SEARCH_GEN_MAX_OUTPUT_TOKENS},
                toolConfig=tool_config,
            )
            blocks = response["output"]["message"]["content"]
            tool_blocks = [block["toolUse"] for block in blocks if "toolUse" in block]
            if not tool_blocks:
                raise RuntimeError("no tool call")
            if len(tool_blocks) != 1:
                raise RuntimeError(f"{len(tool_blocks)} tool calls")
            tool_use = tool_blocks[0]
            if tool_use.get("name") != CLAUDE_QUERY_TOOL_NAME:
                raise RuntimeError("unexpected tool name")
            tool_input = tool_use.get("input")
            if not isinstance(tool_input, dict):
                raise RuntimeError("tool input is not an object")
            try:
                wire = SearchQueriesWire.model_validate(tool_input)
            except ValidationError as exc:
                raise RuntimeError("tool input failed validation") from exc
            usage_data = response.get("usage")
            if not isinstance(usage_data, dict):
                raise RuntimeError("usage fields must be integers")
            values = {
                "prompt": usage_data.get("inputTokens"),
                "completion": usage_data.get("outputTokens"),
                "total": usage_data.get("totalTokens"),
            }
            if any(
                not isinstance(value, int) or isinstance(value, bool) for value in values.values()
            ):
                raise RuntimeError("usage fields must be integers")
            cached = usage_data.get("cacheReadInputTokens")
            if cached is not None and (not isinstance(cached, int) or isinstance(cached, bool)):
                raise RuntimeError("usage fields must be integers")
            usage = TokenUsage(cached=cached, **values)
            log.info("search_generation.claude.queries.usage", **usage_metadata(usage))
            return wire, usage

        def _update(span: Any, result: UsageResult[SearchQueriesWire]) -> None:
            wire, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"system": SEARCH_QUERIES_CLAUDE_SYSTEM_PROMPT, "user": user_text},
                output=wire.model_dump(),
                model=model,
                metadata={
                    "prompt_version": SEARCH_QUERIES_CLAUDE_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        return tracing.traced_call(
            self._langfuse_client,
            name="search:generate_queries",
            as_type="generation",
            call=_call,
            update=_update,
        )

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        """Delegate query reformulation to the inner OpenAI backend."""
        return self._inner.reformulate(payload)

    def suggest(self, payload: SuggestPayload) -> UsageResult[SearchSuggestWire]:
        """Delegate paper suggestions to the inner OpenAI backend."""
        return self._inner.suggest(payload)


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

    prompt_files = (SEARCH_QUERIES_V2_OPENALEX_PROMPT_FILE, SEARCH_QUERIES_V2_OVERTON_PROMPT_FILE)

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
