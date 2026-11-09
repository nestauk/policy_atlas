import { useMemo, useState, type CSSProperties } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { cn } from "../../ui/brand/cn";
import { scrub } from "../../lib/scrub";
import { useTask } from "../../api/queries";
import { SECTION_EXPAND_LINK_CLASS } from "../ArtefactOutline";
import { isRunActive } from "../scopingActivity";
import { Select } from "../../ui/brand/Select";
import { ShortlistToggle, useOptionActions, WithTooltip } from "./optionActions";
import { ExcludeIcon } from "../../ui/brand/icons";
import {
  GRID_COLUMN_LINES,
  LEVEL_WORDS,
  LINE_NAMES,
  MIDDLE_WORD,
  NO_IN_SCOPE_WORDS,
  capitalise,
  holdsPlace,
  NO_OPTIONS_FOR,
  OTHER_LEVER,
  shortlistedFirst,
  exclusionLine,
  uncoveredLevers,
} from "./longlistPresentation";
import { useRegroupTransition } from "./regroupTransition";
import { GroupHeading } from "./GroupHeading";
import { LABEL_CLASS } from "../../ui/brand/label";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

type GridLine = (typeof GRID_COLUMN_LINES)[number];

const NONE_FITS_KEY = "__none_fits__";
/** The tile's corner glyph: the shortlist check, or an excluded tile's mark. */
const GRID_TOGGLE_GLYPH = 24;
const UNTAGGED_KEY = "__untagged__";
const MIDDLE_KEY = "__middle__";

/** A column head's cell; the words take the list's group heading
 *  (`GroupHeading`, round 13, owner). */
const HEADER_CELL_CLASS = "border-b border-navy px-3 py-2 align-bottom font-normal";

/** A cell shows this many options before folding the rest behind "+N more". */
const CELL_LIMIT = 4;

/**
 * The reduced grid (D12, contract deliverable 9): rows the lever types in
 * taxonomy order plus "Other", columns the chosen line's `less` word,
 * "Middle", `more` word and "Untagged" (R41) — tiles that open the option and carry its excluded/
 * no-in-scope-evidence states in words. The lever types with no option are
 * one Grey line under the table, "No options: Subsidise, Tax or charge and
 * Inform" (round 10, finding 13: the owner's 2026-09-23 "the absence is the
 * message" in one line, not ten empty bands). The shortlist toggle rides
 * each tile on the name's line (task 055; round 10, finding 6). Offered from
 * `md` up only: the list view hides the switch on a phone.
 */
