import { useState } from "react";

import { usePatchPlan, useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { overlayIsDirty, overlayToPlanPatch, type PlanOverlay } from "./planOverlay";

/** Green Start search — Nesta green, not the blue primary. */
export const START_SEARCH_CLASS =
  "bg-green px-6 py-3.5 text-body font-bold text-white hover:bg-[#147a6c]";

const APPLY_FAILED_FALLBACK = "The plan edits couldn't be applied. Try again.";

/**
 * Apply local plan edits (if any) then start the run. Shared by the chat
 * actions and the plan document's own Start search.
 */
export function usePlanStart({
  taskId,
  overlay,
  runActive,
  onStarted,
  onDiscardOverlay,
}: {
  taskId: string;
  overlay: PlanOverlay;
  runActive: boolean;
  onStarted?: () => void;
  /** Clears the caller's overlay state — wired to the same `setPlanOverlay({})`
   *  clearer a normal `onStarted` uses, but called up front so Discard starts
   *  against the last saved server plan without a PATCH. */
  onDiscardOverlay?: () => void;
}) {
  const planQuery = usePlan(taskId);
  const startRun = useStartRun(taskId);
  const patchPlan = usePatchPlan(taskId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  const plan = planQuery.data?.plan ?? null;
  const applying = patchPlan.isPending || startRun.isPending;

  // A fresh edit (or a discard) makes the last failure stale — it no longer
  // describes what Start would do next. Adjusted during render (React's
  // documented pattern for resetting state on a prop change) rather than in
  // an effect, so it takes effect the same render instead of one tick late.
  const [noticeForOverlay, setNoticeForOverlay] = useState(overlay);
  if (noticeForOverlay !== overlay) {
    setNoticeForOverlay(overlay);
    setStartNotice(null);
  }

  const beginRun = () => {
    startRun.mutate(undefined, {
      onSuccess: () => onStarted?.(),
      onError: (error) => {
        const code = (error as { code?: string }).code;
        setStartNotice(
          isConflictCode(code) ? conflictSentences[code] : "The search couldn't start. Try again.",
        );
      },
    });
  };

  const start = () => {
    if (plan === null) return;
    setStartNotice(null);
    if (!overlayIsDirty(overlay)) {
      beginRun();
      return;
    }
    patchPlan.mutate(overlayToPlanPatch(overlay, plan), {
      onSuccess: () => beginRun(),
      onError: (error) => {
        const code = (error as { code?: string }).code;
        const message = (error as Error | undefined)?.message;
        setStartNotice(
          isConflictCode(code)
            ? conflictSentences[code]
            : message != null && message !== ""
              ? `Those plan edits couldn't be saved: ${message}`
              : APPLY_FAILED_FALLBACK,
        );
      },
    });
  };

  /** Discard the local overlay and start against the last saved server
   *  plan — no PATCH, so a bad local edit can never block a run the
   *  server-approved plan would otherwise start cleanly. */
  const discardAndStart = () => {
    if (plan === null) return;
    setStartNotice(null);
    onDiscardOverlay?.();
    beginRun();
  };

  return {
    start,
    discardAndStart,
    applying,
    startNotice,
    disabled: applying || runActive,
    label: patchPlan.isPending ? "Applying edits…" : startRun.isPending ? "Starting…" : "Start search",
  };
}
