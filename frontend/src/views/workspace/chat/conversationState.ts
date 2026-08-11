import { useCallback } from "react";
import { useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys, useApiClient } from "../../../api/queries";

const OPEN_TABS_PREFIX = "policy-atlas.open-chat-tabs.";

/** Read and update the URL-addressable active conversation.
 *
 * Returns:
 *   The selected chat id (or planning) and a URL-preserving setter.
 */
export function useActiveConversation() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeConversationId = searchParams.get("chat");
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

/** Return the session-local open chat ids for a project.
 *
 * Args:
 *   projectId: Owning project for the browser-session key.
 *
 * Returns:
 *   Chat ids in tab-strip order.
 */
export function openChatTabs(projectId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(tabKey(projectId)) ?? "[]");
    return Array.isArray(stored) ? stored.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

/** Add one chat to the session-local tab strip.
 *
 * Args:
 *   projectId: Owning project for the browser-session key.
 *   conversationId: Chat to make available in the strip.
 */
export function addOpenChatTab(projectId: string, conversationId: string) {
  writeOpenChatTabs(projectId, [...openChatTabs(projectId).filter((id) => id !== conversationId), conversationId]);
}

/** Remove one chat from the session-local tab strip.
 *
 * Args:
 *   projectId: Owning project for the browser-session key.
 *   conversationId: Chat to remove from the strip.
 */
export function removeOpenChatTab(projectId: string, conversationId: string) {
  writeOpenChatTabs(projectId, openChatTabs(projectId).filter((id) => id !== conversationId));
}

/** Small client-side mutations kept outside the read-only G1 stream store.
 *
 * Args:
 *   projectId: Project whose conversation lists need invalidation.
 *
 * Returns:
 *   Create, archive, restore, and update operations.
 */
export function useConversationMutations(projectId: string) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.conversations(projectId) });
  }, [projectId, queryClient]);

  const create = useCallback(async (entryArtefactId: string | null) => {
    const { data, error } = await client.POST("/api/v1/projects/{project_id}/conversations", {
      params: { path: { project_id: projectId } },
      body: entryArtefactId === null ? {} : { entry_artefact_id: entryArtefactId },
    });
    if (data === undefined) throw error;
    refresh();
    return data;
  }, [client, projectId, refresh]);

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

function tabKey(projectId: string) {
  return `${OPEN_TABS_PREFIX}${projectId}`;
}

function writeOpenChatTabs(projectId: string, ids: string[]) {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(tabKey(projectId), JSON.stringify(ids));
  } catch {
    // Tabs are a session convenience; storage failures are non-fatal.
  }
}
