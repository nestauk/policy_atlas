import { useCallback } from "react";
import { useSearchParams } from "react-router";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import type { components } from "../../../api/gen/types";
import { queryKeys, useApiClient } from "../../../api/queries";

type ConversationOut = components["schemas"]["ConversationOut"];
type ConversationListPage = components["schemas"]["Page_ConversationListItemOut_"];

const OPEN_TABS_PREFIX = "policy-atlas.open-chat-tabs.";

/** URL token for the planning thread in the chat overlay (`?chat=planning`)
 *  when the task has no planning-conversation row yet. */
export const PLANNING_TAB_ID = "planning";

/** The planning conversation to select in the overlay strip — the newest
 *  planning row, or `PLANNING_TAB_ID` when none exists yet. */
export function planningConversationId(
  rows: ReadonlyArray<{ id: string; kind: string }>,
): string {
  return rows.find((row) => row.kind === "planning")?.id ?? PLANNING_TAB_ID;
}

/** True when the overlay is showing the planning thread, not a follow-up chat. */
export function isPlanningConversation(
  conversationId: string | null,
  rows: ReadonlyArray<{ id: string; kind: string }>,
): boolean {
  if (conversationId === null) return false;
  if (conversationId === PLANNING_TAB_ID) return true;
  return rows.find((row) => row.id === conversationId)?.kind === "planning";
}

/** Read and update the URL-addressable active conversation.
 *
 * Returns:
 *   The selected chat id (or planning) and a URL-preserving setter.
 */
export function useActiveConversation() {
  const [searchParams, setSearchParams] = useSearchParams();
  // `?chat=` (present but empty) must read as closed, not as a panel bound
  // to conversation id "" — align with AppShell's own `chatOpen` check.
  const activeConversationId = searchParams.get("chat") || null;
  const setActiveConversation = useCallback((conversationId: string | null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (conversationId === null) next.delete("chat");
      else next.set("chat", conversationId);
      return next;
    });
  }, [setSearchParams]);
  return { activeConversationId, setActiveConversation };
}

/** Return the session-local open chat ids for a task.
 *
 * Args:
 *   taskId: Owning task for the browser-session key.
 *
 * Returns:
 *   Chat ids in tab-strip order.
 */
export function openChatTabs(taskId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(tabKey(taskId)) ?? "[]");
    return Array.isArray(stored) ? stored.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

/** Add one chat to the session-local tab strip.
 *
 * Args:
 *   taskId: Owning task for the browser-session key.
 *   conversationId: Chat to make available in the strip.
 */
export function addOpenChatTab(taskId: string, conversationId: string) {
  writeOpenChatTabs(taskId, [...openChatTabs(taskId).filter((id) => id !== conversationId), conversationId]);
}

/** Remove one chat from the session-local tab strip.
 *
 * Args:
 *   taskId: Owning task for the browser-session key.
 *   conversationId: Chat to remove from the strip.
 */
export function removeOpenChatTab(taskId: string, conversationId: string) {
  writeOpenChatTabs(taskId, openChatTabs(taskId).filter((id) => id !== conversationId));
}

/** Small client-side mutations kept outside the read-only G1 stream store.
 *
 * Args:
 *   taskId: Project whose conversation lists need invalidation.
 *
 * Returns:
 *   Create, archive, restore, and update operations.
 */
export function useConversationMutations(taskId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    // The 3-element prefix, not `queryKeys.conversations(taskId)`: that
    // filtered key carries explicit `undefined` kind/status, which never
    // partial-matches a consumer's `{ kind: "chat", status: "active" }` key.
    void queryClient.invalidateQueries({ queryKey: queryKeys.conversationsRoot(taskId) });
  }, [taskId, queryClient]);

  const create = useCallback(async (entryArtefactId: string | null) => {
    const { data, error } = await client.POST("/api/v1/tasks/{task_id}/conversations", {
      params: { path: { task_id: taskId } },
      body: entryArtefactId === null ? {} : { entry_artefact_id: entryArtefactId },
    });
    if (data === undefined) throw error;
    // Write the row into the list cache before invalidate-refetch, or the
    // tab strip filters it out (id in session storage, not yet in `data`)
    // and the composer still sends against a conversation the strip doesn't
    // show.
    seedCreatedConversation(queryClient, taskId, data);
    refresh();
    return data;
  }, [client, taskId, queryClient, refresh]);

  const archive = useCallback(async (conversationId: string) => {
    const { data, error } = await client.POST("/api/v1/conversations/{conversation_id}/archive", {
      params: { path: { conversation_id: conversationId } },
    });
    if (data === undefined) throw error;
    refresh();
    return data;
  }, [client, refresh]);

  const unarchive = useCallback(async (conversationId: string) => {
    const { data, error } = await client.POST("/api/v1/conversations/{conversation_id}/unarchive", {
      params: { path: { conversation_id: conversationId } },
    });
    if (data === undefined) throw error;
    refresh();
    return data;
  }, [client, refresh]);

  const update = useCallback(async (conversationId: string, body: { title?: string; entry_artefact_id?: string | null }) => {
    const { data, error } = await client.PATCH("/api/v1/conversations/{conversation_id}", {
      params: { path: { conversation_id: conversationId } },
      body,
    });
    if (data === undefined) throw error;
    refresh();
    void queryClient.invalidateQueries({ queryKey: queryKeys.conversation(conversationId) });
    return data;
  }, [client, queryClient, refresh]);

  return { create, archive, unarchive, update };
}

function seedCreatedConversation(
  queryClient: QueryClient,
  taskId: string,
  created: ConversationOut,
) {
  const item = { ...created, latest_turn_preview: null };
  queryClient.setQueriesData(
    { queryKey: queryKeys.conversationsRoot(taskId) },
    (current: ConversationListPage | undefined) => {
      if (current == null || !Array.isArray(current.data)) return current;
      if (current.data.some((row) => row.id === created.id)) return current;
      return { ...current, data: [item, ...current.data] };
    },
  );
  queryClient.setQueryData(queryKeys.conversation(created.id), created);
}

function tabKey(taskId: string) {
  return `${OPEN_TABS_PREFIX}${taskId}`;
}

function writeOpenChatTabs(taskId: string, ids: string[]) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(tabKey(taskId), JSON.stringify(ids));
  } catch {
    // Tabs are a session convenience; storage failures are non-fatal.
  }
}
