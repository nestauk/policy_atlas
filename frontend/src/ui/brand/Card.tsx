import type { HTMLAttributes } from "react";

import { cn } from "./cn";
import { FoldMarkAnimated } from "./FoldMarkAnimated";
import { PANE_LABEL_CLASS } from "./label";

/** Paper surface on the app ground (hifi.css .screen): 0 radius, hairline
 * border, the soft navy-tinted shadow. Composable — no configuration. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "border border-line-2 bg-paper",
        "shadow-[0_1px_3px_rgba(15,41,74,0.05),0_8px_24px_rgba(15,41,74,0.04)]",
        className,
      )}
      {...props}
    />
  );
}

/** Uppercase pane heading (hifi.css .pane-h). */
export function PaneHeading({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center justify-between px-4 pb-2.5 pt-3.5",
        PANE_LABEL_CLASS,
        className,
      )}
      {...props}
    />
  );
}

/** Hairline divider. */
export function Divider({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("h-px bg-line", className)} {...props} />;
}

const STATUS_MARK_TONES = {
  running: "bg-blue",
  complete: "bg-green",
  paused: "bg-orange",
  idle: "bg-line-2",
  failed: "bg-red",
} as const;

/** The colour a status mark takes: live, done, waiting, not started, failed. */
export type StatusTone = keyof typeof STATUS_MARK_TONES;

/**
 * The status mark (task 058; DESIGN.md § Status mark): a 6 px square with
 * square corners, always followed by its word, never colour alone. Electric
 * Blue while a run is live, Green when it ended well, Orange while it waits
 * on a person, Red when it failed, Line 2 when nothing has started.
 *
 * Args:
 *   tone: Which state the mark shows.
 *   breathing: True while updates are arriving (the caller's freshness
 *     rule); only a live mark breathes, and it holds still under reduced
 *     motion.
 */
export function StatusMark({
  tone,
  breathing = false,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone: StatusTone; breathing?: boolean }) {
  return (
    <span
      aria-hidden="true"
      data-tone={tone}
      className={cn(
        // A mark that changes state (a step landing: blue to green) eases
        // its colour over 150 ms (round 9).
        "inline-block size-1.5 flex-none transition-colors duration-150 ease-[ease]",
        STATUS_MARK_TONES[tone],
        breathing && tone === "running" && "anim-breathe",
        className,
      )}
      {...props}
    />
  );
}

/** The live mark's size in a line of text; the conversation rail uses the
 *  brand size (17 px) instead. */
export const LIVE_MARK_TEXT_SIZE = 14;

/**
 * The live mark (task 058; annex § Owner round after the trace, item 6):
 * wherever a run is live, its mark is the Policy Atlas fold mark turning.
 * It holds still (the shut blue diamond) under reduced motion. The static
 * states keep the 6 px square (`StatusMark`).
 *
 * Args:
 *   size: 14 px in a line of text (the default), 17 px in the rail.
 */
export function LiveMark({
  size = LIVE_MARK_TEXT_SIZE,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { size?: number }) {
  return (
    <span
      aria-hidden="true"
      data-live-mark=""
      className={cn("inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      {...props}
    >
      <FoldMarkAnimated size={size} onDark={false} />
    </span>
  );
}
