import { useId, useRef, useState, type KeyboardEvent, type ReactElement } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "../radix/Popover";
import { cn } from "./cn";
import { ChevronIcon } from "./icons";

/** One choice in a `Select`: its value, its words and an optional grey line under them. */
export interface SelectOption<V extends string = string> {
  value: V;
  label: string;
  sub?: string;
}

/** The keys that move the highlight inside the open list. */
const MOVE_KEYS = new Set(["ArrowDown", "ArrowUp", "Home", "End"]);

/**
 * The app's one dropdown (round 12, owner: "make sure we use the custom
 * styling and not the browser default"): the field's skin as the trigger
 * (Paper, a 1 px Line 2 border, square, the 12 px chevron at the right) and
 * the popover's tokens for the list, the Sources filter bar's listbox made
 * shared. No native `<select>` and no phone picker: the list opens as a
 * popover at every width.
 *
 * Keyboard: Enter, Space or the arrow keys on the trigger open the list on
 * the chosen value; the arrow keys, Home and End move through it; a letter
 * moves to the next choice starting with it; Enter or Space picks; Escape
 * or a press outside closes it and returns focus to the trigger.
 *
 * Args:
 *   label: The control's name; the trigger is a select-only combobox (the
 *     ARIA pattern), so a screen reader reads the chosen words as its value.
 *   value: The chosen value; one not among `options` shows `placeholder`.
 *   options: The choices, in order.
 *   onChange: Called with the picked value (also when it is the chosen one).
 *   disabled: Inert, in the field's disabled look.
 *   size: 40 (Body, the field's height) or 32 (Meta, inside a card or panel).
 *   placeholder: The words shown while no choice is chosen.
 *   id: The trigger's id, so a visible `<label htmlFor>` can point at it.
 *   className: Width and placement of the trigger.
 *   renderTrigger: A trigger of the caller's own in place of the field's
 *     (round 12: the Sources filter bar's outline box and applied chip). It
 *     gets the open state and the chosen option, and must be one element
 *     that forwards its ref and props to a button (the popover's trigger
 *     merges its own onto it). Omitted, the field's trigger shows.
 *   contentClassName: Width of the open list, when the trigger's is too
 *     narrow for the choices.
 */
export function Select<V extends string>({
  label,
  value,
  options,
  onChange,
  disabled = false,
  size = 40,
  placeholder,
  id,
  className,
  renderTrigger,
  contentClassName,
}: {
  label: string;
  value: V | "";
  options: ReadonlyArray<SelectOption<V>>;
  onChange: (value: V) => void;
  disabled?: boolean;
  size?: 32 | 40;
  placeholder?: string;
  id?: string;
  className?: string;
  renderTrigger?: (state: { open: boolean; chosen: SelectOption<V> | undefined }) => ReactElement;
  contentClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();
  const chosen = options.find((option) => option.value === value);
  const shown = chosen?.label ?? placeholder ?? "";

  const optionButtons = () =>
    Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
  const pick = (next: V) => {
    onChange(next);
    setOpen(false);
  };
  const onListKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const buttons = optionButtons();
    if (buttons.length === 0) return;
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (MOVE_KEYS.has(event.key)) {
      event.preventDefault();
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? buttons.length - 1
            : event.key === "ArrowDown"
              ? Math.min(current + 1, buttons.length - 1)
              : Math.max(current - 1, 0);
      buttons[next]?.focus();
      return;
    }
    // Type-ahead on the first letter: the next choice after the current one
    // whose words start with it, wrapping round.
    if (event.key.length === 1 && /\S/.test(event.key) && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const letter = event.key.toLocaleLowerCase();
      for (let step = 1; step <= buttons.length; step += 1) {
        const index = (current + step) % buttons.length;
        if ((options[index]?.label ?? "").toLocaleLowerCase().startsWith(letter)) {
          event.preventDefault();
          buttons[index]?.focus();
          return;
        }
      }
    }
  };

  return (
    <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
      <PopoverTrigger asChild>
        {renderTrigger !== undefined ? renderTrigger({ open, chosen }) : (
        <button
          type="button"
          id={id}
          disabled={disabled}
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-label={label}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setOpen(true);
            }
          }}
          className={cn(
            "relative inline-flex max-w-full min-w-0 cursor-pointer items-center border bg-paper pr-9 pl-3 text-left text-ink",
            "transition-colors duration-150",
            size === 40 ? "h-10 text-body" : "h-8 text-meta",
            open ? "border-navy" : "border-line-2",
            "disabled:cursor-default disabled:bg-ground disabled:text-grey",
            className,
          )}
        >
          <span className={cn("min-w-0 flex-1 truncate", chosen === undefined && "text-grey")}>{shown}</span>
          <ChevronIcon
            size={12}
            className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90 text-grey"
          />
        </button>
        )}
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn("w-[var(--radix-popover-trigger-width)] min-w-48 max-w-[calc(100vw-2rem)] p-1", contentClassName)}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          const buttons = optionButtons();
          (buttons.find((button) => button.getAttribute("aria-selected") === "true") ?? buttons[0])?.focus();
        }}
      >
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          aria-label={label}
          onKeyDown={onListKeyDown}
          className="flex max-h-80 flex-col overflow-y-auto"
        >
          {options.map((option) => {
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
                  <span className="block">{option.label}</span>
                  {option.sub !== undefined && option.sub !== "" && (
                    <span className="mt-0.5 block text-caption font-normal text-grey">{option.sub}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
