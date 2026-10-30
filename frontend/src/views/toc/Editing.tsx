import { useState } from "react";

import { type TocEdit, useTocEdit } from "../../api/mutations";
import { useTocHistory } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { LAYER_LABEL } from "./tocModel";
import type { BoxLayer, TocGraph } from "./types";

/** What an edit control needs: run an edit, with the line the Undo toast shows after it. */
export interface Editor {
  run: (edit: TocEdit, done?: string, then?: (data: unknown) => void) => void;
  busy: boolean;
}

/** Plain words for an edit the server refused. */
function refusal(error: unknown): string {
  const code = (error as { code?: string } | null)?.code;
  if (code === "toc_stale_revision") return "Someone changed this since you opened it. The page now shows their version; try again.";
  if (code === "toc_duplicate") return "These two boxes are already connected.";
  if (code === "run_active") return "A check is running. Try again when it finishes.";
  if (code === "capacity") return "Policy Atlas is busy. Try again in a minute.";
  return (error as Error | null)?.message ?? "That did not work. Try again.";
}

/**
 * The editing state of the Result page (C41): runs edits, keeps the Undo
 * toast for the last one, and the error line for a refused one. Undo in the
 * toast reverses the newest undoable change in History.
 */
export function useTocEditor(taskId: string, canEdit: boolean) {
  const edit = useTocEdit(taskId);
  const history = useTocHistory(taskId, canEdit);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const editor: Editor = {
    busy: edit.isPending,
    run: (item, done, then) => {
      setError(null);
      edit.mutate(item, {
        onSuccess: (data) => {
          setToast(done ?? null);
          then?.(data);
        },
        onError: (err) => setError(refusal(err)),
      });
    },
  };
  // ponytail: Undo in the toast takes the newest undoable change, which is this user's last edit unless a co-editor edited in the same seconds; return the event id from each write if that matters.
  const undoLast = () => {
    const last = history.data?.find((entry) => entry.undoable);
    if (last !== undefined) editor.run({ kind: "undo", eventId: last.event_id });
    setToast(null);
  };
  return { editor, toast, dismissToast: () => setToast(null), undoLast, error, history: history.data ?? [] };
}

const LAYERS: BoxLayer[] = ["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"];

/** The toolbar's editing buttons (C41, C47, C40). */
export function EditToolbar({
  graph,
  editor,
  mode,
  onMode,
  onAddBox,
}: {
  graph: TocGraph;
  editor: Editor;
  mode: "view" | "connect";
  onMode: (mode: "view" | "connect") => void;
  onAddBox: () => void;
}) {
  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  const unchecked = graph.links.filter((link) => link.state === "unchecked").map((link) => link.link_id);
  const moved = graph.boxes.some((box) => box.position != null);
  return (
    <>
      {running && (
        <Button variant="secondary" size="sm" disabled={editor.busy} onClick={() => editor.run({ kind: "stop" })}>
          Stop the check
        </Button>
      )}
      <Button variant="secondary" size="sm" onClick={onAddBox}>
        ＋ Add box
      </Button>
      <Button variant="secondary" size="sm" aria-pressed={mode === "connect"} className={mode === "connect" ? "!border-blue !text-blue" : ""} onClick={() => onMode(mode === "connect" ? "view" : "connect")}>
        Connect
      </Button>
      {moved && (
        <Button variant="secondary" size="sm" disabled={editor.busy} onClick={() => editor.run({ kind: "resetLayout" }, "Reset the layout")}>
          Reset layout
        </Button>
      )}
      {unchecked.length > 0 && (
        <Button
          variant="secondary"
          size="sm"
          disabled={editor.busy || running}
          onClick={() => editor.run({ kind: "check", body: { link_ids: unchecked, mode: "new_items" } }, undefined)}
        >
          Find evidence for new connections ({unchecked.length})
        </Button>
      )}
    </>
  );
}

/** Add a box: its layer and text (C41). */
export function AddBoxForm({ editor, onDone }: { editor: Editor; onDone: (boxId: string | null) => void }) {
  const [layer, setLayer] = useState<BoxLayer>("outcome_short");
  const [text, setText] = useState("");
  return (
    <form
      aria-label="Add a box"
      className="mb-3 flex flex-wrap items-end gap-2 border border-line bg-paper-2 px-3 py-2.5"
      onSubmit={(event) => {
        event.preventDefault();
        if (text.trim() === "") return;
        editor.run({ kind: "createBox", body: { layer, text: text.trim() } }, "Added a box", (data) => onDone((data as { id?: string } | undefined)?.id ?? null));
      }}
    >
      <label className="grid gap-1 text-meta font-semibold text-ink">
        Layer
        <select value={layer} onChange={(event) => setLayer(event.target.value as BoxLayer)} className="border border-line-2 bg-paper px-2 py-1.5 text-body font-normal">
          {LAYERS.map((item) => (
            <option key={item} value={item}>
              {LAYER_LABEL[item]}
            </option>
          ))}
        </select>
      </label>
      <label className="grid min-w-[16rem] flex-1 gap-1 text-meta font-semibold text-ink">
        What changes
        <input autoFocus value={text} onChange={(event) => setText(event.target.value)} maxLength={500} className="border border-line-2 bg-paper px-2 py-1.5 text-body font-normal" />
      </label>
      <Button type="submit" size="sm" disabled={editor.busy || text.trim() === ""}>
        Add
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={() => onDone(null)}>
        Cancel
      </Button>
    </form>
  );
}

/** The toast after an edit: what changed, and Undo (C41). */
export function UndoToast({ text, onUndo, onClose }: { text: string; onUndo: () => void; onClose: () => void }) {
  return (
    <div role="status" className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-4 rounded-md bg-navy px-4 py-2.5 text-body text-paper shadow-lg">
      <span>{text}</span>
      <button type="button" onClick={onUndo} className="cursor-pointer font-bold text-blue-tint hover:underline">
        Undo
      </button>
      <button type="button" aria-label="Dismiss" onClick={onClose} className="cursor-pointer text-paper/70 hover:text-paper">
        ×
      </button>
    </div>
  );
}

const WHEN = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "Edited by Ada · 30 Oct, 11:20" under a title (C41); nothing when nobody has edited it. */
export function EditedLine({ by, at }: { by?: string | null; at?: string | null }) {
  if (by == null) return null;
  return (
    <p className="mt-0.5 text-meta text-grey">
      Edited by {scrub(by)}
      {at != null && ` · ${WHEN.format(new Date(at))}`}
    </p>
  );
}

/** History: who changed what, newest first, with Undo on the user's own edits (C41). */
export function HistorySection({ entries, editor }: { entries: { event_id: string; at: string; who: string; what: string; undoable: boolean }[]; editor: Editor }) {
  return (
    <details id="toc-history" className="mt-10 border-t border-line pt-4">
      <summary className="cursor-pointer text-meta font-bold uppercase tracking-[0.06em] text-blue">History ({entries.length})</summary>
      <table className="mt-3 w-full border-collapse text-body">
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.event_id} className="border-b border-line align-top">
              <td className="whitespace-nowrap py-2 pr-4 text-grey">{WHEN.format(new Date(entry.at))}</td>
              <td className="py-2 pr-4">{scrub(entry.who)}</td>
              <td className="w-full py-2 pr-4">{scrub(entry.what)}</td>
              <td className="py-2 text-right">
                {entry.undoable && (
                  <button type="button" disabled={editor.busy} onClick={() => editor.run({ kind: "undo", eventId: entry.event_id }, "Undid a change")} className="cursor-pointer font-bold text-blue hover:underline">
                    Undo
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
