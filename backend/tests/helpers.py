"""Shared test helpers — not fixtures, plain functions."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_base.sourcing.search_loop import CallVerb, ExecutedCall, QueryOrigin
from policy_atlas.evidence_base.sourcing.search_prompts import (
    QueriesPayload,
    ReformulatePayload,
    SearchQueriesWire,
    SearchSuggestWire,
    SuggestPayload,
)

if TYPE_CHECKING:
    from policy_atlas.evidence_base.extract.icf_records import ICFRecordWire

EVIDENCE_TYPE = "RCTs and Quasi-Experimental Studies"
IOF_PROFILE_ID = "eb_iof_base_v1"
ICF_PROFILE_ID = "eb_icf_base_v1"

_UNSET: Any = object()


def now() -> datetime:
    return datetime.now(UTC)


# --- Fake OpenAI ``chat.completions.parse`` client double (task 023 WP8) ---
#
# Every ``OpenAI*Backend.<verb>`` seam that calls ``self._client.chat.completions.parse(...)``
# and reads ``response.choices[0].message.parsed`` shares this shape. Backends whose live path
# calls ``.completions.create`` with tool-call messages (e.g. ``OpenAISynthesisBackend``'s
# section-turn loop) are a genuinely different shape — those stay local to their test module.


@dataclass
class FakeParsedMessage:
    parsed: Any


@dataclass
class FakeChoice:
    message: FakeParsedMessage


@dataclass
class FakeParseResponse:
    choices: list[FakeChoice]
    usage: Any = None


class FakeParseCompletions:
    """Test double for ``client.chat.completions``, recording every ``parse()`` call's kwargs."""

    def __init__(self, response: FakeParseResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> FakeParseResponse:
        self.calls.append(kwargs)
        return self._response


class FakeParseChat:
    def __init__(self, response: FakeParseResponse) -> None:
        self.completions = FakeParseCompletions(response)


class FakeOpenAIParseClient:
    """Test double for an OpenAI client exposing only ``chat.completions.parse``.

    Build via ``fake_parse_client``, not directly.
    """

    def __init__(self, response: FakeParseResponse) -> None:
        self.chat = FakeParseChat(response)


def fake_parse_client(
    *,
    parsed: Any = _UNSET,
    usage: Any = None,
    choices: list[FakeChoice] | None = None,
) -> FakeOpenAIParseClient:
    """Build a fake OpenAI client double for a ``chat.completions.parse`` backend seam.

    The common case passes ``parsed``: it becomes the sole choice's
    ``message.parsed`` (identity-preserved — ``result is parsed`` holds for
    backends that return the parsed object verbatim). Pass ``choices``
    directly instead — even ``[]`` — to control the choices list exactly,
    e.g. to exercise a backend's no-choices error path. Exactly one of
    ``parsed``/``choices`` should be given.

    Every ``parse()`` call's kwargs are recorded on
    ``client.chat.completions.calls``, in order, for assertions like
    ``kwargs["model"] == ...``.

    Args:
        parsed: The parsed payload for the sole response choice.
        usage: The fake response's ``usage`` attribute; most backends under
            test don't read it, so it defaults to ``None``.
        choices: An explicit choices list, bypassing ``parsed``.

    Returns:
        A fake client to assign onto a backend's ``_client`` attribute.
    """
    if choices is None:
        if parsed is _UNSET:
            raise ValueError("fake_parse_client requires parsed= or choices=")
        choices = [FakeChoice(message=FakeParsedMessage(parsed))]
    return FakeOpenAIParseClient(FakeParseResponse(choices=choices, usage=usage))


def executed_calls_for(
    backends: "Sequence[Any]",
    query: str,
    *,
    verb: "CallVerb" = "search",
    query_origin: "QueryOrigin" = "verbatim",
) -> list[ExecutedCall]:
    """Build one ``ExecutedCall`` per backend via a direct ``backend.search(query)`` call.

    Mirrors the removed ``acquire.py`` legacy none-fabrication path (task 023 C3
    cut): production always supplies ``executed_calls`` to ``acquire_sources``
    now, so tests that exercised the old omitted-``executed_calls`` branch
    build their own executed-call stream here, upstream of ``acquire_sources``.

    Args:
        backends: Backend instances to call ``search`` on, in order.
        query: Query text passed to each backend's ``search``.
        verb: Recorded call verb; defaults to ``"search"``.
        query_origin: Recorded query origin; defaults to ``"verbatim"``.

    Returns:
        One ``ExecutedCall`` per backend, ``status="error"`` if ``search`` raised.
    """
    calls: list[ExecutedCall] = []
    for backend in backends:
        status: Literal["ok", "error"]
        error: str | None
        try:
            records = backend.search(query)
            status, error = "ok", None
        except Exception as exc:
            records = []
            status, error = "error", str(exc)
        calls.append(
            ExecutedCall(
                backend_name=backend.name,
                verb=verb,
                query=query,
                query_origin=query_origin,
                wire_params={},
                records=records,
                status=status,
                error=error,
            )
        )
    return calls


def make_icf_wire_record(**overrides: Any) -> "ICFRecordWire":
    """Build an ICF wire record with sane defaults; override per test."""
    from policy_atlas.evidence_base.extract.icf_records import ICFRecordWire
    from policy_atlas.evidence_base.extract.iof_records import IOFAnchorWire

    values: dict[str, Any] = {
        "context_type": "barrier",
        "claim": "Training gaps slowed delivery of the programme.",
        "context_label": None,
        "intervention": "home visiting",
        "outcome": None,
        "population": "families with young children",
        "setting": "primary care",
        "study_geography": "England",
        "study_design": "process evaluation",
        "claim_level": "study",
        "claim_basis": "studied",
        "level": "provider",
        "resource_requirements": None,
        "workforce_requirements": "additional staff training",
        "anchors": [
            IOFAnchorWire(
                segment_id="s1",
                quote="Training gaps slowed delivery of the programme.",
            )
        ],
    }
    values.update(overrides)
    return ICFRecordWire.model_validate(values)


def profile_counts(
    summary: dict[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return a profile's count block from a Phase-B extraction summary."""
    return cast("dict[str, Any]", summary["counts"]["profiles"][profile_id])


def profile_findings(
    summary: dict[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, int]:
    """Return a profile's finding counters from a Phase-B extraction summary."""
    return cast("dict[str, int]", profile_counts(summary, profile_id)["findings"])


def profile_docs(
    summary: dict[str, Any], profile_id: str = IOF_PROFILE_ID
) -> list[dict[str, Any]]:
    """Return old-style document outcome entries for a profile summary."""
    return [
        {
            "pss_id": doc["pss_id"],
            "basis": doc["basis"],
            **doc["profiles"][profile_id],
        }
        for doc in summary["docs"]
        if profile_id in doc["profiles"]
    ]


def profile_doc(
    summary: dict[str, Any], index: int = 0, profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return one profile-projected document entry from a summary."""
    return profile_docs(summary, profile_id)[index]


def profile_provenance(
    summary: dict[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return a profile's provenance block from a Phase-B extraction summary."""
    return cast("dict[str, Any]", summary["provenance"]["profiles"][profile_id])


def profile_vetted_out(
    summary: dict[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return a profile's vetted-out accounting block from a summary."""
    return cast("dict[str, Any]", summary["profiles"][profile_id]["vetted_out"])


def delete_project_data(conn: Connection, project_id: uuid.UUID) -> None:
    """Delete every row belonging to a project, FK-ordered.

    Used by tests that must genuinely commit (e.g. commit-survival) and then clean up,
    since the rolled-back ``conn`` fixture can't isolate committed rows.

    Args:
        conn: Open database connection.
        project_id: Project whose rows to remove.
    """
    from policy_atlas.core.schema import (
        addressable_unit,
        annotation,
        artefact,
        block,
        capability_run,
        characterisation_result,
        chunk_embedding,
        event_log,
        evidence_scope,
        extraction_result,
        grouping_result,
        implementation_context_finding,
        intervention_outcome_finding,
        orchestration_plan,
        project,
        project_source_snapshot,
        runs,
        search_coverage_record,
        selection_result,
        source_appraisal_result,
        source_classification_result,
        source_extraction_record,
        source_screening_result,
        source_snapshot,
        source_tag,
        synthesis_result,
    )
    from policy_atlas.core.schema import (
        chunk as chunk_table,
    )
    from policy_atlas.core.schema import (
        citation as citation_table,
    )

    # Capture snapshot IDs associated with this project before any deletes.
    # Union of envelope + full-text snapshot ids (plan-review finding 5:
    # full-text snapshots are project-less rows reachable only through the
    # link; capturing only the envelope id orphans them).
    snapshot_ids_set: set[uuid.UUID] = set()
    for env_id, ft_id in conn.execute(
        select(
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
        ).where(project_source_snapshot.c.project_id == project_id)
    ).fetchall():
        snapshot_ids_set.add(env_id)
        if ft_id is not None:
            snapshot_ids_set.add(ft_id)
    snapshot_ids = list(snapshot_ids_set)

    block_ids_subq = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
        )
    )
    annotation_ids_subq = select(annotation.c.annotation_id).where(
        annotation.c.block_id.in_(block_ids_subq)
    )

    # Task 013 row first: FKs onto artefact and all four upstream result tables
    # (characterisation/selection/extraction/grouping) plus scope/runs.
    conn.execute(delete(synthesis_result).where(
        synthesis_result.c.project_id == project_id
    ))
    # citation → annotation → addressable_unit → block (then event_log, artefact, runs)
    conn.execute(delete(citation_table).where(
        citation_table.c.annotation_id.in_(annotation_ids_subq)
    ))
    conn.execute(delete(annotation).where(annotation.c.block_id.in_(block_ids_subq)))
    conn.execute(delete(addressable_unit).where(addressable_unit.c.block_id.in_(block_ids_subq)))
    # Task 012 row: FKs onto extraction_result/scope/runs.
    conn.execute(delete(grouping_result).where(
        grouping_result.c.project_id == project_id
    ))
    # Task 011 rows first: findings FK onto extraction records, which FK onto
    # pss/runs; extraction_result FKs onto scope/runs.
    conn.execute(delete(implementation_context_finding).where(
        implementation_context_finding.c.project_id == project_id
    ))
    conn.execute(delete(intervention_outcome_finding).where(
        intervention_outcome_finding.c.project_id == project_id
    ))
    conn.execute(delete(source_extraction_record).where(
        source_extraction_record.c.project_id == project_id
    ))
    conn.execute(delete(extraction_result).where(
        extraction_result.c.project_id == project_id
    ))
    # Task 009 rows first: tags/characterisation FK onto pss/runs; embeddings FK onto chunk
    conn.execute(delete(source_tag).where(source_tag.c.project_id == project_id))
    # Task 010 row: same FK class as characterisation_result (scope + runs guards).
    conn.execute(delete(selection_result).where(
        selection_result.c.project_id == project_id
    ))
    conn.execute(delete(characterisation_result).where(
        characterisation_result.c.project_id == project_id
    ))
    # source_appraisal_result → source_classification_result → source_screening_result
    # (FK-safe order)
    conn.execute(delete(source_appraisal_result).where(
        source_appraisal_result.c.project_id == project_id
    ))
    conn.execute(delete(source_classification_result).where(
        source_classification_result.c.project_id == project_id
    ))
    conn.execute(delete(source_screening_result).where(
        source_screening_result.c.project_id == project_id
    ))
    conn.execute(delete(search_coverage_record).where(
        search_coverage_record.c.project_id == project_id
    ))
    conn.execute(delete(event_log).where(event_log.c.project_id == project_id))
    conn.execute(
        delete(block).where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
            )
        )
    )
    conn.execute(delete(artefact).where(artefact.c.project_id == project_id))
    # project_source_snapshot before runs: acquired links carry run_id (FK to runs);
    # upload links carry run_id=NULL, which is why the old runs-first order never bit.
    conn.execute(delete(project_source_snapshot).where(
        project_source_snapshot.c.project_id == project_id
    ))
    conn.execute(delete(runs).where(runs.c.project_id == project_id))
    # capability_run after runs (runs.capability_run_id FKs onto it) and before
    # evidence_scope/project (its composite scope FK + project FK target them).
    conn.execute(delete(capability_run).where(capability_run.c.project_id == project_id))
    if snapshot_ids:
        conn.execute(delete(chunk_embedding).where(
            chunk_embedding.c.chunk_id.in_(
                select(chunk_table.c.chunk_id).where(
                    chunk_table.c.source_snapshot_id.in_(snapshot_ids)
                )
            )
        ))
        conn.execute(delete(chunk_table).where(
            chunk_table.c.source_snapshot_id.in_(snapshot_ids)
        ))
        conn.execute(delete(source_snapshot).where(
            source_snapshot.c.source_snapshot_id.in_(snapshot_ids)
        ))
    # orchestration_plan before evidence_scope (fk_oplan_scope_project).
    conn.execute(delete(orchestration_plan).where(
        orchestration_plan.c.project_id == project_id
    ))
    conn.execute(delete(evidence_scope).where(evidence_scope.c.project_id == project_id))
    conn.execute(delete(project).where(project.c.project_id == project_id))


def seed_ingested_full_text(
    conn: Connection,
    *,
    pss_id: uuid.UUID,
    chunks: list[str],
) -> uuid.UUID:
    """Insert an ingested full-text snapshot with chunks + embeddings; link it to ``pss_id``.

    Returns the full-text snapshot id.
    """
    from policy_atlas.core.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, StubEmbeddingBackend
    from policy_atlas.core.hashing import content_hash
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import chunk_embedding, project_source_snapshot, source_snapshot

    full_snapshot_id = uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=full_snapshot_id,
            content_hash=content_hash("\n".join(chunks)),
            text_basis="full_text",
            source_locator=f"full-text-{full_snapshot_id}",
            metadata={"title": "Full text fixture", "abstract": "Full text abstract."},
            created_at=now(),
        )
    )
    conn.execute(
        update(project_source_snapshot)
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
        .values(full_text_snapshot_id=full_snapshot_id, full_text_status="ingested")
    )
    embedder = StubEmbeddingBackend()
    vectors = embedder.embed_texts(chunks)
    for index, content in enumerate(chunks):
        chunk_id = uuid.uuid4()
        conn.execute(
            chunk_table.insert().values(
                chunk_id=chunk_id,
                source_snapshot_id=full_snapshot_id,
                sequence=index,
                content=content,
                content_hash=content_hash(content),
                locator={},
                segmentation_policy="manual_v1",
                created_at=now(),
            )
        )
        conn.execute(
            chunk_embedding.insert().values(
                chunk_embedding_id=uuid.uuid4(),
                chunk_id=chunk_id,
                embedding_profile=EMBEDDING_PROFILE,
                unit_policy=UNIT_POLICY,
                unit_index=0,
                unit_locator={"start": 0, "end": len(content)},
                vector=vectors[index],
                created_at=now(),
            )
        )
    return full_snapshot_id


def seed_source(
    conn: Connection, project_id: uuid.UUID, meta: dict[str, Any] | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert source_snapshot + project_source_snapshot; return (source_snapshot_id, pss_id)."""
    from policy_atlas.core.schema import project_source_snapshot, source_snapshot

    snap_id = uuid.uuid4()
    pss_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=snap_id,
        content_hash=str(uuid.uuid4()),
        text_basis="full_text",
        source_locator="test.pdf",
        metadata=meta or {},
        created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        source_snapshot_id=snap_id,
        origin="uploaded",
        run_id=None,
        ingested_at=now(),
    ))
    return snap_id, pss_id


def seed_scope(
    conn: Connection, project_id: uuid.UUID, context: dict[str, Any] | None = None
) -> uuid.UUID:
    """Insert a evidence_scope; return scope_id."""
    from policy_atlas.core.schema import evidence_scope

    scope_id = uuid.uuid4()
    conn.execute(evidence_scope.insert().values(
        evidence_scope_id=scope_id,
        project_id=project_id,
        intent="Test intent",
        context=context or {},
        created_at=now(),
    ))
    return scope_id


def seed_screening_result(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: str = "relevant",
    *,
    screen_stage: int = 1,
    screen_basis: str = "title_abstract",
    screen_generation: int = 0,
) -> uuid.UUID:
    """Insert a source_screening_result row; return its id.

    ``screen_stage`` defaults to 1; pass 2 to seed a stage-2 row (e.g. a
    demotion or confirmation) atop a doc's stage-1 row. ``screen_generation``
    defaults to the inert 0; pass a higher value to seed a re-screen generation
    (task 024 generation supersession).
    """
    from policy_atlas.core.schema import source_screening_result

    if status == "failed":
        basis = None
        confidence = None
    else:
        basis = screen_basis
        confidence = 0.9 if status == "relevant" else 0.95
    row_id = uuid.uuid4()
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=row_id,
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        screened_by_run_id=run_id,
        status=status,
        screen_basis=basis,
        screen_decision_confidence=confidence,
        screen_stage=screen_stage,
        screen_generation=screen_generation,
        screened_at=now(),
    ))
    return row_id


def seed_project_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a project + running run; return (project_id, run_id).

    Revision-aware: migration roundtrip tests call this at downgraded
    revisions where the 025 lifecycle columns don't exist yet, so the
    lifecycle values are included only when the live table carries them.
    """
    from sqlalchemy import inspect

    from policy_atlas.core.schema import project

    pid = uuid.uuid4()
    values: dict[str, object] = {"project_id": pid, "created_at": now()}
    live_columns = {col["name"] for col in inspect(conn).get_columns("project")}
    if "name" in live_columns:
        values.update(name="Test project", status="active", updated_at=now())
    conn.execute(project.insert().values(**values))
    return pid, seed_run(conn, pid)


def seed_run(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    """Insert an additional running run for an existing project; return run_id."""
    from policy_atlas.core.schema import runs

    rid = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=rid, project_id=project_id, status="running", started_at=now()
        )
    )
    return rid


def seed_select_doc(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    title: str,
    evidence_type: str | None = EVIDENCE_TYPE,
    abstract: str | None = None,
    quality: int | None = 3,
    year: int = 2026,
    origin: str = "uploaded",
    text_basis: str = "full_text",
) -> uuid.UUID:
    """Insert a screened-relevant source ready for select, with optional classification."""
    from policy_atlas.core.schema import (
        project_source_snapshot,
        source_appraisal_result,
        source_classification_result,
        source_snapshot,
    )

    snap_id, pss_id = seed_source(
        conn,
        project_id,
        meta={"title": title, "abstract": abstract or f"Abstract for {title}.", "year": year},
    )
    conn.execute(
        update(project_source_snapshot)
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
        .values(origin=origin)
    )
    conn.execute(
        update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == snap_id)
        .values(text_basis=text_basis)
    )
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    if evidence_type is not None:
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            classified_by_run_id=run_id,
            primary_evidence_type=evidence_type,
            classified_at=now(),
        ))
    if quality is not None:
        conn.execute(source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            appraised_by_run_id=run_id,
            quality_score=quality,
            rubric_version="test-rubric",
            appraised_at=now(),
        ))
    return pss_id


