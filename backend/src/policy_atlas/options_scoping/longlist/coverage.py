"""The source-quality profile: an option's deterministic coverage (task 045, S8).

Per option, from its membership alone — no model call, the same inputs always
give the same JSON: documents by evidence type and quality tier (through the
label resolver, :func:`~policy_atlas.options_scoping.labels.labels_for_snapshots`),
by role, where tried (grouped against the plan's Where), populations,
settings, outcomes; flagged members counted (``design_feature_not_stated``,
D11); ``abstract_only`` counted. Display and a later sort, never "how sure"
(ruling 33).

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

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from policy_atlas.options_scoping.labels import DocumentLabels
from policy_atlas.options_scoping.longlist.where_tried import (
    WHERE_GROUPS,
    countries_in,
    where_group,
)

#: The bucket for a document with no evidence type or no quality tier.
NOT_RATED = "not rated"

#: The role funnel's keys, in display order (``comparator`` never counts as
#: membership, so it has no bucket).
ROLE_BUCKETS: tuple[str, ...] = ("evaluated", "described", "recommended", "mentioned")

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
        population: The record's population text.
        setting: The record's setting text.
        outcome: The record's outcome text.
        study_geography: The record's study geography text.
    """

    unit_kind: str
    doc_key: str
    tss_id: uuid.UUID | None
    role: str | None
    basis: str | None
    flagged: bool
    population: str | None
    setting: str | None
    outcome: str | None
    study_geography: str | None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


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


def empty_coverage() -> dict[str, Any]:
    """The coverage of an option with no member (a seed nothing was assigned to).

    Returns:
        Every key present, every count zero.
    """
    return option_coverage([], labels={}, home=frozenset())


def option_coverage(
    members: Iterable[CoverageMember],
    *,
    labels: Mapping[uuid.UUID, DocumentLabels],
    home: frozenset[str],
) -> dict[str, Any]:
    """Compute one option's source-quality profile.

    Args:
        members: The option's membership rows, as coverage reads them.
        labels: The label resolver's answer per ``tss_id``.
        home: The plan's Where as ISO codes.

    Returns:
        ``members`` · ``documents`` · ``flagged_members`` ·
        ``flagged_documents`` · ``abstract_only`` · ``inherited_labels`` ·
        ``evidence_type`` · ``tier`` · ``role`` · ``where_tried`` ·
        ``countries`` · ``populations`` · ``settings`` · ``outcomes`` ·
        ``findings`` — documents DOI-collapsed except the two member counts.
    """
    by_doc: dict[str, list[CoverageMember]] = {}
    member_count = 0
    flagged_members = 0
    findings = {"iof": 0, "icf": 0}
    for member in members:
        member_count += 1
        flagged_members += int(member.flagged)
        if member.unit_kind in findings:
            findings[member.unit_kind] += 1
        by_doc.setdefault(member.doc_key, []).append(member)

    evidence_type: dict[str, int] = {}
    tier: dict[str, int] = {}
    role = dict.fromkeys(ROLE_BUCKETS, 0)
    where_tried = dict.fromkeys(WHERE_GROUPS, 0)
    countries: dict[str, int] = {}
    populations: dict[str, int] = {}
    settings: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    flagged_documents = 0
    abstract_only = 0
    inherited_labels = 0

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
        # A document counts as flagged only when none of its members here
        # states the defining feature.
        flagged_documents += int(all(m.flagged for m in doc_members))
        abstract_only += int(all(m.basis == "abstract_only" for m in doc_members))
        geographies = [m.study_geography for m in doc_members]
        where_tried[where_group(geographies, home)] += 1
        doc_codes: set[str] = set()
        for text in geographies:
            doc_codes |= countries_in(text)[0]
        for code in doc_codes:
            _add(countries, code)
        for field, counts in (
            ("population", populations),
            ("setting", settings),
            ("outcome", outcomes),
        ):
            for value in {_clean(getattr(m, field)) for m in doc_members} - {None}:
                assert value is not None
                _add(counts, value)

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
        "where_tried": where_tried,
        "countries": _sorted(countries),
        "populations": _sorted(populations),
        "settings": _sorted(settings),
        "outcomes": _sorted(outcomes),
        "findings": findings,
    }
