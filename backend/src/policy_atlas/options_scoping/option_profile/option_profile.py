"""The ``option_profile`` component: all that is said about each option (task 046, R37).

ADR 0040 (amendment 2). The longlist walk runs
``longlist → option_profile → constrain → theme``: ``longlist`` makes the
list, ``option_profile`` writes what is said about each option, ``constrain``
makes verdicts, ``theme`` groups what a reader still sees. It is a spine step:
an :class:`OptionProfileFailure` fails the walk.

This phase holds one call, lever typing, moved out of ``longlist`` as built
(S20). ``option_profile_scope`` reads the walk's latest ``longlist_result``
and the task's options that are not merged, included or not (S16), in the
order ``created_at, option_id``. Typing runs one call per
:data:`~policy_atlas.options_scoping.option_profile.lever_typing_prompt.LEVER_TYPING_BATCH_SIZE`
options, the batches in a thread pool of :data:`TYPING_MAX_CONCURRENT`, with
the place-stripped plan and the baseline. An invalid or failed typing leaves
the option's columns as they are and carries its runner-up and its lever
reason forward from the latest earlier result (task 046, S12).

Writes (S17), all after the last model call: the lever types and the
ambition on each option row typed validly, and on the ``longlist_result`` row,
merged into its JSON as ``theme`` merges, the typing keys the read side reads
(``provenance.runner_up``, ``provenance.lever_reason``,
``provenance.typing``, ``provenance.prompt_versions.typing``,
``provenance.models.typing``, ``provenance.taxonomy_version``,
``counts.none_fits``, ``counts.typing_invalid``) and
``provenance.option_profile``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import tracing
from policy_atlas.core.schema import longlist_result, option
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.options_scoping.longlist.lever_types import (
    AMBITION_BANDS,
    LEVER_TYPE_KEYS,
    TAXONOMY_VERSION,
)
from policy_atlas.options_scoping.longlist.longlist import _seeds
from policy_atlas.options_scoping.longlist.longlist_backend import (
    LONGLIST_JUDGMENT_MODEL,
    LonglistBackend,
)
from policy_atlas.options_scoping.longlist_intent import longlist_plan_data
from policy_atlas.options_scoping.option_profile.lever_typing_prompt import (
    LEVER_TYPING_BATCH_SIZE,
    LEVER_TYPING_PROMPT_VERSION,
    LeverTypingResponse,
)
from policy_atlas.options_scoping.suggest.suggest import baseline_sections, walk_plan

log = structlog.get_logger()

#: Typing batches in flight at once (task 046, S12).
TYPING_MAX_CONCURRENT = 4
#: The reason an unusable typing was recorded under before task 046 (a
#: stored row can still carry it; the read models leave it out of *none
#: fits*). A typing that fails now leaves the option's columns as they are.
TYPING_INVALID_REASON = "typing invalid"


class OptionProfileFailure(Exception):
    """The profile could not be written (no longlist exists for the walk)."""


@dataclass
class OptionProfileContext:
    """Scope-level input to an ``option_profile`` run.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused).
        context: Its context JSONB (unused).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class _ProfiledOption:
    """One option as the typing call reads it (the payload ``longlist`` sent)."""

    option_id: uuid.UUID
    label: str
    description: str
    design_features: list[str]
    #: The option carries a typing already (its columns hold one).
    typed_before: bool


@dataclass(frozen=True)
class _Typing:
    primary: str | None
    secondary: list[str]
    none_fits_reason: str | None
    ambition: str
    ambition_reason: str
    runner_up: str | None
    lever_reason: str | None = None


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
        raise OptionProfileFailure("option_profile: no longlist exists for this walk")
    return row


def _profiled_options(conn: Connection, *, task_id: uuid.UUID) -> list[_ProfiledOption]:
    """The task's options that are not merged, included or not (S16).

    In the order ``created_at, option_id``. Each option's label, description
    and design features are the ones ``longlist`` offers a seed (engine-valid,
    unique labels), so the typing call reads what it read inside ``longlist``.
    """
    rows = conn.execute(
        select(option.c.option_id, option.c.taxonomy_version)
        .where(option.c.task_id == task_id)
        .where(option.c.merged_into_option_id.is_(None))
        .order_by(option.c.created_at, option.c.option_id)
    ).all()
    seeds = {seed.option_id: seed for seed in _seeds(conn, task_id=task_id)}
    return [
        _ProfiledOption(
            option_id=row.option_id,
            label=seeds[row.option_id].label,
            description=seeds[row.option_id].description,
            design_features=seeds[row.option_id].design_features,
            typed_before=row.taxonomy_version is not None,
        )
        for row in rows
    ]


