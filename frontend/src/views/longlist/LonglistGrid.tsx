import { useState } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { cn } from "../../ui/brand/cn";
import { Chip } from "../../ui/brand/Chip";
import { scrub } from "../../lib/scrub";
import { SECTION_EXPAND_LINK_CLASS } from "../ArtefactOutline";
import { capitalise } from "./longlistPresentation";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

const NONE_FITS_KEY = "__none_fits__";
const UNTAGGED_KEY = "__untagged__";

const HEADER_CELL_CLASS = "border-b border-navy px-3 py-2 text-meta font-semibold text-navy";

/** A cell shows this many options before folding the rest behind "+N more". */
const CELL_LIMIT = 6;

/**
 * The reduced grid (D12, contract deliverable 9): rows the lever types in
 * taxonomy order plus "None fits", columns the ambition bands plus
 * "Untagged" — tiles that open the option and carry its excluded/
 * no-in-scope-evidence states. An empty row stays empty (owner, 2026-09-23:
 * the absence is the message). No shortlist state, actions, gap messages or
 * footer (task 3 extends it).
 */
export function LonglistGrid({
  taskId,
  longlist,
  showExcluded = false,
}: {
  taskId: string;
  longlist: LonglistOut;
  /** Excluded options stay out of the grid unless the reader asks. */
  showExcluded?: boolean;
}) {
  const options = (longlist.options ?? []).filter((option) => showExcluded || option.state !== "excluded");
  const [openCells, setOpenCells] = useState<Set<string>>(new Set());
  const toggleCell = (key: string) =>
    setOpenCells((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const leverTypes = longlist.lever_types ?? [];
  const ambitionBands = longlist.ambition_bands ?? [];

  const hasNoneFits = options.some((option) => option.primary_lever_type == null);
  const hasUntagged = options.some((option) => option.ambition == null);

  const rows = [...leverTypes, ...(hasNoneFits ? [NONE_FITS_KEY] : [])];
  const columns = [
    ...ambitionBands.map((band) => band.key),
    ...(hasUntagged ? [UNTAGGED_KEY] : []),
  ];
  const columnLabels = [
    ...ambitionBands.map((band) => band.label),
    ...(hasUntagged ? ["Untagged"] : []),
  ];

  const cellOptions = (leverKey: string, ambitionKey: string): OptionSummaryOut[] =>
    options.filter((option) => {
      const matchesLever =
        leverKey === NONE_FITS_KEY ? option.primary_lever_type == null : option.primary_lever_type === leverKey;
      const matchesAmbition =
        ambitionKey === UNTAGGED_KEY ? option.ambition == null : option.ambition === ambitionKey;
      return matchesLever && matchesAmbition;
    });

  return (
    <div className="-mx-6 overflow-x-auto px-6">
      <table className="w-full min-w-[640px] table-fixed border-collapse text-left">
        <thead>
          <tr>
            <th scope="col" className={cn(HEADER_CELL_CLASS, "w-44 pl-0")}>
              Lever type
            </th>
            {columnLabels.map((label) => (
              <th key={label} scope="col" className={HEADER_CELL_CLASS}>
                {scrub(label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((leverKey) => {
            const rowLabel = leverKey === NONE_FITS_KEY ? "None fits" : capitalise(leverKey);
            return (
              <tr key={leverKey} className="border-b border-line align-top last:border-b-0">
                <th scope="row" className="py-3 pl-0 pr-3 text-meta font-semibold text-navy">
                  {scrub(rowLabel)}
                </th>
                {                  columns.map((ambitionKey) => {
                    const cellKey = `${leverKey}|${ambitionKey}`;
                    const all = cellOptions(leverKey, ambitionKey);
                    const open = openCells.has(cellKey);
                    const shown = open || all.length <= CELL_LIMIT ? all : all.slice(0, CELL_LIMIT);
                    const hidden = all.length - shown.length;
                    return (
                      <td key={ambitionKey} className="px-3 py-3 text-body">
                        <ul className="space-y-2">
                          {shown.map((option) => (
                            <li key={option.option_id} className="leading-snug">
                              <Link
                                to={`/tasks/${taskId}/options/${option.option_id}`}
                                className={cn(
                                  "font-semibold text-navy underline-offset-4 hover:underline",
                                  option.state === "excluded" && "text-grey line-through",
                                )}
                              >
                                {scrub(option.name)}
                              </Link>
                              {option.state === "excluded" && (
                                <Chip tone="red" className="ml-1.5 align-middle">
                                  excluded
                                </Chip>
                              )}
                              {option.no_in_scope_evidence && (
                                <Chip tone="yellow" className="ml-1.5 align-middle">
                                  no in-scope evidence
                                </Chip>
                              )}
                            </li>
                          ))}
                        </ul>
                        {(hidden > 0 || (open && all.length > CELL_LIMIT)) && (
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
  );
}
