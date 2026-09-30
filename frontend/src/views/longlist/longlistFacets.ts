/** The Tried on facet's chips and filter (task 046, amendment 3, R54): every
 *  kind an option's evidence covers, the most options first, then by name.
 *  Labels only: no counts. */
export function triedOnKinds(options: readonly { tried_on?: readonly { kind: string }[] | null }[]): string[] {
  const counts = new Map<string, number>();
  for (const option of options) {
    const seen = new Set<string>();
    for (const entry of option.tried_on ?? []) {
      if (seen.has(entry.kind)) continue;
      seen.add(entry.kind);
      counts.set(entry.kind, (counts.get(entry.kind) ?? 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([kind]) => kind);
}

/** Whether an option's evidence covers one Tried on kind. */
export function matchesTriedOn(triedOn: readonly { kind: string }[] | null | undefined, kind: string): boolean {
  return (triedOn ?? []).some((entry) => entry.kind === kind);
}
