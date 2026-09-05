import type { components } from "../api/gen/types";
import { Button } from "../ui/brand/Button";

type Visibility = components["schemas"]["TaskOut"]["visibility"];

/**
 * The one binding visibility-outcome line (contract § 11, rubric 41 —
 * lead-owned copy, stated not asked). A project cascade appends how many
 * Tasks follow, singular-correct; a plain Task change has no count.
 */
export function visibilityOutcomeLine(next: Visibility, taskCount?: number): string {
  const base = next === "private" ? "Now private." : "Now shared with your organisation.";
  if (taskCount === undefined) return base;
  return taskCount === 1 ? `${base} 1 Task follows.` : `${base} ${taskCount} Tasks follow.`;
}

/**
 * Owner-only visibility toggle (task 033 phase 10b).
 *
 * Renders nothing unless the caller owns the row: this introduces a brand
 * new mutation trigger, and Phase 10c — not this phase — is where the rest
 * of the affordance matrix (rename, archive, …) gets its owner gating. A
 * fresh control should not ship pre-broken in the same way.
 */
export function VisibilityControl({
  visibility,
  isOwner,
  pending,
  onChange,
  className,
}: {
  visibility: Visibility;
  isOwner: boolean;
  pending: boolean;
  onChange: (next: Visibility) => void;
  className?: string;
}) {
  if (!isOwner) return null;
  const next: Visibility = visibility === "private" ? "org" : "private";
  const label = visibility === "private" ? "Share with organisation" : "Make private";
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={pending}
      onClick={() => onChange(next)}
      className={className}
    >
      {label}
    </Button>
  );
}
