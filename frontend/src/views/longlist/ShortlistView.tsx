import type { ReactNode } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { usePatchPlan, useSuggestMore } from "../../api/mutations";
import { usePlan, useRuns, useTask } from "../../api/queries";
import { actionFailedNotice } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { isRunActive } from "../scopingActivity";
import { SCOPING_RUNS_PAGE_SIZE } from "../workspace/planStart";
import { RISK_APPETITE_LABELS, type RiskAppetite } from "../workspace/planVocabulary";
import {
  constraintLabel,
  holdsPlace,
  leverLabel,
  LEVEL_WORDS,
  maturityLine,
} from "./longlistPresentation";
import { ShortlistActionButton, useOptionActions } from "./optionActions";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

const SELECT_CLASS =
  "border border-line-2 bg-paper px-2 py-1 text-body text-ink focus-visible:outline-2 focus-visible:outline-blue disabled:bg-paper-2 disabled:text-grey";

/** The risk appetite as a `<select>` over the three approved answers. It
 *  patches the plan directly (no chat seeding); the server re-proposes when
 *  a longlist exists. Shared by the shortlist header and the plan document. */
export function RiskAppetiteSelect({
  value,
  disabled,
  onChange,
  id,
}: {
  value: RiskAppetite;
  disabled: boolean;
  onChange: (value: RiskAppetite) => void;
  id?: string;
}) {
  return (
    <select
      id={id}
      aria-label="Risk appetite"
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value as RiskAppetite)}
      className={SELECT_CLASS}
    >
      {(Object.keys(RISK_APPETITE_LABELS) as RiskAppetite[]).map((key) => (
        <option key={key} value={key}>
          {RISK_APPETITE_LABELS[key]}
        </option>
      ))}
    </select>
  );
}

/** One group of the "Other options" list, as the list mode builds it. */
export type OptionGroup = { key: string; name: string; options: OptionSummaryOut[] };

function byName(a: OptionSummaryOut, b: OptionSummaryOut): number {
  return a.name.localeCompare(b.name);
}

