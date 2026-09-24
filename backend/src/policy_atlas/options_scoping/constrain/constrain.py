"""The ``constrain`` component: the longlist walk's last step (task 045, S9).

Contract deliverable 7, D9, D10, D21, D22; ADR 0039 decisions 7 and 10.

1. **Judgements.** Every option of the task — included and excluded — is
   judged, one call per :data:`CONSTRAIN_BATCH_SIZE` options on the judgment
   model (``constrain_v1``), against the plan's ``requirement`` constraints
   (a setting requirement among them, D21) followed by the three
   :data:`DEFAULT_SCREENS`, on the option's specified design and a compact
   coverage summary. The response is validated fail-closed; a malformed batch
   is retried once, then its options are recorded ``cannot_check`` on every
   constraint ("judgement unavailable") — never a crash, never an exclusion.
2. **Verdicts → state.** A ``breaks`` on a requirement or a screen excludes
   the option, naming the constraint (the first that broke, requirements
   before screens). *Distinct* never applies to an option with a ``part_of``
   relation at either end: its verdict is forced to ``passes``. A *distinct*
   ``breaks`` applies only to a later duplicate: its reason must name (by
   label or id) another option of the same batch that comes earlier in
   :func:`_duplicate_order` and stays on the list; the earliest of a group is
   kept (``passes``, :data:`DUPLICATE_KEPT_REASON`), and a ``breaks`` that
   names no option of its batch is recorded ``cannot_check``
   (:data:`DUPLICATE_UNNAMED_REASON`) — never an exclusion on a guess. A
   later duplicate whose first break is *distinct* is **merged, not
   excluded** (owner ruling 2026-09-24): ``merged_into_option_id`` names the
   kept option (the final one of a chain, never a merged one), its
   memberships move there (a unit the kept option already holds stays put),
   the kept option's coverage is recomputed, and its own ``state`` and
   ``exclusion`` are left as they were — it leaves the list through the
   merge. Its judgement record still shows the *distinct* verdict. A
   user-held duplicate is never merged away. Merged options are not judged
   again on a rebuild. A
   batch that stays malformed keeps every option's prior state and
   ``exclusion``; a ``breaks`` with a blank reason makes a batch malformed.
   On a rebuild
   every option is re-judged: one constrain excluded last time and now
   passing is included again. **User state always wins**: a row whose
   ``exclusion.by`` is ``"user"`` keeps its ``state`` and ``exclusion``
   untouched, whichever state that is. That is the marker this slice
   defines with the row's existing fields: the user's *exclude* writes
   ``state="excluded"`` with ``exclusion.by="user"``, and the user's
   *include again* writes ``state="included"`` and keeps an ``exclusion``
   record with ``by="user"`` (the read models show ``exclusion`` only when
   ``state == "excluded"``). A row with no ``exclusion``, or one written
   ``by="constrain"``, is constrain's to set. Thin evidence never excludes:
   nothing here reads a document count as an input to the state.
3. **Guesses.** One capped reasoned guess per preference and option, the
   default transferability preference removed before the call (D22: no guess
   before assessment). A guess never changes state.
4. **No in-scope evidence** (:mod:`.in_scope`), deterministic, no model call.
5. **Writes.** ``longlist_result.judgements`` and ``.guesses`` of the walk's
   latest longlist row, keyed ``[option_id][design_version]`` (D10), its
   ``counts`` (and, after a merge, the kept options' ``coverage``) updated;
   the option rows' ``state``, ``exclusion``, ``no_in_scope_evidence``,
   ``merged_into_option_id`` and ``updated_at``; a merged duplicate's
   memberships. Every model call happens
   before the first write.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import exists, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import longlist_result, option, option_membership, option_relation
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.options_scoping.constrain.constrain_prompt import (
    CONSTRAIN_BATCH_SIZE,
    CONSTRAIN_PROMPT_VERSION,
    DEFAULT_SCREENS,
    ConstrainResponse,
)
from policy_atlas.options_scoping.constrain.in_scope import in_scope_evidence
from policy_atlas.options_scoping.longlist.longlist import membership_coverage
from policy_atlas.options_scoping.longlist.longlist_backend import LONGLIST_JUDGMENT_MODEL
from policy_atlas.options_scoping.suggest.suggest import walk_plan
from policy_atlas.runtime.scoping_plan import TRANSFERABILITY_DEFAULT, ScopingPlan

log = structlog.get_logger()

#: Attempts per batch: the call and one retry.
BATCH_ATTEMPTS = 2
#: The reason recorded when a batch stays malformed after its retry.
JUDGEMENT_UNAVAILABLE = "judgement unavailable"
#: The forced *distinct* reason for an option in a package relation (ruling 36).
PACKAGE_DISTINCT_REASON = "packages and their parts are shown together"
#: The *distinct* reason for the earliest option of a duplicate group (kept).
DUPLICATE_KEPT_REASON = "the first of its duplicates on the longlist is kept"
#: The *distinct* reason when a ``breaks`` names no other option of its batch.
DUPLICATE_UNNAMED_REASON = "the option it duplicates could not be identified"
#: Origins a duplicate group keeps first: the user's and Evidence search's own.
_KEPT_FIRST_ORIGINS = frozenset({"added_by_you", "from_evidence_search"})
#: The ``judgements`` key of the deterministic in-scope record. Not
#: ``"in_scope"``: that id is the *within scope* default screen's.
IN_SCOPE_EVIDENCE_KEY = "in_scope_evidence"
#: Setting texts shown per option in the coverage summary.
COVERAGE_SETTINGS_MAX = 5

_DISTINCT = "distinct"


class ConstrainFailure(Exception):
    """Constrain could not run (no longlist for the walk)."""


class ConstrainBackend(Protocol):
    """The seam :func:`constrain_scope` calls; the longlist backends satisfy it."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``."""
        ...

    def constrain(
        self,
        *,
        plan: dict[str, object],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[ConstrainResponse]:
        """Judge one batch (see ``LonglistBackend.constrain``)."""
        ...


@dataclass
class ConstrainContext:
    """Scope-level input to a ``constrain`` run.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused).
        context: Its context JSONB (unused).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class _Verdict:
    verdict: str
    reason: str


@dataclass(frozen=True)
class _Judged:
    verdicts: dict[str, _Verdict]
    guesses: dict[str, tuple[str, str]]  # preference id -> (guess, leaning)


def user_holds_state(exclusion: object) -> bool:
    """Whether the user set this option's state (user state always wins).

    Args:
        exclusion: The option row's ``exclusion`` JSONB.

    Returns:
        ``True`` when ``exclusion.by == "user"``.
    """
    return isinstance(exclusion, Mapping) and exclusion.get("by") == "user"


def _plan_data(plan: ScopingPlan) -> dict[str, object]:
    return {
        "question": plan.question,
        "target_unit": plan.target_unit.text,
        "intended_change": plan.intended_change.text,
        "outcomes": [outcome.text for outcome in plan.outcomes],
    }


def _constraint_lists(
    plan: ScopingPlan,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """``(requirements + default screens, preferences minus transferability)``."""
    requirements = [
        {"id": f"req-{i}", "text": c.text}
        for i, c in enumerate((c for c in plan.constraints if c.kind == "requirement"), start=1)
    ]
    requirements += [{"id": key, "text": label} for key, label in DEFAULT_SCREENS]
    preferences = [
        {"id": f"pref-{i}", "text": c.text}
        for i, c in enumerate(
            (
                c
                for c in plan.constraints
                if c.kind == "preference" and c.default != TRANSFERABILITY_DEFAULT
            ),
            start=1,
        )
    ]
    return requirements, preferences


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
        raise ConstrainFailure("constrain: no longlist exists for this walk")
    return row


def _relations(
    conn: Connection, *, task_id: uuid.UUID, labels: Mapping[uuid.UUID, str]
) -> dict[uuid.UUID, list[dict[str, object]]]:
    """Each option's ``part_of`` relations, from both ends."""
    out: dict[uuid.UUID, list[dict[str, object]]] = {}
    rows = conn.execute(
        select(option_relation.c.from_option_id, option_relation.c.to_option_id)
        .where(option_relation.c.task_id == task_id, option_relation.c.kind == "part_of")
        .order_by(option_relation.c.created_at, option_relation.c.relation_id)
    )
    for row in rows:
        component, package = row.from_option_id, row.to_option_id
        out.setdefault(component, []).append(
            {
                "kind": "part_of",
                "role": "component",
                "other_option_id": str(package),
                "other_label": labels.get(package, ""),
            }
        )
        out.setdefault(package, []).append(
            {
                "kind": "part_of",
                "role": "package",
                "other_option_id": str(component),
                "other_label": labels.get(component, ""),
            }
        )
    return out


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _coverage_summary(coverage: object, where_labels: Mapping[str, str]) -> dict[str, object]:
    """A compact coverage summary: context for the screens, never an exclusion input."""
    cov = _mapping(coverage)
    roles = _mapping(cov.get("role"))
    where = _mapping(cov.get("where_tried"))
    settings = _mapping(cov.get("settings"))
    top_settings = sorted(settings.items(), key=lambda kv: (-int(kv[1] or 0), str(kv[0])))
    return {
        "documents": int(cov.get("documents") or 0),
        "evaluated": int(roles.get("evaluated") or 0),
        "roles": {str(k): int(v or 0) for k, v in roles.items()},
        "where_tried": {
            where_labels.get(str(k), str(k)): int(v or 0) for k, v in where.items() if v
        },
        "settings": [str(text) for text, _ in top_settings[:COVERAGE_SETTINGS_MAX]],
    }


def _option_data(
    row: Any,
    relations: list[dict[str, object]],
    coverage: object,
    where_labels: Mapping[str, str],
) -> dict[str, object]:
    design = row.design if isinstance(row.design, Mapping) else {}
    features = design.get("design_features")
    outcomes = design.get("outcomes_served")
    return {
        "option_id": str(row.option_id),
        "label": row.name,
        "description": row.description,
        "design_features": list(features) if isinstance(features, list) else [],
        "outcomes_served": (
            list(outcomes) if isinstance(outcomes, list) else list(row.outcomes or [])
        ),
        "relations": relations,
        "coverage": _coverage_summary(coverage, where_labels),
    }


def _validated(
    response: ConstrainResponse,
    *,
    option_ids: Sequence[str],
    requirement_ids: Sequence[str],
    preference_ids: Sequence[str],
) -> dict[str, _Judged] | None:
    """The batch's judgements, or ``None`` when the response is malformed.

    Every option exactly once; per option every requirement/screen id exactly
    once and every preference id exactly once; nothing else.
    """
    seen = [o.option_id for o in response.options]
    if sorted(seen) != sorted(option_ids):
        return None
    out: dict[str, _Judged] = {}
    for wire in response.options:
        judged = [j.constraint_id for j in wire.judgements]
        guessed = [g.constraint_id for g in wire.guesses]
        if sorted(judged) != sorted(requirement_ids) or sorted(guessed) != sorted(
            preference_ids
        ):
            return None
        if any(j.verdict == "breaks" and not j.reason.strip() for j in wire.judgements):
            return None  # an exclusion must name why
        out[wire.option_id] = _Judged(
            verdicts={
                j.constraint_id: _Verdict(j.verdict, j.reason.strip()) for j in wire.judgements
            },
            guesses={g.constraint_id: (g.guess.strip(), g.leaning) for g in wire.guesses},
        )
    return out


def _unavailable(requirement_ids: Sequence[str]) -> _Judged:
    return _Judged(
        verdicts={cid: _Verdict("cannot_check", JUDGEMENT_UNAVAILABLE) for cid in requirement_ids},
        guesses={},
    )


def _judge(
    backend: ConstrainBackend,
    *,
    plan: dict[str, object],
    requirements: list[dict[str, str]],
    preferences: list[dict[str, str]],
    options: list[dict[str, object]],
    usage: UsageAccumulator,
) -> tuple[dict[str, _Judged], dict[str, int], set[str]]:
    """Judge every option, batch by batch; a malformed batch degrades.

    Returns ``(judged, stats, failed)``; ``failed`` holds the option ids of
    the batches that stayed malformed.
    """
    requirement_ids = [r["id"] for r in requirements]
    preference_ids = [p["id"] for p in preferences]
    judged: dict[str, _Judged] = {}
    failed: set[str] = set()
    stats = {"calls": 0, "retries": 0, "failed_batches": 0}
    for start in range(0, len(options), CONSTRAIN_BATCH_SIZE):
        batch = options[start : start + CONSTRAIN_BATCH_SIZE]
        option_ids = [str(o["option_id"]) for o in batch]
        result: dict[str, _Judged] | None = None
        for attempt in range(BATCH_ATTEMPTS):
            stats["calls"] += 1
            if attempt:
                stats["retries"] += 1
            try:
                response, call_usage = backend.constrain(
                    plan=plan, requirements=requirements, preferences=preferences, options=batch
                )
            except Exception as exc:  # fail-closed: a failed call is a malformed batch
                log.warning("constrain.batch_call_failed", error_type=type(exc).__name__)
                continue
            usage.add(call_usage)
            result = _validated(
                response,
                option_ids=option_ids,
                requirement_ids=requirement_ids,
                preference_ids=preference_ids,
            )
            if result is not None:
                break
            log.warning("constrain.batch_malformed", attempt=attempt, options=len(batch))
        if result is None:
            stats["failed_batches"] += 1
            failed.update(option_ids)
            result = {oid: _unavailable(requirement_ids) for oid in option_ids}
        judged.update(result)
    return judged, stats, failed


def _duplicate_order(row: Any) -> tuple[bool, Any, str]:
    """A duplicate group's keep order: the user's and Evidence search's
    options first, then the earliest created, then the lowest id."""
    return (row.origin not in _KEPT_FIRST_ORIGINS, row.created_at, str(row.option_id))


def _named_options(reason: str, candidates: Sequence[tuple[str, str]]) -> set[str]:
    """The candidate option ids a *distinct* reason names, by id or label.

    Labels are matched case-insensitively on word boundaries, longest first;
    a label found only inside a longer matched label ("Mentoring" inside
    "Youth mentoring") does not count.
    """
    text = reason.casefold()
    named = {oid for oid, _ in candidates if oid.casefold() in text}
    by_label: dict[str, list[str]] = {}
    for oid, label in candidates:
        if label.strip():
            by_label.setdefault(label.strip().casefold(), []).append(oid)
    claimed: list[tuple[int, int]] = []
    for label in sorted(by_label, key=lambda lab: (-len(lab), lab)):
        for match in re.finditer(rf"(?<!\w){re.escape(label)}(?!\w)", text):
            start, end = match.span()
            if all(end <= s or start >= e for s, e in claimed):
                claimed.append((start, end))
                named.update(by_label[label])
    return named


def _move_memberships(
    conn: Connection, *, task_id: uuid.UUID, duplicate: uuid.UUID, kept: uuid.UUID
) -> None:
    """Move a merged duplicate's memberships to the kept option.

    A unit the kept option already holds stays on the duplicate
    (``uq_om_option_unit``); the kept option shows it once.
    """
    om = option_membership
    held = om.alias("held")
    conn.execute(
        om.update()
        .where(om.c.task_id == task_id, om.c.option_id == duplicate)
        .where(
            ~exists().where(
                held.c.task_id == task_id,
                held.c.option_id == kept,
                held.c.unit_kind == om.c.unit_kind,
                held.c.unit_id == om.c.unit_id,
            )
        )
        .values(option_id=kept)
    )


def constrain_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ConstrainContext,
    backend: ConstrainBackend,
) -> dict[str, Any]:
    """Judge every option of the walk's longlist and write the verdicts.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``constrain`` run.
        context: The walk's intent record.
        backend: The model seam (the longlist backend's ``constrain``).

    Returns:
        ``{"options", "excluded", "no_in_scope", "cannot_check", "guesses"}``
        — ``options`` counts the options judged (a merged duplicate among
        them; ``longlist_result.counts.merged`` counts those); ``excluded``
        counts every excluded option on the list after this run (user
        exclusions included); ``cannot_check`` counts options with at least
        one ``cannot_check`` verdict; ``guesses`` counts the guesses written.

    Raises:
        ConstrainFailure: If the walk has no ``longlist_result``.
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    result_row = _latest_longlist(conn, task_id=task_id, scope_id=context.scope_id)
    rows = list(
        conn.execute(
            select(option)
            .where(option.c.task_id == task_id)
            .where(option.c.merged_into_option_id.is_(None))  # merged: off the list
            .order_by(option.c.created_at, option.c.option_id)
        )
    )
    labels = {row.option_id: row.name for row in rows}
    relations = _relations(conn, task_id=task_id, labels=labels)
    coverage = result_row.coverage if isinstance(result_row.coverage, Mapping) else {}
    provenance = dict(result_row.provenance) if isinstance(result_row.provenance, Mapping) else {}
    where_labels_raw = provenance.get("where_tried_labels")
    where_labels = (
        {str(k): str(v) for k, v in where_labels_raw.items()}
        if isinstance(where_labels_raw, Mapping)
        else {}
    )
    requirements, preferences = _constraint_lists(plan)
    texts = {r["id"]: r["text"] for r in requirements + preferences}

    # 1. Every model call, before any write.
    usage = UsageAccumulator()
    judged, stats, failed = _judge(
        backend,
        plan=_plan_data(plan),
        requirements=requirements,
        preferences=preferences,
        options=[
            _option_data(
                row,
                relations.get(row.option_id, []),
                coverage.get(str(row.option_id)),
                where_labels,
            )
            for row in rows
        ],
        usage=usage,
    )
    # 2. Verdicts -> state or merge, earlier options first, so a duplicate's
    # partner is settled before it. No write yet.
    batch_of = {row.option_id: i // CONSTRAIN_BATCH_SIZE for i, row in enumerate(rows)}
    ordered = sorted(rows, key=_duplicate_order)
    rank = {row.option_id: i for i, row in enumerate(ordered)}
    final_state: dict[uuid.UUID, str] = {}
    merged_into: dict[uuid.UUID, uuid.UUID] = {}
    decided: list[tuple[Any, dict[str, _Verdict], str, dict[str, Any]]] = []

    def kept_as(other: uuid.UUID) -> uuid.UUID | None:
        """The option on the list that stands for ``other``, if any."""
        if other in merged_into:
            return merged_into[other]
        return other if final_state.get(other) == "included" else None

    for row in ordered:
        oid = str(row.option_id)
        verdicts = dict(judged[oid].verdicts)
        kept: uuid.UUID | None = None
        if row.option_id in relations:
            verdicts[_DISTINCT] = _Verdict("passes", PACKAGE_DISTINCT_REASON)
        elif verdicts[_DISTINCT].verdict == "breaks":
            candidates = [
                (str(other.option_id), other.name)
                for other in rows
                if batch_of[other.option_id] == batch_of[row.option_id]
            ]
            named = _named_options(verdicts[_DISTINCT].reason, candidates) - {oid}
            partners = {kept_as(uuid.UUID(other)) for other in named} - {None}
            kept = min(partners, key=lambda p: rank[p]) if partners else None
            if not named:
                verdicts[_DISTINCT] = _Verdict("cannot_check", DUPLICATE_UNNAMED_REASON)
            elif kept is None:
                verdicts[_DISTINCT] = _Verdict("passes", DUPLICATE_KEPT_REASON)
        values: dict[str, Any] = {}
        if user_holds_state(row.exclusion) or oid in failed:
            # User state always wins (a user-held duplicate is never merged
            # away); a failed batch keeps the prior state.
            state = row.state
        else:
            broken = next(
                (r for r in requirements if verdicts[r["id"]].verdict == "breaks"), None
            )
            if broken is None:
                state = "included"
                values.update(state="included", exclusion=None)
            elif broken["id"] == _DISTINCT and kept is not None:
                # Merged, not excluded: its state stays as it was.
                state = row.state
                merged_into[row.option_id] = kept
                values.update(merged_into_option_id=kept)
            else:
                state = "excluded"
                values.update(
                    state="excluded",
                    exclusion={
                        "constraint": broken["text"],
                        "reason": verdicts[broken["id"]].reason,
                        "by": "constrain",
                    },
                )
        final_state[row.option_id] = state
        decided.append((row, verdicts, state, values))

    # 3. The merges' writes: memberships to the kept option, its coverage
    # recomputed; then the deterministic in-scope check (no model call) over
    # the options on the list, reading the moved memberships.
    for duplicate, kept_id in merged_into.items():
        _move_memberships(conn, task_id=task_id, duplicate=duplicate, kept=kept_id)
    coverage_updates = (
        membership_coverage(
            conn,
            task_id=task_id,
            scope_id=context.scope_id,
            where=plan.where.text,
            option_ids=sorted(set(merged_into.values()), key=str),
        )
        if merged_into
        else {}
    )
    in_scope = in_scope_evidence(
        conn,
        task_id=task_id,
        plan=plan,
        option_ids=[row.option_id for row in rows if row.option_id not in merged_into],
    )

    # 4. Judgements, guesses and the option rows.
    now = datetime.now(UTC)
    judgements: dict[str, dict[str, dict[str, Any]]] = {}
    guesses: dict[str, dict[str, dict[str, Any]]] = {}
    states: Counter[str] = Counter()
    cannot_check = 0
    guess_count = 0
    no_in_scope = 0
    for row, verdicts, state, values in decided:
        oid = str(row.option_id)
        version = str(row.design_version)
        entry = judged[oid]
        record: dict[str, Any] = {
            cid: {
                "verdict": verdicts[cid].verdict,
                "reason": verdicts[cid].reason,
                "constraint_text": texts[cid],
            }
            for cid in (r["id"] for r in requirements)
        }
        if entry.guesses:
            guesses[oid] = {
                version: {
                    cid: {"guess": guess, "leaning": leaning, "constraint_text": texts[cid]}
                    for cid, (guess, leaning) in entry.guesses.items()
                }
            }
            guess_count += len(entry.guesses)
        if any(v.verdict == "cannot_check" for v in verdicts.values()):
            cannot_check += 1
        values["updated_at"] = now
        if row.option_id not in merged_into:
            check = in_scope.get(row.option_id)
            marked = bool(check and check["no_in_scope_evidence"])
            if check is not None:
                record[IN_SCOPE_EVIDENCE_KEY] = {
                    "restriction": check["restriction"],
                    "in_scope_documents": check["in_scope_documents"],
                    "documents": check["documents"],
                }
            no_in_scope += int(marked)
            values["no_in_scope_evidence"] = marked
            states[state] += 1
        judgements[oid] = {version: record}
        conn.execute(
            option.update()
            .where(option.c.option_id == row.option_id, option.c.task_id == task_id)
            .values(**values)
        )

    # 5. The walk's longlist row.
    counts = dict(result_row.counts) if isinstance(result_row.counts, Mapping) else {}
    counts.update(
        options=len(rows) - len(merged_into),
        merged=len(merged_into),
        included=states["included"],
        excluded=states["excluded"],
        no_in_scope_evidence=no_in_scope,
        cannot_check=cannot_check,
        guesses=guess_count,
    )
    live = backend.mode == "live"
    provenance["constrain"] = {
        "run_id": str(run_id),
        "backend_mode": backend.mode,
        "prompt_version": CONSTRAIN_PROMPT_VERSION,
        "model": LONGLIST_JUDGMENT_MODEL if live else "stub",
        "batch_size": CONSTRAIN_BATCH_SIZE,
        **stats,
        "requirements": len(requirements) - len(DEFAULT_SCREENS),
        "preferences": len(preferences),
        "usage_totals": usage.payload(),
    }
    conn.execute(
        longlist_result.update()
        .where(
            longlist_result.c.longlist_result_id == result_row.longlist_result_id,
            longlist_result.c.task_id == task_id,
        )
        .values(
            judgements=judgements,
            guesses=guesses,
            counts=counts,
            provenance=provenance,
            coverage={**coverage, **coverage_updates},
        )
    )
    summary = {
        "options": len(rows),
        "excluded": states["excluded"],
        "no_in_scope": no_in_scope,
        "cannot_check": cannot_check,
        "guesses": guess_count,
    }
    log.info(
        "constrain.done",
        **summary,
        merged=len(merged_into),
        failed_batches=stats["failed_batches"],
    )
    return summary
