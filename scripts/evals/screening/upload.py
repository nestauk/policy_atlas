"""Turn the sampled screening ground truth into a Langfuse dataset.

The screening eval reads its rows from the source files that
``sync_s3.py screening download`` puts in ``datasets/`` (about 300 MB). This
script takes the sampled rows the eval scores, ``mini`` (288 documents) or
``full`` (2,949), and uploads them to Langfuse, one dataset item per document,
so the rows can be read without the source files and a run can be linked to
its items. It upserts, so running it again never creates duplicates.

One Langfuse dataset item per document:

* ``input`` — ``{"intent", "title", "abstract"}``: the question as the screen
  sees it (the published title, no criteria) and the document's title and
  abstract. A document with no abstract has ``abstract`` null.
* ``expected_output`` — ``{"relevant": 1 or 0}``, the human label.
* ``metadata`` — ``target_id``, ``target_name``, ``dataset_source``,
  ``doc_id`` and ``criteria`` (the published criteria, for runs that add them).

The datasets are ``screening-ground-truth-mini`` and ``screening-ground-truth-full``.
The screening scripts do not read from Langfuse yet; they still read ``datasets/``.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/screening/upload.py [--dataset mini|full] \\
        [--targets Name ...] [--dry-run]

``--dry-run`` builds the items, prints a summary and needs no Langfuse keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from adapter import MISSING_ABSTRACT, MISSING_TITLE, SIZES, load_and_adapt_dataset
from targets import select_targets

from policy_atlas.core import tracing

DATASET_PREFIX = "screening-ground-truth"


def _item_id(dataset: str, target_id: str, doc_id: str) -> str:
    # Stable across re-runs (upsert) and prefixed with the dataset name, because
    # Langfuse item ids are unique per project, not per dataset.
    digest = hashlib.sha256(f"{target_id}:{doc_id}".encode()).hexdigest()[:32]
    return f"{dataset}:{digest}"


def build_items(
    target: dict[str, Any], dataset: str, size: str
) -> list[dict[str, Any]]:
    """Shape one dataset item per sampled document of one target.

    Args:
        target: One entry from ``select_targets``.
        dataset: The Langfuse dataset name (prefixes the item ids).
        size: ``mini`` or ``full``, the sample to draw.

    Returns:
        Item dicts ready for ``upload``.
    """
    frame = load_and_adapt_dataset(target, size=size)
    items: list[dict[str, Any]] = []
    for row in frame.itertuples(index=False):
        title = None if row.title == MISSING_TITLE else row.title
        abstract = (
            None
            if row.abstract_or_summary == MISSING_ABSTRACT
            else row.abstract_or_summary
        )
        items.append(
            {
                "id": _item_id(dataset, target["id"], str(row.doc_id)),
                "input": {
                    "intent": target["query"],
                    "title": title,
                    "abstract": abstract,
                },
                "expected_output": {"relevant": int(row.ground_truth_relevant)},
                "metadata": {
                    "target_id": target["id"],
                    "target_name": target["name"],
                    "dataset_source": target["dataset_source"],
                    "doc_id": str(row.doc_id),
                    "criteria": target.get("criteria") or [],
                },
            }
        )
    return items


def upload(client: Any, dataset: str, items: list[dict[str, Any]]) -> None:
    """Create the dataset (if new) and upsert every item."""
    try:
        client.create_dataset(name=dataset)
    except Exception as exc:  # the SDK does a bare POST with no existence check
        print(
            f"  create_dataset: {type(exc).__name__}: {exc} (continuing, it probably exists)"
        )
    for item in items:
        client.create_dataset_item(dataset_name=dataset, **item)
    client.flush()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", choices=sorted(SIZES), default="mini")
    parser.add_argument("--targets", nargs="*", help="Target names; default all")
    parser.add_argument(
        "--dry-run", action="store_true", help="Build and summarise, upload nothing"
    )
    args = parser.parse_args()

    dataset = f"{DATASET_PREFIX}-{args.dataset}"
    items: list[dict[str, Any]] = []
    for target in select_targets(args.targets):
        built = build_items(target, dataset, args.dataset)
        positives = sum(item["expected_output"]["relevant"] for item in built)
        print(f"  {target['name']}: {len(built)} documents, {positives} included")
        items.extend(built)
    size_mb = len(json.dumps(items).encode()) / 1e6
    print(f"{dataset}: {len(items)} items, {size_mb:.1f} MB as JSON")

    if args.dry_run:
        print("Dry run: nothing uploaded.")
        return
    client = tracing.get_langfuse()
    if client is None:
        raise SystemExit(
            "Langfuse is not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST). "
            "Use --dry-run to check the rows."
        )
    upload(client, dataset, items)
    print(f"Uploaded {len(items)} items to {dataset}.")


if __name__ == "__main__":
    main()
