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

It prints the tables and writes them next to itself as ``2026-10-05-mini-question-intents.md``
and, with click-to-sort column headers, as ``2026-10-05-mini-question-intents.html``.
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


def markdown_to_html(lines: list[str], title: str) -> str:
    """A self-contained HTML page from the markdown lines, every table sortable by clicking a header.

    Sorting reads the first number in a cell (so "34/84 (40%)" sorts by 34 and "11.7%" by
    11.7) and falls back to text. No library; one short script.
    """
    import html

    body: list[str] = []
    table: list[list[str]] = []

    def flush() -> None:
        if not table:
            return
        head, *rows = [r for r in table if not set(r[0]) <= set("-: ")]
        body.append(
            "<table><thead><tr>"
            + "".join(f"<th>{html.escape(c)}</th>" for c in head)
            + "</tr></thead><tbody>"
        )
        for row in rows:
            body.append(
                "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
            )
        body.append("</tbody></table>")
        table.clear()

    for line in lines:
        if line.startswith("|"):
            table.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        flush()
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.strip():
            body.append(f"<p>{html.escape(line)}</p>")
    flush()
    script = """
document.querySelectorAll("th").forEach((th, i) => th.addEventListener("click", () => {
  const table = th.closest("table"), body = table.tBodies[0];
  const num = (t) => { const m = t.match(/-?\\d+(\\.\\d+)?/); return m ? parseFloat(m[0]) : null; };
  const col = Array.from(th.parentNode.children).indexOf(th);
  const asc = th.dataset.asc !== "true"; th.dataset.asc = asc;
  Array.from(body.rows).sort((a, b) => {
    const x = a.cells[col].textContent, y = b.cells[col].textContent, nx = num(x), ny = num(y);
    const r = (nx !== null && ny !== null) ? nx - ny : x.localeCompare(y);
    return asc ? r : -r;
  }).forEach((row) => body.appendChild(row));
}));
"""
    style = (
        "body{font:14px/1.4 system-ui,sans-serif;max-width:1400px;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;margin:1rem 0;width:100%}th,td{border:1px solid #ccc;padding:4px 8px;text-align:left}"
        "th{cursor:pointer;background:#f3f3f3;user-select:none}th:hover{background:#e6e6e6}p{max-width:90ch}"
    )
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
        f"<style>{style}</style></head><body>"
        + "\n".join(body)
        + f"<script>{script}</script></body></html>\n"
    )


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
        "One free Semantic Scholar snippet request and one Consensus request tie at 11.7% at the "
        "ceiling, above the pipeline's standard depth (4.8%) and five times its rapid depth (2.2%); "
        "the keyword engine barely registers.",
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
        "The ranking of engines holds within every source, but the level does not: the 3ie and YEF "
        "gap-map rows stay near zero for everyone (a corpus problem, not a wording one), while the "
        "hand-made reviews score highest on every semantic engine.",
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
        "The two semantic engines disagree sharply review by review (Consensus 34/84 on child sleep "
        "and obesity where the snippet engine finds 18; snippet 27/84 on loneliness where Consensus "
        "finds 16), so querying both would likely add; the pipeline beats neither on any review and "
        "has its one good result, parental leave at standard depth, on the intent most like a "
        "research question.",
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
    page = Path(__file__).with_suffix(".html")
    page.write_text(markdown_to_html(lines, lines[0].lstrip("# ")), encoding="utf-8")
    print(f"written {out} and {page} (click a column header to sort)")


if __name__ == "__main__":
    main()
