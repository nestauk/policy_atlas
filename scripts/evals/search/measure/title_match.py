"""Title matching for the references and candidates that have no DOI (R&D, task 049).

The recall evaluation scores on DOIs. A reference without a DOI (a government report,
a working paper, a book chapter) can never be a hit, and a candidate without a DOI (most
Overton policy documents, some OpenAlex records) can never score. This script measures
what that hides, offline, by matching **titles**:

1. **Target.** Every reference in the mini sample file, DOI or not
   (``results/ground_truth/sample_mini_references.csv``: title, year, DOI). The four
   hand-made reviews are not in that file, so they are left out here.
2. **Candidates.** Three lists per review, each with titles: the Overton policy
   documents of an ``overton_recall.py`` arm (their own titles, English title first,
   and their own DOI when they have one); the papers those documents cite that carry
   no DOI (titles only); and the OpenAlex pool of a ``snowball_recall.py`` run.
3. **Match.** Titles are normalised: lower case, accents and punctuation removed,
   spaces collapsed. ``strict`` is equality of normalised titles. ``loose`` adds a
   fallback for near-identical titles (``difflib`` ratio at least 0.92) when both
   titles have at least six words, so subtitle and punctuation differences count and
   short generic titles do not. Every loose match is printed so it can be checked by
   eye; this is a deterministic rule, not a judgement.
4. **Report.** Per review: how many references lack a DOI, how many of those a title
   match finds on each candidate list, and how many **extra** DOI-bearing references a
   title match finds on candidates that have no DOI (the reverse gap). Then the recall
   of the Overton route and of the OpenAlex pool with both keys counted, against the
   DOI-only recall, so the size of the blind spot is one number.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/measure/title_match.py \\
        [--arm docs-cites-all-400] [--run RUN_FOLDER] [--loose] [--show]

Reads the ground truth from Langfuse (for the review titles) and otherwise only files
that other scripts cached.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import CACHE_DIR
from evals_search_utils import DEFAULT_DATASET, normalize_doi
from snowball_recall import slug

import argparse
import collections
import csv
import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from policy_atlas.core import tracing

RESULTS = Path(__file__).resolve().parents[1] / "results"
REFERENCES = RESULTS / "ground_truth" / "sample_mini_references.csv"
DEFAULT_RUN = (
    RESULTS / "snowball" / "2026-10-06-shared+semantic-c6e320-s200-k200-f200p10c300t20"
)
LOOSE_RATIO = 0.92
LOOSE_MIN_WORDS = 6


def norm(title: str | None) -> str:
    """Lower case, no accents, no punctuation, single spaces."""
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def match(
    ref_titles: dict[str, str], cand_titles: list[str], *, loose: bool
) -> dict[str, tuple[str, str]]:
    """Reference key -> (candidate title, 'strict' | 'loose') for every matched reference."""
    found: dict[str, tuple[str, str]] = {}
    by_norm: dict[str, str] = {}
    for title in cand_titles:
        n = norm(title)
        if n:
            by_norm.setdefault(n, title)
    for key, ref_title in ref_titles.items():
        n = norm(ref_title)
        if not n:
            continue
        if n in by_norm:
            found[key] = (by_norm[n], "strict")
            continue
        if loose and len(n.split()) >= LOOSE_MIN_WORDS:
            # difflib over the whole list is O(n) per reference; the lists are
            # a few thousand titles, fine offline.
            for cand_norm, cand_title in by_norm.items():
                if len(cand_norm.split()) >= LOOSE_MIN_WORDS and (
                    abs(len(cand_norm) - len(n)) <= 0.2 * len(n)
                    and difflib.SequenceMatcher(None, n, cand_norm).ratio()
                    >= LOOSE_RATIO
                ):
                    found[key] = (cand_title, "loose")
                    break
    return found


def cache_path_for(folder: Path, item_id: str) -> Path | None:
    """The one cached payload for a review in an arm folder (shape-suffixed file name)."""
    if not item_id:
        return None
    matches = sorted(folder.glob(f"{item_id}-*.json")) + [folder / f"{item_id}.json"]
    return next((p for p in matches if p.exists()), None)


def load_references() -> dict[str, list[dict[str, Any]]]:
    refs: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    with REFERENCES.open() as fh:
        for r in csv.DictReader(fh):
            refs[r["review_title"]].append(
                {
                    "key": r["ref_id"] or r["doi"] or r["ref_title"],
                    "title": r["ref_title"],
                    "doi": normalize_doi(r["doi"]),
                    "year": r["year"],
                }
            )
    return refs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=DEFAULT_DATASET + "-mini")
    parser.add_argument("--arm", default="docs-cites-all-400")
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--loose", action="store_true", help="add the near-match rule")
    parser.add_argument("--show", action="store_true", help="print every match")
    args = parser.parse_args()

    # The Overton cache is keyed by Langfuse item id, the references file by review
    # title; the dataset items carry both.
    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST"
        )
    item_by_title = {
        norm(item.metadata.get("review_title", "")): str(item.id)
        for item in client.get_dataset(args.dataset).items
    }
    cache_dir = CACHE_DIR / f"overton-{args.arm}"

    refs = load_references()
    totals: collections.Counter[str] = collections.Counter()
    print(
        "| review | refs | no DOI | found by title: Overton docs | cited, no DOI | "
        "DOI-less OpenAlex records (any OpenAlex record) | "
        "extra DOI refs found by title on DOI-less candidates | "
        "DOI recall over DOI refs (Overton / OpenAlex) | "
        "coverage over all refs with titles (Overton / OpenAlex) |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for title, review_refs in refs.items():
        path = cache_path_for(cache_dir, item_by_title.get(norm(title), ""))
        if path is None:
            print(f"| {title[:40]} | no Overton cache | | | | | | | |")
            continue
        payload = json.loads(path.read_text())
        docs = payload.get("docs", [])
        doc_titles = [d.get("translated_title") or d.get("title") or "" for d in docs]
        doc_titles += [d.get("title") or "" for d in docs if d.get("translated_title")]
        cited_nodoi = payload.get("cited_without_doi", [])
        oa_rows = list(
            csv.DictReader((args.run / "candidates" / f"{slug(title)}.csv").open())
        )
        oa_titles = [r["title"] for r in oa_rows]
        oa_titles_nodoi = [r["title"] for r in oa_rows if not r["doi"]]
        doc_titles_nodoi = [
            d.get("translated_title") or d.get("title") or ""
            for d in docs
            if not d.get("doi")
        ]

        no_doi = {r["key"]: r["title"] for r in review_refs if not r["doi"]}
        with_doi = {r["key"]: r["title"] for r in review_refs if r["doi"]}
        gt_dois = {r["doi"] for r in review_refs if r["doi"]}

        m_docs = match(no_doi, doc_titles, loose=args.loose)
        m_cited = match(no_doi, cited_nodoi, loose=args.loose)
        # DOI-less references against the DOI-less OpenAlex records only, as the
        # write-up states (Codex review, 2026-10-08); the whole-pool match is kept too.
        m_oa = match(no_doi, oa_titles_nodoi, loose=args.loose)
        m_oa_any = match(no_doi, oa_titles, loose=args.loose)
        # Reverse gap: references WITH a DOI, found only by title on candidates WITHOUT one.
        m_rev = match(with_doi, doc_titles_nodoi + oa_titles_nodoi, loose=args.loose)

        ov_doi_hits = (
            {d["doi"] for d in docs if d.get("doi")} | set(payload["dois"])
        ) & gt_dois
        oa_doi_hits = {normalize_doi(r["doi"]) for r in oa_rows if r["doi"]} & gt_dois
        n = len(review_refs)
        n_doi = len(gt_dois)
        ov_title = len(set(m_docs) | set(m_cited))
        oa_title = len(m_oa)
        totals.update(
            {
                "refs": n,
                "dois": n_doi,
                "no_doi": len(no_doi),
                "docs": len(m_docs),
                "cited": len(m_cited),
                "oa": len(m_oa),
                "oa_any": len(m_oa_any),
                "rev": len(m_rev),
                "ov_doi": len(ov_doi_hits),
                "oa_doi": len(oa_doi_hits),
                "ov_both": len(ov_doi_hits) + ov_title,
                "oa_both": len(oa_doi_hits) + oa_title,
            }
        )
        print(
            f"| {title[:40]} | {n} | {len(no_doi)} | {len(m_docs)} | {len(m_cited)} | "
            f"{len(m_oa)} ({len(m_oa_any)}) | {len(m_rev)} | "
            f"{len(ov_doi_hits) / n_doi:.0%} / {len(oa_doi_hits) / n_doi:.0%} | "
            f"{(len(ov_doi_hits) + ov_title) / n:.0%} / {(len(oa_doi_hits) + oa_title) / n:.0%} |"
        )
        if args.show:
            for label, found, source in (
                ("no-DOI ref", m_docs, no_doi),
                ("no-DOI ref", m_cited, no_doi),
                ("no-DOI ref", m_oa, no_doi),
                ("DOI ref on DOI-less candidate", m_rev, with_doi),
            ):
                for key, (cand, kind) in found.items():
                    print(f"    {label} [{kind}]: {source[key][:70]}  <->  {cand[:70]}")
    t = totals
    print(
        f"\nTotals over {len(refs)} reviews: {t['refs']} references, {t['no_doi']} without a "
        f"DOI. Found by title: {t['docs']} on Overton documents, {t['cited']} on cited "
        f"works without a DOI, {t['oa']} on DOI-less OpenAlex records ({t['oa_any']} on "
        f"any OpenAlex record); reverse gap {t['rev']}."
    )
    print(
        f"DOI recall over the {t['dois']} DOI references: Overton {t['ov_doi'] / t['dois']:.1%}, "
        f"OpenAlex {t['oa_doi'] / t['dois']:.1%}. Coverage over all {t['refs']} references, "
        f"DOI hits plus title matches: Overton {t['ov_both'] / t['refs']:.1%}, OpenAlex "
        f"{t['oa_both'] / t['refs']:.1%} (pooled over references, not a mean of reviews)."
    )


if __name__ == "__main__":
    main()
