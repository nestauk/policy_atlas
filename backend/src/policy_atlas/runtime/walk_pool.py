"""The option-search pool and the two per-component slots (task 045, S2).

Two bounds, both process-wide (ADR 0039 decision 4):

- **The option-search pool** runs a longlist walk's option searches — its
  child walks — at width :data:`~policy_atlas.runtime.scoping_plan.OPTION_SEARCH_WIDTH`.
  It is **separate from** ``app.state.run_executor`` on purpose: the parent
  walk occupies one of that executor's workers while it waits for its
  children, so children submitted to the same executor could wait forever
  behind their own parent.
- **The per-component slots** close the fan-out seam task 044 recorded:
  classify's provider fan-out and ingest's parse workers were bounded per run,
  not across runs, so four children and a parent would each have taken their
  own twelve classify threads and their own parse processes.
  :data:`CLASSIFY_SLOTS` is taken around each classification provider call
  and :data:`INGEST_SLOTS` around each parse job, so every walk in the process
  shares one budget of each. For a single walk the budget equals the per-run
  width, so a lone walk behaves exactly as before.

The database pool is not changed here (production config); the live check
measures peak connection use with four children running.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from policy_atlas.evidence_search.assess.classify import MAX_CONCURRENT_CLASSIFY
from policy_atlas.evidence_search.sourcing.ingest_full_text import DEFAULT_MAX_WORKERS
from policy_atlas.runtime.scoping_plan import OPTION_SEARCH_WIDTH

#: Classification provider calls in flight across every walk in the process.
CLASSIFY_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_CLASSIFY)

#: Live parse-job worker processes across every walk in the process.
INGEST_SLOTS = threading.BoundedSemaphore(DEFAULT_MAX_WORKERS)

_pool_lock = threading.Lock()
_pool: ThreadPoolExecutor | None = None


def option_search_pool() -> ThreadPoolExecutor:
    """Return the process-wide option-search pool, creating it on first use.

    Created lazily so importing the runtime starts no threads; the pool then
    lives for the process, like the walk executor.

    Returns:
        The pool, ``max_workers=OPTION_SEARCH_WIDTH``.
    """
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(
                max_workers=OPTION_SEARCH_WIDTH,
                thread_name_prefix="policy-atlas-option-search",
            )
        return _pool
