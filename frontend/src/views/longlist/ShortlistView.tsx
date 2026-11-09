import { useRef, useState } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { usePatchPlan, useSuggestMore } from "../../api/mutations";
import { usePlan, useRuns, useTask } from "../../api/queries";
import { actionFailedNotice, suggestConflictSentences } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import { REPORT_TITLE_CLASS, ReportPage } from "../reportPage";
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
import { Select } from "../../ui/brand/Select";
import { ShortlistToggle, useOptionActions } from "./optionActions";
import { usePublicView } from "../publicView";
import { useOpenAtTop } from "../../lib/openAtTop";
import { CARD_FROM_SHORTLIST } from "./OptionCard";
import { NOTE_REVIEWING_WORDS, useNoteRefresh, useRefreshShortlistNote } from "./shortlistNote";
import { ActionLine } from "../workspace/ActionLine";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];

/** The risk appetite as the app's dropdown over the three approved answers. It
 *  patches the plan directly (no chat seeding); the server re-proposes when
 *  a longlist exists. Shared by the shortlist page (in the field's skin, full
 *  width up to 32rem, the longest answer whole on a desktop, so it fits a phone: round 10, finding 4) and the plan
 *  document (compact, in its panel). */
export function RiskAppetiteSelect({
  value,
  disabled,
  onChange,
  id,
  field = false,
}: {
  value: RiskAppetite;
  disabled: boolean;
  onChange: (value: RiskAppetite) => void;
  id?: string;
  field?: boolean;
}) {
  const options = (Object.keys(RISK_APPETITE_LABELS) as RiskAppetite[]).map((key) => ({
    value: key,
    label: RISK_APPETITE_LABELS[key],
  }));
  // The shortlist page's field is 40 px; the plan document's compact one 32 px (round 12).
  return (
    <Select
      id={id}
      label="Risk appetite"
      value={value}
      options={options}
      disabled={disabled}
      onChange={onChange}
      size={field ? 40 : 32}
      className={field ? "w-full max-w-[32rem]" : undefined}
    />
  );
}

/** A bold lead-in on a line Policy Atlas wrote ("Why:", "Not covered:"),
 *  in place of an uppercase label over it (round 10, C4). */
function LeadIn({ children }: { children: string }) {
  return <strong className="font-bold text-navy">{children}</strong>;
}

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
 * the picks; the risk appetite over Suggest more, the two controls that
 * re-propose, with a way back to the longlist beside it; Assess as the
 * page's one primary at its end, its reason in words under it while it is
 * off (round 10, finding 4). Adding places happens on the longlist, where
 * every row and card carries Add to shortlist.
 */
