"""Baseline mode in synthesise (task 044 phase 4.2).

The baseline is the same synthesise machinery under a different output kind:
its required sections are supplied rather than proposed, the section proposer
runs only for at most two problem-specific extras, each section carries its own
turn cap, the three Evidence-search-only passes are off, and the Sources
section is rendered by code from the coverage record.

These tests are DB-backed (``conn``, rolled back per test) and use stub
backends, exactly as ``test_synthesise.py`` does.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import (
    artefact,
    block,
    source_snapshot,
    synthesis_result,
    task_source_snapshot,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.synthesis.baseline_prompt import (
    BASELINE_ARTEFACT_TITLE,
    BASELINE_DEPTH_LABEL,
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_SECTION_TURN_CAP,
    BASELINE_SECTIONS,
    SOURCES_NOT_SEARCHED_LINE,
    SOURCES_SECTION_TITLE,
    required_titles,
)
from policy_atlas.evidence_search.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.evidence_search.synthesis.synthesis_backend import (
    CaseStudyWire,
    ClaimWire,
    GapPayloadWire,
    IntroWire,
    NoteWire,
    SectionProposalWire,
    SectionProseWire,
    SectionTurn,
    SectionWire,
    StubSynthesisBackend,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    SECTION_TURN_CAP,
    ToolExchange,
)
from policy_atlas.evidence_search.synthesis.synthesise import (
    CONCLUSIONS_TITLE,
    SynthesiseContext,
    _rollup_flags,
    generation_budget_max,
    synthesise_scope,
)
from policy_atlas.runtime.progress import ProgressEmitter
from policy_atlas.runtime.scoping_plan import _baseline_section_directives
from tests.helpers import (
    seed_ingested_full_text,
    seed_scope,
    seed_task_and_run,
)
from tests.helpers import seed_select_doc as _seed_select_doc
from tests.synthesis_wire import ScriptedSynthesisBackend, prose_section

REQUIRED_TITLES = [section.title for section in BASELINE_SECTIONS]
CONTESTED = "What is contested"


def _baseline_context(**overrides: Any) -> dict[str, Any]:
    """The scoping chain's own compiled synthesise directive."""
    synthesis: dict[str, Any] = {
        "template": "baseline",
        "sections": _baseline_section_directives(),
        "section_budget": BASELINE_PROPOSED_SECTIONS_MAX,
    }
    synthesis.update(overrides)
    return {"synthesis": synthesis}


class _RecordingEmitter(ProgressEmitter):
    """A progress emitter that records events instead of writing them."""

    def __init__(self) -> None:
        super().__init__(cast("Any", None), task_id=uuid.uuid4(), run_id=uuid.uuid4())
        self.events: list[tuple[str, dict[str, Any]]] = []

    def _append(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


class _BaselineBackend(ScriptedSynthesisBackend):
    """Emits one reasoning claim per section and records every seed it saw.

    ``burn_turns`` makes each section spend its whole turn cap before emitting,
    so a test can read the per-section cap off the recorded turn counts.
    """

    def __init__(
        self,
        *,
        proposal: SectionProposalWire | None = None,
        repair_proposal: SectionProposalWire | None = None,
        burn_turns: bool = False,
    ) -> None:
        super().__init__(proposal=proposal or SectionProposalWire(sections=[]))
        self._repair_proposal = repair_proposal
        self._burn_turns = burn_turns
        self.proposal_calls: list[dict[str, Any]] = []
        self.seeds: list[dict[str, Any]] = []
        self.turns_by_section: dict[int, int] = {}
        self.key_findings_calls = 0
        self.case_study_calls = 0
        self.source_note_calls = 0
        self.intro_calls = 0

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        self.proposal_calls.append(
            {"rejection": rejection, "section_budget": section_budget}
        )
        if rejection is not None and self._repair_proposal is not None:
            return self._repair_proposal, None
        assert self._proposal is not None
        return self._proposal, None

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        index = int(seed.get("section_index", 0))
        if index not in self.turns_by_section:
            self.seeds.append(seed)
        self.turns_by_section[index] = self.turns_by_section.get(index, 0) + 1
        if self._burn_turns and not force_emit:
            # A rejected tool call still consumes its turn — enough to walk the
            # loop up to its cap without needing real substrate.
            return {
                "tool_calls": [{"tool": "no_such_tool", "arguments": {}}],
                "claims": None,
            }, None
        title = str(seed["section"]["title"])
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="reasoning",
                        text=f"Reading the sources, {title.lower()} is as described.",
                    )
                ]
            ),
        }, None

    def write_key_findings(self, seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
        self.key_findings_calls += 1
        return SectionProseWire(prose="", claims=[]), None

    def write_case_studies(self, seed: dict[str, Any]) -> UsageResult[CaseStudyWire]:
        self.case_study_calls += 1
        return CaseStudyWire(cards=[]), None

    def write_source_note(self, seed: dict[str, Any]) -> UsageResult[NoteWire]:
        self.source_note_calls += 1
        return NoteWire(note=""), None

    def write_full_report_intro(self, seed: dict[str, Any]) -> UsageResult[IntroWire]:
        self.intro_calls += 1
        return IntroWire(intro=""), None


def _seed_baseline_corpus(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    backends: tuple[str, ...] = ("overton", "overton", "openalex"),
) -> list[uuid.UUID]:
    """Seed screened-in, classified, appraised, ingested documents."""
    tss_ids: list[uuid.UUID] = []
    for index, backend in enumerate(backends):
        tss_id = _seed_select_doc(
            conn,
            task_id,
            run_id,
            scope_id,
            title=f"Status quo source {index}",
        )
        conn.execute(
            update(source_snapshot)
            .where(
                source_snapshot.c.source_snapshot_id
                == select(task_source_snapshot.c.source_snapshot_id)
                .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
                .scalar_subquery()
            )
            .values(
                metadata={
                    "title": f"Status quo source {index}",
                    "abstract": "Abstract.",
                    "year": 2025,
                    "backend": backend,
                }
            )
        )
        seed_ingested_full_text(
            conn, tss_id=tss_id, chunks=[f"Status quo chunk {index}."]
        )
        tss_ids.append(tss_id)
    return tss_ids


def _run_baseline(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    backend: Any,
    context: dict[str, Any] | None = None,
    progress_emitter: ProgressEmitter | None = None,
) -> dict[str, Any]:
    return synthesise_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent="What is the current situation for the target group?",
            context=context if context is not None else _baseline_context(),
        ),
        synthesis_backend=backend,
        grounding_judge_backend=StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
        progress_emitter=progress_emitter,
    )


