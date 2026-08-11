/** Machine-readable conflict conditions surfaced by the API (the real
 *  `ApiConflict` codes raised by the backend — see `runs.py`,
 *  `planning.py`, `check_ins.py`). */
export type ConflictCode =
  | "run_active"
  | "capacity"
  | "planning_turn_in_progress"
  | "stale_turn"
  | "already_answered"
  | "plan_stale";

/** Human-readable, trigger-local conflict copy — the one place this
 *  copy lives; call sites wire it in rather than inlining their own. */
export const conflictSentences: Record<ConflictCode, string> = {
  run_active: "A run is already active for this project. Refresh to see its current progress.",
  capacity: "This run cannot start yet because the workspace is at capacity. Try again shortly.",
  planning_turn_in_progress: "That planning turn is still being prepared. Refresh to see the completed turn.",
  stale_turn: "That planning turn is no longer the latest one. Refresh the planning conversation and try again.",
  already_answered: "This check-in has already been answered. Refresh to see the recorded decision.",
  plan_stale:
    "The plan predates your latest planning message. Review the updated plan, then start.",
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
