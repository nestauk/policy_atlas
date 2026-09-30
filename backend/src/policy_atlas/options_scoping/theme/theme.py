"""The ``theme`` component: the included options grouped into themes (task 046, R28).

ADR 0040 decision 5. The longlist walk ends ``longlist → option_profile →
constrain → theme``: ``longlist`` makes options, ``option_profile`` writes what
is said about each, ``constrain`` makes verdicts, ``theme`` groups the
options a reader still sees. It is the Evidence search characterise's theme
machine, modified: its unit is the option. The clustering engine runs
unchanged — one unseeded :func:`~policy_atlas.evidence_search.clustering_engine.cluster_units`
call, with the policy and the ceiling ``longlist`` used before this slice.

``theme_scope`` reads the walk's latest ``longlist_result`` and the options
whose state is ``included`` and that are not merged, runs the call, and
writes ``themes``, ``counts.themes``, ``counts.no_theme`` and
``provenance.theme`` into that row. Every model call happens before the one
write. It is not a spine step: a :class:`ThemeFailure` fails the step, the
walk ends ``degraded``, and the verdicts ``constrain`` committed stay.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import longlist_result, option
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.evidence_search.clustering_engine import (
    AssignmentOutput,
    ClusterAssignment,
    ClusteringBackend,
    ClusteringFailure,
    ClusteringPolicy,
    ClusterLabel,
    ClusterUnit,
    cluster_units,
)
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.options_scoping.longlist.longlist import (
    ASSIGNMENT_REPAIR_CAP,
    DISCOVERY_RETRY_CAP,
    MAX_CONCURRENT_BATCHES,
    MODEL_RESIDUAL_LABEL,
    RESIDUAL_LABEL,
    _engine_stats,
    _forbidden_label,
    _key,
)
from policy_atlas.options_scoping.longlist.longlist_backend import (
    LONGLIST_JUDGMENT_MODEL,
    LonglistBackend,
)
from policy_atlas.options_scoping.suggest.suggest import walk_plan
from policy_atlas.options_scoping.theme.longlist_theme_prompt import (
    LONGLIST_THEME_PROMPT_VERSION,
    THEME_DESCRIPTION_MAX,
    THEME_LABEL_MAX,
)

log = structlog.get_logger()

#: Engine policy for the theme clustering.
THEME_ASSIGNMENT_BATCH_SIZE = 40

#: The theme ceiling ``clamp(ceil(n / 3), 3, 12)`` over n options (lead call:
#: about three options a theme, characterise's 3..12 theme bounds).
THEME_CEILING_DIVISOR, THEME_CEILING_MIN, THEME_CEILING_MAX = 3, 3, 12

# Fixed namespace for content-keyed theme identity — never rotate:
# theme_id = uuid5(ns, f"{task_id}:{theme_name}") (the characterise pattern).
_THEME_ID_NAMESPACE = uuid.UUID("0a5e1f4c-3b2d-4e8f-9c71-045045045045")


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


class ThemeFailure(Exception):
    """The themes could not be built (no longlist, or the clustering failed)."""


@dataclass
class ThemeContext:
    """Scope-level input to a ``theme`` run.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused).
        context: Its context JSONB (unused).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


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


def _latest_longlist(conn: Connection, *, task_id: uuid.UUID, scope_id: uuid.UUID) -> Any:
    row = conn.execute(
        select(longlist_result)
        .where(longlist_result.c.task_id == task_id)
        .where(longlist_result.c.evidence_scope_id == scope_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
    ).one_or_none()
    if row is None:
        raise ThemeFailure("theme: no longlist exists for this walk")
    return row


def _option_payload(row: Any) -> dict[str, object]:
    """One included option as a theme unit: what it is and what it serves."""
    try:
        features = list(OptionDesign.model_validate(row.design).design_features)
    except ValidationError:
        log.warning("theme.option_design_invalid", option_id=str(row.option_id))
        features = []
    return {
        "unit_id": str(row.option_id),
        "label": row.name,
        "description": row.description,
        "design_features": features,
        "outcomes_served": list(row.outcomes or []),
    }


def theme_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ThemeContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Group the walk's included options into themes and write them.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``theme`` run.
        context: The walk's intent record.
        backend: The model seam (the longlist backend's theme calls).

    Returns:
        ``{"options", "themes", "no_theme"}``: the included options grouped,
        the themes written and the options under no theme.

    Raises:
        ThemeFailure: If the walk has no ``longlist_result`` or the clustering
            fails.
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    result_row = _latest_longlist(conn, task_id=task_id, scope_id=context.scope_id)
    rows = list(
        conn.execute(
            select(option)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_(None))
            .where(option.c.state == "included")
            .order_by(option.c.created_at, option.c.option_id)
        )
    )
    ceiling = theme_ceiling(len(rows))
    try:
        theme_result = (
            cluster_units(
                [
                    ClusterUnit(unit_id=str(row.option_id), payload=_option_payload(row))
                    for row in rows
                ],
                backend=_ThemeClusteringBackend(backend, question=plan.question),
                policy=_theme_policy(ceiling),
            )
            if rows
            else None
        )
    except ClusteringFailure as exc:
        raise ThemeFailure(f"theme grouping failed: {exc.error}") from exc

    usage = UsageAccumulator()
    themes_out: list[dict[str, Any]] = []
    no_theme = len(rows)
    if theme_result is not None:
        usage.add_payload(theme_result.usage_totals)
        members_by_theme: dict[str, list[str]] = {label.label: [] for label in theme_result.labels}
        for row in rows:
            theme = theme_result.assignments.get(str(row.option_id), RESIDUAL_LABEL)
            if theme != RESIDUAL_LABEL:
                members_by_theme[theme].append(str(row.option_id))
        no_theme = len(rows) - sum(len(ids) for ids in members_by_theme.values())
        themes_out = [
            {
                "theme_id": str(uuid.uuid5(_THEME_ID_NAMESPACE, f"{task_id}:{label.label}")),
                "name": label.label,
                "description": label.description,
                "option_ids": members_by_theme[label.label],
            }
            for label in theme_result.labels
        ]

    counts = dict(result_row.counts) if isinstance(result_row.counts, Mapping) else {}
    counts.update(themes=len(themes_out), no_theme=no_theme)
    provenance = dict(result_row.provenance) if isinstance(result_row.provenance, Mapping) else {}
    provenance["theme"] = {
        "run_id": str(run_id),
        "backend_mode": backend.mode,
        "prompt_version": LONGLIST_THEME_PROMPT_VERSION,
        "model": LONGLIST_JUDGMENT_MODEL if backend.mode == "live" else "stub",
        "theme_ceiling": {
            "formula": "clamp(ceil(n/3), 3, 12)",
            "options": len(rows),
            "ceiling": ceiling,
        },
        "clustering": _engine_stats(theme_result),
        "usage_totals": usage.payload(),
    }
    conn.execute(
        longlist_result.update()
        .where(
            longlist_result.c.longlist_result_id == result_row.longlist_result_id,
            longlist_result.c.task_id == task_id,
        )
        .values(themes=themes_out, counts=counts, provenance=provenance)
    )
    summary = {"options": len(rows), "themes": len(themes_out), "no_theme": no_theme}
    log.info("theme.done", **summary)
    return summary
