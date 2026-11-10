"""Write ``cases/<id>/source.json`` for every kept candidate, from its longlist row.

The checking agents recorded each document's local file and the figure images they
rendered (``candidates/longlist.csv``). This turns that row into the input ``extract.py``
needs, and never overwrites a ``source.json`` that exists (a hand-edited one wins).
It prints the cases it could not prepare and why.

Run: python3 scripts/evals/theory_of_change/prepare.py [--decision keep]
"""

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOWNLOADS = HERE / "downloads"
MAX_FIGURES = 4


def find(ref: str) -> Path | None:
    """A file the agents named, wherever it ended up under downloads/."""
    ref = ref.strip()
    if not ref:
        return None
    name = Path(ref).name
    for cand in (HERE.parents[2] / ref, HERE / ref, DOWNLOADS / ref, DOWNLOADS / name):
        if cand.is_file():
            return cand
    hits = [p for p in DOWNLOADS.rglob(name) if p.is_file()]
    return hits[0] if hits else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decision", default="keep")
    args = ap.parse_args()
    rows = csv.DictReader((HERE / "candidates" / "longlist.csv").open())
    for r in (r for r in rows if r["decision"] == args.decision):
        out = HERE / "cases" / r["id"] / "source.json"
        if out.exists():
            continue
        # Drop bracketed notes before splitting: they can hold a ';' themselves.
        refs = {k: re.sub(r"\(.*?\)", "", r[k]).split(";") for k in ("local_file", "figure_png")}
        files = [f for f in map(find, refs["local_file"]) if f]
        figures = [f for f in map(find, refs["figure_png"]) if f][:MAX_FIGURES]
        docs = [f for f in files if f.suffix.lower() in (".pdf", ".html", ".htm", ".xml")]
        if not docs or not figures:
            print(f"SKIP {r['id']}: document {'found' if docs else 'missing'}, "
                  f"figures {'found' if figures else 'missing'}")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "file": str(docs[0].relative_to(HERE)),
            "doc_url": r["doc_url"],
            "landing_url": r["landing_url"],
            "retrieved": dt.date.today().isoformat(),
            "figures": [str(f.relative_to(HERE)) for f in figures],
            "notes": f"Figure(s): {r['figure_page']}. Verdict scale: {r['verdict_scale']}. "
                     f"Timing: {r['timing']}. {r['notes']} (Prepared from the longlist row; "
                     "figures rendered by the checking agent.)",
        }, indent=1) + "\n")
        print(f"ok   {r['id']}: {docs[0].name}, {len(figures)} figure(s)")


if __name__ == "__main__":
    main()
