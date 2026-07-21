import type { components } from "./gen/types";

export type SseFrame = components["schemas"]["SseFrame"];

const SSE_FRAME_TYPES: ReadonlySet<SseFrame["type"]> = new Set([
  "run.status",
  "stage.started",
  "stage.completed",
  "stage.failed",
  "checkin.pending",
  "checkin.resolved",
  "plan.updated",
  "project.updated",
  "tick",
] satisfies SseFrame["type"][]);

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
  if (typeof type !== "string" || !SSE_FRAME_TYPES.has(type as SseFrame["type"])) {
    return null;
  }
  // Narrow seam: the discriminator is verified; the remaining shape is
  // trusted from the generated contract rather than field-by-field checked.
  return payload as SseFrame;
}
