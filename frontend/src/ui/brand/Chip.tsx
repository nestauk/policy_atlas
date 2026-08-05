import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "./cn";

/*
 * Chip/pill (hifi.css .chip family): squared-off status and tag markers.
 * Tone maps to meaning, never meaning to colour alone — pair every toned
 * chip with its text label (labels-not-scores discipline).
 */
const chipVariants = cva(
  "inline-flex items-center gap-1.5 border px-2.5 py-1 text-caption font-semibold",
  {
    variants: {
      tone: {
        default: "border-line-2 bg-paper text-navy",
        blue: "border-[#c7c7ff] bg-blue-tint text-blue",
        soft: "border-line bg-ground text-grey",
        green: "border-[#b7e0d8] bg-green-tint text-[#0c6b5a]",
        yellow: "border-[#f3d99a] bg-yellow-tint text-[#8a5a00]",
        red: "border-[#f4b8c6] bg-red-tint text-red",
      },
    },
    defaultVariants: { tone: "default" },
  },
);

export type ChipProps = HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof chipVariants>;

/** Squared Nesta chip for statuses, tags and counts. */
export function Chip({ className, tone, ...props }: ChipProps) {
  return <span className={cn(chipVariants({ tone }), className)} {...props} />;
}
