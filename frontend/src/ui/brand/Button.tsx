import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "./cn";

/*
 * Nesta button language (brand tokens § Buttons):
 * - primary: solid electric blue, white text, the 45° cutout — ONE per view
 * - start: the cut shape in green, the one action that starts a run
 * - secondary: text only, subtle grey hover, no cutout
 * - outline: secondary with a Line 2 border on Paper (pagination, Download,
 *   the bordered actions inside a card)
 * - ghost: low emphasis (Cancel, Back to top)
 * - labels are sentence case and action-oriented; disabled is visible, inert
 *
 * Focus: the house ring (2px Electric Blue, offset 2px) comes from the base
 * rule in index.css. The cut-corner variants cannot show it: their clip-path
 * clips anything drawn outside the box, outline included. So they draw the
 * ring inside, in white on the fill (task 058 consistency pass).
 */
const CUT_FOCUS_RING = "focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-white";

export const buttonVariants = cva(
  "pressable inline-flex cursor-pointer items-center gap-2 font-sans leading-none no-underline " +
    "disabled:cursor-default",
  {
    variants: {
      variant: {
        primary:
          `cutout bg-blue font-bold text-white hover:bg-blue-pressed ${CUT_FOCUS_RING} ` +
          "disabled:bg-line-2 disabled:text-white",
        secondary:
          "bg-transparent font-semibold text-navy hover:bg-[#f0f0f3] " +
          "disabled:text-line-2 disabled:hover:bg-transparent",
        outline:
          "border border-line-2 bg-paper font-semibold text-navy hover:bg-[#f0f0f3] " +
          "disabled:text-line-2 disabled:hover:bg-paper",
        ghost:
          "bg-transparent font-semibold text-grey hover:text-navy " +
          "disabled:text-line-2 disabled:hover:text-line-2",
        // The one action that starts a run: the cut shape in green, the
        // only green fill in the system (DESIGN.md § Buttons, Start run).
        start:
          `cutout bg-green font-bold text-white hover:bg-green-pressed ${CUT_FOCUS_RING} ` +
          "disabled:bg-line-2 disabled:text-white",
      },
      size: {
        md: "px-[18px] py-[11px] text-meta",
        sm: "px-[13px] py-2 text-meta",
        // The entry size: the list pages' primary, the New Task submit, Start
        // run. 52 px tall, at least 144 px wide, the label centred and never
        // wrapped (DESIGN.md § Buttons).
        entry: "h-13 min-w-36 justify-center whitespace-nowrap px-6 text-body",
      },
    },
    compoundVariants: [
      { variant: "primary", size: "sm", class: "cutout-sm" },
      { variant: "start", size: "sm", class: "cutout-sm" },
      { variant: "secondary", size: "md", class: "px-3.5" },
      // The border takes 1px a side, so the outline keeps the secondary's
      // height at each size.
      { variant: "outline", size: "md", class: "px-3.5 py-2.5" },
      { variant: "outline", size: "sm", class: "py-[7px]" },
      { variant: "ghost", size: "md", class: "px-3 py-[9px] text-meta" },
    ],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

/** Nesta-language button: 0 radius, primary carries the 45° cutout. */
export function Button({ className, variant, size, type, ...props }: ButtonProps) {
  return (
    <button
      type={type ?? "button"}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
