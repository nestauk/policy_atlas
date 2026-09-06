/**
 * The kinds of work the system can do.
 *
 * Three are listed but cannot run yet. The shape of the product stays visible
 * so scoping options reads as planned rather than forgotten.
 */
export const CAPABILITIES = [
  {
    key: "evidence_search",
    name: "Evidence search",
    available: true,
  },
  {
    key: "scoping_policy_options",
    name: "Scoping policy options",
    available: false,
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

/**
 * Human label for a capability key on list surfaces.
 *
 * The tasks API does not carry capability yet; every live task is evidence
 * search until that field lands, so a missing key falls back honestly.
 */
export function capabilityLabel(key?: string | null): string {
  if (key == null) return LABEL_BY_KEY.get("evidence_search") ?? "Evidence search";
  return LABEL_BY_KEY.get(key) ?? key;
}
