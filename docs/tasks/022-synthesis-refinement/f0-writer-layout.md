# F0 — `synthesise_section_v7` message/prefix layout spec (lead-pinned)

Pinned before F1–F3 per the plan (adversarial finding 8): the builders in
`synthesis_backend.py` implement THIS layout mechanically; the v7 prompt text
itself lands at Phase G. Provider-neutral: relies only on exact append-only
token prefixes (OpenAI automatic caching + Bedrock `cachePoint` both key on
prefix; no `prompt_cache_key`-class API surface).

## Section-loop conversation (`build_section_messages`)

Order is normative; every block is serialized with `sort_keys=True`,
`ensure_ascii=False` (unchanged determinism rules).

1. **System — stable per run**: `SECTION_SYSTEM_PROMPT` (v7). No run- or
   section-varying content, no counts, no dates.
2. **User — RUN block, stable across every section of one run**:
   `SECTION_RUN_TEMPLATE.format(run_json=…)` where `run_json` carries exactly:
   `intent`, `substrate` (characterisation + grouping summaries, slimmed per
   the § DTO spec), `corpus`, `available_tools`, `available_claim_types`.
   Byte-identical for all sections and all turns of a run — this is the
   cross-section shared prefix.
3. **User — SECTION block, fixed per section from turn 1**:
   `SECTION_TASK_TEMPLATE.format(section_json=…)` where `section_json` carries
   exactly: `section` (title / focus / group_ids), the section's member
   findings + `computed_spread`, and the rolling `ledger` **as it stood when
   the section opened** (the ledger is per-section input, never mutated
   mid-section — already true today).
4. **Tool exchange pairs** — assistant tool-call + tool result, appended in
   execution order with stable synthetic call ids (unchanged). Within a
   section the conversation only ever APPENDS after block 3.
5. **Final-turn user message** (`force_emit`) or **repair user message** —
   always last, never inserted.

Blocks 1+2 are the run-stable prefix (cross-section cache); blocks 1–3 are the
section-stable prefix (intra-section cache across turns). Nothing above block
4 may vary between turns of one section; nothing above block 3 may vary
between sections of one run.

## Repair micro-call (`build_section_repair_messages` — F2)

The full-transcript resend is GONE. The repair call is:

1. System — the same v7 `SECTION_SYSTEM_PROMPT` (same versioned surface).
2. User — the RUN block (byte-identical to the loop's block 2 — reuses the
   cached prefix).
3. User — `SECTION_REPAIR_TEMPLATE.format(repair_json=…)` where `repair_json`
   carries exactly, per failing claim: `claim_id`, `failure_reason`, the
   `replacement_span` plus adjacent prose context (the paragraph the span sits
   in), and `dependencies` — the records the claim's type actually depends on:
   cited chunk records for chunk/finding claims; the computed/lookup records
   (spread tables, coverage records, theme/group records) for pattern, theme
   and gap claims. Id-keyed data, fenced as data.

Replacements carry the failing claim's id (`claim_id`) and validate against
the failing set (item 11). Interface shaped so a future re-gather repair can
add tool turns after block 3 without changing blocks 1–2.

## Key-findings call

Unchanged two-message shape, but its seed is filtered to chunks cited by
surviving claims (rider 16) and uses the slimmed ledger records (§ DTO spec).

## § DTO spec (prompt-facing slimming — F4)

- Prompt-side theme/group records carry `id · label · description · size ·
  spread · residual counts` — NEVER membership UUID lists.
- The ordinary rolling-ledger record slims to `claim id · type · text`; the
  evidence-bearing key-findings ledger keeps its evidence payload (separate
  record type).
- Internal (non-prompt) consumers keep the full records — the split is at the
  seed/prompt boundary, not in storage.
