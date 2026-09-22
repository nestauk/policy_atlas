"""The ``longlist`` component: records clustered into options (task 045, S8).

Contract deliverable 6, D4, D5, D8, D10, D11, D14, D16, D20; ADR 0039
decisions 7 and 8. The longlist walk's clustering step:

1. **Units.** The ``intervention_profile_record`` rows of the longlist scope
   and of every targeted scope whose walk is a child of this walk (read
   through each scope's latest extraction roll-up), minus ``comparator``
   records; plus, per link whose pinned walk ran ``extract``, the source
   task's IOF/ICF findings of that walk through ``finding_reference_union``
   (D5). Each unit's payload is this component's projection.
2. **Seeded clustering, the engine untouched** (P8). The seeds are every
   option the task holds — on a first build the entrants ``suggest`` minted
   (and the user's own), on a rebuild every existing option (D14).
   :class:`LonglistClusteringBackend` returns the seeds plus newly
   discovered options from ``discover`` and places each unit under one label
   in ``assign``; :func:`~policy_atlas.evidence_search.clustering_engine.cluster_units`
   runs exactly as characterise runs it.
3. **Option rows**: seeds keep their rows; each discovered option mints one
   (``origin="clustered"``, design v1 from the discovery wire); a discovered
   bundle is a package with ``part_of`` rows from its components. One option
   per record; a document with several records lands in several options.
   Memberships are replaced wholesale by this run's.
4. **Themes**: a second, unseeded ``cluster_units`` run over the options.
5. **Typing**: one batched call per :data:`LEVER_TYPING_BATCH_SIZE` options;
   lever types and the ambition tag on the option row, the runner-up in
   ``longlist_result.provenance`` only (D8).
6. **Coverage** (:mod:`.coverage`), deterministic, DOI-collapsed.
7. **``longlist_result``**, written last (the 010 pattern).

Every model call happens before the first write, so a failure leaves nothing
behind. User state (``state``, ``exclusion``) is never touched and no option
is ever deleted.

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

import math
import threading
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from pydantic import ValidationError
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    option_relation,
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
from policy_atlas.evidence_search.extract.extract import record_ids_by_profile
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.interventions_records import (
    PROFILE_ID as INTERVENTIONS_PROFILE_ID,
)
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.options_scoping.labels import labels_for_snapshots
from policy_atlas.options_scoping.longlist.coverage import (
    CoverageMember,
    document_key,
    normalise_doi,
    option_coverage,
)
from policy_atlas.options_scoping.longlist.lever_types import (
    AMBITION_BANDS,
    LEVER_TYPE_KEYS,
    TAXONOMY_VERSION,
)
from policy_atlas.options_scoping.longlist.lever_typing_prompt import (
    LEVER_TYPING_BATCH_SIZE,
    LEVER_TYPING_PROMPT_VERSION,
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
from policy_atlas.options_scoping.longlist.longlist_theme_prompt import (
    LONGLIST_THEME_PROMPT_VERSION,
    THEME_DESCRIPTION_MAX,
    THEME_LABEL_MAX,
)
from policy_atlas.options_scoping.longlist.where_tried import where_codes, where_labels
from policy_atlas.options_scoping.suggest.suggest import walk_plan

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
#: Engine policy for the theme clustering.
THEME_ASSIGNMENT_BATCH_SIZE = 40

#: The discovery ceiling ``clamp(ceil(N / 4), 8, 40)`` over N units (D4).
CEILING_DIVISOR, CEILING_MIN, CEILING_MAX = 4, 8, 40
#: The theme ceiling ``clamp(ceil(n / 3), 3, 12)`` over n options (lead call:
#: about three options a theme, characterise's 3..12 theme bounds).
THEME_CEILING_DIVISOR, THEME_CEILING_MIN, THEME_CEILING_MAX = 3, 3, 12

#: A unit payload's free-text bound (the quote, a claim, each reference).
UNIT_TEXT_MAX = 240
UNIT_FEATURES_MAX = 8
#: The reason an unusable typing is recorded under (fail-closed, D8).
TYPING_INVALID_REASON = "typing invalid"

#: Seeds are offered in entrant order, then the clustered options (D14).
_SEED_ORIGIN_ORDER = ("added_by_you", "from_evidence_search", "suggested", "clustered")

# Fixed namespace for content-keyed theme identity — never rotate:
# theme_id = uuid5(ns, f"{task_id}:{theme_name}") (the characterise pattern).
_THEME_ID_NAMESPACE = uuid.UUID("0a5e1f4c-3b2d-4e8f-9c71-045045045045")

UnitKind = Literal["interventions", "iof", "icf"]


def discovery_ceiling(unit_count: int) -> int:
    """The option ceiling ``clamp(ceil(N / 4), 8, 40)`` (D4), counting seeds.

    Args:
        unit_count: N, the units clustered.

    Returns:
        The ceiling.
    """
    return max(CEILING_MIN, min(CEILING_MAX, math.ceil(unit_count / CEILING_DIVISOR)))


def theme_ceiling(option_count: int) -> int:
    """The theme ceiling ``clamp(ceil(n / 3), 3, 12)``.

    Args:
        option_count: n, the options grouped.

    Returns:
        The ceiling.
    """
    return max(
        THEME_CEILING_MIN,
        min(THEME_CEILING_MAX, math.ceil(option_count / THEME_CEILING_DIVISOR)),
    )


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


def _own_units(
    conn: Connection, *, task_id: uuid.UUID, scope_ids: Sequence[uuid.UUID]
) -> tuple[list[_Unit], int]:
    """The profile records of the given scopes, minus comparators.

    Returns:
        ``(units, comparator_records)``.
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
        return [], 0
    ipr = intervention_profile_record
    rows = conn.execute(
        select(
            ipr,
            source_extraction_record.c.task_source_snapshot_id,
            source_extraction_record.c.basis,
            source_snapshot.c.metadata,
        )
        .select_from(
            ipr.join(
                source_extraction_record,
                and_(
                    source_extraction_record.c.extraction_record_id == ipr.c.extraction_record_id,
                    source_extraction_record.c.task_id == ipr.c.task_id,
                ),
            )
            .join(
                task_source_snapshot,
                and_(
                    task_source_snapshot.c.task_source_snapshot_id
                    == source_extraction_record.c.task_source_snapshot_id,
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
        .order_by(source_extraction_record.c.task_source_snapshot_id, ipr.c.record_id)
    ).all()
    units: list[_Unit] = []
    seen: set[uuid.UUID] = set()
    comparators = 0
    for row in rows:
        if row.record_id in seen:
            continue
        seen.add(row.record_id)
        if row.role == "comparator":
            comparators += 1
            continue
        unit_id = str(row.record_id)
        payload: dict[str, object] = {
            "unit_id": unit_id,
            "intervention": _bound(row.intervention),
            "role": row.role,
            "design_features": _string_list(row.design_features),
            "is_bundle": bool(row.is_bundle),
            "components": _string_list(row.components),
            "outcome": _bound(row.outcome),
            "population": _bound(row.population),
            "setting": _bound(row.setting),
            "study_geography": _bound(row.study_geography),
            "quote": _first_quote(row.grounding),
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
            )
        )
    return units, comparators


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

    def as_data(self) -> dict[str, object]:
        return {
            "label": self.label,
            "description": self.description,
            "design_features": self.design_features,
        }


def _clean_label_text(value: str, limit: int) -> str:
    text = "".join(ch for ch in value if not unicodedata.category(ch).startswith("C"))
    text = " ".join(text.split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _seeds(conn: Connection, *, task_id: uuid.UUID) -> list[_Seed]:
    """Every option of the task as a seed, labels made engine-valid and unique."""
    rows = conn.execute(
        select(
            option.c.option_id,
            option.c.name,
            option.c.description,
            option.c.design,
            option.c.origin,
            option.c.created_at,
        ).where(option.c.task_id == task_id)
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
            features = list(OptionDesign.model_validate(row.design).design_features)
        except ValidationError:
            log.warning("longlist.seed_design_invalid", option_id=str(row.option_id))
            features = []
        seeds.append(
            _Seed(
                option_id=row.option_id,
                label=label,
                description=description,
                design_features=features,
            )
        )
    return seeds


# --- the engine's backends ------------------------------------------------------


@dataclass(frozen=True)
class _Answer:
    kind: Literal["option", "not_an_option", "unclustered"]
    label: str
    reason: str | None
    design_feature_not_stated: bool


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


class LonglistClusteringBackend(ClusteringBackend):
    """The engine's backend for seeded option clustering (P8).

    ``discover`` returns the seeds followed by the options the model discovers
    beyond them (one call, ``max_new = max_labels - len(seeds)``, none when
    that is zero); the discovered options' full wire is kept on the side by
    label. ``assign`` returns ``unit_id → label`` to the engine and keeps the
    reason and ``design_feature_not_stated`` on the side by unit id; the
    component's ``not an option`` and the prompt's ``ungroupable`` reach the
    engine as its residual label, the difference remembered here.

    Args:
        backend: The model seam.
        question: The plan's question (context only).
        seeds: The seed options, in offer order.
    """

    def __init__(self, backend: LonglistBackend, *, question: str, seeds: list[_Seed]) -> None:
        self._backend = backend
        self._question = question
        self._seeds = seeds
        self._seed_keys = {_key(seed.label) for seed in seeds}
        self._lock = threading.Lock()
        self.discovered: dict[str, DiscoveredOptionWire] = {}
        self.answers: dict[str, _Answer] = {}
        self.restated_seeds_dropped = 0
        self.max_new = 0

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        """Return the seeds plus newly discovered options.

        Args:
            units: The units, in deterministic order.
            min_labels: The policy's minimum (unused: the prompt has none).
            max_labels: The policy's ceiling, counting the seeds.

        Returns:
            Seed labels then discovered labels, and the call's usage.
        """
        del min_labels
        labels = [
            ClusterLabel(label=seed.label, description=seed.description) for seed in self._seeds
        ]
        self.discovered = {}
        self.max_new = max(max_labels - len(self._seeds), 0)
        if self.max_new == 0:
            return labels, None
        response, usage = self._backend.discover(
            question=self._question,
            seeds=[seed.as_data() for seed in self._seeds],
            records=[unit.payload for unit in units],
            max_new=self.max_new,
        )
        for wire in response.options:
            label = wire.label.strip()
            if _key(label) in self._seed_keys:
                self.restated_seeds_dropped += 1
                continue
            self.discovered[label] = wire
            labels.append(ClusterLabel(label=label, description=wire.description))
        return labels, usage

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
        """Assign one batch; the component's labels become the engine's residual.

        Args:
            batch: The batch's units.
            labels: The validated labels (seeds and discovered).

        Returns:
            One assignment per answered unit (duplicates kept, so the engine
            sees conflicts), and the call's usage.
        """
        response, usage = self._backend.assign(
            options=[self._option_data(label) for label in labels],
            records=[unit.payload for unit in batch],
        )
        by_key = {_key(label.label): label.label for label in labels}
        not_an_option = _key(NOT_AN_OPTION_LABEL)
        residual_keys = {_key(MODEL_RESIDUAL_LABEL), _key(RESIDUAL_LABEL)}
        assignments: list[ClusterAssignment] = []
        with self._lock:
            for wire in response.assignments:
                raw = _key(wire.option_label)
                if raw == not_an_option:
                    answer = _Answer("not_an_option", RESIDUAL_LABEL, wire.reason, False)
                elif raw in residual_keys:
                    answer = _Answer("unclustered", RESIDUAL_LABEL, wire.reason, False)
                else:
                    label = by_key.get(raw, wire.option_label)
                    answer = _Answer("option", label, wire.reason, wire.design_feature_not_stated)
                self.answers[wire.unit_id] = answer
                assignments.append(ClusterAssignment(unit_id=wire.unit_id, label=answer.label))
        return assignments, usage


class _ThemeClusteringBackend(ClusteringBackend):
    """The engine's backend for themes over options (unseeded)."""

    def __init__(self, backend: LonglistBackend, *, question: str) -> None:
        self._backend = backend
        self._question = question

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        """Discover themes over the options."""
        del min_labels
        response, usage = self._backend.discover_themes(
            question=self._question,
            records=[unit.payload for unit in units],
            max_labels=max_labels,
        )
        return (
            [
                ClusterLabel(label=t.label.strip(), description=t.description)
                for t in response.themes
            ],
            usage,
        )

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        """Assign options to themes; ``ungroupable`` becomes the residual."""
        response, usage = self._backend.assign_themes(
            themes=[{"label": label.label, "description": label.description} for label in labels],
            records=[unit.payload for unit in batch],
        )
        by_key = {_key(label.label): label.label for label in labels}
        residual_keys = {_key(MODEL_RESIDUAL_LABEL), _key(RESIDUAL_LABEL)}
        assignments = [
            ClusterAssignment(
                unit_id=wire.unit_id,
                label=(
                    RESIDUAL_LABEL
                    if _key(wire.theme_label) in residual_keys
                    else by_key.get(_key(wire.theme_label), wire.theme_label)
                ),
            )
            for wire in response.assignments
        ]
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


def _theme_policy(max_labels: int) -> ClusteringPolicy:
    return ClusteringPolicy(
        min_labels=0,
        max_labels=max_labels,
        assignment_batch_size=THEME_ASSIGNMENT_BATCH_SIZE,
        discovery_retry_cap=DISCOVERY_RETRY_CAP,
        assignment_repair_cap=ASSIGNMENT_REPAIR_CAP,
        residual_label=RESIDUAL_LABEL,
        unresolved_policy="residual",
        label_max=THEME_LABEL_MAX,
        description_max=THEME_DESCRIPTION_MAX,
        forbidden_label_reason=_forbidden_label("theme"),
        label_noun="theme",
        log_event_prefix="longlist.themes",
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


# --- options, themes, typing ------------------------------------------------------


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


@dataclass(frozen=True)
class _Typing:
    primary: str | None
    secondary: list[str]
    none_fits_reason: str | None
    ambition: str | None
    ambition_reason: str | None
    runner_up: str | None
    runner_up_reason: str | None
    invalid: bool


_INVALID_TYPING = _Typing(
    primary=None,
    secondary=[],
    none_fits_reason=TYPING_INVALID_REASON,
    ambition=None,
    ambition_reason=None,
    runner_up=None,
    runner_up_reason=None,
    invalid=True,
)


def _validated_typing(wire: Any) -> _Typing:
    """One wire typing, validated fail-closed (D8)."""
    primary = wire.primary_lever_type
    reason = (wire.none_fits_reason or "").strip() or None
    ambition = wire.ambition
    ambition_reason = (wire.ambition_reason or "").strip() or None
    if ambition not in AMBITION_BANDS or ambition_reason is None:
        return _INVALID_TYPING
    if primary is None:
        if reason is None:
            return _INVALID_TYPING
    elif primary not in LEVER_TYPE_KEYS:
        return _INVALID_TYPING
    secondary: list[str] = []
    for key in wire.secondary_lever_types:
        if key in LEVER_TYPE_KEYS and key != primary and key not in secondary:
            secondary.append(key)
    runner_up = wire.runner_up_lever_type if wire.runner_up_lever_type in LEVER_TYPE_KEYS else None
    return _Typing(
        primary=primary,
        secondary=secondary,
        none_fits_reason=reason if primary is None else None,
        ambition=ambition,
        ambition_reason=ambition_reason,
        runner_up=runner_up if runner_up != primary else None,
        runner_up_reason=((wire.runner_up_reason or "").strip() or None) if runner_up else None,
        invalid=False,
    )


def _type_options(
    backend: LonglistBackend, options: list[_Option], usage: UsageAccumulator
) -> tuple[dict[uuid.UUID, _Typing], dict[str, Any]]:
    """Type every option, one call per batch; any failure is *typing invalid*."""
    typings: dict[uuid.UUID, _Typing] = {}
    calls = 0
    failed_batches = 0
    for start in range(0, len(options), LEVER_TYPING_BATCH_SIZE):
        batch = options[start : start + LEVER_TYPING_BATCH_SIZE]
        by_unit = {str(o.option_id): o for o in batch}
        calls += 1
        try:
            response, call_usage = backend.type_options(
                options=[
                    {
                        "unit_id": str(o.option_id),
                        "label": o.label,
                        "description": o.description,
                        "design_features": o.design_features,
                    }
                    for o in batch
                ]
            )
        except Exception as exc:  # fail-closed: the batch is recorded invalid
            failed_batches += 1
            log.warning("longlist.typing_batch_failed", error_type=type(exc).__name__)
            continue
        usage.add(call_usage)
        for wire in response.typings:
            target = by_unit.get(wire.unit_id)
            if target is None or target.option_id in typings:
                continue
            typings[target.option_id] = _validated_typing(wire)
    for o in options:
        typings.setdefault(o.option_id, _INVALID_TYPING)
    return typings, {
        "calls": calls,
        "batch_size": LEVER_TYPING_BATCH_SIZE,
        "failed_batches": failed_batches,
        "invalid": sum(1 for t in typings.values() if t.invalid),
    }


def _discovered_design(label: str, wire: DiscoveredOptionWire) -> OptionDesign:
    """Design v1 from the discovery wire; a wire with no feature keeps its description."""
    features = [f for f in (_bound(item, 2_000) for item in wire.design_features) if f]
    outcomes = [o for o in (_bound(item, 2_000) for item in wire.outcomes_served) if o]
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
            name=label, description=label, design_features=[label], outcomes_served=[], assumed=[]
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


def _child_scopes(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID | None
) -> list[uuid.UUID]:
    """The targeted scopes of this walk's child walks (its option searches)."""
    if walk_id is None:
        return []
    return [
        row.evidence_scope_id
        for row in conn.execute(
            select(capability_run.c.evidence_scope_id)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.parent_capability_run_id == walk_id)
            .order_by(capability_run.c.started_at, capability_run.c.capability_run_id)
        )
    ]


def longlist_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: LonglistContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Build the longlist for one longlist walk.

    Every model call (discovery, assignment, themes, typing) happens before
    the first write; the writes — new option rows, ``part_of`` relations, the
    task's memberships replaced, typing on every option, and
    ``longlist_result`` last — share the component transaction.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``longlist`` run.
        context: The walk's intent record.
        backend: The model seam.

    Returns:
        The component summary: ``options``, ``themes``, ``unclustered``,
        ``not_an_option``, ``none_fits`` and ``units``.

    Raises:
        LonglistFailure: If clustering fails or the exhaustiveness invariant
            (units = memberships + unclustered + not an option) breaks.
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    walk_id, plan_version = _walk_ref(
        conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id
    )
    child_scopes = _child_scopes(conn, task_id=task_id, walk_id=walk_id)
    own, comparators = _own_units(
        conn, task_id=task_id, scope_ids=[context.scope_id, *child_scopes]
    )
    linked, link_provenance = _linked_units(conn, task_id=task_id)
    units = own + linked
    seeds = _seeds(conn, task_id=task_id)

    # 1. Seeded option clustering, the engine untouched.
    ceiling = discovery_ceiling(len(units))
    # The seeds are all assigned against even when they outnumber the ceiling.
    max_labels = max(ceiling, len(seeds))
    clustering_backend = LonglistClusteringBackend(backend, question=plan.question, seeds=seeds)
    try:
        clustering = (
            cluster_units(
                [ClusterUnit(unit_id=u.unit_id, payload=u.payload) for u in units],
                backend=clustering_backend,
                policy=_option_policy(max_labels),
            )
            if units
            else None
        )
    except ClusteringFailure as exc:
        raise LonglistFailure(f"longlist clustering failed: {exc.error}") from exc

    now = datetime.now(UTC)
    options: list[_Option] = [
        _Option(
            option_id=seed.option_id,
            label=seed.label,
            description=seed.description,
            design_features=seed.design_features,
            outcomes=[],
            seed=True,
        )
        for seed in seeds
    ]
    by_label = {o.label: o for o in options}
    if clustering is not None:
        for label in clustering.labels:
            wire = clustering_backend.discovered.get(label.label)
            if wire is None or label.label in by_label:
                continue
            design = _discovered_design(label.label, wire)
            discovered = _Option(
                option_id=uuid.uuid4(),
                label=label.label,
                description=label.description,
                design_features=list(design.design_features),
                outcomes=list(design.outcomes_served),
                seed=False,
                wire=wire,
                design=design,
            )
            options.append(discovered)
            by_label[label.label] = discovered

    unclustered: list[_Unit] = []
    not_an_option: list[_Unit] = []
    answers = clustering_backend.answers
    assignments = clustering.assignments if clustering is not None else {}
    for unit in units:
        final = assignments.get(unit.unit_id, RESIDUAL_LABEL)
        if final == RESIDUAL_LABEL:
            answer = answers.get(unit.unit_id)
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

    # 2. Packages: a discovered bundle's components, matched by label.
    label_keys = {_key(o.label): o for o in options}
    relations: list[tuple[uuid.UUID, uuid.UUID]] = []
    unmatched_components = 0
    packages = 0
    for package in options:
        if package.wire is None or not package.wire.is_bundle:
            continue
        packages += 1
        for component_label in package.wire.components:
            component = label_keys.get(_key(component_label))
            if component is None or component.option_id == package.option_id:
                unmatched_components += 1
                continue
            relations.append((component.option_id, package.option_id))

    # 3. Themes: an unseeded run over the options.
    usage = UsageAccumulator()
    if clustering is not None:
        usage.add_payload(clustering.usage_totals)
    themes_ceiling = theme_ceiling(len(options))
    try:
        theme_result = (
            cluster_units(
                [
                    ClusterUnit(
                        unit_id=str(o.option_id),
                        payload={
                            "unit_id": str(o.option_id),
                            "label": o.label,
                            "description": o.description,
                            "design_features": o.design_features,
                            "outcomes_served": o.outcomes,
                        },
                    )
                    for o in options
                ],
                backend=_ThemeClusteringBackend(backend, question=plan.question),
                policy=_theme_policy(themes_ceiling),
            )
            if options
            else None
        )
    except ClusteringFailure as exc:
        raise LonglistFailure(f"longlist theme grouping failed: {exc.error}") from exc
    if theme_result is not None:
        usage.add_payload(theme_result.usage_totals)
    themes_out: list[dict[str, Any]] = []
    no_theme = len(options)
    if theme_result is not None:
        members_by_theme: dict[str, list[str]] = {label.label: [] for label in theme_result.labels}
        for o in options:
            theme = theme_result.assignments.get(str(o.option_id), RESIDUAL_LABEL)
            if theme != RESIDUAL_LABEL:
                members_by_theme[theme].append(str(o.option_id))
        no_theme = len(options) - sum(len(ids) for ids in members_by_theme.values())
        themes_out = [
            {
                "theme_id": str(uuid.uuid5(_THEME_ID_NAMESPACE, f"{task_id}:{label.label}")),
                "name": label.label,
                "description": label.description,
                "option_ids": members_by_theme[label.label],
            }
            for label in theme_result.labels
        ]

    # 4. Typing.
    typings, typing_stats = _type_options(backend, options, usage)

    # 5. Coverage (deterministic).
    label_ids = {u.label_tss_id for u in units if u.label_tss_id is not None}
    labels = labels_for_snapshots(conn, task_id=task_id, tss_ids=label_ids)
    home = where_codes(plan.where.text)
    coverage = {
        str(o.option_id): option_coverage(
            [
                CoverageMember(
                    unit_kind=u.kind,
                    doc_key=u.doc_key,
                    tss_id=u.label_tss_id,
                    role=u.role,
                    basis=u.basis,
                    flagged=_flagged(answers, u, o.label),
                    population=u.population,
                    setting=u.setting,
                    outcome=u.outcome,
                    study_geography=u.study_geography,
                )
                for u in o.members
            ],
            labels=labels,
            home=home,
        )
        for o in options
    }

    # 6. Writes, all after every model call.
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
    for from_id, to_id in relations:
        conn.execute(
            pg_insert(option_relation)
            .values(
                relation_id=uuid.uuid4(),
                task_id=task_id,
                from_option_id=from_id,
                to_option_id=to_id,
                kind="part_of",
                created_by="longlist",
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_orel_pair_kind")
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
    for o in options:
        typing = typings[o.option_id]
        conn.execute(
            option.update()
            .where(option.c.option_id == o.option_id, option.c.task_id == task_id)
            .values(
                primary_lever_type=typing.primary,
                secondary_lever_types=typing.secondary,
                lever_none_fits_reason=typing.none_fits_reason,
                taxonomy_version=TAXONOMY_VERSION,
                ambition=typing.ambition,
                ambition_reason=typing.ambition_reason,
                updated_at=now,
            )
        )

    states = [
        row.state
        for row in conn.execute(select(option.c.state).where(option.c.task_id == task_id))
    ]
    none_fits = sum(1 for t in typings.values() if t.primary is None)
    documents = {u.doc_key for u in units}
    counts = {
        "options": len(options),
        "themes": len(themes_out),
        "no_theme": no_theme,
        "included": sum(1 for s in states if s == "included"),
        "excluded": sum(1 for s in states if s == "excluded"),
        "no_in_scope_evidence": 0,
        "unclustered": len(unclustered),
        "not_an_option": len(not_an_option),
        "none_fits": none_fits,
        "typing_invalid": typing_stats["invalid"],
        "units": len(units),
        "members": member_count,
        "documents": len(documents),
        "comparator_records": comparators,
        "seeds": len(seeds),
        "discovered": sum(1 for o in options if not o.seed),
        "packages": packages,
        "seeds_without_members": sum(1 for o in options if o.seed and not o.members),
    }
    live = backend.mode == "live"
    provenance: dict[str, Any] = {
        "backend_mode": backend.mode,
        "prompt_versions": {
            "cluster": LONGLIST_CLUSTER_PROMPT_VERSION,
            "theme": LONGLIST_THEME_PROMPT_VERSION,
            "typing": LEVER_TYPING_PROMPT_VERSION,
        },
        "models": {
            "discovery": LONGLIST_JUDGMENT_MODEL if live else "stub",
            "assignment": LONGLIST_ASSIGNMENT_MODEL if live else "stub",
            "themes": LONGLIST_JUDGMENT_MODEL if live else "stub",
            "typing": LONGLIST_JUDGMENT_MODEL if live else "stub",
        },
        "taxonomy_version": TAXONOMY_VERSION,
        "ceiling": {
            "formula": "clamp(ceil(N/4), 8, 40)",
            "units": len(units),
            "ceiling": ceiling,
            "seeds": len(seeds),
            "max_labels": max_labels,
            "max_new": clustering_backend.max_new,
        },
        "theme_ceiling": {
            "formula": "clamp(ceil(n/3), 3, 12)",
            "options": len(options),
            "ceiling": themes_ceiling,
        },
        "seed_ids": [str(seed.option_id) for seed in seeds],
        "discovered_ids": [str(o.option_id) for o in options if not o.seed],
        "scopes": {
            "longlist": str(context.scope_id),
            "targeted": [str(scope) for scope in child_scopes],
        },
        "links": link_provenance,
        "clustering": {
            **_engine_stats(clustering),
            "restated_seeds_dropped": clustering_backend.restated_seeds_dropped,
        },
        "theme_clustering": _engine_stats(theme_result),
        "typing": typing_stats,
        "runner_up": {
            str(option_id): {"lever_type": t.runner_up, "reason": t.runner_up_reason}
            for option_id, t in typings.items()
            if t.runner_up is not None
        },
        "bundles": {"packages": packages, "unmatched_components": unmatched_components},
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
            themes=themes_out,
            coverage=coverage,
            judgements={},
            guesses={},
            counts=counts,
            provenance=provenance,
            created_at=now,
        )
    )
    log.info(
        "longlist.built",
        units=len(units),
        options=len(options),
        themes=len(themes_out),
        unclustered=len(unclustered),
        not_an_option=len(not_an_option),
        none_fits=none_fits,
    )
    return {
        "options": len(options),
        "themes": len(themes_out),
        "unclustered": len(unclustered),
        "not_an_option": len(not_an_option),
        "none_fits": none_fits,
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
