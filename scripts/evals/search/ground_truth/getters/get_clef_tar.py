"""CLEF TAR 2017 + 2018 medical reviews -> ground-truth CSVs.

CLEF TAR (Conference and Labs of the Evaluation Forum, Technology-Assisted Review) is a
public test collection of Cochrane diagnostic test accuracy reviews
(https://github.com/CLEF-TAR/tar, MIT licence). For each review it gives the title, the
expert Boolean query, the PubMed ids the query returned (the "pool") and which of those
the review authors kept after reading the title and abstract (the "abstract-level"
labels). Wang et al. (SIGIR 2023, arXiv 2302.03495) used exactly these 72 reviews to test
LLM-written Boolean queries, so scoring our search on them gives figures we can set
beside theirs. We read the 2018 Task 2 copy: its training topics are the 42 kept 2017
reviews, its testing topics the 30 new 2018 reviews.

What the script writes (the two CSVs ``ground_truth/upload.py`` reads):

* ``results/ground_truth/clef_tar_reviews.csv`` — one row per review. The intent is the
  review title as it is (Wang et al. also started from the title). ``published_before``
  is the review's search date: the end of the search range for the 2018 reviews
  (``pubdates.txt``), and for the 2017 reviews, which have no dates, the publication date
  of the newest record in the expert query's pool that OpenAlex knows (the pool was retrieved on the search
  date, so nothing newer was ever in it).
* ``results/ground_truth/clef_tar_references.csv`` — one row per relevant study, labelled
  ``content`` because the labels are real relevance judgements, not a raw reference list.
  Each PubMed id is mapped to its OpenAlex record for the DOI. A study with no DOI, or
  that OpenAlex does not know, is still written (``ref_id`` says ``pmid:<id>``); the
  uploader counts it as unscorable, and the summary line says how many there are.

Raw downloads are cached under ``results/ground_truth/raw/clef_tar/``, so a re-run makes
no network calls unless ``--refresh`` is passed.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/ground_truth/getters/get_clef_tar.py [--refresh]
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
from collections import defaultdict
from typing import Any

import httpx
from evals_search_utils import normalize_doi, openalex_get
from fetch_helpers import RAW_DIR, cached_json, write_ground_truth

RAW = RAW_DIR / "clef_tar"
REPO = "CLEF-TAR/tar"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/master/2018-TAR"
SPLITS = {
    # split folder -> abstract-level qrels file in that folder
    "Training": "Training/qrels/full.train.abs.2018.qrels",
    "Testing": "Testing/qrels/full.test.abs.2018.qrels",
}
PUBDATES = "Task1/Testing/pubdates.txt"
BATCH = 50  # OpenAlex accepts up to 50 values in one filter
# A pool's newest PubMed id is sometimes missing from OpenAlex, so the date is taken
# from the latest of its few newest ids (PubMed ids grow over time).
NEWEST = 5


def _text(path: str) -> str:
    resp = httpx.get(f"{RAW_URL}/{path}", timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def topic_ids(split: str) -> list[str]:
    """The topic file names (Cochrane review ids) in one split's ``topics/`` folder."""
    resp = httpx.get(
        f"https://api.github.com/repos/{REPO}/contents/2018-TAR/Task2/{split}/topics",
        timeout=60.0,
    )
    resp.raise_for_status()
    return sorted(entry["name"] for entry in resp.json() if entry["type"] == "file")


def parse_topic(text: str) -> dict[str, Any]:
    """Title and pool PubMed ids from one topic file ("Title:" line, "Pids:" block)."""
    title = ""
    pids: list[str] = []
    in_pids = False
    for line in text.splitlines():
        if line.startswith("Title:"):
            title = line.removeprefix("Title:").strip()
        elif line.startswith("Pids:"):
            in_pids = True
        elif in_pids and line.strip().isdigit():
            pids.append(line.strip())
    return {"title": title, "pids": pids}


def relevant_pmids(qrels: str) -> dict[str, list[str]]:
    """Topic -> PubMed ids judged relevant (fourth column above 0)."""
    out: dict[str, list[str]] = defaultdict(list)
    for line in qrels.splitlines():
        parts = line.split()
        if len(parts) == 4 and int(parts[3]) > 0:
            out[parts[0]].append(parts[2])
    return out


