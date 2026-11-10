"""Draft a case record from a published theory of change, with an OpenAI vision model.

What it does, in plain terms: for one case it reads ``cases/<id>/source.json`` (which PDF,
which pages hold the figure, which pages hold the findings), turns the figure pages into
images, takes the text of the findings pages, and asks one model call to fill the case
schema (``schema.py``). The result is a **draft**, ``cases/<id>/case.draft.json``: a person
checks every box and link against the figure before it becomes ``case.json``.

``source.json`` looks like::

    {"file": "downloads/mup_final.pdf", "doc_url": "https://...", "retrieved": "2026-11-09",
     "figure_pages": [12], "text_pages": "40-62",
     "notes": "Figure 2 is the ToC; Table 5 rates each pathway."}

``file`` may be a PDF, a web page (HTML) or article XML. The figure is given either as
``figure_pages`` (PDF page numbers, as a PDF viewer counts them, not the printed ones) or
as ``figures`` (image files, relative to this folder). ``text_pages`` (``"3-9,40-62"``)
picks the findings pages of a PDF; without it the script keeps the passages that mention
the theory, its assumptions and the findings most, up to ``MAX_TEXT_CHARS``.

Spend: every call is logged to ``cases/_spend.jsonl``; the script refuses to start once
the total reaches ``BUDGET_USD`` (the owner's cap for building the dataset).

Run from the repo root:

    uv run --project backend --env-file backend/.env python -I \\
        scripts/evals/theory_of_change/extract.py <case_id> [--model gpt-6.1-sol]
"""

from __future__ import annotations

import os

# Dataset building calls OpenAI directly, whatever backend/.env selects.
os.environ["POLICY_ATLAS_MODEL_ROUTE"] = "openai-direct"

import argparse
import base64
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schema import Case  # noqa: E402

CASES = HERE / "cases"
SPEND = CASES / "_spend.jsonl"
BUDGET_USD = 10.0
DPI = 150
MAX_TEXT_CHARS = 60_000
#: Words that mark the passages worth sending when no findings pages are given.
KEYWORDS = ("theory of change", "logic model", "contribution", "assumption", "pathway",
            "conclusion", "finding", "evidence", "supported", "hold", "achieved", "outcome")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}

PROMPT = """\
You transcribe a published theory of change (ToC) into a fixed JSON record, for use as
ground truth when testing an AI tool. Accuracy matters more than completeness: never invent
a box, an arrow or a verdict. If something is unclear, say so in transcription.open_questions.

The images are the figure page(s). The text is the document's findings and conclusions.

Boxes and links
- One box per box drawn in the figure, in the source's own words (fix only line breaks).
- Layer: map the figure's columns or rows to input, activity, output, outcome_short,
  outcome_long, impact, vision, context. Use the source's own headings to decide.
- A column, row, band or panel title ("Inputs", "Intervention", "Mediating factors",
  "Impact", "Urban girls 15-19") with no arrow of its own only tells you the layer, or which
  panel a box is in: it is not a box, not a container and not a link end. If an arrow is
  drawn from or to a title, it is a link end: make it a container of the boxes under it,
  or a box if nothing sits under it.
- A container is a set of boxes that an arrow starts or ends at as one unit. It can be
  drawn as a frame, a brace, a bracket, or a shared connector line that several boxes feed
  into. Use one only when such an arrow exists; otherwise give the boxes no container.
  Label it with the frame's title, or describe it ("braces: savings, financial education").
- One link per arrow drawn. An arrow that starts or ends at a container links the
  container. Never add a link for an arrow that is not drawn: if the figure has no arrows
  at box level (columns only), leave links empty and say so in open_questions.
- Several diagrams: if the figures show one theory twice (an original and a revised or
  populated version), transcribe it once and take the verdicts from the populated one.
  If they show different diagrams (an overview plus one per group or strand), transcribe
  only the one the findings test most, and name the others in open_questions.
- confidence is how sure you are about the arrow: high (clear), medium (crowded or
  ambiguous), low (inferred, not drawn).
- Assumptions and risks: use those written in the figure or in the text, placed on the
  links they apply to, or between two layers when the source places them that way.

Verdicts (only where the source judges the evidence)
- Put a verdict on a link when the source judges that causal step; on an assumption when it
  judges the assumption; on a box only when it judges whether that result happened.
- raw = the source's own words; quote = a short quote that carries it; page = the page.
- scale: supports (holds, strong, achieved, claim met), partly (some, mixed, moderate,
  partially), insufficient (too early, no data, unclear, not enough evidence), against
  (does not hold, not leading, not met, evidence of no effect), not_assessed.
- studies: the studies the source names for that step (DOI if printed, else "Author year").
- conclusions: the overall verdict on the theory, the links or assumptions the source calls
  weakest and strongest (by id), its main conclusions close to its words, recommendations.

Key claims (the unit of scoring; never lose a finding)
- 5 to 12 causal claims that a good theory for this case must contain, in plain words
  ("Mentoring sessions build social assets", "Lower consumption reduces deaths"). Cover the
  main pathway end to end, the key assumptions, and any claim the source found weak.
- refs: the ids of the boxes, links or assumptions the claim covers. Leave empty when the
  claim is tested only on a panel, table or subgroup you did not transcribe.
- Every evidence finding in the source must land on a key claim, including findings on
  panels, tables or subgroups that are not in the transcribed diagram. If one claim has
  different results by subgroup or measure, say so in raw ("positive for older urban girls,
  none for younger") and choose the scale for the claim as a whole.
- where: the figure, table or section where the source tests it.
- Also keep verdicts on links, boxes and assumptions where they fit, as above.

Brief (what a person would know BEFORE drawing this theory)
- intended_change, population, place, time_horizon, intervention (with dosage), context:
  from the document's description of the intervention and its aims, not from the figure's
  outcome boxes. Do not list the theory's intermediate steps, and do not list the areas,
  strands or mechanisms the boxes name (say "academic and pastoral support", not the five
  topics it covers): the tool must find those itself.
- outcome_first: a short first message to the tool (2-4 sentences) that asks for a theory
  of change for the intended change, population and place, without naming the intervention.
- intervention_first: a short first message that names the intervention, population, place
  and intended change, and asks for its theory of change.

Meta: fill from the document and the notes. figure_pages are the page numbers given.
"""


