import type { ReactNode } from "react";

import { cn } from "./cn";

/** A bulleted item: the bullet, then the text, on the first line's baseline. */
export const BULLET_ITEM_CLASS = "flex items-baseline gap-2";

/** The report's 6 px Electric Blue square, its middle on the text's x-height
 *  at any size (owner, round 11): baseline alignment puts its bottom edge on
 *  the baseline, then it rises by half an `ex` less half its height. */
export const BULLET_MARK_CLASS = "relative bottom-[calc(0.5ex_-_3px)] size-1.5 shrink-0";

/**
 * The report's bulleted list, shared (round 12, owner: the option card reads
 * as a mini report): an Electric Blue square before each item, items 12 px
 * apart, no browser marker. `data-bullet` prints the square as a border,
 * since print drops backgrounds (`index.css`).
 *
 * Args:
 *   items: The items' contents, in order.
 *   className: Extra classes for the list (its measure, its size).
 *   label: An accessible name for the list, when it needs one.
 */
export function BulletList({
  items,
  className,
  label,
}: {
  items: readonly ReactNode[];
  className?: string;
  label?: string;
}) {
  return (
    <ul role="list" aria-label={label} className={cn("list-none space-y-3", className)}>
      {items.map((item, index) => (
        <li key={index} className={BULLET_ITEM_CLASS}>
          <span aria-hidden="true" data-bullet="" className={cn(BULLET_MARK_CLASS, "bg-blue")} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
