# ADR 0013 — The mandatory EB spine (every run fetches, ingests and synthesises)

**Status:** Accepted — 2026-07-09 (Shabeer Rauf; task 016 contract rev 2.2,
amended 2.3–2.6 + plan rev 2). The round-by-round decision trail lives in the
task 016 contract's revision history (revs 1–2.6: five user gate calls, the
substrate-fork resolution, and two Codex adversarial reviews — contract-stage
10 findings/8 adopted, plan-stage 12/12 adopted).

## Context

Through task 015 the chain's composition was implicit: specs described a
"rapid chain" and a "deep profile", the 015 smoke deliberately ran minus its
`ingest` leg (live fetch didn't exist), and synthesise refused an envelope-only
corpus (`no_groundable_substrate`) — a refusal the 015 smoke actually hit. The
demo build (2026-07-09, throwaway) surfaced the product question: what is the
minimum every evidence-base run owes the user? With 016 landing live fetch,
the orchestrator slice needs one authoritative chain-shape rule to compile
against, and the "what if fetch fails" edge needs an honest answer rather than
a structural refusal.

## Decisions

1. **The mandatory spine: every EB run executes acquire(`search`) → screen →
   classify → appraise → ingest(fetch) → synthesise.** Synthesise is the
   terminus that mints the run's artefact (ADR 0009); ingest is now on the
   spine because a run that never even attempts full text cannot honestly
   claim to have read the evidence. Everything else — characterise · select ·
   extract · group · stage-2 screen — is **orchestrator-discretionary**,
   chosen per the user's depth-gradation preference (the tool-wide
   depth/time-budget seam allocates; per-depth fetch budgets are a recorded
   lever of that seam, not hard-wired in 016).

2. **Mandatory ingest is a mandatory ATTEMPT, never a substrate guarantee.**
   Live fetching fails per document (paywalls, bot-blocks, dead links) and can
   fail for an entire corpus. What the spine guarantees is that the attempt
   was made and every outcome is reason-coded on the record.

3. **The failure path is substrate, not silence (components §4 enacted in
   full).** A document whose fetch fails is still ingested on the text in
   hand — its envelope abstract, already snapshotted/chunked/embedded at
   acquire — and joins grounded retrieval as labelled substrate:
   `text_basis: abstract_only` rides every citation into it, through both
   synthesis loaders (claim loader and `search_chunks` retrieval scope), the
   writer's records and the grounding judge's envelope. An all-fetch-failed
   corpus still synthesises, visibly abstract-labelled. This is flag-not-drop
   at the synthesis surface: a paywalled RCT's abstract is real, labelled
   evidence — never silently invisible.

4. **`no_groundable_substrate` narrows to its true meaning.** With the spine
   mandatory and the failure path substrate-bearing, synthesise's structural
   refusal fires only for a genuinely empty screened-in corpus — the
   miscomposition/empty backstop, kept fail-closed.

5. **Envelope-basis synthesis absent ingest is not a product mode.** The
   demo's quick-run-over-abstracts shape is served honestly by the spine: the
   fetch attempt always runs; what varies by depth is budget, not whether the
   product tried to read.

## Rejected

- **Option B (widen synthesise's gate so rapid runs skip fetch and ground on
  envelope chunks):** rejected by the user at the contract gate — depth
  gradations tune budgets, not whether ingest happens; skipping fetch
  entirely would make "we read the evidence" depth-dependent in kind rather
  than degree.
- **Spec-§9-literal with synthesise untouched (the original Option A
  wording):** refuted by the plan-stage evidence — it promised
  "fetched-text substrate in every composed run", which live fetch cannot
  guarantee; superseded by decisions 2–3 (attempt + labelled failure path).
- **Duplicate abstract-basis full-text snapshots for failed fetches:** the
  envelope snapshot IS the text in hand, already chunked and embedded;
  duplicating it into `full_text` rows adds write volume and a second source
  of truth for the same bytes.

## Consequences

- The orchestrator slice compiles plans against one authoritative chain rule;
  the components.md opening chain table, components §9 and capability.md carry
  the same statement (016 flow-back — two stale chain sources were found and
  both are updated).
- The 015 live-check's minus-`ingest` smoke deviation closes with 016's
  mandatory-spine smoke.
- Stage-2 screen remains full-text-only and orchestrator-discretionary;
  abstract-only documents are honestly `skipped_no_fulltext` there.
- Wall-clock: every run now pays a fetch/ingest leg; bounding it per depth is
  the recorded per-depth-fetch-budget lever on the tool-wide depth seam.
