# 018 → eval-workstream handoff (pointers, not content)

> One-stop re-grounding index for the eval slice's design conversation.
> Everything here lives elsewhere; this file only says where and why it
> matters. Written at Phase C exit (2026-07-11).

## The loop protocol that survived contact (→ the eval-slice convention)

`verification.md § Loop protocol notes` — parallel-by-default with
same-project serialization (event-log sequence contention), one suite runner
per test DB, cheap probe classes (planner/proposal single bounded calls)
outside the counted replay budget, version-bump-per-prompt-change
(fingerprints hash version strings, not text), bounded rounds with the
contingent-judge escape hatch, batched user taste verdicts at pause points.

## The v1 replay set (→ grows to the 50–200-case paired set)

- Pinned substrates: `91d2d684` (mission intent) + `e8ac8418` (finance
  intent); pins in `docs/verification/private/018/drivers/replay.py`.
- Baseline-1 records: `docs/verification/private/018/baseline-1/`.
- All C-loop arms + exports: `docs/verification/private/018/c-loop/`
  (findings per extraction arm, artefact blocks per writer arm, section
  lists per proposal arm, classify A/Bs incl. the xhigh-uncapped study).
- Probe drivers (generalise into harness fixtures): `replay.py`,
  `export_findings.py`, `export_artefact.py`, `classify_ab.py`
  (direct-backend A/B, no DB writes — the substrate-safe pattern),
  `sections_probe.py` (proposal-only unit).

## Intent diversity

- The 7-category real-question taxonomy: product-internal, held outside the
  repo (owner / lead notes). C3 used one real question per category —
  the pins + per-category composition-adequacy verdicts are in
  `verification.md § C3 taxonomy pins`.
- Owner capability posture for stats/opinions shapes: deferred.md
  § Capabilities mapping (EB neither refuses nor pretends).

## Named eval-gated items this slice minted or sharpened

(all in `docs/deferred.md` unless noted)

- **Junk-judge calibration** — extract_junk_judge_v1 shipped conservative
  (flag only clear cases); precision/recall on reference sets is eval work.
- **EB report-shape boundary vs future capabilities** — § EB report-shape
  boundary; judge composition across the 7 shapes with this boundary.
- **Two-stage facet grouping** (owner note riding § Large-corpus grouping).
- **Future-target rule collateral** — modelled BAU-scenario projections
  dropped as aspiration (verification.md knowledge candidates; watch item).
- **Unspanned-flag calibration** — writer under-anchoring, not judge
  over-flagging; claim-coverage behaviour is eval territory
  (verification.md § Unspanned-flag calibration).
- **Multi-read vs cache economics** — judge cost changes on the
  cache-discounted curve, not raw tokens; D1 billing adjudicates section_v5
  (verification.md § cost riders).
- **Prompt-registry / datasets tooling** — assessed at A2(e), parked for the
  eval slice (plan rev 3).
- **classify effort** — high pinned on A/B evidence; xhigh-uncapped study
  archived (`c-loop/classify-xhigh-uncapped.txt`); effort×cap validated
  together per surface is the transferable rule.

## Prompting doctrine (promote out of this task folder at step 8)

`prompting-research-notes.md` — the 12 family-general rules, mini-tier
adjustments, provider quarantine, and the loop method (conflict audit,
fresh-minimal on family swap, numeric bounds, motivation-bearing rules) —
now validated by this slice's rounds. Step-8 knowledge candidate: author the
durable doctrine doc (incl. agent-loop conventions) in docs/specs/system/ or
docs/knowledge/.
