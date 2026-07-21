# C.4 — Thread-safety audit

Executed per `parking-seam-design.md` §7 (contract concurrent-users pin).
Components under `backend/src/policy_atlas/{core,evidence_base,runtime}`
were built one-walk-at-a-time; task 025's API introduces concurrent walks on
**different** projects (never the same project twice at once — that stays
outside scope, see the single-writer-per-project note below). This audit
sweeps for module-global mutable state, run-scoped `lru_cache`, `os.environ`
mutation, monkeypatching in product code, and shared class-level state, then
clears the five named suspects explicitly.

Regression evidence: `backend/tests/runtime/test_concurrent_walks.py` (the
"both-complete" test) — two concurrent stub walks on two different projects,
driven from two threads over the same shared engine, both complete
`succeeded`, with fully project-scoped `runs`/`capability_run` read-back, no
cross-project `event_log` rows, and no per-project sequence collision.

## 1. Grep sweep — module-level mutable state

| Pattern | Result |
|---|---|
| `functools.lru_cache` / `functools.cache` on any function | **None found** anywhere in `core/`, `evidence_base/`, `runtime/`. |
| `os.environ` mutation (`[...] =`, `.setdefault`, `.pop`, `.update`, `del`) | **None found** in product code under the swept trees — every `os.environ` reference is a read (`os.environ.get(...)`). |
| `monkeypatch` in product code | **None found** — the demo's monkeypatching pattern (banned) is absent from `core/`, `evidence_base/`, `runtime/`; all `monkeypatch` hits are test-only. |
| Module-level mutable dict/list/set assignments | Numerous (`DEFAULT_WEIGHTS`, `TIME_BANDS`, `LATTICE_POINTS`, `COMPONENT_REGISTRY`, `ISO_3166_ALPHA2`, `_MAPPERS`, etc. — ~50 hits). All are **read-only lookup/config tables** populated once at import time and never mutated at runtime (verified: no `.update(`/`.append(`/item-assignment call site against any of them outside their own definition). Safe. |
| Module-level mutable **cache** (the one pattern the sweep specifically flags) | **One real finding** — `evidence_base/sourcing/search_live.py:_SEARCH_CACHE` (below). |
| Class attributes used as shared instance state (classic "mutable default" gotcha) | **None found** — every per-instance counter/cache seen (`_batch_count`, `_assign_count`, `http_calls`, `_client`) is set in `__init__`/an init method, not as a class-body default. |

## 2. Named suspects

| Module | Verdict | Notes |
|---|---|---|
| `core/openai_client.py` | **Safe / parameter-passed** | `resolve_openai_client()` constructs a fresh `OpenAI(...)` client per call; no module-level client or cache. Every call site (`extraction_backend.py`, `screening_backend.py`, `synthesis_backend.py`, `embeddings.py`, `planner.py`, `orchestrator_backend.py`, …) stores the client on `self._client` of its own backend instance. The OpenAI Python SDK's `OpenAI` client (httpx-based) is documented thread-safe for concurrent requests when an instance is shared across threads — today's call convention (`RunnerBackends()`/`_live_planner_and_backends()` constructed fresh per `main()`/`run_plan()` invocation, orchestrate.py:1013) means no instance is shared across concurrent walks in the first place; if a future API layer pools/shares one `RunnerBackends` bundle across concurrent requests for efficiency, that remains safe per the SDK's own thread-safety contract. |
| `core/tracing.py` | **Safe / parameter-passed** | `get_langfuse()` constructs a fresh `Langfuse(...)` client per call — no global singleton. `session_id` is a plain parameter threaded through `traced_call`/`_set_current_trace_session` down to Langfuse's `update_current_trace(session_id=...)`; never read from a global. `TracedEmbeddingBackend`/`TracedThemeGroupingBackend` hold a per-instance `_batch_count`/`_assign_count` guarded by a per-instance `threading.Lock()` — correctly synchronized *if* an instance were ever shared across threads, though today's construction (fresh per walk, orchestrate.py `_live_planner_and_backends`) means no such sharing occurs. Forward-looking note only, not a bug: if the API layer later pools these wrappers across concurrent walks, the lock keeps the counter correct, but the resulting span labels (`embed:batch3`) interleave numbering across two projects' traces — cosmetic (a label), not a correctness or attribution defect (trace/session attachment goes through Langfuse's own context, driven by the parameter-passed `session_id`, not this counter). |
| `core/db.py` | **Safe — process-singleton by design** | `get_engine()` builds a plain SQLAlchemy `Engine` from `DATABASE_URL`; no caching at all in this function (every call constructs a new `Engine`), but SQLAlchemy's `Engine` + connection-pool is documented thread-safe, and callers holding one shared `Engine` for the process (the intended FastAPI pattern) is the supported, safe usage this comment anticipates. `test_concurrent_walks.py` exercises exactly this shape — one shared `engine` fixture, two threads each checking out their own pooled connection. |
| `core/embeddings.py` | **Safe** | No `lru_cache`, no module-level cache. Module-level state is two compiled regexes (`_SENTENCE_BOUNDARY_RE`, `_PARAGRAPH_BOUNDARY_RE`) and a `time.sleep` alias (`_sleep`) — all read-only/immutable, safe to share across threads (`re.Pattern.match` is thread-safe). `OpenAIEmbeddingBackend.__init__` builds its own client via `resolve_openai_client`, per-instance, same pattern as every other live backend. |
| `evidence_base/sourcing/search_live.py` | **Real finding — see §3** | `_SEARCH_CACHE` (module-level `OrderedDict`) is genuinely shared, unsynchronized, mutable process-global state. |