def _validated_typing(wire: Any) -> _Typing | None:
    """One wire typing, validated fail-closed (D8); ``None`` when unusable."""
    primary = wire.primary_lever_type
    reason = (wire.none_fits_reason or "").strip() or None
    ambition = wire.ambition
    ambition_reason = (wire.ambition_reason or "").strip() or None
    if ambition not in AMBITION_BANDS or ambition_reason is None:
        return None
    if primary is None:
        if reason is None:
            return None
    elif primary not in LEVER_TYPE_KEYS:
        return None
    secondary: list[str] = []
    for key in wire.secondary_lever_types:
        if key in LEVER_TYPE_KEYS and key != primary and key not in secondary:
            secondary.append(key)
    runner_up = wire.runner_up_lever_type if wire.runner_up_lever_type in LEVER_TYPE_KEYS else None
    # R29: the reader's sentence for the lever type; a blank one is not
    # shown, and never makes the typing invalid.
    lever_reason = (wire.lever_reason or "").strip() or None
    return _Typing(
        primary=primary,
        secondary=secondary,
        none_fits_reason=reason if primary is None else None,
        ambition=ambition,
        ambition_reason=ambition_reason,
        runner_up=runner_up if runner_up != primary else None,
        lever_reason=lever_reason,
    )


def _type_options(
    backend: LonglistBackend,
    options: Sequence[_ProfiledOption],
    usage: UsageAccumulator,
    *,
    plan: dict[str, object],
    baseline: list[tuple[str, str]],
) -> tuple[dict[uuid.UUID, _Typing], list[uuid.UUID], dict[str, Any]]:
    """Type every option, one call per batch, the batches in a thread pool (S12).

    Returns:
        ``(valid typings, kept option ids, stats)``: an option whose typing
        is invalid, missing or in a failed batch is *kept* — its columns are
        left as they are.
    """
    batches = [
        options[start : start + LEVER_TYPING_BATCH_SIZE]
        for start in range(0, len(options), LEVER_TYPING_BATCH_SIZE)
    ]
    typings: dict[uuid.UUID, _Typing] = {}
    answered: set[uuid.UUID] = set()
    failed_batches = 0
    with ThreadPoolExecutor(max_workers=TYPING_MAX_CONCURRENT) as pool:
        futures = [
            tracing.submit_with_context(
                pool,
                backend.type_options,
                options=[
                    {
                        "unit_id": str(o.option_id),
                        "label": o.label,
                        "description": o.description,
                        "design_features": o.design_features,
                    }
                    for o in batch
                ],
                plan=plan,
                baseline_sections=baseline,
            )
            for batch in batches
        ]
        results: list[UsageResult[LeverTypingResponse] | None] = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as exc:  # fail-closed: the batch's options are kept
                failed_batches += 1
                log.warning("longlist.typing_batch_failed", error_type=type(exc).__name__)
                results.append(None)
    for batch, result in zip(batches, results, strict=True):
        if result is None:
            continue
        response, call_usage = result
        usage.add(call_usage)
        by_unit = {str(o.option_id): o for o in batch}
        for wire in response.typings:
            target = by_unit.get(wire.unit_id)
            if target is None or target.option_id in answered:
                continue
            answered.add(target.option_id)
            typing = _validated_typing(wire)
            if typing is not None:
                typings[target.option_id] = typing
    kept = [o.option_id for o in options if o.option_id not in typings]
    return typings, kept, {
        "calls": len(batches),
        "batch_size": LEVER_TYPING_BATCH_SIZE,
        "max_concurrent": TYPING_MAX_CONCURRENT,
        "failed_batches": failed_batches,
        "invalid": len(kept),
        "kept_ids": [str(option_id) for option_id in kept],
    }


def _earlier_runner_ups(
    conn: Connection, *, task_id: uuid.UUID, option_ids: Sequence[uuid.UUID]
) -> dict[str, dict[str, Any]]:
    """The runner-up a kept typing carries forward (S12).

    Per option, the runner-up of the latest earlier ``longlist_result`` of
    the task that records one for it. A result that typed the option validly
    with no runner-up (it lists the option among its options and not among
    its ``typing.kept_ids``) ends the search: the typing that stands has none.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options whose typing was kept.

    Returns:
        ``{option_id: {"lever_type", "carried_forward": True}}``.
    """

    def _runner_up(entry: Any) -> dict[str, Any] | None:
        lever = entry.get("lever_type") if isinstance(entry, Mapping) else None
        if isinstance(lever, str) and lever in LEVER_TYPE_KEYS:
            return {"lever_type": lever, "carried_forward": True}
        return None

    return _earlier_typing_entries(
        conn, task_id=task_id, option_ids=option_ids, key="runner_up", read=_runner_up
    )


def _earlier_lever_reasons(
    conn: Connection, *, task_id: uuid.UUID, option_ids: Sequence[uuid.UUID]
) -> dict[str, str]:
    """The lever reason a kept typing carries forward (R29), as the runner-up does.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options whose typing was kept.

    Returns:
        ``{option_id: reason}``.
    """

    def _reason(entry: Any) -> str | None:
        return (entry.strip() or None) if isinstance(entry, str) else None

    return _earlier_typing_entries(
        conn, task_id=task_id, option_ids=option_ids, key="lever_reason", read=_reason
    )


