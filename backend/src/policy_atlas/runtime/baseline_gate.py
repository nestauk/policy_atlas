"""The options-scoping baseline gate's deterministic card content (task 044, S4).

The gate is the one steer point on the scoping lattice
(``baseline_confirm = PausePoint("after_component", "synthesise")``). Its card
is built from state that already exists — the baseline artefact's *Key
assumption* section and four fields of the approved plan — so nothing here
calls a model, and the same walk always renders the same card.

The runner builds the bundle at the boundary and persists the render on the
pause event (the check-in content of record); ``api/checkin_read.py`` projects
the bundle's display fields back out for the card.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import block, synthesis_result
from policy_atlas.runtime.scoping_plan import ScopingPlan

#: The baseline section whose prose the gate quotes back. Matches the section
#: title the baseline prompt asks for; a stub or degraded artefact may not carry
#: it, which is shown as an absence rather than papered over.
KEY_ASSUMPTION_TITLE = "Key assumption"

#: What the card says when the artefact carries no key-assumption section.
KEY_ASSUMPTION_ABSENT = "Key assumption: not found"

#: The card's heading.
GATE_HEADING = "Confirm the plan against the baseline"


def baseline_settings(plan: ScopingPlan) -> dict[str, Any]:
    """Return the four plan settings the gate shows beside the baseline.

    Args:
        plan: The approved scoping plan the walk ran from.

    Returns:
        ``target_unit``, ``where``, ``outcomes`` (plain strings, tags dropped —
        the card shows what was run, the plan document shows where it came
        from) and ``depth``.
    """
    return {
        "target_unit": plan.target_unit.text,
        "where": plan.where.text,
        "outcomes": [outcome.text for outcome in plan.outcomes],
        "depth": plan.depth,
    }


def read_baseline(
    conn: Connection, *, task_id: uuid.UUID, synthesise_run_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, str | None]:
    """Read the baseline artefact id and its key-assumption prose.

    Args:
        conn: Open read connection.
        task_id: The scoping task.
        synthesise_run_id: The synthesise run the boundary fired for, or
            ``None`` when synthesise left no successful run.

    Returns:
        ``(artefact_id, key_assumption_prose)``. Either element is ``None`` when
        the run, the section or the block is absent — an honest absence, never
        a substitute.
    """
    if synthesise_run_id is None:
        return (None, None)
    row = (
        conn.execute(
            select(synthesis_result.c.artefact_id, synthesis_result.c.blocks)
            .where(synthesis_result.c.task_id == task_id)
            .where(synthesis_result.c.run_id == synthesise_run_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return (None, None)
    artefact_id = row["artefact_id"]
    specs = row["blocks"] if isinstance(row["blocks"], list) else []
    block_id: uuid.UUID | None = None
    for spec in specs:
        if not isinstance(spec, dict) or spec.get("title") != KEY_ASSUMPTION_TITLE:
            continue
        try:
            block_id = uuid.UUID(str(spec.get("block_id")))
        except (TypeError, ValueError):
            block_id = None
        break
    if block_id is None:
        return (artefact_id, None)
    prose = conn.execute(
        select(block.c.content).where(block.c.block_id == block_id)
    ).scalar_one_or_none()
    return (artefact_id, prose if isinstance(prose, str) and prose.strip() else None)


def build_baseline_bundle(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    plan: ScopingPlan,
    synthesise_run_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Build the gate's deterministic decision bundle.

    Args:
        conn: Open read connection.
        task_id: The scoping task.
        plan: The approved scoping plan.
        synthesise_run_id: The synthesise run the boundary fired for.

    Returns:
        ``key_assumption`` (prose or ``None``), ``artefact_id`` (str or
        ``None``) and the four ``settings``.
    """
    artefact_id, key_assumption = read_baseline(
        conn, task_id=task_id, synthesise_run_id=synthesise_run_id
    )
    return {
        "key_assumption": key_assumption,
        "artefact_id": str(artefact_id) if artefact_id is not None else None,
        "settings": baseline_settings(plan),
    }


# Screen words for the one dial (A8: never the internal key on a rendered card).
DEPTH_LABEL: dict[str, str] = {"rapid": "Rapid scoping", "standard": "Standard scoping"}


def render_baseline_gate(bundle: dict[str, Any]) -> str:
    """Render the gate card deterministically from its bundle.

    Args:
        bundle: A :func:`build_baseline_bundle` result, or any mapping shaped
            like one (a projected read-model bundle renders identically).

    Returns:
        The heading, the key assumption (or its stated absence) and the four
        settings, one per line.
    """
    key_assumption = bundle.get("key_assumption")
    lines = [GATE_HEADING]
    if isinstance(key_assumption, str) and key_assumption.strip():
        lines.append(f"{KEY_ASSUMPTION_TITLE}: {key_assumption.strip()}")
    else:
        lines.append(KEY_ASSUMPTION_ABSENT)
    settings = bundle.get("settings")
    if isinstance(settings, dict):
        outcomes = settings.get("outcomes")
        lines.extend(
            [
                "Settings",
                f"Target unit: {settings.get('target_unit')}",
                f"Where: {settings.get('where')}",
                "Outcomes: "
                + ("; ".join(str(item) for item in outcomes) if isinstance(outcomes, list) else ""),
                f"Depth: {DEPTH_LABEL.get(str(settings.get('depth')), settings.get('depth'))}",
            ]
        )
    return "\n".join(lines)
