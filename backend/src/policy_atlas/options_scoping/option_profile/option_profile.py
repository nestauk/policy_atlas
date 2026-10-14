"""The ``option_profile`` component: all that is said about each option (task 046, R37).

ADR 0040 (amendment 2). The longlist walk runs
``longlist → option_profile → constrain → theme``: ``longlist`` makes the
list, ``option_profile`` writes what is said about each option, ``constrain``
makes verdicts, ``theme`` groups what a reader still sees. It is a spine step:
an :class:`OptionProfileFailure` fails the walk.

``option_profile_scope`` reads the walk's latest ``longlist_result`` and the
task's options that are not merged, included or not (S16), in the order
``created_at, option_id``. Two kinds of call run at one time:

- **Lever typing**, moved out of ``longlist`` as built (S20): one call per
  :data:`~policy_atlas.options_scoping.option_profile.lever_typing_prompt.LEVER_TYPING_BATCH_SIZE`
  options, the batches in a thread pool of :data:`TYPING_MAX_CONCURRENT`,
  with the place-stripped plan and the baseline. An invalid or failed typing
  leaves the option's columns as they are and carries its runner-up and its
  lever reason forward from the latest earlier result (task 046, S12).
- **The ten profile calls** (R36, R40, R41), each over the WHOLE list, in a
  thread pool of :data:`OPTION_PROFILE_MAX_CONCURRENT`: one per line of
  "What it would take" (:data:`~policy_atlas.runtime.scoping_plan.PROFILE_LINE_KEYS`),
  the ambition and the delivery setting. Each reads the same option list
  (S16): short ids ``o1 … oN``, the label, description and design features,
  and at most :data:`OPTION_PROFILE_RECORDS_MAX` member records ordered by
  role. The plan data is the place-stripped plan the typing reads; the
  plan's Where reaches the ``who_decides`` call only. Each response is
  checked fail-closed (every option once, no other id, a sentence); a call
  that raises or answers malformed is tried once more; one that fails again
  fails the step (:class:`OptionProfileFailure`) and nothing is written. The
  model's marks are stored as given: no quota, no floor, no check of a mark
  against its sentence.
- **The two folding calls** (task 046, amendment 3, R54, R55; S21), in the
  same pool, on the mini model: one per facet over the DISTINCT record words
  of the whole list — every member of every option, not the profile calls'
  records — the ``unit`` words for Tried on, the ``outcome`` words for
  Measures, keyed ``w1 … wN``; word → kind. One retry; an invalid answer
  after it fails the step. A word the answer leaves out keeps its own text as
  its kind; a kind for an id not in the input is dropped; a kind equal
  (case-folded) to a plan outcome or to the target unit is that plan text.

Writes (S17), all after the last model call: the lever types on each option
row typed validly and the ambition (mark and sentence) on every option row;
on the ``longlist_result`` row, the ``option_profile`` column replaced whole
(per option id and design version: the eight lines and the setting), and,
merged into its JSON as ``theme`` merges, the typing keys the read side reads
(``provenance.runner_up``, ``provenance.lever_reason``,
``provenance.typing``, ``provenance.prompt_versions.typing``,
``provenance.models.typing``, ``provenance.taxonomy_version``,
``counts.none_fits``, ``counts.typing_invalid``), ``counts.profiled`` and
``provenance.option_profile``; the folding maps at list level in the
``option_profile`` column under ``folds``, and each option's coverage keys
``tried_on_kinds``, ``measures_kinds`` and ``outcome_counts`` recomputed from
its members through the maps (a database read, no model call) and merged
into the row's ``coverage``.

**The place sentences (task 046, amendment 4, R80; S31).** A second wave,
after the first pool has returned and before any write: per option on the
stored coverage that has evaluating documents, one call on the mini model
(:meth:`~policy_atlas.options_scoping.longlist.longlist_backend.LonglistBackend.place_sentences`),
the calls in a pool of :data:`OPTION_PROFILE_MAX_CONCURRENT`, each tried once
more. The input, the template and the trace check are code
(:mod:`.place_sentences`). A failed call, a sentence over the ceiling or one
that fails the trace check falls back to the template; nothing in the wave
fails the step. The sentences are merged into each option's coverage under
:data:`PLACE_SENTENCES_KEY` (``[{place, sentence, generated, where}]``, the
card's order) and counted in ``provenance.option_profile.place_sentences``.
"""

