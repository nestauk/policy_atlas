"""The source-quality profile: an option's deterministic coverage (task 045, S8).

Per option, from its membership alone — no model call, the same inputs always
give the same JSON: documents by evidence type and quality tier (through the
label resolver, :func:`~policy_atlas.options_scoping.labels.labels_for_snapshots`),
by role, where tried (two levels from the records' ``study_country`` and
``study_geography``: :mod:`.where_tried`), populations,
settings, outcomes; flagged members counted (``design_feature_not_stated``,
D11); ``abstract_only`` counted. Display and a later sort, never "how sure"
(ruling 33).

Task 046 (S11) adds the counts by population tag, *tried on* (the
populations of the ``adjacent`` members), the *examples* (the members'
distinct programme names), ``folded`` (the folded seeds' names) and the setting pass: on
this read side only — the stored record is never rewritten — a setting that
names a place is read as the record's study geography (when it has none) or
left out of the facet, each a counted and logged repair, and the remaining
settings' spelling variants are grouped into one facet label
(:data:`SETTING_FOLDS`).

The outcome counts (R42, R56) give, in documents, how many evaluated the option
(a member with role ``evaluated``) and, per plan outcome, how many documents of
any role have a member whose ``outcome_tag`` is that outcome (case and
whitespace folded, as the longlist reads the tag) and, separately, how many of
those have an ``evaluated`` member with that tag; ``other`` and no tag count for
no outcome. Counts only: no direction, no size.

**The folded kinds (task 046, amendment 3, R54, R55; S21, S24).** Given the
list's two folding maps (word → kind, stored by ``option_profile`` at list
level), the coverage carries ``tried_on_kinds`` (documents per kind of the
records' ``unit`` words, the plan's target unit's kind first) and
``measures_kinds`` (documents and evaluated documents per kind of the
records' ``outcome`` words). A word the map lacks keeps its own text as its
kind; two words of one kind in one document count one document. A plan
outcome's row also counts the documents whose records are tagged ``other``
or not tagged and whose Measures kind is that outcome's own text (A4), and
``outcome_counts.other`` lists the other kinds, counting only such records.
Without the maps both lists and ``other`` are empty.

**Counting grain (D16, A8, A20).** Every count below except ``members`` and
``flagged_members`` is a count of *documents*, and documents are collapsed by
DOI: two documents whose normalised DOI is the same count once; a document
without a DOI counts as itself. Membership rows stay uncollapsed.

**Labels.** Unknown and Non-evidence are their own evidence-type buckets
(they are classification results); a document with no label (the resolver's
``absent``) is ``not rated``; an inherited label counts as its type and tier,
and ``inherited_labels`` says how many documents' labels came through a link.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import structlog

from policy_atlas.options_scoping.labels import DocumentLabels
from policy_atlas.options_scoping.longlist.where_tried import (
    MULTIPLE_COUNTRIES,
    document_where,
    names_place,
)

log = structlog.get_logger()

#: The bucket for a document with no evidence type or no quality tier.
NOT_RATED = "not rated"

#: The role funnel's keys, in display order (``comparator`` never counts as
#: membership, so it has no bucket).
ROLE_BUCKETS: tuple[str, ...] = ("evaluated", "described", "recommended", "mentioned")

#: The population-tag buckets, in display order; ``not_tagged`` is a member
#: with no tag (a record from another tagging context, a linked finding).
POPULATION_TAG_BUCKETS: tuple[str, ...] = ("on_target", "adjacent", "other", "not_tagged")

#: At most this many *tried on* populations per option (AM20).
TRIED_ON_MAX = 8

#: At most this many *examples* (distinct programme names) per option (R63).
EXAMPLES_MAX = 5

#: The two folded facets and the record field each folds (R54, R55).
FOLD_FIELDS: dict[str, str] = {"tried_on": "unit", "measures": "outcome"}

#: The outcome tag of a record whose outcome is not a plan outcome.
OTHER_OUTCOME_TAG = "other"

#: The setting folds, applied in order to the whitespace-collapsed,
#: case-folded setting to give the key its spellings are grouped under
#: (the facet shows the members' most frequent original spelling): a
#: trailing "setting(s)" goes ("school settings" → "school"), then the
#: last word loses its plural ("communities" → "community", "schools" →
#: "school"; "business", "campus" and "analysis" keep their "s"). The
#: whole rule is this table.
SETTING_FOLDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\s+settings?$"), ""),
    (re.compile(r"ies$"), "y"),
    (re.compile(r"(?<![sui])s$"), ""),
)

_DOI_PREFIXES: tuple[str, ...] = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalise_doi(metadata: Mapping[str, Any] | None) -> str | None:
    """A document's DOI, normalised for counting, or ``None``.

    Lower-cased, trimmed, a resolver prefix (``https://doi.org/`` and its
    variants, ``doi:``) stripped.

    Args:
        metadata: The document's envelope metadata.

    Returns:
        The normalised DOI, or ``None`` when the document has none.
    """
    if not isinstance(metadata, Mapping):
        return None
    value = metadata.get("doi")
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip().casefold()
    for prefix in _DOI_PREFIXES:
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
            break
    return doi or None


def document_key(*, doi: str | None, document_id: uuid.UUID | str) -> str:
    """The key a document counts under: its DOI, else itself.

    Args:
        doi: The normalised DOI, or ``None``.
        document_id: The document's own id (a ``task_source_snapshot`` id, or
            a source snapshot id for a linked finding with no row here).

    Returns:
        ``doi:<doi>`` or ``doc:<id>``.
    """
    return f"doi:{doi}" if doi else f"doc:{document_id}"


@dataclass(frozen=True)
class CoverageMember:
    """One membership row as coverage reads it.

    Attributes:
        unit_kind: ``interventions``, ``iof`` or ``icf``.
        doc_key: :func:`document_key` of the unit's document.
        tss_id: This task's document row, when there is one (the label key).
        role: The record's role (for a linked finding, the role its kind
            implies: an IOF finding reports an evaluated effect, an ICF
            finding describes implementation).
        basis: The extraction basis (``abstract_only`` or ``full_text``).
        flagged: ``design_feature_not_stated``.
        unit: The record's unit text (who or what it was delivered to).
        setting: The record's setting text.
        outcome: The record's outcome text.
        study_geography: The record's study geography text.
        programme_name: The record's programme name (task 046, amendment 3),
            ``None`` for a linked finding.
        study_country: The record's study country (task 046, amendment 3),
            ``None`` for a linked finding.
        intervention: The record's intervention name.
        unit_tag: The record's unit tag, ``None`` when not tagged
            (task 046).
        outcome_tag: The record's outcome tag (a plan outcome's text or
            ``other``), ``None`` when not tagged and for a linked finding
            (R42).
    """

    unit_kind: str
    doc_key: str
    tss_id: uuid.UUID | None
    role: str | None
    basis: str | None
    flagged: bool
    unit: str | None
    setting: str | None
    outcome: str | None
    study_geography: str | None
    intervention: str | None = None
    unit_tag: str | None = None
    outcome_tag: str | None = None
    programme_name: str | None = None
    study_country: str | None = None


@dataclass(frozen=True)
class FoldedSeed:
    """An option folded into another by discovery, listed under ``folded``.

    Attributes:
        name: The folded option's name.
        documents: The folded option's own member documents (0 when its
            members now sit with the wider option).
    """

    name: str
    documents: int


def fold_setting(setting: str) -> str:
    """The key a setting's spelling variants are grouped under (:data:`SETTING_FOLDS`).

    Args:
        setting: A non-empty setting text.

    Returns:
        The folded key (lower case, single spaces, singular).
    """
    label = " ".join(setting.split()).casefold()
    for pattern, replacement in SETTING_FOLDS:
        label = pattern.sub(replacement, label)
    return label or " ".join(setting.split()).casefold()


def _read_setting(member: CoverageMember) -> tuple[str | None, str | None, str | None]:
    """The setting pass on one member: ``(setting_label, study_geography, repair)``.

    A setting that names a place (:func:`names_place`) is not a setting: it
    is read as the study geography when the record has none (``moved``),
    else it leaves the facet (``dropped``). Any other setting is kept as
    written, to be grouped by :func:`fold_setting`. Nothing is written back.
    """
    setting = _clean(member.setting)
    geography = member.study_geography
    if setting is None:
        return None, geography, None
    if names_place(setting):
        if _clean(geography) is None:
            return None, setting, "moved"
        return None, geography, "dropped"
    return setting, geography, None


def _ranked(
    counts: dict[str, set[str]], shown: dict[str, str]
) -> list[tuple[str, int]]:
    """``(display text, documents)`` by documents descending, then text."""
    return sorted(
        ((shown[key], len(docs)) for key, docs in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )


def _show(shown: dict[str, str], key: str, text: str) -> None:
    """Keep the smallest spelling of a folded key as its display text."""
    current = shown.get(key)
    if current is None or text < current:
        shown[key] = text


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def _fold_tag(value: str) -> str:
    """An outcome tag or plan outcome as compared (case and whitespace folded)."""
    return " ".join(value.split()).casefold()


def _add(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _sorted(counts: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _pick_label(candidates: list[DocumentLabels]) -> DocumentLabels | None:
    """The label a DOI-collapsed document counts under.

    The twin whose label is resolved (an evidence type or a tier) wins, own
    before inherited, then the one with a tier; the first twin (id order)
    only when none is resolved. Deterministic whatever the ids' order.
    """
    resolved = [
        label
        for label in candidates
        if label.provenance != "absent"
        and (label.evidence_type is not None or label.quality_score is not None)
    ]
    if not resolved:
        return candidates[0] if candidates else None
    return min(
        enumerate(resolved),
        key=lambda item: (
            item[1].provenance != "own",
            item[1].quality_score is None,
            item[1].evidence_type is None,
            item[0],
        ),
    )[1]


def distinct_words(members: Iterable[CoverageMember], facet: str) -> list[str]:
    """The distinct words of one folded facet over ``members`` (S21).

    Whitespace collapsed, de-duplicated case-folded, sorted; each word shown
    in the first spelling of that order.

    Args:
        members: Membership rows, as coverage reads them.
        facet: ``"tried_on"`` (the ``unit`` words) or ``"measures"`` (the
            ``outcome`` words).

    Returns:
        The distinct words.
    """
    field = FOLD_FIELDS[facet]
    cleaned = {
        word for member in members if (word := _clean(getattr(member, field))) is not None
    }
    out: list[str] = []
    seen: set[str] = set()
    for word in sorted(cleaned, key=lambda text: (text.casefold(), text)):
        if word.casefold() not in seen:
            seen.add(word.casefold())
            out.append(word)
    return out


def stored_folds(option_profile: object) -> dict[str, dict[str, str]] | None:
    """The list's folding maps as ``option_profile`` stored them (S21).

    Args:
        option_profile: A ``longlist_result.option_profile`` value.

    Returns:
        ``{"tried_on": {word: kind}, "measures": {word: kind}}``, or ``None``
        when the row holds no maps (a row the profile step has not run on).
    """
    raw = option_profile.get("folds") if isinstance(option_profile, Mapping) else None
    if not isinstance(raw, Mapping):
        return None
    out: dict[str, dict[str, str]] = {}
    for facet in FOLD_FIELDS:
        stored = raw.get(facet)
        out[facet] = {
            word: kind
            for word, kind in (stored.items() if isinstance(stored, Mapping) else ())
            if isinstance(word, str) and isinstance(kind, str)
        }
    return out


def _fold_lookup(
    folds: Mapping[str, Mapping[str, str]] | None, facet: str
) -> dict[str, str] | None:
    """One facet's stored map, keyed case-folded; ``None`` without maps."""
    if folds is None:
        return None
    stored = folds.get(facet)
    lookup: dict[str, str] = {}
    for word, kind in (stored if isinstance(stored, Mapping) else {}).items():
        clean_word = _clean(word) if isinstance(word, str) else None
        clean_kind = _clean(kind) if isinstance(kind, str) else None
        if clean_word is not None and clean_kind is not None:
            lookup.setdefault(_fold_tag(clean_word), clean_kind)
    return lookup


