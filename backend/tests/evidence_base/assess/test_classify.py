"""Tests for the classify component — schema, backend seam, round-trips, harness integration."""

import uuid
from typing import Any, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.openai_client import openai_kwargs
from policy_atlas.core.schema import (
    METHODOLOGICAL_STRUCTURAL,
    metadata,
    runs,
    source_classification_result,
    source_screening_result,
    source_tag,
)
from policy_atlas.core.usage import TokenUsage, UsageResult
from policy_atlas.evidence_base.assess.classification_backend import (
    OpenAIClassificationBackend,
    StubClassificationBackend,
)
from policy_atlas.evidence_base.assess.classify import ClassifyContext, classify_sources
from policy_atlas.evidence_base.assess.classify_prompt import (
    CLASSIFY_MODEL,
    CLASSIFY_REASONING_EFFORT,
    TAG_MAX_CHARS,
    TAGS_MAX_PER_DOC,
    ClassifyEnvelopePayload,
    ClassifyWire,
)
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    fake_parse_client,
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

# --- Schema ---

def test_table_count(conn: Connection) -> None:
    # 33 -> 35: task 033 adds `organisation` and `app_user` (tenancy above the
    # entity hierarchy); no evidence-base table changed.
    assert len(metadata.tables) == 35


# --- Stub logic (pure Python, no DB) ---

def _stub_classify(metadata: dict[str, object]) -> str:
    wire, usage = StubClassificationBackend().classify(
        ClassifyEnvelopePayload(
            pss_id=str(uuid.uuid4()),
            title="",
            abstract=None,
            priors={},
            metadata=dict(metadata),
        )
    )
    assert usage is None
    return wire.primary_evidence_type


def test_stub_default_unknown() -> None:
    assert _stub_classify({}) == "Unknown / Insufficient information"


def test_stub_non_evidence() -> None:
    assert _stub_classify({"_stub_non_evidence": True}) == "Other (Non-evidence documents)"


def test_stub_policy_guidance() -> None:
    assert _stub_classify({"_stub_policy_guidance": True}) == (
        "Policy Syntheses & Guidance Documents"
    )


def test_stub_rct() -> None:
    assert _stub_classify({"_stub_rct": True}) == "RCTs and Quasi-Experimental Studies"


def test_stub_failure_sentinel_raises() -> None:
    with pytest.raises(RuntimeError):
        StubClassificationBackend().classify(
            ClassifyEnvelopePayload(
                pss_id=str(uuid.uuid4()),
                title="",
                abstract=None,
                priors={},
                metadata={"_stub_classify_failed": True},
            )
        )


# --- Round-trips ---

