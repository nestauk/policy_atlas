"""Turn the two ground-truth CSVs into a Langfuse dataset.

Run it once, and again whenever new ground truth datasets are added (one RQ + a set of references that answer the question); it
upserts, so re-running never creates duplicates.

Inputs, both under ``input/``:

* ``gt_reviews.csv`` — one row per review to search for. Columns: ``title``
  (cleaned into the search intent), ``doi`` or ``url`` (the review's
  identifier), ``published_before`` (ISO ``YYYY-MM-DD`` search cutoff — when
  empty on a DOI row it is derived from OpenAlex, one month before the
  review's own publication date, and printed so you can paste it in; a URL
  row must give it), and ``exclude`` (any value skips the row).
* ``references.csv`` — one row per work a review cites. Columns used:
  ``review_title`` (must match ``title`` above exactly), ``ref_title``,
  ``label`` (only ``content`` rows form the recall target), and the scoring
  key: ``doi`` (bare or ``https://doi.org/...``) or ``overton_id`` (Overton
  policy-document id, for grey literature with no DOI). A ``content`` row with
  neither cannot be scored and is counted, not silently dropped.

One Langfuse dataset item per review:

* ``input`` — ``{"intent", "published_before"}``, exactly what the sweep
  feeds to the search stage.
* ``expected_output`` — ``{"keys": [...], "titles": {key: ref_title}}``, the
  recall target. Keys are lowercase DOIs or ``overton:<id>``.
* ``metadata`` — ``review_id``, ``review_title``, ``source`` (``doi``/``url``),
  ``n_target``, ``n_unscorable``.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/eval_ground_truth/ground_truth_dataset.py [--dry-run]

``--dry-run`` prints what would be uploaded and needs no Langfuse keys.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ground_truth import fetch_openalex_work, normalize_doi, overton_key
from run_and_score import _iso_date, _months_earlier, clean_review_title

from policy_atlas.core import tracing

INPUT_DIR = Path(__file__).parent / "input"
DEFAULT_DATASET = "retrieval-ground-truth"


@dataclass
class ReviewSpec:
    """One review from ``gt_reviews.csv``.

    Exactly one of ``doi``/``url`` is set. ``published_before`` is the search
    cutoff: optional for a DOI (derived from OpenAlex) and required for a URL,
    where no machine-readable publication date exists.
    """

    title: str
    doi: str | None = None
    url: str | None = None
    published_before: str | None = None

    @property
    def identifier(self) -> str:
        return self.doi or self.url or ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Rows with lowercased, stripped headers and stripped values."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            for raw in csv.DictReader(handle)
        ]


def load_reviews(path: Path) -> list[ReviewSpec]:
    """Read ``gt_reviews.csv``, validating every row before any network call.

    Raises:
        ValueError: With every problem found, one per line, so a broken sheet is
            fixed in one pass instead of one row at a time.
    """
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"{path} has no rows.")

    reviews: list[ReviewSpec] = []
    problems: list[str] = []
    for line_no, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        if row.get("exclude"):
            print(f"  row {line_no}: skipped (exclude={row['exclude']!r})")
            continue
        title, doi, url = row.get("title", ""), row.get("doi", ""), row.get("url", "")
        published_before = row.get("published_before", "")
        if not title:
            problems.append(f"row {line_no}: no title")
            continue
        if not doi and not url:
            problems.append(f"row {line_no} ({title[:50]}): neither doi nor url")
            continue
        if published_before:
            try:
                _iso_date(published_before)
            except argparse.ArgumentTypeError as exc:
                problems.append(f"row {line_no} ({title[:50]}): {exc}")
                continue
        elif not doi:
            problems.append(
                f"row {line_no} ({title[:50]}): a url row needs a published_before date "
                "(ISO YYYY-MM-DD) — there is no machine-readable publication date to "
                "derive one from. Fill in 'published_before', or set 'exclude' to skip it."
            )
            continue
        reviews.append(
            ReviewSpec(
                title=title,
                # A DOI wins when both are present: it is the more stable identifier.
                doi=normalize_doi(doi) if doi else None,
                url=None if doi else url,
                published_before=published_before or None,
            )
        )

    if problems:
        raise ValueError(f"{path} has {len(problems)} unusable row(s):\n  " + "\n  ".join(problems))
    if not reviews:
        raise ValueError(f"{path} has no usable rows (every row excluded?).")
    return reviews


def load_references(path: Path) -> dict[str, dict[str, Any]]:
    """Read ``references.csv`` into per-review recall targets.

    Returns:
        ``review_title -> {"titles": {key: ref_title}, "n_unscorable": int}``.
        Only ``label == content`` rows count; a content row with no ``doi`` and
        no ``overton_id`` has no scoring key and is tallied in ``n_unscorable``.
    """
    targets: dict[str, dict[str, Any]] = {}
    for row in _read_csv(path):
        if row.get("label") != "content":
            continue
        target = targets.setdefault(row["review_title"], {"titles": {}, "n_unscorable": 0})
        key = normalize_doi(row.get("doi")) or overton_key(row.get("overton_id"))
        if key:
            target["titles"][key] = row.get("ref_title") or key
        else:
            target["n_unscorable"] += 1
    return targets


def _item_id(dataset: str, review_id: str) -> str:
    # Stable across re-runs (upsert) and prefixed with the dataset name, because
    # Langfuse item ids are unique per project, not per dataset.
    return f"{dataset}:{hashlib.sha256(review_id.encode()).hexdigest()[:32]}"


def build_items(
    reviews: list[ReviewSpec], references: dict[str, dict[str, Any]], dataset: str
) -> list[dict[str, Any]]:
    """Join reviews to their references and shape one dataset item per review.

    A review with no scorable content references is skipped and reported:
    recall against an empty target is undefined. A missing DOI-row cutoff is
    derived from OpenAlex here (the one network call this script makes).
    """
    items: list[dict[str, Any]] = []
    for spec in reviews:
        target = references.get(spec.title)
        if not target or not target["titles"]:
            print(f"  SKIPPED {spec.title!r}: no scorable 'content' references in references.csv")
            continue
        published_before = spec.published_before
        if not published_before:
            assert spec.doi  # load_reviews guarantees a URL row has a date
            work = fetch_openalex_work(spec.doi)
            if not work.get("publication_date"):
                raise ValueError(
                    f"OpenAlex has no publication_date for {spec.doi}; fill in "
                    "published_before for this row."
                )
            published_before = _months_earlier(work["publication_date"], 1)
            print(
                f"  derived published_before={published_before} for {spec.title[:50]!r} "
                "(paste it into gt_reviews.csv to pin it)"
            )
        titles = target["titles"]
        items.append(
            {
                "id": _item_id(dataset, spec.identifier),
                "input": {"intent": clean_review_title(spec.title), "published_before": published_before},
                "expected_output": {"keys": sorted(titles), "titles": titles},
                "metadata": {
                    "review_id": spec.identifier,
                    "review_title": spec.title,
                    "source": "doi" if spec.doi else "url",
                    "n_target": len(titles),
                    "n_unscorable": target["n_unscorable"],
                },
            }
        )
    return items


def upload(client: Any, dataset: str, items: list[dict[str, Any]]) -> None:
    """Create the dataset (if new) and upsert every item."""
    try:
        client.create_dataset(name=dataset)
    except Exception as exc:  # the SDK does a bare POST with no existence check
        print(f"  create_dataset: {type(exc).__name__}: {exc} (continuing — it probably exists)")
    for item in items:
        client.create_dataset_item(dataset_name=dataset, **item)
    client.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help=f"Langfuse dataset name (default {DEFAULT_DATASET}).")
    parser.add_argument("--reviews", type=Path, default=INPUT_DIR / "gt_reviews.csv")
    parser.add_argument("--references", type=Path, default=INPUT_DIR / "references.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print the items; upload nothing.")
    args = parser.parse_args()

    try:
        reviews = load_reviews(args.reviews)
    except ValueError as exc:
        parser.error(str(exc))
    references = load_references(args.references)
    orphans = set(references) - {r.title for r in reviews}
    if orphans:
        print(f"  WARNING: references.csv has {len(orphans)} review_title(s) not in gt_reviews.csv: {sorted(orphans)}")

    items = build_items(reviews, references, args.dataset)
    for item in items:
        meta = item["metadata"]
        print(
            f"  {meta['review_title'][:60]!r}: {meta['n_target']} target keys, "
            f"{meta['n_unscorable']} unscorable, cutoff {item['input']['published_before']}"
        )
    if not items:
        parser.error("no review has any scorable references — nothing to upload.")
    if args.dry_run:
        print(f"Dry run: {len(items)} item(s) would go to dataset {args.dataset!r}.")
        return

    client = tracing.get_langfuse()
    if client is None:
        parser.error("Langfuse is not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST). Use --dry-run to check the CSVs.")
    upload(client, args.dataset, items)
    print(f"Upserted {len(items)} item(s) into dataset {args.dataset!r}.")


if __name__ == "__main__":
    main()
