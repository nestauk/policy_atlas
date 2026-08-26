"""Ground-truth builder: given a systematic review's DOI or URL, produce its
full reference-list DOI set — the recall target (see run_and_score.py for why
precision is still never scored directly against it).

Dev-only pilot tooling for the search+screen eval methodology
(docs/../plans — "Evaluate search+screen against a systematic review's ground
truth"). Not part of the runtime package.
"""

from __future__ import annotations

import difflib
import html
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
OVERTON_HOST = "https://app.overton.io"
# Overton's own pacing floor, mirroring search_live.OVERTON_MIN_INTERVAL_S.
_OVERTON_MIN_INTERVAL_S = 1.2
_EXTRACTION_MODEL = "gpt-5.4"
_EXTRACTION_PROMPT_VERSION = "eval_extract_reference_list_v1"
_TITLE_MATCH_THRESHOLD = 0.82
_FULL_TEXT_CHAR_CAP = 300_000
_THIN_TEXT_MIN = 500
# A one-shot pilot; typical systematic-review bibliographies fit well inside this.
_REFERENCED_WORKS_CAP = 250
_RESOLVABILITY_BATCH = 25
# Overton title lookups per citation, and how many citations get one at all.
# Overton paces itself at ~1.2s a request, so the cap bounds the wait: 200
# no-DOI citations cost about four minutes, paid once per ground-truth build.
_OVERTON_LOOKUP_RESULTS = 5
_OVERTON_RESOLVE_CAP = 200


def overton_key(policy_document_id: Any) -> str | None:
    """One Overton policy document id as a scoring key, e.g. ``overton:12345``.

    Prefixed so DOI keys and Overton keys can live in one set without any
    chance of collision.
    """
    if policy_document_id is None or policy_document_id == "":
        return None
    return f"overton:{policy_document_id}"


def record_key(metadata: dict[str, Any] | None) -> str | None:
    """The identity a document is scored on: its DOI, else its Overton id.

    Most scholarly papers carry a DOI, and that is the strongest key there is.
    Policy documents — an ONS statistical bulletin, a select-committee report —
    usually carry none at all, and scoring on DOIs alone silently drops every
    one of them from both the target list and the results. Falling back to the
    Overton document id keeps them in the measurement, which is the only way
    Overton's own contribution becomes visible.

    Works on anything carrying the pipeline's envelope keys: a persisted
    ``source_snapshot.metadata`` row, or a freshly mapped provider record.

    Returns:
        A DOI, an ``overton:<id>`` key, or None for a document with neither
        (which cannot be matched against the ground truth at all).
    """
    if not metadata:
        return None
    doi = normalize_doi(metadata.get("doi"))
    if doi:
        return doi
    if metadata.get("backend") == "overton":
        return overton_key(metadata.get("backend_record_id"))
    return None


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


def openalex_get(path: str, **params: str) -> httpx.Response:
    """GET an OpenAlex path, retrying transient failures (5xx / timeouts).

    OpenAlex intermittently returns 504 Gateway Timeout under load. These are
    not real "the record is missing" errors, so we wait and ask again — five
    tries with a doubling wait (1s, 2s, 4s, 8s). The last response is returned
    as-is, so callers keep their existing status-code handling.
    """
    delay = 1.0
    for attempt in range(5):
        try:
            resp = httpx.get(f"{OPENALEX_HOST}{path}", params=_openalex_params(**params), timeout=30.0)
            if resp.status_code < 500:
                return resp
        except httpx.TransportError:
            if attempt == 4:
                raise
        if attempt < 4:
            time.sleep(delay)
            delay *= 2
    return resp


def fetch_openalex_work(doi: str) -> dict[str, Any]:
    """Fetch one OpenAlex work record by DOI. Keyless; polite-pool mailto optional."""
    normalized = normalize_doi(doi) or doi
    resp = openalex_get(f"/works/https://doi.org/{normalized}")
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
    resp = openalex_get("/works", search=citation.title_guess, per_page="3", select="doi,title")
    if resp.status_code != 200:
        return None
    for candidate in resp.json().get("results", []):
        title = candidate.get("title") or ""
        similarity = difflib.SequenceMatcher(None, title.lower(), citation.title_guess.lower()).ratio()
        if similarity >= _TITLE_MATCH_THRESHOLD:
            return normalize_doi(candidate.get("doi"))
    return None


