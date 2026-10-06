"""Turn human-scored reports into the Langfuse dataset used to calibrate the judge.

Inputs:

* ``results/runs.csv`` — written by ``run_queries.py``; gives the task id,
  question and depth of every report.
* ``input/answer_relevance.csv`` — Rosie's scores. Columns: ``task_id``,
  ``answer_relevance`` (an integer 1 to 5) and ``comment`` (free text: what,
  if anything, is wrong with the report).

The script reads each report from the database ``DATABASE_URL`` points at
(the same local database the runs were written to) and renders it to plain
markdown. Every run gets a markdown file under ``results/reports/`` so the
scoring can be done from files. Only runs with a score become dataset items.

One Langfuse dataset item per scored report:

* ``input`` — ``{"question", "report"}``, what the judge sees.
* ``expected_output`` — ``{"answer_relevance": <1-5>}``, the human score.
  ``calibrate.py`` never shows this to the judge; it only compares against it.
* ``metadata`` — ``task_id``, ``conversation_id``, ``depth``, ``comment``,
  ``git_commit``, ``plan_question`` (the planner's wording of the question).

A report that was not made by ``run_queries.py`` can still be scored: add a
line to ``runs.csv`` with just its ``task_id`` and the question is taken from
the report itself.

Item ids are ``<dataset>:<task_id>``, so running the script again updates
items in place rather than duplicating them.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/report/build_dataset.py [--dry-run]

``--dry-run`` renders the reports, writes ``results/items.json`` and uploads
nothing. Run it first. The live upload is a Langfuse write; run it yourself.
"""

from __future__ import annotations

import argparse
import csv
import json
import uuid
from pathlib import Path
from typing import Any

from policy_atlas.api.contract.read_models import ArtefactOut
from policy_atlas.api.readmodels.repository import artefact_out
from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine

HERE = Path(__file__).parent
RUNS = HERE / "results" / "runs.csv"
SCORES = HERE / "input" / "answer_relevance.csv"
REPORTS_DIR = HERE / "results" / "reports"
ITEMS_JSON = HERE / "results" / "items.json"
DEFAULT_DATASET = "evidence-report-answer-relevance"


def render_report(artefact: ArtefactOut) -> str:
    """Render the artefact as the plain markdown a reader would see.

    Title, question, introduction, each section's prose (and case-study
    cards), then the numbered reference list. Claim anchors, summaries and
    coverage counts are left out: they are machinery, not the report.
    """
    lines = [f"# {artefact.title}", "", f"**Question:** {artefact.question}", ""]
    if artefact.full_report_intro:
        lines += [artefact.full_report_intro.strip(), ""]
    for section in artefact.sections:
        lines += [f"## {section.title}", ""]
        for block in section.blocks:
            lines += [block.prose.strip(), ""]
        for card in section.cards:
            lines += [f"### {card.title}", "", card.prose.strip(), ""]
    if artefact.references:
        lines += ["## References", ""]
        for ref in artefact.references:
            bits = [ref.title]
            if ref.year:
                bits.append(f"({ref.year})")
            if ref.venue:
                bits.append(ref.venue)
            if ref.url:
                bits.append(ref.url)
            lines.append(f"{ref.n}. {' '.join(bits)}")
    return "\n".join(lines).rstrip() + "\n"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_scores(path: Path) -> dict[str, dict[str, str]]:
    """``task_id`` -> score row. A score outside 1 to 5 is an error, not a guess."""
    scores: dict[str, dict[str, str]] = {}
    for index, row in enumerate(_read_csv(path), start=2):
        task_id = (row.get("task_id") or "").strip()
        if not task_id:
            continue
        raw = (row.get("answer_relevance") or "").strip()
        if raw not in {"1", "2", "3", "4", "5"}:
            raise ValueError(
                f"{path.name} line {index}: answer_relevance must be 1-5, got {raw!r}"
            )
        scores[task_id] = {**row, "task_id": task_id, "answer_relevance": raw}
    return scores


def build_item(
    run: dict[str, str],
    score: dict[str, str],
    report: str,
    dataset: str,
    plan_question: str = "",
) -> dict[str, Any]:
    """Shape one dataset item from a run row, its score row and the rendered report.

    The judge sees the question as the user asked it (``runs.csv``). When that
    is empty, for a report listed by task id alone, the planner's version of
    the question stored with the report is used instead. Both are kept.
    """
    question = (run.get("question") or "").strip() or plan_question
    return {
        "id": f"{dataset}:{run['task_id']}",
        "input": {"question": question, "report": report},
        "expected_output": {"answer_relevance": int(score["answer_relevance"])},
        "metadata": {
            "task_id": run["task_id"],
            "conversation_id": run.get("conversation_id", ""),
            "depth": run.get("depth", ""),
            "comment": score.get("comment", ""),
            "git_commit": run.get("git_commit", ""),
            "plan_question": plan_question,
        },
    }


def upload(client: Any, dataset: str, items: list[dict[str, Any]]) -> None:
    """Create the dataset (if new) and upsert every item."""
    try:
        client.create_dataset(name=dataset)
    except Exception as exc:  # the SDK does a bare POST with no existence check
        print(
            f"  create_dataset: {type(exc).__name__}: {exc} (continuing — it probably exists)"
        )
    for item in items:
        client.create_dataset_item(dataset_name=dataset, **item)
    client.flush()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--scores", type=Path, default=SCORES)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and write items.json; upload nothing.",
    )
    args = parser.parse_args()

    if not args.runs.exists():
        parser.error(f"{args.runs} not found — run run_queries.py first.")
    runs = [r for r in _read_csv(args.runs) if r.get("task_id")]
    try:
        scores = load_scores(args.scores)
    except ValueError as exc:
        parser.error(str(exc))
    unknown = set(scores) - {r["task_id"] for r in runs}
    if unknown:
        print(
            f"  WARNING: {len(unknown)} scored task_id(s) are not in runs.csv: {sorted(unknown)}"
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    items: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for run in runs:
            artefact = artefact_out(conn, uuid.UUID(run["task_id"]))
            if artefact is None:
                print(f"  SKIPPED {run['task_id']}: no report in the database")
                continue
            report = render_report(artefact)
            (REPORTS_DIR / f"{run['task_id']}.md").write_text(report, encoding="utf-8")
            score = scores.get(run["task_id"])
            if score is None:
                print(f"  rendered {run['task_id']} (unscored)")
                continue
            items.append(
                build_item(run, score, report, args.dataset, artefact.question)
            )
            print(f"  rendered {run['task_id']} score={score['answer_relevance']}")

    print(f"\n{len(runs)} run(s), {len(items)} scored -> dataset {args.dataset!r}")
    ITEMS_JSON.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"items written to {ITEMS_JSON}")
    if args.dry_run or not items:
        return
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    upload(client, args.dataset, items)
    print(f"uploaded {len(items)} item(s) to dataset {args.dataset!r}")


if __name__ == "__main__":
    main()
