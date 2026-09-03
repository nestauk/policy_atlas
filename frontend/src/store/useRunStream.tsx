import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { connectEventStream } from "../api/sse";
import { useAuth } from "../auth";
import { createInitialRunStreamState } from "./types";
import { reduceRunStreamFrame } from "./reducer";
import type { RunStreamState } from "./types";

/**
 * Trailing window for collapsing bursty `stage.completed` / `run.status`
 * invalidations — especially the full-history replay on a cold connect —
 * into one read-model refresh instead of one per frame.
 */
export const RUN_STREAM_INVALIDATE_DEBOUNCE_MS = 300;

interface RunStreamContextValue {
  projectId: string;
  state: RunStreamState;
}

const RunStreamContext = createContext<RunStreamContextValue | null>(null);

/**
 * Own the project's SSE connection at the task shell so Plan / Results /
 * Sources / History / Share share one replay-then-tail stream instead of
 * each leaf remount reconnecting from `cursor=0` (and storming read-model
 * invalidations mid-replay).
 *
 * Args:
 *   projectId: The open task. Changing it resets the reducer and opens a
 *     fresh connection for the new project.
 *   children: Shell chrome and the routed task view.
 */
export function RunStreamProvider({
  projectId,
  children,
}: {
  projectId: string;
  children: ReactNode;
}) {
  const state = useRunStreamConnection(projectId);
  return (
    <RunStreamContext.Provider value={{ projectId, state }}>
      {children}
    </RunStreamContext.Provider>
  );
}

/**
 * Read the shell-owned run stream for this project.
 *
 * Args:
 *   projectId: Must match the surrounding `RunStreamProvider`.
 *
 * Returns:
 *   The live reducer state for the project's event stream.
 *
 * Raises:
 *   Error when called outside a provider, or for a different project id.
 */
export function useRunStream(projectId: string): RunStreamState {
  const ctx = useContext(RunStreamContext);
  if (ctx === null) {
    throw new Error("useRunStream must be used within a RunStreamProvider");
  }
  if (ctx.projectId !== projectId) {
    throw new Error(
      `useRunStream(${projectId}) does not match RunStreamProvider(${ctx.projectId})`,
    );
  }
  return ctx.state;
}

/**
 * Open one authed SSE connection, fold frames through the pure reducer, and
 * coalesce read-model invalidations on `stage.completed` / `run.status`. A
 * fresh mount/reconnect always starts from `cursor=0` — the reducer's replay
 * idempotence is what makes that safe.
 */
function useRunStreamConnection(projectId: string): RunStreamState {
  const auth = useAuth();
  const queryClient = useQueryClient();

  const [state, setState] = useState<RunStreamState>(createInitialRunStreamState);

  // Reset the store when `projectId` changes, following React's documented
  // "adjust state during render" pattern rather than an effect — this runs
  // synchronously during render (before paint) exactly when the state on
  // hand no longer belongs to the current project.
  const [stateProjectId, setStateProjectId] = useState(projectId);
  if (stateProjectId !== projectId) {
    setStateProjectId(projectId);
    setState(createInitialRunStreamState());
  }

  useEffect(() => {
    // Guards against a frame from THIS effect's connection landing after
    // its cleanup has run but before the closure is torn down — without
    // this, such a frame would fold into the next project's already-reset
    // state (a stale-connection race at the project-switch boundary).
    let closed = false;
    let invalidateTimer: ReturnType<typeof setTimeout> | null = null;

    const flushInvalidate = () => {
      invalidateTimer = null;
      void queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] === "projects" && query.queryKey[1] === projectId,
      });
    };

    const scheduleInvalidate = () => {
      if (invalidateTimer !== null) clearTimeout(invalidateTimer);
      invalidateTimer = setTimeout(flushInvalidate, RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    };

    const connection = connectEventStream({
      projectId,
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
        setState((previous) => reduceRunStreamFrame(previous, frame));
        if (frame.type === "stage.completed" || frame.type === "run.status") {
          scheduleInvalidate();
        }
      },
    });

    return () => {
      closed = true;
      if (invalidateTimer !== null) clearTimeout(invalidateTimer);
      connection.close();
    };
  }, [projectId, auth, queryClient]);

  return state;
}
