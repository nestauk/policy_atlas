"""Score the product's title-and-abstract screen against the labelled datasets.

The calls go through the production stage-1 code: the same backend, prompt,
call order, concurrency and retries as the app. Only the model, the number of
calls per document and an optional reasoning effort can change, in this
process only (``use_settings``).

Default is the ``mini`` dataset (about 300 documents over all 30 questions)
using production's adaptive vote and model. ``--vote majority --reps N`` runs
the historical fixed-repetition experiment. ``--dataset full`` (about 3,000
documents) is for a setting that already looks good on ``mini``.

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/screening/checks/run_screen.py
    uv run --project backend --env-file backend/.env \\
        python scripts/evals/screening/checks/run_screen.py --reps 1 --model gpt-5.6-luna
    uv run --project backend --env-file backend/.env \\
        python scripts/evals/screening/checks/run_screen.py --dataset full
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import logging
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from typing import Any

import _bootstrap  # noqa: F401
import pandas as pd
import policy_atlas.evidence_search.assess.screen as product_screen
import policy_atlas.evidence_search.assess.screen_prompt as product_prompt
import policy_atlas.evidence_search.assess.screening_backend as product_backend
from adapter import MISSING_ABSTRACT, SIZES, dataset_manifest, load_and_adapt_dataset
from metrics import PRICE_AS_OF, PRICE_PER_MILLION, calculate_metrics, cost_usd
from policy_atlas.core import tracing
from policy_atlas.core.openai_client import CallBudget
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.assess.screen import (
    MAX_CONCURRENT_STAGE1,
    SCREEN_RETRY_CAP,
    _RepOutcome,
    _Stage1Doc,
    _run_stage1_calls,
)
from policy_atlas.evidence_search.assess.screen_prompt import (
    SCREEN_MODEL,
    SCREEN_PROMPT_VERSION,
    ScreenEnvelopePayload,
)
from policy_atlas.evidence_search.assess.screening_backend import (
    OpenAIScreeningBackend,
    ScreeningBackend,
)
from targets import TARGETS_JSON, select_targets
from vote import combine_adaptive, combine_reps

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results" / "runs"


def abstract_for_prompt(value: object) -> str | None:
    """Return the abstract the screen should see, or None when there is none.

    Args:
        value: The table cell. The adapter's missing-abstract sentence counts
            as no abstract, so the title-only keep rule still applies.

    Returns:
        The abstract text, or None.
    """
    text = (
        ""
        if value is None or (isinstance(value, float) and pd.isna(value))
        else str(value)
    )
    text = text.strip()
    if not text or text == MISSING_ABSTRACT:
        return None
    return text


# The production values, read once at import, so every call to use_settings
# starts from production and a setting left out is never inherited from an
# earlier run in the same process.
_PRODUCTION = {
    "prompt": product_prompt.SCREEN_SYSTEM_PROMPT,
    "model": product_backend.SCREEN_MODEL,
    "parse": product_backend.parse_structured,
}


def use_settings(
    *, model: str, effort: str | None, system_prompt: Path | None = None
) -> str:
    """Point the production screen at the eval's settings, in this process only.

    The eval calls the production stage-1 code (``_run_stage1_calls`` and
    ``OpenAIScreeningBackend``), so call order, concurrency, retries and the
    prompt are the app's. Only the model, the number of calls per document, an
    optional reasoning effort and an optional system prompt change, by resetting
    module names here. The committed product settings and the hash-pinned prompt
    are not edited: a prompt experiment reads a copy from ``prompts/``.

    Args:
        model: OpenAI model id.
        effort: Optional ``reasoning_effort``. None leaves the call as in production.
        system_prompt: Optional file holding a replacement stage-1 system
            prompt. None keeps the production ``screen_v4`` text.

    Returns:
        A label for the system prompt used: ``screen_v4`` or the file name plus
        the first 12 characters of its SHA-256 hash.
    """
    label = SCREEN_PROMPT_VERSION
    product_prompt.SCREEN_SYSTEM_PROMPT = _PRODUCTION["prompt"]
    if system_prompt is not None:
        text = system_prompt.read_text(encoding="utf-8")
        product_prompt.SCREEN_SYSTEM_PROMPT = text
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        label = f"{system_prompt.stem}@{digest}"
    product_backend.SCREEN_MODEL = model
    product_backend.parse_structured = _PRODUCTION["parse"]
    if effort is not None:
        product_backend.parse_structured = functools.partial(
            _PRODUCTION["parse"], reasoning_effort=effort
        )
    return label


def _run_fixed_reps(
    docs: list[_Stage1Doc], *, reps: int, backend: ScreeningBackend
) -> tuple[dict[int, list[_RepOutcome]], int, dict[str, int]]:
    """Run eval-only historical fixed repetitions with production retry mechanics."""
    tasks = [
        (doc_index, rep_index)
        for doc_index in range(len(docs))
        for rep_index in range(reps)
    ]
    budget = CallBudget(maximum=len(tasks) * (1 + SCREEN_RETRY_CAP))
    results: dict[tuple[int, int], Any] = {}
    errors: dict[tuple[int, int], Exception] = {}
    usage = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STAGE1) as executor:
        submitted: list[tuple[tuple[int, int], Future[Any]]] = []
        for key in tasks:
            if not budget.reserve():
                errors[key] = RuntimeError("call budget exhausted")
                continue
            doc_index, rep_index = key
            submitted.append(
                (
                    key,
                    tracing.submit_with_context(
                        executor,
                        backend.screen_envelope,
                        docs[doc_index].payload,
                        rep_index=rep_index,
                    ),
                )
            )
        wait([future for _, future in submitted])
        for key, future in submitted:
            try:
                reply, call_usage = future.result()
                results[key] = reply
                usage.add(call_usage)
            except Exception as exc:  # noqa: BLE001
                errors[key] = exc
    retries = 0
    for key in list(errors):
        if not budget.reserve():
            continue
        retries += 1
        doc_index, rep_index = key
        try:
            reply, call_usage = backend.screen_envelope(
                docs[doc_index].payload, rep_index=rep_index
            )
            results[key] = reply
            usage.add(call_usage)
        except Exception as exc:  # noqa: BLE001
            errors[key] = exc
        else:
            del errors[key]
    return (
        {
            doc_index: [
                _RepOutcome(rep=results[key])
                if key in results
                else _RepOutcome(error_type=type(errors[key]).__name__)
                for rep_index in range(reps)
                for key in [(doc_index, rep_index)]
            ]
            for doc_index in range(len(docs))
        },
        retries,
        usage.payload(),
    )


def _stage1_doc(index: int, row: pd.Series, intent: str) -> _Stage1Doc:
    """Build the record the production stage-1 loop screens.

    The labelled abstracts are paper abstracts, so the fields match what
    acquire stores for an OpenAlex paper: ``abstract_source`` is
    ``publisher_abstract`` (``none`` without an abstract) and there is no
    ``title_source``.
    """
    abstract = abstract_for_prompt(row["abstract_or_summary"])
    placeholder = uuid.UUID(int=index)  # the loop reads only ``payload``
    return _Stage1Doc(
        tss_id=placeholder,
        source_snapshot_id=placeholder,
        metadata={},
        basis="title_abstract" if abstract else "title_only",
        payload=ScreenEnvelopePayload(
            tss_id=str(row["doc_id"]),
            title=str(row["title"]),
            abstract=abstract,
            abstract_source="publisher_abstract" if abstract else "none",
            title_source=None,
            intent=intent,
        ),
    )


def screen_frame(
    frame: pd.DataFrame,
    *,
    backend: ScreeningBackend,
    intent: str,
    vote: str,
    reps: int,
) -> tuple[pd.DataFrame, dict[str, int], int]:
    """Screen every row the way one production stage-1 batch does.

    Args:
        frame: The adapted table for one target.
        backend: The production OpenAI screening backend (the stub in tests).
        intent: The target question.
        vote: ``adaptive`` for production's rule or ``majority`` for historical experiments.
        reps: Independent calls per document for majority mode.

    Returns:
        The input columns plus the screen columns, in the original row order;
        the token totals; and the number of retried calls.
    """
    frame = frame.reset_index(drop=True)
    docs = [_stage1_doc(index, row, intent) for index, row in frame.iterrows()]
    logger.info("Screening %s documents with %s vote", len(docs), vote)
    if vote == "adaptive":
        outcomes_by_doc, retries, usage = _run_stage1_calls(
            docs, screening_backend=backend
        )
    elif vote == "majority":
        outcomes_by_doc, retries, usage = _run_fixed_reps(
            docs, reps=reps, backend=backend
        )
    else:
        raise ValueError(f"unknown vote mode: {vote}")

    rows: list[dict] = []
    for index, doc in enumerate(docs):
        outcomes = outcomes_by_doc[index]
        parsed = [outcome.rep for outcome in outcomes if outcome.rep is not None]
        decision = (
            combine_adaptive([outcome.rep for outcome in outcomes])
            if vote == "adaptive"
            else combine_reps(parsed, reps_requested=reps, title_only=False)
        )
        counts = {"relevant": 0, "not_relevant": 0, "unsure": 0}
        for rep in parsed:
            counts[rep.decision] += 1
        source = frame.iloc[index]
        rows.append(
            {
                "doc_id": source["doc_id"],
                "title": source["title"],
                "abstract_or_summary": source["abstract_or_summary"],
                "ground_truth_relevant": int(source["ground_truth_relevant"]),
                "status": decision.status,
                "confidence": decision.confidence,
                "predicted_relevant": int(decision.status == "relevant"),
                "n_relevant": counts["relevant"],
                "n_not_relevant": counts["not_relevant"],
                "n_unsure": counts["unsure"],
                "n_failed_reps": len(outcomes) - len(parsed),
                "flags": ",".join(decision.flags),
                "reasons": " | ".join(rep.reason for rep in parsed),
                "errors": " | ".join(
                    outcome.error_type or ""
                    for outcome in outcomes
                    if outcome.rep is None
                ),
                # Every call in order, so one-call and adaptive-vote results can
                # be worked out later from this run without new calls.
                "rep_answers": json.dumps(
                    [
                        {"failed": outcome.error_type}
                        if outcome.rep is None
                        else {
                            "decision": outcome.rep.decision,
                            "confidence": float(outcome.rep.confidence),
                        }
                        for outcome in outcomes
                    ]
                ),
            }
        )
    return pd.DataFrame(rows), usage, retries


def target_intent(target: dict, *, with_criteria: bool) -> str:
    """The scope intent the screen sees for one target.

    Args:
        target: From ``select_targets``.
        with_criteria: Add the published criteria under the question, through
            the product's own ``_compose_screen_intent``, as the app does when a
            plan carries screening criteria.

    Returns:
        The question alone, or the question plus criteria.
    """
    if not with_criteria:
        return target["query"]
    return product_screen._compose_screen_intent(target["query"], target["criteria"])


def _run_name(
    dataset: str,
    model: str,
    vote: str,
    reps: int,
    effort: str | None,
    prompt: Path | None,
    criteria: bool,
) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = model.replace("/", "-")
    name = f"{stamp}-{dataset}-{slug}-{vote}-r{reps}"
    if effort:
        name += f"-e{effort}"
    if prompt is not None:
        name += f"-{prompt.stem}"
    if criteria:
        name += "-criteria"
    return name


def run(args: argparse.Namespace) -> Path:
    """Screen the selected targets and write one results folder.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The run folder.

    Raises:
        SystemExit: If every target failed to load or to score.
    """
    targets = select_targets(args.targets)
    effort = args.reasoning_effort
    output = RUNS / _run_name(
        args.dataset,
        args.model,
        args.vote,
        args.reps,
        effort,
        args.system_prompt,
        args.criteria,
    )
    output.mkdir(parents=True, exist_ok=True)
    prompt_label = use_settings(
        model=args.model,
        effort=effort,
        system_prompt=args.system_prompt,
    )
    backend = OpenAIScreeningBackend()  # no Langfuse client: tracing is off

    summaries: list[dict] = []
    run_usage = UsageAccumulator()
    for target in targets:
        name = target["name"]
        logger.info("Starting %s (%s)", name, target["id"])
        try:
            frame = load_and_adapt_dataset(target, size=args.dataset)
        except Exception as exc:
            logger.error("Failed to load %s: %s", name, exc)
            summaries.append({"target": name, "error": str(exc)})
            continue
        if frame.empty:
            logger.warning("Dataset empty for %s", name)
            summaries.append({"target": name, "error": "Dataset empty"})
            continue

        screened, usage, retries = screen_frame(
            frame,
            backend=backend,
            intent=target_intent(target, with_criteria=args.criteria),
            vote=args.vote,
            reps=args.reps,
        )
        run_usage.add_payload(usage)
        screened.to_csv(output / f"result_{name}.csv", index=False)
        metrics = calculate_metrics(screened)
        metrics.update(
            {
                "target": name,
                "id": target["id"],
                "dataset_source": target["dataset_source"],
                "num_docs": len(screened),
                "num_positives": int(screened["ground_truth_relevant"].sum()),
                "n_failed": int((screened["status"] == "failed").sum()),
                "n_unsure_reps": int(screened["n_unsure"].sum()),
                "retries": retries,
                "usage": usage,
            }
        )
        summaries.append(metrics)
        logger.info(
            "%s recall=%.3f precision=%.3f failed=%s",
            name,
            metrics["recall"],
            metrics["precision"],
            metrics["n_failed"],
        )

    scored = [row for row in summaries if "recall" in row]
    if not scored:
        raise SystemExit("No targets scored. See the log above.")

    payload = {
        "dataset": args.dataset,
        "dataset_files": dataset_manifest(),
        "targets_selected": args.targets or "all",
        "model": args.model,
        "vote": args.vote,
        "reps": args.reps,
        "reasoning_effort": effort,
        "prompt_version": SCREEN_PROMPT_VERSION,
        "system_prompt": prompt_label,
        "questions": "targets.json@"
        + hashlib.sha256(TARGETS_JSON.read_bytes()).hexdigest()[:12],
        "criteria": args.criteria,
        "usage": run_usage.payload(),
        "cost_usd": cost_usd(
            args.model,
            prompt_tokens=run_usage.prompt,
            cached_tokens=run_usage.cached,
            completion_tokens=run_usage.completion,
        ),
        "price_per_million_usd": {
            "rates": PRICE_PER_MILLION.get(args.model),
            "as_of": PRICE_AS_OF,
        },
        "targets": summaries,
    }
    (output / "eval_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    table = pd.DataFrame(scored)
    columns = [
        "dataset_source",
        "target",
        "num_docs",
        "num_positives",
        "recall",
        "precision",
        "f_beta_2",
        "n_failed",
    ]
    print("\n=== Screening results ===")
    print(table[columns].to_string(index=False))
    cost = payload["cost_usd"]
    cost_text = "unknown model, see token counts" if cost is None else f"${cost:.4f}"
    print(f"\nTokens: {run_usage.payload()}  Cost: {cost_text}")
    print(f"Wrote {output}")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model",
        default=SCREEN_MODEL,
        help=f"OpenAI model (default: the product screen, {SCREEN_MODEL})",
    )
    parser.add_argument(
        "--vote",
        choices=("majority", "adaptive"),
        default="adaptive",
        help="Vote rule: adaptive production rule (default) or historical majority.",
    )
    parser.add_argument(
        "--reps",
        type=int,
        default=3,
        help="Independent replies per document for --vote majority (ignored for adaptive).",
    )
    parser.add_argument(
        "--criteria",
        action="store_true",
        help="Add each question's published criteria (targets.json) under the "
        "question, as the app does when a plan carries screening criteria. "
        "Default: the question alone.",
    )
    parser.add_argument(
        "--system-prompt",
        type=Path,
        default=None,
        help="File with a replacement stage-1 system prompt, for a prompt experiment "
        "(see prompts/). Default: the production screen_v4 prompt.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=None,
        help="Optional reasoning effort (for example low). Omitted by default, as in production.",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=None,
        help="Target names to score, for a pilot. Default: all 30 questions.",
    )
    parser.add_argument(
        "--dataset",
        choices=sorted(SIZES),
        default="mini",
        help="mini (about 300 documents, default) or full (about 3,000).",
    )
    args = parser.parse_args()
    if args.reps < 1:
        parser.error("--reps must be at least 1")
    if args.vote == "adaptive" and args.reps != 3:
        logger.info("--reps is ignored for adaptive voting")
    return args


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    run(parse_args())


if __name__ == "__main__":
    main()
