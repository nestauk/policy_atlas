"""Summarise one or more screening runs, and compare them, from their saved files.

No model calls: everything is worked out from the ``result_*.csv`` files and
``eval_results.json`` that ``run_screen.py`` writes. The same run folders always
give the same numbers, so every figure in the task notes can be checked.

    uv run --project backend python scripts/evals/screening/checks/analyse_runs.py \\
        scripts/evals/screening/results/runs/<run A> [<run B> ...]

What it prints, as Markdown:

- Per run and per source: recall on included documents with a 95% interval,
  excludes dropped, precision (SYNERGY and all sources together only; see the
  README for why the other sources' precision is not a fair number), the expected
  one-call recall, how often all calls agree, ``unsure`` answers and the cost.
- The confidence of wrong ``not_relevant`` answers, against right ones.
- With two runs: the includes only one run kept, and an exact McNemar test.
- With two or more runs: the includes every run dropped.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd
from adapter import MISSING_ABSTRACT

KEEP = ("relevant", "unsure")


def wilson_interval(kept: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a share, which behaves well near 0 and 1.

    Args:
        kept: Successes, for example included documents kept.
        total: Trials, for example included documents.
        z: Normal quantile; 1.96 gives a 95% interval.

    Returns:
        ``(low, high)``, or ``(nan, nan)`` when ``total`` is 0.
    """
    if total == 0:
        return math.nan, math.nan
    share = kept / total
    denominator = 1 + z * z / total
    centre = (share + z * z / (2 * total)) / denominator
    half = (
        z
        * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total))
        / denominator
    )
    return centre - half, centre + half


