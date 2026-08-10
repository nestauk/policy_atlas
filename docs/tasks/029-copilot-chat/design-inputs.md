# 029 design inputs — PR #35 chat mockup (rev 2.6)

PR #35 (`demo-live-run-test-1`, colleague's demo-frontend refactor, capabilities →
artifacts IA) re-read 2026-08-10 specifically for its **chat** ideas, now that the
co-pilot slice it was routed to (027 adjudication) is being contracted. The container
model (multi-thread rail + Chats library + per-thread artifact context) was already
adopted at rev 2; this pass mines the interaction detail. ⚠️ The branch itself is
design-input only — never merge/run (burned dev keypair in its history).

## Adopted into the contract (rev 2.6)

- **Context chips with "Whole project" as the zero-state** (ContextBar): the chat's
  entry artefact renders as a removable chip between stream and composer; no chips =
  "Whole project". Chip click navigates to the artefact. This is the concrete UX for
  the rev-2 pin "artefact is an entry point and provenance, never a scope fence."
  The `@ Add context` multi-artifact picker is **deferred to workspace-cluster**
  (single-artefact era; and the mockup's own checkbox-list-of-all-artifacts doesn't
  scale — needs typeahead when it lands).
- **URL-addressable conversations**: thread identity in the route, so library rows,
  artefact "ask" affordances and shared links deep-link to a conversation. (The
  mockup lacks this and its reopen flow relies on in-memory state — its own listed
  dead end.)

## Build-time presentation details (follow at strand 6 build; not contract pins)

- Threads as a horizontal tab strip; ✕ on hover; close = archive (never destroy);
  focus falls to the neighbouring tab; the rail never empties (blank chat
  auto-created); a blank "New chat" tab is reused rather than duplicated.
- Chats library rows: 2-line last-message preview · context chip echo · relative
  time · Enter-to-open focus ring. (The mockup's "Open" badge was cut at the
  2026-08-10 mockup review — tab presence and the preview carry it.)
- Force-expand-rail signal so remote affordances (artefact "Ask about this") can pop
  the collapsed rail; drag-resize with min/max + collapse-to-spine (027/028 rail
  machinery already does most of this).
- Assistant prose on a ~52ch measure, bubbles only for user messages (matches the
  028 thread styling).
- New chat inherits the open artefact as its entry context.
- Planning-conversation titles derive from the plan/run (the mockup's job-thread
  auto-titling, mapped onto our lifecycle).

## Already covered by stronger contract pins

- Progress affordance: mockup's single planner-progress line → our typed progress
  events + activity summary (rev 2.3).
- Composer disabled-while-thinking → our stop button + cancelled-partial persistence
  (rev 2.3/2.4); the mockup's no-interrupt composer is one of its own dead ends.
- Undeletable primary thread → our planning conversations are lifecycle-created and
  non-archivable by kind, not by special-cased id.
- Start-a-run-from-chat (mockup's job picker inside chat) → out of scope by owner
  decision: chats never mutate; the planning conversation is the run channel, chat
  hands off with a link.
- Check-in cards in the rail → already shipped in 027 rev 4 (real, not mock).

## Declined (with the mockup's own evidence where it applies)

- `primary` vs `mock` thread-type split threaded through the store — one conversation
  entity with `kind` is the model; no special-cased ids.
- Display-string timestamps + parallel sort clock — real timestamps, format at render;
  `turn_index` orders turns.
- Suggested quick-reply chips — copy-diet decline stands (also declined at V2 review).
- Hard delete in the library — archive/reopen only (house rule, rev 2 pin).
- Module-scope mutable state / in-memory-only threads — the entire point of the
  server-side conversation store.
- No markdown/citations in chat (the mockup renders none) — ours is plain prose by
  security pin but **with** durable-id citations + tier chip; the mockup's citation
  absence is a gap, not a precedent.
