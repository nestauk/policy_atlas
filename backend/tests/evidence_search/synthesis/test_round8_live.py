"""Round 8 of task 058: the key findings, the introduction and the source notes, live.

B1: completed sections' citations carry the saved ids and quote (asserted with
the round-7 whole-run test in ``test_live_citations_and_cards.py``).
B2: the key findings stream into their slot, with claim marks; the parse is the
forced call's. B3: the introduction streams into its own slot. B4: each source
note is named on the activity line and sent to the page as it is written.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.api.read_models.repository import artefact_out
from policy_atlas.core import liveness
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.synthesis import synthesis_backend as sb
from policy_atlas.evidence_search.synthesis.section_prompt import (
    IntroWire,
    SectionProseWire,
    build_key_findings_messages,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import _salvage_section
from policy_atlas.evidence_search.synthesis.synthesis_tools import UNTITLED_SOURCE
from tests.evidence_search.synthesis.test_live_citations_and_cards import (
    _backend,
    _CaseStudiesBackend,
    _completed,
    _run,
)

# --- B2, B3, B4 through a whole synthesis run -----------------------------------------


class _LiveBackend(_CaseStudiesBackend):
    """The round-7 test writer, with the streamed key findings and introduction.

    Each streamed variant records what it was given and returns what the
    structured call returns.
    """

    def __init__(self) -> None:
        super().__init__()
        self.kf_stream: list[tuple[int, Any]] = []
        self.intro_stream: list[int] = []

    def write_key_findings_stream(
        self, seed: dict[str, Any], *, index: int, sources: Any = None
    ) -> UsageResult[SectionProseWire]:
        self.kf_stream.append((index, sources))
        return self.write_key_findings(seed)

    def write_full_report_intro_stream(
        self, seed: dict[str, Any], *, index: int
    ) -> UsageResult[IntroWire]:
        self.intro_stream.append(index)
        return self.write_full_report_intro(seed)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {"progress": [], "notes": []}
    real_progress = liveness.publish_progress

    def _progress(**kwargs: Any) -> None:
        out["progress"].append(kwargs)
        real_progress(**kwargs)

    monkeypatch.setattr(liveness, "publish_progress", _progress)
    monkeypatch.setattr(
        liveness,
        "publish_source_note",
        lambda source_id, title, note: out["notes"].append((source_id, title, note)),
    )
    return out


def test_key_findings_intro_and_notes_are_live(
    conn: Connection, recorded: dict[str, list[Any]]
) -> None:
    backend = _LiveBackend()
    task_id, emitter = _run(conn, backend)
    skeleton = next(p for t, p in emitter.events if t == "artefact.skeleton")
    intro_index = skeleton["sections"][-1]["index"]
    assert skeleton["sections"][-1]["role"] == "intro"

    # B2: the key findings stream into slot 0, with the sections' sources
    # for the claim marks.
    [(kf_index, sources)] = backend.kf_stream
    assert kf_index == 0
    by_chunk, by_finding = sources
    assert by_chunk or by_finding
    assert {
        "activity": "Writing the key findings",
        "section": "Key findings",
    } in recorded["progress"]
    assert {"activity": "Checking claims", "section": "Key findings"} in recorded["progress"]

    # B3: the introduction streams into its own slot, which starts and then
    # completes with the introduction the report keeps, without citations.
    assert backend.intro_stream == [intro_index]
    lifecycle = [(t, p["index"]) for t, p in emitter.events if t != "artefact.skeleton"]
    assert lifecycle[-2:] == [
        ("artefact.section_started", intro_index),
        ("artefact.section_completed", intro_index),
    ]
    report = artefact_out(conn, task_id)
    assert report is not None and report.full_report_intro
    intro = _completed(emitter)["Full report"]
    assert intro["prose"] == report.full_report_intro
    assert intro["citations"] == []
    # Round 9: the slot keeps its "Full report" title; the line names the
    # introduction, so the card and the strip read "Writing · Introduction".
    assert {
        "activity": "Writing the introduction",
        "section": "Introduction",
    } in recorded["progress"]

    # B4: each kept note is sent as it is written, in the report's order,
    # titled as the report's references title the source, and its line names
    # the source.
    saved = [(note.source_id, note.note) for note in report.most_relevant_notes]
    assert saved
    assert [(source_id, note) for source_id, _title, note in recorded["notes"]] == saved
    titles = {
        citation["source_id"]: citation["title"]
        for payload in _completed(emitter).values()
        for citation in payload["citations"]
    }
    for source_id, title, _note in recorded["notes"]:
        assert title == titles[source_id]
    named = [
        line["activity"]
        for line in recorded["progress"]
        if line["activity"].startswith("Writing a source note · ")
    ]
    assert len(named) == len(saved)


def test_a_backend_without_streaming_still_closes_the_intro_slot(
    conn: Connection, recorded: dict[str, list[Any]]
) -> None:
    backend = _LiveBackend()
    cast("Any", backend).write_key_findings_stream = None
    cast("Any", backend).write_full_report_intro_stream = None
    _task_id, emitter = _run(conn, backend)
    assert backend.kf_stream == [] and backend.intro_stream == []
    assert _completed(emitter)["Full report"]["prose"]


# --- B2: the streamed key-findings call -----------------------------------------------

_KF = {
    "prose": (
        '- Uptake rose with "universal" provision: in eleven of fifteen trials.\n'
        "- Costs fell \\ modestly: two councils reported savings.\n"
    ),
    "claims": [
        {
            "claim_type": "chunk",
            "text": 'Uptake rose with "universal" provision: in eleven of fifteen trials.',
            "citations": [{"chunk_record_id": "c1", "quote": "eleven of fifteen"}],
        },
        {
            "claim_type": "finding",
            "text": "Costs fell \\ modestly: two councils reported savings.",
            "cited_finding_ids": ["f1"],
        },
    ],
}
_KF_SEED: dict[str, Any] = {"intent": "What helps?", "ledger": [], "display_index": 0}
_SOURCES: tuple[dict[str, tuple[str, str | None]], dict[str, tuple[str, str | None]]] = (
    {"c1": ("tss-1", "Breakfast clubs")},
    {"f1": ("tss-2", None)},
)


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {"deltas": [], "claims": []}
    monkeypatch.setattr(
        sb,
        "publish_section_delta",
        lambda index, text, mode="append": out["deltas"].append((index, text, mode)),
    )
    monkeypatch.setattr(
        sb,
        "publish_section_claim",
        lambda index, start, end, sources: out["claims"].append((index, start, end, sources)),
    )
    return out


@pytest.mark.parametrize("size", [1, 4, 23, 100_000])
def test_key_findings_stream_into_the_slot_and_parse_as_the_forced_call(
    size: int, live: dict[str, list[Any]]
) -> None:
    text = json.dumps(_KF)
    backend, completions = _backend(text, size)
    section, _usage = backend.write_key_findings_stream(_KF_SEED, index=0, sources=_SOURCES)

    # The parse is the forced call's parse of the same arguments.
    assert section == _salvage_section(text)[0]
    assert backend.stream_fallbacks == 0
    # The "- " list streams as it is, on slot 0.
    assert {index for index, _t, _m in live["deltas"]} == {0}
    assert all(mode == "append" for _i, _t, mode in live["deltas"])
    assert "".join(t for _i, t, _m in live["deltas"]) == _KF["prose"]
    # Each claim is marked on the draft with its source's name.
    prose = _KF["prose"]
    first, second = (claim["text"] for claim in cast("list[dict[str, Any]]", _KF["claims"]))
    assert live["claims"] == [
        (0, prose.index(first), prose.index(first) + len(first), [("tss-1", "Breakfast clubs")]),
        (0, prose.index(second), prose.index(second) + len(second), [("tss-2", UNTITLED_SOURCE)]),
    ]
    # The same messages as the forced call, as a strict structured reply; no tools.
    [call] = completions.calls
    assert call["stream"] is True
    assert "tools" not in call and "tool_choice" not in call
    schema = call["response_format"]["json_schema"]
    assert call["response_format"]["type"] == "json_schema"
    assert schema["name"] == "emit_section" and schema["strict"] is True
    assert schema["schema"] == SectionProseWire.model_json_schema()
    assert call["messages"][-1]["content"] == build_key_findings_messages(_KF_SEED)[-1][
        "content"
    ]


def test_key_findings_stream_without_sources_marks_nothing(live: dict[str, list[Any]]) -> None:
    backend, _completions = _backend(json.dumps(_KF), 7)
    backend.write_key_findings_stream(_KF_SEED, index=0)
    assert live["claims"] == []
    assert live["deltas"]


def test_a_reply_that_is_not_a_section_resets_the_slot_and_falls_back_once(
    live: dict[str, list[Any]],
) -> None:
    text = '{"prose": "- A headline: stated.\\n", "claims": [{"claim_type"'
    backend, _completions = _backend(text, 5)
    fallback = SectionProseWire(prose="- Fallback.", claims=[])
    calls: list[dict[str, Any]] = []

    def _forced(seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
        calls.append(seed)
        return fallback, None

    cast("Any", backend).write_key_findings = _forced
    section, _usage = backend.write_key_findings_stream(_KF_SEED, index=0, sources=_SOURCES)
    # The reset, then the fallback's prose in one replace (task 058 review).
    assert live["deltas"][-2:] == [(0, "", "replace"), (0, "- Fallback.", "replace")]
    assert "".join(t for _i, t, m in live["deltas"] if m == "append") == "- A headline: stated.\n"
    assert calls == [_KF_SEED]
    assert section is fallback
    assert backend.stream_fallbacks == 1


# --- B3: the streamed introduction ----------------------------------------------------

_INTRO = {"intro": 'The report first weighs "what works", then asks \\ what it costs.'}
_INTRO_SEED: dict[str, Any] = {"intent": "What helps?", "sections": []}


@pytest.fixture
def intro_backend(monkeypatch: pytest.MonkeyPatch) -> Any:
    def make(text: str, size: int) -> tuple[Any, Any]:
        backend, completions = _backend(text, size)
        # The intro call resolves its own client; give it the stream too.
        monkeypatch.setattr(
            sb,
            "resolve_openai_client",
            lambda _key, *, backend_name: cast("Any", backend)._client,
        )
        return backend, completions

    return make


@pytest.mark.parametrize("size", [1, 6, 100_000])
def test_the_intro_streams_into_its_slot_and_parses_as_the_structured_call(
    size: int, live: dict[str, list[Any]], intro_backend: Any
) -> None:
    text = json.dumps(_INTRO)
    backend, completions = intro_backend(text, size)
    wire, _usage = backend.write_full_report_intro_stream(_INTRO_SEED, index=7)
    assert wire == IntroWire.model_validate_json(text)
    assert {index for index, _t, _m in live["deltas"]} == {7}
    assert "".join(t for _i, t, _m in live["deltas"]) == _INTRO["intro"]
    assert backend.stream_fallbacks == 0
    [call] = completions.calls
    assert call["stream"] is True
    assert call["response_format"]["json_schema"]["name"] == "IntroWire"
    assert call["response_format"]["json_schema"]["strict"] is True


def test_a_broken_intro_resets_the_slot_and_falls_back_once(
    live: dict[str, list[Any]], intro_backend: Any
) -> None:
    backend, _completions = intro_backend('{"intro": "The report fir', 4)
    fallback = IntroWire(intro="Fallback.")
    calls: list[dict[str, Any]] = []

    def _structured(seed: dict[str, Any]) -> UsageResult[IntroWire]:
        calls.append(seed)
        return fallback, None

    cast("Any", backend).write_full_report_intro = _structured
    wire, _usage = backend.write_full_report_intro_stream(_INTRO_SEED, index=7)
    assert live["deltas"][-2:] == [(7, "", "replace"), (7, "Fallback.", "replace")]
    assert calls == [_INTRO_SEED]
    assert wire is fallback
    assert backend.stream_fallbacks == 1
