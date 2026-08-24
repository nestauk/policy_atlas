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
 */
export function PlanCard({
  projectId,
  runActive,
  started = false,
  onReviewPlan,
  overlay = {},
  onOverlayApplied,
}: {
  projectId: string;
  runActive: boolean;
  started?: boolean;
  onReviewPlan?: () => void;
  overlay?: PlanOverlay;
  onOverlayApplied?: () => void;
}) {
  const planQuery = usePlan(projectId);
  const { start, startNotice, disabled, label } = usePlanStart({
    projectId,
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
      <Button className={cn(START_SEARCH_CLASS)} disabled={disabled} onClick={start}>
        {label}
      </Button>
      {startNotice != null && (
        <p role="alert" className="w-full text-body text-red">
          {startNotice}
        </p>
      )}
    </div>
  );
}
