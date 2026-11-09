/*
 * A reader's remembered choices (task 058, round 12 consolidation): small
 * per-viewer conveniences kept in `localStorage`, one key per task, under
 * one key scheme, `policy-atlas:<name>:<taskId>`. Each choice says how its
 * value is written and how a stored string is read back; a stored string
 * that is no longer a value reads as nothing. A storage that is missing,
 * blocked or full never throws: the write is skipped and the read gives
 * `null`, so the caller's own default applies. The Sources subtab and the
 * Sources page size use it.
 */

/**
 * The storage key for one choice on one task.
 *
 * Args:
 *   name: The choice's name ("sources-subtab").
 *   taskId: The task.
 *
 * Returns:
 *   `policy-atlas:<name>:<taskId>`.
 */
export function rememberedKey(name: string, taskId: string): string {
  return `policy-atlas:${name}:${taskId}`;
}

/** One remembered choice, per task. */
export interface RememberedChoice<T> {
  /** Remember the value the reader chose on a task. */
  remember(taskId: string, value: T): void;
  /** The value the reader last chose on a task, or `null` when nothing was
   *  chosen, the stored string is not a value, or the storage fails. */
  read(taskId: string): T | null;
}

/**
 * A choice remembered per task.
 *
 * Args:
 *   name: The choice's name, the middle of its key.
 *   codec: `write` turns a value into the stored string; `read` turns a
 *     stored string back into a value, or `null` when it is not one.
 *
 * Returns:
 *   The choice's `remember` and `read`.
 */
export function rememberedChoice<T>(
  name: string,
  codec: { write: (value: T) => string; read: (stored: string) => T | null },
): RememberedChoice<T> {
  return {
    remember(taskId, value) {
      try {
        window.localStorage.setItem(rememberedKey(name, taskId), codec.write(value));
      } catch {
        // A per-viewer convenience: without storage the default applies.
      }
    },
    read(taskId) {
      try {
        const stored = window.localStorage.getItem(rememberedKey(name, taskId));
        return stored === null ? null : codec.read(stored);
      } catch {
        return null;
      }
    },
  };
}
