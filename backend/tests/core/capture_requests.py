"""Record the exact HTTP request every model call site sends, on the ``bedrock`` route.

This is a plain script, not a pytest module. ``test_request_capture.py`` runs it in
a child process, because the test suite's ``conftest.py`` removes the route
variable and many model ids and reasoning efforts are read from the route when
their modules are first imported. Run it by hand with::

    POLICY_ATLAS_MODEL_ROUTE=bedrock AWS_BEARER_TOKEN_BEDROCK=throwaway \\
        uv run python tests/core/capture_requests.py out.json

How it works, in plain terms:

- The ``OpenAI`` name in ``core.openai_client`` is swapped for a factory that builds
  a real OpenAI SDK (software development kit) client whose network layer is an
  ``httpx.MockTransport``: nothing leaves the machine. The transport writes down
  each request's address path, its JSON body and its timeout, then sends back a
  made-up ("canned") answer shaped so the call site's own code runs to its end.
- Requests go to the OpenAI Responses endpoint (``/responses``). A canned answer
  is derived from the request itself: the smallest JSON object that fits the
  request's answer schema, or one call of the tool the request forces. Streamed
  requests get the same text as server-sent events (SSE), the line-by-line
  format the provider streams in, ending with ``response.completed``.
- Each entry below drives one call site with fixed inputs written in this file
  (no database, no outside text) and keeps one of the requests it made. The
  script fails if a driver makes a different number of requests than expected
  (a silent fallback or retry would show up that way), or if any route step in
  ``model_routes.toml`` has no entry.

Output: one JSON file, a list of entries sorted by step and variant, each with
``step``, ``variant``, ``path``, ``body`` and ``timeout``.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import openai

from policy_atlas.core import model_routes
from policy_atlas.core import openai_client as openai_client_module
from policy_atlas.core.clustering_engine import ClusterLabel, ClusterUnit
from policy_atlas.evidence_search.assess.classification_backend import (
    OpenAIClassificationBackend,
)
from policy_atlas.evidence_search.assess.classify_prompt import ClassifyEnvelopePayload
from policy_atlas.evidence_search.assess.screen_prompt import (
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
)
from policy_atlas.evidence_search.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_search.corpus.ranking import OpenAIRankingBackend
from policy_atlas.evidence_search.corpus.theme_grouping import OpenAIThemeGroupingBackend
from policy_atlas.evidence_search.extract.extraction_backend import (
    OpenAIExtractionBackend,
    OpenAIICFExtractionBackend,
    OpenAIInterventionsBackend,
)
from policy_atlas.evidence_search.extract.finding_vetter import (
    OpenAIFindingVetterBackend,
    OpenAIICFFindingVetterBackend,
)
from policy_atlas.evidence_search.extract.iof_records import ExtractionWindowPayload
from policy_atlas.evidence_search.extract.relevance_annotator import (
    OpenAIRelevanceAnnotatorBackend,
)
from policy_atlas.evidence_search.group.group_clustering import (
    OpenAIGroupClusteringBackendFactory,
)
from policy_atlas.evidence_search.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    MAX_PARAPHRASES,
    N_QUERIES,
    QueriesPayload,
    ReformulatePayload,
    SuggestPayload,
)
from policy_atlas.evidence_search.synthesis.grounding_judge import (
    OpenAIGroundingJudgeBackend,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import OpenAISynthesisBackend
from policy_atlas.options_scoping.scoping_backend import OpenAILonglistBackend
from policy_atlas.options_scoping.suggest.suggest_prompt import SuggestPlanContext
from policy_atlas.runtime.agent_backend import OpenAIAgentBackend
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend
from policy_atlas.runtime.chat_context import window_turns
from policy_atlas.runtime.chat_prompt import CHAT_MAX_OUTPUT_TOKENS, build_chat_messages
from policy_atlas.runtime.task_agent import EVIDENCE_SEARCH_TASK_AGENT, OpenAITaskAgentBackend
from policy_atlas.runtime.task_agent_scoping import OPTIONS_SCOPING_TASK_AGENT, ScopingInputs
from policy_atlas.runtime.task_agent_toc import TOC_TASK_AGENT, TocInputs
from policy_atlas.theory_of_change.backend import OpenAITocBackend

API_KEY = "sk-test-request-capture"
FIXED_ID = "00000000-0000-4000-8000-000000000063"
ROUTE = "bedrock"

# --- Recording transport and canned answers -------------------------------------


@dataclass
class _Recorded:
    path: str
    body: Any
    timeout: Any


_REQUESTS: list[_Recorded] = []
#: The current driver's answer overrides, one per request in order.
_ANSWERS: list[dict[str, Any] | None] = []


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = {**root.get("$defs", root.get("definitions", {}))[name], **{
            k: v for k, v in schema.items() if k != "$ref"
        }}
    return schema


def _minimal(schema: dict[str, Any], root: dict[str, Any]) -> Any:
    """The smallest value that fits a JSON schema (first enum value, shortest list)."""
    schema = _resolve(schema, root)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [_resolve(option, root) for option in schema[key]]
            if any(option.get("type") == "null" for option in options):
                return None
            return _minimal(options[0], root)
    kind = schema.get("type")
    if isinstance(kind, list):
        if "null" in kind:
            return None
        kind = kind[0]
    if kind == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        return {
            name: _minimal(properties[name], root)
            for name in schema.get("required", list(properties))
        }
    if kind == "array":
        return [_minimal(schema.get("items", {}), root) for _ in range(schema.get("minItems", 0))]
    if kind == "string":
        return "x" * schema.get("minLength", 0)
    if kind in ("integer", "number"):
        return schema.get("minimum", 0)
    if kind == "boolean":
        return False
    return None


def _tool_parameters(body: dict[str, Any], name: str) -> dict[str, Any]:
    for tool in body.get("tools", []):
        if tool["name"] == name:
            parameters: dict[str, Any] = tool.get("parameters") or {}
            return parameters
    raise AssertionError(f"tool {name!r} not offered")


def _answer(
    body: dict[str, Any], override: dict[str, Any] | None
) -> tuple[str | None, list[tuple[str, str]]]:
    """The canned answer for one request: (text, [(tool name, arguments)])."""
    if override and "text" in override:
        return override["text"], []
    if override and "tool" in override:
        name, arguments = override["tool"]
        return None, [(name, json.dumps(arguments))]
    choice = body.get("tool_choice")
    if isinstance(choice, dict) and choice.get("type") == "function":
        name = choice["name"]
        parameters = _tool_parameters(body, name)
        return None, [(name, json.dumps(_minimal(parameters, parameters)))]
    if isinstance(choice, dict) or choice == "required":
        raise AssertionError("an open tool turn needs an override naming the tool to call")
    text_format = body.get("text", {}).get("format")
    if isinstance(text_format, dict) and text_format.get("type") == "json_schema":
        schema = text_format["schema"]
        return json.dumps(_minimal(schema, schema)), []
    raise AssertionError("a request with no schema and no forced tool needs an override")


_USAGE = {
    "input_tokens": 10,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens": 5,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 15,
}


def _response(
    body: dict[str, Any], text: str | None, calls: list[tuple[str, str]]
) -> dict[str, Any]:
    output: list[dict[str, Any]] = [
        {"type": "function_call", "id": f"fc_{i}", "call_id": f"call_{i}", "name": name,
         "arguments": args, "status": "completed"}
        for i, (name, args) in enumerate(calls)
    ]
    if text is not None:
        output.insert(0, {
            "type": "message", "id": "msg_0", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        })
    return {
        "id": "resp", "object": "response", "created_at": 0, "model": body["model"],
        "status": "completed", "output": output, "usage": _USAGE,
        "parallel_tool_calls": body.get("parallel_tool_calls", True),
        "tool_choice": body.get("tool_choice", "auto"), "tools": body.get("tools", []),
    }


def _responses_answer(body: dict[str, Any], override: dict[str, Any] | None) -> httpx.Response:
    text, calls = _answer(body, override)
    response = _response(body, text, calls)
    if body.get("stream"):
        # No streamed site forces a tool, so a stream carries text only.
        assert not calls, "a streamed request with a forced tool"
        events: list[dict[str, Any]] = [
            {"type": "response.created", "response": {**response, "status": "in_progress",
                                                       "output": [], "usage": None}},
            {"type": "response.output_text.delta", "item_id": "msg_0", "output_index": 0,
             "content_index": 0, "delta": text or "", "logprobs": []},
            {"type": "response.completed", "response": response},
        ]
        lines = "".join(
            f"event: {event['type']}\ndata: "
            + json.dumps({**event, "sequence_number": number})
            + "\n\n"
            for number, event in enumerate(events)
        )
        return httpx.Response(
            200, content=lines.encode(), headers={"content-type": "text/event-stream"}
        )
    return httpx.Response(200, json=response)


def _handle(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    _REQUESTS.append(
        _Recorded(path=request.url.path, body=body, timeout=request.extensions.get("timeout"))
    )
    index = len(_REQUESTS) - 1
    override = _ANSWERS[index] if index < len(_ANSWERS) else None
    if request.url.path.endswith("/responses"):
        return _responses_answer(body, override)
    raise AssertionError(f"no canned answer for {request.url.path}")


_REAL_OPENAI = openai.OpenAI


def _recording_openai(**kwargs: Any) -> openai.OpenAI:
    return _REAL_OPENAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(_handle)))


# --- Fixture inputs (repository literals only) ----------------------------------

_DOCS: list[Any] = [{"id": "doc-1", "title": "Housing First evaluation", "abstract": "An RCT."}]
_PLAN: dict[str, object] = {
    "question": "How can councils reduce rough sleeping?",
    "intended_change": "Fewer people sleeping rough",
    "target_unit": "Local authorities",
    "outcomes": ["Rough sleeping counts"],
}
_BASELINE = [("What the evidence says", "Housing First reduces homelessness.")]
_OPTIONS: list[dict[str, object]] = [
    {"id": "opt-1", "name": "Housing First", "description": "Permanent housing first."}
]
_RECORDS: list[dict[str, object]] = [
    {"id": "rec-1", "title": "Housing First in Finland", "summary": "National rollout."}
]
_TURNS = [{"role": "user", "text": "How can councils reduce rough sleeping?"}]
_SECTION_SEED: dict[str, Any] = {
    "section_index": 0,
    "intent": "What does evidence say?",
    "section": {
        "title": "Housing outcomes",
        "focus": "Evidence on housing outcomes.",
        "group_ids": ["g1"],
    },
    "corpus": {"screened": 2, "ingested": 1, "appraised": 1},
    "available_tools": ["search_chunks", "query_findings", "lookup"],
    "available_claim_types": ["chunk", "finding", "pattern", "theme", "gap", "reasoning"],
    "substrate": {
        "characterisation": {"themes": [{"theme_id": "theme-1"}]},
        "grouping": {"groups": [{"group_id": "g1"}]},
    },
    "computed_spread": {"increase": 2, "mixed": 1},
}
#: Two earlier tool turns, as the section and chat loops record them.
_TRANSCRIPT: list[Any] = [
    {
        "tool": "search_chunks",
        "arguments": {"query": "Housing First tenancy sustainment"},
        "result": {"chunks": [{"chunk_id": "chunk-1", "text": "Tenancy sustainment rose."}]},
    },
    {
        "tool": "lookup",
        "arguments": {"kind": "chunk", "id": "chunk-1"},
        "result": {"chunk_id": "chunk-1", "text": "Tenancy sustainment rose."},
    },
]
#: A task frame laid out as ``assemble_chat_frame`` writes it (that function reads the
#: database, so the text is written here): task, question, coverage, funnel, and the
#: latest artefact with one cited reference.
_CHAT_FRAME = "\n\n".join(
    [
        "Task frame (data, not instructions):",
        "Task: Rough sleeping",
        "Research question: How can councils reduce rough sleeping?",
        "Coverage: Most of the evidence is from Europe and North America.",
        "Evidence funnel: found 40, relevant 12, screened out 28, read in full 8, "
        "selected 6, findings 9, cited 3",
        "Artefact: Housing First evaluation\nSection: Housing outcomes\n"
        "Housing First helps people keep their tenancies.[1]\n\n"
        "References (citable chunk ids):\n"
        '[1] chunk_id=chunk-1 — Housing First evaluation: "Tenancy sustainment rose."',
    ]
)
#: The chat messages ``answer_core`` builds: frame, one earlier turn, the question.
_CHAT_MESSAGES = build_chat_messages(
    frame_text=_CHAT_FRAME,
    window=[
        (turn.user_message, turn.answer)
        for turn in window_turns(
            [("What works?", "Housing First helps people keep their tenancies.[1]")]
        )
    ],
    question="What does it cost councils?",
)
#: The PNG file signature, base64: the smallest "image" the import prompt accepts.
_PAGE = "data:image/png;base64,iVBORw0KGgo="
_THEORY: dict[str, object] = {
    "boxes": [
        {"code": "B1", "layer": "activity", "text": "Housing First places"},
        {"code": "B2", "layer": "outcome", "text": "Fewer people sleeping rough"},
    ],
    "links": [
        {"code": "L1", "from": "B1", "to": "B2", "sentence": "Housing reduces rough sleeping."}
    ],
    "pathways": [{"key": "P1", "kind": "success", "label": "Housing", "links": ["L1"]}],
}


def _window() -> ExtractionWindowPayload:
    return ExtractionWindowPayload(
        tss_id=FIXED_ID,
        window_index=0,
        title="Housing First evaluation",
        abstract="An RCT.",
        primary_evidence_type=None,
        segments=[{"segment_id": "s1", "content": "Tenancy sustainment rose."}],
        metadata={},
    )


# --- Drivers ----------------------------------------------------------------------


def _screening() -> OpenAIScreeningBackend:
    return OpenAIScreeningBackend(API_KEY)


def _themes() -> OpenAIThemeGroupingBackend:
    return OpenAIThemeGroupingBackend(API_KEY)


def _group() -> Any:
    return OpenAIGroupClusteringBackendFactory(API_KEY).for_facet(
        facet="outcome", projection="value", include_context_in_discovery=False
    )


_UNITS = [ClusterUnit(unit_id="u1", payload={"text": "Tenancy sustainment"})]
_REFORMULATE = ReformulatePayload(intent="I", round_index=1)
#: The split search prompts: the OpenAlex queries, then the Overton paraphrases.
_V2 = N_QUERIES + MAX_PARAPHRASES


def _synthesis() -> OpenAISynthesisBackend:
    return OpenAISynthesisBackend(API_KEY)


def _agent() -> OpenAIAgentBackend:
    return OpenAIAgentBackend(API_KEY)


def _task_agent() -> OpenAITaskAgentBackend:
    return OpenAITaskAgentBackend(API_KEY)


def _longlist() -> OpenAILonglistBackend:
    return OpenAILonglistBackend(API_KEY)


def _toc() -> OpenAITocBackend:
    return OpenAITocBackend(API_KEY)


def _chat(force_emit: bool) -> object:
    return OpenAIChatBackend(API_KEY).chat_turn(
        _CHAT_MESSAGES,
        _TRANSCRIPT,
        force_emit=force_emit,
        max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
        on_delta=(lambda _text: None) if force_emit else None,
    )


_TOC_INPUTS = TocInputs(theory_state="no draft yet", has_draft=False, approved=None)
_SCOPING_INPUTS = ScopingInputs(linked_context=[], linked_task_ids=[])
_SUGGEST_PLAN = SuggestPlanContext(
    question="Q?",
    intended_change="Fewer evictions",
    target_unit="Councils",
    outcomes=["Fewer evictions"],
    requirements=[],
    your_context=[],
    your_options=[],
)
_ON_TEXT: Callable[[str], None] = lambda _text: None  # noqa: E731
_SEARCH_TOOL = ("search_chunks", {"query": "Housing First outcomes"})
_LOOKUP_TOOL = ("lookup", {"kind": "chunk", "id": "chunk-1"})
_PROSE = "Housing First helps people keep their tenancies."
_EMIT = {"prose": _PROSE, "claims": []}


@dataclass(frozen=True)
class Entry:
    """One captured request: a route step, a variant name, and how to make it.

    Attributes:
        step: The route step in ``model_routes.toml``.
        variant: Which request of the step; ``""`` for the step's ordinary call.
        drive: Calls the site with fixed inputs.
        keep: Which of the driver's requests is this entry (counting from 0).
        expect: How many requests the driver must make in all.
        answers: Canned answer overrides, one per request in order (``None`` keeps
            the derived answer): ``{"text": ...}`` or ``{"tool": (name, arguments)}``.
    """

    step: str
    variant: str
    drive: Callable[[], object]
    keep: int = 0
    expect: int = 1
    answers: tuple[dict[str, Any] | None, ...] = ()


ENTRIES: tuple[Entry, ...] = (
    # Evidence search: assess, corpus, group, extract
    Entry("classify_document", "", lambda: OpenAIClassificationBackend(API_KEY).classify(
        ClassifyEnvelopePayload(tss_id=FIXED_ID, title="T", abstract="A", priors={})
    )),
    Entry("screen_abstract", "", lambda: _screening().screen_envelope(
        ScreenEnvelopePayload(
            tss_id=FIXED_ID, title="T", abstract="A", abstract_source="openalex", intent="I"
        )
    )),
    Entry("screen_full", "", lambda: _screening().screen_fulltext(
        ScreenFullTextPayload(
            tss_id=FIXED_ID, title="T", intent="I", window_index=0,
            segments=[{"segment_id": "s1", "content": "Text."}],
        )
    )),
    Entry("select_rerank", "", lambda: OpenAIRankingBackend(API_KEY).rank(_DOCS, intent="I")),
    Entry("characterise_discover", "", lambda: _themes().discover(
        _DOCS, intent="I", min_themes=2, max_themes=5
    )),
    Entry("characterise_assign", "", lambda: _themes().assign(
        _DOCS, themes=[{"name": "Housing", "description": "Housing outcomes."}]
    )),
    Entry("group_discover", "", lambda: _group().discover(_UNITS, min_labels=0, max_labels=5)),
    Entry("group_assign", "", lambda: _group().assign(
        _UNITS, labels=[ClusterLabel(label="Housing", description="Housing outcomes.")]
    )),
    Entry("extract_iof_findings", "", lambda: OpenAIExtractionBackend(API_KEY).extract(_window())),
    Entry("extract_icf_findings", "", lambda: OpenAIICFExtractionBackend(API_KEY).extract(
        _window()
    )),
    Entry("extract_interventions", "", lambda: OpenAIInterventionsBackend(API_KEY).extract(
        _window()
    )),
    Entry("extract_vet_iof_findings", "", lambda: OpenAIFindingVetterBackend(API_KEY).judge(
        {"findings": [{"index": 0}]}
    )),
    Entry("extract_vet_icf_findings", "", lambda: OpenAIICFFindingVetterBackend(API_KEY).judge(
        {"findings": [{"index": 0}]}
    )),
    Entry("extract_annotate_relevance", "", lambda: OpenAIRelevanceAnnotatorBackend(
        API_KEY
    ).annotate({"emphasis": ["cost"], "findings": [{"finding_id": FIXED_ID}]})),
    # Evidence search: search
    Entry("search_generate_queries", "", lambda: OpenAISearchGenerationBackend(
        API_KEY
    ).generate_queries(QueriesPayload(intent="I"))),
    Entry("search_reformulate", "", lambda: OpenAISearchGenerationBackend(API_KEY).reformulate(
        _REFORMULATE
    )),
    Entry("search_suggest", "", lambda: OpenAISearchGenerationBackend(API_KEY).suggest(
        SuggestPayload(intent="I")
    )),
    Entry("search_queries_v2_openalex", "", lambda: V2SearchGenerationBackend(
        API_KEY
    ).generate_queries(QueriesPayload(intent="I")), expect=_V2),
    Entry("search_queries_v2_overton", "", lambda: V2SearchGenerationBackend(
        API_KEY
    ).generate_queries(QueriesPayload(intent="I")), keep=N_QUERIES, expect=_V2),
    Entry("search_reformulate_v2_openalex", "", lambda: V2SearchGenerationBackend(
        API_KEY
    ).reformulate(_REFORMULATE), expect=_V2),
    Entry("search_reformulate_v2_overton", "", lambda: V2SearchGenerationBackend(
        API_KEY
    ).reformulate(_REFORMULATE), keep=N_QUERIES, expect=_V2),
    # Evidence search: synthesise
    Entry("synthesise_propose_sections", "", lambda: _synthesis().propose_sections(
        intent="I", substrate=_SECTION_SEED["substrate"]
    )),
    Entry("synthesise_write_block_summary", "", lambda: _synthesis().write_block_summary(
        {"title": "T", "prose": "P."}
    )),
    Entry("synthesise_write_artefact_summary", "", lambda: _synthesis().write_block_summary(
        {"kind": "artefact", "title": "T", "prose": "P."}
    )),
    Entry("synthesise_judge_summary", "", lambda: _synthesis().judge_summary(
        summary="S.", detail={"title": "T", "prose": "P."}
    )),
    Entry("synthesise_section_turn", "", lambda: _synthesis().section_turn(
        _SECTION_SEED, [], force_emit=False
    ), answers=({"tool": _SEARCH_TOOL},)),
    Entry("synthesise_section_turn", "history", lambda: _synthesis().section_turn(
        _SECTION_SEED, _TRANSCRIPT, force_emit=False
    ), answers=({"tool": _SEARCH_TOOL},)),
    Entry("synthesise_section_turn", "forced", lambda: _synthesis().section_turn(
        _SECTION_SEED, _TRANSCRIPT, force_emit=True
    ), answers=({"tool": ("emit_section", _EMIT)},)),
    Entry("synthesise_section_turn", "repair", lambda: _synthesis().repair_section(
        _SECTION_SEED,
        _TRANSCRIPT,
        failing=[{"index": 0, "text": "Claim.", "rationale": "Unsupported."}],
    )),
    Entry("synthesise_section_emit", "", lambda: _synthesis().section_emit_stream(
        _SECTION_SEED, _TRANSCRIPT
    ), answers=({"text": json.dumps(_EMIT)},)),
    Entry("synthesise_write_key_findings", "", lambda: _synthesis().write_key_findings_stream(
        {"intent": "I", "claims": []}, index=0
    )),
    Entry("synthesise_write_key_findings", "fallback", lambda: _synthesis().write_key_findings(
        {"intent": "I", "claims": []}
    ), answers=({"tool": ("emit_section", _EMIT)},)),
    Entry("synthesise_write_case_studies", "", lambda: _synthesis().write_case_studies_stream(
        {"intent": "I", "candidates": []}, index=1
    )),
    Entry("synthesise_write_case_studies", "fallback", lambda: _synthesis().write_case_studies(
        {"intent": "I", "candidates": []}
    )),
    Entry("synthesise_write_source_note", "", lambda: _synthesis().write_source_note(
        {"title": "T"}
    )),
    Entry("synthesise_write_intro", "", lambda: _synthesis().write_full_report_intro_stream(
        {"intent": "I", "sections": []}, index=1
    )),
    Entry("synthesise_write_intro", "fallback", lambda: _synthesis().write_full_report_intro(
        {"intent": "I", "sections": []}
    )),
    Entry("judge_grounding", "", lambda: OpenAIGroundingJudgeBackend(API_KEY).judge_block(
        {"claims": [], "chunks": [], "section_prose": "P."}
    )),
    # Conversation and agents
    Entry("task_title", "", lambda: _agent().write_title(
        "task", "How can councils reduce rough sleeping?"
    )),
    Entry("chat_title", "", lambda: _agent().write_title("chat", "What works?")),
    Entry("chat", "tool_turn", lambda: _chat(False), answers=({"tool": _LOOKUP_TOOL},)),
    Entry("chat", "reply_stream", lambda: _chat(True), expect=2, answers=({"text": _PROSE},)),
    Entry("chat", "final_parse", lambda: _chat(True), keep=1, expect=2,
          answers=({"text": _PROSE},)),
    Entry("agent_route", "", lambda: _agent().route("Drop the grey literature.", {})),
    Entry("agent_triage", "", lambda: _agent().triage("Watch costs.", {}, {}, {})),
    Entry("agent_decide", "", lambda: _agent().decide("Watch costs.", {}, {}, {})),
    Entry("agent_gate_sort", "", lambda: _agent().sort_gate_turn(
        "Go ahead.", [{"id": "approve", "label": "Approve"}]
    )),
    Entry("agent_longlist_sort", "", lambda: _agent().sort_longlist_turn(
        "Drop option one.", [{"id": "opt-1", "name": "A"}]
    )),
    Entry("agent_option_design", "", lambda: _agent().propose_option_design(
        "A rent guarantee", question="Q?", target_unit="Councils", outcomes=["Fewer evictions"]
    )),
    Entry("agent_suggest", "", lambda: _agent().suggest_options(
        plan=_SUGGEST_PLAN, baseline_sections=_BASELINE, linked_reports=[]
    )),
    Entry("task_agent_turn", "", lambda: _task_agent().turn(
        EVIDENCE_SEARCH_TASK_AGENT, _TURNS, None
    )),
    Entry("task_agent_turn", "stream", lambda: _task_agent().turn(
        EVIDENCE_SEARCH_TASK_AGENT, _TURNS, None, on_delta=_ON_TEXT
    )),
    Entry("task_agent_scoping_turn", "", lambda: _task_agent().turn(
        OPTIONS_SCOPING_TASK_AGENT, _TURNS, None, inputs=_SCOPING_INPUTS
    )),
    Entry("task_agent_scoping_turn", "stream", lambda: _task_agent().turn(
        OPTIONS_SCOPING_TASK_AGENT, _TURNS, None, inputs=_SCOPING_INPUTS, on_delta=_ON_TEXT
    )),
    Entry("task_agent_toc", "", lambda: _task_agent().turn(
        TOC_TASK_AGENT, _TURNS, None, inputs=_TOC_INPUTS
    )),
    Entry("task_agent_toc", "stream", lambda: _task_agent().turn(
        TOC_TASK_AGENT, _TURNS, None, inputs=_TOC_INPUTS, on_delta=_ON_TEXT
    )),
    # Options scoping
    Entry("longlist_discover", "", lambda: _longlist().discover(
        plan=_PLAN, baseline_sections=_BASELINE, seeds=[], digest=_RECORDS, target_size=10,
        max_new=5,
    )),
    Entry("longlist_assign", "", lambda: _longlist().assign(options=_OPTIONS, records=_RECORDS)),
    Entry("longlist_themes", "", lambda: _longlist().discover_themes(
        question="Q?", records=_RECORDS, max_labels=5
    )),
    Entry("longlist_assign_themes", "", lambda: _longlist().assign_themes(
        themes=[{"label": "Housing", "description": "Housing."}], records=_RECORDS
    )),
    Entry("longlist_type", "", lambda: _longlist().type_options(
        options=_OPTIONS, plan=_PLAN, baseline_sections=_BASELINE
    )),
    Entry("longlist_constrain", "", lambda: _longlist().constrain(
        plan=_PLAN,
        baseline_sections=_BASELINE,
        requirements=[{"id": "r1", "text": "Within budget"}],
        preferences=[],
        options=_OPTIONS,
    )),
    Entry("longlist_distinct", "", lambda: _longlist().distinct(options=_OPTIONS)),
    Entry("longlist_authority", "", lambda: _longlist().authority(
        considerations=["Statutory duty"], options=_OPTIONS
    )),
    Entry("longlist_shortlist", "", lambda: _longlist().propose_shortlist(
        messages=[
            {"role": "system", "content": "You propose the shortlist."},
            {"role": "user", "content": "Propose."},
        ]
    )),
    Entry("shortlist_note", "", lambda: _longlist().shortlist_note(
        outcomes=["Rough sleeping counts"],
        options=_OPTIONS,
        places=["Finland"],
        changes=[],
    )),
    Entry("option_profile_line", "", lambda: _longlist().profile_line(
        line_key="cost", plan=_PLAN, where=None, baseline_sections=_BASELINE, options=_OPTIONS
    )),
    Entry("option_profile_potential_impact", "", lambda: _longlist().profile_potential_impact(
        plan=_PLAN, baseline_sections=_BASELINE, options=_OPTIONS
    )),
    Entry("option_profile_ambition", "", lambda: _longlist().profile_ambition(
        plan=_PLAN, baseline_sections=_BASELINE, options=_OPTIONS
    )),
    Entry("option_profile_setting", "", lambda: _longlist().profile_setting(
        plan=_PLAN, options=_OPTIONS
    )),
    Entry("option_profile_fold", "", lambda: _longlist().fold(
        facet="measures", plan=_PLAN, words={"opt-1": "Rough sleeping"}
    )),
    Entry("option_profile_place_sentences", "", lambda: _longlist().place_sentences(
        option={"id": "opt-1", "name": "Housing First"},
        plan=_PLAN,
        vocabulary={"measures": ["Rough sleeping"], "tried_on": ["Adults"]},
        places=[{"place": "Finland", "records": []}],
    )),
    # Theory of change
    Entry("toc_draft", "", lambda: _toc().draft(plan=_PLAN, existing_theory=None)),
    Entry("toc_draft", "stream", lambda: _toc().draft_stream(
        plan=_PLAN, existing_theory=None, on_text=_ON_TEXT, first_content_s=None
    )),
    Entry("toc_discover", "", lambda: _toc().discover(plan=_PLAN, theory=_THEORY, documents=[
        {"id": "doc-1", "title": "Housing First evaluation", "text": "Tenancy sustainment rose."}
    ])),
    Entry("toc_merge", "", lambda: _toc().merge(
        plan=_PLAN, boxes=_THEORY["boxes"], pathways=_THEORY["pathways"]  # type: ignore[arg-type]
    )),
    Entry("toc_merge", "consolidate", lambda: _toc().consolidate(
        plan=_PLAN, theory=_THEORY, proposals=[], max_success=2, max_failure=1
    )),
    Entry("toc_pick", "", lambda: _toc().pick(item_text="Housing reduces rough sleeping.",
                                             candidates=_DOCS)),
    Entry("toc_judge", "", lambda: _toc().judge(
        item_text="Housing reduces rough sleeping.",
        population="Adults sleeping rough",
        place="Finland",
        document_id="doc-1",
        title="Housing First evaluation",
        year=2020,
        text="Tenancy sustainment rose.",
    )),
    Entry("toc_figures", "", lambda: _toc().figures(
        source="Housing First places",
        target="Fewer people sleeping rough",
        population="Adults sleeping rough",
        place="Finland",
        title="Housing First evaluation",
        year=2020,
        text="Tenancy sustainment rose.",
    )),
    Entry("toc_choose", "", lambda: _toc().choose(
        plan=_PLAN, pathways=_THEORY["pathways"],  # type: ignore[arg-type]
        recorded_conditions=[], max_success=2, max_failure=1,
    )),
    Entry("toc_summarise", "", lambda: _toc().summarise(plan=_PLAN, theory=_THEORY)),
    Entry("toc_report", "", lambda: _toc().report(
        plan=_PLAN, theory=_THEORY, rows=[], sources=[]
    )),
    Entry("toc_report", "stream", lambda: _toc().report_stream(
        plan=_PLAN, theory=_THEORY, rows=[], sources=[], on_text=_ON_TEXT, first_content_s=None
    )),
    Entry("toc_review", "", lambda: _toc().review(
        plan=_PLAN, theory=_THEORY, edits=["Added box B2."], report=None
    )),
    Entry("toc_sense_check", "", lambda: _toc().sense_check(plan=_PLAN, documents=[
        {"id": "doc-1", "title": "Housing First evaluation", "abstract": "An RCT."}
    ])),
    Entry("toc_import", "", lambda: _toc().import_theory(pages=[_PAGE])),
    Entry("toc_verdict", "", lambda: _toc().theory_verdict(theory=_THEORY, sense_check=None)),
)


# --- Capture --------------------------------------------------------------------


def _capture(entry: Entry) -> dict[str, Any]:
    _REQUESTS.clear()
    _ANSWERS[:] = entry.answers
    entry.drive()
    label = f"{entry.step}/{entry.variant}"
    if len(_REQUESTS) != entry.expect:
        raise SystemExit(f"{label}: expected {entry.expect} requests, saw {len(_REQUESTS)}")
    kept = _REQUESTS[entry.keep]
    return {
        "step": entry.step,
        "variant": entry.variant,
        "path": kept.path,
        "body": kept.body,
        "timeout": kept.timeout,
    }


def capture_all(entries: tuple[Entry, ...] = ENTRIES) -> list[dict[str, Any]]:
    """Drive every entry and return the recorded requests, sorted by step and variant.

    Raises:
        SystemExit: If the route is not ``bedrock``, a driver makes an unexpected
            number of requests, or a route step has no entry.
    """
    if model_routes.route().name != ROUTE:
        raise SystemExit(f"run with {model_routes.ROUTE_ENV}={ROUTE}")
    # Every backend builds its client through ``resolve_openai_client``, which looks
    # this name up in its module at call time.
    vars(openai_client_module)["OpenAI"] = _recording_openai
    captured = [_capture(entry) for entry in entries]
    missing = sorted(set(model_routes.route().steps) - {entry.step for entry in entries})
    if missing:
        raise SystemExit(f"route steps with no captured request: {missing}")
    return sorted(captured, key=lambda item: (item["step"], item["variant"]))


def main(argv: list[str]) -> None:
    """Write the capture to the path given as the only argument."""
    if len(argv) != 2:
        raise SystemExit("usage: capture_requests.py OUTPUT.json")
    Path(argv[1]).write_text(
        json.dumps(capture_all(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
    main(sys.argv)
