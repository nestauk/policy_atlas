import { useEffect, useMemo } from "react";

import { useConversation } from "../../../api/queries";
import { useChatConversation } from "../../../store";
import { cn } from "../../../ui/brand/cn";
import { LIFECYCLE_PAGE_CLASS } from "../../listPageChrome";
import { ChatComposer } from "./ChatComposer";
import { ChatEmptyState, starterQuestions } from "./ChatEmptyState";
import { ChatMessages } from "./ChatMessages";
import { ContextBar } from "./ContextBar";
import { takeFirstMessage } from "./conversationState";
import { useFooterReveal } from "./useFooterReveal";

/** Compose one URL-addressable chat conversation — in the overlay, or wide
 *  in the Agent tab's main column.
 *
 * Args:
 *   props: Conversation identity, optional starter section titles, the
 *     hand-off to the planning thread, `wide` for the Agent tab's reading
 *     column, and `onAtBottomChange`, reporting the reader's deliberate
 *     scroll past the transcript's end so the tab can reveal the footer.
 *
 * Returns:
 *   A transcript, context bar, and composer.
 */
export function ChatPane({
  taskId,
  conversationId,
  sectionTitles = [],
  onOpenPlanning,
  wide = false,
  onAtBottomChange,
}: {
  taskId: string;
  conversationId: string;
  sectionTitles?: string[];
  onOpenPlanning: () => void;
  wide?: boolean;
  onAtBottomChange?: (atBottom: boolean) => void;
}) {
  const conversation = useConversation(conversationId);
  const chat = useChatConversation(conversationId);
  const starters = useMemo(() => starterQuestions(sectionTitles), [sectionTitles]);
  const durableRows = chat.rows.filter(
    (row): row is Extract<(typeof chat.rows)[number], { id: string }> => "id" in row,
  );
  const pendingTurnId = durableRows.find((row) => row.status === "pending")?.id;
  // A pending durable turn with no local stream (a reload mid-answer, or a
  // second tab) still fences a send server-side — say so up front instead of
  // letting the composer accept input the server will just reject.
  const disabledReason = conversation.isError
    ? "This chat couldn't be opened."
    : !chat.isStreaming && pendingTurnId !== undefined
      ? "Waiting for the current answer…"
      : null;
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

  // A draft chat hands its first message over as it becomes this chat (038
  // V8): send it once, on mount under the new id. `sendTurn` is the store's
  // stable callback for this conversation, so the effect keys on it honestly.
  const { sendTurn } = chat;
  useEffect(() => {
    const first = takeFirstMessage(conversationId);
    if (first !== null) void sendTurn(first).catch(() => undefined);
  }, [conversationId, sendTurn]);

  const footer = useFooterReveal(onAtBottomChange);

  const empty = !chat.isPending && chat.rows.length === 0;
  const column = wide ? LIFECYCLE_PAGE_CLASS : "px-4";
  return (
    <section aria-label="Chat" className="flex h-full min-h-0 flex-col">
      <div
        onScroll={footer.onScroll}
        onWheel={footer.onWheel}
        className="min-h-0 flex-1 overflow-y-auto py-4 [scrollbar-gutter:stable]"
      >
        <div className={cn("w-full", column)}>
          {empty ? (
            <ChatEmptyState
              message={conversation.isError ? "This chat couldn't be opened." : "Ask about the evidence."}
              questions={conversation.isError ? [] : starters}
              onAsk={send}
            />
          ) : (
            <ChatMessages taskId={taskId} rows={chat.rows} onOpenPlanning={onOpenPlanning} onRetry={retry} />
          )}
        </div>
      </div>
      <div className={cn("w-full", column)}>
        <ContextBar
          taskId={taskId}
          conversationId={conversationId}
          entryArtefactId={conversation.data?.entry_artefact_id ?? null}
        />
      </div>
      <div className="border-t border-line">
        <div className={cn("w-full py-4", column)}>
          <ChatComposer
            conversationId={conversationId}
            isStreaming={chat.isStreaming}
            disabledReason={disabledReason}
            onSend={send}
            onStop={() => void cancel()}
          />
        </div>
      </div>
    </section>
  );
}
