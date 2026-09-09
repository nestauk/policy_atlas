import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { connectEventStream } from "../api/sse";
import { useAuth } from "../auth";
import { createInitialRunStreamState } from "./types";
import { reduceRunStreamFrame } from "./reducer";
import type { RunStreamState } from "./types";

/**
 * React binding for one task's run stream: opens the authed SSE
 * connection, folds every frame through the pure reducer, and invalidates
 * the read-model queries for this task whenever a `stage.completed` or
 * `run.status` frame lands (both mark points where a read model may have
 * moved). A fresh mount/reconnect always starts from `cursor=0` — the
 * reducer's replay idempotence is what makes that safe.
 */
export function useRunStream(taskId: string): RunStreamState {
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
    // Guards against a frame from THIS effect's connection landing after
    // its cleanup has run but before the closure is torn down — without
    // this, such a frame would fold into the next task's already-reset
    // state (a stale-connection race at the task-switch boundary).
    let closed = false;

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
        setState((previous) => reduceRunStreamFrame(previous, frame));
        if (frame.type === "stage.completed" || frame.type === "run.status") {
          void queryClient.invalidateQueries({
            predicate: (query) => query.queryKey[0] === "tasks" && query.queryKey[1] === taskId,
          });
        }
      },
    });

    return () => {
      closed = true;
      connection.close();
    };
  }, [taskId, auth, queryClient]);

  return state;
}
