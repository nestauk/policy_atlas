import type { ReactNode } from "react";

import { cn } from "./cn";

/**
 * The app's checkbox (owner, round 13; first used by the New page's "Evidence
 * search to start from"): a 16 px square box in the plan card radio's
 * language, Navy at 40 % when empty, Navy filled with a white tick when
 * checked, Line 2 when disabled; square, as everything but the radio is.
 * The whole row is the control, a `role="checkbox"` button, its label beside
 * the box. The row washes Paper 2 on hover, as a radio row does.
 *
 * Args:
 *   checked: Whether the box is ticked.
 *   disabled: Inert, in the Line 2 look; it cannot be ticked.
 *   label: What the box is for, laid out by the caller (a name and a grey
 *     line under it, say); it is also the control's accessible name.
 *   onChange: Called with the next state when the row is pressed.
 */
export function Checkbox({
  checked,
  disabled = false,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: ReactNode;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-start gap-3 px-2 py-2 text-left transition-colors duration-150 hover:bg-paper-2 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue disabled:cursor-default disabled:hover:bg-transparent"
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-1 flex size-4 shrink-0 items-center justify-center border-2",
          checked ? "border-navy bg-navy text-paper" : disabled ? "border-line-2" : "border-navy/40",
        )}
      >
        {checked && (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.75">
            <path d="M1.5 5.25 4 7.5l4.5-5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      <span className="min-w-0">{label}</span>
    </button>
  );
}
