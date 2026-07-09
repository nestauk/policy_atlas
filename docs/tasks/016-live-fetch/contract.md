# Task contract: 016-live-fetch

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **APPROVED rev 2.2 · amended revs 2.3–2.5
> post-approval** (2.3: fixture-corpus relocation, user challenge ·
> 2.4: adversarial review adjudicated, 8/10 adopted · 2.5: findings
> 4+5 resolved spec-faithful, user call) — planning next.
> Contract approved (before planning): **2026-07-09 · Shabeer Rauf**
> (rev 2.2, covering the gated set: runtime egress — live document
> fetching — and the one CI addition, the pip-audit job; ratifying
> the decision-9 chain-composition rule, the decision-8
> access-failure ladder, and the rev-2 dependency posture) ·
> Plan approved (before implementation): _pending_ · ADR: expected
> (chain-composition rule, decision 9).
>
> **Terminology note — "plan-pinned"**: pinned in THIS TASK's
> implementation plan (`plan.md`, task-cycle step 3) and reviewed at
> the plan 🛑 — exact constant values (timeouts, byte caps,
> concurrency numbers) are decided there, not in this contract. It
> never refers to the orchestrator's analysis plan-as-object.
>
> **Revision history:**
> - **rev 2.6** (2026-07-09, minor clarification from the PLAN-stage
>   adversarial review, finding 11): "zero new prompts" precised to
>   "zero new prompt SURFACES" — the rev-2.5 widening carries one
>   lead-authored existing-prompt text edit (`synthesise_section_v1 →
>   v2`, the text_basis rule); no settled decision changed.
> - **rev 2.5** (2026-07-09, user call closing the rev-2.4 reopened
>   question — findings 4+5 resolved **spec-faithful**): components
>   §4's flag-not-drop ingestion clause enacted in full — failed-fetch
>   docs are ingested on abstract + metadata, join grounded retrieval
>   as labelled substrate (`text_basis: abstract_only` on citations),
>   an all-fetch-failed corpus still synthesises visibly labelled,
>   and `no_groundable_substrate` narrows to genuinely empty corpora.
>   In-scope: the ingest failure path's abstract-basis substrate
>   entry + a bounded synthesise chunk-loader widening. Live check
>   gains the labelled-abstract-substrate observation. This enacts
>   written spec text 008 never reached; doesn't touch the A-vs-B
>   call (fetch is attempted for every document regardless).
> - **rev 2.4** (2026-07-09, contract-stage adversarial review
>   adjudicated — Codex, 10 findings: 2 blocker · 7 major · 1 minor;
>   **8 adopted in-slice, 2 reopen a scoped 🛑 question**). Adopted:
>   **BLOCKER 1** — URL hygiene: userinfo URLs refused; fragments
>   stripped; log lines/events carry scheme+host+path only (never
>   query strings — tokened OA URLs are the 015 leak class); verbatim
>   URLs persist only in the DB attempts trail + `fetched_from`
>   (provider-data retention, 007 precedent). **BLOCKER 2** — DNS
>   rebinding closed: all A/AAAA answers classified (IPv4-mapped-IPv6
>   normalised), connection pinned to the validated address or
>   revalidated at connect. **3** — DOI fallback named as the one
>   URL-construction exception (validated, encoded, fully guarded).
>   **6** — prefix-hydration proof added to acceptance/rubric.
>   **7** — live-check rubric item gains politeness/memory/isolation
>   evidence. **8** — OS-level CI egress guard explicitly deferred
>   with rationale (test-level socket-deny already covers parent +
>   workers as-built); the "every pre-registered requirement" claim
>   annotated. **9** — flow-back scope gains the components.md
>   opening chain statement (second stale chain source). **10** —
>   pip-audit rubric item added. **REOPENED (findings 4+5, one
>   substrate-honesty pair)**: decision 9's wording corrected to
>   mandatory-ATTEMPT (live fetch can fail for every document); the
>   all-fetch-failed corpus at synthesise — and whether failed-fetch
>   docs join grounded retrieval on labelled abstract text per
>   components §4's flag-not-drop ingestion clause (as-built,
>   synthesise loads only full-text chunks) — is ❓ OPEN for the
>   user at the gate.
> - **rev 2.3** (2026-07-09, post-approval amendment — user challenge
>   held): **fixture-corpus relocation folded in-slice** (new decision
>   12; live check renumbered to 13). Rev 1 misread the pre-registered
>   trigger — "when the live fetcher takes over as default" means the
>   *product* default, not the library/test default: with 016, replay
>   stops being product behaviour and the committed corpus is test
>   substrate only, so the ~24 MB moves out of the wheel now, exactly
>   as the 2026-07-05 user decision specified. Adds the test-pinned
>   invariant that a live-flagged run never silently falls back to
>   fixture replay.
> - **rev 2.2** (2026-07-09, user gate call): **pip-audit CI step
>   folded in-slice** — the CI gate is approved at this contract's 🛑
>   (one dependency-vulnerability audit job + a documented
>   ignore-list policy with written justifications). Rationale: 016
>   is the slice that turns pymupdf/lxml into parsers of arbitrary
>   hostile web bytes, so the standing known-CVE control lands with
>   the exposure, not after it. Discharges the deferred.md
>   pre-registration ("a pip-audit-style dependency check belongs in
>   CI now that binary parsing deps are in the tree").
> - **rev 2.1** (2026-07-09, two user probes at the gate): **(a)**
>   decision 11's invariant sharpened — peak memory bounded by window
>   budgets, never corpus full-text size (the as-built loader holds
>   every document's full chunk list simultaneously; the user's
>   200-doc × ≥25-page case makes that tens of MB and unbounded in
>   the long-report tail). **(b)** Oversized-chunk provenance
>   ergonomics (citations resolving into huge frozen chunks) recorded
>   as a new deferred seam — **citation-context character clamp** at
>   the consumption surfaces (grounding-judge envelope ·  future read
>   surfaces), NOT in-slice: chunks are frozen, and clamping judge
>   input is prompt-bearing/eval-sensitive (013 surface). Stage-2
>   window confirmed fine by the user at its 60k budget.
> - **rev 2** (2026-07-09, user gate calls — five substantive):
>   **(a) Substrate fork resolved — Option A adopted, generalised
>   into a chain-composition rule**: every EB run executes the
>   **mandatory spine** acquire(`search`) → screen → classify →
>   appraise → **ingest(fetch)** → synthesise; everything else
>   (characterise · select · extract · group · stage-2 screen) is
>   orchestrator-discretionary per the user's depth-gradation
>   preference. Synthesise's substrate gate is **untouched** (its
>   envelope-only refusal becomes unreachable in composed runs and
>   stays as the fail-closed backstop). Decision 9 rewritten; ADR
>   required. **(b) De-RETRO'd**: the demo retro is demoted from
>   design authority to anecdotal prior everywhere — the demo was a
>   rapid throwaway build; this slice is production code. Decision 5
>   rewritten from first principles (notably: parsing ALREADY
>   parallelises across spawned worker processes as-built —
>   `ingest_full_text.py` fan-out with terminate-able 120 s/doc
>   timeout; the demo's "serial ingest" was the demo driver's shape,
>   not the library's); the live check's "RETRO baseline" reframed as a
>   prior data point, never a target. **(c) Dependency posture made a
>   reasoned adjudication, not a reflex** — candidates named and
>   adjudicated in Constraints; the dep gate stays open for a
>   plan-time case. **(d) Paywall honesty**: 403 is NOT reliably a
>   paywall live (WAF/bot-blocking from datacenter IPs is common);
>   decision 8 rewritten — 401 maps to `paywall`, 403 only with
>   corroboration, else a new code-enforced `blocked_by_host` reason
>   so bot-blocks are visible, never miscounted as paywalls (coverage
>   honesty). **(e) "Plan-pinned" glossary note added** (collision
>   with plan-as-object named).
> - **rev 1** (2026-07-09): initial draft. Sequencing context: third
>   slice of the live-demo path (014 LLM screen+classify MERGED →
>   015 live search MERGED → **016 live fetch/ingest** → 017 demo
>   dress-rehearsal → eval slice). Grounded on: `docs/deferred.md`
>   § Full-text ingestion (the pre-registered 008 requirements
>   ledger), the as-built `ingest_full_text.py` seam, the 015
>   transport precedents (decisions 1 · 3 · 7 · 9), and demo
>   evidence (now demoted per rev 2b).

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
   rediscovered in production (decisions 1–8, 10–12; one named
   exception — the OS-level CI egress guard is explicitly deferred
   with rationale, see Out of scope; rev 2.4).
2. **The chain-composition rule** (decision 9, user call at this
   gate): the mandatory EB spine includes ingest, so every run —
   rapid included — synthesises over fetched text; synthesise's
   substrate machinery is untouched.

Everything downstream of the seam already exists and is reused: the
URL cascade (`candidate_urls`), per-URL attempt accounting, the closed
reason vocabulary, the parse worker fan-out, segment → embed,
`text_basis` honesty labels, flag-not-drop for unfetchable sources.

## Deliverable

PR landing:

- Live fetch module: a `LiveDocumentFetcher` (`mode="live"`) in a
  **new module** — `ingest_full_text.py` stays free of HTTP imports
  (decision 1).
- The hardening set: SSRF/redirect policy · timeouts · size caps +
  bounded buffering · per-host politeness · bounded-concurrency
  fetching · retry/backoff · magic-byte sniffing · charset handling ·
  per-link exception isolation (decisions 3–6).
- Bounded recall aids: landing-page PDF-link discovery + DOI-URL
  cascade fallback · the honest access-failure ladder + OA
  cross-check (decisions 7–8).
- The chain-composition rule (decision 9): spec flow-back (components
  §9 + capability.md + the components.md opening chain statement —
  rev 2.4) + `log.md` entry + ADR; skeleton/profile wiring so every
  profile's chain includes ingest; the **§4 failure-path enactment**
  (rev 2.5) — abstract-basis ingestion of unfetchable docs +
  synthesise's bounded loader widening with citation labels.
- Tests (transport-stubbed, zero-egress; SSRF guard unit tests) +
  `verification.md` with the pinned live check (decision 13).
- The fixture-corpus relocation (decision 12, rev 2.3): corpus out
  of the wheel, suite-substrate home in the repo.
- The **pip-audit CI job** + ignore-list policy (rev 2.2 — the CI
  gate's one approved addition).
- `deferred.md` + knowledge updates (discharged entries marked; new
  seams recorded).

## Read first

- [EB components §4 — full-text ingestion](../../specs/capabilities/evidence-base/components.md)
  (gated by screen, built for all screened-in; flag-not-drop;
  `text_basis`; fetch is mechanical execution of the governed
  `search` — telemetry plane, not per-document audit events)
- [EB components §9 — synthesise](../../specs/capabilities/evidence-base/components.md)
  (the substrate-conditional flow; the envelope-only refusal decision
  9 makes unreachable-by-composition)
- [deferred.md § Full-text ingestion](../../deferred.md) — the
  pre-registered requirements ledger this contract enacts
- [008 contract](../008-full-text/contract.md) — the seam design and
  the closed failure-reason vocabulary
- As-built: `ingest_full_text.py` (the seam, `candidate_urls`, the
  attempt loop, the spawned-process parse fan-out + per-doc timeout,
  reason vocabulary), `acquire.py` envelope chunking + embedding
  (abstracts are chunked AND embedded at acquire — the flag-not-drop
  retrieval guarantee in decision 8's note), `synthesise.py` corpus
  profile + substrate gating (unchanged, understood)
- 015 contract decisions 1 (httpx posture) · 3 (timeouts) · 7 (retry
  set) · 9 (the "no provider URL is ever fetched" rule this slice
  deliberately opens, with guards — rationale recap in decision 3)
- `demo/RETRO.md` §4 + `demo/server/fetcher.py` (branch
  `demo-live-run`) — **anecdotal prior only** (rev 2b): one deep
  run's observed failure classes (paywalls, empty bodies behind DOI
  redirects, parse failures on grey literature) inform which hazards
  are real; none of its implementation shapes or numbers are design
  authority.

## Scope / Out of scope

**In:**

- New live-fetch module + its tests.
- `ingest_full_text.py`: only what wiring requires (growing the
  code-enforced `FAILURE_REASONS` — zero-schema by design; the
  fetch-stage concurrency hook per decision 5's plan-designed
  pipeline).
- `skeleton.py` / harness / profile wiring: the live fetcher rides
  the existing one live switch (decision 2); every profile's chain
  gains the ingest leg (decision 9).
- `screen.py` stage-2 loader — the bounded windowing rider
  (decision 11) only.
- `synthesise.py` — the bounded chunk-loader widening for
  abstract-basis substrate + citation labels (decision 9, rev 2.5)
  only; the substrate gate's fail-closed character unchanged.
- CI config — the pip-audit job only (rev 2.2).
- Packaging + fixture loading — the corpus relocation (decision 13,
  rev 2.3) only.
- Spec flow-back: components §4/§9 + capability.md mandatory-spine
  statement; `deferred.md`; knowledge docs; ADR.

**Out (stay deferred — `docs/deferred.md`):**

- docling / ML-layout parse escalation; OCR for `no_text_layer`;
  pymupdf-layout (licence-blocked).
- Multi-PDF Overton assembly (`grouped_pdf_ids_in_result`); primary
  `pdf_url` only, as-built.
- Cross-run / cross-project fetch caching and snapshot reuse;
  concurrent-run write guard (web-app slice).
- The designed component-progress protocol — recorded seam; this
  slice ships log-line telemetry only.
- Time-budget parser-tier selection; chunk-volume bias controls at
  retrieve; per-depth fetch budgets (a lever for the tool-wide
  depth/time-budget gradation seam, not hard-wired here).
- The `unshare -n`-style **OS-level CI egress guard** *(rev 2.4,
  adversarial finding 8 — explicit deferral with rationale, not a
  silent drop)*: the pre-registered test-level control already
  exists as-built (the socket-deny guard covers parent + workers);
  the OS-level CI variant is the stronger durable control but is a
  CI change beyond this slice's one approved addition — stays in
  deferred.md with this rationale.

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

2. **Egress switch: the skeleton's one live flag.** A live run uses
   the live fetcher; the suite and all library defaults stay
   fixture-backed and egress-free (`make verify` unchanged). No
   per-surface toggles. **No API keys exist on this surface** (public
   document URLs) — the 015 key-hygiene machinery is n/a, but a test
   asserts no `Authorization`/cookie state is ever attached to
   document fetches (we fetch as an anonymous public client, always).

3. **SSRF posture — the deliberate opening of 015's "no provider URL
   is ever fetched" rule, with structural guards.** *Rationale recap
   (user question, rev 2): the 015 rule exists because URLs arriving
   in provider responses are third-party-controlled data — fetching
   them turns the product into a proxy that poisoned or malicious
   upstream data can point at internal targets (cloud metadata
   endpoints, localhost admin ports) or at keyed URLs whose
   credentials then leak into logs/snapshots (Overton's
   `next_page_url` carries the API key — 015's one guarded
   exception). 015's search surface never needed arbitrary fetches,
   so a total structural ban was the cheapest correct rule. 016's
   entire purpose is fetching provider-supplied URLs, so the ban is
   replaced by guards.* The fetched URL universe is exactly:
   `candidate_urls()` from the source's own envelope metadata, plus
   decision 7's discovered links, plus the DOI fallback. Guards, all
   test-pinned: scheme allowlist (`http`/`https` only); the resolved
   target IP is checked before connecting and **private / loopback /
   link-local / metadata ranges are refused**; redirects are followed
   to a plan-pinned hop cap with **every hop re-validated** (scheme +
   resolved IP); a refused URL is a per-URL reason-coded failure
   (`blocked` joins the code-enforced `FAILURE_REASONS` — no
   migration), never a crash. URLs are fetched verbatim from
   metadata — never rewritten, never templated — with **one named
   construction exception**: decision 7's DOI fallback *(rev 2.4,
   adversarial finding 3)*. **DNS-rebinding is closed structurally**
   *(rev 2.4, adversarial finding 2)*: ALL resolved addresses are
   classified (every A and AAAA answer, IPv4-mapped-IPv6 forms
   normalised before checking), and the connection is made **to the
   validated address** (pinned-IP transport with Host/SNI preserved)
   or revalidated at connect time — never check-then-reresolve.
   **URL hygiene** *(rev 2.4, adversarial finding 1)*: URLs carrying
   userinfo (`user:pass@host`) are refused outright (`blocked`);
   fragments are stripped; **log lines and events carry scheme +
   host + path only — never query strings** (OA aggregators hand out
   signed/tokened URLs; a token in a log line is the 015 leak class
   again). The verbatim URL lives only in the persisted per-URL
   attempts trail — provider-supplied data retained under the same
   discipline as the rest of the envelope metadata (007 precedent) —
   and in `fetched_from` provenance; verification evidence records
   hosts only.

4. **Timeouts, size caps, bounded buffering.** Every request carries
   an explicit connect+read timeout (constant plan-pinned). Byte cap
   enforced against BOTH `Content-Length` and the streamed body
   (plan-pinned; existing `too_large` reason). **Total in-flight
   buffered bytes across concurrent fetches are capped** (plan-pinned;
   backpressure, not failure) — the pre-registered OOM control: a
   live run holding many concurrent multi-MB bodies must degrade to
   waiting, not to memory exhaustion.

5. **Pipeline: the contract pins invariants; the plan designs the
   shape** *(rewritten rev 2 from first principles — no demo-derived
   shapes)*. The workload has three parts with different physics:
   **fetch** is I/O-bound → bounded-parallel (global cap + per-host
   cap, plan-pinned); **parse** is CPU-bound → the as-built
   spawned-process fan-out with its terminate-able per-doc timeout is
   reused (parallel parsing already exists — nothing here is serial
   by design); **DB writes** stay within the run's single transaction
   (the single-active-writer-per-project invariant; write volume is
   trivial next to fetch/parse). Whether fetch and parse overlap as a
   pipeline or run as staged phases is a **plan-time design choice**,
   judged on bounded memory (decision 4's cap) and code simplicity —
   not pre-committed here. Invariants that bind any shape:
   per-host politeness (concurrency cap + minimum interval —
   publisher hosts ban abusers; the Overton-limiter lesson
   generalised); one retry on transient failures (timeout · 429 ·
   500/502/503/504 — the 015 decision-7 set) with backoff, then a
   reason-coded failure; **per-link exception isolation** — any raise
   inside a fetch becomes a reason-coded `FetchResult`; the component
   never fails because documents failed (fail-loud is correct
   fixture-world and wrong live — pre-registered); an in-run URL
   cache dedups repeat URLs within one run; determinism in the suite
   (concurrency is a live-mode property; fixture replay stays
   deterministic).

6. **Content-type by magic bytes first, headers second; explicit
   charset handling.** `%PDF` magic wins over any header (a PDF served
   as `application/octet-stream` must never fall through to the
   plain-text parser — pre-registered); HTML detected by header or
   body sniff. HTML bytes pass to trafilatura undecoded (it handles
   declared charsets); the UTF-8-replace decode applies only to the
   plain-text path. Unit tests pin every classification branch.

7. **Bounded recall aids: landing-page PDF discovery + DOI fallback.**
   Landing pages and redirect chains that end in HTML rather than the
   document are a structural feature of scholarly URLs (DOI resolvers
   land on publisher pages), not a demo anecdote. (a) When a fetched
   body is HTML on a URL the cascade expected to be a document, parse
   it for `<meta name="citation_pdf_url">` (the scholarly standard)
   and obvious PDF anchors; **at most one discovered link** is
   followed per landing page, SSRF-validated (decision 3), recorded
   in the existing per-URL attempts trail. (b) `candidate_urls` gains
   a final **`https://doi.org/<doi>` fallback** when the envelope
   carries a DOI and it is not already present — **the one URL the
   product constructs rather than receives** *(rev 2.4, adversarial
   finding 3 — named exception to decision 3's verbatim rule)*: the
   DOI value is validated before use (shape/length caps,
   control-character rejection), percent-encoded into the path, and
   the resulting URL goes through the full decision-3 guard set
   including per-hop redirect validation. Both aids are
   deterministic mechanics, not new judgment surfaces.

8. **Access-failure honesty: 401/403 are NOT one bucket** *(rewritten
   rev 2 — user challenge held: 403 is frequently WAF/bot-blocking of
   datacenter clients, not a paywall; and many real paywalls serve
   200 + landing HTML)*. The ladder: **401 → `paywall`** (auth
   demanded is the paywall shape); **403 → `paywall` only with
   corroboration** — envelope OA status says closed access, or
   paywall/login markers in the response body (plan-pinned marker
   list) — **else `blocked_by_host`** (new code-enforced reason:
   we were refused as a client, which says nothing about the
   document's accessibility); **200 + paywall-marker landing HTML →
   `paywall`**. The **OA cross-check** uses envelope metadata already
   in hand (OpenAlex `open_access`): an allegedly-OA doc landing in
   `paywall`/`blocked_by_host` logs the inconsistency (a future eval
   signal). Exact mappings plan-pinned; vocabulary additions are
   code-enforced (zero-schema). Flag-not-drop unchanged — and
   *by construction as-built at the embedding layer* (verified, user
   question): a doc whose fetch fails keeps its envelope snapshot,
   whose abstract was chunked AND embedded at acquire (`acquire.py`
   envelope path + `embed_pending_chunks`) — and *(rev 2.5,
   adversarial finding 5 + user call)* that availability now extends
   to the **synthesis surface** via decision 9's §4 enactment:
   failed-fetch docs join grounded retrieval as labelled
   abstract-basis substrate; nothing is dropped for being
   unfetchable.

9. **Chain composition: the mandatory EB spine includes ingest**
   *(user call at this gate, 2026-07-09 — Option A, generalised)*.
   Every EB run executes **acquire(`search`) → screen → classify →
   appraise → ingest(fetch) → synthesise**; every other component —
   characterise · select · extract · group · stage-2 screen — is
   **orchestrator-discretionary**, chosen per the user's
   depth-gradation preference (the tool-wide depth/time-budget seam
   allocates; per-depth fetch budgets are a recorded lever of that
   seam, not hard-wired here). **Precision (rev 2.4, adversarial
   finding 4): mandatory ingest is a mandatory ATTEMPT, not a
   substrate guarantee** — live fetching can fail per document and,
   in the worst corpus, for every document; what the spine
   guarantees is that the attempt was made and every outcome is
   reason-coded. **Resolved (rev 2.5, user call): components §4's
   flag-not-drop ingestion clause is enacted in full** — a document
   whose fetch fails is still ingested **on the text in hand**
   (abstract + metadata), enters grounded retrieval as labelled
   substrate, and every citation into it carries
   `text_basis: abstract_only` so grounding and readers see what a
   claim rests on. Consequences: an all-fetch-failed corpus still
   synthesises — everything visibly abstract-labelled — and
   `no_groundable_substrate` narrows to genuinely empty corpora
   (screened-in count zero), the true miscomposition backstop.
   In-scope mechanics: the ingest failure path materialises the
   abstract-basis substrate entry (exact shape plan-designed) and
   synthesise's chunk loader gains the **bounded** widening to
   include it, labels carried through; the substrate gate's
   fail-closed character is preserved. This enacts spec text that
   008 (fixture era) never reached — no spec flow-back needed
   beyond an as-enacted note. Unchanged
   either way: the 015 smoke's minus-`ingest` deviation closes
   (decision 13b); envelope-basis synthesis absent ingest is not a
   product mode. Spec flow-back: the mandatory-spine statement lands
   in components §9 + capability.md **and the components.md opening
   chain/table statement** *(rev 2.4, adversarial finding 9 — the
   top-of-file chain shape is a second stale source the orchestrator
   compiler would read)* with a `log.md` entry; **ADR records the
   rule**.

10. **Telemetry: the fetch is mechanical execution of the governed
    `search`** (spec) — structured log lines per attempt (as-built
    pattern, **amended rev 2.4**: log lines carry scheme+host+path
    only, never query strings — decision 3's URL hygiene) +
    **run-record summary counts** (attempted · ok · per-reason
    failures · parse failures · bytes fetched · wall-clock), no
    per-document audit events. The user-grade component-progress
    protocol stays a recorded seam.

11. **Stage-2 screen windowing rider (small, pre-registered
    trigger).** Context: screen is two-stage (components §2) — stage
    1 judges title+abstract; stage 2, run at depth **after
    ingestion**, re-screens on full text (demote-only). The 014
    implementation's stage-2 loader (`_load_stage2_docs`,
    `screen.py`) loads **every chunk of every document** into memory,
    although the stage-2 prompt consumes only a token-bounded first
    window. Harmless at fixture scale (24 docs); needless memory/DB
    load at live corpus scale (hundreds of docs × tens of chunks) —
    which is exactly what this slice creates. The 014 review deferred
    the fix with the trigger "when 015/016 lands"; 016 is that
    trigger. The rider: load only the chunks the stage-2 window
    actually reads. The binding invariant *(rev 2.1, user question)*:
    **peak memory is bounded by window budgets, never by corpus
    full-text size** — as-built, `_load_stage2_docs` materialises
    every document's full chunk list simultaneously before any
    payload is built, so an unluckily long corpus (200 long reports)
    is unbounded resident text; after the rider, per-doc load stops
    at the window budget (+ split-boundary slack) and what persists
    per doc is only its ≤ budget payload. Exact loading shape
    (prefix query vs streaming) is plan-designed. No behaviour
    change, test-pinned (byte-identical first-window payload); if
    the plan finds it non-trivial, it returns to deferred with a
    note — it must not grow this slice.

12. **Fixture-corpus relocation — the pre-registered trigger fires
    with this slice** *(rev 2.3, user call at the gate — correcting
    rev 1's misreading)*. The 2026-07-05 decision committed the
    ~24 MB corpus inside the package "only because replay *is* the
    v3.0 product behaviour", with relocation triggered "when the
    live fetcher takes over as default". 016 is that moment: live
    fetch becomes the product behaviour; the fixtures were only ever
    test substrate. In-slice: the corpus moves out of
    `src/policy_atlas/data/fulltext/` — out of the wheel — to a
    repo-committed test-data home (`tests/`, per the 2026-07-05
    decision; exact home + loader mechanics plan-designed, noting
    `FixtureFetcher` currently loads via
    `importlib.resources.files("policy_atlas")` and its resolution
    must move with the corpus); the corpus itself stays committed as
    the deterministic test substrate; the ≤30 MB licence-guard
    budget test moves with it. Invariants: the suite stays
    deterministic and egress-free; the wheel slims by the corpus;
    and a **live-flagged run never silently falls back to fixture
    replay** (decision 2's one-switch, now stated as a test-pinned
    property). Packaging-only — no schema or public-interface
    change; if loader mechanics turn out non-trivial, escalate
    rather than grow the slice.

13. **Live-check scope pin** (contract-time, per failure-log
    2026-07-08): changed surfaces + one cheap full-chain smoke —
    (a) one live fetch/ingest run over a real screened-in scope
    (~30–60 docs): the full outcome distribution recorded (ok ·
    per-reason failures · parse failures — observed counts, never
    pinned values; demo numbers are a prior data point, not a
    target), politeness observed (per-host spacing visible in logs),
    per-link failures never fail the component, bounded memory
    (buffering cap respected); (b) **the mandatory-spine chain smoke**
    — acquire → screen → classify → appraise → ingest → synthesise
    over a live-acquired corpus, synthesise minting chunk-cited
    claims over live-fetched full text — **discharging the 015
    rev-3.14 flow-back deviation** (its smoke ran minus `ingest`);
    (c) SSRF guards evidenced at test level (localhost / private-IP /
    redirect-to-private all refused) — no live probe; (d) *(rev 2.5)*
    at least one failed-fetch document observed in the smoke's
    synthesise output as **labelled abstract-basis substrate**
    (partial fetch failure is a near-certainty in any live corpus,
    so this costs nothing extra); (e) wall-clock
    recorded per leg (feeds the depth/time-budget seam and 017).
    **No deep-chain e2e** (the 014 lesson; 017 owns the dress
    rehearsal — no select/extract/group legs). Cost: mini-class LLM
    legs over one modest corpus — low single-digit dollars.

## Constraints & approval gates

- **Runtime egress** (gated, rides this slice): live document
  fetching — the running product reaching arbitrary publisher hosts
  carrying no project data beyond the URL itself. This is the
  slice's reason to exist; approved at this contract's 🛑.
- **Schema**: none expected. `FAILURE_REASONS` growth (`blocked` ·
  `blocked_by_host`) is code-enforced by design (008 decision 3);
  decision 9 is composition + spec text, no migration. Any schema
  need = stop condition.
- **Dependencies** *(rev 2 — reasoned adjudication, not a reflex;
  the 015 httpx lesson cuts both ways)*: candidates considered —
  retry libraries (tenacity et al.: our policy is one retry + one
  backoff, a few lines; a library adds a competing semantics layer),
  SSRF-guard libraries (the requests-era ones are unmaintained;
  stdlib `ipaddress` + explicit resolution is small and auditable —
  and this is exactly the surface we want first-party, like 015's
  transport hardening), HTML link extraction (lxml is already in the
  tree via trafilatura), charset detection (trafilatura owns it),
  robots.txt (stdlib `urllib.robotparser` if adopted at plan time).
  **Default: no new dependency — but the gate stays open**: if
  plan-time design finds a candidate that genuinely earns its place
  (including declaration-only promotion of an existing transitive,
  the 015 rev-3.13 precedent), it comes back through the dependency
  gate with its case; it is not blocked by this contract.
- **CI** *(rev 2.2 — approved at this gate)*: one addition rides this
  slice — a **`pip-audit` dependency-vulnerability job** (advisories
  from the PyPA/OSV databases against the lockfile), with an explicit
  ignore-list policy: every ignored advisory carries a written
  justification in the repo. No other CI change.
- **Public interfaces**: none — no new Plan/Config fields; the live
  switch already exists.
- **No new LLM surfaces** — zero new prompt surfaces (first
  live-path slice with no egress-side generation). *(rev 2.6
  clarification, plan-review finding 11)*: decision 9's rev-2.5
  widening carries **one existing-prompt text edit** —
  `synthesise_section_v1 → v2`, the single `text_basis` labelling
  rule, lead-authored, wire-compatible; a provenance bump, not a new
  surface.

## Public / private boundary

Committable: contract/plan/verification artefacts, tests, fixtures
(sanitized or openly-licensed per the fixtures policy). Private:
fetched document bytes (never committed — live-check evidence records
counts, hosts, reasons and timings only).

## Model route

n/a for new surfaces (no new inference). The live-check chain smoke
rides the existing routed components unchanged.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag that doesn't change v3.0 behaviour.
- **Flag, don't drop** — unfetchable/blocked sources stay, labelled; never hidden.
- **Honest absence** — `text_basis` and failure reasons carry what a claim rests on;
  bot-blocks are never counted as paywalls (decision 8).
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: any approval gate above is hit beyond what
this contract records (schema, deps beyond the recorded posture, CI,
public interface); scope would grow past this slice (a parse-tier
escalation, a caching layer, a progress protocol); decision 9's
flow-back turns out to require more than spec text + profile wiring
(e.g. a schema or public-interface change); or the turn/token budget
is spent. Report the blocker; don't push through.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) —
  green, deterministic, zero-egress (fixture default unchanged;
  socket-deny guard extended to the live module's import boundary).
- Unit tests pin: SSRF refusals (scheme · userinfo · private/
  loopback/link-local/metadata IP across ALL A/AAAA answers and
  IPv4-mapped-IPv6 forms · per-hop redirect · connect-time pinning,
  rev 2.4) · URL log hygiene (no query strings in log lines) ·
  size-cap enforcement (header + streamed) · content-type
  classification branches · retry/backoff set · per-link isolation
  (a raising fetcher yields a reason-coded outcome) · politeness
  spacing (clock injected) · landing-page discovery + DOI fallback
  (validated, encoded, guarded) · the decision-8 ladder (401 vs
  corroborated-403 vs `blocked_by_host` vs 200-with-markers) ·
  stage-2 windowing rider: behaviour preservation (byte-identical
  first-window payload) AND **prefix hydration proof** — only chunks
  up to `STAGE2_WINDOW_CHAR_BUDGET` + split-boundary slack are
  loaded per doc (rev 2.4, adversarial finding 6).
- The pinned live check (decision 13), evidenced in verification.md.

## Verification evidence expected

Command results; the live-check record (full outcome distribution,
wall-clock per leg, politeness/memory observations); diff summary;
public-safety confirmation (no document bytes committed); known gaps
+ deferred updates.

## Risk tier & review focus

**Tier 3** — runtime egress + untrusted input (arbitrary web PDFs/HTML
into binary parsers). Review focus: SSRF completeness (redirect
re-validation especially) · resource exhaustion (size caps, buffering,
politeness) · per-link isolation vs fail-loud boundaries (which
failures are per-document vs component-level) · provenance honesty
(decision 8's ladder; flag-not-drop) · decision 9's flow-back fidelity
(spec text matches the adopted rule exactly) · scope creep (parse
tiers, caching, progress protocols all stay deferred).
