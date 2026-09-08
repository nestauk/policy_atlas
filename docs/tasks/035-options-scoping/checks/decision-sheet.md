# Decision sheet — spec changes proposed by feasibility checks 6, 2, 3, 4, 5

Every proposal below is the owner's to accept, reject or edit. Nothing here is in the specs yet
(an earlier unilateral amendment pass was reverted, 2026-09-08). When a row is decided, the spec
is edited to the ruling, quoting the decision. Rows are grouped by the spec they would change.
"Rec." is the agent's recommendation only.

Legend for *Decision*: accept · reject · edit (say how) · defer.

## A — data-model.md

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| A1 | The **option is an addressable-unit kind**, so claims about an option (ambition tag, coverage patterns, constraint judgements, reasoned guesses, relation rationales) are ordinary annotations keyed `(option, type)`. Today annotations key on `(block, unit)` and unit ids change on regeneration; the option id does not. | § Atomic units; § Option entity | 6 F1 | accept | |
| A2 | **`intervention_mention` as a third finding kind** (the abstract profile): the shared reference vocabulary at mention grain plus `design_features`, `role` (evaluated · described · recommended · comparator · mentioned), `is_bundle`/`components`, an **adoptability** flag, a quote anchor; document-level `design_hint`, `names_no_intervention`. Joins `finding_reference_union`. Own fingerprint domain. | § Findings layer | 6 F2; 3 C3-3 | accept | |
| A3 | **Light profile = IOF subset + four fields** (`design_features`, `magnitude_as_reported` as number-and-unit only, `period`, `trial_or_registration_id`) writing `intervention_outcome_finding` under its own profile id, plus a document-level **`study_identity`** (registration id; programme or trial name matched name-first; protocol-only; reports-own-data). | § Findings layer | 2 C2-2, C2-1 | accept | |
| A4 | **Memo key for acquired snapshots drops `task_id`**; requirement resolution at **field grain within a schema** with the intervention-as-implemented as a match key. As built the memo is task-scoped and whole-record; rulings 35 and 48 depend on this in both directions. *Evidence search change → ADR.* | § Findings layer intro | 6 F3; 2 C2-2 | accept, own ADR | |
| A5 | **`text_basis` derived from the parse result**, not the fetch (a minimum-size or parse-success rule, or a third value `full_text_failed_parse`). Five of 21 read-set "full text" documents were failed parses of under 800 characters. *Evidence search change → ADR.* | § Corpus & snapshots | 2 C2-7 | accept, own ADR | |
| A6 | **`task_link`** record (source task · target task · kind · optional option id · created by/at): the input `inherit` reads in both directions; the option entity's child-task link is one row of it. | new § Links between tasks | 6 F6 | accept | |
| A7 | **`inherited_from_task_id`** on `task_source_snapshot`, not a new `origin` value. Classify and appraise rows are **copied as inherited assertions** when the classifier or rubric version matches, else re-run (closes the 🟡 in OS components § 0). | same | 6 F7 | accept | |
| A8 | **Document identity for counting** = DOI or normalised title plus year, resolved at `inherit` and `longlist`; one review present as two snapshots counts once. | § Option entity | 2 C2-5 | accept | |
| A9 | Relations gain **instance of** (or *part of* reused with a type): mentions cluster to class-grain options, deep findings to named implementations; a class option carries its named implementations beneath it. | § Option entity | 3 C3-1 | accept | ❓ |
| A10 | Lever types stored as **primary, secondary and runner-up** with the one-sentence reason (a runner-up was named for 18 of 29 and 27 of 32 options). | § Option entity | 3 C3-4 | accept | |
| A11 | Membership records carry an **assignment stability marker** (class options lost a third of members under paraphrase; named designs kept theirs) and admit **design feature not stated** as a third outcome, attaching to the parent class only (ruling 36 made concrete). | § Option entity | 3 C3-5; 2 C2-3 | accept | |

