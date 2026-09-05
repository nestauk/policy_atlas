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
  return (
    <div role="tablist" aria-label="Scope" className="inline-flex border border-line-2">
      {options.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          role="tab"
          aria-selected={scope === value}
          onClick={() => onChange(value)}
          className={cn(
            "px-3.5 py-2 text-meta font-semibold",
            scope === value
              ? "bg-blue text-white"
              : "bg-paper text-navy hover:bg-blue-tint-2",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
