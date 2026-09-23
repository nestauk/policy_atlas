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
      return `clustered from ${documentCount} ${documentCount === 1 ? "document" : "documents"}`;
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

/** The card's "Where tried" sentence: the documents by place, zero groups
 *  dropped — "6 documents: 4 from United Kingdom, 2 from comparable
 *  systems (OECD)." */
export function whereTriedSentence(whereTried: WhereTriedOut, whereLabel: string): string {
  const total = whereTried.where + whereTried.comparable + whereTried.other + whereTried.unknown;
  if (total === 0) return "No document says where it was tried.";
  const parts = [
    [whereTried.where, `from ${whereLabel}`],
    [whereTried.comparable, "from comparable systems (OECD)"],
    [whereTried.other, "from elsewhere"],
    [whereTried.unknown, "with no place stated"],
  ]
    .filter(([n]) => (n as number) > 0)
    .map(([n, where]) => `${n} ${where}`);
  return `${total} ${total === 1 ? "document" : "documents"}: ${parts.join(", ")}.`;
}

/** Join a `{label: count}` map as "{n} {label}, …" (the evidence-type and
 *  quality-tier sentences), in insertion order — the fixture and the real
 *  read model both order "not rated" last. Tier names are single words and
 *  read better lowercase; evidence-type names keep their case (acronyms). */
export function joinCounts(counts: Record<string, number> | undefined, lowercase = false): string {
  return Object.entries(counts ?? {})
    .map(([label, n]) => `${n} ${lowercase ? label.toLowerCase() : label}`)
    .join(", ");
}

/** "{n} documents name this option: 3 evaluated it, 2 described it and 1
 *  mentioned it." Zero roles are dropped; a missing evaluation is said. */
export function documentsSentence(
  documents: number,
  byRole: Partial<Record<"evaluated" | "described" | "recommended" | "mentioned", number>>,
): string {
  if (documents === 0) return "No document names this option yet.";
  const roles = (["evaluated", "described", "recommended", "mentioned"] as const)
    .map((role) => [byRole[role] ?? 0, role] as const)
    .filter(([n]) => n > 0)
    .map(([n, role]) => `${n} ${role} it`);
  const head = `${documents} ${documents === 1 ? "document names" : "documents name"} this option`;
  const list = roles.length === 0 ? "" : `: ${joinAnd(roles)}`;
  const noEvaluation = (byRole.evaluated ?? 0) === 0 ? " None evaluated it." : "";
  return `${head}${list}.${noEvaluation}`;
}

/** A constraint's text as a label: its own full stop dropped, so "…cuts.:
 *  passes" and 'breaks "…run.".' do not double up. */
export function constraintLabel(text: string): string {
  return text.trim().replace(/[.。]+$/, "");
}

