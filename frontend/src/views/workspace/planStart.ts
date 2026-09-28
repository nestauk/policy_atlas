import { useState } from "react";

import { useConfirmBaseline, usePatchPlan, useStartRun } from "../../api/mutations";
import { useLonglist, usePlan, useRuns, useTask } from "../../api/queries";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { activeRun, hasLonglist } from "../scopingActivity";
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
 * correction 2026-09-09; reworked task 044 review C6; task 045 S13/S15).
 * States off what exists and what is active — `TaskOut.active_run` (any
 * walk, option searches included) and the longlist — then the walk list
 * (`baselineRun`, the latest walk that actually wrote a baseline, read off
 * `artefact_id !== null` — never a status guess) and the current plan
 * version. In dispatch order:
 *
 *   - a walk is running or paused → `none`: nothing to click. Before the
 *     plan is confirmed the gate's check-in card and the Task Agent chat own
 *     the decision; after it (or once a longlist exists) the line says the
 *     longlist is being built. A running option search lands here too, so
 *     it disables the start actions — but it never opens or locks a tab.
 *   - no walk yet → `build`: one primary action, with the time band.
 *   - a longlist exists for the plan version on screen → `longlist_built`.
 *   - a longlist exists but the plan has moved on since it was built →
 *     `rebuild_longlist`, whose **Rebuild longlist** posts to
 *     `confirm-baseline` on the new version; the server opens the walk (D14,
 *     P12).
 *   - `baseline_confirmed.plan_version === plan.version`, or `baselineRun`
 *     finished (`succeeded`/`degraded`) on this very version → `confirmed`:
 *     settled, but no longlist yet and nothing running (the longlist walk
 *     was refused or failed) — **Build longlist** asks again.
 *   - `baselineRun` exists otherwise (the plan moved on since it wrote the
 *     baseline, or it was aborted at the gate, or a later rebuild
 *     aborted/failed before writing one of its own) → `rebuild_or_confirm`.
 *   - no `baselineRun` (nothing has ever reached synthesise) → `build`, the
 *     same fresh-start action.
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
  | {
      kind: "none";
      /** The walk that is running builds (or rebuilds) the longlist: the plan
       *  is confirmed for this version, or a longlist already exists. */
      buildingLonglist: boolean;
    }
  | {
      kind: "rebuild_or_confirm";
      rebuild: { label: string; onStart: () => void; disabled: boolean };
      confirm: { label: string; onConfirm: () => void; disabled: boolean };
      notice: string | null;
    }
  | {
      kind: "confirmed";
      /** Confirmed but no longlist and nothing running — ask for it again. */
      build: { label: string; onConfirm: () => void; disabled: boolean };
      notice: string | null;
    }
  | { kind: "longlist_built"; options: number }
  | {
      kind: "rebuild_longlist";
      /** The plan version the longlist on hand was built from; null when the
       *  longlist could not be read (task 045, L6). */
      builtFrom: number | null;
      rebuild: { label: string; onConfirm: () => void; disabled: boolean };
      notice: string | null;
    };

/** The longlist fields the start states read. */
export interface ScopingLonglist {
  plan_version: number;
  counts: { options: number };
}

/**
 * The one sentence that says where the plan stands, or `null` when a state
 * says nothing. Shared by the plan document and any surface that words the
 * same state, so two surfaces can never word it differently (task 044,
 * C18; task 045 replaces the old fixed "the longlist arrives with the next
 * stage").
 */
export function scopingStatusLine(state: ScopingStartState): string | null {
  switch (state.kind) {
    case "longlist_built":
      return `Longlist built · ${state.options} ${state.options === 1 ? "option" : "options"}`;
    case "rebuild_longlist":
      // An unread longlist (L6) says so in its notice instead.
      return state.builtFrom === null
        ? null
        : `Longlist built from plan version ${state.builtFrom} · the plan has changed`;
    case "confirmed":
      return "Plan confirmed · no longlist yet";
    case "none":
      return state.buildingLonglist ? "Building the longlist" : null;
    default:
      return null;
  }
}

/** The server page-size cap (`contract/common.py`). The list is read with
 *  `parentless` (task 045, A13): only the baseline and longlist walks, never
 *  the option searches, so the baseline walk cannot be paged out. */
const SCOPING_RUNS_PAGE_SIZE = 200;

