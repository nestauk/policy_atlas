import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { PAGE_CONTROL_CLASS } from "../ui/brand/PageHeader";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";

/** One thing the popover can find: its name, where it opens, and when it
 *  last changed (for the starting list). */
export type FindItem = {
  id: string;
  label: string;
  href: string;
  updatedAt: string;
};

/** How long the field waits after a keystroke before it filters. */
export const FIND_DEBOUNCE_MS = 150;

/** How many recent items the empty field offers as a starting list. */
export const FIND_RECENT_COUNT = 5;

/** The list's words, by what it finds ("tasks", "projects"). */
type FindCopy = {
  /** The trigger's label and the field's name ("Find a task"). */
  label: string;
  /** The plural noun ("tasks"). */
  noun: string;
};

/** The items whose name holds every typed word, or the most recent few
 *  when nothing is typed. Matching ignores case and word order. */
export function findMatches(items: readonly FindItem[], words: string): FindItem[] {
  const needles = words.trim().toLowerCase().split(/\s+/).filter((word) => word !== "");
  if (needles.length === 0) {
    return [...items]
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
      .slice(0, FIND_RECENT_COUNT);
  }
  return items.filter((item) => {
    const haystack = item.label.toLowerCase();
    return needles.every((needle) => haystack.includes(needle));
  });
}

/** The typed words, settled `FIND_DEBOUNCE_MS` after the last keystroke.
 *  An emptied field settles at once (back to the starting list). */
function useSettled(value: string): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), FIND_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [value]);
  return value.trim() === "" ? value : settled;
}

/**
 * "Find a task" and "Find a project" (task 058 consistency pass, owner and
 * lead rulings): a page-header control that opens a popover under itself.
 *
 * - The field is focused on open; Escape and an outside press close it, and
 *   focus returns to the trigger (Radix).
 * - With nothing typed the field shows no result line, only the most recent
 *   five as a starting list. Results follow the typing 150 ms after the last
 *   key; "No tasks match “…”" appears only once there are words.
 * - The field is a combobox: the arrow keys move the highlighted row, Enter
 *   opens it. The highlight is the menu-item wash, never blue text, and the
 *   matched words are not marked (blue is the one pen).
 * - The popover is the system's popover: Paper, a Line 2 hairline, the
 *   overlay lift, 16 px padding, 384 px wide (capped at 92vw), scaling in
 *   from its trigger on the strong ease-out.
 */
export function FindPopover({ items, copy }: { items: readonly FindItem[]; copy: FindCopy }) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [active, setActive] = useState(0);
  const settled = useSettled(term);
  const matches = useMemo(() => findMatches(items, settled), [items, settled]);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const optionId = (index: number) => `${listId}-option-${index}`;
  const typed = settled.trim() !== "";
  const highlighted = Math.min(active, Math.max(matches.length - 1, 0));

  const choose = (item: FindItem) => {
    setOpen(false);
    void navigate(item.href);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setTerm("");
          setActive(0);
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" className={cn(PAGE_CONTROL_CLASS, open && "text-navy")}>
          {copy.label}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        aria-label={copy.label}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <label className="sr-only" htmlFor={`${listId}-field`}>
          {copy.label}
        </label>
        <input
          ref={inputRef}
          id={`${listId}-field`}
          role="combobox"
          aria-expanded={matches.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={matches.length > 0 ? optionId(highlighted) : undefined}
          autoComplete="off"
          value={term}
          onChange={(event) => {
            setTerm(event.target.value);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((index) => Math.min(index + 1, matches.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((index) => Math.max(index - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              const item = matches[highlighted];
              if (item !== undefined) choose(item);
            }
          }}
          placeholder={`Search your ${copy.noun} by name`}
          className="h-10 w-full border border-line-2 bg-paper px-3 text-body text-navy placeholder:text-grey"
        />
        {typed && matches.length === 0 ? (
          <p role="status" className="mt-3 text-body text-grey">
            No {copy.noun} match “{scrub(settled.trim())}”
          </p>
        ) : matches.length === 0 ? null : (
          <ul id={listId} role="listbox" aria-label={copy.label} className="-mx-4 -mb-4 mt-3 max-h-80 overflow-y-auto border-t border-line">
            {matches.map((item, index) => (
              <li
                key={item.id}
                id={optionId(index)}
                role="option"
                aria-selected={index === highlighted}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(item)}
                className={cn(
                  "flex h-10 cursor-pointer items-center px-4 text-body text-navy",
                  index === highlighted && "bg-blue-tint-2",
                )}
              >
                <span className="truncate">{scrub(item.label)}</span>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
