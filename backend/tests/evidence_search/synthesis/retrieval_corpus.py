"""Load the synthetic retrieval corpus into the test database (task 057 Phase 3).

The corpus lives in ``data/retrieval_synthetic/corpus.json`` as small, readable
records: documents with their screening, classification, appraisal and tags per
evidence scope, and chunks with their embedding units and stub vectors. This
module writes them through the real tables (``source_snapshot``,
``task_source_snapshot``, ``source_screening_result``, the classification,
appraisal and tag tables, ``chunk`` and ``chunk_embedding``), so the retriever
under test reads them exactly as it reads a real run.

Every id is derived from the record's name and keeps the names' sort order
(``a1`` sorts before ``a2``, and so do their ids). The retriever breaks ties on
ids, so a tie in the corpus breaks the same way on every run and reads naturally
in the expected output, which is written in names.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import EMBEDDING_DIMENSIONS, EMBEDDING_PROFILE, UNIT_POLICY
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import (
    chunk,
    chunk_embedding,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
    task_source_snapshot,
)
from policy_atlas.core.tokens import word_tokens
from tests.helpers import now, seed_scope, seed_task_and_run

CORPUS_DIR = Path(__file__).parent / "data" / "retrieval_synthetic"

# One number per kind of id, so ids of different kinds never collide.
_KIND_TSS = 1
_KIND_ENVELOPE = 2
_KIND_FULL_TEXT = 3
_KIND_CHUNK = 4
_KIND_UNIT = 5


def _ordered_id(kind: int, index: int) -> uuid.UUID:
    # The id's text form sorts like (kind, index), which is the names' sort order.
    return uuid.UUID(int=(kind << 64) | (index + 1))


def read_json(name: str) -> dict[str, Any]:
    """Return one JSON file from the corpus folder.

    Args:
        name: The file name, such as ``"corpus.json"``.

    Returns:
        The parsed JSON object.
    """
    loaded: dict[str, Any] = json.loads((CORPUS_DIR / name).read_text())
    return loaded


def dense_vector(sparse: dict[str, float]) -> list[float]:
    """Expand a ``{dimension: value}`` map into a full 1536-number vector.

    Args:
        sparse: The non-zero values keyed by dimension (as a string).

    Returns:
        The full vector, zero everywhere else.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for dimension, value in sparse.items():
        vector[int(dimension)] = float(value)
    return vector


def chunk_content(spec: str | list[Any]) -> str:
    """Build a chunk's text from a string or a list of strings and pads.

    Args:
        spec: A string, or a list whose items are strings or ``{"pad": n}``
            (``n`` characters of ``"x x x"``).

    Returns:
        The chunk text.
    """
    if isinstance(spec, str):
        return spec
    parts: list[str] = []
    for item in spec:
        if isinstance(item, str):
            parts.append(item)
        else:
            parts.append(("x " * item["pad"])[: item["pad"]])
    return "".join(parts)


@dataclass(frozen=True)
class LoadedCorpus:
    """The ids the loader wrote, and the way back from ids to names.

    Attributes:
        task_id: The task every row belongs to.
        scope_ids: Evidence scope id per scope name (``S1``, ``S2``).
        tss_ids: ``task_source_snapshot`` id per document name.
        names: Record name per id string (documents, chunks, units).
        unit_vectors: Each unit's full stub vector, keyed by unit name.
    """

    task_id: uuid.UUID
    scope_ids: dict[str, uuid.UUID]
    tss_ids: dict[str, uuid.UUID]
    names: dict[str, str]
    unit_vectors: dict[str, list[float]]


