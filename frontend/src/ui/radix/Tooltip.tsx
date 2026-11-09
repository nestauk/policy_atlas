import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { useState, type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "../brand/cn";
import { portalContainer } from "./portal";

/*
 * Tooltip (Radix copy-in) — the hover rung of the citation ladder.
 * Radix owns hover/focus timing and positioning; skin is navy-on-paper.
 */

export const TooltipProvider = TooltipPrimitive.Provider;

/** A scroll within this long of the reader's own wheel, touch, scroll key
 *  or press is the reader's; any other scroll was caused by the page. */
export const SCROLL_INTENT_MS = 400;
/** A close that comes this soon after a scroll was caused by that scroll. */
const SCROLL_CLOSE_MS = 50;

const SCROLL_KEYS = new Set(["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]);

let lastScrollIntent = Number.NEGATIVE_INFINITY;
let lastScroll = Number.NEGATIVE_INFINITY;

// Registered when the module loads, before any tooltip opens, so these
// capture listeners run before the one Radix adds when a tooltip opens.
if (typeof window !== "undefined") {
  const intent = () => {
    lastScrollIntent = performance.now();
  };
  window.addEventListener("wheel", intent, { capture: true, passive: true });
  window.addEventListener("touchmove", intent, { capture: true, passive: true });
  window.addEventListener("pointerdown", intent, { capture: true, passive: true });
  window.addEventListener(
    "keydown",
    (event) => {
      if (SCROLL_KEYS.has(event.key)) intent();
    },
    { capture: true },
  );
  window.addEventListener(
    "scroll",
    () => {
      lastScroll = performance.now();
    },
    { capture: true, passive: true },
  );
}

/** Whether a close Radix asks for now comes from a scroll the reader did not
 *  make: content growing above the trigger while a run is live (the live
 *  report's sections fill in above the one being read) moves the pane, and
 *  Radix closes a tooltip on any scroll of its trigger's ancestors. */
function pageScrolledItself(): boolean {
  const now = performance.now();
  return now - lastScroll < SCROLL_CLOSE_MS && now - lastScrollIntent > SCROLL_INTENT_MS;
}

export function Tooltip({
  content,
  children,
  className,
  ...props
}: Omit<ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>, "content"> & {
  // Omit the native HTML `content` string attribute — ours is a ReactNode.
  content: ReactNode;
  children: ReactNode;
}) {
  // Controlled, so a close caused by the page scrolling itself can be
  // declined: the tooltip stays open (and follows its trigger) while content
  // grows above it, and closes on pointer leave, focus loss, Escape, a press
  // elsewhere or the reader's own scroll (task 058, round 8).
  const [open, setOpen] = useState(false);
  return (
    <TooltipPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!next && pageScrolledItself()) return;
        setOpen(next);
      }}
    >
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal container={portalContainer()}>
        <TooltipPrimitive.Content
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            // A tight paper card; caption scale, navy ink. Tooltips that
            // originate from an edge (the conversation rail) add the
            // system's 2px blue leading rule via `className`; ones that
            // sit in running text (citations) stay plain.
            "z-50 max-w-xs border border-line-2 bg-paper px-2.5 py-1.5",
            "text-caption leading-snug text-navy shadow-tooltip",
            "origin-[var(--radix-tooltip-content-transform-origin)] transition-[opacity,transform] duration-[125ms] ease-out-strong starting:scale-[0.97] starting:opacity-0",
            className,
          )}
          {...props}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
