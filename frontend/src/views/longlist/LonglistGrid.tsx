import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { cn } from "../../ui/brand/cn";
import { Chip } from "../../ui/brand/Chip";
import { scrub } from "../../lib/scrub";
import { capitalise } from "./longlistPresentation";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

const NONE_FITS_KEY = "__none_fits__";
const UNTAGGED_KEY = "__untagged__";

/**
 * The reduced grid (D12, contract deliverable 9): rows the lever types in
 * taxonomy order plus "None fits", columns the ambition bands plus
 * "Untagged" — tiles that open the option and carry its excluded/
 * no-in-scope-evidence states. No shortlist state, actions, gap messages or
 * footer (task 3 extends it).
 */
export function LonglistGrid({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const options = longlist.options ?? [];
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
    <table className="w-full min-w-[640px] border-collapse text-left">
      <thead>
        <tr>
          <th scope="col" className="border-b border-line px-3 py-2 text-caption font-semibold uppercase tracking-wide text-grey">
            Lever type
          </th>
          {columnLabels.map((label) => (
            <th
              key={label}
              scope="col"
              className="border-b border-line px-3 py-2 text-caption font-semibold uppercase tracking-wide text-grey"
            >
              {scrub(label)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((leverKey) => {
          const rowLabel = leverKey === NONE_FITS_KEY ? "None fits" : capitalise(leverKey);
          const rowOptionCount = columns.reduce(
            (total, ambitionKey) => total + cellOptions(leverKey, ambitionKey).length,
            0,
          );
          return (
            <tr key={leverKey} className="border-b border-line last:border-b-0">
              <th scope="row" className="px-3 py-2.5 align-top text-body font-semibold text-navy">
                {scrub(rowLabel)}
              </th>
              {rowOptionCount === 0 ? (
                <td colSpan={columns.length} className="px-3 py-2.5 align-top text-body italic text-grey">
                  no option of this type on the longlist
                </td>
              ) : (
                columns.map((ambitionKey) => (
                  <td key={ambitionKey} className="px-3 py-2.5 align-top text-body">
                    <ul className="space-y-1.5">
                      {cellOptions(leverKey, ambitionKey).map((option) => (
                        <li key={option.option_id}>
                          <Link
                            to={`/tasks/${taskId}/options/${option.option_id}`}
                            className={cn(
                              "font-semibold text-navy hover:underline",
                              option.state === "excluded" && "text-grey line-through",
                            )}
                          >
                            {scrub(option.name)}
                          </Link>
                          {option.state === "excluded" && (
                            <Chip tone="soft" className="ml-1.5 align-middle">
                              excluded
                            </Chip>
                          )}
                          {option.no_in_scope_evidence && (
                            <Chip tone="soft" className="ml-1.5 align-middle">
                              no in-scope evidence
                            </Chip>
                          )}
                        </li>
                      ))}
                    </ul>
                  </td>
                ))
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
