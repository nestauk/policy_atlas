"""Shared helpers for the ground-truth fetchers (``ground_truth/getters/get_*.py``).

A fetcher downloads one public collection of "a review plus the studies it covers" and
writes it as the two CSV files ``upload.py`` reads. What they share lives here: pulling a
real DOI (Digital Object Identifier) out of a messy field, spotting titles that are not
reviews (protocols, errata), resolving OpenAlex ids to DOIs in batches with a local cache,
the folders under ``results/ground_truth/``, a fetch-once JSON cache, the two CSV column
lists and the writer that joins reviews to references by title.

Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import _bootstrap  # noqa: F401
from evals_search_utils import normalize_doi, openalex_get


_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")


def doi_if_valid(value: Any) -> str | None:
    """A real DOI pulled out of a messy field, or None.

    Source databases write "No DOI", "n/a", a bare DOI, a ``https://doi.org/``
    link or a publisher link into the same column. Anything that does not
    contain a ``10.xxxx/...`` pattern is treated as no DOI at all.
    """
    if not isinstance(value, str):
        return None
    match = _DOI_RE.search(value)
    return normalize_doi(match.group(0).rstrip(".,;)")) if match else None


def _plain(phrase: str) -> str:
    """Lower-case every word except acronyms, read " / " as " or " and " + " as " and "."""
    phrase = phrase.replace(" / ", " or ").replace(" + ", " and ").strip()
    words = []
    for word in phrase.split(" "):
        # An acronym (CBT, PAH, COVID-19) has two or more capitals in one part; keep it.
        acronym = any(sum(c.isupper() for c in part) >= 2 for part in word.split("-"))
        words.append(word if acronym else word.lower())
    return " ".join(words)


_MAP_TYPE_TAIL_RE = re.compile(
    r"\s*(?:rapid\s+)?(?:evidence\s+(?:and\s+)?gap\s+map|evidence\s+map|systematic\s+map)\s*$",
    re.IGNORECASE,
)
_MAP_TYPE_HEAD_RE = re.compile(
    r"^\s*(?:rapid\s+)?evidence\s+(?:gap\s+)?map:\s*", re.IGNORECASE
)


def gap_map_question(theme: str, row: str | None = None) -> str:
    """A question-shaped intent for a gap-map row, built the same way every time.

    A gap-map row's title is "<map title>: <intervention label>", which no search engine
    handles well. This turns the two parts into one plain question, deterministically:
    "What is the evidence on <intervention> in relation to <map theme>?" (or, for a whole
    map, "What is the evidence on <map theme>?"). Title-case words are lower-cased, acronyms
    such as CBT are kept, " / " becomes " or " and " + " becomes " and ". Anyone who wants a
    better question for one row can overwrite the ``intent`` column by hand; the uploader
    sends whatever is there.

    Args:
        theme: The map title, already passed through ``clean_review_title``.
        row: The intervention row or strand label; None for the whole map.

    Returns:
        One question, ending in a question mark.
    """
    # A map title may carry its own type with no separator for clean_review_title to anchor
    # on ("Nutrition-Sensitive Agriculture Evidence Gap Map", "Rapid Evidence Map: ...").
    theme = _MAP_TYPE_TAIL_RE.sub("", theme)
    theme = _MAP_TYPE_HEAD_RE.sub("", theme)
    if row:
        return f"What is the evidence on {_plain(row)} in relation to {_plain(theme)}?"
    return f"What is the evidence on {_plain(theme)}?"


# Titles that a review database lists but that are not reviews with a reference
# list worth scoring against: protocols announce a review, errata correct one.
NOT_A_REVIEW_TITLE_RE = re.compile(
    r"^\s*(protocol|erratum|corrigendum|correction|retraction)\b", re.IGNORECASE
)


def resolve_openalex_works(ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Look up many OpenAlex works by id (``W123`` or the full URL), 50 per call.

    Returns:
        ``{"W123": {"id", "doi", "title", "publication_year", "publication_date"}}``
        for every id OpenAlex knows. Ids it does not know are simply absent.
    """
    wanted = sorted({str(i).rsplit("/", 1)[-1] for i in ids if i})
    found: dict[str, dict[str, Any]] = {}
    for start in range(0, len(wanted), 50):
        batch = wanted[start : start + 50]
        resp = openalex_get(
            "/works",
            filter=f"openalex_id:{'|'.join(batch)}",
            select="id,doi,title,publication_year,publication_date",
            **{"per-page": "50"},
        )
        resp.raise_for_status()
        for work in resp.json()["results"]:
            found[work["id"].rsplit("/", 1)[-1]] = work
    return found


