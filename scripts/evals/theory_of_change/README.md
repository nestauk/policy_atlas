# Theory of change evaluation dataset (task 060)

A set of published theories of change (ToCs), each turned into one record, used to test
Policy Atlas's theory-of-change capability. The plan is in
`docs/tasks/060-toc-evals/plan.md`; decisions and results are in `notes.md` there.

| Path | What it is |
|---|---|
| `candidates/` | The wide-net longlist and the per-document fact tables used to choose cases |
| `cases/<id>/source.json` | Where the case comes from: the PDF, the figure pages, the findings pages |
| `cases/<id>/case.draft.json` | The model's first transcription (not yet checked) |
| `cases/<id>/case.json` | The checked record: the ground truth |
| `cases/_spend.jsonl` | Every model call made to build the dataset, with its cost (cap: 10 USD) |
| `schema.py` | The record format; `python schema.py` checks every case file |
| `extract.py` | Makes `case.draft.json` from `source.json` with one vision-model call |
| `prepare.py` | Writes `source.json` for every kept candidate from its longlist row |
| `candidates/merge.py` | Joins the fact tables (`verified_*.csv`) and the decisions (`decisions.csv`) into `longlist.csv` |
| `review.py` | The review website: `python3 scripts/evals/theory_of_change/review.py`, then open http://127.0.0.1:8765 |
| `downloads/` | Source PDFs and rendered figure pages (local only, not in git) |
| `archive_v1/` | The first pack (4 ToCs) and its scripts, kept for reuse |

## Add a case

1. Put the PDF in `downloads/` and write `cases/<id>/source.json` (see `extract.py`).
2. `uv run --project backend --env-file backend/.env python -I scripts/evals/theory_of_change/extract.py <id>`
   (from the repo root; about 0.10 USD a case).
3. Check every box, link and verdict against the figure. Fix the draft, note what you
   changed in `transcription.open_questions`, set `checked_by`, and save it as `case.json`.
4. `uv run --project backend python scripts/evals/theory_of_change/schema.py`.

## Provenance: every fact can be traced back

| Step | Where it is recorded |
|---|---|
| Why the document was found and chosen | `candidates/longlist.csv`: its row (same `id` as the case), with the decision and the reason |
| Which document, exactly | `cases/<id>/source.json`: URL, retrieval date, local file, figure and findings pages (PDF page numbers) |
| Which bytes were read | `source_sha256` in the record and in `_spend.jsonl`: the checksum of the PDF. If a re-download gives a different checksum, the publisher changed the file |
| How the draft was made | `transcription.method` (model, pages), `prompt_sha256` (the prompt version), `_spend.jsonl` (cost) |
| What a person changed | `case.draft.json` and `case.json` are both committed, so `diff` shows every hand correction; `checked_by` says who |
| Where each verdict comes from | each verdict's `raw` words, `quote` and `page` |

No PDF is committed. `source.json` keeps the URL so anyone can download it again.