/** "a, b and c" */
export function joinAnd(parts: readonly string[]): string {
  if (parts.length <= 1) return parts[0] ?? "";
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/** "{k} of the {n} were read from the abstract only." / "All {n} were …" */
export function abstractOnlySentence(abstractOnly: number, documents: number): string {
  if (abstractOnly === 0) return "None was read from the abstract only.";
  if (abstractOnly >= documents) return `All ${documents} were read from the abstract only.`;
  return `${abstractOnly} of the ${documents} were read from the abstract only.`;
}

/** The short origin: the count says "clustered"; the other three origins
 *  are the tag itself (the snapshot cell and the row meta). */
export function originShort(origin: OptionSummaryOut["origin"]): string | null {
  switch (origin) {
    case "clustered":
      return null;
    case "suggested":
      return "suggested by Policy Atlas";
    case "from_evidence_search":
      return "from your evidence search";
    case "added_by_you":
      return "added by you";
  }
}

/** A list row's grey meta parts: the document count (or why there is
 *  none yet), the origin when it is not "clustered", then relations. */
export function rowMetaParts(option: OptionSummaryOut): string[] {
  const parts: string[] = [];
  if (option.search_pending) parts.push("searching for its evidence…");
  else if (option.is_entrant_with_no_documents) parts.push("no documents found yet");
  else parts.push(`${option.document_count} ${option.document_count === 1 ? "document" : "documents"}`);
  const origin = originShort(option.origin);
  if (origin !== null) parts.push(origin);
  for (const relation of option.relations ?? []) parts.push(relationLabel(relation));
  return parts;
}

/** A lever type as the noun a theme heading uses ("services, subsidies
 *  and regulation"). Keyed on the backend taxonomy in
 *  backend/src/policy_atlas/options_scoping/longlist/lever_types.py
 *  (`LEVER_TYPES`): a key added or renamed there needs a noun here, or it
 *  reads as its raw key. */
export function leverNoun(leverType: string): string {
  const nouns: Record<string, string> = {
    regulate: "regulation",
    subsidise: "subsidies",
    "tax or charge": "taxes or charges",
    inform: "information",
    "provide a service": "services",
    "enforce existing powers": "enforcement",
    devolve: "devolution",
    "change who runs the system": "changes to who runs the system",
    "invest in infrastructure": "infrastructure",
    "build or change infrastructure": "infrastructure",
    convene: "convening",
    "procure or commission": "procurement",
  };
  return nouns[leverType] ?? leverType;
}

/** The instruments a group of options uses, in taxonomy order: "services
 *  only", "services, subsidies and procurement", or "" when none is typed. */
export function instrumentsSummary(
  options: readonly { primary_lever_type?: string | null }[],
  leverTypes: readonly string[],
): string {
  const present = new Set(options.map((option) => option.primary_lever_type).filter((lever): lever is string => lever != null));
  const ordered = [...leverTypes.filter((lever) => present.has(lever)), ...[...present].filter((lever) => !leverTypes.includes(lever))];
  if (ordered.length === 0) return "";
  if (ordered.length === 1) return `${leverNoun(ordered[0])} only`;
  return joinAnd(ordered.map(leverNoun));
}

/** Sort key: taxonomy position of the primary lever (none fits last), then name. */
export function byLeverThenName(leverTypes: readonly string[]) {
  return (a: OptionSummaryOut, b: OptionSummaryOut): number => {
    const rank = (option: OptionSummaryOut) => {
      if (option.primary_lever_type == null) return leverTypes.length;
      const index = leverTypes.indexOf(option.primary_lever_type);
      return index === -1 ? leverTypes.length : index;
    };
    return rank(a) - rank(b) || a.name.localeCompare(b.name);
  };
}

/** A row's lever and ambition, as the first thing after its name:
 *  "Provide a service · Incremental". */
export function leverAmbitionLabel(option: OptionSummaryOut): string {
  const parts = [option.primary_lever_type == null ? "No lever fits" : capitalise(option.primary_lever_type)];
  if (option.ambition != null) parts.push(ambitionLabel(option.ambition));
  return parts.join(" · ");
}

/** A taxonomy definition as a heading's line: capitalised, one full stop. */
export function definitionSentence(definition: string | null | undefined): string {
  const text = (definition ?? "").trim().replace(/[.]+$/, "");
  return text === "" ? "" : `${capitalise(text)}.`;
}

/** A collapsed theme's summary: its description (owner, 2026-09-23: no
 *  option names). */
export function themeSummary(description: string): string {
  return description.trim();
}

/** The lever line on the option card: the primary type and what it also
 *  touches, or the none-fits reason (contract deliverable 9; the board's
 *  sentence shape). */
export function leverLine(
  primary: string | null | undefined,
  secondary: string[] | undefined,
  noneFitsReason: string | null | undefined,
): string {
  if (primary == null) {
    const reason = (noneFitsReason ?? "").trim();
    return reason === "" ? "Primary lever type: none fits." : `Primary lever type: none fits. ${reason}`;
  }
  const also = (secondary ?? []).map((type) => capitalise(type));
  return also.length > 0
    ? `Primary lever type: ${capitalise(primary)}; it also touches ${also.join(", ")}.`
    : `Primary lever type: ${capitalise(primary)}.`;
}

/** A document's where-tried group, as the card's document list words it. */
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
      return "elsewhere";
    case "unknown":
      return "place not stated";
  }
}

