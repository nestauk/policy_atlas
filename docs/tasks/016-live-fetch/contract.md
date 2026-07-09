# Task contract: 016-live-fetch

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 1) — awaiting contract approval.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: expected
> (substrate decision, if adopted).
>
> **Revision history:**
> - **rev 1** (2026-07-09): initial draft. Sequencing context: third
>   slice of the live-demo path (014 LLM screen+classify MERGED →
>   015 live search MERGED → **016 live fetch/ingest** → 017 demo
>   dress-rehearsal → eval slice). Grounded on: `docs/deferred.md`
>   § Full-text ingestion (the pre-registered 008 requirements ledger),
>   `demo/RETRO.md` §4 on branch `demo-live-run` (real fetch statistics
>   from the 2026-07-09 demo build), the as-built
>   `ingest_full_text.py` seam, and the 015 transport precedents
>   (contract decisions 1 · 3 · 7 · 9).

## Goal

Make full-text ingestion **live**: a hardened live `DocumentFetcher`
behind the unchanged 008 seam, so the EB chain fetches real full text
for screened-in sources instead of replaying fixtures — the last
missing leg of the live chain (user, 2026-07-05: "the product cannot
function as intended without live fetching"; the deferred.md entry is
*sequencing*, not scoping-out).

Two things land together:

1. **The live fetcher**, carrying every pre-registered requirement
   from `docs/deferred.md` § Full-text ingestion so none is
   rediscovered in production (decisions 1–8, 10–11).
2. **The substrate decision** (decision 9 — the one real design fork):
   as-built, a no-reference synthesise run over a corpus with zero
   full-text-ingested documents refuses with `no_groundable_substrate`
   (`synthesise.py:2541`; the 015 chain smoke hit this). The demo
   validated quick-run synthesis over titles+abstracts as a product
   experience ("headline evidence base — from titles and abstracts",
   `demo/RETRO.md` §4). This contract pins how every profile mints an
   honestly-labelled artefact.

Everything downstream of the seam already exists and is reused: the
URL cascade (`candidate_urls`), per-URL attempt accounting, the closed
reason vocabulary, parse → segment → embed, `text_basis` honesty
labels, flag-not-drop for unfetchable sources.

## Deliverable

PR landing:

- Live fetch module: a `LiveDocumentFetcher` (`mode="live"`) in a
  **new module** — `ingest_full_text.py` stays free of HTTP imports
  (decision 1).
- The hardening set: SSRF/redirect policy · timeouts · size caps +
  bounded buffering · per-host politeness · bounded-concurrency
  prefetch · retry/backoff · magic-byte sniffing · charset handling ·
  per-link exception isolation (decisions 3–6).
- Bounded recall aids: landing-page PDF-link discovery + DOI-URL
  cascade fallback · paywall signal ladder + OA cross-check
  (decisions 7–8).
- The substrate decision as adopted at the gate (decision 9), with
  its components §9 spec flow-back + `log.md` entry and an ADR.
- Tests (transport-stubbed, zero-egress; SSRF guard unit tests) +
  `verification.md` with the pinned live check (decision 12).
- `deferred.md` + knowledge updates (discharged entries marked; new
  seams recorded).

## Read first

- [EB components §4 — full-text ingestion](../../specs/capabilities/evidence-base/components.md)
  (gated by screen, built for all screened-in; flag-not-drop;
  `text_basis`; fetch is mechanical execution of the governed
  `search` — telemetry plane, not per-document audit events)
- [EB components §9 — synthesise](../../specs/capabilities/evidence-base/components.md)
  (the substrate-conditional flow; the envelope-only refusal this
  slice resolves)
- [deferred.md § Full-text ingestion](../../deferred.md) — the
  pre-registered requirements ledger this contract enacts
- [008 contract](../008-full-text/contract.md) — the seam design and
  the closed failure-reason vocabulary
- `demo/RETRO.md` §4 (branch `demo-live-run`) — the real numbers: one
  deep run = 222 fetch attempts → 81 ingested, ~39 fetch_failed +
  22 parse_failed; paywalls (Lancet/Elsevier); empty bodies behind DOI
  redirects; 10-way parallel prefetch + serial ingest worked well
- `demo/server/fetcher.py` (branch `demo-live-run`) — the throwaway
  demo fetcher: evidence for shape (streaming size cap, magic-byte
  sniff, cache), explicitly NOT the hardened seam (no SSRF policy, no
  politeness — its own docstring says so)
