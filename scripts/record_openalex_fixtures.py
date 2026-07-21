"""Dev-time recorder: fetch real OpenAlex responses, sanitize, write committed fixtures.

Not part of the runtime package — never imported by policy_atlas. Stdlib only.

Fetches one page of Work objects via the keyword form v2 used
(``filter=title_and_abstract.search:<query>``), saves the raw response to the
gitignored ``scripts/recordings/`` path, then derives the committed sanitized
fixture: real field names, nesting and nullability patterns; fabricated values.
Leak-guard markers: every DOI gets the reserved fake prefix ``10.99999/``,
every URL lands on ``example.org`` (test-enforced).

Usage: uv run --project backend python scripts/record_openalex_fixtures.py
(``OPENALEX_API_KEY`` optional — OpenAlex works keyless.)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from _fixture_sanitizer import LEXICON as _LEXICON
from _fixture_sanitizer import fake_doi as _fake_doi
from _fixture_sanitizer import fake_name as _fake_name
from _fixture_sanitizer import fake_url as _fake_url
from _fixture_sanitizer import fake_words as _fake_words
from _fixture_sanitizer import h as _h

QUERY = "housing affordability policy"
N_RECORDS = 12
TIMEOUT_S = 30
SANITIZER_VERSION = "v2"
RAW_PATH = Path(__file__).parent / "recordings" / "openalex_raw.json"
FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "backend"
    / "tests"
    / "data"
    / "provider_records"
    / "openalex_works.json"
)


def _fake_issn(s: str) -> str:
    digits = "".join(str(int(c, 16) % 10) for c in _h("issn:" + s)[:8])
    return f"{digits[:4]}-{digits[4:]}"


def _sanitize_string(value: str, key: str | None, parent: str | None) -> str:
    if not value:
        return value  # empty string is an authentic absence pattern — preserve
    if "doi.org/" in value:
        return "https://doi.org/" + _fake_doi(value)
    if value.startswith("doi:"):
        return "doi:" + _fake_doi(value)
    if value.startswith("pmh:"):  # OAI-PMH repository ids carry repo domains + real ids
        return "pmh:oai:example.org:" + _h("pmh:" + value)[:12]
    if value.startswith(("http://", "https://")):
        return _fake_url(value)
    if value.startswith("10.") and "/" in value:
        return _fake_doi(value)
    if key in ("issn_l",) or parent == "issn":
        return _fake_issn(value)
    if key in ("funder_award_id", "award_id"):
        # real grant IDs are unique, indexed identifiers — one API query re-identifies
        # the whole record; hash like mag below
        return _h("award:" + value)[:8]
    if key == "mag":
        return "".join(str(int(c, 16) % 10) for c in _h("mag:" + value)[:10])
    if key == "display_name" and parent == "author":
        return _fake_name(value)
    if key == "raw_author_name":
        return _fake_name(value)
    # Free-text keys carrying names/titles/affiliations anywhere in the Work object.
    # NB list items inherit the list's key (e.g. raw_affiliation_strings entries).
    if key in (
        "display_name",
        "title",
        "raw_source_name",
        "host_organization_name",
        "host_organization_lineage_names",
        "funder_display_name",
        "raw_affiliation_string",
        "raw_affiliation_strings",
    ):
        return _fake_words(value)
    # Everything else (enums, language/country codes, dates, oa_status, …) is
    # non-identifying vocabulary — kept as authentic values.
    return value


def _sanitize_inverted_index(index: dict[str, list[int]]) -> dict[str, list[int]]:
    """Fabricate tokens, preserve the position structure exactly (incl. multi-position)."""
    out: dict[str, list[int]] = {}
    for i, (token, positions) in enumerate(index.items()):
        fake = _LEXICON[int(_h("tok:" + token)[:2], 16) % len(_LEXICON)]
        while fake in out:  # collisions would merge position lists — keep tokens distinct
            fake += str(i % 10)
        out[fake] = positions
    return out


def _sanitize(obj: object, key: str | None = None, parent: str | None = None) -> object:
    if key == "abstract_inverted_index" and isinstance(obj, dict):
        return _sanitize_inverted_index(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v, k, key) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v, key, parent) for v in obj]
    if isinstance(obj, str):
        return _sanitize_string(obj, key, parent)
    return obj


def _fetch() -> dict:
    params = {
        "filter": f"title_and_abstract.search:{QUERY}",
        "per-page": "25",
    }
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    mailto = os.environ.get("OPENALEX_EMAIL")
    if mailto:
        params["mailto"] = mailto  # polite pool
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        return json.load(resp)


def _ensure_quirks(records: list[dict]) -> list[str]:
    """Guarantee the contracted quirk coverage; patch shapes only where the live
    page lacked a quirk (patched values are fabricated anyway — the *pattern* is
    authentic per the OpenAlex docs: these fields are nullable / enum-valued)."""
    quirks: list[str] = []

    def _find(pred, label):
        for r in records:
            if pred(r):
                return r, f"{label} (recorded)"
        return None, None

    r, note = _find(lambda r: r.get("abstract_inverted_index") is None, "missing abstract")
    if r is None:
        records[1]["abstract_inverted_index"] = None
        note = "missing abstract (patched: nulled per documented nullability)"
    quirks.append(note)

    r, note = _find(lambda r: r.get("publication_year") is None, "missing year")
    if r is None:
        target = next(rec for rec in records if rec.get("abstract_inverted_index") is not None)
        target["publication_year"] = None
        target["publication_date"] = None
        note = "missing year (patched: nulled per documented nullability)"
    quirks.append(note)

    r, note = _find(lambda r: r.get("type") not in (None, "article"), "non-article type")
    if r is None:
        records[2]["type"] = "report"
        note = "non-article type (patched: 'report' from the documented type vocabulary)"
    quirks.append(note)

    r, note = _find(lambda r: r.get("language") not in (None, "en"), "non-English record")
    if r is None:
        records[3]["language"] = "fr"
        note = "non-English record (patched: 'fr')"
    quirks.append(note)

    r, note = _find(lambda r: r.get("doi") is None, "missing doi")
    if r is None:
        records[4]["doi"] = None
        if isinstance(records[4].get("ids"), dict):
            records[4]["ids"].pop("doi", None)
        note = "missing doi (patched: nulled per documented nullability)"
    quirks.append(note)

    multi = any(
        any(len(p) > 1 for p in (rec.get("abstract_inverted_index") or {}).values())
        for rec in records
    )
    assert multi, "no record with a multi-position inverted-index token — refetch"
    quirks.append("structurally real abstract_inverted_index with multi-position tokens (recorded)")
    return quirks


def main() -> None:
    if "--resanitize" in sys.argv:  # re-derive from the existing raw recording, no fetch
        raw = json.loads(RAW_PATH.read_text())
    else:
        raw = _fetch()
        RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
        RAW_PATH.write_text(json.dumps(raw, indent=1))
    print(f"raw response ({len(raw['results'])} works) -> {RAW_PATH} (gitignored)")

    records = [_sanitize(r) for r in raw["results"][:N_RECORDS]]
    quirks = _ensure_quirks(records)

    fixture = {
        "_meta": {
            "backend": "openalex",
            "mode": "keyword filter=title_and_abstract.search",
            "recorder_query": QUERY,
            "recorded_at": datetime.now(UTC).date().isoformat(),
            "record_count": len(records),
            "sanitizer_version": SANITIZER_VERSION,
            "sanitized": "real structure/nesting/nullability, fabricated values; "
            "DOIs 10.99999/*, URLs example.org (leak guard, test-enforced); "
            "residual: authentic dates/counts/biblio retained (accepted risk, "
            "see task 007 verification.md)",
            "quirk_coverage": quirks,
        },
        "records": records,
    }
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"sanitized fixture ({len(records)} works) -> {FIXTURE_PATH}")
    for q in quirks:
        print("  quirk:", q)


if __name__ == "__main__":
    main()
