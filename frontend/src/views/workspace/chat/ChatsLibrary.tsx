import { useState } from "react";

import { useConversations } from "../../../api/queries";
import type { components } from "../../../api/gen/types";
import { scrub } from "../../../lib/scrub";
import { Chip } from "../../../ui/brand/Chip";
import { addOpenChatTab, useActiveConversation, useConversationMutations } from "./conversationState";

type LibraryRow = components["schemas"]["ConversationListItemOut"];

/** Overlay listing active and archived task chats.
 *
 * Args:
 *   props: Project identity and overlay visibility controls.
 *
 * Returns:
 *   The active and archived conversation library when open.
 */
export function ChatsLibrary({ taskId, open, onClose }: { taskId: string; open: boolean; onClose: () => void }) {
  const active = useConversations(taskId, { status: "active" });
  const archived = useConversations(taskId, { status: "archived" });
  const { setActiveConversation } = useActiveConversation();
  const { archive, unarchive, update } = useConversationMutations(taskId);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  if (!open) return null;

  const openRow = (row: LibraryRow) => {
    if (row.kind !== "planning") addOpenChatTab(taskId, row.id);
    setActiveConversation(row.id);
    onClose();
  };
  const startRename = (row: LibraryRow) => {
    setEditing(row.id);
    setTitle(row.title);
  };
  const commitRename = async (id: string) => {
    if (title.trim()) await update(id, { title: title.trim() });
    setEditing(null);
  };

  // A planning row never archives (no control fires it), but guard the
  // restore-and-open path anyway so a synthetically-archived planning row
  // isn't routed through the chat-only unarchive+open flow.
  const openArchivedRow = (row: LibraryRow) =>
    row.kind === "planning" ? openRow(row) : void unarchive(row.id).then(() => openRow(row));

  return (
    <div role="dialog" aria-modal="true" aria-label="Chats" className="absolute inset-x-3 top-3 z-20 max-h-[calc(100%-24px)] overflow-y-auto border border-line bg-paper p-4 shadow-lg">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-heading font-bold text-navy">Chats</h2><button type="button" aria-label="Close chats" onClick={onClose}>×</button></div>
      <LibraryGroups rows={active.data?.data ?? []} onOpen={openRow} editing={editing} title={title} setTitle={setTitle} onRename={startRename} onCommit={commitRename} onArchive={(id) => void archive(id)} />
      {(archived.data?.data.length ?? 0) > 0 && <><h3 className="mt-5 border-b border-line pb-1 text-meta font-bold uppercase tracking-[0.06em] text-grey">Archived</h3><LibraryGroups rows={archived.data?.data ?? []} onOpen={openArchivedRow} editing={editing} title={title} setTitle={setTitle} onRename={startRename} onCommit={commitRename} onArchive={(id) => void unarchive(id)} archived /></>}
    </div>
  );
}

function LibraryGroups({ rows, ...props }: { rows: LibraryRow[]; onOpen: (row: LibraryRow) => void; editing: string | null; title: string; setTitle: (value: string) => void; onRename: (row: LibraryRow) => void; onCommit: (id: string) => Promise<void>; onArchive: (id: string) => void; archived?: boolean }) {
  const groups = new Map<string, LibraryRow[]>();
  for (const row of rows) {
    const label = dateGroup(row.latest_turn_preview?.at ?? row.created_at);
    groups.set(label, [...(groups.get(label) ?? []), row]);
  }
  return <>{[...groups].map(([label, grouped]) => <section key={label}><h3 className="mt-3 text-meta font-bold uppercase tracking-[0.06em] text-grey">{label}</h3>{grouped.map((row) => <LibraryRow key={row.id} row={row} {...props} />)}</section>)}</>;
}

function LibraryRow({ row, onOpen, editing, title, setTitle, onRename, onCommit, onArchive, archived = false }: { row: LibraryRow; onOpen: (row: LibraryRow) => void; editing: string | null; title: string; setTitle: (value: string) => void; onRename: (row: LibraryRow) => void; onCommit: (id: string) => Promise<void>; onArchive: (id: string) => void; archived?: boolean }) {
  const preview = row.latest_turn_preview?.reply_snippet ?? row.latest_turn_preview?.user_message ?? "";
  const isPlanning = row.kind === "planning";
  return <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-b border-line px-2 py-3 focus-within:outline focus-within:outline-2 focus-within:outline-blue">
    <div>{editing === row.id ? <input aria-label="Chat title" autoFocus value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void onCommit(row.id); }} onBlur={() => void onCommit(row.id)} className="w-full border border-line px-2 py-1 text-meta" /> : <button type="button" onClick={() => onOpen(row)} className="text-left text-meta font-semibold text-navy hover:underline">{scrub(row.title)}</button>}{!isPlanning && <button type="button" aria-label={`Rename ${row.title}`} title="Rename" onClick={() => onRename(row)} className="ml-2 align-middle text-grey hover:text-blue"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M11.5 2.5a1.4 1.4 0 0 1 2 2L5 13l-3 1 1-3 8.5-8.5Z" /></svg></button>}<p className="mt-1 line-clamp-2 max-w-[60ch] whitespace-pre-wrap text-body text-grey">{scrub(preview)}</p><div className="mt-1 flex items-center gap-2">{isPlanning && <Chip tone="blue">Planning</Chip>}{isPlanning && <Chip tone={row.closed_at !== null ? "soft" : "green"}>{row.closed_at !== null ? "Closed" : "Open"}</Chip>}{row.entry_artefact_id !== null && <Chip tone="soft">Report</Chip>}<span className="text-caption text-grey">{relativeTime(row.latest_turn_preview?.at ?? row.created_at)}</span></div></div>
    {!isPlanning && <button type="button" aria-label={archived ? `Restore ${row.title}` : `Archive ${row.title}`} title={archived ? "Restore" : "Archive"} onClick={() => onArchive(row.id)} className="self-center text-grey hover:text-blue">{archived ? <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 8a6 6 0 1 1 1.8 4.3" /><path d="M2 8V4.5M2 8h3.5" /></svg> : <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="12" height="3.5" rx="0.5" /><path d="M3.5 6.5V13h9V6.5M6.5 9h3" /></svg>}</button>}
  </div>;
}

function dateGroup(value: string) { const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000); return days <= 0 ? "Today" : days < 7 ? "This week" : "Earlier"; }
function relativeTime(value: string) { const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60_000)); return minutes < 60 ? `${minutes || 1}m ago` : minutes < 1_440 ? `${Math.floor(minutes / 60)}h ago` : `${Math.floor(minutes / 1_440)}d ago`; }
