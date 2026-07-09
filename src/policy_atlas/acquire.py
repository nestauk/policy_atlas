"""Acquire component — metadata-only acquisition through the ``search`` seam.

``SearchBackend`` is the seam (protocol, like ``InferenceProvider``); the v3.0
implementations replay committed sanitized fixtures derived from dev-time-recorded
real OpenAlex and Overton responses — authentic structure, fabricated values,
zero runtime egress. Live HTTP backends live in ``search_live.py`` behind the
same protocol, so this module stays fixture-default and HTTP-import-free.

Each accepted result is snapshotted on the text in hand (title + best available
summary), joined to the project with ``origin="acquired"``. Every search call
emits a ``search.executed`` governance event; every acquire run writes one
``search_coverage_record`` row.
"""

import functools
import importlib.resources
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.embeddings import EmbeddingBackend, StubEmbeddingBackend, embed_pending_chunks
from policy_atlas.grounding import content_hash
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import (
    project_source_snapshot,
    search_coverage_record,
    source_snapshot,
)
from policy_atlas.tags import has_control_character, insert_source_tags

log = structlog.get_logger()

SEGMENTATION_POLICY = "metadata_envelope_v1"
# Provider tag values are third-party (including provider-LLM) output; bound them
# like theme names so no unvalidated text shape reaches source_tag or coverage keys.
TAG_MAX_LENGTH = 200
MAX_TAGS_PER_RECORD = 50


@dataclass
class AcquireContext:
    """Scope-level input to an acquire run.

    Attributes:
        scope_id: The evidence scope whose intent drives the search.
        intent: The scope's research intent — the v3.0 query, verbatim.
        context: The scope's context JSONB.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class BackendCaps:
    """Capability flags declared by a search backend.

    Attributes:
        has_snowball: Whether citation/reference expansion verbs are available.
        has_title_lookup: Whether exact-title lookup is available.
    """

    has_snowball: bool
    has_title_lookup: bool


class SearchBackend(Protocol):
    """The ``search`` seam: one configured backend with a declared trust class.

    Attributes:
        name: Backend identifier (e.g. ``"openalex"``).
        trust_class: Declared trust class (e.g. ``"academic_aggregator"``).
        mode: ``"fixture"`` or ``"live"`` — carried into events + coverage record.
        caps: Backend capability flags for deeper search loops.
    """

    name: str
    trust_class: str
    mode: str
    caps: BackendCaps

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw provider records for the query."""
        ...

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return records citing the given provider record."""
        ...

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return provider records for referenced provider IDs."""
        ...

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return provider records matching a title query."""
        ...


def _limit_fixture_records(
    records: list[dict[str, Any]], max_results: int | None
) -> list[dict[str, Any]]:
    if max_results is None:
        return records
    if max_results <= 0:
        return []
    return records[:max_results]


@functools.cache  # fixture files are immutable for the process lifetime
def _load_fixture(filename: str) -> list[dict[str, Any]]:
    data = json.loads(
        importlib.resources.files("policy_atlas").joinpath("data", filename).read_text()
    )
    records: list[dict[str, Any]] = data["records"]
    return records


class OpenAlexFixtureBackend:
    """Replays committed, dev-time-recorded OpenAlex responses. Zero egress."""

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "fixture"
    caps = BackendCaps(has_snowball=True, has_title_lookup=True)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the sanitized fixture Work records (query is not interpreted)."""
        return _limit_fixture_records(_load_fixture("openalex_works.json"), max_results)

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return a deterministic small citation slice from the fixture page."""
        return _limit_fixture_records(_load_fixture("openalex_works.json")[:3], max_results)

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return a deterministic small reference slice from the fixture page."""
        return _limit_fixture_records(_load_fixture("openalex_works.json")[:3], max_results)

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return fixture records whose titles contain the query string."""
        needle = title.casefold().strip()
        if not needle:
            return []
        return [
            record
            for record in _load_fixture("openalex_works.json")
            if needle in str(record.get("display_name", "")).casefold()
        ]


class OvertonFixtureBackend:
    """Replays committed, dev-time-recorded Overton responses. Zero egress."""

    name = "overton"
    trust_class = "grey_literature_aggregator"
    mode = "fixture"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the sanitized fixture policy-document records (query is not interpreted)."""
        return _limit_fixture_records(_load_fixture("overton_documents.json"), max_results)

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_snowball=False")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_snowball=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no title-lookup capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_title_lookup=False")


