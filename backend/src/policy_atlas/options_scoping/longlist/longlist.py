"""The ``longlist`` component: records clustered into options (task 045, S8).

Contract deliverable 6, D4, D5, D8, D10, D11, D14, D16, D20; ADR 0039
decisions 7 and 8. The longlist walk's clustering step:

1. **Units.** The ``intervention_profile_record`` rows of the longlist scope
   and of each option's latest finished add-walk search (a targeted walk with
   no parent; task 046, S3), read through each scope's latest extraction
   roll-up, one extraction per document, minus ``comparator`` records; plus,
   per link whose pinned walk ran ``extract``, the source task's IOF/ICF
   findings of that walk through ``finding_reference_union``
   (D5). Each unit's payload is this component's projection.
   Before clustering the profile records are **thinned** (task 046, S10):
   ``mentioned`` records with no features and no outcome are dropped,
   records of one document with the same folded name collapse to the one of
   the highest role, and at most :data:`RECORDS_PER_DOCUMENT_MAX` records a
   document are kept; each rule's count is in ``provenance.thinning``.
2. **Seeded clustering, the engine untouched** (P8). The seeds are every
   option the task holds — on a first build the entrants ``suggest`` minted
   (and the user's own), on a rebuild every existing option (D14).
   :class:`LonglistClusteringBackend` returns the seeds plus newly
   discovered options from ``discover`` and places each unit under one label
   in ``assign``; :func:`~policy_atlas.evidence_search.clustering_engine.cluster_units`
   runs exactly as characterise runs it. Discovery reads the plan, the
   baseline, the seeds and the **corpus digest** — never a unit record — and
   works to :data:`LONGLIST_TARGET_SIZE`; new options stop at
   :data:`LONGLIST_HARD_CEILING`, seeds included (task 046, R1). It may
   **fold** a suggested seed into a wider option (the existing merge,
   ``merged_into_option_id``); code rejects a fold of a user's option, of a
   user-held one, into an unknown label or into a folded seed, and counts
   each rejection. Assignment prompts carry short unit ids (``u1`` …) that
   code maps back per call.
3. **The residual pass** (task 046, R9): a second ``cluster_units`` call
   over the *unclustered* units only, every option on the list as a seed
   that cannot be folded, its new options bounded by the room left under the
   ceiling; skipped when there is no room or no unclustered unit. Its answers
   replace the first call's for those units. At most once.
4. **Option rows**: seeds keep their rows; each discovered option mints one
   (``origin="clustered"``, design v1 from the discovery wire, its outcomes
   the plan outcomes its members' outcome tags name). No package is minted
   and no ``part_of`` row is written (task 046, item 4). One option per
   record; a document with several records lands in several options.
   Memberships are replaced wholesale by this run's.
5. **Themes** are not built here: the ``theme`` component groups the
   included options after ``constrain`` (task 046, R28); this component
   writes ``themes = []`` and no theme counts.
6. **Typing** is not done here: the ``option_profile`` component types every
   option after this one (task 046, R37, S20). This component writes no
   lever column, no ambition and no typing key; its ``longlist_result`` row
   holds none until ``option_profile`` has run.
7. **Coverage** (:mod:`.coverage`), deterministic, DOI-collapsed.
8. **``longlist_result``**, written last (the 010 pattern).

Every model call happens before the first write, so a failure leaves nothing
behind. User state (``state``, ``exclusion``) is never touched and no option
is ever deleted. A duplicate constrain merged into a kept option
(``merged_into_option_id``) is not a seed and stays merged; discovery may not
re-mint its name.

**How the two buckets pass through the engine.** The assignment prompt may
answer ``not an option`` (the component's own label) or ``ungroupable``.
:class:`LonglistClusteringBackend` hands both to the engine as the policy's
residual label ``unclustered`` and remembers, per unit, which one the model
said; after the engine returns, a residual unit whose last answer was
``not an option`` is counted there, every other residual unit (including one
the engine placed there after repair) as *unclustered*. The engine never
sees the component's label, so its validation is unchanged.
"""

from __future__ import annotations

