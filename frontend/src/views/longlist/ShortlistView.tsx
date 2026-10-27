import { Link, useNavigate } from "react-router";

import type { components } from "../../api/gen/types";
import { usePatchPlan, useSuggestMore } from "../../api/mutations";
import { usePlan, useRuns, useTask } from "../../api/queries";
import { actionFailedNotice, suggestConflictSentences } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { REPORT_TITLE_CLASS, ReportKindRow, ReportPage } from "../reportPage";
import { isRunActive } from "../scopingActivity";
import { SCOPING_RUNS_PAGE_SIZE } from "../workspace/planStart";
import { RISK_APPETITE_LABELS, type RiskAppetite } from "../workspace/planVocabulary";
import {
  constraintLabel,
  holdsPlace,
  leverLabel,
  longlistTitle,
  maturityPhrase,
} from "./longlistPresentation";
import { ShortlistActionButton, useOptionActions } from "./optionActions";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

const SELECT_CLASS =
  "max-w-full border border-line-2 bg-paper px-2 py-1 text-meta font-semibold text-navy focus-visible:outline-2 focus-visible:outline-blue disabled:bg-paper-2 disabled:text-grey";

/** The risk appetite as a `<select>` over the three approved answers. It
 *  patches the plan directly (no chat seeding); the server re-proposes when
 *  a longlist exists. Shared by the shortlist page and the plan document. */
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

/** The small label over a line Policy Atlas wrote (its reason, its note). */
const VOICE_LABEL_CLASS = "text-caption font-bold uppercase tracking-[0.06em] text-grey";

function byName(a: OptionSummaryOut, b: OptionSummaryOut): number {
  return a.name.localeCompare(b.name);
}

