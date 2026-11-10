# Task 060 notes

## 2026-11-09 Settings the experiments can change (code map)

Paths are under `backend/src/policy_atlas/` unless stated.

- **Models per step:** `model_routes.toml:110-128`. Tiers: fast = Luna, standard = Terra,
  frontier = Sol. Draft = Sol; discover, judge, summarise = Terra; merge, choose, report,
  verdict = Sol; pick, figures = Luna; import (reads an image or PDF) = Sol.
  Override for an eval, with no committed change: `POLICY_ATLAS_MODEL_ROUTE=<name>` plus
  `POLICY_ATLAS_MODEL_ROUTE_FILE=<overlay.toml>` with a `[routes.X.steps]` table
  (`core/model_routes.py:46-47,435`). Read once at start-up, so set before the server starts.
  Example: `archive_v1/_route.py` and `archive_v1/model_route_6x.toml`.
- **Search depth:** code constants, not settings. One search per link: 2 OpenAlex calls, 1
  Overton call, review and trial keyword variants (`evidence_search/sourcing/search_loop.py:118`).
  60 records kept (`runtime/toc_plan.py:84`). 10 documents picked and judged per link
  (`check/pick_prompt.py:27`, `check/selecting.py:83`). Links rated "not enough evidence" get one
  automatic second search (`runtime/runner.py:1267`). The manual "Find more evidence"
  (POST `/toc/check`, `mode: "find_more"`) doubles the results and judges 40 documents per link
  (`toc_plan.py:90-94`). No web search in the link check. The judge reads the title and abstract only.
  An eval can change constants only by patching them in the server process it starts.
- **Entry points through the API:** the Task Agent sets `entry_point` (`outcome_first`,
  `intervention_first`, `existing_theory`). An upload: POST `/tasks/{id}/toc/uploads` with a
  base64 PNG, JPEG or PDF (up to 10 MB).
- **Leakage controls:** a year window is supported (`published_after`, `published_before`; PATCH
  `/tasks/{id}/plan` before the draft). **Excluding one DOI or URL is not supported**; it would
  need new code.
- **Output:** GET `/toc` (boxes, links with verdict and evidence sentence, pathways, report with the
  theory verdict); GET `/toc/evidence` (documents per link with stance and quote). Cost is not on
  the API: it is in the `toc_check.cost` server log line.
- **Draft only:** an upload stops after the draft (`check_status = drafted`) until POST
  `/toc/check/full`. For the other entry points: POST `/toc/check/stop` once the draft lands.

## 2026-11-09 Existing datasets and methods (research/existing_datasets.md, local)

- No published dataset pairs ToC diagrams with evidence verdicts for each link. We build our own.
- No peer-reviewed study (2023–2026) scores an AI-drafted ToC against a published one; our
  evaluation is new ground.
- Closest reusable method: ReCITE (ACL 2026, CC BY 4.0, 292 text-to-causal-graph pairs). Match
  boxes with an LLM judge, then score link precision, recall and F1. This is the method v1 already uses.
  The best model in ReCITE reaches a link F1 of about 0.5, so v1's low link recall is not unusual.
- Seed list: Breuer et al. 2016 (62 public health papers with ToCs, 28 with a diagram).
- Rubrics for inclusion and for a judge: Davies 2012 (10 evaluability criteria), the Breuer
  checklist (CC BY). Mayne 2017 "robust ToC" criteria: open page 162 by hand.

## 2026-11-09 First extraction of the 29 kept cases

- All 29 drafted with gpt-6.1-sol (`extract.py`); all pass `schema.py`. Spend 2.82 USD of the
  10 USD cap (`cases/_spend.jsonl`), 0.04–0.16 USD a case.
- Verdicts land in different places: on links (housing and health 48, Housing First 17,
  advice services 9), on boxes (Prospera 19, LFFN 15, MUP 10), on assumptions (Agri-Tech 17,
  Building Choices 16). The evidence comparison must handle all three (plan § Step 3).
- Seven drafts carry no verdict at all: youth justice (Canada), CDC tobacco, Family Hubs,
  Nesta heat pump, Uniformed Youth Fund, plus near-zero for CAI (DESNZ) and Men's Sheds.
  Some are expected (level B), but Uniformed Youth Fund (two ratings per claim) and Men's Sheds
  (arrow thickness = papers) should have them: likely missed by the extraction, to check.
