import { ConversationList, type ConversationRow } from "./ConversationList";
import { addOpenChatTab, useActiveConversation } from "./conversationState";

/** The overlay's chats library: the shared conversation list in a dialog.
 *
 * The Agent tab mounts `ConversationList` directly as its sidebar; this is
 * the same list for the other tabs, where the overlay has no room to keep it
 * on screen.
 *
 * Args:
 *   props: Task identity and overlay visibility controls.
 *
 * Returns:
 *   The conversation library when open.
 */
export function ChatsLibrary({ taskId, open, onClose }: { taskId: string; open: boolean; onClose: () => void }) {
  const { setActiveConversation } = useActiveConversation();
  if (!open) return null;

  const openRow = (row: ConversationRow) => {
    if (row.kind !== "planning") addOpenChatTab(taskId, row.id);
    setActiveConversation(row.id);
    onClose();
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Chats" className="absolute inset-x-3 top-3 z-20 max-h-[calc(100%-24px)] overflow-y-auto border border-line bg-paper p-4 shadow-lg">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-heading font-bold text-navy">Chats</h2><button type="button" aria-label="Close chats" onClick={onClose}>×</button></div>
      <ConversationList taskId={taskId} onOpen={openRow} />
    </div>
  );
}
