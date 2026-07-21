/** Machine-readable conflict conditions surfaced by the API. */
export type ConflictCode = "run_active" | "capacity" | "turn_in_progress" | "answered";

/** Human-readable, trigger-local conflict copy. */
export const conflictSentences: Record<ConflictCode, string> = {
  run_active: "A run is already active for this project. Refresh to see its current progress.",
  capacity: "This run cannot start yet because the workspace is at capacity. Try again shortly.",
  turn_in_progress: "That planning turn is still being prepared. Refresh to see the completed turn.",
  answered: "This check-in has already been answered. Refresh to see the recorded decision.",
};

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
