import { useMemo } from "react";

import { useConversation } from "../../../api/queries";
import { useChatConversation } from "../../../store";
import { ChatComposer } from "./ChatComposer";
import { ChatMessages } from "./ChatMessages";
import { ContextBar } from "./ContextBar";

/** Compose one URL-addressable chat conversation in the workspace rail.
 *
 * Args:
 *   props: Conversation identity, optional starter section titles, and hand-off.
 *
 * Returns:
 *   A transcript, context bar, and composer.
 */
export function ChatPane({ projectId, conversationId, sectionTitles = [], onOpenPlanning }: { projectId: string; conversationId: string; sectionTitles?: string[]; onOpenPlanning: () => void }) {
  const conversation = useConversation(conversationId);
  const chat = useChatConversation(conversationId);
  const starterQuestions = useMemo(() => sectionTitles.slice(0, 3).map((title) => `What does ${title} show?`), [sectionTitles]);
  const durableRows = chat.rows.filter(
    (row): row is Extract<(typeof chat.rows)[number], { id: string }> => "id" in row,
  );
  const pendingTurnId = durableRows.find((row) => row.status === "pending")?.id;
  // A pending durable turn with no local stream (a reload mid-answer, or a
  // second tab) still fences a send server-side — say so up front instead of
  // letting the composer accept input the server will just reject.
  const disabledReason = !chat.isStreaming && pendingTurnId !== undefined ? "Waiting for the current answer…" : null;
  const send = (message: string) => { void chat.sendTurn(message).catch(() => undefined); };
  const retry = (clientTurnId: string) => { void chat.retry(clientTurnId); };
  const cancel = async () => {
    if (pendingTurnId !== undefined) return void chat.cancelTurn(pendingTurnId);
    // Mid-stream the durable row may not be in the cache yet — resolve it by
    // the optimistic turn's idempotency key, the id the client actually owns.
    const optimistic = chat.optimisticTurns.find(
      (turn): turn is Extract<(typeof chat.optimisticTurns)[number], { clientTurnId: string }> =>
        "clientTurnId" in turn && turn.status === "pending",
    );
    if (optimistic === undefined) return;
    if (optimistic.turnId !== undefined) return void chat.cancelTurn(optimistic.turnId);
    const page = await chat.refetch();
    const row = page.data?.data.find(
      (candidate) => candidate.client_turn_id === optimistic.clientTurnId && candidate.status === "pending",
    );
    if (row !== undefined) void chat.cancelTurn(row.id);
  };
  const empty = !chat.isPending && chat.rows.length === 0;
  return <section aria-label="Chat" className="flex h-full min-h-0 flex-col"><div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{empty ? <div className="space-y-2 py-8"><p className="text-meta text-grey">Ask about the evidence.</p>{starterQuestions.map((question) => <button key={question} type="button" onClick={() => send(question)} className="block text-left text-meta font-semibold text-blue hover:underline">{question}</button>)}</div> : <ChatMessages projectId={projectId} rows={chat.rows} onOpenPlanning={onOpenPlanning} onRetry={retry} />}</div><ContextBar projectId={projectId} conversationId={conversationId} entryArtefactId={conversation.data?.entry_artefact_id ?? null} /><div className="border-t border-line p-4"><ChatComposer conversationId={conversationId} isStreaming={chat.isStreaming} disabledReason={disabledReason} onSend={send} onStop={() => void cancel()} /></div></section>;
}