def _block_titles(conn: Connection, task_id: uuid.UUID) -> list[str]:
    row = conn.execute(
        select(synthesis_result.c.blocks).where(synthesis_result.c.task_id == task_id)
    ).one()
    return [entry["title"] for entry in row.blocks]


def _rollup(conn: Connection, task_id: uuid.UUID) -> Any:
    return conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()


# --- The supplied eight, and the at-most-two extras ---


def test_baseline_supplies_its_sections_and_places_extras_after_contested(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend(
        proposal=SectionProposalWire(
            sections=[
                SectionWire(
                    title="Regional variation",
                    focus="How the situation differs across regions.",
                )
            ]
        )
    )

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend
    )

    titles = _block_titles(conn, task_id)
    assert titles == [
        *REQUIRED_TITLES[: REQUIRED_TITLES.index(CONTESTED) + 1],
        "Regional variation",
        *REQUIRED_TITLES[REQUIRED_TITLES.index(CONTESTED) + 1 :],
        SOURCES_SECTION_TITLE,
    ]
    # The eight required sections are supplied, never proposed: the proposer
    # ran once, and only for the extras.
    assert len(backend.proposal_calls) == 1
    assert backend.proposal_calls[0]["section_budget"] == BASELINE_PROPOSED_SECTIONS_MAX
    assert backend.proposal_calls[0]["rejection"] is None


