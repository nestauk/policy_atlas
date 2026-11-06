import { useEffect, useMemo, useState, useSyncExternalStore, type CSSProperties, type FormEvent, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { useAddOption } from "../../api/mutations";
import { useLonglist, useOptions, usePlan, useTask } from "../../api/queries";
import { actionFailedNotice } from "../../lib/errors";
import { Figures } from "../../lib/figures";
import { scrub } from "../../lib/scrub";
import { countOf } from "../../lib/vocabulary";
import { Button } from "../../ui/brand/Button";
import { StatusMark } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { prefersReducedMotion } from "../../ui/motion/motion";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { SectionDisclosure, sectionAnchor, type SidebarEntry } from "../ArtefactOutline";
import { REPORT_TITLE_CLASS, ReportPage } from "../reportPage";
import { isRunActive } from "../scopingActivity";
import { LonglistGrid } from "./LonglistGrid";
import {
  READ_FROM_ABSTRACTS,
  buildingLayout,
  capitalise,
  constraintLabel,
  countsParts,
  definitionSentence,
  instrumentsSummary,
  layoutSignature,
  leverDefinitionFor,
  longlistTitle,
  rowMetaFields,
  type BuildingLayout,
  type BuildingRow,
} from "./longlistPresentation";
import {
  ExcludeReasonForm,
  OptionActionButton,
  REASON_INPUT_CLASS,
  ShortlistToggle,
  ShortlistedWord,
  useOptionActions,
} from "./optionActions";
import "./longlist.css";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];
type GroupBy = "theme" | "lever";
type Mode = "list" | "grid";
type OptionActions = ReturnType<typeof useOptionActions>;

/**
 * The finished longlist opens with its theme sections open (round 10, lead
 * ruling D1, reversing the owner's 2026-09-23 "open collapsed" for themes),
 * so its first screen shows options, not a wall of headings. One switch for
 * the owner to decide: `false` restores the collapsed themes. Excluded
 * options stay collapsed either way.
 */
export const THEMES_OPEN_BY_DEFAULT = true;

const GROUP_BY: { key: GroupBy; label: string }[] = [
  { key: "theme", label: "Theme" },
  { key: "lever", label: "Lever type" },
];

const MODES: { key: Mode; label: string }[] = [
  { key: "list", label: "List" },
  { key: "grid", label: "Grid" },
];

const ADD_OPTION_ANCHOR = "add-option";
const EXCLUDED_ANCHOR = "excluded-options";
const EXCLUDED_SUMMARY = "Set aside by a constraint or by you, with the reason.";

/** Theme sections rise one after another, 60 ms apart; under reduced
 *  motion every wave appears at once. Literal classes so the build keeps them. */
const RISE_DELAY_CLASSES = [
  "",
  "motion-safe:[animation-delay:60ms]",
  "motion-safe:[animation-delay:120ms]",
  "motion-safe:[animation-delay:180ms]",
  "motion-safe:[animation-delay:240ms]",
];

/** The class `longlist.css` keys the regrouping's names on, set on the
 *  document only while a regrouping transition runs. */
const REGROUPING_CLASS = "longlist-regrouping";

type ViewTransitionStart = (update: () => void) => { finished: Promise<void> };

/** The browser's View Transition, when it has one (not jsdom, not every browser). */
function viewTransitionStart(): ViewTransitionStart | null {
  const start = (document as Document & { startViewTransition?: ViewTransitionStart }).startViewTransition;
  return typeof start === "function" ? start.bind(document) : null;
}

/**
 * The layout on screen, moving its rows when the grouping changes (round
 * 10, finding 2): rows that are already on screen keep their opacity and
 * travel to their new place over 300 ms on the strong ease-out (a View
 * Transition, each row named by its option), so a theme wave or an exclusion
 * never blanks the list. Any other change (a value landing) shows at once.
 * Without View Transitions, or under reduced motion, the list cuts to its
 * new order.
 *
 * Args:
 *   layout: The layout the reads give now (memoised on the reads).
 *
 * Returns:
 *   The layout to render.
 */
