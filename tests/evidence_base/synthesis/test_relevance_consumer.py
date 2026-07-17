"""Tests for the B2′ synthesis consumer (024 / ADR 0023).

The section-drafting prompt bumps to ``synthesise_section_v8`` (always), with
the priority-findings block rendered conditionally on the run carrying
relevance annotations; member findings and ``query_findings`` results gain a
``"relevance"`` mark when (and only when) the run carries annotations; and the
P4 ``priority_counts_by_group`` helper counts marks per group. Prompt-level and
pure-helper cases need no DB; the reader/loader cases ride the ``conn`` fixture.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.evidence_base.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_base.synthesis.synthesis_backend import (
    PRIORITY_FINDINGS_BLOCK,
    SECTION_PROMPT_VERSION,
    build_section_messages,
    build_section_repair_messages,
)
from policy_atlas.evidence_base.synthesis.synthesis_prompts_v6 import (
    build_v6_section_messages,
)
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    make_findings_reader,
    priority_counts_by_group,
)
from policy_atlas.evidence_base.synthesis.synthesise import (
    _load_findings,
    _relevance_annotations,
)
from tests.helpers import (
    seed_project_and_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

from .test_synthesis_tools import _seed_reader_finding


def _seed() -> dict[str, Any]:
    return {
        "intent": "does coaching help?",
        "section": {"title": "Coaching", "focus": "effects", "group_ids": []},
        "section_index": 0,
        "substrate": {},
        "corpus": {},
        "available_tools": ["query_findings", "lookup"],
        "available_claim_types": ["finding", "gap", "reasoning"],
        "member_findings": [],
        "computed_spread": None,
        "ledger": [],
    }


# --- 1. Version + conditional block ------------------------------------------


def test_section_prompt_version_is_v8() -> None:
    assert SECTION_PROMPT_VERSION == "synthesise_section_v8"


def test_block_absent_when_not_active() -> None:
    seed = _seed()  # no priority_block_active key
    for messages in (
        build_section_messages(seed, [], force_emit=False),
        build_section_repair_messages(seed, failing=[]),
    ):
        system = messages[0]["content"]
        assert PRIORITY_FINDINGS_BLOCK not in system

    seed_false = {**_seed(), "priority_block_active": False}
    messages = build_section_messages(seed_false, [], force_emit=False)
    assert PRIORITY_FINDINGS_BLOCK not in messages[0]["content"]


def test_block_present_when_active() -> None:
    seed = {**_seed(), "priority_block_active": True}
    for messages in (
        build_section_messages(seed, [], force_emit=False),
        build_section_repair_messages(seed, failing=[]),
    ):
        assert PRIORITY_FINDINGS_BLOCK in messages[0]["content"]


def test_priority_flag_never_enters_data_payload() -> None:
    """The control flag rides the seed for the system prompt only — it must not
    surface in the id-keyed data payload the model reads as evidence."""
    seed = {**_seed(), "priority_block_active": True}
    messages = build_section_messages(seed, [], force_emit=False)
    for message in messages[1:]:
        assert "priority_block_active" not in message["content"]


def test_v6_baseline_byte_identical_regardless_of_flag() -> None:
    """The frozen v6 cost baseline strips the v8-only control flag: adding it to
    the seed leaves the rendered v6 messages byte-identical."""
    base = _seed()
    with_flag = {**_seed(), "priority_block_active": True}
    a = build_v6_section_messages(base, [], force_emit=False, final_turn_message="END")
    b = build_v6_section_messages(with_flag, [], force_emit=False, final_turn_message="END")
    assert a == b


# --- 2. _relevance_annotations reader ----------------------------------------


def test_relevance_annotations_reads_provenance() -> None:
    row = {
        "extraction_provenance": {
            "profiles": {IOF_PROFILE_ID: {}},
            "relevance": {"annotations": {"f1": "priority", "f2": "normal"}},
        }
    }
    assert _relevance_annotations(row) == {"f1": "priority", "f2": "normal"}


def test_relevance_annotations_absent_or_malformed_degrades_empty() -> None:
    assert _relevance_annotations(None) == {}
    assert _relevance_annotations({"extraction_provenance": {"profiles": {}}}) == {}
    assert _relevance_annotations({"extraction_provenance": "junk"}) == {}
    # A stray non-enum value is dropped, never surfaced.
    row = {
        "extraction_provenance": {
            "relevance": {"annotations": {"f1": "priority", "f2": "urgent", 3: "normal"}}
        }
    }
    assert _relevance_annotations(row) == {"f1": "priority"}


# --- 3. query_findings marks -------------------------------------------------


def _seed_finding(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Doc"})
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    _record_id, finding_id = _seed_reader_finding(
        conn, project_id=project_id, run_id=run_id, scope_id=scope_id,
        pss_id=pss_id, snap_id=snap_id,
    )
    return project_id, run_id, scope_id, finding_id


def test_query_findings_records_carry_mark_when_annotated(conn: Connection) -> None:
    project_id, run_id, scope_id, finding_id = _seed_finding(conn)
    reader = make_findings_reader(
        conn, project_id=project_id, extraction_run_id=run_id,
        evidence_scope_id=scope_id, grouping_groups=None,
        relevance_annotations={str(finding_id): "priority"},
    )
    [record] = reader({})["iof_findings"]
    assert record["relevance"] == "priority"


def test_query_findings_records_no_mark_without_annotations(conn: Connection) -> None:
    project_id, run_id, scope_id, finding_id = _seed_finding(conn)
    reader = make_findings_reader(
        conn, project_id=project_id, extraction_run_id=run_id,
        evidence_scope_id=scope_id, grouping_groups=None,
        relevance_annotations=None,
    )
    [record] = reader({})["iof_findings"]
    assert "relevance" not in record


# --- 4. member-finding marks (_load_findings) --------------------------------


def _extraction_row(pss_id: str, record_id: str, annotations: dict[str, str]) -> dict[str, Any]:
    provenance: dict[str, Any] = {"profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}}}
    if annotations:
        provenance["relevance"] = {"annotations": annotations}
    return {
        "docs": [
            {
                "pss_id": pss_id,
                "basis": "full_text",
                "profiles": {
                    IOF_PROFILE_ID: {
                        "status": "extracted",
                        "finding_count": 1,
                        "reused": False,
                        "error": None,
                        "extraction_record_id": record_id,
                    }
                },
            }
        ],
        "extraction_provenance": provenance,
    }


def test_load_findings_member_record_carries_mark(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Doc"})
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    record_id, finding_id = _seed_reader_finding(
        conn, project_id=project_id, run_id=run_id, scope_id=scope_id,
        pss_id=pss_id, snap_id=snap_id,
    )
    annotations = {str(finding_id): "priority"}
    row = _extraction_row(str(pss_id), str(record_id), annotations)
    assert _relevance_annotations(row) == annotations

    finding_by_id, _icf, _avail, _bases = _load_findings(
        conn, project_id=project_id, extraction_row=row, relevance_annotations=annotations
    )
    assert finding_by_id[str(finding_id)].record["relevance"] == "priority"

    # No annotations → no relevance key on the record (never fabricated).
    bare_row = _extraction_row(str(pss_id), str(record_id), {})
    finding_by_id2, _i2, _a2, _b2 = _load_findings(
        conn, project_id=project_id, extraction_row=bare_row, relevance_annotations={}
    )
    assert "relevance" not in finding_by_id2[str(finding_id)].record


# --- 5. P4 helper ------------------------------------------------------------


def test_priority_counts_by_group() -> None:
    groups = [
        {"group_id": "instrument:g01", "member_finding_ids": ["a", "b", "c"]},
        {"group_id": "instrument:g02", "member_finding_ids": ["d"]},
        {"group_id": "bad-id", "member_finding_ids": ["e"]},  # skipped (unqualified)
    ]
    annotations = {"a": "priority", "b": "normal", "d": "priority"}
    counts = priority_counts_by_group(groups, annotations)
    assert counts == {
        "instrument:g01": {"priority": 1, "normal": 1, "total": 3},  # c absent → total only
        "instrument:g02": {"priority": 1, "normal": 0, "total": 1},
    }


def test_priority_counts_by_group_empty_annotations() -> None:
    groups = [{"group_id": "instrument:g01", "member_finding_ids": ["a", "b"]}]
    assert priority_counts_by_group(groups, None) == {
        "instrument:g01": {"priority": 0, "normal": 0, "total": 2}
    }
    assert priority_counts_by_group(None, {"a": "priority"}) == {}