import re
import threading
import unicodedata
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from pydantic import ValidationError
from sqlalchemy import and_, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    extraction_result,
    finding_reference_union,
    implementation_context_finding,
    intervention_outcome_finding,
    intervention_profile_record,
    longlist_result,
    option,
    option_membership,
    runs,
    source_extraction_record,
    source_snapshot,
    task_link,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.evidence_search.clustering_engine import (
    AssignmentOutput,
    ClusterAssignment,
    ClusteringBackend,
    ClusteringFailure,
    ClusteringPolicy,
    ClusteringResult,
    ClusterLabel,
    ClusterUnit,
    cluster_units,
)
from policy_atlas.evidence_search.extract.extract import (
    EXTRACT_RETRY_CAP,
    record_ids_by_profile,
)
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.interventions_profile import (
    interventions_fingerprint,
)
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.options_scoping.labels import labels_for_snapshots
from policy_atlas.options_scoping.longlist.coverage import (
    ROLE_BUCKETS,
    CoverageMember,
    FoldedSeed,
    document_key,
    normalise_doi,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.longlist_backend import (
    LONGLIST_ASSIGNMENT_MODEL,
    LONGLIST_JUDGMENT_MODEL,
    LonglistBackend,
)
from policy_atlas.options_scoping.longlist.longlist_cluster_prompt import (
    LONGLIST_CLUSTER_PROMPT_VERSION,
    NOT_AN_OPTION_LABEL,
    OPTION_DESCRIPTION_MAX,
    OPTION_LABEL_MAX,
    DiscoveredOptionWire,
)
from policy_atlas.options_scoping.longlist.where_tried import where_codes, where_labels
from policy_atlas.options_scoping.longlist_intent import longlist_plan_data, plan_tagging_context
from policy_atlas.options_scoping.suggest.suggest import baseline_sections, walk_plan
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.scoping_plan import TARGETED_PURPOSE, ScopingPlan

log = structlog.get_logger()

#: The engine's residual label for this component (shown as *unclustered*).
RESIDUAL_LABEL = "unclustered"
#: The prompts' word for "no listed option / theme fits".
MODEL_RESIDUAL_LABEL = "ungroupable"
_RESERVED_LABELS = frozenset(
    label.casefold() for label in (RESIDUAL_LABEL, MODEL_RESIDUAL_LABEL, NOT_AN_OPTION_LABEL)
)

#: Engine policy for the option clustering.
ASSIGNMENT_BATCH_SIZE = 30
DISCOVERY_RETRY_CAP = 1
ASSIGNMENT_REPAIR_CAP = 1
MAX_CONCURRENT_BATCHES = 4

#: The list's target size and hard ceiling, seeds included (task 046, R1).
LONGLIST_TARGET_SIZE = 20
LONGLIST_HARD_CEILING = 25

#: Thinning (task 046, S10): records kept per document, at most.
RECORDS_PER_DOCUMENT_MAX = 8
#: The corpus digest's names, at most (task 046, S8).
DIGEST_NAMES_MAX = 400

#: A unit payload's free-text bound (the quote, a claim, each reference).
UNIT_TEXT_MAX = 240
UNIT_FEATURES_MAX = 8

#: Seeds are offered in entrant order, then the clustered options (D14).
_SEED_ORIGIN_ORDER = ("added_by_you", "from_evidence_search", "suggested", "clustered")

#: The reader's word for a seed's origin, as the discovery prompt reads it.
ORIGIN_WORDS: dict[str, str] = {
    "added_by_you": "added by you",
    "suggested": "suggested by Policy Atlas",
    "from_evidence_search": "from your evidence search",
    "clustered": "on the list",
}
#: The word for every seed of the residual pass, and for any other origin.
ON_THE_LIST = "on the list"

#: The role order thinning keeps by (the highest first).
_ROLE_RANK: dict[str, int] = {role: rank for rank, role in enumerate(ROLE_BUCKETS)}

#: A model-mangled short id ("U1", " u1 ", "1", "u 01") read as ``u<n>``.
_SHORT_ID = re.compile(r"^\s*u?\s*0*(\d+)\s*$", re.IGNORECASE)

UnitKind = Literal["interventions", "iof", "icf"]


def discovery_bounds(seed_count: int) -> tuple[int, int]:
    """The discovery bounds for ``seed_count`` seeds (task 046, R1, AM9).

    Args:
        seed_count: The seeds offered.

    Returns:
        ``(max_new, max_labels)``: new options stop at the hard ceiling,
        seeds included, and every seed is always assigned against.
    """
    max_new = max(LONGLIST_HARD_CEILING - seed_count, 0)
    return max_new, max(seed_count + max_new, seed_count)


class LonglistFailure(Exception):
    """The longlist could not be built (clustering failed or an invariant broke)."""


@dataclass
class LonglistContext:
    """Scope-level input to a ``longlist`` run.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused: the plan is read whole).
        context: Its context JSONB (unused: no directive in this slice).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


# --- units ----------------------------------------------------------------------


@dataclass(frozen=True)
class _Unit:
    unit_id: str
    kind: UnitKind
    record_id: uuid.UUID
    unit_task_id: uuid.UUID
    member_tss_id: uuid.UUID | None  # this task's document row, own records only
    label_tss_id: uuid.UUID | None  # this task's document row for labels (either kind)
    doc_key: str
    role: str | None
    basis: str | None
    population: str | None
    setting: str | None
    outcome: str | None
    study_geography: str | None
    payload: dict[str, object]
    # The record's three tags (task 046), ``None`` when the record was written
    # under another tagging context than the current plan's (S3 a).
    population_tag: str | None = None
    outcome_tag: str | None = None
    object_tag: str | None = None


def _bound(value: object, limit: int = UNIT_TEXT_MAX) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _first_quote(grounding: object) -> str | None:
    if not isinstance(grounding, list):
        return None
    for entry in grounding:
        if isinstance(entry, Mapping):
            quote = _bound(entry.get("quote"))
            if quote:
                return quote
    return None


def _string_list(value: object, *, limit: int = UNIT_FEATURES_MAX) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_bound(item, 120) for item in value]
    return [item for item in items if item][:limit]


def _latest_rollup_record_ids(
    conn: Connection, *, where: Any, profile_ids: Sequence[str]
) -> dict[str, list[uuid.UUID]]:
    """The newest roll-up matching ``where`` that carries any of ``profile_ids``."""
    rows = conn.execute(
        select(extraction_result.c.docs)
        .where(where)
        .order_by(
            extraction_result.c.created_at.desc(),
            extraction_result.c.extraction_result_id.desc(),
        )
    ).all()
    for row in rows:
        docs = row.docs if isinstance(row.docs, list) else []
        by_profile = record_ids_by_profile([d for d in docs if isinstance(d, Mapping)])
        if not any(profile in by_profile for profile in profile_ids):
            continue
        parsed: dict[str, list[uuid.UUID]] = {}
        for profile in profile_ids:
            for raw in by_profile.get(profile, []):
                try:
                    parsed.setdefault(profile, []).append(uuid.UUID(str(raw)))
                except ValueError:
                    log.warning("longlist.rollup_record_id_invalid", profile=profile)
        return parsed
    return {}


def current_profile_fingerprints(
    conn: Connection, *, task_id: uuid.UUID, scope_id: uuid.UUID
) -> frozenset[str]:
    """The intervention-profile fingerprints of the scope plan's tagging context.

    The profile's fingerprint depends on the backend mode, which this
    component does not know, so both modes' fingerprints are returned; a
    record matches when its extraction record carries either (task 046,
    S3 a). The context is built from the plan the intent record names
    (``evidence_scope.plan_id``), as the profile's own harness node builds it;
    a record with no plan gives the context-free fingerprint.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        scope_id: The longlist walk's intent record.

    Returns:
        The fingerprints a record tagged under the current plan carries.
    """
    payload = conn.execute(
        select(task_plan.c.payload)
        .select_from(
            evidence_scope.join(
                task_plan,
                and_(
                    task_plan.c.plan_id == evidence_scope.c.plan_id,
                    task_plan.c.task_id == evidence_scope.c.task_id,
                ),
            )
        )
        .where(
            evidence_scope.c.evidence_scope_id == scope_id,
            evidence_scope.c.task_id == task_id,
        )
    ).scalar_one_or_none()
    context = None
    if payload is not None:
        try:
            plan = validate_plan(OPTIONS_SCOPING, payload)
        except ValidationError:
            log.warning("longlist.scope_plan_invalid", scope_id=str(scope_id))
        else:
            if isinstance(plan, ScopingPlan):
                context = plan_tagging_context(plan)
    return frozenset(
        interventions_fingerprint(mode, retry_cap=EXTRACT_RETRY_CAP, context=context)[0]
        for mode in ("live", "stub")
    )


@dataclass(frozen=True)
class _OwnUnits:
    """What :func:`_own_units` read: the units and the counts of what it left out."""

    units: list[_Unit]
    comparators: int = 0
    superseded: int = 0
    thinning: dict[str, int] = field(default_factory=dict)


def _thin_order(row: Any) -> tuple[int, datetime, str]:
    """Thinning's keep order within a document: role, then profile order (S10)."""
    return (_ROLE_RANK.get(row.role, len(_ROLE_RANK)), row.created_at, str(row.record_id))


def _thin(rows: Sequence[Any]) -> tuple[set[uuid.UUID], dict[str, int]]:
    """The thinning rules of S10 over one union of profile records, in order.

    1. a ``mentioned`` record with no design feature and no outcome is dropped;
    2. records of one document with the same folded intervention name
       collapse to one, the highest role kept (then the earliest, then the
       lowest record id);
    3. at most :data:`RECORDS_PER_DOCUMENT_MAX` records a document are kept,
       by role, then ``created_at``, then ``record_id``.

    No rule reads a tag.

    Args:
        rows: The records, comparators and superseded extractions already
            left out.

    Returns:
        ``(kept record ids, counts per rule)``.
    """
    bare = 0
    survivors: list[Any] = []
    for row in rows:
        if row.role == "mentioned" and not _string_list(row.design_features) and (
            _bound(row.outcome) is None
        ):
            bare += 1
            continue
        survivors.append(row)
    collapsed = 0
    named: set[tuple[uuid.UUID, str]] = set()
    distinct: list[Any] = []
    for row in sorted(survivors, key=_thin_order):
        name = _bound(row.intervention)
        if name is not None:
            doc_name = (row.task_source_snapshot_id, _key(name))
            if doc_name in named:
                collapsed += 1
                continue
            named.add(doc_name)
        distinct.append(row)
    capped = 0
    per_document: dict[uuid.UUID, int] = {}
    kept: set[uuid.UUID] = set()
    for row in sorted(distinct, key=_thin_order):
        held = per_document.get(row.task_source_snapshot_id, 0)
        if held >= RECORDS_PER_DOCUMENT_MAX:
            capped += 1
            continue
        per_document[row.task_source_snapshot_id] = held + 1
        kept.add(row.record_id)
    return kept, {
        "mentioned_without_features_or_outcome": bare,
        "same_name_in_document": collapsed,
        "over_document_cap": capped,
        "document_cap": RECORDS_PER_DOCUMENT_MAX,
    }


def _own_units(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_ids: Sequence[uuid.UUID],
    current_fingerprints: frozenset[str],
) -> _OwnUnits:
    """The profile records of the given scopes, minus comparators, thinned.

    The union of the scopes' latest roll-ups (task 046, S3). A document
    profiled in two scopes counts once: the memo shares one extraction record
    between scopes profiled under the same fingerprint, and when a document
    has records from more than one extraction record (profiled under two
    tagging contexts) only one extraction's records are kept — the one
    written under the current plan's context, else the newest. A record whose
    extraction fingerprint is not in ``current_fingerprints`` reads as "not
    tagged": its tags are ``None`` in the unit and its payload. The thinning
    of S10 (:func:`_thin`) then runs over what that rule keeps.

    Returns:
        The units in document order, the comparator records, the records of
        a document's other extractions (superseded) and the thinning counts.
    """
    record_ids: list[uuid.UUID] = []
    for scope_id in scope_ids:
        ids = _latest_rollup_record_ids(
            conn,
            where=and_(
                extraction_result.c.task_id == task_id,
                extraction_result.c.evidence_scope_id == scope_id,
            ),
            profile_ids=(INTERVENTIONS_PROFILE_ID,),
        )
        record_ids.extend(ids.get(INTERVENTIONS_PROFILE_ID, []))
    if not record_ids:
        return _OwnUnits(units=[], thinning=_thin([])[1])
    ipr = intervention_profile_record
    ser = source_extraction_record
    rows = conn.execute(
        select(
            ipr,
            ser.c.task_source_snapshot_id,
            ser.c.basis,
            ser.c.extraction_fingerprint,
            ser.c.created_at.label("extracted_at"),
            source_snapshot.c.metadata,
        )
        .select_from(
            ipr.join(
                ser,
                and_(
                    ser.c.extraction_record_id == ipr.c.extraction_record_id,
                    ser.c.task_id == ipr.c.task_id,
                ),
            )
            .join(
                task_source_snapshot,
                and_(
                    task_source_snapshot.c.task_source_snapshot_id
                    == ser.c.task_source_snapshot_id,
                    task_source_snapshot.c.task_id == ipr.c.task_id,
                ),
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(ipr.c.task_id == task_id)
        .where(ipr.c.extraction_record_id.in_(set(record_ids)))
        .order_by(ser.c.task_source_snapshot_id, ipr.c.record_id)
    ).all()
    # One extraction per document: the current context's, else the newest.
    chosen: dict[uuid.UUID, tuple[bool, datetime, str]] = {}
    for row in rows:
        rank = (
            row.extraction_fingerprint in current_fingerprints,
            row.extracted_at,
            str(row.extraction_record_id),
        )
        best = chosen.get(row.task_source_snapshot_id)
        if best is None or rank > best:
            chosen[row.task_source_snapshot_id] = rank
    candidates: list[Any] = []
    seen: set[uuid.UUID] = set()
    comparators = 0
    superseded = 0
    for row in rows:
        if row.record_id in seen:
            continue
        seen.add(row.record_id)
        if str(row.extraction_record_id) != chosen[row.task_source_snapshot_id][2]:
            superseded += 1
            continue
        if row.role == "comparator":
            comparators += 1
            continue
        candidates.append(row)
    kept, thinning = _thin(candidates)
    units: list[_Unit] = []
    for row in candidates:
        if row.record_id not in kept:
            continue
        tagged = row.extraction_fingerprint in current_fingerprints
        population_tag = row.population_tag if tagged else None
        outcome_tag = row.outcome_tag if tagged else None
        object_tag = row.object_tag if tagged else None
        unit_id = str(row.record_id)
        payload: dict[str, object] = {
            "unit_id": unit_id,
            "intervention": _bound(row.intervention),
            "role": row.role,
            "design_features": _string_list(row.design_features),
            "outcome": _bound(row.outcome),
            "population": _bound(row.population),
            "setting": _bound(row.setting),
            "study_geography": _bound(row.study_geography),
            "quote": _first_quote(row.grounding),
            "population_tag": population_tag,
            "outcome_tag": outcome_tag,
            "object_tag": object_tag,
        }
        units.append(
            _Unit(
                unit_id=unit_id,
                kind="interventions",
                record_id=row.record_id,
                unit_task_id=task_id,
                member_tss_id=row.task_source_snapshot_id,
                label_tss_id=row.task_source_snapshot_id,
                doc_key=document_key(
                    doi=normalise_doi(row.metadata), document_id=row.task_source_snapshot_id
                ),
                role=row.role,
                basis=row.basis,
                population=row.population,
                setting=row.setting,
                outcome=row.outcome,
                study_geography=row.study_geography,
                payload=payload,
                population_tag=population_tag,
                outcome_tag=outcome_tag,
                object_tag=object_tag,
            )
        )
    return _OwnUnits(
        units=units, comparators=comparators, superseded=superseded, thinning=thinning
    )


#: The role a linked finding's kind implies, for the role funnel and the
#: prompt: an IOF finding reports a studied effect; an ICF finding describes
#: how the intervention was implemented.
_FINDING_ROLE: dict[str, str] = {"iof": "evaluated", "icf": "described"}


def _linked_units(
    conn: Connection, *, task_id: uuid.UUID
) -> tuple[list[_Unit], list[dict[str, Any]]]:
    """Each link's pinned walk's IOF/ICF findings, when that walk ran ``extract`` (D5).

    Returns:
        ``(units, link_provenance)``.
    """
    links = conn.execute(
        select(task_link.c.source_task_id, task_link.c.source_capability_run_id)
        .where(task_link.c.target_task_id == task_id)
        .order_by(task_link.c.created_at, task_link.c.link_id)
    ).all()
    units: list[_Unit] = []
    provenance: list[dict[str, Any]] = []
    seen: set[uuid.UUID] = set()
    for link in links:
        walk_runs = select(runs.c.run_id).where(
            runs.c.capability_run_id == link.source_capability_run_id,
            runs.c.task_id == link.source_task_id,
        )
        by_profile = _latest_rollup_record_ids(
            conn,
            where=and_(
                extraction_result.c.task_id == link.source_task_id,
                extraction_result.c.run_id.in_(walk_runs.scalar_subquery()),
            ),
            profile_ids=(IOF_PROFILE_ID, ICF_PROFILE_ID),
        )
        record_ids = [*by_profile.get(IOF_PROFILE_ID, []), *by_profile.get(ICF_PROFILE_ID, [])]
        link_units = _finding_units(
            conn, task_id=task_id, source_task_id=link.source_task_id, record_ids=record_ids
        )
        link_units = [unit for unit in link_units if unit.record_id not in seen]
        seen.update(unit.record_id for unit in link_units)
        units.extend(link_units)
        provenance.append(
            {
                "source_task_id": str(link.source_task_id),
                "source_run_id": str(link.source_capability_run_id),
                "ran_extract": bool(by_profile),
                "findings": len(link_units),
            }
        )
    return units, provenance


def _finding_units(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    source_task_id: uuid.UUID,
    record_ids: Sequence[uuid.UUID],
) -> list[_Unit]:
    if not record_ids:
        return []
    fru = finding_reference_union
    source_tss = task_source_snapshot.alias("source_tss")
    rows = conn.execute(
        select(
            fru,
            source_extraction_record.c.basis,
            source_tss.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .select_from(
            fru.join(
                source_extraction_record,
                and_(
                    source_extraction_record.c.extraction_record_id == fru.c.extraction_record_id,
                    source_extraction_record.c.task_id == fru.c.task_id,
                ),
            )
            .join(
                source_tss,
                and_(
                    source_tss.c.task_source_snapshot_id
                    == source_extraction_record.c.task_source_snapshot_id,
                    source_tss.c.task_id == fru.c.task_id,
                ),
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == source_tss.c.source_snapshot_id,
            )
        )
        .where(fru.c.task_id == source_task_id)
        .where(fru.c.kind.in_(("iof", "icf")))
        .where(fru.c.extraction_record_id.in_(set(record_ids)))
        .order_by(fru.c.extraction_record_id, fru.c.finding_id)
    ).all()
    if not rows:
        return []
    finding_ids = [row.finding_id for row in rows]
    iof_details = {
        row.finding_id: row
        for row in conn.execute(
            select(
                intervention_outcome_finding.c.finding_id,
                intervention_outcome_finding.c.effect_direction,
                intervention_outcome_finding.c.grounding,
            )
            .where(intervention_outcome_finding.c.task_id == source_task_id)
            .where(intervention_outcome_finding.c.finding_id.in_(finding_ids))
        )
    }
    icf_details = {
        row.finding_id: row
        for row in conn.execute(
            select(
                implementation_context_finding.c.finding_id,
                implementation_context_finding.c.claim,
                implementation_context_finding.c.grounding,
            )
            .where(implementation_context_finding.c.task_id == source_task_id)
            .where(implementation_context_finding.c.finding_id.in_(finding_ids))
        )
    }
    # The same document in this task (inherit copied it): its labels are ours.
    own_tss = {
        row.source_snapshot_id: row.task_source_snapshot_id
        for row in conn.execute(
            select(
                task_source_snapshot.c.source_snapshot_id,
                task_source_snapshot.c.task_source_snapshot_id,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(
                task_source_snapshot.c.source_snapshot_id.in_(
                    {row.source_snapshot_id for row in rows}
                )
            )
        )
    }
    units: list[_Unit] = []
    for row in rows:
        unit_id = str(row.finding_id)
        role = _FINDING_ROLE[row.kind]
        payload: dict[str, object] = {
            "unit_id": unit_id,
            "kind": "effect finding" if row.kind == "iof" else "implementation finding",
            "intervention": _bound(row.intervention),
            "role": role,
            "outcome": _bound(row.outcome),
            "population": _bound(row.population),
            "setting": _bound(row.setting),
            "study_geography": _bound(row.study_geography),
            "study_design": _bound(row.study_design),
        }
        if row.kind == "iof" and row.finding_id in iof_details:
            detail = iof_details[row.finding_id]
            payload["effect_direction"] = detail.effect_direction
            payload["quote"] = _first_quote(detail.grounding)
        elif row.kind == "icf" and row.finding_id in icf_details:
            detail = icf_details[row.finding_id]
            payload["claim"] = _bound(detail.claim)
            payload["quote"] = _first_quote(detail.grounding)
        own = own_tss.get(row.source_snapshot_id)
        units.append(
            _Unit(
                unit_id=unit_id,
                kind=row.kind,
                record_id=row.finding_id,
                unit_task_id=source_task_id,
                member_tss_id=None,
                label_tss_id=own,
                doc_key=document_key(
                    doi=normalise_doi(row.metadata),
                    document_id=own if own is not None else row.source_snapshot_id,
                ),
                role=role,
                basis=row.basis,
                population=row.population,
                setting=row.setting,
                outcome=row.outcome,
                study_geography=row.study_geography,
                payload=payload,
            )
        )
    return units


# --- seeds ----------------------------------------------------------------------


@dataclass(frozen=True)
class _Seed:
    option_id: uuid.UUID
    label: str
    description: str
    design_features: list[str]
    origin: str = "clustered"
    #: The user set this option's state (``exclusion.by == "user"``).
    user_held: bool = False
    name: str = ""
    outcomes: list[str] = field(default_factory=list)

    def as_data(self, origin: str) -> dict[str, object]:
        return {
            "label": self.label,
            "description": self.description,
            "design_features": self.design_features,
            "origin": origin,
        }


def _clean_label_text(value: str, limit: int) -> str:
    text = "".join(ch for ch in value if not unicodedata.category(ch).startswith("C"))
    text = " ".join(text.split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _seeds(conn: Connection, *, task_id: uuid.UUID) -> list[_Seed]:
    """Every option of the task as a seed, labels made engine-valid and unique.

    A duplicate constrain merged into a kept option is not a seed: it stays
    merged (its name is a :func:`_merged_names` entry instead).
    """
    # Imported here: ``constrain`` imports this module.
    from policy_atlas.options_scoping.constrain.constrain import user_holds_state

    rows = conn.execute(
        select(
            option.c.option_id,
            option.c.name,
            option.c.description,
            option.c.design,
            option.c.origin,
            option.c.exclusion,
            option.c.created_at,
        )
        .where(option.c.task_id == task_id)
        .where(option.c.merged_into_option_id.is_(None))
    ).all()
    order = {origin: index for index, origin in enumerate(_SEED_ORIGIN_ORDER)}
    rows = sorted(
        rows, key=lambda r: (order.get(r.origin, len(order)), r.created_at, str(r.option_id))
    )
    seeds: list[_Seed] = []
    taken = set(_RESERVED_LABELS)
    for row in rows:
        base = _clean_label_text(row.name, OPTION_LABEL_MAX) or "Option"
        label = base
        suffix = 2
        while label.casefold() in taken:
            tail = f" ({suffix})"
            label = f"{base[: OPTION_LABEL_MAX - len(tail)]}{tail}"
            suffix += 1
        taken.add(label.casefold())
        description = _clean_label_text(row.description, OPTION_DESCRIPTION_MAX) or label
        try:
            design = OptionDesign.model_validate(row.design)
        except ValidationError:
            log.warning("longlist.seed_design_invalid", option_id=str(row.option_id))
            features: list[str] = []
            outcomes: list[str] = []
        else:
            features = list(design.design_features)
            outcomes = list(design.outcomes_served)
        seeds.append(
            _Seed(
                option_id=row.option_id,
                label=label,
                description=description,
                design_features=features,
                origin=row.origin,
                user_held=user_holds_state(row.exclusion),
                name=row.name,
                outcomes=outcomes,
            )
        )
    return seeds


def _merged_names(conn: Connection, *, task_id: uuid.UUID) -> list[str]:
    """The names of the task's merged duplicates, which discovery must not re-mint."""
    return list(
        conn.execute(
            select(option.c.name)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_not(None))
        ).scalars()
    )


# --- the engine's backends ------------------------------------------------------


@dataclass(frozen=True)
class _Answer:
    kind: Literal["option", "not_an_option", "unclustered"]
    label: str
    reason: str | None
    design_feature_not_stated: bool


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def corpus_digest(
    entries: Iterable[tuple[object, object]], *, limit: int = DIGEST_NAMES_MAX
) -> tuple[list[dict[str, object]], int]:
    """The corpus digest: each folded intervention name with its record counts (S8).

    Built by code from the units, in place of every unit record: one entry
    per folded name (whitespace collapsed, case folded) with its record count
    and its counts by role, by records descending then name, at most
    ``limit`` names. The name shown is the name's most frequent spelling
    (then the shortest, then the first alphabetically). A unit with no name
    is left out.

    Args:
        entries: ``(intervention, role)`` per unit.
        limit: The names kept, at most.

    Returns:
        ``(digest, distinct names)``: each entry ``{"name", "records",
        "roles"}``, ``roles`` in role order with zero counts left out; and
        the number of distinct names before the limit.
    """
    records: dict[str, int] = {}
    roles: dict[str, dict[str, int]] = {}
    spellings: dict[str, dict[str, int]] = {}
    for intervention, role in entries:
        name = _bound(intervention)
        if name is None:
            continue
        key = _key(name)
        records[key] = records.get(key, 0) + 1
        by_role = roles.setdefault(key, {})
        if isinstance(role, str) and role in _ROLE_RANK:
            by_role[role] = by_role.get(role, 0) + 1
        spelled = spellings.setdefault(key, {})
        spelled[name] = spelled.get(name, 0) + 1
    shown = {
        key: min(counts, key=lambda text: (-counts[text], len(text), text))
        for key, counts in spellings.items()
    }
    ordered = sorted(records, key=lambda key: (-records[key], shown[key]))
    digest: list[dict[str, object]] = [
        {
            "name": shown[key],
            "records": records[key],
            "roles": {role: roles[key][role] for role in ROLE_BUCKETS if role in roles[key]},
        }
        for key in ordered[:limit]
    ]
    return digest, len(records)


def _short_id(raw: str, short: Mapping[str, str]) -> tuple[str, bool]:
    """Map a returned short id back to its unit id (S9).

    A mangled short id ("U1", " u1 ", "1") is read as ``u<n>`` when that is
    an id of this call; an id not of this call goes to the engine as it came
    (an unknown id, which the engine's repair path handles).

    Returns:
        ``(unit id or the raw id, repaired)``.
    """
    if raw in short:
        return short[raw], False
    match = _SHORT_ID.match(raw)
    if match is not None:
        candidate = f"u{int(match.group(1))}"
        if candidate in short:
            return short[candidate], True
    return raw, False


@dataclass(frozen=True)
class _Fold:
    seed: _Seed
    into_label: str


class LonglistClusteringBackend(ClusteringBackend):
    """The engine's backend for seeded option clustering (P8; task 046, S8, S9).

    ``discover`` returns the seeds that are not folded, followed by the
    options the model discovers beyond them (one call over the plan, the
    baseline, the seeds and the corpus digest — never a unit record —
    ``max_new = max_labels - len(seeds)``); the discovered options' full wire
    is kept on the side by label, the accepted folds by seed. New options
    over ``max_new``, restated seeds and repeated labels are dropped and
    counted. ``assign`` sends each batch under short ids (``u1`` …, a map
    built per call), maps the answers back, returns ``unit_id → label`` to
    the engine and keeps the reason and ``design_feature_not_stated`` on the
    side by unit id; the component's ``not an option`` and the prompt's
    ``ungroupable`` reach the engine as its residual label, the difference
    remembered here.

    Args:
        backend: The model seam.
        plan: The plan fields as data, place stripped.
        baseline: The baseline's ``(title, markdown)`` sections.
        seeds: The seed options, in offer order.
        retired: Names a discovered option may not restate either (the
            merged duplicates'); dropped like a restated seed.
        residual: The residual pass: every seed is "on the list" and no fold
            is accepted.
    """

    def __init__(
        self,
        backend: LonglistBackend,
        *,
        plan: dict[str, object],
        baseline: list[tuple[str, str]],
        seeds: list[_Seed],
        retired: Sequence[str] = (),
        residual: bool = False,
    ) -> None:
        self._backend = backend
        self._plan = plan
        self._baseline = baseline
        self._seeds = seeds
        self._residual = residual
        self._seed_keys = {_key(seed.label) for seed in seeds} | {_key(n) for n in retired}
        self._lock = threading.Lock()
        self.discovered: dict[str, DiscoveredOptionWire] = {}
        self.folds: dict[uuid.UUID, _Fold] = {}
        self.rejected_folds: list[dict[str, str]] = []
        self.answers: dict[str, _Answer] = {}
        self.restated_seeds_dropped = 0
        self.repeated_labels_dropped = 0
        self.over_ceiling_dropped = 0
        self.short_id_repairs = 0
        self.max_new = 0
        self.called = False
        self.digest: dict[str, int] = {}

    def _origin(self, seed: _Seed) -> str:
        if self._residual:
            return ON_THE_LIST
        return ORIGIN_WORDS.get(seed.origin, ON_THE_LIST)

    def _foldable(self) -> bool:
        return not self._residual and any(
            seed.origin != "added_by_you" and not seed.user_held for seed in self._seeds
        )

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        """Return the seeds not folded plus newly discovered options.

        The call is made when a new option is allowed or a seed can be
        folded; the seeds alone come back otherwise.

        Args:
            units: The units, in deterministic order (read for the digest only).
            min_labels: The policy's minimum (unused: the prompt has none).
            max_labels: The policy's ceiling, counting the seeds.

        Returns:
            Seed labels then discovered labels, and the call's usage.
        """
        del min_labels
        self.discovered = {}
        self.folds = {}
        self.rejected_folds = []
        self.restated_seeds_dropped = 0
        self.repeated_labels_dropped = 0
        self.over_ceiling_dropped = 0
        self.max_new = max(max_labels - len(self._seeds), 0)
        digest, names = corpus_digest(
            (unit.payload.get("intervention"), unit.payload.get("role")) for unit in units
        )
        self.digest = {"units": len(units), "names": names, "shown": len(digest)}
        if self.max_new == 0 and not self._foldable():
            return self._labels(), None
        self.called = True
        response, usage = self._backend.discover(
            plan=self._plan,
            baseline_sections=self._baseline,
            seeds=[seed.as_data(self._origin(seed)) for seed in self._seeds],
            digest=digest,
            target_size=LONGLIST_TARGET_SIZE,
            max_new=self.max_new,
            residual=self._residual,
        )
        taken: set[str] = set()
        for wire in response.options:
            label = wire.label.strip()
            key = _key(label)
            if key in self._seed_keys:
                self.restated_seeds_dropped += 1
                continue
            if key in taken:
                self.repeated_labels_dropped += 1
                continue
            if len(self.discovered) >= self.max_new:
                self.over_ceiling_dropped += 1
                continue
            taken.add(key)
            self.discovered[label] = wire
        for fold in response.folds:
            self._fold(fold.seed_label, fold.into_label)
        return self._labels(), usage

    def _fold(self, seed_label: str, into_label: str) -> None:
        """Accept one fold, or record why it is rejected (the four guards, S8)."""
        seeds = {_key(seed.label): seed for seed in self._seeds}
        new = {_key(label): label for label in self.discovered}
        seed = seeds.get(_key(seed_label))
        target_key = _key(into_label)
        folded = {fold.seed.option_id for fold in self.folds.values()}
        targets = {_key(fold.into_label) for fold in self.folds.values()}
        reason: str | None = None
        if self._residual:
            reason = "residual_pass"
        elif seed is None:
            reason = "unknown_seed"
        elif seed.origin == "added_by_you":
            reason = "added_by_you"
        elif seed.user_held:
            reason = "user_held"
        elif target_key == _key(seed.label):
            reason = "into_itself"
        elif target_key not in seeds and target_key not in new:
            reason = "unknown_target"
        elif seed.option_id in folded:
            reason = "already_folded"
        elif target_key in seeds and seeds[target_key].option_id in folded:
            reason = "into_folded_seed"
        elif _key(seed.label) in targets:
            reason = "seed_is_fold_target"
        if reason is not None or seed is None:
            self.rejected_folds.append(
                {"seed_label": seed_label, "into_label": into_label, "reason": reason or ""}
            )
            return
        target = seeds[target_key].label if target_key in seeds else new[target_key]
        self.folds[seed.option_id] = _Fold(seed=seed, into_label=target)

    def _labels(self) -> list[ClusterLabel]:
        labels = [
            ClusterLabel(label=seed.label, description=seed.description)
            for seed in self._seeds
            if seed.option_id not in self.folds
        ]
        labels.extend(
            ClusterLabel(label=label, description=wire.description)
            for label, wire in self.discovered.items()
        )
        return labels

    def _option_data(self, label: ClusterLabel) -> dict[str, object]:
        wire = self.discovered.get(label.label)
        if wire is not None:
            return {
                "label": label.label,
                "description": label.description,
                "design_features": list(wire.design_features),
            }
        seed = next((s for s in self._seeds if s.label == label.label), None)
        return {
            "label": label.label,
            "description": label.description,
            "design_features": seed.design_features if seed is not None else [],
        }

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        """Assign one batch under short ids; the component's labels become the engine's residual.

        Args:
            batch: The batch's units.
            labels: The validated labels (seeds and discovered).

        Returns:
            One assignment per answered unit, keyed by the unit's id after
            mapping back (duplicates kept, so the engine sees conflicts), and
            the call's usage.
        """
        short = {f"u{index}": unit.unit_id for index, unit in enumerate(batch, start=1)}
        records = [
            {"unit_id": sid, **{k: v for k, v in unit.payload.items() if k != "unit_id"}}
            for sid, unit in zip(short, batch, strict=True)
        ]
        response, usage = self._backend.assign(
            options=[self._option_data(label) for label in labels],
            records=records,
        )
        by_key = {_key(label.label): label.label for label in labels}
        not_an_option = _key(NOT_AN_OPTION_LABEL)
        residual_keys = {_key(MODEL_RESIDUAL_LABEL), _key(RESIDUAL_LABEL)}
        known = set(short.values())
        assignments: list[ClusterAssignment] = []
        with self._lock:
            for wire in response.assignments:
                unit_id, repaired = _short_id(wire.unit_id, short)
                self.short_id_repairs += int(repaired)
                raw = _key(wire.option_label)
                if raw == not_an_option:
                    answer = _Answer("not_an_option", RESIDUAL_LABEL, wire.reason, False)
                elif raw in residual_keys:
                    answer = _Answer("unclustered", RESIDUAL_LABEL, wire.reason, False)
                else:
                    label = by_key.get(raw, wire.option_label)
                    answer = _Answer("option", label, wire.reason, wire.design_feature_not_stated)
                if unit_id in known:
                    self.answers[unit_id] = answer
                assignments.append(ClusterAssignment(unit_id=unit_id, label=answer.label))
        return assignments, usage


def _forbidden_label(noun: str) -> Any:
    def _reason(index: int, label: str) -> str | None:
        if label.casefold() in _RESERVED_LABELS:
            return f"{noun} {index} name collides with a reserved label"
        return None

    return _reason


def _option_policy(max_labels: int) -> ClusteringPolicy:
    return ClusteringPolicy(
        min_labels=0,
        max_labels=max_labels,
        assignment_batch_size=ASSIGNMENT_BATCH_SIZE,
        discovery_retry_cap=DISCOVERY_RETRY_CAP,
        assignment_repair_cap=ASSIGNMENT_REPAIR_CAP,
        residual_label=RESIDUAL_LABEL,
        unresolved_policy="residual",
        label_max=OPTION_LABEL_MAX,
        description_max=OPTION_DESCRIPTION_MAX,
        forbidden_label_reason=_forbidden_label("option"),
        label_noun="option",
        log_event_prefix="longlist",
        max_concurrent_batches=MAX_CONCURRENT_BATCHES,
    )


def _engine_stats(result: ClusteringResult | None) -> dict[str, Any]:
    if result is None:
        return {"ran": False}
    return {
        "ran": True,
        "calls_used": result.calls_used,
        "call_budget": {
            "batch_count": result.call_budget.batch_count,
            "baseline": result.call_budget.baseline,
            "maximum": result.call_budget.maximum,
        },
        "discovery_retries_used": result.discovery_retries_used,
        "assignment_repair_calls_used": result.assignment_repair_calls_used,
        "discovery_rejections": result.discovery_rejections,
        "rejection_reasons": result.rejection_reasons,
        "usage_totals": result.usage_totals,
    }


# --- options ---------------------------------------------------------------


@dataclass
class _Option:
    option_id: uuid.UUID
    label: str
    description: str
    design_features: list[str]
    outcomes: list[str]
    seed: bool
    wire: DiscoveredOptionWire | None = None
    design: OptionDesign | None = None
    members: list[_Unit] = field(default_factory=list)


def _member_outcomes(members: Sequence[_Unit], plan_outcomes: Sequence[str]) -> list[str]:
    """The plan outcomes the members' outcome tags name, in plan order (S11).

    ``other`` and a tag that names no plan outcome are left out; empty when no
    member has a plan outcome.
    """
    tags = {_key(unit.outcome_tag) for unit in members if unit.outcome_tag}
    return [outcome for outcome in plan_outcomes if _key(outcome) in tags]


def _discovered_design(
    label: str, wire: DiscoveredOptionWire, outcomes: list[str]
) -> OptionDesign:
    """Design v1 from the discovery wire and the members' outcomes (S11).

    A wire with no feature keeps its description as the one feature.
    """
    features = [f for f in (_bound(item, 2_000) for item in wire.design_features) if f]
    description = _bound(wire.description, 2_000) or label
    try:
        return OptionDesign(
            name=label,
            description=description,
            design_features=features or [description],
            outcomes_served=outcomes,
            assumed=[],
        )
    except ValidationError:
        log.warning("longlist.discovered_design_invalid")
        return OptionDesign(
            name=label,
            description=label,
            design_features=[label],
            outcomes_served=outcomes,
            assumed=[],
        )


# --- the component -----------------------------------------------------------------


def _walk_ref(
    conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID, scope_id: uuid.UUID
) -> tuple[uuid.UUID | None, int]:
    """This run's walk and its plan version (else the intent record's plan version)."""
    row = conn.execute(
        select(capability_run.c.capability_run_id, capability_run.c.plan_version)
        .select_from(
            runs.join(
                capability_run,
                and_(
                    capability_run.c.capability_run_id == runs.c.capability_run_id,
                    capability_run.c.task_id == runs.c.task_id,
                ),
            )
        )
        .where(runs.c.run_id == run_id, runs.c.task_id == task_id)
    ).one_or_none()
    if row is not None:
        return row.capability_run_id, int(row.plan_version)
    version = conn.execute(
        select(task_plan.c.version)
        .select_from(
            evidence_scope.join(
                task_plan,
                and_(
                    task_plan.c.plan_id == evidence_scope.c.plan_id,
                    task_plan.c.task_id == evidence_scope.c.task_id,
                ),
            )
        )
        .where(
            evidence_scope.c.evidence_scope_id == scope_id,
            evidence_scope.c.task_id == task_id,
        )
    ).scalar_one_or_none()
    if version is None:
        raise LonglistFailure("longlist: no plan version found for the walk")
    return None, int(version)


def _option_search_scopes(conn: Connection, *, task_id: uuid.UUID) -> list[uuid.UUID]:
    """Each option's latest finished add-walk search on this task.

    One targeted scope per option: the latest ``succeeded`` or ``degraded``
    walk with **no parent** under a ``targeted`` record naming it — the verb
    *add*'s search (task 046, S3, AM5). A longlist walk's option searches only
    acquire; the longlist scope screens and profiles their documents, so
    their scopes supply no units — and an old full-chain child of a build
    before this slice would supply a document a second time.
    """
    walks = conn.execute(
        select(
            capability_run.c.evidence_scope_id,
            evidence_scope.c.context["option_id"].astext.label("option_id"),
        )
        .select_from(
            capability_run.join(
                evidence_scope,
                and_(
                    evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
                    evidence_scope.c.task_id == capability_run.c.task_id,
                ),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(evidence_scope.c.purpose == TARGETED_PURPOSE)
        .where(capability_run.c.parent_capability_run_id.is_(None))
        .where(capability_run.c.status.in_(("succeeded", "degraded")))
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
    ).all()
    latest: dict[str, uuid.UUID] = {}
    for walk in walks:
        if walk.option_id is not None:
            latest.setdefault(walk.option_id, walk.evidence_scope_id)
    return list(reversed(list(latest.values())))


def _coverage_member(unit: _Unit, *, flagged: bool) -> CoverageMember:
    """One unit as coverage reads it, its tag and intervention name included."""
    intervention = unit.payload.get("intervention")
    return CoverageMember(
        unit_kind=unit.kind,
        doc_key=unit.doc_key,
        tss_id=unit.label_tss_id,
        role=unit.role,
        basis=unit.basis,
        flagged=flagged,
        population=unit.population,
        setting=unit.setting,
        outcome=unit.outcome,
        study_geography=unit.study_geography,
        intervention=intervention if isinstance(intervention, str) else None,
        population_tag=unit.population_tag,
        outcome_tag=unit.outcome_tag if unit.kind == "interventions" else None,
    )


def _folded_seeds(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_ids: Sequence[uuid.UUID],
    documents_of: Mapping[uuid.UUID, set[str]],
) -> dict[uuid.UUID, list[FoldedSeed]]:
    """The options folded into each of ``option_ids`` (task 046, AM20).

    A folded seed is an option merged into the wider one
    (``merged_into_option_id``) that the user did not name (origin not
    ``added_by_you``). Its variant entry carries its name and its own member
    documents, 0 when it has none.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The wider options.
        documents_of: The document keys of each option's members, as they
            stand for this read.

    Returns:
        ``{option_id: [FoldedSeed, ...]}``; an option with none is absent.
    """
    if not option_ids:
        return {}
    folded: dict[uuid.UUID, list[FoldedSeed]] = {}
    for row in conn.execute(
        select(option.c.option_id, option.c.name, option.c.merged_into_option_id)
        .where(option.c.task_id == task_id)
        .where(option.c.merged_into_option_id.in_(list(option_ids)))
        .where(option.c.origin != "added_by_you")
        .order_by(option.c.option_id)
    ):
        folded.setdefault(row.merged_into_option_id, []).append(
            FoldedSeed(name=row.name, documents=len(documents_of.get(row.option_id, set())))
        )
    return folded


def membership_coverage(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    where: str,
    option_ids: Sequence[uuid.UUID],
    plan_outcomes: Sequence[str] = (),
) -> dict[str, dict[str, Any]]:
    """The options' coverage recomputed from their membership rows as they stand.

    For constrain's *distinct* merge, which moves a duplicate's memberships
    to the kept option after the build wrote its coverage. The units are
    loaded exactly as :func:`longlist_scope` loads them (the walk's scope,
    the add-walk searches, the links); a membership whose unit no longer loads
    is skipped.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        scope_id: The longlist walk's intent record.
        where: The plan's *where* text (the home group).
        option_ids: The options to recompute.
        plan_outcomes: The plan's outcome texts, in plan order (R42).

    Returns:
        ``{option_id: coverage}`` for each of ``option_ids``.
    """
    search_scopes = _option_search_scopes(conn, task_id=task_id)
    own = _own_units(
        conn,
        task_id=task_id,
        scope_ids=[scope_id, *search_scopes],
        current_fingerprints=current_profile_fingerprints(
            conn, task_id=task_id, scope_id=scope_id
        ),
    ).units
    linked, _ = _linked_units(conn, task_id=task_id)
    by_key = {(u.kind, u.record_id): u for u in own + linked}
    members: dict[uuid.UUID, list[tuple[_Unit, bool]]] = {oid: [] for oid in option_ids}
    # Every option's member documents as they stand, so a folded seed's own
    # documents are counted too.
    documents_of: dict[uuid.UUID, set[str]] = {}
    for row in conn.execute(
        select(
            option_membership.c.option_id,
            option_membership.c.unit_kind,
            option_membership.c.unit_id,
            option_membership.c.design_feature_not_stated,
        ).where(option_membership.c.task_id == task_id)
    ):
        unit = by_key.get((row.unit_kind, row.unit_id))
        if unit is None:
            continue
        documents_of.setdefault(row.option_id, set()).add(unit.doc_key)
        if row.option_id in members:
            members[row.option_id].append((unit, bool(row.design_feature_not_stated)))
    labels = labels_for_snapshots(
        conn,
        task_id=task_id,
        tss_ids={u.label_tss_id for ms in members.values() for u, _ in ms if u.label_tss_id},
    )
    home = where_codes(where)
    folded = _folded_seeds(
        conn, task_id=task_id, option_ids=list(members), documents_of=documents_of
    )
    return {
        str(oid): option_coverage(
            [_coverage_member(u, flagged=flagged) for u, flagged in ms],
            labels=labels,
            home=home,
            folded_seeds=folded.get(oid, ()),
            plan_outcomes=plan_outcomes,
        )
        for oid, ms in members.items()
    }


def _title_only(conn: Connection, *, task_id: uuid.UUID, scope_id: uuid.UUID) -> int:
    """The title-only documents the scope's latest extraction left unprofiled (S10)."""
    counts = conn.execute(
        select(extraction_result.c.counts)
        .where(extraction_result.c.task_id == task_id)
        .where(extraction_result.c.evidence_scope_id == scope_id)
        .order_by(
            extraction_result.c.created_at.desc(),
            extraction_result.c.extraction_result_id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    value = counts.get("title_only") if isinstance(counts, Mapping) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _cluster(
    units: Sequence[_Unit], backend: LonglistClusteringBackend, max_labels: int
) -> ClusteringResult | None:
    """One ``cluster_units`` call over ``units``; ``None`` when there is none."""
    if not units:
        return None
    return cluster_units(
        [ClusterUnit(unit_id=u.unit_id, payload=u.payload) for u in units],
        backend=backend,
        policy=_option_policy(max_labels),
    )


def _new_options(
    clustering: ClusteringResult | None,
    backend: LonglistClusteringBackend,
    by_label: Mapping[str, _Option],
) -> list[_Option]:
    """The options this clustering discovered, one row each, in label order."""
    if clustering is None:
        return []
    minted: list[_Option] = []
    for label in clustering.labels:
        wire = backend.discovered.get(label.label)
        if wire is None or label.label in by_label:
            continue
        minted.append(
            _Option(
                option_id=uuid.uuid4(),
                label=label.label,
                description=label.description,
                design_features=[
                    f for f in (_bound(item, 2_000) for item in wire.design_features) if f
                ],
                outcomes=[],
                seed=False,
                wire=wire,
            )
        )
    return minted


def _placements(
    units: Sequence[_Unit],
    clustering: ClusteringResult | None,
    answers: Mapping[str, _Answer],
) -> dict[str, tuple[str, _Answer | None]]:
    """Each unit's final place: an option label or the residual, and its answer."""
    assignments = clustering.assignments if clustering is not None else {}
    return {
        unit.unit_id: (assignments.get(unit.unit_id, RESIDUAL_LABEL), answers.get(unit.unit_id))
        for unit in units
    }


def _unclustered(placement: tuple[str, _Answer | None]) -> bool:
    """Whether a unit ended in the residual without a *not an option* answer."""
    final, answer = placement
    return final == RESIDUAL_LABEL and not (answer is not None and answer.kind == "not_an_option")


def longlist_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: LonglistContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Build the longlist for one longlist walk.

    Every model call (discovery, assignment, the residual pass) happens
    before the first write; the writes — new option rows, the folds' merges,
    the task's memberships replaced, and ``longlist_result`` last — share the
    component transaction. No typing: ``option_profile`` types the options
    after this step (task 046, S20).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``longlist`` run.
        context: The walk's intent record.
        backend: The model seam.

    Returns:
        The component summary: ``options``, ``unclustered``,
        ``not_an_option`` and ``units``.

    Raises:
        LonglistFailure: If clustering fails or the exhaustiveness invariant
            (units = memberships + unclustered + not an option) breaks.
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    _walk_id, plan_version = _walk_ref(
        conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id
    )
    plan_data = longlist_plan_data(plan)
    baseline = baseline_sections(conn, task_id)
    search_scopes = _option_search_scopes(conn, task_id=task_id)
    own = _own_units(
        conn,
        task_id=task_id,
        scope_ids=[context.scope_id, *search_scopes],
        current_fingerprints=current_profile_fingerprints(
            conn, task_id=task_id, scope_id=context.scope_id
        ),
    )
    linked, link_provenance = _linked_units(conn, task_id=task_id)
    units = own.units + linked
    seeds = _seeds(conn, task_id=task_id)
    retired = _merged_names(conn, task_id=task_id)

    # 1. Seeded option clustering, the engine untouched.
    max_new, max_labels = discovery_bounds(len(seeds))
    clustering_backend = LonglistClusteringBackend(
        backend, plan=plan_data, baseline=baseline, seeds=seeds, retired=retired
    )
    try:
        clustering = _cluster(units, clustering_backend, max_labels)
    except ClusteringFailure as exc:
        raise LonglistFailure(f"longlist clustering failed: {exc.error}") from exc
    folds = clustering_backend.folds

    now = datetime.now(UTC)
    options: list[_Option] = [
        _Option(
            option_id=seed.option_id,
            label=seed.label,
            description=seed.description,
            design_features=seed.design_features,
            outcomes=list(seed.outcomes),
            seed=True,
        )
        for seed in seeds
        if seed.option_id not in folds
    ]
    by_label = {o.label: o for o in options}
    for discovered in _new_options(clustering, clustering_backend, by_label):
        options.append(discovered)
        by_label[discovered.label] = discovered
    placements = _placements(units, clustering, clustering_backend.answers)
    answers: dict[str, _Answer] = dict(clustering_backend.answers)

    # 2. The residual pass (R9): the unclustered units only, every option on
    # the list as a seed that cannot be folded, at most once.
    residual_units = [unit for unit in units if _unclustered(placements[unit.unit_id])]
    room = max(LONGLIST_HARD_CEILING - len(options), 0)
    residual_record: dict[str, Any] = {
        "ran": False,
        "skipped": None,
        "units": len(residual_units),
        "max_new": room,
    }
    residual_backend: LonglistClusteringBackend | None = None
    residual_clustering: ClusteringResult | None = None
    if not residual_units:
        residual_record["skipped"] = "no unclustered unit"
    elif room == 0:
        residual_record["skipped"] = "no room under the ceiling"
    else:
        residual_seeds = [
            _Seed(
                option_id=o.option_id,
                label=o.label,
                description=o.description,
                design_features=o.design_features,
            )
            for o in options
        ]
        residual_backend = LonglistClusteringBackend(
            backend,
            plan=plan_data,
            baseline=baseline,
            seeds=residual_seeds,
            retired=[*retired, *(fold.seed.label for fold in folds.values())],
            residual=True,
        )
        try:
            residual_clustering = _cluster(
                residual_units, residual_backend, len(residual_seeds) + room
            )
        except ClusteringFailure as exc:
            # The first pass stands; the residual stays unclustered.
            log.warning("longlist.residual_pass_failed", error=exc.error)
            residual_record["skipped"] = "failed"
            residual_record["error"] = exc.error
            residual_backend = None
    if residual_backend is not None:
        new_in_residual = _new_options(residual_clustering, residual_backend, by_label)
        for discovered in new_in_residual:
            options.append(discovered)
            by_label[discovered.label] = discovered
        second = _placements(residual_units, residual_clustering, residual_backend.answers)
        placements.update(second)
        for unit in residual_units:
            answer = residual_backend.answers.get(unit.unit_id)
            if answer is None:
                answers.pop(unit.unit_id, None)
            else:
                answers[unit.unit_id] = answer
        placed = sum(1 for label, _ in second.values() if label != RESIDUAL_LABEL)
        residual_record.update(
            ran=True,
            new_options=len(new_in_residual),
            units_placed=placed,
            units_left=len(residual_units) - placed,
            restated_seeds_dropped=residual_backend.restated_seeds_dropped,
            short_id_repairs=residual_backend.short_id_repairs,
            digest=residual_backend.digest,
            clustering=_engine_stats(residual_clustering),
        )

    # 3. The merge: every unit in one option, unclustered or not an option,
    # checked once.
    unclustered: list[_Unit] = []
    not_an_option: list[_Unit] = []
    for unit in units:
        final, answer = placements[unit.unit_id]
        if final == RESIDUAL_LABEL:
            if answer is not None and answer.kind == "not_an_option":
                not_an_option.append(unit)
            else:
                unclustered.append(unit)
        else:
            by_label[final].members.append(unit)
    member_count = sum(len(o.members) for o in options)
    if member_count + len(unclustered) + len(not_an_option) != len(units):
        raise LonglistFailure(
            "longlist invariant violated: "
            f"units={len(units)} members={member_count} "
            f"unclustered={len(unclustered)} not_an_option={len(not_an_option)}"
        )

    # 4. Outcomes at mint time (S11): a discovered option's are the plan
    # outcomes its members' tags name; a seed keeps its design's.
    plan_outcomes = [outcome.text for outcome in plan.outcomes]
    for o in options:
        if o.seed or o.wire is None:
            continue
        o.design = _discovered_design(o.label, o.wire, _member_outcomes(o.members, plan_outcomes))
        o.design_features = list(o.design.design_features)
        o.outcomes = list(o.design.outcomes_served)

    # Themes are the ``theme`` component's, after ``constrain`` (task 046,
    # R28): this row is written with none.
    usage = UsageAccumulator()
    if clustering is not None:
        usage.add_payload(clustering.usage_totals)
    if residual_clustering is not None:
        usage.add_payload(residual_clustering.usage_totals)

    # 5. Typing is the ``option_profile`` component's, after this one (S20).

    # 6. Coverage (deterministic).
    label_ids = {u.label_tss_id for u in units if u.label_tss_id is not None}
    labels = labels_for_snapshots(conn, task_id=task_id, tss_ids=label_ids)
    home = where_codes(plan.where.text)
    # A folded seed's own documents are this build's: its earlier memberships
    # are replaced by this build's writes. This build's folds are not written
    # yet; they join the ones already stored, with no documents of their own.
    target_ids = {o.label: o.option_id for o in options}
    folded = _folded_seeds(
        conn,
        task_id=task_id,
        option_ids=[o.option_id for o in options],
        documents_of={o.option_id: {u.doc_key for u in o.members} for o in options},
    )
    fold_rows: list[tuple[uuid.UUID, uuid.UUID]] = []
    for fold in folds.values():
        into = target_ids[fold.into_label]
        fold_rows.append((fold.seed.option_id, into))
        folded.setdefault(into, []).append(FoldedSeed(name=fold.seed.name, documents=0))
    coverage = {
        str(o.option_id): option_coverage(
            [_coverage_member(u, flagged=_flagged(answers, u, o.label)) for u in o.members],
            labels=labels,
            home=home,
            folded_seeds=folded.get(o.option_id, ()),
            plan_outcomes=plan_outcomes,
        )
        for o in options
    }

    # 7. Writes, all after every model call. New option rows first, then the
    # folds' merges (which may name them).
    for o in options:
        minted = o.design
        if o.seed or minted is None:
            continue
        conn.execute(
            option.insert().values(
                option_id=o.option_id,
                task_id=task_id,
                name=minted.name,
                description=minted.description,
                design=minted.model_dump(mode="json"),
                design_version=minted.version,
                outcomes=list(minted.outcomes_served),
                origin="clustered",
                state="included",
                secondary_lever_types=[],
                created_by_run_id=run_id,
                created_at=now,
                updated_at=now,
            )
        )
    for seed_id, into in fold_rows:
        # A duplicate merged into the folded seed follows it, so a merge
        # always names an option on the list.
        conn.execute(
            option.update()
            .where(option.c.task_id == task_id)
            .where(
                (option.c.option_id == seed_id) | (option.c.merged_into_option_id == seed_id)
            )
            .values(merged_into_option_id=into, updated_at=now)
        )
    conn.execute(option_membership.delete().where(option_membership.c.task_id == task_id))
    membership_rows = [
        {
            "membership_id": uuid.uuid4(),
            "option_id": o.option_id,
            "task_id": task_id,
            "unit_kind": u.kind,
            "unit_id": u.record_id,
            "unit_task_id": u.unit_task_id,
            "task_source_snapshot_id": u.member_tss_id,
            "assignment_reason": _reason(answers, u, o.label),
            "design_feature_not_stated": _flagged(answers, u, o.label),
            "assigned_by_run_id": run_id,
        }
        for o in options
        for u in o.members
    ]
    if membership_rows:
        conn.execute(option_membership.insert(), membership_rows)

    states = [
        row.state
        for row in conn.execute(
            select(option.c.state)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_(None))
        )
    ]
    documents = {u.doc_key for u in units}
    counts = {
        "options": len(options),
        "included": sum(1 for s in states if s == "included"),
        "excluded": sum(1 for s in states if s == "excluded"),
        "no_in_scope_evidence": 0,
        "unclustered": len(unclustered),
        "not_an_option": len(not_an_option),
        "units": len(units),
        "members": member_count,
        "documents": len(documents),
        "comparator_records": own.comparators,
        "title_only": _title_only(conn, task_id=task_id, scope_id=context.scope_id),
        "seeds": len(seeds),
        "folded": len(folds),
        "discovered": sum(1 for o in options if not o.seed),
        "seeds_without_members": sum(1 for o in options if o.seed and not o.members),
    }
    rejected_folds = clustering_backend.rejected_folds
    rejected_by_reason: dict[str, int] = {}
    for rejection in rejected_folds:
        rejected_by_reason[rejection["reason"]] = rejected_by_reason.get(rejection["reason"], 0) + 1
    live = backend.mode == "live"
    provenance: dict[str, Any] = {
        "backend_mode": backend.mode,
        "prompt_versions": {"cluster": LONGLIST_CLUSTER_PROMPT_VERSION},
        "models": {
            "discovery": LONGLIST_JUDGMENT_MODEL if live else "stub",
            "assignment": LONGLIST_ASSIGNMENT_MODEL if live else "stub",
        },
        "ceiling": {
            "target_size": LONGLIST_TARGET_SIZE,
            "hard_ceiling": LONGLIST_HARD_CEILING,
            "seeds": len(seeds),
            "max_new": max_new,
            "max_labels": max_labels,
            "discovery_called": clustering_backend.called,
            "over_ceiling_dropped": clustering_backend.over_ceiling_dropped,
            "excess": max(len(options) - LONGLIST_HARD_CEILING, 0),
        },
        "digest": clustering_backend.digest,
        "thinning": own.thinning,
        "folds": {
            "accepted": [
                {
                    "seed_id": str(fold.seed.option_id),
                    "seed_label": fold.seed.label,
                    "into_id": str(target_ids[fold.into_label]),
                    "into_label": fold.into_label,
                }
                for fold in folds.values()
            ],
            "rejected": rejected_folds,
            "rejected_by_reason": rejected_by_reason,
        },
        "residual_pass": residual_record,
        "seed_ids": [str(seed.option_id) for seed in seeds],
        "discovered_ids": [str(o.option_id) for o in options if not o.seed],
        "scopes": {
            "longlist": str(context.scope_id),
            "targeted": [str(scope) for scope in search_scopes],
            "superseded_records": own.superseded,
        },
        "links": link_provenance,
        "clustering": {
            **_engine_stats(clustering),
            "restated_seeds_dropped": clustering_backend.restated_seeds_dropped,
            "repeated_labels_dropped": clustering_backend.repeated_labels_dropped,
            "short_id_repairs": clustering_backend.short_id_repairs,
        },
        "where_tried_labels": where_labels(plan.where.text),
        "usage_totals": usage.payload(),
    }
    conn.execute(
        longlist_result.insert().values(
            longlist_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            plan_version=plan_version,
            themes=[],
            coverage=coverage,
            judgements={},
            guesses={},
            option_profile={},
            counts=counts,
            provenance=provenance,
            created_at=now,
        )
    )
    log.info(
        "longlist.built",
        units=len(units),
        options=len(options),
        folded=len(folds),
        residual_pass=residual_record["ran"],
        unclustered=len(unclustered),
        not_an_option=len(not_an_option),
    )
    return {
        "options": len(options),
        "unclustered": len(unclustered),
        "not_an_option": len(not_an_option),
        "units": len(units),
    }


def _answer_for(answers: Mapping[str, _Answer], unit: _Unit, label: str) -> _Answer | None:
    """The model's answer that placed ``unit`` under ``label``, if it is the last one."""
    answer = answers.get(unit.unit_id)
    if answer is None or answer.kind != "option" or answer.label != label:
        return None
    return answer


def _flagged(answers: Mapping[str, _Answer], unit: _Unit, label: str) -> bool:
    answer = _answer_for(answers, unit, label)
    return bool(answer and answer.design_feature_not_stated)


def _reason(answers: Mapping[str, _Answer], unit: _Unit, label: str) -> str | None:
    answer = _answer_for(answers, unit, label)
    return _bound(answer.reason, 500) if answer is not None else None