/** The page reads provenance defensively: it is an open object. */
function numberOf(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * The Shortlist: its own Result view beside Baseline and Longlist (task 055,
 * item 8, as amended by the owner after the build). The question as the
 * title; the places in two groups, each with the option's description and,
 * for a pick, Policy Atlas's reason; the not-covered note at the foot of
 * the picks; the risk appetite beside Suggest more, the two controls that
 * re-propose; a way back to the longlist; the disabled
 * Assess as the page's end. Adding places happens on the longlist, where
 * every row and card carries Add to shortlist.
 */
export function ShortlistView({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const navigate = useNavigate();
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
  // The longlist's setting words were judged against the plan it was built
  // from; after a plan change, name no place until the Rebuild.
  const where = longlist.plan_inputs_changed ? null : (plan.data?.scoping?.where?.text ?? null);

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

  // A stale shortlist re-proposes, so it needs no open option.
  const canSuggest = hasOpenOption || shortlist.stale;
  const suggestTitle = walkActive ? "A walk is running" : !canSuggest ? "Nothing left to propose" : undefined;
  const hasNote = shortlist.note != null && shortlist.note !== "";

  const renderPlaceRow = (option: OptionSummaryOut) => {
    const state = option.shortlist?.state;
    const breach = option.state === "excluded" && option.exclusion != null && option.exclusion.by !== "user";
    const footing = maturityPhrase(option.maturity, where);
    const reason = state === "proposed" ? (option.shortlist?.reason ?? "") : "";
    return (
      <li key={option.option_id} className="py-5">
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <Link
              to={`/tasks/${taskId}/options/${option.option_id}`}
              className="text-lead font-bold text-navy underline-offset-4 hover:underline max-md:text-body"
            >
              {scrub(option.name)}
            </Link>
            {option.description !== "" && (
              <p className="mt-1.5 max-w-[62ch] text-body text-ink">{scrub(option.description)}</p>
            )}
            <p className="mt-1.5 text-meta text-grey">
              {scrub(leverLabel(option))}
              {footing !== null && (
                <>
                  <span aria-hidden="true"> · </span>
                  {footing}
                </>
              )}
            </p>
            {reason !== "" && (
              <div className="mt-3 border-l border-line pl-3">
                <p className={VOICE_LABEL_CLASS}>Policy Atlas's reason</p>
                <p className="mt-1 max-w-[62ch] text-body text-ink">{scrub(reason)}</p>
              </div>
            )}
            {breach && option.exclusion != null && (
              <p className="mt-2 text-body text-ink">
                <Chip tone="red" className="mr-2 align-middle">excluded</Chip>
                Breaks "{constraintLabel(scrub(option.exclusion.constraint))}". {scrub(option.exclusion.reason)}
              </p>
            )}
            {actions.notice !== null && actions.notice.optionId === option.option_id && (
              <p role="alert" className="mt-2 text-body text-red">
                {actions.notice.text}
              </p>
            )}
          </div>
          <ShortlistActionButton
            actions={actions}
            optionId={option.option_id}
            shortlistState={state}
            excluded={option.state === "excluded"}
            className="-my-1 flex-none"
          />
        </div>
      </li>
    );
  };

  const noPlaces = placed.length === 0;

  return (
    <ReportPage>
      <header>
        <ReportKindRow kind="Shortlist">
          {walkActive && (
            <span role="status" className="text-meta text-grey">
              Shortlisting…
            </span>
          )}
        </ReportKindRow>
        <h1 className={REPORT_TITLE_CLASS}>{scrub(longlistTitle(plan.data?.scoping, task.data?.name))}</h1>
      </header>

      {proposalFailed && (
        <p role="alert" className="mt-6 text-body text-red">
          Policy Atlas could not propose. Your places are unchanged.
        </p>
      )}

      {addedByYou.length > 0 && (
        <section className="mt-8">
          <h2 className={REPORT_SECTION_HEADING_CLASS}>Added by you</h2>
          <ul role="list" className="mt-3 divide-y divide-line border-y border-line">
            {addedByYou.map(renderPlaceRow)}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <h2 className={REPORT_SECTION_HEADING_CLASS}>Policy Atlas's picks</h2>
        {picks.length > 0 ? (
          <ul role="list" className="mt-3 divide-y divide-line border-y border-line">
            {picks.map(renderPlaceRow)}
          </ul>
        ) : (
          <p role="status" className="mt-3 border-y border-line py-5 text-body text-grey">
            {walkActive
              ? "Policy Atlas is proposing a shortlist…"
              : noPlaces
                ? "No places yet."
                : "No picks beside your places. Suggest more asks Policy Atlas for some."}
          </p>
        )}
        {hasNote && (
          <div className="mt-4">
            <p className={VOICE_LABEL_CLASS}>What this shortlist leaves out</p>
            <p className="mt-1 max-w-[62ch] text-body text-ink">{scrub(shortlist.note ?? "")}</p>
            {footerLines.map((line) => (
              <p key={line} className="mt-1 text-meta text-grey">
                {line}
              </p>
            ))}
          </div>
        )}
      </section>

      <div className="print-hide mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
        <label className="flex items-center gap-2 text-meta text-grey">
          <span>Risk appetite</span>
          <RiskAppetiteSelect
            value={appetite}
            disabled={walkActive || patchPlan.isPending}
            onChange={(value) => patchPlan.mutate({ scoping: { risk_appetite: value } })}
          />
        </label>
        <Button
          variant="primary"
          size="sm"
          disabled={walkActive || !canSuggest || suggest.isPending}
          title={suggestTitle}
          onClick={() => suggest.mutate()}
        >
          Suggest more
        </Button>
        <Button variant="secondary" size="sm" onClick={() => void navigate(`/tasks/${taskId}/result`)}>
          Add more from the longlist
        </Button>
        {shortlist.stale && !walkActive && (
          <span className="text-meta text-grey">Press Suggest more to re-propose</span>
        )}
      </div>
      {patchPlan.isError && (
        <p role="alert" className="mt-2 text-body text-red">
          {actionFailedNotice(patchPlan.error, "The appetite couldn't be changed. Try again.")}
        </p>
      )}
      {suggest.isError && (
        <p role="alert" className="mt-2 text-body text-red">
          {actionFailedNotice(suggest.error, "Policy Atlas couldn't start. Try again.", suggestConflictSentences)}
        </p>
      )}

      <div className="mt-10 border-t border-line pt-6">
        <Button variant="primary" disabled>
          Assess these {placed.length}
        </Button>
        <p className="mt-2 text-meta text-grey">Assessment is not yet available.</p>
      </div>
    </ReportPage>
  );
}
