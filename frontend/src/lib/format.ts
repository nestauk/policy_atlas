/*
 * The one count formatter (task 058, consolidation batch B): every count a
 * reader sees, "1,234 sources", goes through `formatCount`, so the tables,
 * the counts lines and the run trace group their thousands the same way.
 */

const COUNT = new Intl.NumberFormat("en-GB");

/**
 * A count with its thousands grouped, en-GB: 1234 → "1,234".
 *
 * Args:
 *   n: The count.
 *
 * Returns:
 *   The count as the reader sees it.
 */
export function formatCount(n: number): string {
  return COUNT.format(n);
}