def load_corpus(conn: Connection, corpus: dict[str, Any] | None = None) -> LoadedCorpus:
    """Write the synthetic corpus into the database through the real tables.

    Args:
        conn: An open connection inside the test's transaction.
        corpus: The corpus records; defaults to ``corpus.json``.

    Returns:
        The written ids and the id-to-name map.
    """
    corpus = corpus if corpus is not None else read_json("corpus.json")
    task_id, run_id = seed_task_and_run(conn)
    base_time = now() - timedelta(hours=2)
    scope_ids = {
        name: seed_scope(conn, task_id, intent=f"scope {name}") for name in corpus["scopes"]
    }
    names: dict[str, str] = {}

    doc_names = sorted(doc["name"] for doc in corpus["documents"])
    tss_ids = {name: _ordered_id(_KIND_TSS, i) for i, name in enumerate(doc_names)}
    envelope_ids = {name: _ordered_id(_KIND_ENVELOPE, i) for i, name in enumerate(doc_names)}
    full_ids = {name: _ordered_id(_KIND_FULL_TEXT, i) for i, name in enumerate(doc_names)}
    for doc in corpus["documents"]:
        name = doc["name"]
        names[str(tss_ids[name])] = name
        conn.execute(source_snapshot.insert().values(
            source_snapshot_id=envelope_ids[name],
            content_hash=f"envelope-{name}",
            text_basis=doc["envelope_basis"],
            source_locator=f"synthetic://{name}",
            metadata={"title": doc["title"], "year": 2020 + doc_names.index(name)},
            created_at=base_time,
        ))
        if doc["full_text"]:
            conn.execute(source_snapshot.insert().values(
                source_snapshot_id=full_ids[name],
                content_hash=f"full-{name}",
                text_basis="full_text",
                source_locator=f"synthetic://{name}/full",
                metadata={},
                created_at=base_time,
            ))
        conn.execute(task_source_snapshot.insert().values(
            task_source_snapshot_id=tss_ids[name],
            task_id=task_id,
            source_snapshot_id=envelope_ids[name],
            origin=doc["origin"],
            run_id=None,
            ingested_at=base_time,
            full_text_snapshot_id=full_ids[name] if doc["full_text"] else None,
            full_text_status="ingested" if doc["full_text"] else "not_attempted",
        ))
        for scope_name, screen in doc["screens"].items():
            scope_id = scope_ids[scope_name]
            screened_at = base_time + timedelta(minutes=screen["minute"])
            conn.execute(source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                task_source_snapshot_id=tss_ids[name],
                task_id=task_id,
                screened_by_run_id=run_id,
                status=screen["status"],
                screen_basis="title_abstract",
                screen_decision_confidence=screen["confidence"],
                screen_stage=1,
                screened_at=screened_at,
            ))
            if screen.get("demoted"):
                conn.execute(source_screening_result.insert().values(
                    source_screening_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    task_source_snapshot_id=tss_ids[name],
                    task_id=task_id,
                    screened_by_run_id=run_id,
                    status="not_relevant",
                    screen_basis="full_text",
                    screen_decision_confidence=0.9,
                    screen_stage=2,
                    screened_at=screened_at + timedelta(seconds=30),
                ))
            if screen.get("evidence_type") is not None:
                conn.execute(source_classification_result.insert().values(
                    source_classification_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    task_source_snapshot_id=tss_ids[name],
                    task_id=task_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type=screen["evidence_type"],
                    classified_at=screened_at,
                ))
            if screen.get("quality") is not None or screen.get("unrated"):
                conn.execute(source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    task_source_snapshot_id=tss_ids[name],
                    task_id=task_id,
                    appraised_by_run_id=run_id,
                    quality_score=None if screen.get("unrated") else screen["quality"],
                    unrated=bool(screen.get("unrated")),
                    rubric_version="synthetic",
                    appraised_at=screened_at,
                ))
        for tag, tag_type in doc["tags"]:
            conn.execute(source_tag.insert().values(
                source_tag_id=uuid.uuid4(),
                task_id=task_id,
                task_source_snapshot_id=tss_ids[name],
                tag=tag,
                tag_type=tag_type,
                asserted_by="characterise",
                created_by_run_id=run_id,
                created_at=base_time,
            ))

    docs_by_name = {doc["name"]: doc for doc in corpus["documents"]}
    chunk_names = sorted(spec["name"] for spec in corpus["chunks"])
    unit_names = sorted(
        f"{spec['name']}u{index}"
        for spec in corpus["chunks"]
        for index in range(len(spec.get("units", [None])))
    )
    sequences: dict[uuid.UUID, int] = {}
    unit_vectors: dict[str, list[float]] = {}
    for spec in corpus["chunks"]:
        doc = docs_by_name[spec["doc"]]
        on_full = spec.get("on", "full" if doc["full_text"] else "envelope") == "full"
        snapshot_id = full_ids[spec["doc"]] if on_full else envelope_ids[spec["doc"]]
        sequence = sequences.get(snapshot_id, 0)
        sequences[snapshot_id] = sequence + 1
        content = chunk_content(spec["content"])
        chunk_id = _ordered_id(_KIND_CHUNK, chunk_names.index(spec["name"]))
        names[str(chunk_id)] = spec["name"]
        conn.execute(chunk.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=snapshot_id,
            sequence=sequence,
            content=content,
            content_hash=content_hash(content),
            locator={},
            segmentation_policy="manual_v1",
            created_at=base_time,
        ))
        units = spec.get("units") or [{"start": 0, "end": -1, "vector": spec["vector"]}]
        for index, unit in enumerate(units):
            unit_name = f"{spec['name']}u{index}"
            unit_id = _ordered_id(_KIND_UNIT, unit_names.index(unit_name))
            names[str(unit_id)] = unit_name
            start = unit["start"]
            end = len(content) if unit["end"] == -1 else unit["end"]
            vector = dense_vector(unit["vector"])
            unit_vectors[unit_name] = vector
            conn.execute(chunk_embedding.insert().values(
                chunk_embedding_id=unit_id,
                chunk_id=chunk_id,
                embedding_profile=EMBEDDING_PROFILE,
                unit_policy=UNIT_POLICY,
                unit_index=index,
                unit_locator={"start": start, "end": end},
                embedding=vector,
                tokens=sorted(word_tokens(content[start:end])),
                created_at=base_time,
            ))
    return LoadedCorpus(
        task_id=task_id,
        scope_ids=scope_ids,
        tss_ids=tss_ids,
        names=names,
        unit_vectors=unit_vectors,
    )