function useRegroupTransition(layout: BuildingLayout): BuildingLayout {
  const signature = layoutSignature(layout);
  const [shown, setShown] = useState({ signature, layout });
  // A value landing within the same grouping updates in place.
  if (shown.signature === signature && shown.layout !== layout) setShown({ signature, layout });
  useEffect(() => {
    if (shown.signature === signature) return;
    const commit = () => setShown({ signature, layout });
    const start = viewTransitionStart();
    if (start === null || prefersReducedMotion()) {
      commit();
      return;
    }
    const root = document.documentElement;
    root.classList.add(REGROUPING_CLASS);
    const transition = start(() => flushSync(commit));
    void transition.finished.finally(() => root.classList.remove(REGROUPING_CLASS));
  }, [signature, layout, shown.signature]);
  return shown.signature === signature ? layout : shown.layout;
}

const WIDE_QUERY = "(min-width: 48rem)";

function subscribeWide(onChange: () => void): () => void {
  const query = typeof window.matchMedia === "function" ? window.matchMedia(WIDE_QUERY) : null;
  query?.addEventListener("change", onChange);
  return () => query?.removeEventListener("change", onChange);
}

/** Whether the screen is `md` or wider; true where the media query cannot be
 *  asked (tests). The grid is offered only there (round 10, finding 13). */
function useWideScreen(): boolean {
  return useSyncExternalStore(
    subscribeWide,
    () => (typeof window.matchMedia === "function" ? window.matchMedia(WIDE_QUERY).matches : true),
    () => true,
  );
}

/** What can arrive while the page is open, each with its own key. Anything
 *  already on screen when the page opened does not animate. */
function arrivalKeys(layout: BuildingLayout): Set<string> {
  const keys = new Set<string>();
  const add = (row: BuildingRow) => {
    keys.add(`row:${row.id}`);
    if (row.summary !== null) keys.add(`meta:${row.id}`);
    if (row.lever !== null) keys.add(`lever:${row.id}`);
    if (row.shortlisted) keys.add(`short:${row.id}`);
    for (const folded of row.folded) keys.add(`fold:${folded.id}`);
  };
  for (const group of layout.groups) {
    if (group.title !== null) keys.add(`theme:${group.key}`);
    group.rows.forEach(add);
  }
  if (layout.excluded.length > 0) keys.add("excluded");
  layout.excluded.forEach(add);
  return keys;
}

/**
 * A switch between two or three views (round 10, finding 3): the outline
 * button's look, joined into one bar, `aria-pressed` on each; the chosen one
 * takes a Navy border and Navy words, the others stay Grey. 40 px tall, the
 * height of every control but the primary. Never a fill: the fill belongs to
 * the page's one primary.
 */