def mcnemar_exact_p(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar test on the documents where two runs disagree.

    Args:
        only_a: Documents run A kept and run B dropped.
        only_b: Documents run B kept and run A dropped.

    Returns:
        The p-value: how often a split at least this uneven happens by chance
        when the two runs are equally good. 1.0 when they never disagree.
    """
    total = only_a + only_b
    if total == 0:
        return 1.0
    probabilities = [math.comb(total, k) / 2**total for k in range(total + 1)]
    observed = probabilities[only_a]
    return min(1.0, sum(p for p in probabilities if p <= observed + 1e-12))


def f_score(precision: float, recall: float, beta: float = 1.0) -> float:
    """F-score: one number combining precision and recall.

    F1 (``beta=1``) weighs them equally. F2 (``beta=2``) counts recall twice
    as much, which suits a screen that should rather keep a doubtful document.

    Args:
        precision: Share of kept documents that are included.
        recall: Share of included documents that are kept.
        beta: How many times more recall counts than precision.

    Returns:
        The score, or 0.0 when both inputs are 0.
    """
    denominator = beta * beta * precision + recall
    if denominator == 0:
        return 0.0
    return (1 + beta * beta) * precision * recall / denominator


def keep_share(answers: list[dict]) -> float:
    """Share of a document's calls that voted to keep it.

    A single call is one draw from the same model and prompt, so this is the
    chance that a one-call screen keeps the document.

    Args:
        answers: The parsed ``rep_answers`` list; failed calls are skipped.

    Returns:
        A share between 0 and 1, or ``nan`` when every call failed.
    """
    valid = [answer for answer in answers if "decision" in answer]
    if not valid:
        return math.nan
    return sum(answer["decision"] in KEEP for answer in valid) / len(valid)


def load_run(folder: Path) -> tuple[pd.DataFrame, dict]:
    """Read a run folder into one table with a row per document.

    Args:
        folder: A folder written by ``run_screen.py``.

    Returns:
        The documents with ``target``, ``source`` and derived columns, and the
        run's ``eval_results.json``.
    """
    summary = json.loads((folder / "eval_results.json").read_text(encoding="utf-8"))
    sources = {
        item["target"]: item["dataset_source"]
        for item in summary["targets"]
        if "dataset_source" in item
    }
    frames = []
    for path in sorted(folder.glob("result_*.csv")):
        frame = pd.read_csv(path)
        frame["target"] = path.stem.removeprefix("result_")
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True)
    table["source"] = table["target"].map(sources)
    answers = table["rep_answers"].map(json.loads)
    table["answers"] = answers
    table["keep_share"] = answers.map(keep_share)
    table["first_keep"] = answers.map(
        lambda reps: float(reps[0].get("decision") in KEEP) if reps else math.nan
    )
    table["unanimous"] = table["keep_share"].isin([0.0, 1.0])
    return table, summary


def _source_row(name: str, group: pd.DataFrame, show_precision: bool) -> str:
    included = group[group["ground_truth_relevant"] == 1]
    excluded = group[group["ground_truth_relevant"] == 0]
    kept_included = int(included["predicted_relevant"].sum())
    low, high = wilson_interval(kept_included, len(included))
    recall = kept_included / len(included) if len(included) else math.nan
    kept = int(group["predicted_relevant"].sum())
    if show_precision and kept:
        share_kept = kept_included / kept
        precision = f"{share_kept:.3f}"
        f1 = f"{f_score(share_kept, recall):.3f}"
        f2 = f"{f_score(share_kept, recall, beta=2):.3f}"
    else:
        precision = f1 = f2 = "—"
    dropped = int((excluded["predicted_relevant"] == 0).sum())
    unsure = int(group["n_unsure"].sum())
    calls = int(group["answers"].map(len).sum())
    return (
        f"| {name} | {len(group)} | {recall:.3f} ({kept_included}/{len(included)}) "
        f"[{low:.2f}–{high:.2f}] | {dropped}/{len(excluded)} | {precision} | {f1} | {f2} | "
        f"{included['keep_share'].mean():.3f} | {included['first_keep'].mean():.3f} | "
        f"{group['unanimous'].mean():.0%} | {unsure}/{calls} |"
    )


def describe_run(folder: Path, table: pd.DataFrame, summary: dict) -> list[str]:
    """Markdown summary of one run.

    Args:
        folder: The run folder.
        table: From ``load_run``.
        summary: The run's ``eval_results.json``.

    Returns:
        Markdown lines.
    """
    cost = summary.get("cost_usd")
    lines = [
        f"## {folder.name}",
        "",
        f"Model `{summary['model']}`, {summary['reps']} call(s) per document, "
        f"dataset `{summary.get('dataset', '?')}`, prompt "
        f"`{summary.get('system_prompt', summary.get('prompt_version'))}`, "
        f"questions `{summary.get('questions', 'v1 (hand-written)')}`"
        f"{' with criteria' if summary.get('criteria') else ''}, "
        f"cost {'unknown' if cost is None else f'${cost:.2f}'}, "
        f"failed documents {int((table['status'] == 'failed').sum())}.",
        "",
        "| Source | Docs | Recall [95%] | Excludes dropped | Precision | F1 | F2 | "
        "One-call recall (expected) | One-call recall (first call) | "
        "All calls agree | Unsure answers |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source, group in table.groupby("source"):
        lines.append(_source_row(source, group, show_precision=source == "SYNERGY"))
    lines.append(_source_row("**All**", table, show_precision=True))

    wrong, right = [], []
    for answers, label in zip(
        table["answers"], table["ground_truth_relevant"], strict=True
    ):
        for answer in answers:
            if answer.get("decision") == "not_relevant":
                (wrong if label == 1 else right).append(answer["confidence"])
    if wrong:
        lines += [
            "",
            f"`not_relevant` answers on included documents (wrong): {len(wrong)}, "
            f"confidence {min(wrong):.2f}–{max(wrong):.2f}, median "
            f"{pd.Series(wrong).median():.2f}. On excluded documents (right): "
            f"{len(right)}, median {pd.Series(right).median():.2f}.",
        ]
    return lines + [""]


def _keeps(answer: dict) -> bool:
    return answer.get("decision") in KEEP


def vote_rules(table: pd.DataFrame) -> list[str]:
    """Replay other ways of combining a three-call run's answers, with no new calls.

    Each document's calls are in order, so cheaper rules can be read off the
    same run: what the first call alone decided, what asking again only after
    a "drop" would have decided, and what keeping on any "keep" would have
    decided. Every rule also applies the production title-only rule: a
    document with no abstract is kept when any call it used said
    ``relevant``. So the majority row is exactly what the run recorded.
    Documents with a failed call are left as the run decided them (the
    runs so far had none).

    Args:
        table: From ``load_run``, a run with three calls per document.

    Returns:
        Markdown lines, or nothing when the run did not make three calls.
    """
    answers = table["answers"]
    if not (answers.map(len) == 3).all():
        return []
    complete = answers.map(lambda reps: all("decision" in a for a in reps))
    title_only = table["abstract_or_summary"].map(
        lambda value: (
            value is None
            or (isinstance(value, float) and math.isnan(value))
            or str(value).strip() in ("", MISSING_ABSTRACT)
        )
    )

    def rule(decide) -> tuple[pd.Series, pd.Series]:
        kept, calls = [], []
        for reps, done, no_abstract, run_kept in zip(
            answers, complete, title_only, table["predicted_relevant"], strict=True
        ):
            if not done:
                kept.append(int(run_kept))
                calls.append(3)
                continue
            keep, used = decide([_keeps(a) for a in reps])
            if no_abstract and not keep:
                keep = any(a["decision"] == "relevant" for a in reps[:used])
            kept.append(int(keep))
            calls.append(used)
        return pd.Series(kept, index=table.index), pd.Series(calls, index=table.index)

    rules = {
        "One call (the first)": lambda v: (v[0], 1),
        "Majority of three (production)": lambda v: (sum(v) >= 2, 3),
        "Keep if any of three keeps": lambda v: (any(v), 3),
        "Adaptive: on a drop, ask twice more, majority": lambda v: (
            (True, 1) if v[0] else (sum(v) >= 2, 3)
        ),
        "Adaptive: on a drop, ask once more, keep if it keeps": lambda v: (
            (True, 1) if v[0] else (v[1], 2)
        ),
    }
    included = table["ground_truth_relevant"] == 1
    lines = [
        "## Vote rules replayed on this run",
        "",
        "Same answers, other ways of combining them, each with the production "
        "title-only rule. The majority row is the run's own decision.",
        "",
        "| Rule | Recall | Excludes dropped | Precision SYNERGY | Precision all | F1 | "
        "F2 | Calls per document |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, decide in rules.items():
        kept, calls = rule(decide)
        hits = int(kept[included].sum())
        recall = hits / included.sum()
        precision = hits / kept.sum()
        synergy = table["source"] == "SYNERGY"
        synergy_precision = kept[included & synergy].sum() / kept[synergy].sum()
        lines.append(
            f"| {name} | {recall:.3f} ({hits}/{int(included.sum())}) | "
            f"{int((kept[~included] == 0).sum())}/{int((~included).sum())} | "
            f"{synergy_precision:.3f} | {precision:.3f} | "
            f"{f_score(precision, recall):.3f} | {f_score(precision, recall, beta=2):.3f} | "
            f"{calls.mean():.2f} |"
        )
    # Two separate one-call runs disagree on a document as often as two of its
    # calls do: k keeps out of three calls give k * (3 - k) disagreeing pairs of 3.
    votes = answers[complete].map(lambda reps: sum(_keeps(a) for a in reps))
    pair_disagreement = votes.map(lambda k: k * (3 - k) / 3)
    included_votes = pair_disagreement[included[complete]]
    lines += [
        "",
        f"Two separate one-call runs would decide differently on about "
        f"{pair_disagreement.mean():.1%} of documents ({included_votes.mean():.1%} of "
        "included ones), estimated from the pairs of calls within each document.",
    ]
    return lines + [""]


def compare(runs: list[tuple[Path, pd.DataFrame]]) -> list[str]:
    """Markdown comparison of runs over the same documents.

    Args:
        runs: ``(folder, table)`` pairs from ``load_run``.

    Returns:
        Markdown lines. Empty for a single run.
    """
    if len(runs) < 2:
        return []
    key = ["target", "doc_id"]
    kept = None
    for index, (_folder, table) in enumerate(runs):
        part = (
            table[table["ground_truth_relevant"] == 1]
            .set_index(key)[["predicted_relevant"]]
            .rename(columns={"predicted_relevant": f"kept_{index}"})
        )
        if kept is None:
            kept = part.join(table.set_index(key)[["title", "source"]])
        else:
            kept = kept.join(part, how="inner")
    columns = [f"kept_{index}" for index in range(len(runs))]
    lines = [f"## Included documents, compared ({len(kept)} in every run)", ""]

    if len(runs) == 2:
        only_a = kept[(kept["kept_0"] == 1) & (kept["kept_1"] == 0)]
        only_b = kept[(kept["kept_0"] == 0) & (kept["kept_1"] == 1)]
        p_value = mcnemar_exact_p(len(only_a), len(only_b))
        lines += [
            f"Kept only by `{runs[0][0].name}`: {len(only_a)}. "
            f"Kept only by `{runs[1][0].name}`: {len(only_b)}. "
            f"Exact McNemar p = {p_value:.3f}.",
            "",
        ]
        for label, part in (("first only", only_a), ("second only", only_b)):
            for (target, _doc), row in part.iterrows():
                lines.append(f"- {label}: {target} — {str(row['title'])[:110]}")
        lines.append("")

    missed = kept[(kept[columns] == 0).all(axis=1)]
    lines += [f"Dropped by every run: {len(missed)}.", ""]
    for (target, doc_id), row in missed.iterrows():
        lines.append(f"- {target} (`{doc_id}`) — {str(row['title'])[:110]}")
    return lines + [""]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("runs", nargs="+", type=Path, help="Run folders")
    args = parser.parse_args()
    loaded = []
    lines: list[str] = []
    for folder in args.runs:
        table, summary = load_run(folder)
        loaded.append((folder, table))
        lines += describe_run(folder, table, summary)
        lines += vote_rules(table)
    lines += compare(loaded)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
