import { useState } from "react";

import { useConversations } from "../../../api/queries";
import type { components } from "../../../api/gen/types";
import { scrub } from "../../../lib/scrub";
import { COPY } from "../../../lib/vocabulary";
import { Chip } from "../../../ui/brand/Chip";
import { taskAgentConversationId, useConversationMutations } from "./conversationState";

export type ConversationRow = components["schemas"]["ConversationListItemOut"];

/** A Task's conversations, the Task Agent pinned first.
 *
 * The list body itself, with no chrome of its own: the Agent tab mounts it
 * as its always-visible sidebar, and the overlay's `ChatsLibrary` mounts the
 * same body inside its dialog (038 V8 — one list, two frames).
 *
 * Args:
 *   props: The owning task; `onOpen`, called with the row the reader chose
 *     (a restore has already run for an archived row); and `selectedId`, the
 *     row the caller is currently showing, if it shows one.
 *
 * Returns:
 *   The pinned Task Agent, the remaining conversations by date group, and
 *   the archived group when it has rows.
 */
export function ConversationList({
  taskId,
  onOpen,
  selectedId = null,
}: {
  taskId: string;
  onOpen: (row: ConversationRow) => void;
  selectedId?: string | null;
}) {
  const active = useConversations(taskId, { status: "active" });
  const archived = useConversations(taskId, { status: "archived" });
  const { archive, unarchive, update } = useConversationMutations(taskId);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  const startRename = (row: ConversationRow) => {
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
  const openArchivedRow = (row: ConversationRow) =>
    row.kind === "planning" ? onOpen(row) : void unarchive(row.id).then(() => onOpen(row));

  // The Task Agent is pinned above the date groups rather than sorted to the
  // front of them: it is usually a Task's OLDEST conversation, so sorting it
  // first would drag its "Earlier" heading above "Today".
  const activeRows = active.data?.data ?? [];
  const taskAgentId = taskAgentConversationId(activeRows);
  const pinned = activeRows.find((row) => row.id === taskAgentId) ?? null;
  const rest = pinned === null ? activeRows : activeRows.filter((row) => row.id !== pinned.id);
  const rowProps = {
    taskAgentId,
    selectedId,
    onOpen,
    editing,
    title,
    setTitle,
    onRename: startRename,
    onCommit: commitRename,
    onArchive: (id: string) => void archive(id),
  };

  return (
    <>
      {pinned !== null && <ListRow row={pinned} {...rowProps} />}
      <ListGroups rows={rest} {...rowProps} />
      {(archived.data?.data.length ?? 0) > 0 && <><h3 className="mt-5 border-b border-line pb-1 text-meta font-bold uppercase tracking-[0.06em] text-grey">Archived</h3><ListGroups rows={archived.data?.data ?? []} {...rowProps} onOpen={openArchivedRow} onArchive={(id) => void unarchive(id)} archived /></>}
    </>
  );
}

type RowProps = {
  taskAgentId: string;
  selectedId: string | null;
  onOpen: (row: ConversationRow) => void;
  editing: string | null;
  title: string;
  setTitle: (value: string) => void;
  onRename: (row: ConversationRow) => void;
  onCommit: (id: string) => Promise<void>;
  onArchive: (id: string) => void;
  archived?: boolean;
};

function ListGroups({ rows, ...props }: RowProps & { rows: ConversationRow[] }) {
  const groups = new Map<string, ConversationRow[]>();
  for (const row of rows) {
    const label = dateGroup(row.latest_turn_preview?.at ?? row.created_at);
    groups.set(label, [...(groups.get(label) ?? []), row]);
  }
  return <>{[...groups].map(([label, grouped]) => <section key={label}><h3 className="mt-3 text-meta font-bold uppercase tracking-[0.06em] text-grey">{label}</h3>{grouped.map((row) => <ListRow key={row.id} row={row} {...props} />)}</section>)}</>;
}

function ListRow({ row, taskAgentId, selectedId, onOpen, editing, title, setTitle, onRename, onCommit, onArchive, archived = false }: RowProps & { row: ConversationRow }) {
  const preview = row.latest_turn_preview?.reply_snippet ?? row.latest_turn_preview?.user_message ?? "";
  const isPlanning = row.kind === "planning";
  // A planning row is named by its label, never by the stored title (the
  // runtime writes "Planning" there): exactly one is the Task Agent, and any
  // older lineage reads "Earlier plan" (contract § V8, invariant I8 / A10).
  const planningLabel = row.id === taskAgentId ? COPY.taskAgent : COPY.earlierPlan;
  const selected = row.id === selectedId;
  return <div className={`grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-b border-line px-2 py-3 focus-within:outline focus-within:outline-2 focus-within:outline-blue ${selected ? "bg-blue-tint-2" : ""}`}>
    <div>{editing === row.id ? <input aria-label="Chat title" autoFocus value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void onCommit(row.id); }} onBlur={() => void onCommit(row.id)} className="w-full border border-line px-2 py-1 text-meta" /> : <button type="button" aria-current={selected ? "true" : undefined} onClick={() => onOpen(row)} className="text-left text-meta font-semibold text-navy hover:underline">{isPlanning ? planningLabel : scrub(row.title)}</button>}{!isPlanning && <button type="button" aria-label={`Rename ${row.title}`} title="Rename" onClick={() => onRename(row)} className="ml-2 align-middle text-grey hover:text-blue"><svg aria-hidden="true" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M11.5 2.5a1.4 1.4 0 0 1 2 2L5 13l-3 1 1-3 8.5-8.5Z" /></svg></button>}<p className="mt-1 line-clamp-2 max-w-[60ch] whitespace-pre-wrap text-body text-grey">{scrub(preview)}</p><div className="mt-1 flex items-center gap-2">{isPlanning && <Chip tone={row.id === taskAgentId ? "blue" : "soft"}>{planningLabel}</Chip>}{isPlanning && <Chip tone={row.closed_at !== null ? "soft" : "green"}>{row.closed_at !== null ? "Closed" : "Open"}</Chip>}{row.entry_artefact_id !== null && <Chip tone="soft">Report</Chip>}<span className="text-caption text-grey">{relativeTime(row.latest_turn_preview?.at ?? row.created_at)}</span></div></div>
    {!isPlanning && <button type="button" aria-label={archived ? `Restore ${row.title}` : `Archive ${row.title}`} title={archived ? "Restore" : "Archive"} onClick={() => onArchive(row.id)} className="self-center text-grey hover:text-blue">{archived ? <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 8a6 6 0 1 1 1.8 4.3" /><path d="M2 8V4.5M2 8h3.5" /></svg> : <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="3" width="12" height="3.5" rx="0.5" /><path d="M3.5 6.5V13h9V6.5M6.5 9h3" /></svg>}</button>}
  </div>;
}

function dateGroup(value: string) { const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000); return days <= 0 ? "Today" : days < 7 ? "This week" : "Earlier"; }
function relativeTime(value: string) { const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60_000)); return minutes < 60 ? `${minutes || 1}m ago` : minutes < 1_440 ? `${Math.floor(minutes / 60)}h ago` : `${Math.floor(minutes / 1_440)}d ago`; }
