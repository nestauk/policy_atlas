import { PROJECT, TASK } from "./vocabulary";

/** Machine-readable conflict conditions surfaced by the API (the real
 *  `ApiConflict` codes raised by the backend — see `runs.py`,
 *  `task_agent.py`, `check_ins.py`). */
type ConflictCode =
  | "run_active"
  | "capacity"
  | "task_agent_turn_in_progress"
  | "stale_turn"
  | "already_answered"
  | "plan_stale"
  | "no_completed_run"
  | "chat_turn_in_progress"
  | "chat_capacity"
  | "visibility_conflict"
  | "link_project_mismatch"
  | "link_source_unfinished"
  | "link_source_capability";

/** Human-readable, trigger-local conflict copy — the one place this
 *  copy lives; call sites wire it in rather than inlining their own. */
export const conflictSentences: Record<ConflictCode, string> = {
  run_active: `A run is already active for this ${TASK.lower}. Refresh to see its current progress.`,
  capacity: "This run cannot start yet because the workspace is at capacity. Try again shortly.",
  task_agent_turn_in_progress: "That Task Agent turn is still being prepared. Refresh to see the completed turn.",
  stale_turn: "That Task Agent turn is no longer the latest one. Refresh the Task Agent conversation and try again.",
  already_answered: "This check-in has already been answered. Refresh to see the recorded decision.",
  plan_stale:
    "The plan predates your latest Task Agent message. Review the updated plan, then start.",
  no_completed_run: `This ${TASK.lower} needs a completed run before you can chat about the evidence.`,
  chat_turn_in_progress: "A chat turn is already running. Refresh to see it finish.",
  chat_capacity: "Chat is at capacity right now. Try again shortly.",
  // Task 033 i.5, contract § 11 (lead-owned, binding): a Task's own
  // visibility can't diverge from the Project it belongs to.
  visibility_conflict:
    `This ${TASK.one} is in a ${PROJECT.one}. Change the ${PROJECT.one}'s visibility, or leave the ${TASK.one} out of the ${PROJECT.one}.`,
  // Task 044 (C11, C12): the two rules a Link must satisfy when it is written.
  link_project_mismatch: `That Evidence search is in a different ${PROJECT.one}. Put both in the same ${PROJECT.one} first.`,
  link_source_unfinished: "That Evidence search has not finished a run yet. Wait for it, then try again.",
  link_source_capability: "A task can only start from an Evidence search task.",
};

/**
 * Type guard: does `code` name one of the API's known conflict codes?
 *
 * Args:
 *   code: A `error.code` value pulled off a thrown query/mutation error.
 *
 * Returns:
 *   Whether `code` is a key of `conflictSentences`.
 */
export function isConflictCode(code: string | undefined | null): code is ConflictCode {
  return code !== undefined && code !== null && code in conflictSentences;
}

/**
 * Extract the API's machine-readable error `code` from a thrown
 * query/mutation error envelope (`{ error: { code, message } }`).
 *
 * Args:
 *   error: The `error` thrown by a query or mutation function.
 *
 * Returns:
 *   The envelope's `code`, or `undefined` if the shape doesn't match.
 */
export function errorCode(error: unknown): string | undefined {
  return (error as { error?: { code?: string } } | null | undefined)?.error?.code;
}

/** Field-indexed messages suitable for input-adjacent rendering. */
export type FieldErrorMap = Record<string, string[]>;

/**
 * Convert the API's 422 validation envelope to field-indexed messages.
 *
 * Args:
 *   envelope: Unknown response body received from the API.
 *
 * Returns:
 *   Messages keyed by the final string location segment (for example, `name`).
 */
export function fieldErrorsFromEnvelope(envelope: unknown): FieldErrorMap {
  if (!isRecord(envelope) || !Array.isArray(envelope.detail)) return {};

  return envelope.detail.reduce<FieldErrorMap>((errors, detail) => {
    if (!isRecord(detail) || !Array.isArray(detail.loc) || typeof detail.msg !== "string") return errors;
    const field = [...detail.loc].reverse().find((part): part is string => typeof part === "string");
    if (!field) return errors;
    return { ...errors, [field]: [...(errors[field] ?? []), detail.msg] };
  }, {});
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