from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from itertools import batched
from typing import Any, cast

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import tracing
from policy_atlas.core.schema import (
    intervention_profile_record,
    longlist_result,
    option,
    option_membership,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.options_scoping.longlist.coverage import (
    FOLD_FIELDS,
    distinct_words,
    fold_programme_names,
)
from policy_atlas.options_scoping.longlist.lever_types import LEVER_TYPE_KEYS, TAXONOMY_VERSION
from policy_atlas.options_scoping.longlist.longlist import (
    MembershipRead,
    _seeds,
    latest_longlist,
    read_membership,
)
from policy_atlas.options_scoping.longlist.longlist_backend import (
    LONGLIST_ASSIGNMENT_MODEL,
    LONGLIST_JUDGMENT_MODEL,
    LonglistBackend,
)
from policy_atlas.options_scoping.longlist.where_tried import resolve_country
from policy_atlas.options_scoping.longlist_intent import (
    longlist_plan_data,
    who_decides_considerations,
)
from policy_atlas.options_scoping.model_calls import CALL_ATTEMPTS, CallOutcome, call_with_retry
from policy_atlas.options_scoping.option_profile.folding_prompt import (
    FOLDING_PROMPT_VERSION,
    Facet,
    FoldingResponse,
)
from policy_atlas.options_scoping.option_profile.lever_typing_prompt import (
    LEVER_TYPING_BATCH_SIZE,
    LEVER_TYPING_PROMPT_VERSION,
    LeverTypingResponse,
)
from policy_atlas.options_scoping.option_profile.option_profile_prompt import (
    OPTION_PROFILE_PROMPT_VERSION,
    AmbitionResponse,
    MarkedLineResponse,
    PlainLineResponse,
    SettingResponse,
    line_is_marked,
)
from policy_atlas.options_scoping.option_profile.place_sentences import (
    PlaceGroup,
    call_input,
    from_membership,
    group_places,
    metadata_year,
    template_sentence,
    trace_check,
    vocabulary_from_folds,
)
from policy_atlas.options_scoping.option_profile.place_sentences_prompt import (
    PLACE_SENTENCE_MAX_CHARS,
    PLACE_SENTENCES_PROMPT_VERSION,
    PlaceSentencesResponse,
)
from policy_atlas.options_scoping.suggest.suggest import baseline_sections, walk_plan
from policy_atlas.options_scoping.text import clean_text, fold_text
from policy_atlas.runtime.scoping_plan import PROFILE_LINE_KEYS

log = structlog.get_logger()

#: Typing batches in flight at once (task 046, S12).
TYPING_MAX_CONCURRENT = 4
# ponytail: kept only for the read-model import another cleanup lane deletes; delete then.
TYPING_INVALID_REASON = "typing invalid"
#: The ten profile calls and the two folding calls in flight at once: all
#: of them (R37; task 046, amendment 3, S21).
OPTION_PROFILE_MAX_CONCURRENT = 12
#: Member records each option carries into the profile calls (S16).
OPTION_PROFILE_RECORDS_MAX = 5
#: Design features each of those records carries (S16).
OPTION_PROFILE_RECORD_FEATURES_MAX = 3
#: The record's intervention text, cut to this many characters (S16).
OPTION_PROFILE_INTERVENTION_MAX = 100
#: The order the records are taken in (S16); a role not listed sorts last.
OPTION_PROFILE_ROLE_ORDER: tuple[str, ...] = ("evaluated", "described", "recommended", "mentioned")
#: The membership kind whose unit is an intervention profile record.
_PROFILE_UNIT_KIND = "interventions"
#: The name of the ambition call and of the setting call, as a failure names them.
_AMBITION_CALL = "ambition"
_SETTING_CALL = "setting"
#: The kinds a folding answer should hold at most (the prompt's ceiling, A6);
#: more is kept and logged, never invalid.
FOLDING_KINDS_MAX = 12
#: A folding answer is a catch-all when one kind holds more than this share
#: of the list's words on a list of at least :data:`FOLDING_CATCH_ALL_MIN_WORDS`
#: words (task 046, amendment 4, round 9 of the folding loop; the fault
#: amendment 3 recorded): the call is tried once more, and the retry's answer
#: is kept either way (a catch-all is a quality fault, never a failed step).
FOLDING_CATCH_ALL_SHARE = 0.5
FOLDING_CATCH_ALL_MIN_WORDS = 20
#: The coverage keys the folding maps recompute and merge (S21, S24).
FOLDED_COVERAGE_KEYS: tuple[str, ...] = ("outcome_counts",)
#: The coverage key the place sentences are merged under (task 046, amendment
#: 4, R80; S31): ``[{place, sentence, generated, where}]`` in the card's order.
#: Written by the second wave only; ``membership.coverage`` never computes it,
#: so constrain's merge recompute carries it through.
PLACE_SENTENCES_KEY = "place_sentences"


class OptionProfileFailure(Exception):
    """The profile could not be written.

    No longlist exists for the walk, or a profile call (a line, the ambition,
    the setting or a folding call) failed twice.
    """


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
    #: The design version the profile is keyed under (S17).
    design_version: int


@dataclass(frozen=True)
class _Typing:
    primary: str | None
    secondary: list[str]
    none_fits_reason: str | None
    runner_up: str | None
    lever_reason: str | None = None


def _profiled_options(conn: Connection, *, task_id: uuid.UUID) -> list[_ProfiledOption]:
    """The task's options that are not merged, included or not (S16).

    In the order ``created_at, option_id``. Each option's label, description
    and design features are the ones ``longlist`` offers a seed (engine-valid,
    unique labels), so the typing call reads what it read inside ``longlist``.
    """
    rows = conn.execute(
        select(option.c.option_id, option.c.taxonomy_version, option.c.design_version)
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
            design_version=int(row.design_version),
        )
        for row in rows
    ]


def _validated_typing(wire: Any) -> _Typing | None:
    """One wire typing, validated fail-closed (D8); ``None`` when unusable."""
    primary = wire.primary_lever_type
    reason = (wire.none_fits_reason or "").strip() or None
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
    batches = [list(batch) for batch in batched(options, LEVER_TYPING_BATCH_SIZE)]
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


def _runner_up_entry(entry: Any) -> dict[str, Any] | None:
    lever = entry.get("lever_type") if isinstance(entry, Mapping) else None
    if isinstance(lever, str) and lever in LEVER_TYPE_KEYS:
        return {"lever_type": lever, "carried_forward": True}
    return None


def _lever_reason_entry(entry: Any) -> str | None:
    return (entry.strip() or None) if isinstance(entry, str) else None


#: The typing entries a kept typing carries forward, and how each stored entry is read.
_CARRIED_ENTRIES: dict[str, Callable[[Any], Any]] = {
    "runner_up": _runner_up_entry,
    "lever_reason": _lever_reason_entry,
}