# --- Mapping layer (private): raw provider record -> normalized envelope + chunk ---


def _reconstruct_abstract(index: dict[str, list[int]] | None) -> str | None:
    """Rebuild plain text from an OpenAlex ``abstract_inverted_index``.

    OpenAlex ships no plain abstract — tokens map to their positions; the
    position-ordered join is the abstract. Empty/missing index -> None.
    """
    if not index:
        return None
    positions: dict[int, str] = {}
    for token, token_positions in index.items():
        for pos in token_positions:
            positions[pos] = token
    return " ".join(positions[p] for p in sorted(positions)) or None


def _normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI to lowercase bare form (cross-backend identity key)."""
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if d.startswith(prefix):
            d = d[len(prefix):]
            break
    return d or None


def _slim_authorships(authorships: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Names + institution names + countries only — the retained slice of authorships."""
    return [
        {
            "author_name": (a.get("author") or {}).get("display_name"),
            "institutions": [
                i.get("display_name") for i in (a.get("institutions") or [])
            ],
            "countries": a.get("countries") or [],
        }
        for a in (authorships or [])
    ]


_OPENALEX_RETAIN_KEYS = (
    "primary_location",  # URL/OA block — required by slice 008
    "best_oa_location",
    "open_access",
    "topics",
    "primary_topic",
    "keywords",
    "cited_by_count",
    "fwci",
    "is_retracted",
    "is_paratext",
    "ids",
    "language",
    "sustainable_development_goals",
)

_OVERTON_RETAIN_KEYS = (
    "document_url",  # slice 008; multi-PDF documents are real
    "pdf_url",
    "grouped_pdf_ids_in_result",
    "source",  # geography + publisher typing for characterise
    "topics",
    "classifications",
    "sdgcategories",
    "cofog_divisions",
    "cites",  # snowball-seam signal
    "citation_count",
    "citation_count_including_self",
    "es_score",  # provider relevance
    "published_on",
    "added_on",
    "languages",
    "authors_are_organizations",
    # LLM-generated, like llm_document_description — retained but always
    # identifiable as machine text, never mixed into document-own-words fields
    "llm_document_theme",
)


def _map_openalex_work(record: dict[str, Any]) -> dict[str, Any] | None:
    """OpenAlex Work -> normalized envelope + chunk; None when unusable.

    Unusable = no title (nothing screenable) or no ``id`` (no locator, no
    re-run identity — and ``source_locator`` is NOT NULL).
    """
    title = record.get("display_name")
    if not title or not record.get("id"):
        return None
    abstract = _reconstruct_abstract(record.get("abstract_inverted_index"))
    source = (record.get("primary_location") or {}).get("source") or {}
    envelope = {
        "title": title,
        "abstract": abstract,
        "year": record.get("publication_year"),
        "doi": _normalize_doi(record.get("doi")),
        "language": record.get("language"),
        "backend": "openalex",
        "backend_record_id": record.get("id"),
        "record_type": record.get("type"),
        "publisher_org": source.get("display_name"),
    }
    provider_fields = {k: record.get(k) for k in _OPENALEX_RETAIN_KEYS if k in record}
    provider_fields["authorships"] = _slim_authorships(record.get("authorships"))
    return {
        "envelope": envelope,
        "abstract_source": "publisher_abstract" if abstract else "none",
        "source_locator": record.get("id"),  # the work's canonical id URL
        "provider_fields": provider_fields,
    }


def _first_or_none(value: Any) -> Any:
    """First element of a non-empty list, else None (Overton list-or-absent shapes)."""
    if isinstance(value, list) and value:
        return value[0]
    return None


