"""Ground-truth builder: given a systematic review's DOI or URL, produce its
full reference-list DOI set — the recall target (see run_and_score.py for why
precision is still never scored directly against it).

Dev-only pilot tooling for the search+screen eval methodology
(docs/../plans — "Evaluate search+screen against a systematic review's ground
truth"). Not part of the runtime package.
"""

from __future__ import annotations

import difflib
import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from langfuse import Langfuse
from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import openai_kwargs, parse_structured, resolve_openai_client
from policy_atlas.core.usage import usage_metadata
from policy_atlas.evidence_base.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_base.sourcing.ingest_full_text import parse_and_segment

OPENALEX_HOST = "https://api.openalex.org"
_EXTRACTION_MODEL = "gpt-5.4"
_EXTRACTION_PROMPT_VERSION = "eval_extract_reference_list_v1"
_TITLE_MATCH_THRESHOLD = 0.82
_FULL_TEXT_CHAR_CAP = 300_000
_THIN_TEXT_MIN = 500
# A one-shot pilot; typical systematic-review bibliographies fit well inside this.
_REFERENCED_WORKS_CAP = 250
_RESOLVABILITY_BATCH = 25


def normalize_doi(doi: Any) -> str | None:
    """Normalize a DOI to lowercase bare form.

    Mirrors ``acquire._normalize_doi`` (private to that module) so ground-truth
    DOIs and pipeline-output DOIs match on the same identity key.
    """
    if not isinstance(doi, str) or not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if d.startswith(prefix):
            d = d[len(prefix):]
            break
    return d or None


def _openalex_params(**extra: str) -> dict[str, str]:
    params = dict(extra)
    email = os.environ.get("OPENALEX_EMAIL")
    if email:
        params["mailto"] = email
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    return params