/** The start area's words when the longlist exists but could not be read. */
const LONGLIST_UNREAD_NOTICE = "The longlist couldn't be loaded.";

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
  /** The run stream's own "a walk is running or paused" — ahead of the task
   *  read model until its next refetch. */
  runActive: boolean;
  onStarted?: () => void;
}): ScopingStartState {
  const planQuery = usePlan(taskId);
  const runsQuery = useRuns(taskId, { page_size: SCOPING_RUNS_PAGE_SIZE, parentless: true });
  const taskQuery = useTask(taskId);
  // Task 045 (S15): what exists and what is active. The longlist is read
  // only once the task says one exists (its plan version decides between
  // `longlist_built` and `rebuild_longlist`).
  const longlistExists = hasLonglist(taskQuery.data);
  const longlistQuery = useLonglist(longlistExists ? taskId : "");
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

  /** `POST /plan/confirm-baseline` on the version on screen; the server
   *  opens the longlist walk (a rebuild when a longlist already exists —
   *  D14, P12). */
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
  const confirmDisabled = confirmBaseline.isPending || runActive || baselineRun === null;

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
      disabled: confirmDisabled,
    },
    notice,
  });

  return scopingStartDispatch({
    // Any of three sources may be first to know: the run stream, the task
    // read model (`active_run`, option searches included) and the walk list.
    active:
      runActive ||
      activeRun(taskQuery.data) !== null ||
      latestRun?.status === "running" ||
      latestRun?.status === "paused",
    anyWalk: latestRun !== null,
    longlistExists,
    longlist: longlistQuery.data,
    longlistError: longlistQuery.isError,
    currentVersion,
    confirmed,
    baselineRun: baselineRun !== null,
    states: {
      build,
      rebuildOrConfirm,
      confirmed: () => ({
        kind: "confirmed",
        build: {
          label: confirmBaseline.isPending ? "Starting…" : "Build longlist",
          onConfirm: confirmAndBuildLonglist,
          disabled: confirmDisabled,
        },
        notice,
      }),
      rebuildLonglist: (builtFrom) => ({
        kind: "rebuild_longlist",
        builtFrom,
        rebuild: {
          label: confirmBaseline.isPending ? "Starting…" : "Rebuild longlist",
          onConfirm: confirmAndBuildLonglist,
          disabled: confirmDisabled,
        },
        notice: notice ?? (builtFrom === null ? LONGLIST_UNREAD_NOTICE : null),
      }),
    },
  });
}

/**
 * The start area's dispatch order (see `ScopingStartState`), apart from the
 * hooks so the order itself is one readable function. The longlist states
 * come **before** `confirmed` (task 045, A7): a confirmed plan with a
 * longlist says so, not "no longlist yet".
 */
function scopingStartDispatch({
  active,
  anyWalk,
  longlistExists,
  longlist,
  longlistError,
  currentVersion,
  confirmed,
  baselineRun,
  states,
}: {
  active: boolean;
  anyWalk: boolean;
  longlistExists: boolean;
  longlist: ScopingLonglist | null | undefined;
  longlistError: boolean;
  currentVersion: number | null;
  confirmed: boolean;
  baselineRun: boolean;
  states: {
    build: () => ScopingStartState;
    rebuildOrConfirm: () => ScopingStartState;
    confirmed: () => ScopingStartState;
    rebuildLonglist: (builtFrom: number | null) => ScopingStartState;
  };
}): ScopingStartState {
  if (active) return { kind: "none", buildingLonglist: confirmed || longlistExists };
  if (!anyWalk) return states.build();
  if (longlistExists) {
    // Its plan version decides the state; until it has loaded, say nothing
    // rather than guess. A read that failed (L6) still leaves Rebuild.
    if (longlist == null && longlistError) return states.rebuildLonglist(null);
    if (longlist == null || currentVersion === null) return { kind: "none", buildingLonglist: false };
    if (currentVersion > longlist.plan_version) return states.rebuildLonglist(longlist.plan_version);
    return { kind: "longlist_built", options: longlist.counts.options };
  }
  if (confirmed) return states.confirmed();
  // A baseline exists but not for the version on screen — the plan moved on,
  // or the walk that wrote it was aborted at the gate, or a later rebuild
  // aborted/failed before writing one of its own.
  if (baselineRun) return states.rebuildOrConfirm();
  // Nothing was ever produced (`failed`/`interrupted`, or aborted before
  // synthesise) — the same fresh-start action as before any walk at all.
  return states.build();
}
