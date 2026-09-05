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
}: Omit<ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>, "content"> & {
  // Omit the native HTML `content` string attribute — ours is a ReactNode.
  content: ReactNode;
  children: ReactNode;
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          collisionPadding={8}
          className={cn(
            // The system's marker — a 2px blue rule on the leading edge, as on
            // a selected row — on a tight paper card; caption scale, navy ink.
            "z-50 max-w-xs border border-line-2 border-l-2 border-l-blue bg-paper px-2.5 py-1.5",
            "text-caption leading-snug text-navy shadow-[0_4px_16px_rgba(15,41,74,0.12)]",
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
