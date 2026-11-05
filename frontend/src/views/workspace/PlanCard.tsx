import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { Button } from "../../ui/brand/Button";
import { isScoping } from "../scopingActivity";
import type { PlanOverlay } from "./planOverlay";
import { usePlanStart, useScopingPlanStart } from "./planStart";
import { researchApproachLabel } from "./planVocabulary";

type PlanDraft = components["schemas"]["PlanDraft"];

/** Stable default so an unset `overlay` prop never fools the "clear the
 *  start notice on overlay change" effect with a fresh `{}` every render. */
const EMPTY_OVERLAY: PlanOverlay = {};

/** The words on the run-start button, per capability (annex block H). */
const START_WORDS = {
  evidence_search: "Start the search",
  options_scoping: "Confirm and build the baseline",
} as const;

/** "Search plan · Standard report · ~20 to 40 min": what the plan is, from the
 *  draft's own fields; parts the draft does not carry are left out. */
function planSummary(plan: PlanDraft): string {
  const approach = researchApproachLabel(plan.search_effort ?? "", plan.analysis_depth ?? "");
  return ["Search plan", approach, plan.time_band].filter((part): part is string => Boolean(part)).join(" · ");
}

/**
 * The plan card once the planner's parts are done (task 058, N18; annex
 * scene 11): what the plan is, a quiet "Review the plan" link and the green
 * cut-corner button that starts the run, for both capabilities ("Start the
 * search" / "Confirm and build the baseline"). Local plan edits apply on
 * start, not on each save. Start is disabled while a planner turn streams,
 * so a partial reply never sits beside a live Start against the older plan
 * (N9).
 *
 * `isOwner` (task 033 phase 10c, contract § 11 / rubric 37): starting a run
 * is an owner-only mutation, so a non-owner sees "Review the plan" only.
 */
export function PlanCard({
  taskId,
  runActive,
  streaming = false,
  started = false,
  isOwner,
  onReviewPlan,
  overlay = EMPTY_OVERLAY,
  onOverlayApplied,
  onDiscardOverlay,
}: {
  taskId: string;
  runActive: boolean;
  /** True while a planner turn is streaming in. */
  streaming?: boolean;
  started?: boolean;
  isOwner: boolean;
  onReviewPlan?: () => void;
  overlay?: PlanOverlay;
  onOverlayApplied?: () => void;
  onDiscardOverlay?: () => void;
}) {
  const planQuery = usePlan(taskId);
  const search = usePlanStart({
    taskId,
    overlay,
    runActive,
    onOverlayApplied,
    onDiscardOverlay,
  });
  const scopingStart = useScopingPlanStart({ taskId, runActive });

  const planOut = planQuery.data;
  // Task 044: a scoping turn's readiness lives on `scoping`, never `plan`.
  const scoping = isScoping(planOut);
  const plan: PlanDraft | null = scoping ? null : (planOut?.plan ?? null);
  const approved = planOut?.status === "approved";
  const scopingReady = scoping && planOut?.scoping?.ready === true;
  if (started || !approved) return null;
  if (scoping ? !scopingReady : plan === null || !plan.ready) return null;

  // Scoping starts from the card only while the plan has never been built;
  // every later state (rebuild, confirm, longlist) lives in the plan document.
  const scopingBuild = scopingStart.kind === "build" ? scopingStart : null;
  const startLabel =
    scoping
      ? scopingBuild?.action.label === "Starting…" ? "Starting…" : START_WORDS.options_scoping
      : search.label === "Start search" ? START_WORDS.evidence_search : search.label;
  const startDisabled = streaming || (scoping ? (scopingBuild?.action.disabled ?? true) : search.disabled);
  const notice = scoping ? (scopingBuild?.notice ?? null) : search.startNotice;
  const showStart = isOwner && (!scoping || scopingBuild !== null);

  return (
    <div className="anim-rise mr-8 border border-line-2 bg-paper px-5 py-4" data-testid="plan-ready-actions">
      {plan !== null && <p className="text-body font-semibold text-navy">{planSummary(plan)}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-3">
        {showStart && (
          <Button
            variant="start"
            size="entry"
            disabled={startDisabled}
            onClick={scoping ? scopingBuild?.action.onClick : search.start}
          >
            {startLabel}
          </Button>
        )}
        <button
          type="button"
          onClick={() => onReviewPlan?.()}
          className="cursor-pointer text-body font-semibold text-navy underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
        >
          Review the plan
        </button>
      </div>
      {isOwner && notice != null && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p role="alert" className="text-body text-red">
            {notice}
          </p>
          {!scoping && search.hasLocalEdits && (
            <Button variant="secondary" size="sm" onClick={search.discardAndStart}>
              Discard edits and start
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