- Oversized drafts: CAI (DESNZ) 100 boxes and DCMS opportunity mission 76 boxes merge several
  diagrams; Building Choices 61 boxes with only 23 links. Candidates for splitting by level.

## 2026-11-09 Prompt v2: headings, panels, no invented links; short briefs

- Owner spot check (AGEP): column titles ("Intervention", "Mediating") and panel titles ("Urban girls 15-19") had become containers and link ends. Prompt now: headings set the layer only; a container needs an arrow drawn to or from it; never add a link that is not drawn (columns-only figures get no links); one theory per case (original + populated = one; overview + per-group panels = the main one, others named in open_questions).
- Rich brief: must not list the areas or mechanisms the boxes name (TASO's brief listed its five short-term outcomes).
- Re-run on AGEP, TASO, Men's Sheds, MUP: 0.35 USD. AGEP 30 → 15 boxes, title containers gone, but verdicts 22 → 8 (the colour-coded findings sit on the per-group panels, which are no longer transcribed). Men's Sheds: the model now declines to turn line thickness (number of papers) into verdicts, so 0 verdicts; its level A rating is doubtful.
- Short briefs: `cases/<id>/brief.json` (`ShortBrief` in schema.py), hand-written, with author, date and what was read. Names rule: a single organisation's scheme or role comes out (City College Norwich, HETS); a widely known intervention type stays (Men's Sheds, minimum unit pricing); setting type and country stay. Written for TASO, Men's Sheds, MUP.
- extract.py now copies landing_url from source.json (it was dropped before).

## 2026-11-09 Key claims; all 29 re-run (prompt v3)

- Owner ruling: one version only (no old/new drafts side by side); keep the verdicts through key claims and score on them.
- Schema: `Case.key_claims` (`KeyClaim`: claim, refs to box/link/assumption ids, where, verdict). Prompt: 5-12 claims per case; every finding must land on a claim, including findings on panels, tables or subgroups not transcribed as boxes (refs may then be empty).
- Re-run of all 29: 3.41 USD. Verdicts on boxes, links and assumptions 384 → 382 in total, plus 303 key-claim verdicts. Big drops on single elements are covered by claims (AGEP 22 → 11 on elements, 12/12 claims with verdicts; advice services 9 → 2, 10/10 claims).
- Cases that shrank because they had merged several diagrams: CAI 100 → 49 boxes, DCMS 76 → 38, housing and health 52 → 24, Agri-Tech 47 → 21, MapSan 44 → 22, EU Regio 30 → 4 (Figure 4, the populated 4-step chain with a verdict per arrow, as the checking agent advised).
- The "headings are never link ends" rule went too far: arrows drawn from a heading were dropped (Youth Justice strands, Uniformed Youth Fund "Mechanisms of change"). Prompt v3: a title with an arrow of its own becomes a container or a box. Re-ran those two only (0.21 USD); the other 27 drafts carry the v2 prompt sha. Youth Justice also had no findings text (only Appendix A was downloaded): p5 (findings) and p6 (conclusions) were added, joined with p8 into one file; now 12/12 claims with verdicts.
- Spend 6.79 USD of the 10 USD cap.
- Known instability: the same source words can map to a different scale between runs (MUP consumption → harms: supports, then partly). Hand check of key-claim verdicts is needed before scoring.
- Owner spot check (AGEP): the brace and bracket arrows to the outcomes were missing (the container rule said "frame"). Prompt v4: a container can be a frame, a brace, a bracket or a shared connector line. Re-ran the five cases whose open questions named the problem (AGEP, CDC tobacco, Youth Justice, Tackling Loneliness, Building Choices): 0.62 USD; AGEP now matches Figure 1 (14 links). Spend 7.41 USD.
- Shared figure gallery for the team (Claude artifact, private until shared): https://claude.ai/artifact/S3myVVPbeW4xbg25UcMRgD. Metadata from longlist.csv; the model's meta (year, organisation, evidence level) is weaker: it rated most cases B because it had no rubric.
