import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { useTask, useToc, useTocEvidence, useTocProposals } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { DetailedInformation } from "./DetailedInformation";
import { DetailPanel, type Selection } from "./DetailPanel";
import { AddBoxForm, CanvasBar, UndoToast, useTocEditor } from "./Editing";
import { Suggestions } from "./Suggestions";
import { ReadingGuide, VerdictLegend } from "./ReadingGuide";
import { TocCanvas } from "./TocCanvas";
import { keptPathways, pathwayTitles, tocTitle } from "./tocModel";

/** The overall verdict's text colour: the canvas's verdict colours, darkened for text. */
const THEORY_VERDICT_TEXT: Record<"supported" | "plausible_untested" | "doubtful" | "implausible", string> = {
  supported: "var(--color-verdict-confident-text)",
  plausible_untested: "var(--color-verdict-little-text)",
  doubtful: "var(--color-verdict-mixed-text)",
  implausible: "var(--color-verdict-against-text)",
};

/** The headline without a leading "Implausible:" that repeats the label, capitalised. */
function headlineAfter(label: string, headline: string): string {
  const rest = headline.startsWith(`${label}:`) ? headline.slice(label.length + 1).trim() : headline;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** The theory-of-change Result tab: header, canvas with its bar and detail panel, the report. */
export function TocResult({ taskId }: { taskId: string }) {
  const toc = useToc(taskId);
  const task = useTask(taskId);
  const evidence = useTocEvidence(taskId);
  const [pathway, setPathway] = useState("all");
  const [guideOpen, setGuideOpen] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  // A code clicked in the report: the canvas centres on it (count makes a repeat click re-centre).
  const [focus, setFocus] = useState<{ target: Selection; count: number } | null>(null);
  const [mode, setMode] = useState<"view" | "connect">("view");
  const [adding, setAdding] = useState(false);
  const canEdit = toc.data?.can_edit === true;
  const { editor, toast, dismissToast, undoLast, error } = useTocEditor(taskId, canEdit);
  // A review runs in the background; poll for its card for a while after asking (C45).
  const [reviewing, setReviewing] = useState(false);
  const proposals = useTocProposals(taskId, canEdit, reviewing);
  const askReview = () =>
    editor.run({ kind: "review" }, undefined, () => {
      setReviewing(true);
      window.setTimeout(() => setReviewing(false), 180_000);
    });

  const graph = toc.data;
  // A code clicked in the chat (?focus=#5) selects that box or connection here (round 6).
  const [params, setParams] = useSearchParams();
  const wanted = params.get("focus");
  const [handled, setHandled] = useState<string | null>(null);
  if (wanted !== handled && (wanted === null || graph != null)) {
    setHandled(wanted);
    const box = graph?.boxes.find((item) => item.code === wanted);
    const link = graph?.links.find((item) => item.code === wanted);
    const target: Selection | null = box !== undefined ? { kind: "box", id: box.box_id } : link !== undefined ? { kind: "link", id: link.link_id } : null;
    if (target !== null) {
      setSelection(target);
      setFocus((current) => ({ target, count: (current?.count ?? 0) + 1 }));
    }
  }
  useEffect(() => {
    if (wanted === null || graph == null) return;
    setParams(
      (current) => {
        current.delete("focus");
        return current;
      },
      { replace: true },
    );
  }, [wanted, graph, setParams]);
  if (graph == null || graph.boxes.length === 0) {
    return (
      <main aria-busy={toc.isPending} className="mx-auto my-8 w-full max-w-[1280px] bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
        <p className="text-body text-grey">{toc.isPending ? "Loading the theory of change…" : "The theory of change is being drafted."}</p>
      </main>
    );
  }

  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  // A code in the report selects its box or link, brings the canvas into view and centres it there.
  const showCanvas = () => {
    const canvas = document.querySelector('[aria-label="Theory of change canvas"]');
    if (canvas instanceof HTMLElement && typeof canvas.scrollIntoView === "function") canvas.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const select = (target: Selection) => {
    setSelection(target);
    setFocus((current) => ({ target, count: (current?.count ?? 0) + 1 }));
    showCanvas();
  };
  // A pathway named in the report: the canvas shows that pathway alone, as the bar's dropdown does.
  const showPathway = (pathwayId: string) => {
    setPathway(pathwayId);
    showCanvas();
  };
  const titles = pathwayTitles(graph);
  const reviewWaiting = reviewing && (proposals.data ?? []).length === 0;
  return (
    <main className="mx-auto my-8 w-full max-w-[1280px] bg-paper px-10 py-9 shadow-sm ring-1 ring-line max-md:my-0 max-md:px-4 max-md:py-6 max-md:shadow-none max-md:ring-0">
      {/* The report's short title and summary; the task's name until a report is written. */}
      <h1 className="text-title font-extrabold leading-tight tracking-[-0.2px] text-navy">{scrub(graph.report?.title ?? task.data?.name ?? tocTitle(graph))}</h1>
      {/* Can the theory work? The overall verdict leads, in its colour, then the plain headline. */}
      {graph.report?.verdict != null && (
        <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>
          <b className="uppercase tracking-[0.04em]" style={{ color: THEORY_VERDICT_TEXT[graph.report.verdict.verdict] }}>
            {scrub(graph.report.verdict.label)}.
          </b>{" "}
          <b>{scrub(headlineAfter(graph.report.verdict.label, graph.report.verdict.headline))}</b>
        </p>
      )}
      {graph.report?.summary_text != null && <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>{scrub(graph.report.summary_text)}</p>}
      {running && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>
          Policy Atlas is checking each step against the evidence. Steps take their colour as they are checked.
        </p>
      )}
      {graph.check_status === "stopped" && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>The check was stopped. What it finished stays; connections it did not reach show Needs evidence.</p>
      )}
      {/* The full-screen area: the bar, what it opens, and the canvas with its detail panel. */}
      <div id="toc-canvas" className="mt-6 flex scroll-mt-4 flex-col border border-line bg-paper [&:fullscreen]:overflow-y-auto">
        <CanvasBar
          graph={graph}
          pathway={pathway}
          pathways={keptPathways(graph).map((item) => ({ id: item.pathway_id, title: titles.get(item.pathway_id) ?? "" }))}
          onPathway={setPathway}
          editor={canEdit ? editor : null}
          mode={mode}
          onMode={setMode}
          onAddBox={() => setAdding(true)}
          onReview={askReview}
          reviewLabel={`Review the theory${graph.edits_since_review >= 5 ? ` (${graph.edits_since_review} changes)` : ""}`}
          reviewDisabled={editor.busy || reviewWaiting}
          onGuide={() => setGuideOpen((open) => !open)}
          guideOpen={guideOpen}
        />
        {(guideOpen || error !== null || canEdit || adding) && (
          <div className="shrink-0 px-3 empty:hidden">
            {guideOpen && <ReadingGuide graph={graph} />}
            {error !== null && (
              <p role="alert" className="my-2 text-body text-[var(--color-verdict-against-text)]">
                {error}
              </p>
            )}
            {canEdit && <Suggestions proposals={proposals.data ?? []} editor={editor} />}
            {reviewWaiting && <p className="my-2 text-body text-grey">Policy Atlas is reviewing the theory. Its suggestions appear here.</p>}
            {adding && (
              <AddBoxForm
                editor={editor}
                onDone={(boxId) => {
                  setAdding(false);
                  if (boxId !== null) setSelection({ kind: "box", id: boxId });
                }}
              />
            )}
          </div>
        )}
        <div className="flex min-h-0 lg:h-[640px] max-lg:flex-col [:fullscreen>&]:h-auto [:fullscreen>&]:flex-1">
        <TocCanvas
          graph={graph}
          pathway={pathway}
          selection={selection}
          focus={focus}
          onSelect={setSelection}
          editing={
            canEdit
              ? {
                  mode,
                  onMove: (boxId, revision, x, y) => {
                    const code = graph.boxes.find((box) => box.box_id === boxId)?.code ?? "a box";
                    editor.run({ kind: "moveBox", boxId, body: { expected_revision: revision, x, y } }, `Moved ${code}`);
                  },
                  onConnect: (source, target) => {
                    setMode("view");
                    editor.run({ kind: "createLink", body: { source_box_id: source, target_box_id: target } }, "Added a connection", (data) => {
                      const id = (data as { id?: string } | undefined)?.id;
                      if (id !== undefined) setSelection({ kind: "link", id });
                    });
                  },
                  onCancelConnect: () => setMode("view"),
                }
              : null
          }
        />
        {selection !== null && (
          <DetailPanel taskId={taskId} graph={graph} evidence={evidence.data} selection={selection} editor={canEdit ? editor : null} onClose={() => setSelection(null)} />
        )}
        </div>
      </div>
      <VerdictLegend />
      <DetailedInformation taskId={taskId} graph={graph} onSelect={select} onPathway={showPathway} />
      {toast !== null && <UndoToast text={toast} onUndo={undoLast} onClose={dismissToast} />}
    </main>
  );
}
