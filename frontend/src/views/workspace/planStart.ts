import { useState } from "react";

import { useConfirmBaseline, usePatchPlan, useStartRun } from "../../api/mutations";
import { useArtefact, usePlan, useRuns } from "../../api/queries";
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
  onOverlayApplied,
  onDiscardOverlay,
}: {
  taskId: string;
  overlay: PlanOverlay;
  runActive: boolean;
  onStarted?: () => void;
  /** Clears the caller's overlay state as soon as the PATCH lands — the
   *  edits are on the server from that moment, so keeping them locally would
   *  let a failed run start replay them over later server-side changes. */
  onOverlayApplied?: () => void;
  /** Clears the caller's overlay state — wired to the same `setPlanOverlay({})`
   *  clearer `onOverlayApplied` uses, but called up front so Discard starts
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
    // The pruned body can be empty even when the overlay holds keys (a chat
    // turn applied the same edits meanwhile) — a bodyless PATCH would still
    // mint a new approved plan version, so skip it and clear the stale keys.
    const body = overlayIsDirty(overlay) ? overlayToPlanPatch(overlay, plan) : {};
    if (Object.keys(body).length === 0) {
      if (overlayIsDirty(overlay)) onOverlayApplied?.();
      beginRun();
      return;
    }
    patchPlan.mutate(body, {
      onSuccess: () => {
        onOverlayApplied?.();
        beginRun();
      },
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
    // Gates "Discard edits and start": with nothing local to discard the
    // action is a mislabelled retry.
    hasLocalEdits: overlayIsDirty(overlay),
    applying,
    startNotice,
    disabled: applying || runActive,
    label: patchPlan.isPending ? "Applying edits…" : startRun.isPending ? "Starting…" : "Start search",
  };
}

/**
 * The scoping plan document's start area (contract deliverable 5, owner
 * correction 2026-09-09). Five states off the latest walk and the current
 * plan version — never a "newer than" heuristic, because a walk's own
 * pause/finish state is definitive:
 *
 *   - no walk yet → `build`: one primary action, with the time band.
 *   - latest walk `running` or `paused` → `none`: the gate's check-in card
 *     and the Task Agent chat own the decision here — `POST
 *     .../plan/confirm-baseline` is 409 `run_active` while a walk is running
 *     or paused, so this component must offer nothing to click.
 *   - `baseline_confirmed.plan_version === plan.version` → `confirmed`.
 *   - latest walk `succeeded` (or `degraded` — it still produced a baseline)
 *     and `plan.version === walk.plan_version` → also `confirmed`: a
 *     succeeded walk can only have finished through the gate's Confirm
 *     option or the unattended standing default, so the record already
 *     exists even before this task's own confirm-baseline call has fired.
 *   - latest walk finished (`succeeded`/`degraded`/`aborted`) and
 *     `plan.version > walk.plan_version` (edited since) → `rebuild_or_confirm`.
 *   - latest walk `aborted` and `plan.version === walk.plan_version` (the
 *     user chose Change the plan but has not changed it yet) → also
 *     `rebuild_or_confirm`.
 *   - anything else (a `failed`/`interrupted` walk with nothing usable to
 *     confirm or rebuild from) → `build`, the same fresh-start action.
 */
export type ScopingStartState =
  | {
      kind: "build";
      label: string;
      timeBand: string | null;
      onStart: () => void;
      disabled: boolean;
      notice: string | null;
    }
  | { kind: "none" }
  | {
      kind: "rebuild_or_confirm";
      rebuild: { label: string; onStart: () => void; disabled: boolean };
      confirm: { label: string; onConfirm: () => void; disabled: boolean };
      notice: string | null;
    }
  | { kind: "confirmed" };

/** The server page-size cap (`contract/common.py`) — one page comfortably
 *  covers every walk a scoping task has run in this slice (one gate, no
 *  option runs yet). */
const SCOPING_RUNS_PAGE_SIZE = 200;

/** A walk that produced a baseline worth confirming or rebuilding from. */
function baselineProduced(status: string): boolean {
  return status === "succeeded" || status === "degraded";
}

export function useScopingPlanStart({
  taskId,
  runActive,
  onStarted,
}: {
  taskId: string;
  runActive: boolean;
  onStarted?: () => void;
}): ScopingStartState {
  const planQuery = usePlan(taskId);
  const runsQuery = useRuns(taskId, { page_size: SCOPING_RUNS_PAGE_SIZE });
  const artefactQuery = useArtefact(taskId);
  const startRun = useStartRun(taskId);
  const confirmBaseline = useConfirmBaseline(taskId);
  const [notice, setNotice] = useState<string | null>(null);

  const planOut = planQuery.data;
  const scoping = planOut?.scoping ?? null;
  const currentVersion = planOut?.version ?? null;
  const runs = runsQuery.data?.data ?? [];
  // The most recently STARTED walk, whatever its status — the gate's own
  // pause/finish state decides what this card offers, not just the walks
  // that happen to have produced a result.
  const latestRun =
    [...runs].sort((left, right) => right.started_at.localeCompare(left.started_at))[0] ?? null;
  const baselineConfirmed = scoping?.baseline_confirmed ?? null;
  const confirmedForCurrentVersion =
    baselineConfirmed !== null &&
    currentVersion !== null &&
    baselineConfirmed.plan_version === currentVersion;
  const sameVersionAsLatestWalk =
    latestRun !== null && currentVersion !== null && currentVersion === latestRun.plan_version;
  const newerVersionThanLatestWalk =
    latestRun !== null && currentVersion !== null && currentVersion > latestRun.plan_version;

  const beginRun = () => {
    setNotice(null);
    startRun.mutate(undefined, {
      onSuccess: () => onStarted?.(),
      onError: (error) => {
        const code = (error as { code?: string }).code;
        setNotice(isConflictCode(code) ? conflictSentences[code] : "The run couldn't start. Try again.");
      },
    });
  };

  const confirmAndBuildLonglist = () => {
    const artefactId = artefactQuery.data?.artefact_id;
    if (currentVersion === null || artefactId === undefined) return;
    setNotice(null);
    confirmBaseline.mutate(
      { artefact_id: artefactId, plan_version: currentVersion },
      {
        onError: (error) => {
          const code = (error as { code?: string }).code;
          setNotice(
            isConflictCode(code) ? conflictSentences[code] : "The plan couldn't be confirmed. Try again.",
          );
        },
      },
    );
  };

  const build = (): ScopingStartState => ({
    kind: "build",
    label: startRun.isPending ? "Starting…" : "Confirm and build baseline",
    timeBand: scoping?.time_band ?? null,
    onStart: beginRun,
    disabled: startRun.isPending || runActive,
    notice,
  });

  const rebuildOrConfirm = (): ScopingStartState => ({
    kind: "rebuild_or_confirm",
    rebuild: {
      label: startRun.isPending ? "Starting…" : "Rebuild baseline",
      onStart: beginRun,
      disabled: startRun.isPending || runActive,
    },
    confirm: {
      label: confirmBaseline.isPending ? "Confirming…" : "Confirm plan and build longlist",
      onConfirm: confirmAndBuildLonglist,
      disabled: confirmBaseline.isPending || runActive || artefactQuery.data?.artefact_id === undefined,
    },
    notice,
  });

  if (latestRun === null) return build();
  if (latestRun.status === "running" || latestRun.status === "paused") return { kind: "none" };
  if (confirmedForCurrentVersion) return { kind: "confirmed" };
  if (baselineProduced(latestRun.status) && sameVersionAsLatestWalk) return { kind: "confirmed" };
  if (
    (baselineProduced(latestRun.status) || latestRun.status === "aborted") &&
    newerVersionThanLatestWalk
  ) {
    return rebuildOrConfirm();
  }
  if (latestRun.status === "aborted" && sameVersionAsLatestWalk) return rebuildOrConfirm();
  // `failed` / `interrupted`: nothing usable was produced — the same
  // fresh-start action as before any walk at all.
  return build();
}
