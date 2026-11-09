import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../api/queries";
import { connectEventStream } from "../api/sse";
import { useAuth } from "../auth";
import { createInitialRunStreamState } from "./types";
import { isOtherRunsStage, reduceRunStreamFrame } from "./reducer";
import type { RunStreamState } from "./types";

/**
 * Trailing window for collapsing bursty `stage.completed` / `run.status`
 * invalidations — especially the full-history replay on a cold connect —
 * into one read-model refresh instead of one per frame.
 */
export const RUN_STREAM_INVALIDATE_DEBOUNCE_MS = 300;

/**
 * Trailing window for refreshing the Sources list and the Landscape while
 * the full texts are read: at most one refresh per window, however many
 * `ingest` ticks arrive (task 058, N16).
 */
export const INGEST_REFRESH_THROTTLE_MS = 5_000;

interface RunStreamContextValue {
  taskId: string;
  state: RunStreamState;
}

const RunStreamContext = createContext<RunStreamContextValue | null>(null);

/**
 * Own the task's SSE connection at the task shell so Plan / Results /
 * Sources / History / Share share one replay-then-tail stream instead of
 * each leaf remount reconnecting from `cursor=0` (and storming read-model
 * invalidations mid-replay).
 *
 * Args:
 *   taskId: The open task. Changing it resets the reducer and opens a
 *     fresh connection for the new task.
 *   connect: Whether to open the SSE connection at all. `false` for the
 *     public task view (task 037): the events route is not on the public
 *     read surface, so the provider stays mounted (the views' `useRunStream`
 *     calls keep working) but holds the idle initial state and never
 *     issues a request.
 *   children: Shell chrome and the routed task view.
 */
export function RunStreamProvider({
  taskId,
  connect = true,
  children,
}: {
  taskId: string;
  connect?: boolean;
  children: ReactNode;
}) {
  const state = useRunStreamConnection(taskId, connect);
  return (
    <RunStreamContext.Provider value={{ taskId, state }}>
      {children}
    </RunStreamContext.Provider>
  );
}

/**
 * Read the shell-owned run stream for this task.
 *
 * Args:
 *   taskId: Must match the surrounding `RunStreamProvider`.
 *
 * Returns:
 *   The live reducer state for the task's event stream.
 *
 * Raises:
 *   Error when called outside a provider, or for a different task id.
 */
export function useRunStream(taskId: string): RunStreamState {
  const ctx = useContext(RunStreamContext);
  if (ctx === null) {
    throw new Error("useRunStream must be used within a RunStreamProvider");
  }
  if (ctx.taskId !== taskId) {
    throw new Error(
      `useRunStream(${taskId}) does not match RunStreamProvider(${ctx.taskId})`,
    );
  }
  return ctx.state;
}

/**
 * Open one authed SSE connection, fold frames through the pure reducer, and
 * refresh the read models the frames make stale:
 *
 * - the tracked run's `stage.completed` / `run.status`: every query under the
 *   task, debounced so a cold full-history replay is one refresh;
 * - a child walk's (an option search's) `stage.completed` / `run.status`:
 *   the options query only, in the same debounce window (task 058, N23);
 * - an `ingest` tick: the Sources list and the Landscape, at most once per
 *   `INGEST_REFRESH_THROTTLE_MS` (task 058, N16). No other tick refreshes
 *   anything.
 *
 * A fresh mount always starts from `cursor=0` — the reducer's replay
 * idempotence is what makes that safe.
 */
function useRunStreamConnection(taskId: string, connect: boolean): RunStreamState {
  const auth = useAuth();
  const queryClient = useQueryClient();

  const [state, setState] = useState<RunStreamState>(createInitialRunStreamState);

  // Reset the store when `taskId` changes, following React's documented
  // "adjust state during render" pattern rather than an effect — this runs
  // synchronously during render (before paint) exactly when the state on
  // hand no longer belongs to the current task.
  const [stateTaskId, setStateTaskId] = useState(taskId);
  if (stateTaskId !== taskId) {
    setStateTaskId(taskId);
    setState(createInitialRunStreamState());
  }

  useEffect(() => {
    if (!connect) return undefined;
    // Guards against a frame from THIS effect's connection landing after
    // its cleanup has run but before the closure is torn down — without
    // this, such a frame would fold into the next task's already-reset
    // state (a stale-connection race at the task-switch boundary).
    let closed = false;
    let invalidateTimer: ReturnType<typeof setTimeout> | null = null;
    let ingestTimer: ReturnType<typeof setTimeout> | null = null;
    // This connection's frames folded on their own, so a frame can be told
    // apart as a child walk's (a longlist's option search) as it lands.
    let folded = createInitialRunStreamState();
    // What the pending debounce window has seen: a tracked-run frame
    // refreshes everything; child frames alone refresh the options only.
    let parentPending = false;

    const flushInvalidate = () => {
      invalidateTimer = null;
      const everything = parentPending;
      parentPending = false;
      const queryKey: readonly unknown[] = everything
        ? queryKeys.taskRoot(taskId)
        : [...queryKeys.taskRoot(taskId), "options"];
      void queryClient.invalidateQueries({ queryKey });
    };

    const scheduleInvalidate = (fromChild: boolean) => {
      if (!fromChild) parentPending = true;
      if (invalidateTimer !== null) clearTimeout(invalidateTimer);
      invalidateTimer = setTimeout(flushInvalidate, RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    };

    const flushIngestRefresh = () => {
      ingestTimer = null;
      void queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "evidence"] });
      void queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "landscape"] });
    };

    // Trailing throttle: the first ingest tick opens a window; later ticks
    // inside it are folded into the one refresh at its end.
    const scheduleIngestRefresh = () => {
      if (ingestTimer === null) ingestTimer = setTimeout(flushIngestRefresh, INGEST_REFRESH_THROTTLE_MS);
    };

    const connection = connectEventStream({
      taskId,
      getAccessToken: (forceRefresh) => auth.getAccessToken(forceRefresh),
      onUnauthenticated: () => auth.onUnauthenticated(),
      onConnected: () => {
        if (closed) return;
        setState((previous) => ({ ...previous, connectionStatus: "connected" }));
      },
      onDisconnected: () => {
        if (closed) return;
        setState((previous) => ({ ...previous, connectionStatus: "reconnecting" }));
      },
      onError: () => {
        if (closed) return;
        setState((previous) => ({ ...previous, connectionStatus: "reconnecting" }));
      },
      onFrame: (frame) => {
        if (closed) return;
        folded = reduceRunStreamFrame(folded, frame);
        setState((previous) => reduceRunStreamFrame(previous, frame));
        if (frame.type === "stage.completed" || frame.type === "run.status") {
          scheduleInvalidate(isOtherRunsStage(folded, frame.capability_run_id));
        } else if (frame.type === "tick" && frame.stage === "ingest") {
          scheduleIngestRefresh();
        }
      },
    });

    return () => {
      closed = true;
      if (invalidateTimer !== null) clearTimeout(invalidateTimer);
      if (ingestTimer !== null) clearTimeout(ingestTimer);
      connection.close();
    };
  }, [taskId, auth, queryClient, connect]);

  return state;
}