def overton_get(query: str) -> list[dict[str, Any]]:
    """One keyword search against Overton, paced to its rate limit.

    Deliberately the eval's own HTTP call rather than the pipeline's Overton
    backend, exactly as ``resolve_citation_doi`` calls OpenAlex directly. The
    two want different things from the same API: the pipeline searches
    semantically (``squery``, matched against Overton's AI-written document
    descriptions) because it is looking for documents *about* a topic; this is
    looking for one *named* document, which is what the documented keyword
    ``query`` mode does.

    Raises:
        httpx.HTTPError: On a transport failure or a non-2xx response — the
            caller must not confuse a broken lookup with an absent document.
    """
    key = os.environ.get("OVERTON_API_KEY")
    if not key:
        raise RuntimeError("OVERTON_API_KEY is required to resolve citations against Overton")
    resp = httpx.get(
        f"{OVERTON_HOST}/documents.php",
        params={
            "query": query,
            "format": "json",
            "api_key": key,
            "pp": str(_OVERTON_LOOKUP_RESULTS),
        },
        timeout=30.0,
    )
    time.sleep(_OVERTON_MIN_INTERVAL_S)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results if isinstance(results, list) else []


def _overton_title(record: dict[str, Any]) -> str:
    """A record's display title, with HTML entities decoded (Overton ships
    ``&#39;`` and friends raw, which would wreck a similarity comparison)."""
    return html.unescape(record.get("translated_title") or record.get("title") or "")


def _match_form(title: str) -> str:
    """Lowercased, with curly quotes folded to straight ones — for comparing
    two spellings of the same title, not for querying."""
    return title.lower().replace("’", "'").replace("“", '"').replace("”", '"')


def _overton_query_variants(title: str) -> list[str]:
    """The queries to try for one title, most precise first.

    Overton's keyword index treats punctuation literally, and a typographic
    apostrophe is not a straight one: "Children's ... experiences of
    loneliness" finds nothing, while "Children’s ..." returns the document
    itself. Rather than guess which spelling a given publisher used, try both.
    Titles with no apostrophe produce identical variants and are de-duplicated
    away, so the common case still costs a single request.
    """
    # Quotes and colons are query syntax: a colon inside a title ("A connected
    # society: a strategy...") would otherwise read as a field prefix.
    straight = title.replace('"', " ").replace(":", " ").strip()
    curly = straight.replace("'", "’")
    variants = [f'title:"{straight}"', f'title:"{curly}"', curly, straight]
    return list(dict.fromkeys(variants))


def resolve_citation_overton(citation: ExtractedCitation) -> str | None:
    """Find one citation in Overton by title, for references that have no DOI.

    The twin of ``resolve_citation_doi``, same shape: a bounded lookup accepted
    only when the returned title closely matches the citation's. It tries the
    queries ``_overton_query_variants`` builds, most precise first, and stops
    at the first close match.

    All of them are keyword mode. Semantic mode (``squery``, what the pipeline
    itself searches with) was tried first and is the wrong instrument for this
    job: asked for "A connected society: a strategy for tackling loneliness" it
    returned Japanese loneliness policy papers and never the document itself,
    because it matches meaning against AI-written summaries, not names.

    Args:
        citation: One transcribed reference-list entry.

    Returns:
        An ``overton:<id>`` key, or None when nothing matched closely enough —
        including when Overton simply does not hold the document.

    Raises:
        httpx.HTTPError: On a failed lookup, so the caller can report it rather
            than record a silent miss.
    """
    title = (citation.title_guess or "").strip()
    if not title:
        return None
    wanted = _match_form(title)
    for query in _overton_query_variants(title):
        for record in overton_get(query):
            similarity = difflib.SequenceMatcher(
                None, _match_form(_overton_title(record)), wanted
            ).ratio()
            if similarity >= _TITLE_MATCH_THRESHOLD:
                return overton_key(record.get("policy_document_id"))
    return None


def fetch_reference_list_dois(work: dict[str, Any]) -> set[str]:
    """Resolve the review's full reference list (OpenAlex ``referenced_works``) to DOIs."""
    dois: set[str] = set()
    for work_id in (work.get("referenced_works") or [])[:_REFERENCED_WORKS_CAP]:
        short_id = work_id.rsplit("/", 1)[-1]
        resp = openalex_get(f"/works/{short_id}", select="doi")
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
        resp = openalex_get(
            "/works", filter=f"doi:{'|'.join(batch)}", per_page=str(len(batch)), select="doi"
        )
        if resp.status_code == 200:
            found += len(resp.json().get("results", []))
        time.sleep(0.1)
    return found / len(dois)