export function ShortlistView({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const patchPlan = usePatchPlan(taskId);
  const suggest = useSuggestMore(taskId);
  const walkActive = isRunActive(task.data);
  const actions = useOptionActions(taskId, walkActive);
  // A Result-tab switch opens the page at its top, focus on the title (round 13, owner).
  const titleRef = useRef<HTMLHeadingElement>(null);
  useOpenAtTop(titleRef, "shortlist");
  // The public link reads the shortlist; it changes nothing (round 12).
  const publicView = usePublicView();

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

  // A stale shortlist re-proposes, so it needs no open option. Why Suggest
  // more is off is said in words under it, never only in a tooltip.
  const canSuggest = hasOpenOption || shortlist.stale;
  const suggestOff = walkActive ? "A walk is running." : !canSuggest ? "Nothing left to propose." : null;
  const hasNote = shortlist.note != null && shortlist.note !== "";
  // The note kept current (owner, 2026-11-08): rewritten on opening when
  // stale, and once 3 s after the last change on the page if still stale.
  // ponytail: `note_stale` typed here until the generated types carry it.
  const noteStale = (shortlist as typeof shortlist & { note_stale?: boolean }).note_stale === true;
  const noteRefresh = useRefreshShortlistNote(taskId);
  const placesSignature = placed.map((option) => `${option.option_id}:${option.shortlist?.state}`).join(",");
  useNoteRefresh(
    () => {
      if (!noteRefresh.isPending) noteRefresh.mutate();
    },
    noteStale,
    placesSignature,
    !publicView,
  );
  // A note that changes while the page is open fades in; the one it opened with does not.
  const [openingNote] = useState(shortlist.note ?? "");
  const noteSwapped = (shortlist.note ?? "") !== openingNote;

  const renderPlaceRow = (option: OptionSummaryOut) => {
    const state = option.shortlist?.state;
    const breach = option.state === "excluded" && option.exclusion != null && option.exclusion.by !== "user";
    const footing = maturityPhrase(option.maturity, where);
    const reason = state === "proposed" ? (option.shortlist?.reason ?? "") : "";
    return (
      <li key={option.option_id} className="py-5">
        <div className="flex items-start justify-between gap-6 max-sm:flex-col max-sm:gap-2">
          <div className="min-w-0 flex-1">
            <Link
              to={`/tasks/${taskId}/options/${option.option_id}`}
              // The card's breadcrumb leads back here (round 15, owner).
              state={CARD_FROM_SHORTLIST}
              className="text-lead font-bold text-navy underline-offset-4 hover:underline max-md:text-body"
            >
              {scrub(option.name)}
            </Link>
            {option.description !== "" && (
              <p className="mt-1.5 max-w-[62ch] text-body text-ink">{scrub(option.description)}</p>
            )}
            <p className="mt-1.5 text-meta text-grey">
              <span className="font-semibold text-navy">{scrub(leverLabel(option))}</span>
              {footing !== null && (
                <>
                  <span aria-hidden="true"> · </span>
                  <span className="sr-only">, </span>
                  {footing}
                </>
              )}
            </p>
            {reason !== "" && (
              <p className="mt-3 max-w-[62ch] border-l border-line pl-3 text-body text-ink">
                <LeadIn>Why:</LeadIn> {scrub(reason)}
              </p>
            )}
            {breach && option.exclusion != null && (
              <p className="mt-2 text-body text-ink">
                <span className="font-semibold text-red">Excluded:</span> breaks "
                {constraintLabel(scrub(option.exclusion.constraint))}". {scrub(option.exclusion.reason)}
              </p>
            )}
            {actions.notice !== null && actions.notice.optionId === option.option_id && (
              <p role="alert" className="mt-2 text-body text-red">
                {actions.notice.text}
              </p>
            )}
          </div>
          <ShortlistToggle
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
  const question = scrub(longlistTitle(plan.data?.scoping, task.data?.name));

  return (
    <ReportPage>
      {/* One header with the longlist's (round 10, lead): "Shortlist" as the
          title, the plan's question under it in Lead Grey, no label over it. */}
      <header>
        <h1 ref={titleRef} tabIndex={-1} className={cn(REPORT_TITLE_CLASS, "outline-none")}>
          Shortlist
        </h1>
        {question !== "Longlist" && (
          <p className="mt-2 max-w-prose-measure text-lead text-grey max-md:text-body">{question}</p>
        )}
        {walkActive && (
          <p role="status" className="mt-2 text-meta text-grey">
            Shortlisting…
          </p>
        )}
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
                : publicView
                  ? "No picks beside your places."
                  : "No picks beside your places. Suggest more asks Policy Atlas for some."}
          </p>
        )}
        {(hasNote || noteRefresh.isPending) && (
          <div className="mt-4">
            {noteRefresh.isPending ? (
              // While the note is rewritten, the Task Agent's working line in
              // its place: the turning fold mark and what it is doing (owner,
              // 2026-11-08); the new note replaces it with the arrivals' fade.
              <ActionLine label={NOTE_REVIEWING_WORDS} live arrivalId={`shortlist-note-${taskId}`} />
            ) : (
              <p
                key={shortlist.note ?? ""}
                className={cn("max-w-[62ch] text-body text-ink", noteSwapped && "anim-swap-in")}
              >
                <LeadIn>Not covered:</LeadIn> {scrub(shortlist.note ?? "")}
              </p>
            )}
            {noteStale && !publicView && !noteRefresh.isPending && (
              <p className="mt-1 text-meta text-grey">Written before your latest changes.</p>
            )}
            {footerLines.map((line) => (
              <p key={line} className="mt-1 text-meta text-grey">
                {line}
              </p>
            ))}
          </div>
        )}
      </section>

      {/* The two controls that re-propose, one block on the left edge: the
          risk appetite over Suggest more (a secondary: the page's one primary
          is Assess), the way back to the longlist beside it (round 10,
          finding 4). Stacked, it fits a 400 px screen. */}
      {publicView ? (
        <div className="mt-8">
          <p className="text-meta font-semibold text-grey">Risk appetite</p>
          <p className="mt-1.5 text-body text-ink">{RISK_APPETITE_LABELS[appetite]}</p>
        </div>
      ) : (
      <div className="print-hide mt-8">
        <label htmlFor="shortlist-risk-appetite" className="block text-meta font-semibold text-grey">
          Risk appetite
        </label>
        <div className="mt-1.5">
          <RiskAppetiteSelect
            id="shortlist-risk-appetite"
            field
            value={appetite}
            disabled={walkActive || patchPlan.isPending}
            onChange={(value) => patchPlan.mutate({ scoping: { risk_appetite: value } })}
          />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            variant="outline"
            className="h-10"
            disabled={walkActive || !canSuggest || suggest.isPending}
            aria-describedby={suggestOff !== null ? "shortlist-suggest-off" : undefined}
            onClick={() => suggest.mutate()}
          >
            Suggest more
          </Button>
          <Link to={`/tasks/${taskId}/result`} className={cn(LINK_CLASS, "text-meta")}>
            Add more from the longlist
          </Link>
        </div>
        {suggestOff !== null && (
          <p id="shortlist-suggest-off" className="mt-2 text-meta text-grey">
            {suggestOff}
          </p>
        )}
        {shortlist.stale && !walkActive && (
          <p className="mt-2 text-meta text-grey">The plan has changed. Suggest more to update the picks.</p>
        )}
      </div>
      )}
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

      {/* The page's one primary; while it is off its reason is a line of
          words under it, not a tooltip (round 10, finding 4). */}
      {!publicView && (
        <div className="mt-10 border-t border-line pt-6">
          <Button variant="primary" disabled aria-describedby="shortlist-assess-off">
            Assess these {placed.length}
          </Button>
          <p id="shortlist-assess-off" className="mt-2 text-meta text-grey">
            Assessment is not yet available.
          </p>
        </div>
      )}
    </ReportPage>
  );
}
