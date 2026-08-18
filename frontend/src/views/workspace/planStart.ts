import { useState } from "react";

import { usePatchPlan, useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { overlayIsDirty, overlayToPlanPatch, type PlanOverlay } from "./planOverlay";

/** Green Start search — Nesta green, not the blue primary. */
export const START_SEARCH_CLASS =
  "bg-green px-6 py-3.5 text-body font-bold text-white hover:bg-[#147a6c]";

/**
 * Apply local plan edits (if any) then start the run. Shared by the chat
 * actions and the plan document's own Start search.
 */
export function usePlanStart({
  projectId,
  overlay,
  runActive,
  onStarted,
}: {
  projectId: string;
  overlay: PlanOverlay;
  runActive: boolean;
  onStarted?: () => void;
}) {
  const planQuery = usePlan(projectId);
  const startRun = useStartRun(projectId);
  const patchPlan = usePatchPlan(projectId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  const plan = planQuery.data?.plan ?? null;
  const applying = patchPlan.isPending || startRun.isPending;

  const start = () => {
    if (plan === null) return;
    setStartNotice(null);
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
    if (!overlayIsDirty(overlay)) {
      beginRun();
      return;
    }
    patchPlan.mutate(overlayToPlanPatch(overlay), {
      onSuccess: () => beginRun(),
      onError: (error) => {
        const code = (error as { code?: string }).code;
        setStartNotice(
          isConflictCode(code)
            ? conflictSentences[code]
            : "The plan edits couldn't be applied. Try again, or start without them.",
        );
      },
    });
  };

  return {
    start,
    applying,
    startNotice,
    disabled: applying || runActive,
    label: patchPlan.isPending ? "Applying edits…" : startRun.isPending ? "Starting…" : "Start search",
  };
}