def test_rapid_writes_the_seven_sections_and_never_calls_the_proposer(conn: Connection) -> None:
    """Phase 8 (owner 2026-09-17): a rapid directive carries no section_budget, so
    the writer lands the same seven supplied sections plus Sources and the
    proposer is never asked."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend(
        proposal=SectionProposalWire(
            sections=[SectionWire(title="Regional variation", focus="Across regions.")]
        )
    )
    rapid = _baseline_context()
    del rapid["synthesis"]["section_budget"]

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend, context=rapid
    )

    assert _block_titles(conn, task_id) == list(required_titles())
    assert backend.proposal_calls == []


def test_baseline_repairs_a_forbidden_proposal_then_lands_zero_extras(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend(
        proposal=SectionProposalWire(
            sections=[SectionWire(title="Conclusions", focus="What it all means.")]
        ),
        repair_proposal=SectionProposalWire(
            sections=[
                SectionWire(title="Who is affected", focus="A duplicate of a required one.")
            ]
        ),
    )

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend
    )

    titles = _block_titles(conn, task_id)
    assert titles == [*REQUIRED_TITLES, SOURCES_SECTION_TITLE]
    assert len(backend.proposal_calls) == 2
    rejection = backend.proposal_calls[1]["rejection"]
    assert rejection is not None
    assert any("title_forbidden" in reason for reason in rejection)
    row = _rollup(conn, task_id)
    normalisations = row.synthesis_provenance["section_set"]["proposal_normalisations"]
    assert any("baseline_extras_dropped" in note for note in normalisations)
    assert any("title_duplicates_required" in note for note in normalisations)


def test_a_baseline_artefact_is_titled_for_what_it_is(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_BaselineBackend(),
    )

    title = conn.execute(
        select(artefact.c.title).where(artefact.c.task_id == task_id)
    ).scalar_one()
    assert title == BASELINE_ARTEFACT_TITLE


# --- Per-section turn cap ---


def test_baseline_sections_run_under_the_template_turn_cap(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend(burn_turns=True)

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend
    )

    assert BASELINE_SECTION_TURN_CAP < SECTION_TURN_CAP
    assert set(backend.turns_by_section.values()) == {BASELINE_SECTION_TURN_CAP}
    row = _rollup(conn, task_id)
    assert row.synthesis_provenance["generation_budget_max"] == generation_budget_max(
        [BASELINE_SECTION_TURN_CAP] * len(REQUIRED_TITLES)
    )


# --- The three Evidence-search-only passes are off ---


def test_baseline_runs_no_evidence_search_shaped_passes(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend()

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend
    )

    assert backend.key_findings_calls == 0
    assert backend.case_study_calls == 0
    assert backend.source_note_calls == 0
    assert backend.intro_calls == 0
    titles = _block_titles(conn, task_id)
    assert CONCLUSIONS_TITLE not in titles
    assert "Key findings" not in titles
    row = _rollup(conn, task_id)
    assert row.counts["key_findings"] == {
        "present": False,
        "reason": "template_has_no_key_findings",
    }
    assert row.counts["case_studies"] == {
        "present": False,
        "reason": "template_has_no_case_studies",
    }
    assert "most_relevant_notes" not in row.counts
    assert "full_report_intro" not in row.counts


def test_baseline_seed_carries_the_template_and_the_substrate_claim_types(
    conn: Connection,
) -> None:
    """No characterise / extract / group ran, so the claim set is what the
    substrate can bear: chunk, reasoning and gap — nothing to code beyond
    this test."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    backend = _BaselineBackend()

    _run_baseline(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id, backend=backend
    )

    assert backend.seeds
    for seed in backend.seeds:
        assert seed["template"] == "baseline"
        assert set(seed["available_claim_types"]) == {"chunk", "reasoning", "gap"}


# --- A section with nothing behind it ---


class _GapOnlyBackend(_BaselineBackend):
    """Every section reports the absence honestly, as a gap claim."""

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        index = int(seed.get("section_index", 0))
        self.turns_by_section[index] = self.turns_by_section.get(index, 0) + 1
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="gap",
                        text="No source found reports on this.",
                        gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
                    )
                ]
            ),
        }, None


def test_baseline_section_with_no_support_renders_as_a_gap(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_GapOnlyBackend(),
    )

    row = _rollup(conn, task_id)
    written = [entry for entry in row.blocks if entry["role"] != "sources"]
    assert written
    for entry in written:
        assert entry["claim_counts_by_type"].get("gap", 0) == 1
    assert row.counts["claims_total"]["gap"] == len(written)


# --- The code-rendered Sources block ---


def test_baseline_sources_block_is_code_rendered_and_carries_no_claims(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backends=("overton", "overton", "openalex"),
    )

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_BaselineBackend(),
    )

    row = _rollup(conn, task_id)
    sources = next(entry for entry in row.blocks if entry["title"] == SOURCES_SECTION_TITLE)
    assert sources["role"] == "sources"
    assert not any(sources["claim_counts_by_type"].values())
    assert sources["citations_verified"] == 0

    prose = conn.execute(
        select(block.c.content)
        .where(block.c.block_id == uuid.UUID(sources["block_id"]))
    ).scalar_one()
    assert prose.startswith("3 sources from Overton and OpenAlex")
    assert SOURCES_NOT_SEARCHED_LINE in prose
    assert "2 grey literature" in prose
    assert "1 academic articles" in prose
    assert "leans on grey-literature sources" in prose


def test_baseline_sources_block_counts_an_unrecorded_backend_as_undetermined(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backends=("openalex", "somewhere_else"),
    )

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_BaselineBackend(),
    )

    row = _rollup(conn, task_id)
    sources = next(entry for entry in row.blocks if entry["title"] == SOURCES_SECTION_TITLE)
    prose = conn.execute(
        select(block.c.content)
        .where(block.c.block_id == uuid.UUID(sources["block_id"]))
    ).scalar_one()
    assert "with 1 of undetermined type" in prose
    assert "leans on academic sources" in prose


