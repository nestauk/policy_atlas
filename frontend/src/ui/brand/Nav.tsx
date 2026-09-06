import type { HTMLAttributes, ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router";

import { Tooltip } from "../radix/Tooltip";
import { Chip } from "./Chip";
import { cn } from "./cn";
import { FoldMarkAnimated } from "./FoldMarkAnimated";
import { FoldMarkIcon } from "./FoldMarkIcon";

/** Hover copy for the BETA chip beside the wordmark. */
export const BETA_CHIP_HINT =
  "Beta means Policy Atlas is an experimental tool under development. Features may be incomplete or change, and outputs should be verified before they inform advice or decisions. We're testing with users and improving it continuously.";

/** Top nav bar: brand left, links right, full viewport width. */
export function NavBar({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <nav className={cn("w-full border-b border-line bg-paper", className)} {...props}>
      <div className="flex h-16 w-full items-center justify-between px-6">
        {children}
      </div>
    </nav>
  );
}

/**
 * Wordmark: fold-mark diamond + "Policy" navy + "Atlas" electric blue.
 *
 * @param running - When true the mark animates, signalling an active run.
 */
export function NavLogo({ running = false }: { running?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.25 whitespace-nowrap font-display text-heading font-extrabold tracking-[-0.02em] text-navy">
      {running ? <FoldMarkAnimated onDark={false} /> : <FoldMarkIcon />}
      <span>
        Policy <b className="font-extrabold text-blue">Atlas</b>
      </span>
    </span>
  );
}

/**
 * Brand wordmark, always home. It is not a nav item — the active underline
 * is reserved for New / Tasks / Projects, so the logo never looks selected.
 *
 * @param running - When true the fold-mark animates (active run in progress).
 */
export function NavHomeLink({ running = false }: { running?: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Link to="/" className="min-w-0 no-underline">
        <NavLogo running={running} />
      </Link>
      <Tooltip
        content={<p className="text-body leading-relaxed text-navy">{BETA_CHIP_HINT}</p>}
      >
        <span tabIndex={0} className="inline-flex">
          <Chip tone="blue">BETA</Chip>
        </span>
      </Tooltip>
    </div>
  );
}

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
          active && "border-blue font-extrabold",
        );
      }}
    >
      {children}
    </NavLink>
  );
}
