import { useState } from "react";

import { useTask, useToc, useTocEvidence, useTocProposals } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { Button } from "../../ui/brand/Button";
import { ContentsSidebar } from "../ArtefactOutline";
import { DetailedInformation, REPORT_SECTIONS } from "./DetailedInformation";
import { DetailPanel, type Selection } from "./DetailPanel";
import { AddBoxForm, EditToolbar, HistorySection, UndoToast, useTocEditor } from "./Editing";
import { Suggestions } from "./Suggestions";
import { ReadingGuide, VerdictLegend } from "./ReadingGuide";
import { TocCanvas } from "./TocCanvas";
import { keptPathways, pathwayTitles, tocTitle } from "./tocModel";

/** The theory-of-change Result tab: contents sidebar, header, canvas with its detail panel, the report. */
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
  const { editor, toast, dismissToast, undoLast, error, history } = useTocEditor(taskId, canEdit);
  // A review runs in the background; poll for its card for a while after asking (C45).
  const [reviewing, setReviewing] = useState(false);
  const proposals = useTocProposals(taskId, canEdit, reviewing);
  const askReview = () =>
    editor.run({ kind: "review" }, undefined, () => {
      setReviewing(true);
      window.setTimeout(() => setReviewing(false), 180_000);
    });

  const graph = toc.data;
  if (graph == null || graph.boxes.length === 0) {
    return (
      <main aria-busy={toc.isPending} className="mx-auto my-8 w-full max-w-[1280px] bg-paper px-10 py-9 shadow-sm ring-1 ring-line">
        <p className="text-body text-grey">{toc.isPending ? "Loading the theory of change…" : "The theory of change is being drafted."}</p>
      </main>
    );
  }

  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  // A code in the report selects its box or link, brings the canvas into view and centres it there.
  const select = (target: Selection) => {
    setSelection(target);
    setFocus((current) => ({ target, count: (current?.count ?? 0) + 1 }));
    const canvas = document.querySelector('[aria-label="Theory of change canvas"]');
    if (canvas instanceof HTMLElement && typeof canvas.scrollIntoView === "function") canvas.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const titles = pathwayTitles(graph);
  return (
    <div className="mx-auto flex w-full max-w-[1520px] flex-col gap-6 px-6 max-md:gap-0 max-md:px-0 md:flex-row">
    <ContentsSidebar entries={[{ id: "toc-canvas", title: "Canvas" }, ...REPORT_SECTIONS]} />
    <main className="my-8 min-w-0 flex-1 bg-paper px-10 py-9 shadow-sm ring-1 ring-line max-md:my-0 max-md:px-4 max-md:py-6 max-md:shadow-none max-md:ring-0">
      {/* The report's short title and summary; the task's name until a report is written. */}
      <h1 className="text-title font-extrabold leading-tight tracking-[-0.2px] text-navy">{scrub(graph.report?.title ?? task.data?.name ?? tocTitle(graph))}</h1>
      {graph.report?.summary_text != null && <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>{scrub(graph.report.summary_text)}</p>}
      {running && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>
          Policy Atlas is checking each step against the evidence. Steps take their colour as they are checked.
        </p>
      )}
      {graph.check_status === "stopped" && (
        <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>The check was stopped. What it finished stays; connections it did not reach show Needs evidence.</p>
      )}
      <div className="mb-3 mt-6 flex items-center gap-2">
        <select
          aria-label="Pathway"
          value={pathway}
          onChange={(event) => setPathway(event.target.value)}
          className="border border-line-2 bg-paper px-2.5 py-[5px] text-meta font-semibold text-navy"
        >
          <option value="all">All pathways</option>
          {keptPathways(graph).map((item) => (
            <option key={item.pathway_id} value={item.pathway_id}>
              {titles.get(item.pathway_id)}
            </option>
          ))}
        </select>
        <span className="flex-1" />
        {canEdit && <EditToolbar graph={graph} editor={editor} mode={mode} onMode={setMode} onAddBox={() => setAdding(true)} />}
        {canEdit && (
          <Button
            variant="secondary"
            size="sm"
            disabled={editor.busy || (reviewing && (proposals.data ?? []).length === 0)}
            onClick={askReview}
          >
            Review the theory{graph.edits_since_review >= 5 ? ` (${graph.edits_since_review} changes)` : ""}
          </Button>
        )}
        <Button variant="secondary" size="sm" aria-expanded={guideOpen} onClick={() => setGuideOpen((open) => !open)}>
          How to read this
        </Button>
      </div>
      {guideOpen && <ReadingGuide graph={graph} />}
      {error !== null && (
        <p role="alert" className="mb-2 text-body text-[var(--color-verdict-against-text)]">
          {error}
        </p>
      )}
      {canEdit && <Suggestions proposals={proposals.data ?? []} editor={editor} />}
      {reviewing && (proposals.data ?? []).length === 0 && (
        <p className="mb-2 text-body text-grey">Policy Atlas is reviewing the theory. Its suggestions appear here.</p>
      )}
      {adding && (
        <AddBoxForm
          editor={editor}
          onDone={(boxId) => {
            setAdding(false);
            if (boxId !== null) setSelection({ kind: "box", id: boxId });
          }}
        />
      )}
      <div id="toc-canvas" className="flex scroll-mt-4 border border-line bg-paper max-lg:flex-col">
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
      <VerdictLegend />
      <DetailedInformation taskId={taskId} graph={graph} onSelect={select} />
      {canEdit && <HistorySection entries={history} editor={editor} />}
      {toast !== null && <UndoToast text={toast} onUndo={undoLast} onClose={dismissToast} />}
    </main>
    </div>
  );
}
