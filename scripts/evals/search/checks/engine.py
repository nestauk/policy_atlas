"""Run one research intent through the real search stage (and optionally
screening) and score it against a review's reference list.

This is the engine that ``experiments/sweep_record_cap.py`` and ``checks/production_recall.py``
drive. It has no command line of its own. ``run_one_query`` seeds a throwaway
task/scope, runs the pipeline's own ``run_search`` once and, when asked,
``screen_sources`` once, inside the caller's transaction (which the caller
rolls back, so nothing is ever committed). It returns a ``QueryResult`` with
recall attributed to each stage, plus everything needed to unpick the run
offline (see ``checks/inspect_run.py``).

Search is one pass at every depth (task 051, ADR 0038): keyword and semantic
seeds, backward and forward citation chasing, Overton relevance results and
landmarks, two ranked pools cut at the depth's two caps. The depths differ only
in those caps, so a search-only measurement is valid at any depth.

Precision is not scored. A screened-in paper that is absent from one review's
bibliography is not proven irrelevant (the review had its own scope and time
cutoff), so bibliography membership is not a valid false-positive signal.

Two caps bound how many candidates a run keeps, both in
``search_loop.DEPTH_CONSTANTS`` (the sweep overrides ``papers_cap`` in this
process only):

* ``papers_cap`` — papers (OpenAlex) persisted from the ranked paper pool.
* ``policy_cap`` — policy documents (Overton) persisted from the ranked policy pool.

Records past a cap were fetched and paid for, then discarded (the
``acquire.capped`` log line); the caps set the recall ceiling.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import _bootstrap  # noqa: F401
from evals_search_utils import GroundTruth, record_key
from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import tracing
from policy_atlas.core.schema import (
    event_log,
    evidence_scope,
    runs,
    source_snapshot,
    task,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.screen import (
    ScreenContext,
    effective_screen_rows,
    screen_sources,
)
from policy_atlas.evidence_search.assess.screening_backend import OpenAIScreeningBackend
from policy_atlas.evidence_search.sourcing.acquire import AcquireContext
from policy_atlas.evidence_search.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_live import live_search_backends
from policy_atlas.evidence_search.sourcing.search_loop import (
    DEPTH_CONSTANTS,
    run_search,
)

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


def _seed_task(conn: Connection) -> uuid.UUID:
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now,
            name="eval-pilot",
            status="active",
            updated_at=now,
        )
    )
    return task_id


def _seed_run(conn: Connection, task_id: uuid.UUID) -> uuid.UUID:
    """One ``runs`` row. The pipeline keys its per-round bookkeeping (which
    screen run wrote which verdicts) on the run id, so every search round and
    every screen round gets a fresh one, exactly as the app's runner does."""
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            task_id=task_id,
            status="running",
            started_at=datetime.now(UTC),
        )
    )
    return run_id


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


