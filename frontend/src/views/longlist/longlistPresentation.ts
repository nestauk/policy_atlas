import type { components } from "../../api/gen/types";
import type { LiveTheme, RunStreamState } from "../../store";
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

/** The origin words, one vocabulary from the first row of the build to the
 *  option card (round 10, C1). The one place the `origin` literal becomes
 *  words. */
export const ORIGIN_WORDS: Record<OptionSummaryOut["origin"], string> = {
  from_evidence_search: "from your report",
  suggested: "suggested by Policy Atlas",
  added_by_you: "added by you",
  clustered: "found in the evidence",
};

/** The option card's origin: the row's words, and for an option drawn from
 *  the linked report the section it came from (task 045, F3; round 10, C1:
 *  "from your report · <section>"). */
export function originLabel(origin: OptionSummaryOut["origin"], fromSection?: string | null): string {
  const section = fromSection?.trim() ?? "";
  return origin === "from_evidence_search" && section !== "" ? `${ORIGIN_WORDS[origin]} · ${section}` : ORIGIN_WORDS[origin];
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

/** The words for an option with no in-scope evidence, as plain text at the
 *  end of the row's meta line (round 10: no chip for a settled state). */
export const NO_IN_SCOPE_WORDS = "No in-scope evidence";

/**
 * A list row's one meta line (round 11, review finding 4; round 10's fixed
 * order kept): the lever (or, under a lever heading, the theme), the
 * evidence signal's first part, then "No in-scope evidence" when that holds.
 * "searching for its evidence…" stands for the signal while the option's
 * own search runs. Relations, origin and the rest of the signal are the
 * option card's.
 *
 * Args:
 *   option: The option's summary.
 *   lever: The lever's words, or null when the grouping says it or the
 *     profile wave has not written it.
 *   theme: The theme's name to show, or null when the grouping says it.
 *
 * Returns:
 *   The fields, each one whole (a line wraps between fields, never inside a
 *   middot).
 */
export function rowMetaFields(option: OptionSummaryOut, lever: string | null, theme: string | null): string[] {
  const fields: string[] = [];
  if (lever !== null) fields.push(lever);
  if (theme !== null) fields.push(theme);
  if (option.search_pending) fields.push("searching for its evidence…");
  else fields.push(evidenceSignal(option).split(" · ")[0]);
  if (option.no_in_scope_evidence) fields.push(NO_IN_SCOPE_WORDS);
  return fields;
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

/** The line under the longlist's counts that says how its documents were
 *  read (round 10, C4: it replaces the "scoping pass" chip and its hover
 *  sentence). */
export const READ_FROM_ABSTRACTS = "Read from titles and abstracts";


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
 *  line never carries a mark (who decides, dependencies). Potential impact
 *  carries a mark since 2026-10-27 (task 055). */
export const LEVEL_WORDS: Record<ProfileLineKey | "ambition", Record<Mark, string | null>> = {
  cost: { less: "Cheaper", more: "Costlier" },
  time_to_set_up: { less: "Quicker", more: "Slower" },
  time_to_effect: { less: "Quicker", more: "Slower" },
  workforce: { less: "Lower", more: "Higher" },
  who_decides: { less: null, more: null },
  dependencies: { less: null, more: null },
  coordination: { less: "Lower", more: "Higher" },
  delivery_complexity: { less: "Simpler", more: "More complex" },
  potential_impact: { less: "Lower", more: "Higher" },
  ambition: { less: "Smaller", more: "Bigger" },
};

/** The lines the grid can put in its columns: the eight that carry a mark,
 *  ambition first (R41), Potential impact last (task 055). */
export const GRID_COLUMN_LINES: readonly (ProfileLineKey | "ambition")[] = [
  "ambition",
  "cost",
  "time_to_set_up",
  "time_to_effect",
  "workforce",
  "coordination",
  "delivery_complexity",
  "potential_impact",
];

/** A marked level word (round 10, lead ruling on finding 7): one Navy look
 *  for both directions, the word itself saying which way ("Quicker",
 *  "Higher"), after a 6 px Navy square; no tint, so no colour reads as good
 *  or bad. A line with no mark reads "Middle" in Grey. */
export const LEVEL_MARKED_CLASS = "inline-flex items-center gap-1.5 text-meta font-semibold text-navy";
export const LEVEL_MIDDLE_CLASS = "text-meta font-semibold text-grey";

/** The collapsed profile's summary of its unmarked lines (round 10): "Middle
 *  on 6 of 8" once, rather than "Middle" in six cells; "No line stands out"
 *  when no line carries a mark (C5). */
export function middleSummary(unmarked: number, total: number): string {
  return unmarked >= total ? "No line stands out" : `${MIDDLE_WORD} on ${unmarked} of ${total}`;
}

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

/** One line of the notices under the description (R78; round 10: a word in
 *  its tone, then the sentence, no chip). */
export type ConstraintNotice = {
  key: string;
  /** The constraint's label, so the card can drop the notice the exclusion line already states. */
  constraint: string;
  /** Red only for a break (a failure); Navy for a likely shortfall; Grey when it cannot be said. */
  tone: "red" | "navy" | "grey";
  word: string;
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
      notices.push({ key: judgement.constraint_id, constraint: label, tone: "red", word: "Breaks", text: `"${label}". ${judgement.reason}` });
    } else if (judgement.verdict === "cannot_check") {
      notices.push({ key: judgement.constraint_id, constraint: label, tone: "grey", word: "Cannot check", text: `"${label}". ${judgement.reason}` });
    }
  }
  for (const guess of guesses) {
    const label = constraintLabel(guess.constraint_text);
    if (guess.leaning === "likely_falls_short") {
      notices.push({ key: guess.constraint_id, constraint: label, tone: "navy", word: "May fall short", text: `"${label}". ${guess.guess}` });
    } else if (guess.leaning === "cannot_say") {
      notices.push({ key: guess.constraint_id, constraint: label, tone: "grey", word: "Cannot check", text: `"${label}". ${guess.guess}` });
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

type MaturityOut = components["schemas"]["MaturityOut"];

/** The backend's `MATURITY_RECENT_YEARS`: an evaluation older than this
 *  many years is stale. */
const MATURITY_RECENT_YEARS = 5;

/** The maturity rung's word (task 055, item 7). */
export const MATURITY_WORDS: Record<MaturityOut["rung"], string> = {
  proposal_only: "Proposed, not yet implemented",
  described: "Implemented, not yet evaluated",
  evaluated: "Evaluated",
  reviewed: "Evaluated, including a review",
};

/** The rung line: the rung word, then ` · {design mix}` when there is one,
 *  then each modifier as ` · {modifier}`. "most recent evaluation before
 *  {year}" is the current year minus `MATURITY_RECENT_YEARS` and shows only when the newest
 *  evaluation is stale. `null` maturity (a longlist written before the rung
 *  existed) gives `null`: nothing new to show. */
export function maturityLine(maturity: MaturityOut | null | undefined, now: Date = new Date()): string | null {
  if (maturity == null) return null;
  const parts: string[] = [MATURITY_WORDS[maturity.rung]];
  if (maturity.design_mix !== "") parts.push(maturity.design_mix);
  if (maturity.none_in_your_setting) parts.push("none in your setting");
  if (maturity.stale) parts.push(`most recent evaluation before ${now.getFullYear() - MATURITY_RECENT_YEARS}`);
  return parts.join(" · ");
}

/** The shortlist row's evidence footing in plain words (owner, 2026-10-27:
 *  the rung line read as jargon): the rung's words, then ", not in {Where}"
 *  and ", last before {year}" as they apply. Policy Atlas assesses;
 *  documents evaluate — the words keep that line. */
export function maturityPhrase(
  maturity: MaturityOut | null | undefined,
  where: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (maturity == null) return null;
  if (maturity.rung === "proposal_only" || maturity.rung === "described") return MATURITY_WORDS[maturity.rung];
  const parts: string[] = [MATURITY_WORDS[maturity.rung]];
  if (maturity.none_in_your_setting) parts.push(where ? `not in ${where}` : "not in your setting");
  if (maturity.stale) parts.push(`last before ${now.getFullYear() - MATURITY_RECENT_YEARS}`);
  return parts.join(", ");
}


// --- The longlist while it is being built (task 058, N24; annex scene 15) ---

type OptionProgressOut = components["schemas"]["OptionProgressOut"];
type LonglistOut = components["schemas"]["LonglistOut"];

/** The shortlist toggle's words (round 10, lead ruling on finding 6): the
 *  state a row holds, said in words beside the row's name, from the
 *  shortlist wave of the build to the finished list. */
export const SHORTLISTED_WORD = "Shortlisted";
export const ADD_TO_SHORTLIST_WORDS = "Add to shortlist";
/** What pressing "Shortlisted" does, said on hover and keyboard focus
 *  (round 11, owner): the held words alone did not say it. */
export const REMOVE_FROM_SHORTLIST_WORDS = "Remove from shortlist";

/** A longlist walk's stages (the server's keys). "shortlist" is left out on
 *  purpose: a walk that runs only that stage is the standalone shortlist
 *  walk, which leaves the built longlist on screen. */
export const LONGLIST_WALK_STAGES: ReadonlySet<string> = new Set([
  "inherit",
  "suggest",
  "option_searches",
  "extract_interventions",
  "longlist",
  "option_profile",
  "constrain",
  "theme",
]);

/**
 * Whether the scoping Result shows the longlist being built (N24): a
 * longlist walk is running or paused. The live stream says so first (any of
 * its stages is a longlist stage, its last one included); the task read
 * stands in until the stream catches up. No API flag, no qualifier word.
 *
 * Args:
 *   task: The task read model (`capability`, `active_run`).
 *   streamStages: The tracked walk's stage frames from the run stream.
 *
 * Returns:
 *   `true` while a longlist walk is live.
 */
export function isLonglistBuilding(
  task:
    | { capability?: string | null; active_run?: { stage?: string | null } | null }
    | null
    | undefined,
  streamStages: readonly { stage: string }[],
): boolean {
  if (task?.capability !== "options_scoping" || task.active_run == null) return false;
  if (streamStages.some((entry) => LONGLIST_WALK_STAGES.has(entry.stage))) return true;
  const stage = task.active_run.stage;
  return stage != null && LONGLIST_WALK_STAGES.has(stage);
}

const FOUND_FORMAT = new Intl.NumberFormat("en-GB");

/** A row's right-hand line while its own search is the news; nothing once
 *  the longlist read has the option (its evidence then sits on the meta
 *  line, so the count is said once: round 10, finding 2 with R85). */
export type BuildingStatus = { kind: "queued" | "searching" | "searched" | "failed" | "assigning"; text: string } | null;

/** The right-hand line while the option's search is the news. */
export function searchStatusLine(row: Pick<OptionProgressOut, "search_status" | "found">): BuildingStatus {
  switch (row.search_status) {
    case "queued":
      return { kind: "queued", text: "Queued" };
    case "searching":
      return { kind: "searching", text: "Searching" };
    case "failed":
      return { kind: "failed", text: "Search failed" };
    case "searched":
      return {
        kind: "searched",
        text: row.found == null ? "Searched" : `Searched · ${FOUND_FORMAT.format(row.found)} found`,
      };
  }
}

/**
 * The names a longlist walk's steps publish while they run (round 11),
 * before the step commits anything to a read: the options "Clustering into
 * options" names, then the themes "Grouping into themes" names. Names and
 * descriptions only; the committed longlist brings the counts and which
 * option is in which theme.
 */
export interface LiveNames {
  options: readonly LiveTheme[];
  themes: readonly LiveTheme[];
}

export const NO_LIVE_NAMES: LiveNames = { options: [], themes: [] };

/**
 * The names the walk's clustering steps have published, from the run
 * stream: the options of "Clustering into options" (`liveOptions`, the
 * Themes frame with `stage: "longlist"`; the residual pass sends the whole
 * list again) and the themes of "Grouping into themes" (`liveOptionThemes`,
 * `stage: "theme"`). The empty lists are shared, so a memo on them holds.
 *
 * Args:
 *   stream: The task's run stream state.
 *
 * Returns:
 *   The published names, or `NO_LIVE_NAMES` when none are.
 */
export function liveNamesOf(stream: Pick<RunStreamState, "liveOptions" | "liveOptionThemes">): LiveNames {
  return {
    options: stream.liveOptions ?? NO_LIVE_NAMES.options,
    themes: stream.liveOptionThemes ?? NO_LIVE_NAMES.themes,
  };
}

/** A name compared as the server compares it: case, width and spacing
 *  folded. */
export function foldName(text: string): string {
  return text.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
}

/** A stable key for a name (a React key and a View Transition name, so a
 *  CSS identifier): the prefix and a hash of the folded name. */
export function nameKey(prefix: string, text: string): string {
  let hash = 5381;
  for (const char of foldName(text)) hash = ((hash * 33) ^ char.codePointAt(0)!) >>> 0;
  return `${prefix}-${hash.toString(36)}`;
}

/** The right-hand line of a row while "Clustering into options" assigns the
 *  sources (round 11): it breathes until the step commits, when the row's
 *  evidence line brings its count. */
export const ASSIGNING_LINE: BuildingStatus = { kind: "assigning", text: "Assigning sources" };

/** One row of the longlist, built or being built: one anatomy from the
 *  first row of the build to the finished list (round 10, finding 2). */
export interface BuildingRow {
  id: string;
  /** The row's React key and View Transition name: the option's id, or for
   *  an option clustering found, its name's key, so the row a published name
   *  drew keeps its place when the read brings the option (round 11). */
  key: string;
  name: string;
  description: string;
  /** The grey origin words ("from your report", "found in the evidence"). */
  origin: string;
  status: BuildingStatus;
  /** The lever, from the profile wave on. */
  lever: string | null;
  /** The longlist read's summary, from clustering on: the meta line, the
   *  exclusion and the shortlist state come from it. */
  summary: OptionSummaryOut | null;
  /** True from the shortlist wave on, for a row that holds a place. */
  shortlisted: boolean;
  /** The suggestions clustering folded into this option, in row order. */
  folded: { id: string; name: string }[];
}

/** A run of rows under one heading; `title` is `null` before the theme wave. */
export interface BuildingGroup {
  key: string;
  title: string | null;
  /** The theme's description, "" when it has none. */
  description: string;
  rows: BuildingRow[];
  /** A theme "Grouping into themes" has named and the read does not have
   *  yet: its heading shows before any option is in it (round 11). */
  named?: true;
}

export interface BuildingLayout {
  groups: BuildingGroup[];
  excluded: BuildingRow[];
}

/** Whether the profile wave has written this option's lever. */
function profiled(option: OptionSummaryOut): boolean {
  return option.profile != null || option.primary_lever_type != null || option.lever_none_fits_reason != null;
}

/**
 * The longlist being built, as rows in place (N24, D9).
 *
 * The options read gives the rows and their order from the end of suggest,
 * with each option's search and, from clustering on, the folds. While
 * "Clustering into options" runs, the names it publishes join as rows at
 * once (an option the options read does not have yet, origin "found in the
 * evidence"), and every row not yet on the longlist reads "Assigning
 * sources" with its count as the batches land (round 11). Once the longlist
 * read exists it fills them in, in waves: the evidence line, then the
 * lever, then exclusions (into their own group), then themes (rows move
 * under them), then shortlist marks. While "Grouping into themes" runs, the
 * themes it names stand as headings under the rows before the read has
 * them, and an option moves under its theme as it is assigned (round 11).
 * A folded row moves under the option it was folded into. The finished list
 * is the same layout (round 10, finding 2): without the options read (a
 * finished task opened cold) the rows come from the longlist read alone.
 *
 * Within a theme the rows run by lever, then name, as the finished list
 * sorts them, so the walk's end moves nothing.
 *
 * Args:
 *   rows: The options read's rows, oldest first.
 *   longlist: The longlist read, or `null` while it 404s.
 *   live: The names the walk's steps have published (`NO_LIVE_NAMES` on a
 *     finished list).
 *
 * Returns:
 *   The groups of included rows in order, and the excluded rows.
 */
export function buildingLayout(
  rows: readonly OptionProgressOut[],
  longlist: LonglistOut | null | undefined,
  live: LiveNames = NO_LIVE_NAMES,
): BuildingLayout {
  const summaries = new Map((longlist?.options ?? []).map((option) => [option.option_id, option]));
  const ids = new Set(rows.map((row) => row.option_id));
  const liveRows = rows.filter((row) => row.merged_into_option_id == null || !ids.has(row.merged_into_option_id));
  const named = new Map(live.options.map((option) => [foldName(option.label), option]));
  // The clustering step is naming options and nothing is on the longlist yet.
  const assigning = named.size > 0 && (longlist?.options ?? []).length === 0;

  const toRow = (
    id: string,
    name: string,
    description: string,
    origin: OptionSummaryOut["origin"],
    search: BuildingStatus,
  ): BuildingRow => {
    const summary = summaries.get(id);
    const shownName = summary?.name ?? name;
    const liveName = named.get(foldName(shownName));
    const shownOrigin = summary?.origin ?? origin;
    return {
      id,
      key: shownOrigin === "clustered" && liveName !== undefined ? nameKey("named", shownName) : id,
      name: shownName,
      description: (summary?.description ?? description).trim(),
      origin: ORIGIN_WORDS[shownOrigin],
      status: summary !== undefined ? null : assigning ? ASSIGNING_LINE : search,
      lever: summary !== undefined && profiled(summary) ? leverLabel(summary) : null,
      summary: summary ?? null,
      shortlisted: summary !== undefined && holdsPlace(summary),
      folded: rows
        .filter((other) => other.merged_into_option_id === id)
        .map((other) => ({ id: other.option_id, name: other.name })),
    };
  };

  const all: BuildingRow[] = [
    ...liveRows.map((row) => toRow(row.option_id, row.name, row.description, row.origin, searchStatusLine(row))),
    // An option the longlist has that the options read does not: every row
    // of a finished list opened before the options read answers (and never
    // drop a row the reader could otherwise see).
    ...(longlist?.options ?? [])
      .filter((option) => !ids.has(option.option_id))
      .map((option) => toRow(option.option_id, option.name, option.description, option.origin, null)),
  ];
  if (assigning) {
    // A name the clustering step published that no read has yet joins at
    // the end, as the options it found do once the read has them.
    const shown = new Set(all.map((row) => foldName(row.name)));
    for (const option of live.options) {
      const folded = foldName(option.label);
      if (folded === "" || shown.has(folded)) continue;
      shown.add(folded);
      const key = nameKey("named", option.label);
      all.push({
        id: key,
        key,
        name: option.label.trim(),
        description: (option.description ?? "").trim(),
        origin: ORIGIN_WORDS.clustered,
        status: ASSIGNING_LINE,
        lever: null,
        summary: null,
        shortlisted: false,
        folded: [],
      });
    }
  }
  const excludedIds = new Set(
    [...summaries.values()].filter((option) => option.state === "excluded").map((option) => option.option_id),
  );
  const included = all.filter((row) => !excludedIds.has(row.id));
  const excluded = all.filter((row) => excludedIds.has(row.id));

  const byLever = byLeverThenName(longlist?.lever_types ?? []);
  const sorted = (members: BuildingRow[]) =>
    [...members].sort((a, b) =>
      a.summary !== null && b.summary !== null
        ? byLever(a.summary, b.summary)
        : Number(a.summary === null) - Number(b.summary === null) || a.name.localeCompare(b.name),
    );
  // A theme's key is its name's, so a heading the theming step named keeps
  // its place (and does not rise again) when the read brings the theme.
  const takenKeys = new Set<string>();
  const themeKey = (name: string, fallback: string) => {
    const key = nameKey("theme", name);
    const unique = takenKeys.has(key) ? `${key}-${fallback}` : key;
    takenKeys.add(unique);
    return unique;
  };

  const themes = longlist?.themes ?? [];
  if (themes.length === 0) {
    const flat: BuildingGroup[] = included.length > 0 ? [{ key: "all", title: null, description: "", rows: included }] : [];
    if (live.themes.length === 0 || longlist == null) return { groups: flat, excluded };
    // "Grouping into themes" has named its themes: each stands as a heading
    // under the rows until the committed themes move the rows under theirs.
    const headings: BuildingGroup[] = live.themes.map((theme, index) => ({
      key: themeKey(theme.label, String(index)),
      title: theme.label.trim(),
      description: themeSummary(theme.description ?? ""),
      rows: [],
      named: true,
    }));
    return { groups: [...flat, ...headings], excluded };
  }
  const placed = new Set<string>();
  const groups: BuildingGroup[] = themes.map((theme) => {
    const members = new Set(theme.option_ids ?? []);
    const themed = included.filter((row) => members.has(row.id) && !placed.has(row.id));
    for (const row of themed) placed.add(row.id);
    return {
      key: themeKey(theme.name, theme.theme_id),
      title: theme.name,
      description: themeSummary(theme.description ?? ""),
      rows: sorted(themed),
    };
  });
  const rest = included.filter((row) => !placed.has(row.id));
  if (rest.length > 0) groups.push({ key: "no-theme", title: "No theme", description: "", rows: sorted(rest) });
  return { groups: groups.filter((group) => group.rows.length > 0), excluded };
}

/**
 * What the regrouping animation compares: the groups and their rows in
 * order, and the excluded rows. When it changes the rows move to their new
 * places (a View Transition); any other change lands in place.
 */
export function layoutSignature(layout: BuildingLayout): string {
  const groups = layout.groups.map((group) => `${group.key}:${group.rows.map((row) => row.key).join(",")}`);
  return `${groups.join("|")}#${layout.excluded.map((row) => row.key).join(",")}`;
}

/** Whether the option holds a place (a pick or one added by you); a
 *  set-aside pick holds none. */
export function holdsPlace(option: Pick<OptionSummaryOut, "shortlist">): boolean {
  const state = option.shortlist?.state;
  return state === "proposed" || state === "added_by_you";
}

