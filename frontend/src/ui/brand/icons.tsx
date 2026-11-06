import type { ReactNode } from "react";

import { cn } from "./cn";

/*
 * The app's one icon module (task 058 consistency pass): every glyph on one
 * 16-unit grid, one 1.5 stroke, round joins, `currentColor`, drawn here (the
 * app carries no icon library). Two sizes, each in its own button box
 * (DESIGN.md § Buttons, Icon buttons):
 *
 * - chrome: a 16 px glyph in a 32 px box (the rail, panel headers, close,
 *   the longlist's option actions, jump to end)
 * - row: a 13 px glyph in a 28 px box (actions revealed on a list row)
 */

/** Glyph size for chrome icon buttons. */
export const ICON_CHROME = 16;
/** Glyph size for row icon buttons. */
export const ICON_ROW = 13;

const ICON_BUTTON_BASE =
  "pressable inline-flex shrink-0 cursor-pointer items-center justify-center p-0 text-grey " +
  "hover:bg-blue-tint-2 hover:text-navy " +
  "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent";

/** The icon button's box, hover (Blue Wash, Navy) and press, at either size. */
export function iconButtonClass(size: "chrome" | "row" = "chrome"): string {
  return cn(ICON_BUTTON_BASE, size === "chrome" ? "h-8 w-8" : "h-7 w-7");
}

type IconProps = { size?: number; className?: string };

function Glyph({ size = ICON_CHROME, className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

/** Add: new chat, add to shortlist. */
export function PlusIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M8 3v10M3 8h10" />
    </Glyph>
  );
}

/** Remove from shortlist. */
export function MinusIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M3 8h10" />
    </Glyph>
  );
}

/** Exclude: a circle with a bar. */
export function BanIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M4.2 4.2l7.6 7.6" />
    </Glyph>
  );
}

/** Include again: an arrow turning back. */
export function UndoIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M6 4.5L3.5 7l2.5 2.5" />
      <path d="M3.5 7h5.25a3.25 3.25 0 010 6.5H7" />
    </Glyph>
  );
}

/** Sidebar toggle: a panel with its left column marked. */
export function PanelIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <rect x="2" y="3" width="12" height="10" rx="1" />
      <path d="M6 3v10" />
    </Glyph>
  );
}

/** Close the sidebar: the panel, its left column, and a chevron tucking in. */
export function PanelCloseIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <rect x="2" y="3" width="12" height="10" rx="1" />
      <path d="M6 3v10" />
      <path d="M11.5 6 9.5 8l2 2" />
    </Glyph>
  );
}

export function PencilIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M11.5 2.5a1.4 1.4 0 0 1 2 2L5 13l-3 1 1-3 8.5-8.5Z" />
    </Glyph>
  );
}

export function ArchiveIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <rect x="2" y="3" width="12" height="3.5" rx="0.5" />
      <path d="M3.5 6.5V13h9V6.5M6.5 9h3" />
    </Glyph>
  );
}

export function RestoreIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M2 8a6 6 0 1 1 1.8 4.3" />
      <path d="M2 8V4.5M2 8h3.5" />
    </Glyph>
  );
}

/** One chat (the rail's marks); the stacked `ChatsIcon` is the list. */
export function ChatIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M2.5 3.5h11v7.5H7l-3 2.5v-2.5H2.5v-7.5Z" />
    </Glyph>
  );
}

/** Stacked speech bubbles: the conversation-list glyph on the overlay's header. */
export function ChatsIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M5 4h9v7h-3l-2 2-2-2H5z" />
      <path d="M3 8H2V1h9v1" />
    </Glyph>
  );
}

/** Open in the Agent tab: an arrow leaving the corner of a frame. */
export function ExpandIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M9 3h4v4M13 3 7.5 8.5" />
      <path d="M12 9.5V13H3V4h3.5" />
    </Glyph>
  );
}

/** Down to the end of a transcript. */
export function ArrowDownIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M8 3v10M3.5 8.5 8 13l4.5-4.5" />
    </Glyph>
  );
}

/** Download: an arrow into a tray (the sources' Download CSV, round 12). */
export function DownloadIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M8 2.5v7.5M4.75 6.75 8 10l3.25-3.25" />
      <path d="M3 13h10" />
    </Glyph>
  );
}

/** More: a list row's own menu (Rename, Add to project, Archive; owner,
 *  round 12). Three dots across the grid's middle, drawn as round-capped
 *  zero-length strokes so they take the module's stroke weight. */
export function MoreIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M3.5 8h0M8 8h0M12.5 8h0" strokeWidth="2.25" />
    </Glyph>
  );
}

/** Points right; rotate with a class when a disclosure is open. */
export function ChevronIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M6 3.5 10.5 8 6 12.5" />
    </Glyph>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </Glyph>
  );
}

/** About: the "i" after a heading whose tooltip says what the block is
 *  (the option card's What it would take, round 12). */
export function InfoIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7.25v3.75" />
      <path d="M8 4.9v.1" />
    </Glyph>
  );
}

/** Find: the list pages' "Find a task" / "Find a project" (round 11). */
export function SearchIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5 13.5 13.5" />
    </Glyph>
  );
}