def _earlier_typing_entries(
    conn: Connection, *, task_id: uuid.UUID, option_ids: Sequence[uuid.UUID]
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Per kept option, the runner-up and the lever reason it carries forward (S12, R29).

    One walk over the task's ``longlist_result`` rows, newest first, reading
    ``provenance[key][option_id]`` for each key of :data:`_CARRIED_ENTRIES`.
    For each key, a result that typed the option validly without the entry
    (it lists the option among its options and not among its
    ``typing.kept_ids``) ends that key's search: the typing that stands has
    none. The row this walk's ``longlist`` wrote holds no typing yet, so it
    neither supplies an entry nor ends a search.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options whose typing was kept.

    Returns:
        ``(runner_ups, lever_reasons)``: ``{option_id: {"lever_type",
        "carried_forward": True}}`` and ``{option_id: reason}``.
    """
    wanted = {str(option_id) for option_id in option_ids}
    found: dict[str, dict[str, Any]] = {key: {} for key in _CARRIED_ENTRIES}
    settled: dict[str, set[str]] = {key: set() for key in _CARRIED_ENTRIES}
    if wanted:
        for (provenance,) in conn.execute(
            select(longlist_result.c.provenance)
            .where(longlist_result.c.task_id == task_id)
            .order_by(
                longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
            )
        ):
            record = provenance if isinstance(provenance, Mapping) else {}
            typing = record.get("typing")
            kept_ids = typing.get("kept_ids") if isinstance(typing, Mapping) else None
            listed = {
                str(option_id)
                for list_key in ("seed_ids", "discovered_ids")
                for option_id in (record.get(list_key) or [])
            }
            for key, read in _CARRIED_ENTRIES.items():
                entries = record.get(key)
                entries = entries if isinstance(entries, Mapping) else {}
                for option_id in wanted - settled[key]:
                    value = read(entries.get(option_id))
                    if value is not None:
                        found[key][option_id] = value
                        settled[key].add(option_id)
                    elif (
                        isinstance(kept_ids, list)
                        and option_id in listed
                        and option_id not in kept_ids
                    ):
                        settled[key].add(option_id)
            if all(done >= wanted for done in settled.values()):
                break
    return found["runner_up"], found["lever_reason"]


@dataclass(frozen=True)
class _Line:
    """One option's answer on one line, normalised."""

    sentence: str
    #: ``less``, ``more`` or ``None`` (no mark; always ``None`` on an unmarked line).
    mark: str | None


@dataclass(frozen=True)
class _Setting:
    """One option's delivery setting, normalised (lower case)."""

    main: str | None
    second: str | None


def _evidence_records(
    conn: Connection, *, task_id: uuid.UUID, option_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[dict[str, object]]]:
    """At most :data:`OPTION_PROFILE_RECORDS_MAX` member records per option (S16).

    The option's intervention profile records, ordered by role
    (:data:`OPTION_PROFILE_ROLE_ORDER`), then ``created_at``, then
    ``record_id``. Each record carries its intervention (cut to
    :data:`OPTION_PROFILE_INTERVENTION_MAX` characters), its role and at most
    :data:`OPTION_PROFILE_RECORD_FEATURES_MAX` design features: no study
    geography, no population, no place.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        option_ids: The options read.

    Returns:
        ``{option_id: [{"intervention", "role", "features"}, ...]}``.
    """
    if not option_ids:
        return {}
    ipr = intervention_profile_record
    om = option_membership
    rows = conn.execute(
        select(
            om.c.option_id,
            ipr.c.record_id,
            ipr.c.intervention,
            ipr.c.role,
            ipr.c.design_features,
            ipr.c.created_at,
        )
        .select_from(om.join(ipr, ipr.c.record_id == om.c.unit_id))
        .where(om.c.task_id == task_id)
        .where(om.c.unit_kind == _PROFILE_UNIT_KIND)
        .where(om.c.option_id.in_(list(option_ids)))
    ).all()
    rank = {role: index for index, role in enumerate(OPTION_PROFILE_ROLE_ORDER)}
    rows = sorted(
        rows,
        key=lambda r: (rank.get(r.role, len(rank)), r.created_at, str(r.record_id)),
    )
    records: dict[uuid.UUID, list[dict[str, object]]] = {}
    for row in rows:
        held = records.setdefault(row.option_id, [])
        if len(held) >= OPTION_PROFILE_RECORDS_MAX:
            continue
        features = row.design_features if isinstance(row.design_features, list) else []
        held.append(
            {
                "intervention": row.intervention[:OPTION_PROFILE_INTERVENTION_MAX],
                "role": row.role,
                "features": list(features[:OPTION_PROFILE_RECORD_FEATURES_MAX]),
            }
        )
    return records


def _profile_payload(
    options: Sequence[_ProfiledOption], records: Mapping[uuid.UUID, list[dict[str, object]]]
) -> tuple[list[dict[str, object]], dict[str, uuid.UUID]]:
    """The one option list all ten profile calls read (S16).

    Short ids ``o1 … oN`` in list order, mapped back to the option ids in
    code.

    Returns:
        ``(payload, {short id: option id})``.
    """
    short_ids = {f"o{index}": o.option_id for index, o in enumerate(options, start=1)}
    payload: list[dict[str, object]] = [
        {
            "option_id": short_id,
            "label": o.label,
            "description": o.description,
            "design_features": list(o.design_features),
            "evidence_records": records.get(o.option_id, []),
        }
        for short_id, o in zip(short_ids, options, strict=True)
    ]
    return payload, short_ids


def _covers_the_list(answered: Sequence[str], short_ids: Mapping[str, uuid.UUID]) -> bool:
    """Every option of the list exactly once, and no other id."""
    return len(answered) == len(set(answered)) and set(answered) == set(short_ids)


def _mark(stands_out: str) -> str | None:
    return None if stands_out == "no" else stands_out


def _answered(
    response: Any, kind: type | tuple[type, ...], short_ids: Mapping[str, uuid.UUID]
) -> list[tuple[str, Any]] | None:
    """``(short id, wire)`` per option answered, or ``None`` when the response is
    not of ``kind`` or does not cover the list exactly once."""
    if not isinstance(response, kind):
        return None
    wires: Sequence[Any] = cast(Any, response).options
    answered = [wire.option_id.strip() for wire in wires]
    if not _covers_the_list(answered, short_ids):
        return None
    return list(zip(answered, wires, strict=True))


def _checked_line(
    line_key: str, response: Any, short_ids: Mapping[str, uuid.UUID]
) -> dict[str, _Line] | None:
    """One line response, checked fail-closed; ``None`` when malformed.

    On ``who_decides`` and ``dependencies`` the mark is ``None`` whatever
    the response holds (R36).
    """
    pairs = _answered(response, (MarkedLineResponse, PlainLineResponse), short_ids)
    if pairs is None:
        return None
    marked = line_is_marked(line_key)
    lines: dict[str, _Line] = {}
    for short_id, wire in pairs:
        sentence = wire.answer.strip()
        if not sentence:
            return None
        stands_out = getattr(wire, "stands_out", "no") if marked else "no"
        lines[short_id] = _Line(sentence=sentence, mark=_mark(stands_out))
    return lines


def _checked_ambition(
    response: Any, short_ids: Mapping[str, uuid.UUID]
) -> dict[str, _Line] | None:
    """The ambition response, checked fail-closed; ``None`` when malformed (R40)."""
    pairs = _answered(response, AmbitionResponse, short_ids)
    if pairs is None:
        return None
    ambitions: dict[str, _Line] = {}
    for short_id, wire in pairs:
        reason = wire.reason.strip()
        if not reason:
            return None
        ambitions[short_id] = _Line(sentence=reason, mark=_mark(wire.stands_out))
    return ambitions


def _checked_setting(
    response: Any, short_ids: Mapping[str, uuid.UUID]
) -> dict[str, _Setting] | None:
    """The setting response, checked fail-closed; ``None`` when malformed (R41).

    A setting is null or a non-blank word, lower-cased; the second setting is
    null when the main one is.
    """
    pairs = _answered(response, SettingResponse, short_ids)
    if pairs is None:
        return None
    settings: dict[str, _Setting] = {}
    for short_id, wire in pairs:
        main = None if wire.main_setting is None else wire.main_setting.strip().lower()
        second = None if wire.second_setting is None else wire.second_setting.strip().lower()
        if main == "" or second == "" or (main is None and second is not None):
            return None
        settings[short_id] = _Setting(main=main, second=second)
    return settings


def _profile_calls(
    backend: LonglistBackend,
    *,
    plan: dict[str, object],
    where: str,
    baseline: list[tuple[str, str]],
    payload: list[dict[str, object]],
    short_ids: Mapping[str, uuid.UUID],
    considerations: list[str] | None = None,
) -> list[tuple[str, Callable[[], UsageResult[Any]], Callable[[Any], Mapping[str, Any] | None]]]:
    """The ten profile calls: one per line, the ambition, the setting (R36, R40, R41).

    Where and the plan's who-can-act constraint texts reach the ``who_decides``
    call only (task 046, amendment 4: R89; S35).
    """

    def _line(line_key: str) -> Callable[[], UsageResult[Any]]:
        return lambda: backend.profile_line(
            line_key=line_key,
            plan=plan,
            where=where if line_key == "who_decides" else None,
            baseline_sections=baseline,
            options=payload,
            considerations=considerations if line_key == "who_decides" else None,
        )

    def _line_check(line_key: str) -> Callable[[Any], Mapping[str, Any] | None]:
        return lambda response: _checked_line(line_key, response, short_ids)

    calls: list[
        tuple[str, Callable[[], UsageResult[Any]], Callable[[Any], Mapping[str, Any] | None]]
    ] = [(line_key, _line(line_key), _line_check(line_key)) for line_key in PROFILE_LINE_KEYS]
    calls.append(
        (
            _AMBITION_CALL,
            lambda: backend.profile_ambition(
                plan=plan, baseline_sections=baseline, options=payload
            ),
            lambda response: _checked_ambition(response, short_ids),
        )
    )
    calls.append(
        (
            _SETTING_CALL,
            lambda: backend.profile_setting(plan=plan, options=payload),
            lambda response: _checked_setting(response, short_ids),
        )
    )
    return calls


def _fold_call_name(facet: str) -> str:
    """A folding call's name, as a failure names it."""
    return f"{facet} folding"


def _folding_words(read: MembershipRead) -> dict[str, dict[str, str]]:
    """Per facet, the list's distinct words keyed ``w1 … wN`` (S21).

    Over every member of every option read, sorted, de-duplicated
    case-folded (:func:`~policy_atlas.options_scoping.longlist.coverage.distinct_words`).
    """
    members = [member for held in read.members.values() for member in held]
    return {
        facet: {
            f"w{index}": word
            for index, word in enumerate(distinct_words(members, facet), start=1)
        }
        for facet in FOLD_FIELDS
    }


def _guarded_kind(kind: str, references: Sequence[str]) -> str:
    """The plan outcome a kind contains as whole words, else the kind (R86; S34).

    Case-folded, on word boundaries (``employment`` is not in
    ``unemployment``). Several outcomes in one kind: the longest wins, the
    first in plan order on a tie.
    """
    folded = kind.casefold()
    best = ""
    for text in references:
        text = " ".join(text.split())
        if not text or len(text) <= len(best):
            continue
        if re.search(rf"(?<!\w){re.escape(text.casefold())}(?!\w)", folded):
            best = text
    return best or kind


def _checked_folds(
    response: Any, words: Mapping[str, str], references: Sequence[str], *, facet: str
) -> dict[str, Any] | None:
    """One folding response mapped back to ``{word: kind}``; ``None`` when invalid.

    The wire (``folding_v3``) lists the kinds first, then each word's kind
    as a 0-based index into them. Invalid: not a :class:`FoldingResponse`;
    one input id given two different indexes; or not one input id answered.
    Otherwise every input word is in the map: a word left out, or whose
    index is out of range or names a blank kind, keeps its own text; an id
    not in the input is dropped (B10); a kind equal, case-folded, to one of
    ``references`` (the plan outcomes, or the target unit) is that plan text
    exactly (A4). More than :data:`FOLDING_KINDS_MAX` kinds is kept, and
    logged (the refine loop measures it). On the Measures facet only, a
    returned kind that contains a plan outcome as whole words becomes that
    outcome's text (the longest, when it contains several) before the words
    are mapped back (task 046, amendment 4: R86; S34; contract review C12).

    Returns:
        ``{"folds": {word: kind}, "catch_all": bool}``, or ``None``.
    """
    if not isinstance(response, FoldingResponse):
        return None
    indexes: dict[str, int] = {}
    for wire in response.folds:
        word_id = wire.word_id.strip()
        if word_id not in words:
            continue
        if indexes.get(word_id, wire.kind) != wire.kind:
            return None
        indexes[word_id] = wire.kind
    if words and not indexes:
        return None
    if len(response.kinds) > FOLDING_KINDS_MAX:
        log.warning(
            "option_profile.folding_kinds_over_max",
            kinds=len(response.kinds),
            max_kinds=FOLDING_KINDS_MAX,
        )
    # A kind joined by slashes is cut at the first slash (task 046, amendment
    # 4, round 7 of the folding loop: the mini model answers a cap with
    # "obesity / overweight / BMI"); the first member names the kind.
    kinds = [" ".join(kind.split(" / ")[0].split(" /")[0].split()) for kind in response.kinds]
    if facet == "measures":
        for position, returned in enumerate(kinds):
            mapped = _guarded_kind(returned, references)
            if mapped != returned:
                kinds[position] = mapped
                log.info(
                    "option_profile.folding_guard",
                    facet=facet,
                    returned_kind=returned,
                    outcome=mapped,
                )
    by_key = {
        fold_text(text): text for text in references if text and text.strip()
    }
    folds: dict[str, str] = {}
    for word_id, word in words.items():
        index = indexes.get(word_id)
        kind = kinds[index] if index is not None and 0 <= index < len(kinds) else ""
        kind = kind or word
        folds[word] = by_key.get(kind.casefold(), kind)
    largest = max(Counter(kind.casefold() for kind in folds.values()).values(), default=0)
    catch_all = (
        len(folds) >= FOLDING_CATCH_ALL_MIN_WORDS
        and largest > FOLDING_CATCH_ALL_SHARE * len(folds)
    )
    if catch_all:
        log.warning(
            "option_profile.folding_catch_all",
            facet=facet,
            words=len(folds),
            largest_kind_words=largest,
        )
    return {"folds": folds, "catch_all": catch_all}


def _folding_calls(
    backend: LonglistBackend,
    *,
    plan: dict[str, object],
    words: Mapping[str, dict[str, str]],
    plan_outcomes: Sequence[str],
    target_unit: str,
) -> list[
    tuple[
        str,
        Callable[[], UsageResult[Any]],
        Callable[[Any], Mapping[str, Any] | None],
        Callable[[Any], Mapping[str, Any] | None],
    ]
]:
    """The two folding calls, one per facet with words (R54, R55; S21).

    Each entry: the name, the call, the strict check (a catch-all answer is
    refused) and the lenient check for the last attempt.
    """
    references: dict[str, list[str]] = {"tried_on": [target_unit], "measures": list(plan_outcomes)}

    def _call(facet: Facet) -> Callable[[], UsageResult[Any]]:
        return lambda: backend.fold(facet=facet, plan=plan, words=dict(words[facet]))

    def _check(facet: Facet) -> Callable[[Any], Mapping[str, Any] | None]:
        return lambda response: _checked_folds(
            response, words[facet], references[facet], facet=facet
        )

    def _strict(facet: Facet) -> Callable[[Any], Mapping[str, Any] | None]:
        # A catch-all answer is refused on the first attempt (the retry's
        # answer is kept either way).
        lenient = _check(facet)

        def check(response: Any) -> Mapping[str, Any] | None:
            value = lenient(response)
            return None if value is not None and value.get("catch_all") else value

        return check

    facets: tuple[Facet, ...] = ("tried_on", "measures")
    return [
        (_fold_call_name(facet), _call(facet), _strict(facet), _check(facet))
        for facet in facets
        if words.get(facet)
    ]


def option_profile_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: OptionProfileContext,
    backend: LonglistBackend,
) -> dict[str, Any]:
    """Write what is said about each option of the walk's list (S16, S17, S20).

    The typing batches and the ten profile calls run at one time; every
    model call ends before the first write. The writes — the lever columns
    of every option typed validly, the ambition of every option, the
    ``option_profile`` column and the typing keys of the walk's latest
    ``longlist_result`` — share the component transaction.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``option_profile`` run.
        context: The walk's intent record.
        backend: The model seam (the longlist backend's typing and profile calls).

    Returns:
        ``{"options", "typed", "kept", "invalid", "profiled"}``: the options
        read, those typed validly, those whose earlier typing stands, those
        with no valid typing from this run (the kept ones and the never
        typed), and those profiled.

    Raises:
        OptionProfileFailure: If the walk has no ``longlist_result``, or a
            profile call or a folding call failed twice (nothing is written).
    """
    plan, _ = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    result_row = latest_longlist(conn, task_id=task_id, scope_id=context.scope_id)
    if result_row is None:
        raise OptionProfileFailure("option_profile: no longlist exists for this walk")
    plan_data = longlist_plan_data(plan)
    baseline = baseline_sections(conn, task_id)
    options = _profiled_options(conn, task_id=task_id)
    records = _evidence_records(conn, task_id=task_id, option_ids=[o.option_id for o in options])
    payload, short_ids = _profile_payload(options, records)
    # The folding calls read the distinct words of every member (S21).
    membership = read_membership(
        conn,
        task_id=task_id,
        scope_id=context.scope_id,
        option_ids=[o.option_id for o in options],
    )
    words = _folding_words(membership)
    plan_outcomes = [outcome.text for outcome in plan.outcomes]
    target_unit = plan.target_unit.text
    fold_calls = _folding_calls(
        backend, plan=plan_data, words=words, plan_outcomes=plan_outcomes, target_unit=target_unit
    )
    calls = (
        _profile_calls(
            backend,
            plan=plan_data,
            where=plan.where.text,
            baseline=baseline,
            payload=payload,
            short_ids=short_ids,
            considerations=who_decides_considerations(plan) or None,
        )
        if options
        else []
    )

    # The ten profile calls, the two folding calls and the typing batches,
    # at one time.
    usage = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=OPTION_PROFILE_MAX_CONCURRENT) as pool:
        futures: list[Future[CallOutcome[Mapping[str, Any]]]] = [
            tracing.submit_with_context(
                pool, call_with_retry, name, call, check, event="option_profile"
            )
            for name, call, check in calls
        ]
        fold_futures: list[Future[CallOutcome[Mapping[str, Any]]]] = [
            tracing.submit_with_context(
                pool,
                call_with_retry,
                name,
                call,
                check,
                final_check=final_check,
                event="option_profile",
            )
            for name, call, check, final_check in fold_calls
        ]
        # Typing (S12): batches in parallel; a kept typing carries forward.
        typings, kept_typings, typing_stats = _type_options(
            backend, options, usage, plan=plan_data, baseline=baseline
        )
        outcomes = [future.result() for future in futures]
        fold_outcomes = [future.result() for future in fold_futures]
    for outcome in [*outcomes, *fold_outcomes]:
        for call_usage in outcome.usages:
            usage.add(call_usage)
    failed = [
        outcome.name for outcome in [*outcomes, *fold_outcomes] if outcome.value is None
    ]
    if failed:
        log.warning("option_profile.failed", calls=failed)
        raise OptionProfileFailure(
            f"option_profile: the {', '.join(failed)} call failed after "
            f"{CALL_ATTEMPTS} attempts"
        )
    answers = {outcome.name: outcome.value for outcome in outcomes}
    retries = sum(outcome.attempts - 1 for outcome in outcomes)
    folded = {outcome.name: outcome.value or {} for outcome in fold_outcomes}
    by_facet = {facet: folded.get(_fold_call_name(facet), {}) for facet in FOLD_FIELDS}
    folds: dict[str, dict[str, str]] = {
        facet: dict(value.get("folds") or {}) for facet, value in by_facet.items()
    }
    catch_all = {facet: bool(value.get("catch_all")) for facet, value in by_facet.items()}

    # The second wave (S31): the place sentences, once the folds are known
    # and before any write. It never fails the step.
    resolved_where = resolve_country(plan.where.text)
    where_country = resolved_where[1] if resolved_where is not None else None
    stored_coverage = result_row.coverage if isinstance(result_row.coverage, Mapping) else {}
    place_sentences, place_stats = _place_sentence_wave(
        conn,
        backend,
        task_id=task_id,
        options=[o for o in options if isinstance(stored_coverage.get(str(o.option_id)), Mapping)],
        membership=membership,
        folds=folds,
        plan_outcomes=plan_outcomes,
        target_unit=target_unit,
        where_country=where_country,
        usage=usage,
    )

    runner_ups: dict[str, dict[str, Any]] = {
        str(option_id): {"lever_type": t.runner_up}
        for option_id, t in typings.items()
        if t.runner_up is not None
    }
    earlier_runner_ups, earlier_reasons = _earlier_typing_entries(
        conn, task_id=task_id, option_ids=kept_typings
    )
    runner_ups.update(earlier_runner_ups)
    lever_reasons: dict[str, str] = {
        str(option_id): t.lever_reason
        for option_id, t in typings.items()
        if t.lever_reason is not None
    }
    lever_reasons.update(earlier_reasons)

    # Writes, all after every model call.
    now = datetime.now(UTC)
    ambitions: Mapping[str, _Line] = answers.get(_AMBITION_CALL) or {}
    for short_id, o in zip(short_ids, options, strict=True):
        values: dict[str, Any] = {
            "ambition": ambitions[short_id].mark,
            "ambition_reason": ambitions[short_id].sentence,
            "updated_at": now,
        }
        typing = typings.get(o.option_id)
        if typing is not None:  # else kept: the lever columns stay as they are (S12)
            values.update(
                primary_lever_type=typing.primary,
                secondary_lever_types=typing.secondary,
                lever_none_fits_reason=typing.none_fits_reason,
                taxonomy_version=TAXONOMY_VERSION,
            )
        conn.execute(
            option.update()
            .where(option.c.option_id == o.option_id, option.c.task_id == task_id)
            .values(**values)
        )
    profile = _profile_column(options, short_ids, answers)
    coverage = _folded_coverage(
        result_row.coverage,
        membership,
        folds,
        plan_outcomes=plan_outcomes,
        where_country=where_country,
        place_sentences=place_sentences,
    )

    none_fits = sum(1 for t in typings.values() if t.primary is None)
    counts = dict(result_row.counts) if isinstance(result_row.counts, Mapping) else {}
    counts.update(
        none_fits=none_fits, typing_invalid=typing_stats["invalid"], profiled=len(profile)
    )
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
            "prompt_version": OPTION_PROFILE_PROMPT_VERSION,
            "model": LONGLIST_JUDGMENT_MODEL if live else "stub",
            "records_max": OPTION_PROFILE_RECORDS_MAX,
            "calls": len(calls),
            "retries": retries,
            "marks": {
                line_key: _mark_counts(answers.get(line_key) or {})
                for line_key in PROFILE_LINE_KEYS
            },
            "ambition_marks": _mark_counts(ambitions),
            "folding": {
                "prompt_version": FOLDING_PROMPT_VERSION,
                "model": LONGLIST_ASSIGNMENT_MODEL if live else "stub",
                "calls": len(fold_calls),
                "retries": sum(outcome.attempts - 1 for outcome in fold_outcomes),
                "words": {facet: len(words[facet]) for facet in FOLD_FIELDS},
                "kinds": {
                    facet: len({kind.casefold() for kind in folds[facet].values()})
                    for facet in FOLD_FIELDS
                },
                "catch_all": catch_all,
            },
            "place_sentences": {
                "prompt_version": PLACE_SENTENCES_PROMPT_VERSION,
                "model": LONGLIST_ASSIGNMENT_MODEL if live else "stub",
                **place_stats,
            },
        },
    )
    conn.execute(
        longlist_result.update()
        .where(
            longlist_result.c.longlist_result_id == result_row.longlist_result_id,
            longlist_result.c.task_id == task_id,
        )
        .values(
            counts=counts,
            provenance=provenance,
            option_profile={**profile, "folds": folds},
            coverage=coverage,
        )
    )
    kept_ids = set(kept_typings)
    summary = {
        "options": len(options),
        "typed": len(typings),
        "kept": sum(1 for o in options if o.option_id in kept_ids and o.typed_before),
        "invalid": typing_stats["invalid"],
        "profiled": len(profile),
    }
    log.info("option_profile.done", none_fits=none_fits, **summary)
    return summary


