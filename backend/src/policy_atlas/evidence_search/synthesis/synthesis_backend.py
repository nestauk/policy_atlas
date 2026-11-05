"""The synthesis writer backends (live OpenAI and stub) for the section prompt surfaces.

The prompt text, tool schemas and response models now live in
:mod:`policy_atlas.evidence_search.synthesis.section_prompt` (task 056, so the
prompt hash guard pins them); the history below describes those surfaces.

The repo's fifth and sixth product prompts — lead-authored, versioned, recorded
in synthesis provenance and event payloads. ``synthesise_sections_v2`` (v2, 018 C2:
the evidence-descriptive role menu — owner-scoped addition) is a
single bounded schema-constrained call proposing the intent-led section list.
``synthesise_section_v7`` (v3, task 018 B-B2: the deliberate voice design; v4,
018 C2 round 2: repetition/label-translation rules; v5 = 018 C2 round 3
multi-read-tool turns; v6 = task 021 Phase E unified kind-typed findings read;
v7 = task 022 Phase F cache-prefix RUN/SECTION layout and id-carrying repair)
is the section-loop surface: one system prompt plus
the three tool JSON schemas, **versioned as one unit** — the OpenAI form runs
the bounded tool-calling loop (the repo's first agent loop; the loop runner and
turn accounting live in :mod:`policy_atlas.evidence_search.synthesis.synthesis_tools`).

Standing injection posture, tightened for the loop (contract decision 14):
intent, substrate summaries, finding records, tool-returned frozen chunk text,
lookup results (tag labels included) and the rolling claim ledger enter as
id-keyed JSON data records, never instructions; responses and tool calls are
schema-constrained; the tool set is closed, read-only and code-scoped.

Section emission rides a dedicated ``emit_section`` function schema (the
emission channel, not an executable tool): every loop turn is exactly one
forced function call — one of the three read tools, or ``emit_section``. On the
final turn the loop runner forces ``emit_section`` (cap exhaustion forces
emission, never extends the loop). ``emit_section`` carries the section prose
plus the typed claims that anchor into it (ADR 0015).
"""

from __future__ import annotations

import json
from threading import Lock
from typing import Any, Literal, NotRequired, Protocol, TypedDict

import structlog
from langfuse import Langfuse
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from policy_atlas.core import tracing
from policy_atlas.core.liveness import (
    publish_section_card,
    publish_section_claim,
    publish_section_delta,
)
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import (
    JsonArrayObjectDecoder,
    JsonStringFieldDecoder,
    openai_kwargs,
    require_parsed,
    require_single_tool_call,
    resolve_openai_client,
    with_system_breakpoint,
)
from policy_atlas.core.usage import (
    UsageResult,
    log_usage,
    token_usage_from_provider,
    usage_details,
    usage_metadata,
)
from policy_atlas.evidence_search.group.facet_values import FORBIDDEN_GROUP_LABELS
from policy_atlas.evidence_search.synthesis.cache_modes import cache_mode_for
from policy_atlas.evidence_search.synthesis.section_prompt import (
    CASE_STUDIES_PROMPT_VERSION,
    EMIT_SECTION_TOOL_SCHEMA,
    FORCE_EMIT_REPAIRS_TOOL_CHOICE,
    FORCE_EMIT_SECTION_TOOL_CHOICE,
    FULL_REPORT_INTRO_PROMPT_VERSION,
    FULL_REPORT_INTRO_SYSTEM_PROMPT,
    FULL_REPORT_INTRO_USER_TEMPLATE,
    KEY_FINDINGS_PROMPT_VERSION,
    MOST_RELEVANT_NOTE_PROMPT_VERSION,
    MRS_NOTE_SYSTEM_PROMPT,
    MRS_NOTE_USER_TEMPLATE,
    SECTION_PROMPT_VERSION,
    SECTION_REPAIR_PROMPT_VERSION,
    SECTION_TITLE_PROPOSAL_MAX,
    SECTION_TURN_TOOL_CHOICE,
    SECTIONS_PROMPT_VERSION,
    CaseStudyCardWire,
    CaseStudyClaimWire,
    CaseStudyWire,
    ChunkCitationWire,
    ClaimWire,
    GapPayloadWire,
    IntroWire,
    NoteWire,
    PatternPayloadWire,
    RepairItemWire,
    SectionProposalWire,
    SectionProseWire,
    SectionRepairWire,
    SectionWire,
    SummaryJudgeWire,
    SummaryWire,
    ThemePayloadWire,
    build_artefact_summary_messages,
    build_block_summary_messages,
    build_case_studies_messages,
    build_key_findings_messages,
    build_section_messages,
    build_section_repair_messages,
    build_sections_messages,
    build_summary_judge_messages,
    section_request_tools,
)
from policy_atlas.evidence_search.synthesis.summary_prompts import (
    SUMMARISER_PROMPT_VERSION,
    SUMMARY_JUDGE_PROMPT_VERSION,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    MalformedEmissionError,
    ToolCallRequest,
    ToolExchange,
    citable_sources,
    is_qualified_group_id,
    name_sources,
)

log = structlog.get_logger()


# The contracted model floor (the 009 nano lesson is binding); section/prose
# quality on real corpora is eval territory, not asserted by the build.
# Models from the route file (task 053); see core/model_routes.py. Every call
# site below is its own step (task 056): its own model and its own effort.
# ``SYNTHESIS_MODEL`` is the section-turn step's model, the one the run's
# provenance stamps as "the synthesis model".
SYNTHESIS_MODEL = route().model_for("synthesise_section_turn")
CASE_STUDIES_MODEL = route().model_for("synthesise_write_case_studies")
# The matching prompts live in section_prompt.py.
MRS_NOTE_MODEL = route().model_for("synthesise_write_source_note")
FULL_REPORT_INTRO_MODEL = route().model_for("synthesise_write_intro")


def _step_kwargs(step: str) -> dict[str, Any]:
    """Return the model, reasoning effort and request timeout for one synthesis call site.

    All three come from the route file (tasks 056 and 057): Terra needs
    ``"none"`` or tool-bearing and structured-parse calls return 400 (029),
    and the route file says so on the writer steps.

    Args:
        step: A step name from the route file's ``[steps]`` table.

    Returns:
        Kwargs suitable for ``chat.completions.create`` / ``parse``.
    """
    return openai_kwargs(
        route().model_for(step),
        reasoning_effort=route().effort_for(step),
        prompt_cache=cache_mode_for(step),
        timeout_s=route().timeout_for(step),
    )


def _cache_messages(step: str, messages: list[Any]) -> list[Any]:
    """Return the messages as they should be sent for one synthesis call site.

    For a ``"breakpoint"`` step the system message is sent as content parts that
    mark the end of the part the provider may store and reuse. For every other
    mode the messages are sent unchanged.

    Args:
        step: A step name from the route file's ``[steps]`` table.
        messages: The chat messages built for the call.

    Returns:
        The messages to send.
    """
    if cache_mode_for(step) == "breakpoint":
        return with_system_breakpoint(messages)
    return messages

# Read-path ceiling for section titles (artefacts minted before task 034); the
# proposal bounds the prompt states live in section_prompt.py.
SECTION_TITLE_MAX = 200

# Forbidden generic section titles — the 012 label set, shared verbatim
# (contract rev 8 M5), plus the section-shaped catch-alls of the same kind.
FORBIDDEN_SECTION_TITLES = FORBIDDEN_GROUP_LABELS | frozenset(
    {"overview", "introduction", "conclusion", "summary", "findings", "background"}
)

CLAIM_TYPES = ("finding", "chunk", "pattern", "theme", "gap", "reasoning")
GAP_GRADES = ("corpus_absence", "acknowledged_sparsity", "inferred")

# Per-emission bounds, enforced at salvage: turn/section/budget caps bound
# the loop, but nothing bounded one emission's claim count or text length —
# the one hole in the cap discipline (review-stack finding). Overflow counts
# into claims_rejected_structural, never silently.
EMISSION_CLAIMS_MAX = 50
CLAIM_TEXT_MAX = 5000

# Bound on the authored section prose (v2 wire): a single emission's prose is
# capped so one oversized emission cannot drive unbounded content/span work.
# Over-cap or missing/non-str prose is a turn-consuming recoverable
# MalformedEmissionError (the same lane as an unparseable envelope).
SECTION_PROSE_MAX = 20_000


class SectionTurn(TypedDict):
    """One backend turn: exactly one of ``tool_calls`` (one or more read-tool
    calls) or ``claims`` (the prose-first emission).

    ``malformed_claims`` counts claim objects a live emission carried that
    failed structural validation and were salvaged away (per-claim, never a
    whole-emission failure) — surfaced into ``claims_rejected_structural``.
    ``extra_tool_calls_ignored`` counts the further tool calls a forced
    final turn carried beyond the ``emit_section`` call that was taken (task
    056 D10: parallel tool calls stay on for the forced turn so it reads the
    cache). The ``claims`` field name is kept for the wire shape ``SectionProseWire``
    (prose + claims) to bound the diff.

    ``ready`` is True when the writer said it has gathered enough (task 058,
    owner 2026-11-05): it called ``write_section``, or replied with no tool
    call at all. Such a turn carries no reads and no claims; the loop then
    runs the write turn, which streams the section to the user.
    """

    tool_calls: list[ToolCallRequest]
    claims: SectionProseWire | None
    malformed_claims: NotRequired[int]
    extra_tool_calls_ignored: NotRequired[int]
    ready: NotRequired[bool]


