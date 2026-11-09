import { useRef, useState } from "react";

import { useConversations } from "../../../api/queries";
import type { components } from "../../../api/gen/types";
import { scrub } from "../../../lib/scrub";
import { COPY } from "../../../lib/vocabulary";
import { cn } from "../../../ui/brand/cn";
import { FoldMarkIcon } from "../../../ui/brand/FoldMarkIcon";
import { DRAFT_CHAT_ID, TASK_AGENT_TAB_ID, taskAgentConversationId, useConversationMutations } from "./conversationState";
import { ChangingText } from "../ChangingText";
import { ArchiveIcon, ICON_ROW, PencilIcon, RestoreIcon, iconButtonClass } from "../../../ui/brand/icons";
import { CAPTION_LABEL_CLASS } from "../../../ui/brand/label";
import { DisclosureChevron } from "../../../ui/brand/Disclosure";

export type ConversationRow = components["schemas"]["ConversationListItemOut"];

/** A Task's conversations, the Task Agent pinned first.
 *
 * The list body itself, with no chrome of its own: the Agent tab mounts it
 * in its sidebar, and the overlay mounts the same body behind its header's
 * list toggle (038 V8 — one list, two frames). Rows carry a
 * title and nothing else — the selected row and the pinned Task Agent are
 * marked the way the Result tab's contents nav marks its place (a 2px blue
 * rule on the left), and a row's actions surface on hover or focus.
 *
 * Args:
 *   props: The owning task; `onOpen`, called with the row the reader chose
 *     (a restore has already run for an archived row); and `selectedId`, the
 *     row the caller is currently showing, if it shows one.
 *
 * Returns:
 *   The pinned Task Agent, the remaining conversations by date group, and an
 *   "Archived" disclosure — shut by default — when there are archived rows.
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
  const cancelRename = () => setEditing(null);

  // A task_agent row never archives (no control fires it), but guard the
  // restore-and-open path anyway so a synthetically-archived task_agent row
  // isn't routed through the chat-only unarchive+open flow.
  const openArchivedRow = (row: ConversationRow) =>
    row.kind === "task_agent" ? onOpen(row) : void unarchive(row.id).then(() => onOpen(row));

  // The Task Agent is pinned above the date groups rather than sorted to the
  // front of them: it is usually a Task's OLDEST conversation, so sorting it
  // first would drag its "Earlier" heading above "Today".
  const activeRows = active.data?.data ?? [];
  const taskAgentId = taskAgentConversationId(activeRows);
  // The Task Agent is always listed: a run closes the task_agent lineage, and
  // the active listing then carries no task_agent row at all — the row here is
  // the task_agent thread itself (`TASK_AGENT_TAB_ID`), which every consumer
  // resolves to the Task Agent (038 V8 build finding on completed tasks).
  const pinned: ConversationRow =
    activeRows.find((row) => row.id === taskAgentId) ?? syntheticRow(TASK_AGENT_TAB_ID, "task_agent", COPY.taskAgent);
  const rest = activeRows.filter((row) => row.id !== pinned.id);
  // A draft chat (`?chat=new`) shows as a selected "New chat" row until its
  // first message creates the real row.
  const draft = selectedId === DRAFT_CHAT_ID ? syntheticRow(DRAFT_CHAT_ID, "chat", COPY.newChat) : null;
  const archivedRows = archived.data?.data ?? [];
  const rowProps = {
    taskAgentId,
    selectedId,
    onOpen,
    editing,
    title,
    setTitle,
    onRename: startRename,
    onCommit: commitRename,
    onCancel: cancelRename,
    onArchive: (id: string) => void archive(id),
  };

  return (
    <div className="flex flex-col">
      <ListRow row={pinned} {...rowProps} />
      <ListGroups rows={draft === null ? rest : [draft, ...rest]} {...rowProps} />
      {archivedRows.length > 0 && (
        <details className="group/archive mt-4">
          <summary className={cn(CAPTION_LABEL_CLASS, "group flex cursor-pointer select-none items-center gap-1.5 py-1 pl-1.5 pr-2 hover:text-navy [&::-webkit-details-marker]:hidden")}>
            <DisclosureChevron className="group-open/archive:rotate-90" />
            <h3 className="font-bold">Archived</h3>
            <span className="normal-case tracking-normal">{archivedRows.length}</span>
          </summary>
          <ListGroups rows={archivedRows} {...rowProps} onOpen={openArchivedRow} onArchive={(id) => void unarchive(id)} archived />
        </details>
      )}
    </div>
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
  onCancel: () => void;
  onArchive: (id: string) => void;
  archived?: boolean;
};

function ListGroups({ rows, ...props }: RowProps & { rows: ConversationRow[] }) {
  const groups = new Map<string, ConversationRow[]>();
  for (const row of rows) {
    const label = dateGroup(row.latest_turn_preview?.at ?? row.created_at);
    groups.set(label, [...(groups.get(label) ?? []), row]);
  }
  return (
    <>
      {[...groups].map(([label, grouped]) => (
        <section key={label}>
          {!props.archived && (
            <h3 className={cn(CAPTION_LABEL_CLASS, "mt-4 mb-1 pl-3")}>{label}</h3>
          )}
          {grouped.map((row) => <ListRow key={row.id} row={row} {...props} />)}
        </section>
      ))}
    </>
  );
}

const ACTION_CLASS = iconButtonClass("row");

function ListRow({ row, taskAgentId, selectedId, onOpen, editing, title, setTitle, onRename, onCommit, onCancel, onArchive, archived = false }: RowProps & { row: ConversationRow }) {
  const isTaskAgent = row.kind === "task_agent";
  // A task_agent row is named by its label, never by the stored title (the
  // runtime writes "Planning" there): exactly one is the Task Agent, and any
  // older lineage reads "Earlier plan" (contract § V8, invariant I8 / A10).
  const label = isTaskAgent ? (row.id === taskAgentId ? COPY.taskAgent : COPY.earlierPlan) : scrub(row.title);
  const selected = row.id === selectedId;
  const cancelled = useRef(false);

  if (editing === row.id) {
    return (
      <div className="border-l-2 border-l-blue py-1 pl-2.5 pr-2">
        <input
          aria-label="Chat title"
          autoFocus
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onFocus={() => {
            cancelled.current = false;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") void onCommit(row.id);
            if (event.key === "Escape") {
              // Escape discards the edit; the blur that follows must not save it.
              cancelled.current = true;
              onCancel();
            }
          }}
          onBlur={() => {
            if (!cancelled.current) void onCommit(row.id);
          }}
          className="w-full border border-line bg-paper px-2 py-1 text-meta text-navy focus:border-blue focus:outline-none"
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group/row flex items-center border-l-2 pr-1",
        selected ? "border-l-blue bg-blue-tint" : "border-l-transparent hover:bg-blue-tint-2",
      )}
    >
      <button
        type="button"
        aria-current={selected ? "true" : undefined}
        onClick={() => onOpen(row)}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2 py-1.5 pl-2.5 pr-1 text-left text-meta text-navy focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue",
          selected && "font-semibold",
        )}
      >
        {isTaskAgent && <FoldMarkIcon size={10} className="text-blue" />}
        {/* A chat's title, written by the backend from its first message
            and put in the cached reads (round 14), is revealed as the task's
            name is; the reader's own rename remounts the label and commits. */}
        {isTaskAgent ? <span className="truncate">{label}</span> : <ChangingText text={row.title} testIdPrefix="chat-title" />}
      </button>
      {!isTaskAgent && row.id !== DRAFT_CHAT_ID && (
        <div className="flex shrink-0 items-center opacity-0 transition-opacity duration-150 group-hover/row:opacity-100 group-focus-within/row:opacity-100">
          {!archived && (
            <button type="button" aria-label={`Rename ${row.title}`} title="Rename" onClick={() => onRename(row)} className={ACTION_CLASS}>
              <PencilIcon size={ICON_ROW} />
            </button>
          )}
          <button
            type="button"
            aria-label={archived ? `Restore ${row.title}` : `Archive ${row.title}`}
            title={archived ? "Restore" : "Archive"}
            onClick={() => onArchive(row.id)}
            className={ACTION_CLASS}
          >
            {archived ? <RestoreIcon size={ICON_ROW} /> : <ArchiveIcon size={ICON_ROW} />}
          </button>
        </div>
      )}
    </div>
  );
}

/** A row the listing does not carry but the list must show: the Task Agent
 *  once a run has closed the task_agent lineage, or a draft chat. Only the
 *  fields the rows read are meaningful; the rest satisfy the wire shape. */
function syntheticRow(id: string, kind: "task_agent" | "chat", title: string): ConversationRow {
  return {
    id,
    kind,
    title,
    status: "active",
    closed_at: null,
    archived_at: null,
    created_at: new Date().toISOString(),
    entry_artefact_id: null,
    latest_turn_preview: null,
  } as ConversationRow;
}

function dateGroup(value: string) {
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
  return days <= 0 ? "Today" : days < 7 ? "This week" : "Earlier";
}
