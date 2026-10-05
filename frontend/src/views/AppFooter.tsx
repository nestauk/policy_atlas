import { Link } from "react-router";

import { cn } from "../ui/brand/cn";

/** Disclaimer shown on every workspace-level page, above the legal links. */
export const SITE_DISCLAIMER =
  "Policy Atlas is powered by AI and may make mistakes. The outputs are a synthesis of third-party evidence from academic and grey literature, they do not necessarily reflect the official views of Nesta. They are intended for informational purposes only and should be cross-referenced with primary sources before being used for decision-making.";

/**
 * Site footer: AI/Nesta disclaimer plus Privacy policy and Terms of use.
 *
 * Args:
 *   className: Optional class overrides (e.g. drop `mt-auto` when the parent
 *     already pins the footer inside a scroll pane).
 */
export function AppFooter({ className }: { className?: string } = {}) {
  return (
    <footer
      className={cn("mt-auto w-full shrink-0 border-t border-line bg-ground px-6 py-2", className)}
    >
      <div className="mx-auto max-w-prose-measure text-center">
        <p className="text-caption text-grey">{SITE_DISCLAIMER}</p>
        <p className="mt-1 text-caption text-grey">
          <Link to="/privacy" className="text-grey no-underline hover:text-navy hover:underline">
            Privacy policy
          </Link>
          <span aria-hidden="true"> | </span>
          <Link to="/terms" className="text-grey no-underline hover:text-navy hover:underline">
            Terms of use
          </Link>
        </p>
      </div>
    </footer>
  );
}
