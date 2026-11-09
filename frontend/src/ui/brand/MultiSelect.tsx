import { useId, useRef, useState } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "../radix/Popover";
import { APPLIED_CHIP_CLASS, APPLIED_CHIP_PART_CLASS } from "./Chip";
import { Checkbox } from "./Checkbox";
import { cn } from "./cn";
import { ChevronIcon, CloseIcon } from "./icons";
import type { SelectOption } from "./Select";

/**
 * The app's searchable multi-select (owner, round 14; first used by the New
 * page's "Evidence search to start from"). Built on the `Select`'s skin and
 * popover: the field's trigger (Paper, a Line 2 border, square, the 12 px
 * chevron), reading the placeholder with nothing chosen, the one choice's
 * words with one, "2 selected" with more. The list opens with a filter field
 * at its top (focused as it opens; typing narrows the rows by their words)
 * and a row per choice through the shared `Checkbox`, its grey line under
 * it. The chosen ones show under the trigger as the applied Navy chips, each
 * with its × to take it out.
 *
 * Args:
 *   id: The trigger's id, so a visible `<label htmlFor>` can point at it.
 *   label: The control's name (the trigger and the list).
 *   options: The choices, in order; `sub` is the grey line under one.
 *   values: The chosen values, in the order chosen.
 *   onChange: Called with the next chosen values.
 *   placeholder: The trigger's words while nothing is chosen.
 *   filterLabel: The filter field's name and placeholder.
 *   empty: What the list says when nothing matches the filter (or there is
 *     nothing to choose).
 *   disabled: Inert, in the field's disabled look (Ground, Grey words); the
 *     trigger reads `placeholder`, so the caller words why ("Choose a
 *     project first").
 *   className: Width and placement of the trigger.
 */
export function MultiSelect<V extends string>({
  id,
  label,
  options,
  values,
  onChange,
  placeholder,
  filterLabel,
  empty,
  disabled = false,
  className,
}: {
  id?: string;
  label: string;
  options: ReadonlyArray<SelectOption<V>>;
  values: readonly V[];
  onChange: (values: V[]) => void;
  placeholder: string;
  filterLabel: string;
  empty: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const filterRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const chosen = values
    .map((value) => options.find((option) => option.value === value))
    .filter((option): option is SelectOption<V> => option !== undefined);
  const shown =
    disabled || chosen.length === 0
      ? placeholder
      : chosen.length === 1
        ? chosen[0].label
        : `${chosen.length} selected`;
  const needle = filter.trim().toLocaleLowerCase();
  const listed = needle === "" ? options : options.filter((option) => option.label.toLocaleLowerCase().includes(needle));
  const toggle = (value: V) =>
    onChange(values.includes(value) ? values.filter((chosenValue) => chosenValue !== value) : [...values, value]);

  return (
    <div className={className}>
      <Popover
        open={open && !disabled}
        onOpenChange={(next) => {
          if (disabled) return;
          setOpen(next);
          if (!next) setFilter("");
        }}
      >
        <PopoverTrigger asChild>
          <button
            type="button"
            id={id}
            disabled={disabled}
            // A button that opens a small dialog (a filter field and checkbox
            // rows), not a combobox: its rows are checkboxes, not options.
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-controls={open ? listId : undefined}
            aria-label={`${label}: ${shown}`}
            className={cn(
              "relative inline-flex h-10 w-full min-w-0 cursor-pointer items-center border bg-paper pr-9 pl-3 text-left text-body text-ink",
              "transition-colors duration-150",
              open ? "border-navy" : "border-line-2",
              "disabled:cursor-default disabled:bg-ground disabled:text-grey",
            )}
          >
            <span className={cn("min-w-0 flex-1 truncate", (disabled || chosen.length === 0) && "text-grey")}>{shown}</span>
            <ChevronIcon
              size={12}
              className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90 text-grey"
            />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-[var(--radix-popover-trigger-width)] min-w-64 max-w-[calc(100vw-2rem)] p-1"
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
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="mb-1 h-10 w-full border border-line-2 bg-paper px-3 text-body text-ink focus-visible:outline-2 focus-visible:outline-blue"
          />
          <ul id={listId} role="group" aria-label={label} className="flex max-h-80 flex-col overflow-y-auto px-2">
            {listed.length === 0 ? (
              <li className="px-1 py-2 text-meta text-grey">{empty}</li>
            ) : (
              listed.map((option) => (
                <li key={option.value}>
                  <Checkbox
                    checked={values.includes(option.value)}
                    onChange={() => toggle(option.value)}
                    label={
                      <>
                        <span className="block text-body text-navy">{option.label}</span>
                        {option.sub !== undefined && option.sub !== "" && (
                          <span className="block text-meta text-grey">{option.sub}</span>
                        )}
                      </>
                    }
                  />
                </li>
              ))
            )}
          </ul>
        </PopoverContent>
      </Popover>
      {!disabled && chosen.length > 0 && (
        <ul aria-label={`${label}: chosen`} className="mt-2 flex flex-wrap gap-2">
          {chosen.map((option) => (
            <li key={option.value} className={APPLIED_CHIP_CLASS}>
              <span className={cn(APPLIED_CHIP_PART_CLASS, "cursor-default pl-2.5 pr-2 hover:bg-transparent")}>
                <span className="truncate">{option.label}</span>
              </span>
              <button
                type="button"
                aria-label={`Remove ${option.label}`}
                onClick={() => toggle(option.value)}
                className={cn(APPLIED_CHIP_PART_CLASS, "border-l border-navy-line px-2")}
              >
                <CloseIcon size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
