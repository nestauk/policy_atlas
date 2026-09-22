import type { components } from "../../api/gen/types";

/**
 * Presentation helpers shared by the longlist's three surfaces (list view,
 * reduced grid, option card) — task 045 phase 6.2. Structure-and-plumbing:
 * every string here is either given verbatim by the task contract/brief or
 * a direct template of a read-model field. No summary prose, no writer
 * call — the option card is assembled, not written (D15).
 */

type WhereTriedOut = components["schemas"]["WhereTriedOut"];
type RelationOut = components["schemas"]["RelationOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

/** Capitalise a lever-type or ambition-band key's first letter only — the
 *  keys are already natural lowercase phrases ("tax or charge", "do
 *  minimum"), so nothing else needs changing. */
export function capitalise(value: string): string {
  return value.length === 0 ? value : value[0].toUpperCase() + value.slice(1);
}

/** The origin tag's exact wording (contract § Terms "entrant"; deliverable
 *  9's list view spec). `clustered` carries the document count; the other
 *  three are fixed phrases. */
export function originLabel(
  origin: OptionSummaryOut["origin"],
  documentCount: number,
): string {
  switch (origin) {
    case "clustered":
      return `clustered from ${documentCount} documents`;
    case "suggested":
      return "suggested by Policy Atlas";
    case "from_evidence_search":
      return "from your evidence search";
    case "added_by_you":
      return "added by you";
  }
}

/** One relation, rendered from this option's side (contract § Terms
 *  "package"; the list view and card both use this literal wording). */
export function relationLabel(relation: RelationOut): string {
  return relation.kind === "part_of" ? `part of ${relation.other_name}` : `includes ${relation.other_name}`;
}

/** The where-tried facet's four chip labels (list view spec): the plan's
 *  own Where first, then the three fixed groups, Title Case. */
export function whereTriedFacetChips(
  whereLabel: string,
): { group: "where" | "comparable" | "other" | "unknown"; label: string }[] {
  return [
    { group: "where", label: whereLabel },
    { group: "comparable", label: "Comparable systems (OECD)" },
    { group: "other", label: "Other" },
    { group: "unknown", label: "Unknown" },
  ];
}

/** The card's "Where tried" sentence (deliverable 9's option-card spec):
 *  "{where_label} {n} · comparable systems (OECD) {n} · other {n} · unknown
 *  {n}" — sentence case for the three fixed groups. */
export function whereTriedSentence(whereTried: WhereTriedOut, whereLabel: string): string {
  return [
    `${whereLabel} ${whereTried.where}`,
    `comparable systems (OECD) ${whereTried.comparable}`,
    `other ${whereTried.other}`,
    `unknown ${whereTried.unknown}`,
  ].join(" · ");
}

/** Join a `{label: count}` map as "{label} {n}, …" (the evidence-type and
 *  quality-tier sentences), in insertion order — the fixture and the real
 *  read model both order "not rated" last. */
export function joinCounts(counts: Record<string, number> | undefined): string {
  return Object.entries(counts ?? {})
    .map(([label, n]) => `${label} ${n}`)
    .join(", ");
}

/** The lever line on the option card: the primary type and what it also
 *  touches, or the none-fits reason — both exact templates from the
 *  contract's deliverable 9. */
export function leverLine(
  primary: string | null | undefined,
  secondary: string[] | undefined,
  noneFitsReason: string | null | undefined,
): string {
  if (primary == null) {
    return `Lever: none fits — ${noneFitsReason ?? ""}`;
  }
  const also = (secondary ?? []).map((type) => capitalise(type));
  return also.length > 0
    ? `Lever: ${capitalise(primary)} · also touches: ${also.join(", ")}`
    : `Lever: ${capitalise(primary)}`;
}

/** A document's where-tried group, in the card's lowercase sentence case
 *  (the same four groups as `whereTriedSentence`). */
export function whereTriedGroupLabel(
  group: "where" | "comparable" | "other" | "unknown",
  whereLabel: string,
): string {
  switch (group) {
    case "where":
      return whereLabel;
    case "comparable":
      return "comparable systems (OECD)";
    case "other":
      return "other";
    case "unknown":
      return "unknown";
  }
}

/** A judgement's verdict, rendered as prose ("breaks", "passes", "cannot
 *  check" — `cannot_check`'s underscore is the only value needing it). */
export function verdictLabel(verdict: "passes" | "breaks" | "cannot_check"): string {
  return verdict === "cannot_check" ? "cannot check" : verdict;
}

export const SCOPING_PASS_SENTENCE =
  "Screened on titles and abstracts · nothing read in full · document set not confirmed";

export const DO_NOTHING_SENTENCE =
  "Do nothing — the baseline describes the situation these options would change.";
/** The same sentence split around its link: only "the baseline" is the link. */
export const DO_NOTHING_BEFORE = "Do nothing — ";
export const DO_NOTHING_LINK = "the baseline";
export const DO_NOTHING_AFTER = " describes the situation these options would change.";

export const MENTION_NOT_SUPPORT = "A mention is not support.";
