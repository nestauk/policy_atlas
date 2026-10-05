"""Pick the ground-truth sample from the fetched collections (owner decisions, 2026-10-05).

The ``getters/`` scripts write one pair of CSV files per public collection under
``results/ground_truth/`` (Campbell, 3ie, YEF, SR4ALL): hundreds of candidate reviews.
This script applies a simple quality check to every candidate, spreads the picks across
topics, and writes two samples in the shape ``ground_truth_dataset.py`` reads:

- ``sample_100``: 30 Campbell reviews, 30 3ie gap-map rows, 30 SR4ALL reviews and 10 YEF
  strands. The full eval set.
- ``sample_10``: ten rows chosen by hand from the hundred (``SAMPLE_10_TITLES``: 3
  Campbell, 3 3ie, 3 SR4ALL, 1 YEF), leaning towards Nesta's missions: a healthy life, a
  fairer start, a sustainable future. The cheap set for quick checks; always a subset of
  the full one, and the script refuses a title that is not in the hundred.

**The quality check** (one reason per failing row, printed with ``--verbose``):

1. One specific question: an intervention row or a single review, not a whole gap map,
   and a title that appears once in its collection (the title joins the two CSV files).
2. Between 20 and 300 references with a DOI (Digital Object Identifier). Fewer than 20
   makes recall swing by whole tens of percent on one hit; more than 300 lets one list
   dominate a run.
3. At least 70% of the references carry a DOI, because every recall number is scholarly
   recall until the grey-literature keys exist (P2). YEF cites many evaluation reports,
   so its floor is 50%; otherwise only seven strands would pass.
4. The cutoff date is in the past and 2010 or later.
5. The title is not a protocol, an editorial or a guide: those have a reference list but
   no included studies, so there is nothing for a search to find.

**Spread.** Within a collection the picks rotate across groups so no one subject fills the
quota: for gap-map sources the group is the map (3ie rows share their map's title), for
review sources it is a coarse keyword topic (education, crime and justice, mental health,
and so on). Inside a group the best rows come first: highest DOI share, then most DOI
references. Everything is sorted, so the same inputs give the same sample.

**Labels.** Every reference row in the sample is written ``label = content``, including
the Campbell and SR4ALL reference lists that nobody has labelled. The owner chose this on
2026-10-05 instead of a labelling pass: a reference list mixes the studies a review is about
with background and methods citations, so about half of its rows may be off topic, and a
search that finds every on-topic study would still score near 50% on those rows. Read
Campbell and SR4ALL recall against that ceiling, not against 100%. The reviews file says
which rows are labelled (``target_labelled``: ``yes`` for gap maps, ``no`` for lists).

Usage::

    uv run --project backend python scripts/evals/search/select_ground_truth.py [--verbose]

then upload each sample as its own Langfuse dataset::

    uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth_dataset.py \\
        --reviews scripts/evals/search/results/ground_truth/sample_10_reviews.csv \\
        --references scripts/evals/search/results/ground_truth/sample_10_references.csv \\
        --dataset retrieval-ground-truth-10 --dry-run

Dev-only eval tooling. No network. Not part of the runtime package.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from ground_truth import GROUND_TRUTH_DIR, REFERENCE_COLUMNS, REVIEW_COLUMNS

QUOTAS = {"campbell": 30, "3ie": 30, "sr4all": 30, "yef": 10}
# The cheap sample, chosen by hand from the hundred (owner, 2026-10-05): two health rows,
# schools, home energy, jobs, civic education, violence, learning loss, adolescent drug use.
SAMPLE_10_TITLES = (
    "Health and Social Care Interventions in the 80 years Old and Over Population: An Evidence and Gap Map",
    "Evidence and Gap Map of Whole-School Interventions Promoting Mental Health and Preventing Risk Behaviours in Adolescence: Programme Component Mapping Within the Health-Promoting Schools Framework: An evidence and gap map",
    "Residential energy efficiency interventions: A meta-analysis of effectiveness studies",
    "Improving Labour Market Outcomes Through Learning to Earning Interventions in Low- and Middle-Income Countries: Core skills training",
    "Nutrition-Sensitive Agriculture Evidence Gap Map: Consumption / provision of large-scale fortified foods",
    "Human Rights: Civic and Legal Education",
    "Recent intimate partner violence against women and health: a systematic review and meta-analysis of cohort studies",
    "A systematic review and meta-analysis of the evidence on learning during the COVID-19 pandemic",
    "Risk and protective factors of drug abuse among adolescents: a systematic review",
    "Interventions to prevent children and young people's involvement in violence: Trauma-specific therapies",
)
GAP_MAP_SOURCES = {"3ie", "yef"}  # rows already labelled content by the map's screeners
MIN_DOI_REFS, MAX_REFS = 20, 300
MIN_DOI_SHARE = {"yef": 0.5}
DEFAULT_MIN_DOI_SHARE = 0.7
MIN_CUTOFF = "2010-01-01"
# A protocol announces a review; an editorial or guide is not one. None has included studies.
NOT_A_REVIEW_RE = re.compile(r"\bprotocol\b|^\s*editorial\b|\ba guide to\b", re.IGNORECASE)
# Coarse keyword topics, first match wins. Only used to spread the picks, never to score.
TOPICS = {
    "education": r"school|educat|learning|literacy|teacher|student|pupil|preschool",
    "crime and justice": r"crime|violen|offend|polic|justice|prison|bully|gang|delinquen",
    "mental health": r"mental|depress|anxiety|suicid|psycholog|wellbeing|well-being|loneli|self-esteem|self-harm",
    "families and children": r"parent|famil|child|youth|adolesc|foster",
    "welfare and work": r"employ|job|labour|labor|poverty|cash transfer|welfare|income|housing|homeless|social care|pension|microfinance",
    "health": r"health|nutrition|disease|hiv|malaria|water|sanitation|drug|alcohol|smok|obes|exercise|physical activity",
    "development and environment": r"governance|rule of law|corruption|agricultur|forest|land|energy|climate|infrastructure|humanitarian|refugee|migration",
    "organisations and innovation": r"innovation|business|firm|entrepreneur|management|organis|organiz|network",
}
SAMPLE_REVIEW_COLUMNS = (*REVIEW_COLUMNS, "topic", "target_labelled")


def topic(title: str) -> str:
    """Coarse keyword topic of a review title; ``other`` when nothing matches."""
    lowered = title.lower()
    for name, pattern in TOPICS.items():
        if re.search(pattern, lowered):
            return name
    return "other"


def load_source(name: str, directory: Path = GROUND_TRUTH_DIR) -> list[dict[str, Any]]:
    """Reviews of one collection with their reference counts recomputed from the references file."""
    with (directory / f"{name}_references.csv").open(newline="", encoding="utf-8") as handle:
        references = list(csv.DictReader(handle))
    n_refs: Counter[str] = Counter()
    n_doi: Counter[str] = Counter()
    for row in references:
        n_refs[row["review_title"]] += 1
        n_doi[row["review_title"]] += bool(row.get("doi"))
    with (directory / f"{name}_reviews.csv").open(newline="", encoding="utf-8") as handle:
        reviews = list(csv.DictReader(handle))
    titles = Counter(r["title"] for r in reviews)
    for review in reviews:
        review["dataset"] = name
        review["_n_refs"] = n_refs[review["title"]]
        review["_n_doi"] = n_doi[review["title"]]
        review["_dup_title"] = titles[review["title"]] > 1
    return reviews


def rejection(review: dict[str, Any], today: str) -> str | None:
    """Why a candidate fails the quality check (one fixed phrase per rule), or None when it passes."""
    if review.get("level") == "map":
        return "whole gap map, not one question"
    if review["_dup_title"]:
        return "title appears twice in its collection"
    if NOT_A_REVIEW_RE.search(review["title"]):
        return "a protocol, editorial or guide, not a review"
    if review["_n_doi"] < MIN_DOI_REFS:
        return f"fewer than {MIN_DOI_REFS} references with a DOI"
    if review["_n_refs"] > MAX_REFS:
        return f"more than {MAX_REFS} references"
    floor = MIN_DOI_SHARE.get(review["dataset"], DEFAULT_MIN_DOI_SHARE)
    if review["_n_doi"] / review["_n_refs"] < floor:
        return f"under {floor:.0%} of references have a DOI"
    cutoff = review.get("published_before") or ""
    if cutoff < MIN_CUTOFF:
        return f"cutoff before {MIN_CUTOFF}"
    if cutoff >= today:
        return "cutoff not in the past (the map is still growing)"
    return None


def group_of(review: dict[str, Any]) -> str:
    """What the picks rotate across: the map for gap-map rows, the keyword topic otherwise."""
    if review["dataset"] in GAP_MAP_SOURCES:
        return review["title"].split(":")[0].strip()
    return topic(review["title"])


def pick(candidates: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    """Round-robin across groups, best rows first within a group, until the quota is met."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in sorted(
        candidates,
        key=lambda r: (-r["_n_doi"] / r["_n_refs"], -r["_n_doi"], r["title"]),
    ):
        groups[group_of(review)].append(review)
    queues = [groups[key] for key in sorted(groups)]
    picked: list[dict[str, Any]] = []
    while len(picked) < quota and any(queues):
        for queue in queues:
            if queue and len(picked) < quota:
                picked.append(queue.pop(0))
    return picked


