import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { connectEventStream } from "../api/sse";
import { useAuth } from "../auth";
import { createInitialRunStreamState } from "./types";
import { reduceRunStreamFrame } from "./reducer";
import type { RunStreamState } from "./types";

/**
 * React binding for one project's run stream: opens the authed SSE
 * connection, folds every frame through the pure reducer, and invalidates
 * the read-model queries for this project whenever a `stage.completed` or
 * `run.status` frame lands (both mark points where a read model may have
 * moved). A fresh mount/reconnect always starts from `cursor=0` — the
 * reducer's replay idempotence is what makes that safe.
 */
export function useRunStream(projectId: string): RunStreamState {
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
    const connection = connectEventStream({
      projectId,
      getAccessToken: (forceRefresh) => auth.getAccessToken(forceRefresh),
      onUnauthenticated: () => auth.onUnauthenticated(),
      onConnected: () => {
        setState((previous) => ({ ...previous, connectionStatus: "connected" }));
      },
      onDisconnected: () => {
        setState((previous) => ({ ...previous, connectionStatus: "reconnecting" }));
      },
      onError: () => {
        setState((previous) => ({ ...previous, connectionStatus: "reconnecting" }));
      },
      onFrame: (frame) => {
        setState((previous) => reduceRunStreamFrame(previous, frame));
        if (frame.type === "stage.completed" || frame.type === "run.status") {
          void queryClient.invalidateQueries({
            predicate: (query) => query.queryKey[0] === "projects" && query.queryKey[1] === projectId,
          });
        }
      },
    });

    return () => connection.close();
  }, [projectId, auth, queryClient]);

  return state;
}
