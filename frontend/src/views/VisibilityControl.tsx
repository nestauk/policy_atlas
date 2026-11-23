import type { components } from "../api/gen/types";
import { Button } from "../ui/brand/Button";
import { TASK } from "../lib/vocabulary";

type Visibility = components["schemas"]["TaskOut"]["visibility"];

/**
 * The one binding visibility-outcome line (stated, not asked). A project cascade appends how many
 * Tasks follow, singular-correct; a plain Task change has no count.
 */
export function visibilityOutcomeLine(next: Visibility, taskCount?: number): string {
  const base = next === "private" ? "Now private." : "Now shared with your organisation.";
  if (taskCount === undefined) return base;
  return taskCount === 1
    ? `${base} 1 ${TASK.one} follows.`
    : `${base} ${taskCount} ${TASK.many} follow.`;
}

/**
 * Owner-only visibility toggle.
 *
 * Renders nothing unless the caller owns the row.
 */
export function VisibilityControl({
  visibility,
  isOwner,
  pending,
  onChange,
  className,
  variant = "ghost",
}: {
  visibility: Visibility;
  isOwner: boolean;
  pending: boolean;
  onChange: (next: Visibility) => void;
  className?: string;
  variant?: "ghost" | "primary";
}) {
  if (!isOwner) return null;
  const next: Visibility = visibility === "private" ? "org" : "private";
  const label = visibility === "private" ? "Share with organisation" : "Make private";
  return (
    <Button
      type="button"
      variant={variant}
      size="sm"
      disabled={pending}
      onClick={() => onChange(next)}
      className={className}
    >
      {label}
    </Button>
  );
}
