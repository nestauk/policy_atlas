import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import type { components } from "../../api/gen/types";
import { useAddOption } from "../../api/mutations";
import { usePlan, useTask } from "../../api/queries";
import { actionFailedNotice } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { countOf } from "../../lib/vocabulary";
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
import { ShortlistView } from "./ShortlistView";
import {
  SCOPING_PASS_SENTENCE,
  byLeverThenName,
  capitalise,
  constraintLabel,
  countsParts,
  definitionSentence,
  holdsPlace,
  leverDefinitionFor,
  instrumentsSummary,
  leverLabel,
  longlistTitle,
  rowMetaParts,
  themeSummary,
} from "./longlistPresentation";
import {
  ExcludeReasonForm,
  OptionActionButton,
  REASON_INPUT_CLASS,
  ShortlistActionButton,
  useOptionActions,
} from "./optionActions";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];
type GroupBy = "theme" | "lever";

const GROUP_BY: { key: GroupBy; label: string }[] = [
  { key: "theme", label: "Theme" },
  { key: "lever", label: "Lever type" },
];

type Mode = "list" | "grid" | "shortlist";

const MODES: { key: Mode; label: string }[] = [
  { key: "list", label: "List" },
  { key: "grid", label: "Grid" },
  { key: "shortlist", label: "Shortlist" },
];

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

/**
 * The longlist's list view (contract deliverable 9, plan S13) on the
 * report's page chrome (EB-modified: `ReportPage`, `SectionDisclosure`):
 * the kind row with the List · Grid switch, the counts as the title and
 * snapshot cells, the Group by switch, theme sections that
 * expand and collapse like report sections, option rows, the "Do nothing"
 * reference, and an add-option row. The grid (D12) widens the paper.
 */