def test_classify_sources_round_trip(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1
    assert rows[0].evidence_scope_id == scope_id
    assert rows[0].project_source_snapshot_id == pss_id


def test_classify_sources_fan_out_by_type_matches_sentinels(conn: Connection) -> None:
    """Multiple sentinel-driven docs classify to their sentinel's type in one run."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_rct = seed_source(conn, pid, meta={"_stub_rct": True})
    _, pss_policy = seed_source(conn, pid, meta={"_stub_policy_guidance": True})
    _, pss_qual = seed_source(conn, pid, meta={"_stub_qualitative": True})
    _, pss_unknown = seed_source(conn, pid)
    for pss_id in (pss_rct, pss_policy, pss_qual, pss_unknown):
        seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 4
    assert counts["by_type"] == {
        "RCTs and Quasi-Experimental Studies": 1,
        "Policy Syntheses & Guidance Documents": 1,
        "Qualitative & Contextual Evidence": 1,
        "Unknown / Insufficient information": 1,
    }
    rows = conn.execute(
        select(
            source_classification_result.c.project_source_snapshot_id,
            source_classification_result.c.primary_evidence_type,
        ).where(source_classification_result.c.project_id == pid)
    ).fetchall()
    by_pss = {r.project_source_snapshot_id: r.primary_evidence_type for r in rows}
    assert by_pss[pss_rct] == "RCTs and Quasi-Experimental Studies"
    assert by_pss[pss_policy] == "Policy Syntheses & Guidance Documents"
    assert by_pss[pss_qual] == "Qualitative & Contextual Evidence"
    assert by_pss[pss_unknown] == "Unknown / Insufficient information"


def test_classify_sources_non_evidence_persists(conn: Connection) -> None:
    """Non-evidence rows land in source_classification_result (flag-don't-drop)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid, meta={"_stub_non_evidence": True})
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).one()
    assert row.primary_evidence_type == "Other (Non-evidence documents)"


def test_classify_sources_skips_not_relevant(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_relevant = seed_source(conn, pid)
    _, pss_not_relevant = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_relevant, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, pss_not_relevant, status="not_relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 1
    assert counts["skipped"] == 1
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1


def test_classify_sources_skips_failed(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_failed = seed_source(conn, pid)
    # Failed rows are attempt history; two raw failures for one source still
    # count as one effective skipped source.
    for _ in range(2):
        conn.execute(source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_failed,
            project_id=pid,
            screened_by_run_id=rid,
            status="failed",
            screen_basis=None,
            screen_decision_confidence=None,
            screened_at=now(),
        ))

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 0
    assert counts["skipped"] == 1


def test_classify_sources_uses_effective_screen_rows(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_demoted = seed_source(conn, pid, meta={"_stub_rct": True})
    _, pss_confirmed = seed_source(conn, pid, meta={"_stub_policy_guidance": True})
    seed_screening_result(conn, pid, rid, scope_id, pss_demoted, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, pss_confirmed, status="relevant")
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_demoted,
        project_id=pid,
        screened_by_run_id=rid,
        status="not_relevant",
        screen_basis="title_abstract",
        screen_decision_confidence=0.95,
        screen_stage=2,
        screened_at=now(),
    ))
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_confirmed,
        project_id=pid,
        screened_by_run_id=rid,
        status="relevant",
        screen_basis="title_abstract",
        screen_decision_confidence=0.9,
        screen_stage=2,
        screened_at=now(),
    ))

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 1
    assert counts["skipped"] == 1
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1
    assert rows[0].project_source_snapshot_id == pss_confirmed
    assert rows[0].primary_evidence_type == "Policy Syntheses & Guidance Documents"


def test_classify_count_invariant(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, p1 = seed_source(conn, pid)
    _, p2 = seed_source(conn, pid)
    _, p3 = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, p1, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, p2, status="not_relevant")
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=p3,
        project_id=pid,
        screened_by_run_id=rid,
        status="failed",
        screen_basis=None,
        screen_decision_confidence=None,
        screened_at=now(),
    ))

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] + counts["skipped"] + counts["already_classified"] == 3


def test_excluded_retracted_never_reaches_classify_eligibility(conn: Connection) -> None:
    """A retracted doc (task 019 item 8) has an effective screening row but
    never a 'relevant' one, so it is never classified — it lands in 'skipped'
    like a not_relevant doc, not silently dropped from the funnel invariant."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_relevant = seed_source(conn, pid)
    _, pss_retracted = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_relevant, status="relevant")
    seed_screening_result(
        conn, pid, rid, scope_id, pss_retracted, status="excluded_retracted"
    )

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 1
    assert counts["skipped"] == 1
    assert counts["classified"] + counts["skipped"] + counts["already_classified"] == 2

    rows = conn.execute(
        select(source_classification_result.c.project_source_snapshot_id).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert [row.project_source_snapshot_id for row in rows] == [pss_relevant]


def test_classify_sources_idempotent_rerun(conn: Connection) -> None:
    """Re-running classify_sources for the same scope does not raise or duplicate rows."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    first = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert first["classified"] == 1
    assert first["already_classified"] == 0

    second = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert second["classified"] == 0
    assert second["already_classified"] == 1
    assert second["classified"] + second["skipped"] + second["already_classified"] == 1

    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1


def test_classified_by_run_id(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).one()
    assert row.classified_by_run_id == rid


# --- Check / unique constraints ---

def test_ck_bad_primary_evidence_type(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)

    with pytest.raises(IntegrityError):
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=pid,
            classified_by_run_id=rid,
            primary_evidence_type="Not A Valid Type",
            classified_at=now(),
        ))
    conn.rollback()
    conn.begin()


def test_uq_scope_source_duplicate(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    with pytest.raises(IntegrityError):
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=pid,
            classified_by_run_id=rid,
            primary_evidence_type="Unknown / Insufficient information",
            classified_at=now(),
        ))
    conn.rollback()
    conn.begin()


