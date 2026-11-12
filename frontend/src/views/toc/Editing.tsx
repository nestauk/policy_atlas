import { type ComponentProps, useState } from "react";

import { type TocEdit, useTocEdit } from "../../api/mutations";
import { useTocHistory } from "../../api/queries";
import { formatDate } from "../../lib/dates";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { CloseButton } from "../../ui/brand/CloseButton";
import { cn } from "../../ui/brand/cn";
import { iconButtonClass, MoreIcon } from "../../ui/brand/icons";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { Select } from "../../ui/brand/Select";
import { Popover, PopoverContent, PopoverTrigger } from "../../ui/radix/Popover";
import { TOAST_CLASS } from "../../ui/radix/Toast";
import { MENU_ITEM_CLASS } from "../DownloadMenu";
import { canvasImage, downloadDrawio, downloadJson, downloadReferences, printReport } from "./exports";
import { keptPathways, LAYER_LABEL, pathwayTitles } from "./tocModel";
import type { BoxLayer, TocGraph } from "./types";

/** A form field (DESIGN.md § Inputs): Paper, a Line 2 hairline, 12 by 10 px, Lead words, square. */
export const FIELD_CLASS = "w-full min-w-0 border border-line-2 bg-paper px-3 py-2.5 text-lead text-ink placeholder:text-grey";

/** A field's label over it: Meta Semibold Navy. */
export const FIELD_LABEL_CLASS = "text-meta font-semibold text-navy";

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

/** A button that checks these links: its own words; "Finding evidence…" and inactive while the check runs on them; "Added to the queue" once it waits for the running check. The outline button: the view's one fill is "Check the evidence". */
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
    <Button variant="outline" size="sm" {...props} disabled={editor.busy || disabled || queued || checking} onClick={() => editor.run({ kind: "check", body: { link_ids: ids, mode } })}>
      {queued ? "Added to the queue" : checking ? "Finding evidence…" : label}
    </Button>
  );
}

const LAYER_OPTIONS = (Object.entries(LAYER_LABEL) as [BoxLayer, string][]).map(([value, label]) => ({ value, label }));

/** The layer choice, in the canvas's column order: the app's one dropdown. */
export function LayerSelect({ value, onChange, id, className }: { value: BoxLayer; onChange: (layer: BoxLayer) => void; id?: string; className?: string }) {
  return <Select label="Layer" id={id} value={value} options={LAYER_OPTIONS} onChange={onChange} className={className} />;
}

/**
 * The canvas bar's edit actions: the outline button at the bar's 32 px, the
 * Sources filter bar's control height. A toggle (Connect, Suggestions) shows
 * its pressed state as the outline switch does: a Navy border, never a fill.
 */
function ToolButton({ label, pressed, disabled, onClick }: { label: string; pressed?: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <Button
      variant="outline"
      size="sm"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className="h-8 py-0 transition-colors duration-150 aria-pressed:border-navy aria-pressed:bg-hover-fill max-sm:order-3"
    >
      {label}
    </Button>
  );
}

/** The more menu: the actions used less often. Closes on a choice, a click elsewhere or Esc. */
function MoreMenu({ items }: { items: { label: string; disabled?: boolean; onClick: () => void }[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger aria-label="More actions" className={cn(iconButtonClass("chrome"), "max-sm:order-1")}>
        <MoreIcon />
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
 * buttons and the more menu. It sits inside the full-screen area, so all of it
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
      <Select
        label="Pathway"
        size={32}
        value={pathway}
        onChange={onPathway}
        options={[{ value: "all", label: "All pathways" }, ...keptPathways(graph).map((item) => ({ value: item.pathway_id, label: titles.get(item.pathway_id) ?? "" }))]}
        className="w-64 max-sm:w-auto max-sm:min-w-0 max-sm:flex-1"
        contentClassName="w-80"
      />
      {/* On a phone the more menu sits beside the pathway choice and the edit actions take the next row. */}
      <span aria-hidden="true" className={cn("flex-1 max-sm:order-2", (editor !== null || suggestions > 0) && "max-sm:basis-full")} />
      {editor !== null && running && <ToolButton label="Stop the check" disabled={editor.busy} onClick={() => editor.run({ kind: "stop" })} />}
      {editor !== null && (
        <>
          <ToolButton label="Add box" onClick={onAddBox} />
          <ToolButton label="Connect" pressed={mode === "connect"} onClick={() => onMode(mode === "connect" ? "view" : "connect")} />
          <ToolButton label="Reset layout" disabled={editor.busy || !moved} onClick={() => editor.run({ kind: "resetLayout" }, "Reset the layout")} />
        </>
      )}
      {suggestions > 0 && <ToolButton label={`Suggestions (${suggestions})`} pressed={suggestionsOpen} onClick={onSuggestions} />}
      <MoreMenu items={menu} />
    </div>
  );
}

/** The Download menu (contract item 6), grouped by what people do next. It
 *  sits in the report's kind row (task 054, A14). An image that cannot be
 *  made reports through `onFailed` (the page's error toast), never a browser
 *  dialog. */
export function tocDownloads(graph: TocGraph, onFailed?: (message: string) => void) {
  const failed = () => onFailed?.("The download could not be made. Try again.");
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
      className="mb-3 flex flex-wrap items-end gap-x-3 gap-y-2 border border-line bg-paper px-4 py-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (text.trim() === "") return;
        editor.run({ kind: "createBox", body: { layer, text: text.trim() } }, "Added a box", (data) => onDone((data as { id?: string } | undefined)?.id ?? null));
      }}
    >
      <div className="grid gap-1">
        <span aria-hidden="true" className={FIELD_LABEL_CLASS}>
          Layer
        </span>
        <LayerSelect value={layer} onChange={setLayer} className="w-56" />
      </div>
      <label className="grid min-w-[16rem] flex-1 gap-1">
        <span className={FIELD_LABEL_CLASS}>What changes</span>
        <input autoFocus value={text} onChange={(event) => setText(event.target.value)} maxLength={500} className={cn(FIELD_CLASS, "h-10 py-0 text-body")} />
      </label>
      <span className="flex gap-1">
        <Button type="submit" variant="outline" className="h-10 py-0" disabled={editor.busy || text.trim() === ""}>
          Add
        </Button>
        <Button type="button" variant="ghost" className="h-10 py-0" onClick={() => onDone(null)}>
          Cancel
        </Button>
      </span>
    </form>
  );
}

/** The toast after an edit: what changed, and Undo (C41). */
export function UndoToast({ text, onUndo, onClose }: { text: string; onUndo: () => void; onClose: () => void }) {
  return (
    <div role="status" className={cn(TOAST_CLASS, "fixed bottom-4 right-4 z-50 w-96 max-w-[92vw] items-center border-line-2 text-body")}>
      <span className="flex-1 text-navy">{text}</span>
      <button type="button" onClick={onUndo} className={LINK_CLASS}>
        Undo
      </button>
      <CloseButton aria-label="Dismiss" onClick={onClose} className="-my-1.5 -mr-2" />
    </div>
  );
}

/** "Edited by Ada · 30 Oct, 11:20" under a title (C41); nothing when nobody has edited it. */
export function EditedLine({ by, at }: { by?: string | null; at?: string | null }) {
  if (by == null) return null;
  return (
    <p className="mt-0.5 text-meta text-grey">
      Edited by {scrub(by)}
      {at != null && ` · ${formatDate(at, "short")}, ${formatDate(at, "time")}`}
    </p>
  );
}
