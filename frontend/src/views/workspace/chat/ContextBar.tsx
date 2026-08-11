import { Link } from "react-router";

import { Chip } from "../../../ui/brand/Chip";
import { useConversationMutations } from "./conversationState";

/** The optional entry artefact is relevance context, never a chat scope fence.
 *
 * Args:
 *   props: Conversation and entry-artefact identities.
 *
 * Returns:
 *   A removable artefact chip or the whole-project state.
 */
export function ContextBar({ projectId, conversationId, entryArtefactId }: { projectId: string; conversationId: string; entryArtefactId: string | null }) {
  const { update } = useConversationMutations(projectId);
  if (entryArtefactId === null) return <div className="border-t border-line px-4 py-2 text-caption text-grey">Whole project</div>;
  return <div className="flex items-center gap-2 border-t border-line px-4 py-2"><Link to={`/projects/${projectId}/evidence-base`} className="hover:underline"><Chip tone="soft">Evidence base</Chip></Link><button type="button" aria-label="Clear evidence base context" onClick={() => void update(conversationId, { entry_artefact_id: null })} className="text-caption text-grey hover:text-navy">×</button></div>;
}
