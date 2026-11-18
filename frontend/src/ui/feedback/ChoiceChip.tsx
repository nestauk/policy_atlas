import type { ButtonHTMLAttributes } from "react";

import { cn } from "../brand/cn";

/**
 * A chip that the user selects: one answer among a few, or a reason.
 *
 * A real `<button>` with `aria-pressed`, at least 44 px tall (the feedback
 * brief's touch target). Idle, it has the outline box of the filter chips;
 * selected, it is filled Navy.
 *
 * Args:
 *   selected: Whether the chip is chosen.
 *   className: Width and placement.
 */
export function ChoiceChip({
  selected,
  className,
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> & { selected: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      className={cn(
        "inline-flex min-h-11 cursor-pointer items-center border px-3 text-left text-meta font-semibold transition-colors duration-150 disabled:cursor-default",
        selected
          ? "border-navy bg-navy text-paper"
          : "border-line-2 bg-paper text-navy hover:bg-hover-fill",
        className,
      )}
      {...props}
    />
  );
}