def select(
    directory: Path = GROUND_TRUTH_DIR, today: str | None = None
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Counter[str]]]:
    """Pick every collection's quota.

    Returns:
        The picks per source, and per source a counter of rejection reasons plus the
        key ``"passing"`` for the rows that passed the quality check.
    """
    today = today or date.today().isoformat()
    picks: dict[str, list[dict[str, Any]]] = {}
    reasons: dict[str, Counter[str]] = {}
    for name, quota in QUOTAS.items():
        reviews = load_source(name, directory)
        reasons[name] = Counter()
        passing = []
        for review in reviews:
            why = rejection(review, today)
            if why is None:
                passing.append(review)
            else:
                reasons[name][why] += 1
        reasons[name]["passing"] = len(passing)
        picks[name] = pick(passing, quota)
    return picks, reasons


def mini_sample(
    picks: dict[str, list[dict[str, Any]]], titles: tuple[str, ...] = SAMPLE_10_TITLES
) -> dict[str, list[dict[str, Any]]]:
    """The hand-chosen rows out of the full picks, grouped by source in the picks' order.

    Raises:
        ValueError: When a title is not in the full sample, so the small set can never
            drift away from the big one.
    """
    by_title = {review["title"]: (source, review) for source, rows in picks.items() for review in rows}
    missing = [t for t in titles if t not in by_title]
    if missing:
        raise ValueError(f"{len(missing)} title(s) not in the full sample: {missing[:2]}")
    small: dict[str, list[dict[str, Any]]] = {source: [] for source in picks}
    for title in titles:
        source, review = by_title[title]
        small[source].append(review)
    return small


