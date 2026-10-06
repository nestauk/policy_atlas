"""Run the answer-relevance judge on the scored reports and compare it with the human scores.

This is the calibration loop. The dataset (``build_dataset.py``) holds each
report and Rosie's 1-to-5 score. This script asks the judge model to score
the same reports with the prompt in ``judges/answer_relevance.md``, records
everything as one Langfuse dataset run, and reports how well the judge
agrees with the human.

The prompt file is the source of truth. Its git history is its version
history. Langfuse prompt management holds a read-only copy so every judge
call in Langfuse links to the exact text that produced it:

* the script compares the file with the newest Langfuse version;
* ``--push-prompt`` uploads the file as a new version when the text or
  config differs (a Langfuse write, so you run it yourself);
* without the flag, a mismatch stops the script, so a run never uses stale
  text.

Scores on each item (visible in the Langfuse run): ``answer_relevance``
(the judge's score, with its reasoning as the comment),
``human_answer_relevance``, ``exact_match``, ``within_one`` and
``abs_error``. Run-level: the mean of each, plus ``spearman`` (rank
correlation between judge and human; 1 is perfect agreement, 0 is none).

``--repeat 2`` runs the judge twice (two dataset runs) and prints how often
it disagrees with itself. That is the noise floor: a judge cannot agree with
a human more reliably than it agrees with itself.

Usage:

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/report/calibrate.py [--push-prompt] [--repeat N] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from langfuse import Evaluation
from pydantic import BaseModel, Field

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import resolve_openai_client

HERE = Path(__file__).parent
PROMPT_FILE = HERE / "judges" / "answer_relevance.md"
DEFAULT_DATASET = "evidence-report-answer-relevance"
EXPERIMENT = "answer-relevance-judge"


class JudgeWire(BaseModel):
    """The judge's structured reply."""

    score: int = Field(ge=1, le=5)
    reasoning: str


def load_prompt_file(path: Path) -> tuple[dict[str, str], str]:
    """Split the prompt file into its front-matter config and the prompt text.

    The file starts with a block between two ``---`` lines holding
    ``key: value`` pairs (``name``, ``model``, optionally ``temperature``).
    Everything after the second ``---`` is the prompt.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name} must start with a '---' front-matter block")
    _, front, body = text.split("---\n", 2)
    config: dict[str, str] = {}
    for line in front.strip().splitlines():
        key, _, value = line.partition(":")
        config[key.strip()] = value.strip()
    for key in ("name", "model"):
        if not config.get(key):
            raise ValueError(f"{path.name}: front matter needs '{key}'")
    return config, body.strip()


def sync_prompt(
    client: Any, config: dict[str, str], text: str, *, push: bool, commit: str
) -> Any:
    """Return the Langfuse prompt matching the file, creating a version if asked.

    Raises:
        RuntimeError: The file and the newest Langfuse version differ and
            ``push`` is false.
    """
    name = config["name"]
    model_config = {k: v for k, v in config.items() if k != "name"}
    try:
        latest = client.get_prompt(name, label="latest", cache_ttl_seconds=0)
    except Exception:
        latest = None
    if (
        latest is not None
        and latest.prompt.strip() == text
        and (latest.config or {}) == model_config
    ):
        return latest
    if not push:
        state = (
            "has no Langfuse copy yet"
            if latest is None
            else f"differs from Langfuse version {latest.version}"
        )
        raise RuntimeError(
            f"prompt file {PROMPT_FILE.name} {state}. Re-run with --push-prompt to upload it."
        )
    created = client.create_prompt(
        name=name,
        prompt=text,
        type="text",
        labels=["production"],
        config=model_config,
        commit_message=f"synced from {PROMPT_FILE.name} at {commit[:7]}",
    )
    print(f"  pushed {name} as Langfuse version {created.version}")
    return created


def make_judge(client: Any, openai: Any, prompt: Any, config: dict[str, str]) -> Any:
    """Build the experiment task: compile the prompt, call the model, return the reply."""
    model = config["model"]
    params: dict[str, Any] = {}
    if config.get("temperature"):
        params["temperature"] = float(config["temperature"])

    def judge(*, item: Any, **_: Any) -> dict[str, Any]:
        compiled = prompt.compile(
            question=item.input["question"], report=item.input["report"]
        )
        with client.start_as_current_observation(
            name="judge:answer_relevance",
            as_type="generation",
            model=model,
            model_parameters=params or None,
            prompt=prompt,
            input=compiled,
        ) as generation:
            response = openai.chat.completions.parse(
                model=model,
                messages=[{"role": "user", "content": compiled}],
                response_format=JudgeWire,
                **params,
            )
            parsed: JudgeWire = response.choices[0].message.parsed
            if parsed is None:
                raise RuntimeError(
                    f"judge returned no parsable reply: {response.choices[0].message.refusal}"
                )
            usage = response.usage
            generation.update(
                output=parsed.model_dump(),
                usage_details={
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                }
                if usage
                else None,
            )
        return parsed.model_dump()

    return judge


def item_scores(
    *, output: dict[str, Any], expected_output: dict[str, Any], **_: Any
) -> list[Evaluation]:
    """Judge score, human score and the three agreement measures for one report."""
    judge, human = int(output["score"]), int(expected_output["answer_relevance"])
    return [
        Evaluation(
            name="answer_relevance", value=judge, comment=output.get("reasoning")
        ),
        Evaluation(name="human_answer_relevance", value=human),
        Evaluation(name="exact_match", value=int(judge == human)),
        Evaluation(name="within_one", value=int(abs(judge - human) <= 1)),
        Evaluation(name="abs_error", value=abs(judge - human)),
    ]


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share the mean of the positions they occupy)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation; ``None`` when undefined (fewer than 2 points or no variance)."""
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


