import { Link } from "react-router";

import { Chip } from "../../../ui/brand/Chip";
import { useConversationMutations } from "./conversationState";

/** The optional entry artefact is relevance context, never a chat scope fence.
 *
 * Args:
 *   props: Conversation and entry-artefact identities.
 *
 * Returns:
 *   A removable artefact chip, or nothing when the chat has no entry
 *   context (owner live check, 2026-08-11: the "Whole task" zero-state
 *   label read as noise, not signal).
 */
export function ContextBar({ taskId, conversationId, entryArtefactId }: { taskId: string; conversationId: string; entryArtefactId: string | null }) {
  const { update } = useConversationMutations(taskId);
  if (entryArtefactId === null) return null;
  return <div className="flex items-center gap-2 border-t border-line px-4 py-2"><Link to={`/tasks/${taskId}/result`} className="hover:underline"><Chip tone="soft">Report</Chip></Link><button type="button" aria-label="Clear report context" onClick={() => void update(conversationId, { entry_artefact_id: null })} className="text-meta text-grey hover:text-navy">×</button></div>;
}
