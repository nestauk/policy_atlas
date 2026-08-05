import type { FieldErrorMap } from "../../lib/errors";

/** Input-adjacent rendering for normalized 422 validation messages. */
export function FieldErrors({ field, errors }: { field: string; errors: FieldErrorMap }) {
  const messages = errors[field] ?? [];
  if (messages.length === 0) return null;
  return (
    <ul id={`${field}-errors`} role="alert" className="mt-1 text-caption text-red">
      {messages.map((message) => <li key={message}>{message}</li>)}
    </ul>
  );
}