def write_sample(
    name: str,
    picks: dict[str, list[dict[str, Any]]],
    directory: Path = GROUND_TRUTH_DIR,
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write ``<name>_reviews.csv`` and ``<name>_references.csv``; every reference is ``content``."""
    out_dir = out_dir or directory
    out_dir.mkdir(parents=True, exist_ok=True)
    reviews_path = out_dir / f"{name}_reviews.csv"
    references_path = out_dir / f"{name}_references.csv"
    with reviews_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for source, rows in picks.items():
            for review in rows:
                writer.writerow(
                    {
                        **review,
                        "topic": topic(review["title"]),
                        "target_labelled": "yes" if source in GAP_MAP_SOURCES else "no",
                    }
                )
    with references_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for source, rows in picks.items():
            wanted = {review["title"] for review in rows}
            with (directory / f"{source}_references.csv").open(newline="", encoding="utf-8") as src:
                for row in csv.DictReader(src):
                    if row["review_title"] in wanted:
                        writer.writerow({**row, "label": "content"})
    return reviews_path, references_path


def main() -> None:
    """Select both samples, write them next to the fetched files and print a summary."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dir", type=Path, default=GROUND_TRUTH_DIR, help="Where the fetched CSVs are.")
    parser.add_argument("--today", default=None, help="Override today's date (YYYY-MM-DD) for the cutoff rule.")
    parser.add_argument("--verbose", action="store_true", help="Print the rejection reasons per source.")
    args = parser.parse_args()
    picks, reasons = select(args.dir, args.today)
    small = mini_sample(picks)
    write_sample("sample_100", picks, args.dir)
    write_sample("sample_10", small, args.dir)
    print(f"{'source':<10}{'candidates':>12}{'passing':>9}{'picked':>8}{'in 10':>7}  groups covered")
    for name, rows in picks.items():
        n_candidates = sum(reasons[name].values())
        passing = reasons[name]["passing"]
        groups = Counter(group_of(r) for r in rows)
        print(
            f"{name:<10}{n_candidates:>12}{passing:>9}{len(rows):>8}{len(small[name]):>7}  "
            f"{len(groups)} ({', '.join(f'{k} {v}' for k, v in sorted(groups.items()))})"
        )
        if len(rows) < QUOTAS[name]:
            print(f"  WARNING: {name} fills {len(rows)} of {QUOTAS[name]}; relax a rule or widen the fetch")
        if args.verbose:
            for why, count in reasons[name].most_common():
                if why != "passing":
                    print(f"  rejected {count:>4}: {why}")
    total = sum(len(r) for r in picks.values())
    refs = sum(r["_n_refs"] for rows in picks.values() for r in rows)
    print(f"sample_100: {total} reviews, {refs} references; sample_10: {sum(len(r) for r in small.values())} reviews")


if __name__ == "__main__":
    main()
