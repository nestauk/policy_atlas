"""
I made a mistake when setting up the synthesis evals: the references in each of the POST/
CAPE briefings are obtained from OpenAlex if possible, and if not, the text is retrieved from the url.
Therefore I had to retrospectively check what proportion of references could in theory
have been obtained from Overton.

This script goes through the references list of each briefing and checks which references
could have been got from Overton.

Usage:
cd into the directory where this script sits (`scripts/evals/post_screening_and_synthesis`),
then:
```
set -a; source ../../../backend/.env; set +a
../../../backend/.venv/bin/python determine_which_refs_are_in_overton.py
```
"""

import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

from utils import GROUND_TRUTH_DIR, RESULTS_DIR

API_KEY = os.environ["OVERTON_API_KEY"]
API_URL = "https://app.overton.io/documents.php"

import json
from collections import defaultdict

RUN_DIR = RESULTS_DIR / "2026-11-05-deep-necessary-facts"
OUTPUT_PATH = RUN_DIR / "overton_title_matches.jsonl"

TITLE_COLUMN = "title"
MAX_PAGES = 1  # Maximum pages of results to retrieve per title

session = requests.Session()

def normalise_title(title: str) -> str:
    """Normalise a title for comparing search results."""
    title = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"\w+", title))


def get_page(title: str, page: int) -> dict:
    """Search Overton for an exact phrase within document titles."""

    # Remove characters that have special meaning in search syntax.
    safe_title = re.sub(r'["*?]', " ", title)
    query = f'complex:"{safe_title}":ti'

    params = {
        "api_key": API_KEY,
        "format": "json",
        "query": query,
        "page": page,
    }

    for attempt in range(4):
        # Overton requires no more than one request per second.
        time.sleep(2)

        response = session.get(
            API_URL, params=params, timeout=30
        )

        if response.status_code == 429:
            time.sleep(2 ** (attempt + 1))
            continue

        if response.status_code != 200:
            raise RuntimeError(
                f"Overton returned HTTP {response.status_code}"
            )

        return response.json()

    raise RuntimeError("Overton rate limit exceeded after retries")


def search_title(title: str) -> tuple[list[dict], int]:
    """Retrieve candidate policy documents for a title."""

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

            candidates.append({
                "overton_title": overton_title,
                "translated_title": translated_title,
                "policy_document_id": doc_id,
                "pdf_document_id": doc.get("pdf_document_id"),
                "source": (doc.get("source") or {}).get("title"),
                "published_on": doc.get("published_on"),
                "document_url": (
                    doc.get("document_url")
                    or doc.get("policy_document_url")
                ),
                "title_similarity": round(similarity, 3),
                "exact_title_match": similarity == 1.0,
            })

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

    for csv_file in references_files:
        csv_file = Path(csv_file)
        df = pd.read_csv(csv_file)

        for value in df[TITLE_COLUMN].dropna():
            title = str(value).strip()

            if title:
                titles_to_search[title].add(str(csv_file))


    # 2. Load previous results.
    existing_results = load_existing_results(OUTPUT_PATH)

    completed = {
        title
        for title, record in existing_results.items()
        if (
            record["status"] == "success"
            and record.get("max_pages") == MAX_PAGES
        )
    }

    print(f"Found {len(titles_to_search)} unique titles.")
    print(f"Already completed: {len(completed & titles_to_search.keys())}")


    # 3. Search and append each result immediately.
    with OUTPUT_PATH.open("a", encoding="utf-8") as f:

        for i, (title, source_files) in enumerate(
            titles_to_search.items(), start=1
        ):

            if title in completed:
                continue

            print(f"[{i}/{len(titles_to_search)}] Searching: {title}")

            try:
                candidates, total_results = search_title(title)

                record = {
                    "input_title": title,
                    "source_files": sorted(source_files),
                    "status": "success",
                    "total_results": total_results,
                    "max_pages": MAX_PAGES,
                    "candidates": candidates,
                    "error": None,
                }

            except (
                requests.exceptions.RequestException,
                RuntimeError,
                ValueError,
            ) as e:
                record = {
                    "input_title": title,
                    "source_files": sorted(source_files),
                    "status": "error",
                    "total_results": None,
                    "max_pages": MAX_PAGES,
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