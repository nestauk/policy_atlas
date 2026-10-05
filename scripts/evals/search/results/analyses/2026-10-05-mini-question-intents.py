"""Mini-dataset results of 2026-10-05: title-shaped against question-shaped gap-map intents.

Reads two labelled sets of Langfuse dataset runs on ``retrieval-ground-truth-mini`` and
rebuilds every figure quoted in `history.md` and `verification.md` for that day, so the
numbers can be re-derived rather than trusted:

- ``mini-2026-10-05``: every arm and the pipeline over the fifteen reviews, title intents.
- ``mini-q-2026-10-05``: the same after the four gap-map intents became questions
  (contract D18). The baselines and rapid cover all fifteen; standard covers the four
  gap-map rows only, so its fifteen-row figure is **spliced**: the four re-run rows plus
  the eleven rows kept from the first label. The table says so.

Three tables, on the current runs (``mini-q-2026-10-05``, with the eleven standard rows
kept from the first label): total recall per experiment; the same broken down by source
(Campbell, 3ie, SR4ALL, YEF, hand-made); and every review against the main experiments.
Campbell and SR4ALL rows are unlabelled reference lists with a recall ceiling near 50%;
the others are labelled. The script refuses to run if a run does not hold the number of
items it expects, so a changed dataset cannot produce a quietly different table.

Run from the repo root (read-only against Langfuse, no search-service calls)::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/results/analyses/2026-10-05-mini-question-intents.py

It prints the table and writes it next to itself as ``2026-10-05-mini-question-intents.md``.
Dev-only eval tooling. Not part of the runtime package.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import _bootstrap  # noqa: F401

from policy_atlas.core import tracing

DATASET = "retrieval-ground-truth-mini"
BEFORE, AFTER = "mini-2026-10-05", "mini-q-2026-10-05"
RUNS = [
    "openalex-raw-cap50",
    "openalex-raw-cap100",
    "openalex-raw-cap200",
    "openalex-raw-cap1000",
    "semantic-scholar-cap50",
    "semantic-scholar-cap100",
    "semantic-scholar-cap200",
    "semantic-scholar-cap1000",
    "semantic-scholar-snippet-cap50",
    "semantic-scholar-snippet-cap100",
    "semantic-scholar-snippet-cap200",
    "semantic-scholar-snippet-cap1000",
    "consensus-cap50",
    "consensus-cap100",
    "consensus-cap200",
    "consensus-cap1000",
    "rapid",
    "standard",
]
# Items each run must hold: fifteen everywhere, except standard under the second label.
EXPECTED_ITEMS = {(AFTER, "standard"): 4}
SOURCES = ("campbell", "3ie", "sr4all", "yef", "hand-made")
SAMPLE_REVIEWS = (
    Path(__file__).resolve().parents[1] / "ground_truth" / "sample_mini_reviews.csv"
)
# The experiments shown per review (the per-experiment tables show all of them).
PER_REVIEW_RUNS = [
    "openalex-raw-cap1000",
    "semantic-scholar-cap1000",
    "semantic-scholar-snippet-cap1000",
    "consensus-cap1000",
    "rapid",
    "standard",
]


def source_of(item: Any, dataset_by_title: dict[str, str]) -> str:
    """Which collection a dataset item came from; the copied originals are ``hand-made``."""
    if item.metadata.get("copied_from"):
        return "hand-made"
    return dataset_by_title[item.metadata["review_title"]]


def run_scores(
    client: Any, dataset_id: str, run_name: str
) -> dict[str, dict[str, float]]:
    """Per dataset item, the scores of one run (``search_recall`` and friends)."""
    out: dict[str, dict[str, float]] = {}
    for run_item in client.api.dataset_run_items.list(
        dataset_id=dataset_id, run_name=run_name, limit=100
    ).data:
        scores = client.api.scores.get_many(trace_id=run_item.trace_id, limit=100).data
        out[run_item.dataset_item_id] = {
            s.name: float(s.value) for s in scores if s.value is not None
        }
    return out


def mean_recall(
    scores: dict[str, dict[str, float]], item_ids: set[str]
) -> float | None:
    values = [scores[i]["search_recall"] for i in item_ids if i in scores]
    return sum(values) / len(values) if values else None


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def main() -> None:
    client = tracing.get_langfuse()
    if client is None:
        sys.exit(
            "Langfuse is not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST)."
        )
    dataset = client.api.datasets.get(DATASET)
    items = {i.id: i for i in client.get_dataset(DATASET).items}
    assert len(items) == 15, f"expected 15 items in {DATASET}, found {len(items)}"
    with SAMPLE_REVIEWS.open(newline="", encoding="utf-8") as handle:
        dataset_by_title = {r["title"]: r["dataset"] for r in csv.DictReader(handle)}
    source = {i: source_of(it, dataset_by_title) for i, it in items.items()}
    by_source = {s: {i for i in items if source[i] == s} for s in SOURCES}
    assert {s: len(v) for s, v in by_source.items()} == {
        "campbell": 3,
        "3ie": 3,
        "sr4all": 4,
        "yef": 1,
        "hand-made": 4,
    }, {s: len(v) for s, v in by_source.items()}

    # Current scores per run: the second label, with the eleven standard rows kept from the first.
    current: dict[str, dict[str, dict[str, float]]] = {}
    for run in RUNS:
        after = run_scores(client, dataset.id, f"{AFTER}/{run}")
        want = EXPECTED_ITEMS.get((AFTER, run), 15)
        assert len(after) == want, f"{AFTER}/{run}: {len(after)} items, expected {want}"
        if want < 15:
            before = run_scores(client, dataset.id, f"{BEFORE}/{run}")
            assert len(before) == 15, (
                f"{BEFORE}/{run}: {len(before)} items, expected 15"
            )
            after = {**before, **after}
        current[run] = after

    def label(run: str) -> str:
        return (
            run
            if EXPECTED_ITEMS.get((AFTER, run), 15) == 15
            else f"{run} (spliced: 4 re-run + 11 kept)"
        )

    lines = [
        "# Mini dataset, 2026-10-05: recall per experiment, by source, by review",
        "",
        f"Generated by `{Path(__file__).name}` from the Langfuse runs under `{AFTER}` "
        f"(question-shaped intents on the four gap-map rows; the eleven `standard` rows not "
        f"re-run are kept from `{BEFORE}`). Mean `search_recall` over the fifteen reviews. "
        "Campbell and SR4ALL rows are unlabelled reference lists with a recall ceiling near "
        "50%; 3ie, YEF and the hand-made rows are labelled. Per-review cells show "
        "found/target.",
        "",
        "## 1. Total recall per experiment",
        "",
        "| experiment | recall (15 reviews) |",
        "|---|---|",
    ]
    for run in RUNS:
        lines.append(f"| {label(run)} | {pct(mean_recall(current[run], set(items)))} |")
    lines += [
        "",
        "## 2. Recall per experiment, by source",
        "",
        "| experiment | "
        + " | ".join(f"{s} ({len(by_source[s])})" for s in SOURCES)
        + " |",
        "|---|" + "---|" * len(SOURCES),
    ]
    for run in RUNS:
        cells = [pct(mean_recall(current[run], by_source[s])) for s in SOURCES]
        lines.append(f"| {label(run)} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 3. Recall per review (found/target)",
        "",
        "| source | review | " + " | ".join(PER_REVIEW_RUNS) + " |",
        "|---|---|" + "---|" * len(PER_REVIEW_RUNS),
    ]
    ordered = sorted(
        items,
        key=lambda i: (SOURCES.index(source[i]), items[i].metadata["review_title"]),
    )
    for i in ordered:
        target = len(items[i].expected_output["keys"])
        cells = []
        for run in PER_REVIEW_RUNS:
            sc = current[run].get(i)
            cells.append(
                "-"
                if sc is None
                else f"{sc['n_found']:.0f}/{target} ({sc['search_recall']:.0%})"
            )
        title = items[i].metadata["review_title"].replace("|", "/")
        lines.append(f"| {source[i]} | {title[:90]} | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    print(text)
    out = Path(__file__).with_suffix(".md")
    out.write_text(text, encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
