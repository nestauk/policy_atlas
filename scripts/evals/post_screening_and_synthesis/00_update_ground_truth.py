"""Step 0: build ground truth for briefings that are in the Google Sheet but not yet in Langfuse.

Usage (from the repo root, with OPENAI_API_KEY, GOOGLE_SHEETS_CREDENTIALS and the
Langfuse keys in backend/.env):

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/post_screening_and_synthesis/00_update_ground_truth.py \\
        [--rerun airports_health_impacts speed_limits_20mph] [--workers 8]

Without ``--rerun`` the script reads the test-set sheet, lists the Langfuse dataset
``synthesis-coverage`` and takes every briefing in the sheet that has no dataset item.
A briefing that already has ``ground_truth/<doc_id>/references.csv`` on disk is skipped
(it was extracted but not pushed yet: run ``01_upload_to_langfuse.py``). ``--rerun``
names briefings to extract again; their CSVs, and any human ``keep`` edits in them,
are overwritten.

Each briefing needs ``inputs/briefings/<doc_id>.<pdf|html>``, downloaded by hand
(parliament.uk blocks scripted fetches). The script stops before any model call if one
is missing.

Per briefing, three model calls: one for every reference-list entry; one that is given
those references and returns the briefing's key points; and one that sees only the key
points and breaks each into atomic facts. They write ``ground_truth/<doc_id>/
references.csv`` and ``key_facts.csv`` (one row per atomic fact, with the key point it
came from) with ``keep=y`` on every row. Then each kept reference is resolved to corpus
text: OpenAlex by DOI, else by strict title match; then the production URL cascade,
fetcher and parser; the briefing's own URL is tried last. No full text but an OpenAlex
abstract gives an ``abstract_only`` chunk; otherwise the reference is ``dropped`` with a
reason. Each outcome is cached in ``datasets/<doc_id>/refs/<label>.json`` (rerun is
network-free) and summarised in ``ground_truth/<doc_id>/corpus_resolution.csv``.

A human then edits the ``keep`` columns, reruns this script to re-resolve if references
changed, and pushes with ``01_upload_to_langfuse.py``.
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import _bootstrap  # noqa: F401
import httpx
from utils import (
    DATASET,
    EXPERIMENT,
    GROUND_TRUTH_DIR,
    LABEL_SEP,
    MODEL,
    briefing_path,
    briefing_text,
    load_kept,
    load_test_set,
    norm_title,
    openai_client,
    prompt,
    ref_cache_path,
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
FACT_FIELDS = ["fact_id", "point_id", "point", "statement", "ref_labels", "keep"]
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
# A 230-reference briefing used about 17k completion tokens (reasoning included).
EXTRACT_MAX_OUTPUT_TOKENS = 32_000


class Ref(BaseModel):
    label: str
    title: str | None
    authors: str | None
    year: str | None
    doi: str | None
    url: str | None


class References(BaseModel):
    references: list[Ref]


class KeyPoint(BaseModel):
    point: str
    ref_labels: list[str]


class KeyPoints(BaseModel):
    key_points: list[KeyPoint]


class PointFacts(BaseModel):
    point_id: int
    facts: list[str]


class Decomposition(BaseModel):
    points: list[PointFacts]


def extract_references(
    doc: dict[str, str],
    text: str,
    client: OpenAI,
    langfuse_client: Any,
) -> tuple[list[Ref], Any, str]:
    """Ask the eval model for every reference-list entry of one briefing.

    Args:
        doc: A row of the test set.
        text: The briefing text from ``briefing_text``.
        client: OpenAI client.
        langfuse_client: Langfuse client, or None for no tracing.

    Returns:
        The references, the call's token usage and the prompt sha.
    """
    system, sha = prompt("extract_references_v1")
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
        response_format=References,
        model=MODEL,
        max_output_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        usage_event="eval.synthesis.extract_references",
        label="extract_references",
        name="eval.synthesis.extract_references",
        prompt_version=f"extract_references_v1@{sha}",
        metadata={"experiment": EXPERIMENT, "doc_id": doc["Doc ID"]},
    )
    return parsed.references, usage, sha


def extract_key_points(
    doc: dict[str, str],
    text: str,
    references: list[Ref],
    client: OpenAI,
    langfuse_client: Any,
) -> tuple[list[KeyPoint], Any, str]:
    """Ask the eval model for the briefing's key points with their reference labels.

    The extracted references are passed in so the labels the model cites are the
    labels in ``references.csv``.

    Args:
        doc: A row of the test set.
        text: The briefing text from ``briefing_text``.
        references: The output of ``extract_references``.
        client: OpenAI client.
        langfuse_client: Langfuse client, or None for no tracing.

    Returns:
        The key points, the call's token usage and the prompt sha.
    """
    system, sha = prompt("extract_key_points_v1")
    # No brackets around the label: the model copies it verbatim into ref_labels,
    # which must match ``references.csv`` for the ingested-coverage join.
    reference_list = "\n".join(f"{r.label}: {r.title or ''}" for r in references)
    user = (
        f"Briefing title: {doc['Title']}\n"
        f"Research question: {doc['Research question']}\n\n"
        f"References (label and title):\n{reference_list}\n\n"
        f"Briefing text:\n{text}"
    )
    parsed, usage = traced_parse(
        client,
        langfuse_client,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=KeyPoints,
        model=MODEL,
        max_output_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        usage_event="eval.synthesis.extract_key_points",
        label="extract_key_points",
        name="eval.synthesis.extract_key_points",
        prompt_version=f"extract_key_points_v1@{sha}",
        metadata={"experiment": EXPERIMENT, "doc_id": doc["Doc ID"]},
    )
    return parsed.key_points, usage, sha


def decompose_key_points(
    doc_id: str,
    key_points: list[KeyPoint],
    client: OpenAI,
    langfuse_client: Any,
) -> tuple[list[list[str]], Any, str]:
    """Break each key point into atomic facts, from the point texts alone.

    The briefing is deliberately not sent: the model can only restate what the key
    point says, so no detail leaks in from the body.

    Args:
        doc_id: Briefing Doc ID, for the trace metadata.
        key_points: The output of ``extract_key_points``.
        client: OpenAI client.
        langfuse_client: Langfuse client, or None for no tracing.

    Returns:
        One list of facts per key point, in the same order; the call's token usage;
        the prompt sha.

    Raises:
        ValueError: If the model does not return exactly one entry per key point.
    """
    system, sha = prompt("decompose_facts_v1")
    user = "\n\n".join(f"{i}. {kp.point}" for i, kp in enumerate(key_points, start=1))
    parsed, usage = traced_parse(
        client,
        langfuse_client,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=Decomposition,
        model=MODEL,
        max_output_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        usage_event="eval.synthesis.decompose_facts",
        label="decompose_facts",
        name="eval.synthesis.decompose_facts",
        prompt_version=f"decompose_facts_v1@{sha}",
        metadata={"experiment": EXPERIMENT, "doc_id": doc_id},
    )
    by_id = {p.point_id: p.facts for p in parsed.points}
    expected = list(range(1, len(key_points) + 1))
    if sorted(by_id) != expected or len(parsed.points) != len(key_points):
        raise ValueError(
            f"doc {doc_id}: decomposition returned point ids {sorted(by_id)}, "
            f"expected {expected}"
        )
    return [by_id[i] for i in expected], usage, sha


def flatten_key_points(
    key_points: list[KeyPoint], facts_per_point: list[list[str]]
) -> list[dict[str, Any]]:
    """One ``key_facts.csv`` row per atomic fact, numbered in document order.

    Args:
        key_points: Key points in document order.
        facts_per_point: The atomic facts of each key point, in the same order.

    Returns:
        Rows with ``fact_id`` sequential across all points, ``point_id`` sequential
        across points, the point text, the fact and the point's joined labels.
    """
    rows = []
    for point_id, (kp, facts) in enumerate(
        zip(key_points, facts_per_point, strict=True), start=1
    ):
        for statement in facts:
            rows.append(
                {
                    "fact_id": len(rows) + 1,
                    "point_id": point_id,
                    "point": kp.point,
                    "statement": statement,
                    "ref_labels": LABEL_SEP.join(kp.ref_labels),
                    "keep": "y",
                }
            )
    return rows


def extract(doc: dict[str, str], client: OpenAI, langfuse_client: Any) -> None:
    """Extract one briefing's references and key facts and write the two CSVs.

    Args:
        doc: A row of the test set.
        client: OpenAI client.
        langfuse_client: Langfuse client, or None for no tracing.
    """
    doc_id = doc["Doc ID"]
    out_dir = GROUND_TRUTH_DIR / doc_id
    text = briefing_text(doc_id)
    references, ref_usage, ref_sha = extract_references(
        doc, text, client, langfuse_client
    )
    key_points, points_usage, points_sha = extract_key_points(
        doc, text, references, client, langfuse_client
    )
    facts_per_point, facts_usage, facts_sha = decompose_key_points(
        doc_id, key_points, client, langfuse_client
    )
    fact_rows = flatten_key_points(key_points, facts_per_point)
    known = {r.label for r in references}
    unknown = sorted({label for kp in key_points for label in kp.ref_labels} - known)
    if unknown:
        print(
            f"doc {doc_id}: WARNING {len(unknown)} ref_labels are not in references.csv "
            f"and will never count as ingested: {unknown[:10]}"
        )
    write_csv(
        out_dir / "references.csv",
        [{**r.model_dump(), "keep": "y"} for r in references],
        REF_FIELDS,
    )
    write_csv(out_dir / "key_facts.csv", fact_rows, FACT_FIELDS)
    print(
        f"doc {doc_id}: {len(references)} references "
        f"({ref_usage}; extract_references_v1 {ref_sha}), "
        f"{len(key_points)} key points "
        f"({points_usage}; extract_key_points_v1 {points_sha}) "
        f"-> {len(fact_rows)} facts ({facts_usage}; decompose_facts_v1 {facts_sha}); "
        f"{len(text)} chars in -> {out_dir}"
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


def dataset_doc_ids(langfuse_client: Any) -> set[str]:
    """Doc IDs with an item in the Langfuse dataset; empty if the dataset is missing."""
    try:
        return {
            i.metadata["review_id"] for i in langfuse_client.get_dataset(DATASET).items
        }
    except Exception as exc:  # the SDK raises a transport error for a missing dataset
        print(
            f"dataset {DATASET!r} not readable ({type(exc).__name__}); treating as empty"
        )
        return set()


def pick_docs(
    docs: list[dict[str, str]], in_langfuse: set[str], rerun: list[str] | None
) -> list[dict[str, str]]:
    """The briefings to extract: ``rerun``, or those in the sheet but not in Langfuse.

    A briefing with ground truth on disk but no dataset item is skipped unless named
    in ``rerun``, so a rerun never overwrites unpushed human edits by accident.
    """
    if rerun:
        wanted = set(rerun)
        return [d for d in docs if d["Doc ID"] in wanted]
    picked = []
    for doc in docs:
        doc_id = doc["Doc ID"]
        if doc_id in in_langfuse:
            continue
        if (GROUND_TRUTH_DIR / doc_id / "references.csv").exists():
            print(
                f"doc {doc_id}: ground truth on disk but not in Langfuse; "
                "run 01_upload_to_langfuse.py, or pass --rerun to extract again"
            )
            continue
        picked.append(doc)
    return picked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--rerun", nargs="+", metavar="DOC_ID", help="Extract these again (overwrites)"
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    langfuse_client = tracing.get_langfuse()
    docs = load_test_set(args.rerun)
    in_langfuse = dataset_doc_ids(langfuse_client) if langfuse_client else set()
    print(f"{len(docs)} briefings in the sheet, {len(in_langfuse)} in Langfuse")
    targets = pick_docs(docs, in_langfuse, args.rerun)
    if not targets:
        print("nothing to do")
        return
    missing = []
    for doc in targets:
        try:
            briefing_path(doc["Doc ID"])
        except FileNotFoundError as exc:
            missing.append(str(exc))
    if missing:
        raise SystemExit(
            "download these briefings by hand first:\n" + "\n".join(missing)
        )

    client = openai_client()
    for doc in targets:
        extract(doc, client, langfuse_client)
        resolve(doc["Doc ID"], workers=args.workers)
    if langfuse_client is not None:
        langfuse_client.flush()
    print(
        f"done: {[d['Doc ID'] for d in targets]}. Check the keep columns under "
        f"{GROUND_TRUTH_DIR}, then run 01_upload_to_langfuse.py"
    )


if __name__ == "__main__":
    main()