/** The shortlist's rows read provenance defensively: it is an open object. */
function numberOf(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * The shortlist view (task 055, item 8; plan P15): the header with the risk
 * appetite, the fixed baseline line, the places in two alphabetical groups,
 * Suggest more, the not-covered note, the disabled Assess button and the
 * included options holding no place. Structure only; the lead polishes the
 * layout.
 */
export function ShortlistView({
  taskId,
  longlist,
  otherGroups,
  renderOtherRow,
}: {
  taskId: string;
  longlist: LonglistOut;
  /** The included options holding no place, grouped as List mode groups them. */
  otherGroups: OptionGroup[];
  /** A List-mode row (grey line included) for one of those options. */
  renderOtherRow: (option: OptionSummaryOut) => ReactNode;
}) {
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const patchPlan = usePatchPlan(taskId);
  const suggest = useSuggestMore(taskId);
  const walkActive = isRunActive(task.data);
  const actions = useOptionActions(taskId, walkActive);

  const options = longlist.options ?? [];
  const placed = options.filter(holdsPlace);
  const addedByYou = placed.filter((option) => option.shortlist?.state === "added_by_you").sort(byName);
  const picks = placed.filter((option) => option.shortlist?.state === "proposed").sort(byName);
  const hasOpenOption = options.some((option) => option.state === "included" && option.shortlist == null);
  const shortlist = longlist.shortlist;
  const appetite: RiskAppetite = plan.data?.scoping?.risk_appetite ?? "mostly_tried";

  // A shortlist walk that could not propose (P17): the task's newest
  // parentless walk has the purpose "shortlist" and ended degraded or
  // failed. Any other walk ending that way shows nothing here.
  const runs = useRuns(taskId, { page_size: SCOPING_RUNS_PAGE_SIZE, parentless: true });
  const newest = runs.data?.data?.[0] ?? null;
  const proposalFailed =
    newest !== null && newest.purpose === "shortlist" && (newest.status === "degraded" || newest.status === "failed");

  const provenance = shortlist.provenance ?? {};
  const linesCut = numberOf(provenance.document_lines_cut);
  const linesTotal = numberOf(provenance.document_lines_total);
  const baselineCut = numberOf(provenance.baseline_chars_cut);
  const footerLines: string[] = [];
  if (linesCut !== null && linesCut > 0 && linesTotal !== null) {
    footerLines.push(`Policy Atlas read ${linesTotal - linesCut} of ${linesTotal} document lines`);
  }
  if (baselineCut !== null && baselineCut > 0) footerLines.push("The baseline was cut");

  const suggestTitle = walkActive ? "A walk is running" : !hasOpenOption ? "Nothing left to propose" : undefined;

  const renderPlaceRow = (option: OptionSummaryOut) => {
    const state = option.shortlist?.state;
    const breach = option.state === "excluded" && option.exclusion != null && option.exclusion.by !== "user";
    const mark = option.ambition == null ? null : LEVEL_WORDS.ambition[option.ambition];
    const maturity = maturityLine(option.maturity);
    const reason = state === "added_by_you" ? "Added by you" : (option.shortlist?.reason ?? "");
    return (
      <li key={option.option_id} className="py-4">
        <div className="flex items-start justify-between gap-4">
          <Link
            to={`/tasks/${taskId}/options/${option.option_id}`}
            className="min-w-0 text-body font-bold text-navy underline-offset-4 hover:underline"
          >
            {scrub(option.name)}
          </Link>
          <ShortlistActionButton
            actions={actions}
            optionId={option.option_id}
            shortlistState={state}
            excluded={option.state === "excluded"}
            className="-my-2 flex-none"
          />
        </div>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-grey">
          <span className="font-semibold text-navy">{scrub(leverLabel(option))}</span>
          {mark !== null && (
            <>
              <span aria-hidden="true">·</span>
              <span>{mark}</span>
            </>
          )}
          {maturity !== null && (
            <>
              <span aria-hidden="true">·</span>
              <span>{maturity}</span>
            </>
          )}
        </p>
        {reason !== "" && <p className="mt-1 max-w-[44em] text-body text-ink">{scrub(reason)}</p>}
        {breach && option.exclusion != null && (
          <p className="mt-1.5 text-body text-ink">
            <Chip tone="red" className="mr-2 align-middle">excluded</Chip>
            Breaks "{constraintLabel(scrub(option.exclusion.constraint))}". {scrub(option.exclusion.reason)}
          </p>
        )}
        {actions.notice !== null && actions.notice.optionId === option.option_id && (
          <p role="alert" className="mt-2 text-body text-red">
            {actions.notice.text}
          </p>
        )}
      </li>
    );
  };

  const groupedPlaces = [
    { key: "added", title: "Added by you", rows: addedByYou },
    { key: "picks", title: "Policy Atlas's picks", rows: picks },
  ].filter((group) => group.rows.length > 0);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-body text-grey">
        <span className="font-semibold text-navy">{placed.length} places</span>
        <span aria-hidden="true">·</span>
        <label className="flex items-center gap-2">
          <span>Appetite: {RISK_APPETITE_LABELS[appetite]}</span>
          <RiskAppetiteSelect
            value={appetite}
            disabled={walkActive || patchPlan.isPending}
            onChange={(value) => patchPlan.mutate({ scoping: { risk_appetite: value } })}
          />
        </label>
        {walkActive && <span role="status">Shortlisting…</span>}
      </div>
      {patchPlan.isError && (
        <p role="alert" className="mb-3 text-body text-red">
          {actionFailedNotice(patchPlan.error, "The appetite couldn't be changed. Try again.")}
        </p>
      )}

      <p className="mb-6 text-body text-ink">
        The situation today:{" "}
        <Link to={`/tasks/${taskId}/result?view=baseline`} className="font-semibold text-blue underline underline-offset-4">
          Baseline
        </Link>
      </p>

      {proposalFailed && (
        <p role="alert" className="mb-4 text-body text-red">
          Policy Atlas could not propose; your places are unchanged.
        </p>
      )}

      {placed.length === 0 && walkActive ? (
        <p role="status" className="py-4 text-body text-grey">
          Policy Atlas is proposing a shortlist…
        </p>
      ) : (
        groupedPlaces.map((group) => (
          <section key={group.key} className="mb-6">
            <h2 className={REPORT_SECTION_HEADING_CLASS}>{group.title}</h2>
            <ul role="list" className="divide-y divide-line border-t border-line">
              {group.rows.map(renderPlaceRow)}
            </ul>
          </section>
        ))
      )}

      <div className="print-hide mb-4 flex flex-wrap items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={walkActive || !hasOpenOption || suggest.isPending}
          title={suggestTitle}
          onClick={() => suggest.mutate()}
        >
          Suggest more
        </Button>
        {suggest.isError && (
          <p role="alert" className="text-body text-red">
            {actionFailedNotice(suggest.error, "Policy Atlas couldn't start. Try again.")}
          </p>
        )}
      </div>

      {shortlist.stale && <p className="mb-4 text-body text-grey">Press Suggest more to re-propose</p>}

      {shortlist.note != null && shortlist.note !== "" && (
        <section className="mb-6">
          <h2 className={REPORT_SECTION_HEADING_CLASS}>What this shortlist leaves out</h2>
          <p className="mt-2 max-w-[44em] text-body text-ink">{scrub(shortlist.note)}</p>
          {footerLines.map((line) => (
            <p key={line} className="mt-1 text-meta text-grey">
              {line}
            </p>
          ))}
        </section>
      )}

      <div className="mb-8">
        <Button variant="secondary" disabled>
          Assess these {placed.length}
        </Button>
        <p className="mt-1.5 text-meta text-grey">Assessment is not yet available.</p>
      </div>

      <section>
        <h2 className={REPORT_SECTION_HEADING_CLASS}>Other options</h2>
        {otherGroups.map((group) => (
          <div key={group.key} className="mt-4">
            <h3 className="text-meta font-semibold text-grey">{scrub(group.name)}</h3>
            <ul role="list" className="divide-y divide-line border-t border-line">
              {group.options.map(renderOtherRow)}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}
