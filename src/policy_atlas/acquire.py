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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.embeddings import EmbeddingBackend, StubEmbeddingBackend, embed_pending_chunks
from policy_atlas.grounding import content_hash
from policy_atlas.schema import (
    METHODOLOGICAL_STRUCTURAL,
    TOPIC_THEME,
    project_source_snapshot,
    search_coverage_record,
    source_snapshot,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.tags import has_control_character, insert_source_tags

log = structlog.get_logger()

SEGMENTATION_POLICY = "metadata_envelope_v1"
# Provider tag values are third-party (including provider-LLM) output; bound them
# like theme names so no unvalidated text shape reaches source_tag or coverage keys.
TAG_MAX_LENGTH = 200
MAX_TAGS_PER_RECORD = 50
# Bounded retention for the deep loop's backward-snowball batch (decision 16):
# referenced_works can run into the hundreds; only the leading slice is kept.
REFERENCED_WORKS_RETAIN_CAP = 60


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


class ExecutedSearchCall(Protocol):
    """Duck-typed executed search call accepted from the strategy layer."""

    @property
    def backend_name(self) -> str:
        """Backend identifier matching a configured backend."""
        ...

    @property
    def verb(self) -> str:
        """Search verb for the executed call."""
        ...

    @property
    def query(self) -> str:
        """Exact query text sent to the backend."""
        ...

    @property
    def query_origin(self) -> str:
        """Deterministic origin of the query text."""
        ...

    @property
    def wire_params(self) -> dict[str, str]:
        """Executed backend wire parameters."""
        ...

    @property
    def records(self) -> list[dict[str, Any]]:
        """Raw provider records returned by the call."""
        ...

    @property
    def status(self) -> str:
        """``"ok"`` or ``"error"``."""
        ...

    @property
    def error(self) -> str | None:
        """Redacted error text for failed calls."""
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
    "indexed_in",  # decision 20: crossref/doaj/pubmed/arxiv — cheap discipline/OA prior
    "publication_date",  # decision 20: full ISO date; envelope keeps year-grain only
)
# "referenced_works" is deliberately NOT in this tuple — decision 20 caps its
# retention (REFERENCED_WORKS_RETAIN_CAP) rather than keeping it raw/unbounded,
# so it is handled explicitly in _map_openalex_work below.

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
    "overton_policy_document_series",  # decision 20: also tagged, see _provider_tags
    "translated_title",  # decision 20: English-first title mapping input
    "title",  # decision 20: native title, retained so it survives displacement
    "pdf_document_id",  # decision 20: second half of the two-level identity
    "keyed_other_identifiers",  # decision 20: cross-reference identity beyond DOI
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
    referenced_works = record.get("referenced_works")
    if isinstance(referenced_works, list) and referenced_works:
        provider_fields["referenced_works"] = referenced_works[:REFERENCED_WORKS_RETAIN_CAP]
    return {
        "envelope": envelope,
        "abstract_source": "publisher_abstract" if abstract else "none",
        "title_source": None,  # OpenAlex has no translation seam (decision 20)
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

    English-first title mapping (contract rev 3.6a): the envelope title is
    ``translated_title`` when present, else the native ``title`` — unusable
    only when both are absent. The native title is always retained in
    ``provider_fields`` (``_OVERTON_RETAIN_KEYS``) so it survives displacement.
    """
    native_title = record.get("title") or None
    translated_title = record.get("translated_title") or None
    if translated_title:
        title, title_source = translated_title, "translated"
    elif native_title:
        title, title_source = native_title, "native"
    else:
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
        "title_source": title_source,
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


def _dedupe_tag_values(
    values: list[Any], asserted_by: str, tag_type: str = TOPIC_THEME
) -> list[tuple[str, str, str]]:
    tags: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for value in values:
        tag = _normalize_tag(value)
        if tag is None:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append((tag, asserted_by, tag_type))
    return tags


def _provider_tags(backend_name: str, record: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extract provider topical/structural assertions from a raw provider record.

    Returns ``(tag, asserted_by, tag_type)`` triples — the tag-assignment type
    is per-assertion (decision 20) so topical and methodological/structural
    provider assertions coexist under the same asserter.
    """
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
        # "keywords" is deliberately never promoted to tags (decision 20: the
        # shape probe showed wrong-sense disambiguation noise, e.g.
        # "Stock (firearms)") — retention in provider_fields stands.
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
        source_tags = record.get("source_tags")  # decision 20: publisher-curated headings
        if isinstance(source_tags, list):
            overton_values.extend(source_tags)
        tags = [
            *_dedupe_tag_values(overton_values, "overton"),
            *_dedupe_tag_values([record.get("llm_document_theme")], "overton_llm"),
        ]
        # decision 20 (rev 3.6b): the document series is methodological/
        # structural material, not a topical assertion.
        tags.extend(
            _dedupe_tag_values(
                [record.get("overton_policy_document_series")],
                "overton",
                tag_type=METHODOLOGICAL_STRUCTURAL,
            )
        )
        return tags

    return []


def acquire_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: AcquireContext,
    backends: list[SearchBackend],
    embedder: EmbeddingBackend | None = None,
    executed_calls: Sequence[ExecutedSearchCall] | None = None,
    depth: str = "rapid",
    scope_wire_params: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Acquire metadata-only sources for an evidence scope over the given backends.

    With ``executed_calls`` omitted, the legacy path makes one
    ``backend.search(context.intent)`` call per backend, in list order. With
    ``executed_calls`` supplied, this function performs no search egress; it
    consumes those call records in order and reuses the existing mapping,
    deduplication, event, coverage, tag, and embedding machinery.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        project_id: Owning project.
        run_id: The run recorded on project links and the coverage record.
        context: Scope-level input; ``context.intent`` is the query, verbatim.
        backends: Configured backends, searched in list order (dedup outcomes
            are deterministic because the order is fixed).
        embedder: Optional embedding backend. Defaults to the deterministic stub.
        executed_calls: Optional pre-executed call stream from the search
            strategy layer. When supplied, no backend ``search`` method is
            called here.
        depth: Search-depth directive recorded in events and coverage.
        scope_wire_params: Per-backend executed wire params recorded on the
            coverage record.

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
    backend_by_name = {backend.name: backend for backend in backends}
    if executed_calls is not None:
        unknown_call_backends = [
            call.backend_name
            for call in executed_calls
            if call.backend_name not in backend_by_name
        ]
        if unknown_call_backends:
            raise ValueError(
                f"executed call references unknown backend(s): {unknown_call_backends}"
            )

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
    by_backend: dict[str, dict[str, Any]] = {
        backend.name: {
            "status": "ok",
            "error": None,
            "results_returned": 0,
            "acquired": 0,
            "already_acquired": 0,
            "skipped_unusable": 0,
            "tags_materialised": 0,
        }
        for backend in backends
    }
    ok_calls_by_backend = dict.fromkeys(names, 0)
    errors_by_backend: dict[str, list[str]] = {name: [] for name in names}
    tag_assertions: list[tuple[uuid.UUID, str, str, str]] = []

    def process_records(
        *,
        backend_name: str,
        records: list[dict[str, Any]],
        counts: dict[str, Any],
    ) -> None:
        counts["results_returned"] += len(records)
        mapper = _MAPPERS[backend_name]  # validated upfront

        for record in records:
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
                        # title_source follows abstract_source's None-omission
                        # pattern: OpenAlex has no translation seam, so it maps
                        # to None and is left out of persisted metadata.
                        **(
                            {"title_source": mapped["title_source"]}
                            if mapped["title_source"] is not None
                            else {}
                        ),
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
            tag_pairs = _provider_tags(backend_name, record)
            if len(tag_pairs) > MAX_TAGS_PER_RECORD:
                log.warning(
                    "acquire.tags_truncated",
                    backend=backend_name,
                    backend_record_id=record_id,
                    tag_count=len(tag_pairs),
                    cap=MAX_TAGS_PER_RECORD,
                )
                tag_pairs = tag_pairs[:MAX_TAGS_PER_RECORD]
            tag_assertions.extend(
                (pss_id, tag, asserted_by, tag_type) for tag, asserted_by, tag_type in tag_pairs
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
                    "backend": backend_name,
                    "backend_record_id": record_id,
                },
            )

            counts["acquired"] += 1
            seen_hashes.add(chash)
            if record_id:
                seen_record_ids.add(record_id)
            if doi:
                seen_dois.add(doi)

    if executed_calls is None:
        for backend in backends:
            counts = by_backend[backend.name]
            try:
                results = backend.search(context.intent)
                ok_calls_by_backend[backend.name] += 1
                status, error = "ok", None
            except Exception as exc:
                # Per-backend error isolation: this part of the search space
                # wasn't searched, but the other backends and the run continue.
                results = []
                status, error = "error", str(exc)
                errors_by_backend[backend.name].append(error)
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
                    "depth": depth,
                    "filters": {},
                    "status": status,
                    "result_count": len(results),
                    "error": error,
                    "evidence_scope_id": str(context.scope_id),
                },
            )
            if status == "ok":
                process_records(
                    backend_name=backend.name,
                    records=results,
                    counts=counts,
                )
    else:
        for call in executed_calls:
            backend = backend_by_name[call.backend_name]
            counts = by_backend[backend.name]
            if call.status not in {"ok", "error"}:
                raise ValueError(f"executed call has invalid status: {call.status!r}")
            result_count = len(call.records) if call.status == "ok" else 0
            error = call.error if call.status == "error" else None
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="search.executed",
                payload={
                    "backend": backend.name,
                    "trust_class": backend.trust_class,
                    "mode": backend.mode,
                    "query": call.query,
                    "query_origin": call.query_origin,
                    "verb": call.verb,
                    "depth": depth,
                    "filters": call.wire_params,
                    "status": call.status,
                    "result_count": result_count,
                    "error": error,
                    "evidence_scope_id": str(context.scope_id),
                },
            )
            if call.status == "ok":
                ok_calls_by_backend[backend.name] += 1
                process_records(
                    backend_name=backend.name,
                    records=call.records,
                    counts=counts,
                )
            else:
                errors_by_backend[backend.name].append(error or "unknown search error")
                log.warning(
                    "acquire.backend_failed",
                    backend=backend.name,
                    project_id=str(project_id),
                    run_id=str(run_id),
                    error=error,
                )

    any_error = False
    for backend in backends:
        errors = errors_by_backend[backend.name]
        if errors:
            by_backend[backend.name]["error"] = "; ".join(errors)
        if errors and ok_calls_by_backend[backend.name] == 0:
            by_backend[backend.name]["status"] = "error"
            any_error = True

    # Bulk insert per tag_type (insert_source_tags takes one tag_type per call)
    # instead of one statement per record; tag_types are sorted so call order
    # is deterministic across runs.
    assertions_by_type: dict[str, list[tuple[uuid.UUID, str, str]]] = {}
    for pss_id, tag, asserted_by, tag_type in tag_assertions:
        assertions_by_type.setdefault(tag_type, []).append((pss_id, tag, asserted_by))
    for tag_type in sorted(assertions_by_type):
        insert_source_tags(
            conn,
            project_id=project_id,
            run_id=run_id,
            now=now,
            assertions=assertions_by_type[tag_type],
            tag_type=tag_type,
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
                {
                    "backend": b.name,
                    "trust_class": b.trust_class,
                    "mode": b.mode,
                    "depth": depth,
                }
                for b in backends
            ],
            scope_filters=scope_wire_params or {},
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
