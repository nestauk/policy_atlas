import { type ComponentProps, type ReactNode, useState } from "react";

import { type TocEdit, useTocEdit } from "../../api/mutations";
import { useTocHistory } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../../ui/radix/Popover";
import { TOAST_CLASS } from "../../ui/radix/Toast";
import { DownloadMenu, MENU_ITEM_CLASS } from "../DownloadMenu";
import { usePublicView } from "../publicView";
import { canvasImage, downloadDrawio, downloadJson, downloadReferences, printReport } from "./exports";
import { keptPathways, LAYER_LABEL, pathwayTitles } from "./tocModel";
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
function isQueued(graph: TocGraph, linkIds: string[]): boolean {
  const queued = new Set(graph.queued_link_ids ?? []);
  return linkIds.length > 0 && linkIds.every((id) => queued.has(id));
}

/** Whether the running check names every one of these links (their state is `checking`). */
function isChecking(graph: TocGraph, linkIds: string[]): boolean {
  const checking = new Set(graph.links.filter((link) => link.state === "checking").map((link) => link.link_id));
  return linkIds.length > 0 && linkIds.every((id) => checking.has(id));
}

type CheckMode = Extract<TocEdit, { kind: "check" }>["body"]["mode"];

/** A button that checks these links: its own words; "Finding evidence…" and inactive while the check runs on them; "Added to the queue" once it waits for the running check. */
export function CheckButton({
  graph,
  editor,
  ids,
  mode,
  label,
  disabled = false,
  ...props
}: { graph: TocGraph; editor: Editor; ids: string[]; mode: CheckMode; label: string } & Omit<ComponentProps<typeof Button>, "onClick" | "children">) {
  const queued = isQueued(graph, ids);
  const checking = isChecking(graph, ids);
  return (
    <Button size="sm" {...props} disabled={editor.busy || disabled || queued || checking} onClick={() => editor.run({ kind: "check", body: { link_ids: ids, mode } })}>
      {queued ? "Added to the queue" : checking ? "Finding evidence…" : label}
    </Button>
  );
}

/** The layer choice, in the canvas's column order. */
export function LayerSelect(props: ComponentProps<"select">) {
  return (
    <select {...props}>
      {Object.entries(LAYER_LABEL).map(([layer, label]) => (
        <option key={layer} value={layer}>
          {label}
        </option>
      ))}
    </select>
  );
}

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

/** The "…" menu: the actions used less often. Closes on a choice, a click elsewhere or Esc. */
function MoreMenu({ items }: { items: { label: string; disabled?: boolean; onClick: () => void }[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger aria-label="More actions" className="flex cursor-pointer items-center border border-line-2 bg-paper px-2.5 py-1.5 text-meta font-bold leading-none text-navy hover:border-navy">
        …
      </PopoverTrigger>
      <PopoverContent role="menu" align="end" sideOffset={4} className="grid w-auto min-w-[16rem] border-line p-0 py-1">
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            onClick={() => {
              setOpen(false);
              item.onClick();
            }}
            className={cn(MENU_ITEM_CLASS, "disabled:cursor-default disabled:text-line-2 disabled:hover:bg-transparent disabled:hover:text-line-2")}
          >
            {item.label}
          </button>
        ))}
      </PopoverContent>
    </Popover>
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
  onPathway,
  editor,
  mode,
  onMode,
  onAddBox,
  onReview,
  onGuide,
  guideOpen,
  suggestions,
  suggestionsOpen,
  onSuggestions,
}: {
  graph: TocGraph;
  pathway: string;
  onPathway: (id: string) => void;
  /** Null for a reader: the bar shows the pathway choice and How to read this only. */
  editor: Editor | null;
  mode: "view" | "connect";
  onMode: (mode: "view" | "connect") => void;
  onAddBox: () => void;
  onReview: () => void;
  onGuide: () => void;
  guideOpen: boolean;
  /** Suggestions waiting, and whether their panel is open (owner, 2026-11-04). */
  suggestions: number;
  suggestionsOpen: boolean;
  onSuggestions: () => void;
}) {
  const titles = pathwayTitles(graph);
  // Downloads are for signed-in readers only, never the public link (C17).
  const isPublicView = usePublicView();
  const reviewLabel = `Review the theory${graph.edits_since_review >= 5 ? ` (${graph.edits_since_review} changes)` : ""}`;
  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  // Before the draft there is no plan to check or review against.
  const drafted = graph.check_status !== "none";
  const unchecked = graph.links.filter((link) => link.state === "unchecked").map((link) => link.link_id);
  const moved = graph.boxes.some((box) => box.position != null);
  const menu = [
    ...(editor !== null && drafted && unchecked.length > 0 && !isQueued(graph, unchecked)
      ? [
          {
            label: `Find evidence for new connections (${unchecked.length})`,
            disabled: editor.busy,
            onClick: () => editor.run({ kind: "check", body: { link_ids: unchecked, mode: "new_items" } }),
          },
        ]
      : []),
    ...(editor !== null && drafted ? [{ label: reviewLabel, disabled: editor.busy || graph.reviewing === true, onClick: onReview }] : []),
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
        {keptPathways(graph).map((item) => (
          <option key={item.pathway_id} value={item.pathway_id}>
            {titles.get(item.pathway_id) ?? ""}
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
      {suggestions > 0 && (
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
      {!isPublicView && <DownloadMenu small items={downloads(graph)} />}
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
        <LayerSelect value={layer} onChange={(event) => setLayer(event.target.value as BoxLayer)} className="border border-line-2 bg-paper px-2 py-1.5 text-body font-normal" />
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
    <div role="status" className={cn(TOAST_CLASS, "fixed bottom-4 right-4 z-50 w-96 max-w-[92vw] items-center border-line-2 text-body")}>
      <span className="flex-1 text-navy">{text}</span>
      <button type="button" onClick={onUndo} className="cursor-pointer font-bold text-blue hover:underline">
        Undo
      </button>
      <button type="button" aria-label="Dismiss" onClick={onClose} className="cursor-pointer text-grey hover:text-navy">
        ✕
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
