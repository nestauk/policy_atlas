"""Contract tests for terminal-run chat reader binding."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.chat_scope import build_chat_readers, resolve_terminal_run_components
from policy_atlas.core import events
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    TOPIC_THEME,
    capability_run,
    runs,
    search_coverage_record,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_tag,
    task_source_snapshot,
)
from tests.helpers import now
from tests.runtime.test_runner import _cleanup, _seed_task


def _walk(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    status: str = "succeeded",
    components: tuple[str, ...] = ("characterise", "select", "extract", "group"),
) -> tuple[uuid.UUID, dict[str, list[uuid.UUID]]]:
    """Persist a stub capability walk and its ordered component starts."""
    capability_run_id = uuid.uuid4()
    component_runs: dict[str, list[uuid.UUID]] = {}
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=capability_run_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="evidence_search",
                plan_id=uuid.uuid4(),
                plan_version=1,
                status=status,
                started_at=now(),
                ended_at=now() if status in {"succeeded", "degraded"} else None,
            )
        )
        for component in components:
            run_id = uuid.uuid4()
            component_runs.setdefault(component, []).append(run_id)
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=task_id,
                    status="succeeded",
                    started_at=now(),
                    ended_at=now(),
                    capability_run_id=capability_run_id,
                )
            )
            events.append(
                conn,
                task_id=task_id,
                run_id=run_id,
                event_type="run.started",
                payload={"component": component, "registry_component": component},
            )
    return capability_run_id, component_runs


def _append_attempt(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    component: str,
    status: str = "succeeded",
) -> uuid.UUID:
    """Append one ordered component attempt to an existing walk."""
    run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=task_id,
                status=status,
                started_at=now(),
                ended_at=now(),
                capability_run_id=capability_run_id,
            )
        )
        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type="run.started",
            payload={"component": component, "registry_component": component},
        )
    return run_id


def test_resolver_returns_terminal_component_ids(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        capability_run_id, attempts = _walk(
            engine, task_id=task_id, scope_id=scope_id
        )

        scope = resolve_terminal_run_components(engine, task_id=task_id)
        assert scope is not None
        assert scope.capability_run_id == capability_run_id
        assert scope.evidence_scope_id == scope_id
        assert scope.characterisation_run_id == attempts["characterise"][-1]
        assert scope.selection_run_id == attempts["select"][-1]
        assert scope.extraction_run_id == attempts["extract"][-1]
        assert scope.grouping_run_id == attempts["group"][-1]
    finally:
        _cleanup(engine, task_id)


def test_resolver_uses_later_replacement_attempt(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        _capability_run_id, attempts = _walk(engine, task_id=task_id, scope_id=scope_id)
        replacement = _append_attempt(
            engine,
            task_id=task_id,
            capability_run_id=_capability_run_id,
            component="select",
        )

        scope = resolve_terminal_run_components(engine, task_id=task_id)
        assert scope is not None
        assert scope.selection_run_id == replacement
        assert scope.selection_run_id != attempts["select"][-1]
    finally:
        _cleanup(engine, task_id)


def test_resolver_ignores_additive_acquire_retries(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        capability_run_id, attempts = _walk(engine, task_id=task_id, scope_id=scope_id)
        _append_attempt(
            engine,
            task_id=task_id,
            capability_run_id=capability_run_id,
            component="acquire",
        )
        _append_attempt(
            engine,
            task_id=task_id,
            capability_run_id=capability_run_id,
            component="acquire",
        )

        scope = resolve_terminal_run_components(engine, task_id=task_id)
        assert scope is not None
        assert scope.selection_run_id == attempts["select"][-1]
        assert scope.extraction_run_id == attempts["extract"][-1]
    finally:
        _cleanup(engine, task_id)


def test_resolver_keeps_degraded_missing_component_honest(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        _walk(
            engine,
            task_id=task_id,
            scope_id=scope_id,
            status="degraded",
            components=("characterise", "select", "extract"),
        )

        scope = resolve_terminal_run_components(engine, task_id=task_id)
        assert scope is not None
        assert scope.grouping_run_id is None
    finally:
        _cleanup(engine, task_id)


def test_resolver_returns_none_without_completed_walk(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="running")
        assert resolve_terminal_run_components(engine, task_id=task_id) is None
    finally:
        _cleanup(engine, task_id)


def test_scope_wide_readers_exclude_rows_from_newer_walk(engine: Engine) -> None:
    """Every run-keyed scope-wide lookup remains at its turn-start snapshot."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        terminal_id, old = _walk(
            engine,
            task_id=task_id,
            scope_id=scope_id,
            components=(
                "acquire",
                "screen_abstract",
                "classify",
                "appraise",
                "characterise",
                "select",
                "extract",
                "group",
            ),
        )
        with engine.begin() as conn:
            tss_ids = list(
                conn.execute(
                    select(task_source_snapshot.c.task_source_snapshot_id)
                    .where(task_source_snapshot.c.task_id == task_id)
                    .order_by(task_source_snapshot.c.task_source_snapshot_id)
                ).scalars()
            )
            old_doc, new_doc = tss_ids[:2]
            _seed_scope_rows(
                conn,
                task_id=task_id,
                scope_id=scope_id,
                doc_id=old_doc,
                runs_by_component=old,
                suffix="old",
            )

        resolved = resolve_terminal_run_components(engine, task_id=task_id)
        assert resolved is not None and resolved.capability_run_id == terminal_id
        _retriever, _findings, lookup = build_chat_readers(engine, resolved, task_id)
        assert lookup({"kind": "appraisal_by_doc", "doc_id": str(old_doc)})["result"] == {
            "quality_score": 3,
            "rubric_version": "old",
        }

        newer_id, newer = _walk(
            engine,
            task_id=task_id,
            scope_id=scope_id,
            status="running",
            components=("acquire", "screen_abstract", "classify", "appraise"),
        )
        del newer_id
        with engine.begin() as conn:
            conn.execute(
                update(source_appraisal_result)
                .where(source_appraisal_result.c.task_id == task_id)
                .values(appraised_by_run_id=newer["appraise"][-1], quality_score=5)
            )
            conn.execute(
                update(source_classification_result)
                .where(source_classification_result.c.task_id == task_id)
                .values(classified_by_run_id=newer["classify"][-1])
            )
            _seed_scope_rows(
                conn,
                task_id=task_id,
                scope_id=scope_id,
                doc_id=new_doc,
                runs_by_component=newer,
                suffix="new",
                include_appraisal=False,
                include_classification=False,
            )

        assert lookup({"kind": "appraisal_by_doc", "doc_id": str(old_doc)})["result"] == {
            "absent": True
        }
        assert lookup({"kind": "classification_by_doc", "doc_id": str(old_doc)})[
            "result"
        ] == {"absent": True}
        assert lookup({"kind": "tags_by_doc", "doc_id": str(old_doc)})["result"] == [
            {"tag": "shared", "tag_type": TOPIC_THEME, "asserted_by": "characterise"}
        ]
        assert lookup({"kind": "screening_by_doc", "doc_id": str(old_doc)})["result"] == [
            {
                "screen_stage": 1,
                "status": "relevant",
                "screen_basis": "title_abstract",
                "screen_decision_confidence": 0.9,
            }
        ]
        assert lookup({"kind": "coverage_records"})["result"] and len(
            lookup({"kind": "coverage_records"})["result"]
        ) == 1
        assert lookup({"kind": "docs_by_tag", "tag": "shared"})["result"] == [str(old_doc)]
        assert lookup({"kind": "tag_aggregate", "by": "type"})["result"] == {
            TOPIC_THEME: 1
        }
        # ``screening_by_doc`` resolves doc ids task-wide by design (022
        # rider 16: screened-out docs' history must stay readable), so a doc
        # known only to a newer walk resolves — but none of its rows may
        # appear in this turn's snapshot.
        assert lookup({"kind": "screening_by_doc", "doc_id": str(new_doc)})["result"] == []
    finally:
        _cleanup(engine, task_id)


