import { useRef, type ReactNode } from "react";
import { Link, Outlet } from "react-router";

import { useAuth } from "../auth";
import { Button } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { PAGE_COLUMN_CLASS } from "../ui/brand/PageHeader";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { MENU_ITEM_CLASS, moveMenuFocus } from "../ui/radix/menu";
import { errorStatus, usePeople, useRequests, type Person } from "./api";
import { productOrigin } from "./format";

/**
 * The ops pages' frame: their own top bar (the wordmark followed by "Ops", the
 * sections when there is something to show, the way back to the product and
 * the signed-in person) over the page column. No New, Tasks or Projects:
 * ops work is separate from using the product (contract B6).
 */
function Frame({ sections, account, children }: { sections?: ReactNode; account?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col bg-ground">
      <NavBar>
        <div className="flex min-w-0 flex-wrap items-center gap-x-8 gap-y-1">
          <Link to="/people" className="flex min-w-0 items-center gap-2 no-underline">
            <NavLogo />
            <span className="font-display text-heading font-extrabold tracking-[-0.02em] text-navy">Ops</span>
          </Link>
          {sections}
        </div>
        <div className="flex items-center gap-4">
          <a
            href={productOrigin()}
            className="whitespace-nowrap text-meta font-semibold text-grey no-underline transition-colors duration-150 hover:text-navy"
          >
            Back to Policy Atlas
          </a>
          {account}
        </div>
      </NavBar>
      <main className={cn(PAGE_COLUMN_CLASS, "flex-1")}>{children}</main>
    </div>
  );
}

/** Signed out, or the session could not be refreshed: one button. */
function SignIn() {
  const auth = useAuth();
  return (
    <div className="pt-10">
      <Button onClick={() => void auth.signIn()}>Sign in</Button>
    </div>
  );
}

/** A 403 on the first call: the two sentences and nothing else. */
function NoOpsRole() {
  return (
    <div className="max-w-[44em] pt-10">
      <p className="text-lead font-semibold text-navy">Your account does not have the ops role.</p>
      <p className="mt-2 text-body text-grey">Ask an operator to grant it from the command line.</p>
    </div>
  );
}

/** "Karlis Kanders" → "KK"; one name → its first letter. */
function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? [words[0], words[words.length - 1]] : words;
  return letters.map((word) => word[0]?.toUpperCase() ?? "").join("");
}

/** The signed-in person: their initials, opening a menu with who they are and Sign out. */
function AccountMenu({ me }: { me: Person | undefined }) {
  const auth = useAuth();
  const menuRef = useRef<HTMLDivElement>(null);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Account"
          aria-haspopup="menu"
          className={cn(
            "pressable inline-flex h-8 min-w-8 cursor-pointer items-center justify-center border border-line-2 bg-paper px-1.5",
            "text-caption font-bold tabular-nums text-navy hover:bg-blue-tint-2 data-[state=open]:bg-blue-tint-2",
          )}
        >
          {initials(me?.display_name ?? "") || (
            // Who they are is unknown (the people read was refused): the account glyph.
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="anim-menu w-auto min-w-60 p-0 transition-none"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
        }}
      >
        {me !== undefined && (
          <div className="max-w-80 p-4 pb-3">
            <p className="truncate text-meta font-bold text-navy">{me.display_name}</p>
            {me.email != null && <p className="truncate text-caption text-grey">{me.email}</p>}
          </div>
        )}
        <div
          ref={menuRef}
          role="menu"
          aria-label="Account"
          className={cn("py-1", me !== undefined && "border-t border-line")}
          onKeyDown={(event) => moveMenuFocus(event, menuRef.current)}
        >
          <button type="button" role="menuitem" onClick={() => void auth.signOut()} className={MENU_ITEM_CLASS}>
            Sign out
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** The signed-in shell: the people read is the first call, and a 403 or 401 on it replaces the page. */
function SignedInShell() {
  const auth = useAuth();
  const people = usePeople();
  const requests = useRequests();
  const status = errorStatus(people.error);

  if (status === 403) {
    // Still a way out: the account menu with Sign out. No sections, no retry.
    return (
      <Frame account={<AccountMenu me={undefined} />}>
        <NoOpsRole />
      </Frame>
    );
  }
  if (status === 401) {
    return (
      <Frame>
        <SignIn />
      </Frame>
    );
  }

  const waiting = requests.data?.items.filter((item) => item.status === "waiting").length ?? 0;
  const me = people.data?.find((person) => person.user_id === auth.user?.sub);
  const sections = (
    <div className="flex items-center gap-5">
      <NavItem to="/people">People</NavItem>
      <NavItem to="/organisations">Organisations</NavItem>
      <NavItem to="/requests">
        Requests
        {waiting > 0 && (
          <>
            <span aria-hidden="true" className="ml-1.5 font-semibold tabular-nums text-blue">
              {waiting}
            </span>
            <span className="sr-only">, {waiting} waiting</span>
          </>
        )}
      </NavItem>
    </div>
  );
  return (
    <Frame sections={sections} account={<AccountMenu me={me} />}>
      <Outlet />
    </Frame>
  );
}

/** The route element every ops page sits in. */
export function OpsShell() {
  const auth = useAuth();
  if (auth.status !== "authenticated") {
    return (
      <Frame>
        <SignIn />
      </Frame>
    );
  }
  return <SignedInShell />;
}
