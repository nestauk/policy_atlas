import { useFeatureFlagEnabled } from "posthog-js/react";

/**
 * The kinds of work the system can do.
 *
 * Two are listed but cannot run yet. The shape of the product stays visible
 * so the rest reads as planned rather than forgotten.
 */
export const CAPABILITIES = [
  {
    key: "evidence_search",
    name: "Evidence search",
    available: true,
  },
  {
    // The key is the API's stored `task.capability` value, so
    // the label lookup below works straight off `TaskOut.capability` with no
    // translation table in between.
    key: "options_scoping",
    name: "Options scoping",
    // The PostHog feature flag `options_scoping` decides this at run time
    // (`useCapabilities` below). VITE_OPTIONS_SCOPING=1 is only the fallback
    // for a build with no PostHog token (local dev, tests) and for the moment
    // before the flags arrive. Delete both once shortlist + assessment land.
    available: import.meta.env.VITE_OPTIONS_SCOPING === "1",
  },
  {
    key: "theory_of_change",
    name: "Theory of change",
    // The PostHog feature flag `theory_of_change` decides this, with
    // VITE_THEORY_OF_CHANGE=1 as the fallback, like Options scoping above.
    // The API has its own switch (POLICY_ATLAS_THEORY_OF_CHANGE) and refuses
    // to create one while that is off, whatever the flag says.
    available: import.meta.env.VITE_THEORY_OF_CHANGE === "1",
  },
  {
    key: "map_stakeholders",
    name: "Mapping stakeholders",
    available: false,
  },
] as const;

const LABEL_BY_KEY = new Map<string, string>(
  CAPABILITIES.map((capability) => [capability.key, capability.name]),
);

/**
 * The capability list, with PostHog feature flags deciding the flagged entries.
 *
 * A flag's key is the capability's key. Each flag gives true or false once
 * PostHog has answered, and undefined when PostHog is not running, has not
 * answered yet, or has no flag of that key; the entry then keeps its
 * environment-variable default from `CAPABILITIES`.
 *
 * Returns:
 *   `CAPABILITIES` with `available` settled for the current person.
 */
export function useCapabilities() {
  const flags: Record<string, boolean | undefined> = {
    options_scoping: useFeatureFlagEnabled("options_scoping"),
    theory_of_change: useFeatureFlagEnabled("theory_of_change"),
  };
  return CAPABILITIES.map((capability) => ({
    ...capability,
    available: flags[capability.key] ?? capability.available,
  }));
}

/** One of the keys the New task screen can offer. */
export type SelectableCapabilityKey = "evidence_search" | "options_scoping" | "theory_of_change";

/**
 * Whether a URL parameter names a capability a new task can be created with.
 *
 * Args:
 *   key: A raw `?capability=` value, or null when the parameter is absent.
 *   capabilities: The list to check against; pass `useCapabilities()` so
 *     feature flags count. Defaults to the build-time list.
 *
 * Returns:
 *   Whether the value is one of the selectable keys.
 */
export function isSelectableCapability(
  key: string | null | undefined,
  capabilities: readonly { key: string; available: boolean }[] = CAPABILITIES,
): key is SelectableCapabilityKey {
  return capabilities.some((capability) => capability.key === key && capability.available);
}

/**
 * Human label for a capability key on list surfaces.
 *
 * `TaskOut.capability` carries the key, but the fallback
 * stays: an older client reading a newer key should show the key rather than
 * nothing, and a row with no key at all predates the capability field (an
 * Evidence search).
 */
export function capabilityLabel(key?: string | null): string {
  if (key == null) return LABEL_BY_KEY.get("evidence_search") ?? "Evidence search";
  return LABEL_BY_KEY.get(key) ?? key;
}
