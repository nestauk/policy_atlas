import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge doesn't know the named type scale (index.css @theme
// --text-*), and an unknown `text-<x>` utility is classified as a text
// COLOUR — so "text-white … text-meta" silently dropped the colour and
// every primary button rendered ink-on-blue (028 live finding). Register
// the scale as font-size utilities so colour and size never conflict.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["caption", "meta", "body", "lead", "heading", "title"] }],
    },
  },
});

/** Merge conditional class values with Tailwind conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
