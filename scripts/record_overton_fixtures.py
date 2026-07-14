"""Dev-time recorder: fetch real Overton responses, sanitize, write committed fixtures.

Not part of the runtime package — never imported by policy_atlas. Stdlib only.

Fetches one page of policy documents via Overton's semantic mode (``squery`` —
v2's production mode for Overton), honouring the 1 call/second rate limit
(single call here), saves the raw response to the gitignored
``scripts/recordings/`` path, then derives the committed sanitized fixture:
real field names, nesting and nullability patterns (empty-string absence,
string-or-list authors/topics, two-level document identity); fabricated values.
Leak-guard markers: every DOI gets the reserved fake prefix ``10.99999/``,
every URL lands on ``example.org`` (test-enforced).

Usage: uv run --env-file .env python scripts/record_overton_fixtures.py
(``OVERTON_API_KEY`` required; read from the environment, never committed.)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from _fixture_sanitizer import fake_doi as _fake_doi
from _fixture_sanitizer import fake_name as _fake_name
from _fixture_sanitizer import fake_url as _fake_url
from _fixture_sanitizer import fake_words as _fake_words
from _fixture_sanitizer import h as _h

QUERY = "housing affordability policy"
N_RECORDS = 12
TIMEOUT_S = 30
SANITIZER_VERSION = "v2"
RAW_PATH = Path(__file__).parent / "recordings" / "overton_raw.json"
FIXTURE_PATH = (
    Path(__file__).parent.parent / "src" / "policy_atlas" / "data" / "overton_documents.json"
)

# Free-text fields carrying the document's (or provider-LLM's) words — always fabricated.
# Includes the cites-entry fields (reference_string embeds raw URLs mid-string).
_TEXT_KEYS = {
    "title",
    "translated_title",
    "snippet",
    "llm_document_description",
    "llm_document_theme",
    "reference_string",
    "matched_news_outlet",
    "affiliation",
    "journal",
    "publisher",
}


def _fake_slug(s: str) -> str:
    return "sanitizedorg" + _h("slug:" + s)[:6]


def _fake_document_id(s: str) -> str:
    """Preserve the two-level '{source_slug}-{32hex}[-{32hex}]' identity structure."""
    parts = s.split("-")
    slug = _fake_slug(parts[0])
    hexes = [_h("docid:" + p)[:32] for p in parts[1:]]
    return "-".join([slug, *hexes])


def _sanitize_string(value: str, key: str | None, parent: str | None) -> str:
    if not value:
        return value  # empty string is an authentic Overton absence pattern — preserve
    if key in ("policy_document_id", "pdf_document_id", "overton_id",
               "grouped_pdf_ids_in_result"):
        return _fake_document_id(value)
    if key in ("source_id", "policy_source_id"):
        return _fake_slug(value)
    if "doi.org/" in value:
        return "https://doi.org/" + _fake_doi(value)
    if value.startswith(("http://", "https://")):
        return _fake_url(value)
    if value.startswith("10.") and "/" in value:
        return _fake_doi(value)
    # NB list items inherit the list's key (highlights/source_tags/authors entries).
    if key in _TEXT_KEYS or key in ("highlights", "source_tags"):
        return _fake_words(value)
    if key in ("authors", "person"):
        return _fake_name(value)
    if key == "thumbnail_path":
        ext = "." + value.rsplit(".", 1)[-1] if "." in value else ""
        return "cache_image/pdf_thumbnails/sanitized/" + _h("thumb:" + value)[:16] + ext
    # Everything else (source typing, countries, regions, topic/classification
    # taxonomy labels, dates, series labels, …) is shared vocabulary — kept.
    return value


def _sanitize(obj: object, key: str | None = None, parent: str | None = None) -> object:
    if isinstance(obj, dict):
        return {k: _sanitize(v, k, key) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v, key, parent) for v in obj]
    if isinstance(obj, str):
        return _sanitize_string(obj, key, parent)
    return obj


def _fetch() -> dict:
    api_key = os.environ.get("OVERTON_API_KEY")
    if not api_key:
        raise SystemExit("OVERTON_API_KEY not set (run via: uv run --env-file .env …)")
    params = {"squery": QUERY, "format": "json", "api_key": api_key}
    url = "https://app.overton.io/documents.php?" + urllib.parse.urlencode(params)
    # Rate limit: max 1 call/second — this recorder makes exactly one call.
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        return json.load(resp)


def _pick_records(results: list[dict]) -> list[dict]:
    """Greedily pick records that add uncovered quirks, then fill to N_RECORDS."""

    def _koi_doi(r: dict) -> bool:
        koi = r.get("keyed_other_identifiers")
        return isinstance(koi, dict) and bool(koi.get("doi"))

    preds = [
        _koi_doi,                                                  # DOI in the koi list
        lambda r: not _koi_doi(r),                                 # the common no-DOI case
        lambda r: r.get("snippet") == "" and bool(r.get("llm_document_description")),
        lambda r: bool(r.get("translated_title")),
        lambda r: (r.get("source") or {}).get("type") == "government",
        lambda r: (r.get("source") or {}).get("type") == "igo",
        lambda r: (r.get("source") or {}).get("type") == "think tank",
        lambda r: isinstance(r.get("authors"), list) and bool(r.get("authors")),
    ]
    picked: list[dict] = []
    for pred in preds:
        if not any(pred(p) for p in picked):
            match = next((r for r in results if pred(r) and r not in picked), None)
            if match:
                picked.append(match)
    for r in results:
        if len(picked) >= N_RECORDS:
            break
        if r not in picked:
            picked.append(r)
    return picked


def _ensure_quirks(records: list[dict]) -> list[str]:
    """Guarantee contracted quirk coverage; patch shapes only where the live page
    lacked a quirk (patched values are fabricated anyway — the *patterns* are
    v2-confirmed / live-observed Overton behaviours)."""
    quirks: list[str] = []

    def _koi_doi(r: dict) -> bool:
        koi = r.get("keyed_other_identifiers")
        return isinstance(koi, dict) and bool(koi.get("doi"))

    def _check(pred, label, patch=None):
        if any(pred(r) for r in records):
            quirks.append(f"{label} (recorded)")
        else:
            assert patch is not None, f"quirk {label!r} missing and no patch defined — refetch"
            patch()
            quirks.append(f"{label} (patched: v2-confirmed/live-observed shape)")

    _check(_koi_doi, "DOI in keyed_other_identifiers.doi list")
    _check(lambda r: not _koi_doi(r), "no-DOI record (common case)")
    _check(
        lambda r: r.get("snippet") == "" and bool(r.get("llm_document_description")),
        "empty-string snippet with populated llm_document_description",
    )

    def _patch_neither():
        target = next(r for r in records if not _koi_doi(r))
        target["snippet"] = ""
        target["llm_document_description"] = ""

    _check(
        lambda r: not r.get("snippet") and not r.get("llm_document_description"),
        "neither snippet nor llm_document_description",
        _patch_neither,
    )

    def _patch_str_authors():
        target = next(r for r in records if isinstance(r.get("authors"), list))
        target["authors"] = _fake_name("string-authors")

    _check(
        lambda r: isinstance(r.get("authors"), str) and r.get("authors"),
        "string-shaped authors",
        _patch_str_authors,
    )
    _check(
        lambda r: isinstance(r.get("authors"), list) and bool(r.get("authors")),
        "list-shaped authors",
    )

    def _patch_str_topics():
        target = next(r for r in records if isinstance(r.get("topics"), list))
        target["topics"] = "Affordable housing"

    _check(
        lambda r: isinstance(r.get("topics"), str) and r.get("topics"),
        "string-shaped topics",
        _patch_str_topics,
    )
    _check(lambda r: isinstance(r.get("topics"), list) and bool(r.get("topics")),
           "list-shaped topics")

    _check(lambda r: (r.get("source") or {}).get("type") == "government",
           "government publisher")
    _check(lambda r: (r.get("source") or {}).get("type") == "igo", "IGO publisher")
    _check(lambda r: bool(r.get("translated_title")), "translated title")

    def _patch_multi_pdf():
        target = records[0]
        first = target["grouped_pdf_ids_in_result"][0]
        target["grouped_pdf_ids_in_result"] = [first, _fake_document_id(first + "-second")]
        target["grouped_pdf_ids_in_result_count"] = 2

    _check(
        lambda r: (r.get("grouped_pdf_ids_in_result_count") or 0) > 1,
        "multi-PDF grouped document",
        _patch_multi_pdf,
    )
    return quirks


def main() -> None:
    if "--resanitize" in sys.argv:  # re-derive from the existing raw recording, no fetch
        raw = json.loads(RAW_PATH.read_text())
    else:
        raw = _fetch()
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Overton responses can echo request params (next-page URLs) — never let the
        # key rest on disk, even in the gitignored raw path
        raw_text = json.dumps(raw, indent=1)
        api_key = os.environ.get("OVERTON_API_KEY", "")
        if api_key:
            raw_text = raw_text.replace(api_key, "REDACTED_API_KEY")
        RAW_PATH.write_text(raw_text)
        raw = json.loads(raw_text)
    print(f"raw response ({len(raw['results'])} documents) -> {RAW_PATH} (gitignored)")

    records = [_sanitize(r) for r in _pick_records(raw["results"])]
    quirks = _ensure_quirks(records)

    fixture = {
        "_meta": {
            "backend": "overton",
            "mode": "semantic squery",
            "recorder_query": QUERY,
            "recorded_at": datetime.now(UTC).date().isoformat(),
            "record_count": len(records),
            "sanitizer_version": SANITIZER_VERSION,
            "sanitized": "real structure/nesting/nullability, fabricated values; "
            "DOIs 10.99999/*, URLs example.org (leak guard, test-enforced); "
            "residual: authentic dates/counts/scores retained (accepted risk, "
            "see task 007 verification.md)",
            "quirk_coverage": quirks,
        },
        "records": records,
    }
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"sanitized fixture ({len(records)} documents) -> {FIXTURE_PATH}")
    for q in quirks:
        print("  quirk:", q)


if __name__ == "__main__":
    main()