export type { GridLine };
export function LonglistGrid({
  taskId,
  longlist,
  showExcluded,
  line: controlledLine,
}: {
  taskId: string;
  longlist: LonglistOut;
  /** Excluded options stay out of the grid unless the reader asks. */
  showExcluded: boolean;
  /** The chosen line, when the page's controls row holds the Columns
   *  choice (round 13, owner); the grid then draws neither that choice nor
   *  the line of levers with no option, which the page shows instead. */
  line?: GridLine;
}) {
  const task = useTask(taskId);
  const actions = useOptionActions(taskId, isRunActive(task.data));
  const listed = useMemo(
    () => (longlist.options ?? []).filter((option) => showExcluded || option.state !== "excluded"),
    [longlist.options, showExcluded],
  );
  const [ownLine, setLine] = useState<GridLine>("ambition");
  const wantedLine = controlledLine ?? ownLine;
  // Only a new Columns line moves the tiles (round 13, owner): a shortlist
  // toggle, Show excluded or Include again updates in place.
  const regrouped = useMemo(() => ({ listed, line: wantedLine }), [listed, wantedLine]);
  const { listed: options, line } = useRegroupTransition(regrouped, wantedLine);
  const [openCells, setOpenCells] = useState<Set<string>>(new Set());
  const toggleCell = (key: string) =>
    setOpenCells((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const pageOwnsControls = controlledLine !== undefined;
  const leverTypes = longlist.lever_types ?? [];

  const hasNoneFits = options.some(
    (option) => option.primary_lever_type == null,
  );
  const hasUntagged = options.some((option) => option.profile == null);

  const leverHas = (leverKey: string) =>
    options.some((option) =>
      leverKey === NONE_FITS_KEY ? option.primary_lever_type == null : option.primary_lever_type === leverKey,
    );
  const rows = [...leverTypes, ...(hasNoneFits ? [NONE_FITS_KEY] : [])].filter(leverHas);
  // The lever types no option in the grid uses, listed under it (round
  // 13, owner); never "Other".
  const emptyLevers = uncoveredLevers(leverTypes, longlist.options ?? []).map(capitalise);
  const columns: { key: string; label: string }[] = [
    { key: "less", label: LEVEL_WORDS[line].less ?? "" },
    { key: MIDDLE_KEY, label: MIDDLE_WORD },
    { key: "more", label: LEVEL_WORDS[line].more ?? "" },
    ...(hasUntagged ? [{ key: UNTAGGED_KEY, label: "Untagged" }] : []),
  ];

  /** The column an option sits in on the chosen line: no profile is
   *  Untagged whatever its ambition; a profile without a mark is Middle. */
  const columnOf = (option: OptionSummaryOut): string => {
    if (option.profile == null) return UNTAGGED_KEY;
    const mark =
      line === "ambition"
        ? option.ambition
        : option.profile.lines.find((entry) => entry.key === line)?.mark;
    return mark ?? MIDDLE_KEY;
  };

  const cellOptions = (
    leverKey: string,
    columnKey: string,
  ): OptionSummaryOut[] =>
    // The shortlisted lead each cell (round 12, owner), as on the list.
    shortlistedFirst(
      options.filter((option) => {
        const matchesLever =
          leverKey === NONE_FITS_KEY
            ? option.primary_lever_type == null
            : option.primary_lever_type === leverKey;
        return matchesLever && columnOf(option) === columnKey;
      }),
      holdsPlace,
    );

  return (
    <div>
      {!pageOwnsControls && (
      <div className="print-hide mb-4 flex items-center gap-3">
        <label
          htmlFor="longlist-grid-columns"
          className="text-meta font-semibold text-grey"
        >
          Columns
        </label>
        <Select
          id="longlist-grid-columns"
          label="Columns"
          value={line}
          options={GRID_COLUMN_LINES.map((key) => ({ value: key, label: LINE_NAMES[key] }))}
          onChange={setLine}
          className="w-64"
        />
      </div>
      )}
      <div className="-mx-6 overflow-x-auto px-6">
        <table className="w-full min-w-[640px] table-fixed border-collapse text-left">
          <thead>
            <tr>
              <th scope="col" className={cn(HEADER_CELL_CLASS, "w-44 pl-0")}>
                <GroupHeading title="Lever" count="" />
              </th>
              {columns.map((column) => (
                <th key={column.key} scope="col" className={HEADER_CELL_CLASS}>
                  <GroupHeading title={column.label} count="" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((leverKey) => {
              const rowLabel =
                leverKey === NONE_FITS_KEY ? OTHER_LEVER : capitalise(leverKey);
              return (
                <tr
                  key={leverKey}
                  className="border-b border-line align-top last:border-b-0"
                >
                  <th scope="row" className="py-3 pl-0 pr-3 font-normal">
                    <GroupHeading title={rowLabel} count="" />
                  </th>
                  {columns.map(({ key: columnKey }) => {
                    const cellKey = `${leverKey}|${columnKey}`;
                    const all = cellOptions(leverKey, columnKey);
                    const open = openCells.has(cellKey);
                    const shown = open ? all : all.slice(0, CELL_LIMIT);
                    const hidden = all.length - shown.length;
                    return (
                      <td key={columnKey} className="px-3 py-3 text-body">
                        <ul className="space-y-2">
                          {shown.map((option) => (
                            <li
                              key={option.option_id}
                              // Named for the move when a toggle reorders the cell (`longlist.css`).
                              className="longlist-row relative pr-7 leading-snug"
                              style={{ "--longlist-row": `opt-${option.option_id}` } as CSSProperties}
                            >
                              <Link
                                to={`/tasks/${taskId}/options/${option.option_id}`}
                                className={cn(
                                  "font-semibold text-navy underline-offset-4 hover:underline",
                                  option.state === "excluded" && "text-grey",
                                )}
                              >
                                {scrub(option.name)}
                              </Link>
                              {option.state !== "excluded" && option.no_in_scope_evidence && (
                                <span className="mt-0.5 block text-meta text-grey">{NO_IN_SCOPE_WORDS}</span>
                              )}
                              {/* The check in the tile's top-right corner, its
                                  target over the padding (round 13, owner); an
                                  excluded tile shows the exclude glyph there in
                                  Grey, its exclusion line as the tooltip, no
                                  words on the tile (round 13, owner). */}
                              {option.state === "excluded" ? (
                                <ExcludedMark line={option.exclusion == null ? "" : scrub(exclusionLine(option.exclusion))} />
                              ) : (
                                <ShortlistToggle
                                  actions={actions}
                                  optionId={option.option_id}
                                  shortlistState={option.shortlist?.state}
                                  excluded={false}
                                  glyphSize={GRID_TOGGLE_GLYPH}
                                  className="absolute -top-2 -right-2"
                                />
                              )}
                              {actions.notice !== null &&
                                actions.notice.optionId === option.option_id && (
                                  <p role="alert" className="mt-1 text-meta text-red">
                                    {actions.notice.text}
                                  </p>
                                )}
                            </li>
                          ))}
                        </ul>
                        {all.length > CELL_LIMIT && (
                          <button
                            type="button"
                            aria-expanded={open}
                            onClick={() => toggleCell(cellKey)}
                            className={`${SECTION_EXPAND_LINK_CLASS} mt-2 block cursor-pointer hover:underline`}
                          >
                            {open ? "Show fewer −" : `+${hidden} more`}
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* The lever types no option uses, directly under the grid in the row
          heads' column only, each a head with nothing under it (round 13,
          owner); never "Other". */}
      {emptyLevers.length > 0 && (
        <NoOptionsFoot names={emptyLevers} />
      )}
    </div>
  );
}

/** An excluded tile's mark in the toggle's corner: the exclude glyph in
 *  Grey, not a control, its exclusion line as the tooltip (round 13, owner). */
function ExcludedMark({ line }: { line: string }) {
  return (
    <WithTooltip note={line || undefined}>
      <span
        role="img"
        tabIndex={0}
        aria-label={line || "Excluded"}
        data-testid="tile-excluded"
        className="absolute -top-2 -right-2 inline-flex h-10 w-10 items-center justify-center text-grey"
      >
        <ExcludeIcon size={GRID_TOGGLE_GLYPH} />
      </span>
    </WithTooltip>
  );
}

/**
 * "No options found for" and the lever types no option carries, one per
 * line in the row heads' style, 8 px apart, under a full-width hairline:
 * the grid's foot and the list's lever view alike (round 13/14, owner). The words a Body Grey sentence-case
 * line, so they never read as one more lever.
 */
export function NoOptionsFoot({ names, className }: { names: readonly string[]; className?: string }) {
  // A Line hairline across the full width above it, the rows' own rule,
  // then the foot 24 px below it, in both views (round 13/14, owner).
  return (
    <div data-testid="no-options-foot" className={cn("border-t border-line pt-6", className)}>
      <div aria-label={NO_OPTIONS_FOR} role="group" className="w-44 space-y-2">
        <p data-testid="no-options-for" className="text-body text-grey">
          {NO_OPTIONS_FOR}
        </p>
        {names.map((name) => (
          <p key={name} className={cn(LABEL_CLASS, "text-grey")}>
            {name}
          </p>
        ))}
      </div>
    </div>
  );
}
