/**
 * The Sources subtab a reader last chose on a task (owner, round 10).
 *
 * Before the reader has chosen one, the Sources tab lands by stage
 * (`sourcesLanding`). Once they pick a subtab on this task, the Sources tab
 * returns them there, live or done, until they pick another. The choice is a
 * per-viewer convenience kept in `localStorage`, one key per task; a storage
 * that is missing, blocked or full simply means the landing rule applies.
 */

/** The subtab paths after `/sources` ("" is Themes, the index). */
export type SourcesSubtab = "" | "/landscape" | "/all" | "/findings";

const SUBTABS: readonly SourcesSubtab[] = ["", "/landscape", "/all", "/findings"];

const key = (taskId: string) => `policy-atlas:sources-subtab:${taskId}`;

/**
 * Remember the subtab the reader chose on a task.
 *
 * Args:
 *   taskId: The task.
 *   subtab: The path after `/sources`.
 */
export function rememberSourcesSubtab(taskId: string, subtab: SourcesSubtab): void {
  try {
    window.localStorage.setItem(key(taskId), subtab === "" ? "themes" : subtab);
  } catch {
    // A per-viewer convenience: without storage the landing rule applies.
  }
}

/**
 * The subtab the reader last chose on a task, if any.
 *
 * Args:
 *   taskId: The task.
 *
 * Returns:
 *   The path after `/sources`, or `null` when nothing was chosen or the
 *   storage cannot be read.
 */
export function rememberedSourcesSubtab(taskId: string): SourcesSubtab | null {
  try {
    const stored = window.localStorage.getItem(key(taskId));
    if (stored === null) return null;
    const subtab = stored === "themes" ? "" : stored;
    return SUBTABS.find((candidate) => candidate === subtab) ?? null;
  } catch {
    return null;
  }
}
