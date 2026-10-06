"""Frequency snowball on top of the raw OpenAlex baseline (R&D, task 047).

The idea, in one paragraph. Keyword search returns papers whose words match the
question. The papers that a topic's literature keeps citing often use older or
different words, so keyword search misses them (the "seminal works" gap seen in user
feedback and in the 046 miss diagnosis). But every OpenAlex record carries its
reference list. If we take the first N keyword results as **seeds**, read all their
reference lists, and count how many seeds cite each work, the most-cited works are the
topic's landmarks, found without anyone knowing their titles. This script adds the top
K of those to the seed set, ranks the union a few different ways, and scores recall
against the same ground truth and with the same keys as ``baseline_recall.py``.

Stages per review:

1. **Seeds.** The first ``--seeds`` results of the cached ``openalex-raw`` arm (fetched
   by ``baseline_recall.py`` if missing). One batched lookup per 50 seeds fetches each
   seed's reference list and citation count (the raw arm's cache has neither).
2. **Count.** Tally how many seeds cite each referenced work. Works already in the seed
   set keep their tally (it is used for ranking) but are not added twice.
3. **Expand.** Resolve the ``--expand`` most-cited new works to records, in batches of
   50, filtered to the review's cutoff date, so a reference published after the cutoff
   is dropped. Fewer than K may come back for that reason.
4. **Rank** the union by one of ``RANKINGS`` (see that table) and **score** recall at
   each ``--caps`` value: first N of the ranked list, duplicates on the scoring key
   removed, recall = share of the review's reference list found. ``n_from_snowball``
   says how many of the hits the keyword search alone did not have.

Everything the services return is cached under ``results/cache/openalex-snowball/``
(key: review, seeds, expand) and ``results/cache/gt-citations/`` (the ground truth's
own citation counts, for the seminal-decile score), so a second run makes no requests.
Per-review scores and the ranked candidate tables are written under ``--out`` so misses
can be read, and a ``--manual`` question with no ground truth is exported there too
(subfolder ``manual/<slug>/``, one CSV per ranking) for hand inspection.

Seminal decile: for reviews whose reference list is a labelled set of included studies,
the tenth of the list with the most citations (floor five). Unlabelled lists mix in
methods papers, where that tenth is mostly Rayyan and ROBINS-I, so it is not reported
for them. The labelled flag comes from ``results/ground_truth/sample_100_reviews.csv``
by title or review id; the four hand-made reviews count as labelled.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/measure/snowball_recall.py \\
        [--dataset retrieval-ground-truth-mini] [--seeds 200] [--expand 200] \\
        [--caps 50 100 200 400] [--rankings raw inset specific global interleave] \\
        [--reviews TEXT ...] [--manual QUESTION ...] [--out DIR] [--refresh]

Free: OpenAlex only, about (seeds + expand) / 50 requests per review. Uploads nothing
to Langfuse (R&D; a chosen configuration can be promoted to an arm later). Dev-only eval
tooling. Not part of the runtime package.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import (
    cache_path,
    load_or_fetch,
    make_getter,
    openalex_cutoff,
    openalex_query,
    records_of,
)
from evals_search_utils import (
    DEFAULT_DATASET,
    GroundTruth,
    ground_truth_from_item,
    normalize_doi,
    record_key,
    select_items,
)

import argparse
import collections
import csv
import hashlib
import json
import math
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing
from policy_atlas.evidence_search.sourcing import search_generation, search_prompts
from policy_atlas.evidence_search.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
)
from policy_atlas.evidence_search.sourcing.search_live import sanitize_openalex_query
from policy_atlas.evidence_search.sourcing.search_loop import (
    RCT_CLAUSE,
    SR_CLAUSE,
    _compose_variant,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    QueriesPayload,
    SearchQueriesWire,
    validated_queries,
)
from pydantic import BaseModel, ConfigDict, Field

ARM = "openalex-snowball"
SEED_ARM = "openalex-raw"
MINI_DATASET = DEFAULT_DATASET + "-mini"
BATCH = 50  # OpenAlex accepts up to 50 values in one filter
# ``counts_by_year`` lets every citation count be taken AS OF the review's cutoff (today's
# count minus citations in later years), so a historical-cutoff evaluation does not rank
# on citations the review's authors could not have seen. OpenAlex carries the last ten
# years, which covers every cutoff in the datasets (2018 onward).
SEED_SELECT = "id,doi,display_name,publication_date,cited_by_count,counts_by_year,referenced_works"
RESOLVE_SELECT = "id,doi,display_name,publication_date,cited_by_count,counts_by_year"
# Bumped when cached payload contents change shape (here: counts_by_year added), so old
# cache files are not read as if they held the new fields.
CACHE_VERSION = "v2"
DEFAULT_CAPS = [50, 100, 200, 400]
SEMINAL_FLOOR = 5
OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "snowball"
REVIEWS_CSVS = sorted(
    (Path(__file__).resolve().parents[1] / "results" / "ground_truth").glob(
        "sample_*_reviews.csv"
    )
)
# How the union of seeds and snowball candidates is ordered before the cap is applied.
# Where the seeds come from. ``raw`` is the one plain query of the openalex-raw baseline.
# The other two are the pipeline's own rapid-search query generation, run through the
# backend's classes: ``shared`` (one prompt writes the OpenAlex queries and the Overton
# paraphrases, prompt file search_queries_system_v3.txt) and ``per-provider`` (one prompt
# per service, search_queries_openalex_system_v2.txt). Only the OpenAlex queries are sent;
# Overton is not part of this experiment.
QUERY_SOURCES = {
    "raw": None,
    "shared": OpenAISearchGenerationBackend,
    "per-provider": V2SearchGenerationBackend,
    # Semi-deterministic: one call asks the model for concept blocks (vocabulary only);
    # ``compose_queries`` assembles the boolean queries in code.
    "concepts": "concepts",
    # OpenAlex semantic search (``search.semantic``, embedding search over titles and
    # abstracts, 50 results per call, about $0.001 per call, one request per second).
    # ``semantic`` seeds from it alone: the question, the production prompt's two
    # natural-language paraphrases and its five keyword queries, each as one semantic
    # call. ``shared+semantic`` merges those with the keyword results.
    "semantic": "semantic",
    "shared+semantic": "semantic",
}
SEMANTIC_PER_CALL = 50
SEMANTIC_INTERVAL_S = 1.0
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
CONCEPTS_PROMPT_DEFAULT = PROMPTS_DIR / "openalex_concepts_exp_f.txt"
CONCEPTS_PROMPT = ""  # set by override_prompt
REASONING_EFFORT: str | None = (
    None  # set from --reasoning-effort; None = the pipeline's default
)


def set_reasoning_effort(effort: str | None) -> None:
    """Forward ``reasoning_effort`` on every generation call, without touching the backend.

    The backend's ``_parse_once`` calls ``parse_structured`` by its module-level name and
    does not pass ``reasoning_effort``, so the model runs at its default effort. Wrapping
    that name in this process adds the argument for the experiment only.
    """
    global REASONING_EFFORT
    REASONING_EFFORT = effort
    if effort is None:
        return
    original = search_generation.parse_structured

    def with_effort(*args: Any, **kwargs: Any) -> Any:
        return original(*args, reasoning_effort=effort, **kwargs)

    search_generation.parse_structured = with_effort


QUERY_MAX_CHARS = 250
TERM_MAX_CHARS = 40
TERMS_PER_BLOCK = 6


class ConceptBlocksWire(BaseModel):
    """Concept blocks for one research question, vocabulary only (schema-constrained)."""

    model_config = ConfigDict(extra="forbid")

    population: list[str] = Field(
        description="Who or what the question is about; empty if none."
    )
    phenomenon: list[str] = Field(
        description="The intervention, exposure or phenomenon, technical vocabulary."
    )
    phenomenon_alternatives: list[str] = Field(
        description="The same phenomenon in the other register: lay words, policy words, other spelling, abbreviations."
    )
    setting: list[str] = Field(
        description="Context, place or sector the question names; empty if none."
    )
    forms: list[str] = Field(
        description="Specific forms, components, mechanisms or delivery modes of the phenomenon."
    )
    outcome: list[str] = Field(
        description="Only a concrete outcome the question itself names; empty otherwise."
    )


def _clean_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        t = re.sub(r"[\"'()*?~]", " ", term).strip()
        t = re.sub(r"\s+", " ", t)
        if t and len(t) <= TERM_MAX_CHARS and t.lower() not in {o.lower() for o in out}:
            out.append(t)
    return out[:TERMS_PER_BLOCK]


def _group(terms: list[str]) -> str:
    return "(" + " OR ".join(f'"{t}"' if " " in t else t for t in terms) + ")"


def _fit(groups: list[list[str]], limit: int = QUERY_MAX_CHARS) -> str:
    """Render groups joined by AND; drop the last synonym of the longest group until it fits."""
    groups = [list(g) for g in groups if g]
    while True:
        text = " AND ".join(_group(g) for g in groups)
        if len(text) <= limit or all(len(g) <= 1 for g in groups):
            return text
        max(groups, key=len).pop()


def compose_queries(wire: ConceptBlocksWire) -> list[str]:
    """Up to five boolean queries from the concept blocks, two groups at most each.

    Order mirrors the roles a specialist would cover: broad net, core, alternative
    vocabulary, narrowed to the setting, mechanism or form (or the named outcome).
    """
    pop, phen, alt, setting, forms, outcome = (
        _clean_terms(getattr(wire, name))
        for name in (
            "population",
            "phenomenon",
            "phenomenon_alternatives",
            "setting",
            "forms",
            "outcome",
        )
    )
    plans: list[list[list[str]]] = []
    if phen:
        plans.append([phen])
    if pop and phen:
        plans.append([pop, phen])
    if alt:
        plans.append([pop or setting, alt] if (pop or setting) else [alt])
    if setting and phen:
        plans.append([phen, setting])
    if forms:
        plans.append([forms, pop or phen] if (pop or phen) else [forms])
    if outcome and phen:
        plans.append([phen, outcome])
    queries: list[str] = []
    for plan in plans:
        text = _fit(plan)
        if text and text.lower() not in {q.lower() for q in queries}:
            queries.append(text)
    return queries[:5]


PER_CALL_DEFAULT = 200  # results fetched per generated query (rapid itself fetches 50)
# Forward citation chasing (hypothesis 1 of the search experiments write-up § 6): papers that CITE the
# seeds. OpenAlex's ``cites:`` filter takes up to 100 ids joined by ``|``; a seed with
# thousands of citations floods the result, so only seeds with at most
# ``forward_max_cites`` citations are chased. Candidates are ranked by **coupling**: how
# many seeds each citing paper cites (bibliographic coupling), computed locally from
# its reference list.
FORWARD_SELECT = "id,doi,display_name,publication_date,cited_by_count,counts_by_year,referenced_works"
FORWARD_IDS_PER_CALL = 100
RANKINGS = {
    "raw": "keyword results in the service's order, then snowball works by in-set citations",
    "inset": "everything by in-set citations (how many seeds cite it), ties by global citations",
    "specific": "everything by specificity = in-set citations / log10(global citations + 10); "
    "damps works everyone cites (PRISMA, Egger's test) in favour of works this topic cites",
    "global": "everything by global citation count",
    "interleave": "alternate one keyword result (service order) and one snowball work (in-set order)",
}


def cited_asof(work: dict[str, Any], cutoff: str) -> int:
    """The work's citation count as of the cutoff date: today's count minus later years.

    ``counts_by_year`` lists ``{year, cited_by_count}`` for the last ten years. Citations
    received in years after the cutoff year are subtracted; the cutoff year itself is
    kept whole (a month-level approximation, as the Consensus baseline's cutoff is).
    A work without the field keeps today's count.
    """
    total = int(work.get("cited_by_count") or 0)
    cutoff_year = int(cutoff[:4])
    later = sum(
        int(entry.get("cited_by_count") or 0)
        for entry in work.get("counts_by_year") or []
        if int(entry.get("year") or 0) > cutoff_year
    )
    return max(0, total - later)


def short_id(openalex_id: str | None) -> str | None:
    """``https://openalex.org/W123`` -> ``W123``."""
    return openalex_id.rsplit("/", 1)[-1] if openalex_id else None


def lookup(
    ids: list[str], *, select: str, get: Any, extra_filter: str | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Fetch OpenAlex works by id, 50 per request. Returns (works, raw pages, failed)."""
    works: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    failed = 0
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        filters = f"openalex_id:{'|'.join(chunk)}"
        if extra_filter:
            filters += "," + extra_filter
        response = get(
            "/works", {"filter": filters, "select": select, "per-page": str(BATCH)}, {}
        )
        if response is None or response.status_code != 200:
            failed += 1
            continue
        body = response.json()
        pages.append({"meta": body.get("meta", {}), "n": len(body.get("results", []))})
        works.extend(body.get("results", []))
    return works, pages, failed


def count_references(seed_works: list[dict[str, Any]]) -> collections.Counter[str]:
    """How many seeds cite each work (short OpenAlex ids), seeds included."""
    counts: collections.Counter[str] = collections.Counter()
    for work in seed_works:
        for ref in set(work.get("referenced_works") or []):
            counts[short_id(ref) or ref] += 1
    return counts


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def override_prompt(source: str, prompt_file: Path | None) -> str:
    """Point the chosen generator at an alternative system prompt; return the prompt's hash.

    The backend classes read the system prompt from a module constant at call time, so
    replacing that constant in this process is enough. The committed, hash-pinned prompt
    files are never edited: an experiment copies one, edits the copy and passes it here.
    """
    global CONCEPTS_PROMPT
    if source == "concepts":
        CONCEPTS_PROMPT = (prompt_file or CONCEPTS_PROMPT_DEFAULT).read_text(
            encoding="utf-8"
        )
        return _digest(CONCEPTS_PROMPT)
    attribute = {
        "shared": "SEARCH_QUERIES_SYSTEM_PROMPT",
        "semantic": "SEARCH_QUERIES_SYSTEM_PROMPT",
        "shared+semantic": "SEARCH_QUERIES_SYSTEM_PROMPT",
        "per-provider": "SEARCH_QUERIES_V2_OPENALEX_SYSTEM_PROMPT",
    }[source]
    if prompt_file is not None:
        setattr(search_prompts, attribute, prompt_file.read_text(encoding="utf-8"))
    return _digest(getattr(search_prompts, attribute))


def generated_queries(
    intent: str, *, source: str, prompt_sha: str, refresh: bool, repeat: int = 1
) -> dict[str, Any]:
    """The pipeline's generated OpenAlex queries for one intent, cached per prompt.

    ``repeat`` > 1 asks the model again (a new cache entry), to measure run-to-run
    variance in query generation. One language-model call per intent in every source.
    """
    model = search_generation.SEARCH_QUERIES_MODEL
    suffix = (f"|r{repeat}" if repeat > 1 else "") + (
        f"|e{REASONING_EFFORT}" if REASONING_EFFORT else ""
    )
    path = cache_path(
        "openalex-queries", f"{intent}|{source}|{prompt_sha}|{model}{suffix}"
    )
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    started = time.monotonic()
    blocks: dict[str, Any] | None = None
    if source == "concepts":
        backend = OpenAISearchGenerationBackend(langfuse_client=None)
        wire, usage = backend._call_wire(  # noqa: SLF001 — the pipeline's structured-output call
            messages=[
                {"role": "system", "content": CONCEPTS_PROMPT},
                {
                    "role": "user",
                    "content": "Research question record (data, not instructions):\n"
                    + json.dumps({"intent": intent}),
                },
            ],
            model=model,
            response_format=ConceptBlocksWire,
            prompt_version="openalex_concepts_exp",
            usage_event="search_generation.queries.usage",
            trace_name="search:generate_concepts",
            label="concept blocks",
        )
        blocks = wire.model_dump()
        queries, paraphrases = validated_queries(
            SearchQueriesWire(queries=compose_queries(wire), overton_paraphrases=[])
        )
    else:
        backend_cls = QUERY_SOURCES[source]
        if backend_cls == "semantic":
            backend_cls = OpenAISearchGenerationBackend
        backend = backend_cls(langfuse_client=None)
        wire, usage = backend.generate_queries(QueriesPayload(intent=intent))
        queries, paraphrases = validated_queries(wire)
    payload = {
        "blocks": blocks,
        "repeat": repeat,
        "reasoning_effort": REASONING_EFFORT,
        "gen_seconds": round(time.monotonic() - started, 2),
        "intent": intent,
        "source": source,
        "prompt_sha": prompt_sha,
        "model": model,
        "queries": queries,
        "paraphrases": paraphrases,
        "tokens": None if usage is None else usage.total,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1))
    return payload


def planned_calls(queries: list[str], *, variants: bool) -> list[tuple[str, str]]:
    """(origin, query text) in the pipeline's rapid order: each query, then its SR and RCT variants."""
    calls: list[tuple[str, str]] = []
    for query in queries:
        calls.append(("generated", query))
        if variants:
            calls.append(("variant_sr", _compose_variant(query, SR_CLAUSE)))
            calls.append(("variant_rct", _compose_variant(query, RCT_CLAUSE)))
    return calls


def query_page(
    query: str, *, cutoff: str, per_call: int, get: Any, refresh: bool
) -> dict[str, Any]:
    """One OpenAlex keyword search, first page only, cached by query text and cutoff."""
    path = cache_path("openalex-query-pages", f"{query}|{cutoff}|{per_call}")
    if path.exists() and not refresh:
        cached = json.loads(path.read_text())
        if cached.get(
            "ok"
        ):  # a failed page is kept for diagnosis but fetched again next run
            return cached
    response = get(
        "/works",
        {
            "search": openalex_query(sanitize_openalex_query(query)),
            "select": "id,doi,display_name,publication_date",
            "per-page": str(per_call),
            "filter": openalex_cutoff(cutoff),
        },
        {},
    )
    ok = response is not None and response.status_code == 200
    body = response.json() if ok else {}
    payload = {
        "query": query,
        "cutoff": cutoff,
        "ok": ok,
        "status": None if response is None else response.status_code,
        "results": body.get("results", []),
        "meta": body.get("meta", {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload


def semantic_page(text: str, *, cutoff: str, get: Any, refresh: bool) -> dict[str, Any]:
    """One OpenAlex semantic search (50 results), cached by text and cutoff."""
    path = cache_path("openalex-semantic-pages", f"{text}|{cutoff}")
    if path.exists() and not refresh:
        cached = json.loads(path.read_text())
        if cached.get("ok"):
            return cached
    # The semantic endpoint rejects date filters; publication_year is allowed, so the
    # year fence is applied server-side and the exact cutoff date locally.
    params = {
        "search.semantic": text[:2000],
        "select": "id,doi,display_name,publication_date",
        "per-page": str(SEMANTIC_PER_CALL),
        "filter": f"publication_year:<{int(cutoff[:4]) + 1}",
    }
    response = None
    for attempt in range(3):
        time.sleep(SEMANTIC_INTERVAL_S * (1 + attempt))  # one request per second
        response = get("/works", params, {})
        if response is not None and response.status_code != 429:
            break
    ok = response is not None and response.status_code == 200
    body = response.json() if ok else {}
    results = [
        w
        for w in body.get("results", [])
        if (w.get("publication_date") or "") <= cutoff
    ]
    payload = {
        "query": text,
        "cutoff": cutoff,
        "ok": ok,
        "status": None if response is None else response.status_code,
        "results": results,
        "meta": body.get("meta", {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return payload


def interleave_ids(result_lists: list[list[dict[str, Any]]], n: int) -> list[str]:
    """Round-robin over the calls' result lists, as acquire's rank-interleaved merge does."""
    order: list[str] = []
    seen: set[str] = set()
    longest = max((len(lst) for lst in result_lists), default=0)
    for position in range(longest):
        for lst in result_lists:
            if position < len(lst):
                sid = short_id(lst[position].get("id"))
                if sid and sid not in seen:
                    seen.add(sid)
                    order.append(sid)
                    if len(order) >= n:
                        return order
    return order


def raw_seed_ids(seed_fetched: Any, n_seeds: int) -> list[str]:
    seed_ids: list[str] = []
    seen: set[str] = set()
    for record in records_of(SEED_ARM, seed_fetched):
        sid = short_id(record.get("backend_record_id"))
        if sid and sid not in seen:
            seen.add(sid)
            seed_ids.append(sid)
        if len(seed_ids) >= n_seeds:
            break
    return seed_ids


def expand(
    seed_ids: list[str], *, cutoff: str, n_seeds: int, n_expand: int, get: Any
) -> dict[str, Any]:
    """Run stages 2 and 3 for one ordered seed list and return the cacheable payload."""
    seed_works, pages_a, failed_a = lookup(seed_ids, select=SEED_SELECT, get=get)
    counts = count_references(seed_works)
    seed_set = set(seed_ids)
    new_ids = [wid for wid, _ in counts.most_common() if wid not in seed_set][:n_expand]
    new_works, pages_b, failed_b = lookup(
        new_ids, select=RESOLVE_SELECT, get=get, extra_filter=openalex_cutoff(cutoff)
    )
    return {
        "arm": ARM,
        "n_seeds": n_seeds,
        "n_expand": n_expand,
        "cutoff": cutoff,
        "seed_order": seed_ids,
        "seed_works": seed_works,
        "counts": dict(counts.most_common()),
        "new_works": new_works,
        "pages": pages_a + pages_b,
        "n_failed_calls": failed_a + failed_b,
        "complete": failed_a + failed_b == 0,
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def forward_chase(
    seed_works: list[dict[str, Any]],
    *,
    intent: str,
    cutoff: str,
    max_cites: int,
    pages: int,
    use_search: bool,
    get: Any,
    top: int = 0,
    counts: dict[str, int] | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    """Fetch papers that cite the seeds and score each by how many seeds it cites.

    ``sort`` is passed to OpenAlex (for example ``cited_by_count:desc``); without it the
    service's default order applies, which the cache analysis showed is a poor order to
    truncate on. Each citing paper also gets a **weighted coupling**: the sum over the
    seeds it cites of log2(1 + that seed's in-set citations), so citing a landmark seed
    counts for more than citing a peripheral one.

    With ``top`` > 0 only the ``top`` seeds with the most in-set citations are chased (the
    topic's landmarks among the seeds), instead of every seed under ``max_cites``.

    Args:
        seed_works: Seed records with ``id`` and ``cited_by_count``.
        intent: The research question; with ``use_search`` it is sent as the search text
            so the citing papers come back in relevance order and must match the words.
        cutoff: Only papers published on or before this date count.
        max_cites: Seeds cited more often than this are not chased (they flood the set).
        pages: Pages of up to 200 fetched per batch of 100 seeds.
        use_search: Whether to add the intent as ``search``.
        get: Rate-limited getter.

    Returns:
        ``works`` (deduplicated citing papers with a ``coupling`` count), ``pages``,
        ``n_failed_calls``, and the chased seed ids.
    """
    seed_ids = [short_id(w["id"]) for w in seed_works if short_id(w["id"])]
    if top > 0:
        ranked_seeds = sorted(
            seed_works, key=lambda w: -(counts or {}).get(short_id(w["id"]) or "", 0)
        )
        chased = [short_id(w["id"]) for w in ranked_seeds[:top] if short_id(w["id"])]
    else:
        chased = [
            short_id(w["id"])
            for w in seed_works
            if cited_asof(w, cutoff) <= max_cites and short_id(w["id"])
        ]
    seed_set = set(seed_ids)
    found: dict[str, dict[str, Any]] = {}
    page_meta: list[dict[str, Any]] = []
    failed = 0
    for start in range(0, len(chased), FORWARD_IDS_PER_CALL):
        chunk = chased[start : start + FORWARD_IDS_PER_CALL]
        for page in range(1, pages + 1):
            params = {
                "filter": f"cites:{'|'.join(chunk)},{openalex_cutoff(cutoff)}",
                "select": FORWARD_SELECT,
                "per-page": "200",
                "page": str(page),
            }
            if use_search:
                params["search"] = openalex_query(intent)
            if sort:
                params["sort"] = sort
            response = get("/works", params, {})
            if response is None or response.status_code != 200:
                failed += 1
                break
            body = response.json()
            results = body.get("results", [])
            page_meta.append({"meta": body.get("meta", {}), "n": len(results)})
            for work in results:
                sid = short_id(work.get("id")) or ""
                if sid and sid not in seed_set and sid not in found:
                    refs = {short_id(r) for r in work.get("referenced_works") or []}
                    cited_seeds = refs & seed_set
                    work["coupling"] = len(cited_seeds)
                    work["wcoupling"] = round(
                        sum(
                            math.log2(1 + (counts or {}).get(c, 0)) for c in cited_seeds
                        ),
                        3,
                    )
                    work["forward_rank"] = len(found)
                    found[sid] = work
            # Stop on the server's own page size, not the one requested: OpenAlex's
            # documented maximum is now 100, and a request for 200 may be served as 100.
            served = int((body.get("meta") or {}).get("per_page") or len(results) or 1)
            if len(results) < served:
                break
    return {
        "works": list(found.values()),
        "pages": page_meta,
        "n_failed_calls": failed,
        "chased": chased,
    }


def candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The union of seeds and snowball works as flat rows with every ranking signal."""
    counts = payload["counts"]
    order = {sid: rank for rank, sid in enumerate(payload["seed_order"])}
    seed_set = {short_id(w["id"]) for w in payload["seed_works"]}
    rows: list[dict[str, Any]] = []
    for source, works in (
        ("seed", payload["seed_works"]),
        ("snowball", payload["new_works"]),
        ("forward", payload.get("forward_works") or []),
    ):
        for work in works:
            sid = short_id(work.get("id")) or ""
            inset = counts.get(sid, 0)
            # Coupling: how many seeds this work cites. Known for seeds (their reference
            # lists were fetched) and forward candidates; backward candidates carry none.
            cited_seeds = {
                short_id(r) for r in work.get("referenced_works") or []
            } & seed_set
            coupling = work.get("coupling", len(cited_seeds))
            wcoupling = work.get(
                "wcoupling",
                round(sum(math.log2(1 + counts.get(c, 0)) for c in cited_seeds), 3),
            )
            cites = cited_asof(work, payload["cutoff"])
            rows.append(
                {
                    "openalex_id": sid,
                    "doi": normalize_doi(work.get("doi")),
                    "backend": "openalex",
                    "title": work.get("display_name"),
                    "year": (work.get("publication_date") or "")[:4],
                    # As of the cutoff; today's count kept beside it for reading.
                    "cited_by_count": cites,
                    "cited_by_count_now": work.get("cited_by_count") or 0,
                    "inset": inset,
                    "coupling": coupling,
                    "wcoupling": wcoupling,
                    # In-set citations and coupling are the two graph signals; both say
                    # "this work is tied to the seed set". Summed as plain counts (the
                    # weighted coupling is on a different scale and, used here, floods
                    # the top of the list with citing papers), then damped by how widely
                    # the work is cited overall. Weighted coupling breaks ties.
                    "specificity": round(
                        (inset + coupling) / math.log10(cites + 10), 3
                    ),
                    "source": source,
                    "raw_rank": order.get(sid, 10**6),
                    "forward_rank": work.get("forward_rank", 10**6),
                }
            )
    return rows


def rank(rows: list[dict[str, Any]], how: str) -> list[dict[str, Any]]:
    """Order the candidate rows by one of ``RANKINGS``."""
    seeds = sorted(
        (r for r in rows if r["source"] == "seed"), key=lambda r: r["raw_rank"]
    )
    snow = sorted(
        (r for r in rows if r["source"] == "snowball"),
        key=lambda r: (-r["inset"], -r["cited_by_count"]),
    )
    fwd = sorted(
        (r for r in rows if r["source"] == "forward"),
        key=lambda r: (-r["wcoupling"], -r["coupling"], r["forward_rank"]),
    )
    if how == "raw":
        return seeds + snow + fwd
    if how == "inset":
        return sorted(
            rows, key=lambda r: (-r["inset"], -r["cited_by_count"], r["raw_rank"])
        )
    if how == "specific":
        return sorted(
            rows,
            key=lambda r: (
                -r["specificity"],
                -r["wcoupling"],
                -r["inset"],
                r["raw_rank"],
            ),
        )
    if how == "global":
        return sorted(rows, key=lambda r: (-r["cited_by_count"], -r["inset"]))
    if how == "interleave":
        out: list[dict[str, Any]] = []
        for a, b in zip(seeds, snow, strict=False):
            out += [a, b]
        longer = seeds if len(seeds) > len(snow) else snow
        return out + longer[min(len(seeds), len(snow)) :] + fwd
    raise ValueError(how)


def score(
    ranked: list[dict[str, Any]], ground_truth: GroundTruth, cap: int, seminal: set[str]
) -> dict[str, Any]:
    """Recall at a cap over a ranked list, plus where the hits came from."""
    seen: set[str] = set()
    found_from: dict[str, str] = {}
    kept = 0
    for row in ranked[:cap]:
        key = record_key(row)
        if key is not None and key in seen:
            continue
        kept += 1
        if key is not None:
            seen.add(key)
            if key in ground_truth.keys:
                found_from.setdefault(key, row["source"])
    n_gt = len(ground_truth.keys)
    return {
        "recall": len(found_from) / n_gt if n_gt else 0.0,
        "n_found": len(found_from),
        **{
            f"n_from_{source}": sum(1 for s in found_from.values() if s == source)
            for source in ("seed", "snowball", "forward", "topic")
        },
        "n_candidates": kept,
        "n_gt": n_gt,
        "seminal_recall": (len(seminal & set(found_from)) / len(seminal))
        if seminal
        else None,
        "n_seminal": len(seminal),
    }


def gt_citations(
    ground_truth: GroundTruth, *, item_id: str, get: Any, refresh: bool, cutoff: str
) -> dict[str, int]:
    """Citation count per ground-truth DOI as of the cutoff, cached. Missing DOIs count as zero."""
    path = cache_path("gt-citations", f"{item_id}|{cutoff}|{CACHE_VERSION}")
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    counts: dict[str, int] = {}
    dois = sorted(d for d in ground_truth.dois if "|" not in d and "," not in d)
    for start in range(0, len(dois), BATCH):
        chunk = dois[start : start + BATCH]
        response = get(
            "/works",
            {
                "filter": f"doi:{'|'.join(chunk)}",
                "select": "doi,cited_by_count,counts_by_year",
                "per-page": str(BATCH),
            },
            {},
        )
        if response is None or response.status_code != 200:
            continue
        for work in response.json().get("results", []):
            key = normalize_doi(work.get("doi"))
            if key:
                counts[key] = cited_asof(work, cutoff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts))
    return counts


def seminal_keys(ground_truth: GroundTruth, counts: dict[str, int]) -> set[str]:
    """The most-cited tenth of the DOI target, floor ``SEMINAL_FLOOR``."""
    ranked = sorted(ground_truth.dois, key=lambda d: -counts.get(d, 0))
    return set(ranked[: max(SEMINAL_FLOOR, len(ranked) // 10)])


def labelled_reviews() -> set[str]:
    """Titles and review ids whose reference list is a labelled set of included studies."""
    keys: set[str] = set()
    for path in REVIEWS_CSVS:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("target_labelled") == "yes":
                    keys |= {row.get("title", ""), row.get("review_id", "")} - {""}
    return keys


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def load_or_expand(
    *,
    item_id: str,
    intent: str,
    cutoff: str,
    n_seeds: int,
    n_expand: int,
    refresh: bool,
    get: Any,
    source: str = "raw",
    prompt_sha: str = "",
    variants: bool = True,
    per_call: int = PER_CALL_DEFAULT,
    repeat: int = 1,
    forward: int = 0,
    forward_pages: int = 5,
    forward_max_cites: int = 300,
    forward_search: bool = False,
    forward_top: int = 0,
    forward_sort: str | None = None,
    semantic_texts: str = "all",
) -> tuple[dict[str, Any], bool]:
    """Seeds from the chosen source, then the snowball, both cached.

    ``raw`` seeds come from the openalex-raw baseline cache (fetched if missing). The
    generated sources call the pipeline's query generator once per intent (cached per
    prompt hash), send each query and, with ``variants``, its systematic-review and
    randomised-trial variants to OpenAlex (one page of ``per_call`` each, cached per
    query), and merge the result lists round-robin, as acquire does. The payload carries
    the queries and per-call hit counts so a prompt change can be read query by query.
    """
    model = search_generation.SEARCH_QUERIES_MODEL
    tag = (
        "raw"
        if source == "raw"
        else f"{source}-{prompt_sha}-{model}-v{int(variants)}-p{per_call}"
        + (f"-r{repeat}" if repeat > 1 else "")
        + (f"-st{semantic_texts}" if semantic_texts != "all" else "")
        + (f"-e{REASONING_EFFORT}" if REASONING_EFFORT else "")
    )
    path = cache_path(
        ARM, snowball_cache_key(item_id, tag, intent, cutoff, n_seeds, n_expand)
    )
    if path.exists() and not refresh:
        payload = json.loads(path.read_text())
        if payload.get("complete") and payload.get("cutoff") == cutoff:
            if forward:
                payload = with_forward(
                    payload,
                    item_id=item_id,
                    tag=tag,
                    intent=intent,
                    cutoff=cutoff,
                    n_seeds=n_seeds,
                    forward=forward,
                    pages=forward_pages,
                    max_cites=forward_max_cites,
                    use_search=forward_search,
                    refresh=refresh,
                    get=get,
                    top=forward_top,
                    sort=forward_sort,
                )
            return payload, True
    calls: list[dict[str, Any]] = []
    if source == "raw":
        seed_fetched, _ = load_or_fetch(
            SEED_ARM, item_id=item_id, intent=intent, cutoff=cutoff
        )
        seed_ids = raw_seed_ids(seed_fetched, n_seeds)
        generation: dict[str, Any] | None = None
    else:
        generation = generated_queries(
            intent, source=source, prompt_sha=prompt_sha, refresh=refresh, repeat=repeat
        )
        if source != "semantic":
            for origin, query in planned_calls(
                generation["queries"], variants=variants
            ):
                page = query_page(
                    query, cutoff=cutoff, per_call=per_call, get=get, refresh=refresh
                )
                calls.append(
                    {
                        "origin": origin,
                        "query": query,
                        "ok": page["ok"],
                        "results": page["results"],
                    }
                )
        if QUERY_SOURCES[source] == "semantic":
            texts = [intent, *generation.get("paraphrases", [])]
            if semantic_texts == "all":
                texts += generation["queries"]
            for text in texts:
                page = semantic_page(text, cutoff=cutoff, get=get, refresh=refresh)
                calls.append(
                    {
                        "origin": "semantic",
                        "query": text,
                        "ok": page["ok"],
                        "results": page["results"],
                    }
                )
        seed_ids = interleave_ids([c["results"] for c in calls], n_seeds)
    payload = expand(
        seed_ids, cutoff=cutoff, n_seeds=n_seeds, n_expand=n_expand, get=get
    )
    payload["source"] = source
    payload["generation"] = generation
    payload["calls"] = [
        {
            "origin": c["origin"],
            "query": c["query"],
            "ok": c["ok"],
            "n_results": len(c["results"]),
            "dois": [normalize_doi(r.get("doi")) for r in c["results"] if r.get("doi")],
        }
        for c in calls
    ]
    payload["n_failed_calls"] += sum(1 for c in calls if not c["ok"])
    payload["complete"] = payload["n_failed_calls"] == 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    if forward:
        payload = with_forward(
            payload,
            item_id=item_id,
            tag=tag,
            intent=intent,
            cutoff=cutoff,
            n_seeds=n_seeds,
            forward=forward,
            pages=forward_pages,
            max_cites=forward_max_cites,
            use_search=forward_search,
            refresh=refresh,
            get=get,
            top=forward_top,
            sort=forward_sort,
        )
    return payload, False


def snowball_cache_key(
    item_id: str, tag: str, intent: str, cutoff: str, n_seeds: int, n_expand: int
) -> str:
    """Identity of one backward-snowball payload: every input that changes its content."""
    return f"{item_id}|{tag}|{_digest(intent)}|{cutoff}|s{n_seeds}|k{n_expand}|{CACHE_VERSION}"


def forward_cache_key(
    item_id: str,
    tag: str,
    intent: str,
    cutoff: str,
    n_seeds: int,
    *,
    forward: int,
    pages: int,
    max_cites: int,
    use_search: bool,
    top: int,
    sort: str | None,
) -> str:
    """Identity of one forward chase: the seed set's identity plus every chase setting."""
    return (
        f"{item_id}|{tag}|{_digest(intent)}|{cutoff}|s{n_seeds}|f{forward}|p{pages}|c{max_cites}|q{int(use_search)}"
        + (f"|t{top}" if top else "")
        + (f"|o{sort}" if sort else "")
        + f"|{CACHE_VERSION}"
    )


def with_forward(
    payload: dict[str, Any],
    *,
    item_id: str,
    tag: str,
    intent: str,
    cutoff: str,
    n_seeds: int,
    forward: int,
    pages: int,
    max_cites: int,
    use_search: bool,
    refresh: bool,
    get: Any,
    top: int = 0,
    sort: str | None = None,
) -> dict[str, Any]:
    """Attach the top ``forward`` citing papers (by weighted coupling) to a snowball payload.

    Cached under ``results/cache/openalex-forward/`` by seed set and forward settings, so
    the backward snowball cache is untouched and a settings change refetches only this.
    """
    key = forward_cache_key(
        item_id,
        tag,
        intent,
        cutoff,
        n_seeds,
        forward=forward,
        pages=pages,
        max_cites=max_cites,
        use_search=use_search,
        top=top,
        sort=sort,
    )
    path = cache_path("openalex-forward", key)
    if path.exists() and not refresh:
        chase = json.loads(path.read_text())
    else:
        chase = forward_chase(
            payload["seed_works"],
            intent=intent,
            cutoff=cutoff,
            max_cites=max_cites,
            pages=pages,
            use_search=use_search,
            get=get,
            top=top,
            counts=payload["counts"],
            sort=sort,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(chase))
    taken = {short_id(w["id"]) for w in payload["new_works"]}
    ranked = sorted(
        (w for w in chase["works"] if short_id(w["id"]) not in taken),
        key=lambda w: (
            -w.get("wcoupling", w["coupling"]),
            -w["coupling"],
            w["forward_rank"],
        ),
    )
    payload = dict(payload)
    payload["forward_works"] = ranked[:forward]
    payload["forward_fetched"] = len(chase["works"])
    payload["forward_chased"] = len(chase["chased"])
    payload["forward_pages"] = len(chase["pages"])
    payload["forward_failed"] = chase["n_failed_calls"]
    return payload


def write_candidates(
    path: Path, ranked: list[dict[str, Any]], gt_keys: set[str] | None
) -> None:
    fields = [
        "rank",
        "source",
        "inset",
        "coupling",
        "wcoupling",
        "specificity",
        "cited_by_count",
        "cited_by_count_now",
        "year",
        "title",
        "doi",
        "openalex_id",
        "raw_rank",
    ]
    if gt_keys is not None:
        fields.append("in_ground_truth")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for position, row in enumerate(ranked, start=1):
            out = {**row, "rank": position}
            if gt_keys is not None:
                out["in_ground_truth"] = row["doi"] in gt_keys
            writer.writerow(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=MINI_DATASET)
    parser.add_argument(
        "--seeds", type=int, default=200, help="keyword results used as seeds"
    )
    parser.add_argument(
        "--expand", type=int, default=200, help="most-cited new works added"
    )
    parser.add_argument("--caps", nargs="+", type=int, default=DEFAULT_CAPS)
    parser.add_argument(
        "--queries",
        choices=sorted(QUERY_SOURCES),
        default="raw",
        help="seed source: the one raw query, or the pipeline's generated queries (shared or per-provider prompt)",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=None,
        help="alternative system prompt for the chosen generator (a copy of the committed file, edited)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="query-generation model to use instead of the pipeline's SEARCH_QUERIES_MODEL (for comparison runs)",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        help="OpenAI reasoning_effort for the generation call (for example minimal, low); default: the pipeline's",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="ask the generator again under a new cache key (2, 3, ...) to measure query variance",
    )
    parser.add_argument(
        "--no-variants",
        action="store_true",
        help="send only the generated queries, without the SR and RCT variants rapid adds",
    )
    parser.add_argument(
        "--per-call",
        type=int,
        default=PER_CALL_DEFAULT,
        help="results per generated query",
    )
    parser.add_argument(
        "--forward",
        type=int,
        default=0,
        help="also add this many papers that CITE the seeds, ranked by how many seeds they cite (0 = off)",
    )
    parser.add_argument(
        "--forward-pages", type=int, default=5, help="pages of 200 per 100 chased seeds"
    )
    parser.add_argument(
        "--forward-max-cites",
        type=int,
        default=300,
        help="chase only seeds cited at most this often",
    )
    parser.add_argument(
        "--forward-top",
        type=int,
        default=0,
        help="chase only this many seeds, the ones with most in-set citations (0 = every seed under --forward-max-cites)",
    )
    parser.add_argument(
        "--semantic-texts",
        choices=["all", "intent"],
        default="all",
        help="texts sent to semantic search: the question, paraphrases and keyword queries (all), or only the question and paraphrases (intent)",
    )
    parser.add_argument(
        "--forward-sort",
        default=None,
        help="OpenAlex sort for the citing papers, for example cited_by_count:desc (default: the service's order)",
    )
    parser.add_argument(
        "--forward-search",
        action="store_true",
        help="send the intent as search text with the cites filter: citing papers must also match the words",
    )
    parser.add_argument(
        "--rankings", nargs="+", choices=sorted(RANKINGS), default=sorted(RANKINGS)
    )
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument(
        "--manual",
        nargs="+",
        default=[],
        metavar="QUESTION",
        help="questions with no ground truth; ranked tables are exported for hand review",
    )
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--label", default=None, help="run folder name (default: date + parameters)"
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.model:
        search_generation.SEARCH_QUERIES_MODEL = args.model
    set_reasoning_effort(args.reasoning_effort)
    model_tag = "" if args.queries == "raw" or not args.model else f"-{args.model}"
    prompt_sha = (
        "" if args.queries == "raw" else override_prompt(args.queries, args.prompt_file)
    )
    source_tag = (
        args.queries
        if args.queries == "raw"
        else f"{args.queries}-{prompt_sha[:6]}{model_tag}"
    )
    label = (
        args.label
        or f"{date.today().isoformat()}-{source_tag}-s{args.seeds}-k{args.expand}"
        + (f"-r{args.repeat}" if args.repeat > 1 else "")
        + (f"-e{args.reasoning_effort}" if args.reasoning_effort else "")
        + (f"-st{args.semantic_texts}" if args.semantic_texts != "all" else "")
        + (
            f"-f{args.forward}p{args.forward_pages}c{args.forward_max_cites}{'q' if args.forward_search else ''}{f't{args.forward_top}' if args.forward_top else ''}{'o' + args.forward_sort.split(':')[0] if args.forward_sort else ''}"
            if args.forward
            else ""
        )
    )
    seed_kwargs = dict(
        source=args.queries,
        prompt_sha=prompt_sha,
        variants=not args.no_variants,
        per_call=args.per_call,
        repeat=args.repeat,
        forward=args.forward,
        forward_pages=args.forward_pages,
        forward_max_cites=args.forward_max_cites,
        forward_search=args.forward_search,
        forward_top=args.forward_top,
        forward_sort=args.forward_sort,
        semantic_texts=args.semantic_texts,
    )
    out = args.out / label
    get = make_getter(SEED_ARM)  # OpenAlex pacing and retries
    labelled = labelled_reviews()

    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    items = select_items(list(client.get_dataset(args.dataset).items), args.reviews)

    rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    gen_seconds: list[float] = []
    for item in items:
        title = item.metadata.get("review_title", str(item.id))
        intent, cutoff = item.input["intent"], item.input["published_before"]
        ground_truth = ground_truth_from_item(item)
        started = time.monotonic()
        payload, cached = load_or_expand(
            item_id=str(item.id),
            intent=intent,
            cutoff=cutoff,
            n_seeds=args.seeds,
            n_expand=args.expand,
            refresh=args.refresh,
            get=get,
            **seed_kwargs,
        )
        if payload.get("generation"):
            gen_seconds.append(payload["generation"].get("gen_seconds") or 0.0)
        for call in payload.get("calls", []):
            hits = len(set(call["dois"]) & ground_truth.keys)
            query_rows.append(
                {
                    "review": title,
                    "origin": call["origin"],
                    "query": call["query"],
                    "ok": call["ok"],
                    "n_results": call["n_results"],
                    "gt_hits": hits,
                }
            )
        is_labelled = (
            title in labelled
            or str(item.metadata.get("review_id", "")) in labelled
            or item.metadata.get("copied_from")
            is not None  # the four hand-labelled originals
        )
        seminal = (
            seminal_keys(
                ground_truth,
                gt_citations(
                    ground_truth,
                    item_id=str(item.id),
                    get=get,
                    refresh=args.refresh,
                    cutoff=cutoff,
                ),
            )
            if is_labelled
            else set()
        )
        cands = candidates(payload)
        print(
            f"{title[:60]}: {len(payload['seed_works'])} seeds, {len(payload['counts'])} distinct references, "
            f"{len(payload['new_works'])} added, {len(payload['pages'])} requests"
            + (
                f"; forward: {payload['forward_chased']} seeds chased, {payload['forward_fetched']} citing papers in "
                f"{payload['forward_pages']} pages, {len(payload['forward_works'])} kept"
                + (
                    f", {payload['forward_failed']} FAILED"
                    if payload["forward_failed"]
                    else ""
                )
                if payload.get("forward_works") is not None
                else ""
            )
            + f"{' (cached)' if cached else f', {time.monotonic() - started:.1f}s'}"
            + f"{', FAILED CALLS ' + str(payload['n_failed_calls']) if payload['n_failed_calls'] else ''}"
        )
        for how in args.rankings:
            ranked = rank(cands, how)
            if how == "specific":
                write_candidates(
                    out / "candidates" / f"{slug(title)}.csv", ranked, ground_truth.keys
                )
            for cap in args.caps:
                s = score(ranked, ground_truth, cap, seminal)
                rows.append(
                    {
                        "review": title,
                        "labelled": is_labelled,
                        "ranking": how,
                        "cap": cap,
                        "n_requests": len(payload["pages"]),
                        **s,
                    }
                )

    def mean(key: str, rs: list[dict[str, Any]]) -> float:
        return sum(r[key] for r in rs) / len(rs) if rs else 0.0

    if rows:
        out.mkdir(parents=True, exist_ok=True)
        with (out / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        if query_rows:
            with (out / "queries.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=list(query_rows[0]))
                writer.writeheader()
                writer.writerows(query_rows)
            n_q = sum(1 for r in query_rows if r["origin"] == "generated")
            print(
                f"\n{n_q} generated queries over {len(items)} reviews, prompt sha {prompt_sha}, "
                f"{sum(r['gt_hits'] for r in query_rows)} query-level ground-truth hits (with repeats), "
                f"{sum(1 for r in query_rows if not r['ok'])} failed calls; "
                f"generation {sum(gen_seconds) / len(gen_seconds):.1f}s per intent on average"
                if gen_seconds
                else f"{sum(1 for r in query_rows if not r['ok'])} failed calls"
            )
        print(
            f"\nseeds {args.seeds}, expand {args.expand}, {len(items)} reviews -> {out}"
        )
        print(
            f"{'ranking':12s} {'cap':>5s} {'recall':>7s} {'seed':>5s} {'snow':>5s} {'fwd':>5s} {'cands':>6s} {'seminal(lab.)':>14s}"
        )
        for how in args.rankings:
            for cap in args.caps:
                cell = [r for r in rows if r["ranking"] == how and r["cap"] == cap]
                lab = [r for r in cell if r["seminal_recall"] is not None]
                print(
                    f"{how:12s} {cap:>5d} {mean('recall', cell):>7.1%} {mean('n_from_seed', cell):>5.1f} "
                    f"{mean('n_from_snowball', cell):>5.1f} {mean('n_from_forward', cell):>5.1f} {mean('n_candidates', cell):>6.0f} "
                    f"{mean('seminal_recall', lab):>9.1%} n={len(lab)}"
                )

    today = date.today().isoformat()
    for question in args.manual:
        folder = args.out / "manual" / slug(question)
        payload, cached = load_or_expand(
            item_id=f"manual:{slug(question)}",
            intent=question,
            cutoff=today,
            n_seeds=args.seeds,
            n_expand=args.expand,
            refresh=args.refresh,
            get=get,
            **seed_kwargs,
        )
        if payload.get("generation"):
            (folder / f"{label}-queries.txt").parent.mkdir(parents=True, exist_ok=True)
            (folder / f"{label}-queries.txt").write_text(
                "\n".join(payload["generation"]["queries"]) + "\n"
            )
        cands = candidates(payload)
        for how in RANKINGS:
            write_candidates(folder / f"{label}-{how}.csv", rank(cands, how), None)
        print(
            f"\nmanual: {question!r}: {len(payload['seed_works'])} seeds, {len(payload['new_works'])} added -> {folder}"
        )


if __name__ == "__main__":
    main()