# --- The backend seam ---


class SynthesisBackend(Protocol):
    """The synthesis writer seam (task 013) — both writer surfaces, one backend.

    Backends perform one schema-constrained provider call per method (or
    deterministic fixture-like work) and return raw output after structural
    parsing only. Callers own semantic validation (proposal validation, the
    per-type claim validators) and all budget/turn/repair policy — the loop
    runner in :mod:`policy_atlas.evidence_search.synthesis.synthesis_tools` owns turn
    accounting, tool execution and cap enforcement. A transport or parse failure raises so the
    caller can fail the component honestly.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        """Propose the intent-led section list (``synthesise_sections_v1``).

        Args:
            intent: The evidence scope's intent, verbatim.
            substrate: Id-keyed substrate summaries.
            rejection: Validation errors driving the one bounded repair call.
            section_budget: Optional ordinary-section ceiling from the plan.

        Returns:
            Raw structurally parsed proposal plus token usage.
        """
        ...

    def write_block_summary(self, seed: dict[str, Any]) -> UsageResult[SummaryWire]:
        """Write one navigation summary for a persisted report block.

        Args:
            seed: Block title, prose, and epistemic annotations as data.

        Returns:
            Structurally parsed summary plus provider usage.
        """
        ...

    def judge_summary(
        self, *, summary: str, detail: dict[str, Any]
    ) -> UsageResult[SummaryJudgeWire]:
        """Judge a summary directly against its raw persisted detail.

        Args:
            summary: Candidate navigation summary.
            detail: Raw detail and its epistemic annotations.

        Returns:
            Flat pass/fail verdict plus provider usage.
        """
        ...

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        """Produce one loop turn: one or more read-tool calls, the claims
        emission, or the ready signal.

        Args:
            seed: Id-keyed section seed.
            transcript: Executed tool exchanges so far.
            force_emit: True on the final turn — the backend must emit claims.

        Returns:
            The turn plus token usage: exactly one of ``tool_calls`` (one or
            more entries), ``claims``, or ``ready`` (the writer has gathered
            enough; the loop runs the write turn next, task 058).
        """
        ...

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionRepairWire]:
        """One loop-free repair of the failing claims' prose segments only.

        Args:
            seed: The section seed used by the original loop.
            transcript: The section's executed tool exchanges. Kept on the
                seam for compatibility; live repair prompts do not resend it.
            failing: Dependency-complete failing-claim records with claim ids,
                verification rationales, prose context and support records.

        Returns:
            Raw structurally parsed replacement segments plus token usage. The
            caller binds repairs by ``claim_id`` against the failing set.
        """
        ...

    def write_key_findings(
        self, seed: dict[str, Any]
    ) -> UsageResult[SectionProseWire]:
        """Emit the key-findings block in one schema-constrained call (no loop).

        The block is produced last (after every section incl. conclusions) and
        shown first (ADR 0015 §8). It re-states the report's headline claims in
        the same prose-first, span-anchored form; an empty emission (empty prose
        + no claims) is the explicit no-headline absence path.

        Args:
            seed: The key-findings seed — intent + the run's surviving claims
                ledger with evidence + available claim types.

        Returns:
            Raw structurally parsed prose + claims plus token usage.
        """
        ...

    def write_case_studies(
        self, seed: dict[str, Any]
    ) -> UsageResult[CaseStudyWire]:
        """Emit the case-studies cards in one schema-constrained call.

        Args:
            seed: The case-studies seed — intent + verified claims ledger
                with evidence + cited document metadata.

        Returns:
            Raw structurally parsed cards plus token usage.
        """
        ...

    def write_source_note(
        self, seed: dict[str, Any]
    ) -> UsageResult[NoteWire]:
        """Emit a one-sentence grounded note for one cited source.

        Args:
            seed: Source note seed — title + appraisal + evidence type +
                cited claim texts and quotes.

        Returns:
            Structurally parsed note plus token usage.
        """
        ...

    def write_full_report_intro(
        self, seed: dict[str, Any]
    ) -> UsageResult[IntroWire]:
        """Emit a short introduction to the full-report body sections.

        Args:
            seed: Report intent plus ordered body section titles and briefs.

        Returns:
            Structurally parsed intro plus token usage.
        """
        ...


def _strip_code_fence(text: str) -> str:
    """Remove a Markdown code fence the model may wrap its JSON reply in.

    The streamed write turn asks for a bare JSON object, but a model sometimes
    wraps it as ```` ```json … ``` ````. A leading fence line (with or without
    a language tag) and a trailing ```` ``` ```` are dropped; any other text is
    returned as it came, stripped of outer whitespace.

    Args:
        text: The whole streamed reply.

    Returns:
        The reply without the fence.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return stripped
    body = stripped[first_newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def _salvage_section(arguments: str) -> tuple[SectionProseWire, int]:
    """Parse an ``emit_section`` argument string: prose plus claim-by-claim.

    Live emissions malform at claim grain (a v1 run persistently emitted
    ``gap.sparsity`` as a float); whole-emission rejection let one bad field
    poison every turn until the cap. Valid claims are salvaged; malformed
    claims are counted (the caller lands them in
    ``claims_rejected_structural`` — visible, never silent) and logged
    bounded. The prose is validated whole: missing/non-str prose or prose over
    :data:`SECTION_PROSE_MAX` is a turn-consuming recoverable failure.

    Raises:
        MalformedEmissionError: If the envelope itself does not parse (not a
            JSON object with a ``claims`` list), or the prose is missing,
            non-str or over-cap — the turn-consuming recoverable event.
    """
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise MalformedEmissionError(f"emit_section arguments not JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise MalformedEmissionError(
            "emit_section arguments must be an object with a 'claims' list"
        )
    prose = payload.get("prose")
    if not isinstance(prose, str):
        raise MalformedEmissionError("emit_section arguments must carry a 'prose' string")
    if len(prose) > SECTION_PROSE_MAX:
        raise MalformedEmissionError(
            f"emit_section prose exceeds {SECTION_PROSE_MAX} chars"
        )
    raw_claims = payload["claims"]
    valid: list[ClaimWire] = []
    malformed = 0
    if len(raw_claims) > EMISSION_CLAIMS_MAX:
        # No cap bound a single emission's claim count — one oversized
        # emission drives O(claims) writes and ledger/prompt growth.
        malformed += len(raw_claims) - EMISSION_CLAIMS_MAX
        log.warning(
            "synthesis.emission_overflow",
            claims_emitted=len(raw_claims),
            cap=EMISSION_CLAIMS_MAX,
        )
        raw_claims = raw_claims[:EMISSION_CLAIMS_MAX]
    for index, raw_claim in enumerate(raw_claims):
        if (
            isinstance(raw_claim, dict)
            and isinstance(raw_claim.get("text"), str)
            and len(raw_claim["text"]) > CLAIM_TEXT_MAX
        ):
            malformed += 1
            log.warning(
                "synthesis.claim_malformed",
                claim_index=index,
                error=f"claim text exceeds {CLAIM_TEXT_MAX} chars",
            )
            continue
        try:
            valid.append(ClaimWire.model_validate(raw_claim))
        except ValidationError as exc:
            malformed += 1
            log.warning(
                "synthesis.claim_malformed",
                claim_index=index,
                error=str(exc)[:300],
            )
    return SectionProseWire(prose=prose, claims=valid), malformed


class StreamedClaimMarker:
    """Mark the writer's citations on the page as each claim closes (task 058).

    In plain terms: the streamed write turn sends the prose first and then the
    claims, each naming the exact words of the prose it supports and the
    sources it cites. As each claim object closes, this class reads it alone,
    finds its words in the prose streamed so far (the same ordered search as
    the final binding: from where the last claim ended, else the first place
    that does not overlap a claim already placed), and publishes the span and
    the cited sources' names through :func:`publish_section_claim`.

    Display-only: a claim that does not parse, does not validate, does not
    bind, or cites no known source is skipped; nothing here can raise or
    change what the final parse returns.

    Args:
        index: The page's index for the section.
        seed: The section seed (its member findings are citable).
        transcript: The section's tool exchanges.
    """

    def __init__(
        self, index: int, seed: dict[str, Any], transcript: list[ToolExchange]
    ) -> None:
        self._index = index
        self._seed = seed
        self._transcript = transcript
        self._claims = JsonArrayObjectDecoder("claims")
        self._prose = ""
        self._cursor = 0
        self._bound: list[tuple[int, int]] = []
        self._seen = 0
        self._sources: (
            tuple[dict[str, tuple[str, str | None]], dict[str, tuple[str, str | None]]] | None
        ) = None
        self._broken = False

    def feed(self, fragment: str, decoded_prose: str) -> None:
        """Take one streamed piece and the prose decoded from it.

        Args:
            fragment: The raw streamed JSON text.
            decoded_prose: The prose characters decoded from ``fragment``.
        """
        if self._broken:
            return
        try:
            self._prose += decoded_prose
            for raw in self._claims.feed(fragment):
                self._claim(raw)
        except Exception as exc:  # noqa: BLE001 - display-only, never fails the turn
            self._broken = True
            log.warning("synthesis.streamed_claim_marker.failed", error=type(exc).__name__)

    def _claim(self, raw: str) -> None:
        self._seen += 1
        if self._seen > EMISSION_CLAIMS_MAX:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        text = payload.get("text")
        if not isinstance(text, str) or not text or len(text) > CLAIM_TEXT_MAX:
            return
        try:
            claim = ClaimWire.model_validate(payload)
        except ValidationError:
            return
        span = self._bind(claim.text)
        if span is None:
            return
        sources = self._cited_sources(claim)
        if sources:
            publish_section_claim(self._index, span[0], span[1], sources)

    def _bind(self, text: str) -> tuple[int, int] | None:
        prose = self._prose
        at = prose.find(text, self._cursor)
        if at == -1:
            search = 0
            while True:
                candidate = prose.find(text, search)
                if candidate == -1:
                    break
                if not self._overlaps((candidate, candidate + len(text))):
                    at = candidate
                    break
                search = candidate + 1
        if at == -1:
            return None
        span = (at, at + len(text))
        if self._overlaps(span):
            return None
        self._bound.append(span)
        self._cursor = max(self._cursor, span[1])
        return span

    def _overlaps(self, span: tuple[int, int]) -> bool:
        return any(span[0] < end and start < span[1] for start, end in self._bound)

    def _cited_sources(self, claim: ClaimWire) -> list[tuple[str, str]]:
        if self._sources is None:
            self._sources = citable_sources(self._seed, self._transcript)
        by_chunk, by_finding = self._sources
        found: list[tuple[str, str | None]] = []
        if claim.claim_type == "chunk":
            found = [
                by_chunk[citation.chunk_record_id]
                for citation in claim.citations
                if citation.chunk_record_id in by_chunk
            ]
        elif claim.claim_type == "finding":
            found = [
                by_finding[finding_id]
                for finding_id in claim.cited_finding_ids
                if finding_id in by_finding
            ]
        return name_sources(found)


class StreamedCardPublisher:
    """Send each case-study card to the page as it closes in the reply (task 058).

    In plain terms: the case-studies reply is one JSON object,
    ``{"cards": [{"title": ..., "prose": ..., ...}, ...]}``, arriving in
    pieces. As each card object closes it is read on its own and, when it has
    a title and some text, sent through :func:`publish_section_card`.

    Display-only: a card that does not parse or lacks a title or text is
    skipped; nothing here can raise or change what the final parse returns.

    Args:
        index: The page's index for the case-studies slot.
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._cards = JsonArrayObjectDecoder("cards")
        self._broken = False

    def feed(self, fragment: str) -> None:
        """Take one streamed piece of the reply.

        Args:
            fragment: The raw streamed JSON text.
        """
        if self._broken:
            return
        try:
            for raw in self._cards.feed(fragment):
                self._card(raw)
        except Exception as exc:  # noqa: BLE001 - display-only, never fails the call
            self._broken = True
            log.warning("synthesis.streamed_card_publisher.failed", error=type(exc).__name__)

    def _card(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        title, prose = payload.get("title"), payload.get("prose")
        if not isinstance(title, str) or not isinstance(prose, str):
            return
        if not title.strip() or not prose.strip():
            return
        publish_section_card(self._index, title, prose)


def _salvage_repairs(arguments: str) -> SectionRepairWire:
    """Parse an ``emit_repairs`` argument string into the repair wire.

    Raises:
        MalformedEmissionError: If the arguments do not parse into
            :class:`SectionRepairWire` — the loop-free, unrepeatable repair
            then produced nothing and the caller lands the failing claims per
            the exhaustion rules.
    """
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise MalformedEmissionError(f"emit_repairs arguments not JSON: {exc}") from exc
    try:
        return SectionRepairWire.model_validate(payload)
    except ValidationError as exc:
        raise MalformedEmissionError(
            f"emit_repairs arguments invalid: {str(exc)[:300]}"
        ) from exc


# Deterministic connective sentence spliced between stub claim texts so the
# stub's prose is more than a bare join (block content ≠ "\n\n".join) while
# every claim text stays an exact substring bindable by the span binder.
_STUB_CONNECTIVE = " On this the section observes the following. "


def _stub_prose(texts: list[str]) -> str:
    """Join claim texts with a deterministic connective sentence between each."""
    return _STUB_CONNECTIVE.join(texts)


def _json_object_or_empty(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _strip_control_chars(text: str) -> str:
    return "".join(ch for ch in text if ord(ch) >= 32 and ord(ch) != 127)


def _record_id(record: Any, *keys: str) -> str | None:
    if isinstance(record, str):
        return record
    if not isinstance(record, dict):
        return None
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _group_ids_from_substrate(substrate: dict[str, Any]) -> list[str]:
    grouping = substrate.get("grouping", {})
    if not isinstance(grouping, dict):
        return []
    groups = grouping.get("groups", [])
    if not isinstance(groups, list):
        return []
    group_ids: list[str] = []
    for group in groups:
        group_id = _record_id(group, "group_id")
        if group_id is not None and is_qualified_group_id(group_id):
            group_ids.append(group_id)
    return group_ids


def _section_title(seed: dict[str, Any]) -> str:
    section = seed.get("section", {})
    if isinstance(section, dict):
        title = section.get("title")
        if isinstance(title, str):
            return title
    return "Section"


def _section_focus(seed: dict[str, Any]) -> str:
    section = seed.get("section", {})
    if isinstance(section, dict):
        focus = section.get("focus")
        if isinstance(focus, str):
            return focus
    return ""


def _section_group_ids(seed: dict[str, Any]) -> list[str]:
    section = seed.get("section", {})
    if not isinstance(section, dict):
        return []
    group_ids = section.get("group_ids", [])
    if not isinstance(group_ids, list):
        return []
    return [group_id for group_id in group_ids if isinstance(group_id, str)]


def _transcript_records(
    transcript: list[ToolExchange], *, tool: str, key: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for exchange in transcript:
        if exchange["tool"] != tool:
            continue
        raw = exchange["result"].get(key, [])
        if isinstance(raw, list):
            records.extend(record for record in raw if isinstance(record, dict))
    return records


def _transcript_chunks(transcript: list[ToolExchange]) -> list[dict[str, Any]]:
    return _transcript_records(transcript, tool="search_chunks", key="chunks")


def _transcript_findings(transcript: list[ToolExchange]) -> list[dict[str, Any]]:
    records = _transcript_records(transcript, tool="query_findings", key="findings")
    records.extend(_transcript_records(transcript, tool="query_findings", key="iof_findings"))
    records.extend(_transcript_records(transcript, tool="query_findings", key="icf_findings"))
    return records


def _chunk_content_by_id(transcript: list[ToolExchange]) -> dict[str, str]:
    content_by_id: dict[str, str] = {}
    for chunk in _transcript_chunks(transcript):
        chunk_id = _record_id(chunk, "chunk_record_id", "id")
        content = chunk.get("content")
        if chunk_id is not None and isinstance(content, str):
            content_by_id[chunk_id] = content
    return content_by_id


def _repair_dependency_chunk_content_by_id(
    failing: list[dict[str, Any]],
) -> dict[str, str]:
    content_by_id: dict[str, str] = {}
    for record in failing:
        dependencies = record.get("dependencies")
        if not isinstance(dependencies, dict):
            continue
        chunks = dependencies.get("chunks")
        if not isinstance(chunks, dict):
            continue
        for chunk_id, chunk_record in chunks.items():
            if not isinstance(chunk_id, str) or not isinstance(chunk_record, dict):
                continue
            content = chunk_record.get("content")
            if isinstance(content, str):
                content_by_id[chunk_id] = content
    return content_by_id


def _first_theme_reference(
    seed: dict[str, Any],
) -> tuple[Literal["characterisation", "grouping"], str] | None:
    substrate = seed.get("substrate", {})
    if not isinstance(substrate, dict):
        return None
    characterisation = substrate.get("characterisation", {})
    if isinstance(characterisation, dict):
        themes = characterisation.get("themes", [])
        if isinstance(themes, list):
            for theme in themes:
                theme_id = _record_id(theme, "theme_id", "id")
                if theme_id is not None:
                    return "characterisation", theme_id
    grouping = substrate.get("grouping", {})
    if isinstance(grouping, dict):
        groups = grouping.get("groups", [])
        if isinstance(groups, list):
            for group in groups:
                group_id = _record_id(group, "group_id")
                if group_id is not None and is_qualified_group_id(group_id):
                    return "grouping", group_id
    return None


def _first_named_tool_call(
    response: Any, *, name: str, label: str
) -> tuple[Any, list[str]]:
    """Return a forced response's first ``name`` call and the ignored calls' names.

    The forced final section turn and the repair keep ``parallel_tool_calls``
    on (task 056 D10, so their request matches the cached prefix), so the
    provider may return more than one call. The first call named ``name`` is
    taken; every other call is ignored, logged
    (``synthesise.extra_tool_calls_ignored``) and counted by the caller. When
    no call carries ``name`` the first call is returned, so the caller's own
    protocol check still fires.

    Args:
        response: A chat-completions ``create`` response.
        name: The forced function's name.
        label: Human-readable call label for error messages and the log.

    Returns:
        The taken tool call and the names of the ignored ones, in order.

    Raises:
        RuntimeError: If the response has no choices or no tool call.
    """
    if not response.choices:
        raise RuntimeError(f"OpenAI {label} response had no choices.")
    tool_calls = response.choices[0].message.tool_calls or []
    if not tool_calls:
        raise RuntimeError(f"OpenAI {label} response had no tool call.")
    taken_index = next(
        (index for index, call in enumerate(tool_calls) if call.function.name == name), 0
    )
    ignored = [
        str(call.function.name)
        for index, call in enumerate(tool_calls)
        if index != taken_index
    ]
    if ignored:
        log.warning(
            "synthesise.extra_tool_calls_ignored",
            call=label,
            count=len(ignored),
            names=ignored,
        )
    return tool_calls[taken_index], ignored


def _turn_output(turn: SectionTurn) -> dict[str, Any]:
    claims = turn["claims"]
    return {
        "tool_calls": turn["tool_calls"],
        "claims": claims.model_dump() if claims is not None else None,
    }


class OpenAISynthesisBackend:
    """Live OpenAI implementation of the section proposal and section loop seams.

    Args:
        api_key: Optional OpenAI API key. If omitted, the route's key variable is read
            from the environment.
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
        """Create a live synthesis backend.

        Args:
            api_key: Optional OpenAI API key.
            langfuse_client: Optional Langfuse client for generation spans.
        """
        self._client = resolve_openai_client(api_key, backend_name="OpenAISynthesisBackend")
        self._langfuse_client = langfuse_client
        self._turn_count = 0
        self._lock = Lock()
        # Streamed final turns that fell back to the forced tool call (task 058, N6).
        self.stream_fallbacks = 0

    @property
    def langfuse_client(self) -> Langfuse | None:
        """Tracing client shared with the section read loop (``tool:*`` spans)."""
        return self._langfuse_client

    def _section_messages(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> list[dict[str, Any]]:
        return build_section_messages(seed, transcript, force_emit=force_emit)

    @property
    def _section_prompt_version(self) -> str:
        return SECTION_PROMPT_VERSION

    def _next_turn_index(self) -> int:
        with self._lock:
            self._turn_count += 1
            return self._turn_count

    def _parse_proposal_once(
        self,
        messages: list[dict[str, Any]],
    ) -> UsageResult[SectionProposalWire]:
        completions: Any = self._client.chat.completions
        response = completions.parse(
            **_step_kwargs("synthesise_propose_sections"),
            messages=_cache_messages("synthesise_propose_sections", messages),
            response_format=SectionProposalWire,
        )
        log_usage("synthesis.proposal.usage", response.usage)
        parsed_model: SectionProposalWire = require_parsed(
            response, label="synthesis section proposal"
        )
        return parsed_model, token_usage_from_provider(response.usage)

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        """Propose sections through structured OpenAI output.

        Args:
            intent: Evidence-scope intent.
            substrate: Available substrate summaries.
            rejection: Optional rejected-proposal reasons for the bounded repair call.
            section_budget: Optional ordinary-section ceiling from the plan.

        Returns:
            Raw structurally parsed section proposal plus token usage.

        Raises:
            RuntimeError: If the provider response is empty or unparsed.
        """
        messages = build_sections_messages(
            intent=intent,
            substrate=substrate,
            rejection=rejection,
            section_budget=section_budget,
        )

        def _update(
            span: Any, result: UsageResult[SectionProposalWire]
        ) -> None:
            proposal, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=proposal.model_dump(),
                model=route().model_for("synthesise_propose_sections"),
                metadata={
                    "prompt_version": SECTIONS_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        proposal, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:propose_sections",
            step="synthesise_propose_sections",
            call=lambda: self._parse_proposal_once(messages),
            update=_update,
        )
        return proposal, usage

    def _write_summary_once(
        self, messages: list[dict[str, Any]], *, step: str
    ) -> UsageResult[SummaryWire]:
        completions: Any = self._client.chat.completions
        response = completions.parse(
            **_step_kwargs(step),
            messages=_cache_messages(step, messages),
            response_format=SummaryWire,
        )
        log_usage("synthesis.summary.usage", response.usage)
        parsed = require_parsed(response, label="synthesis summary")
        return parsed, token_usage_from_provider(response.usage)

    def write_block_summary(self, seed: dict[str, Any]) -> UsageResult[SummaryWire]:
        """Write a block navigation summary through structured OpenAI output.

        Args:
            seed: Block title, prose, and epistemic annotations as data.

        Returns:
            Structurally parsed summary plus provider usage.
        """
        is_artefact = seed.get("kind") == "artefact"
        step = (
            "synthesise_write_artefact_summary"
            if is_artefact
            else "synthesise_write_block_summary"
        )
        messages = (
            build_artefact_summary_messages(seed)
            if is_artefact
            else build_block_summary_messages(seed)
        )

        def _update(span: Any, result: UsageResult[SummaryWire]) -> None:
            summary, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=summary.model_dump(),
                model=route().model_for(step),
                metadata={"prompt_version": SUMMARISER_PROMPT_VERSION, **usage_metadata(usage)},
            )

        return tracing.traced_attempts(
            self._langfuse_client,
            name=(
                "synthesise:write_artefact_summary"
                if seed.get("kind") == "artefact"
                else "synthesise:write_block_summary"
            ),
            step=step,
            call=lambda: self._write_summary_once(messages, step=step),
            update=_update,
        )

    def judge_summary(
        self, *, summary: str, detail: dict[str, Any]
    ) -> UsageResult[SummaryJudgeWire]:
        """Judge a summary through structured OpenAI output.

        Args:
            summary: Candidate navigation summary.
            detail: Raw detail and its epistemic annotations.

        Returns:
            Flat pass/fail verdict plus provider usage.
        """
        messages = build_summary_judge_messages(summary=summary, detail=detail)

        def _call() -> UsageResult[SummaryJudgeWire]:
            completions: Any = self._client.chat.completions
            response = completions.parse(
                **_step_kwargs("synthesise_judge_summary"),
                messages=_cache_messages("synthesise_judge_summary", messages),
                response_format=SummaryJudgeWire,
            )
            log_usage("synthesis.summary_judge.usage", response.usage)
            parsed = require_parsed(response, label="synthesis summary judge")
            return parsed, token_usage_from_provider(response.usage)

        def _update(span: Any, result: UsageResult[SummaryJudgeWire]) -> None:
            verdict, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=verdict.model_dump(),
                model=route().model_for("synthesise_judge_summary"),
                metadata={"prompt_version": SUMMARY_JUDGE_PROMPT_VERSION, **usage_metadata(usage)},
            )

        return tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:judge_summary",
            step="synthesise_judge_summary",
            call=_call,
            update=_update,
        )

    def _create_section_turn_once(
        self,
        messages: list[dict[str, Any]],
        *,
        force_emit: bool,
        tools: list[dict[str, Any]] | None = None,
    ) -> UsageResult[SectionTurn]:
        # Task 056 D10: every turn sends the same five tools and parallel tool
        # calls, so the request prefix matches the cache; tool_choice alone
        # differs (allowed_tools over the four section tools, or emit_section
        # by name on the forced final turn). ``tools`` defaults to the full
        # lookup vocabulary when a caller has no seed to derive it from.
        completions: Any = self._client.chat.completions
        response = completions.create(
            **_step_kwargs("synthesise_section_turn"),
            messages=messages,
            tools=tools if tools is not None else section_request_tools({}),
            parallel_tool_calls=True,
            tool_choice=(
                FORCE_EMIT_SECTION_TOOL_CHOICE if force_emit else SECTION_TURN_TOOL_CHOICE
            ),
        )
        log_usage("synthesis.section_turn.usage", response.usage)

        def _emit_turn(arguments: str) -> UsageResult[SectionTurn]:
            section, malformed = _salvage_section(arguments)
            turn: SectionTurn = {"tool_calls": [], "claims": section}
            if malformed:
                turn["malformed_claims"] = malformed
            return turn, token_usage_from_provider(response.usage)

        def _read_turn(name: str, arguments: str) -> UsageResult[SectionTurn]:
            return {
                "tool_calls": [{"tool": name, "arguments": _json_object_or_empty(arguments)}],
                "claims": None,
            }, token_usage_from_provider(response.usage)

        if force_emit:
            taken, ignored = _first_named_tool_call(
                response, name="emit_section", label="synthesis section turn"
            )
            name = taken.function.name
            arguments = taken.function.arguments
            if not isinstance(name, str) or not name:
                raise RuntimeError("OpenAI synthesis section turn returned an unnamed tool call.")
            if not isinstance(arguments, str):
                arguments = "{}"
            forced_turn = _emit_turn(arguments) if name == "emit_section" else _read_turn(
                name, arguments
            )
            if ignored:
                forced_turn[0]["extra_tool_calls_ignored"] = len(ignored)
            return forced_turn

        def _ready_turn() -> UsageResult[SectionTurn]:
            return {
                "tool_calls": [],
                "claims": None,
                "ready": True,
            }, token_usage_from_provider(response.usage)

        if not response.choices:
            raise RuntimeError("OpenAI synthesis section turn response had no choices.")
        message_tool_calls = response.choices[0].message.tool_calls or []
        if not message_tool_calls:
            # A bare reply with no tool call means the writer is ready to write
            # (owner, 2026-11-05): the loop runs the write turn next.
            return _ready_turn()

        if len(message_tool_calls) == 1:
            only_call = message_tool_calls[0]
            name = only_call.function.name
            arguments = only_call.function.arguments
            if not isinstance(name, str) or not name:
                raise RuntimeError("OpenAI synthesis section turn returned an unnamed tool call.")
            if not isinstance(arguments, str):
                arguments = "{}"
            if name == "write_section":
                return _ready_turn()
            if name == "emit_section":
                return _emit_turn(arguments)
            return _read_turn(name, arguments)

        read_calls: list[ToolCallRequest] = []
        emit_arguments: str | None = None
        write_requested = False
        for tool_call in message_tool_calls:
            name = tool_call.function.name
            arguments = tool_call.function.arguments
            if not isinstance(name, str) or not name:
                raise RuntimeError("OpenAI synthesis section turn returned an unnamed tool call.")
            if not isinstance(arguments, str):
                arguments = "{}"
            if name == "write_section":
                write_requested = True
                continue
            if name == "emit_section":
                emit_arguments = arguments
                continue
            read_calls.append({"tool": name, "arguments": _json_object_or_empty(arguments)})
        if emit_arguments is not None and not read_calls:
            # Every parallel call was emit_section (perhaps beside
            # write_section) — honour the emission rather than returning an
            # empty turn the loop would treat as a protocol violation.
            return _emit_turn(emit_arguments)
        if write_requested and not read_calls:
            # Every parallel call was write_section: the writer is ready.
            return _ready_turn()
        if write_requested:
            # write_section beside reads: run the reads and drop the write;
            # the model sees the results and calls write_section again.
            log.warning(
                "synthesis.write_with_reads_deferred", read_tool_count=len(read_calls)
            )
        if emit_arguments is not None:
            log.warning(
                "synthesis.emit_with_reads_deferred", read_tool_count=len(read_calls)
            )
        return {"tool_calls": read_calls, "claims": None}, token_usage_from_provider(response.usage)

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        """Produce one OpenAI tool-forced section-loop turn.

        Args:
            seed: Section seed record.
            transcript: Executed tool exchanges so far.
            force_emit: Whether this is the final forced-emission turn.

        Returns:
            Read-tool call requests, a claims emission, or (on an open turn) the
            ready signal, plus token usage.

        Raises:
            RuntimeError: If the provider response violates the one-tool-call protocol.
        """
        messages = self._section_messages(seed, transcript, force_emit=force_emit)
        tools = section_request_tools(seed)
        turn_index = self._next_turn_index() if self._langfuse_client is not None else 0

        def _update(span: Any, result: UsageResult[SectionTurn]) -> None:
            turn, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=_turn_output(turn),
                model=route().model_for("synthesise_section_turn"),
                metadata={
                    "prompt_version": self._section_prompt_version,
                    "force_emit": force_emit,
                    "transcript_length": len(transcript),
                    "turn_index": turn_index,
                    "extra_tool_calls_ignored": int(turn.get("extra_tool_calls_ignored", 0)),
                    **usage_metadata(usage),
                },
            )

        turn, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:section_turn",
            step="synthesise_section_turn",
            call=lambda: self._create_section_turn_once(
                messages, force_emit=force_emit, tools=tools
            ),
            update=_update,
        )
        return turn, usage

    def section_emit_stream(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
    ) -> UsageResult[SectionTurn]:
        """Write the section as one streamed reply (task 058, N6; owner 2026-11-05).

        This is every section's write turn: the turn after the writer calls
        ``write_section`` (it has gathered enough), and the forced final turn
        when the turn budget runs out.

        The request keeps the section turns' tools on it, with no tool allowed
        (``tool_choice="none"``) and no structured-output schema, and the last
        message asks for the ``emit_section`` arguments as one JSON object.
        Keeping the tools means the provider can reuse the part of the prompt
        it has already stored from the earlier turns (its "prompt cache"); a
        structured-output schema would change that stored part and lose the
        reuse (probe, 2026-11-05). Each piece of prose is sent to the user as
        it arrives through :func:`publish_section_delta`. Each claim object is
        read as soon as it closes, and a claim whose text is found in the
        prose and that cites a source is sent to the page with its sources
        (:class:`StreamedClaimMarker`, display-only). The whole text, less
        any Markdown code fence around it, is then parsed exactly as the
        forced ``emit_section`` call is, so the result continues into the
        claim checks unchanged.

        The call runs once, outside the retry loop, because a retry would
        repeat text the user has already seen; the route step's timeout bounds
        the wait between chunks. On any failure (connection, a gap between
        chunks that runs out, text that is not a section object) the user's
        draft is reset with an empty ``replace``, :attr:`stream_fallbacks` is
        counted, and the turn is run once more without streaming through
        :meth:`section_turn` with the forced tool, which keeps its own retries.

        Args:
            seed: Section seed record.
            transcript: Executed tool exchanges so far.

        Returns:
            A parsed claims emission plus token usage.
        """
        step = "synthesise_section_emit"
        # ``streamed=True`` appends the write-turn message whatever
        # ``force_emit`` says, so the ready and the forced write send the same.
        messages = build_section_messages(
            seed, transcript, force_emit=False, streamed=True
        )
        tools = section_request_tools(seed)
        # Deltas are addressed to the page's section index (key findings first
        # at 0), which the seed carries as ``display_index``; the loop's own
        # ``section_index`` is one lower for a body section when the report
        # has key findings (task 058; owner round 5).
        index = int(seed.get("display_index", seed["section_index"]))
        metadata = {
            "step": step,
            "attempt": 1,
            "prompt_version": self._section_prompt_version,
            "transcript_length": len(transcript),
        }

        def _stream(span: Any | None = None) -> UsageResult[SectionTurn]:
            if span is not None:
                span.update(input={"messages": messages}, metadata=metadata)
            completions: Any = self._client.chat.completions
            stream = completions.create(
                **_step_kwargs(step),
                messages=_cache_messages(step, messages),
                tools=tools,
                tool_choice="none",
                stream=True,
                stream_options={"include_usage": True},
            )
            decoder = JsonStringFieldDecoder("prose")
            markers = StreamedClaimMarker(index, seed, transcript)
            text = ""
            provider_usage: Any | None = None
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if choices:
                    delta = getattr(choices[0], "delta", None)
                    fragment = getattr(delta, "content", None)
                    if isinstance(fragment, str):
                        text += fragment
                        decoded = decoder.feed(fragment)
                        if decoded:
                            publish_section_delta(index, decoded)
                        markers.feed(fragment, decoded)
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    provider_usage = chunk_usage
            log_usage("synthesis.section_emit_stream.usage", provider_usage)
            section, malformed = _salvage_section(_strip_code_fence(text))
            turn: SectionTurn = {"tool_calls": [], "claims": section}
            if malformed:
                turn["malformed_claims"] = malformed
            usage = token_usage_from_provider(provider_usage)
            if span is not None:
                span.update(
                    usage_details=usage_details(usage),
                    output=_turn_output(turn),
                    model=route().model_for(step),
                    metadata={**metadata, **usage_metadata(usage)},
                )
            return turn, usage

        try:
            if self._langfuse_client is None:
                return _stream()
            with tracing._observation(
                self._langfuse_client,
                name="synthesise:section_emit",
                as_type="generation",
            ) as span:
                return _stream(span)
        except Exception as exc:
            log.warning(
                "synthesis.section_emit_stream.fallback",
                section_index=index,
                error=type(exc).__name__,
            )
            publish_section_delta(index, "", mode="replace")
            with self._lock:
                self.stream_fallbacks += 1
            return self.section_turn(seed, transcript, force_emit=True)

    def _repair_once(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[SectionRepairWire, Any, int]:
        """Send the repair request; return the repairs, usage and ignored-call count."""
        # Task 056 D10: the same five tools and parallel tool calls as the
        # section turns, so the repair reads the section's cached prefix;
        # emit_repairs is forced by name.
        completions: Any = self._client.chat.completions
        response = completions.create(
            **_step_kwargs("synthesise_section_turn"),
            messages=messages,
            tools=tools if tools is not None else section_request_tools({}),
            parallel_tool_calls=True,
            tool_choice=FORCE_EMIT_REPAIRS_TOOL_CHOICE,
        )
        log_usage("synthesis.repair.usage", response.usage)
        taken, ignored = _first_named_tool_call(
            response, name="emit_repairs", label="synthesis repair"
        )
        function = taken.function
        if function.name != "emit_repairs":
            raise RuntimeError("OpenAI synthesis repair response did not emit repairs.")
        arguments = function.arguments
        if not isinstance(arguments, str):
            arguments = "{}"
        # An unparseable envelope means the loop-free, unrepeatable repair
        # produced nothing — the raised MalformedEmissionError lands the
        # failing claims per the exhaustion rules (soft-flag / the counted
        # exclusions), never a whole-component failure.
        repairs = _salvage_repairs(arguments)
        return repairs, token_usage_from_provider(response.usage), len(ignored)

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionRepairWire]:
        """Repair failing claims through one emit-forced OpenAI call.

        Args:
            seed: Section seed record.
            transcript: Executed tool exchanges from the original section loop;
                not resent in the repair prompt.
            failing: Dependency-complete failing claim records with rationales.

        Returns:
            Replacement segments for the failing records plus token usage.

        Raises:
            RuntimeError: If the provider response does not emit repairs.
        """
        del transcript
        messages = build_section_repair_messages(seed, failing=failing)
        tools = section_request_tools(seed)

        def _update(span: Any, result: tuple[SectionRepairWire, Any, int]) -> None:
            repairs, usage, ignored = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=repairs.model_dump(),
                model=route().model_for("synthesise_section_turn"),
                metadata={
                    "prompt_version": SECTION_REPAIR_PROMPT_VERSION,
                    "failing_count": len(failing),
                    "extra_tool_calls_ignored": ignored,
                    **usage_metadata(usage),
                },
            )

        repairs, usage, _ignored = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:repair_claims",
            step="synthesise_section_turn",
            call=lambda: self._repair_once(messages, tools=tools),
            update=_update,
        )
        return repairs, usage

    def _write_key_findings_once(
        self,
        messages: list[dict[str, Any]],
    ) -> UsageResult[SectionProseWire]:
        completions: Any = self._client.chat.completions
        response = completions.create(
            **_step_kwargs("synthesise_write_key_findings"),
            messages=_cache_messages("synthesise_write_key_findings", messages),
            tools=[EMIT_SECTION_TOOL_SCHEMA],
            tool_choice={"type": "function", "function": {"name": "emit_section"}},
        )
        log_usage("synthesis.key_findings.usage", response.usage)
        function = require_single_tool_call(
            response, label="synthesis key findings"
        ).function
        if function.name != "emit_section":
            raise RuntimeError(
                "OpenAI synthesis key-findings response did not emit a section."
            )
        arguments = function.arguments
        if not isinstance(arguments, str):
            arguments = "{}"
        try:
            # Reuse the section salvage path (per-claim salvage). A malformed
            # emission with no recoverable prose is treated as the absence path
            # (empty emission), never a whole-component failure — the block is
            # conditional-required, never forced.
            section, _malformed = _salvage_section(arguments)
        except MalformedEmissionError:
            section = SectionProseWire(prose="", claims=[])
        return section, token_usage_from_provider(response.usage)

    def write_key_findings(
        self, seed: dict[str, Any]
    ) -> UsageResult[SectionProseWire]:
        """Emit the key-findings block through one emit-forced OpenAI call.

        Args:
            seed: The key-findings seed (intent + surviving claims ledger).

        Returns:
            Raw structurally parsed prose + claims plus token usage.

        Raises:
            RuntimeError: If the provider response does not emit a section.
        """
        messages = build_key_findings_messages(seed)

        def _update(span: Any, result: UsageResult[SectionProseWire]) -> None:
            section, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=section.model_dump(),
                model=route().model_for("synthesise_write_key_findings"),
                metadata={
                    "prompt_version": KEY_FINDINGS_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        section, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:write_key_findings",
            step="synthesise_write_key_findings",
            call=lambda: self._write_key_findings_once(messages),
            update=_update,
        )
        return section, usage

    def _write_case_studies_once(
        self,
        messages: list[dict[str, Any]],
    ) -> UsageResult[CaseStudyWire]:
        completions: Any = self._client.chat.completions
        response = completions.parse(
            **_step_kwargs("synthesise_write_case_studies"),
            messages=_cache_messages("synthesise_write_case_studies", messages),
            response_format=CaseStudyWire,
        )
        log_usage("synthesis.case_studies.usage", response.usage)
        parsed = require_parsed(response, label="synthesis case studies")
        return parsed, token_usage_from_provider(response.usage)

    def write_case_studies(
        self, seed: dict[str, Any]
    ) -> UsageResult[CaseStudyWire]:
        """Emit the case-studies cards through one structured OpenAI call.

        Args:
            seed: The case-studies seed.

        Returns:
            Raw structurally parsed cards plus token usage.
        """
        messages = build_case_studies_messages(seed)

        def _update(span: Any, result: UsageResult[CaseStudyWire]) -> None:
            wire, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=wire.model_dump(),
                model=CASE_STUDIES_MODEL,
                metadata={
                    "prompt_version": CASE_STUDIES_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        wire, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:write_case_studies",
            step="synthesise_write_case_studies",
            call=lambda: self._write_case_studies_once(messages),
            update=_update,
        )
        return wire, usage

    def write_case_studies_stream(
        self, seed: dict[str, Any], *, index: int
    ) -> UsageResult[CaseStudyWire]:
        """Write the case-study cards as one streamed reply (task 058, round 7).

        The request is the one :meth:`write_case_studies` sends (the same
        messages and the same structured-output schema), streamed. As each
        card object in the reply's ``cards`` array closes, its title and text
        are sent to the page through :func:`publish_section_card`
        (display-only: a card that does not read as one is skipped). The
        whole reply is then parsed into :class:`CaseStudyWire` exactly as the
        structured call is, so the result goes on to the card checks
        unchanged.

        The call runs once, outside the retry loop, because a retry would
        repeat cards the user has already seen. On any failure the page's
        cards for the slot are cleared with an empty ``replace`` delta,
        :attr:`stream_fallbacks` is counted, and :meth:`write_case_studies`
        runs once more without streaming (with its own retries).

        Args:
            seed: The case-studies seed.
            index: The page's index for the case-studies slot.

        Returns:
            Raw structurally parsed cards plus token usage.
        """
        step = "synthesise_write_case_studies"
        messages = build_case_studies_messages(seed)
        metadata = {"step": step, "attempt": 1, "prompt_version": CASE_STUDIES_PROMPT_VERSION}

        def _stream(span: Any | None = None) -> UsageResult[CaseStudyWire]:
            if span is not None:
                span.update(input={"messages": messages}, metadata=metadata)
            completions: Any = self._client.chat.completions
            stream = completions.create(
                **_step_kwargs(step),
                messages=_cache_messages(step, messages),
                # The schema ``parse`` sends for the same wire.
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "schema": to_strict_json_schema(CaseStudyWire),
                        "name": CaseStudyWire.__name__,
                        "strict": True,
                    },
                },
                stream=True,
                stream_options={"include_usage": True},
            )
            cards = StreamedCardPublisher(index)
            text = ""
            provider_usage: Any | None = None
            for chunk in stream:
                choices = getattr(chunk, "choices", None)
                if choices:
                    delta = getattr(choices[0], "delta", None)
                    fragment = getattr(delta, "content", None)
                    if isinstance(fragment, str):
                        text += fragment
                        cards.feed(fragment)
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    provider_usage = chunk_usage
            log_usage("synthesis.case_studies.usage", provider_usage)
            wire = CaseStudyWire.model_validate_json(_strip_code_fence(text))
            usage = token_usage_from_provider(provider_usage)
            if span is not None:
                span.update(
                    usage_details=usage_details(usage),
                    output=wire.model_dump(),
                    model=CASE_STUDIES_MODEL,
                    metadata={**metadata, **usage_metadata(usage)},
                )
            return wire, usage

        try:
            if self._langfuse_client is None:
                return _stream()
            with tracing._observation(
                self._langfuse_client,
                name="synthesise:write_case_studies",
                as_type="generation",
            ) as span:
                return _stream(span)
        except Exception as exc:
            log.warning(
                "synthesis.case_studies_stream.fallback",
                section_index=index,
                error=type(exc).__name__,
            )
            publish_section_delta(index, "", mode="replace")
            with self._lock:
                self.stream_fallbacks += 1
            return self.write_case_studies(seed)

    def write_source_note(
        self, seed: dict[str, Any]
    ) -> UsageResult[NoteWire]:
        """Emit a grounded one-sentence note for one cited source.

        Args:
            seed: Source note seed.

        Returns:
            Structurally parsed note plus token usage.
        """
        client = resolve_openai_client(None, backend_name="MRSNoteWriter")
        messages = [
            {"role": "system", "content": MRS_NOTE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": MRS_NOTE_USER_TEMPLATE.format(
                    seed_json=json.dumps(seed, ensure_ascii=False, sort_keys=True)
                ),
            },
        ]

        def _call() -> UsageResult[NoteWire]:
            completions: Any = client.chat.completions
            response = completions.parse(
                **_step_kwargs("synthesise_write_source_note"),
                messages=_cache_messages("synthesise_write_source_note", messages),
                response_format=NoteWire,
            )
            log_usage("synthesis.mrs_note.usage", response.usage)
            parsed = require_parsed(response, label="MRS note")
            return parsed, token_usage_from_provider(response.usage)

        def _update(span: Any, result: UsageResult[NoteWire]) -> None:
            wire, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=wire.model_dump(),
                model=MRS_NOTE_MODEL,
                metadata={
                    "prompt_version": MOST_RELEVANT_NOTE_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        wire, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:write_source_note",
            step="synthesise_write_source_note",
            call=_call,
            update=_update,
        )
        return wire, usage

    def write_full_report_intro(
        self, seed: dict[str, Any]
    ) -> UsageResult[IntroWire]:
        """Emit a short introduction to the full-report body sections.

        Args:
            seed: Report intent plus ordered body section titles and briefs.

        Returns:
            Structurally parsed intro plus token usage.
        """
        client = resolve_openai_client(None, backend_name="FullReportIntroWriter")
        messages = [
            {"role": "system", "content": FULL_REPORT_INTRO_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": FULL_REPORT_INTRO_USER_TEMPLATE.format(
                    seed_json=json.dumps(seed, ensure_ascii=False, sort_keys=True)
                ),
            },
        ]

        def _call() -> UsageResult[IntroWire]:
            completions: Any = client.chat.completions
            response = completions.parse(
                **_step_kwargs("synthesise_write_intro"),
                messages=_cache_messages("synthesise_write_intro", messages),
                response_format=IntroWire,
            )
            log_usage("synthesis.full_report_intro.usage", response.usage)
            parsed = require_parsed(response, label="full report intro")
            return parsed, token_usage_from_provider(response.usage)

        def _update(span: Any, result: UsageResult[IntroWire]) -> None:
            wire, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=wire.model_dump(),
                model=FULL_REPORT_INTRO_MODEL,
                metadata={
                    "prompt_version": FULL_REPORT_INTRO_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        wire, usage = tracing.traced_attempts(
            self._langfuse_client,
            name="synthesise:write_intro",
            step="synthesise_write_intro",
            call=_call,
            update=_update,
        )
        return wire, usage


class StubSynthesisBackend:
    """Deterministic zero-egress synthesis backend for tests and local runs."""

    mode = "stub"

    def __init__(
        self,
        *,
        script: list[list[SectionTurn]] | None = None,
        proposal: SectionProposalWire | None = None,
        repair: SectionRepairWire | None = None,
        fail: bool = False,
        summary_fail: bool = False,
        summary_judgements: list[SummaryJudgeWire] | None = None,
    ) -> None:
        """Create a stub synthesis backend.

        Args:
            script: Optional stateless per-section turn script.
            proposal: Optional fixed section proposal.
            repair: Optional fixed repair response.
            fail: When true, every method raises the failure sentinel.
            summary_fail: When true, summary-provider methods raise without
                affecting ordinary synthesis methods.
            summary_judgements: Optional verdict script consumed in order.
        """
        self._script = script
        self._proposal = proposal
        self._repair = repair
        self._fail = fail
        self._summary_fail = summary_fail
        self._summary_judgements = list(summary_judgements or [])
        self.proposal_inputs: list[dict[str, Any]] = []
        self.summary_seeds: list[dict[str, Any]] = []
        self.summary_judge_inputs: list[dict[str, Any]] = []

    def _raise_if_failed(self) -> None:
        if self._fail:
            raise RuntimeError("Stub synthesis failure sentinel.")

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        """Return a fixed or deterministic two-section proposal.

        Args:
            intent: Evidence-scope intent.
            substrate: Available substrate summaries.
            rejection: Ignored by the deterministic stub.

        Returns:
            The configured proposal, or the default two-section proposal, plus
            no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        self.proposal_inputs.append(
            {
                "intent": intent,
                "substrate": substrate,
                "rejection": rejection,
                "section_budget": section_budget,
            }
        )
        del rejection, section_budget
        if self._proposal is not None:
            return self._proposal, None

        bounded_intent = _strip_control_chars(intent[:80])
        group_ids = _group_ids_from_substrate(substrate)
        title_prefix = "Evidence on: "
        intent_for_title = bounded_intent[
            : max(0, SECTION_TITLE_PROPOSAL_MAX - len(title_prefix))
        ].rstrip()
        return (
            SectionProposalWire(
                sections=[
                    SectionWire(
                        title=f"{title_prefix}{intent_for_title}",
                        focus=f"What the assembled evidence says about: {bounded_intent}",
                        group_ids=group_ids,
                    ),
                    SectionWire(
                        title="Coverage and gaps in the assembled evidence",
                        focus="The corpus's shape, spread and absences.",
                    ),
                ]
            ),
            None,
        )

    def write_block_summary(self, seed: dict[str, Any]) -> UsageResult[SummaryWire]:
        """Return a deterministic first-sentence navigation summary.

        Args:
            seed: Persisted block detail.

        Returns:
            A summary wire plus no token usage.

        Raises:
            RuntimeError: If the summary failure sentinel is enabled.
        """
        if self._summary_fail:
            raise RuntimeError("Stub summary failure sentinel.")
        self.summary_seeds.append(seed)
        prose = str(seed.get("prose", "")).strip()
        sentence = prose.split(".", 1)[0].strip()
        summary = sentence + "." if sentence else "No summary available."
        return SummaryWire(summary=summary[:200]), None

    def judge_summary(
        self, *, summary: str, detail: dict[str, Any]
    ) -> UsageResult[SummaryJudgeWire]:
        """Return the next scripted or default passing summary verdict.

        Args:
            summary: Candidate summary.
            detail: Persisted raw detail.

        Returns:
            A flat verdict wire plus no token usage.

        Raises:
            RuntimeError: If the summary failure sentinel is enabled.
        """
        if self._summary_fail:
            raise RuntimeError("Stub summary failure sentinel.")
        self.summary_judge_inputs.append({"summary": summary, "detail": detail})
        if self._summary_judgements:
            return self._summary_judgements.pop(0), None
        return SummaryJudgeWire(verdict="pass", reason="deterministic stub"), None

    def _scripted_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> SectionTurn | None:
        if self._script is None:
            return None
        section_index = seed.get("section_index", 0)
        if not isinstance(section_index, int):
            section_index = 0
        if section_index >= len(self._script) or section_index < 0:
            return None
        section_script = self._script[section_index]
        turn_index = len(transcript)
        if turn_index >= len(section_script):
            return None
        scripted = section_script[turn_index]
        if force_emit and scripted["claims"] is None and scripted["tool_calls"]:
            return None
        return scripted

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        """Return the next scripted turn, default tool call, or deterministic claims.

        Args:
            seed: Section seed record.
            transcript: Executed tool exchanges so far.
            force_emit: Whether this is the final forced-emission turn.

        Returns:
            One tool call request or a deterministic claims emission, plus no
            token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        scripted = self._scripted_turn(seed, transcript, force_emit=force_emit)
        if scripted is not None:
            return scripted, None

        available_tools = [
            tool
            for tool in ("search_chunks", "query_findings", "lookup")
            if tool in seed.get("available_tools", [])
        ]
        if not force_emit and len(transcript) < len(available_tools):
            tool_name = available_tools[len(transcript)]
            if tool_name == "search_chunks":
                arguments = {"query": _section_title(seed)}
            elif tool_name == "query_findings":
                arguments = {}
            elif "characterisation" in seed.get("substrate", {}):
                arguments = {"kind": "characterisation_summary"}
            else:
                arguments = {"kind": "coverage_records"}
            return (
                {"tool_calls": [{"tool": tool_name, "arguments": arguments}], "claims": None},
                None,
            )

        return {"tool_calls": [], "claims": self._emit_section(seed, transcript)}, None

    def _emit_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
    ) -> SectionProseWire:
        available_claim_types = set(seed.get("available_claim_types", []))
        claims: list[ClaimWire] = []

        chunks = _transcript_chunks(transcript)
        if "chunk" in available_claim_types and chunks:
            # Prefer a citable (appraised) chunk — the prompt's own rule.
            chunk = next(
                (record for record in chunks if record.get("appraised")),
                chunks[0],
            )
            chunk_id = _record_id(chunk, "chunk_record_id", "id")
            content = chunk.get("content")
            if chunk_id is not None and isinstance(content, str):
                quote = content[:120]
                intent_or_focus = f"{seed.get('intent', '')} {_section_focus(seed)}"
                if "stubfabricate" in intent_or_focus:
                    quote = "This quote is fabricated entirely and appears nowhere."
                claims.append(
                    ClaimWire(
                        claim_type="chunk",
                        text="The corpus states this directly (stub).",
                        citations=[
                            ChunkCitationWire(chunk_record_id=chunk_id, quote=quote)
                        ],
                    )
                )

        findings = _transcript_findings(transcript)
        if "finding" in available_claim_types and findings:
            finding_ids = [
                finding_id
                for finding in findings[:2]
                if (finding_id := _record_id(finding, "finding_id", "id")) is not None
            ]
            if finding_ids:
                claims.append(
                    ClaimWire(
                        claim_type="finding",
                        text="Extracted findings report on this (stub).",
                        cited_finding_ids=finding_ids,
                    )
                )

        computed_spread = seed.get("computed_spread")
        if "pattern" in available_claim_types and isinstance(computed_spread, dict):
            group_ids = _section_group_ids(seed)
            claims.append(
                ClaimWire(
                    claim_type="pattern",
                    text="The extracted direction spread is computed directly (stub).",
                    pattern=PatternPayloadWire(
                        kind="direction_spread",
                        computed_from=(
                            "group_direction_spread"
                            if group_ids
                            else "extraction_direction_spread"
                        ),
                        group_id=group_ids[0] if group_ids else None,
                        stated={
                            str(direction): int(count)
                            for direction, count in computed_spread.items()
                        },
                        base="extracted",
                    ),
                )
            )

        theme_reference = _first_theme_reference(seed)
        if "theme" in available_claim_types and theme_reference is not None:
            source, referenced_id = theme_reference
            claims.append(
                ClaimWire(
                    claim_type="theme",
                    text="The substrate clustering identifies this theme (stub).",
                    theme=ThemePayloadWire(
                        source=source,
                        referenced_ids=[referenced_id],
                        base="screened",
                    ),
                )
            )

        if "gap" in available_claim_types:
            claims.append(
                ClaimWire(
                    claim_type="gap",
                    text="Evidence on adjacent questions is thin here (stub inference).",
                    gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
                )
            )

        if "reasoning" in available_claim_types:
            claims.append(
                ClaimWire(
                    claim_type="reasoning",
                    text="Background context, labelled as reasoning (stub).",
                )
            )

        return SectionProseWire(prose=_stub_prose([claim.text for claim in claims]), claims=claims)

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionRepairWire]:
        """Return fixed repairs or deterministic reworded replacement segments.

        Args:
            seed: Section seed record.
            transcript: Executed tool exchanges from the original section loop.
                Used only as a compatibility fallback when tests provide
                legacy failing records without dependency chunks.
            failing: Dependency-complete failing claim records with rationales.

        Returns:
            The configured repairs, or deterministic reworded replacement
            segments (each ``replacement_segment`` carries its claim's text as
            an exact substring, per ADR 0015 §4), plus no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        if self._repair is not None:
            return self._repair, None

        content_by_id = _repair_dependency_chunk_content_by_id(failing)
        if not content_by_id:
            content_by_id = _chunk_content_by_id(transcript)
        repairs: list[RepairItemWire] = []
        claim_fields = set(ClaimWire.model_fields)
        for record in failing:
            claim_id = str(record.get("claim_id", len(repairs)))
            raw_claim_value = record.get("claim")
            raw_claim = raw_claim_value if isinstance(raw_claim_value, dict) else record
            claim_data = {key: value for key, value in raw_claim.items() if key in claim_fields}
            claim = ClaimWire.model_validate(claim_data)
            updated = claim.model_dump()
            updated["text"] = f"Reworded down: {claim.text}"
            if claim.claim_type == "chunk":
                updated_citations: list[dict[str, str]] = []
                for citation in claim.citations:
                    quote = citation.quote
                    content = content_by_id.get(citation.chunk_record_id)
                    fabricated = "fabricated" in quote.casefold()
                    repairable = "stubrepairable" in str(seed.get("intent", ""))
                    if content is not None and (not fabricated or repairable):
                        quote = content[:60]
                    updated_citations.append({
                        "chunk_record_id": citation.chunk_record_id,
                        "quote": quote,
                    })
                updated["citations"] = updated_citations
            repaired_claim = ClaimWire.model_validate(updated)
            # The replacement segment carries the reworded claim text verbatim
            # (an exact substring) so the code-side span binder locates it.
            repairs.append(
                RepairItemWire(
                    claim_id=claim_id,
                    replacement_segment=repaired_claim.text,
                    claim=repaired_claim,
                )
            )
        return SectionRepairWire(repairs=repairs), None

    def write_key_findings(
        self, seed: dict[str, Any]
    ) -> UsageResult[SectionProseWire]:
        """Return a deterministic key-findings emission over the seed ledger.

        Emits a small prose plus 1–2 finding/chunk claims re-citing ledger ids
        when the seed ledger carries citable claims. Sentinel: an intent
        containing ``"stubnoheadline"`` (or a ledger with no citable claims)
        yields the empty emission — the explicit absence path (ADR 0015 §8).

        Args:
            seed: The key-findings seed (intent + surviving claims ledger +
                available claim types).

        Returns:
            The deterministic prose + claims, plus no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        intent = str(seed.get("intent", ""))
        available = set(seed.get("available_claim_types", []))
        finding_ids: list[str] = []
        chunk_citations: list[tuple[str, str]] = []
        ledger = seed.get("ledger", [])
        if isinstance(ledger, list):
            for entry in ledger:
                if not isinstance(entry, dict):
                    continue
                for claim in entry.get("claims", []):
                    if not isinstance(claim, dict):
                        continue
                    for fid in claim.get("cited_finding_ids", []) or []:
                        if isinstance(fid, str):
                            finding_ids.append(fid)
                    for citation in claim.get("chunk_citations", []) or []:
                        if not isinstance(citation, dict):
                            continue
                        cid = citation.get("chunk_record_id")
                        quote = citation.get("quote")
                        if isinstance(cid, str) and isinstance(quote, str):
                            chunk_citations.append((cid, quote))

        if "stubnoheadline" in intent or (not finding_ids and not chunk_citations):
            return SectionProseWire(prose="", claims=[]), None

        claims: list[ClaimWire] = []
        if "chunk" in available and chunk_citations:
            cid, quote = chunk_citations[0]
            claims.append(
                ClaimWire(
                    claim_type="chunk",
                    text="Headline: the corpus states this directly (stub).",
                    citations=[ChunkCitationWire(chunk_record_id=cid, quote=quote)],
                )
            )
        if "finding" in available and finding_ids:
            claims.append(
                ClaimWire(
                    claim_type="finding",
                    text="Headline: extracted findings report on this (stub).",
                    cited_finding_ids=finding_ids[:2],
                )
            )
        if not claims:
            return SectionProseWire(prose="", claims=[]), None
        return (
            SectionProseWire(
                prose=_stub_prose([claim.text for claim in claims]), claims=claims
            ),
            None,
        )

    def write_case_studies(
        self, seed: dict[str, Any]
    ) -> UsageResult[CaseStudyWire]:
        """Return deterministic case-study cards from the seed ledger.

        Sentinel: an intent containing ``"stubnocasestudies"`` yields an
        empty card list. Otherwise emits two cards with a finding claim each.

        Args:
            seed: The case-studies seed.

        Returns:
            Deterministic cards plus no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        intent = str(seed.get("intent", ""))
        if "stubnocasestudies" in intent:
            return CaseStudyWire(cards=[]), None

        ledger = seed.get("ledger", [])
        finding_ids: list[str] = []
        if isinstance(ledger, list):
            for entry in ledger:
                if not isinstance(entry, dict):
                    continue
                for claim in entry.get("claims", []):
                    if not isinstance(claim, dict):
                        continue
                    for fid in claim.get("cited_finding_ids", []) or []:
                        if isinstance(fid, str):
                            finding_ids.append(fid)
        if len(finding_ids) < 2:
            return CaseStudyWire(cards=[]), None

        cards = [
            CaseStudyCardWire(
                title="Finland — Universal school meals",
                prose="Finland introduced universal school meals in 1948. "
                "Uptake is near-universal (stub).",
                claims=[
                    CaseStudyClaimWire(
                        claim_type="finding",
                        text="Uptake is near-universal (stub).",
                        cited_finding_ids=[finding_ids[0]],
                    ),
                ],
                result_ordinal=0,
            ),
            CaseStudyCardWire(
                title="Sweden — Free school lunches",
                prose="Sweden provides free school lunches to all pupils. "
                "Evaluations report nutritional gains (stub).",
                claims=[
                    CaseStudyClaimWire(
                        claim_type="finding",
                        text="Evaluations report nutritional gains (stub).",
                        cited_finding_ids=[finding_ids[1]],
                    ),
                ],
                result_ordinal=0,
            ),
        ]
        return CaseStudyWire(cards=cards), None

    def write_source_note(
        self, seed: dict[str, Any]
    ) -> UsageResult[NoteWire]:
        """Return a deterministic one-sentence note.

        Args:
            seed: Source note seed.

        Returns:
            Deterministic note plus no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        title = seed.get("title", "this source")
        return NoteWire(note=f"Cited for evidence on the intervention ({title})."), None

    def write_full_report_intro(
        self, seed: dict[str, Any]
    ) -> UsageResult[IntroWire]:
        """Return a deterministic full-report intro.

        Args:
            seed: Report intro seed.

        Returns:
            Deterministic intro plus no token usage.

        Raises:
            RuntimeError: If the failure sentinel is enabled.
        """
        self._raise_if_failed()
        del seed
        return IntroWire(
            intro=(
                "The sections below examine the main themes in the evidence, "
                "then draw together the overall conclusions."
            ),
        ), None
