import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { useAddOption, useExcludeOption, useIncludeOption } from "../../api/mutations";
import { usePlan, useTask } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import {
  FullReportExpandAllButton,
  FullReportExpandProvider,
  SectionDisclosure,
  sectionAnchor,
  type SidebarEntry,
} from "../ArtefactOutline";
import { REPORT_TITLE_CLASS, ReportKindRow, ReportPage } from "../reportPage";
import { isRunActive } from "../scopingActivity";
import { FILTER_CHIP_CLASS } from "../sourcesPresentation";
import { LonglistGrid } from "./LonglistGrid";
import {
  SCOPING_PASS_SENTENCE,
  byLeverThenName,
  capitalise,
  constraintLabel,
  countsLine,
  definitionSentence,
  instrumentsSummary,
  leverAmbitionLabel,
  longlistTitle,
  rowMetaParts,
  themeSummary,
  whereTriedFacetChips,
} from "./longlistPresentation";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];
type WhereTriedGroup = "where" | "comparable" | "other" | "unknown";
type GroupBy = "theme" | "lever" | "ambition";

const GROUP_BY: { key: GroupBy; label: string }[] = [
  { key: "theme", label: "Theme" },
  { key: "lever", label: "Lever type" },
  { key: "ambition", label: "Ambition" },
];

/** The setting facet shows this many chips before "more". */
const SETTING_FACET_LIMIT = 8;
const ADD_OPTION_ANCHOR = "add-option";
const EXCLUDED_ANCHOR = "excluded-options";

/** The facet chips share the Sources view's filter language (is-EB). */
function facetChipClass(active: boolean): string {
  return cn(
    FILTER_CHIP_CLASS,
    "transition-colors",
    active ? "border-blue bg-blue-tint text-blue" : "border-line-2 bg-paper text-grey hover:text-navy",
  );
}

const FACET_LABEL_CLASS = "w-20 flex-none pt-1.5 text-meta font-semibold text-grey max-md:w-full max-md:pt-0";

const REASON_INPUT_CLASS =
  "min-w-0 flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body text-ink placeholder:text-grey/80 " +
  "focus-visible:outline-2 focus-visible:outline-blue";

function toggleInSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

/**
 * The longlist's list view (contract deliverable 9, plan S13) on the
 * report's page chrome (EB-modified: `ReportPage`, `SectionDisclosure`):
 * the kind row with the List · Grid switch, the counts as the title and
 * snapshot cells, the Show/Setting/Where-tried facets, theme sections that
 * expand and collapse like report sections, option rows, the "Do nothing"
 * reference, and an add-option row. The grid (D12) widens the paper.
 */
