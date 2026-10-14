"""Screened seeds against raw seeds for the citation snowball (R&D, task 051).

The task 047 experiments built the snowball from raw search results: the first 200
records the generated queries returned, unscreened. In production every record is
screened, so the seeds could be the screened-in set instead. Seed quality mattered
more than seed count there (500 seeds scored below 200), so screened seeds might
give cleaner citation counts. Or they might lose the seeds that are off topic but
cite the right papers. This script measures it.

Per review:

1. Take the seeds and the snowball of one configuration (the task 047 best run,
   through ``snowball_recall.load_or_expand``, cached).
2. Fetch the seeds' abstracts (one batched OpenAlex call per 50 seeds, cached) and
   screen each seed with the production stage-1 code through the screening eval's
   harness: ``gpt-5.6-luna``, the ``screen_v4`` prompt, and the adaptive rule (one
   call; a second call only after a drop; keep if the second call keeps).
3. Score three candidate lists at each cap, ranked by specificity:
   ``raw``: the task 047 list as it is (no screen);
   ``raw-screened``: the same list with the dropped seeds removed (what production
   would keep from it);
   ``screened``: snowball and forward chasing rebuilt from the kept seeds only, with
   the dropped seeds removed.
4. Report, per review, how many seeds the screen kept, and how many of the
   ground-truth papers among the seeds it kept: a screening recall on real search
   candidates, which the labelled screening datasets cannot give.

Usage::

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/search/experiments/screened_seeds.py \\
        [--model gpt-5.6-luna] [--screen-model gpt-5.6-luna] [--caps 100 150 200 300 400]

Cost: about 1.3 Luna calls per seed (15 reviews x 200 seeds, roughly 50 cents in all).
Verdicts are written per review under ``--out`` and reused on a rerun. Free OpenAlex
calls for the abstracts and the rebuilt snowball, cached. Uploads nothing.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from baseline_recall import cache_path, make_getter
from evals_search_utils import ground_truth_from_item, record_key, select_items
from snowball_recall import (
    MINI_DATASET,
    SEED_ARM,
    candidates,
    expand,
    load_or_expand,
    lookup,
    override_prompt,
    rank,
    score,
    short_id,
    slug,
    with_forward,
)

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from policy_atlas.core import tracing
from policy_atlas.evidence_search.sourcing import search_generation
from policy_atlas.evidence_search.sourcing.acquire import _reconstruct_abstract

# The screening eval's harness (production stage-1 code path, settings swapped in
# this process only). Its folders are not on the import path of the search eval.
_SCREENING = Path(__file__).resolve().parents[2] / "screening"
for _folder in (_SCREENING, _SCREENING / "checks"):
    if str(_folder) not in sys.path:
        sys.path.insert(1, str(_folder))
from policy_atlas.evidence_search.assess.screening_backend import (  # noqa: E402
    OpenAIScreeningBackend,
)
from run_screen import screen_frame, use_settings  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "results" / "snowball"
SCREEN_PROMPT = _SCREENING / "prompts" / "screen_v4.txt"
ABSTRACT_SELECT = "id,abstract_inverted_index"
VARIANTS = ("raw", "raw-screened", "screened")


def seed_abstracts(seed_ids: list[str], *, get: Any) -> dict[str, str | None]:
    """Abstracts of the seeds by short OpenAlex id, cached by the seed set."""
    key = hashlib.sha256("|".join(sorted(seed_ids)).encode()).hexdigest()[:16]
    path = cache_path("openalex-abstracts", key)
    if path.exists():
        return json.loads(path.read_text())
    works, _pages, failed = lookup(seed_ids, select=ABSTRACT_SELECT, get=get)
    if failed:
        raise RuntimeError(f"{failed} abstract lookups failed; rerun")
    out = {
        short_id(w["id"]) or "": _reconstruct_abstract(w.get("abstract_inverted_index"))
        for w in works
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def screen_seeds(
    frame: pd.DataFrame, *, backend: OpenAIScreeningBackend, intent: str
) -> tuple[pd.DataFrame, int]:
    """The adaptive rule: one call each; a second call for the drops; keep if it keeps.

    Returns the per-seed table (first and second decisions, final keep) and the
    number of calls made.
    """
    first, _usage, _retries = screen_frame(
        frame, backend=backend, intent=intent, reps=1
    )
    first = first.rename(columns={"status": "status_1", "confidence": "confidence_1"})
    dropped = first[first["predicted_relevant"] == 0]
    calls = len(first)
    first["status_2"] = None
    first["confidence_2"] = None
    first["kept"] = first["predicted_relevant"].astype(int)
    if len(dropped):
        second, _usage, _retries = screen_frame(
            frame[frame["doc_id"].isin(dropped["doc_id"])],
            backend=backend,
            intent=intent,
            reps=1,
        )
        calls += len(second)
        by_id = second.set_index("doc_id")
        for index, row in first.iterrows():
            if row["doc_id"] in by_id.index:
                first.at[index, "status_2"] = by_id.at[row["doc_id"], "status"]
                first.at[index, "confidence_2"] = by_id.at[row["doc_id"], "confidence"]
                first.at[index, "kept"] = int(
                    by_id.at[row["doc_id"], "predicted_relevant"]
                )
    return first, calls


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", default=MINI_DATASET)
    parser.add_argument(
        "--model", default="gpt-5.6-luna", help="query-generation model"
    )
    parser.add_argument("--screen-model", default="gpt-5.6-luna")
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--expand", type=int, default=200)
    parser.add_argument("--forward", type=int, default=200)
    parser.add_argument(
        "--caps", nargs="+", type=int, default=[100, 150, 200, 300, 400]
    )
    parser.add_argument("--reviews", nargs="+", default=None, metavar="TEXT")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()

    search_generation.SEARCH_QUERIES_MODEL = args.model
    prompt_sha = override_prompt("shared+semantic", None)
    seed_kwargs: dict[str, Any] = dict(
        source="shared+semantic",
        prompt_sha=prompt_sha,
        forward=args.forward,
        forward_pages=10,
        forward_max_cites=300,
        forward_top=20,
    )
    label = args.label or (
        f"{date.today().isoformat()}-screened-seeds-{args.model}-s{args.seeds}-k{args.expand}-f{args.forward}"
    )
    out = args.out / label
    (out / "verdicts").mkdir(parents=True, exist_ok=True)
    get = make_getter(SEED_ARM)
    prompt_label = use_settings(
        model=args.screen_model, reps=1, effort=None, system_prompt=SCREEN_PROMPT
    )
    backend = OpenAIScreeningBackend()

    client = tracing.get_langfuse()
    if client is None:
        parser.error(
            "needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST."
        )
    items = select_items(list(client.get_dataset(args.dataset).items), args.reviews)

    rows: list[dict[str, Any]] = []
    seed_rows: list[dict[str, Any]] = []
    for item in items:
        title = item.metadata.get("review_title", str(item.id))
        intent, cutoff = item.input["intent"], item.input["published_before"]
        ground_truth = ground_truth_from_item(item)
        payload, _cached = load_or_expand(
            item_id=str(item.id),
            intent=intent,
            cutoff=cutoff,
            n_seeds=args.seeds,
            n_expand=args.expand,
            refresh=False,
            get=get,
            **seed_kwargs,
        )
        seed_ids = [short_id(w["id"]) or "" for w in payload["seed_works"]]
        verdict_path = out / "verdicts" / f"{slug(title)}.csv"
        if verdict_path.exists():
            verdicts = pd.read_csv(verdict_path)
            calls = int(verdicts["n_calls"].iloc[0]) if "n_calls" in verdicts else 0
        else:
            abstracts = seed_abstracts(seed_ids, get=get)
            frame = pd.DataFrame(
                {
                    "doc_id": seed_ids,
                    "title": [
                        w.get("display_name") or "" for w in payload["seed_works"]
                    ],
                    "abstract_or_summary": [
                        abstracts.get(sid) or "" for sid in seed_ids
                    ],
                    "ground_truth_relevant": [
                        int(
                            (
                                record_key({"doi": w.get("doi"), "backend": "openalex"})
                                or ""
                            )
                            in ground_truth.keys
                        )
                        for w in payload["seed_works"]
                    ],
                }
            )
            verdicts, calls = screen_seeds(frame, backend=backend, intent=intent)
            verdicts["n_calls"] = calls
            verdicts.to_csv(verdict_path, index=False)
        kept_ids = [
            str(d) for d in verdicts.loc[verdicts["kept"] == 1, "doc_id"].tolist()
        ]
        kept_set = set(kept_ids)
        gt_seeds = int(verdicts["ground_truth_relevant"].sum())
        gt_kept = int(
            verdicts.loc[verdicts["kept"] == 1, "ground_truth_relevant"].sum()
        )
        seed_rows.append(
            {
                "review": title,
                "n_seeds": len(seed_ids),
                "n_kept": len(kept_ids),
                "gt_seeds": gt_seeds,
                "gt_seeds_kept": gt_kept,
                "n_calls": calls,
            }
        )
        print(
            f"{title[:60]}: {len(kept_ids)}/{len(seed_ids)} seeds kept, "
            f"{gt_kept}/{gt_seeds} ground-truth seeds kept, {calls} calls"
        )

        # The rebuilt snowball from the kept seeds, cached by the kept set.
        kept_digest = hashlib.sha256("|".join(kept_ids).encode()).hexdigest()[:12]
        tag = f"screened-{prompt_label}-{kept_digest}"
        path = cache_path(
            "openalex-snowball-screened", f"{item.id}|{tag}|{cutoff}|{args.expand}"
        )
        if path.exists():
            screened = json.loads(path.read_text())
        else:
            screened = expand(
                kept_ids,
                cutoff=cutoff,
                n_seeds=len(kept_ids),
                n_expand=args.expand,
                get=get,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(screened))
        screened = with_forward(
            screened,
            item_id=str(item.id),
            tag=tag,
            intent=intent,
            cutoff=cutoff,
            n_seeds=len(kept_ids),
            forward=args.forward,
            pages=10,
            max_cites=300,
            use_search=False,
            refresh=False,
            get=get,
            top=20,
            sort=None,
        )

        lists = {
            "raw": rank(candidates(payload), "specific"),
            "raw-screened": [
                r
                for r in rank(candidates(payload), "specific")
                if r["source"] != "seed" or r["openalex_id"] in kept_set
            ],
            "screened": rank(candidates(screened), "specific"),
        }
        for variant, ranked in lists.items():
            for cap in args.caps + [10**6]:
                s = score(ranked, ground_truth, cap, set())
                rows.append(
                    {
                        "review": title,
                        "variant": variant,
                        "cap": cap if cap < 10**6 else "all",
                        **{k: v for k, v in s.items() if k != "seminal_recall"},
                    }
                )

    with (out / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (out / "seeds.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(seed_rows[0]))
        writer.writeheader()
        writer.writerows(seed_rows)

    n = len(seed_rows)
    print(
        f"\n{n} reviews -> {out}\nseeds kept {sum(r['n_kept'] for r in seed_rows) / max(1, sum(r['n_seeds'] for r in seed_rows)):.0%}; "
        f"ground-truth seeds kept {sum(r['gt_seeds_kept'] for r in seed_rows)}/{sum(r['gt_seeds'] for r in seed_rows)}; "
        f"{sum(r['n_calls'] for r in seed_rows)} screening calls"
    )
    caps = args.caps + ["all"]
    print(f"\n| variant | {' | '.join(f'@{c}' for c in caps)} |")
    print(f"|---|{'---:|' * len(caps)}")
    for variant in VARIANTS:
        cells = []
        for cap in caps:
            sub = [r for r in rows if r["variant"] == variant and r["cap"] == cap]
            cells.append(f"{sum(r['recall'] for r in sub) / max(1, len(sub)):.1%}")
        print(f"| {variant} | {' | '.join(cells)} |")


if __name__ == "__main__":
    main()
