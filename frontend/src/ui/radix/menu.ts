import type { KeyboardEvent } from "react";

/** A menu row (DESIGN.md § Overlays, Menu): 40 px, Meta Semibold Navy,
 *  hovering and focusing to the Blue Wash with blue text. The menu draws its
 *  focus as the wash, inside the row, so the ring never spills past the
 *  menu's edge. */
export const MENU_ITEM_CLASS =
  "flex h-10 w-full cursor-pointer items-center px-4 text-left text-meta font-semibold text-navy " +
  "transition-colors duration-150 hover:bg-blue-tint-2 hover:text-blue " +
  "focus-visible:bg-blue-tint-2 focus-visible:text-blue focus-visible:outline-2 focus-visible:-outline-offset-2";

/** Arrow keys, Home and End move focus between a menu's items, wrapping. */
export function moveMenuFocus(event: KeyboardEvent<HTMLElement>, menu: HTMLElement | null) {
  if (menu === null) return;
  const items = [...menu.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])')];
  if (items.length === 0) return;
  const at = items.indexOf(document.activeElement as HTMLElement);
  let next: number | null = null;
  if (event.key === "ArrowDown") next = at < 0 ? 0 : (at + 1) % items.length;
  else if (event.key === "ArrowUp") next = at < 0 ? items.length - 1 : (at - 1 + items.length) % items.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = items.length - 1;
  if (next === null) return;
  event.preventDefault();
  items[next].focus();
}
