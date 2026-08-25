import type { HTMLAttributes, ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router";

import { Chip } from "./Chip";
import { cn } from "./cn";

/** Height of one chrome row. The shell stacks two of these inside a task. */
export const NAV_BAR_HEIGHT_PX = 64;

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

/** Wordmark: "Policy" navy + "Atlas" electric blue, display face. */
export function NavLogo() {
  return (
    <span className="whitespace-nowrap font-display text-heading font-extrabold tracking-[-0.02em] text-navy">
      Policy <b className="font-extrabold text-blue">Atlas</b>
    </span>
  );
}

/**
 * Brand wordmark, always home. It is not a nav item — the active underline
 * is reserved for New / Tasks / Projects, so the logo never looks selected.
 */
export function NavHomeLink() {
  return (
    <Link to="/" className="flex min-w-0 items-center gap-2 no-underline">
      <NavLogo />
      <Chip tone="blue">BETA</Chip>
    </Link>
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