def _map_overton_document(record: dict[str, Any]) -> dict[str, Any] | None:
    """Overton policy document -> normalized envelope + chunk; None when unusable.

    Overton expresses absence as empty strings/lists on always-present keys —
    empty-string/empty-list is treated as absent throughout.
    """
    title = record.get("title") or record.get("translated_title")
    if not title:
        return None

    # Overton ships no real abstract: snippet (document excerpt) falls back to
    # llm_document_description (LLM-generated — its use must always be visible).
    snippet = record.get("snippet") or None
    llm_description = record.get("llm_document_description") or None
    if snippet:
        abstract, abstract_source = snippet, "snippet"
    elif llm_description:
        abstract, abstract_source = llm_description, "llm_description"
    else:
        abstract, abstract_source = None, "none"

    published_on = record.get("published_on") or ""
    year = int(published_on[:4]) if published_on[:4].isdigit() else None

    source_locator = record.get("document_url") or record.get("overton_url")
    if not source_locator:
        # no address at all: the identity triple can't be completed and
        # source_locator is NOT NULL — unusable, counted, never a crashed run
        return None

    koi = record.get("keyed_other_identifiers")
    doi = _normalize_doi(_first_or_none(koi.get("doi")) if isinstance(koi, dict) else None)

    source = record.get("source") or {}
    envelope = {
        "title": title,
        "abstract": abstract,
        "year": year,
        "doi": doi,
        "language": _first_or_none(record.get("languages")) or None,
        "backend": "overton",
        "backend_record_id": record.get("policy_document_id"),
        "record_type": source.get("type") or None,
        "publisher_org": source.get("title") or None,
    }
    provider_fields = {k: record.get(k) for k in _OVERTON_RETAIN_KEYS if k in record}
    return {
        "envelope": envelope,
        "abstract_source": abstract_source,
        "source_locator": source_locator,
        "provider_fields": provider_fields,
    }


_MAPPERS = {
    "openalex": _map_openalex_work,
    "overton": _map_overton_document,
}


def _chunk_text(envelope: dict[str, Any]) -> str:
    """The text in hand: title + best available summary."""
    title: str = envelope["title"]
    abstract = envelope.get("abstract")
    return f"{title}\n\n{abstract}" if abstract else title


