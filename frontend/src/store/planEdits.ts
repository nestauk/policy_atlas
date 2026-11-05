import { useCallback, useSyncExternalStore } from "react";

import type { PlanOverlay } from "../views/workspace/planOverlay";

/**
 * The Evidence search plan's unsaved edits, per task (task 058, N20). They
 * live here, not in the Agent tab's view, so leaving the tab and coming back
 * keeps them; they apply when the run starts, as before. Held for the page's
 * life only: a reload starts from the saved plan.
 */
const overlays = new Map<string, PlanOverlay>();
const listeners = new Set<() => void>();
const EMPTY: PlanOverlay = {};

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Replace a task's plan edits.
 *
 * Args:
 *   taskId: The task the edits belong to.
 *   overlay: The edits; an empty object clears them.
 */
export function setPlanEdits(taskId: string, overlay: PlanOverlay): void {
  if (Object.keys(overlay).length === 0) overlays.delete(taskId);
  else overlays.set(taskId, overlay);
  for (const listener of listeners) listener();
}

/**
 * Read and change a task's plan edits.
 *
 * Args:
 *   taskId: The task the edits belong to.
 *
 * Returns:
 *   The current edits and a setter, like `useState`'s pair.
 */
export function usePlanEdits(taskId: string): [PlanOverlay, (overlay: PlanOverlay) => void] {
  const overlay = useSyncExternalStore(
    subscribe,
    () => overlays.get(taskId) ?? EMPTY,
    () => EMPTY,
  );
  const set = useCallback((next: PlanOverlay) => setPlanEdits(taskId, next), [taskId]);
  return [overlay, set];
}