/** A judgement's verdict, rendered as prose ("breaks", "passes", "cannot
 *  check" — `cannot_check`'s underscore is the only value needing it). */
export function verdictLabel(verdict: "passes" | "breaks" | "cannot_check"): string {
  return verdict === "cannot_check" ? "cannot check" : verdict;
}

export const SCOPING_PASS_SENTENCE =
  "Screened on titles and abstracts · nothing read in full · document set not confirmed";


type LonglistCountsOut = components["schemas"]["LonglistCountsOut"];

/** The counts line under the longlist title: "40 options in 12 themes ·
 *  3 excluded", with "with no in-scope evidence" only when it is not zero
 *  (the contract's header counts, minus the internal unclustered figure —
 *  owner, 2026-09-23). */
export function countsLine(counts: LonglistCountsOut): string {
  const parts = [
    `${counts.options} ${counts.options === 1 ? "option" : "options"} in ${counts.themes} ${
      counts.themes === 1 ? "theme" : "themes"
    }`,
    `${counts.excluded} excluded`,
  ];
  if (counts.no_in_scope > 0) parts.push(`${counts.no_in_scope} with no in-scope evidence`);
  return parts.join(" · ");
}

/** The longlist's title: the plan's question, else its title, else the
 *  task's name — the report titles itself with the question too. */
export function longlistTitle(
  scoping: { question?: string | null; title?: string | null } | null | undefined,
  taskName: string | undefined,
): string {
  for (const candidate of [scoping?.question, scoping?.title, taskName]) {
    if (candidate != null && candidate.trim() !== "") return candidate.trim();
  }
  return "Longlist";
}

/** The row's outcomes, as one sentence: "For {a}, {b} and {c}." */
export function outcomesSentence(outcomes: string[] | undefined): string {
  const list = (outcomes ?? []).filter((outcome) => outcome.trim() !== "");
  if (list.length === 0) return "";
  const joined = list.length === 1 ? list[0] : `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
  return `For ${joined}.`;
}

/** An ambition band's stored key as its label: "do_minimum" → "Do minimum"
 *  (the backend's AMBITION_LABELS, derived rather than fetched because the
 *  option card has no longlist read in hand). */
export function ambitionLabel(ambition: string): string {
  return capitalise(ambition.replace(/_/g, " "));
}

/** The ambition line on the option card: "Ambition: {band}. {reason}" */
export function ambitionLine(ambition: string, reason: string | null | undefined): string {
  const why = (reason ?? "").trim();
  return why === "" ? `Ambition: ${ambitionLabel(ambition)}.` : `Ambition: ${ambitionLabel(ambition)}. ${why}`;
}

/** The constraints section's collapsed line: "2 break, 1 passes, 1 cannot
 *  be checked yet." — the verb agrees with the count. */
export function checksSummary(verdicts: readonly ("passes" | "breaks" | "cannot_check")[]): string {
  const forms: Record<"breaks" | "passes" | "cannot_check", [one: string, many: string]> = {
    breaks: ["breaks", "break"],
    passes: ["passes", "pass"],
    cannot_check: ["cannot be checked yet", "cannot be checked yet"],
  };
  const parts = (["breaks", "passes", "cannot_check"] as const)
    .map((verdict) => [verdicts.filter((v) => v === verdict).length, verdict] as const)
    .filter(([n]) => n > 0)
    .map(([n, verdict]) => `${n} ${forms[verdict][n === 1 ? 0 : 1]}`);
  return parts.length === 0 ? "" : `${parts.join(", ")}.`;
}

/** A document's role on the option, as a chip: "Evaluated it". */
export function roleLabel(role: "evaluated" | "described" | "recommended" | "mentioned"): string {
  return `${capitalise(role)} it`;
}
