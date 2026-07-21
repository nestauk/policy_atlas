import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { cn } from "../brand/cn";

/*
 * Tooltip (Radix copy-in) — the hover rung of the citation ladder.
 * Radix owns hover/focus timing and positioning; skin is navy-on-paper.
 */

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({
  content,
  children,
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> & {
  content: ReactNode;
  children: ReactNode;
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className={cn(
            "z-50 max-w-sm border border-line-2 bg-paper px-3 py-2",
            "text-xs text-ink shadow-[0_10px_30px_rgba(15,41,74,0.14)]",
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
