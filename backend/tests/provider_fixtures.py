"""Zero-egress provider fixture backends — test/demo doubles of the search seam.

Replays committed, sanitized OpenAlex/Overton records (recorded by
``scripts/record_*_fixtures.py`` into ``tests/data/provider_records/``). Moved out
of the shipped package in task 023 (owner rider): production resolves search
backends by injection; the no-key stub run uses empty search backends and the
seeded stub corpus.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

from policy_atlas.evidence_search.sourcing.acquire import BackendCaps, _normalize_doi

_DATA_DIR = Path(__file__).resolve().parent / "data" / "provider_records"


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
    data = json.loads((_DATA_DIR / filename).read_text())
    records: list[dict[str, Any]] = data["records"]
    return records


class OpenAlexFixtureBackend:
    """Replays committed, dev-time-recorded OpenAlex responses. Zero egress."""

    name = "openalex"
    trust_class = "academic_aggregator"
    mode = "fixture"
    caps = BackendCaps(
        has_snowball=True,
        has_title_lookup=True,
        has_doi_lookup=True,
        has_semantic=True,
        has_id_lookup=True,
        has_forward=True,
    )

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the sanitized fixture Work records (query is not interpreted).

        Args:
            query: Ignored; fixture replay is query-independent.
            wire_params: Ignored; accepted for protocol parity with live backends.
            max_results: Optional result cap applied to the fixture page.
        """
        return _limit_fixture_records(_load_fixture("openalex_works.json"), max_results)

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return a deterministic small citation slice from the fixture page.

        Args:
            record_id: Ignored; fixture replay is record-independent.
            max_results: Optional result cap applied to the citation slice.
        """
        return _limit_fixture_records(_load_fixture("openalex_works.json")[:3], max_results)

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return a deterministic small reference slice from the fixture page.

        Args:
            record_ids: Ignored; fixture replay is record-independent.
            max_results: Optional result cap applied to the reference slice.
        """
        return _limit_fixture_records(_load_fixture("openalex_works.json")[:3], max_results)

    def search_semantic(
        self,
        text: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return fixture Works in reverse order for semantic searches."""
        return _limit_fixture_records(
            list(reversed(_load_fixture("openalex_works.json"))), max_results
        )

    def lookup_ids(
        self, ids: list[str], *, wire_params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Return fixture Works whose short IDs were requested."""
        wanted = {record_id.rsplit("/", 1)[-1] for record_id in ids}
        return [
            record
            for record in _load_fixture("openalex_works.json")
            if str(record.get("id", "")).rsplit("/", 1)[-1] in wanted
        ]

    def fetch_citing(
        self,
        ids: list[str],
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Return one deterministic fixture forward-citation page."""
        if page > 1:
            return []
        return _limit_fixture_records(_load_fixture("openalex_works.json")[3:9], max_results)

    def fetch_by_id(self, record_id: str) -> dict[str, Any] | None:
        """Raise because OpenAlex fixture exposes no policy-document fetch capability."""
        raise NotImplementedError("OpenAlexFixtureBackend caps.has_fetch_by_id=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Return fixture records whose titles contain the query string.

        Args:
            title: Title text matched (casefolded) against fixture record titles.
        """
        needle = title.casefold().strip()
        if not needle:
            return []
        return [
            record
            for record in _load_fixture("openalex_works.json")
            if needle in str(record.get("display_name", "")).casefold()
        ]

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Return fixture records whose normalized DOI matches a requested DOI.

        Args:
            dois: DOI identifiers to match, normalized before comparison.
            max_results: Optional result cap applied to the matched records.
        """
        wanted = {_normalize_doi(doi) for doi in dois}
        wanted.discard(None)
        records = [
            record
            for record in _load_fixture("openalex_works.json")
            if _normalize_doi(record.get("doi")) in wanted
        ]
        return _limit_fixture_records(records, max_results)


class OvertonFixtureBackend:
    """Replays committed, dev-time-recorded Overton responses. Zero egress."""

    name = "overton"
    trust_class = "grey_literature_aggregator"
    mode = "fixture"
    caps = BackendCaps(has_snowball=False, has_title_lookup=False, has_fetch_by_id=True)

    def search(
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return the sanitized fixture policy-document records (query is not interpreted).

        Args:
            query: Ignored; fixture replay is query-independent.
            wire_params: Ignored; accepted for protocol parity with live backends.
            max_results: Optional result cap applied to the fixture page.
        """
        return _limit_fixture_records(_load_fixture("overton_documents.json"), max_results)

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability.

        Args:
            record_id: Ignored; the call always raises.
            max_results: Ignored; the call always raises.

        Raises:
            NotImplementedError: Always — ``caps.has_snowball`` is False.
        """
        raise NotImplementedError("OvertonFixtureBackend caps.has_snowball=False")

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no snowball capability.

        Args:
            record_ids: Ignored; the call always raises.
            max_results: Ignored; the call always raises.

        Raises:
            NotImplementedError: Always — ``caps.has_snowball`` is False.
        """
        raise NotImplementedError("OvertonFixtureBackend caps.has_snowball=False")

    def fetch_by_id(self, record_id: str) -> dict[str, Any] | None:
        """Return the fixture policy document matching its exact identifier."""
        return next(
            (
                record
                for record in _load_fixture("overton_documents.json")
                if record.get("policy_document_id") == record_id
            ),
            None,
        )

    def search_semantic(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Raise because Overton exposes no OpenAlex semantic capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_semantic=False")

    def lookup_ids(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Raise because Overton exposes no OpenAlex ID-lookup capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_id_lookup=False")

    def fetch_citing(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Raise because Overton exposes no OpenAlex forward capability."""
        raise NotImplementedError("OvertonFixtureBackend caps.has_forward=False")

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no title-lookup capability.

        Args:
            title: Ignored; the call always raises.

        Raises:
            NotImplementedError: Always — ``caps.has_title_lookup`` is False.
        """
        raise NotImplementedError("OvertonFixtureBackend caps.has_title_lookup=False")

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Raise because Overton v1 declares no DOI-lookup capability.

        Args:
            dois: Ignored; the call always raises.
            max_results: Ignored; the call always raises.

        Raises:
            NotImplementedError: Always — ``caps.has_doi_lookup`` is False.
        """
        raise NotImplementedError("OvertonFixtureBackend caps.has_doi_lookup=False")


# --- Mapping layer (private): raw provider record -> normalized envelope + chunk ---