- As-built: `ingest_full_text.py` (the seam, `candidate_urls`, the
  attempt loop, reason vocabulary), `acquire.py` envelope chunking
  (abstracts are chunked + embedded at acquire — decision 9's
  substrate already exists), `synthesise.py` corpus profile +
  substrate gating
- 015 contract decisions 1 (httpx posture) · 3 (timeouts) · 7 (retry
  set) · 9 (the "no provider URL is ever fetched" rule this slice
  deliberately opens, with guards)

## Scope / Out of scope

**In:**

- New live-fetch module + its tests.
- `ingest_full_text.py`: only what wiring requires (e.g. growing the
  code-enforced `FAILURE_REASONS` — zero-schema by design) and the
  in-run prefetch hook (decision 5) if the plan routes it here.
- `skeleton.py` / harness wiring: the live fetcher rides the existing
  one live switch (decision 2).
- `synthesise.py` substrate gate + components §9 flow-back (decision
  9, if adopted).
- `deferred.md`, knowledge docs, verification evidence.

**Out (stay deferred — `docs/deferred.md`):**

- docling / ML-layout parse escalation; OCR for `no_text_layer`;
  pymupdf-layout (licence-blocked).
- Multi-PDF Overton assembly (`grouped_pdf_ids_in_result`); primary
  `pdf_url` only, as-built.
- Cross-run / cross-project fetch caching and snapshot reuse;
  concurrent-run write guard (web-app slice).
- The designed component-progress protocol (RETRO §4 liveness gap) —
  recorded seam; this slice ships log-line telemetry only.
- Fixture-corpus relocation — triggered only "when the live fetcher
  takes over as default"; in this slice the fixture stays the
  default, so the trigger has not fired.
- Time-budget parser-tier selection; chunk-volume bias controls at
  retrieve.

## Decisions

1. **Live fetcher is a new implementation behind the unchanged seam.**
   `DocumentFetcher` (protocol), `FetchResult`, `candidate_urls`, the
   attempt loop, reason vocabulary, parse/segment/embed are all
   reused. The live class lives in a **new module** so
   `ingest_full_text.py` stays free of HTTP imports; the 008
   zero-egress guard extends to assert the ingest module never
   imports the live module (the 015 decision-1 pattern exactly).
   Transport is a **sync `httpx.Client`** (already a declared
   dependency, 015 rev 3.13): one pooled client, explicit timeout
   config, our retry semantics on top — never a library retry layer.
   **No new dependencies.**

2. **Egress switch: the skeleton's one live flag.** A live run uses
   the live fetcher; the suite and all library defaults stay
   fixture-backed and egress-free (`make verify` unchanged). No
   per-surface toggles. **No API keys exist on this surface** (public
   document URLs) — the 015 key-hygiene machinery is n/a, but a test
   asserts no `Authorization`/cookie state is ever attached to
   document fetches (we fetch as an anonymous public client, always).

3. **SSRF posture — the deliberate opening of 015's "no provider URL
   is ever fetched" rule, with structural guards.** The fetched URL
   universe is exactly: `candidate_urls()` from the source's own
   envelope metadata, plus decision 7's discovered links, plus the
   DOI fallback. Guards, all test-pinned: scheme allowlist
   (`http`/`https` only); the resolved target IP is checked before
   connecting and **private / loopback / link-local / metadata ranges
   are refused**; redirects are followed to a plan-pinned hop cap
   with **every hop re-validated** (scheme + resolved IP); a refused
   URL is a per-URL reason-coded failure (`blocked` joins the
   code-enforced `FAILURE_REASONS` — no migration), never a crash.
   URLs are fetched verbatim from metadata — never rewritten,
   never templated.

4. **Timeouts, size caps, bounded buffering.** Every request carries
   an explicit connect+read timeout (constant plan-pinned; 30 s
   recorder/demo precedent). Byte cap enforced against BOTH
   `Content-Length` and the streamed body (plan-pinned; 25 MB demo
   precedent; existing `too_large` reason). **Total in-flight
   buffered bytes during prefetch are capped** (plan-pinned;
   backpressure, not failure) — the pre-registered OOM control: 24
   fixture docs were fine, a live run holding N × 25 MB bodies
   concurrently is not.

