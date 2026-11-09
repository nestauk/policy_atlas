import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { queryKeys, useApiClient } from "../../api/queries";

/** How long the shortlist page waits after the last change before it asks
 *  for a fresh "Not covered" note (owner, 2026-11-08). */
export const NOTE_REFRESH_PAUSE_MS = 3000;

/** The working line while the note is rewritten (owner, 2026-11-08). */
export const NOTE_REVIEWING_WORDS = "Reviewing the shortlist for gaps";

type UntypedPost = (path: string, init: object) => Promise<{ error?: unknown; response: Response }>;

/** `POST .../shortlist/note`: rewrites the not-covered note when it is
 *  stale; the longlist read then carries the new note. */
export function useRefreshShortlistNote(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      // ponytail: untyped until the generated client carries the route.
      const post = client.POST.bind(client) as unknown as UntypedPost;
      const { error, response } = await post("/api/v1/tasks/{task_id}/shortlist/note", {
        params: { path: { task_id: taskId } },
      });
      if (!response.ok) throw error ?? new Error("The note could not be rewritten.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...queryKeys.taskRoot(taskId), "longlist"] }),
  });
}

/**
 * Keep the shortlist's note current without a call per change (owner,
 * 2026-11-08): on opening, a stale note is rewritten once; after a change
 * on the page, one timer waits `NOTE_REFRESH_PAUSE_MS` after the last change
 * and rewrites it once if it is still stale. Unmounting cancels the timer.
 * Off on the public link. The longlist never calls it.
 *
 * Args:
 *   refresh: Starts the rewrite (the mutation's `mutate`).
 *   stale: Whether the read says the note is stale.
 *   changes: The shortlist's places as one string; a new value is a change.
 *   enabled: False on the public link.
 */
export function useNoteRefresh(refresh: () => void, stale: boolean, changes: string, enabled: boolean) {
  const latest = useRef({ refresh, stale });
  const opened = useRef(false);
  useEffect(() => {
    latest.current = { refresh, stale };
  });
  useEffect(() => {
    if (!enabled) return;
    if (!opened.current) {
      opened.current = true;
      if (latest.current.stale) latest.current.refresh();
      return;
    }
    const timer = window.setTimeout(() => {
      if (latest.current.stale) latest.current.refresh();
    }, NOTE_REFRESH_PAUSE_MS);
    return () => window.clearTimeout(timer);
  }, [changes, enabled]);
}
