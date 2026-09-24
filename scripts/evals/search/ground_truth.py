"""Shared ground-truth helpers for the eval: the key a document is scored on,
the ``GroundTruth`` container, the review-title-to-intent cleaner, the date
helpers for a review's search cutoff, and the one OpenAlex lookup the dataset
builder needs. Pure Python plus ``httpx`` — nothing here imports the pipeline
or the database, so the CSV loader stays cheap to run.

The recall target itself comes from the hand-curated CSVs under ``input/``
(see ``ground_truth_dataset.py``), not from anything here.

Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import argparse
import calendar
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import httpx

OPENALEX_HOST = "https://api.openalex.org"


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
    tries with exponential backoff (1s, 2s, 4s, 8s). The last response is returned
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


# Trailing review-type clause, anchored to a colon/dash separator at the END
# of the title only — e.g. "...: a systematic review", "...: a scoping review
# of RCTs", "... - A Bibliometric Analysis". Anchoring on the separator is what
# keeps this safe: "Barriers to conducting systematic reviews in LMICs" has no
# such separator before "systematic reviews," so it's left untouched.
_REVIEW_TYPE_SUFFIX_RE = re.compile(
    r"""[:–—-]\s*                       # colon, en/em dash, or hyphen
        (?:an?\s+|the\s+)?              # optional leading article
        (?:
            (?:systematic|scoping|rapid|narrative|literature|umbrella|integrative)
            \s+review(?:\s+and\s+meta-analysis)?
            |
            (?:bibliometric|scientometric)\s+analysis
            |
            meta-analysis
        )
        \s*.*$                          # swallow any trailing clause, e.g. "of RCTs"
    """,
    re.IGNORECASE | re.VERBOSE,
)


def clean_review_title(title: str) -> str:
    """Strip a trailing generic review-type clause, giving a plain research-scope
    statement to use directly as the search intent. No match -> title unchanged.
    """
    stripped = _REVIEW_TYPE_SUFFIX_RE.sub("", title).strip()
    return stripped or title


def iso_date(value: str) -> str:
    """Validate a ``YYYY-MM-DD`` string; usable as an argparse ``type``."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid ISO date (YYYY-MM-DD)") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(f"{value!r} must be a YYYY-MM-DD ISO date")
    return value


def months_earlier(iso: str, months: int) -> str:
    """``iso`` shifted back ``months`` calendar months, clamped to the target
    month's actual last day (e.g. 2023-03-31 - 1 month -> 2023-02-28).

    Used to place a review's search cutoff one month before its publication
    date: OpenAlex's date filter is inclusive, so without the shift a review
    finds itself in its own results.
    """
    d = date.fromisoformat(iso)
    total_months = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total_months, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


@dataclass
class GroundTruth:
    """One review's recall target, as the sweep reads it back from a Langfuse
    dataset item."""

    dois: set[str]
    """Reference-list entries with a DOI — the scholarly target."""
    source: Literal["doi", "url"]
    """Whether the review itself was identified by a DOI or a URL."""
    overton_ids: set[str] = field(default_factory=set)
    """``overton:<id>`` keys for reference-list entries that have no DOI but do
    exist in Overton — the policy-document target."""
    titles: dict[str, str] = field(default_factory=dict)
    """Key -> the reference's title, for labelling rows in reports."""

    @property
    def keys(self) -> set[str]:
        """The full recall target: DOI keys and Overton keys together.

        Score against this, not ``dois``, or every policy document in the
        reference list counts as a miss it was never possible to hit.
        """
        return self.dois | self.overton_ids