def _kind(lookup: Mapping[str, str], text: str | None) -> str | None:
    """A record word's kind: the map's, else the word itself; ``None`` for no word."""
    word = _clean(text)
    if word is None:
        return None
    return lookup.get(_fold_tag(word), word)


def _untagged(member: CoverageMember) -> bool:
    """A record tagged ``other`` or not tagged (A4)."""
    return not member.outcome_tag or _fold_tag(member.outcome_tag) == OTHER_OUTCOME_TAG


def empty_coverage() -> dict[str, Any]:
    """The coverage of an option with no member (a seed nothing was assigned to).

    Returns:
        Every key present, every count zero.
    """
    return option_coverage([], labels={})


def option_coverage(
    members: Iterable[CoverageMember],
    *,
    labels: Mapping[uuid.UUID, DocumentLabels],
    folded_seeds: Sequence[FoldedSeed] = (),
    plan_outcomes: Sequence[str] = (),
    folds: Mapping[str, Mapping[str, str]] | None = None,
    target_unit: str | None = None,
) -> dict[str, Any]:
    """Compute one option's source-quality profile.

    Args:
        members: The option's membership rows, as coverage reads them.
        labels: The label resolver's answer per ``tss_id``.
        folded_seeds: The options discovery folded into this one (task 046),
            named under ``folded``.
        plan_outcomes: The plan's outcome texts, in plan order (R42).
        folds: The list's folding maps, ``{"tried_on": {word: kind},
            "measures": {word: kind}}`` (S21); ``None`` leaves the kinds and
            ``outcome_counts.other`` empty.
        target_unit: The plan's target unit as the folding call read it
            (place stripped): its kind leads ``tried_on_kinds``.

    Returns:
        ``members`` · ``documents`` · ``flagged_members`` ·
        ``flagged_documents`` · ``abstract_only`` · ``inherited_labels`` ·
        ``evidence_type`` · ``tier`` · ``role`` · ``where_tried`` (a list of
        ``{top, documents, places: [{place, documents}], countries}``, by
        documents descending then top; ``countries`` is empty except under
        "multiple countries") · ``populations`` · ``settings`` · ``outcomes`` ·
        ``findings`` · ``population_tags`` · ``tried_on`` ·
        ``examples`` (``[{name, documents}]``, at most :data:`EXAMPLES_MAX`) ·
        ``folded`` (the folded seeds' names) ·
        ``setting_repairs`` · ``outcome_counts`` (``evaluating_documents``,
        ``by_outcome``: ``[{outcome, documents, evaluated}]`` in plan order, and
        ``other``: ``[{kind, documents, evaluated}]``, the Measures kinds that
        are not plan outcomes, counting only records tagged ``other`` or not
        tagged) · ``tried_on_kinds`` (``[{kind, documents}]``) ·
        ``measures_kinds`` (``[{kind, documents, evaluated}]``) — documents
        DOI-collapsed except the two member counts and ``setting_repairs``
        (one per member repaired).
    """
    by_doc: dict[str, list[CoverageMember]] = {}
    member_count = 0
    flagged_members = 0
    setting_repairs = 0
    findings = {"iof": 0, "icf": 0}
    # The setting pass, member by member: each member is read with its
    # setting label and its (possibly moved-in) geography.
    for member in members:
        member_count += 1
        flagged_members += int(member.flagged)
        if member.unit_kind in findings:
            findings[member.unit_kind] += 1
        setting_label, geography, repair = _read_setting(member)
        if repair is not None:
            setting_repairs += 1
            log.info(
                "longlist.coverage.setting_repair",
                action=repair,
                setting=_clean(member.setting),
                unit_kind=member.unit_kind,
            )
        by_doc.setdefault(member.doc_key, []).append(
            replace(member, setting=setting_label, study_geography=geography)
        )

    evidence_type: dict[str, int] = {}
    tier: dict[str, int] = {}
    role = dict.fromkeys(ROLE_BUCKETS, 0)
    where_docs: dict[str, set[str]] = {}
    where_shown: dict[str, str] = {}
    where_places: dict[str, dict[str, set[str]]] = {}
    places_shown: dict[str, str] = {}
    where_countries: dict[str, set[str]] = {}
    countries_shown: dict[str, str] = {}
    populations: dict[str, int] = {}
    settings: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    population_tags = dict.fromkeys(POPULATION_TAG_BUCKETS, 0)
    setting_docs: dict[str, set[str]] = {}
    setting_spellings: dict[str, dict[str, int]] = {}
    tried_on: dict[str, set[str]] = {}
    tried_on_shown: dict[str, str] = {}
    examples: dict[str, set[str]] = {}
    examples_shown: dict[str, str] = {}
    flagged_documents = 0
    abstract_only = 0
    inherited_labels = 0
    evaluating_documents = 0
    outcome_documents = dict.fromkeys((_fold_tag(o) for o in plan_outcomes), 0)
    outcome_evaluated = dict.fromkeys(outcome_documents, 0)
    tried_lookup = _fold_lookup(folds, "tried_on")
    measures_lookup = _fold_lookup(folds, "measures")
    tried_kinds: dict[str, set[str]] = {}
    tried_kinds_shown: dict[str, str] = {}
    measure_kinds: dict[str, set[str]] = {}
    measure_kinds_evaluated: dict[str, set[str]] = {}
    measure_kinds_shown: dict[str, str] = {}
    other_kinds: dict[str, set[str]] = {}
    other_kinds_evaluated: dict[str, set[str]] = {}

    for key in sorted(by_doc):
        doc_members = by_doc[key]
        # A DOI-collapsed document takes its best-resolved twin's labels.
        tss_ids = sorted({m.tss_id for m in doc_members if m.tss_id is not None}, key=str)
        label = _pick_label([labels[t] for t in tss_ids if t in labels])
        if label is None or label.provenance == "absent":
            _add(evidence_type, NOT_RATED)
            _add(tier, NOT_RATED)
        else:
            _add(evidence_type, label.evidence_type or NOT_RATED)
            _add(tier, str(label.quality_score) if label.quality_score is not None else NOT_RATED)
            inherited_labels += int(label.provenance == "inherited")
        for role_key in {m.role for m in doc_members if m.role in role}:
            role[role_key] += 1
        evaluated = [m for m in doc_members if m.role == "evaluated"]
        evaluating_documents += int(bool(evaluated))
        doc_outcomes = {_fold_tag(m.outcome_tag) for m in doc_members if m.outcome_tag}
        doc_outcomes_evaluated = {_fold_tag(m.outcome_tag) for m in evaluated if m.outcome_tag}
        if tried_lookup is not None:
            for m in doc_members:
                kind = _kind(tried_lookup, m.unit)
                if kind is not None:
                    tried_kinds.setdefault(_fold_tag(kind), set()).add(key)
                    _show(tried_kinds_shown, _fold_tag(kind), kind)
        if measures_lookup is not None:
            for m in doc_members:
                kind = _kind(measures_lookup, m.outcome)
                if kind is None:
                    continue
                kind_key = _fold_tag(kind)
                measure_kinds.setdefault(kind_key, set()).add(key)
                _show(measure_kinds_shown, kind_key, kind)
                if m.role == "evaluated":
                    measure_kinds_evaluated.setdefault(kind_key, set()).add(key)
                if not _untagged(m):
                    continue
                # A4: a record tagged other (or not tagged) whose kind is a
                # plan outcome counts on that outcome's row; any other kind
                # counts under ``other``.
                if kind_key in outcome_documents:
                    doc_outcomes.add(kind_key)
                    if m.role == "evaluated":
                        doc_outcomes_evaluated.add(kind_key)
                else:
                    other_kinds.setdefault(kind_key, set()).add(key)
                    if m.role == "evaluated":
                        other_kinds_evaluated.setdefault(kind_key, set()).add(key)
        for tag in doc_outcomes & set(outcome_documents):
            outcome_documents[tag] += 1
        for tag in doc_outcomes_evaluated & set(outcome_documents):
            outcome_evaluated[tag] += 1
        # A document counts as flagged only when none of its members here
        # states the defining feature.
        flagged_documents += int(all(m.flagged for m in doc_members))
        abstract_only += int(all(m.basis == "abstract_only" for m in doc_members))
        top, doc_countries = document_where(
            (m.study_country, m.study_geography) for m in doc_members
        )
        top_key = top.casefold()
        where_docs.setdefault(top_key, set()).add(key)
        _show(where_shown, top_key, top)
        places = where_places.setdefault(top_key, {})
        for m in doc_members:
            place = _clean(m.study_geography)
            if place is not None:
                places.setdefault(place.casefold(), set()).add(key)
                _show(places_shown, place.casefold(), place)
        if top == MULTIPLE_COUNTRIES:
            for country in doc_countries:
                where_countries.setdefault(top_key, set()).add(country.casefold())
                _show(countries_shown, country.casefold(), country)
        for m in doc_members:
            if m.setting is not None:
                folded_setting = fold_setting(m.setting)
                setting_docs.setdefault(folded_setting, set()).add(key)
                spellings = setting_spellings.setdefault(folded_setting, {})
                spellings[m.setting] = spellings.get(m.setting, 0) + 1
        for field, counts in (
            ("unit", populations),
            ("outcome", outcomes),
        ):
            for value in {_clean(getattr(m, field)) for m in doc_members} - {None}:
                assert value is not None
                _add(counts, value)
        for tag in {
            m.unit_tag if m.unit_tag in POPULATION_TAG_BUCKETS else "not_tagged"
            for m in doc_members
        }:
            population_tags[tag] += 1
        for m in doc_members:
            population = _clean(m.unit) if m.unit_tag == "adjacent" else None
            if population is not None:
                folded = population.casefold()
                tried_on.setdefault(folded, set()).add(key)
                _show(tried_on_shown, folded, population)
            name = _clean(m.programme_name)
            if name is not None:
                folded = name.casefold()
                examples.setdefault(folded, set()).add(key)
                _show(examples_shown, folded, name)

    # One facet label per folded setting: its most frequent original spelling
    # among the members, then the shortest, then the first alphabetically.
    for folded_setting, docs in setting_docs.items():
        counts_by_spelling = setting_spellings[folded_setting]
        shown = min(
            counts_by_spelling,
            key=lambda text: (-counts_by_spelling[text], len(text), text),
        )
        settings[shown] = len(docs)

    target_key = _fold_tag(target_unit) if target_unit and target_unit.strip() else None
    tried_on_kinds = [
        {"kind": tried_kinds_shown[kind_key], "documents": len(docs)}
        for kind_key, docs in sorted(
            tried_kinds.items(),
            key=lambda item: (
                item[0] != target_key,
                -len(item[1]),
                tried_kinds_shown[item[0]],
            ),
        )
    ]

    def _kind_rows(
        docs_by_kind: dict[str, set[str]], evaluated_by_kind: dict[str, set[str]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "kind": measure_kinds_shown[kind_key],
                "documents": len(docs),
                "evaluated": len(evaluated_by_kind.get(kind_key, set())),
            }
            for kind_key, docs in sorted(
                docs_by_kind.items(),
                key=lambda item: (-len(item[1]), measure_kinds_shown[item[0]]),
            )
        ]

    return {
        "members": member_count,
        "documents": len(by_doc),
        "flagged_members": flagged_members,
        "flagged_documents": flagged_documents,
        "abstract_only": abstract_only,
        "inherited_labels": inherited_labels,
        "evidence_type": _sorted(evidence_type),
        "tier": _sorted(tier),
        "role": role,
        "where_tried": [
            {
                "top": where_shown[top_key],
                "documents": len(docs),
                "places": [
                    {"place": place, "documents": documents}
                    for place, documents in _ranked(where_places[top_key], places_shown)
                ],
                "countries": sorted(
                    (countries_shown[c] for c in where_countries.get(top_key, set())),
                    key=lambda name: (name.casefold(), name),
                ),
            }
            for top_key, docs in sorted(
                where_docs.items(), key=lambda item: (-len(item[1]), where_shown[item[0]])
            )
        ],
        "populations": _sorted(populations),
        "settings": _sorted(settings),
        "outcomes": _sorted(outcomes),
        "findings": findings,
        "population_tags": population_tags,
        "tried_on": [
            {"population": population, "documents": documents}
            for population, documents in _ranked(tried_on, tried_on_shown)[:TRIED_ON_MAX]
        ],
        "examples": [
            {"name": name, "documents": documents}
            for name, documents in _ranked(examples, examples_shown)[:EXAMPLES_MAX]
        ],
        "folded": [
            name
            for name in dict.fromkeys(_clean(seed.name) or seed.name for seed in folded_seeds)
        ],
        "setting_repairs": setting_repairs,
        "outcome_counts": {
            "evaluating_documents": evaluating_documents,
            "by_outcome": [
                {
                    "outcome": outcome,
                    "documents": outcome_documents[_fold_tag(outcome)],
                    "evaluated": outcome_evaluated[_fold_tag(outcome)],
                }
                for outcome in plan_outcomes
            ],
            # Each Measures kind that is not a plan outcome, counting only
            # records tagged other or not tagged (A4).
            "other": _kind_rows(other_kinds, other_kinds_evaluated),
        },
        "tried_on_kinds": tried_on_kinds,
        "measures_kinds": _kind_rows(measure_kinds, measure_kinds_evaluated),
    }
