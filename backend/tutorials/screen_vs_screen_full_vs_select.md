# Screen, screen_full and select: what each stage decides

Three stages of the Evidence search pipeline look similar because each one narrows the set of
documents. They answer three different questions, on three different inputs, with three different
consequences. This note explains the difference. It accompanies `pipeline_walkthrough.ipynb`,
which runs all three on a small corpus.

## The three questions

### screen (stage 1): is this document about the question at all?

Runs on the title and abstract, before any full text exists. It is a relevance gate tuned for
recall: keep anything plausibly useful, and exclude only on positive grounds, such as a clearly
different subject, population or domain. The model is asked three times and the majority wins.
"Unsure" counts as kept, and a document with no abstract can only be excluded if all three
answers agree.

A document that fails here is gone for good. No later stage sees it.

### screen_full (stage 2): now that we have the full text, was stage 1 right to keep it?

Same question and same relevance gate, but on the fetched document, and only for documents that
were fetched. It exists because abstracts mislead: a paper whose abstract mentions heat pumps may
turn out to be about ventilation. It runs only when the plan opts in (standard and deep depths).

Stage 2 can confirm or demote, never rescue. Recall is won at stage 1 or not at all. A demoted
document is excluded exactly like a stage-1 exclusion. Documents without full text keep their
stage-1 verdict.

### select: of the relevant documents, which ones do we pay to read deeply?

Not a relevance question. Everything in the pool is already relevant. Select is a budget decision.
Extraction costs several model calls per document, so a plan at `deep` depth reads 25 documents,
and select chooses those 25 so that they:

- cover the characterisation themes evenly (a stratified pick with a breadth floor), rather than
  collapsing onto the top of one theme;
- prefer well-appraised and recent sources that have full text;
- honour the plan's hard rules: `must_include_ids` bypass the budget, `exclude_ids` leave the pool.

Non-evidence documents (press releases, announcements) are never selectable. The ranking within
each theme is deterministic by default; the plan can switch on an LLM reranker that scores
purpose-fit, but its scores only reorder, never exclude.

Nothing is excluded by select. Unselected documents stay screened-in, stay searchable by the
report writer, and can still be cited as chunk quotes. They simply do not get structured findings
extracted.

## Side by side

| | screen | screen_full | select |
|---|---|---|---|
| question | relevant? | still relevant on full text? | worth the deep read? |
| input | title + abstract | full text (first window) | the screened-in set, with themes, appraisals and tags |
| who decides | LLM, 3 reps, majority | LLM, 1 rep | deterministic stratified ranking (LLM rerank optional) |
| runs when | always | plan opts in (standard, deep) | plan opts in (standard, deep) |
| a "no" means | out of the corpus | out of the corpus | not extracted, but still citable |
| failure mode guarded | losing a relevant document | keeping an irrelevant one | reading only the top of one theme |
| result table | `source_screening_result` (stage 1) | `source_screening_result` (stage 2) | `selection_result` |

## In one sentence

The two screens shrink the corpus by relevance; select allocates the reading budget within it.

## What synthesis can cite

A natural misreading is "synthesis can cite anything that passed either screen_full or select".
The "or" is wrong, because select is not a gate at all: passing it is never what makes a document
citable.

The citable pool is every document whose **effective screen verdict is relevant** and which has
been **appraised**. Spelled out:

- A document with full text must have passed both screens. Stage 2 is demote-only, so its stage-2
  verdict is the effective one.
- A document without full text (fetch failed, or `screen_full` was not in the plan) only needs
  its stage-1 verdict. Its abstract chunks are the text that can be cited, labelled
  `abstract_only`.
- It must also have an appraisal row, which means its classification was an evidence type.
  Non-evidence and Unknown documents are screened in but uncitable.

Select then changes *how* a document can be cited, not *whether*:

| document | citable as a chunk quote | citable as a finding |
|---|---|---|
| screened in, appraised, selected | yes, with a ranking boost | yes, if extraction produced findings |
| screened in, appraised, not selected | yes, origin recorded as `unselected_screened` | no, nothing was extracted |
| screened in, Non-evidence or Unknown | no | no |
| screened out at either stage | no, its text is never searched | no |

The accurate sentence: synthesis can cite anything that passed screening and was appraised;
selection only decides which of those also carry structured findings, and which the writer sees
first.

## Where this shows up downstream

- The report writer retrieves over the **whole screened-in corpus**. The selection is only a soft
  ranking prior: chunks from selected documents are boosted, so the writer sees them first, but an
  unselected document's chunk can still be retrieved and cited. Every chunk citation records
  whether its document was `selected` or `unselected_screened`.
- Only selected documents are extracted, so only they can be cited as **finding** claims with
  verified quote anchors.
- Synthesis cites only appraised evidence, so Non-evidence and Unknown documents cannot be cited
  even though they are screened in.
- In the funnel read model, `relevant` is the citable pool, `selected` is the extracted subset, and
  `cited` is what the writer actually used.

## Code

| stage | entry function | module |
|---|---|---|
| screen, screen_full | `screen_sources` | `evidence_search/assess/screen.py` (prompt in `screen_prompt.py`) |
| select | `select_scope` | `evidence_search/corpus/select.py` (optional reranker in `ranking.py`) |