def _score(result: Any, name: str) -> float | None:
    for ev in result.evaluations:
        if ev.name == name:
            return float(ev.value)
    return None


def run_scores(*, item_results: list[Any], **_: Any) -> list[Evaluation]:
    """Run-level agreement: means of the item measures plus Spearman correlation."""
    pairs = [
        (_score(r, "answer_relevance"), _score(r, "human_answer_relevance"))
        for r in item_results
    ]
    pairs = [(j, h) for j, h in pairs if j is not None and h is not None]
    n = len(pairs)
    out = [Evaluation(name="n_scored", value=n)]
    if not n:
        return out
    judge, human = [p[0] for p in pairs], [p[1] for p in pairs]
    out += [
        Evaluation(name="exact_match_rate", value=sum(j == h for j, h in pairs) / n),
        Evaluation(
            name="within_one_rate", value=sum(abs(j - h) <= 1 for j, h in pairs) / n
        ),
        Evaluation(name="mean_abs_error", value=sum(abs(j - h) for j, h in pairs) / n),
        Evaluation(
            name="mean_judge_minus_human", value=sum(j - h for j, h in pairs) / n
        ),
    ]
    rho = spearman(judge, human)
    if rho is not None:
        out.append(Evaluation(name="spearman", value=rho))
    return out