def resolve_pmids(pmids: list[str]) -> dict[str, dict[str, Any]]:
    """PubMed id -> OpenAlex record (id, doi, title, publication date), 50 per call."""
    wanted = sorted(set(pmids))
    found: dict[str, dict[str, Any]] = {}
    for start in range(0, len(wanted), BATCH):
        resp = openalex_get(
            "/works",
            filter=f"ids.pmid:{'|'.join(wanted[start : start + BATCH])}",
            select="id,doi,title,publication_date,ids",
            **{"per-page": str(BATCH)},
        )
        resp.raise_for_status()
        for work in resp.json()["results"]:
            pmid = (work.get("ids") or {}).get("pmid", "").rsplit("/", 1)[-1]
            if pmid:
                found[pmid] = work
    return found


def download() -> dict[str, Any]:
    """Every topic's title, pool and relevant ids, plus the 2018 search dates."""
    topics: dict[str, Any] = {}
    for split, qrels_path in SPLITS.items():
        relevant = relevant_pmids(_text(f"Task2/{qrels_path}"))
        for topic in topic_ids(split):
            parsed = parse_topic(_text(f"Task2/{split}/topics/{topic}"))
            topics[topic] = {**parsed, "split": split, "relevant": relevant[topic]}
    pubdates = {}
    for line in _text(PUBDATES).splitlines():
        parts = line.split()
        if len(parts) == 3:
            end = parts[2]
            pubdates[parts[0]] = f"{end[:4]}-{end[4:6]}-{end[6:]}"
    return {"topics": topics, "pubdates": pubdates}


def build_rows(
    data: dict[str, Any],
    newest: dict[str, dict[str, Any]],
    resolved: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Shape the two CSVs. ``newest`` maps a pool's newest PubMed id to its record."""
    review_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    for topic, t in sorted(data["topics"].items()):
        cutoff = data["pubdates"].get(topic)
        if not cutoff:
            dates = [
                (newest.get(pmid) or {}).get("publication_date") or ""
                for pmid in sorted(t["pids"], key=int)[-NEWEST:]
            ]
            cutoff = max(dates) or None
        if not cutoff or not t["relevant"]:
            print(f"  SKIPPED {topic}: no cutoff date or no relevant studies")
            continue
        n_with_doi = 0
        for pmid in t["relevant"]:
            work = resolved.get(pmid) or {}
            doi = normalize_doi(work.get("doi")) or ""
            n_with_doi += bool(doi)
            reference_rows.append(
                {
                    "review_title": t["title"],
                    "ref_title": work.get("title") or f"PubMed {pmid}",
                    "label": "content",
                    "doi": doi,
                    "overton_id": "",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "year": (work.get("publication_date") or "")[:4],
                    "ref_id": work["id"].rsplit("/", 1)[-1] if work else f"pmid:{pmid}",
                }
            )
        review_rows.append(
            {
                "title": t["title"],
                "intent": t["title"],
                "doi": "",
                "url": f"https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.{topic}",
                "published_before": cutoff,
                "exclude": "",
                "dataset": f"clef_tar_{'2017' if t['split'] == 'Training' else '2018'}",
                "review_id": topic,
                "level": "review",
                "n_references": len(t["relevant"]),
                "n_with_doi": n_with_doi,
                "research_questions": "",
            }
        )
    titles = [r["title"] for r in review_rows]
    if len(set(titles)) != len(titles):
        raise ValueError(
            "two CLEF TAR reviews share a title; the CSV join key would clash"
        )
    return review_rows, reference_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the raw cache and download again.",
    )
    args = parser.parse_args()

    data = cached_json(RAW / "topics.json", download, args.refresh)
    topics = data["topics"]
    print(
        f"{len(topics)} CLEF TAR reviews "
        f"({sum(t['split'] == 'Training' for t in topics.values())} from 2017, "
        f"{sum(t['split'] == 'Testing' for t in topics.values())} from 2018)"
    )
    undated = [
        pmid
        for k, t in topics.items()
        if k not in data["pubdates"]
        for pmid in sorted(t["pids"], key=int)[-NEWEST:]
    ]
    newest = cached_json(
        RAW / "newest_pool_records.json", lambda: resolve_pmids(undated), args.refresh
    )
    pmids = [p for t in topics.values() for p in t["relevant"]]
    resolved = cached_json(
        RAW / "relevant_records.json", lambda: resolve_pmids(pmids), args.refresh
    )
    print(
        f"{len(set(pmids))} relevant PubMed ids, {len(resolved)} found in OpenAlex, "
        f"{sum(1 for w in resolved.values() if w.get('doi'))} with a DOI"
    )
    write_ground_truth("clef_tar", *build_rows(data, newest, resolved))


if __name__ == "__main__":
    main()