def seed_characterisation(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    themes: dict[str, list[uuid.UUID]],
    unclustered: list[uuid.UUID] | None = None,
) -> None:
    """Insert a characterisation_result row with the given theme membership."""
    from policy_atlas.core.schema import characterisation_result

    conn.execute(characterisation_result.insert().values(
        characterisation_id=uuid.uuid4(),
        project_id=project_id,
        evidence_scope_id=scope_id,
        run_id=run_id,
        grouping_provenance={"backend_mode": "stub"},
        coverage={"base": "screened"},
        themes={
            "themes": [
                {
                    "name": name,
                    "description": f"{name} documents",
                    "member_ids": [str(pss_id) for pss_id in ids],
                    "size": len(ids),
                }
                for name, ids in themes.items()
            ],
            "unclustered_ids": [str(pss_id) for pss_id in (unclustered or [])],
        },
        created_at=now(),
    ))


def run_select(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID,
    *,
    context: dict[str, Any] | None = None,
    backend: Any = None,
) -> tuple[dict[str, Any], Any, uuid.UUID]:
    """Seed a fresh run and execute select_scope; return (summary, persisted row, run_id)."""
    from policy_atlas.core.schema import selection_result
    from policy_atlas.evidence_base.corpus.select import SelectContext, select_scope

    run_id = seed_run(conn, project_id)
    summary = select_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=SelectContext(
            scope_id=scope_id,
            intent="Select the best evidence.",
            context=context or {},
            characterisation_run_id=characterisation_run_id,
        ),
        ranking_backend=backend,
    )
    row = conn.execute(
        select(selection_result)
        .where(selection_result.c.project_id == project_id)
        .where(selection_result.c.run_id == run_id)
    ).one()
    return summary, row, run_id


