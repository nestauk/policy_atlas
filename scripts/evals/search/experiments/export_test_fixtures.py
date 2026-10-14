"""Write the task 051 test fixtures from recorded experiment data (plan Phase 0c, S12).

Two fixture sets, both deterministic (a second run writes identical files):

1. ``backend/tests/data/pool_fixture.json`` — the paper pool of one mini-set review
   (the loneliness review) from the Luna run of experiment 1
   (``results/snowball/2026-10-09-shared+semantic-c6e320-gpt-5.6-luna-s200-k200-f200p10c300t20``),
   trimmed, with the order the experiment's own ranking gives on the trimmed set:

   - seeds: the first 60 of the 200 seeds, in seed order;
   - each seed's ``referenced_works`` trimmed to the 100 ids the 60 seeds cite most;
   - backward: the resolved records for those 100 ids that are not seeds (from the
     experiment's resolved set, so an id the full run never resolved is left out);
   - forward: the first 80 of the run's ranked citing works, their ``coupling``,
     ``wcoupling`` and ``forward_rank`` removed so the oracle recomputes them on the
     trimmed seed set, their ``referenced_works`` trimmed to the trimmed seeds;
   - every record reduced to ``id``, ``doi``, ``display_name``, ``publication_date``,
     ``cited_by_count`` and (seeds, forward) ``referenced_works``. ``cited_by_count``
     is the count as of the review's cutoff (``counts_by_year`` folded in and
     dropped), so the oracle and production read the same number;
   - ``expected_order``: ``rank(candidates(trimmed), "specific")`` from
     ``snowball_recall.py``; ``expected_rows`` carries each candidate's signals.

   Read from ``results/cache/openalex-snowball/`` and ``openalex-forward/`` through
   ``load_or_expand`` with the experiment's exact settings; the script stops if the
   cache is missing rather than fetch.

2. ``backend/tests/data/policy_replay/<slug>.json`` — one file per task 049 manual
   question (obesity, decarbonising heating, early years attainment): the three
   Overton result lists (the question and its two cached paraphrases, relevance
   order, first page of 50 trimmed to 40), the 15 landmark records, and the expected
   outputs of each pool step. Three synthetic records are appended to the third list:
   two duplicates by title of records in the first two lists (new ids, the title with
   different case and punctuation) and one titleless record. Records carry only
   ``policy_document_id``, ``title``, ``translated_title``, ``published_on``,
   ``es_score``, ``citation_count``, ``source.{title,type,country}`` and
   ``cites.policy[].overton_id``. No snippet, no description, no full text.

   The raw Overton pages are fetched once and cached under
   ``results/cache/overton-replay-051/`` (git-ignored); the paraphrases come from the
   task 047 generation cache (a miss costs one language-model call per question).

   ``expected``: ``interleaved`` (round-robin by rank, first occurrence by id),
   ``deduplicated`` (title duplicates dropped, the first copy kept, titleless kept),
   ``result_ids`` (the deduplicated ids, the set landmarks must not be in),
   ``landmarks`` (the 15 ids most cited by the deduplicated results and not among
   them), ``specific`` (results and landmarks by in-set / log10(citation_count + 10),
   ties by in-set count then position, landmarks after results; computed by
   ``policy_rank.order``), ``uk_only`` (the ``specific`` order kept to
   ``source.country == "UK"``), ``cut_50`` (the first 50 of ``specific``).

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/export_test_fixtures.py

Needs the Langfuse keys (for the loneliness item) and the Overton key (first run
only). Nothing is uploaded.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR, make_getter
from evals_search_utils import DEFAULT_DATASET, select_items
from overton_recall import generated_texts, get as overton_get
from policy_rank import order as policy_order
from snowball_recall import (
    SEED_ARM,
    candidates,
    cited_asof,
    count_references,
    load_or_expand,
    override_prompt,
    rank,
    short_id,
    slug,
)

import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing
from policy_atlas.evidence_search.sourcing import search_generation

DATA_DIR = Path(__file__).resolve().parents[4] / "backend" / "tests" / "data"
POOL_FIXTURE = DATA_DIR / "pool_fixture.json"
REPLAY_DIR = DATA_DIR / "policy_replay"
REPLAY_CACHE = CACHE_DIR / "overton-replay-051"

LONELINESS = "loneliness"
QUERY_MODEL = "gpt-5.6-luna"
N_SEEDS, N_REF_IDS, N_FORWARD = 60, 100, 80
QUESTIONS = [
    "Policies to reduce obesity in the UK",
    "Interventions to decarbonise heating",
    "Interventions to improve early years attainment",
]
PER_LIST, N_LANDMARKS, CUT = 40, 15, 50


# --- 1. paper pool ----------------------------------------------------------------


def _slim_work(
    work: dict[str, Any], cutoff: str, keep_refs: set[str] | None
) -> dict[str, Any]:
    out = {
        "id": work["id"],
        "doi": work.get("doi"),
        "display_name": work.get("display_name"),
        "publication_date": work.get("publication_date"),
        "cited_by_count": cited_asof(work, cutoff),
    }
    if keep_refs is not None:
        out["referenced_works"] = [
            ref
            for ref in work.get("referenced_works") or []
            if (short_id(ref) or ref) in keep_refs
        ]
    return out


def _ordered_counts(seeds: list[dict[str, Any]]) -> collections.Counter[str]:
    """``count_references`` with ties in first-appearance order.

    The experiment iterates each seed's references as a set, so two ids with the same
    count come out in an order that changes from one process to the next (string
    hashing). Walking the lists in seed order makes the fixture deterministic and
    gives the production rule its oracle: ties by first appearance.
    """
    counts: collections.Counter[str] = collections.Counter()
    for work in seeds:
        for ref in dict.fromkeys(work.get("referenced_works") or []):
            counts[short_id(ref) or ref] += 1
    return counts


def export_pool() -> None:
    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST"
        )
    item = select_items(
        list(client.get_dataset(DEFAULT_DATASET + "-mini").items), [LONELINESS]
    )[0]
    intent, cutoff = item.input["intent"], item.input["published_before"]

    search_generation.SEARCH_QUERIES_MODEL = QUERY_MODEL
    payload, cached = load_or_expand(
        item_id=str(item.id),
        intent=intent,
        cutoff=cutoff,
        n_seeds=200,
        n_expand=200,
        refresh=False,
        get=make_getter(SEED_ARM),
        source="shared+semantic",
        prompt_sha=override_prompt("shared+semantic", None),
        variants=True,
        per_call=200,
        forward=200,
        forward_pages=10,
        forward_max_cites=300,
        forward_top=20,
        semantic_texts="all",
    )
    if not cached:
        raise SystemExit(
            "the experiment-1 Luna cache for the loneliness review is missing"
        )

    by_id = {short_id(w["id"]): w for w in payload["seed_works"]}
    seed_order = [sid for sid in payload["seed_order"] if sid in by_id][:N_SEEDS]
    seed_set = set(seed_order)
    full_counts = _ordered_counts([by_id[sid] for sid in seed_order])
    keep_refs = {wid for wid, _ in full_counts.most_common(N_REF_IDS)}
    seeds = [_slim_work(by_id[sid], cutoff, keep_refs) for sid in seed_order]
    counts = _ordered_counts(seeds)
    assert counts == count_references(seeds)  # same numbers, deterministic order
    resolved = {short_id(w["id"]): w for w in payload["new_works"]}
    backward = [
        _slim_work(resolved[wid], cutoff, None)
        for wid, _ in counts.most_common()
        if wid not in seed_set and wid in resolved
    ]
    forward = []
    for work in payload["forward_works"][:N_FORWARD]:
        slim = _slim_work(work, cutoff, seed_set)
        forward.append(slim)

    trimmed = {
        "cutoff": cutoff,
        "seed_order": seed_order,
        "seed_works": seeds,
        "counts": dict(counts.most_common()),
        "new_works": backward,
        "forward_works": forward,
    }
    ranked = rank(candidates(trimmed), "specific")
    fixture = {
        "source": {
            "review": item.metadata.get("review_title"),
            "run": "results/snowball/2026-10-09-shared+semantic-c6e320-gpt-5.6-luna-s200-k200-f200p10c300t20",
            "trim": f"seeds {N_SEEDS}, reference ids {N_REF_IDS}, forward {N_FORWARD}",
        },
        "cutoff": cutoff,
        "seed_order": seed_order,
        "seeds": seeds,
        "backward": backward,
        "forward": forward,
        "counts": trimmed["counts"],
        "expected_backward_targets": [
            wid for wid, _ in counts.most_common() if wid not in seed_set
        ],
        "expected_order": [row["openalex_id"] for row in ranked],
        "expected_rows": [
            {
                key: row[key]
                for key in (
                    "openalex_id",
                    "source",
                    "inset",
                    "coupling",
                    "wcoupling",
                    "cited_by_count",
                    "specificity",
                    "raw_rank",
                )
            }
            for row in ranked
        ],
    }
    POOL_FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")

    # Self-check from the written file, not the in-memory objects.
    back = json.loads(POOL_FIXTURE.read_text())
    again = rank(
        candidates(
            {
                "cutoff": back["cutoff"],
                "seed_order": back["seed_order"],
                "seed_works": back["seeds"],
                "counts": back["counts"],
                "new_works": back["backward"],
                "forward_works": back["forward"],
            }
        ),
        "specific",
    )
    assert [r["openalex_id"] for r in again] == back["expected_order"]
    print(
        f"pool fixture: {len(seeds)} seeds, {len(backward)} backward, {len(forward)} forward, "
        f"{len(back['expected_order'])} ranked -> {POOL_FIXTURE}"
    )


# --- 2. policy replay --------------------------------------------------------------


def _cached_overton(name: str, **params: str) -> dict[str, Any]:
    key = hashlib.sha256(
        json.dumps([name, params], sort_keys=True).encode()
    ).hexdigest()[:16]
    path = REPLAY_CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    body = overton_get(name, **params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))
    return body


def _slim_doc(doc: dict[str, Any]) -> dict[str, Any]:
    source = doc.get("source") or {}
    return {
        "policy_document_id": doc.get("policy_document_id"),
        "title": doc.get("title"),
        "translated_title": doc.get("translated_title"),
        "published_on": doc.get("published_on"),
        "es_score": doc.get("es_score"),
        "citation_count": int(doc.get("citation_count") or 0),
        "source": {
            "title": source.get("title"),
            "type": source.get("type"),
            "country": source.get("country"),
        },
        "cites": {
            "policy": [
                {"overton_id": p.get("overton_id")}
                for p in (doc.get("cites") or {}).get("policy") or []
                if p.get("overton_id")
            ]
        },
    }


def _title_of(doc: dict[str, Any]) -> str:
    return doc.get("translated_title") or doc.get("title") or ""


def normalised_title(text: str) -> str:
    """Lower-case, punctuation and whitespace collapsed (the contract's D8 rule)."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def _duplicate(doc: dict[str, Any], suffix: str) -> dict[str, Any]:
    """A copy with a new id and the same title in different case and punctuation."""
    out = json.loads(json.dumps(doc))
    out["policy_document_id"] = f"{doc['policy_document_id']}-{suffix}"
    out["title"] = _title_of(doc).upper().replace(" ", "  ") + "."
    out["translated_title"] = None
    out["es_score"] = (doc.get("es_score") or 0) - 0.01
    return out


def _interleave(lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position in range(max(len(lst) for lst in lists)):
        for lst in lists:
            if position < len(lst) and lst[position]["policy_document_id"] not in seen:
                seen.add(lst[position]["policy_document_id"])
                out.append(lst[position])
    return out


def _dedupe(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        key = normalised_title(_title_of(doc)) or doc["policy_document_id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out


def _as_policy_rank_doc(
    doc: dict[str, Any], position: int, inset: int
) -> dict[str, Any]:
    return {
        "id": doc["policy_document_id"],
        "rel_rank": position,
        "inset": inset,
        "specific": round(inset / math.log10(doc["citation_count"] + 10), 3),
        "coupling": 0,
        "forward": 0,
    }


def export_replay(question: str) -> None:
    texts = [question, *generated_texts(question)["paraphrases"]]
    lists = []
    for text in texts:
        body = _cached_overton(
            "documents.php",
            squery=text,
            min_similarity="0.3",
            sort="relevance",
            pp="50",
            page="1",
        )
        lists.append([_slim_doc(d) for d in body["results"][:PER_LIST]])
    synthetic = {
        "duplicates": [
            _duplicate(lists[0][5], "dup-a"),
            _duplicate(lists[1][7], "dup-b"),
        ],
        "titleless": {
            **_slim_doc({}),
            "policy_document_id": "synthetic-titleless-1",
            "citation_count": 3,
            "es_score": 0.5,
            "source": {"title": "Synthetic", "type": "other", "country": "UK"},
        },
    }
    lists[2] = [*lists[2], *synthetic["duplicates"], synthetic["titleless"]]

    interleaved = _interleave(lists)
    deduplicated = _dedupe(interleaved)
    result_ids = [d["policy_document_id"] for d in deduplicated]
    cites = collections.Counter(
        p["overton_id"]
        for d in deduplicated
        for p in {c["overton_id"]: c for c in d["cites"]["policy"]}.values()
    )
    landmark_ids = [p for p, _ in cites.most_common() if p not in set(result_ids)][
        :N_LANDMARKS
    ]
    landmarks = []
    for doc_id in landmark_ids:
        body = _cached_overton("documents.php", policy_document_id=doc_id, pp="1")
        results = body.get("results") or []
        if results:
            landmarks.append(_slim_doc(results[0]))
    found_ids = [d["policy_document_id"] for d in landmarks]

    ranked_in = [
        _as_policy_rank_doc(d, position, cites.get(d["policy_document_id"], 0))
        for position, d in enumerate(deduplicated, start=1)
    ] + [
        _as_policy_rank_doc(d, 10**6, cites.get(d["policy_document_id"], 0))
        for d in landmarks
    ]
    specific = [d["id"] for d in policy_order(ranked_in, "specific")]
    country = {
        d["policy_document_id"]: d["source"]["country"]
        for d in [*deduplicated, *landmarks]
    }
    fixture = {
        "question": question,
        "texts": texts,
        "result_lists": lists,
        "landmark_records": landmarks,
        "synthetic_ids": [
            d["policy_document_id"]
            for d in [*synthetic["duplicates"], synthetic["titleless"]]
        ],
        "expected": {
            "interleaved": [d["policy_document_id"] for d in interleaved],
            "deduplicated": result_ids,
            "result_ids": result_ids,
            "landmarks": landmark_ids,
            "landmarks_found": found_ids,
            "inset": {
                k: v for k, v in cites.items() if k in set(result_ids) | set(found_ids)
            },
            "specific": specific,
            "uk_only": [i for i in specific if country.get(i) == "UK"],
            "cut_50": specific[:CUT],
        },
    }
    path = REPLAY_DIR / f"{slug(question)}.json"
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=1) + "\n")
    back = json.loads(path.read_text())
    assert back["expected"]["specific"] == specific
    print(
        f"replay fixture: {question!r}: {[len(lst) for lst in lists]} results, "
        f"{len(deduplicated)} after dedup, {len(landmarks)}/{len(landmark_ids)} landmarks -> {path}"
    )


def main() -> None:
    export_pool()
    for question in QUESTIONS:
        export_replay(question)


if __name__ == "__main__":
    main()
