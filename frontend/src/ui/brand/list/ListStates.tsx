import type { ReactNode } from "react";

import { Button } from "../Button";
import { cn } from "../cn";

/*
 * A list's frames (task 058, consolidation batch B): the empty, loading and
 * failed states every list and table shows in its own frame, defined once
 * and used by the Tasks, Projects and History lists and the Sources table.
 * A surface passes only its frame (`frameClassName`): the lists' hairline
 * box by default, the Sources table's rules above and below.
 */

/** The list frame: hairline paper, rows divided by Line hairlines. */
export const LIST_FRAME_CLASS = "border border-line-2 bg-paper";

/** A control inside a list's frame: the 40 px ghost at the ghost's own Meta
 *  size (the header's controls are Body; this one is not in the header).
 *  Try again, Retry, Clear filters. */
export const LIST_CONTROL_CLASS = "h-10 whitespace-nowrap px-3 py-0 text-meta";

/**
 * The list loading: the list's own frame and row shape (lead ruling), so
 * the rows arrive into it rather than replacing a different page. Five rows
 * of the real row's height, 56 px (84 px below md, two lines), each with
 * the system's placeholder bar where the name will sit. The bars breathe,
 * and hold still under reduced motion.
 *
 * Args:
 *   label: The list's name while it loads ("Loading tasks").
 */
export function ListSkeleton({ label }: { label: string }) {
  return (
    <ul role="list" aria-busy="true" aria-label={label} className={LIST_FRAME_CLASS}>
      {Array.from({ length: 5 }).map((_, index) => (
        <li
          key={index}
          aria-hidden="true"
          className="flex h-14 flex-col justify-center gap-y-1 border-b border-line px-4 last:border-b-0 max-md:h-21"
        >
          <span className="flex h-7 items-center max-md:h-6">
            <span className="placeholder-bar h-2.5 w-2/5" />
          </span>
          <span className="hidden h-7 items-center max-md:flex">
            <span className="placeholder-bar h-2.5 w-1/4" />
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * An empty list: the list's frame with nothing in it, left-aligned at the
 * list's edge, hairline only (no card shadow). A label, then one plain
 * sentence when there is one, and at the right the way out when there is
 * one (Clear filters). The page's primary stays the way forward.
 *
 * Args:
 *   label: What the list holds none of ("No tasks yet").
 *   children: The one plain sentence, or nothing.
 *   action: A control at the frame's right end, or nothing.
 *   frameClassName: The surface's frame, when it is not the lists' box.
 */
export function ListEmpty({
  label,
  children,
  action,
  frameClassName = LIST_FRAME_CLASS,
}: {
  label: string;
  children?: ReactNode;
  action?: ReactNode;
  frameClassName?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        frameClassName,
        "flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-6 pl-4",
        action != null ? "pr-1" : "pr-4",
      )}
    >
      <div>
        <p className="text-body font-semibold text-navy">{label}</p>
        {children != null && <p className="mt-1 text-body text-grey">{children}</p>}
      </div>
      {action}
    </div>
  );
}

/**
 * A list that failed to load: the list's frame, the sentence, and a 40 px
 * ghost that asks again (lead ruling, 2026-11-05).
 *
 * Args:
 *   children: The sentence that says what failed.
 *   actionLabel: The ghost's words ("Try again", "Retry").
 *   onRetry: Asks again.
 *   frameClassName: The surface's frame, when it is not the lists' box.
 */
export function ListError({
  children,
  actionLabel,
  onRetry,
  frameClassName = LIST_FRAME_CLASS,
}: {
  children: ReactNode;
  actionLabel: string;
  onRetry: () => void;
  frameClassName?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(frameClassName, "flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-4 pl-4 pr-1")}
    >
      <p className="text-body text-navy">{children}</p>
      <Button variant="ghost" className={LIST_CONTROL_CLASS} onClick={onRetry}>
        {actionLabel}
      </Button>
    </div>
  );
}
