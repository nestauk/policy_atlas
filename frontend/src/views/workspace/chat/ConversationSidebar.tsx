import { Button } from "../../../ui/brand/Button";
import { ConversationList, type ConversationRow } from "./ConversationList";
import { addOpenChatTab, useConversationMutations } from "./conversationState";

/** The Agent tab's left column: every conversation in the Task, always on
 *  screen (038 V8, owner ruling 2026-09-05).
 *
 * Selection is the route's own `?chat=` param, which the other tabs' overlay
 * shares — so a chat opened here is the chat that opens there. The Task
 * Agent carries no id in the URL: choosing it clears the param.
 *
 * Args:
 *   props: The owning task, the id the main view is showing (the Task Agent
 *     when the param is clear), and `onSelect`, called with the conversation
 *     to show — `null` for the Task Agent.
 *
 * Returns:
 *   The new-chat action above the shared conversation list.
 */
export function ConversationSidebar({
  taskId,
  selectedId,
  onSelect,
}: {
  taskId: string;
  selectedId: string | null;
  onSelect: (conversationId: string | null) => void;
}) {
  const { create } = useConversationMutations(taskId);

  const open = (row: ConversationRow) => {
    // Any planning row resolves to the Task Agent: the pane renders the
    // Task's planning thread, never one lineage in isolation, so an id in
    // the URL would claim more than the view delivers.
    if (row.kind === "planning") return onSelect(null);
    addOpenChatTab(taskId, row.id);
    onSelect(row.id);
  };
  const newChat = async () => {
    const created = await create(null);
    addOpenChatTab(taskId, created.id);
    onSelect(created.id);
  };

  return (
    <aside
      aria-label="Chats"
      className="flex w-full shrink-0 flex-col overflow-hidden border-b border-line bg-paper lg:h-full lg:w-80 lg:border-b-0 lg:border-r"
    >
      <div className="flex shrink-0 items-center justify-between border-b border-line px-4 py-3">
        <h2 className="font-display text-lead font-bold text-navy">Chats</h2>
        <Button size="sm" variant="secondary" onClick={() => void newChat()}>
          New chat
        </Button>
      </div>
      {/* Narrow viewports stack the list above the conversation and cap its
          height; from `lg` it is the full-height column. */}
      <div className="max-h-64 min-h-0 flex-1 overflow-y-auto px-4 pb-4 lg:max-h-none">
        <ConversationList taskId={taskId} onOpen={open} selectedId={selectedId} />
      </div>
    </aside>
  );
}
