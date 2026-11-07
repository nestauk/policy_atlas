import type { ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router";

import { cn } from "./cn";
import { GROWING_RULE_ACTIVE_CLASS, GROWING_RULE_CLASS } from "./Nav";

const TAB_CLASS = cn(
  "inline-flex items-center gap-1.5 border-b-[3px] border-transparent pb-1 text-lead font-semibold leading-none text-grey no-underline transition-colors duration-150 hover:text-navy",
  GROWING_RULE_CLASS,
);
const TAB_ACTIVE_CLASS = cn(GROWING_RULE_ACTIVE_CLASS, "text-navy");

type LifecycleBarItem = {
  tab: string;
  label: string;
  to: string;
  locked: boolean;
  /** Rendered beside the label when the tab wants attention (a pending check-in). */
  marker?: ReactNode;
  /** When the link opens on a subview (Sources during a run), the tab still
   *  reads as current anywhere under this path. */
  activePrefix?: string;
};

/**
 * The five task stages, with the unavailable ones visibly locked.
 *
 * A locked stage is *rendered* — the reader can see the shape of the whole
 * lifecycle from the first moment, which is what makes the progression
 * legible — but it is not a link, is not focusable, and carries
 * `aria-disabled` so it reads as unavailable rather than broken.
 */
/**
 * Mobile placement of the same tabs (040 D2): a bar pinned under the content,
 * horizontally scrollable when the viewport is too narrow. Hidden from `md`
 * up, where LifecycleBar sits in the task NavBar instead.
 */
export function LifecycleBottomBar({
  items,
  hint,
  lead,
}: {
  items: readonly LifecycleBarItem[];
  hint: string;
  /** A control set before the tabs (the task's "Plan" control). */
  lead?: ReactNode;
}) {
  return (
    <nav
      aria-label="Task stages"
      // Its own View Transition layer, held still (round 13, owner).
      className="print-hide shrink-0 border-t border-line bg-paper md:hidden [view-transition-name:task-stages] [view-transition-class:shell-chrome]"
    >
      <div className="overflow-x-auto px-4 pt-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
        <LifecycleBar items={items} hint={hint} lead={lead} />
      </div>
    </nav>
  );
}

export function LifecycleBar({
  items,
  hint,
  lead,
}: {
  items: readonly LifecycleBarItem[];
  hint: string;
  /** A control set before the tabs, behind a hairline (the "Plan" control). */
  lead?: ReactNode;
}) {
  const { pathname } = useLocation();
  const under = (prefix: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);
  return (
    <div className="flex items-end gap-5">
      {lead !== undefined && (
        <span className="inline-flex items-end gap-5 after:mb-1 after:h-4 after:w-px after:bg-line-2 after:content-['']">
          {lead}
        </span>
      )}
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
        ) : item.activePrefix !== undefined ? (
          // The link opens a subview, so the tab's own match is the prefix.
          <Link
            key={item.tab}
            to={item.to}
            aria-current={under(item.activePrefix) ? "page" : undefined}
            className={cn(TAB_CLASS, under(item.activePrefix) && TAB_ACTIVE_CLASS)}
          >
            {item.label}
            {item.marker}
          </Link>
        ) : (
          <NavLink
            key={item.tab}
            to={item.to}
            // Agent is the bare task path, so without `end` it would stay
            // active on every stage beneath it.
            end={item.tab === "agent"}
            className={({ isActive }) => cn(TAB_CLASS, isActive && TAB_ACTIVE_CLASS)}
          >
            {item.label}
            {item.marker}
          </NavLink>
        ),
      )}
    </div>
  );
}
