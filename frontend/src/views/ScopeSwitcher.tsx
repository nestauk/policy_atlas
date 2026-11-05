import { TENANCY_COPY } from "../lib/vocabulary";
import { cn } from "../ui/brand/cn";

export type Scope = "all" | "mine";

/**
 * The Organisation/Mine switcher (task 033 phase 10b, contract § 11).
 *
 * Two options, no component label — the pair is the whole affordance
 * (lead-owned copy, binding). Callers hide this entirely rather than pass a
 * flag into it: whether `/me` has an organisation is the dark-launch
 * invariant (rubric 14) and belongs at the call site, so this component
 * carries no visibility logic of its own to get wrong.
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
  // The active option is a 2 px Electric Blue rule, never a fill (lead
  // ruling P4; DESIGN.md § Shapes): the page's one blue fill is its primary.
  // Each label reserves its Extrabold width, so choosing one never nudges
  // the other sideways.
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
            "inline-grid cursor-pointer items-center border-b-2 pt-0.5 text-meta",
            "transition-colors duration-150 ease-[ease]",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue",
            scope === value
              ? "border-blue font-extrabold text-navy"
              : "border-transparent font-semibold text-grey hover:text-navy",
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