function OutlineSwitch<K extends string>({
  label,
  choices,
  value,
  onChange,
}: {
  label: string;
  choices: { key: K; label: string }[];
  value: K;
  onChange: (key: K) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex">
      {choices.map((choice, index) => {
        const pressed = choice.key === value;
        return (
          <button
            key={choice.key}
            type="button"
            aria-pressed={pressed}
            onClick={() => onChange(choice.key)}
            className={cn(
              "pressable relative h-10 cursor-pointer border bg-paper px-3.5 text-meta font-semibold transition-colors duration-150",
              index > 0 && "-ml-px",
              pressed
                ? "z-10 border-navy text-navy"
                : "border-line-2 text-grey hover:bg-[#f0f0f3] hover:text-navy",
            )}
          >
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}

/** One field of a row's meta line: whole, so a line wraps between fields;
 *  the middot after it belongs to it, so no line starts with one, and a
 *  screen reader hears a comma in its place. */
function MetaField({ last, children }: { last: boolean; children: ReactNode }) {
  return (
    <span className="inline-block max-w-full">
      <span>{children}</span>
      {!last && (
        <>
          <span aria-hidden="true">{" ·"}</span>
          <span className="sr-only">,</span>
        </>
      )}
    </span>
  );
}

/**
 * One option row, the same from the first row of the build to the finished
 * list (round 10, finding 2): the name with its origin words beside it, the
 * row's own search while it runs at the right, the description, one meta
 * line of fixed fields (the lever, the theme when the grouping does not say
 * it, relations, the evidence, "No in-scope evidence"), the exclusion, and
 * the suggestions folded into it. The finished list adds its controls: the
 * name links to the option card, the shortlist toggle and Exclude or
 * Include again.
 */
function OptionRow({
  taskId,
  row,
  theme,
  showLever,
  controls,
  rises,
  lands,
}: {
  taskId: string;
  row: BuildingRow;
  /** The theme to name on the meta line, or null when the grouping says it. */
  theme: string | null;
  /** False under a lever heading, which already names it. */
  showLever: boolean;
  /** The finished list's row controls; null while the list is built. */
  controls: OptionActions | null;
  /** The row itself arrives (it rises in). */
  rises: boolean;
  /** Which of its parts arrive now (they fade in). */
  lands: (part: "meta" | "lever" | "short" | "fold", id?: string) => boolean;
}) {
  const summary = row.summary;
  const lever = showLever ? row.lever : null;
  const excluded = summary?.state === "excluded";
  const fields = summary === null ? [] : rowMetaFields(summary, theme);
  const status = row.status;
  const exclusion = excluded ? (summary?.exclusion ?? null) : null;
  const notice = controls?.notice ?? null;
  // The row's name in the regrouping transition (`longlist.css`).
  const style = { "--longlist-row": `opt-${row.id}` } as CSSProperties;
  return (
    <li className={cn("longlist-row border-b border-line py-4", rises && "anim-rise")} style={style}>
      <div className="flex items-start justify-between gap-x-6 gap-y-1 max-sm:flex-col">
        <p className="min-w-0 text-body">
          {controls !== null ? (
            <Link
              to={`/tasks/${taskId}/options/${row.id}`}
              className={cn("font-bold underline-offset-4 hover:underline", excluded ? "text-grey" : "text-navy")}
            >
              {scrub(row.name)}
            </Link>
          ) : (
            <span className={cn("font-bold", excluded ? "text-grey" : "text-navy")}>{scrub(row.name)}</span>
          )}
          {/* A space, so a long name can break before its origin words. */}{" "}
          <span className="ml-1.5 whitespace-nowrap text-meta text-grey">{row.origin}</span>
        </p>
        <div className="-mt-1 flex flex-none items-center gap-x-4 text-meta text-grey max-sm:mt-0 max-sm:-ml-px">
          {status !== null && (
            <span className="inline-flex min-h-8 items-center gap-2 whitespace-nowrap">
              {/* A live search breathes its 6 px blue square; the one turning
                  mark on the screen is the status bar's (round 10, D3). */}
              {status.kind === "searching" && <StatusMark tone="running" breathing />}
              {status.kind === "failed" && <StatusMark tone="failed" />}
              <span className={cn(status.kind === "failed" && "font-semibold text-red")}>
                <Figures text={status.text} />
              </span>
            </span>
          )}
          {controls !== null && summary !== null ? (
            <>
              <ShortlistToggle
                actions={controls}
                optionId={row.id}
                shortlistState={summary.shortlist?.state}
                excluded={excluded}
              />
              <OptionActionButton actions={controls} optionId={row.id} excluded={excluded} />
            </>
          ) : (
            row.shortlisted && <ShortlistedWord className={cn(lands("short") && "anim-swap-in")} />
          )}
        </div>
      </div>
      {row.description !== "" && (
        <p className={cn("mt-1 max-w-[44em] text-body", excluded ? "text-grey" : "text-ink")}>{scrub(row.description)}</p>
      )}
      {(lever !== null || fields.length > 0) && (
        <p className={cn("mt-1.5 max-w-[44em] text-meta text-grey", lands("meta") && "anim-swap-in")}>
          {lever !== null && (
            <>
              <MetaField last={fields.length === 0}>
                <span
                  className={cn(
                    "font-semibold",
                    excluded ? "text-grey" : "text-navy",
                    !lands("meta") && lands("lever") && "inline-block anim-swap-in",
                  )}
                >
                  {scrub(lever)}
                </span>
              </MetaField>{" "}
            </>
          )}
          {fields.map((field, index) => (
            <span key={`${index}-${field}`}>
              <MetaField last={index === fields.length - 1}>{scrub(field)}</MetaField>{" "}
            </span>
          ))}
        </p>
      )}
      {exclusion !== null && (
        <p className="mt-1.5 max-w-[44em] text-meta text-ink">
          <span className="font-semibold text-red">Excluded:</span>{" "}
          {constraintLabel(exclusion.constraint ?? "") !== "" && (
            <>breaks "{constraintLabel(scrub(exclusion.constraint ?? ""))}". </>
          )}
          {scrub(exclusion.reason ?? "")}
        </p>
      )}
      {row.folded.map((folded) => (
        <div key={folded.id} className={cn("mt-3 border-l border-line-2 pl-4", lands("fold", folded.id) && "anim-rise")}>
          <p className="text-body text-grey">{scrub(folded.name)}</p>
          <p className="text-meta text-grey">Folded into {scrub(row.name)}</p>
        </div>
      ))}
      {controls !== null && (
        <ExcludeReasonForm actions={controls} optionId={row.id} className="mt-3 flex flex-wrap items-center gap-2" />
      )}
      {notice !== null && notice.optionId === row.id && (
        <p role="alert" className="mt-2 text-body text-red">
          {notice.text}
        </p>
      )}
    </li>
  );
}

/** A group of rows on the page: a theme, a lever type, or (before the theme
 *  wave) the one untitled run of rows. */
type Section = { key: string; title: string | null; description: string; rows: BuildingRow[] };

/**
 * The longlist, from the first row of its build to the finished list (task
 * 058, N24 and round 10; contract deliverable 9 for the finished list), on
 * the report's page chrome (EB-modified: `ReportPage`, `SectionDisclosure`).
 *
 * One page and one row anatomy all the way (round 10, finding 2). The title
 * is "Longlist" with the plan's question under it. While a walk builds the
 * list (`longlist` not passed) rows come from the options read as soon as
 * suggest has written them, each with its own search, and from clustering on
 * the longlist read fills them in place in waves (the evidence line, the
 * lever, exclusions, themes, shortlist marks); rows move into their themes
 * rather than blinking out. No stage line: the run status bar above says
 * what the walk is doing (round 10, D3). Once the walk ends the same page
 * gains its controls: the counts' link to the excluded options, Group by,
 * List or Grid (from `md` up), Show all, each row's toggle and actions, and
 * Add an option. The grid widens the paper.
 *
 * `LonglistBuilding` and `LonglistView` are this one component, so the
 * Result tab's switch from one to the other at the walk's end keeps the page
 * mounted: React keeps an instance only while its type is the same.
 *
 * Args:
 *   taskId: The scoping task.
 *   longlist: The finished longlist; absent while a walk builds it.
 */
export function Longlist({ taskId, longlist: finished }: { taskId: string; longlist?: LonglistOut }) {
  const building = finished === undefined;
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const options = useOptions(taskId);
  const longlistRead = useLonglist(taskId);
  const addOption = useAddOption(taskId);
  const wide = useWideScreen();

  const [chosenMode, setMode] = useState<Mode>("list");
  const [chosenGroupBy, setGroupBy] = useState<GroupBy>("theme");
  const [showExcludedInGrid, setShowExcludedInGrid] = useState(false);
  // "Show all" / "Hide all" (the report's words, round 10): the sections
  // start as the switch above says and remount open or shut on a press.
  const [allOpen, setAllOpen] = useState({ open: THEMES_OPEN_BY_DEFAULT, revision: 0 });
  const [addText, setAddText] = useState("");
  // The grid is not offered on a phone, nor while the list is being built.
  const mode: Mode = building || !wide ? "list" : chosenMode;
  const groupBy: GroupBy = building ? "theme" : chosenGroupBy;

  const longlist = finished ?? longlistRead.data ?? null;
  const optionRows = options.data?.options;
  // Once the list is finished the longlist read is the authority: a row the
  // options read has but the longlist does not (and that was not folded
  // into another) is not on the list.
  const computed = useMemo(() => {
    const layout = buildingLayout(optionRows ?? [], longlist);
    if (building) return layout;
    const listed = (rows: BuildingRow[]) => rows.filter((row) => row.summary !== null);
    return {
      groups: layout.groups.map((group) => ({ ...group, rows: listed(group.rows) })).filter((group) => group.rows.length > 0),
      excluded: listed(layout.excluded),
    };
  }, [optionRows, longlist, building]);
  const layout = useRegroupTransition(computed);
  // Only a list being built has arrivals; a finished list opens still.
  const [initialKeys] = useState(() => arrivalKeys(layout));
  const arrives = (key: string) => building && !initialKeys.has(key);

  const walkActive = isRunActive(task.data);
  const actions = useOptionActions(taskId, walkActive);
  const { notice, setNotice } = actions;
  const controls = building ? null : actions;

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

  const leverTypes = longlist?.lever_types ?? [];
  const themeOfOption = new Map<string, string>();
  for (const theme of longlist?.themes ?? []) {
    for (const id of theme.option_ids ?? []) themeOfOption.set(id, theme.name);
  }
  const summaryOf = (row: BuildingRow): Pick<OptionSummaryOut, "primary_lever_type"> =>
    row.summary ?? { primary_lever_type: null };

  // By lever type (the finished list only): the taxonomy's own one-line
  // definition under each heading; the meta adds how many themes it spans.
  const includedRows = layout.groups.flatMap((group) => group.rows);
  const leverDefinitions = new Map(
    (longlist?.lever_type_definitions ?? []).map((lever) => [lever.key, definitionSentence(lever.definition)]),
  );
  const byName = (a: BuildingRow, b: BuildingRow) => a.name.localeCompare(b.name);
  const byLever: Section[] = [
    ...leverTypes.map((lever) => {
      const rows = includedRows.filter((row) => row.summary?.primary_lever_type === lever).sort(byName);
      return {
        key: lever,
        title: capitalise(lever),
        description: leverDefinitionFor(
          lever,
          rows.flatMap((row) => (row.summary === null ? [] : [row.summary])),
          longlist?.lever_type_definitions_by_version,
          leverDefinitions.get(lever) ?? "",
        ),
        rows,
      };
    }),
    {
      key: "none-fits",
      title: "No lever fits",
      description: "Options that no lever type on the list names; each says what it does instead.",
      rows: includedRows.filter((row) => row.summary?.primary_lever_type == null).sort(byName),
    },
  ];
  const sections = (groupBy === "theme" ? layout.groups : byLever)
    .filter((group) => group.rows.length > 0)
    .map((group, index) => ({ ...group, id: group.title === null ? "options" : sectionAnchor(group.title, index) }));
  const titled = sections.some((section) => section.title !== null);
  const excludedRows = layout.excluded;

  const entries: SidebarEntry[] =
    mode !== "list" || !titled
      ? []
      : [
          ...sections.map((section) => ({ id: section.id, title: section.title ?? "" })),
          ...(excludedRows.length > 0 ? [{ id: EXCLUDED_ANCHOR, title: "Excluded" }] : []),
          ...(building ? [] : [{ id: ADD_OPTION_ANCHOR, title: "Add an option" }]),
        ];

  // A new grouping, or Show all / Hide all, remounts the sections.
  const sectionKey = (key: string) => `${groupBy}-${allOpen.revision}-${key}`;
  const themeCount = (rows: readonly BuildingRow[]) =>
    countOf(new Set(rows.map((row) => themeOfOption.get(row.id) ?? "No theme")).size, "theme", "themes");
  const rowTheme = (row: BuildingRow) =>
    groupBy === "theme" && row.summary?.state !== "excluded" ? null : (themeOfOption.get(row.id) ?? null);

  const renderRow = (row: BuildingRow, flat: boolean) => (
    <OptionRow
      key={row.id}
      taskId={taskId}
      row={row}
      theme={rowTheme(row)}
      showLever={groupBy !== "lever" || row.summary?.state === "excluded"}
      controls={controls}
      rises={flat && arrives(`row:${row.id}`)}
      lands={(part, id) => arrives(part === "fold" ? `fold:${id}` : `${part}:${row.id}`)}
    />
  );

  const question = scrub(longlistTitle(plan.data?.scoping, task.data?.name));
  const counts = longlist === null ? null : countsParts(longlist.counts);

  return (
    <ReportPage entries={entries} className={cn("longlist-paper", mode === "grid" && "md:max-w-[1180px]")}>
      <header className="mb-6">
        <h1 className={REPORT_TITLE_CLASS}>Longlist</h1>
        {question !== "Longlist" && (
          <p className="mt-2 max-w-prose-measure text-lead text-grey max-md:text-body">{question}</p>
        )}
        {counts !== null && (
          <div className="mt-3 text-meta text-grey">
            <p>
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
            <p>{READ_FROM_ABSTRACTS}</p>
          </div>
        )}
      </header>

      {!building && (
        <div className="print-hide mb-6 flex min-h-10 flex-wrap items-center justify-between gap-x-6 gap-y-3">
          {mode === "list" ? (
            <div className="flex items-center gap-3">
              <span className="text-meta font-semibold text-grey">Group by</span>
              <OutlineSwitch label="Group by" choices={GROUP_BY} value={groupBy} onChange={setGroupBy} />
            </div>
          ) : (
            longlist !== null &&
            longlist.counts.excluded > 0 && (
              <button
                type="button"
                aria-pressed={showExcludedInGrid}
                onClick={() => setShowExcludedInGrid((value) => !value)}
                className={cn(
                  "pressable h-10 cursor-pointer border bg-paper px-3.5 text-meta font-semibold transition-colors duration-150",
                  showExcludedInGrid ? "border-navy text-navy" : "border-line-2 text-grey hover:bg-[#f0f0f3] hover:text-navy",
                )}
              >
                Show excluded
                <span className="ml-1.5 font-normal tabular-nums">{longlist.counts.excluded}</span>
              </button>
            )
          )}
          {wide && <OutlineSwitch label="View" choices={MODES} value={mode} onChange={setMode} />}
        </div>
      )}

      {mode === "grid" && longlist !== null ? (
        <LonglistGrid taskId={taskId} longlist={longlist} showExcluded={showExcludedInGrid} />
      ) : (
        <>
          {titled && (
            <div className="print-hide mb-2 flex justify-end">
              <button
                type="button"
                onClick={() => setAllOpen(({ open, revision }) => ({ open: !open, revision: revision + 1 }))}
                className={cn(QUIET_CONTROL_CLASS, "text-meta")}
              >
                {allOpen.open ? "Hide all" : "Show all"}
              </button>
            </div>
          )}
          {sections.map((section, index) =>
            section.title === null ? (
              <ul key={section.key} role="list" aria-label="Options" className="border-t border-line">
                {section.rows.map((row) => renderRow(row, true))}
              </ul>
            ) : (
              <div
                key={sectionKey(section.key)}
                className={cn(
                  arrives(`theme:${section.key}`) && "anim-rise",
                  arrives(`theme:${section.key}`) && RISE_DELAY_CLASSES[Math.min(index, RISE_DELAY_CLASSES.length - 1)],
                )}
              >
                <SectionDisclosure
                  id={section.id}
                  section={{ title: section.title, role: "standard", summary: section.description, summary_status: "verified" }}
                  defaultOpen={allOpen.open}
                  collapsible
                  meta={[
                    countOf(section.rows.length, "option", "options"),
                    groupBy === "theme"
                      ? instrumentsSummary(section.rows.map(summaryOf), leverTypes)
                      : themeCount(section.rows),
                  ]
                    .filter((part) => part !== "")
                    .join(" · ")}
                >
                  {section.description !== "" && (
                    <p className="max-w-prose-measure text-body text-grey">{scrub(section.description)}</p>
                  )}
                  <ul role="list" className="border-t border-line">
                    {section.rows.map((row) => renderRow(row, false))}
                  </ul>
                </SectionDisclosure>
              </div>
            ),
          )}
        </>
      )}
      {/* Show all opens the themes, not the set-aside options. */}
      {mode === "list" && excludedRows.length > 0 && (
        <div className={cn("mt-10", arrives("excluded") && "anim-rise")}>
          <SectionDisclosure
            key={`${groupBy}-excluded`}
            id={EXCLUDED_ANCHOR}
            section={{ title: "Excluded", role: "conclusions", summary: EXCLUDED_SUMMARY, summary_status: "verified" }}
            defaultOpen={false}
            collapsible
            meta={String(excludedRows.length)}
          >
            {!building && (
              <p className="max-w-prose-measure text-body text-grey">
                {EXCLUDED_SUMMARY} Include again puts one back in its theme.
              </p>
            )}
            <ul role="list" className="border-t border-line">
              {excludedRows.map((row) => renderRow(row, false))}
            </ul>
          </SectionDisclosure>
        </div>
      )}

      {!building && (
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
      )}
    </ReportPage>
  );
}

/** The longlist while a walk builds it (task 058, N24; annex scene 15). */
export const LonglistBuilding = Longlist;

/** The finished longlist (contract deliverable 9). */
export const LonglistView = Longlist;