## 3. Real finding: `search_live._SEARCH_CACHE` — unsynchronized shared cache

`evidence_base/sourcing/search_live.py:83` declares:

```python
_SEARCH_CACHE: OrderedDict[_SearchCacheKey, tuple[float, Any]] = OrderedDict()
```

a **process-global, unlocked** LRU-ish cache of live search responses, keyed
by `(scheme, netloc, path, sorted non-credential params)` — i.e. content-
addressed by the external query, not by `project_id`/`run_id`. It's read and
written from `_search_cache_get`/`_search_cache_set` (lines 754–770), called
from every `_TransportMixin._request_json` (OpenAlex/Overton live search).

- **Not a cross-project data-leak concern in the security sense**: the
  cached payloads are public third-party API search results (OpenAlex/
  Overton), not project-scoped or sensitive data. Two projects issuing the
  identical external query legitimately get the identical external answer —
  sharing the cache across projects is the intended semantic, not a bug.
- **It is a real concurrency bug**, reachable once task 025 allows two
  different projects' walks to call live search concurrently (both use
  `POLICY_ATLAS_SEARCH_CACHE_TTL_S` search caching whenever a live
  OpenAlex/Overton key is configured — the default construction path when
  live keys are present, not merely a test double). `_search_cache_get`
  (lines 754–763) is a check-then-act sequence with no lock:

  ```python
  cached = _SEARCH_CACHE.get(key)
  ...
  if _monotonic() - cached_at >= ttl_s:
      del _SEARCH_CACHE[key]      # <-- unguarded
      return None
  ```

  Two threads racing on the *same* cache key at its TTL-expiry boundary can
  both observe the entry as expired and both call `del _SEARCH_CACHE[key]`;
  the second `del` raises `KeyError` (the key was already removed by the
  first thread), uncaught, which propagates out of the live search call and
  fails that walk's `acquire`/search step. The window is narrow (needs two
  concurrent walks issuing the identical external query at the identical
  moment of expiry) but it is a genuine, previously-latent bug that
  concurrent walks (not one-walk-at-a-time) make reachable for the first
  time. Beyond the crash path, the get/set/evict sequence (`move_to_end`,
  `popitem(last=False)` under `_SEARCH_CACHE_MAX_ENTRIES`) is also not
  atomic as a whole, so heavy concurrent traffic could transiently exceed
  the entry cap or evict/reinsert out of true LRU order — benign
  (correctness of *returned data* is unaffected; every cache path re-fetches
  live on a miss), but worth the lead's attention alongside the `KeyError`.

**Disposition**: not fixed here. This is not a mechanical parameter-passing
change — the fix is a concurrency-hardening decision (a lock around the
get/check/evict sequence, or `dict.pop(key, None)` instead of `del`, or
scoping/disabling the cache under concurrent-walk mode) that belongs to the
lead's call on `search_live.py`, a file this brief was scoped to audit, not
modify. Filed here as the stop-condition finding the brief anticipates.

## 4. Per-run config is parameter-passed everywhere

Spot-checked the call graph for `run_plan`: `project_id`, `evidence_scope_id`,
`plan`, `plan_id`, `plan_version`, `backends`, `io`, `session_id`,
`orchestrator`, `discretion_hook` are all explicit parameters threaded down
through every `_handle_*`/`_run_*` helper (`runner.py`) — no read-from-global
of directive/plan state anywhere in the sweep. `steering.py`'s directive/
delta helpers (`leg_directive`, `deep_merge_delta`, `commit_layer_overlay`)
take the plan/state as arguments; none reach for a module global.

## 5. Other module-level state noted, judged out of scope for this audit

- `core/logging.py:configure_logging()` calls `structlog.configure(...)`,
  which mutates structlog's own global processor-chain configuration.
  Every process entrypoint (`orchestrate.main()`, the harness) calls this
  once at the top unconditionally. It carries no per-run/per-project data
  (it only sets log *formatting*), so concurrent or repeated calls are
  last-writer-wins on global logging format, not a correctness bug for any
  individual walk — noted for completeness, not a finding.

## Summary verdict

| Item | Verdict |
|---|---|
| `core/openai_client.py` | Safe / parameter-passed |
| `core/tracing.py` | Safe / parameter-passed (forward-looking cosmetic note on span-label numbering if backends are ever pooled) |
| `core/db.py` | Safe — process-singleton by design |
| `core/embeddings.py` | Safe |
| `evidence_base/sourcing/search_live.py` | **Real finding — unsynchronized `_SEARCH_CACHE`, reachable `KeyError` under concurrent identical-query races. Not fixed; reported to the lead.** |
| Per-run config parameter-passing | Confirmed throughout `runner.py`/`steering.py` |
| Both-complete regression test | `backend/tests/runtime/test_concurrent_walks.py` — green |
