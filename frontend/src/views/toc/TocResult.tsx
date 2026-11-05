import { useEffect, useState } from "react";
import { askForFinishAlerts } from "../../lib/askForAlerts";
import { useSearchParams } from "react-router";

import { useTask, useToc, useTocEvidence, useTocProposals } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { DetailedInformation } from "./DetailedInformation";
import { DetailPanel, SidePanel, type Selection } from "./DetailPanel";
import { AddBoxForm, CanvasBar, UndoToast, useTocEditor } from "./Editing";
import { pendingCount, type Preview, Suggestions } from "./Suggestions";
import { ReadingGuide, VerdictLegend } from "./ReadingGuide";
import { TocCanvas } from "./TocCanvas";
import { usePanelWidth } from "../workspace/usePanelWidth";
import { keptPathways, pathwayTitles, tocTitle } from "./tocModel";

/** The overall verdict's text colour: the canvas's verdict colours, darkened for text. */
const EVIDENCE_TEXT: Record<"supports" | "mixed" | "too_little" | "against", string> = {
  supports: "var(--color-verdict-confident-text)",
  mixed: "var(--color-verdict-mixed-text)",
  too_little: "var(--color-verdict-little-text)",
  against: "var(--color-verdict-against-text)",
};

/** An implausible mechanism reads as against; otherwise the evidence's colour. */
function verdictColour(verdict: { mechanism: string; evidence: keyof typeof EVIDENCE_TEXT }): string {
  return verdict.mechanism === "implausible" ? EVIDENCE_TEXT.against : EVIDENCE_TEXT[verdict.evidence];
}

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
  const panel = usePanelWidth({ label: "Resize the details panel", initial: 380, edge: "left" });
  const { editor, toast, dismissToast, undoLast, error } = useTocEditor(taskId, canEdit);
  // A review runs in the background; poll for its card for a while after asking (C45).
  const [reviewing, setReviewing] = useState(false);
  const proposals = useTocProposals(taskId, canEdit, reviewing);
  // Suggestions sit in the side panel, open while any wait until the user closes it.
  const waiting = canEdit ? pendingCount(proposals.data ?? []) : 0;
  const [suggestionsChoice, setSuggestionsChoice] = useState<boolean | null>(null);
  const suggestionsOpen = waiting > 0 && (suggestionsChoice ?? true);
  // The route a hovered suggestion would add, shown faded on the canvas.
  const [preview, setPreview] = useState<Preview | null>(null);
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
          <b className="uppercase tracking-[0.04em]" style={{ color: verdictColour(graph.report.verdict) }}>
            {scrub(graph.report.verdict.label)}.
          </b>{" "}
          <b>{scrub(headlineAfter(graph.report.verdict.label, graph.report.verdict.headline))}</b>
        </p>
      )}
      {/* The goal, as the report's question (its plan goal on reports before toc_report_v7), then the evidence in brief. */}
      {graph.report != null && (graph.report.summary.question ?? graph.report.summary.goal) !== "" && (
        <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>{scrub((graph.report.summary.question ?? graph.report.summary.goal).replace(/\.?$/, "."))}</p>
      )}
      {graph.report?.summary_text != null && <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>{scrub(graph.report.summary_text)}</p>}
      {running && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>
          Policy Atlas is checking each step against the evidence. Steps take their colour as they are checked.
        </p>
      )}
      {graph.check_status === "drafted" && (
        // An uploaded theory (increment 5): the user checks the reading before the evidence check.
        <div role="status" className="mt-4 flex max-w-[1100px] flex-wrap items-center gap-4 border-l-4 border-blue bg-blue-tint-2 px-4 py-3">
          <p className={`min-w-0 flex-1 ${REPORT_BODY_CLASS}`}>
            This is how Policy Atlas read your diagram. Solid dark connections are drawn in your diagram. Dashed blue ones are connections Policy Atlas suggested where your diagram grouped boxes or left them unconnected. What Policy Atlas would add to complete the theory waits under Suggestions, beside the canvas. Compare it with your original in the plan, fix anything that is wrong, then check the evidence.
          </p>
          {canEdit && (
            <Button
              disabled={editor.busy}
              onClick={() => {
                askForFinishAlerts();
                editor.run({ kind: "checkFull" });
              }}
            >
              Check the evidence
            </Button>
          )}
        </div>
      )}
      {graph.check_status === "stopped" && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>The check was stopped. What it finished stays; connections it did not reach show Needs evidence.</p>
      )}
      {graph.check_status === "failed" && (
        // A check that ended with an error: say so and offer the retry the chat names (owner, 2026-11-04).
        <div role="alert" className="mt-4 flex max-w-[1100px] flex-wrap items-center gap-4 border-l-4 border-[var(--color-verdict-against)] bg-paper-2 px-4 py-3">
          <p className={`min-w-0 flex-1 ${REPORT_BODY_CLASS}`}>The evidence check stopped with an error. What it finished stays on the canvas.</p>
          {canEdit && (
            <Button
              disabled={editor.busy}
              onClick={() => {
                askForFinishAlerts();
                editor.run({ kind: "checkFull" });
              }}
            >
              Check the evidence
            </Button>
          )}
        </div>
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
          suggestions={waiting}
          suggestionsOpen={suggestionsOpen && selection === null}
          onSuggestions={() => {
            setSelection(null);
            setSuggestionsChoice(!(suggestionsOpen && selection === null));
          }}
        />
        {(guideOpen || error !== null || canEdit || adding) && (
          <div className="shrink-0 px-3 empty:hidden">
            {guideOpen && <ReadingGuide graph={graph} />}
            {error !== null && (
              <p role="alert" className="my-2 text-body text-[var(--color-verdict-against-text)]">
                {error}
              </p>
            )}
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
          preview={preview}
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
        {selection === null && suggestionsOpen && (
          <SidePanel label="Suggestions" panel={panel} onClose={() => { setSuggestionsChoice(false); setPreview(null); }}>
            <Suggestions proposals={proposals.data ?? []} editor={editor} onPreview={setPreview} />
          </SidePanel>
        )}
        {selection !== null && (
          <DetailPanel taskId={taskId} graph={graph} evidence={evidence.data} selection={selection} editor={canEdit ? editor : null} onClose={() => setSelection(null)} panel={panel} />
        )}
        </div>
      </div>
      <VerdictLegend />
      <DetailedInformation taskId={taskId} graph={graph} onSelect={select} onPathway={showPathway} />
      {toast !== null && <UndoToast text={toast} onUndo={undoLast} onClose={dismissToast} />}
    </main>
  );
}
