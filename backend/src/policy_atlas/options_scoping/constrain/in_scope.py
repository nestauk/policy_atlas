"""The deterministic "no in-scope evidence" check (task 045, S9; D9, A12).

An evidence restriction never excludes an option (ruling 23). Retrieval
already applies it, so only inherited documents and documents acquired under
an earlier plan version's restriction can fall outside it (A12). This module
reads each member document's publication country and publication year from
its snapshot metadata and marks an option **no in-scope evidence** when none
of its member documents passes the plan's restrictions. No model is called;
languages are not applied (044 C8: the search grammar has no language
filter, so nothing was narrowed by language either).

Which fields are read, and why:

- **country** — the publication country through
  :func:`~policy_atlas.api.readmodels.repository.publication_country` (the
  read the source-geography chart makes; an ISO code from OpenAlex, an
  Overton display name mapped back to its ISO code), **and** the OpenAlex
  authorship countries (``provider_fields.authorships[].countries``): the
  OpenAlex leg of retrieval filters a country group on
  ``authorships.countries`` (``search_loop.openalex_wire_params``), not on the
  publisher's country, and D9 reads "the same fields retrieval filtered on".
  Without it a journal article retrieved *under* the restriction, whose
  publisher sits elsewhere, would read as out of scope.
- **year** — ``publication_year`` else ``year``, the envelope's year grain
  (acquire maps OpenAlex ``publication_year`` and Overton ``published_on`` to
  it); the plan's ``published_after`` / ``published_before`` dates are
  compared at year granularity.

A document with no country (or no year) in its metadata is not shown to be
outside the restriction on that dimension and counts as passing it: the
check marks only what the metadata proves.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.engine import Connection

from policy_atlas.api.readmodels.repository import publication_country
from policy_atlas.core.schema import (
    finding_reference_union,
    option_membership,
    source_extraction_record,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.sourcing.country_filters import (
    ISO_3166_ALPHA2,
    OVERTON_COUNTRY_DISPLAY,
    TIER1_GROUPS,
)
from policy_atlas.options_scoping.longlist.coverage import document_key, normalise_doi
from policy_atlas.runtime.scoping_plan import ScopingPlan

#: Overton display names back to their ISO codes ("UK" → "GB").
_OVERTON_NAME_TO_ISO: dict[str, str] = {
    name.casefold(): code for code, name in OVERTON_COUNTRY_DISPLAY.items()
}


@dataclass(frozen=True)
class Restriction:
    """One evidence restriction that bites on documents.

    Attributes:
        text: The constraint's own words, as the card names it.
        countries: The country group's ISO codes, or ``None`` for no country
            dimension.
        year_after: The earliest publication year allowed, or ``None``.
        year_before: The latest publication year allowed, or ``None``.
    """

    text: str
    countries: frozenset[str] | None
    year_after: int | None
    year_before: int | None


@dataclass(frozen=True)
class _Document:
    key: str
    countries: frozenset[str]
    year: int | None


def restrictions_for(plan: ScopingPlan) -> list[Restriction]:
    """The plan's evidence restrictions with a country group or a year bound.

    A restriction with only languages is left out (not applied, 044 C8).

    Args:
        plan: The walk's scoping plan.

    Returns:
        The restrictions, in plan order; empty when the plan restricts no
        document by country or year.
    """
    out: list[Restriction] = []
    for c in plan.constraints:
        if c.kind != "evidence_restriction":
            continue
        countries: frozenset[str] | None = None
        if c.country_group is not None:
            group = c.country_group
            codes = TIER1_GROUPS.get(group.label) if group.countries is None else group.countries
            countries = frozenset(code.upper() for code in codes or ())
        after = _year_of(c.published_after)
        before = _year_of(c.published_before)
        if countries is None and after is None and before is None:
            continue
        out.append(
            Restriction(text=c.text, countries=countries, year_after=after, year_before=before)
        )
    return out


def _year_of(value: str | None) -> int | None:
    if value is None or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _to_iso(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.upper() in ISO_3166_ALPHA2:
        return text.upper()
    return _OVERTON_NAME_TO_ISO.get(text.casefold())


def document_countries(metadata: Mapping[str, Any]) -> frozenset[str]:
    """A document's countries as ISO codes: publication country and authorships.

    Args:
        metadata: The snapshot's envelope metadata.

    Returns:
        The ISO codes the metadata names; empty when it names none.
    """
    codes: set[str] = set()
    published = _to_iso(publication_country(metadata))
    if published is not None:
        codes.add(published)
    provider = metadata.get("provider_fields")
    authorships = provider.get("authorships") if isinstance(provider, Mapping) else None
    if isinstance(authorships, list):
        for entry in authorships:
            countries = entry.get("countries") if isinstance(entry, Mapping) else None
            if isinstance(countries, list):
                codes.update(code for code in map(_to_iso, countries) if code is not None)
    return frozenset(codes)


def document_year(metadata: Mapping[str, Any]) -> int | None:
    """A document's publication year, the envelope's year grain.

    Args:
        metadata: The snapshot's envelope metadata.

    Returns:
        The year, or ``None`` when the metadata carries none.
    """
    value = metadata.get("publication_year", metadata.get("year"))
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _passes_one(document: _Document, restriction: Restriction) -> bool:
    if (
        restriction.countries is not None
        and document.countries
        and not (document.countries & restriction.countries)
    ):
        return False
    if document.year is not None:
        if restriction.year_after is not None and document.year < restriction.year_after:
            return False
        if restriction.year_before is not None and document.year > restriction.year_before:
            return False
    return True


def _member_documents(
    conn: Connection, *, task_id: uuid.UUID
) -> dict[uuid.UUID, dict[str, _Document]]:
    """Every option's member documents, DOI-collapsed, with their metadata read."""
    om = option_membership
    own = (
        select(om.c.option_id, source_snapshot.c.source_snapshot_id, source_snapshot.c.metadata)
        .select_from(
            om.join(
                task_source_snapshot,
                and_(
                    task_source_snapshot.c.task_source_snapshot_id
                    == om.c.task_source_snapshot_id,
                    task_source_snapshot.c.task_id == om.c.task_id,
                ),
            ).join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(om.c.task_id == task_id, om.c.unit_kind == "interventions")
    )
    fru = finding_reference_union
    linked = (
        select(om.c.option_id, source_snapshot.c.source_snapshot_id, source_snapshot.c.metadata)
        .select_from(
            om.join(
                fru,
                and_(
                    fru.c.finding_id == om.c.unit_id,
                    fru.c.task_id == om.c.unit_task_id,
                    fru.c.kind == om.c.unit_kind,
                ),
            )
            .join(
                source_extraction_record,
                and_(
                    source_extraction_record.c.extraction_record_id == fru.c.extraction_record_id,
                    source_extraction_record.c.task_id == fru.c.task_id,
                ),
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id
                == source_extraction_record.c.source_snapshot_id,
            )
        )
        .where(om.c.task_id == task_id, om.c.unit_kind.in_(("iof", "icf")))
    )
    documents: dict[uuid.UUID, dict[str, _Document]] = {}
    # DOI twins: keep the snapshot with the most read metadata (countries,
    # then year), ties to the lowest snapshot id — never the row order.
    ranks: dict[tuple[uuid.UUID, str], tuple[int, int, str]] = {}
    for query in (own, linked):
        for row in conn.execute(query):
            metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
            key = document_key(doi=normalise_doi(metadata), document_id=row.source_snapshot_id)
            doc = _Document(
                key=key, countries=document_countries(metadata), year=document_year(metadata)
            )
            rank = (
                -int(bool(doc.countries)),
                -int(doc.year is not None),
                str(row.source_snapshot_id),
            )
            held = ranks.get((row.option_id, key))
            if held is None or rank < held:
                ranks[(row.option_id, key)] = rank
                documents.setdefault(row.option_id, {})[key] = doc
    return documents


def in_scope_evidence(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    plan: ScopingPlan,
    option_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, dict[str, Any]]:
    """The in-scope check for every option (deterministic, no model call).

    Args:
        conn: Open connection.
        task_id: The scoping task.
        plan: The walk's scoping plan.
        option_ids: The options to check.

    Returns:
        Per option ``{"restriction", "in_scope_documents", "documents",
        "no_in_scope_evidence"}``; empty when the plan has no restriction on
        country or year (nothing is marked). ``restriction`` names the
        restrictions no member document passes (all of them when each is
        passed by some document but none passes every one).
    """
    restrictions = restrictions_for(plan)
    if not restrictions:
        return {}
    by_option = _member_documents(conn, task_id=task_id)
    out: dict[uuid.UUID, dict[str, Any]] = {}
    for option_id in option_ids:
        docs = list(by_option.get(option_id, {}).values())
        passing = [d for d in docs if all(_passes_one(d, r) for r in restrictions)]
        broken = [r.text for r in restrictions if not any(_passes_one(d, r) for d in docs)]
        # An option with no documents is never marked: there is nothing to be
        # out of scope (thin evidence is shown by coverage, never flagged here).
        marked = bool(docs) and not passing
        named = broken if broken else [r.text for r in restrictions]
        out[option_id] = {
            "restriction": "; ".join(named),
            "in_scope_documents": len(passing),
            "documents": len(docs),
            "no_in_scope_evidence": marked,
        }
    return out
