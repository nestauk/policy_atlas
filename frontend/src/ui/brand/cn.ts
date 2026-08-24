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
      // Every name here must exist as a --text-* token in index.css, and
      // every --text-* token there must appear here. TypeScale.test.ts
      // asserts the two lists are equal, so the next token cannot repeat the
      // 028 failure by being added to only one of them.
      "font-size": [
        { text: ["caption", "meta", "body", "lead", "heading", "title", "display"] },
      ],
    },
  },
});

/** Merge conditional class values with Tailwind conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
