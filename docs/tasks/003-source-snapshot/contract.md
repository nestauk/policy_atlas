# Task contract: 003-source-snapshot

One implementation slice. Boundaries: [AGENTS.md](../../../AGENTS.md). Specs: [docs/specs/index.md](../../specs/index.md).

> **Status: approved. Tier 3.** Schema gate crossed (new tables + migration). No `search` egress,
> no vectors, no text-parsing library, no real model calls.
> Contract approved: 2026-06-29 · Shabeer · Plan approved: 2026-06-29 · Shabeer · ADR: none.

## Goal

Add the **corpus/source model** — the Tier-0 substrate every Evidence Base component depends on
— and flip `produce_grounded_block` from synthetic in-memory fixtures to real, DB-persisted
chunks. After this slice, a document can be ingested into a project corpus and a grounded block
can be verified against frozen chunk text stored in the database.

## Deliverable

A PR landing: three new tables + one Alembic migration; a minimal upload-ingest function; an
updated `produce_grounded_block` that reads chunks from the DB; a structured `citation` table
enforcing the `chunk_id` FK; deterministic tests; and `verification.md` evidence.

"Shipped" = `make verify` green, an end-to-end thread that ingests a source, produces a grounded
block citing a real DB chunk, and fails closed on a fabricated quote.

## Read first

Route via [specs/index.md](../../specs/index.md). Read the source sections in depth:

- [system/data-model.md](../../specs/system/data-model.md) §§ Corpus & source snapshots, Atomic
  units — table shapes, `text_basis`, `segmentation_policy`, identity rules, upload vs acquired
  dedup behaviour, and the annotation layer.
- [system/provenance-grounding.md](../../specs/system/provenance-grounding.md) §§
  `produce-grounded-block`, Grounding tiers — how verify works; the quote-presence check runs
  against stored chunk text, not a snapshot reload.

## Scope

### In

**Schema (five new tables, one migration):**

- **`source_snapshot`** — content-addressed record, no original bytes retained.
  `source_snapshot_id` uuid pk · `content_hash` text not-null · `text_basis` text not-null
  (`full_text` | `abstract_only`) · `source_locator` text not-null (filename or user-assigned
  ref for uploaded; URL for acquired) · `metadata` jsonb not-null · `created_at` timestamptz.
  No `project_id` — identity is content, not project.

- **`project_source_snapshot`** — corpus membership; one row per (project, snapshot).
  `id` uuid pk · `project_id` uuid fk→project · `source_snapshot_id` uuid fk→source_snapshot ·
  `origin` text not-null (`uploaded` | `acquired`) · `run_id` uuid nullable fk→runs (null for
  uploads; set for acquired) · `ingested_at` timestamptz.
  Unique `(project_id, source_snapshot_id)`.

- **`chunk`** — frozen parsed text units; the content-of-record for citation and grounding.
  `chunk_id` uuid pk · `source_snapshot_id` uuid fk→source_snapshot · `sequence` int not-null ·
  `content` text not-null · `content_hash` text not-null · `locator` jsonb not-null (recorded
  by-product of parse; `{"page": n, "start": n, "end": n}` or similar) · `segmentation_policy`
  text not-null (fixed `manual_v1` this slice) · `created_at` timestamptz.
  Unique `(source_snapshot_id, sequence)`.

- **`citation`** — structured FK replacing the buried `source_ref` in `annotation.payload` for
  `annotation_type = 'citation'`. `citation_id` uuid pk · `annotation_id` uuid fk→annotation ·
  `chunk_id` uuid fk→chunk · `quote` text not-null · `verification_result` text not-null
  (`pass` | `fail`) · `created_at` timestamptz.

**Runtime changes:**

- **Upload-ingest function** — `ingest_upload(conn, project_id, chunks, source_locator, metadata,
  text_basis) → source_snapshot_id`. Creates one `source_snapshot` row (no dedup — each upload
  is a new snapshot per spec; see *No content-hash dedup for uploaded* below), chunk rows
  (sequence-ordered, `manual_v1` policy), and a `project_source_snapshot` membership row.

- **`produce_grounded_block` seam flip** — signature changes from `source_ref: str` to
  `source_snapshot_id: UUID`. Resolves chunks from the DB (`SELECT … FROM chunk WHERE
  source_snapshot_id = … ORDER BY sequence`) for the quote-presence check. Inserts into `citation`
  table (not only `annotation.payload`). `annotation.payload` for `citation` type retains
  `{"quote": …, "verification_result": …}` for human readability but the FK is the canonical
  reference. The `fixtures.py` synthetic lookup path is **retired from the runtime**; tests use
  DB-seeded chunk rows.

**Tests:**

- `test_ingest.py` — round-trip: `ingest_upload` creates expected rows; membership row present;
  each re-call creates a new snapshot (no silent dedup).
- `test_grounding.py` updates — quote-presence pass and fabricated-quote hard-fail against a
  real DB-seeded chunk (not a fixture); `citation` row has correct `chunk_id` FK.
- `test_schema.py` update — new tables covered by schema-compile check.

### Out (unchanged / deferred)

- No `search` egress — `acquire` component (OpenAlex / Overton) is deferred.
- No pgvector / embedding column on `chunk` — the seam is open (column can be added later
  without a data migration since chunks are immutable).
- No text-parsing library — `ingest_upload` accepts pre-parsed chunk strings; parse-on-ingest
  is a follow-on slice.