def self_agreement(first: list[Any], second: list[Any]) -> dict[str, float | int]:
    """How often two runs of the judge gave the same score to the same item."""
    by_id = {
        r.item.id: int(r.output["score"]) for r in first if isinstance(r.output, dict)
    }
    pairs = [
        (by_id[r.item.id], int(r.output["score"]))
        for r in second
        if isinstance(r.output, dict) and r.item.id in by_id
    ]
    n = len(pairs)
    return {
        "n": n,
        "exact": sum(a == b for a, b in pairs) / n if n else 0.0,
        "within_one": sum(abs(a - b) <= 1 for a, b in pairs) / n if n else 0.0,
    }


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _fmt(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--prompt-file", type=Path, default=PROMPT_FILE)
    parser.add_argument(
        "--push-prompt",
        action="store_true",
        help="Upload the prompt file to Langfuse if it differs.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Run the judge N times to measure its noise floor.",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Run name prefix (default: today's date and git commit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the compiled prompt for one item; call nothing.",
    )
    args = parser.parse_args()

    try:
        config, text = load_prompt_file(args.prompt_file)
    except ValueError as exc:
        parser.error(str(exc))
    commit = _git_commit()
    os.environ.setdefault("LANGFUSE_RELEASE", commit)
    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    dataset = client.get_dataset(args.dataset)
    if not dataset.items:
        parser.error(
            f"dataset {args.dataset!r} has no items — run build_dataset.py first."
        )

    if args.dry_run:
        item = dataset.items[0]
        compiled = text.replace("{{question}}", item.input["question"]).replace(
            "{{report}}", item.input["report"]
        )
        print(
            f"--- compiled prompt for {item.id} (model {config['model']}) ---\n{compiled}"
        )
        print(
            f"\nDry run: {len(dataset.items)} item(s); no model calls, no Langfuse writes."
        )
        return

    try:
        prompt = sync_prompt(client, config, text, push=args.push_prompt, commit=commit)
    except RuntimeError as exc:
        parser.error(str(exc))
    openai = resolve_openai_client(
        None, backend_name="calibrate.py", timeout=120.0, max_retries=2
    )
    judge = make_judge(client, openai, prompt, config)
    label = args.run_label or f"{date.today().isoformat()}-{commit[:7]}"
    meta = {
        "experiment": EXPERIMENT,
        "prompt_name": config["name"],
        "prompt_version": str(prompt.version),
        "model": config["model"],
        "temperature": config.get("temperature", "model default"),
        "git_commit": commit,
    }
    print(
        f"Dataset: {args.dataset} ({len(dataset.items)} items); prompt v{prompt.version}; model {config['model']}"
    )

    results = []
    for rep in range(1, args.repeat + 1):
        run_name = f"{label}/v{prompt.version}" + (
            f"-r{rep}" if args.repeat > 1 else ""
        )
        result = client.run_experiment(
            name=EXPERIMENT,
            run_name=run_name,
            data=dataset.items,
            task=judge,
            evaluators=[item_scores],
            run_evaluators=[run_scores],
            max_concurrency=4,
            metadata=meta,
            _dataset_version=dataset.version,
        )
        results.append(result)
        print(f"\n=== {run_name} ===")
        print(f"{'task_id':<38}{'human':>6}{'judge':>6}  reasoning")
        for r in result.item_results:
            if not isinstance(r.output, dict):
                continue
            print(
                f"{str(r.item.metadata.get('task_id', r.item.id)):<38}"
                f"{int(r.item.expected_output['answer_relevance']):>6}"
                f"{int(r.output['score']):>6}  {r.output.get('reasoning', '')[:90]}"
            )
        summary = {ev.name: ev.value for ev in result.run_evaluations}
        print(
            f"\nn={summary.get('n_scored')}  exact={_fmt(summary.get('exact_match_rate'), True)}  "
            f"within_one={_fmt(summary.get('within_one_rate'), True)}  "
            f"mean_abs_error={_fmt(summary.get('mean_abs_error'))}  "
            f"judge-human={_fmt(summary.get('mean_judge_minus_human'))}  "
            f"spearman={_fmt(summary.get('spearman'))}"
        )
        dropped = len(dataset.items) - len(result.item_results)
        if dropped:
            print(
                f"WARNING: {dropped} item(s) failed — see the errors above; they are left out of the averages"
            )
        print(f"-> {result.dataset_run_url}")

    if len(results) > 1:
        floor = self_agreement(results[0].item_results, results[1].item_results)
        print(
            f"\nNoise floor (run 1 vs run 2, n={floor['n']}): judge agrees with itself "
            f"exactly {floor['exact']:.0%}, within one point {floor['within_one']:.0%}"
        )
    tracing.flush(client)


if __name__ == "__main__":
    main()
