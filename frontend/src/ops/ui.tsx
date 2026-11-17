import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useId, useRef, useState, type ReactNode } from "react";

import { Button } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { MoreIcon, SearchIcon, iconButtonClass, ICON_ROW } from "../ui/brand/icons";
import { CAPTION_LABEL_CLASS, PANE_LABEL_CLASS } from "../ui/brand/label";
import { LIST_CONTROL_CLASS } from "../ui/brand/list/ListStates";
import { Select } from "../ui/brand/Select";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { MENU_ITEM_CLASS, moveMenuFocus } from "../ui/radix/menu";
import { SHEET_SCRIM_CLASS } from "../ui/radix/Sheet";
import { useToast } from "../ui/radix/Toast";
import { portalContainer } from "../ui/radix/portal";
import type { Organisation } from "./api";
import { recorded } from "./format";

/* The ops pages' own pieces, built from the shared design system. */

/** The page's loading state: the words alone. */
export function Loading() {
  return (
    <p role="status" className="py-6 text-body text-grey">
      Loading…
    </p>
  );
}

/** A request that failed (5xx or no answer): one line under the table. */
export function FailedLine({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
      <p className="text-body text-navy">Something went wrong. Try again.</p>
      <Button variant="ghost" className={LIST_CONTROL_CLASS} onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

/** The toast after a write: "<summary> · recorded". */
export function useRecordedToast() {
  const { toast } = useToast();
  return (summary: string) => toast({ title: recorded(summary), tone: "default" });
}

/** A field's control: Paper, a Line 2 hairline, square, 40 px, Body words. */
export const INPUT_CLASS =
  "h-10 w-full min-w-0 border border-line-2 bg-paper px-3 text-body text-ink placeholder:text-grey " +
  "aria-[invalid=true]:border-red";

/** The filters row's search: filters the loaded list as you type. */
export function SearchField({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="relative block w-96 max-w-full">
      <span className="sr-only">{placeholder}</span>
      <SearchIcon className="pointer-events-none absolute left-3 top-3 text-grey" />
      <input
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className={cn(INPUT_CLASS, "pl-9")}
      />
    </label>
  );
}

/**
 * One form field: the Body Semibold Navy label, the control, then one Body
 * Grey line of help and a red line for an error.
 */
export function Field({
  label,
  help,
  error,
  children,
  id,
}: {
  label: string;
  help?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  id: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-body font-semibold text-navy">
        {label}
      </label>
      {children}
      {help != null && <div className="text-body text-grey">{help}</div>}
      {error != null && (
        <p id={`${id}-error`} className="text-body text-red">
          {error}
        </p>
      )}
    </div>
  );
}

/** The organisation picker every form shares (the app's one dropdown). */
export function OrganisationSelect({
  id,
  label,
  organisations,
  value,
  onChange,
}: {
  id: string;
  label: string;
  organisations: readonly Organisation[];
  value: string;
  onChange: (orgId: string) => void;
}) {
  return (
    <Select
      id={id}
      label={label}
      value={value}
      options={organisations.map((org) => ({ value: org.org_id, label: org.name }))}
      onChange={onChange}
      className="w-full"
      contentClassName="w-80"
    />
  );
}

/* Tables (DESIGN.md § Tables): a Line hairline above and below, rows ruled,
   no side borders, headers in the Label style at Caption size, figures
   right-aligned in tabular figures. */
export const TABLE_WRAP_CLASS = "relative overflow-x-auto border-y border-line bg-paper";
/** Tables keep their columns on a phone and scroll sideways in their frame. */
export const TABLE_CLASS = "w-full min-w-[52rem] border-collapse text-left";
export const TH_CLASS = cn(CAPTION_LABEL_CLASS, "h-10 whitespace-nowrap px-3 pb-2 align-bottom font-bold");
export const TD_CLASS = "border-t border-line px-3 py-3 align-top text-meta text-ink";
/** A figures column: right-aligned, one line. Wrap the value in `Figures` so
 *  only its digits take tabular figures (they widen the spaces too). */
export const FIGURE_CLASS = "whitespace-nowrap text-right";

/** A ruled panel beside or below a page's content, under a pane heading. */
export function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className={cn("border border-line bg-paper", className)}>
      <h2 id={id} className={cn(PANE_LABEL_CLASS, "px-4 pb-2.5 pt-3.5")}>
        {title}
      </h2>
      <div className="px-4 pb-4">{children}</div>
    </section>
  );
}

/** The red fill of the one destructive confirm (Offboard). */
export const DANGER_CLASS = "bg-red hover:bg-red/90";

/**
 * A centred dialog over the sheets' scrim: Paper, a Line 2 hairline, the
 * overlay lift, square. It rises 8 px into place (a cut under reduced
 * motion); Radix traps focus, closes on Escape and returns focus.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  children,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal container={portalContainer()}>
        <DialogPrimitive.Overlay className={SHEET_SCRIM_CLASS} />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            "anim-centre-in fixed left-1/2 top-[12vh] z-50 flex max-h-[76vh] w-[min(34rem,calc(100vw-32px))] -translate-x-1/2 flex-col",
            "border border-line-2 bg-paper shadow-overlay focus-visible:outline-none",
          )}
        >
          <DialogPrimitive.Title className="px-6 pt-5 font-display text-lead font-bold text-navy">
            {title}
          </DialogPrimitive.Title>
          <div className="min-h-0 overflow-y-auto px-6 pb-2 pt-3">{children}</div>
          <div className="flex flex-wrap items-center justify-end gap-3 px-6 pb-5 pt-3">{footer}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A dialog's list of the people an action names: name, then the address. */
export function NameList({ people }: { people: ReadonlyArray<{ user_id: string; display_name: string; email?: string | null }> }) {
  return (
    <ul className="mt-3 max-h-56 overflow-y-auto border-y border-line">
      {people.map((person) => (
        <li key={person.user_id} className="flex flex-wrap gap-x-3 border-t border-line py-2 text-meta first:border-t-0">
          <span className="font-semibold text-navy">{person.display_name}</span>
          {person.email != null && <span className="text-grey">{person.email}</span>}
        </li>
      ))}
    </ul>
  );
}

/** One row menu item; a disabled one may say why under its words. */
export interface MenuItem {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  hint?: string;
}

/**
 * A row's menu: the three-dot row icon button, and the menu popover's 40 px
 * rows (DESIGN.md § Overlays, Menu). Arrow keys, Home and End move; Escape
 * and a press outside close it.
 */
export function RowMenu({ label, items }: { label: string; items: readonly MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-haspopup="menu"
          className={cn(iconButtonClass("row"), "data-[state=open]:bg-blue-tint-2 data-[state=open]:text-navy")}
        >
          <MoreIcon size={ICON_ROW} />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="anim-menu w-auto min-w-60 p-0 transition-none"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus();
        }}
      >
        <div
          ref={menuRef}
          role="menu"
          aria-label={label}
          className="py-1"
          onKeyDown={(event) => moveMenuFocus(event, menuRef.current)}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                MENU_ITEM_CLASS,
                item.hint != null && "h-auto min-h-10 flex-col items-start justify-center py-2",
                "disabled:cursor-default disabled:text-grey disabled:hover:bg-transparent",
              )}
            >
              {item.label}
              {item.hint != null && <span className="text-caption font-normal text-grey">{item.hint}</span>}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