def _folded_coverage(
    stored: Any,
    membership: MembershipRead,
    folds: Mapping[str, Mapping[str, str]],
    *,
    plan_outcomes: Sequence[str],
    where_country: str | None = None,
    place_sentences: Mapping[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """The row's coverage with each option's folded keys recomputed (S21, S24).

    Each option the stored coverage holds and the membership read covers gets
    :data:`FOLDED_COVERAGE_KEYS` from its members through the maps, and each
    option the second wave wrote sentences for gets :data:`PLACE_SENTENCES_KEY`
    (task 046, amendment 4, S31); every other key, and every other option (an
    option added since, read from its own search at read time), is left as
    it is.
    """
    coverage = dict(stored) if isinstance(stored, Mapping) else {}
    recomputed = membership.coverage(
        plan_outcomes=plan_outcomes,
        folds=folds,
        where_country=where_country,
    )
    for option_id, fresh in recomputed.items():
        entry = coverage.get(option_id)
        if isinstance(entry, Mapping):
            coverage[option_id] = {
                **entry,
                **{key: fresh[key] for key in FOLDED_COVERAGE_KEYS},
            }
    for option_id, sentences in (place_sentences or {}).items():
        entry = coverage.get(option_id)
        if isinstance(entry, Mapping):
            coverage[option_id] = {**entry, PLACE_SENTENCES_KEY: sentences}
    return coverage


def _document_meta(
    conn: Connection, *, task_id: uuid.UUID, tss_ids: set[uuid.UUID]
) -> tuple[dict[uuid.UUID, int | None], dict[uuid.UUID, str]]:
    """Each document row's publication year and title, from its snapshot's metadata."""
    if not tss_ids:
        return {}, {}
    years: dict[uuid.UUID, int | None] = {}
    titles: dict[uuid.UUID, str] = {}
    for tss_id, metadata in conn.execute(
        select(task_source_snapshot.c.task_source_snapshot_id, source_snapshot.c.metadata)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(tss_ids))
    ):
        meta = metadata if isinstance(metadata, Mapping) else {}
        years[tss_id] = metadata_year(meta)
        title = meta.get("title")
        if isinstance(title, str) and title.strip():
            titles[tss_id] = " ".join(title.split())
    return years, titles


def _checked_places(
    response: Any, known: Collection[str] | None = None
) -> Mapping[str, Any] | None:
    """A place-sentence answer, checked; ``None`` when malformed (S31).

    An id not in ``known`` (the input's place ids) is dropped first, so an
    unknown id never makes the answer malformed; malformed is not a
    :class:`PlaceSentencesResponse`, or one known place id twice.
    """
    if not isinstance(response, PlaceSentencesResponse):
        return None
    pairs = [(wire.place_id.strip(), wire) for wire in response.places]
    if known is not None:
        pairs = [(pid, wire) for pid, wire in pairs if pid in known]
    ids = [pid for pid, _ in pairs]
    if len(ids) != len(set(ids)):
        return None
    return {"places": {pid: wire.sentence for pid, wire in pairs}}


def _checked_places_within_ceiling(
    response: Any, known: Collection[str] | None = None
) -> Mapping[str, Any] | None:
    """The place-sentence check for the first attempt: an answer with a
    sentence over the ceiling is refused once, so the retry can come in under
    it (loop 26L, round 3); the last attempt accepts it and the ceiling check
    then replaces that sentence with the template."""
    value = _checked_places(response, known)
    if value is None:
        return None
    places = value.get("places") or {}
    if any(len(str(text).strip()) > PLACE_SENTENCE_MAX_CHARS for text in places.values()):
        return None
    return value



def _place_sentence_wave(
    conn: Connection,
    backend: LonglistBackend,
    *,
    task_id: uuid.UUID,
    options: Sequence[_ProfiledOption],
    membership: MembershipRead,
    folds: Mapping[str, Mapping[str, str]],
    plan_outcomes: Sequence[str],
    target_unit: str,
    where_country: str | None,
    usage: UsageAccumulator,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """The place sentences of every option given (task 046, amendment 4, R80; S31).

    Per option, its evaluating documents grouped by place
    (:func:`~.place_sentences.group_places`, the Where country first); one call
    per option with at least one, in a pool of
    :data:`OPTION_PROFILE_MAX_CONCURRENT`, each tried once more. Per place:
    the answer's sentence, stripped, when it is within
    :data:`~.place_sentences_prompt.PLACE_SENTENCE_MAX_CHARS` and passes the
    trace check; else the template. A place the answer leaves out (or answers
    blank) keeps the template; an id not in the input is dropped; a call that
    raises or answers malformed twice leaves the option on templates. It
    never raises.

    Returns:
        ``({option_id: [{"place", "sentence", "generated", "where", "reason"}]}, stats)``;
        an option with no evaluating document maps to ``[]``.
    """
    started = time.monotonic()
    vocabulary = vocabulary_from_folds(folds)
    members = [m for o in options for m in membership.members.get(o.option_id, [])]
    years, titles = _document_meta(
        conn, task_id=task_id, tss_ids={m.tss_id for m in members if m.tss_id is not None}
    )
    groups: dict[str, list[PlaceGroup]] = {}
    for o in options:
        option_members = membership.members.get(o.option_id, [])
        documents = from_membership(
            option_members,
            labels=membership.labels,
            folds=folds,
            plan_outcomes=plan_outcomes,
            programme_fold=fold_programme_names(
                name
                for m in option_members
                if (name := clean_text(m.programme_name)) is not None
            ),
            year_by_tss=years,
            title_by_tss=titles,
        )
        groups[str(o.option_id)] = group_places(documents, where_country=where_country)
    called = [o for o in options if groups[str(o.option_id)]]

    def _call(o: _ProfiledOption) -> Callable[[], UsageResult[Any]]:
        data = call_input(
            o.label,
            o.description,
            plan_outcomes=plan_outcomes,
            target_unit=target_unit,
            vocabulary=vocabulary,
            groups=groups[str(o.option_id)],
        )
        return lambda: backend.place_sentences(**data)

    def _place_ids(o: _ProfiledOption) -> frozenset[str]:
        return frozenset(group.place_id for group in groups[str(o.option_id)])

    with ThreadPoolExecutor(max_workers=OPTION_PROFILE_MAX_CONCURRENT) as pool:
        futures = {
            str(o.option_id): tracing.submit_with_context(
                pool,
                call_with_retry,
                f"place sentences {o.option_id}",
                _call(o),
                partial(_checked_places_within_ceiling, known=_place_ids(o)),
                final_check=partial(_checked_places, known=_place_ids(o)),
                event="option_profile",
            )
            for o in called
        }
        answers = {option_id: future.result() for option_id, future in futures.items()}
    stats: dict[str, Any] = {
        "calls": len(called),
        "retries": 0,
        "generated": 0,
        "template": 0,
        "failed_call": 0,
    }
    sentences: dict[str, list[dict[str, Any]]] = {}
    for o in options:
        option_id = str(o.option_id)
        outcome = answers.get(option_id)
        answered: Mapping[str, str] | None = None
        if outcome is not None:
            for call_usage in outcome.usages:
                usage.add(call_usage)
            stats["retries"] += outcome.attempts - 1
            if outcome.value is None:
                stats["failed_call"] += 1
                log.warning("option_profile.place_sentences_failed", option_id=option_id)
            else:
                answered = outcome.value["places"]
        entries: list[dict[str, Any]] = []
        for group in groups[option_id]:
            sentence = (answered or {}).get(group.place_id, "").strip()
            generated = False
            # Why the template stands, kept with the entry so that a card's
            # sentence can be diagnosed without the log (review of task 046,
            # 2026-10-12): "call", "missing", "length" or the trace rule.
            reason: str | None = (
                "call" if outcome is not None and outcome.value is None else "missing"
            )
            if sentence and len(sentence) > PLACE_SENTENCE_MAX_CHARS:
                reason = "length"
                log.info(
                    "option_profile.place_sentence_too_long",
                    option_id=option_id,
                    place=group.place,
                    length=len(sentence),
                    sentence=sentence[:300],
                )
            elif sentence:
                rule = trace_check(
                    sentence,
                    group,
                    plan_outcomes=plan_outcomes,
                    vocabulary=vocabulary,
                    target_unit=target_unit,
                )
                if rule is None:
                    generated, reason = True, None
                else:
                    reason = rule
                    log.info(
                        "option_profile.place_sentence_trace_failed",
                        option_id=option_id,
                        place=group.place,
                        rule=rule,
                        sentence=sentence[:240],
                    )
            stats["generated" if generated else "template"] += 1
            entries.append(
                {
                    "place": group.place,
                    "sentence": (
                        sentence
                        if generated
                        else template_sentence(group, target_unit=target_unit)
                    ),
                    "generated": generated,
                    "where": group.is_where,
                    "reason": reason,
                }
            )
        sentences[option_id] = entries
    stats["seconds"] = round(time.monotonic() - started, 2)
    log.info("option_profile.place_sentences", **stats)
    return sentences, stats


def _mark_counts(answers: Mapping[str, _Line]) -> dict[str, int]:
    """The count of ``less``, ``more`` and no mark over one call's answers."""
    marks = Counter(line.mark for line in answers.values())
    return {"less": marks["less"], "more": marks["more"], "none": marks[None]}


def _profile_column(
    options: Sequence[_ProfiledOption],
    short_ids: Mapping[str, uuid.UUID],
    answers: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, dict[str, dict[str, Any]]]:
    """The ``longlist_result.option_profile`` value (S17; final § 2.10).

    ``{option_id: {design_version: {"lines": {line key: {"sentence",
    "mark"}}, "setting": {"main", "second"}}}}`` for every option of the list,
    the lines in :data:`~policy_atlas.runtime.scoping_plan.PROFILE_LINE_KEYS`
    order.
    """
    settings: Mapping[str, _Setting] = answers.get(_SETTING_CALL) or {}
    column: dict[str, dict[str, dict[str, Any]]] = {}
    for short_id, o in zip(short_ids, options, strict=True):
        lines: dict[str, dict[str, str | None]] = {}
        for line_key in PROFILE_LINE_KEYS:
            line: _Line = (answers.get(line_key) or {})[short_id]
            lines[line_key] = {"sentence": line.sentence, "mark": line.mark}
        setting = settings[short_id]
        column[str(o.option_id)] = {
            str(o.design_version): {
                "lines": lines,
                "setting": {"main": setting.main, "second": setting.second},
            }
        }
    return column
