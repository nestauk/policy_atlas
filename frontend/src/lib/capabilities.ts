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
    // Task 044 (D5): the key is the API's stored `task.capability` value, so
    // the label lookup below works straight off `TaskOut.capability` with no
    // translation table in between.
    key: "options_scoping",
    name: "Options scoping",
    // Shown only where VITE_OPTIONS_SCOPING=1 at build time (local dev, staging,
    // tests). Production builds leave it unset until the capability is complete,
    // so the entry reads as planned there, like the two below. Delete the flag
    // once shortlist + assessment land.
    available: import.meta.env.VITE_OPTIONS_SCOPING === "1",
  },
  {
    key: "theory_of_change",
    name: "Theory of change",
    available: false,
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

/** The keys a new task can actually be created with (task 044). */
export const SELECTABLE_CAPABILITY_KEYS = CAPABILITIES.filter(
  // The predicate keeps the key union narrow: entries that are never
  // available drop out of the type as well as the array.
  (capability): capability is Exclude<typeof capability, { available: false }> =>
    capability.available,
).map((capability) => capability.key);

/** One of the keys the New task screen offers. */
export type SelectableCapabilityKey = (typeof SELECTABLE_CAPABILITY_KEYS)[number];

/**
 * Whether a URL parameter names a capability a new task can be created with.
 *
 * Args:
 *   key: A raw `?capability=` value, or null when the parameter is absent.
 *
 * Returns:
 *   Whether the value is one of the selectable keys.
 */
export function isSelectableCapability(
  key: string | null | undefined,
): key is SelectableCapabilityKey {
  return key != null && (SELECTABLE_CAPABILITY_KEYS as readonly string[]).includes(key);
}

/**
 * Human label for a capability key on list surfaces.
 *
 * `TaskOut.capability` carries the key from task 044 on, but the fallback
 * stays: an older client reading a newer key should show the key rather than
 * nothing, and a caller with no key at all is reading a pre-044 row.
 */
export function capabilityLabel(key?: string | null): string {
  if (key == null) return LABEL_BY_KEY.get("evidence_search") ?? "Evidence search";
  return LABEL_BY_KEY.get(key) ?? key;
}
