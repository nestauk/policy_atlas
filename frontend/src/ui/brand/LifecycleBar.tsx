import type { ReactNode } from "react";
import { NavLink } from "react-router";

import { cn } from "./cn";

export type LifecycleBarItem = {
  tab: string;
  label: string;
  to: string;
  locked: boolean;
  /** Rendered beside the label when the tab wants attention (a pending check-in). */
  marker?: ReactNode;
};

/**
 * The five task stages, with the unavailable ones visibly locked.
 *
 * A locked stage is *rendered* — the reader can see the shape of the whole
 * lifecycle from the first moment, which is what makes the progression
 * legible — but it is not a link, is not focusable, and carries
 * `aria-disabled` so it reads as unavailable rather than broken.
 */
export function LifecycleBar({ items, hint }: { items: readonly LifecycleBarItem[]; hint: string }) {
  return (
    <div className="flex items-end gap-5">
      {items.map((item) =>
        item.locked ? (
          <span
            key={item.tab}
            aria-disabled="true"
            title={hint}
            className="inline-flex cursor-not-allowed items-center border-b-[3px] border-transparent pb-1 text-lead font-semibold leading-none text-line-2 select-none"
          >
            {item.label}
            <span className="sr-only"> — {hint}</span>
          </span>
        ) : (
          <NavLink
            key={item.tab}
            to={item.to}
            // Plan is the bare project path, so without `end` it would stay
            // active on every stage beneath it.
            end={item.tab === "plan"}
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-1.5 border-b-[3px] border-transparent pb-1 text-lead font-semibold leading-none text-grey no-underline hover:text-navy",
                isActive && "border-blue text-navy",
              )
            }
          >
            {item.label}
            {item.marker}
          </NavLink>
        ),
      )}
    </div>
  );
}