5. **Concurrency + politeness.** Bounded parallel prefetch feeding
   serial parse/ingest (the RETRO-validated shape: 10-way prefetch +
   serial cache-hit ingest). Plan-pinned: global concurrency cap,
   **per-host concurrency cap and per-host minimum interval**
   (politeness — publisher hosts ban abusers; the Overton-limiter
   lesson generalised). One retry on transient failures (timeout ·
   429 · 500/502/503/504 — the 015 decision-7 set) with backoff, then
   a reason-coded failure. **Per-link exception isolation**: any raise
   inside a fetch becomes a reason-coded `FetchResult` — fail-loud is
   correct fixture-world and wrong live (pre-registered); the
   component itself never fails because documents failed. An in-run
   URL cache dedups repeat URLs within one run (demo-validated);
   cross-run caching stays deferred.

6. **Content-type by magic bytes first, headers second; explicit
   charset handling.** `%PDF` magic wins over any header (a PDF served
   as `application/octet-stream` must never fall through to the
   plain-text parser — pre-registered); HTML detected by header or
   body sniff (demo shape). HTML bytes pass to trafilatura undecoded
   (it handles declared charsets); the UTF-8-replace decode applies
   only to the plain-text path. Unit tests pin every classification
   branch.

7. **Bounded recall aids: landing-page PDF discovery + DOI fallback.**
   RETRO evidence: empty bodies and landing pages behind DOI
   redirects are a top live failure. (a) When a fetched body is HTML
   on a URL the cascade expected to be a document, parse it for
   `<meta name="citation_pdf_url">` (the scholarly standard) and
   obvious PDF anchors; **at most one discovered link** is followed
   per landing page, SSRF-validated (decision 3), recorded in the
   existing per-URL attempts trail. (b) `candidate_urls` gains a
   final **`https://doi.org/<doi>` fallback** when the envelope
   carries a DOI and it is not already present. Both are
   deterministic mechanics, not new judgment surfaces.

8. **Paywall signal ladder, bounded; OA cross-check.** Kept modest:
   the HTTP-status map (401/403 → `paywall`, as-built) + a
   plan-pinned marker sniff for login/consent walls on landing HTML +
   an **OA cross-check** using envelope metadata already in hand
   (OpenAlex `open_access`): a closed-access doc that failed fetch
   refines `not_found`-ish outcomes toward `paywall`; an
   allegedly-OA doc that hit `paywall` logs the inconsistency (a
   future eval signal). Flag-not-drop unchanged: paywalled sources
   stay in the corpus on their envelope basis, `text_basis`
   labelled — nothing is dropped for being unfetchable.