export function LonglistView({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const addOption = useAddOption(taskId);

  // A finished shortlist walk links here with ?mode=shortlist (task 055).
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<Mode>(
    searchParams.get("mode") === "shortlist" ? "shortlist" : "list",
  );
  const [groupBy, setGroupBy] = useState<GroupBy>("theme");
  const [showExcludedInGrid, setShowExcludedInGrid] = useState(false);
  const [addText, setAddText] = useState("");

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

  const walkActive = isRunActive(task.data);
  const actions = useOptionActions(taskId, walkActive);
  const { notice, setNotice } = actions;

  const handleAddOption = (event: FormEvent) => {
    event.preventDefault();
    const text = addText.trim();
    if (text === "" || addOption.isPending || walkActive) return;
    setNotice(null);
    addOption.mutate(
      { text },
      {
        onSuccess: () => setAddText(""),
        onError: (error) =>
          setNotice({ optionId: null, text: actionFailedNotice(error, "The option couldn't be added. Try again.") }),
      },
    );
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
          <div className="-my-2 flex flex-none items-center gap-2">
            <ShortlistActionButton
              actions={actions}
              optionId={option.option_id}
              shortlistState={option.shortlist?.state}
              excluded={excluded}
            />
            <OptionActionButton actions={actions} optionId={option.option_id} excluded={excluded} />
          </div>
        </div>
        <p className={cn("mt-1 max-w-[44em] text-body", excluded ? "text-grey" : "text-ink")}>
          {scrub(option.description)}
        </p>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-grey">
          {excluded && option.exclusion != null && (
            <Chip tone="red">excluded: breaks "{constraintLabel(scrub(option.exclusion.constraint))}"</Chip>
          )}
          {option.no_in_scope_evidence && <Chip tone="yellow">no in-scope evidence</Chip>}
          <span className={cn("font-semibold", excluded ? "text-grey" : "text-navy")}>{scrub(leverLabel(option))}</span>
          {[
            ...(groupBy !== "theme" || excluded ? [themeOfOption.get(option.option_id) ?? "No theme"] : []),
            ...rowMetaParts(option),
          ].map((part, index) => (
            <span key={`${index}-${part}`} className="inline-flex items-center gap-x-2">
              <span aria-hidden="true">·</span>
              <span>{scrub(part)}</span>
            </span>
          ))}
        </p>
        <ExcludeReasonForm
          actions={actions}
          optionId={option.option_id}
          className="mt-3 flex flex-wrap items-center gap-2"
        />
        {notice !== null && notice.optionId === option.option_id && (
          <p role="alert" className="mt-2 text-body text-red">
            {notice.text}
          </p>
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
      .sort(sortRows);
  const includedOptions = options.filter(included);
  const themeCount = (group: readonly OptionSummaryOut[]) =>
    countOf(new Set(group.map((option) => themeOfOption.get(option.option_id) ?? "No theme")).size, "theme", "themes");
  const byTheme = [
    ...(longlist.themes ?? []).map((theme) => ({
      key: theme.theme_id,
      name: theme.name,
      description: themeSummary(theme.description),
      options: collect(theme.option_ids ?? []),
    })),
    { key: "no-theme", name: "No theme", description: "", options: collect(longlist.unthemed_option_ids ?? []) },
  ];
  // A lever group's description is the taxonomy's own one-line
  // definition; the heading's meta adds how many themes the group spans.
  const withDefinition = <T extends { options: OptionSummaryOut[] }>(group: T, definition: string) => ({
    ...group,
    description: definition,
  });
  const byLever = [
    ...leverTypes.map((lever) => {
      const group = includedOptions
        .filter((option) => option.primary_lever_type === lever)
        .sort((a, b) => a.name.localeCompare(b.name));
      return withDefinition(
        { key: lever, name: capitalise(lever), options: group },
        leverDefinitionFor(
          lever,
          group,
          longlist.lever_type_definitions_by_version,
          leverDefinitions.get(lever) ?? "",
        ),
      );
    }),
    withDefinition(
      {
        key: "none-fits",
        name: "No lever fits",
        options: includedOptions.filter((option) => option.primary_lever_type == null).sort((a, b) => a.name.localeCompare(b.name)),
      },
      "Options that no lever type on the list names; each says what it does instead.",
    ),
  ];
  const themeGroups = (groupBy === "theme" ? byTheme : byLever)
    .filter((group) => group.options.length > 0)
    .map((group, index) => ({ ...group, id: sectionAnchor(group.name, index) }));
  const excludedOptions = options.filter((option) => option.state === "excluded");

  const entries: SidebarEntry[] =
    mode !== "list"
      ? []
      : [
          ...themeGroups.map((group) => ({ id: group.id, title: group.name })),
          ...(excludedOptions.length > 0 ? [{ id: EXCLUDED_ANCHOR, title: "Excluded options" }] : []),
          { id: ADD_OPTION_ANCHOR, title: "Add an option" },
        ];

  // A new grouping remounts the sections closed.
  const sectionKey = (key: string) => `${groupBy}-${key}`;

  const counts = countsParts(longlist.counts);

  return (
    <ReportPage entries={entries} className={mode === "grid" ? "md:max-w-[1180px]" : undefined}>
      <header className="mb-8">
        <ReportKindRow kind="Longlist" tag={<Chip tone="blue" title={SCOPING_PASS_SENTENCE}>{scrub(longlist.depth_label)}</Chip>}>
          <div role="group" aria-label="View" className="print-hide flex items-center gap-1.5">
            {MODES.map((choice) => (
              <button
                key={choice.key}
                type="button"
                aria-pressed={mode === choice.key}
                onClick={() => setMode(choice.key)}
                className={facetChipClass(mode === choice.key)}
              >
                {choice.label}
              </button>
            ))}
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
        <p className="mt-2 text-lead text-grey">
          {counts.head}
          {counts.excluded !== null && (
            <>
              {" · "}
              {mode === "list" ? (
                <a href={`#${EXCLUDED_ANCHOR}`} className="underline underline-offset-4 hover:text-navy">
                  {counts.excluded}
                </a>
              ) : (
                counts.excluded
              )}
            </>
          )}
          {counts.noInScope !== null && ` · ${counts.noInScope}`}
        </p>
      </header>

      {mode === "list" && (
        <div className="print-hide mb-8 border-y border-line py-3">
          <div role="group" aria-label="Group by" className="flex flex-wrap items-start gap-1.5">
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
        </div>
      )}

      {mode === "shortlist" ? (
        <ShortlistView
          taskId={taskId}
          longlist={longlist}
          otherGroups={themeGroups
            .map((group) => ({
              key: group.key,
              name: group.name,
              options: group.options.filter((option) => !holdsPlace(option)),
            }))
            .filter((group) => group.options.length > 0)}
          renderOtherRow={renderOptionRow}
        />
      ) : mode === "grid" ? (
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
                summary: group.description,
                summary_status: "verified",
              }}
              defaultOpen={false}
              collapsible
              meta={[
                countOf(group.options.length, "option", "options"),
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
      {mode === "list" && excludedOptions.length > 0 && (
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
        {notice !== null && notice.optionId === null && (
          <p role="alert" className="mt-2 text-body text-red">
            {notice.text}
          </p>
        )}
      </form>
    </ReportPage>
  );
}
