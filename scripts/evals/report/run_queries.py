"""Run a list of research questions through the full pipeline, unattended.

Each row of ``input/questions.csv`` (columns ``question``, ``depth``) becomes one
real pipeline run in the local database, exactly as if a user had typed the
question into the app, approved the planner's plan and let it run. The
planner conversation is answered by a scripted console (see
``ScriptedConsole``), so nobody has to sit at the keyboard.

What it writes:

* rows in the database that ``DATABASE_URL`` points at (use the local Docker
  Postgres, never production);
* Langfuse traces, one per pipeline stage, all sharing the run's session id;
* one line per question in ``results/runs.csv``: ``task_id``,
  ``conversation_id`` (the Langfuse session id), ``question``, ``depth``,
  ``status``, ``artefact_present``, ``git_commit``, ``started_at``.

The ``task_id`` is the key you use to score the report (``input/
answer_relevance.csv``) and the key ``build_dataset.py`` joins on.

``depth`` is ``rapid``, ``standard`` or ``deep``. It sets the search effort
and the matching analysis depth (``landscape``, ``standard``, ``deep``).

Cost: one full live run per question (search, screening, synthesis and the
run-time judges). Try ``--limit 1`` first.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/report/run_queries.py [--limit N] [--questions PATH]
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
QUESTIONS = HERE / "input" / "questions.csv"
RUNS = HERE / "results" / "runs.csv"
RUN_COLUMNS = [
    "task_id",
    "conversation_id",
    "question",
    "depth",
    "status",
    "artefact_present",
    "git_commit",
    "started_at",
]
DEPTHS = {"rapid": "landscape", "standard": "standard", "deep": "deep"}
# What the scripted console says whenever the planner asks a clarifying
# question. The planner must settle the plan on its own.
PLANNER_ANSWER = (
    "Use your best judgement and keep the plan as drafted. "
    "Run unattended with no pauses."
)


def intent_text(question: str, depth: str) -> str:
    """The first message to the planner: the question plus the run settings."""
    return (
        f"{question}\n\n"
        f"Search effort: {depth}. Analysis depth: {DEPTHS[depth]}. "
        "Steering mode: unattended. Do not ask clarifying questions; "
        "use your best judgement."
    )


class ScriptedConsole:
    """A console double that answers every prompt ``runtime.agent.main`` can ask.

    The prompts it answers, matched on the prompt text:

    * "Describe the evidence review you want" -> the question;
    * "Approve, edit, or abandon?" -> ``approve``;
    * "Describe a revision, or type 'abandon'" (the plan failed validation)
      -> ``abandon``, so a broken plan is skipped rather than looped on;
    * "> " (a planner clarifying question) -> ``PLANNER_ANSWER``;
    * anything else (a steering pause menu, where 1 is Continue) -> ``1``.

    Everything the agent prints is kept in ``lines`` for the log.
    """

    def __init__(self, intent: str) -> None:
        self._intent = intent
        self.lines: list[str] = []
        self.answers: list[tuple[str, str]] = []

    def prompt(self, message: str) -> str:
        if message.startswith("Describe the evidence review"):
            answer = self._intent
        elif message.startswith("Approve, edit"):
            answer = "approve"
        elif message.startswith("Describe a revision"):
            answer = "abandon"
        elif message.strip() == ">":
            answer = PLANNER_ANSWER
        elif message.startswith("Apply this steering"):
            answer = "n"
        else:
            answer = "1"  # ponytail: pause menus always Continue; add options if a run stalls
        self.answers.append((message, answer))
        return answer

    def print(self, message: str) -> None:
        self.lines.append(message)
        print(message)


def load_questions(path: Path) -> list[dict[str, str]]:
    """Read ``questions.csv``; every row needs a question and a known depth."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, start=2):
        if not (row.get("question") or "").strip():
            raise ValueError(f"{path.name} line {index}: empty question")
        if row.get("depth") not in DEPTHS:
            raise ValueError(
                f"{path.name} line {index}: depth must be one of {sorted(DEPTHS)}, "
                f"got {row.get('depth')!r}"
            )
    return rows


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def append_run(path: Path, row: dict[str, object]) -> None:
    """Append one row to ``runs.csv``, writing the header on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in RUN_COLUMNS})


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument(
        "--limit", type=int, default=None, help="Run only the first N rows."
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        parser.error(
            "OPENAI_API_KEY is not set; this must be a live run (use --env-file backend/.env)."
        )
    try:
        rows = load_questions(args.questions)
    except ValueError as exc:
        parser.error(str(exc))
    rows = rows[: args.limit] if args.limit else rows
    git_commit = _git_commit()
    os.environ.setdefault("LANGFUSE_RELEASE", git_commit)

    from policy_atlas.runtime.agent import main as agent_main

    print(f"{len(rows)} question(s); runs recorded in {RUNS}")
    for row in rows:
        question, depth = row["question"].strip(), row["depth"]
        started_at = datetime.now(UTC).isoformat(timespec="seconds")
        print(f"\n=== {depth}: {question[:80]} ===")
        console = ScriptedConsole(intent_text(question, depth))
        result = agent_main(console=console)
        status = (
            result.outcome.status
            if result.outcome
            else f"no_run(exit={result.exit_code})"
        )
        append_run(
            RUNS,
            {
                "task_id": result.task_id or "",
                "conversation_id": result.conversation_id or "",
                "question": question,
                "depth": depth,
                "status": status,
                "artefact_present": result.artefact_present,
                "git_commit": git_commit,
                "started_at": started_at,
            },
        )
        print(
            f"-> task_id={result.task_id} session={result.conversation_id} "
            f"status={status} artefact={result.artefact_present}"
        )


if __name__ == "__main__":
    main()