def test_a_claim_less_sources_block_is_not_an_uncited_section() -> None:
    """The grounding roll-up reads the code-rendered foot as structural."""
    cited = {"citations_verified": 1, "role": "standard"}
    sources = {"citations_verified": 0, "role": "sources"}
    uncited = {"citations_verified": 0, "role": "standard"}

    def _flags(blocks: list[dict[str, Any]]) -> dict[str, bool]:
        return _rollup_flags(
            groups_unsectioned=0,
            all_claims=[],
            section_blocks=blocks,
            chunk_claims_rejected=0,
            claims_rejected_structural=0,
            gap_claims_degraded=0,
            span_bind_failures=0,
            unspanned_assertions=0,
            turn_cap_hit=False,
            repair_path_taken=False,
            repair_count_mismatch=False,
            repair_unparseable=False,
        )

    assert "uncited_sections" not in _flags([cited, sources])
    assert _flags([cited, sources, uncited])["uncited_sections"] is True


# --- The roll-up and the skeleton ---


def test_baseline_rollup_carries_the_scoping_pass_depth_label(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_BaselineBackend(),
    )

    row = _rollup(conn, task_id)
    assert row.counts["depth_label"] == BASELINE_DEPTH_LABEL == "scoping pass"
    assert row.counts["template"] == "baseline"
    assert row.synthesis_provenance["directive"]["template"] == "baseline"
    assert row.synthesis_provenance["prompt_versions"]["template"] == "baseline_template_v1"


def test_baseline_skeleton_is_the_section_list_with_no_key_findings(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    emitter = _RecordingEmitter()

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_BaselineBackend(),
        progress_emitter=emitter,
    )

    skeleton = next(
        payload for event_type, payload in emitter.events if event_type == "artefact.skeleton"
    )
    assert [entry["title"] for entry in skeleton["sections"]] == [
        *REQUIRED_TITLES,
        SOURCES_SECTION_TITLE,
    ]
    assert [entry["index"] for entry in skeleton["sections"]] == list(
        range(len(REQUIRED_TITLES) + 1)
    )
    # Every section, including the code-rendered foot, streams.
    completed = [
        payload["title"]
        for event_type, payload in emitter.events
        if event_type == "artefact.section_completed"
    ]
    assert completed == [*REQUIRED_TITLES, SOURCES_SECTION_TITLE]


def test_evidence_search_skeleton_still_leads_with_key_findings(conn: Connection) -> None:
    """The Evidence search report is untouched: Conclusions is still injected,
    the key-findings pass still runs and the skeleton still leads with it."""
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
        synthesis_backend=StubSynthesisBackend(),
        grounding_judge_backend=StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
        progress_emitter=emitter,
    )

    skeleton = next(
        payload for event_type, payload in emitter.events if event_type == "artefact.skeleton"
    )
    titles = [entry["title"] for entry in skeleton["sections"]]
    assert titles[0] == "Key findings"
    assert titles[-1] == CONCLUSIONS_TITLE
    assert SOURCES_SECTION_TITLE not in titles
    row = _rollup(conn, task_id)
    assert row.synthesis_provenance["directive"]["template"] is None
    assert "depth_label" not in row.counts


# --- The directive grammar's per-section turn cap ---


def test_directive_rejects_an_out_of_range_section_turn_cap(conn: Connection) -> None:
    from policy_atlas.evidence_search.synthesis.synthesise import SynthesiseFailure

    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    sections: list[dict[str, Any]] = [dict(item) for item in _baseline_section_directives()]
    sections[0]["turn_cap"] = SECTION_TURN_CAP + 1

    with pytest.raises(SynthesiseFailure, match="turn_cap"):
        _run_baseline(
            conn,
            task_id=task_id,
            run_id=run_id,
            scope_id=scope_id,
            backend=_BaselineBackend(),
            context=_baseline_context(sections=sections),
        )


def test_a_supplied_turn_cap_overrides_the_template_default(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_baseline_corpus(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)
    sections: list[dict[str, Any]] = [dict(item) for item in _baseline_section_directives()]
    sections[0]["turn_cap"] = 2
    backend = _BaselineBackend(burn_turns=True)

    _run_baseline(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=backend,
        context=_baseline_context(sections=sections),
    )

    assert backend.turns_by_section[0] == 2
    assert backend.turns_by_section[1] == BASELINE_SECTION_TURN_CAP
