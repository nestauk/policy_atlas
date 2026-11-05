import { type ReactNode, useEffect, useRef, useState } from "react";

import { type TocEdit, useTocEdit } from "../../api/mutations";
import { useTocHistory } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { DownloadMenu } from "../DownloadMenu";
import { canvasImage, downloadDrawio, downloadJson, downloadReferences, printReport } from "./exports";
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

/** Whether a queued check already names every one of these links (it starts when the running walk ends). */
export function isQueued(graph: TocGraph, linkIds: string[]): boolean {
  const queued = new Set(graph.queued_link_ids ?? []);
  return linkIds.length > 0 && linkIds.every((id) => queued.has(id));
}

/** A check button's words: its own, then "Added to the queue" once it waits for the running check. */
export function checkWords(graph: TocGraph, linkIds: string[], label: string): string {
  return isQueued(graph, linkIds) ? "Added to the queue" : label;
}

const LAYERS: BoxLayer[] = ["input", "output", "outcome_short", "outcome_long", "impact", "failure_outcome"];

/** A bordered tool button with its icon: the canvas bar's edit actions. */
function ToolButton({ icon, label, pressed, disabled, onClick }: { icon: ReactNode; label: string; pressed?: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex cursor-pointer items-center gap-1.5 border px-2.5 py-1.5 text-meta font-semibold focus-visible:outline-2 focus-visible:outline-blue disabled:cursor-default disabled:text-line-2 ${
        pressed ? "border-blue bg-blue-tint text-blue" : "border-line-2 bg-paper text-navy hover:border-navy disabled:hover:border-line-2"
      }`}
    >
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        {icon}
      </svg>
      {label}
    </button>
  );
}

/** The "…" menu: the actions used less often. Closes on a choice or a click elsewhere. */
function MoreMenu({ items }: { items: { label: string; disabled?: boolean; onClick: () => void }[] }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (ref.current !== null && !ref.current.contains(event.target as Node)) ref.current.open = false;
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);
  if (items.length === 0) return null;
  return (
    <details ref={ref} className="relative">
      <summary aria-label="More actions" className="flex cursor-pointer list-none items-center border border-line-2 bg-paper px-2.5 py-1.5 text-meta font-bold leading-none text-navy hover:border-navy [&::-webkit-details-marker]:hidden">
        …
      </summary>
      <div role="menu" className="absolute right-0 z-20 mt-1 grid min-w-[16rem] border border-line bg-paper py-1 shadow-lg">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            onClick={() => {
              if (ref.current !== null) ref.current.open = false;
              item.onClick();
            }}
            className="cursor-pointer px-3 py-2 text-left text-meta font-semibold text-navy hover:bg-paper-2 disabled:cursor-default disabled:text-line-2 disabled:hover:bg-transparent"
          >
            {item.label}
          </button>
        ))}
      </div>
    </details>
  );
}

/**
 * The bar across the top of the canvas (round 5): the pathway choice, the edit
 * buttons and the "…" menu. It sits inside the full-screen area, so all of it
 * works in full screen too.
 */
export function CanvasBar({
  graph,
  pathway,
  pathways,
  onPathway,
  editor,
  mode,
  onMode,
  onAddBox,
  onReview,
  reviewLabel,
  reviewDisabled,
  onGuide,
  guideOpen,
  suggestions = 0,
  suggestionsOpen = false,
  onSuggestions,
}: {
  graph: TocGraph;
  pathway: string;
  pathways: { id: string; title: string }[];
  onPathway: (id: string) => void;
  /** Null for a reader: the bar shows the pathway choice and How to read this only. */
  editor: Editor | null;
  mode: "view" | "connect";
  onMode: (mode: "view" | "connect") => void;
  onAddBox: () => void;
  onReview: () => void;
  reviewLabel: string;
  reviewDisabled: boolean;
  onGuide: () => void;
  guideOpen: boolean;
  /** Suggestions waiting, and whether their panel is open (owner, 2026-11-04). */
  suggestions?: number;
  suggestionsOpen?: boolean;
  onSuggestions?: () => void;
}) {
  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  const unchecked = graph.links.filter((link) => link.state === "unchecked").map((link) => link.link_id);
  const moved = graph.boxes.some((box) => box.position != null);
  const menu = [
    ...(editor !== null && unchecked.length > 0 && !isQueued(graph, unchecked)
      ? [
          {
            label: `Find evidence for new connections (${unchecked.length})`,
            disabled: editor.busy,
            onClick: () => editor.run({ kind: "check", body: { link_ids: unchecked, mode: "new_items" } }),
          },
        ]
      : []),
    ...(editor !== null ? [{ label: reviewLabel, disabled: reviewDisabled, onClick: onReview }] : []),
    { label: guideOpen ? "Hide how to read this" : "How to read this", onClick: onGuide },
  ];
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-line bg-paper px-3 py-2">
      <select
        aria-label="Pathway"
        value={pathway}
        onChange={(event) => onPathway(event.target.value)}
        className="w-[16rem] min-w-0 border border-line-2 bg-paper px-2.5 py-[5px] text-meta font-semibold text-navy"
      >
        <option value="all">All pathways</option>
        {pathways.map((item) => (
          <option key={item.id} value={item.id}>
            {item.title}
          </option>
        ))}
      </select>
      <span className="flex-1" />
      {editor !== null && running && (
        <ToolButton icon={<rect x="4" y="4" width="8" height="8" fill="currentColor" stroke="none" />} label="Stop the check" disabled={editor.busy} onClick={() => editor.run({ kind: "stop" })} />
      )}
      {editor !== null && (
        <>
          <ToolButton icon={<path d="M2.5 4.5h11v7h-11zM8 6v4M6 8h4" />} label="Add box" onClick={onAddBox} />
          <ToolButton
            icon={<path d="M1.5 5.5h4v5h-4zM10.5 5.5h4v5h-4zM5.5 8h4.5M8.5 6.5 10 8l-1.5 1.5" />}
            label="Connect"
            pressed={mode === "connect"}
            onClick={() => onMode(mode === "connect" ? "view" : "connect")}
          />
          <ToolButton
            icon={<path d="M3 8a5 5 0 1 0 1.5-3.5M3 2.5V5h2.5" />}
            label="Reset layout"
            disabled={editor.busy || !moved}
            onClick={() => editor.run({ kind: "resetLayout" }, "Reset the layout")}
          />
        </>
      )}
      {suggestions > 0 && onSuggestions !== undefined && (
        <button
          type="button"
          aria-pressed={suggestionsOpen}
          onClick={onSuggestions}
          className="inline-flex cursor-pointer items-center gap-1.5 border border-blue bg-paper px-2.5 py-[5px] text-meta font-semibold text-blue hover:bg-blue-tint-2 aria-pressed:bg-blue-tint-2"
        >
          Suggestions ({suggestions})
        </button>
      )}
      <MoreMenu items={menu} />
      <DownloadMenu small items={downloads(graph)} />
    </div>
  );
}

/** The Download menu (contract item 6), grouped by what people do next. */
function downloads(graph: TocGraph) {
  const failed = () => window.alert("The download could not be made. Try again.");
  const image = (kind: "png" | "svg") => () => void canvasImage(graph, kind).catch(failed);
  return [
    { group: "Read and share", label: "Report (PDF)", hint: "The whole canvas, then the report", onSelect: () => void printReport(graph) },
    { label: "Image (PNG)", hint: "The whole canvas", onSelect: image("png") },
    { label: "Image (SVG)", hint: "The whole canvas, for web pages", onSelect: image("svg") },
    { group: "Keep working", label: "Diagram file (draw.io)", hint: "Opens in Miro, Lucidchart and diagrams.net", onSelect: () => downloadDrawio(graph) },
    { group: "Data", label: "References (CSV)", hint: "Each cited document and the connections it supports", onSelect: () => downloadReferences(graph) },
    { label: "Theory (JSON)", hint: "For other tools", onSelect: () => downloadJson(graph) },
  ];
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