def _normalize_tag(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    tag = " ".join(value.strip().split())
    if not tag or len(tag) > TAG_MAX_LENGTH or has_control_character(tag):
        return None
    return tag


def _dedupe_tag_values(values: list[Any], asserted_by: str) -> list[tuple[str, str]]:
    tags: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        tag = _normalize_tag(value)
        if tag is None:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append((tag, asserted_by))
    return tags


def _provider_tags(backend_name: str, record: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract provider topical assertions from a raw provider record."""
    if backend_name == "openalex":
        values: list[Any] = []
        primary_topic = record.get("primary_topic")
        if isinstance(primary_topic, dict):
            values.append(primary_topic.get("display_name"))
        topics = record.get("topics")
        if isinstance(topics, list):
            values.extend(
                topic.get("display_name") for topic in topics if isinstance(topic, dict)
            )
        sdgs = record.get("sustainable_development_goals")
        if isinstance(sdgs, list):
            values.extend(sdg.get("display_name") for sdg in sdgs if isinstance(sdg, dict))
        return _dedupe_tag_values(values, "openalex")

    if backend_name == "overton":
        overton_values: list[Any] = []
        topics = record.get("topics")
        if isinstance(topics, str):
            overton_values.append(topics)
        elif isinstance(topics, list):
            overton_values.extend(topics)
        classifications = record.get("classifications")
        if isinstance(classifications, list):
            for classification in classifications:
                if isinstance(classification, dict):
                    overton_values.append(classification.get("name"))
                else:
                    overton_values.append(classification)
        sdgcategories = record.get("sdgcategories")
        if isinstance(sdgcategories, list):
            overton_values.extend(sdgcategories)
        return [
            *_dedupe_tag_values(overton_values, "overton"),
            *_dedupe_tag_values([record.get("llm_document_theme")], "overton_llm"),
        ]

    return []


def acquire_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: AcquireContext,
    backends: list[SearchBackend],
    embedder: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """Acquire metadata-only sources for an evidence scope over the given backends.

    One search call per backend, in list order, error-isolated: a raising
    backend contributes zero results and never aborts the other backends or the
    run. Each attempted call emits a ``search.executed`` event; each newly
    acquired snapshot emits ``source.acquired``; the run always writes one
    ``search_coverage_record`` (fail-closed adequacy verdict).

    Args:
        conn: Open database connection; all writes occur within its transaction.
        project_id: Owning project.
        run_id: The run recorded on project links and the coverage record.
        context: Scope-level input; ``context.intent`` is the query, verbatim.
        backends: Configured backends, searched in list order (dedup outcomes
            are deterministic because the order is fixed).
        embedder: Optional embedding backend. Defaults to the deterministic stub.

    Returns:
        Counts dict: ``acquired``, ``already_acquired``, ``skipped_unusable``,
        ``results_returned`` (invariant: the first three sum to it, per backend
        and in total), ``by_backend`` (with per-backend ``status``/``error``),
        ``tags_materialised``, ``embed``, ``stop_condition``,
        ``adequacy_verdict``, ``coverage_record_id``.
    """
    # A backend without a registered mapping (or a duplicate name, which would
    # corrupt by_backend) is a wiring error, not a search failure — fail loud
    # before any work; the harness reports it as component.failed.
    names = [b.name for b in backends]
    unknown = [n for n in names if n not in _MAPPERS]
    if unknown:
        raise ValueError(f"no mapper registered for backend(s): {unknown}")
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate backend names: {names}")

    # Preload the project's existing identity keys — dedup is then in-memory,
    # and also catches duplicates within this call's own result stream.
    # ponytail: JSONB ->> scan over all project snapshots; fine at v3.0 corpus
    # sizes, add expression indexes if acquire volume ever makes this slow.
    seen_record_ids: set[str] = set()
    seen_dois: set[str] = set()
    seen_hashes: set[str] = set()
    for meta, chash in conn.execute(
        select(source_snapshot.c.metadata, source_snapshot.c.content_hash)
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
    ):
        seen_hashes.add(chash)
        if meta.get("backend_record_id"):
            seen_record_ids.add(meta["backend_record_id"])
        # normalize on read: uploaded snapshots may carry a prefixed/mixed-case
        # DOI in their free-form metadata; acquire-written envelopes are already
        # normalized, but the guard must hold across origins
        doi = _normalize_doi(meta.get("doi"))
        if doi:
            seen_dois.add(doi)

    now = datetime.now(UTC)
    by_backend: dict[str, dict[str, Any]] = {}
    any_error = False
    tag_assertions: list[tuple[uuid.UUID, str, str]] = []

    for backend in backends:
        status, error = "ok", None
        try:
            results = backend.search(context.intent)
        except Exception as exc:
            # Per-backend error isolation: this part of the search space wasn't
            # searched, but the other backends and the run continue.
            results = []
            status, error = "error", str(exc)
            any_error = True
            log.warning(
                "acquire.backend_failed",
                backend=backend.name,
                project_id=str(project_id),
                run_id=str(run_id),
                error=error,
            )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="search.executed",
            payload={
                "backend": backend.name,
                "trust_class": backend.trust_class,
                "mode": backend.mode,
                "query": context.intent,
                "filters": {},
                "status": status,
                "result_count": len(results),
                "error": error,
                "evidence_scope_id": str(context.scope_id),
            },
        )

        counts: dict[str, Any] = {
            "status": status,
            "error": error,
            "results_returned": len(results),
            "acquired": 0,
            "already_acquired": 0,
            "skipped_unusable": 0,
            "tags_materialised": 0,
        }
        mapper = _MAPPERS[backend.name]  # validated upfront

        for record in results:
            mapped = mapper(record)
            if mapped is None:
                # A snapshot needs at least a title to be screenable —
                # skip is visible, never silent.
                counts["skipped_unusable"] += 1
                continue

            envelope = mapped["envelope"]
            text = _chunk_text(envelope)
            chash = content_hash(text)
            record_id = envelope["backend_record_id"]
            doi = envelope["doi"]

            # Three identity guards, project-scoped: exact re-run, cross-backend
            # DOI identity, exact text duplicate.
            if (
                (record_id and record_id in seen_record_ids)
                or (doi and doi in seen_dois)
                or chash in seen_hashes
            ):
                counts["already_acquired"] += 1
                continue

            snapshot_id = uuid.uuid4()
            pss_id = uuid.uuid4()
            conn.execute(
                source_snapshot.insert().values(
                    source_snapshot_id=snapshot_id,
                    content_hash=chash,
                    text_basis="abstract_only",  # metadata envelope in hand, not full text
                    source_locator=mapped["source_locator"],
                    # None-valued envelope keys are persisted as *absent* —
                    # authentic absence (contract decision 4), and exactly what
                    # _stub_screen's fail-open default expects (missing abstract
                    # -> title_only, no screen changes).
                    metadata={
                        **{k: v for k, v in envelope.items() if v is not None},
                        "abstract_source": mapped["abstract_source"],
                        "provider_fields": mapped["provider_fields"],
                    },
                    created_at=now,
                )
            )
            conn.execute(
                chunk_table.insert().values(
                    chunk_id=uuid.uuid4(),
                    source_snapshot_id=snapshot_id,
                    sequence=1,
                    content=text,
                    content_hash=chash,
                    locator={"sequence": 1},
                    segmentation_policy=SEGMENTATION_POLICY,
                    created_at=now,
                )
            )
            conn.execute(
                project_source_snapshot.insert().values(
                    project_source_snapshot_id=pss_id,
                    project_id=project_id,
                    source_snapshot_id=snapshot_id,
                    origin="acquired",
                    run_id=run_id,
                    ingested_at=now,
                )
            )
            tag_pairs = _provider_tags(backend.name, record)
            if len(tag_pairs) > MAX_TAGS_PER_RECORD:
                log.warning(
                    "acquire.tags_truncated",
                    backend=backend.name,
                    backend_record_id=record_id,
                    tag_count=len(tag_pairs),
                    cap=MAX_TAGS_PER_RECORD,
                )
                tag_pairs = tag_pairs[:MAX_TAGS_PER_RECORD]
            tag_assertions.extend(
                (pss_id, tag, asserted_by) for tag, asserted_by in tag_pairs
            )
            counts["tags_materialised"] += len(tag_pairs)
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="source.acquired",
                payload={
                    "source_snapshot_id": str(snapshot_id),
                    "project_source_snapshot_id": str(pss_id),
                    "evidence_scope_id": str(context.scope_id),
                    "backend": backend.name,
                    "backend_record_id": record_id,
                },
            )

            counts["acquired"] += 1
            seen_hashes.add(chash)
            if record_id:
                seen_record_ids.add(record_id)
            if doi:
                seen_dois.add(doi)

        by_backend[backend.name] = counts

    # One bulk insert for the whole run instead of one statement per record.
    insert_source_tags(
        conn, project_id=project_id, run_id=run_id, now=now, assertions=tag_assertions
    )

    totals = {
        key: sum(b[key] for b in by_backend.values())
        for key in (
            "acquired",
            "already_acquired",
            "skipped_unusable",
            "results_returned",
            "tags_materialised",
        )
    }

    # Fail-closed adequacy (decision 8): any backend error -> inadequate (that
    # part of the search space wasn't searched); zero usable records across the
    # run -> inadequate (nothing screenable came back). An empty-but-successful
    # backend beside a productive one is honest coverage, not inadequacy.
    stop_condition = "error" if any_error else "breadth_truncated"
    usable = totals["acquired"] + totals["already_acquired"]
    adequacy_verdict = "inadequate" if (any_error or usable == 0) else "adequate"

    coverage_record_id = uuid.uuid4()
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=coverage_record_id,
            evidence_scope_id=context.scope_id,
            project_id=project_id,
            acquired_by_run_id=run_id,
            backends=[
                {"backend": b.name, "trust_class": b.trust_class, "mode": b.mode}
                for b in backends
            ],
            scope_filters={},
            stop_condition=stop_condition,
            adequacy_verdict=adequacy_verdict,
            verdict_origin="model",
            created_at=now,
        )
    )

    if embedder is None:
        embedder = StubEmbeddingBackend()
    embed_counts = embed_pending_chunks(
        conn,
        embedder=embedder,
        project_id=project_id,
        run_id=run_id,
    )

    return {
        **totals,
        "by_backend": by_backend,
        "embed": embed_counts,
        "stop_condition": stop_condition,
        "adequacy_verdict": adequacy_verdict,
        "coverage_record_id": str(coverage_record_id),
    }
