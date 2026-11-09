import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties, type FormEvent, type ReactNode } from "react";
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
import { useRunStream } from "../../store";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { sectionAnchor, useOpenWhenNavigated } from "../ArtefactOutline";
import { DisclosureWord, useExpandForPrint } from "../../ui/brand/Disclosure";
import { LABEL_CLASS } from "../../ui/brand/label";
import { OutlineSwitch } from "../../ui/brand/OutlineSwitch";
import { REPORT_TITLE_CLASS, ReportPage } from "../reportPage";
import { isRunActive } from "../scopingActivity";
import { GroupCount, GroupName } from "./GroupHeading";
import { ChevronIcon } from "../../ui/brand/icons";
import { useOpenAtTop } from "../../lib/openAtTop";
import { InfoHint } from "../../ui/brand/InfoHint";
import { usePublicView } from "../publicView";
import { LonglistGrid, NoOptionsFoot, type GridLine } from "./LonglistGrid";
import { Select } from "../../ui/brand/Select";
import { useRegroupTransition } from "./regroupTransition";
import {
  OTHER_LEVER,
  GRID_COLUMN_LINES,
  LINE_NAMES,
  groupCountWords,
  uncoveredLevers,
  themeSummary,
  EXCLUDE_GROUP_FROM_SHORTLISTING,
  INCLUDE_GROUP_AGAIN,
  EXCLUDE_TOOLTIP,
  buildingLayout,
  capitalise,
  countsParts,
  groupExclusionReason,
  exclusionLine,
  leverCount,
  definitionSentence,
  layoutSignature,
  shortlistedFirst,
  leverDefinitionFor,
  liveNamesOf,
  longlistTitle,
  NO_LIVE_NAMES,
  rowMetaFields,
  type BuildingLayout,
  type BuildingRow,
} from "./longlistPresentation";
import {
  REASON_INPUT_CLASS,
  ShortlistToggle,
  ShortlistedWord,
  EdgeAction,
  useOptionActions,
} from "./optionActions";
import "./longlist.css";

type LonglistOut = components["schemas"]["LonglistOut"];
type GroupBy = "theme" | "lever";
type Mode = "list" | "grid";
type OptionActions = ReturnType<typeof useOptionActions>;

const GROUP_BY: { key: GroupBy; label: string }[] = [
  { key: "theme", label: "Theme" },
  { key: "lever", label: "Lever" },
];

/** The "i" beside Group by (round 12, owner): the two definitions, one line
 *  each, nothing else. */
export const GROUP_BY_INFO_LABEL = "What a theme and a lever are";
export const GROUP_BY_INFO = [
  "Theme: a group of options that work in a similar way.",
  "Lever: the kind of action that the policy takes.",
] as const;

const MODES: { key: Mode; label: string }[] = [
  { key: "list", label: "List" },
  { key: "grid", label: "Grid" },
];

const ADD_OPTION_ANCHOR = "add-option";
const EXCLUDED_ANCHOR = "excluded-options";
const EXCLUDED_SUMMARY = "Excluded from shortlisting by a constraint or by you.";

/** Theme sections rise one after another, 60 ms apart; under reduced
 *  motion every wave appears at once. Literal classes so the build keeps them. */
const RISE_DELAY_CLASSES = [
  "",
  "motion-safe:[animation-delay:60ms]",
  "motion-safe:[animation-delay:120ms]",
  "motion-safe:[animation-delay:180ms]",
  "motion-safe:[animation-delay:240ms]",
];

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
    keys.add(`row:${row.key}`);
    if (row.summary !== null) keys.add(`meta:${row.key}`);
    if (row.lever !== null) keys.add(`lever:${row.key}`);
    if (row.shortlisted) keys.add(`short:${row.key}`);
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
 * A group of options on the list (round 11, review findings 3, 11 and 13): a
 * theme, a lever type or the excluded options. Its heading is the Label
 * style (uppercase, tracked, Grey) holding the disclosure button (the
 * report's pattern, so it stays in the outline): the name on the left, and
 * at the line's right the count in Meta Grey, then the chevron with "Show"
 * or "Hide" on the page's one right edge (round 12) at every width; under it one Body Grey
 * line, the group's description, open or shut (ruling 1: a collapsed header
 * carries its one-line takeaway); then the rows, 16 px apart. Opens when the
 * contents or a link points at it, and for print.
 */
