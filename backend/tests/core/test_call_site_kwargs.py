"""Pin the provider request every model call site sends today (task 056, Phase 0).

Task 056 Phase 1 gives every call site its own route step and its own reasoning
effort. Its proof of "no behaviour change" is this test: the keyword arguments each
site hands to ``client.chat.completions.parse`` / ``.create`` must stay identical to
the committed fixture ``data/call_site_kwargs_056.json``, except that a reasoning
effort that is omitted today becomes an explicit ``medium``.

How a capture works, in plain terms:

- The OpenAI client class in ``core.openai_client`` is swapped for a recording
  double, so every backend built through ``resolve_openai_client`` talks to it.
- The double writes down the keyword arguments of each request, then raises a
  sentinel (a ``BaseException``, so a backend's ``except Exception`` retry path
  cannot swallow it). The call therefore ends after one request. Where the site is
  not the first request of its method (the Overton half of the split search
  prompts, the structured step after the chat prose stream), the earlier requests
  get a minimal canned reply instead.
- A fake Langfuse client records which observation (trace) is open when the
  request goes out; that is the ``trace_name``.
- ``messages`` are not pinned (prompt text has its own hash guard); everything
  else is serialised: the response-format class name, the tool names, and every
  other argument as sent.

Refresh the fixture deliberately with ``CALL_SITE_KWARGS_UPDATE=1``; the diff is
then the review artefact.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from policy_atlas.core import model_routes
from policy_atlas.core import openai_client as openai_client_module
from policy_atlas.core.clustering_engine import ClusterLabel, ClusterUnit
from policy_atlas.core.tracing import TracedThemeGroupingBackend
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
from policy_atlas.evidence_search.extract import extract as extract_module
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
    V2SingleQueryWire,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    N_QUERIES,
    QueriesPayload,
    ReformulatePayload,
    SuggestPayload,
)
from policy_atlas.evidence_search.synthesis.cache_modes import CACHE_MODES
from policy_atlas.evidence_search.synthesis.grounding_judge import (
    OpenAIGroundingJudgeBackend,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import OpenAISynthesisBackend
from policy_atlas.options_scoping.scoping_backend import OpenAILonglistBackend
from policy_atlas.options_scoping.suggest.suggest_prompt import SuggestPlanContext
from policy_atlas.runtime.agent_backend import OpenAIAgentBackend
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend
from policy_atlas.runtime.chat_prompt import CHAT_MAX_OUTPUT_TOKENS
from policy_atlas.runtime.task_agent import EVIDENCE_SEARCH_TASK_AGENT, OpenAITaskAgentBackend
from policy_atlas.runtime.task_agent_scoping import OPTIONS_SCOPING_TASK_AGENT, ScopingInputs

FIXTURE_PATH = Path(__file__).parent / "data" / "call_site_kwargs_056.json"
UPDATE_ENV = "CALL_SITE_KWARGS_UPDATE"
ROUTE = "openai-direct"
CAPTURED_AT = "2026-11-02"
API_KEY = "sk-test-call-site-kwargs"
FIXED_ID = "00000000-0000-4000-8000-000000000056"

# Kwargs that get their own field in a fixture entry; any other name sent lands
# in ``other_keys``. ``messages`` is always sent and is never pinned here.
_NAMED_KEYS = frozenset(
    {
        "model",
        "reasoning_effort",
        "response_format",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "max_completion_tokens",
        "stream",
        "extra_body",
        "messages",
    }
)


# --- The recording doubles ----------------------------------------------------


class _Captured(BaseException):
    """Raised by the recording client once the request under test is recorded."""


class _RecordingCompletions:
    """Stands in for ``client.chat.completions``; records each request's kwargs."""

    def __init__(
        self,
        *,
        langfuse: _FakeLangfuse,
        stop_at: int,
        respond: Callable[[str, dict[str, Any]], Any] | None,
    ) -> None:
        self._langfuse = langfuse
        self._stop_at = stop_at
        self._respond = respond
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []

    def parse(self, **kwargs: Any) -> Any:
        return self._handle("parse", kwargs)

    def create(self, **kwargs: Any) -> Any:
        return self._handle("create", kwargs)

    def _handle(self, verb: str, kwargs: dict[str, Any]) -> Any:
        self.calls.append((verb, kwargs, self._langfuse.current()))
        if len(self.calls) - 1 >= self._stop_at:
            raise _Captured
        if self._respond is None:  # pragma: no cover - a site spec error
            raise AssertionError("no canned reply for a request before the captured one")
        return self._respond(verb, kwargs)


