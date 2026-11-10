"""Merge the per-family fact tables and the lead's decisions into ``longlist.csv``.

Facts come from ``verified_*.csv`` (one per search family, written by the checking agents).
Decisions come from ``decisions.csv`` (written by hand: keep / reserve / drop / duplicate,
with a reason). A row with no decision gets a default, labelled ``default:`` so it is never
mistaken for a judgement. Prints the coverage of the kept set.

Run: python3 scripts/evals/theory_of_change/candidates/merge.py
"""

import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def default(row: dict) -> tuple[str, str]:
    if not row["verified"].startswith("yes"):
        return "unverified", "default: not checked against the document"
    if row["diagram_type"] in ("text-only", ""):
        return "drop", "default: no diagram"
    return "reserve", "default: checked, not chosen yet"


def main() -> None:
    decisions = {r["id"]: r for r in csv.DictReader((HERE / "decisions.csv").open())}
    rows = []
    for f in sorted(HERE.glob("verified_*.csv")):
        for r in csv.DictReader(f.open()):
            d = decisions.get(r["id"])
            r["decision"], r["reason"] = (d["decision"], d["reason"]) if d else default(r)
            rows.append({"family": f.stem.removeprefix("verified_"), **r})
    if unknown := set(decisions) - {r["id"] for r in rows}:
        raise SystemExit(f"decisions.csv names unknown ids: {sorted(unknown)}")
    # The same id from two families: keep the row that was checked against the document.
    best: dict[str, dict] = {}
    for r in rows:
        if r["id"] not in best or r["verified"].startswith("yes"):
            best[r["id"]] = r
    rows = list(best.values())

    order = {"keep": 0, "reserve": 1, "unverified": 2, "duplicate": 3, "drop": 4}
    rows.sort(key=lambda r: (order[r["decision"]], r["family"], r["id"]))
    with (HERE / "longlist.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    kept = [r for r in rows if r["decision"] == "keep"]
    print(f"{len(rows)} rows -> longlist.csv; decisions: {dict(Counter(r['decision'] for r in rows))}")
    for col in ("evidence_level", "timing", "family", "intervention_type"):
        print(f"kept by {col}: {dict(Counter(r[col] for r in kept))}")


if __name__ == "__main__":
    main()
