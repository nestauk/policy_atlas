"""Build the ground truth for one briefing: its reference list and key facts.

Usage (from the repo root, with OPENAI_API_KEY in backend/.env):

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/post_screening_and_synthesis/ground_truth.py extract --docs 16 5

``extract`` reads ``inputs/briefings/<doc_id>.<pdf|html>``, parses it with the production
parser and asks the eval model for every reference-list entry and 15-40 key facts. It
writes ``ground_truth/<doc_id>/references.csv`` and ``key_facts.csv`` with ``keep=y`` on
every row. A human then edits the ``keep`` column and the files are committed, so
``extract`` refuses to overwrite them without ``--force``.

    ... ground_truth.py resolve --docs 16 5 [--workers 8]

``resolve`` turns each kept reference into corpus text: OpenAlex by DOI, else by strict
title match; then the production URL cascade, fetcher and parser; the briefing's own URL
is tried last. No full text but an OpenAlex abstract gives an ``abstract_only`` chunk;
otherwise the reference is ``dropped`` with a reason. Each outcome is cached in
``datasets/<doc_id>/refs/<label>.json`` (rerun is network-free) and summarised in
``ground_truth/<doc_id>/corpus_resolution.csv``.
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import _bootstrap  # noqa: F401
import httpx
from utils import (
    DATASETS_DIR,
    EXPERIMENT,
    GROUND_TRUTH_DIR,
    MODEL,
    briefing_text,
    load_kept,
    load_test_set,
    norm_title,
    openai_client,
    prompt,
    write_csv,
)
from evals_search_utils import fetch_openalex_work, openalex_get
from openai import OpenAI
from policy_atlas.core import tracing
from policy_atlas.core.openai_client import traced_parse
from policy_atlas.evidence_search.sourcing.acquire import _map_openalex_work
from policy_atlas.evidence_search.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    THIN_TEXT_MIN_CHARS,
    DocumentFetcher,
    candidate_urls,
    discover_document_url,
    parse_and_segment,
)
from pydantic import BaseModel

REF_FIELDS = ["label", "title", "authors", "year", "doi", "url", "keep"]
FACT_FIELDS = ["fact_id", "statement", "ref_labels", "keep"]
RESOLUTION_FIELDS = [
    "label",
    "status",
    "reason",
    "source_locator",
    "fetched_from",
    "n_chunks",
    "n_chars",
    "attempts",
]
LABEL_SEP = "|"
# A 230-reference briefing used about 17k completion tokens (reasoning included).
EXTRACT_MAX_OUTPUT_TOKENS = 32_000


class Ref(BaseModel):
    label: str
    title: str | None
    authors: str | None
    year: str | None
    doi: str | None
    url: str | None


class Fact(BaseModel):
    fact_id: int
    statement: str
    ref_labels: list[str]


class Briefing(BaseModel):
    references: list[Ref]
    key_facts: list[Fact]


def extract(
    doc: dict[str, str], client: OpenAI, langfuse_client: Any, *, force: bool
) -> None:
    """Extract one briefing's references and key facts and write the two CSVs.

    Args:
        doc: A row of the test set CSV.
        client: OpenAI client.
        langfuse_client: Langfuse client, or None for no tracing.
        force: Overwrite existing ground truth (human ``keep`` edits are lost).
    """
    doc_id = doc["Doc ID"]
    out_dir = GROUND_TRUTH_DIR / doc_id
    if (out_dir / "references.csv").exists() and not force:
        raise SystemExit(
            f"{out_dir} already has ground truth; pass --force to overwrite"
        )
    text = briefing_text(doc_id)
    system, sha = prompt("extract_v1")
    user = (
        f"Briefing title: {doc['Title']}\n"
        f"Research question: {doc['Research question']}\n\n{text}"
    )
    parsed, usage = traced_parse(
        client,
        langfuse_client,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=Briefing,
        model=MODEL,
        max_output_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        usage_event="eval.synthesis.extract",
        label="extract",
        name="eval.synthesis.extract",
        prompt_version=f"extract_v1@{sha}",
        metadata={"experiment": EXPERIMENT, "doc_id": doc_id},
    )
    write_csv(
        out_dir / "references.csv",
        [{**r.model_dump(), "keep": "y"} for r in parsed.references],
        REF_FIELDS,
    )
    write_csv(
        out_dir / "key_facts.csv",
        [
            {
                "fact_id": f.fact_id,
                "statement": f.statement,
                "ref_labels": LABEL_SEP.join(f.ref_labels),
                "keep": "y",
            }
            for f in parsed.key_facts
        ],
        FACT_FIELDS,
    )
    print(
        f"doc {doc_id}: {len(parsed.references)} references, {len(parsed.key_facts)} facts "
        f"({len(text)} chars in, {usage}; extract_v1 {sha}) -> {out_dir}"
    )


_PUBMED_IDS = (
    (re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)"), "pmid"),
    (re.compile(r"\b(PMC\d+)\b"), "pmcid"),
)


def _openalex_work(ref: dict[str, str]) -> dict[str, Any] | None:
    """The OpenAlex work for a reference: by DOI, PubMed id in the URL, else strict title."""
    if ref["doi"]:
        try:
            return fetch_openalex_work(ref["doi"])
        except httpx.HTTPStatusError:
            pass
    for pattern, prefix in _PUBMED_IDS:
        found = pattern.search(ref["url"] or "")
        if found:
            resp = openalex_get(f"/works/{prefix}:{found.group(1)}")
            if resp.status_code == 200:
                return resp.json()
    if ref["title"]:
        resp = openalex_get("/works", search=ref["title"], per_page="5")
        if resp.status_code == 200:
            for work in resp.json().get("results", []):
                if norm_title(work.get("display_name")) == norm_title(ref["title"]):
                    return work
    return None


def resolve_ref(
    doc_id: str, ref: dict[str, str], fetcher: DocumentFetcher
) -> dict[str, Any]:
    """Resolve one reference to corpus text.

    Args:
        doc_id: Briefing Doc ID (for the fallback locator).
        ref: A kept row of ``references.csv``.
        fetcher: The production live fetcher.

    Returns:
        ``status`` (``full_text`` | ``abstract_only`` | ``dropped``), ``reason``,
        ``source_locator``, ``metadata`` (production envelope layout plus
        ``eval_ref_label``), ``chunks``, ``fetched_from`` and ``attempts``.
    """
    label = ref["label"]
    mapped = _map_openalex_work(_openalex_work(ref) or {})
    if mapped:
        metadata = {
            **{k: v for k, v in mapped["envelope"].items() if v is not None},
            "abstract_source": mapped["abstract_source"],
            "provider_fields": mapped["provider_fields"],
        }
        urls = candidate_urls(metadata)
        locator = mapped["source_locator"]
    else:
        metadata = {k: ref[k] for k in ("title", "year", "doi") if ref[k]}
        metadata["backend"] = "eval_upload"
        urls = []
        locator = ref["url"] or f"eval:{doc_id}:{label}"
    if ref["url"] and ref["url"] not in urls:
        urls.append(ref["url"])
    metadata["eval_ref_label"] = label

    attempts: list[str] = []
    chunks: list[str] | None = None
    fetched_from = None
    i = 0
    while i < len(urls) and chunks is None:
        url = urls[i]
        i += 1
        result = fetcher.fetch(url)
        if result.status != "ok":
            attempts.append(f"{url}: {result.error}")
            continue
        body = result.body or b""
        content_type = result.content_type or "application/octet-stream"
        parsed = parse_and_segment(body, content_type, THIN_TEXT_MIN_CHARS)
        if parsed["status"] == "ok":
            chunks = [c["content"] for c in parsed["chunks"]]
            fetched_from = url
            attempts.append(f"{url}: ok")
        else:
            attempts.append(f"{url}: {parsed['reason']}")
            if content_type.startswith("text/html"):
                found = discover_document_url(body, url)
                if found and found not in urls:
                    urls.append(found)

    if chunks is not None:
        status, reason = "full_text", ""
    elif metadata.get("abstract"):
        status, reason = "abstract_only", "no_full_text"
        chunks = [f"{metadata['title']}\n\n{metadata['abstract']}"]
    else:
        status = "dropped"
        reason = "no_candidate_urls" if not urls else "no_full_text_no_abstract"
        chunks = []
    return {
        "label": label,
        "status": status,
        "reason": reason,
        "source_locator": locator,
        "metadata": metadata,
        "chunks": chunks,
        "fetched_from": fetched_from,
        "attempts": attempts,
    }


def ref_cache_path(doc_id: str, label: str) -> Path:
    return (
        DATASETS_DIR
        / doc_id
        / "refs"
        / (re.sub(r"[^A-Za-z0-9_.-]+", "_", label) + ".json")
    )


def resolve(doc_id: str, *, workers: int) -> None:
    """Resolve every kept reference of one briefing, caching per reference.

    Args:
        doc_id: Briefing Doc ID.
        workers: Concurrent references; the fetcher applies its own per-host politeness.
    """
    refs = load_kept(doc_id, "references")
    fetcher = LiveDocumentFetcher()

    def one(ref: dict[str, str]) -> dict[str, Any]:
        path = ref_cache_path(doc_id, ref["label"])
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        resolved = resolve_ref(doc_id, ref, fetcher)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(resolved, ensure_ascii=False), encoding="utf-8")
        return resolved

    with ThreadPoolExecutor(max_workers=workers) as pool:
        resolved = list(pool.map(one, refs))

    write_csv(
        GROUND_TRUTH_DIR / doc_id / "corpus_resolution.csv",
        [
            {
                "label": r["label"],
                "status": r["status"],
                "reason": r["reason"],
                "source_locator": r["source_locator"],
                "fetched_from": r["fetched_from"] or "",
                "n_chunks": len(r["chunks"]),
                "n_chars": sum(len(c) for c in r["chunks"]),
                "attempts": " ; ".join(r["attempts"]),
            }
            for r in resolved
        ],
        RESOLUTION_FIELDS,
    )
    counts = {
        s: sum(1 for r in resolved if r["status"] == s)
        for s in ("full_text", "abstract_only", "dropped")
    }
    print(f"doc {doc_id}: {len(refs)} kept references -> {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_extract = sub.add_parser(
        "extract", help="references + key facts from the briefing"
    )
    p_extract.add_argument("--docs", nargs="+", required=True, help="Doc IDs")
    p_extract.add_argument("--force", action="store_true")
    p_resolve = sub.add_parser("resolve", help="fetch corpus text for kept references")
    p_resolve.add_argument("--docs", nargs="+", required=True, help="Doc IDs")
    p_resolve.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if args.command == "extract":
        client = openai_client()
        langfuse_client = tracing.get_langfuse()
        for doc in load_test_set(args.docs):
            extract(doc, client, langfuse_client, force=args.force)
        if langfuse_client is not None:
            langfuse_client.flush()
    else:
        for doc in load_test_set(args.docs):
            resolve(doc["Doc ID"], workers=args.workers)


if __name__ == "__main__":
    main()
