import { useState } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { cn } from "../../ui/brand/cn";
import { scrub } from "../../lib/scrub";
import { useTask } from "../../api/queries";
import { SECTION_EXPAND_LINK_CLASS } from "../ArtefactOutline";
import { isRunActive } from "../scopingActivity";
import { FieldSelect } from "./FieldSelect";
import { ShortlistToggle, useOptionActions } from "./optionActions";
import {
  GRID_COLUMN_LINES,
  LEVEL_WORDS,
  LINE_NAMES,
  MIDDLE_WORD,
  NO_IN_SCOPE_WORDS,
  capitalise,
  joinAnd,
} from "./longlistPresentation";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

type GridLine = (typeof GRID_COLUMN_LINES)[number];

const NONE_FITS_KEY = "__none_fits__";
const UNTAGGED_KEY = "__untagged__";
const MIDDLE_KEY = "__middle__";

const HEADER_CELL_CLASS =
  "border-b border-navy px-3 py-2 text-meta font-semibold text-navy";

/** A cell shows this many options before folding the rest behind "+N more". */
const CELL_LIMIT = 4;

/**
 * The reduced grid (D12, contract deliverable 9): rows the lever types in
 * taxonomy order plus "None fits", columns the chosen line's `less` word,
 * "Middle", `more` word and "Untagged" (R41) — tiles that open the option and carry its excluded/
 * no-in-scope-evidence states in words. The lever types with no option are
 * one Grey line under the table, "No options: Subsidise, Tax or charge and
 * Inform" (round 10, finding 13: the owner's 2026-09-23 "the absence is the
 * message" in one line, not ten empty bands). The shortlist toggle rides
 * each tile on the name's line (task 055; round 10, finding 6). Offered from
 * `md` up only: the list view hides the switch on a phone.
 */
export function LonglistGrid({
  taskId,
  longlist,
  showExcluded,
}: {
  taskId: string;
  longlist: LonglistOut;
  /** Excluded options stay out of the grid unless the reader asks. */
  showExcluded: boolean;
}) {
  const task = useTask(taskId);
  const actions = useOptionActions(taskId, isRunActive(task.data));
  const options = (longlist.options ?? []).filter(
    (option) => showExcluded || option.state !== "excluded",
  );
  const [openCells, setOpenCells] = useState<Set<string>>(new Set());
  const toggleCell = (key: string) =>
    setOpenCells((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const [line, setLine] = useState<GridLine>("ambition");
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
  const emptyLevers = leverTypes.filter((lever) => !leverHas(lever)).map(capitalise);
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
    options.filter((option) => {
      const matchesLever =
        leverKey === NONE_FITS_KEY
          ? option.primary_lever_type == null
          : option.primary_lever_type === leverKey;
      return matchesLever && columnOf(option) === columnKey;
    });

  return (
    <div>
      <div className="print-hide mb-4 flex items-center gap-3">
        <label
          htmlFor="longlist-grid-columns"
          className="text-meta font-semibold text-grey"
        >
          Columns
        </label>
        <FieldSelect
          id="longlist-grid-columns"
          value={line}
          onChange={(event) => setLine(event.target.value as GridLine)}
          className="w-64"
        >
          {GRID_COLUMN_LINES.map((key) => (
            <option key={key} value={key}>
              {LINE_NAMES[key]}
            </option>
          ))}
        </FieldSelect>
      </div>
      <div className="-mx-6 overflow-x-auto px-6">
        <table className="w-full min-w-[640px] table-fixed border-collapse text-left">
          <thead>
            <tr>
              <th scope="col" className={cn(HEADER_CELL_CLASS, "w-44 pl-0")}>
                Lever type
              </th>
              {columns.map((column) => (
                <th key={column.key} scope="col" className={HEADER_CELL_CLASS}>
                  {scrub(column.label)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((leverKey) => {
              const rowLabel =
                leverKey === NONE_FITS_KEY ? "None fits" : capitalise(leverKey);
              return (
                <tr
                  key={leverKey}
                  className="border-b border-line align-top last:border-b-0"
                >
                  <th
                    scope="row"
                    className="py-3 pl-0 pr-3 text-meta font-semibold text-navy"
                  >
                    {scrub(rowLabel)}
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
                            <li key={option.option_id} className="leading-snug">
                              <Link
                                to={`/tasks/${taskId}/options/${option.option_id}`}
                                className={cn(
                                  "font-semibold text-navy underline-offset-4 hover:underline",
                                  option.state === "excluded" && "text-grey",
                                )}
                              >
                                {scrub(option.name)}
                              </Link>
                              {(option.state === "excluded" || option.no_in_scope_evidence) && (
                                <span className="mt-0.5 block text-meta">
                                  {option.state === "excluded" ? (
                                    <span className="font-semibold text-red">Excluded</span>
                                  ) : (
                                    <span className="text-grey">{NO_IN_SCOPE_WORDS}</span>
                                  )}
                                </span>
                              )}
                              <ShortlistToggle
                                actions={actions}
                                optionId={option.option_id}
                                shortlistState={option.shortlist?.state}
                                excluded={option.state === "excluded"}
                                align="start"
                                className="mt-0.5 grid w-fit"
                              />
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
      {emptyLevers.length > 0 && (
        <p className="mt-3 text-meta text-grey">No options: {joinAnd(emptyLevers)}</p>
      )}
    </div>
  );
}
