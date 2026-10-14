"""Non-AI screening baselines: rank each question's documents, no language model.

Three rankers score every document against the same scope intent the language
model sees (the question, plus its published criteria with ``--criteria``):

- **BM25**: the classic keyword-matching score of search engines. Words in the
  question that are rare across the whole dataset and frequent in a document
  raise its score. Fully deterministic; standard library only.
- **Embeddings**: cosine similarity between the question and the document,
  using the product's own embedding model (``text-embedding-3-small``). No
  training. Vectors are cached, so a rerun gives the same numbers.
- **Hybrid**: reciprocal rank fusion of the two rankings (each document scores
  1/(60 + rank) in each list; the sums are ranked).

A ranking is not a keep-or-drop decision. For a fair comparison with a
language-model run, each ranker keeps, for every question, **the same number of
documents that run kept** (``--match``), so both spend the same reading effort;
only which documents are kept differs. Ranking quality is also reported without
any cut-off: AUC (the chance an included document outranks an excluded one; 0.5
is chance) and average precision per question.

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/screening/experiments/rank_baselines.py --criteria \\
        --match scripts/evals/screening/results/runs/<language-model run>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401
import pandas as pd
from adapter import load_and_adapt_dataset
from analyse_runs import f_score, load_run, mcnemar_exact_p, wilson_interval
from policy_atlas.core.embeddings import (
    API_BATCH_SIZE,
    EMBEDDING_MODEL,
    OpenAIEmbeddingBackend,
)
from run_screen import abstract_for_prompt, target_intent
from targets import select_targets

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "results" / "cache" / f"embeddings-{EMBEDDING_MODEL}.jsonl"
OUT = ROOT / "results" / "baselines"

# BM25's usual settings: k1 limits how much repeating a word helps, b how much
# long documents are penalised.
BM25_K1 = 1.2
BM25_B = 0.75
RRF_K = 60
# Embedding input cap, well inside the model's 8,191-token limit.
EMBED_CHAR_LIMIT = 8_000

# Common English words that carry no topic. Short on purpose: a fixed list,
# so the ranking never depends on anything learned.
STOPWORDS = frozenset(
    """a about after all also an and any are as at be been before being between
    both but by can could did do does during each either for from had has have
    how if in into is it its may more most not of on or other our over per
    should since so such than that the their them then there these they this
    those through to under up was we were what when where whether which while
    who will with within without would""".split()
)
RANKERS = ("bm25", "embedding", "hybrid")


def tokens(text: str) -> list[str]:
    """Lower-case words and numbers, without stopwords or single letters."""
    return [
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 1 and word not in STOPWORDS
    ]


def bm25_scores(
    query: str,
    documents: list[str],
    document_frequency: Counter,
    corpus_size: int,
    average_length: float,
) -> list[float]:
    """BM25 score of each document for one query.

    Args:
        query: The scope intent text.
        documents: The question's documents (title and abstract).
        document_frequency: In how many documents of the whole dataset each word
            appears. Computing it over the whole dataset, not one question's few
            documents, keeps "rare word" meaningful.
        corpus_size: Number of documents in the whole dataset.
        average_length: Mean document length in words over the whole dataset.

    Returns:
        One score per document, in input order.
    """
    query_words = set(tokens(query))
    scores = []
    for text in documents:
        words = tokens(text)
        counts = Counter(words)
        score = 0.0
        for word in query_words:
            frequency = counts.get(word, 0)
            if not frequency:
                continue
            df = document_frequency.get(word, 0)
            idf = math.log((corpus_size - df + 0.5) / (df + 0.5) + 1)
            norm = BM25_K1 * (1 - BM25_B + BM25_B * len(words) / average_length)
            score += idf * frequency * (BM25_K1 + 1) / (frequency + norm)
        scores.append(score)
    return scores


def _key(text: str) -> str:
    return hashlib.sha256(f"{EMBEDDING_MODEL}\n{text}".encode()).hexdigest()


def embed(texts: list[str]) -> dict[str, list[float]]:
    """Embed texts, reading and filling the on-disk cache.

    Args:
        texts: Texts to embed; duplicates are embedded once.

    Returns:
        Text hash to vector, for every input text.
    """
    cached: dict[str, list[float]] = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            cached[row["key"]] = row["vector"]
    missing = sorted(
        {_key(text): text for text in texts if _key(text) not in cached}.items()
    )
    if missing:
        backend = OpenAIEmbeddingBackend()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE.open("a", encoding="utf-8") as handle:
            for start in range(0, len(missing), API_BATCH_SIZE):
                batch = missing[start : start + API_BATCH_SIZE]
                vectors = backend.embed_texts([text for _key_, text in batch])
                for (key, _text), vector in zip(batch, vectors, strict=True):
                    cached[key] = vector
                    handle.write(json.dumps({"key": key, "vector": vector}) + "\n")
        logger.info("Embedded %s new texts", len(missing))
    return {_key(text): cached[_key(text)] for text in texts}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _ranks(scores: pd.Series, doc_ids: pd.Series) -> pd.Series:
    """Rank 1 = best; ties broken by document id, so the order is fixed."""
    order = sorted(
        range(len(scores)), key=lambda i: (-scores.iloc[i], str(doc_ids.iloc[i]))
    )
    ranks = [0] * len(scores)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    return pd.Series(ranks, index=scores.index)


def auc(scores: pd.Series, labels: pd.Series) -> float:
    """Chance a random included document scores above a random excluded one."""
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    if positives.empty or negatives.empty:
        return math.nan
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def average_precision(ranks: pd.Series, labels: pd.Series) -> float:
    """Mean of the precision at each included document's rank."""
    included = sorted(ranks[labels == 1])
    if not included:
        return math.nan
    return sum((hit + 1) / rank for hit, rank in enumerate(included)) / len(included)


