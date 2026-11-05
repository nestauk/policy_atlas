import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useEffect, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "../brand/cn";
import { prefersReducedMotion } from "../motion/motion";
import { CloseButton } from "../brand/CloseButton";

/*
 * Slide-over sheet (shadcn-style copy-in over Radix Dialog) — the source
 * dossier's surface. Radix owns focus trap, Esc, overlay dismiss, ARIA;
 * the skin is ours: 0 radius, paper on a navy scrim, hairline border.
 */

/** How long the sheet takes to leave: faster than it came (260 ms). */
const SHEET_EXIT_MS = 200;

/** Whether the exit can run (not under reduced motion, nor where Web
 *  Animations are missing, as in the tests' jsdom). */
function exitRuns(): boolean {
  return typeof document !== "undefined" && typeof document.body?.animate === "function" && !prefersReducedMotion();
}

/**
 * The sheet's root. It leaves the way it came (task 058, round 9; the
 * animation sweep's entry 10): asked to close, it plays its exit (200 ms on
 * the drawer curve along its own edge, the scrim fading with it) before it
 * tells the caller, so a caller that unmounts it on close still sees it go.
 * Under reduced motion it closes at once.
 */
export function Sheet({ open, onOpenChange, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Root>) {
  const [closing, setClosing] = useState(false);
  useEffect(() => {
    if (!closing) return undefined;
    const id = window.setTimeout(() => {
      setClosing(false);
      onOpenChange?.(false);
    }, SHEET_EXIT_MS);
    return () => window.clearTimeout(id);
  }, [closing, onOpenChange]);
  return (
    <DialogPrimitive.Root
      open={open === undefined ? undefined : open && !closing}
      onOpenChange={(next) => {
        if (next || !exitRuns()) onOpenChange?.(next);
        else setClosing(true);
      }}
      {...props}
    />
  );
}
export const SheetTrigger = DialogPrimitive.Trigger;

export function SheetContent({
  className,
  children,
  title,
  description,
  side = "right",
  ...props
}: ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  title: string;
  description?: string;
  side?: "right" | "left";
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-navy/40 transition-opacity duration-200 ease-out starting:opacity-0 data-[state=closed]:animate-[scrim-out_200ms_ease-out_forwards]" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-y-0 z-50 flex w-full max-w-xl flex-col overflow-y-auto",
          "border-line-2 bg-paper shadow-[0_10px_30px_rgba(15,41,74,0.14)]",
          // Slides in from its edge on the drawer curve; transform only.
          "transition-transform duration-[260ms] ease-drawer",
          side === "right" ? "right-0 border-l starting:translate-x-full" : "left-0 border-r starting:-translate-x-full",
          // Leaves along the same edge, faster than it came (round 9).
          side === "right"
            ? "data-[state=closed]:animate-[sheet-out-right_200ms_var(--ease-drawer)_forwards]"
            : "data-[state=closed]:animate-[sheet-out-left_200ms_var(--ease-drawer)_forwards]",
          // Below md both sides collapse to a Wikipedia-style bottom sheet:
          // pinned to the bottom edge, full width, content-driven height
          // capped under half the viewport, sliding up instead of across.
          "max-md:inset-x-0 max-md:inset-y-auto max-md:bottom-0 max-md:max-h-[45svh] max-md:max-w-none",
          "max-md:border-x-0 max-md:border-t",
          "max-md:starting:translate-x-0 max-md:starting:translate-y-full",
          "max-md:data-[state=closed]:animate-[sheet-out-down_200ms_var(--ease-drawer)_forwards]",
          className,
        )}
        {...props}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <DialogPrimitive.Title className="font-display text-lead font-bold text-navy">
              {title}
            </DialogPrimitive.Title>
            {description === undefined ? (
              <VisuallyHiddenDescription />
            ) : (
              <DialogPrimitive.Description className="mt-1 text-body text-grey">
                {description}
              </DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close asChild>
            <CloseButton aria-label="Close panel" />
          </DialogPrimitive.Close>
        </div>
        <div className="flex-1 px-5 py-4">{children}</div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function VisuallyHiddenDescription(): ReactNode {
  return (
    <DialogPrimitive.Description className="sr-only">
      Detail panel
    </DialogPrimitive.Description>
  );
}
