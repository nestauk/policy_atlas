"""The ``constrain`` component: verdicts on the longlist (task 045, S9; task 046, S6, S13, S18).

Contract deliverable 7, D9, D10, D21, D22; ADR 0039 decisions 7 and 10;
task 046 items 5, 7, 10, 11, 12, R4, R21, R38, AM6, AM7.

1. **Distinct** (task 046, S13). One call over the whole list — every option
   that is not merged, with its label, description, design features, origin
   and relations — made before the batches (``constrain_v2``'s distinct
   prompt). Each reported pair is checked: a pair naming an unknown id, the
   same id twice, a duplicate already reported, or a chain (the option
   named as kept is itself reported as a duplicate) is dropped and counted.
   Code, not the call, decides which option of a duplicate group is kept
   (the merge rule of 2026-09-24, components § 7): the user's option first,
   then Evidence search's, then the earliest created
   (:func:`_keep_order`), whichever side of a pair the call put it on. The
   duplicate's *distinct*
   verdict is ``breaks`` with a reason naming the kept option; every other
   option ``passes``. A call that fails or stays malformed after its retry
   gives every option ``cannot_check`` on *distinct* and no merge.
2. **Judgements.** Every option of the task — included and excluded — is
   judged, one call per :data:`CONSTRAIN_BATCH_SIZE` options on the judgment
   model, the batches in a thread pool of :data:`CONSTRAIN_MAX_CONCURRENT`,
   against the plan's ``boundary`` constraints (a setting requirement
   among them, D21, verbatim, AM7) followed by the :data:`DEFAULT_SCREENS`
   (*relevant*, *within scope*), on the option's specified design, a compact
   coverage summary (no ``where_tried``: AM7) and the baseline. The plan
   fields reach the prompt with their place removed (:func:`_plan_data`,
   S6); the removed spans are recorded in ``provenance.constrain.
   place_removed``. The response is validated fail-closed; a malformed batch
   is retried once, then its options are recorded ``cannot_check`` on every
   requirement and screen ("judgement unavailable") — never a crash, never
   an exclusion.
3. **Verdicts → state.** A ``breaks`` on a requirement or a screen excludes
   the option, naming the constraint (the first that broke: requirements,
   then *relevant*, *distinct*, *within scope*). *Distinct* never applies to
   an option with a ``part_of`` relation at either end: its verdict is forced
   to ``passes``. Kept options are settled before their duplicates. A
   duplicate whose first break is *distinct* is **merged, not excluded**
   (owner ruling 2026-09-24) when its kept option stays on the list:
   ``merged_into_option_id`` names the kept option, its memberships move
   there (a unit the kept option already holds stays put), the kept option's
   coverage is recomputed, and its own ``state`` and ``exclusion`` are left
   as they were — it leaves the list through the merge. Its judgement record
   still shows the *distinct* verdict. When the kept option leaves the list
   (excluded), the duplicate is the one kept (``passes``,
   :data:`DUPLICATE_KEPT_REASON`). A user-held duplicate is never merged
   away. Merged options are not judged again on a rebuild. A batch that
   stays malformed keeps every option's prior state and ``exclusion`` (and
   no merge); a ``breaks`` with a blank reason makes a batch malformed. On a
   rebuild every option is re-judged: one constrain excluded last time and
   now passing is included again. **User state always wins**: a row whose
   ``exclusion.by`` is ``"user"`` keeps its ``state`` and ``exclusion``
   untouched, whichever state that is. That is the marker this slice
   defines with the row's existing fields: the user's *exclude* writes
   ``state="excluded"`` with ``exclusion.by="user"``, and the user's
   *include again* writes ``state="included"`` and keeps an ``exclusion``
   record with ``by="user"`` (the read models show ``exclusion`` only when
   ``state == "excluded"``). A row with no ``exclusion``, or one written
   ``by="constrain"``, is constrain's to set. Thin evidence never excludes:
   nothing here reads a document count as an input to the state.
4. **Guesses.** One capped reasoned guess per preference and option, the
   default transferability preference removed before the call (D22: no guess
   before assessment). A guess never changes state.
5. **No in-scope evidence** (:mod:`.in_scope`), deterministic, no model call.
6. **The authority label** (task 046, R38, S18). Made only when the plan
   holds a consideration on ``who_decides``; with none there is no call and
   no label (``provenance.constrain.authority == {"calls": 0}``). With one
   or more: ONE call over the whole list — every option that is not merged
   and that has an entry for its current design version in the latest
   row's ``option_profile`` — run at the same time as the distinct call and
   the batches. It reads the considerations' texts and, per option, its id,
   label, description, design features and the sentence of its line
   ``who_decides``. That sentence can name a country: it is the ONE place
   text constrain reads (amendment 2 § 2.4). The plan data, the batches and
   the distinct call still get no place and no profile line. The answer is
   checked fail-closed (every option sent exactly once, no other id, a
   reason, a body for ``needs_action_by``); a raised or malformed call is
   tried once more, and one that fails again gives no option a label
   (``authority.failed``) — never a crash, never an exclusion. The label is
   stored in the option's judgement record under :data:`AUTHORITY_KEY`,
   never in ``option_profile``. It has no verdict: it is never a check, it
   never excludes, and no consideration changes an option's state. A
   duplicate merged in this run, and an option with no profile entry (added
   after the build), get no label.
7. **Writes.** ``longlist_result.judgements`` and ``.guesses`` of the walk's
   latest longlist row, keyed ``[option_id][design_version]`` (D10), its
   ``counts`` (and, after a merge, the kept options' ``coverage``) updated;
   the option rows' ``state``, ``exclusion``, ``no_in_scope_evidence``,
   ``merged_into_option_id`` and ``updated_at``; a merged duplicate's
   memberships. Every model call — the distinct call, every batch and the
   authority call — happens before the first write.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import exists, select
from sqlalchemy.engine import Connection

from policy_atlas.core import tracing
from policy_atlas.core.schema import longlist_result, option, option_membership, option_relation
from policy_atlas.core.usage import TokenUsage, UsageAccumulator, UsageResult
from policy_atlas.options_scoping.constrain.constrain_prompt import (
    CONSTRAIN_BATCH_SIZE,
    CONSTRAIN_PROMPT_VERSION,
    DEFAULT_SCREENS,
    DISTINCT_SCREEN,
    AuthorityLabel,
    AuthorityResponse,
    ConstrainResponse,
    DistinctResponse,
)
from policy_atlas.options_scoping.constrain.in_scope import in_scope_evidence
from policy_atlas.options_scoping.longlist.coverage import stored_folds
from policy_atlas.options_scoping.longlist.longlist import (
    ON_THE_LIST,
    ORIGIN_WORDS,
    membership_coverage,
)
from policy_atlas.options_scoping.longlist.longlist_backend import LONGLIST_JUDGMENT_MODEL
from policy_atlas.options_scoping.longlist.where_tried import strip_place
from policy_atlas.options_scoping.suggest.suggest import baseline_sections, walk_plan
from policy_atlas.runtime.scoping_plan import TRANSFERABILITY_DEFAULT, ScopingPlan

log = structlog.get_logger()

#: Attempts per batch and for the distinct call: the call and one retry.
BATCH_ATTEMPTS = 2
#: Constrain batches in flight at once (task 046, S13).
CONSTRAIN_MAX_CONCURRENT = 4
#: The reason recorded when a batch or the distinct call stays malformed.
JUDGEMENT_UNAVAILABLE = "judgement unavailable"
#: The forced *distinct* reason for an option in a package relation (ruling 36).
PACKAGE_DISTINCT_REASON = "packages and their parts are shown together"
#: The *distinct* reason for an option the distinct call reported no duplicate of.
DISTINCT_PASSES_REASON = "no other option on the longlist is the same kind of action"
#: The *distinct* reason for a duplicate whose kept option left the list.
DUPLICATE_KEPT_REASON = "the first of its duplicates on the longlist is kept"
#: Origins a duplicate group keeps first, in this order: the user's, then
#: Evidence search's own (components § 7, the merge rule of 2026-09-24).
_KEPT_FIRST_ORIGINS: tuple[str, ...] = ("added_by_you", "from_evidence_search")
#: The ``judgements`` key of the deterministic in-scope record. Not
#: ``"in_scope"``: that id is the *within scope* default screen's.
IN_SCOPE_EVIDENCE_KEY = "in_scope_evidence"
#: The ``judgements`` key of the authority label (task 046, S18). It holds no
#: verdict: nothing that reads the checks reads it.
AUTHORITY_KEY = "authority"
#: The consideration aspect the authority label answers (R38).
WHO_DECIDES = "who_decides"
#: Joins the considerations' texts in the stored ``consideration_text``.
CONSIDERATION_JOIN = " · "
#: The labels, in the order the provenance counts them.
AUTHORITY_LABELS: tuple[AuthorityLabel, ...] = ("within_your_power", "needs_action_by", "unclear")
#: Setting texts shown per option in the coverage summary.
COVERAGE_SETTINGS_MAX = 5

_DISTINCT = DISTINCT_SCREEN[0]


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
        baseline_sections: list[tuple[str, str]],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[ConstrainResponse]:
        """Judge one batch (see ``LonglistBackend.constrain``); called from a thread pool."""
        ...

    def distinct(self, *, options: list[dict[str, object]]) -> UsageResult[DistinctResponse]:
        """Report the duplicates over the whole list (see ``LonglistBackend.distinct``)."""
        ...

    def authority(
        self, *, considerations: list[str], options: list[dict[str, object]]
    ) -> UsageResult[AuthorityResponse]:
        """Label every option by who can adopt it (see ``LonglistBackend.authority``)."""
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


def _plan_data(plan: ScopingPlan) -> tuple[dict[str, object], list[str]]:
    """The plan fields the per-option prompt reads, and the place spans removed.

    The question, the intended change and the target unit pass through
    :func:`strip_place` against the plan's Where (S6, R4, AM7): the exact
    target unit with its place removed, never the screen's widened sentence.
    The outcomes are passed as they are; Where itself is not included.
    Requirement texts are not stripped (they are not plan data here).

    Args:
        plan: The validated scoping plan.

    Returns:
        ``(plan_data, removed)``: ``{"question", "target_unit",
        "intended_change", "outcomes"}`` and the removed spans in field order
        (question, target unit, intended change).
    """
    where = plan.where.text
    question, question_removed = strip_place(plan.question, where)
    target_unit, target_removed = strip_place(plan.target_unit.text, where)
    intended_change, change_removed = strip_place(plan.intended_change.text, where)
    data: dict[str, object] = {
        "question": question,
        "target_unit": target_unit,
        "intended_change": intended_change,
        "outcomes": [outcome.text for outcome in plan.outcomes],
    }
    return data, [*question_removed, *target_removed, *change_removed]


def _checks(requirements: list[dict[str, str]]) -> list[dict[str, str]]:
    """Every id an option's state reads, in the order the first break is taken.

    The requirements, then the default screens with *distinct* in its place
    (relevant · distinct · within scope), as the read models order them.
    """
    screens = [{"id": key, "text": label} for key, label in DEFAULT_SCREENS]
    distinct = {"id": DISTINCT_SCREEN[0], "text": DISTINCT_SCREEN[1]}
    user = [r for r in requirements if r["id"] not in dict(DEFAULT_SCREENS)]
    return [*user, screens[0], distinct, *screens[1:]]


def _constraint_lists(
    plan: ScopingPlan,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """``(requirements + default screens, preferences minus transferability)``.

    The requirements are the plan's boundaries. A consideration is in
    neither list: it never excludes an option (R34).
    """
    requirements = [
        {"id": f"req-{i}", "text": c.text}
        for i, c in enumerate((c for c in plan.constraints if c.kind == "boundary"), start=1)
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


def _coverage_summary(coverage: object) -> dict[str, object]:
    """A compact coverage summary: context for the screens, never an exclusion input.

    No ``where_tried`` (AM7: place never reaches the prompt); the counts by
    role and the *tried on* populations stay.
    """
    cov = _mapping(coverage)
    roles = _mapping(cov.get("role"))
    settings = _mapping(cov.get("settings"))
    top_settings = sorted(settings.items(), key=lambda kv: (-int(kv[1] or 0), str(kv[0])))
    tried_on = cov.get("tried_on")
    return {
        "documents": int(cov.get("documents") or 0),
        "evaluated": int(roles.get("evaluated") or 0),
        "roles": {str(k): int(v or 0) for k, v in roles.items()},
        "tried_on": [
            {
                "population": str(entry.get("population") or ""),
                "documents": int(entry.get("documents") or 0),
            }
            for entry in (tried_on if isinstance(tried_on, list) else [])
            if isinstance(entry, Mapping)
        ],
        "settings": [str(text) for text, _ in top_settings[:COVERAGE_SETTINGS_MAX]],
    }


def _design_features(row: Any) -> list[object]:
    design = row.design if isinstance(row.design, Mapping) else {}
    features = design.get("design_features")
    return list(features) if isinstance(features, list) else []


def _option_data(
    row: Any, relations: list[dict[str, object]], coverage: object
) -> dict[str, object]:
    design = row.design if isinstance(row.design, Mapping) else {}
    outcomes = design.get("outcomes_served")
    return {
        "option_id": str(row.option_id),
        "label": row.name,
        "description": row.description,
        "design_features": _design_features(row),
        "outcomes_served": (
            list(outcomes) if isinstance(outcomes, list) else list(row.outcomes or [])
        ),
        "relations": relations,
        "coverage": _coverage_summary(coverage),
    }


def _distinct_option_data(row: Any, relations: list[dict[str, object]]) -> dict[str, object]:
    """One option as the distinct call reads it (origin in the reader's words)."""
    return {
        "option_id": str(row.option_id),
        "label": row.name,
        "description": row.description,
        "design_features": _design_features(row),
        "origin": ORIGIN_WORDS.get(row.origin, ON_THE_LIST),
        "relations": relations,
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


@dataclass
class _BatchOutcome:
    """One batch's result, built in a worker thread and merged in the caller."""

    result: dict[str, _Judged] | None = None
    usages: list[TokenUsage | None] = field(default_factory=list)
    calls: int = 0


def _judge_batch(
    backend: ConstrainBackend,
    *,
    plan: dict[str, object],
    baseline: list[tuple[str, str]],
    requirements: list[dict[str, str]],
    preferences: list[dict[str, str]],
    batch: list[dict[str, object]],
) -> _BatchOutcome:
    """One batch: the call and one retry; ``result`` is ``None`` when it stays malformed.

    Runs in a worker thread: it touches no connection and no shared state.
    """
    option_ids = [str(o["option_id"]) for o in batch]
    outcome = _BatchOutcome()
    for attempt in range(BATCH_ATTEMPTS):
        outcome.calls += 1
        try:
            response, call_usage = backend.constrain(
                plan=plan,
                baseline_sections=baseline,
                requirements=requirements,
                preferences=preferences,
                options=batch,
            )
        except Exception as exc:  # fail-closed: a failed call is a malformed batch
            log.warning("constrain.batch_call_failed", error_type=type(exc).__name__)
            continue
        outcome.usages.append(call_usage)
        outcome.result = _validated(
            response,
            option_ids=option_ids,
            requirement_ids=[r["id"] for r in requirements],
            preference_ids=[p["id"] for p in preferences],
        )
        if outcome.result is not None:
            break
        log.warning("constrain.batch_malformed", attempt=attempt, options=len(batch))
    return outcome


def _judge(
    backend: ConstrainBackend,
    *,
    plan: dict[str, object],
    baseline: list[tuple[str, str]],
    requirements: list[dict[str, str]],
    preferences: list[dict[str, str]],
    options: list[dict[str, object]],
    usage: UsageAccumulator,
) -> tuple[dict[str, _Judged], dict[str, int], set[str]]:
    """Judge every option, the batches in a thread pool; a malformed batch degrades.

    Returns ``(judged, stats, failed)``; ``failed`` holds the option ids of
    the batches that stayed malformed.
    """
    requirement_ids = [r["id"] for r in requirements]
    batches = [
        options[start : start + CONSTRAIN_BATCH_SIZE]
        for start in range(0, len(options), CONSTRAIN_BATCH_SIZE)
    ]
    with ThreadPoolExecutor(max_workers=CONSTRAIN_MAX_CONCURRENT) as pool:
        futures = [
            tracing.submit_with_context(
                pool,
                _judge_batch,
                backend,
                plan=plan,
                baseline=baseline,
                requirements=requirements,
                preferences=preferences,
                batch=batch,
            )
            for batch in batches
        ]
        outcomes = [future.result() for future in futures]
    judged: dict[str, _Judged] = {}
    failed: set[str] = set()
    stats = {"calls": 0, "retries": 0, "failed_batches": 0}
    for batch, outcome in zip(batches, outcomes, strict=True):
        stats["calls"] += outcome.calls
        stats["retries"] += outcome.calls - 1
        for call_usage in outcome.usages:
            usage.add(call_usage)
        result = outcome.result
        if result is None:
            option_ids = [str(o["option_id"]) for o in batch]
            stats["failed_batches"] += 1
            failed.update(option_ids)
            result = {oid: _unavailable(requirement_ids) for oid in option_ids}
        judged.update(result)
    return judged, stats, failed


@dataclass
class _Distinct:
    """The distinct call's answer, checked and turned into verdicts.

    Attributes:
        verdicts: The *distinct* verdict per option id (every option).
        kept: The kept option id per duplicate option id.
        stats: ``calls``, ``retries``, ``failed``, ``pairs`` (accepted) and
            ``dropped`` counts by cause.
    """

    verdicts: dict[str, _Verdict]
    kept: dict[str, str]
    stats: dict[str, Any]


def _keep_order(row: Any) -> tuple[int, Any, str]:
    """A duplicate group's keep order: the user's option, then Evidence
    search's, then the earliest created, then the lowest id."""
    origin = row.origin
    rank = (
        _KEPT_FIRST_ORIGINS.index(origin)
        if origin in _KEPT_FIRST_ORIGINS
        else len(_KEPT_FIRST_ORIGINS)
    )
    return (rank, row.created_at, str(row.option_id))


def _distinct_verdicts(response: DistinctResponse, rows: Sequence[Any]) -> _Distinct:
    """Check the reported pairs and map them to *distinct* verdicts (S13).

    A reported pair is dropped (and counted) when it names an id not on the
    list (``unknown_id``), the same id twice (``same_id``), a duplicate an
    earlier pair already reported (``repeated``), or an option named as kept
    that is itself reported as a duplicate (``chain``). The remaining pairs
    form groups (an option named as kept with every option reported as its
    duplicate). Code decides which member of a group is kept, by
    :func:`_keep_order` — never the side of the pair the call put it on
    (``turned`` counts the pairs whose kept option differs from the one the
    call named). Every other member ``breaks`` with a reason naming the kept
    option (its own pair's reason, or for the option the call named as kept,
    the reason of the kept option's pair); every other option ``passes``.
    """
    by_id = {str(row.option_id): row for row in rows}
    dropped = dict.fromkeys(("unknown_id", "same_id", "repeated", "chain"), 0)
    reported: dict[str, tuple[str, str]] = {}  # duplicate -> (named kept, reason)
    for wire in response.duplicates:
        duplicate, kept = wire.option_id.strip(), wire.same_as_option_id.strip()
        if duplicate not in by_id or kept not in by_id:
            dropped["unknown_id"] += 1
        elif duplicate == kept:
            dropped["same_id"] += 1
        elif duplicate in reported:
            dropped["repeated"] += 1
        else:
            reported[duplicate] = (kept, wire.reason.strip())
    for duplicate in [d for d, (kept, _) in reported.items() if kept in reported]:
        dropped["chain"] += 1
        del reported[duplicate]
    groups: dict[str, list[str]] = {}  # named kept -> its reported duplicates
    for duplicate, (named, _) in reported.items():
        groups.setdefault(named, []).append(duplicate)
    pairs: dict[str, tuple[str, str]] = {}  # duplicate -> (kept, reason)
    turned = 0
    for named, duplicates in groups.items():
        kept = min([named, *duplicates], key=lambda oid: _keep_order(by_id[oid]))
        if kept != named:
            turned += len(duplicates)
            pairs[named] = (kept, reported[kept][1])
        for duplicate in duplicates:
            if duplicate != kept:
                pairs[duplicate] = (kept, reported[duplicate][1])
    verdicts = {oid: _Verdict("passes", DISTINCT_PASSES_REASON) for oid in by_id}
    for duplicate, (kept, reason) in pairs.items():
        named_text = f'The same as "{by_id[kept].name}"'
        verdicts[duplicate] = _Verdict(
            "breaks", f"{named_text}: {reason}" if reason else f"{named_text}."
        )
    return _Distinct(
        verdicts=verdicts,
        kept={duplicate: kept for duplicate, (kept, _) in pairs.items()},
        stats={"pairs": len(pairs), "turned": turned, "dropped": dropped},
    )


def _distinct(
    backend: ConstrainBackend,
    *,
    rows: Sequence[Any],
    relations: Mapping[uuid.UUID, list[dict[str, object]]],
    usage: UsageAccumulator,
) -> _Distinct:
    """The one distinct call over the whole list, before the batches (S13).

    The call and one retry. A call that fails both times (a raised error,
    which is how a malformed structured answer surfaces) gives every option
    ``cannot_check`` and no pair.
    """
    options = [_distinct_option_data(row, relations.get(row.option_id, [])) for row in rows]
    calls = 0
    response: DistinctResponse | None = None
    if rows:
        for attempt in range(BATCH_ATTEMPTS):
            calls += 1
            try:
                response, call_usage = backend.distinct(options=options)
            except Exception as exc:  # fail-closed: no merge on a failed call
                log.warning(
                    "constrain.distinct_call_failed",
                    attempt=attempt,
                    error_type=type(exc).__name__,
                )
                continue
            usage.add(call_usage)
            break
    base = {"calls": calls, "retries": max(calls - 1, 0)}
    if rows and response is None:
        return _Distinct(
            verdicts={
                str(row.option_id): _Verdict("cannot_check", JUDGEMENT_UNAVAILABLE)
                for row in rows
            },
            kept={},
            stats={**base, "failed": True, "pairs": 0, "turned": 0, "dropped": {}},
        )
    checked = _distinct_verdicts(response or DistinctResponse(duplicates=[]), rows)
    checked.stats = {**base, "failed": False, **checked.stats}
    return checked


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


def who_decides_considerations(plan: ScopingPlan) -> list[str]:
    """The texts of the plan's considerations on who decides, in plan order (R38).

    Args:
        plan: The validated scoping plan.

    Returns:
        The texts; empty when the plan holds none.
    """
    return [
        c.text for c in plan.constraints if c.kind == "consideration" and c.aspect == WHO_DECIDES
    ]


def _who_decides_sentence(profile: Mapping[str, Any], row: Any) -> str | None:
    """The option's ``who_decides`` sentence for its current design version, if any."""
    entry = _mapping(_mapping(profile.get(str(row.option_id))).get(str(row.design_version)))
    sentence = _mapping(_mapping(entry.get("lines")).get(WHO_DECIDES)).get("sentence")
    return sentence.strip() if isinstance(sentence, str) and sentence.strip() else None


def _authority_option_data(row: Any, who_decides: str) -> dict[str, object]:
    """One option as the authority call reads it: no coverage, no records, no other line."""
    return {
        "option_id": str(row.option_id),
        "label": row.name,
        "description": row.description,
        "design_features": _design_features(row),
        "who_decides": who_decides,
    }


def _validated_authority(
    response: AuthorityResponse, option_ids: Sequence[str]
) -> dict[str, dict[str, Any]] | None:
    """The labels per option id, or ``None`` when the response is malformed.

    Every option sent exactly once and no other id; a non-blank reason; a
    non-blank body on ``needs_action_by`` (the body is dropped on any other
    label).
    """
    if sorted(wire.option_id for wire in response.options) != sorted(option_ids):
        return None
    out: dict[str, dict[str, Any]] = {}
    for wire in response.options:
        reason = wire.reason.strip()
        body = (wire.body or "").strip()
        if not reason or (wire.label == "needs_action_by" and not body):
            return None
        out[wire.option_id] = {
            "label": wire.label,
            "body": body if wire.label == "needs_action_by" else None,
            "reason": reason,
        }
    return out


@dataclass
class _Authority:
    """The authority call's checked answer (built in a worker thread).

    Attributes:
        labels: The label entry per option id (empty when the call failed).
        usages: Every call's token usage, added to the step's total by the caller.
        stats: ``calls``, ``retries``, ``failed`` and ``options`` (sent).
    """

    labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    usages: list[TokenUsage | None] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def _authority(
    backend: ConstrainBackend, *, considerations: list[str], options: list[dict[str, object]]
) -> _Authority:
    """The one authority call over the whole list, and one retry (R38, S18).

    Runs in a worker thread: it touches no connection and no shared state.
    A call that raises or stays malformed after its retry gives no label
    (``failed``): never a crash, never an exclusion.
    """
    outcome = _Authority()
    option_ids = [str(o["option_id"]) for o in options]
    calls = 0
    labels: dict[str, dict[str, Any]] | None = None
    if options:
        for attempt in range(BATCH_ATTEMPTS):
            calls += 1
            try:
                response, call_usage = backend.authority(
                    considerations=considerations, options=options
                )
            except Exception as exc:  # fail-closed: no label on a failed call
                log.warning(
                    "constrain.authority_call_failed",
                    attempt=attempt,
                    error_type=type(exc).__name__,
                )
                continue
            outcome.usages.append(call_usage)
            labels = _validated_authority(response, option_ids)
            if labels is not None:
                break
            log.warning("constrain.authority_malformed", attempt=attempt, options=len(options))
    failed = bool(options) and labels is None
    if failed:
        log.warning("constrain.authority_failed", calls=calls, options=len(options))
    outcome.labels = labels or {}
    outcome.stats = {
        "calls": calls,
        "retries": max(calls - 1, 0),
        "failed": failed,
        "options": len(options),
    }
    return outcome


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
        backend: The model seam (the longlist backend's ``distinct`` and ``constrain``).

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
    requirements, preferences = _constraint_lists(plan)
    checks = _checks(requirements)
    texts = {r["id"]: r["text"] for r in checks + preferences}
    plan_data, place_removed = _plan_data(plan)
    if place_removed:
        log.info("constrain.place_removed", spans=len(place_removed))

    considerations = who_decides_considerations(plan)
    profile = _mapping(result_row.option_profile)
    authority_options = [
        _authority_option_data(row, sentence)
        for row in rows
        if (sentence := _who_decides_sentence(profile, row)) is not None
    ]

    # 1. Every model call, before any write: the authority call (only with a
    # consideration on who decides) in a worker at the same time as the
    # distinct call over the whole list, then the batches in parallel.
    usage = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=1) as authority_pool:
        authority_future = (
            tracing.submit_with_context(
                authority_pool,
                _authority,
                backend,
                considerations=considerations,
                options=authority_options,
            )
            if considerations
            else None
        )
        distinct = _distinct(backend, rows=rows, relations=relations, usage=usage)
        judged, stats, failed = _judge(
            backend,
            plan=plan_data,
            baseline=baseline_sections(conn, task_id),
            requirements=requirements,
            preferences=preferences,
            options=[
                _option_data(
                    row, relations.get(row.option_id, []), coverage.get(str(row.option_id))
                )
                for row in rows
            ],
            usage=usage,
        )
        authority = authority_future.result() if authority_future is not None else None
    if authority is not None:
        for call_usage in authority.usages:
            usage.add(call_usage)
    # 2. Verdicts -> state or merge, every kept option before the duplicates,
    # so a duplicate's kept option is settled before it. No write yet.
    ordered = sorted(
        rows,
        key=lambda row: (str(row.option_id) in distinct.kept, row.created_at, str(row.option_id)),
    )
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
        verdicts = {**judged[oid].verdicts, _DISTINCT: distinct.verdicts[oid]}
        kept: uuid.UUID | None = None
        if row.option_id in relations:
            verdicts[_DISTINCT] = _Verdict("passes", PACKAGE_DISTINCT_REASON)
        elif verdicts[_DISTINCT].verdict == "breaks":
            kept = kept_as(uuid.UUID(distinct.kept[oid]))
            if kept is None:
                verdicts[_DISTINCT] = _Verdict("passes", DUPLICATE_KEPT_REASON)
        values: dict[str, Any] = {}
        if user_holds_state(row.exclusion) or oid in failed:
            # User state always wins (a user-held duplicate is never merged
            # away); a failed batch keeps the prior state.
            state = row.state
        else:
            broken = next((r for r in checks if verdicts[r["id"]].verdict == "breaks"), None)
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
            option_ids=sorted(set(merged_into.values()), key=str),
            plan_outcomes=[outcome.text for outcome in plan.outcomes],
            # The list's folding maps, applied again to the merged members
            # (task 046, amendment 3, S21).
            folds=stored_folds(profile),
            target_unit=str(plan_data["target_unit"]),
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
    labelled: Counter[str] = Counter()
    consideration_text = CONSIDERATION_JOIN.join(considerations)
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
            for cid in (r["id"] for r in checks)
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
            label = authority.labels.get(oid) if authority is not None else None
            if label is not None:
                # No verdict: never a check, never an exclusion (S18).
                record[AUTHORITY_KEY] = {**label, "consideration_text": consideration_text}
                labelled[label["label"]] += 1
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
        authority_labelled=sum(labelled.values()),
    )
    live = backend.mode == "live"
    provenance["constrain"] = {
        "run_id": str(run_id),
        "backend_mode": backend.mode,
        "prompt_version": CONSTRAIN_PROMPT_VERSION,
        "model": LONGLIST_JUDGMENT_MODEL if live else "stub",
        "batch_size": CONSTRAIN_BATCH_SIZE,
        "max_concurrent": CONSTRAIN_MAX_CONCURRENT,
        **stats,
        "distinct": distinct.stats,
        "place_removed": place_removed,
        "requirements": len(requirements) - len(DEFAULT_SCREENS),
        "preferences": len(preferences),
        "authority": (
            {**authority.stats, "labels": {key: labelled[key] for key in AUTHORITY_LABELS}}
            if authority is not None
            else {"calls": 0}
        ),
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
        authority_labelled=sum(labelled.values()),
    )
    return summary
