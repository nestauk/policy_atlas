import { useEffect, useState } from "react";

import { usePatchPlan, useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import {
  displayedQuestion,
  overlayIsDirty,
  overlayToPlanPatch,
  pruneOverlayToPlanDiff,
  screeningOverlayError,
  type PlanOverlay,
} from "./planOverlay";

/** Green Start search — Nesta green, not the blue primary. */
export const START_SEARCH_CLASS =
  "bg-green px-6 py-3.5 text-body font-bold text-white hover:bg-[#147a6c]";

function applyFailureMessage(error: {
  code?: string;
  status?: number;
  message?: string;
}): string {
  if (isConflictCode(error.code)) return conflictSentences[error.code];
  if (error.message != null && error.message !== "") {
    return `Those plan edits couldn't be saved: ${error.message}`;
  }
  return "Those plan edits couldn't be saved. Fix them in the plan, or discard the edits and start.";
}

/**
 * Apply local plan edits (if any) then start the run. Shared by the chat
 * actions and the plan document's own Start search.
 */
export function usePlanStart({
  projectId,
  overlay,
  runActive,
  onStarted,
  onDiscardOverlay,
}: {
  projectId: string;
  overlay: PlanOverlay;
  runActive: boolean;
  onStarted?: () => void;
  /** Clear local edits (used by Discard edits and start). */
  onDiscardOverlay?: () => void;
}) {
  const planQuery = usePlan(projectId);
  const startRun = useStartRun(projectId);
  const patchPlan = usePatchPlan(projectId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  const [canDiscard, setCanDiscard] = useState(false);
  const plan = planQuery.data?.plan ?? null;
  const applying = patchPlan.isPending || startRun.isPending;

  // A fixed edit must not keep showing the previous apply error.
  useEffect(() => {
    setStartNotice(null);
    setCanDiscard(false);
  }, [overlay]);

  const beginRun = () => {
    startRun.mutate(undefined, {
      onSuccess: () => onStarted?.(),
      onError: (error) => {
        const code = (error as { code?: string }).code;
        setCanDiscard(false);
        setStartNotice(
          isConflictCode(code) ? conflictSentences[code] : "The search couldn't start. Try again.",
        );
      },
    });
  };

  const startWithOverlay = (nextOverlay: PlanOverlay) => {
    if (plan === null) return;
    setStartNotice(null);
    setCanDiscard(false);

    const effective = pruneOverlayToPlanDiff(nextOverlay, plan);
    if (!overlayIsDirty(effective)) {
      beginRun();
      return;
    }

    const screeningError = screeningOverlayError(
      effective.screening_criteria,
      displayedQuestion(plan, effective),
    );
    if (screeningError !== null) {
      setStartNotice(screeningError);
      setCanDiscard(true);
      return;
    }

    patchPlan.mutate(overlayToPlanPatch(effective, plan), {
      onSuccess: () => beginRun(),
      onError: (error) => {
        setCanDiscard(true);
        setStartNotice(
          applyFailureMessage(
            error as { code?: string; status?: number; message?: string },
          ),
        );
      },
    });
  };

  const start = () => startWithOverlay(overlay);

  const discardAndStart = () => {
    onDiscardOverlay?.();
    setStartNotice(null);
    setCanDiscard(false);
    if (plan === null) return;
    beginRun();
  };

  return {
    start,
    discardAndStart,
    applying,
    startNotice,
    canDiscard: canDiscard && onDiscardOverlay != null && overlayIsDirty(overlay),
    disabled: applying || runActive,
    label: patchPlan.isPending ? "Applying edits…" : startRun.isPending ? "Starting…" : "Start search",
  };
}
