import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { InfoHint } from "../ui/brand/InfoHint";
import { SortArrow, type SortOrder } from "../ui/brand/SortableColumnHeader";
import { ChevronIcon, MoreIcon, SearchIcon, iconButtonClass, ICON_ROW } from "../ui/brand/icons";
import { CAPTION_LABEL_CLASS, PANE_LABEL_CLASS } from "../ui/brand/label";
import { PAGE_TITLE_CLASS } from "../ui/brand/PageHeader";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { MENU_ITEM_CLASS, moveMenuFocus } from "../ui/radix/menu";
import { SHEET_SCRIM_CLASS } from "../ui/radix/Sheet";
import { useToast } from "../ui/radix/Toast";
import { portalContainer } from "../ui/radix/portal";
import { OpsApiError, unwrap, useOpsAction, type Organisation } from "./api";

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
export function FailedLine({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <p role="alert" className="mt-3 text-body text-navy">
      {message}{" "}
      <button type="button" onClick={onRetry} className="cursor-pointer font-bold text-blue hover:underline">
        Try again
      </button>
    </p>
  );
}

/** The toast after a write: its summary (no "· recorded"). */
export function useRecordedToast() {
  const { toast } = useToast();
  return (summary: string) => toast({ title: summary, tone: "default" });
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
 * Grey line of help (or a warning band) and a red line for an error. The
 * control gets the ids of the help and the error to put in its
 * `aria-describedby`, so a screen reader reads them with it.
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
  children: ReactNode | ((describedBy: string | undefined) => ReactNode);
  id: string;
}) {
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const describedBy = [help != null && helpId, error != null && errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-body font-semibold text-navy">
        {label}
      </label>
      {typeof children === "function" ? children(describedBy) : children}
      {help != null && (
        <div id={helpId} className="text-body text-grey">
          {help}
        </div>
      )}
      {error != null && (
        <p id={errorId} className="text-body text-red">
          {error}
        </p>
      )}
    </div>
  );
}

/** What an organisation select says until one is chosen, and its error. */
export const CHOOSE_ORGANISATION = "Choose an organisation.";

/** One choice in a searchable dropdown. */
export interface SearchOption {
  value: string;
  label: string;
}

/**
 * A searchable dropdown: the select's trigger, and a
 * popover with a filter field at its top (focused as it opens; typing
 * narrows the list by name) over the choices. With `create`, when the typed
 * name matches no choice exactly, a last row offers to create it. Enter takes
 * the only match, or creates; the arrow keys move between the rows.
 */
