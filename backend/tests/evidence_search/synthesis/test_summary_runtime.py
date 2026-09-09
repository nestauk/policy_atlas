"""Post-commit navigation-summary runtime tests (task 028 phase C)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import artefact, block, synthesis_result
from policy_atlas.evidence_search.synthesis import synthesise as synthesise_module
from policy_atlas.evidence_search.synthesis.synthesis_backend import (
    StubSynthesisBackend,
    SummaryJudgeWire,
    SummaryWire,
)
from policy_atlas.evidence_search.synthesis.synthesise import (
    SUMMARY_REGENERATE_CAP,
    write_summaries_after_commit,
)
from tests.helpers import delete_task_data, now, seed_scope, seed_task_and_run


class _ScriptedSummaryBackend(StubSynthesisBackend):
    """Stub backend whose block-summary text is scripted call by call."""

    def __init__(self, summaries: list[str]) -> None:
        super().__init__()
        self._summaries = list(summaries)

    def write_block_summary(self, seed: dict[str, Any]) -> Any:
        """Return the next scripted summary, bypassing the prose-derived stub text."""
        self.summary_seeds.append(seed)
        return SummaryWire(summary=self._summaries.pop(0)), None


def _seed_summary_source(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Commit a minimal completed synthesis result for post-commit tests."""
    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
        scope_id = seed_scope(conn, task_id)
        artefact_id = uuid.uuid4()
        conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                task_id=task_id,
                title="Test evidence report",
                created_at=now(),
            )
        )
        definitions = [
            (
                "Ordinary section",
                "standard",
                "Ordinary prose must not anchor the artefact summary.",
            ),
            ("Key findings", "key_findings", "Key findings prose anchors the report summary."),
            ("Conclusions", "conclusions", "Conclusions prose anchors the report summary."),
        ]
        block_ids: list[uuid.UUID] = []
        rollup_blocks: list[dict[str, str]] = []
        for title, role, prose in definitions:
            block_id = uuid.uuid4()
            block_ids.append(block_id)
            conn.execute(
                block.insert().values(
                    block_id=block_id,
                    artefact_id=artefact_id,
                    content=prose,
                    content_hash="summary-test",
                    created_at=now(),
                )
            )
            rollup_blocks.append({"block_id": str(block_id), "title": title, "role": role})
        conn.execute(
            synthesis_result.insert().values(
                synthesis_result_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=rollup_blocks,
                counts={},
                flags={},
                created_at=now(),
            )
        )
    return task_id, run_id, block_ids


def _summary_rows(
    engine: Engine, block_ids: list[uuid.UUID]
) -> list[tuple[str | None, str | None]]:
    with engine.connect() as conn:
        return cast(
            list[tuple[str | None, str | None]],
            list(
            conn.execute(
                select(block.c.summary, block.c.summary_status)
                .where(block.c.block_id.in_(block_ids))
                .order_by(block.c.created_at)
            )
            ),
        )


