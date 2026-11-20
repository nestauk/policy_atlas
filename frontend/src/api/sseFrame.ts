import type { components } from "./gen/types";

export type SseFrame = components["schemas"]["SseFrame"];

// Every frame type must have an entry: the type check fails when the generated
// contract gains a type that is missing here, because a frame that is not in this
// list is dropped before the reducer sees it.
const SSE_FRAME_TYPE_RECORD: Record<SseFrame["type"], true> = {
  "run.status": true,
  "stage.started": true,
  "stage.completed": true,
  "stage.failed": true,
  "artefact.skeleton": true,
  "artefact.section_started": true,
  "artefact.section_completed": true,
  "checkin.pending": true,
  "checkin.resolved": true,
  "plan.updated": true,
  "task.updated": true,
  "tick": true,
  "artefact.section_delta": true,
  "artefact.section_revising": true,
  "artefact.section_sources": true,
  "artefact.section_claim": true,
  "artefact.section_card": true,
  "artefact.source_note": true,
  "search.query": true,
  "characterise.themes": true,
  "toc.sketch": true,
};
const SSE_FRAME_TYPES: ReadonlySet<string> = new Set(Object.keys(SSE_FRAME_TYPE_RECORD));

/**
 * The one narrow seam in the SSE pipeline: parse a `data:` payload as JSON,
 * then trust the server contract for everything beyond `.type` once that
 * discriminator is one of the pinned frame-type strings. Anything else
 * (malformed JSON, an unrecognised `type`, a non-object payload) is
 * dropped rather than forwarded — a frame type unknown to this build is
 * safer ignored than mis-narrowed.
 */
export function narrowSseFrame(payload: unknown): SseFrame | null {
  if (typeof payload !== "object" || payload === null) return null;
  const { type } = payload as { type?: unknown };
  if (typeof type !== "string" || !SSE_FRAME_TYPES.has(type)) {
    return null;
  }
  // Narrow seam: the discriminator is verified; the remaining shape is
  // trusted from the generated contract rather than field-by-field checked.
  return payload as SseFrame;
}