9. **Substrate decision (the design fork — user call at this gate).**
   As-built: `synthesise` refuses (`no_groundable_substrate`) when no
   references resolve AND zero docs are full-text-ingested; chunk
   claims require ≥1 ingested doc. The abstracts are already frozen,
   embedded chunks (acquire's envelope path), so the substrate for
   envelope-basis synthesis exists — the refusal is a gating choice,
   not a data absence. **Options:**
   - **A — spec-§9-literal**: every profile that ends in synthesise
     includes live fetch+ingest; synthesise untouched. Cost: egress +
     minutes of wall-clock on every rapid run (RETRO: fetch+ingest
     dominates a quick run's tail), contradicting the demo-validated
     quick shape.
   - **B — widen the gate (recommended)**: appraised **envelope
     chunks** become groundable substrate — chunk claims may cite
     abstract chunks, each citation carrying `text_basis`
     (`abstract_only`) so grounding and readers see which text a
     claim rests on; the refusal narrows to a corpus with *no
     appraised chunks at all*. Honest by labelling (the spec's
     existing `text_basis` discipline extended to citations), demo-
     validated as the product's quick shape, zero egress for rapid.
     Requires components §9 flow-back + ADR. Whether a given plan
     runs ingest stays **plan composition** (the tool-wide
     depth/time-budget seam) — 016 hard-wires no chain shape.

10. **Telemetry: the fetch is mechanical execution of the governed
    `search`** (spec) — structured log lines per attempt (as-built
    pattern) + **run-record summary counts** (attempted · ok ·
    per-reason failures · parse failures · bytes fetched · wall-clock),
    no per-document audit events. The RETRO user-grade
    component-progress protocol stays a recorded seam.

11. **Stage-2 screen windowing efficiency rider (small, pre-registered
    trigger).** The 014 review deferred `_load_stage2_docs` loading
    every chunk "when 015/016 lands the live corpus scale" — that is
    now. In-scope as a bounded fix (load only the needed window's
    chunks); no behaviour change, test-pinned. If the plan finds it
    non-trivial, it drops back to deferred with a note — it must not
    grow this slice.

12. **Live-check scope pin** (contract-time, per failure-log
    2026-07-08): changed surfaces + one cheap full-chain smoke —
    (a) one live fetch/ingest run over a real screened-in scope
    (~30–60 docs): outcome distribution recorded against the RETRO §4
    baseline (~36% ingested; observed counts, not pinned values),
    politeness observed (per-host spacing visible in logs), per-link
    failures never fail the component, bounded memory (buffering cap
    respected); (b) **the §9 rapid-profile chain smoke WITH the
    ingest leg** — acquire → screen → classify → appraise → ingest →
    characterise → synthesise over a live-acquired corpus, synthesise
    minting chunk-cited claims over live-fetched full text — this
    **discharges the 015 rev-3.14 flow-back deviation** (its smoke
    ran minus `ingest`); (c) SSRF guards evidenced at test level
    (localhost / private-IP / redirect-to-private all refused) — no
    live probe; (d) if decision 9B is adopted: one no-reference
    envelope-basis synthesise run producing a labelled artefact
    instead of refusing. Wall-clock recorded per leg (feeds the
    depth/time-budget seam and 017). **No deep-chain e2e** (the 014
    lesson; 017 owns the dress rehearsal). Cost: mini-class LLM legs
    over one modest corpus — low single-digit dollars.

## Constraints & approval gates

- **Runtime egress** (gated, rides this slice): live document
  fetching — the running product reaching arbitrary publisher hosts
  carrying no project data beyond the URL itself. This is the
  slice's reason to exist; approved at this contract's 🛑.
- **Schema**: none expected. `FAILURE_REASONS` growth (`blocked`) is
  code-enforced by design (008 decision 3); decision 9B is a code
  gate + labelling, no migration. Any schema need = stop condition.
- **Dependencies**: none new (httpx · trafilatura · pymupdf4llm ·
  lxml all present).
- **CI**: unchanged in-slice. The deferred `pip-audit` step is
  surfaced as a gate question below — if approved it lands as its
  own tiny follow-up, not smuggled in here.
- **Public interfaces**: none — no new Plan/Config fields; the live
  switch already exists.
- **No new LLM surfaces** — zero new prompts (first live-path slice
  with no egress-side generation).

## Public / private boundary

Committable: contract/plan/verification artefacts, tests, fixtures
(sanitized or openly-licensed per the fixtures policy). Private:
fetched document bytes (never committed — live-check evidence records
counts, hosts, reasons and timings only), any URL query params of
concern (none expected — public metadata URLs).

## Model route

n/a for new surfaces (no new inference). The live-check chain smoke
rides the existing routed components unchanged.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag that doesn't change v3.0 behaviour.
- **Flag, don't drop** — unfetchable/paywalled sources stay, labelled; never hidden.
- **Honest absence** — `text_basis` and citation labels carry what a claim rests on.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: any approval gate above is hit beyond what
this contract records (schema, deps, CI, public interface); scope
would grow past this slice (a parse-tier escalation, a caching layer,
a progress protocol); the substrate decision turns out to require
more than the §9 gate + labelling (e.g. a schema change); or the
turn/token budget is spent. Report the blocker; don't push through.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) —
  green, deterministic, zero-egress (fixture default unchanged;
  socket-deny guard extended to the live module's import boundary).
- Unit tests pin: SSRF refusals (scheme/IP/redirect) · size-cap
  enforcement (header + streamed) · content-type classification
  branches · retry/backoff set · per-link isolation (a raising
  fetcher yields a reason-coded outcome) · politeness spacing (clock
  injected) · landing-page discovery + DOI fallback · reason mapping.
- The pinned live check (decision 12), evidenced in verification.md.

## Verification evidence expected

Command results; the live-check record (outcome distribution vs the
RETRO baseline, wall-clock per leg, politeness/memory observations);
diff summary; public-safety confirmation (no document bytes
committed); known gaps + deferred updates.

## Risk tier & review focus

**Tier 3** — runtime egress + untrusted input (arbitrary web PDFs/HTML
into binary parsers). Review focus: SSRF completeness (redirect
re-validation especially) · resource exhaustion (size caps, buffering,
politeness) · per-link isolation vs fail-loud boundaries (which
failures are per-document vs component-level) · provenance honesty
(decision 9's labelling; flag-not-drop) · scope creep (parse tiers,
caching, progress protocols all stay deferred).