def pages(spec: str) -> list[int]:
    """'3-5,9' -> [3, 4, 5, 9]."""
    out: list[int] = []
    for part in filter(None, spec.replace(" ", "").split(",")):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND.read_text().splitlines() if line)


def _data_url(path: Path) -> str:
    """An image file as a data URL; other formats (e.g. SVG) are rendered to PNG first."""
    import pymupdf

    if mime := IMAGE_TYPES.get(path.suffix.lower()):
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    with pymupdf.open(path) as doc:
        png = doc[0].get_pixmap(dpi=DPI).tobytes("png")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _best(chunks: list[str]) -> str:
    """The chunks that mention the keywords most, kept in document order, up to the cap."""
    def score(c: str) -> int:
        low = c.lower()
        return sum(low.count(k) for k in KEYWORDS)

    ranked = sorted(range(len(chunks)), key=lambda i: -score(chunks[i]))
    keep, size = set(), 0
    for i in ranked:
        if size + len(chunks[i]) > MAX_TEXT_CHARS:
            continue
        keep.add(i)
        size += len(chunks[i])
    return "\n".join(chunks[i] for i in sorted(keep))


def inputs(src: dict, root: Path) -> tuple[list[str], str]:
    """The figure as image data URLs, and the most useful text of the document."""
    import html
    import re

    import pymupdf

    path = root / src["file"]
    images = [_data_url(root / f) for f in src.get("figures", [])]
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as doc:
            images += [
                "data:image/png;base64,"
                + base64.b64encode(doc[p - 1].get_pixmap(dpi=DPI).tobytes("png")).decode()
                for p in src.get("figure_pages", [])
            ]
            wanted = pages(src.get("text_pages", "")) or range(1, len(doc) + 1)
            chunks = [f"\n--- page {p} ---\n{doc[p - 1].get_text()}"
                      for p in wanted if p <= len(doc)]
    else:  # HTML or XML: drop scripts, styles and tags; cut into ~3,000-character passages
        raw = path.read_text(errors="replace")
        raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        chunks = [text[i:i + 3000] for i in range(0, len(text), 3000)]
    if not images:
        raise SystemExit("No figure: give figure_pages (PDF) or figures (image files).")
    return images, _best(chunks)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--effort", default="medium")
    args = ap.parse_args()

    if (total := spent()) >= BUDGET_USD:
        sys.exit(f"Budget reached: {total:.2f} of {BUDGET_USD:.2f} USD spent.")
    case_dir = CASES / args.case_id
    src = json.loads((case_dir / "source.json").read_text())
    if missing := {"file", "doc_url", "retrieved"} - src.keys():
        sys.exit(f"source.json lacks {sorted(missing)}: provenance comes first.")
    source_sha = hashlib.sha256((HERE / src["file"]).read_bytes()).hexdigest()
    prompt_sha = hashlib.sha256(PROMPT.encode()).hexdigest()
    images, text = inputs(src, HERE)

    from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
    from policy_atlas.theory_of_change.cost import usd

    content = [
        {"type": "text", "text": f"Case id: {args.case_id}\nNotes: {src.get('notes', '')}\n"
         f"Figure: {src.get('figure_pages') or src.get('figures')}\n\nDOCUMENT TEXT:\n{text}"},
        *({"type": "image_url", "image_url": {"url": u, "detail": "high"}} for u in images),
    ]
    case, usage = parse_structured(
        resolve_openai_client(None, backend_name="toc_dataset"),
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": content}],
        response_format=Case,
        usage_event="toc_dataset.extract.usage",
        label="toc_dataset_extract",
        model=args.model,
        reasoning_effort=args.effort,
        prompt_cache="off",
        timeout_s=600.0,
        max_completion_tokens=32_000,
    )
    cost = usd(args.model, {"prompt": usage.prompt or 0, "cached": usage.cached or 0,
                            "completion": usage.completion or 0}) or 0.0
    with SPEND.open("a") as f:
        f.write(json.dumps({"date": dt.datetime.now().isoformat(timespec="seconds"),
                            "case": args.case_id, "model": args.model, "usd": round(cost, 4),
                            "source_sha256": source_sha, "prompt_sha256": prompt_sha,
                            "prompt": usage.prompt, "completion": usage.completion}) + "\n")
    case.transcription.method = (
        f"{args.model} draft from {src.get('figure_pages') or src.get('figures')}; "
        "not yet checked by hand"
    )
    case.transcription.date = dt.date.today().isoformat()
    case.transcription.source_sha256 = source_sha
    case.transcription.prompt_sha256 = prompt_sha
    case.meta.doc_url = src["doc_url"]
    case.meta.landing_url = src.get("landing_url", case.meta.landing_url)
    case.meta.figure_pages = src.get("figure_pages", [])
    (case_dir / "case.draft.json").write_text(case.model_dump_json(indent=1) + "\n")
    print(f"{args.case_id}: {len(case.boxes)} boxes, {len(case.links)} links; "
          f"{cost:.3f} USD (total {spent():.2f} of {BUDGET_USD:.2f})")


if __name__ == "__main__":
    main()
