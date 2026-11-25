import type { AnchorHTMLAttributes } from "react";

/**
 * A link that opens in a new tab and says so to a screen reader.
 *
 * Every link that leaves the app in a new tab goes through this component,
 * so the warning and the `rel` are set in one place.
 */
export function ExternalLink({
  children,
  ...props
}: Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "target" | "rel">) {
  return (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
      {/* Not selectable, so a copied reference does not carry the words. */}
      <span className="sr-only select-none"> (opens in new tab)</span>
    </a>
  );
}
