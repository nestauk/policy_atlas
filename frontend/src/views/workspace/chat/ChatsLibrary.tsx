import { ConversationList, type ConversationRow } from "./ConversationList";
import { addOpenChatTab, useActiveConversation } from "./conversationState";
import { CloseIcon } from "./icons";

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
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Chats"
      className="absolute inset-x-2 top-2 z-20 flex max-h-[calc(100%-16px)] flex-col overflow-hidden border border-line bg-paper-2 shadow-[0_8px_24px_-8px_rgba(15,41,74,0.25)]"
    >
      <div className="flex shrink-0 items-center justify-between px-2 pt-2 pb-1">
        <h2 className="pl-1.5 text-caption font-bold uppercase tracking-label text-grey">Chats</h2>
        <button
          type="button"
          aria-label="Close chats"
          title="Close"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center text-grey hover:bg-blue-tint-2 hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          <CloseIcon size={14} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-3">
        <ConversationList taskId={taskId} onOpen={openRow} />
      </div>
    </div>
  );
}
