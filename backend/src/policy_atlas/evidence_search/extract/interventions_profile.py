"""The intervention profile's bundle parts (task 045, ADR 0039 decision 6).

The third extraction profile runs through the shared extract pipeline
(``extract._interventions_profile`` assembles the bundle). What differs from
the IOF and ICF profiles lives here:

- the fingerprint — no windowing knobs (one call per document, title and
  abstract only) and no vetter;
- the grounding — each record's single quote is located in the abstract,
  then the title, by ``quote_verify.locate_unique_span``; a quote that does not
  locate keeps its record with a failed grounding (counted, never dropped);
- the window adapter — the backend answers one response per document with a
  document-level ``covers_no_intervention`` flag, which the adapter carries
  onto each record so it reaches the table;
- the ``intervention_profile_record`` writer.

The profile never reads full text, even when the document has it, so every
record's text basis is ``abstract_only`` by construction; the basis is stored
on the parent ``source_extraction_record`` row (``basis``).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.core.schema import intervention_profile_record
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.extract.extract_interventions_prompt import (
    INTERVENTIONS_MAX_OUTPUT_TOKENS,
    INTERVENTIONS_MODEL,
)
from policy_atlas.evidence_search.extract.extract_interventions_prompt import (
    PROMPT_VERSION as INTERVENTIONS_PROMPT_VERSION,
)
from policy_atlas.evidence_search.extract.extraction_backend import InterventionsBackend
from policy_atlas.evidence_search.extract.interventions_records import (
    INTERVENTIONS_FIELD_RULES_VERSION,
    PROFILE_ID,
    SCHEMA_VERSION,
    InterventionsRecord,
    InterventionsRecordCarrier,
)
from policy_atlas.evidence_search.extract.iof_records import (
    ABSTRACT_SEGMENT_ID,
    ExtractionWindowPayload,
)
from policy_atlas.evidence_search.extract.quote_verify import (
    QUOTE_VERIFIER_VERSION,
    build_basis,
    locate_unique_span,
)

#: The basis segment name for a document's title (the abstract's is
#: ``iof_records.ABSTRACT_SEGMENT_ID``).
TITLE_SEGMENT_ID = "title"

#: What the profile reads; a fingerprint component.
INTERVENTIONS_BASIS = "title_and_abstract"

#: The quote locator; a fingerprint component.
INTERVENTIONS_LOCATOR = "locate_unique_span"


def interventions_fingerprint(mode: str, *, retry_cap: int) -> tuple[str, dict[str, Any]]:
    """Build the intervention profile's fingerprint and component map.

    The ``extraction_fingerprint`` pattern: a full sha256 hex over the
    canonical JSON of every output-affecting knob. No scope intent enters it,
    so one profile of a document serves the longlist scope and every targeted
    scope of the task (A21).

    Args:
        mode: The backend mode (``"live"`` or ``"stub"``).
        retry_cap: The per-call retry cap the shared pipeline applies.

    Returns:
        ``(fingerprint_hex, components)``; ``components`` is recorded verbatim
        in the roll-up's provenance.
    """
    components: dict[str, Any] = {
        "profile": PROFILE_ID,
        "schema": SCHEMA_VERSION,
        "prompt": INTERVENTIONS_PROMPT_VERSION,
        "model": INTERVENTIONS_MODEL,
        "mode": mode,
        "field_rules": INTERVENTIONS_FIELD_RULES_VERSION,
        "verifier": QUOTE_VERIFIER_VERSION,
        "locator": INTERVENTIONS_LOCATOR,
        "basis": INTERVENTIONS_BASIS,
        "max_output_tokens": INTERVENTIONS_MAX_OUTPUT_TOKENS,
        "retry_cap": retry_cap,
        "finding_vetter": None,
    }
    canonical = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), components


def basis_segments(title: str, abstract: str | None) -> list[tuple[str, str]]:
    """The profile's basis: the non-empty title, then the non-empty abstract.

    Args:
        title: The document title (``""`` when absent).
        abstract: The abstract, or ``None``.

    Returns:
        Ordered ``(segment_id, text)`` pairs; empty when both are blank.
    """
    segments: list[tuple[str, str]] = []
    if title.strip():
        segments.append((TITLE_SEGMENT_ID, title))
    if abstract is not None and abstract.strip():
        segments.append((ABSTRACT_SEGMENT_ID, abstract))
    return segments


def ground_interventions_record(
    segments: Sequence[tuple[str | None, str]], record: InterventionsRecord
) -> tuple[list[dict[str, Any]], bool]:
    """Ground one record's quote in the title and abstract.

    The quote is located by ``locate_unique_span`` in the abstract first, then
    in the title, then across the two (a quote spanning the join) — a name
    that the title and the abstract both carry is therefore not ambiguous.
    The entry keeps the qv_v1 grounding keys the IOF/ICF rows use
    (``segment_id``, ``chunk_id``, ``quote``, ``match_status``,
    ``quote_verified``, ``spans``). ``segment_id`` is ``None`` (the model
    claims no location here) and ``chunk_id`` is ``None`` (an envelope basis
    has no chunk, the abstract-basis convention); each span adds ``segment``
    — ``"title"`` or ``"abstract"`` — so its offsets, local to that segment,
    are readable.

    Args:
        segments: The document's basis, ``(segment_id, text)`` pairs from
            :func:`basis_segments`.
        record: The stored record whose quote is located.

    Returns:
        ``([entry], failed)``: one grounding entry, and whether the quote did
        not locate (absent, ambiguous within a segment, or empty).
    """
    ordered = sorted(segments, key=lambda segment: segment[0] != ABSTRACT_SEGMENT_ID)
    candidates = [build_basis([segment]) for segment in ordered]
    if len(segments) > 1:
        candidates.append(build_basis(list(segments)))
    for basis in candidates:
        located = locate_unique_span(basis, record.quote)
        if located is None:
            continue
        start, end = located
        status = "exact" if basis.raw_text[start:end] == record.quote else "normalised"
        spans = [
            {"chunk_id": None, "segment": span.chunk_id, "start": span.start, "end": span.end}
            for span in basis.split_interval(start, end)
        ]
        entry: dict[str, Any] = {
            "segment_id": None,
            "chunk_id": None,
            "quote": record.quote,
            "match_status": status,
            "quote_verified": True,
            "spans": spans,
        }
        return [entry], False
    failed: dict[str, Any] = {
        "segment_id": None,
        "chunk_id": None,
        "quote": record.quote,
        "match_status": "failed",
        "quote_verified": False,
        "spans": [],
    }
    return [failed], True


def write_interventions_record(
    conn: Connection,
    task_id: uuid.UUID,
    record_id: uuid.UUID,
    record: InterventionsRecord,
    grounding: list[dict[str, Any]],
    coverage: dict[str, str],
    created_at: datetime,
) -> None:
    """Write one ``intervention_profile_record`` row.

    Args:
        conn: Open database connection.
        task_id: Owning task.
        record_id: The parent ``source_extraction_record`` id.
        record: The validated, deduplicated record.
        grounding: The record's grounding entries.
        coverage: The record's field-coverage markers.
        created_at: Write timestamp.
    """
    conn.execute(
        intervention_profile_record.insert().values(
            record_id=uuid.uuid4(),
            task_id=task_id,
            extraction_record_id=record_id,
            intervention=record.intervention,
            role=record.role,
            design_features=list(record.design_features),
            is_bundle=record.is_bundle,
            components=list(record.components),
            outcome=record.outcome,
            population=record.population,
            setting=record.setting,
            study_geography=record.study_geography,
            study_design=record.study_design,
            covers_no_intervention=record.covers_no_intervention,
            field_coverage=coverage,
            grounding=grounding,
            created_at=created_at,
        )
    )


@dataclass(frozen=True)
class _CarriedResponse:
    """The adapter's response: the records under the pipeline's ``findings`` name."""

    findings: list[InterventionsRecordCarrier]


class InterventionsWindowAdapter:
    """Presents an :class:`InterventionsBackend` as the shared pipeline's seam.

    The pipeline reads ``response.findings`` per call; the profile answers
    ``records`` plus a document-level ``covers_no_intervention``. The adapter
    carries the flag onto each record and renames nothing else.

    Args:
        backend: The intervention profile backend.
    """

    def __init__(self, backend: InterventionsBackend) -> None:
        self._backend = backend

    @property
    def mode(self) -> str:
        """The wrapped backend's mode."""
        return self._backend.mode

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[_CarriedResponse]:
        """Profile one document and carry the document flag onto each record.

        Args:
            payload: The document's single payload.

        Returns:
            The carried records plus the call's token usage.
        """
        response, usage = self._backend.extract(payload)
        carried = [
            InterventionsRecordCarrier(
                **record.model_dump(),
                covers_no_intervention=response.covers_no_intervention,
            )
            for record in response.records
        ]
        return _CarriedResponse(findings=carried), usage
