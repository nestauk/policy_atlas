import { useState } from "react";

import { useConfirmBaseline, usePatchPlan, useStartRun } from "../../api/mutations";
import { usePlan, useRuns } from "../../api/queries";
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
 * correction 2026-09-09; reworked task 044 review C6). States off the latest
 * walk, the latest walk that actually wrote a baseline (`baselineRun`, read
 * off `artefact_id !== null` — never a status guess), and the current plan
 * version:
 *
 *   - no walk yet → `build`: one primary action, with the time band.
 *   - latest walk `running` or `paused` → `none`: the gate's check-in card
 *     and the Task Agent chat own the decision here — `POST
 *     .../plan/confirm-baseline` is 409 `run_active` while a walk is running
 *     or paused, so this component must offer nothing to click.
 *   - `baseline_confirmed.plan_version === plan.version` → `confirmed`.
 *   - `baselineRun` exists, its status `succeeded`/`degraded`, and
 *     `plan.version === baselineRun.plan_version` → also `confirmed`: it can
 *     only have finished through the gate's Confirm option or the unattended
 *     standing default, so the record already exists even before this task's
 *     own confirm-baseline call has fired.
 *   - `baselineRun` exists otherwise (the plan moved on since it wrote the
 *     baseline, or it was aborted at the gate, or a later rebuild
 *     aborted/failed before writing one of its own) → `rebuild_or_confirm`.
 *   - no `baselineRun` (nothing has ever reached synthesise) → `build`, the
 *     same fresh-start action.
 */
/** The one sentence that says the plan is settled and what happens next.
 *  Shared by the plan document's start area and the Result band so the two
 *  surfaces can never word the same state differently (task 044, C18). */
export const SCOPING_CONFIRMED_LINE =
  "Plan confirmed · the longlist arrives with the next stage";

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

/** One scoping walk, in the fields every state rule below reads. */
interface ScopingWalk {
  status: string;
  started_at: string;
  plan_version: number;
  /** The artefact this walk wrote, or null/absent when it never reached
   *  synthesise (or ended before it). A walk that carries one produced a
   *  baseline, whatever its terminal status (task 044 review, C6). */
  artefact_id?: string | null;
}

/**
 * The scoping task's walk status: the latest walk and how the current plan
 * version stands against it.
 *
 * The one place the walk-status rule lives. `useScopingPlanStart` turns it
 * into the plan document's actions and `baselineBandState` turns it into the
 * Result band's words — neither re-derives it, so the two surfaces cannot
 * disagree about whether a plan is confirmed (task 044, C18).
 *
 * Args:
 *   runs: The task's walks, in any order.
 *   currentVersion: The plan's current version, or null while it loads.
 *   baselineConfirmed: The plan's `baseline_confirmed` record, if any.
 *
 * Returns:
 *   The latest-started walk, the latest-started walk that actually wrote a
 *   baseline, and whether the plan is settled.
 */
export function scopingWalkStatus({
  runs,
  currentVersion,
  baselineConfirmed,
}: {
  runs: readonly ScopingWalk[];
  currentVersion: number | null;
  baselineConfirmed: { plan_version: number } | null;
}) {
  // The most recently STARTED walk, whatever its status — the gate's own
  // pause/finish state decides what these surfaces say, not just the walks
  // that happen to have produced a result.
  const sorted = [...runs].sort((left, right) => right.started_at.localeCompare(left.started_at));
  const latestRun = sorted[0] ?? null;
  // The latest-started walk that carries an artefact (task 044 review, C6) —
  // whether a walk "produced a baseline" is this fact, not a status guess. A
  // later walk that never reached synthesise (still running, or aborted at
  // the gate before writing) must not hide an earlier baseline that is still
  // the one worth confirming or rebuilding from.
  const baselineRun = sorted.find((run) => run.artefact_id != null) ?? null;
  const confirmedForCurrentVersion =
    baselineConfirmed !== null &&
    currentVersion !== null &&
    baselineConfirmed.plan_version === currentVersion;
  const baselineRunConfirmed =
    baselineRun !== null &&
    currentVersion !== null &&
    baselineProduced(baselineRun.status) &&
    currentVersion === baselineRun.plan_version;
  return {
    latestRun,
    baselineRun,
    /** The plan is settled for the version on screen: either the record says
     *  so, or the walk that wrote the baseline finished on this very version
     *  (it can only have finished through Confirm or the standing default). */
    confirmed: confirmedForCurrentVersion || baselineRunConfirmed,
    /** The plan has moved on since `baselineRun` wrote the baseline — the
     *  Result band's "built from plan version N" mark (task 044, C18). */
    newerVersionThanBaselineRun:
      baselineRun !== null && currentVersion !== null && currentVersion > baselineRun.plan_version,
  };
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
  const startRun = useStartRun(taskId);
  const confirmBaseline = useConfirmBaseline(taskId);
  const [notice, setNotice] = useState<string | null>(null);

  const planOut = planQuery.data;
  const scoping = planOut?.scoping ?? null;
  const currentVersion = planOut?.version ?? null;
  const { latestRun, baselineRun, confirmed } = scopingWalkStatus({
    runs: runsQuery.data?.data ?? [],
    currentVersion,
    baselineConfirmed: scoping?.baseline_confirmed ?? null,
  });

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
    if (currentVersion === null || baselineRun === null || baselineRun.artefact_id == null) return;
    setNotice(null);
    confirmBaseline.mutate(
      { artefact_id: baselineRun.artefact_id, plan_version: currentVersion },
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
      disabled: confirmBaseline.isPending || runActive || baselineRun === null,
    },
    notice,
  });

  if (latestRun === null) return build();
  if (latestRun.status === "running" || latestRun.status === "paused") return { kind: "none" };
  if (confirmed) return { kind: "confirmed" };
  // A baseline exists but not for the version on screen — the plan moved on,
  // or the walk that wrote it was aborted at the gate, or a later rebuild
  // aborted/failed before writing one of its own.
  if (baselineRun !== null) return rebuildOrConfirm();
  // Nothing was ever produced (`failed`/`interrupted`, or aborted before
  // synthesise) — the same fresh-start action as before any walk at all.
  return build();
}