def fetch_openalex_work(doi: str) -> dict[str, Any]:
    """Fetch one OpenAlex work record by DOI. Keyless; polite-pool mailto optional."""
    normalized = normalize_doi(doi) or doi
    resp = httpx.get(
        f"{OPENALEX_HOST}/works/https://doi.org/{normalized}",
        params=_openalex_params(),
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def decode_abstract(work: dict[str, Any]) -> str | None:
    """Reconstruct the plain-text abstract from OpenAlex's inverted index.

    Mirrors ``acquire._reconstruct_abstract`` (private to that module).
    """
    index = work.get("abstract_inverted_index")
    if not index:
        return None
    positions: dict[int, str] = {}
    for token, token_positions in index.items():
        for pos in token_positions:
            positions[pos] = token
    return " ".join(positions[p] for p in sorted(positions)) or None


def fetch_full_text_from_url(url: str) -> str | None:
    """Fetch and parse one explicit URL directly (webpage or PDF) — no OpenAlex
    work record involved (grey-literature reviews rarely have a DOI).
    """
    result = LiveDocumentFetcher().fetch(url)
    if result.status != "ok" or not result.body:
        return None
    parsed = parse_and_segment(result.body, result.content_type or "text/plain", _THIN_TEXT_MIN)
    if parsed["status"] != "ok":
        return None
    text = "\n".join(chunk["content"] for chunk in parsed["chunks"])
    return text[:_FULL_TEXT_CHAR_CAP] if text else None


class ExtractedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_citation: str = Field(description="The citation as it appears in the document's reference list.")
    title_guess: str = Field(
        description="Your best-guess full title for this reference, from the citation "
        "text and any surrounding context."
    )
    doi_in_text: str | None = Field(
        default=None,
        description="A DOI for this reference if one is printed anywhere near it in the "
        "text, else null. Never invented.",
    )


class ReferenceListWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citations: list[ExtractedCitation] = Field(
        description="Every entry in this document's reference list / bibliography section."
    )
    extraction_confidence: Literal["high", "medium", "low"] = Field(
        description="'high' only if the text contains a clearly-delineated reference "
        "list / bibliography section you transcribed directly. 'low' if no such "
        "section could be found and citations had to be inferred from in-text mentions."
    )


_EXTRACTION_SYSTEM = (
    "You are transcribing every entry in a document's reference list / bibliography "
    "section — a mechanical listing task, not a judgment call. Include every "
    "reference the document cites, regardless of topic or type. If the document has "
    "no clearly-delineated reference list section, say so honestly via "
    "extraction_confidence rather than guessing from in-text citations alone."
)


def extract_reference_list(
    full_text: str, review_title: str, langfuse_client: Langfuse | None = None
) -> ReferenceListWire:
    """Lead-authored, schema-constrained transcription of a document's bibliography."""
    client = resolve_openai_client(
        None, backend_name="ground_truth.extract_reference_list", timeout=180.0, max_retries=2
    )
    messages: list[Any] = [
        {"role": "system", "content": _EXTRACTION_SYSTEM},
        {"role": "user", "content": f"Document title: {review_title}\n\nFull text:\n{full_text}"},
    ]

    def _update(span: Any, result: Any) -> None:
        wire, usage = result
        span.update(
            input={"messages": messages},
            output=wire.model_dump(),
            model=_EXTRACTION_MODEL,
            metadata={"prompt_version": _EXTRACTION_PROMPT_VERSION, **usage_metadata(usage)},
        )

    wire, _usage = tracing.traced_call(
        langfuse_client,
        name="eval.extract_reference_list",
        as_type="generation",
        call=lambda: parse_structured(
            client,
            messages=messages,
            response_format=ReferenceListWire,
            usage_event="eval.extract_reference_list",
            label="reference-list extraction",
            **openai_kwargs(_EXTRACTION_MODEL, reasoning_effort="medium"),
            max_completion_tokens=16_384,
        ),
        update=_update,
    )
    return wire


def resolve_citation_doi(citation: ExtractedCitation) -> str | None:
    """DOI-in-text first (contract 015 precedent: DOI over fuzzy title match);
    else a bounded OpenAlex title search accepted only above a similarity floor.
    """
    doi = normalize_doi(citation.doi_in_text)
    if doi:
        return doi
    if not citation.title_guess:
        return None
    resp = httpx.get(
        f"{OPENALEX_HOST}/works",
        params=_openalex_params(search=citation.title_guess, per_page="3", select="doi,title"),
        timeout=30.0,
    )
    if resp.status_code != 200:
        return None
    for candidate in resp.json().get("results", []):
        title = candidate.get("title") or ""
        similarity = difflib.SequenceMatcher(None, title.lower(), citation.title_guess.lower()).ratio()
        if similarity >= _TITLE_MATCH_THRESHOLD:
            return normalize_doi(candidate.get("doi"))
    return None


def fetch_reference_list_dois(work: dict[str, Any]) -> set[str]:
    """Resolve the review's full reference list (OpenAlex ``referenced_works``) to DOIs."""
    dois: set[str] = set()
    for work_id in (work.get("referenced_works") or [])[:_REFERENCED_WORKS_CAP]:
        short_id = work_id.rsplit("/", 1)[-1]
        resp = httpx.get(
            f"{OPENALEX_HOST}/works/{short_id}", params=_openalex_params(select="doi"), timeout=30.0
        )
        if resp.status_code == 200:
            doi = normalize_doi(resp.json().get("doi"))
            if doi:
                dois.add(doi)
        time.sleep(0.1)  # polite pacing across a few hundred sequential GETs
    return dois


def openalex_resolvable_fraction(dois: set[str]) -> float:
    """Fraction of ``dois`` indexed in OpenAlex at all — the search-space ceiling:
    a candidate not indexed here can never be found by this pipeline's OpenAlex
    backend regardless of screen/search quality.
    """
    if not dois:
        return 0.0
    doi_list = list(dois)
    found = 0
    for i in range(0, len(doi_list), _RESOLVABILITY_BATCH):
        batch = doi_list[i : i + _RESOLVABILITY_BATCH]
        resp = httpx.get(
            f"{OPENALEX_HOST}/works",
            params=_openalex_params(filter=f"doi:{'|'.join(batch)}", per_page=str(len(batch)), select="doi"),
            timeout=30.0,
        )
        if resp.status_code == 200:
            found += len(resp.json().get("results", []))
        time.sleep(0.1)
    return found / len(dois)


@dataclass
class GroundTruth:
    dois: set[str]
    """The recall target: every DOI-resolvable entry in the review's reference list."""
    resolvable_fraction: float
    source: Literal["doi", "url"]
    unresolved: list[str] = field(default_factory=list)


def build_ground_truth_from_doi(doi: str, work: dict[str, Any] | None = None) -> GroundTruth:
    """Fetch a review's full reference list straight from its OpenAlex
    ``referenced_works`` — no full-text fetch or LLM extraction needed.

    Args:
        doi: The review's DOI.
        work: A pre-fetched OpenAlex work record for this DOI, if the caller
            already has one (e.g. from a prior search) — skips the redundant
            fetch. Defaults to ``None``, fetching it here.
    """
    work = work if work is not None else fetch_openalex_work(doi)
    dois = fetch_reference_list_dois(work)
    return GroundTruth(
        dois=dois,
        resolvable_fraction=openalex_resolvable_fraction(dois),
        source="doi",
    )


def build_ground_truth_from_url(
    url: str, review_title: str, langfuse_client: Langfuse | None = None
) -> GroundTruth:
    """Build ground truth from an explicit review URL (webpage or PDF) rather
    than a DOI — for grey-literature reviews with no OpenAlex work record, so
    there's no ``referenced_works`` API to call. The reference list is instead
    transcribed from the fetched full text and resolved to DOIs.
    """
    full_text = fetch_full_text_from_url(url)
    if not full_text:
        raise RuntimeError(f"Could not fetch/parse full text from {url!r}.")
    extraction = extract_reference_list(full_text, review_title, langfuse_client)
    dois: set[str] = set()
    unresolved: list[str] = []
    if extraction.extraction_confidence != "low":
        for citation in extraction.citations:
            resolved = resolve_citation_doi(citation)
            if resolved:
                dois.add(resolved)
            else:
                unresolved.append(citation.raw_citation)
    if not dois:
        raise RuntimeError(
            f"Could not extract any resolvable reference-list entries from {url!r} "
            "(no clearly-delineated bibliography section found, or none resolved to a DOI)."
        )
    return GroundTruth(
        dois=dois,
        resolvable_fraction=openalex_resolvable_fraction(dois),
        source="url",
        unresolved=unresolved,
    )