def score_documents(dataset: str, with_criteria: bool) -> pd.DataFrame:
    """Every document of every question, with the three rankers' scores and ranks."""
    frames = []
    for target in select_targets(None):
        frame = load_and_adapt_dataset(target, size=dataset).reset_index(drop=True)
        frame["target"] = target["name"]
        frame["source"] = target["dataset_source"]
        frame["intent"] = target_intent(target, with_criteria=with_criteria)
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True)
    table["text"] = [
        f"{title}\n{abstract_for_prompt(abstract) or ''}".strip()[:EMBED_CHAR_LIMIT]
        for title, abstract in zip(
            table["title"], table["abstract_or_summary"], strict=True
        )
    ]

    unique_docs = table.drop_duplicates("doc_id")
    document_frequency = Counter(
        word for text in unique_docs["text"] for word in set(tokens(text))
    )
    average_length = sum(len(tokens(text)) for text in unique_docs["text"]) / len(
        unique_docs
    )

    vectors = embed(list(table["text"]) + list(table["intent"].unique()))
    table["bm25"] = 0.0
    table["embedding"] = 0.0
    for _name, group in table.groupby("target"):
        intent = group["intent"].iloc[0]
        table.loc[group.index, "bm25"] = bm25_scores(
            intent,
            list(group["text"]),
            document_frequency,
            len(unique_docs),
            average_length,
        )
        query_vector = vectors[_key(intent)]
        table.loc[group.index, "embedding"] = [
            _cosine(query_vector, vectors[_key(text)]) for text in group["text"]
        ]
    for ranker in ("bm25", "embedding"):
        table[f"rank_{ranker}"] = 0
        for _name, group in table.groupby("target"):
            table.loc[group.index, f"rank_{ranker}"] = _ranks(
                group[ranker], group["doc_id"]
            )
    table["hybrid"] = 1 / (RRF_K + table["rank_bm25"]) + 1 / (
        RRF_K + table["rank_embedding"]
    )
    table["rank_hybrid"] = 0
    for _name, group in table.groupby("target"):
        table.loc[group.index, "rank_hybrid"] = _ranks(group["hybrid"], group["doc_id"])
    return table


def _matched_row(name: str, part: pd.DataFrame, kept_column: str) -> str:
    included = part[part["ground_truth_relevant"] == 1]
    excluded = part[part["ground_truth_relevant"] == 0]
    kept_included = int(included[kept_column].sum())
    kept = int(part[kept_column].sum())
    recall = kept_included / len(included)
    precision = kept_included / kept if kept else math.nan
    low, high = wilson_interval(kept_included, len(included))
    synergy = part[part["source"] == "SYNERGY"]
    synergy_kept = int(synergy[kept_column].sum())
    synergy_precision = (
        int(synergy.loc[synergy["ground_truth_relevant"] == 1, kept_column].sum())
        / synergy_kept
        if synergy_kept
        else math.nan
    )
    return (
        f"| {name} | {recall:.3f} ({kept_included}/{len(included)}) [{low:.2f}–{high:.2f}] | "
        f"{int((excluded[kept_column] == 0).sum())}/{len(excluded)} | {synergy_precision:.3f} | "
        f"{precision:.3f} | {f_score(precision, recall):.3f} | "
        f"{f_score(precision, recall, beta=2):.3f} |"
    )