## B — execution-orchestration.md

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| B1 | Resolve the reading-budget seam: **`reading_scope`** parameter on `synthesise` — snapshots readable at full-text depth (the read set), at abstract depth (the option's mentioning documents), plus declared exceptions; chunks outside are not retrievable in that composition; omissions represented. Distinct from the data model's soft-prior rule for intent scoping. | § Vocabulary (the seam note) | 6 F4 | accept | |
| B2 | **Eligibility is a record**: the option's finding-grain membership, written by `longlist` in assign-only mode after extraction; ⟨assess⟩ composes that step between extract and synthesise. | same | 6 F4 | accept | |
| B3 | Record the measurement: **the rapid budget is a synthesis budget** — synthesise is 72 percent of a standard walk's compute on staging, extraction 17 percent of a deep walk; the latency lever is the terminus's section count, turn caps and reading scope. | same or plan-as-object § depth | 5 C5-1 | accept | |

## C — plan-as-object.md

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| C1 | The **evidence-scope constraint as the policy's third face**, compiling to `scope_filters` where a backend can express it and to a **deterministic set-aside** over abstract-profile columns after extract(abstract), before `longlist` — a status per document × constraint, counted on Sources, never support, never an option exclusion. It cannot act at the screen (relevance-only; runs before study geography is known). | § Source / evidence policy | 6 F5 | accept | |
| C2 | Name the **code-name collision**: the as-built `evidence_scope` table is the intent record; the constraint carries a different code name. | same | 6 F5 | accept | |
| C3 | **Typed user-context entries** under Assumptions & boundaries — *stated by you* / *planned by you*, verbatim `user_text`, date, decision-event provenance; versioned with the plan; carried by `inherit`; the entry's type is what decides whether it can lift a cap. | § What a plan contains | 6 F10 | accept | |
| C4 | A plan may compile to **more than one intent record** (baseline scope, longlist scope, one per variant, one per thin option's targeted acquire); coverage unions across scopes; membership keys on the task's document row. | same | 6 F12 | accept | |
| C5 | Record the measured depth numbers (standard walk median 15 min, p90 29; gate waits median 17 min, p90 2 h) and set the **per-option document cap as a plan setting with defaults 5 (rapid) and 8 (standard)**; state time-to-result as compute time and, separately, elapsed time including gates. | § Thoroughness | 5 C5-4, C5-5 | accept | |

## D — provenance-grounding.md (column-grounded blocks)

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| D1 | The block is produced in **two steps**: factor extraction from the evidence once (the two evidence legs judged from evidence and the stated target; one row per support factor with ids, quote, evidence basis), then **context fill** against that fixed list. A single prompt drifted its factor set and tied the evidence legs to context. | § Column-grounded blocks | 4 C4-1 | accept | |
| D2 | **Verify runs code-side rules** and records corrections as flags: planned → never met; retrieved at containing geography → met/not met only when *applies by nature*; dated → unknown; entry id must exist. Five of five model over-statements in the test were caught this way. | same | 4 C4-5 | accept | |
| D3 | The *retrieved* context cell carries **geography level and observation date**. | same | 6 F11; 4 C4-6 | accept | |
| D4 | The **causal-role leg defaults to Unknown**: *not met* requires a stated contradiction between evidence population or deliverer and the target, never an unstated feature. | same | 4 C4-4 | accept | |
| D5 | **Only dealbreakers cap** the support leg; helpful factors are shown, enter the conditions list when planned, and do not cap. Otherwise the verdict reads Unknown for every option unless the user states every factor. When no dealbreaker is named the leg reads "no necessary condition identified" and stays Unknown. | same; trust.md § transferability | 4 C4-2 | accept | ❓ |
| D6 | Whether a **local aggregate** (71 percent of residents live near a park) can set a factor met, or only a local resource observation can. | same | 4 C4-7 | lean: local aggregate is context only | ❓ |

## E — options-scoping components.md, capability.md, trust.md

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| E1 | Re-mark **extract(abstract) as EB modified**, with an **`all_screened_in`** select strategy that includes Non-evidence so the abstract profile runs over every screened-in document. | components row 10; EB components § 3, § 6 | 6 F2 | accept | |
| E2 | Screen row wording: evidence-scope constraints act at retrieval where expressible and as the set-aside after extract(abstract), **never at the screen**. | components row 3 | 6 F5 | accept | |
| E3 | ⟨assess⟩ composition gains **`longlist(assign, finding grain)`** after extract(light) and runs synthesise(profile) under a declared `reading_scope`. | components § compositions | 6 F4 | accept | |
| E4 | `longlist` declares an **assign-only mode**; the discovery ceiling becomes **`clamp(ceil(N/4), 8, 40)`** (the old formula was binding in the thin corpus). | components § 6 | 6 F4, F9; 3 C3-3 | accept | |
| E5 | Two guards on one-place-per-lever-type: a lever type whose options all have **zero evaluated mentions** earns a **gap message, not a place**; a place with a close runner-up lever or a near-equal rival is marked **contested** for the user to confirm. Relabelling moved four of five places in the thin corpus and seated a one-document unevaluated option. | components § 8; capability § shortlist | 3 C3-2 | accept | ❓ |
| E6 | A run-keyed **`shortlist_result`** record (places, reasons, who filled them, gap messages, warnings) for export. | components § 8 | 6 F15 | accept | |
| E7 | Scoping **select strategy stratifies on the abstract profile's evaluated role × outcome family**, reserves one review and one primary study, and uses text availability as a tiebreaker only (full-text-first picked process evaluations with no effects). | components § 9; EB components § 6 | 5 C5-2 | accept | |
| E8 | **Countable cells come from per-document extraction, never from reading alone** (one call over five texts missed contrary evidence extraction found). | components § 9–11 | 5 C5-3 | accept | |
| E9 | Wire the Evidence search's **quote vetter and claim-key dedup** for the light profile (17 percent of anchors failed unvetted; window repeats doubled one document's claims). | components § 10 | 2 C2-6 | accept | |
| E10 | The magnitude cell holds a **number with its unit only**; the source's own characterisation is a separate quoted field. | trust § effect cell | 2 C2-8 | accept | |
| E11 | **"How sure" as two numbers**: documents read, and independent own-data studies where identity is known; reviews are documents, never studies ("3 reviews, 0 independent primary studies read"). | trust § effect cell; capability § assessed evidence | 2 C2-1 | accept | ❓ |
| E12 | `synthesise(profile)` carries a **declared section budget** (the latency lever) and produces the transferability working in the two steps of D1. | components § 11 | 5 C5-1; 4 C4-1 | accept | |
| E13 | The factor step asks explicitly **what the evidence reported as blocking delivery** (it flagged no dealbreaker despite a governance block); a user may **add a condition** the evidence did not name, as a row typed *stated by you* with the evidence cell "not addressed by the evidence". | trust § transferability | 4 C4-3 | accept | |
| E14 | Ruling 47's "prior version in History" is a **derivation edge** from the child artefact to the scoping-pass block version plus a display convention (history is linear per artefact; an artefact lives in one task). | components § ⟨full run⟩ | 6 F8 | accept | |
| E15 | Ruling 41 stands **on one condition**: the child computes membership against the specified design via `group`'s fixed-target-list mode or `longlist(assign)`; record the condition. | components § ⟨full run⟩; EB components § 8 | 6 F9 | accept | |
| E16 | Record the measured rapid number against open question 3: about 25 minutes of compute for a one-option sense-check on today's synthesise. | capability § depths, § open decisions | 5 C5-1 | accept | |

## F — Evidence search components.md (mirrors)

| # | proposal | where | from | rec. | decision |
|---|---|---|---|---|---|
| F1 | § 0 inherit: `task_link` input; copy-or-rerun rule; `inherited_from_task_id`. | § 0 | 6 F6, F7 | accept with A6, A7 | |
| F2 | § 3 classify: Non-evidence stays excluded from select/extract except under the `all_screened_in` strategy. | § 3 | 6 F2 | accept with E1 | |
| F3 | § 6 select: the refined scoping strategy (E7) and `all_screened_in`. | § 6 | 5 C5-2; 6 F2 | accept with E7 | |
| F4 | § 7 extract: the two options-scoping profiles registered; pointer to the two ADR-wanting changes (A4, A5). | § 7 | 6 F3; 2 C2-7 | accept with A2–A5 | |
| F5 | § 8 group: **fixed-target-list mode** (discovery skipped; assignment against a supplied option list). | § 8 | 6 F9 | accept with E15 | |
| F6 | § 9 synthesise: the `reading_scope` parameter; the Evidence search's own compositions unchanged. | § 9 | 6 F4 | accept with B1 | |

## Also proposed, not spec

- A **Results** section in `feasibility-checks.md` summarising each check's outcome and what the
  owner still owes (factual; no design content). Decision: ____
- A **spec log entry** once the accepted rows are applied. Decision: ____
- Two **ADRs** for the Evidence search changes (A4 memo key; A5 `text_basis`). Decision: ____