def resolve_openalex_works_cached(
    path: Path, ids: Iterable[str], refresh: bool = False
) -> dict[str, dict[str, Any]]:
    """``resolve_openalex_works`` behind a JSON cache at ``path``.

    Only ids missing from the cache are fetched, so widening a selection later
    costs only the new lookups. Ids OpenAlex does not know are re-asked each
    run; there are few of them.
    """
    found: dict[str, dict[str, Any]] = {}
    if path.exists() and not refresh:
        with path.open(encoding="utf-8") as handle:
            found = json.load(handle)
    missing = {str(i).rsplit("/", 1)[-1] for i in ids if i} - set(found)
    if missing:
        found.update(resolve_openalex_works(missing))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(found, handle, ensure_ascii=False)
    return found


# Where the ``get_*.py`` fetchers put things. Git ignores everything under
# ``results/`` except ``history.md``, so raw downloads never enter the repo.
GROUND_TRUTH_DIR = Path(__file__).resolve().parents[1] / "results" / "ground_truth"
RAW_DIR = GROUND_TRUTH_DIR / "raw"


def cached_json(path: Path, fetch: Callable[[], Any], refresh: bool = False) -> Any:
    """Return ``path``'s JSON, or call ``fetch()`` and save the result there first.

    Re-running a fetcher after a code change then costs no network calls.
    ``refresh=True`` forces the download.
    """
    if path.exists() and not refresh:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    return data


# The two CSV shapes ``ground_truth/upload.py`` reads (its loaders ignore the
# extra columns, which are there for the human doing the labelling).
REVIEW_COLUMNS = (
    "title",
    "intent",
    "doi",
    "url",
    "published_before",
    "exclude",
    "dataset",
    "review_id",
    "level",
    "n_references",
    "n_with_doi",
    "research_questions",
)
REFERENCE_COLUMNS = (
    "review_title",
    "ref_title",
    "label",
    "doi",
    "overton_id",
    "url",
    "year",
    "ref_id",
)


def write_ground_truth(
    name: str,
    reviews: list[dict[str, Any]],
    references: list[dict[str, Any]],
    out_dir: Path = GROUND_TRUTH_DIR,
) -> tuple[Path, Path]:
    """Write ``<name>_reviews.csv`` and ``<name>_references.csv`` in the shape
    ``ground_truth/upload.py`` expects, and print a one-line summary.

    Every reference row must name a review title that appears in ``reviews``:
    that title is the join key, so a mismatch would silently lose the row.
    """
    titles = {r["title"] for r in reviews}
    orphans = [r["review_title"] for r in references if r["review_title"] not in titles]
    if orphans:
        raise ValueError(
            f"{len(orphans)} reference row(s) name a review that is not in the reviews list: {orphans[:3]}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = (out_dir / f"{name}_reviews.csv", out_dir / f"{name}_references.csv")
    for path, rows, columns in zip(
        paths, (reviews, references), (REVIEW_COLUMNS, REFERENCE_COLUMNS), strict=True
    ):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    with_doi = sum(1 for r in references if r.get("doi"))
    print(
        f"{name}: {len(reviews)} reviews, {len(references)} references ({with_doi} with a DOI) -> {paths[0].parent}"
    )
    return paths
