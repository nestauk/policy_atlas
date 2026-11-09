import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { cn } from "../ui/brand/cn";
import { MoreIcon } from "../ui/brand/icons";
import { prefersReducedMotion } from "../ui/motion/motion";
import { type Action, type MenuStep, NameActionsMenu, NameRenameField } from "./NameMenu";

/** How long a row takes to fold away once archived: the fold the run card's
 *  steps and the run status bar use (200 ms, height and opacity). */
export const ROW_LEAVE_MS = 200;

/**
 * A list row's own menu (task 058, owner round 12: "There should be a way
 * to delete or archive and rename tasks and projects on the tasks/project
 * lists"): a 40 px quiet control with the headers' chevron at the row's right
 * end, a sibling of the row's link, never inside it. Its glyph is the three
 * dots (`MoreIcon`; owner, round 12: not the headers' chevron). It opens the
 * headers' menu (`NameActionsMenu`): Rename, any further steps (a task's
 * "Add to project"), and Archive with its confirm in words.
 *
 * From `md` up the control shows while the row is hovered or holds focus
 * and while its menu is open; on phones it always shows. It sits in the
 * row's right padding (`pr-12` in the row recipe), so it covers no column.
 *
 * Rename turns the row into the name's field with Save and Cancel
 * (`RowRenameField`); the caller renders that in place of the row's link
 * while `editing` is on.
 */
export function RowMenuControl({
  label,
  name,
  onRename,
  archive,
  archiveSentence,
  archiveError,
  pending,
  controlRef,
  steps,
}: {
  /** The headers' control name ("Task settings"). */
  label: string;
  /** The row's name: the control is "<label>: <name>", one per row. */
  name: string;
  onRename: () => void;
  archive?: Action<void>;
  archiveSentence: string;
  archiveError: string;
  pending: boolean;
  controlRef: RefObject<HTMLButtonElement | null>;
  steps?: ReadonlyArray<MenuStep>;
}) {
  const returnFocus = () => window.setTimeout(() => controlRef.current?.focus(), 0);
  return (
    <div className="absolute inset-y-0 right-1 flex items-center">
      <NameActionsMenu
        label={label}
        align="end"
        onRename={onRename}
        archive={archive}
        archiveSentence={archiveSentence}
        archiveError={archiveError}
        pending={pending}
        returnFocus={returnFocus}
        steps={steps}
        trigger={
          <button
            ref={controlRef}
            type="button"
            aria-label={`${label}: ${name}`}
            aria-haspopup="menu"
            title={label}
            className={cn(
              "pressable inline-flex h-10 w-10 cursor-pointer items-center justify-center text-grey",
              "transition-[color,background-color,opacity] duration-150 hover:bg-blue-tint-2 hover:text-navy",
              "data-[state=open]:bg-blue-tint-2 data-[state=open]:text-navy",
              // Quiet until wanted from md up; always there on a phone.
              "md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100",
              "md:focus-visible:opacity-100 md:data-[state=open]:opacity-100",
            )}
          >
            <MoreIcon />
          </button>
        }
      />
    </div>
  );
}

/** The row while its name is edited: the field with Save and Cancel,
 *  at the row's height and padding, in Body Semibold Navy like the name. */
export function RowRenameField(props: {
  name: string;
  label: string;
  fieldLabel: string;
  rename: Action<string>;
  renameError: string;
  pending: boolean;
  onClose: () => void;
}) {
  return (
    <div className="flex min-h-14 items-center bg-blue-tint-2 px-4 py-2 md:col-span-full">
      <NameRenameField {...props} titleClassName="text-body font-semibold text-navy" />
    </div>
  );
}

/**
 * The fold a row leaves by once archived: its height and opacity to nothing
 * over {@link ROW_LEAVE_MS} on the strong ease-out, at once under reduced
 * motion. `subgrid` passes the task list's column tracks through.
 */
export function RowFold({
  leaving,
  subgrid = false,
  children,
}: {
  leaving: boolean;
  subgrid?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "grid transition-[grid-template-rows,opacity] duration-200 ease-[var(--ease-out-strong)] motion-reduce:transition-none",
        leaving ? "grid-rows-[0fr] opacity-0" : "grid-rows-[1fr] opacity-100",
        subgrid && "md:col-span-full md:grid-cols-subgrid",
      )}
      data-leaving={leaving || undefined}
    >
      <div className={cn("relative min-h-0 overflow-hidden", subgrid && "md:col-span-full md:grid md:grid-cols-subgrid")}>
        {children}
      </div>
    </div>
  );
}

/** A row on its way out: the row as it was, and where it stood. */
type Departing<T> = { row: T; index: number; done: boolean };

/**
 * The rows with the archived ones folding away (round 12). An archived row
 * is kept where it stood, folding, for {@link ROW_LEAVE_MS}, whatever the
 * list's refetch does meanwhile, and then left out for good, so it never
 * blinks back if the refetch is slower than the fold.
 *
 * Args:
 *   rows: The list's rows, as the server last gave them.
 *   idOf: A row's id.
 *
 * Returns:
 *   The rows to draw, each with whether it is leaving, and `depart(id)` to
 *   call once a row's archive has succeeded.
 */
export function useDepartingRows<T>(
  rows: readonly T[],
  idOf: (row: T) => string,
): { shown: { row: T; leaving: boolean }[]; depart: (id: string) => void } {
  const [departing, setDeparting] = useState<ReadonlyMap<string, Departing<T>>>(new Map());
  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), []);

  const depart = (id: string) => {
    const index = rows.findIndex((row) => idOf(row) === id);
    if (index === -1) return;
    const row = rows[index];
    const finish = () => setDeparting((current) => new Map(current).set(id, { row, index, done: true }));
    if (prefersReducedMotion()) {
      finish();
      return;
    }
    setDeparting((current) => new Map(current).set(id, { row, index, done: false }));
    timers.current.push(window.setTimeout(finish, ROW_LEAVE_MS));
  };

  const shown: { row: T; leaving: boolean }[] = rows
    .filter((row) => !departing.has(idOf(row)))
    .map((row) => ({ row, leaving: false }));
  for (const [, entry] of [...departing].sort((a, b) => a[1].index - b[1].index)) {
    if (entry.done) continue;
    shown.splice(Math.min(entry.index, shown.length), 0, { row: entry.row, leaving: true });
  }
  return { shown, depart };
}