def _seed_scope_rows(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    doc_id: uuid.UUID,
    runs_by_component: dict[str, list[uuid.UUID]],
    suffix: str,
    include_appraisal: bool = True,
    include_classification: bool = True,
) -> None:
    """Seed each scope-wide lookup row with explicit creating-run provenance."""
    conn.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_source_snapshot_id=doc_id,
            task_id=task_id,
            screened_by_run_id=runs_by_component["screen_abstract"][-1],
            status="relevant",
            screen_basis="title_abstract",
            screen_decision_confidence=0.9,
            screen_stage=1,
            screen_generation=0,
            screened_at=now(),
        )
    )
    if include_classification:
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                task_source_snapshot_id=doc_id,
                task_id=task_id,
                classified_by_run_id=runs_by_component["classify"][-1],
                primary_evidence_type=EVIDENCE_TYPES[0],
                classified_at=now(),
            )
        )
    if include_appraisal:
        conn.execute(
            source_appraisal_result.insert().values(
                source_appraisal_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                task_source_snapshot_id=doc_id,
                task_id=task_id,
                appraised_by_run_id=runs_by_component["appraise"][-1],
                quality_score=3,
                rubric_version=suffix,
                appraised_at=now(),
            )
        )
    conn.execute(
        source_tag.insert().values(
            source_tag_id=uuid.uuid4(),
            task_id=task_id,
            task_source_snapshot_id=doc_id,
            tag="shared",
            tag_type=TOPIC_THEME,
            asserted_by="characterise",
            created_by_run_id=runs_by_component["characterise"][-1]
            if "characterise" in runs_by_component
            else runs_by_component["classify"][-1],
            created_at=now(),
        )
    )
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_id=task_id,
            acquired_by_run_id=runs_by_component["acquire"][-1],
            backends=[],
            scope_filters={},
            stop_condition="completed",
            adequacy_verdict="adequate",
            verdict_origin="model",
            created_at=now(),
        )
    )
