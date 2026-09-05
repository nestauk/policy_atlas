import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import type { PlanOverlay } from "./planOverlay";
import { START_SEARCH_CLASS, usePlanStart } from "./planStart";

type PlanDraft = components["schemas"]["PlanDraft"];

/**
 * Inline actions once the three planning steps are done: review in the plan
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
  overlay = {},
  onOverlayApplied,
}: {
  taskId: string;
  runActive: boolean;
  started?: boolean;
  isOwner: boolean;
  onReviewPlan?: () => void;
  overlay?: PlanOverlay;
  onOverlayApplied?: () => void;
}) {
  const planQuery = usePlan(taskId);
  const { start, startNotice, disabled, label } = usePlanStart({
    taskId,
    overlay,
    runActive,
    onStarted: onOverlayApplied,
  });

  const plan: PlanDraft | null = planQuery.data?.plan ?? null;
  const approved = planQuery.data?.status === "approved";
  if (plan === null || !approved || !plan.ready || started) return null;

  return (
    <div className="anim-rise mr-8 flex flex-wrap items-center gap-3" data-testid="plan-ready-actions">
      <Button className="px-6 py-3.5 text-body" onClick={() => onReviewPlan?.()}>
        Review the plan
      </Button>
      {isOwner && (
        <Button className={cn(START_SEARCH_CLASS)} disabled={disabled} onClick={start}>
          {label}
        </Button>
      )}
      {isOwner && startNotice != null && (
        <p role="alert" className="w-full text-body text-red">
          {startNotice}
        </p>
      )}
    </div>
  );
}
