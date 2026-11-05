#!/usr/bin/env python3
"""Check that chunk retrieval returns the same top 8 as a saved reference (task 057, D7).

What this answers
-----------------
Task 057 moved the ``search_chunks`` retrieval from Python into one SQL statement.
The rule is parity: for the same task, scope and query, the new retriever must return
the same eight chunks in the same order as the old one. This script runs a list of
queries through the retriever of whatever code you run it from and either

- **compares** the eight chunk ids with each query's reference list and prints a
  markdown table (query, same top 8 in order yes/no, the first difference, and how
  long the search took), or
- **writes a reference** (``--write-reference``): a copy of the queries file with each
  query's ``reference_top8`` filled from this code's retriever. Run it this way from
  a checkout of the commit before the change (the Python retriever) to make the
  reference, then compare from the new code.

It only reads the database: every connection it opens is read-only.

The queries file (JSON)
-----------------------
::

    {
      "task_id": "<task uuid>",
      "scope_id": "<evidence scope uuid>",
      "extra_scope_ids": [],              # optional: further scopes, as chat uses them
      "selected_tss_ids": [],             # optional: the run's selection (a soft prior)
      "selection_reference_resolved": false,   # optional: true when a selection ran
      "retrieval_boosts": {},             # optional: the directive's retrieval_boosts
      "queries": [
        {"id": "q1", "query": "words the writer searched for",
         "vector": [...1536 numbers...],  # optional: else embedded live
         "filters": {"doc_ids": [], "evidence_types": [], "tags": []},  # optional
         "reference_top8": ["chunk uuid", ...]}   # needed to compare
      ]
    }

Fill ``queries`` from the Langfuse ``search_chunks`` tool calls of a run (their
arguments and the chunk ids they returned) or from the feasibility study's saved
queries (``qid`` -> ``id``, ``product_top8`` -> ``reference_top8``, vectors from its
``query_vectors.json``). A query without ``vector`` is embedded with the app's
configured embedding backend, which must match the profile the chunks were embedded
with (the ``embedding_profile`` column).

Usage
-----
From the repository root, with ``DATABASE_URL`` pointing at the database to read::

    uv run --project backend python scripts/retrieval_parity.py queries.json
    uv run --project backend python scripts/retrieval_parity.py queries.json \\
        --write-reference reference.json
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from policy_atlas.evidence_search.synthesis import synthesis_tools
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    ChunkRetriever,
    PassThroughChunkReranker,
    SynthesisDirective,
    build_retrieval_scope,
    parse_synthesis_directive,
)


class _GivenVectors:
    """Embedder that returns the queries file's vectors, else asks the live one."""

    mode = "given"

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors
        self._live: Any = None

    def embed_texts(self, texts: list[str], *, kind: str = "query") -> list[list[float]]:
        missing = [text for text in texts if text not in self._vectors]
        if missing:
            if self._live is None:
                from policy_atlas.core.embeddings import live_embedding_backend

                self._live = live_embedding_backend()
            for text, vector in zip(
                missing, self._live.embed_texts(missing, kind=kind), strict=True
            ):
                self._vectors[text] = vector
        return [self._vectors[text] for text in texts]


def _filters(raw: dict[str, Any] | None) -> Any:
    if not raw:
        return None
    return synthesis_tools._ChunkScopeFilters(  # noqa: SLF001 - the tool's own filter record
        doc_ids=frozenset(raw["doc_ids"]) if raw.get("doc_ids") else None,
        evidence_types=frozenset(raw["evidence_types"]) if raw.get("evidence_types") else None,
        tags=frozenset(raw["tags"]) if raw.get("tags") else None,
    )


def _first_difference(got: list[str], reference: list[str]) -> str:
    for position, (mine, theirs) in enumerate(zip(got, reference, strict=False), start=1):
        if mine != theirs:
            return f"#{position}: {mine[:8]} vs reference {theirs[:8]}"
    if len(got) != len(reference):
        return f"{len(got)} results vs reference {len(reference)}"
    return ""


