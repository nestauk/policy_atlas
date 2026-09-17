"""Run one research intent through the real search stage (and optionally
screening) and score it against a review's reference list.

This is the engine ``sweep_record_cap.py`` drives; it has no command line of
its own. ``run_one_query`` seeds a throwaway task/run/scope, runs the
pipeline's own ``run_search`` and ``screen_sources`` inside the caller's
transaction (which the caller rolls back, so nothing is ever committed), and
returns a ``QueryResult`` with stage-attributed recall plus everything needed
to unpick the run offline (see ``inspect_run.py``).

Precision is not scored: a screened-in paper absent from one review's
bibliography is not proven irrelevant (the review had its own scope and time
cutoff), so bibliography membership is not a valid false-positive signal.

Two separate caps bound how many candidates a run collects, and confusing them
wastes a lot of time:

* ``result_cap_per_backend`` — records requested per HTTP call. With the depth's
  ``call_budget`` (number of calls allowed), this bounds what a backend can be
  *asked* for.
* ``record_cap_per_backend`` — candidates acquire *keeps* per backend, applied
  after dedup, before persisting. This is the ``acquire.capped`` log line, and
  normally the tighter of the two: records past it were fetched and paid for,
  then discarded. This is the cap that sets the recall ceiling.

Both live in ``search_loop.DEPTH_CONSTANTS``; the sweep overrides them in this
process only.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection

from ground_truth import GroundTruth, record_key

from policy_atlas.core import tracing
from policy_atlas.core.schema import evidence_scope, task, task_source_snapshot, runs, source_snapshot
from policy_atlas.evidence_search.assess.screen import ScreenContext, effective_screen_rows, screen_sources
from policy_atlas.evidence_search.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext
from policy_atlas.evidence_search.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_live import live_search_backends
from policy_atlas.evidence_search.sourcing.search_loop import run_search

# The two query-generation methodologies this eval compares, named by how
# they prompt:
#
# * ``shared`` — one prompt writes both the OpenAlex keyword queries and the
#   Overton paraphrases.
# * ``per-provider`` — one prompt per provider, each called once per query.
#
# Each class lists the committed prompt file(s) it reads in ``prompt_files``,
# so picking an arm is the whole choice — there is nothing to swap at runtime,
# and the sweep records the files' names and hash on every trace.
GENERATION_BACKENDS = {
    "shared": OpenAISearchGenerationBackend,
    "per-provider": V2SearchGenerationBackend,
}


def _seed_task_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id, created_at=now, name="eval-pilot", status="active", updated_at=now
        )
    )
    run_id = uuid.uuid4()
    conn.execute(runs.insert().values(run_id=run_id, task_id=task_id, status="running", started_at=now))
    return task_id, run_id


def _seed_scope(conn: Connection, task_id: uuid.UUID, intent: str) -> uuid.UUID:
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent=intent,
            context={},
            created_at=datetime.now(UTC),
        )
    )
    return scope_id


def _search_candidate_docs(conn: Connection, task_id: uuid.UUID) -> list[dict[str, Any]]:
    """Metadata for every candidate that reached the database — i.e. what
    survived acquire's dedup and cap, not everything the APIs returned."""
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(task_source_snapshot, task_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _keys_of(docs: list[dict[str, Any]]) -> set[str]:
    """Scoring keys for a set of documents: DOI where there is one, else the
    Overton document id (see ``ground_truth.record_key``). Documents with
    neither cannot be matched against the ground truth and are dropped."""
    return {key for d in docs if (key := record_key(d))}


def _screened_relevant_docs(conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID) -> list[dict[str, Any]]:
    """Mirrors ``classify._load_relevant_docs``'s join shape over the effective screen rows."""
    effective = effective_screen_rows()
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(
            effective,
            (effective.c.task_source_snapshot_id == task_source_snapshot.c.task_source_snapshot_id)
            & (effective.c.task_id == task_source_snapshot.c.task_id),
        )
        .join(source_snapshot, task_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _recall(found: set[str], target: set[str]) -> float:
    if not target:
        return 0.0
    return len(found & target) / len(target)


class _RecordingBackend:
    """Wraps one live ``SearchBackend`` to record every generated query/call and
    its raw returned provider records, for offline diagnosis (e.g. in a
    notebook) of why recall came out low. Pure passthrough otherwise — proxies
    the exact seam ``search_loop.py`` calls on a backend (``acquire.SearchBackend``:
    ``name``/``trust_class``/``mode``/``caps`` plus the 5 fetch/search/lookup
    methods), so it's transparent to the pipeline.
    """

    def __init__(
        self, inner: Any, calls: list[dict[str, Any]], langfuse_client: Langfuse | None = None
    ) -> None:
        self._inner = inner
        self._calls = calls
        self._langfuse_client = langfuse_client

    @property
    def name(self) -> str:
        return self._inner.name  # type: ignore[no-any-return]

    @property
    def trust_class(self) -> str:
        return self._inner.trust_class  # type: ignore[no-any-return]

    @property
    def mode(self) -> str:
        return self._inner.mode  # type: ignore[no-any-return]

    @property
    def caps(self) -> Any:
        return self._inner.caps

    def _record(
        self,
        method: str,
        query: str,
        wire_params: dict[str, str] | None,
        call: Callable[[], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Run one backend call and record it, whether it succeeds or fails.

        A failed call is recorded with zero records and the error text, then
        re-raised so the pipeline behaves exactly as it would without this
        wrapper (``search_loop`` catches it and marks the call errored). Without
        this, a query that 500ed was invisible: it never reached the recorded
        call list, so the queries CSV silently omitted it and the run looked
        like it had simply found less.

        With tracing on, each call is also one Langfuse span (``openalex:search``,
        ``overton:search`` ...) carrying the query and the result count — never
        the records — so a run's trace shows every provider call beside the LLM
        generations. A failed call leaves an errored span.
        """
        return tracing.traced_call(
            self._langfuse_client,
            name=f"{self._inner.name}:{method}",
            as_type="span",
            call=lambda: self._record_call(method, query, wire_params, call),
            update=lambda span, records: span.update(
                input={"query": query, "wire_params": wire_params},
                output={"result_count": len(records)},
            ),
        )

    def _record_call(
        self,
        method: str,
        query: str,
        wire_params: dict[str, str] | None,
        call: Callable[[], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        try:
            records = call()
        except Exception as exc:
            self._calls.append(
                {
                    "backend": self._inner.name,
                    "method": method,
                    "query": query,
                    "wire_params": wire_params,
                    "result_count": 0,
                    "records": [],
                    "error": str(exc),
                }
            )
            raise
        self._calls.append(
            {
                "backend": self._inner.name,
                "method": method,
                "query": query,
                "wire_params": wire_params,
                "result_count": len(records),
                "records": records,
                "error": None,
            }
        )
        return records

    def search(
        self, query: str, *, wire_params: dict[str, str] | None = None, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        return self._record(
            "search",
            query,
            wire_params,
            lambda: self._inner.search(query, wire_params=wire_params, max_results=max_results),
        )

    def fetch_citations(self, record_id: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        return self._record(
            "fetch_citations",
            record_id,
            None,
            lambda: self._inner.fetch_citations(record_id, max_results=max_results),
        )

    def fetch_references(
        self, record_ids: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        return self._record(
            "fetch_references",
            ",".join(record_ids),
            None,
            lambda: self._inner.fetch_references(record_ids, max_results=max_results),
        )

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        return self._record(
            "lookup_title", title, None, lambda: self._inner.lookup_title(title)
        )

    def lookup_dois(self, dois: list[str], *, max_results: int | None = None) -> list[dict[str, Any]]:
        return self._record(
            "lookup_dois",
            ",".join(dois),
            None,
            lambda: self._inner.lookup_dois(dois, max_results=max_results),
        )


@dataclass
class QueryResult:
    query: str
    search_candidate_count: int
    screened_relevant_count: int
    search_recall: float
    screen_recall: float | None
    """None when the run skipped screening (``run_screen=False``) — screening
    was not measured, which is different from screening scoring zero."""
    search_calls: list[dict[str, Any]]
    """Every generated query + its raw returned provider records, one entry per
    backend call this run made — for offline diagnosis, not scored itself."""
    search_docs: list[dict[str, Any]]
    """Metadata for every candidate that survived acquire's dedup + cap into the
    database. Diagnosis only: lets you tell "the API never returned it" from
    "the cap threw it away" (the sweep's papers CSV)."""
    screened_docs: list[dict[str, Any]]
    """Metadata for every candidate the screening LLM marked relevant.
    Diagnosis only — the scored numbers above are counts over these."""


def run_one_query(
    conn: Connection,
    query: str,
    ground_truth: GroundTruth,
    *,
    published_before: str,
    depth: str = "rapid",
    run_screen: bool = True,
    langfuse_client: Langfuse | None = None,
    generation_backend_variant: str = "shared",
) -> QueryResult:
    """Run one intent through search (and optionally screening), and score it.

    Args:
        run_screen: False skips the screening stage entirely — no screening LLM
            calls, no screening bill. Use it when the experiment is about search
            retrieval only; ``screen_recall`` comes back None.
    """
    task_id, run_id = _seed_task_and_run(conn)
    scope_id = _seed_scope(conn, task_id, query)

    search_context = {
        "search": {
            "depth": depth,
            # Never credit the pipeline for finding sources the review itself
            # could not have cited — the review's own publication date is a
            # hard upper bound on its evidence base, not a suggestion.
            "filters": {"shared": {"published_before": published_before}},
        }
    }
    search_calls: list[dict[str, Any]] = []
    recording_backends = [
        _RecordingBackend(b, search_calls, langfuse_client) for b in live_search_backends()
    ]
    run_search(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(scope_id=scope_id, intent=query, context=search_context),
        backends=recording_backends,
        generation_backend=GENERATION_BACKENDS[generation_backend_variant](
            langfuse_client=langfuse_client
        ),
    )
    search_docs = _search_candidate_docs(conn, task_id)
    search_dois = _keys_of(search_docs)

    if run_screen:
        screen_sources(
            conn,
            task_id=task_id,
            run_id=run_id,
            context=ScreenContext(scope_id=scope_id, intent=query, context={}),
            screening_backend=OpenAIScreeningBackend(langfuse_client=langfuse_client),
        )
        screened = _screened_relevant_docs(conn, task_id, scope_id)
    else:
        screened = []
    screened_dois = _keys_of(screened)

    return QueryResult(
        query=query,
        search_candidate_count=len(search_dois),
        screened_relevant_count=len(screened_dois),
        search_recall=_recall(search_dois, ground_truth.keys),
        screen_recall=_recall(screened_dois, ground_truth.keys) if run_screen else None,
        search_calls=search_calls,
        search_docs=search_docs,
        screened_docs=screened,
    )