export function LonglistView({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const addOption = useAddOption(taskId);
  const excludeOption = useExcludeOption(taskId);
  const includeOption = useIncludeOption(taskId);

  const [settingsFilter, setSettingsFilter] = useState<Set<string>>(new Set());
  const [whereFilter, setWhereFilter] = useState<Set<WhereTriedGroup>>(new Set());
  const [mode, setMode] = useState<"list" | "grid">("list");
  const [groupBy, setGroupBy] = useState<GroupBy>("theme");
  const [showExcludedInGrid, setShowExcludedInGrid] = useState(false);
  const [addText, setAddText] = useState("");
  const [excludingId, setExcludingId] = useState<string | null>(null);
  const [excludeReason, setExcludeReason] = useState("");

  const options = longlist.options ?? [];
  const optionsById = new Map(options.map((option) => [option.option_id, option]));
  const leverTypes = longlist.lever_types ?? [];
  const leverDefinitions = new Map(
    (longlist.lever_type_definitions ?? []).map((lever) => [lever.key, definitionSentence(lever.definition)]),
  );
  const themeOfOption = new Map<string, string>();
  for (const theme of longlist.themes ?? []) {
    for (const id of theme.option_ids ?? []) themeOfOption.set(id, theme.name);
  }

  // Settings are source-named and long-tailed (a live NEET longlist carried
  // 28 of them): the facet shows the commonest few and folds the rest.
  const settingCounts = new Map<string, number>();
  for (const option of options) {
    for (const setting of option.settings ?? []) {
      settingCounts.set(setting, (settingCounts.get(setting) ?? 0) + 1);
    }
  }
  const allSettings = [...settingCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([setting]) => setting);
  const [allSettingsShown, setAllSettingsShown] = useState(false);
  const shownSettings =
    allSettingsShown || allSettings.length <= SETTING_FACET_LIMIT
      ? allSettings
      : allSettings.filter((setting) => settingsFilter.has(setting) || allSettings.indexOf(setting) < SETTING_FACET_LIMIT);
  const hiddenSettings = allSettings.length - shownSettings.length;
  const whereChips = whereTriedFacetChips(longlist.where_label);

  const passesFilters = (option: OptionSummaryOut): boolean => {
    if (settingsFilter.size > 0) {
      const optionSettings = option.settings ?? [];
      if (![...settingsFilter].some((setting) => optionSettings.includes(setting))) return false;
    }
    if (whereFilter.size > 0) {
      const whereTried = option.where_tried;
      if (![...whereFilter].some((group) => (whereTried[group] ?? 0) > 0)) return false;
    }
    return true;
  };

  const walkActive = isRunActive(task.data);

  const handleAddOption = (event: FormEvent) => {
    event.preventDefault();
    const text = addText.trim();
    if (text === "" || addOption.isPending || walkActive) return;
    addOption.mutate({ text }, { onSuccess: () => setAddText("") });
  };

  const submitExclude = (optionId: string) => {
    const reason = excludeReason.trim();
    if (reason === "" || excludeOption.isPending) return;
    excludeOption.mutate(
      { optionId, reason },
      {
        onSuccess: () => {
          setExcludingId(null);
          setExcludeReason("");
        },
      },
    );
  };

  const handleInclude = (optionId: string) => {
    if (includeOption.isPending) return;
    includeOption.mutate({ optionId });
  };

  const renderOptionRow = (option: OptionSummaryOut) => {
    const excluded = option.state === "excluded";
    return (
      <li key={option.option_id} className="py-4">
        <div className="flex items-start justify-between gap-4">
          <Link
            to={`/tasks/${taskId}/options/${option.option_id}`}
            className={cn(
              "min-w-0 text-body font-bold text-navy underline-offset-4 hover:underline",
              excluded && "text-grey",
            )}
          >
            {scrub(option.name)}
          </Link>
          {excluded ? (
            <Button
              variant="secondary"
              size="sm"
              className="-my-2 flex-none"
              disabled={includeOption.isPending}
              onClick={() => handleInclude(option.option_id)}
            >
              Include again
            </Button>
          ) : (
            excludingId !== option.option_id && (
              <Button
                variant="secondary"
                size="sm"
                className="-my-2 flex-none"
                onClick={() => {
                  setExcludeReason("");
                  setExcludingId(option.option_id);
                }}
              >
                Exclude
              </Button>
            )
          )}
        </div>
        <p className={cn("mt-1 max-w-[44em] text-body", excluded ? "text-grey" : "text-ink")}>
          {scrub(option.description)}
        </p>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-grey">
          {excluded && option.exclusion != null && (
            <Chip tone="red">excluded: breaks "{constraintLabel(scrub(option.exclusion.constraint))}"</Chip>
          )}
          {option.no_in_scope_evidence && <Chip tone="yellow">no in-scope evidence</Chip>}
          <span className={cn("font-semibold", excluded ? "text-grey" : "text-navy")}>{scrub(leverAmbitionLabel(option))}</span>
          {[
            ...(groupBy !== "theme" || excluded ? [themeOfOption.get(option.option_id) ?? "No theme"] : []),
            ...rowMetaParts(option),
          ].map((part) => (
            <span key={part} className="inline-flex items-center gap-x-2">
              <span aria-hidden="true">·</span>
              <span>{scrub(part)}</span>
            </span>
          ))}
        </p>
        {excludingId === option.option_id && (
          <form
            className="mt-3 flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              submitExclude(option.option_id);
            }}
          >
            <input
              autoFocus
              aria-label="Why exclude this option?"
              value={excludeReason}
              onChange={(event) => setExcludeReason(event.target.value)}
              placeholder="Why exclude this option?"
              className={REASON_INPUT_CLASS}
            />
            <Button
              type="submit"
              variant="secondary"
              size="sm"
              disabled={excludeReason.trim() === "" || excludeOption.isPending}
            >
              Exclude
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setExcludingId(null)}>
              Cancel
            </Button>
          </form>
        )}
      </li>
    );
  };

  // Theme sections carry the report's disclosure and open collapsed: the
  // summary line is the description plus the option names. Excluded options
  // leave their theme for one collapsed section at the end (owner,
  // 2026-09-23: a reader wants them only when curious).
  const included = (option: OptionSummaryOut) => option.state !== "excluded";
  const sortRows = byLeverThenName(leverTypes);
  const collect = (ids: readonly string[]) =>
    ids
      .map((id) => optionsById.get(id))
      .filter((option): option is OptionSummaryOut => option !== undefined)
      .filter(included)
      .filter(passesFilters)
      .sort(sortRows);
  const includedOptions = options.filter(included).filter(passesFilters);
  const themesOf = (group: readonly OptionSummaryOut[]) =>
    new Set(group.map((option) => themeOfOption.get(option.option_id) ?? "No theme")).size;
  const themeCount = (group: readonly OptionSummaryOut[]) => {
    const n = themesOf(group);
    return `${n} ${n === 1 ? "theme" : "themes"}`;
  };
  const byTheme = [
    ...(longlist.themes ?? []).map((theme) => ({
      key: theme.theme_id,
      name: theme.name,
      summary: themeSummary(theme.description),
      description: theme.description,
      options: collect(theme.option_ids ?? []),
    })),
    { key: "no-theme", name: "No theme", summary: "", description: "", options: collect(longlist.unthemed_option_ids ?? []) },
  ];
  // A lever or ambition group's description is the taxonomy's own one-line
  // definition; the heading's meta adds how many themes the group spans.
  const withDefinition = <T extends { options: OptionSummaryOut[] }>(group: T, definition: string) => ({
    ...group,
    description: definition,
    summary: definition,
  });
  const byLever = [
    ...leverTypes.map((lever) =>
      withDefinition(
        {
          key: lever,
          name: capitalise(lever),
          options: includedOptions.filter((option) => option.primary_lever_type === lever).sort((a, b) => a.name.localeCompare(b.name)),
        },
        leverDefinitions.get(lever) ?? "",
      ),
    ),
    withDefinition(
      {
        key: "none-fits",
        name: "No lever fits",
        options: includedOptions.filter((option) => option.primary_lever_type == null).sort((a, b) => a.name.localeCompare(b.name)),
      },
      "Options that no lever type on the list names; each says what it does instead.",
    ),
  ];
  const byAmbition = [
    ...(longlist.ambition_bands ?? []).map((band) =>
      withDefinition(
        {
          key: band.key,
          name: band.label,
          options: includedOptions.filter((option) => option.ambition === band.key).sort(sortRows),
        },
        definitionSentence(band.definition),
      ),
    ),
    withDefinition(
      { key: "untagged", name: "Untagged", options: includedOptions.filter((option) => option.ambition == null).sort(sortRows) },
      "Options without an ambition band yet.",
    ),
  ];
  const themeGroups = (groupBy === "theme" ? byTheme : groupBy === "lever" ? byLever : byAmbition)
    .filter((group) => group.options.length > 0)
    .map((group, index) => ({ ...group, id: sectionAnchor(group.name, index) }));
  const excludedOptions = options.filter((option) => option.state === "excluded").filter(passesFilters);

  const entries: SidebarEntry[] =
    mode === "grid"
      ? []
      : [
          ...themeGroups.map((group) => ({ id: group.id, title: group.name })),
          ...(excludedOptions.length > 0 ? [{ id: EXCLUDED_ANCHOR, title: "Excluded options" }] : []),
          { id: ADD_OPTION_ANCHOR, title: "Add an option" },
        ];

  const shownCount = includedOptions.length;
  const filtersActive = settingsFilter.size > 0 || whereFilter.size > 0;
  // A filter opens the sections it narrowed; the key remounts them with the
  // matching default. A new grouping remounts them closed.
  const sectionKey = (key: string) => `${groupBy}-${key}-${filtersActive ? "filtered" : "all"}`;

  return (
    <ReportPage entries={entries} className={mode === "grid" ? "md:max-w-[1180px]" : undefined}>
      <header className="mb-8">
        <ReportKindRow kind="Longlist" tag={<Chip tone="blue" title={SCOPING_PASS_SENTENCE}>{scrub(longlist.depth_label)}</Chip>}>
          <div role="group" aria-label="View" className="print-hide flex items-center gap-1.5">
            <button
              type="button"
              aria-pressed={mode === "list"}
              onClick={() => setMode("list")}
              className={facetChipClass(mode === "list")}
            >
              List
            </button>
            <button
              type="button"
              aria-pressed={mode === "grid"}
              onClick={() => setMode("grid")}
              className={facetChipClass(mode === "grid")}
            >
              Grid
            </button>
            {mode === "grid" && longlist.counts.excluded > 0 && (
              <button
                type="button"
                aria-pressed={showExcludedInGrid}
                onClick={() => setShowExcludedInGrid((value) => !value)}
                className={cn(facetChipClass(showExcludedInGrid), "ml-3")}
              >
                Show excluded
                <span className="ml-1.5 font-normal tabular-nums">{longlist.counts.excluded}</span>
              </button>
            )}
          </div>
        </ReportKindRow>
        <h1 className={REPORT_TITLE_CLASS}>{scrub(longlistTitle(plan.data?.scoping, task.data?.name))}</h1>
        <p className="mt-2 text-lead text-grey">{countsLine(longlist.counts)}</p>
      </header>

      <div className="print-hide mb-8 border-y border-line py-3">
        {mode === "list" && (
          <div role="group" aria-label="Group by" className="mb-2 flex flex-wrap items-start gap-1.5">
            <span className={FACET_LABEL_CLASS}>Group by</span>
            {GROUP_BY.map((choice) => (
              <button
                key={choice.key}
                type="button"
                aria-pressed={groupBy === choice.key}
                onClick={() => setGroupBy(choice.key)}
                className={facetChipClass(groupBy === choice.key)}
              >
                {choice.label}
              </button>
            ))}
          </div>
        )}
        {allSettings.length > 0 && (
          <div role="group" aria-label="Setting" className="flex flex-wrap items-start gap-1.5">
            <span className={FACET_LABEL_CLASS}>Setting</span>
            {shownSettings.map((setting) => (
              <button
                key={setting}
                type="button"
                aria-pressed={settingsFilter.has(setting)}
                onClick={() => setSettingsFilter((current) => toggleInSet(current, setting))}
                className={facetChipClass(settingsFilter.has(setting))}
              >
                {scrub(setting)}
              </button>
            ))}
            {hiddenSettings > 0 && (
              <button
                type="button"
                onClick={() => setAllSettingsShown(true)}
                className="cursor-pointer px-1 py-1.5 text-meta font-semibold text-blue underline-offset-4 hover:underline"
              >
                +{hiddenSettings} more
              </button>
            )}
            {allSettingsShown && allSettings.length > SETTING_FACET_LIMIT && (
              <button
                type="button"
                onClick={() => setAllSettingsShown(false)}
                className="cursor-pointer px-1 py-1.5 text-meta font-semibold text-blue underline-offset-4 hover:underline"
              >
                fewer
              </button>
            )}
          </div>
        )}
        <div role="group" aria-label="Where tried" className="mt-2 flex flex-wrap items-start gap-1.5">
          <span className={FACET_LABEL_CLASS}>Where tried</span>
          {whereChips.map((chip) => (
            <button
              key={chip.group}
              type="button"
              aria-pressed={whereFilter.has(chip.group)}
              onClick={() => setWhereFilter((current) => toggleInSet(current, chip.group))}
              className={facetChipClass(whereFilter.has(chip.group))}
            >
              {scrub(chip.label)}
            </button>
          ))}
        </div>
        {filtersActive && (
          <p className="mt-3 text-meta text-grey" role="status">
            {shownCount === 0
              ? "No option matches these filters."
              : `${shownCount} of ${longlist.counts.options} options match.`}
          </p>
        )}
      </div>

      {mode === "grid" ? (
        <LonglistGrid taskId={taskId} longlist={longlist} showExcluded={showExcludedInGrid} />
      ) : (
        <FullReportExpandProvider key={sectionKey("all")}>
          <div className="print-hide mb-4 flex justify-end">
            <FullReportExpandAllButton />
          </div>
          {themeGroups.map((group) => (
            <SectionDisclosure
              key={sectionKey(group.key)}
              id={group.id}
              section={{
                title: group.name,
                role: "standard",
                summary: group.summary,
                summary_status: "verified",
              }}
              defaultOpen={filtersActive}
              collapsible
              meta={[
                `${group.options.length} ${group.options.length === 1 ? "option" : "options"}`,
                groupBy === "theme" ? instrumentsSummary(group.options, leverTypes) : themeCount(group.options),
              ]
                .filter((part) => part !== "")
                .join(" · ")}
            >
              {group.description !== "" && (
                <p className="max-w-prose-measure text-body text-grey">{scrub(group.description)}</p>
              )}
              <ul role="list" className="divide-y divide-line border-t border-line">
                {group.options.map(renderOptionRow)}
              </ul>
            </SectionDisclosure>
          ))}
        </FullReportExpandProvider>
      )}
      {/* Outside the provider on purpose: Expand all opens the themes, not
          the set-aside options. */}
      {mode === "list" && (
        <>
        {excludedOptions.length > 0 && (
          <SectionDisclosure
            key={sectionKey("excluded")}
            id={EXCLUDED_ANCHOR}
            section={{
              title: "Excluded options",
              role: "conclusions",
              summary: "Set aside by a constraint or by you, with the reason.",
              summary_status: "verified",
            }}
            defaultOpen={false}
            collapsible
            meta={String(excludedOptions.length)}
          >
            <p className="max-w-prose-measure text-body text-grey">
              Set aside by a constraint or by you, with the reason. Include again puts one back in its theme.
            </p>
            <ul role="list" className="divide-y divide-line border-t border-line">
              {excludedOptions.map(renderOptionRow)}
            </ul>
          </SectionDisclosure>
        )}
        </>
      )}

      <form id={ADD_OPTION_ANCHOR} onSubmit={handleAddOption} className="print-hide mt-12 border-t border-line pt-6">
        <label htmlFor="longlist-add-option" className={`block ${REPORT_SECTION_HEADING_CLASS}`}>
          Add an option
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            id="longlist-add-option"
            value={addText}
            onChange={(event) => setAddText(event.target.value)}
            placeholder="An option of your own, in a few words"
            disabled={walkActive}
            className={cn(REASON_INPUT_CLASS, "max-w-md disabled:bg-paper-2 disabled:text-grey")}
          />
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            disabled={addText.trim() === "" || addOption.isPending || walkActive}
          >
            Add
          </Button>
        </div>
        <p className="mt-1.5 text-meta text-grey">
          {walkActive
            ? "Available once the current build finishes."
            : "It joins the longlist as added by you and gets its own evidence search."}
        </p>
      </form>
    </ReportPage>
  );
}
