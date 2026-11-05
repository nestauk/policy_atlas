import { scrub } from "../../lib/scrub";

const COUNTRY_ALIASES: Record<string, string> = {
  GB: "United Kingdom",
  UK: "United Kingdom",
  "UNITED KINGDOM": "United Kingdom",
  US: "United States",
  USA: "United States",
  "UNITED STATES": "United States",
};

/** Present a data-value label (classifier tags arrive snake_cased). These are
 *  data values, not locked enum vocabulary — presentation-casing is honest. */
export function humaniseLabel(raw: string): string {
  const clean = scrub(raw).replaceAll("_", " ").trim();
  return clean.length === 0 ? clean : clean[0].toUpperCase() + clean.slice(1);
}

/** Normalise mixed ISO and name geography inputs before chart labels render. */
export function normaliseGeographies(data: Record<string, number>): Record<string, number> {
  return Object.entries(data).reduce<Record<string, number>>((normalised, [rawLabel, count]) => {
    const clean = scrub(rawLabel).trim();
    const label = COUNTRY_ALIASES[clean.toUpperCase()] ?? clean;
    normalised[label] = (normalised[label] ?? 0) + count;
    return normalised;
  }, {});
}

/** Fill the inclusive evidence-year range so a missing year stays visible at zero. */
export function fillYearRange(data: Record<string, number>): Array<{ label: string; count: number }> {
  const years = Object.entries(data).flatMap(([label, count]) => {
    const year = Number(label);
    return /^\d{4}$/.test(label) && Number.isInteger(year) ? [{ year, count }] : [];
  });
  if (years.length === 0) return [];
  const counts = new Map(years.map(({ year, count }) => [year, count]));
  const first = Math.min(...counts.keys());
  const last = Math.max(...counts.keys());
  return Array.from({ length: last - first + 1 }, (_, index) => {
    const year = first + index;
    return { label: String(year), count: counts.get(year) ?? 0 };
  });
}

/** Discovered themes, largest first (owner rule, 2026-07-29). */
export function orderThemes<T extends { size: number }>(themes: T[]): T[] {
  return [...themes].sort((a, b) => b.size - a.size);
}
