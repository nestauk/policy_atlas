import { useCallback } from "react";
import { useSearchParams } from "react-router";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import type { components } from "../../../api/gen/types";
import { queryKeys, useApiClient } from "../../../api/queries";

type ConversationOut = components["schemas"]["ConversationOut"];
type ConversationListPage = components["schemas"]["Page_ConversationListItemOut_"];

/** URL token for the planning thread in the chat overlay (`?chat=planning`)
 *  when the task has no planning-conversation row yet. */
export const PLANNING_TAB_ID = "planning";

/** URL token for a chat that does not exist yet (`?chat=new`, 038 V8): the
 *  reader sees an empty chat and a composer, and the row is created on the
 *  first message — never before, so an abandoned "New chat" leaves nothing
 *  behind. */
export const DRAFT_CHAT_ID = "new";

const firstMessages = new Map<string, string>();

/** Hand the draft's first message to the chat that is about to mount under
 *  its real id; `takeFirstMessage` returns it once and forgets it. The chat
 *  takes it one tick after mounting (see `ChatPane`), so a StrictMode
 *  rehearsal — mount, cleanup, mount — sends it exactly once. */
export function stashFirstMessage(conversationId: string, message: string) {
  firstMessages.set(conversationId, message);
}

export function takeFirstMessage(conversationId: string): string | null {
  const message = firstMessages.get(conversationId) ?? null;
  firstMessages.delete(conversationId);
  return message;
}

/** The Task Agent: a Task's primary chat.
 *
 * The `kind = planning` conversation — the open one, or, once a run has
 * closed that lineage, the most recently closed one (contract 038 § Terms).
 * Exactly one row is ever the Task Agent (invariant I8 / fold A10); older
 * closed lineages are "Earlier plan" and are never pinned. No new state:
 * this is a selection rule over the rows the listing already returns.
 *
 * Args:
 *   rows: The task's listed conversations, newest created first.
 *
 * Returns:
 *   The Task Agent's conversation id, or `PLANNING_TAB_ID` when the task has
 *   no planning row yet.
 */
export function taskAgentConversationId(
  rows: ReadonlyArray<{ id: string; kind: string; closed_at?: string | null }>,
): string {
  const planning = rows.filter((row) => row.kind === "planning");
  const open = planning.find((row) => (row.closed_at ?? null) === null);
  if (open !== undefined) return open.id;
  // Newest closure wins. `rows` arrives created_at-descending, so rows
  // carrying no closure time keep that order behind the ones that do.
  return [...planning].sort((a, b) => (b.closed_at ?? "").localeCompare(a.closed_at ?? ""))[0]?.id
    ?? PLANNING_TAB_ID;
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
  // A draft chat may carry the artefact it is about (`?chat=new&entry=<id>`).
  const draftEntryArtefactId = activeConversationId === DRAFT_CHAT_ID ? searchParams.get("entry") || null : null;
  const setActiveConversation = useCallback((conversationId: string | null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("entry");
      if (conversationId === null) next.delete("chat");
      else next.set("chat", conversationId);
      return next;
    });
  }, [setSearchParams]);
  const openDraftChat = useCallback((entryArtefactId: string | null = null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("chat", DRAFT_CHAT_ID);
      if (entryArtefactId === null) next.delete("entry");
      else next.set("entry", entryArtefactId);
      return next;
    });
  }, [setSearchParams]);
  return { activeConversationId, draftEntryArtefactId, setActiveConversation, openDraftChat };
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
    // Write the row into the list cache before invalidate-refetch, so the
    // sidebar and the overlay header show the new chat on the first paint.
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
    {
      queryKey: queryKeys.conversationsRoot(taskId),
      // The prefix reaches every filtered list — including the ARCHIVED
      // one, which a brand-new conversation has no business appearing in.
      // Left unfiltered it flashes under "Archived" for as long as that
      // list takes to refetch (seen in the library once the Agent tab's
      // sidebar started keeping the archived list in cache).
      predicate: (query) => query.queryKey[4] !== "archived",
    },
    (current: ConversationListPage | undefined) => {
      if (current == null || !Array.isArray(current.data)) return current;
      if (current.data.some((row) => row.id === created.id)) return current;
      return { ...current, data: [item, ...current.data] };
    },
  );
  queryClient.setQueryData(queryKeys.conversation(created.id), created);
}