- No `supersedes` edge on `source_snapshot` — human-asserted, spec-deferred.
- No `search_coverage_record` table — required only when absence claims are made; deferred to
  the `acquire` slice.
- No cross-project acquired-snapshot sharing — the schema shape supports it (no `project_id` on
  `source_snapshot`), but dedup logic for acquired sources is a follow-on.
- The EB `acquire → screen → …` component skeleton — this slice only builds the data layer
  those components will write to.
- Aurora / prod untouched; `fixtures.py` stays for any test that doesn't need DB chunks (it is
  not deleted, only retired from the grounding runtime path).

## No content-hash dedup for uploaded sources

Per [data-model.md](../../specs/system/data-model.md): *"A corrected re-upload is a **new
snapshot**."* Content-hash dedup applies to **acquired** cross-project snapshots only. For
uploaded sources, each call to `ingest_upload` creates a new `source_snapshot` row regardless of
content hash. A future `supersedes` edge (deferred) lets the user mark a re-upload as correcting
its predecessor; silent dedup would hide that intent.

## Constraints & approval gates

| Gate | This slice | Decision needed |
|---|---|---|
| **Schema / migration** | 4 new tables + one Alembic migration | 🛑 needs approval |
| **Dependencies** | No new deps — SQLAlchemy + alembic + pytest already present | ✅ no new dep |
| **External egress** | None — no `search`, no model call | ✅ no egress |
| **Public interface** | `produce_grounded_block` signature changes (`source_ref: str` → `source_snapshot_id: UUID`); internal only (harness calls it) | 🛑 needs approval |
| **Inference route** | Same stub provider; no change | ✅ unchanged |
| **Frontend / CI / prod config** | Deferred | ✅ out of scope |

## Public / private boundary

- **Public-safe (committable):** all source code, migration, tests, this packet, `verification.md`.
- **Synthetic only:** test chunks are hand-written synthetic sentences — no real uploaded or
  acquired source text enters the repo.
- **Private (never committed):** credentials, real document text, raw traces.

## Model route

`produce_grounded_block`'s stub provider is unchanged — no real model call this slice.
LLM-as-judge grounding classifier remains a deferred seam (stub path: `verification_result` is
set by the deterministic quote-presence check only).

## Boundary-spanning quote — known limitation

The quote-presence check runs against the **concatenation** of all chunk texts (spec-mandated,
to avoid spurious misses at chunk boundaries). However, the `citation` row requires a single
`chunk_id` FK. When the verified quote spans two chunks — present in the concatenation but
absent from any individual chunk — the implementation selects the `chunk_id` of the first chunk
whose normalised content contains the quote; if none does, it falls back to `chunk_ids[0]`
(the first chunk in sequence order).

This is a v3.0 stub constraint: the stub inference provider always produces a quote that fits
within a single chunk, so the fallback path is untriggered in tests. The limitation must be
recorded in `verification.md` and in `docs/deferred.md`. Resolution path: when a real inference
provider lands, replace the single-chunk FK with a `citation_chunk` join table supporting
multi-chunk spans.

## Disciplines binding this slice

- **Model only what behaves** — no `supersedes` edge, no sensitivity column, no
  embedding/vector column; none changes v3.0 behaviour this slice.
- **Flag, don't drop** — fabricated-quote hard-fail persists the block and marks
  `citation.verification_result = 'fail'`; never silently promoted.
- **Honest absence** — no gap/absence claims are made; `search_coverage_record` is deferred.
- **Segmentation policy column is not optional** — omitting it now requires a later data
  migration against immutable chunk rows.
- Deferred seams stay as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: the schema gate above is unapproved; a new table beyond the four listed
is needed; the slice tempts a real model call, real `search` egress, or any EB component logic;
scope would grow past the corpus data layer + grounding seam flip; or the turn/token budget is
spent.

## Acceptance checks

1. `make verify` green (test · typecheck · lint · build).
2. `ingest_upload` creates `source_snapshot` + `chunk` + `project_source_snapshot` rows; a
   second call with identical content creates a **new** snapshot (no silent dedup).
3. `produce_grounded_block` with a DB-seeded chunk: grounding **pass** produces a `citation` row
   with a non-null `chunk_id` FK pointing to the seeded chunk.
4. `produce_grounded_block` with a fabricated quote against that chunk: **hard fail** —
   `GroundingError` raised; `citation.verification_result = 'fail'`; `chunk_id` FK still set.
5. `annotation.annotation_type = 'citation'` rows have a corresponding `citation` row; orphaned
   annotations (no `citation` row) are caught by a test.
6. `/okf validate docs/knowledge` clean (no new `.md` concept files in this slice, so a pass is
   expected — verify anyway).

## Verification evidence expected

In [verification.md](verification.md): `make verify` output; named-test results; exact
end-to-end command (ingest → grounded block → inspect rows); diff summary; public-safety
confirmation (synthetic text only, no real source content, no egress); known gaps.

## Risk tier & review focus

**Tier 3** — schema gate (new tables + migration) + public interface change on
`produce_grounded_block`. Rollback = revert the PR; `alembic downgrade -1`; no real data, no
consumers, greenfield.

Review focus: schema shape vs spec (especially `segmentation_policy`, `text_basis`,
`source_locator` presence); upload-dedup behaviour (new snapshot on each call, not silent dedup);
citation FK integrity (no orphaned citations, no JSONB-only references); fabricated-quote
hard-fail still fires; scope — no EB component logic snuck in.
