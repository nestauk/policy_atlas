"""
I made a mistake when setting up the synthesis evals: the references in each of the POST/
CAPE briefings are obtained from OpenAlex if possible, and if not, the text is retrieved from the url.
Therefore I had to retrospectively check what proportion of references could in theory
have been obtained from Overton.

This script goes through the references list of each briefing and checks which references
could have been got from Overton.

For each reference title, Overton is searched for documents with all the words of the
title in their title. Each candidate records whether its title equals the reference
title (``exact_title_match``) and whether its URL is a reference URL or a parent page
of one (``url_match``). Overton has no search by URL, so the URL can only confirm a candidate,
not find one.

Rapid responses (the briefings saved as HTML) have no reference list, so the ``title``
column of their ``references.csv`` holds the link text, not the title of the cited
source. For those references the title is inferred: the OpenAlex title from the
reference cache, else the ``<title>`` of the cited page, else the words in the URL slug.

Usage:
cd into the directory where this script sits (`scripts/evals/post_screening_and_synthesis`),
then:
```
set -a; source ../../../backend/.env; set +a
../../../backend/.venv/bin/python determine_which_refs_are_in_overton.py
```
"""

import json
from collections import defaultdict
import html
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from utils import GROUND_TRUTH_DIR, RESULTS_DIR, briefing_path, ref_cache_path

API_KEY = os.environ["OVERTON_API_KEY"]
API_URL = "https://app.overton.io/documents.php"

RUN_DIR = RESULTS_DIR / "2026-11-05-deep-necessary-facts"
OUTPUT_PATH = RUN_DIR / "overton_title_matches.jsonl"

TITLE_COLUMN = "title"
MAX_PAGES = 1  # Maximum pages of results to retrieve per title
TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

session = requests.Session()


def normalise_title(title: str) -> str:
    """Normalise a title for comparing search results."""
    title = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"\w+", title))


def normalise_url(url: str | None) -> str:
    """Reduce a URL to host and path, so that scheme, ``www.`` and a trailing slash do not matter."""
    parsed = urlparse((url or "").strip())
    return parsed.netloc.lower().removeprefix("www.") + parsed.path.rstrip("/")


def is_url_match(reference_url: str, candidate_url: str | None) -> bool:
    """Whether a candidate URL is the reference URL, or a parent page of it.

    GOV.UK publishes an HTML attachment one level below the landing page of its
    publication. A briefing can cite the attachment when Overton holds the landing
    page, so a parent page counts as a match.
    """
    reference, candidate = normalise_url(reference_url), normalise_url(candidate_url)
    if not candidate:
        return False
    # A parent must have a path: a host alone is a parent of each page of its site.
    return reference == candidate or (
        "/" in candidate and reference.startswith(candidate + "/")
    )


def infer_title(doc_id: str, label: str, url: str) -> tuple[str, str]:
    """Infer the title of a reference whose ``title`` column holds link text.

    Args:
        doc_id: Briefing Doc ID.
        label: The reference label in ``references.csv``.
        url: The URL of the cited source.

    Returns:
        The inferred title and where it came from: ``openalex`` (the reference cache
        written by ``00_update_ground_truth.py``), ``html_title`` (the ``<title>`` of
        the cited page) or ``url_slug`` (the words in the last part of the URL path).
        The title is empty when none of the three gives any text.
    """
    cache = ref_cache_path(doc_id, label)
    if cache.exists():
        metadata = json.loads(cache.read_text(encoding="utf-8"))["metadata"]
        if metadata.get("backend") == "openalex" and metadata.get("title"):
            return metadata["title"], "openalex"

    try:
        response = session.get(
            html.unescape(url), timeout=30, headers={"User-Agent": "Mozilla/5.0"}
        )
        is_html = response.ok and "html" in response.headers.get("content-type", "")
        found = TITLE_TAG.search(response.text) if is_html else None
    # ValueError: some ``url`` values are not URLs ("https://uk%20civil%20aviation...").
    except (requests.exceptions.RequestException, ValueError):
        found = None
    if found:
        page_title = " ".join(html.unescape(found.group(1)).split())
        # ponytail: keeps the text before the first " - " or " | " to drop the site
        # name ("... - GOV.UK"). This also cuts a title that contains a spaced dash.
        title = re.split(r"\s+[|\-–—]\s+", page_title)[0]
        if title:
            return title, "html_title"

    slug = Path(urlparse(url).path).stem  # last part of the path, without ".pdf"
    return " ".join(re.findall(r"[a-z0-9]+", slug.lower())), "url_slug"


def get_page(title: str, page: int) -> dict:
    """Search Overton document titles for an exact phrase, or for all words of a title.

    The all-words part also finds a document when the title that Overton holds has
    more words or a different word order. The exact phrase part keeps each result of
    a phrase-only search, and Overton ranks those results first.
    """

    # Remove characters that have special meaning in search syntax.
    safe_title = re.sub(r'["*?]', " ", title)
    # Words keep their inner apostrophes, because Overton does not match "children s"
    # to "children’s". A hyphen separates words: "2001-11" gives an HTTP 500, and
    # "covid-19" gives the same results as "covid 19". A token of punctuation only
    # ("&", ".") is dropped, because Overton treats it as a word that the title must
    # contain.
    tokens = (w.strip("'’") for w in re.findall(r"[\w'’]+", title.lower()))
    words = " ".join(w for w in tokens if w)
    query = f'complex:("{safe_title}" OR ({words})):ti'

    params = {
        "api_key": API_KEY,
        "format": "json",
        "query": query,
        "page": page,
    }

    for attempt in range(4):
        # Overton requires no more than one request per second.
        time.sleep(2)

        response = session.get(API_URL, params=params, timeout=30)

        if response.status_code == 429:
            time.sleep(2 ** (attempt + 1))
            continue

        if response.status_code != 200:
            raise RuntimeError(f"Overton returned HTTP {response.status_code}")

        return response.json()

    raise RuntimeError("Overton rate limit exceeded after retries")