def _earlier_typing_entries[T](
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_ids: Sequence[uuid.UUID],
    key: str,
    read: Callable[[Any], T | None],
) -> dict[str, T]:
    """Per kept option, one typing entry of the latest earlier result that has it.

    Walks the task's ``longlist_result`` rows newest first and reads
    ``provenance[key][option_id]`` through ``read``. A result that typed the
    option validly without the entry (it lists the option among its options
    and not among its ``typing.kept_ids``) ends the search: the typing that
    stands has none. The row this walk's ``longlist`` wrote holds no typing
    yet, so it neither supplies an entry nor ends a search.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options whose typing was kept.
        key: The provenance key (``runner_up``, ``lever_reason``).
        read: Returns the usable value of a stored entry, or ``None``.

    Returns:
        ``{option_id: value}`` for each option an earlier result supplies.
    """
    wanted = {str(option_id) for option_id in option_ids}
    found: dict[str, T] = {}
    if not wanted:
        return found
    settled: set[str] = set()
    for (provenance,) in conn.execute(
        select(longlist_result.c.provenance)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
    ):
        record = provenance if isinstance(provenance, Mapping) else {}
        entries = record.get(key)
        entries = entries if isinstance(entries, Mapping) else {}
        typing = record.get("typing")
        kept_ids = typing.get("kept_ids") if isinstance(typing, Mapping) else None
        listed = {
            str(option_id)
            for list_key in ("seed_ids", "discovered_ids")
            for option_id in (record.get(list_key) or [])
        }
        for option_id in wanted - settled:
            value = read(entries.get(option_id))
            if value is not None:
                found[option_id] = value
                settled.add(option_id)
            elif isinstance(kept_ids, list) and option_id in listed and option_id not in kept_ids:
                settled.add(option_id)
        if settled >= wanted:
            break
    return found


def option_profile_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: OptionProfileContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Write what is said about each option of the walk's list (S16, S17, S20).

    Every model call happens before the first write; the writes — the lever
    columns and the ambition of every option typed validly, then the typing
    keys merged into the walk's latest ``longlist_result`` — share the
    component transaction.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``option_profile`` run.
        context: The walk's intent record.
        backend: The model seam (the longlist backend's typing call).

    Returns:
        ``{"options", "typed", "kept", "invalid"}``: the options read, those
        typed validly, those whose earlier typing stands, and those with no
        valid typing from this run (the kept ones and the never typed).

    Raises:
        OptionProfileFailure: If the walk has no ``longlist_result``.
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    result_row = _latest_longlist(conn, task_id=task_id, scope_id=context.scope_id)
    plan_data = longlist_plan_data(plan)
    baseline = baseline_sections(conn, task_id)
    options = _profiled_options(conn, task_id=task_id)

    # Typing (S12): batches in parallel; a kept typing carries forward.
    usage = UsageAccumulator()
    typings, kept_typings, typing_stats = _type_options(
        backend, options, usage, plan=plan_data, baseline=baseline
    )
    runner_ups: dict[str, dict[str, Any]] = {
        str(option_id): {"lever_type": t.runner_up}
        for option_id, t in typings.items()
        if t.runner_up is not None
    }
    runner_ups.update(_earlier_runner_ups(conn, task_id=task_id, option_ids=kept_typings))
    lever_reasons: dict[str, str] = {
        str(option_id): t.lever_reason
        for option_id, t in typings.items()
        if t.lever_reason is not None
    }
    lever_reasons.update(_earlier_lever_reasons(conn, task_id=task_id, option_ids=kept_typings))

    # Writes, all after every model call.
    now = datetime.now(UTC)
    for o in options:
        typing = typings.get(o.option_id)
        if typing is None:
            continue  # kept: the option's columns stay as they are (S12)
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

    none_fits = sum(1 for t in typings.values() if t.primary is None)
    counts = dict(result_row.counts) if isinstance(result_row.counts, Mapping) else {}
    counts.update(none_fits=none_fits, typing_invalid=typing_stats["invalid"])
    provenance = dict(result_row.provenance) if isinstance(result_row.provenance, Mapping) else {}
    live = backend.mode == "live"
    for key, value in (
        ("prompt_versions", LEVER_TYPING_PROMPT_VERSION),
        ("models", LONGLIST_JUDGMENT_MODEL if live else "stub"),
    ):
        entry = provenance.get(key)
        provenance[key] = {**(entry if isinstance(entry, Mapping) else {}), "typing": value}
    provenance.update(
        taxonomy_version=TAXONOMY_VERSION,
        typing=typing_stats,
        runner_up=runner_ups,
        lever_reason=lever_reasons,
        option_profile={
            "run_id": str(run_id),
            "backend_mode": backend.mode,
            "usage_totals": usage.payload(),
        },
    )
    conn.execute(
        longlist_result.update()
        .where(
            longlist_result.c.longlist_result_id == result_row.longlist_result_id,
            longlist_result.c.task_id == task_id,
        )
        .values(counts=counts, provenance=provenance)
    )
    kept_ids = set(kept_typings)
    summary = {
        "options": len(options),
        "typed": len(typings),
        "kept": sum(1 for o in options if o.option_id in kept_ids and o.typed_before),
        "invalid": typing_stats["invalid"],
    }
    log.info("option_profile.done", none_fits=none_fits, **summary)
    return summary
