"""Round 7 of task 058: citations on completion, case studies streamed.

Item A: every ``artefact.section_completed`` carries the section's checked
citations, numbered as the saved report's read model numbers its references.
Item B: the case studies get their own slot, and their cards are sent to the
page one by one as each closes in the streamed reply; the final parse is the
same as the structured call's.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.api.read_models.repository import artefact_out
from policy_atlas.core import liveness
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.synthesis import synthesis_backend as sb
from policy_atlas.evidence_search.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.evidence_search.synthesis.live_citations import (
    UNKNOWN_SOURCE,
    ReferenceNumbering,
)
from policy_atlas.evidence_search.synthesis.section_prompt import (
    CaseStudyCardWire,
    CaseStudyClaimWire,
    CaseStudyWire,
    ChunkCitationWire,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import (
    OpenAISynthesisBackend,
    StubSynthesisBackend,
)
from policy_atlas.evidence_search.synthesis.synthesise import (
    SynthesiseContext,
    synthesise_scope,
)
from tests.evidence_search.synthesis.test_synthesise_baseline import (
    _RecordingEmitter,
    _seed_baseline_corpus,
)
from tests.helpers import seed_scope, seed_task_and_run

# --- Item A and B through a whole synthesis run -------------------------------------


class _CaseStudiesBackend(StubSynthesisBackend):
    """The stub writer, plus case-study cards built from the cited chunks.

    Each card restates one section's cited chunk claim with the same quote, so
    the cards survive the checks and carry citations. The streamed variant
    sends each card to the page and returns what the structured call returns.
    """

    def __init__(self) -> None:
        super().__init__()
        self.stream_calls: list[int] = []
        self.published: list[tuple[int, str, str]] = []

    def write_case_studies(self, seed: dict[str, Any]) -> UsageResult[CaseStudyWire]:
        cards: list[CaseStudyCardWire] = []
        for position, section in enumerate(seed.get("ledger", [])):
            chunk_claims = [
                claim
                for claim in section.get("claims", [])
                if claim.get("claim_type") == "chunk" and claim.get("chunk_citations")
            ]
            if not chunk_claims:
                continue
            claim = chunk_claims[0]
            citation = claim["chunk_citations"][0]
            cards.append(
                CaseStudyCardWire(
                    title=f"Programme {position + 1}",
                    prose=f"A programme ran here. {claim['text']}",
                    claims=[
                        CaseStudyClaimWire(
                            claim_type="chunk",
                            text=claim["text"],
                            citations=[
                                ChunkCitationWire(
                                    chunk_record_id=citation["chunk_record_id"],
                                    quote=citation["quote"],
                                )
                            ],
                        )
                    ],
                    result_ordinal=0,
                )
            )
        return CaseStudyWire(cards=cards[:2]), None

    def write_case_studies_stream(
        self, seed: dict[str, Any], *, index: int
    ) -> UsageResult[CaseStudyWire]:
        self.stream_calls.append(index)
        wire, usage = self.write_case_studies(seed)
        for card in wire.cards:
            self.published.append((index, card.title, card.prose))
        return wire, usage


def _run(conn: Connection, backend: Any) -> tuple[uuid.UUID, _RecordingEmitter]:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    emitter = _RecordingEmitter()
    synthesise_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent="What works for the target group?",
            context={},
        ),
        synthesis_backend=backend,
        grounding_judge_backend=StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
        progress_emitter=emitter,
    )
    return task_id, emitter


def _completed(emitter: _RecordingEmitter) -> dict[str, dict[str, Any]]:
    return {
        payload["title"]: payload
        for event_type, payload in emitter.events
        if event_type == "artefact.section_completed"
    }


def test_completed_sections_carry_citations_numbered_as_the_saved_report(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress: list[dict[str, Any]] = []
    cleared: list[bool] = []
    real_progress = liveness.publish_progress
    real_clear = liveness.clear_section_draft

    def _progress(**kwargs: Any) -> None:
        progress.append(kwargs)
        real_progress(**kwargs)

    def _clear() -> None:
        cleared.append(True)
        real_clear()

    monkeypatch.setattr(liveness, "publish_progress", _progress)
    monkeypatch.setattr(liveness, "clear_section_draft", _clear)
    backend = _CaseStudiesBackend()
    task_id, emitter = _run(conn, backend)

    # The case studies have the slot after the body sections and stream into
    # it; the introduction's slot comes after (round 8); every slot names
    # its role.
    skeleton = next(p for t, p in emitter.events if t == "artefact.skeleton")
    slots = [(s["index"], s["title"], s["role"]) for s in skeleton["sections"]]
    last = len(slots) - 2
    assert slots[0] == (0, "Key findings", "key_findings")
    assert slots[-2] == (last, "Case studies", "case_studies")
    assert slots[-1] == (last + 1, "Full report", "intro")
    assert all(role == "body" for _i, _t, role in slots[1:-2])
    assert backend.stream_calls == [last]
    assert [index for index, _t, _p in backend.published] == [last, last]
    lifecycle = [(t, p["index"]) for t, p in emitter.events if t != "artefact.skeleton"]
    assert lifecycle[-4:-2] == [
        ("artefact.section_started", last),
        ("artefact.section_completed", last),
    ]
    assert {
        "activity": "Writing the case studies",
        "section": "Case studies",
    } in progress
    # The streamed cards are forgotten before the checked section lands.
    assert cleared

    # Every completed section's citations match the saved report's.
    report = artefact_out(conn, task_id)
    assert report is not None
    completed = _completed(emitter)
    assert completed["Case studies"]["prose"]
    seen_any = 0
    for section in report.sections:
        expected = [
            {
                "start": claim.span[0],
                "end": claim.span[1],
                "n": citation.n,
                "source_id": str(citation.source_id) if citation.source_id else None,
                "title": citation.source_title,
                # Round 8: the saved ids and quote, so the live page can ask
                # for the citation's context before the commit.
                "citation_id": str(citation.citation_id),
                "claim_id": str(claim.claim_id),
                "quote": citation.quote,
            }
            for block in section.blocks
            for claim in block.claims
            if claim.span is not None
            for citation in claim.citations
        ]
        live = completed[section.title]
        assert live["citations"] == expected, section.title
        # Round 13: the verdict rides on the claim, as the saved claim has it.
        expected_claims = [
            {
                "claim_id": str(claim.claim_id),
                "start": claim.span[0],
                "end": claim.span[1],
                "tier": claim.grounding_tier,
                "rationale": claim.grounding_rationale,
            }
            for block in section.blocks
            for claim in block.claims
            if claim.span is not None and claim.citations
        ]
        assert live["claims"] == expected_claims, section.title
        for entry in live["citations"]:
            assert live["prose"][entry["start"] : entry["end"]]
        seen_any += len(expected)
    assert seen_any >= 4
    # The numbers are the references' numbers, and every reference is used.
    numbers = {e["n"] for p in completed.values() for e in p["citations"]}
    assert numbers == {reference.n for reference in report.references}


def test_a_backend_without_streaming_writes_the_case_studies_as_before(
    conn: Connection,
) -> None:
    backend = _CaseStudiesBackend()
    cast("Any", backend).write_case_studies_stream = None
    _task_id, emitter = _run(conn, backend)
    assert backend.stream_calls == []
    assert _completed(emitter)["Case studies"]["prose"]


def test_absent_case_studies_close_their_slot_empty(conn: Connection) -> None:
    # The plain stub finds no programmes in this corpus.
    _task_id, emitter = _run(conn, StubSynthesisBackend())
    case_studies = _completed(emitter)["Case studies"]
    assert case_studies["prose"] == "" and case_studies["citations"] == []
    skeleton = next(p for t, p in emitter.events if t == "artefact.skeleton")
    assert case_studies["index"] == skeleton["sections"][-2]["index"]


def test_reference_numbering_skips_unknown_chunks(conn: Connection) -> None:
    numbering = ReferenceNumbering(conn, task_id=uuid.uuid4())
    claim = SimpleNamespace(
        span=(0, 4),
        verdict="tier_2",
        rationale="Matches.",
        citation_rows=[SimpleNamespace(chunk_id=str(uuid.uuid4()), quote="q")],
    )
    assert numbering.citations([claim]) == []
    # The claim's verdict stands whether or not its chunk is known (round 13).
    assert numbering.claim_verdicts([claim]) == [
        {"claim_id": None, "start": 0, "end": 4, "tier": "tier_2", "rationale": "Matches."}
    ]
    assert numbering.citations([]) == []
    assert UNKNOWN_SOURCE == "Unknown source"


# --- Item B: the streamed case-studies call --------------------------------------------


def _content_chunk(text: str) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None
    )


class _StreamCompletions:
    def __init__(self, text: str, size: int) -> None:
        self._chunks = [_content_chunk(text[at : at + size]) for at in range(0, len(text), size)]
        self._chunks.append(SimpleNamespace(choices=[], usage=None))
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Iterator[Any]:
        self.calls.append(kwargs)
        return iter(self._chunks)


def _backend(text: str, size: int) -> tuple[OpenAISynthesisBackend, _StreamCompletions]:
    backend = OpenAISynthesisBackend(api_key="sk-test-live")
    completions = _StreamCompletions(text, size)
    cast("Any", backend)._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return backend, completions


_CARDS = {
    "cards": [
        {
            "title": 'Leeds — "Breakfast" {every} [primary]',
            "prose": "Uptake rose. A \\ backslash and } brace.",
            "claims": [
                {
                    "claim_type": "chunk",
                    "text": "Uptake rose.",
                    "cited_finding_ids": [],
                    "citations": [{"chunk_record_id": "c1", "quote": "q } ]"}],
                }
            ],
            "result_ordinal": 0,
        },
        {
            "title": "Bristol — Walking buses",
            "prose": "More children walked.",
            "claims": [
                {
                    "claim_type": "reasoning",
                    "text": "More children walked.",
                    "cited_finding_ids": [],
                    "citations": [],
                }
            ],
            "result_ordinal": 0,
        },
    ]
}
_SEED: dict[str, Any] = {"intent": "What helps?", "ledger": [], "chunk_content_by_id": {}}


@pytest.fixture
def cards(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str, str]]:
    recorded: list[tuple[int, str, str]] = []
    monkeypatch.setattr(
        sb,
        "publish_section_card",
        lambda index, title, prose: recorded.append((index, title, prose)),
    )
    return recorded


@pytest.mark.parametrize("size", [1, 3, 17, 100_000])
def test_each_card_is_published_as_it_closes_and_the_parse_is_unchanged(
    size: int, cards: list[tuple[int, str, str]]
) -> None:
    text = json.dumps(_CARDS)
    backend, completions = _backend(text, size)
    wire, _usage = backend.write_case_studies_stream(_SEED, index=1)

    assert cards == [(1, card["title"], card["prose"]) for card in _CARDS["cards"]]
    assert wire == CaseStudyWire.model_validate_json(text)
    assert backend.stream_fallbacks == 0
    # The same request as the structured call, streamed.
    [call] = completions.calls
    assert call["stream"] is True
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["name"] == "CaseStudyWire"
    assert call["response_format"]["json_schema"]["strict"] is True


def test_a_card_without_a_title_or_text_is_not_published(
    cards: list[tuple[int, str, str]],
) -> None:
    payload = json.loads(json.dumps(_CARDS))
    payload["cards"][0]["title"] = "  "
    text = json.dumps(payload)
    backend, _completions = _backend(text, 9)
    wire, _usage = backend.write_case_studies_stream(_SEED, index=1)
    assert [title for _i, title, _p in cards] == ["Bristol — Walking buses"]
    # The parse is still the whole reply; the card checks decide what stays.
    assert len(wire.cards) == 2


def test_a_broken_reply_resets_the_slot_and_falls_back_once(
    cards: list[tuple[int, str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    deltas: list[tuple[int, str, str]] = []
    monkeypatch.setattr(
        sb,
        "publish_section_delta",
        lambda index, text, mode="append": deltas.append((index, text, mode)),
    )
    good = json.dumps(_CARDS["cards"][0])
    text = '{"cards": [' + good + ", {broken"
    backend, _completions = _backend(text, 5)
    fallback = CaseStudyWire.model_validate({"cards": _CARDS["cards"][1:]})
    calls: list[dict[str, Any]] = []

    def _structured(seed: dict[str, Any]) -> UsageResult[CaseStudyWire]:
        calls.append(seed)
        return fallback, None

    cast("Any", backend).write_case_studies = _structured
    wire, _usage = backend.write_case_studies_stream(_SEED, index=1)
    # The first card had already been shown; the reset clears it on the page,
    # then the fallback's cards are shown (task 058 review).
    assert [title for _i, title, _p in cards] == [
        _CARDS["cards"][0]["title"],
        _CARDS["cards"][1]["title"],
    ]
    assert deltas == [(1, "", "replace")]
    assert calls == [_SEED]
    assert wire is fallback
    assert backend.stream_fallbacks == 1


# --- The read model's fixed order (task 058, round 7) ----------------------------------


def test_the_read_model_walks_blocks_in_save_order_and_claims_by_span() -> None:
    from policy_atlas.api.read_models.repository import _annotation_order, _save_rank

    kf, cs, body_a, body_b, foot = (uuid.UUID(int=n) for n in range(1, 6))
    # The roll-up is page order: key findings, case studies, body, foot.
    specs: list[tuple[dict[str, Any], uuid.UUID]] = [
        ({"role": "key_findings"}, kf),
        ({"role": "case_studies"}, cs),
        ({"role": "standard"}, body_a),
        ({"role": "conclusions"}, body_b),
        ({"role": "sources"}, foot),
    ]
    ranks = _save_rank(specs)

    def row(block_id: uuid.UUID, start: int, end: int, n: int) -> Any:
        return SimpleNamespace(
            block_id=block_id,
            locator={"start": start, "end": end},
            annotation_id=uuid.UUID(int=100 + n),
        )

    rows = [
        row(cs, 0, 4, 1),
        row(kf, 0, 4, 2),
        row(body_b, 10, 12, 3),
        row(body_a, 30, 40, 4),
        row(body_a, 2, 8, 5),
        row(foot, 0, 1, 6),
    ]
    ordered = sorted(rows, key=lambda item: _annotation_order(item, ranks))
    assert [(item.block_id, item.locator["start"]) for item in ordered] == [
        (body_a, 2),
        (body_a, 30),
        (body_b, 10),
        (foot, 0),
        (kf, 0),
        (cs, 0),
    ]
    # Whatever order the database returns, the walk is the same.
    assert sorted(reversed(rows), key=lambda item: _annotation_order(item, ranks)) == ordered
