import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "../brand/cn";

/*
 * Popover (Radix copy-in) — the click rung of the citation ladder.
 * Radix owns focus return, Esc and outside-dismiss.
 */

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export function PopoverContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        sideOffset={6}
        className={cn(
          "z-50 w-96 max-w-[92vw] border border-line-2 bg-paper p-4",
          "text-meta text-ink shadow-[0_10px_30px_rgba(15,41,74,0.14)]",
          "focus-visible:outline-none",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