@dataclass
class GroundTruth:
    dois: set[str]
    """Reference-list entries that resolved to a DOI — the scholarly target."""
    resolvable_fraction: float
    """Fraction of ``dois`` that OpenAlex indexes: the ceiling on DOI recall."""
    source: Literal["doi", "url"]
    unresolved: list[str] = field(default_factory=list)
    """Citations that resolved to neither a DOI nor an Overton document. Not
    scorable — neither backend can be asked for them, so they are excluded
    from the target rather than counted as misses."""
    overton_ids: set[str] = field(default_factory=set)
    """``overton:<id>`` keys for reference-list entries that have no DOI but do
    exist in Overton — the policy-document target. Empty in ``--doi`` mode,
    which reads OpenAlex's ``referenced_works`` and never sees a citation
    string to look up (see ``build_ground_truth_from_url``)."""
    titles: dict[str, str] = field(default_factory=dict)
    """Key -> the citation's title, for keys with no OpenAlex record to ask.
    Populated in ``--url`` mode only; used to label Overton targets in reports."""

    @property
    def keys(self) -> set[str]:
        """The full recall target: DOI keys and Overton keys together.

        Score against this, not ``dois``, or every policy document in the
        reference list counts as a miss it was never possible to hit.
        """
        return self.dois | self.overton_ids


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
    url: str,
    review_title: str,
    langfuse_client: Langfuse | None = None,
    resolve_overton: bool = True,
) -> GroundTruth:
    """Build ground truth from an explicit review URL (webpage or PDF) rather
    than a DOI — for grey-literature reviews with no OpenAlex work record, so
    there's no ``referenced_works`` API to call. The reference list is instead
    transcribed from the fetched full text and resolved, entry by entry, in two
    passes: to a DOI where one exists, and otherwise to an Overton document.

    The second pass is what makes a policy review scorable at all. A government
    evidence review cites statistical bulletins, departmental reports and
    evaluations that carry no DOI; DOI-only resolution drops every one of them,
    shrinking the target to the academic minority and leaving the pipeline's
    Overton arm with nothing to be measured against.

    Args:
        url: The review's webpage or PDF.
        review_title: Title, given to the transcription prompt as context.
        langfuse_client: Optional tracing client for the transcription call.
        resolve_overton: Set False to skip the Overton pass — a DOI-only target,
            which is faster (no ~1.2s-per-citation lookups) and comparable with
            runs made before this pass existed.
    """
    full_text = fetch_full_text_from_url(url)
    if not full_text:
        raise RuntimeError(f"Could not fetch/parse full text from {url!r}.")
    extraction = extract_reference_list(full_text, review_title, langfuse_client)
    dois: set[str] = set()
    overton_ids: set[str] = set()
    titles: dict[str, str] = {}
    unresolved: list[str] = []
    if extraction.extraction_confidence != "low":
        overton_attempts = 0
        lookup_failures = 0
        for citation in extraction.citations:
            resolved = resolve_citation_doi(citation)
            if resolved:
                dois.add(resolved)
                continue
            # No DOI. Grey literature — government reports, statistical
            # bulletins, evaluations — mostly has none, and those are exactly
            # the documents Overton indexes and OpenAlex does not. Ask Overton
            # before writing the citation off as unscorable.
            if resolve_overton and overton_attempts < _OVERTON_RESOLVE_CAP:
                overton_attempts += 1
                try:
                    key = resolve_citation_overton(citation)
                except (httpx.HTTPError, RuntimeError) as exc:
                    # A broken lookup is not an absent document. One failure
                    # must not sink a build that has already paid for a
                    # full-text fetch and an LLM transcription, but a silent
                    # zero would read as "Overton holds none of these" — so
                    # count them and say so at the end.
                    lookup_failures += 1
                    if lookup_failures == 1:
                        print(f"  Overton lookup failed ({type(exc).__name__}: {exc})")
                    key = None
                if key:
                    overton_ids.add(key)
                    titles[key] = citation.title_guess
                    continue
            unresolved.append(citation.raw_citation)
        if overton_attempts:
            print(
                f"  Overton lookups: {overton_attempts} citations with no DOI, "
                f"{len(overton_ids)} resolved to a policy document, "
                f"{lookup_failures} lookup failures"
            )
    if not dois and not overton_ids:
        raise RuntimeError(
            f"Could not extract any resolvable reference-list entries from {url!r} "
            "(no clearly-delineated bibliography section found, or nothing resolved "
            "to a DOI or an Overton document)."
        )
    return GroundTruth(
        dois=dois,
        resolvable_fraction=openalex_resolvable_fraction(dois),
        source="url",
        unresolved=unresolved,
        overton_ids=overton_ids,
        titles=titles,
    )