def search_title(title: str, urls: set[str]) -> tuple[list[dict], int]:
    """Retrieve candidate policy documents for a title.

    Args:
        title: The title to search for.
        urls: The URLs of the references with this title. Each candidate records in
            ``url_match`` whether its document URL or PDF URL is one of them, or a
            parent page of one (see ``is_url_match``).

    Returns:
        The candidates, most similar title first, and the total number of results.
    """

    candidates = []
    seen_ids = set()
    total_results = 0

    for page in range(1, MAX_PAGES + 1):
        data = get_page(title, page)
        info = data.get("query", {})
        total_results = info.get("total_results", 0)

        results = data.get("results", [])

        for doc in results:
            doc_id = doc.get("policy_document_id")

            if doc_id in seen_ids:
                continue

            seen_ids.add(doc_id)

            overton_title = doc.get("title") or ""
            translated_title = doc.get("translated_title") or ""

            input_normalised = normalise_title(title)

            similarity = max(
                SequenceMatcher(
                    None,
                    input_normalised,
                    normalise_title(candidate_title),
                ).ratio()
                for candidate_title in (overton_title, translated_title)
            )

            candidates.append(
                {
                    "overton_title": overton_title,
                    "translated_title": translated_title,
                    "policy_document_id": doc_id,
                    "pdf_document_id": doc.get("pdf_document_id"),
                    "source": (doc.get("source") or {}).get("title"),
                    "published_on": doc.get("published_on"),
                    "document_url": (
                        doc.get("document_url") or doc.get("policy_document_url")
                    ),
                    "title_similarity": round(similarity, 3),
                    "exact_title_match": similarity == 1.0,
                    "url_match": any(
                        is_url_match(url, doc.get(field))
                        for url in urls
                        for field in ("document_url", "pdf_url")
                    ),
                }
            )

        if not results or page >= int(info.get("pages", 1)):
            break

    candidates.sort(
        key=lambda x: x["title_similarity"],
        reverse=True,
    )

    return candidates, total_results


def load_existing_results(path: Path) -> dict:
    """Load previous searches to support resuming interrupted runs."""
    results = {}

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    # Latest record wins if a title was retried.
                    results[record["input_title"]] = record

    return results


if __name__ == "__main__":
    references_files = []
    for dir in GROUND_TRUTH_DIR.iterdir():
        references_files.extend(dir.glob("*references.csv"))

    # 1. Read all titles, retaining their source files.
    titles_to_search = defaultdict(set)
    urls_by_title = defaultdict(set)
    # Titles that are link text (see the module docstring), with the reference they
    # belong to. No link text occurs with two different URLs.
    link_text_refs = {}

    for csv_file in references_files:
        csv_file = Path(csv_file)
        df = pd.read_csv(csv_file, dtype=str)
        doc_id = csv_file.parent.name
        is_link_text = briefing_path(doc_id).suffix == ".html"

        for row in df.dropna(subset=[TITLE_COLUMN]).to_dict("records"):
            title = row[TITLE_COLUMN].strip()

            if title:
                titles_to_search[title].add(str(csv_file))
                if isinstance(row["url"], str):  # an empty cell is NaN
                    urls_by_title[title].add(row["url"])
                if is_link_text:
                    link_text_refs[title] = (doc_id, row["label"], row["url"])

    # 2. Load previous results.
    existing_results = load_existing_results(OUTPUT_PATH)

    completed = {
        title
        for title, record in existing_results.items()
        if (
            record["status"] == "success"
            and record.get("max_pages") == MAX_PAGES
            # Redo the records of the first method (exact phrase, no URL comparison).
            and "search_text" in record
        )
    }

    print(f"Found {len(titles_to_search)} unique titles.")
    print(f"Already completed: {len(completed & titles_to_search.keys())}")

    # 3. Search and append each result immediately.
    with OUTPUT_PATH.open("a", encoding="utf-8") as f:
        for i, (title, source_files) in enumerate(titles_to_search.items(), start=1):
            if title in completed:
                continue

            # ``input_title`` stays the ``title`` column, which is the key that
            # coverage_analysis.ipynb joins on. ``search_text`` is what was searched.
            search_text, search_text_source = title, TITLE_COLUMN
            if title in link_text_refs:
                search_text, search_text_source = infer_title(*link_text_refs[title])
            urls = urls_by_title[title]

            print(f"[{i}/{len(titles_to_search)}] Searching: {search_text}")

            record = {
                "input_title": title,
                "search_text": search_text,
                "search_text_source": search_text_source,
                "input_urls": sorted(urls),
                "source_files": sorted(source_files),
                "max_pages": MAX_PAGES,
            }

            try:
                # An empty inferred title (a URL with no path) gives nothing to search.
                candidates, total_results = (
                    search_title(search_text, urls) if search_text else ([], 0)
                )

                record |= {
                    "status": "success",
                    "total_results": total_results,
                    "candidates": candidates,
                    "error": None,
                }

            except (
                requests.exceptions.RequestException,
                RuntimeError,
                ValueError,
            ) as e:
                record |= {
                    "status": "error",
                    "total_results": None,
                    "candidates": [],
                    "error": f"{type(e).__name__}: {e}",
                }

            # Append one JSON record and immediately flush to disk.
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

            if record["status"] == "error":
                print(f"Search failed: {record['error']}")
                print("Results saved. Stopping so the error can be retried.")
                break

    print(f"Results saved to {OUTPUT_PATH}")
