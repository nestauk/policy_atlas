import { TENANCY_COPY } from "../lib/vocabulary";
import { cn } from "../ui/brand/cn";
import { GROWING_RULE_ACTIVE_CLASS, GROWING_RULE_CLASS } from "../ui/brand/Nav";

export type Scope = "all" | "mine";

/** A list's view: a scope, or the reader's own archived tasks (round 10). */
export type ListView = Scope | "archived";

/** The tab language's growing rule at the switcher's 2 px: the shared
 *  rule's height and offset overridden, its motion kept. */
const SWITCHER_RULE_CLASS = cn(GROWING_RULE_CLASS, "after:-bottom-0.5 after:h-0.5");

/**
 * The Mine / Organisation switcher (task 033 phase 10b, contract § 11), with
 * the Archived entry on the Tasks page (round 10).
 *
 * No component label — the options are the whole affordance (lead-owned
 * copy, binding). Callers decide which options show: whether `/me` has an
 * organisation is the dark-launch invariant (rubric 14) and belongs at the
 * call site, so this component carries no visibility logic of its own.
 */
export function ScopeSwitcher({
  scope,
  onChange,
  showOrganisation = true,
  showArchived = false,
}: {
  scope: ListView;
  onChange: (next: ListView) => void;
  /** Off for a caller with no organisation (Mine then pairs with Archived). */
  showOrganisation?: boolean;
  /** The reader has archived tasks to list. */
  showArchived?: boolean;
}) {
  const options: { value: ListView; label: string }[] = [
    // Mine first: it is the default (owner, 2026-09-05).
    { value: "mine", label: TENANCY_COPY.scopeMine },
    ...(showOrganisation ? [{ value: "all" as const, label: TENANCY_COPY.scopeOrganisation }] : []),
    ...(showArchived ? [{ value: "archived" as const, label: "Archived" }] : []),
  ];
  // The tab language of the whole app (owner, round 10): a 2 px Electric
  // Blue rule grows from the item's left edge to its centre on hover and
  // focus over 200 ms, runs full width under the active item, and a click
  // carries it on to the right edge; under reduced motion it appears
  // without growing. Never a fill (lead ruling P4): the page's one blue fill
  // is its primary. Each label reserves its Extrabold width, so choosing one
  // never nudges the others sideways.
  return (
    <div role="tablist" aria-label="Scope" className="flex h-10 items-stretch gap-5">
      {options.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          role="tab"
          aria-selected={scope === value}
          onClick={() => onChange(value)}
          className={cn(
            "inline-grid cursor-pointer items-center border-b-2 border-transparent pt-0.5 text-meta",
            "transition-colors duration-150 ease-[ease]",
            SWITCHER_RULE_CLASS,
            scope === value
              ? cn(GROWING_RULE_ACTIVE_CLASS, "font-extrabold text-navy")
              : "font-semibold text-grey hover:text-navy",
          )}
        >
          <span className="col-start-1 row-start-1">{label}</span>
          <span aria-hidden="true" className="invisible col-start-1 row-start-1 font-extrabold">
            {label}
          </span>
        </button>
      ))}
    </div>
  );
}