def main() -> int:
    """Run the queries and print the comparison table, or write the reference.

    Returns:
        0 when every compared query matches (or a reference was written), else 1.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("queries", type=Path, help="the queries file (JSON)")
    parser.add_argument(
        "--write-reference", type=Path, help="write the queries file with reference_top8 filled"
    )
    args = parser.parse_args()
    spec = json.loads(args.queries.read_text())
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    # Every session this engine opens is read-only.
    engine = create_engine(
        url, connect_args={"options": "-c default_transaction_read_only=on"}
    )
    boosts = spec.get("retrieval_boosts")
    directive = (
        parse_synthesis_directive(
            {"synthesis": {"retrieval_boosts": boosts}}, grouping_group_ids=None
        )
        if boosts
        else SynthesisDirective()
    )
    scope_kwargs: dict[str, Any] = {
        "task_id": uuid.UUID(spec["task_id"]),
        "scope_id": uuid.UUID(spec["scope_id"]),
        "selected_tss_ids": {uuid.UUID(value) for value in spec.get("selected_tss_ids", [])},
        "extra_scope_ids": [uuid.UUID(value) for value in spec.get("extra_scope_ids", [])],
    }
    # The SQL retriever reads through a connection factory; the Python retriever
    # before task 057 has no such argument, so the script runs at both commits.
    if "connect" in inspect.signature(build_retrieval_scope).parameters:
        scope_kwargs["connect"] = engine.connect
    with engine.connect() as conn:
        scope = build_retrieval_scope(conn, **scope_kwargs)
    queries = spec["queries"]
    embedder = _GivenVectors(
        {item["query"]: item["vector"] for item in queries if item.get("vector")}
    )
    retriever = ChunkRetriever(
        scope,
        embedder=embedder,
        directive=directive,
        reranker=PassThroughChunkReranker(),
        selection_reference_resolved=bool(spec.get("selection_reference_resolved")),
    )
    # Embed every query first, so the timings below are the search alone.
    retriever.warm_queries([item["query"] for item in queries])

    rows: list[tuple[str, str, str, str, float]] = []
    timings: list[float] = []
    all_match = True
    for item in queries:
        started = time.perf_counter()
        results = retriever.search(item["query"], filters=_filters(item.get("filters")))
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings.append(elapsed_ms)
        got = [result["chunk_record_id"] for result in results]
        if args.write_reference:
            item["reference_top8"] = got
            continue
        reference = item.get("reference_top8")
        if reference is None:
            rows.append((item["id"], item["query"], "no reference", "", elapsed_ms))
            all_match = False
            continue
        same = got == reference
        all_match = all_match and same
        rows.append((
            item["id"],
            item["query"],
            "yes" if same else "no",
            _first_difference(got, reference),
            elapsed_ms,
        ))

    if args.write_reference:
        args.write_reference.write_text(json.dumps(spec, indent=1) + "\n")
        print(f"wrote {len(queries)} references to {args.write_reference}")
    else:
        print("| Query | Text | Same top 8 in order | First difference | Search ms |")
        print("|---|---|---|---|---|")
        for query_id, text, same, difference, elapsed_ms in rows:
            short = text if len(text) <= 60 else text[:57] + "..."
            print(f"| {query_id} | {short} | {same} | {difference} | {elapsed_ms:.1f} |")
        matched = sum(1 for row in rows if row[2] == "yes")
        print(f"\n{matched} of {len(rows)} queries return the reference top 8 in order.")
    if timings:
        print(
            f"Search time per query: median {statistics.median(timings):.1f} ms, "
            f"max {max(timings):.1f} ms ({len(timings)} queries, "
            f"{len(scope.docs)} documents in scope)."
        )
    return 0 if all_match or args.write_reference else 1


if __name__ == "__main__":
    sys.exit(main())
