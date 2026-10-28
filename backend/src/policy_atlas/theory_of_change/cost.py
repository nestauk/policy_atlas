"""What one theory-of-change check walk cost, in tokens and US dollars (task 054, C30).

Each step's ``component.completed`` event already carries its token totals
(``usage_totals``). This adds them up per step and prices them with the model
the route gives that step. The prices are an estimate for the run log, not a
bill: a model missing from :data:`PRICES` is listed as unpriced, never as $0.
Discover's total includes its consolidate call, priced at discover's model.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.model_routes import route
from policy_atlas.core.schema import event_log, runs

log = structlog.get_logger()

#: US dollars per million tokens: (input, cached input, output).
PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
    "gpt-6.1-sol": (2.00, 0.10, 10.00),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
    "gpt-5.6-terra": (2.00, 0.20, 12.00),
}

#: A walk component whose route step has another name.
_STEP_OF: dict[str, str] = {"toc_select": "toc_pick", "toc_search_new": "toc_pick"}


def usd(model: str, usage: dict[str, int]) -> float | None:
    """Price one step's tokens, or ``None`` when the model has no price.

    Args:
        model: The model id.
        usage: ``prompt`` (cached included), ``cached`` and ``completion`` tokens.

    Returns:
        The estimate in US dollars, or ``None``.
    """
    price = PRICES.get(model)
    if price is None:
        return None
    prompt, cached = usage.get("prompt", 0), usage.get("cached", 0)
    return (
        (prompt - cached) * price[0] + cached * price[1] + usage.get("completion", 0) * price[2]
    ) / 1_000_000


def walk_cost(conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> dict[str, Any]:
    """Token totals per step of one walk and their US-dollar estimate.

    Args:
        conn: Open connection.
        task_id: The task.
        walk_id: The walk (capability run).

    Returns:
        ``steps`` (component → model, tokens and ``usd`` or ``None``), the
        ``usd`` total of the priced steps, and the ``unpriced`` models.
    """
    steps: dict[str, dict[str, Any]] = {}
    for payload in conn.execute(
        select(event_log.c.payload)
        .select_from(
            event_log.join(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(runs.c.capability_run_id == walk_id)
        .where(event_log.c.event_type == "component.completed")
        .order_by(event_log.c.sequence)
    ).scalars():
        usage = payload.get("usage_totals")
        if not isinstance(usage, dict) or not usage.get("total"):
            continue
        component = str(payload.get("component"))
        name = _STEP_OF.get(component, component)
        step = steps.setdefault(
            component,
            {
                "model": route().model_for(name) if name in route().steps else "unknown",
                "prompt": 0,
                "cached": 0,
                "completion": 0,
            },
        )
        for key in ("prompt", "cached", "completion"):
            step[key] += int(usage.get(key) or 0)
    for step in steps.values():
        step["usd"] = usd(step["model"], step)
    priced = [step["usd"] for step in steps.values() if step["usd"] is not None]
    return {
        "steps": steps,
        "usd": round(sum(priced), 4),
        "unpriced": sorted({s["model"] for s in steps.values() if s["usd"] is None}),
    }
