"""Score a screening run against the human include/exclude labels.

Recall is the share of human-included documents the screen also kept.
Precision is the share of kept documents that humans included. F2 weights
recall twice as heavily as precision, which matches a screen that would
rather keep a doubtful document than drop a relevant one.
"""

from __future__ import annotations

import pandas as pd

# USD per 1,000,000 tokens. Standard short-context rates published by OpenAI
# on 2026-10-08 (https://developers.openai.com/api/docs/pricing). Cached input
# is the cheaper rate for prompt tokens the provider marked as cached.
# Tuple is (input, cached input, output).
PRICE_PER_MILLION: dict[str, tuple[float, float, float]] = {
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.6-luna": (0.20, 0.02, 1.20),
}
PRICE_AS_OF = "2026-10-08"


def cost_usd(
    model: str,
    *,
    prompt_tokens: int,
    cached_tokens: int,
    completion_tokens: int,
) -> float | None:
    """Price one run from token counts.

    Args:
        model: OpenAI model id. Unknown models return ``None``; the token
            counts are still stored.
        prompt_tokens: Input tokens, including cached ones.
        cached_tokens: Input tokens billed at the cached rate.
        completion_tokens: Output tokens.

    Returns:
        The dollar cost, or ``None`` when ``model`` has no published rate here.
    """
    rates = PRICE_PER_MILLION.get(model)
    if rates is None:
        return None
    input_rate, cached_rate, output_rate = rates
    cached = min(cached_tokens, prompt_tokens)
    uncached = prompt_tokens - cached
    return (
        uncached * input_rate + cached * cached_rate + completion_tokens * output_rate
    ) / 1_000_000


def calculate_metrics(frame: pd.DataFrame) -> dict[str, float | int | None]:
    """Compare predictions with the human labels.

    Args:
        frame: One row per document. Needs ``ground_truth_relevant`` (0 or 1),
            ``predicted_relevant`` (0 or 1) and ``confidence`` (float, missing
            when the screen failed to decide).

    Returns:
        Recall, precision, F2, the four confusion-table counts, and the mean
        confidence in each cell of that table. A failed screen counts as not
        kept, so it can only add false negatives or true negatives.
    """
    labels = frame["ground_truth_relevant"].astype(int)
    predicted = frame["predicted_relevant"].astype(int)
    confidence = pd.to_numeric(frame["confidence"], errors="coerce")

    true_positive = int(((labels == 1) & (predicted == 1)).sum())
    false_positive = int(((labels == 0) & (predicted == 1)).sum())
    false_negative = int(((labels == 1) & (predicted == 0)).sum())
    true_negative = int(((labels == 0) & (predicted == 0)).sum())

    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    beta = 2
    if precision + recall:
        f_beta = (1 + beta**2) * (precision * recall) / ((beta**2 * precision) + recall)
    else:
        f_beta = 0.0

    def _mean(mask: pd.Series) -> float | None:
        values = confidence[mask].dropna()
        if values.empty:
            return None
        return float(values.mean())

    return {
        "recall": float(recall),
        "precision": float(precision),
        "f_beta_2": float(f_beta),
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "tn": true_negative,
        "avg_conf_tp": _mean((labels == 1) & (predicted == 1)),
        "avg_conf_tn": _mean((labels == 0) & (predicted == 0)),
        "avg_conf_fp": _mean((labels == 0) & (predicted == 1)),
        "avg_conf_fn": _mean((labels == 1) & (predicted == 0)),
    }
