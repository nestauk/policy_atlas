import { useState } from "react";
import { Link } from "react-router";

import { useComposerDraft } from "../../../store";
import { Chip } from "../../../ui/brand/Chip";
import { cn } from "../../../ui/brand/cn";
import { LIFECYCLE_PAGE_CLASS } from "../../listPageChrome";
import { Composer } from "../PlanningPane";
import { ChatEmptyState, starterQuestions } from "./ChatEmptyState";
import { DRAFT_CHAT_ID, stashFirstMessage, useConversationMutations } from "./conversationState";

/** A chat that does not exist yet (`?chat=new`, 038 V8).
 *
 * Looks like an empty chat — the invitation, the starter questions and the
 * composer — but nothing is persisted until the first message: sending
 * creates the conversation (with the entry artefact the draft carries, if
 * any), hands the message to the real `ChatPane` that mounts under the new
 * id, and moves the URL onto it. Abandoning the draft leaves no row behind.
 *
 * Args:
 *   props: The owning task, the optional entry artefact, the report's section
 *     titles for the starters, `wide` for the Agent tab's reading column, and
 *     `onCreated`, called with the new conversation id.
 *
 * Returns:
 *   The empty-chat surface with a live composer.
 */
export function DraftChatPane({
  taskId,
  entryArtefactId = null,
  sectionTitles = [],
  wide = false,
  onCreated,
}: {
  taskId: string;
  entryArtefactId?: string | null;
  sectionTitles?: readonly string[];
  wide?: boolean;
  onCreated: (conversationId: string) => void;
}) {
  const { create } = useConversationMutations(taskId);
  const [draft, setDraft] = useComposerDraft(`${DRAFT_CHAT_ID}:${taskId}`);
  const [submitting, setSubmitting] = useState(false);
  const column = wide ? LIFECYCLE_PAGE_CLASS : "px-4";

  const send = async (message: string) => {
    const trimmed = message.trim();
    if (trimmed.length === 0 || submitting) return;
    setSubmitting(true);
    try {
      const created = await create(entryArtefactId);
      stashFirstMessage(created.id, trimmed);
      setDraft("");
      onCreated(created.id);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section aria-label="Chat" className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto py-4 [scrollbar-gutter:stable]">
        <div className={cn("w-full", column)}>
          <ChatEmptyState
            message="Ask about the evidence."
            questions={starterQuestions(sectionTitles)}
            onAsk={(question) => void send(question)}
          />
        </div>
      </div>
      {entryArtefactId !== null && (
        <div className={cn("flex items-center gap-2 border-t border-line py-2", column)}>
          <Link to={`/tasks/${taskId}/result`} className="hover:underline">
            <Chip tone="soft">Report</Chip>
          </Link>
        </div>
      )}
      <div className={cn("border-t border-line py-4", column)}>
        <Composer
          id={`chat-message-${DRAFT_CHAT_ID}`}
          label="Message the Agent"
          value={draft}
          onChange={setDraft}
          onSubmit={() => void send(draft)}
          placeholder="Ask about the evidence"
          disabled={submitting}
          sendDisabled={submitting || draft.trim().length === 0}
        />
      </div>
    </section>
  );
}