class _RecordingClient:
    def __init__(self, completions: _RecordingCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


class _FakeSpan:
    def update(self, **_kwargs: Any) -> None:
        return None


class _FakeLangfuse:
    """Minimal Langfuse double: tracks which observations are open."""

    def __init__(self) -> None:
        self._open: list[str] = []

    def current(self) -> str | None:
        return self._open[-1] if self._open else None

    @contextmanager
    def _observe(self, name: str) -> Iterator[_FakeSpan]:
        self._open.append(name)
        try:
            yield _FakeSpan()
        finally:
            self._open.pop()

    def start_as_current_observation(self, *, name: str, as_type: str) -> Any:
        del as_type
        return self._observe(name)

    def score_current_trace(self, **_kwargs: Any) -> None:
        return None


def _parsed_reply(parsed: BaseModel) -> Any:
    message = SimpleNamespace(parsed=parsed, tool_calls=None, content=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


def _v2_query_reply(_verb: str, _kwargs: dict[str, Any]) -> Any:
    return _parsed_reply(V2SingleQueryWire(query="housing first outcomes"))


def _empty_stream_reply(verb: str, kwargs: dict[str, Any]) -> Any:
    assert verb == "create" and kwargs.get("stream") is True
    return iter(())


# --- Site specs -----------------------------------------------------------------


Driver = Callable[[Any], object]


@dataclass(frozen=True)
class _Site:
    """One call site: the step key, the entry point driven, and how to drive it."""

    step: str
    path: str
    owner: type
    function: str
    drive: Driver
    stop_at: int = 0
    respond: Callable[[str, dict[str, Any]], Any] | None = None


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


def _classify(lf: Any) -> object:
    backend = OpenAIClassificationBackend(API_KEY, langfuse_client=lf)
    return backend.classify(
        ClassifyEnvelopePayload(tss_id=FIXED_ID, title="T", abstract="A", priors={})
    )


def _screening(lf: Any) -> OpenAIScreeningBackend:
    return OpenAIScreeningBackend(API_KEY, langfuse_client=lf)


def _screen_abstract(lf: Any) -> object:
    return _screening(lf).screen_envelope(
        ScreenEnvelopePayload(
            tss_id=FIXED_ID, title="T", abstract="A", abstract_source="openalex", intent="I"
        )
    )


def _screen_full(lf: Any) -> object:
    return _screening(lf).screen_fulltext(
        ScreenFullTextPayload(
            tss_id=FIXED_ID,
            title="T",
            intent="I",
            window_index=0,
            segments=[{"segment_id": "s1", "content": "Text."}],
        )
    )


def _rerank(lf: Any) -> object:
    backend = OpenAIRankingBackend(API_KEY, langfuse_client=lf)
    return backend.rank(_DOCS, intent="I")


def _themes(lf: Any) -> TracedThemeGroupingBackend:
    return TracedThemeGroupingBackend(OpenAIThemeGroupingBackend(API_KEY), lf)


def _characterise_discover(lf: Any) -> object:
    return _themes(lf).discover(_DOCS, intent="I", min_themes=2, max_themes=5)


def _characterise_assign(lf: Any) -> object:
    return _themes(lf).assign(
        _DOCS,
        themes=[{"name": "Housing", "description": "Housing outcomes."}],
    )


def _group_backend(lf: Any) -> Any:
    factory = OpenAIGroupClusteringBackendFactory(API_KEY, langfuse_client=lf)
    return factory.for_facet(
        facet="outcome", projection="value", include_context_in_discovery=False
    )


_UNITS = [ClusterUnit(unit_id="u1", payload={"text": "Tenancy sustainment"})]


def _group_discover(lf: Any) -> object:
    return _group_backend(lf).discover(_UNITS, min_labels=0, max_labels=5)


def _group_assign(lf: Any) -> object:
    return _group_backend(lf).assign(
        _UNITS, labels=[ClusterLabel(label="Housing", description="Housing outcomes.")]
    )


def _extract_iof(lf: Any) -> object:
    return OpenAIExtractionBackend(API_KEY, langfuse_client=lf).extract(_window())


def _extract_icf(lf: Any) -> object:
    return OpenAIICFExtractionBackend(API_KEY, langfuse_client=lf).extract(_window())


def _extract_interventions(lf: Any) -> object:
    return OpenAIInterventionsBackend(API_KEY, langfuse_client=lf).extract(_window())


def _vet_iof(lf: Any) -> object:
    backend = OpenAIFindingVetterBackend(API_KEY, langfuse_client=lf)
    return backend.judge({"findings": [{"index": 0}]})


def _vet_icf(lf: Any) -> object:
    backend = OpenAIICFFindingVetterBackend(API_KEY, langfuse_client=lf)
    return backend.judge({"findings": [{"index": 0}]})


def _annotate_relevance(lf: Any) -> object:
    backend = OpenAIRelevanceAnnotatorBackend(API_KEY, langfuse_client=lf)
    return backend.annotate({"emphasis": ["cost"], "findings": [{"finding_id": FIXED_ID}]})


def _search(lf: Any) -> OpenAISearchGenerationBackend:
    return OpenAISearchGenerationBackend(API_KEY, langfuse_client=lf)


def _search_v2(lf: Any) -> V2SearchGenerationBackend:
    return V2SearchGenerationBackend(API_KEY, langfuse_client=lf)


_REFORMULATE = ReformulatePayload(intent="I", round_index=1)


def _search_generate(lf: Any) -> object:
    return _search(lf).generate_queries(QueriesPayload(intent="I"))


def _search_reformulate(lf: Any) -> object:
    return _search(lf).reformulate(_REFORMULATE)


def _search_suggest(lf: Any) -> object:
    return _search(lf).suggest(SuggestPayload(intent="I"))


def _search_v2_generate(lf: Any) -> object:
    return _search_v2(lf).generate_queries(QueriesPayload(intent="I"))


def _search_v2_reformulate(lf: Any) -> object:
    return _search_v2(lf).reformulate(_REFORMULATE)


def _synthesis(lf: Any) -> OpenAISynthesisBackend:
    return OpenAISynthesisBackend(API_KEY, langfuse_client=lf)


def _propose_sections(lf: Any) -> object:
    return _synthesis(lf).propose_sections(intent="I", substrate=_SECTION_SEED["substrate"])


def _block_summary(lf: Any) -> object:
    return _synthesis(lf).write_block_summary({"title": "T", "prose": "P."})


def _artefact_summary(lf: Any) -> object:
    return _synthesis(lf).write_block_summary({"kind": "artefact", "title": "T", "prose": "P."})


def _judge_summary(lf: Any) -> object:
    return _synthesis(lf).judge_summary(summary="S.", detail={"title": "T", "prose": "P."})


def _section_turn(lf: Any) -> object:
    # First request of the tool loop (run_section_loop): an empty transcript.
    return _synthesis(lf).section_turn(_SECTION_SEED, [], force_emit=False)


def _repair(lf: Any) -> object:
    return _synthesis(lf).repair_section(
        _SECTION_SEED,
        [],
        failing=[{"index": 0, "text": "Claim.", "rationale": "Unsupported."}],
    )


def _key_findings(lf: Any) -> object:
    return _synthesis(lf).write_key_findings({"intent": "I", "claims": []})


def _case_studies(lf: Any) -> object:
    return _synthesis(lf).write_case_studies({"intent": "I", "candidates": []})


def _source_note(lf: Any) -> object:
    return _synthesis(lf).write_source_note({"title": "T"})


def _intro(lf: Any) -> object:
    return _synthesis(lf).write_full_report_intro({"intent": "I", "sections": []})


def _grounding(lf: Any) -> object:
    backend = OpenAIGroundingJudgeBackend(API_KEY, langfuse_client=lf)
    return backend.judge_block({"claims": [], "chunks": [], "section_prose": "P."})


_CHAT_MESSAGES = [{"role": "user", "content": "What works?"}]


def _chat_tool_turn(_lf: Any) -> object:
    return OpenAIChatBackend(API_KEY).chat_turn(
        _CHAT_MESSAGES, [], force_emit=False, max_output_tokens=CHAT_MAX_OUTPUT_TOKENS
    )


def _chat_final(_lf: Any) -> object:
    return OpenAIChatBackend(API_KEY).chat_turn(
        _CHAT_MESSAGES, [], force_emit=True, max_output_tokens=CHAT_MAX_OUTPUT_TOKENS
    )


def _agent(lf: Any) -> OpenAIAgentBackend:
    return OpenAIAgentBackend(API_KEY, langfuse_client=lf)


def _agent_route(lf: Any) -> object:
    return _agent(lf).route("Drop the grey literature.", {})


def _agent_triage(lf: Any) -> object:
    return _agent(lf).triage("Watch costs.", {}, {}, {})


def _agent_decide(lf: Any) -> object:
    return _agent(lf).decide("Watch costs.", {}, {}, {})


def _agent_gate_sort(lf: Any) -> object:
    return _agent(lf).sort_gate_turn("Go ahead.", [{"id": "approve", "label": "Approve"}])


def _agent_longlist_sort(lf: Any) -> object:
    return _agent(lf).sort_longlist_turn("Drop option one.", [{"id": "opt-1", "name": "A"}])


def _agent_option_design(lf: Any) -> object:
    return _agent(lf).propose_option_design(
        "A rent guarantee", question="Q?", target_unit="Councils", outcomes=["Fewer evictions"]
    )


def _agent_suggest(lf: Any) -> object:
    plan = SuggestPlanContext(
        question="Q?",
        intended_change="Fewer evictions",
        target_unit="Councils",
        outcomes=["Fewer evictions"],
        requirements=[],
        your_context=[],
        your_options=[],
    )
    return _agent(lf).suggest_options(plan=plan, baseline_sections=_BASELINE, linked_reports=[])


def _task_agent(lf: Any) -> OpenAITaskAgentBackend:
    return OpenAITaskAgentBackend(API_KEY, langfuse_client=lf)


def _task_agent_turn(lf: Any) -> object:
    return _task_agent(lf).turn(EVIDENCE_SEARCH_TASK_AGENT, _TURNS, None)


def _task_agent_scoping_turn(lf: Any) -> object:
    return _task_agent(lf).turn(
        OPTIONS_SCOPING_TASK_AGENT,
        _TURNS,
        None,
        inputs=ScopingInputs(linked_context=[], linked_task_ids=[]),
    )


def _longlist(lf: Any) -> Any:
    return OpenAILonglistBackend(API_KEY, langfuse_client=lf)


def _longlist_discover(lf: Any) -> object:
    return _longlist(lf).discover(
        plan=_PLAN, baseline_sections=_BASELINE, seeds=[], digest=_RECORDS, target_size=10,
        max_new=5,
    )


def _longlist_assign(lf: Any) -> object:
    return _longlist(lf).assign(options=_OPTIONS, records=_RECORDS)


def _longlist_themes(lf: Any) -> object:
    return _longlist(lf).discover_themes(question="Q?", records=_RECORDS, max_labels=5)


def _longlist_assign_themes(lf: Any) -> object:
    return _longlist(lf).assign_themes(
        themes=[{"label": "Housing", "description": "Housing."}], records=_RECORDS
    )


def _longlist_type(lf: Any) -> object:
    return _longlist(lf).type_options(options=_OPTIONS, plan=_PLAN, baseline_sections=_BASELINE)


def _longlist_constrain(lf: Any) -> object:
    return _longlist(lf).constrain(
        plan=_PLAN,
        baseline_sections=_BASELINE,
        requirements=[{"id": "r1", "text": "Within budget"}],
        preferences=[],
        options=_OPTIONS,
    )


def _longlist_distinct(lf: Any) -> object:
    return _longlist(lf).distinct(options=_OPTIONS)


def _longlist_authority(lf: Any) -> object:
    return _longlist(lf).authority(considerations=["Statutory duty"], options=_OPTIONS)


def _longlist_shortlist(lf: Any) -> object:
    return _longlist(lf).propose_shortlist(messages=[{"role": "user", "content": "Propose."}])


def _profile_line(lf: Any) -> object:
    # A marked line (``cost``); the plain lines differ only in the response format.
    return _longlist(lf).profile_line(
        line_key="cost", plan=_PLAN, where=None, baseline_sections=_BASELINE, options=_OPTIONS
    )


def _profile_potential_impact(lf: Any) -> object:
    return _longlist(lf).profile_potential_impact(
        plan=_PLAN, baseline_sections=_BASELINE, options=_OPTIONS
    )


def _profile_ambition(lf: Any) -> object:
    return _longlist(lf).profile_ambition(
        plan=_PLAN, baseline_sections=_BASELINE, options=_OPTIONS
    )


def _profile_setting(lf: Any) -> object:
    return _longlist(lf).profile_setting(plan=_PLAN, options=_OPTIONS)


def _profile_fold(lf: Any) -> object:
    return _longlist(lf).fold(facet="measures", plan=_PLAN, words={"opt-1": "Rough sleeping"})


def _profile_place_sentences(lf: Any) -> object:
    return _longlist(lf).place_sentences(
        option={"id": "opt-1", "name": "Housing First"},
        plan=_PLAN,
        vocabulary={"measures": ["Rough sleeping"], "tried_on": ["Adults"]},
        places=[{"place": "Finland", "records": []}],
    )


_PS = "parse_structured"
_DP = "direct_parse"
_DC = "direct_create"
_TP = "traced_parse"

SITES: tuple[_Site, ...] = (
    # parse_structured (core.openai_client.parse_structured)
    _Site("classify_document", _PS, OpenAIClassificationBackend, "classify", _classify),
    _Site("screen_abstract", _PS, OpenAIScreeningBackend, "screen_envelope", _screen_abstract),
    _Site("screen_full", _PS, OpenAIScreeningBackend, "screen_fulltext", _screen_full),
    _Site("select_rerank", _PS, OpenAIRankingBackend, "rank", _rerank),
    _Site(
        "characterise_discover", _PS, OpenAIThemeGroupingBackend, "discover",
        _characterise_discover,
    ),
    _Site(
        "characterise_assign", _PS, OpenAIThemeGroupingBackend, "assign", _characterise_assign
    ),
    _Site(
        "group_discover", _PS, OpenAIGroupClusteringBackendFactory, "for_facet().discover",
        _group_discover,
    ),
    _Site(
        "group_assign", _PS, OpenAIGroupClusteringBackendFactory, "for_facet().assign",
        _group_assign,
    ),
    _Site("extract_iof_findings", _PS, OpenAIExtractionBackend, "extract", _extract_iof),
    _Site("extract_icf_findings", _PS, OpenAIICFExtractionBackend, "extract", _extract_icf),
    _Site(
        "extract_interventions", _PS, OpenAIInterventionsBackend, "extract",
        _extract_interventions,
    ),
    _Site("extract_vet_iof_findings", _PS, OpenAIFindingVetterBackend, "judge", _vet_iof),
    _Site("extract_vet_icf_findings", _PS, OpenAIICFFindingVetterBackend, "judge", _vet_icf),
    _Site(
        "extract_annotate_relevance", _PS, OpenAIRelevanceAnnotatorBackend, "annotate",
        _annotate_relevance,
    ),
    _Site(
        "search_generate_queries", _PS, OpenAISearchGenerationBackend, "generate_queries",
        _search_generate,
    ),
    _Site(
        "search_reformulate", _PS, OpenAISearchGenerationBackend, "reformulate",
        _search_reformulate,
    ),
    _Site("search_suggest", _PS, OpenAISearchGenerationBackend, "suggest", _search_suggest),
    _Site(
        "search_queries_v2_openalex", _PS, V2SearchGenerationBackend, "generate_queries",
        _search_v2_generate,
    ),
    _Site(
        "search_queries_v2_overton", _PS, V2SearchGenerationBackend, "generate_queries",
        _search_v2_generate, stop_at=-1, respond=_v2_query_reply,
    ),
    _Site(
        "search_reformulate_v2_openalex", _PS, V2SearchGenerationBackend, "reformulate",
        _search_v2_reformulate,
    ),
    _Site(
        "search_reformulate_v2_overton", _PS, V2SearchGenerationBackend, "reformulate",
        _search_v2_reformulate, stop_at=-1, respond=_v2_query_reply,
    ),
    # direct chat.completions.parse
    _Site(
        "synthesise_propose_sections", _DP, OpenAISynthesisBackend, "propose_sections",
        _propose_sections,
    ),
    _Site(
        "synthesise_write_block_summary", _DP, OpenAISynthesisBackend, "write_block_summary",
        _block_summary,
    ),
    _Site(
        "synthesise_write_artefact_summary", _DP, OpenAISynthesisBackend, "write_block_summary",
        _artefact_summary,
    ),
    _Site("synthesise_judge_summary", _DP, OpenAISynthesisBackend, "judge_summary", _judge_summary),
    _Site(
        "synthesise_write_case_studies", _DP, OpenAISynthesisBackend, "write_case_studies",
        _case_studies,
    ),
    _Site(
        "synthesise_write_source_note", _DP, OpenAISynthesisBackend, "write_source_note",
        _source_note,
    ),
    _Site(
        "synthesise_write_intro", _DP, OpenAISynthesisBackend, "write_full_report_intro", _intro
    ),
    _Site("judge_grounding", _DP, OpenAIGroundingJudgeBackend, "judge_block", _grounding),
    _Site(
        "chat/parse", _DP, OpenAIChatBackend, "chat_turn(force_emit=True) step 2", _chat_final,
        stop_at=1, respond=_empty_stream_reply,
    ),
    # direct chat.completions.create (tool turns, forced tools, the prose stream)
    _Site(
        "synthesise_section_turn/section_turn", _DC, OpenAISynthesisBackend, "section_turn",
        _section_turn,
    ),
    _Site(
        "synthesise_section_turn/repair", _DC, OpenAISynthesisBackend, "repair_section", _repair
    ),
    _Site(
        "synthesise_write_key_findings", _DC, OpenAISynthesisBackend, "write_key_findings",
        _key_findings,
    ),
    _Site(
        "chat/tool_turn", _DC, OpenAIChatBackend, "chat_turn(force_emit=False)", _chat_tool_turn
    ),
    _Site(
        "chat/stream", _DC, OpenAIChatBackend, "chat_turn(force_emit=True) step 1", _chat_final
    ),
    # traced_parse (core.openai_client.traced_parse)
    _Site("agent_route", _TP, OpenAIAgentBackend, "route", _agent_route),
    _Site("agent_triage", _TP, OpenAIAgentBackend, "triage", _agent_triage),
    _Site("agent_decide", _TP, OpenAIAgentBackend, "decide", _agent_decide),
    _Site("agent_gate_sort", _TP, OpenAIAgentBackend, "sort_gate_turn", _agent_gate_sort),
    _Site(
        "agent_longlist_sort", _TP, OpenAIAgentBackend, "sort_longlist_turn",
        _agent_longlist_sort,
    ),
    _Site(
        "agent_option_design", _TP, OpenAIAgentBackend, "propose_option_design",
        _agent_option_design,
    ),
    _Site("agent_suggest", _TP, OpenAIAgentBackend, "suggest_options", _agent_suggest),
    _Site(
        "task_agent_turn", _TP, OpenAITaskAgentBackend, "turn(EVIDENCE_SEARCH_TASK_AGENT)",
        _task_agent_turn,
    ),
    _Site(
        "task_agent_scoping_turn", _TP, OpenAITaskAgentBackend,
        "turn(OPTIONS_SCOPING_TASK_AGENT)", _task_agent_scoping_turn,
    ),
    _Site("longlist_discover", _TP, OpenAILonglistBackend, "discover", _longlist_discover),
    _Site("longlist_assign", _TP, OpenAILonglistBackend, "assign", _longlist_assign),
    _Site("longlist_themes", _TP, OpenAILonglistBackend, "discover_themes", _longlist_themes),
    _Site(
        "longlist_assign_themes", _TP, OpenAILonglistBackend, "assign_themes",
        _longlist_assign_themes,
    ),
    _Site("longlist_type", _TP, OpenAILonglistBackend, "type_options", _longlist_type),
    _Site("longlist_constrain", _TP, OpenAILonglistBackend, "constrain", _longlist_constrain),
    _Site("longlist_distinct", _TP, OpenAILonglistBackend, "distinct", _longlist_distinct),
    _Site("longlist_authority", _TP, OpenAILonglistBackend, "authority", _longlist_authority),
    _Site(
        "longlist_shortlist", _TP, OpenAILonglistBackend, "propose_shortlist",
        _longlist_shortlist,
    ),
    _Site("option_profile_line", _TP, OpenAILonglistBackend, "profile_line", _profile_line),
    _Site(
        "option_profile_potential_impact", _TP, OpenAILonglistBackend,
        "profile_potential_impact", _profile_potential_impact,
    ),
    _Site(
        "option_profile_ambition", _TP, OpenAILonglistBackend, "profile_ambition",
        _profile_ambition,
    ),
    _Site(
        "option_profile_setting", _TP, OpenAILonglistBackend, "profile_setting",
        _profile_setting,
    ),
    _Site("option_profile_fold", _TP, OpenAILonglistBackend, "fold", _profile_fold),
    _Site(
        "option_profile_place_sentences", _TP, OpenAILonglistBackend, "place_sentences",
        _profile_place_sentences,
    ),
)

#: Call sites the fixture deliberately does not hold, with the reason.
UNCAPTURED: dict[str, str] = {
    "claude_search_generate_queries": (
        "Inventory row 20, ClaudeSearchGenerationBackend.generate_queries: a boto3 Bedrock "
        "`converse` call, not the OpenAI client; it has no route step and no row in the "
        "plan's Steps table, and no route selects it (route search_queries.backend is "
        "never 'claude')."
    ),
}


# --- Capture and serialisation ------------------------------------------------


def _v2_overton_index() -> int:
    """The Overton half starts after the OpenAlex queries (one request each)."""
    return N_QUERIES


def _stop_index(site: _Site) -> int:
    return _v2_overton_index() if site.stop_at == -1 else site.stop_at


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _system_shape(messages: Any) -> str | None:
    """How the first system message is sent: plain text, or content parts with a breakpoint."""
    for message in messages or []:
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return "text"
        if isinstance(content, list) and any(
            isinstance(part, dict) and "prompt_cache_breakpoint" in part for part in content
        ):
            return "parts+breakpoint"
        return "parts"
    return None


def _serialise(site: _Site, kwargs: dict[str, Any], trace_name: str | None) -> dict[str, Any]:
    response_format = kwargs.get("response_format")
    tools = kwargs.get("tools")
    tool_choice = kwargs.get("tool_choice")
    return {
        "module": site.owner.__module__,
        "function": f"{site.owner.__qualname__}.{site.function}",
        "request_path": site.path,
        "trace_name": trace_name,
        "model": kwargs.get("model"),
        "reasoning_effort": kwargs.get("reasoning_effort"),
        "response_format": response_format.__name__ if response_format is not None else None,
        "tools": [tool["function"]["name"] for tool in tools] if tools is not None else None,
        "tool_choice": _json_value(tool_choice) if tool_choice is not None else None,
        "parallel_tool_calls": kwargs.get("parallel_tool_calls"),
        "max_completion_tokens": kwargs.get("max_completion_tokens"),
        "stream": kwargs.get("stream"),
        "extra_body": _json_value(kwargs["extra_body"]) if "extra_body" in kwargs else None,
        "system_shape": _system_shape(kwargs.get("messages")),
        "other_keys": sorted(set(kwargs) - _NAMED_KEYS),
    }


def _capture(site: _Site, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    langfuse = _FakeLangfuse()
    completions = _RecordingCompletions(
        langfuse=langfuse, stop_at=_stop_index(site), respond=site.respond
    )
    client = _RecordingClient(completions)
    with monkeypatch.context() as patch:
        patch.setattr(openai_client_module, "OpenAI", lambda **_kwargs: client)
        try:
            site.drive(langfuse)
        except _Captured:
            pass
        else:  # pragma: no cover - a site spec error
            raise AssertionError(f"{site.step}: the driven entry point made no captured request")
    _verb, kwargs, trace_name = completions.calls[-1]
    return _serialise(site, kwargs, trace_name)


def _fingerprints() -> dict[str, Any]:
    iof, _ = extract_module.extraction_fingerprint("live", finding_vetter_active=True)
    icf, _ = extract_module.icf_extraction_fingerprint("live", finding_vetter_active=True)
    return {
        "extraction_fingerprint": iof,
        "icf_extraction_fingerprint": icf,
        "extraction_fingerprint_source": {
            "extraction_fingerprint": (
                "policy_atlas.evidence_search.extract.extract.extraction_fingerprint"
                "('live', finding_vetter_active=True)"
            ),
            "icf_extraction_fingerprint": (
                "policy_atlas.evidence_search.extract.extract.icf_extraction_fingerprint"
                "('live', finding_vetter_active=True)"
            ),
        },
    }


def _capture_all(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    return {
        "route": ROUTE,
        "captured_at": CAPTURED_AT,
        **_fingerprints(),
        "call_sites": {site.step: _capture(site, monkeypatch) for site in SITES},
        "uncaptured": UNCAPTURED,
    }


def _load_fixture() -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture


@pytest.fixture(autouse=True)
def _openai_direct_route(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pin the default route, no overlay, and a dummy key (the double never calls out)."""
    monkeypatch.delenv(model_routes.ROUTE_ENV, raising=False)
    monkeypatch.delenv(model_routes.OVERLAY_ENV, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", API_KEY)
    model_routes.route.cache_clear()
    assert model_routes.route().name == ROUTE
    yield
    model_routes.route.cache_clear()


# --- Tests ----------------------------------------------------------------------


@pytest.mark.skipif(not os.environ.get(UPDATE_ENV), reason=f"set {UPDATE_ENV}=1 to rewrite")
def test_update_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rewrite the fixture from today's code (deliberate; review the diff)."""
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(_capture_all(monkeypatch), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_fixture_covers_every_call_site() -> None:
    fixture = _load_fixture()
    assert fixture["route"] == ROUTE
    assert sorted(fixture["call_sites"]) == sorted(site.step for site in SITES)
    assert fixture["uncaptured"] == UNCAPTURED
    assert len(SITES) == len({site.step for site in SITES})


def test_extraction_fingerprint_unchanged() -> None:
    fixture = _load_fixture()
    current = _fingerprints()
    for key, value in current.items():
        assert fixture[key] == value, key


def _sites_on(path: str) -> list[_Site]:
    return [site for site in SITES if site.path == path]


def _assert_matches_fixture(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """Today's kwargs equal the fixture exactly.

    The fixture was captured before task 056, then re-captured at the GPT-6
    switch (commit B): that re-capture changed only the 59 model ids, the 44
    efforts that were "not sent" (31 to "medium", the provider default, 13 to
    "low" on the frontier steps) and the two extraction fingerprints, which
    embed the extraction model id. Any other difference is a behaviour change
    and fails here; a deliberate one is re-captured with
    ``CALL_SITE_KWARGS_UPDATE=1`` and the diff recorded in verification.md.
    """
    expected = _load_fixture()["call_sites"][site.step]
    assert _capture(site, monkeypatch) == expected


@pytest.mark.parametrize("site", _sites_on(_PS), ids=lambda site: site.step)
def test_parse_structured_sites(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _assert_matches_fixture(site, monkeypatch)


@pytest.mark.parametrize("site", _sites_on(_DP), ids=lambda site: site.step)
def test_direct_parse_sites(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _assert_matches_fixture(site, monkeypatch)


@pytest.mark.parametrize("site", _sites_on(_DC), ids=lambda site: site.step)
def test_direct_create_sites(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _assert_matches_fixture(site, monkeypatch)


@pytest.mark.parametrize("site", _sites_on(_TP), ids=lambda site: site.step)
def test_traced_parse_sites(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    _assert_matches_fixture(site, monkeypatch)


def test_every_step_has_a_cache_mode_and_sends_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract D3: the cache-mode table covers the route file, and each site sends its mode.

    A site key is its route step, or ``step/part`` where one step has several
    requests. ``auto`` sends no ``extra_body`` and a plain-text system message (a
    driver that passes no system message records ``None``); ``off`` sends the
    body that turns caching off; ``breakpoint`` sends the first system message
    as content parts carrying the breakpoint.
    """
    assert sorted(CACHE_MODES) == sorted(model_routes.route().steps)
    expected_by_mode: dict[str, tuple[Any, set[str | None]]] = {
        "auto": (None, {"text", None}),
        "off": ({"prompt_cache_options": {"mode": "explicit"}}, {"text", None}),
        "breakpoint": (None, {"parts+breakpoint"}),
    }
    for site in SITES:
        mode = CACHE_MODES[site.step.split("/")[0]]
        captured = _capture(site, monkeypatch)
        extra_body, shapes = expected_by_mode[mode]
        assert captured["extra_body"] == extra_body, (site.step, mode)
        assert captured["system_shape"] in shapes, (site.step, mode)
