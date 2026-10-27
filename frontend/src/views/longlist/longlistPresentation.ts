import type { components } from "../../api/gen/types";
import { countOf } from "../../lib/vocabulary";
import { PROFILE_LINE_LABELS } from "../workspace/planVocabulary";

/**
 * Presentation helpers shared by the longlist's three surfaces (list view,
 * reduced grid, option card) — task 045 phase 6.2. Structure-and-plumbing:
 * every string here is either given verbatim by the task contract/brief or
 * a direct template of a read-model field. No summary prose, no writer
 * call — the option card is assembled, not written (D15).
 */

type RelationOut = components["schemas"]["RelationOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

/** Capitalise a lever-type key's first letter only — the keys are already
 *  natural lowercase phrases ("tax or charge"), so nothing else needs
 *  changing. */
export function capitalise(value: string): string {
  return value.length === 0 ? value : value[0].toUpperCase() + value.slice(1);
}

/** "from your evidence search", naming the report section it was drawn
 *  from when that was recorded (task 045, F3). */
function fromEvidenceSearch(fromSection: string | null | undefined): string {
  return fromSection != null && fromSection.trim() !== ""
    ? `from your evidence search · ${fromSection.trim()}`
    : "from your evidence search";
}

/** The origin tag's exact wording (contract § Terms "entrant"; deliverable
 *  9's list view spec). `clustered` carries the document count; the other
 *  three are fixed phrases (the evidence-search one with its section). */
export function originLabel(
  origin: OptionSummaryOut["origin"],
  documentCount: number,
  fromSection?: string | null,
): string {
  switch (origin) {
    case "clustered":
      return `clustered from ${countOf(documentCount, "document", "documents")}`;
    case "suggested":
      return "suggested by Policy Atlas";
    case "from_evidence_search":
      return fromEvidenceSearch(fromSection);
    case "added_by_you":
      return "added by you";
  }
}

/** One relation, rendered from this option's side (contract § Terms
 *  "package"; the list view and card both use this literal wording). */
export function relationLabel(relation: RelationOut): string {
  return relation.kind === "part_of" ? `part of ${relation.other_name}` : `includes ${relation.other_name}`;
}

const fold = (text: string): string => text.trim().toLowerCase();

/** A document's place on its meta line: its top level, with the two
 *  non-country values said as places. */
export function documentPlaceLabel(place: string | null | undefined): string | null {
  if (place == null || place.trim() === "") return null;
  if (fold(place) === "not stated") return "place not stated";
  if (fold(place) === "other") return "other place";
  return place;
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

/** The note on the documents line about how they were read (task 046, amendment 4, R81). */
export const ABSTRACTS_NOTE = "read from titles and abstracts only";

/** The short origin: the count says "clustered"; the other three origins
 *  are the tag itself (the snapshot cell and the row meta). */
export function originShort(
  origin: OptionSummaryOut["origin"],
  fromSection?: string | null,
): string | null {
  return origin === "clustered" ? null : originLabel(origin, 0, fromSection);
}

/** A list row's grey meta parts after the lever type (task 046, amendment 4, R85):
 *  the origin when it is not "clustered", the relations, then the evidence signal's
 *  own parts (no document count of its own). "searching for its evidence…" stands
 *  alone while the option's own search runs. */
export function rowMetaParts(option: OptionSummaryOut): string[] {
  const parts: string[] = [];
  const origin = originShort(option.origin, option.from_section);
  if (origin !== null) parts.push(origin);
  for (const relation of option.relations ?? []) parts.push(relationLabel(relation));
  if (option.search_pending) parts.push("searching for its evidence…");
  else parts.push(...evidenceSignal(option).split(" · "));
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

/** A row's lever, as the first thing after its name: "Provide a service".
 *  A row carries no mark and no ambition word (R40, R44). */
export function leverLabel(option: OptionSummaryOut): string {
  return option.primary_lever_type == null ? "No lever fits" : capitalise(option.primary_lever_type);
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

/** The lever line on the option card (task 046, amendment 3, § 2.5): "Lever:
 *  Subsidise, with Regulate and Provide a service." — the primary type and the
 *  secondary types, or "Lever: none fits." when no type fits. The reason is a
 *  separate sentence under it. */
export function leverLine(primary: string | null | undefined, secondary: string[] | undefined): string {
  if (primary == null) return "Lever: none fits.";
  const also = (secondary ?? []).map((type) => capitalise(type));
  return also.length > 0
    ? `Lever: ${capitalise(primary)}, with ${also.join(" and ")}.`
    : `Lever: ${capitalise(primary)}.`;
}

/** A lever group's definition (task 046, AM19): the definition of the
 *  taxonomy version its options were typed under, when they share one the
 *  longlist knows; the current list's definition otherwise. */
export function leverDefinitionFor(
  lever: string,
  options: readonly { taxonomy_version?: string | null }[],
  byVersion: Record<string, { key: string; definition: string }[]> | undefined,
  current: string,
): string {
  const versions = new Set(options.map((option) => option.taxonomy_version ?? ""));
  if (versions.size !== 1) return current;
  const [version] = versions;
  const typed = (byVersion?.[version] ?? []).find((entry) => entry.key === lever);
  return typed === undefined ? current : definitionSentence(typed.definition);
}

export const SCOPING_PASS_SENTENCE =
  "Screened on titles and abstracts · nothing read in full · document set not confirmed";


type LonglistCountsOut = components["schemas"]["LonglistCountsOut"];

/** The counts line under the longlist title (task 046, amendment 4, R83), as parts:
 *  "40 options in 12 themes", then " · 3 excluded" only when some are (the view
 *  links it in list mode), then " · 2 with no in-scope evidence" only when some
 *  are. One source of the words. */
export function countsParts(counts: LonglistCountsOut): {
  head: string;
  excluded: string | null;
  noInScope: string | null;
} {
  return {
    // No theme count before the theme step has run (or when it wrote none):
    // "in 0 themes" would read as a result (review of task 046, 2026-10-12).
    head:
      countOf(counts.options, "option", "options") +
      (counts.themes > 0 ? ` in ${countOf(counts.themes, "theme", "themes")}` : ""),
    excluded: counts.excluded > 0 ? `${counts.excluded} excluded` : null,
    noInScope: counts.no_in_scope > 0 ? `${counts.no_in_scope} with no in-scope evidence` : null,
  };
}

/** The counts line as one string: the excluded part only when K > 0 (R83). */
export function countsLine(counts: LonglistCountsOut): string {
  const { head, excluded, noInScope } = countsParts(counts);
  return [head, excluded, noInScope].filter((part): part is string => part !== null).join(" · ");
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

type ProfileLineKey = components["schemas"]["ProfileLineOut"]["key"];
type Mark = "less" | "more";
type AuthorityOut = components["schemas"]["AuthorityOut"];

/** The nine profile lines, in display order (R37; Potential impact last, task
 *  055); the last entry of the shared vocabulary, transferability, is read at
 *  assessment and not listed. */
export const PROFILE_LINE_KEYS = (Object.keys(PROFILE_LINE_LABELS) as string[]).filter(
  (key): key is ProfileLineKey => key !== "transferability",
);

/** The name of a profile line or of ambition (R40). */
export const LINE_NAMES = { ...PROFILE_LINE_LABELS, ambition: "Ambition" } as Record<
  ProfileLineKey | "ambition",
  string
>;

/** The level word each mark takes on each line (R40, R44); `null` where the
 *  line never carries a mark. */
export const LEVEL_WORDS: Record<ProfileLineKey | "ambition", Record<Mark, string | null>> = {
  cost: { less: "Cheaper", more: "Costlier" },
  time_to_set_up: { less: "Quicker", more: "Slower" },
  time_to_effect: { less: "Quicker", more: "Slower" },
  workforce: { less: "Lower", more: "Higher" },
  who_decides: { less: null, more: null },
  dependencies: { less: null, more: null },
  coordination: { less: "Lower", more: "Higher" },
  delivery_complexity: { less: "Simpler", more: "More complex" },
  potential_impact: { less: null, more: null },
  ambition: { less: "Smaller", more: "Bigger" },
};

/** The lines the grid can put in its columns: the seven that carry a mark,
 *  ambition first (R41). */
export const GRID_COLUMN_LINES: readonly (ProfileLineKey | "ambition")[] = [
  "ambition",
  "cost",
  "time_to_set_up",
  "time_to_effect",
  "workforce",
  "coordination",
  "delivery_complexity",
];

/** The shape every tinted word shares (level words, authority words). */
export const WORD_TINT_BASE = "inline-block px-1.5 py-0.5 text-meta font-semibold leading-tight";

/** The tint behind a level word: pale aqua for the lower level, pale violet
 *  for the higher one; navy text on both (the lead's proposal, for the owner
 *  to decide on the built screen). */
export const LEVEL_WORD_CLASS: Record<Mark, string> = {
  less: `${WORD_TINT_BASE} bg-aqua-tint text-navy`,
  more: `${WORD_TINT_BASE} bg-violet-tint text-navy`,
};

/** The authority labels' words (R43); a null body reads "another body". */
export const AUTHORITY_LABELS: Record<AuthorityOut["label"], string> = {
  within_your_power: "Within your power",
  needs_action_by: "Needs action by another body",
  unclear: "Unclear who can act",
};

/** The label's words for one option's authority: "Needs action by {body}"
 *  when the body is known. */
export function authorityWords(authority: AuthorityOut): string {
  const body = (authority.body ?? "").trim();
  return authority.label === "needs_action_by" && body !== ""
    ? `Needs action by ${body}`
    : AUTHORITY_LABELS[authority.label];
}

/** The word for a line with no mark, in the collapsed cells and the table (§ 2.9). */
export const MIDDLE_WORD = "Middle";

/** The ids of the three built-in checks among an option's judgements. */
export const BUILT_IN_CHECK_IDS: readonly string[] = ["relevant", "distinct", "in_scope"];

/** Whether the option's design picked this plan outcome (case and spacing folded). */
export function servesOutcome(served: readonly string[] | undefined, outcome: string): boolean {
  const key = outcome.trim().toLowerCase();
  return (served ?? []).some((name) => name.trim().toLowerCase() === key);
}

type EvaluatedCountryOut = components["schemas"]["EvaluatedCountryOut"];
type JudgementOut = components["schemas"]["JudgementOut"];
type GuessOut = components["schemas"]["GuessOut"];

/** Countries whose name takes "the" in running text (task 046, amendment 4, R76). */
const COUNTRIES_WITH_THE: readonly string[] = [
  "netherlands",
  "philippines",
  "czech republic",
  "gambia",
  "bahamas",
  "maldives",
  "dominican republic",
  "democratic republic of the congo",
  "republic of the congo",
];

/** A country's name as it reads in a sentence: "the United Kingdom", "Denmark". */
export function countryWithArticle(name: string): string {
  const key = fold(name);
  return key.startsWith("united") || COUNTRIES_WITH_THE.includes(key) ? `the ${name}` : name;
}

/** The countries part of the evidence signal (R76): the countries in served order. */
function evaluatedInPart(countries: readonly EvaluatedCountryOut[]): string {
  if (countries.length === 0) return "No evaluation gives a place";
  const first = countryWithArticle(countries[0].country);
  if (countries.length === 1) return `Evaluated in ${first}`;
  if (countries.length === 2) return `Evaluated in ${first} and ${countryWithArticle(countries[1].country)}`;
  const others = countries.length - 1;
  return `Evaluated in ${first} and ${countOf(others, "other country", "other countries")}`;
}

/**
 * The evidence signal (task 046, amendment 4, R76), one line shared by the card
 * header and the list row: the documents that evaluated the option and those
 * that describe it, where it was evaluated, how many of the plan's outcomes it
 * measures.
 *
 * Args:
 *   option: The option, read for its document counts, countries and outcome counts.
 *
 * Returns:
 *   The parts joined by " · ".
 */
export function evidenceSignal(
  option: Pick<
    OptionSummaryOut,
    "document_count" | "evaluated_count" | "evaluated_countries" | "outcomes_evaluated" | "outcomes_total"
  >,
): string {
  const documents = option.document_count;
  if (documents === 0) return "No documents yet";
  const evaluated = option.evaluated_count;
  const describing = documents - evaluated;
  if (evaluated === 0) {
    return `No evaluations, ${countOf(describing, "document describes", "documents describe")} it`;
  }
  const parts = [`${countOf(evaluated, "document", "documents")} evaluated it`];
  if (describing > 0) parts.push(`${describing} more describe it`);
  parts.push(evaluatedInPart(option.evaluated_countries ?? []));
  const measured = option.outcomes_evaluated;
  const total = option.outcomes_total;
  parts.push(
    measured === 0
      ? "Measures none of your outcomes"
      : `Measures ${measured} of your ${countOf(total, "outcome", "outcomes")}`,
  );
  return parts.join(" · ");
}

/** The opener of the card's Evidence section (R79, R82), by code. */
export function evidenceOpener(evaluated: number, documents: number): string {
  if (documents === 0) return "No document names this option yet.";
  if (evaluated === 0) {
    return `No evaluations. ${countOf(documents, "document describes", "documents describe")} or recommend${documents === 1 ? "s" : ""} it.`;
  }
  const describing = documents - evaluated;
  const more =
    describing > 0 ? ` ${describing} more describe${describing === 1 ? "s" : ""} or recommend${describing === 1 ? "s" : ""} it.` : "";
  return `Evaluated in ${countOf(evaluated, "document", "documents")}.${more}`;
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

/** The one line that stands for "Your outcomes" when no evaluation measured any (R79). */
export function noOutcomeMeasuredLine(outcomes: number): string {
  if (outcomes === 1) return "No evaluation measured any of your outcome.";
  const count = outcomes >= 2 && outcomes <= 10 ? NUMBER_WORDS[outcomes] : String(outcomes);
  return `No evaluation measured any of your ${count} outcomes.`;
}

/** An outcome's count on its "Your outcomes" line (R79): "11 evaluations". */
export function outcomeCountLabel(evaluated: number): string {
  return countOf(evaluated, "evaluation", "evaluations");
}

/** The words after "Delivered" for each setting kind (R77); other kinds read "in {plural}". */
const SETTING_PHRASES: Record<string, string> = {
  home: "at home",
  online: "online",
  workplace: "at work",
  community: "in the community",
  "primary care": "in primary care",
  "secondary care": "in secondary care",
  hospital: "in hospitals",
  school: "in schools",
  shop: "in shops",
};

/** A small pluraliser for a setting kind: "clinic" → "clinics", "library" → "libraries". */
function plural(word: string): string {
  if (/[^aeiou]y$/i.test(word)) return `${word.slice(0, -1)}ies`;
  if (/(s|x|ch|sh)$/i.test(word)) return `${word}es`;
  return `${word}s`;
}

/** One setting kind as a place phrase: "in schools", "at home". */
export function settingPhrase(kind: string): string {
  const key = fold(kind);
  return SETTING_PHRASES[key] ?? `in ${plural(key)}`;
}

/**
 * The lead-in to the design features (R77): "Delivered in schools and at home.
 * It typically involves:", or "It typically involves:" alone with no setting.
 */
export function deliveredLeadIn(settings: readonly string[] | undefined): string {
  const phrases = (settings ?? []).filter((kind) => kind.trim() !== "").map(settingPhrase);
  return phrases.length === 0 ? "It typically involves:" : `Delivered ${joinAnd(phrases)}. It typically involves:`;
}

/** One line of the callout under the description (R78). */
export type ConstraintNotice = {
  key: string;
  /** The constraint's label, so the card can drop the notice the exclusion line already states. */
  constraint: string;
  tone: "red" | "yellow" | "soft";
  chip: string;
  text: string;
};

/**
 * The callout's lines (R78): a user constraint that breaks or cannot be
 * checked, a guess that likely falls short or cannot be said. A pass, a
 * likely-meets and the built-in checks show nothing.
 */
export function constraintNotices(
  judgements: readonly JudgementOut[],
  guesses: readonly GuessOut[],
): ConstraintNotice[] {
  const notices: ConstraintNotice[] = [];
  for (const judgement of judgements) {
    if (BUILT_IN_CHECK_IDS.includes(judgement.constraint_id)) continue;
    const label = constraintLabel(judgement.constraint_text);
    if (judgement.verdict === "breaks") {
      notices.push({ key: judgement.constraint_id, constraint: label, tone: "red", chip: "breaks", text: `Breaks "${label}". ${judgement.reason}` });
    } else if (judgement.verdict === "cannot_check") {
      notices.push({ key: judgement.constraint_id, constraint: label, tone: "soft", chip: "cannot check", text: `Cannot check "${label}". ${judgement.reason}` });
    }
  }
  for (const guess of guesses) {
    const label = constraintLabel(guess.constraint_text);
    if (guess.leaning === "likely_falls_short") {
      notices.push({ key: guess.constraint_id, constraint: label, tone: "yellow", chip: "may fall short", text: `"${label}". ${guess.guess}` });
    } else if (guess.leaning === "cannot_say") {
      notices.push({ key: guess.constraint_id, constraint: label, tone: "soft", chip: "cannot check", text: `Cannot check "${label}". ${guess.guess}` });
    }
  }
  return notices;
}

/** The documents disclosure's summary (R81): "Documents · 29 · read from titles and abstracts only". */
export function documentsSummary(count: number): string {
  return count > 0 ? `Documents · ${count} · ${ABSTRACTS_NOTE}` : `Documents · ${count}`;
}

/** A document's place and, in grey brackets, the level below when it adds a word (R81). */
export function placeWithDetail(
  place: string | null | undefined,
  detail: string | null | undefined,
): { place: string | null; detail: string | null } {
  const label = documentPlaceLabel(place);
  const below = (detail ?? "").trim();
  return { place: label, detail: below !== "" && fold(below) !== fold(place ?? "") ? below : null };
}