export function SearchSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder,
  filterLabel,
  empty,
  describedBy,
  invalid,
  className,
  create,
}: {
  id?: string;
  label: string;
  options: readonly SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  filterLabel: string;
  empty: string;
  describedBy?: string;
  invalid?: boolean;
  className?: string;
  create?: { noun: string; pending: boolean; error: string | null; run: (name: string, close: () => void) => void; clearError: () => void };
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const filterRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();
  const chosen = options.find((option) => option.value === value);
  const typed = filter.trim();
  const needle = typed.toLocaleLowerCase();
  const listed = needle === "" ? options : options.filter((option) => option.label.toLocaleLowerCase().includes(needle));
  const canCreate =
    create !== undefined && typed !== "" && !options.some((option) => option.label.toLocaleLowerCase() === needle);

  const setOpenState = (next: boolean) => {
    setOpen(next);
    if (!next) {
      setFilter("");
      create?.clearError();
    }
  };
  const pick = (next: string) => {
    onChange(next);
    setOpenState(false);
  };
  const rows = () => Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
  const onFilterKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      rows()[0]?.focus();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (listed.length === 1) pick(listed[0].value);
      else if (canCreate && !create.pending) create.run(typed, () => setOpenState(false));
    }
  };
  const onListKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const buttons = rows();
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "ArrowUp" && current <= 0) filterRef.current?.focus();
    else buttons[Math.min(current + (event.key === "ArrowDown" ? 1 : -1), buttons.length - 1)]?.focus();
  };

  return (
    <Popover open={open} onOpenChange={setOpenState}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-label={label}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn(
            "relative inline-flex h-10 w-full min-w-0 cursor-pointer items-center border bg-paper pr-9 pl-3 text-left text-body text-ink",
            "transition-colors duration-150",
            open ? "border-navy" : invalid ? "border-red" : "border-line-2",
            className,
          )}
        >
          <span className={cn("min-w-0 flex-1 truncate", chosen === undefined && "text-grey")}>
            {chosen?.label ?? placeholder}
          </span>
          <ChevronIcon size={12} className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90 text-grey" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] min-w-72 max-w-[calc(100vw-2rem)] p-1"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          filterRef.current?.focus();
        }}
      >
        <input
          ref={filterRef}
          type="search"
          aria-label={filterLabel}
          placeholder={filterLabel}
          autoComplete="off"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value);
            create?.clearError();
          }}
          onKeyDown={onFilterKeyDown}
          className="mb-1 h-10 w-full border border-line-2 bg-paper px-3 text-body text-ink focus-visible:outline-2 focus-visible:outline-blue"
        />
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          aria-label={label}
          onKeyDown={onListKeyDown}
          className="flex max-h-72 flex-col overflow-y-auto"
        >
          {listed.map((option) => {
            const selected = option.value === value;
            return (
              <li key={option.value} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => pick(option.value)}
                  className={cn(
                    "block min-h-10 w-full cursor-pointer px-3 py-2 text-left text-meta text-navy",
                    "hover:bg-blue-tint-2 hover:text-blue focus-visible:bg-blue-tint-2",
                    selected ? "bg-blue-tint-2 font-semibold" : "font-normal",
                  )}
                >
                  {option.label}
                </button>
              </li>
            );
          })}
          {listed.length === 0 && !canCreate && (
            <li role="none" className="px-3 py-2 text-meta text-grey">
              {empty}
            </li>
          )}
          {canCreate && (
            <li role="none" className={cn(listed.length > 0 && "border-t border-line")}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                disabled={create.pending}
                onClick={() => create.run(typed, () => setOpenState(false))}
                className="block min-h-10 w-full cursor-pointer px-3 py-2 text-left text-meta font-semibold text-blue hover:bg-blue-tint-2 focus-visible:bg-blue-tint-2 disabled:cursor-default disabled:text-grey"
              >
                Create {create.noun} “{typed}”
              </button>
            </li>
          )}
        </ul>
        {create?.error != null && (
          <p role="alert" className="px-3 py-2 text-meta text-red">
            {create.error}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

/**
 * The organisation picker every form shares: the searchable dropdown, which
 * can create an organisation from the typed name and choose it at once.
 */
export function OrganisationSelect({
  id,
  label,
  organisations,
  value,
  onChange,
  describedBy,
  invalid,
}: {
  id: string;
  label: string;
  organisations: readonly Organisation[];
  value: string;
  onChange: (orgId: string) => void;
  describedBy?: string;
  invalid?: boolean;
}) {
  const toast = useRecordedToast();
  const [error, setError] = useState<string | null>(null);
  // The one just created, until the refetched list carries it.
  const [made, setMade] = useState<Organisation | null>(null);
  const create = useOpsAction((client, name: string) =>
    unwrap(client.POST("/api/v1/ops/organisations", { body: { name } })),
  );
  const options = organisations.map((org) => ({ value: org.org_id, label: org.name }));
  if (made !== null && !organisations.some((org) => org.org_id === made.org_id)) {
    options.push({ value: made.org_id, label: made.name });
  }
  return (
    <SearchSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={onChange}
      placeholder={CHOOSE_ORGANISATION}
      filterLabel="Find or create an organisation"
      empty="No organisations yet. Type a name to create one."
      describedBy={describedBy}
      invalid={invalid}
      create={{
        noun: "organisation",
        pending: create.isPending,
        error,
        clearError: () => setError(null),
        run: (name, close) =>
          create.mutate(name, {
            onSuccess: (org) => {
              setMade(org);
              toast(`Created ${org.name}`);
              onChange(org.org_id);
              close();
            },
            onError: (failure) =>
              setError(
                failure instanceof OpsApiError && failure.status === 409
                  ? "An organisation with that name already exists."
                  : "Could not create the organisation. Try again.",
              ),
          }),
      }}
    />
  );
}

/** A value a column sorts by; empty values always sort last. */
export type SortValue = string | number | null | undefined;

function compareValues(a: SortValue, b: SortValue, order: SortOrder): number {
  if (a == null || a === "") return b == null || b === "" ? 0 : 1;
  if (b == null || b === "") return -1;
  const result =
    typeof a === "number" && typeof b === "number"
      ? a - b
      : String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
  return order === "asc" ? result : -result;
}

/**
 * Click-to-sort for an ops table: the first click on a
 * column sorts ascending, the next reverses it. Unsorted, rows keep the
 * server's order.
 */
export function useSort<T, K extends string>(rows: readonly T[], columns: Record<K, (row: T) => SortValue>) {
  const [sort, setSort] = useState<{ key: K; order: SortOrder } | null>(null);
  const sorted =
    sort === null ? rows : [...rows].sort((a, b) => compareValues(columns[sort.key](a), columns[sort.key](b), sort.order));
  const onSort = (key: K) =>
    setSort((current) => ({ key, order: current?.key === key && current.order === "asc" ? "desc" : "asc" }));
  return { sorted, sort, onSort };
}

/**
 * A sortable column header: the words and the product's sort arrow as one
 * button ("Sort by <label>"), `aria-sort` on the cell, and an optional info
 * hint beside it.
 */
export function SortTh<K extends string>({
  sortKey,
  label,
  sort,
  onSort,
  align,
  note,
  className,
}: {
  sortKey: K;
  label: string;
  sort: { key: K; order: SortOrder } | null;
  onSort: (key: K) => void;
  align?: "end";
  note?: string;
  className?: string;
}) {
  const order = sort?.key === sortKey ? sort.order : null;
  return (
    <th
      aria-sort={order === "asc" ? "ascending" : order === "desc" ? "descending" : "none"}
      className={cn(TH_CLASS, align === "end" && "text-right", className)}
    >
      <span className={cn("inline-flex max-w-full items-center gap-1 align-bottom", align === "end" && "justify-end")}>
        <button
          type="button"
          aria-label={`Sort by ${label.toLowerCase()}`}
          onClick={() => onSort(sortKey)}
          className={cn(
            "group inline-flex min-w-0 cursor-pointer items-center gap-1 uppercase hover:text-navy",
            order !== null && "text-navy",
          )}
        >
          {/* Right-aligned, the arrow leads; in the markup, not by reversing the
              row, which would move the header's text baseline. */}
          {align === "end" && <SortArrow order={order} />}
          <span className="truncate">{label}</span>
          {align !== "end" && <SortArrow order={order} />}
        </button>
        {note !== undefined && (
          // The hint's 24 px target must not lift this header off the row's baseline.
          <span className="-my-1.5 inline-flex">
            <InfoHint label={`About ${label.toLowerCase()}`} note={note} />
          </span>
        )}
      </span>
    </th>
  );
}

/* Tables (DESIGN.md § Tables): a Line hairline above and below, rows ruled,
   no side borders, headers in the Label style at Caption size, figures
   right-aligned in tabular figures. */
export const TABLE_WRAP_CLASS = "relative overflow-x-auto border-y border-line bg-paper";
/**
 * Fixed columns (DESIGN.md § Tables): each header cell sets its width, so a
 * search, a note under a name or a status change never moves a column. On
 * a phone the table keeps its columns and scrolls sideways in its frame.
 */
// Every column states a width: the table is never narrower than their sum
// (`min-w-max`), so on a narrow screen it scrolls sideways in its frame
// instead of squeezing an unsized column to nothing.
export const TABLE_CLASS = "w-full min-w-max table-fixed border-collapse text-left";
export const TH_CLASS = cn(CAPTION_LABEL_CLASS, "h-10 truncate px-3 pb-2 align-bottom font-bold");
/** The actions column stays at the frame's right edge while the table
 *  scrolls sideways, so a row's controls stay in reach on a phone. Its rows
 *  carry their own fill (`bg-paper`, or the selection's wash) for it to inherit. */
export const ACTIONS_TH_CLASS = "sticky right-0 w-14 bg-paper";
export const ACTIONS_TD_CLASS = "sticky right-0 bg-inherit";
export const TD_CLASS = "border-t border-line px-3 py-3 align-top text-meta text-ink";
/** A figures column: right-aligned, one line. Wrap the value in `Figures` so
 *  only its digits take tabular figures (they widen the spaces too). */
export const FIGURE_CLASS = "whitespace-nowrap text-right";

/**
 * A list with no rows: the label inside the table's frame, under its
 * headers (DESIGN.md § Lists, States).
 */
export function EmptyRows({ label }: { label: string }) {
  return (
    <p role="status" className="border-t border-line px-4 py-6 text-body font-semibold text-navy">
      {label}
    </p>
  );
}

/**
 * A form page's header: the way back and the title, then the form right
 * under it. Unlike the list pages' header it keeps no empty actions slot or
 * filters row.
 */
export function FormHeader({ back, title, line }: { back: ReactNode; title: string; line?: string }) {
  return (
    <header>
      <div className="mb-2 flex h-6 items-center">{back}</div>
      <h1 className={PAGE_TITLE_CLASS}>{title}</h1>
      {line !== undefined && <p className="mt-2 text-body text-grey">{line}</p>}
    </header>
  );
}

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

/** The red fill of the destructive confirms (Deactivate, Delete). */
export const DANGER_CLASS = "bg-red hover:bg-red/90";

/**
 * A centred dialog over the sheets' scrim: Paper, a Line 2 hairline, the
 * overlay lift, square. It rises 8 px into place (a cut under reduced
 * motion); Radix traps focus and closes on Escape.
 *
 * Args:
 *   description: The consequence sentence, read with the title before
 *     anything in the dialog.
 *   describedBy: Instead, the id of a line inside the dialog that says the
 *     consequence (a field's help that sits under its control).
 *   returnFocus: Where focus goes when it closes, when its opener is gone
 *     (a menu item, a row's button); null leaves Radix's return to the opener.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  describedBy,
  returnFocus,
  children,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  describedBy?: string;
  returnFocus?: () => HTMLElement | null;
  children?: ReactNode;
  footer: ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal container={portalContainer()}>
        <DialogPrimitive.Overlay className={SHEET_SCRIM_CLASS} />
        <DialogPrimitive.Content
          {...(description === undefined && { "aria-describedby": describedBy })}
          onCloseAutoFocus={(event) => {
            const target = returnFocus?.();
            if (target == null) return;
            event.preventDefault();
            target.focus();
          }}
          className={cn(
            "anim-centre-in fixed left-1/2 top-[12vh] z-50 flex max-h-[76vh] w-[min(34rem,calc(100vw-32px))] -translate-x-1/2 flex-col",
            "border border-line-2 bg-paper shadow-overlay focus-visible:outline-hidden",
          )}
        >
          <DialogPrimitive.Title className="px-6 pt-5 font-sans text-lead font-bold text-navy">
            {title}
          </DialogPrimitive.Title>
          <div className="min-h-0 overflow-y-auto px-6 pb-2 pt-3">
            {description !== undefined && (
              <DialogPrimitive.Description className="text-body text-ink">{description}</DialogPrimitive.Description>
            )}
            {children}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3 px-6 pb-5 pt-3">{footer}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** An action that failed, as a dialog, so a long table cannot hide it. */
export function FailedDialog({ message, onRetry, onClose }: { message: string; onRetry: () => void; onClose: () => void }) {
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={message}
      description="Some or all of it did not go through. Try again, or close and check the list."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button onClick={onRetry}>Try again</Button>
        </>
      }
    />
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
export function RowMenu({ id, label, items }: { id?: string; label: string; items: readonly MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
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
          menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
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
              // aria-disabled, not disabled: the item stays in the arrow keys'
              // reach, so its hint is read out.
              aria-disabled={item.disabled || undefined}
              onClick={() => {
                if (item.disabled) return;
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                MENU_ITEM_CLASS,
                item.hint != null && "h-auto min-h-10 flex-col items-start justify-center py-2",
                "aria-disabled:cursor-default aria-disabled:text-grey aria-disabled:hover:bg-transparent aria-disabled:hover:text-grey",
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