# --- Search backend/record test doubles ---


def _inverted_index(text: str) -> dict[str, list[int]]:
    """Build an OpenAlex-style abstract_inverted_index from plain text."""
    index: dict[str, list[int]] = {}
    for position, token in enumerate(text.split()):
        index.setdefault(token, []).append(position)
    return index


def oa_record(
    suffix: str | None = None,
    *,
    rid: str | None = None,
    title: str | None = _UNSET,
    abstract: str | None = "relevant evidence abstract",
    index: dict[str, list[int]] | None = _UNSET,
    doi: str | None = None,
    year: int | None = 2020,
    is_oa: bool = False,
    referenced_works: list[str] | None = None,
    source_name: str = "Willow Journal",
) -> dict[str, Any]:
    """Build a sanitized-shape OpenAlex Work record for acquire/search-loop tests.

    Identity: pass ``rid`` for a full record id (acquire-style dedup tests),
    or a bare ``suffix`` for an ``https://openalex.org/W{suffix}`` id
    (search-loop scripted-backend tests); ``rid`` wins if both are given.
    ``title`` defaults to a per-suffix ``"OpenAlex record {suffix}"`` when a
    suffix is given (so scripted multi-record tests get distinct
    dedup-relevant titles), else a fixed placeholder. Pass ``title=None``
    explicitly (not omitted) to exercise the no-title/unusable path.

    Abstract: ``abstract`` (whitespace-tokenized into word positions) builds
    ``abstract_inverted_index`` by default. Pass ``index`` directly — even
    ``None``, to exercise the missing-abstract path — to bypass that.
    """
    if rid is None:
        rid = (
            f"https://openalex.org/W{suffix}"
            if suffix is not None
            else "https://example.org/W1"
        )
    if title is _UNSET:
        title = f"OpenAlex record {suffix}" if suffix is not None else "Quartz meadow lantern"
    if index is _UNSET:
        index = _inverted_index(abstract) if abstract is not None else None
    record: dict[str, Any] = {
        "id": rid,
        "display_name": title,
        "abstract_inverted_index": index,
        "publication_year": year,
        "publication_date": f"{year}-01-01" if year else None,
        "doi": doi,
        "language": "en",
        "type": "article",
        "primary_location": {"source": {"display_name": source_name}},
        "open_access": {"is_oa": is_oa},
        "authorships": [],
    }
    if referenced_works is not None:
        record["referenced_works"] = referenced_works
    return record


