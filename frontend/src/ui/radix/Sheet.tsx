import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { cn } from "../brand/cn";

/*
 * Slide-over sheet (shadcn-style copy-in over Radix Dialog) — the source
 * dossier's surface. Radix owns focus trap, Esc, overlay dismiss, ARIA;
 * the skin is ours: 0 radius, paper on a navy scrim, hairline border.
 */

export const Sheet = DialogPrimitive.Root;
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
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-navy/40 data-[state=open]:animate-in data-[state=open]:fade-in" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-y-0 z-50 flex w-full max-w-xl flex-col overflow-y-auto",
          "border-line-2 bg-paper shadow-[0_10px_30px_rgba(15,41,74,0.14)]",
          side === "right" ? "right-0 border-l" : "left-0 border-r",
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
          <DialogPrimitive.Close
            aria-label="Close panel"
            className="cursor-pointer p-1.5 text-grey hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
          >
            ✕
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
