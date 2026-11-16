import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";
import { DisclosureChevron } from "./Disclosure";

/**
 * A disclosure's control in words (DESIGN.md § Disclosure; task 054 phase 7):
 * the rotating chevron, then the words as a quiet control, Grey Semibold over
 * a Line 2 underline that turns Navy with the chevron on hover. The words are
 * the surface's ("Show all 6 connections" / "Hide", "Where this came from");
 * the control takes the size of its line. `aria-expanded` follows `open`.
 *
 * Args:
 *   open: Whether what it opens is open.
 *   onToggle: Opens or shuts it.
 *   children: The words.
 *   className: The surface's seat and size.
 */
export function DisclosureToggle({
  open,
  onToggle,
  children,
  className,
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "children"> & {
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      className={cn("group inline-flex min-h-6 cursor-pointer items-center gap-1 text-left font-semibold text-grey", className)}
      {...props}
    >
      <DisclosureChevron open={open} />
      <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
        {children}
      </span>
    </button>
  );
}
