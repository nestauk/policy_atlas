import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "./cn";

/*
 * Nesta button language (brand tokens § Buttons):
 * - primary: solid electric blue, white text, the 45° cutout — ONE per view
 * - secondary: text only, subtle grey hover, no cutout
 * - ghost: low emphasis (Cancel, Back to top)
 * - labels are sentence case and action-oriented; disabled is visible, inert
 */
const buttonVariants = cva(
  "inline-flex cursor-pointer items-center gap-2 font-sans leading-none " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue " +
    "disabled:cursor-default",
  {
    variants: {
      variant: {
        primary:
          "cutout bg-blue font-bold text-white hover:bg-[#0000d6] " +
          "disabled:bg-line-2 disabled:text-white",
        secondary:
          "bg-transparent font-semibold text-navy hover:bg-[#f0f0f3] " +
          "disabled:text-line-2 disabled:hover:bg-transparent",
        ghost:
          "bg-transparent font-semibold text-grey hover:text-navy " +
          "disabled:text-line-2 disabled:hover:text-line-2",
      },
      size: {
        md: "px-[18px] py-[11px] text-meta",
        sm: "px-[13px] py-2 text-caption",
      },
    },
    compoundVariants: [
      { variant: "primary", size: "sm", class: "cutout-sm" },
      { variant: "secondary", size: "md", class: "px-3.5" },
      { variant: "ghost", size: "md", class: "px-3 py-[9px] text-caption" },
    ],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
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
