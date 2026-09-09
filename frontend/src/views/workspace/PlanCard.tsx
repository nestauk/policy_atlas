import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import type { PlanOverlay } from "./planOverlay";
import { START_SEARCH_CLASS, usePlanStart } from "./planStart";

type PlanDraft = components["schemas"]["PlanDraft"];

/** Stable default so an unset `overlay` prop never fools the "clear the
 *  start notice on overlay change" effect with a fresh `{}` every render. */
const EMPTY_OVERLAY: PlanOverlay = {};

/**
 * Inline actions once the three task_agent steps are done: review in the plan
 * document, or start the search. Local plan edits apply on start, not on each save.
 *
 * `isOwner` (task 033 phase 10c, contract § 11 / rubric 37): starting a run
 * is an owner-only mutation, so a non-owner sees "Review the plan" only —
 * the read action stays, Start search hides (the same idiom
 * `VisibilityControl` established, not a disabled button that would error).
 */
export function PlanCard({
  taskId,
  runActive,
  started = false,
  isOwner,
  onReviewPlan,
  overlay = EMPTY_OVERLAY,
  onOverlayApplied,
  onDiscardOverlay,
}: {
  taskId: string;
  runActive: boolean;
  started?: boolean;
  isOwner: boolean;
  onReviewPlan?: () => void;
  overlay?: PlanOverlay;
  onOverlayApplied?: () => void;
  onDiscardOverlay?: () => void;
}) {
  const planQuery = usePlan(taskId);
  const { start, discardAndStart, hasLocalEdits, startNotice, disabled, label } = usePlanStart({
    taskId,
    overlay,
    runActive,
    onOverlayApplied,
    onDiscardOverlay,
  });

  const planOut = planQuery.data;
  // Task 044: a scoping turn's readiness lives on `scoping`, never `plan`
  // (null for that capability) — the capability branch this card needs so a
  // scoping task_agent turn drives it exactly as an ES one does (do not fork
  // the pane: one card, one capability check). Scoping's own multi-state
  // start action lives in the opened plan document (`planStart.ts`'s
  // `useScopingPlanStart`) — this inline card only ever offers the door in.
  const isScoping = planOut?.capability === "options_scoping";
  const plan: PlanDraft | null = isScoping ? null : (planOut?.plan ?? null);
  const approved = planOut?.status === "approved";
  const scopingReady = isScoping && planOut?.scoping?.ready === true;
  if (started || !approved) return null;
  if (isScoping ? !scopingReady : plan === null || !plan.ready) return null;

  return (
    <div className="anim-rise mr-8 flex flex-wrap items-center gap-3" data-testid="plan-ready-actions">
      <Button className="px-6 py-3.5 text-body" onClick={() => onReviewPlan?.()}>
        Review the plan
      </Button>
      {isOwner && !isScoping && (
        <Button className={cn(START_SEARCH_CLASS)} disabled={disabled} onClick={start}>
          {label}
        </Button>
      )}
      {isOwner && !isScoping && startNotice != null && (
        <div className="flex w-full flex-wrap items-center gap-3">
          <p role="alert" className="text-body text-red">
            {startNotice}
          </p>
          {hasLocalEdits && (
            <Button variant="secondary" size="sm" onClick={discardAndStart}>
              Discard edits and start
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