function GroupSection({
  id,
  title,
  count,
  description,
  defaultOpen,
  className,
  action,
  children,
  onOpenChange,
  level = 2,
  muted = false,
}: {
  id: string;
  title: string;
  /** The count beside the title; "" for a theme no option is in yet. */
  count: string;
  description: string;
  defaultOpen: boolean;
  className?: string;
  /** The group's own control, its first line while open (round 13, owner):
   *  "Exclude this theme" / "Exclude this lever", or "Include again". */
  action?: GroupAction;
  /** The group's rows; none for a group all set aside. */
  children?: ReactNode;
  /** Told when the group opens or shuts, so the page's Show all knows. */
  onOpenChange?: (open: boolean) => void;
  /** 3 for a group inside Excluded (round 13, owner). */
  level?: 2 | 3;
  /** The name in Grey, for a group excluded whole. */
  muted?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Heading = level === 3 ? "h3" : "h2";
  useEffect(() => onOpenChange?.(open), [open, onOpenChange]);
  useOpenWhenNavigated(id, setOpen);
  useExpandForPrint(setOpen);
  // The group's own control, on the description's line at its right edge,
  // over the rows' shortlist toggles, while the group is open (round 13,
  // owner): the words, then the glyph at the row toggle's size, centred in
  // the toggle's 40 px width so the glyphs make one column. Its hit area is
  // its own line, clear of the heading's Show / Hide.
  const control =
    action === undefined || !open ? null : (
      <EdgeAction
        label={action.label}
        include={action.include}
        disabled={action.disabled}
        onClick={() => action.run("")}
        tooltip={action.tooltip}
        className="self-start"
      />
    );
  return (
    <section id={id} className={cn("mb-8", className)}>
      <Heading className={LABEL_CLASS}>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="group flex min-h-10 w-full cursor-pointer items-baseline gap-4 py-2 text-left"
        >
          {/* The name on the left; the count, then the chevron with Show or
              Hide, at the line's right (round 12, owner: every count and
              control on the page on one right edge), so a shut group reads
              as one line at every width. The button resets text-transform
              (Tailwind's preflight), so the title carries the Label's
              uppercase itself. The name in Navy (round 12, owner). */}
          <GroupName title={title} className={cn("min-w-0 flex-1", muted && "text-grey")} />
          {count !== "" && " "}
          {count !== "" && <GroupCount count={count} className="shrink-0 text-right" />}
          <DisclosureWord open={open} className="normal-case tracking-normal" />
        </button>
      </Heading>
      {(description !== "" || control !== null) && (
        <div className="flex items-start justify-between gap-6">
          {description !== "" && <p className="max-w-prose-measure text-body text-grey">{scrub(description)}</p>}
          {control !== null && <div className="ml-auto flex">{control}</div>}
        </div>
      )}
      {open && children}
    </section>
  );
}

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
 * list (round 10, finding 2), and as light as a scanning list needs (round
 * 11, review findings 4, 6, 12 and 14): the name, its one-sentence
 * description (ruling 8), one Meta Grey line (the lever, or the theme under
 * a lever heading; the evidence's first part; "No in-scope evidence"), and
 * the exclusion for an excluded option (ruling 4: the constraint it broke).
 * At the right the row's own search while it is the news, then the shortlist
 * toggle and Exclude or Include again (ruling 42's row actions); on a phone
 * they close the row. Origin words, relations, the rest of the evidence and
 * the suggestions folded in are the option card's. Nothing in the row is
 * bold but the name.
 */
function OptionRow({
  taskId,
  row,
  theme,
  showLever,
  controls,
  rises,
  lands,
  inExcludedGroup = false,
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
  lands: (part: "meta" | "lever" | "short") => boolean;
  /** Under an excluded group's heading, which names the theme or lever. */
  inExcludedGroup?: boolean;
}) {
  const summary = row.summary;
  const excluded = summary?.state === "excluded";
  const fields = summary === null ? [] : rowMetaFields(summary, showLever ? row.lever : null, theme);
  const status = row.status;
  const recorded = excluded ? (summary?.exclusion ?? null) : null;
  // Under its group's heading the row reads "Excluded by you" and any reason
  // of its own, not the group's words again (round 13, lead).
  const exclusion =
    recorded !== null && inExcludedGroup
      ? { ...recorded, reason: (recorded.reason ?? "").replace(/^with the (theme|lever) [^:]+:?\s*/, "") }
      : recorded;
  const notice = controls?.notice ?? null;
  const publicView = usePublicView();
  // The row's name in the regrouping transition (`longlist.css`).
  const style = { "--longlist-row": `opt-${row.key}` } as CSSProperties;
  return (
    <li className={cn("longlist-row", rises && "anim-rise")} style={style}>
      <div className="flex items-start gap-x-6 gap-y-1 max-sm:flex-col">
        <div className="min-w-0 flex-1">
          <p className="text-body">
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
          </p>
          {row.description !== "" && (
            <p className={cn("max-w-[44em] text-body", excluded ? "text-grey" : "text-ink")}>{scrub(row.description)}</p>
          )}
          {fields.length > 0 && (
            <p className={cn("mt-0.5 max-w-[44em] text-meta text-grey", (lands("meta") || lands("lever")) && "anim-swap-in")}>
              {fields.map((field, index) => (
                <span key={`${index}-${field}`}>
                  <MetaField last={index === fields.length - 1}>{scrub(field)}</MetaField>{" "}
                </span>
              ))}
            </p>
          )}
          {/* Why it is excluded, at the meta line's size and colour: the
              grey alone marks an excluded row (round 12, owner). */}
          {exclusion !== null && exclusionLine(exclusion) !== "" && (
            <p className="mt-0.5 max-w-[44em] text-meta text-grey">
              {/* A reason is added on the option card only; here it is text
                  (round 13, owner). */}
              {scrub(exclusionLine(exclusion))}
            </p>
          )}
        </div>
        <div className="flex flex-none items-center gap-x-4 text-meta text-grey sm:-mt-1">
          {status !== null && (
            <span className="inline-flex min-h-8 items-center gap-2 whitespace-nowrap">
              {/* A live search breathes its 6 px blue square; the one turning
                  mark on the screen is the status bar's (round 10, D3). */}
              {(status.kind === "searching" || status.kind === "assigning") && <StatusMark tone="running" breathing />}
              {status.kind === "failed" && <StatusMark tone="failed" />}
              <span className={cn(status.kind === "failed" && "font-semibold text-red")}>
                <Figures text={status.text} />
              </span>
            </span>
          )}
          {/* Include again on the action column, like a group's Exclude
              (round 13, owner). */}
          {excluded && controls !== null && !publicView && (
            <EdgeAction
              label="Include again"
              include
              disabled={controls.walkActive || controls.includePending}
              onClick={() => controls.include(row.id)}
            />
          )}
          {controls !== null && summary !== null ? (
            <ShortlistToggle
              actions={controls}
              optionId={row.id}
              shortlistState={summary.shortlist?.state}
              excluded={excluded}
            />
          ) : (
            row.shortlisted && <ShortlistedWord className={cn(lands("short") && "anim-swap-in")} />
          )}
        </div>
      </div>
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
type Section = { key: string; title: string | null; description: string; rows: BuildingRow[]; named?: true };

/** The excluded rows, those set aside with a whole theme or lever grouped
 *  by the reason the group's Exclude recorded ("with the theme <name>"),
 *  and the rest excluded one by one (round 13, owner). */
function groupExcluded(rows: readonly BuildingRow[]): {
  groups: { key: string; title: string; rows: BuildingRow[] }[];
  single: BuildingRow[];
} {
  const groups = new Map<string, { key: string; title: string; rows: BuildingRow[] }>();
  const single: BuildingRow[] = [];
  for (const row of rows) {
    const exclusion = row.summary?.exclusion;
    const match = exclusion?.by === "user" ? /^with the (theme|lever) ([^:]+)/.exec((exclusion.reason ?? "").trim()) : null;
    if (match === null) {
      single.push(row);
      continue;
    }
    const key = `${match[1]}:${match[2].trim()}`;
    const group = groups.get(key) ?? { key, title: match[2].trim(), rows: [] };
    group.rows.push(row);
    groups.set(key, group);
  }
  return { groups: [...groups.values()], single };
}

/** A group heading's own action (round 13, owner): Exclude every included
 *  option in it (with the reason step), or Include again those set aside. */
type GroupAction = { label: string; include: boolean; tooltip?: string; disabled: boolean; run: (reason: string) => void };

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
  const stream = useRunStream(taskId);
  const addOption = useAddOption(taskId);
  const wide = useWideScreen();
  // A Result-tab switch opens the page at its top, focus on the title (round 13, owner).
  const titleRef = useRef<HTMLHeadingElement>(null);
  useOpenAtTop(titleRef, "longlist");
  // The public link reads the list; it adds nothing (round 12).
  const publicView = usePublicView();

  const [chosenMode, setMode] = useState<Mode>("list");
  const [gridLine, setGridLine] = useState<GridLine>("ambition");
  const [chosenGroupBy, setGroupBy] = useState<GroupBy>("theme");
  const [showExcludedInGrid, setShowExcludedInGrid] = useState(false);
  // "Show all" / "Hide all" (the report's words, round 10): the sections
  // remount open or shut on a press. The finished list opens with its
  // groups shut, each heading with its count (round 12, owner, D1: "the
  // groups should be collapsed by default"); while the walk builds it the
  // groups stay open, since rows moving into their themes are the news, and
  // the walk's end leaves them as the reader has them.
  const [allOpen, setAllOpen] = useState({ open: building, revision: 0 });
  // Each group's open state as it reports it, until the next Show all.
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({});
  const reportOpen = useCallback(
    (key: string) => (open: boolean) => setGroupOpen((current) => (current[key] === open ? current : { ...current, [key]: open })),
    [],
  );
  const [addText, setAddText] = useState("");
  // The grid is not offered on a phone, nor while the list is being built.
  const mode: Mode = building || !wide ? "list" : chosenMode;
  const wantedGroupBy: GroupBy = building ? "theme" : chosenGroupBy;

  const longlist = finished ?? longlistRead.data ?? null;
  const optionRows = options.data?.options;
  // The names the walk's clustering steps publish before they commit
  // (round 11); a finished list reads only its reads.
  const published = liveNamesOf(stream);
  const live = useMemo(
    () => (building ? { options: published.options, themes: published.themes } : NO_LIVE_NAMES),
    [building, published.options, published.themes],
  );
  // Once the list is finished the longlist read is the authority: a row the
  // options read has but the longlist does not (and that was not folded
  // into another) is not on the list.
  const computed = useMemo(() => {
    const layout = buildingLayout(optionRows ?? [], longlist, live);
    if (building) return layout;
    const listed = (rows: BuildingRow[]) => rows.filter((row) => row.summary !== null);
    return {
      groups: layout.groups.map((group) => ({ ...group, rows: listed(group.rows) })).filter((group) => group.rows.length > 0),
      excluded: listed(layout.excluded),
    };
  }, [optionRows, longlist, building, live]);
  // Only a regroup moves the rows (round 13, owner): the build's theme wave,
  // a new grouping, a whole theme or lever excluded or included again. A
  // shortlist toggle or one option excluded or included again updates in
  // place.
  const regroupSignature = building
    ? layoutSignature(computed)
    : `${wantedGroupBy}#${groupExcluded(computed.excluded)
        .groups.map((group) => group.key)
        .join("|")}`;
  const regrouped = useMemo(() => ({ computed, groupBy: wantedGroupBy }), [computed, wantedGroupBy]);
  const { computed: layout, groupBy } = useRegroupTransition(regrouped, regroupSignature);
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

  // By lever type (the finished list only): the taxonomy's own one-line
  // definition under each heading; the meta adds how many themes it spans.
  const includedRows = layout.groups.flatMap((group) => group.rows);
  const leverDefinitions = new Map(
    (longlist?.lever_type_definitions ?? []).map((lever) => [lever.key, definitionSentence(lever.definition)]),
  );
  const byName = (a: BuildingRow, b: BuildingRow) => a.name.localeCompare(b.name);
  const byLever: Section[] = [
    ...leverTypes.map((lever) => {
      const rows = shortlistedFirst(
        includedRows.filter((row) => row.summary?.primary_lever_type === lever).sort(byName),
        (row) => row.shortlisted,
      );
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
      title: OTHER_LEVER,
      description: "Options that no lever type on the list names; each says what it does instead.",
      rows: shortlistedFirst(
        includedRows.filter((row) => row.summary?.primary_lever_type == null).sort(byName),
        (row) => row.shortlisted,
      ),
    },
  ];
  // A theme the theming step has named shows its heading before any option
  // is in it (round 11).
  const sections = (groupBy === "theme" ? layout.groups : byLever)
    .filter((group) => group.rows.length > 0 || group.named === true)
    .map((group, index) => ({ ...group, id: group.title === null ? "options" : sectionAnchor(group.title, index) }));
  const titled = sections.some((section) => section.title !== null);
  const excludedRows = layout.excluded;
  // The lever types no included option uses, said plainly (round 13, owner).
  const uncovered = longlist === null || building ? [] : uncoveredLevers(leverTypes, longlist.options ?? []).map(capitalise);
  // In the lever grouping, the last heading names them (round 13, owner).
  const uncoveredGroup =
    uncovered.length === 0 ? null : (
      // The grid's foot, the same component (round 13, owner).
      <NoOptionsFoot names={uncovered} className="mb-8" />
    );

  // Whole groups (round 13, owner): a theme or lever heading excludes every
  // included option in it, or includes again a group all set aside. Not on
  // the public link, nor while the list is built.
  const groupKind: "theme" | "lever" = groupBy === "theme" ? "theme" : "lever";
  const groupActionsOn = controls !== null && !publicView;
  const excludeAction = (section: Section): GroupAction | undefined => {
    if (!groupActionsOn || section.title === null || section.rows.length === 0) return undefined;
    const ids = section.rows.filter((row) => row.summary !== null && row.summary.state !== "excluded").map((row) => row.id);
    if (ids.length === 0) return undefined;
    const name = section.title;
    return {
      label: EXCLUDE_GROUP_FROM_SHORTLISTING[groupKind],
      include: false,
      tooltip: EXCLUDE_TOOLTIP,
      disabled: actions.walkActive || actions.excludePending,
      run: (words) => actions.excludeGroup(ids, groupExclusionReason(groupKind, name, words)),
    };
  };
  // Excluded with a whole theme or lever (round 13, owner): grouped under
  // Excluded by the reason the group's Exclude recorded, before the options
  // excluded one by one.
  const excludedGroups = groupExcluded(excludedRows);
  // An excluded group keeps its one-line description (round 13, owner).
  const excludedGroupDescription = (key: string, title: string): string => {
    if (key.startsWith("theme:")) {
      const theme = (longlist?.themes ?? []).find((entry) => entry.name.trim() === title);
      return theme === undefined ? "" : themeSummary(theme.description ?? "");
    }
    const lever = leverTypes.find((entry) => capitalise(entry) === title);
    return lever === undefined ? "" : (leverDefinitions.get(lever) ?? "");
  };

  // A new grouping, or Show all / Hide all, remounts the sections.
  const sectionKey = (key: string) => `${groupBy}-${allOpen.revision}-${key}`;
  // One row for both states (round 13, owner): an excluded row's grey line
  // is the included row's, the grouping saying what it says for both.
  const rowTheme = (row: BuildingRow) => (groupBy === "theme" ? null : (themeOfOption.get(row.id) ?? null));

  const renderRow = (row: BuildingRow, flat: boolean, inExcludedGroup = false) => (
    <OptionRow
      inExcludedGroup={inExcludedGroup}
      key={row.key}
      taskId={taskId}
      row={row}
      theme={rowTheme(row)}
      showLever={groupBy !== "lever"}
      controls={controls}
      rises={flat && arrives(`row:${row.key}`)}
      lands={(part) => arrives(`${part}:${row.key}`)}
    />
  );

  const question = scrub(longlistTitle(plan.data?.scoping, task.data?.name));
  const counts = longlist === null ? null : countsParts(longlist.counts, leverCount(longlist.options));
  // The shortlist the reader is assembling, said in the count line (round
  // 11, review finding 2).
  const shortlisted = includedRows.filter((row) => row.shortlisted).length;
  // "Hide all" once every group is open, however it was opened (round 13).
  const everyOpen =
    sections.some((section) => section.title !== null) &&
    sections.every((section) => section.title === null || (groupOpen[section.key] ?? allOpen.open));
  const showAll = (
    <button
      type="button"
      aria-expanded={everyOpen}
      onClick={() => {
        const next = !everyOpen;
        setGroupOpen({});
        setAllOpen(({ revision }) => ({ open: next, revision: revision + 1 }));
      }}
      className="group print-hide inline-flex shrink-0 cursor-pointer items-center gap-1 text-meta font-semibold text-grey"
    >
      <ChevronIcon
        size={12}
        className={cn("shrink-0 transition-transform duration-200 ease-[var(--ease-out-strong)]", everyOpen && "rotate-90")}
      />
      <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
        {everyOpen ? "Hide all" : "Show all"}
      </span>
    </button>
  );

  return (
    // No contents sidebar (round 12, owner): the list and the grid take the
    // page's full content column, not the report's reading measure; a link
    // to a group still opens it (`useOpenWhenNavigated`).
    <ReportPage className="longlist-paper md:max-w-[1180px]">
      {/* The first screen is the title, the question, one count line and the
          options (round 11, review finding 1). */}
      <header className="mb-4">
        <h1 ref={titleRef} tabIndex={-1} className={cn(REPORT_TITLE_CLASS, "outline-none")}>
          Longlist
        </h1>
        {question !== "Longlist" && (
          <p className="mt-2 max-w-prose-measure text-lead text-grey max-md:text-body">{question}</p>
        )}
      </header>

      {/* One row of view controls (round 11, review finding 10): Group by on
          the left; the list or grid switch on the right; a Line
          hairline above and below it, 12 px inside each (round 12, owner). */}
      {/* Between two Line hairlines (round 12, owner): the controls row,
          then the count line with Show all at its right edge on the
          headings' Show / Hide edge (round 13, owner; no Show all in the
          grid). */}
      {(!building || counts !== null || (mode === "list" && titled)) && (
        <div data-testid="longlist-controls-block" className="mb-6 space-y-3 border-y border-line py-3">
          {!building && (
            <div
              data-testid="longlist-controls"
              className="print-hide flex min-h-10 flex-wrap items-center justify-between gap-x-6 gap-y-2"
            >
              {/* Round 13 (owner): Group by (list) or Columns (grid) on the
                  left, Show all with Group by; View as and the List / Grid switch
                  on the right edge in both views, so it never moves. */}
              {mode === "list" ? (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <span className="text-meta font-semibold text-grey">Group by</span>
                  <OutlineSwitch label="Group by" choices={GROUP_BY} value={groupBy} onChange={setGroupBy} />
                  {/* What a theme and a lever are (round 12, owner); no intro
                      sentence on the page. */}
                  <span className="-ml-2">
                    <InfoHint label={GROUP_BY_INFO_LABEL} note={GROUP_BY_INFO} />
                  </span>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                  <span className="-mr-2 text-meta font-semibold text-grey">Columns</span>
                  <Select
                    label="Columns"
                    value={gridLine}
                    options={GRID_COLUMN_LINES.map((key) => ({ value: key, label: LINE_NAMES[key] }))}
                    onChange={setGridLine}
                    className="w-56"
                  />
                  {longlist !== null && longlist.counts.excluded > 0 && (
                    <button
                      type="button"
                      aria-pressed={showExcludedInGrid}
                      onClick={() => setShowExcludedInGrid((value) => !value)}
                      className={cn(QUIET_CONTROL_CLASS, "text-meta")}
                    >
                      {showExcludedInGrid ? "Hide excluded" : "Show excluded"}
                    </button>
                  )}
                </div>
              )}
              {wide && (
                <div className="ml-auto flex items-center gap-3">
                  {/* Its label before it (round 13, owner). */}
                  <span className="text-meta text-grey">View as</span>
                  <OutlineSwitch label="View as" choices={MODES} value={mode} onChange={setMode} />
                </div>
              )}
            </div>
          )}
          {(counts !== null || (mode === "list" && titled)) && (
    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              {counts !== null ? (
                <p className="min-w-0 text-meta text-grey">
                  {counts.head}
                  {shortlisted > 0 && ` · ${shortlisted} shortlisted`}
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
              ) : (
                <span />
              )}
              {mode === "list" && titled && showAll}
            </div>
          )}
        </div>
      )}

      {mode === "grid" && longlist !== null ? (
        <>
          <LonglistGrid taskId={taskId} longlist={longlist} showExcluded={showExcludedInGrid} line={gridLine} />
        </>
      ) : (
        sections.map((section, index) =>
          section.title === null ? (
            <ul key={section.key} role="list" aria-label="Options" className="mb-8 space-y-4">
              {section.rows.map((row) => renderRow(row, true))}
            </ul>
          ) : (
            <GroupSection
              key={sectionKey(section.key)}
              id={section.id}
              title={section.title}
              count={
                section.rows.length === 0
                  ? ""
                  : groupCountWords(section.rows.length, section.rows.filter((row) => row.shortlisted).length)
              }
              description={section.description}
              defaultOpen={allOpen.open}
              onOpenChange={reportOpen(section.key)}
              action={excludeAction(section)}
              className={cn(
                arrives(`theme:${section.key}`) && "anim-rise",
                arrives(`theme:${section.key}`) && RISE_DELAY_CLASSES[Math.min(index, RISE_DELAY_CLASSES.length - 1)],
              )}
            >
              {/* A theme just named holds no option yet: its heading and
                  words only, until the first moves under it. */}
              {section.rows.length > 0 && (
                <ul role="list" className="mt-4 space-y-4">
                  {section.rows.map((row) => renderRow(row, false))}
                </ul>
              )}
            </GroupSection>
          ),
        )
      )}
      {/* The lever types no option uses, the last lever heading (round 13). */}
      {mode === "list" && groupBy === "lever" && uncoveredGroup}
      {/* Excluded is a section, not a group (round 13, owner): its heading
          at the page's section size with the description under it, below a
          Line hairline across the list 32 px either side; inside it only
          groups, shut by default: each theme or lever excluded whole, then
          the options excluded one by one under "Options". Show all opens the
          themes, not these. */}
      {mode === "list" && excludedRows.length > 0 && (
        <section
          id={EXCLUDED_ANCHOR}
          aria-labelledby={`${EXCLUDED_ANCHOR}-heading`}
          className={cn("mt-8 border-t border-line pt-8", arrives("excluded") && "anim-rise")}
        >
          <h2 id={`${EXCLUDED_ANCHOR}-heading`} className={REPORT_SECTION_HEADING_CLASS}>
            Excluded
          </h2>
          <p className="mt-1 max-w-prose-measure text-body text-grey">{EXCLUDED_SUMMARY}</p>
          {excludedGroups.groups.map((group) => (
            <GroupSection
              key={`${groupBy}-${group.key}`}
              id={`excluded-${group.key.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}
              title={group.title}
              count={countOf(group.rows.length, "option", "options")}
              description={excludedGroupDescription(group.key, group.title)}
              defaultOpen={false}
              level={3}
              muted
              className="mt-6 mb-0"
              action={
                groupActionsOn
                  ? {
                      label: INCLUDE_GROUP_AGAIN[group.key.startsWith("lever:") ? "lever" : "theme"],
                      include: true,
                      disabled: actions.walkActive || actions.includePending,
                      run: () => actions.includeGroup(group.rows.map((row) => row.id)),
                    }
                  : undefined
              }
            >
              <ul role="list" className="mt-4 space-y-4">
                {group.rows.map((row) => renderRow(row, false, true))}
              </ul>
            </GroupSection>
          ))}
          {excludedGroups.single.length > 0 && (
            <GroupSection
              key={`${groupBy}-excluded-options`}
              id={`${EXCLUDED_ANCHOR}-one-by-one`}
              title="Options"
              count={countOf(excludedGroups.single.length, "option", "options")}
              description=""
              defaultOpen={false}
              level={3}
              muted
              className="mt-6 mb-0"
            >
              <ul role="list" className="mt-4 space-y-4">
                {excludedGroups.single.map((row) => renderRow(row, false))}
              </ul>
            </GroupSection>
          )}
        </section>
      )}
      {/* How the list was read, at its foot rather than over it (round 11,
          review finding 22). */}

      {!building && !publicView && (
        <form id={ADD_OPTION_ANCHOR} onSubmit={handleAddOption} className="print-hide mt-8 border-t border-line pt-6">
          <label htmlFor="longlist-add-option" className={`block ${REPORT_SECTION_HEADING_CLASS}`}>
            Add an option
          </label>
          {/* The field takes the row up to the prose measure, Add after it
              (round 13, owner). */}
          <div className="mt-3 flex max-w-prose-measure items-center gap-2">
            <input
              id="longlist-add-option"
              value={addText}
              onChange={(event) => setAddText(event.target.value)}
              placeholder="An option of your own, in a few words"
              disabled={walkActive}
              className={cn(REASON_INPUT_CLASS, "disabled:bg-paper-2 disabled:text-grey")}
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