def test_summaries_are_post_commit_and_absent_when_synthesis_does_not_commit(
    engine: Engine,
) -> None:
    """No roll-up means no summary work; a committed roll-up is summarised."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id, block_ids = _seed_summary_source(engine)
        result = write_summaries_after_commit(
            engine,
            task_id=task_id,
            run_id=run_id,
            synthesis_backend=StubSynthesisBackend(),
        )
        assert result["call_counts"]["writer"] == 4
        assert all(status == "verified" for _summary, status in _summary_rows(engine, block_ids))

        with engine.begin() as conn:
            failed_run_id = uuid.uuid4()
            # A block without a committed synthesis_result is the rollback/failure
            # shape: the post-commit runner cannot discover or touch it.
            conn.execute(
                block.update()
                .where(block.c.block_id == block_ids[0])
                .values(summary=None, summary_status=None)
            )
        write_summaries_after_commit(
            engine,
            task_id=task_id,
            run_id=failed_run_id,
            synthesis_backend=StubSynthesisBackend(),
        )
        assert _summary_rows(engine, [block_ids[0]]) == [(None, None)]
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_provider_failures_degrade_disable_and_leave_the_component_data_intact(
    engine: Engine,
) -> None:
    """Two consecutive provider errors mark failed summaries and stop later work."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id, block_ids = _seed_summary_source(engine)
        backend = StubSynthesisBackend(summary_fail=True)
        result = write_summaries_after_commit(
            engine, task_id=task_id, run_id=run_id, synthesis_backend=backend
        )
        assert result["provider_disabled"] is True
        assert backend.summary_seeds == []
        assert all(
            summary is None and status == "failed"
            for summary, status in _summary_rows(engine, block_ids)
        )
        with engine.connect() as conn:
            assert conn.execute(
                select(synthesis_result.c.run_id).where(synthesis_result.c.run_id == run_id)
            ).scalar_one() == run_id
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_summary_transaction_failure_is_isolated_to_its_block(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed summary write leaves prose intact and later blocks still summarise."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id, block_ids = _seed_summary_source(engine)
        original = synthesise_module._persist_summary_status

        def _fail_first_block(*args: object, **kwargs: object) -> None:
            if kwargs["target"] == "block" and kwargs["target_id"] == block_ids[0]:
                raise RuntimeError("summary transaction sentinel")
            original(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(synthesise_module, "_persist_summary_status", _fail_first_block)
        write_summaries_after_commit(
            engine,
            task_id=task_id,
            run_id=run_id,
            synthesis_backend=StubSynthesisBackend(),
        )
        rows = _summary_rows(engine, block_ids)
        assert rows[0] == (None, None)
        assert all(status == "verified" for _summary, status in rows[1:])
        with engine.connect() as conn:
            assert conn.execute(
                select(block.c.content).where(block.c.block_id == block_ids[0])
            ).scalar_one() == "Ordinary prose must not anchor the artefact summary."
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_judge_fail_regenerates_then_persists_only_failed_status(engine: Engine) -> None:
    """Three failed verdicts exhaust the bounded regeneration path without text."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id, block_ids = _seed_summary_source(engine)
        backend = StubSynthesisBackend(
            summary_judgements=[
                SummaryJudgeWire(verdict="fail", reason="first"),
                SummaryJudgeWire(verdict="fail", reason="second"),
                SummaryJudgeWire(verdict="fail", reason="third"),
            ]
        )
        result = write_summaries_after_commit(
            engine, task_id=task_id, run_id=run_id, synthesis_backend=backend
        )
        first = next(
            entry
            for entry in result["per_summary"]
            if entry["kind"] == "block" and entry["block_id"] == str(block_ids[0])
        )
        assert first["status"] == "failed"
        assert first["writer_calls"] == 3
        assert first["judge_calls"] == 3
        assert _summary_rows(engine, [block_ids[0]]) == [(None, "failed")]
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_writer_over_length_summary_fails_without_judge() -> None:
    """A deterministically oversized block summary fails before any judge call."""
    long_summary = "x" * 400
    backend = _ScriptedSummaryBackend([long_summary] * (SUMMARY_REGENERATE_CAP + 1))
    result = synthesise_module._write_and_judge_summary(
        synthesis_backend=backend,
        seed={"kind": "block"},
        detail={},
    )
    assert result["status"] == "failed"
    assert result["reason"] == "over_length"
    assert result["judge_calls"] == 0
    assert backend.summary_judge_inputs == []


def test_writer_citation_marker_summary_fails() -> None:
    """A block summary carrying a bracketed citation marker fails deterministically."""
    tainted_summary = "See finding [3] for detail."
    backend = _ScriptedSummaryBackend([tainted_summary] * (SUMMARY_REGENERATE_CAP + 1))
    result = synthesise_module._write_and_judge_summary(
        synthesis_backend=backend,
        seed={"kind": "block"},
        detail={},
    )
    assert result["status"] == "failed"
    assert result["reason"] == "citation_markers"
    assert result["judge_calls"] == 0
    assert backend.summary_judge_inputs == []


def test_format_violation_on_first_attempt_consumes_one_regenerate_and_then_verifies() -> None:
    """An over-length first attempt still leaves a clean regenerate free to verify."""
    long_summary = "x" * 400
    clean_summary = "A concise clean summary."
    backend = _ScriptedSummaryBackend([long_summary, clean_summary])
    result = synthesise_module._write_and_judge_summary(
        synthesis_backend=backend,
        seed={"kind": "block"},
        detail={},
    )
    assert result["status"] == "verified"
    assert result["summary"] == clean_summary
    assert result["writer_calls"] == 2
    assert result["judge_calls"] == 1


def test_artefact_summary_seed_is_anchored_on_key_findings_and_conclusions(engine: Engine) -> None:
    """The artefact writer receives conclusion-bearing prose, never ordinary prose."""
    task_id: uuid.UUID | None = None
    try:
        task_id, run_id, _block_ids = _seed_summary_source(engine)
        backend = StubSynthesisBackend()
        write_summaries_after_commit(
            engine, task_id=task_id, run_id=run_id, synthesis_backend=backend
        )
        artefact_seed = backend.summary_seeds[-1]
        assert artefact_seed["kind"] == "artefact"
        rendered = str(artefact_seed["conclusion_bearing_blocks"])
        assert "Key findings prose" in rendered
        assert "Conclusions prose" in rendered
        assert "Ordinary prose" not in rendered
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)
