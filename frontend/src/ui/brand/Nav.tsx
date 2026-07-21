import type { HTMLAttributes, ReactNode } from "react";
import { NavLink } from "react-router";

import { cn } from "./cn";

/** Top nav bar: brand group left, links right (brand tokens § Navigation). */
export function NavBar({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <nav
      className={cn(
        "flex h-[58px] items-center justify-between border-b border-line bg-paper px-6",
        className,
      )}
      {...props}
    />
  );
}

/** Wordmark: "Policy" navy + "Atlas" electric blue, display face. */
export function NavLogo() {
  return (
    <span className="whitespace-nowrap font-display text-lg font-extrabold tracking-[-0.3px] text-navy">
      Policy <b className="font-extrabold text-blue">Atlas</b>
    </span>
  );
}

/** Growing-underline nav link: active page fills its width in Nesta blue. */
export function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "nav-underline text-[13px] font-semibold text-grey no-underline hover:text-navy",
          isActive && "nav-underline-on font-extrabold text-navy",
        )
      }
    >
      {children}
    </NavLink>
  );
}
