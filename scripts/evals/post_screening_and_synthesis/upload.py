"""Turn the human-checked key facts into the Langfuse dataset ``synthesis-coverage``.

One item per briefing that has ``ground_truth/<doc_id>/key_facts.csv``:

* ``input`` — ``{"question", "doc_id"}``.
* ``expected_output`` — ``{"key_facts": [{fact_id, statement, ref_labels}, ...]}``,
  the kept rows.
* ``metadata`` — ``review_id`` (the Doc ID), ``review_title``, ``type``, ``url``,
  ``n_facts``.

It upserts, so running it again never creates duplicates. Dry run is the default;
``--upload`` writes to Langfuse.

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/post_screening_and_synthesis/upload.py [--docs 16 5] [--upload]
"""

from __future__ import annotations

import argparse
from typing import Any

import _bootstrap  # noqa: F401
from utils import GROUND_TRUTH_DIR, load_kept, load_test_set
from policy_atlas.core import tracing

DATASET = "synthesis-coverage"


def item_id(doc_id: str) -> str:
    # Langfuse item ids are unique per project, not per dataset: prefix with the dataset.
    return f"{DATASET}:{doc_id}"


def build_items(docs: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One dataset item per briefing with ground truth; others are skipped and named."""
    items = []
    for doc in docs:
        doc_id = doc["Doc ID"]
        if not (GROUND_TRUTH_DIR / doc_id / "key_facts.csv").exists():
            print(f"  SKIPPED doc {doc_id}: no key_facts.csv yet")
            continue
        facts = [
            {k: f[k] for k in ("fact_id", "statement", "ref_labels")}
            for f in load_kept(doc_id, "key_facts")
        ]
        items.append(
            {
                "id": item_id(doc_id),
                "input": {"question": doc["Research question"], "doc_id": doc_id},
                "expected_output": {"key_facts": facts},
                "metadata": {
                    "review_id": doc_id,
                    "review_title": doc["Title"],
                    "type": doc["Type"],
                    "url": doc["URL"],
                    "n_facts": len(facts),
                },
            }
        )
    return items


def upload(client: Any, items: list[dict[str, Any]]) -> None:
    """Create the dataset (if new) and upsert every item."""
    try:
        client.create_dataset(name=DATASET)
    except Exception as exc:  # the SDK does a bare POST with no existence check
        print(
            f"  create_dataset: {type(exc).__name__}: {exc} (continuing; it probably exists)"
        )
    for item in items:
        client.create_dataset_item(dataset_name=DATASET, **item)
    client.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--docs", nargs="*", help="Doc IDs (default: all with ground truth)"
    )
    parser.add_argument("--upload", action="store_true", help="Write to Langfuse")
    args = parser.parse_args()

    items = build_items(load_test_set(args.docs or None))
    for item in items:
        print(
            f"  doc {item['metadata']['review_id']}: {item['metadata']['n_facts']} facts"
        )
    if not args.upload:
        print(f"Dry run: {len(items)} item(s) would go to dataset {DATASET!r}.")
        return
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "Langfuse is not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST)."
        )
    upload(client, items)
    print(f"Upserted {len(items)} item(s) into dataset {DATASET!r}.")


if __name__ == "__main__":
    main()
