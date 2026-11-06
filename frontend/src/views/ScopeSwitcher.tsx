import { TENANCY_COPY } from "../lib/vocabulary";
import { cn } from "../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../ui/brand/inlineActions";
import { GROWING_RULE_ACTIVE_CLASS, GROWING_RULE_CLASS } from "../ui/brand/Nav";

export type Scope = "all" | "mine";

/** The tab language's growing rule at the switcher's 2 px: the shared
 *  rule's height and offset overridden, its motion kept. */
const SWITCHER_RULE_CLASS = cn(GROWING_RULE_CLASS, "after:-bottom-0.5 after:h-0.5");

/**
 * The Mine / Organisation switcher (task 033 phase 10b, contract § 11).
 *
 * Two scopes only: Archived is not a scope (owner, round 11) but a toggle
 * at the end of the Tasks page's filters row that lists the archived tasks
 * of whichever scope is open.
 *
 * No component label — the options are the whole affordance (lead-owned
 * copy, binding). Whether the switcher shows at all is the dark-launch
 * invariant (rubric 14: only when `/me` has an organisation) and belongs at
 * the call site, so this component carries no visibility logic of its own.
 */
export function ScopeSwitcher({
  scope,
  onChange,
}: {
  scope: Scope;
  onChange: (next: Scope) => void;
}) {
  const options: { value: Scope; label: string }[] = [
    // Mine first: it is the default (owner, 2026-09-05).
    { value: "mine", label: TENANCY_COPY.scopeMine },
    { value: "all", label: TENANCY_COPY.scopeOrganisation },
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

/** The list's heading while the archive is open: "Archived" at Meta
 *  Semibold Navy, 8 px over the frame (owner, round 11). */
export const ARCHIVED_HEADING_CLASS = "mb-2 text-meta font-semibold text-navy";

/**
 * The archived toggle (owner, round 11), on Tasks and Projects: not a scope
 * but a filter on the open one, and one people will hardly ever use, so it
 * sits at the list's foot, right-aligned after "Show more" (`ListFootRow`),
 * as the quiet control the run trace uses for "See the plan" and "Show
 * steps", at Caption: "Show archived" off, "Hide archived" on. The
 * changing label carries the state, so there is no `aria-pressed` (lead
 * ruling, round 11: it would say the state twice). Its box is the foot
 * row's 40 px for a full-height target, and it reserves the wider label's
 * width so the words never shift its edge.
 */
export function ArchivedToggle({ pressed, onToggle }: { pressed: boolean; onToggle: () => void }) {
  const label = pressed ? "Hide archived" : "Show archived";
  const other = pressed ? "Show archived" : "Hide archived";
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(QUIET_CONTROL_CLASS, "inline-grid min-h-10 items-center justify-items-end whitespace-nowrap text-caption")}
    >
      <span className="col-start-1 row-start-1">{label}</span>
      <span aria-hidden="true" className="invisible col-start-1 row-start-1">
        {other}
      </span>
    </button>
  );
}
