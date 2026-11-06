import type { SelectHTMLAttributes } from "react";

import { cn } from "../../ui/brand/cn";
import { ChevronIcon } from "../../ui/brand/icons";

/**
 * A native select in the field's skin (round 10, finding 13; DESIGN.md
 * § Inputs): Paper, a 1 px Line 2 border, square, Body text, 40 px tall, the
 * 12 px chevron from the icon module at the right in place of the browser's
 * own arrow. The longlist grid's Columns and the shortlist's risk appetite.
 * It stays a native `<select>`, so the keyboard and a phone's picker behave
 * as the platform does.
 */
export function FieldSelect({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={cn("relative inline-flex max-w-full", className)}>
      <select
        {...props}
        className={
          "h-10 w-full min-w-0 cursor-pointer appearance-none truncate border border-line-2 bg-paper pr-9 pl-3 " +
          "text-body text-ink disabled:cursor-default disabled:bg-ground disabled:text-grey"
        }
      >
        {children}
      </select>
      <ChevronIcon
        size={12}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90 text-grey"
      />
    </span>
  );
}