def report(table: pd.DataFrame, match: Path | None, with_criteria: bool) -> list[str]:
    """Markdown: ranking quality, and the matched-workload comparison."""
    lines = [
        "## Ranking quality (no cut-off)",
        "",
        "Mean over questions with at least one included and one excluded document.",
        "",
        "| Ranker | AUC | Average precision |",
        "|---|---:|---:|",
    ]
    for ranker in RANKERS:
        per_target = [
            (
                auc(group[ranker], group["ground_truth_relevant"]),
                average_precision(
                    group[f"rank_{ranker}"], group["ground_truth_relevant"]
                ),
            )
            for _name, group in table.groupby("target")
        ]
        valid = [pair for pair in per_target if not math.isnan(pair[0])]
        lines.append(
            f"| {ranker} | {sum(a for a, _ in valid) / len(valid):.3f} | "
            f"{sum(p for _, p in valid) / len(valid):.3f} |"
        )
    if match is None:
        return lines + [""]

    run, summary = load_run(match)
    run = run[["target", "doc_id", "predicted_relevant"]].rename(
        columns={"predicted_relevant": "kept_llm"}
    )
    joined = table.merge(run, on=["target", "doc_id"], how="inner")
    if len(joined) != len(table):
        raise SystemExit("The run does not cover the same documents; check --dataset.")
    budget = joined.groupby("target")["kept_llm"].sum()
    for ranker in RANKERS:
        joined[f"kept_{ranker}"] = (
            joined[f"rank_{ranker}"] <= joined["target"].map(budget)
        ).astype(int)

    lines += [
        "",
        f"## Same workload as `{match.name}`",
        "",
        f"Each ranker keeps, per question, as many documents as the language model kept "
        f"({int(budget.sum())} of {len(joined)}). Model `{summary['model']}`, prompt "
        f"`{summary.get('system_prompt')}`, criteria {summary.get('criteria', False)}.",
        "",
        f"Ranker query: {'question + criteria' if with_criteria else 'question only'}. "
        + (
            "Same scope text as the run: like for like."
            if bool(summary.get("criteria", False)) == with_criteria
            else "**Not like for like:** the run used "
            + (
                "question + criteria."
                if summary.get("criteria")
                else "the question only."
            )
        ),
        "",
        "| Screen | Recall [95%] | Excludes dropped | Precision SYNERGY | Precision all | F1 | F2 |",
        "|---|---|---:|---:|---:|---:|---:|",
        _matched_row("language model", joined, "kept_llm"),
    ]
    # What keeping the same number of documents at random would give, on average:
    # per question, budget / documents of the included ones are kept.
    sizes = joined.groupby("target").size()
    included_per_target = joined.groupby("target")["ground_truth_relevant"].sum()
    expected = float((budget / sizes * included_per_target).sum())
    total_included = int(included_per_target.sum())
    lines.append(
        f"| chance (expected, random pick) | {expected / total_included:.3f} | — | — | "
        f"{expected / budget.sum():.3f} | — | — |"
    )
    for ranker in RANKERS:
        lines.append(_matched_row(ranker, joined, f"kept_{ranker}"))

    lines += ["", "Included documents only one screen kept (exact McNemar test):", ""]
    included = joined[joined["ground_truth_relevant"] == 1]
    for ranker in RANKERS:
        only_llm = int(
            ((included["kept_llm"] == 1) & (included[f"kept_{ranker}"] == 0)).sum()
        )
        only_ranker = int(
            ((included["kept_llm"] == 0) & (included[f"kept_{ranker}"] == 1)).sum()
        )
        lines.append(
            f"- {ranker}: language model only {only_llm}, {ranker} only {only_ranker}, "
            f"p = {mcnemar_exact_p(only_llm, only_ranker):.3f}"
        )
    for source, part in joined.groupby("source"):
        recalls = ", ".join(
            f"{column.removeprefix('kept_')} "
            f"{part.loc[part['ground_truth_relevant'] == 1, column].mean():.3f}"
            for column in ["kept_llm", *[f"kept_{r}" for r in RANKERS]]
        )
        lines.append(f"- Recall on {source}: {recalls}")
    return lines + [""]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", choices=("mini", "full"), default="mini")
    parser.add_argument(
        "--criteria",
        action="store_true",
        help="Add the published criteria to the query.",
    )
    parser.add_argument(
        "--match", type=Path, default=None, help="A language-model run folder to match."
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    table = score_documents(args.dataset, args.criteria)
    name = f"{args.dataset}{'-criteria' if args.criteria else ''}"
    OUT.mkdir(parents=True, exist_ok=True)
    table.drop(columns=["text", "intent"]).to_csv(
        OUT / f"scores-{name}.csv", index=False
    )
    text = "\n".join(report(table, args.match, args.criteria))
    suffix = f"-vs-{args.match.name}" if args.match else ""
    (OUT / f"report-{name}{suffix}.md").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