class ScriptedGenerationBackend:
    """SearchGenerationBackend double with payload capture.

    ``reformulations``/``suggestions`` left at their ``None`` default means
    the corresponding verb is never expected to be called for this test's
    depth — an unexpected call raises ``AssertionError``. Pass an explicit
    list (even ``[]``) to allow calls; once exhausted, further calls return
    an empty wire result. ``queries`` always falls back to an empty result
    when omitted or exhausted — several deep-loop tests rely on that.
    """

    mode = "scripted"

    def __init__(
        self,
        *,
        queries: list[SearchQueriesWire | BaseException] | None = None,
        reformulations: list[SearchQueriesWire | BaseException] | None = None,
        suggestions: list[SearchSuggestWire | BaseException] | None = None,
    ) -> None:
        self._queries = list(queries or [])
        self._reformulations_allowed = reformulations is not None
        self._reformulations = list(reformulations or [])
        self._suggestions_allowed = suggestions is not None
        self._suggestions = list(suggestions or [])
        self.query_payloads: list[QueriesPayload] = []
        self.reformulate_payloads: list[ReformulatePayload] = []
        self.suggest_payloads: list[SuggestPayload] = []

    @staticmethod
    def _pop_wire[T](queue: list[T | BaseException], fallback: T) -> T:
        item = queue.pop(0) if queue else fallback
        if isinstance(item, BaseException):
            raise item
        return item

    def generate_queries(self, payload: QueriesPayload) -> UsageResult[SearchQueriesWire]:
        self.query_payloads.append(payload)
        return (
            self._pop_wire(
                self._queries,
                SearchQueriesWire(queries=[], overton_paraphrases=[]),
            ),
            None,
        )

    def reformulate(self, payload: ReformulatePayload) -> UsageResult[SearchQueriesWire]:
        if not self._reformulations_allowed:
            raise AssertionError("reformulate was not expected to be called")
        self.reformulate_payloads.append(payload)
        return (
            self._pop_wire(
                self._reformulations,
                SearchQueriesWire(queries=[], overton_paraphrases=[]),
            ),
            None,
        )

    def suggest(self, payload: SuggestPayload) -> UsageResult[SearchSuggestWire]:
        if not self._suggestions_allowed:
            raise AssertionError("suggest was not expected to be called")
        self.suggest_payloads.append(payload)
        return self._pop_wire(self._suggestions, SearchSuggestWire(papers=[])), None
