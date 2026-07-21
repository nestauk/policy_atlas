import type { ElementType } from "react";

/**
 * Remove invisible/control characters from model-authored or source-derived
 * display text, retaining only line breaks and tabs as meaningful whitespace.
 *
 * Args:
 *   value: Untrusted text intended for a visible UI surface.
 *
 * Returns:
 *   NFC-normalized text that cannot carry control, bidi, or format smuggling.
 */
export function scrub(value: string): string {
  return value
    .normalize("NFC")
    .replace(/[\p{Cc}\p{Cf}]/gu, (character) => (character === "\n" || character === "\t" ? character : ""));
}

/** Render display text through the shared scrubber. */
export function Scrubbed({
  value,
  as: Tag = "span",
  className,
}: {
  value: string;
  as?: ElementType;
  className?: string;
}) {
  return <Tag className={className}>{scrub(value)}</Tag>;
}
