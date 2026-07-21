import type { HTMLAttributes } from "react";

import { cn } from "./cn";

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
        "text-[11px] font-extrabold uppercase tracking-[0.06em] text-grey",
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

const STATUS_DOT_TONES = {
  running: "bg-yellow",
  complete: "bg-green",
  paused: "bg-orange",
  idle: "bg-line-2",
  failed: "bg-red",
} as const;

/** Status dot — always pair with a text label (never colour alone). */
export function StatusDot({
  tone,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone: keyof typeof STATUS_DOT_TONES }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-2 flex-none rounded-full",
        STATUS_DOT_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}
