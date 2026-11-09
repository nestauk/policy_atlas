import type { HTMLAttributes, ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router";

import { Tooltip } from "../radix/Tooltip";
import { Chip } from "./Chip";
import { cn } from "./cn";
import { FoldMarkIcon } from "./FoldMarkIcon";

/** Hover copy for the BETA chip beside the wordmark. */
export const BETA_CHIP_HINT =
  "Beta means Policy Atlas is an experimental tool under development. Features may be incomplete or change, and outputs should be verified before they inform advice or decisions. We're testing with users and improving it continuously.";

/** Top nav bar: brand left, links right, full viewport width. */
export function NavBar({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <nav className={cn("w-full border-b border-line bg-paper", className)} {...props}>
      <div className="flex h-16 w-full items-center justify-between px-6 max-md:h-auto max-md:min-h-14 max-md:flex-wrap max-md:gap-x-5 max-md:gap-y-1 max-md:px-4 max-md:py-2">
        {children}
      </div>
    </nav>
  );
}

/**
 * Wordmark: fold-mark diamond + "Policy" navy + "Atlas" electric blue. The
 * mark stays still during a run: the run's own live mark is the one turning
 * logo on the screen (task 058, owner 2026-11-05).
 */
export function NavLogo() {
  return (
    <span className="inline-flex items-center gap-1.25 whitespace-nowrap font-display text-heading font-extrabold tracking-[-0.02em] text-navy">
      <FoldMarkIcon />
      <span>
        Policy <b className="font-extrabold text-blue">Atlas</b>
      </span>
    </span>
  );
}

/**
 * Brand wordmark, always home. It is not a nav item — the active underline
 * is reserved for New / Tasks / Projects, so the logo never looks selected.
 */
export function NavHomeLink() {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Link to="/" className="min-w-0 no-underline">
        <NavLogo />
      </Link>
      <Tooltip
        content={<p className="text-body text-navy">{BETA_CHIP_HINT}</p>}
      >
        <span tabIndex={0} className="inline-flex">
          <Chip tone="blue">BETA</Chip>
        </span>
      </Tooltip>
    </div>
  );
}

/**
 * The growing underline (task 058; owner round 9, reshaped in the
 * consistency pass): one 3 px Electric Blue rule under the item, anchored at
 * its left edge. On hover (fine pointers, Tailwind's `hover:`) and keyboard
 * focus it grows from the left edge to the item's centre (half width, 200 ms,
 * the strong ease-out) and shrinks back on leave. The active item's rule is
 * the same rule at full width, so a click carries the half rule on from the
 * centre to the right edge instead of restarting it. Under reduced motion the
 * half and the full rule appear without growing. Shared by the top nav and
 * the lifecycle tabs; the item keeps a transparent 3 px bottom border so the
 * rule never moves the text.
 */
export const GROWING_RULE_CLASS =
  "relative after:pointer-events-none after:absolute after:inset-x-0 after:-bottom-[3px] after:h-[3px] after:origin-left after:scale-x-0 after:bg-blue after:transition-transform after:duration-200 after:ease-[var(--ease-out-strong)] hover:after:scale-x-50 focus-visible:after:scale-x-50 motion-reduce:after:transition-none";

/** The active item: the growing rule at full width, held there on hover and
 *  focus. Pair with `GROWING_RULE_CLASS` through `cn`. */
export const GROWING_RULE_ACTIVE_CLASS =
  "after:scale-x-100 hover:after:scale-x-100 focus-visible:after:scale-x-100";

/** Growing-underline nav link: active item gets a 3px Nesta-blue rule. */
export function NavItem({
  to,
  end,
  match,
  children,
}: {
  to: string;
  end?: boolean;
  /** When set, wins over React Router's default prefix match. */
  match?: (pathname: string) => boolean;
  children: ReactNode;
}) {
  const { pathname } = useLocation();
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => {
        const active = match ? match(pathname) : isActive;
        return cn(
          "inline-block border-b-[3px] border-transparent pb-1 text-lead font-semibold text-navy no-underline",
          GROWING_RULE_CLASS,
          active && cn(GROWING_RULE_ACTIVE_CLASS, "font-extrabold"),
        );
      }}
    >
      {children}
    </NavLink>
  );
}
