import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "../brand/cn";
import { portalContainer } from "./portal";

/*
 * Popover (Radix copy-in) — the click rung of the citation ladder.
 * Radix owns focus return, Esc and outside-dismiss.
 */

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export function PopoverContent({
  className,
  collisionPadding = 16,
  ...props
}: ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal container={portalContainer()}>
      <PopoverPrimitive.Content
        sideOffset={6}
        // Keeps the page's 16 px gutter on a phone.
        collisionPadding={collisionPadding}
        className={cn(
          "z-50 w-96 max-w-[92vw] border border-line-2 bg-paper p-4",
          "text-meta text-ink shadow-overlay",
          "focus-visible:outline-none",
          // Scales in from its trigger (never from nothing): 150ms, strong ease-out.
          "origin-[var(--radix-popover-content-transform-origin)] transition-[opacity,transform] duration-150 ease-out-strong starting:scale-[0.97] starting:opacity-0",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
