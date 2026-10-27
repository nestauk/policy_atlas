"""Shared paths, readers and model helpers for the post-screening synthesis coverage eval.

Not a script. Imported by ``ground_truth.py``, ``run_synthesis.py``, ``upload.py`` and
the tests after ``_bootstrap``.
"""

from __future__ import annotations

import csv
import hashlib
import html as html_lib
import re
import unicodedata
from pathlib import Path
from typing import Any

from openai import OpenAI
from policy_atlas.core.openai_client import resolve_openai_client
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    THIN_TEXT_MIN_CHARS,
    parse_and_segment,
)

ROOT = Path(__file__).resolve().parent
TEST_SET_CSV = ROOT / "inputs" / "POST_test_set.csv"
BRIEFINGS_DIR = ROOT / "inputs" / "briefings"
GROUND_TRUTH_DIR = ROOT / "ground_truth"
DATASETS_DIR = ROOT / "datasets"
RESULTS_DIR = ROOT / "results" / "runs"
PROMPTS_DIR = ROOT / "prompts"

# Eval-side model for extraction and judging (decision, 2026-10-21).
MODEL = "gpt-5.6-luna"
# Langfuse experiment name; also the `experiment` metadata key on every eval trace.
EXPERIMENT = "synthesis-coverage"
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
}


def load_test_set(doc_ids: list[str] | None = None) -> list[dict[str, str]]:
    """Rows of the POST test set CSV, optionally filtered to the given Doc IDs.

    Args:
        doc_ids: Doc IDs to keep, or None for all 19.

    Raises:
        ValueError: If a requested Doc ID is not in the CSV.
    """
    with TEST_SET_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if doc_ids is None:
        return rows
    wanted = set(doc_ids)
    rows = [r for r in rows if r["Doc ID"] in wanted]
    missing = wanted - {r["Doc ID"] for r in rows}
    if missing:
        raise ValueError(f"unknown Doc ID(s): {sorted(missing)}")
    return rows


def load_kept(doc_id: str, name: str) -> list[dict[str, str]]:
    """Rows of ``ground_truth/<doc_id>/<name>.csv`` whose ``keep`` column is ``y``."""
    path = GROUND_TRUTH_DIR / doc_id / f"{name}.csv"
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["keep"].strip().lower() == "y"]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    """Write rows to a CSV with the given header, creating parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def briefing_path(doc_id: str) -> Path:
    """The hand-downloaded briefing ``inputs/briefings/<doc_id>.<pdf|html>``.

    Raises:
        FileNotFoundError: If there is not exactly one such file.
    """
    hits = [p for p in BRIEFINGS_DIR.glob(f"{doc_id}.*") if p.suffix in CONTENT_TYPES]
    if len(hits) != 1:
        raise FileNotFoundError(
            f"expected one briefing file {doc_id}.<pdf|html> in {BRIEFINGS_DIR}, found {hits}"
        )
    return hits[0]


def parse_bytes(body: bytes, content_type: str) -> list[str] | None:
    """Chunk texts from the production parser, or None when it reports an error."""
    result = parse_and_segment(body, content_type, THIN_TEXT_MIN_CHARS)
    if result["status"] != "ok":
        return None
    return [c["content"] for c in result["chunks"]]


# Rapid responses on post.parliament.uk cite by inline hyperlink and have no reference
# list. The production HTML parser drops hrefs, so the briefing text is rewritten first:
# each external link becomes ``anchor text [n]`` and a "References" list of
# ``[n] anchor text — url`` is appended after parsing. Site and social links are skipped.
_LINK = re.compile(r'<a\b[^>]*?href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_SKIP_HOSTS = (
    "parliament.uk",
    "twitter.com",
    "x.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "instagram.com",
    "whatsapp.com",
)


def mark_links(html: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace each external ``<a>`` with ``inner [n]``; return the html and (text, url) list."""
    refs: list[tuple[str, str]] = []

    def repl(m: re.Match[str]) -> str:
        url, inner = m.group(1), m.group(2)
        if any(host in url for host in _SKIP_HOSTS):
            return m.group(0)
        text = html_lib.unescape(re.sub(r"<[^>]+>", "", inner)).split()
        refs.append((" ".join(text), url))
        return f"{inner} [{len(refs)}]"

    return _LINK.sub(repl, html), refs


def briefing_text(doc_id: str) -> str:
    """The briefing's text as the extract prompt sees it.

    PDFs go straight through the production parser. HTML is link-marked first (see
    ``mark_links``) and gets a generated References list appended.

    Raises:
        SystemExit: If the production parser rejects the file.
    """
    path = briefing_path(doc_id)
    content_type = CONTENT_TYPES[path.suffix]
    body = path.read_bytes()
    refs: list[tuple[str, str]] = []
    if content_type == "text/html":
        marked, refs = mark_links(body.decode("utf-8", errors="replace"))
        body = marked.encode("utf-8")
    chunks = parse_bytes(body, content_type)
    if chunks is None:
        raise SystemExit(f"production parser rejected {path}")
    text = "\n\n".join(chunks)
    if refs:
        text += "\n\nReferences\n" + "\n".join(
            f"[{i}] {t} — {u}" for i, (t, u) in enumerate(refs, start=1)
        )
    return text


def norm_title(title: str | None) -> str:
    """Lower case, no accents, no punctuation, single spaces.

    Copy of ``norm`` in ``scripts/evals/search/experiments/title_match.py``, which cannot
    be imported without that eval's whole import chain.
    """
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def openai_client() -> OpenAI:
    """An OpenAI client from ``OPENAI_API_KEY``; long timeout for whole-briefing calls."""
    return resolve_openai_client(
        None, backend_name="synthesis eval", timeout=600.0, max_retries=2
    )


def prompt(name: str) -> tuple[str, str]:
    """Prompt text and the first 12 hex chars of its sha256, for run records."""
    text = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
