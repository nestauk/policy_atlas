import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ComponentPropsWithoutRef, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";
import { CloseIcon } from "./icons";

/*
 * Chip/pill (hifi.css .chip family): squared-off status and tag markers.
 * Tone maps to meaning, never meaning to colour alone — pair every toned
 * chip with its text label (labels-not-scores discipline).
 */
// Pre-sweep brand sizing restored by owner ruling (2026-08-05): 11.5px is a
// deliberate off-scale chip token — chips sit below caption text.
const chipVariants = cva(
  "inline-flex items-center gap-1.5 border px-2.5 py-1 text-[11.5px] font-semibold",
  {
    variants: {
      tone: {
        default: "border-line-2 bg-paper text-navy",
        blue: "border-[#c7c7ff] bg-blue-tint text-blue",
        soft: "border-line bg-ground text-grey",
        green: "border-[#b7e0d8] bg-green-tint text-[#0c6b5a]",
        yellow: "border-[#f3d99a] bg-yellow-tint text-[#8a5a00]",
        red: "border-[#f4b8c6] bg-red-tint text-red",
      },
    },
    defaultVariants: { tone: "default" },
  },
);

export type ChipProps = HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof chipVariants>;

/** Squared Nesta chip for statuses, tags and counts. */
export function Chip({ className, tone, ...props }: ChipProps) {
  return <span className={cn(chipVariants({ tone }), className)} {...props} />;
}

/** The filter bar's control box: 32 px, Meta Semibold, one line. */
export const FILTER_CONTROL_BASE =
  "inline-flex h-8 min-w-0 shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap border px-2.5 text-meta font-semibold transition-colors duration-150";

/** An idle filter: the outline box (Line 2 border, Navy Semibold, hover
 *  #f0f0f3) at the bar's height. */
const IDLE_CHIP_CLASS = `${FILTER_CONTROL_BASE} border-line-2 bg-paper text-navy hover:bg-[#f0f0f3]`;

/** An applied filter: the filled Navy chip with its × inside it. */
const APPLIED_CHIP_CLASS =
  "inline-flex h-8 min-w-0 max-w-full shrink-0 items-stretch border border-navy bg-navy text-meta font-semibold text-paper";

/** One part of an applied chip (its words, its ×): Navy Line on hover. */
const APPLIED_CHIP_PART_CLASS =
  "inline-flex min-w-0 cursor-pointer items-center gap-1.5 whitespace-nowrap transition-colors duration-150 hover:bg-navy-line focus-visible:outline-offset-[-4px] focus-visible:outline-paper";

export type FilterChipProps = Omit<ComponentPropsWithoutRef<"button">, "children"> & {
  /** Whether the filter narrows the view (the Navy chip) or waits (the box). */
  applied: boolean;
  /** The chip's words: "Cited", "Country: France". */
  children: ReactNode;
  /** Applied: what the × does. No × without it. */
  onClear?: () => void;
  /** Applied: the ×'s name ("Clear the country filter"). */
  clearLabel?: string;
  /** Applied: the words and the × are one button, which clears (a toggle
   *  such as Cited). Otherwise the words are their own part. */
  whole?: boolean;
  /** Applied: the words are text, not a button (a chosen item; a filter set
   *  from elsewhere, cleared only by its ×). */
  staticWords?: boolean;
  /** Idle: what follows the words (a select's chevron). */
  trailing?: ReactNode;
  /** Classes on the words (a truncation cap). */
  wordsClassName?: string;
};

/**
 * The filter chip (task 058, consolidation batch B): the Sources filter
 * bar's look, defined once. Idle, the outline box; applied, the filled Navy
 * chip with its × inside it. Its words are a button (the ref's) that applies
 * the filter or opens its choices, or with `whole` the whole chip is the
 * button that clears it; the × is its own button when the words are not.
 * The Sources filters, the multi-select's chosen items and the plan card's
 * scope chips use it.
 */
export const FilterChip = forwardRef<HTMLButtonElement, FilterChipProps>(function FilterChip(
  { applied, children, onClear, clearLabel, whole = false, staticWords = false, trailing, wordsClassName, className, ...props },
  ref,
) {
  if (!applied) {
    return (
      <button ref={ref} type="button" className={cn(IDLE_CHIP_CLASS, className)} {...props}>
        {wordsClassName === undefined ? children : <span className={wordsClassName}>{children}</span>}
        {trailing}
      </button>
    );
  }
  if (whole) {
    return (
      <span className={cn(APPLIED_CHIP_CLASS, className)}>
        <button ref={ref} type="button" aria-pressed {...props} onClick={onClear} className={cn(APPLIED_CHIP_PART_CLASS, "pl-2.5 pr-2")}>
          {wordsClassName === undefined ? children : <span className={wordsClassName}>{children}</span>}
          <CloseIcon size={12} />
        </button>
      </span>
    );
  }
  const words = <span className={cn("truncate", wordsClassName)}>{children}</span>;
  return (
    <span className={cn(APPLIED_CHIP_CLASS, className)}>
      {staticWords ? (
        <span className={cn(APPLIED_CHIP_PART_CLASS, "cursor-default pl-2.5 pr-2 hover:bg-transparent")}>{words}</span>
      ) : (
        <button ref={ref} type="button" className={cn(APPLIED_CHIP_PART_CLASS, "pl-2.5 pr-2")} {...props}>
          {words}
        </button>
      )}
      {onClear !== undefined && (
        <button
          type="button"
          aria-label={clearLabel}
          onClick={onClear}
          className={cn(APPLIED_CHIP_PART_CLASS, "border-l border-navy-line px-2")}
        >
          <CloseIcon size={12} />
        </button>
      )}
    </span>
  );
});