def test_cross_project_fk_rejected(conn: Connection) -> None:
    pid_a, rid_a = seed_project_and_run(conn)
    pid_b, _ = seed_project_and_run(conn)

    scope_id = seed_scope(conn, pid_a)
    _, pss_id_b = seed_source(conn, pid_b)

    # scope belongs to project A, pss belongs to project B → FK violation
    with pytest.raises(IntegrityError):
        conn.execute(sa.text(
            "INSERT INTO source_classification_result "
            "(source_classification_result_id, evidence_scope_id, project_source_snapshot_id, "
            " project_id, classified_by_run_id, primary_evidence_type, classified_at) "
            "VALUES (:scrid, :scope_id, :pss_id, :pid_a, :rid_a, "
            "'Unknown / Insufficient information', :ts)"
        ), {
            "scrid": uuid.uuid4(),
            "scope_id": scope_id,
            "pss_id": pss_id_b,
            "pid_a": pid_a,
            "rid_a": rid_a,
            "ts": now(),
        })
    conn.rollback()
    conn.begin()


def test_classify_sources_doc_exception_isolated(conn: Connection) -> None:
    """One document's classify exception writes no row; other docs still process."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_boom = seed_source(conn, pid, meta={"_stub_classify_failed": True})
    _, pss_fine = seed_source(conn, pid, meta={"_stub_rct": True})
    seed_screening_result(conn, pid, rid, scope_id, pss_boom, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, pss_fine, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 1
    assert counts["failed"] == 1
    assert counts["retries"] == 1
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    by_pss = {r.project_source_snapshot_id: r.primary_evidence_type for r in rows}
    assert pss_boom not in by_pss
    assert by_pss[pss_fine] == "RCTs and Quasi-Experimental Studies"
    classified_events = [
        e for e in events.read(conn, pid) if e["event_type"] == "source.classified"
    ]
    assert [e["payload"]["project_source_snapshot_id"] for e in classified_events] == [
        str(pss_fine)
    ]

    retry_run = seed_run(conn, pid)
    retry_counts = classify_sources(conn, project_id=pid, run_id=retry_run, context=ctx)

    assert retry_counts["classified"] == 0
    assert retry_counts["already_classified"] == 1
    assert retry_counts["failed"] == 1
    assert retry_counts["retries"] == 1


# --- Harness integration ---


class _UsageClassificationBackend:
    mode = "stub"

    def classify(self, payload: ClassifyEnvelopePayload) -> UsageResult[ClassifyWire]:
        del payload
        return (
            ClassifyWire(
                primary_evidence_type="Qualitative & Contextual Evidence",
                tags=[],
                confidence=0.8,
                reason="Fake backend with token usage.",
            ),
            TokenUsage(prompt=11, completion=7, total=18),
        )


def test_harness_classify_component(conn: Connection) -> None:
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Housing policy."})
    seed_source(conn, pid, meta={"_stub_not_relevant": True, "abstract": "Off-topic."})

    # Screen first so there are relevant rows
    from policy_atlas.evidence_base.assess.screen import ScreenContext, screen_sources
    screen_ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})
    screen_sources(conn, project_id=pid, run_id=rid_screen, context=screen_ctx)

    # Create a second run for classify
    rid_classify = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid_classify, project_id=pid, status="running", started_at=now()
    ))

    plan = Plan(component="classify", evidence_scope_id=scope_id)
    config = compile(plan)
    outcome = run_harness(
        conn,
        config=config,
        project_id=pid,
        run_id=rid_classify,
        provider=StubEchoProvider(),
        classification_backend=_UsageClassificationBackend(),
    )

    # One classification row (only the relevant source)
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1

    summary = outcome["summary"]
    assert summary is not None
    assert {"classified", "by_type", "skipped"} <= set(summary.keys())
    assert summary["classified"] == 1
    assert summary["skipped"] == 1
    assert summary["usage_totals"] == {"prompt": 11, "completion": 7, "total": 18, "cached": 0}

    # Run ended as succeeded
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid_classify)).one()
    assert run_row.status == "succeeded"


def test_source_classified_event_payload(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    snap_id, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    log_entries = events.read(conn, pid)
    classified_events = [e for e in log_entries if e["event_type"] == "source.classified"]
    assert len(classified_events) == 1
    p = classified_events[0]["payload"]
    assert p["source_snapshot_id"] == str(snap_id)
    assert p["project_source_snapshot_id"] == str(pss_id)
    assert p["evidence_scope_id"] == str(scope_id)
    assert p["primary_evidence_type"] == "Unknown / Insufficient information"
    assert p["confidence"] == 0.9
    assert p["reason"] == "Deterministic stub classification."
    assert p["tags"] == []


def test_classify_sources_writes_bounded_methodological_tags(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    valid_tags = [f"method tag {index}" for index in range(TAGS_MAX_PER_DOC + 2)]
    wire_tags = [
        " longitudinal cohort ",
        "",
        "multi-country comparison",
        "multi-country comparison",
        "x" * (TAG_MAX_CHARS + 1),
        "bad\ncontrol",
        *valid_tags,
    ]
    _, pss_id = seed_source(
        conn,
        pid,
        meta={"_stub_policy_guidance": True, "_stub_tags": wire_tags},
    )
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    expected_tags = ["longitudinal cohort", "multi-country comparison", *valid_tags[:8]]
    assert counts["classified"] == 1
    assert counts["tags_written"] == TAGS_MAX_PER_DOC
    assert counts["tags_rejected"] == 6
    rows = conn.execute(
        select(source_tag.c.tag, source_tag.c.tag_type, source_tag.c.asserted_by)
        .where(source_tag.c.project_source_snapshot_id == pss_id)
        .order_by(source_tag.c.tag)
    ).fetchall()
    assert {row.tag for row in rows} == set(expected_tags)
    assert {row.tag_type for row in rows} == {METHODOLOGICAL_STRUCTURAL}
    assert {row.asserted_by for row in rows} == {"classify"}

    classified_event = [
        e for e in events.read(conn, pid) if e["event_type"] == "source.classified"
    ][0]
    assert classified_event["payload"]["tags"] == expected_tags


def test_delete_project_data_removes_classification(conn: Connection) -> None:
    from tests.helpers import delete_project_data

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    # Verify row exists
    count_before = conn.execute(
        sa.select(sa.func.count()).select_from(source_classification_result)
        .where(source_classification_result.c.project_id == pid)
    ).scalar_one()
    assert count_before == 1

    conn.commit()
    delete_project_data(conn, pid)
    conn.commit()

    count_after = conn.execute(
        sa.select(sa.func.count()).select_from(source_classification_result)
        .where(source_classification_result.c.project_id == pid)
    ).scalar_one()
    assert count_after == 0


# --- Model constant + reasoning-effort seam (018 A1) ---


def test_classify_backend_passes_model_and_reasoning_effort() -> None:
    wire = ClassifyWire(
        primary_evidence_type="RCTs and Quasi-Experimental Studies",
        tags=[],
        confidence=0.8,
        reason="Randomized trial.",
    )
    backend: OpenAIClassificationBackend = object.__new__(OpenAIClassificationBackend)
    fake_client = fake_parse_client(parsed=wire)
    cast("Any", backend)._client = fake_client
    cast("Any", backend)._langfuse_client = None

    result, usage = backend.classify(
        ClassifyEnvelopePayload(
            pss_id=str(uuid.uuid4()),
            title="A randomized trial",
            abstract="Abstract text.",
            priors={},
        )
    )

    assert result.primary_evidence_type == "RCTs and Quasi-Experimental Studies"
    assert usage is None
    [kwargs] = fake_client.chat.completions.calls
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["model"] == CLASSIFY_MODEL
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["reasoning_effort"] == CLASSIFY_REASONING_EFFORT


def test_openai_kwargs_omits_reasoning_effort_when_none() -> None:
    kwargs = openai_kwargs("gpt-5.4-mini")
    assert kwargs == {"model": "gpt-5.4-mini"}
    assert "reasoning_effort" not in kwargs


def test_openai_kwargs_includes_reasoning_effort_when_set() -> None:
    kwargs = openai_kwargs("gpt-5.4-mini", reasoning_effort="xhigh")
    assert kwargs == {"model": "gpt-5.4-mini", "reasoning_effort": "xhigh"}