def _search_candidate_docs(
    conn: Connection, task_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Metadata for every candidate that reached the database — i.e. what
    survived acquire's dedup and cap, not everything the APIs returned."""
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(
            task_source_snapshot,
            task_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        )
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _keys_of(docs: list[dict[str, Any]]) -> set[str]:
    """Scoring keys for a set of documents: DOI where there is one, else the
    Overton document id (see ``evals_search_utils.record_key``). Documents with
    neither cannot be matched against the ground truth and are dropped."""
    return {key for d in docs if (key := record_key(d))}


def _screened_relevant_docs(
    conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Mirrors ``classify._load_relevant_docs``'s join shape over the effective screen rows."""
    effective = effective_screen_rows()
    rows = conn.execute(
        select(source_snapshot.c.metadata)
        .join(
            effective,
            (
                effective.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (effective.c.task_id == task_source_snapshot.c.task_id),
        )
        .join(
            source_snapshot,
            task_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        )
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    return [metadata for (metadata,) in rows]


def _recall(found: set[str], target: set[str]) -> float:
    if not target:
        return 0.0
    return len(found & target) / len(target)


def _acquired_in_order(
    conn: Connection, task_id: uuid.UUID
) -> list[tuple[str, dict[str, Any]]]:
    """Every acquired document as (backend, metadata), in the order acquire persisted
    them: the ranked order, so a document's index within its backend is its rank."""
    events = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "source.acquired")
        .order_by(event_log.c.sequence)
    ).fetchall()
    ids = [uuid.UUID(payload["source_snapshot_id"]) for (payload,) in events]
    metadata = dict(
        conn.execute(
            select(
                source_snapshot.c.source_snapshot_id, source_snapshot.c.metadata
            ).where(source_snapshot.c.source_snapshot_id.in_(ids))
        ).fetchall()
    )
    return [
        (payload["backend"], metadata[uuid.UUID(payload["source_snapshot_id"])])
        for (payload,) in events
    ]


def recall_at_smaller_caps(
    acquired: list[tuple[str, dict[str, Any]]],
    screened_keys: set[str],
    target: set[str],
    *,
    depth: str,
) -> dict[str, dict[str, float | int]]:
    """Score the depths whose caps fit inside this run's, from this run's own pool.

    The scopes differ only in where the same ranked pools are cut (papers cap
    100 / 200 / 400, policy cap 50 / 100 / 200), and the screen judges each document
    on its own. So one run at a larger scope says what a smaller scope would have
    found with the same generated queries: the documents in the first ``papers_cap``
    of its OpenAlex order and the first ``policy_cap`` of its Overton order.

    Returns:
        Per smaller depth: ``search_recall``, ``n_found``, ``screen_recall``,
        ``n_screened_in``.
    """
    own = DEPTH_CONSTANTS[depth]
    out: dict[str, dict[str, float | int]] = {}
    for name, constants in DEPTH_CONSTANTS.items():
        if name == depth or constants["papers_cap"] > own["papers_cap"]:
            continue
        cap = {"openalex": constants["papers_cap"], "overton": constants["policy_cap"]}
        seen: dict[str, int] = {}
        within: set[str] = set()
        for backend, metadata in acquired:
            position = seen.get(backend, 0)
            seen[backend] = position + 1
            if position < cap.get(backend, 0) and (key := record_key(metadata)):
                within.add(key)
        out[name] = {
            "search_recall": _recall(within, target),
            "n_found": len(within & target),
            "screen_recall": _recall(within & screened_keys, target),
            "n_screened_in": len(within & screened_keys),
        }
    return out


class _RecordingBackend:
    """Wraps one live ``SearchBackend`` to record every generated query/call and
    its raw returned provider records, for offline diagnosis (e.g. in a
    notebook) of why recall came out low. Pure passthrough otherwise — proxies
    the exact seam ``search_loop.py`` calls on a backend (``acquire.SearchBackend``:
    ``name``/``trust_class``/``mode``/``caps`` plus the 9 fetch/search/lookup
    methods), so it's transparent to the pipeline.
    """

    def __init__(
        self,
        inner: Any,
        calls: list[dict[str, Any]],
        langfuse_client: Langfuse | None = None,
        lock: threading.Lock | None = None,
    ) -> None:
        self._inner = inner
        self._calls = calls
        self._langfuse_client = langfuse_client
        # The search's legs and seed calls run concurrently (task 051); the
        # list is a diagnostic log in completion order. One lock is shared by
        # every wrapper that appends to the same list (``run_one_query``).
        self._lock = lock if lock is not None else threading.Lock()

    def _log(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._calls.append(entry)

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
            self._log(
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
        self._log(
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
        self,
        query: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._record(
            "search",
            query,
            wire_params,
            lambda: self._inner.search(
                query, wire_params=wire_params, max_results=max_results
            ),
        )

    def fetch_citations(
        self, record_id: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
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

    def search_semantic(
        self,
        text: str,
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._record(
            "search_semantic",
            text,
            wire_params,
            lambda: self._inner.search_semantic(
                text, wire_params=wire_params, max_results=max_results
            ),
        )

    def lookup_ids(
        self, ids: list[str], *, wire_params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        return self._record(
            "lookup_ids",
            "|".join(ids),
            wire_params,
            lambda: self._inner.lookup_ids(ids, wire_params=wire_params),
        )

    def fetch_citing(
        self,
        ids: list[str],
        *,
        wire_params: dict[str, str] | None = None,
        max_results: int | None = None,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        return self._record(
            "fetch_citing",
            "|".join(ids),
            wire_params,
            lambda: self._inner.fetch_citing(
                ids,
                wire_params=wire_params,
                max_results=max_results,
                page=page,
            ),
        )

    def fetch_by_id(self, record_id: str) -> dict[str, Any] | None:
        records = self._record(
            "fetch_by_id",
            record_id,
            None,
            lambda: [record] if (record := self._inner.fetch_by_id(record_id)) else [],
        )
        return records[0] if records else None

    def lookup_title(self, title: str) -> list[dict[str, Any]]:
        return self._record(
            "lookup_title", title, None, lambda: self._inner.lookup_title(title)
        )

    def lookup_dois(
        self, dois: list[str], *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
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
    rounds_run: int = 1
    """Always 1: search is one pass at every depth (task 051). Kept so the
    history's columns do not change."""
    stop_condition: str | None = None
    """The coverage record's ``stop_condition`` (``completed`` or ``error``)."""
    recall_at: dict[str, dict[str, float | int]] = field(default_factory=dict)
    """What the smaller depths would have scored on this run's pool and screen
    (``recall_at_smaller_caps``). Empty for ``rapid``."""


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
    """Run one intent through the single search pass, screen it, and score it.

    Args:
        depth: ``rapid``, ``standard`` or ``deep``; the same pass with different caps.
        run_screen: False skips the screening stage entirely: no screening LLM
            calls, no screening bill, ``screen_recall`` comes back None. Valid
            at any depth, since the search needs no screening verdict.
    """
    task_id = _seed_task(conn)
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
    calls_lock = threading.Lock()
    recording_backends = [
        _RecordingBackend(b, search_calls, langfuse_client, lock=calls_lock)
        for b in live_search_backends()
    ]
    generation_backend = GENERATION_BACKENDS[generation_backend_variant](
        langfuse_client=langfuse_client
    )
    screening_backend = (
        OpenAIScreeningBackend(langfuse_client=langfuse_client) if run_screen else None
    )

    search_counts = run_search(
        conn,
        task_id=task_id,
        run_id=_seed_run(conn, task_id),
        context=AcquireContext(scope_id=scope_id, intent=query, context=search_context),
        backends=recording_backends,
        generation_backend=generation_backend,
    )
    stop_condition: str | None = search_counts.get("stop_condition")
    if run_screen:
        screen_sources(
            conn,
            task_id=task_id,
            run_id=_seed_run(conn, task_id),
            context=ScreenContext(scope_id=scope_id, intent=query, context={}),
            screening_backend=screening_backend,
        )

    search_docs = _search_candidate_docs(conn, task_id)
    search_dois = _keys_of(search_docs)
    screened = _screened_relevant_docs(conn, task_id, scope_id) if run_screen else []
    screened_dois = _keys_of(screened)
    recall_at = recall_at_smaller_caps(
        _acquired_in_order(conn, task_id), screened_dois, ground_truth.keys, depth=depth
    )

    return QueryResult(
        query=query,
        search_candidate_count=len(search_dois),
        screened_relevant_count=len(screened_dois),
        search_recall=_recall(search_dois, ground_truth.keys),
        screen_recall=_recall(screened_dois, ground_truth.keys) if run_screen else None,
        search_calls=search_calls,
        search_docs=search_docs,
        screened_docs=screened,
        rounds_run=1,
        stop_condition=stop_condition,
        recall_at=recall_at,
    )
