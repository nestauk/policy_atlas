import { useEffect, useState } from "react";
import { askForFinishAlerts } from "../../lib/askForAlerts";
import { prefersReducedMotion } from "../../lib/motion";
import { useSearchParams } from "react-router";

import { useFunnel, useTask, useToc, useTocEvidence, useTocProposals } from "../../api/queries";
import { formatDate } from "../../lib/dates";
import { formatCount } from "../../lib/format";
import { scrub } from "../../lib/scrub";
import type { LiveSection, LiveSketch } from "../../store";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { useToast } from "../../ui/radix/Toast";
import { theoryVerdictColour, VERDICT_RULE_BLOCK_CLASS, VerdictRule } from "../../ui/brand/verdictTones";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { ReportExpandScope, seedReportExpanded } from "../ArtefactOutline";
import { LiveDraft, SeePlanLink, SourceDossier, usePrefersReducedMotion } from "../ArtefactView";
import { DownloadMenu } from "../DownloadMenu";
import { usePlanPanel } from "../planPanel";
import { usePublicView } from "../publicView";
import { REPORT_ACTIONS_CLASS, REPORT_DATELINE_CLASS, REPORT_TITLE_CLASS, ReportFacts, ReportKindRow, ReportPage, type ReportFact } from "../reportPage";
import { useTaskLive } from "../taskLive";
import { ActionLine } from "../workspace/ActionLine";
import { codeTargets, liveSections, LiveReportBody, ReportBody, reportSections, type SourceRows } from "./DetailedInformation";
import { DetailPanel, SidePanel, type Selection } from "./DetailPanel";
import { AddBoxForm, CanvasBar, tocDownloads, UndoToast, useTocEditor } from "./Editing";
import { pendingCitations, RevealedWords, tocParts, useActivePart, useLiveSourceNames, type TocPartKey } from "./liveReport";
import { pendingCount, type Preview, Suggestions } from "./Suggestions";
import { ReadingGuide, VerdictLegend } from "./ReadingGuide";
import { TocCanvas } from "./TocCanvas";
import { usePanelWidth } from "../workspace/usePanelWidth";
import { sketchGraph, tocTitle } from "./tocModel";
import type { TocGraph } from "./types";

type Report = NonNullable<TocGraph["report"]>;

/** The headline without a leading "Implausible:" that repeats the label, capitalised. */
function headlineAfter(label: string, headline: string): string {
  const rest = headline.startsWith(`${label}:`) ? headline.slice(label.length + 1).trim() : headline;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** What a report says, without whether it is stale (worked out on each
 *  read): a new report is one whose words differ, not a new read of the same
 *  one. */
function reportKey(report: Report | null): string | null {
  return report === null ? null : JSON.stringify({ ...report, stale: false });
}

/** The header's prose: the report's own measure and size. */
const HEADER_P = `mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`;

/** The canvas between a draft that failed its checks and its retry (S12). */
const EMPTY_SKETCH: LiveSketch = { boxes: [], links: [] };

/** The steps an "Update the report" walk runs (`toc_plan`, C45): a walk
 *  whose steps are only these rewrites the report and searches nothing. */
const UPDATE_STAGES = new Set(["toc_summarise", "toc_report"]);

/**
 * The verdict line, the question and "what would settle it" above the
 * canvas (decision 4: the header keeps its four parts), live while the
 * report is written and committed after. The verdict line runs beside a rule
 * in its tone (owner, 2026-11-10); the rule arrives with the committed
 * report, its indent held while the line is written so the words never move.
 */
function HeaderParts({
  report,
  parts,
  sources,
  arriving,
}: {
  report: Report | null | undefined;
  parts: ReadonlyMap<TocPartKey, LiveSection>;
  sources: ReadonlyMap<string, string>;
  arriving: string;
}) {
  if (report != null) {
    const verdict = report.verdict;
    // The shared tone from what the verdict says (never its words); too
    // little evidence takes the Line 2 grey (§ 8).
    const tone = verdict != null ? theoryVerdictColour(verdict) : null;
    const question = report.summary.question ?? report.summary.goal;
    return (
      <>
        {verdict != null && (
          <p className={cn(HEADER_P, VERDICT_RULE_BLOCK_CLASS)}>
            {tone !== null && <VerdictRule colour={tone} className={arriving} />}
            <b>{scrub(verdict.label)}.</b> <b>{scrub(headlineAfter(verdict.label, verdict.headline))}</b>
          </p>
        )}
        {question !== "" && <p className={HEADER_P}>{scrub(question.replace(/\.?$/, "."))}</p>}
        {report.summary_text != null && <p className={HEADER_P}>{scrub(report.summary_text)}</p>}
      </>
    );
  }
  const verdict = parts.get("verdict");
  const live = (key: TocPartKey) => {
    const section = parts.get(key);
    const text = section === undefined ? "" : section.state === "filled" ? (section.prose ?? "") : (section.draft ?? "");
    if (text.trim() === "") return null;
    const marked = pendingCitations(text, sources);
    return (
      <div className="mt-3 [&>div]:max-w-[56em]">
        <LiveDraft draft={marked.text} claims={marked.claims} complete={false} />
      </div>
    );
  };
  return (
    <>
      {verdict !== undefined && verdict.title !== "" && (
        <p className={cn(HEADER_P, VERDICT_RULE_BLOCK_CLASS)}>
          <b>{scrub(verdict.title)}.</b>{" "}
          <b>
            <RevealedWords text={scrub(headlineAfter(verdict.title, verdict.prose ?? ""))} />
          </b>
        </p>
      )}
      {live("question")}
      {live("in_brief")}
    </>
  );
}

/** The theory-of-change Result tab: the report page (task 054, A14), with the
 *  header, the canvas with its bar and detail panel, and the report under it.
 *  The report's expand state is the task's, as the Evidence search's is. */
/** The report's Download menu; a download that cannot be made says so in
 *  the page's error toast. Only a signed-in reader has it. */
function TocDownload({ graph }: { graph: TocGraph }) {
  const { toast } = useToast();
  return <DownloadMenu items={tocDownloads(graph, (message) => toast({ title: message, tone: "error" }))} />;
}

export function TocResult({ taskId }: { taskId: string }) {
  return (
    <ReportExpandScope taskId={taskId}>
      <TocPage taskId={taskId} />
    </ReportExpandScope>
  );
}

function TocPage({ taskId }: { taskId: string }) {
  const toc = useToc(taskId);
  const task = useTask(taskId);
  const evidence = useTocEvidence(taskId);
  const funnel = useFunnel(taskId);
  const isPublicView = usePublicView();
  const planPanel = usePlanPanel();
  // The run stream, while the reader is signed in (the public link has none).
  const stream = useTaskLive()?.stream ?? null;
  const reduceMotion = usePrefersReducedMotion();
  const [pathway, setPathway] = useState("all");
  const [guideOpen, setGuideOpen] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  // A code clicked in the report: the canvas centres on it (count makes a repeat click re-centre).
  const [focus, setFocus] = useState<{ target: Selection; count: number } | null>(null);
  const [mode, setMode] = useState<"view" | "connect">("view");
  const [adding, setAdding] = useState(false);
  // A reference's dossier, by its document row (or its title, for a report written before ids).
  const [reference, setReference] = useState<string | null>(null);
  const canEdit = toc.data?.can_edit === true;
  const panel = usePanelWidth({ label: "Resize the details panel", initial: 380, edge: "left" });
  const { editor, toast, dismissToast, undoLast, error } = useTocEditor(taskId, canEdit);
  // A review runs in the background; poll for its card while it runs (C45), and once more when it ends.
  const reviewing = toc.data?.reviewing === true;
  const proposals = useTocProposals(taskId, canEdit, reviewing);
  const { refetch: refetchProposals } = proposals;
  useEffect(() => {
    if (!reviewing) void refetchProposals();
  }, [reviewing, refetchProposals]);
  // Suggestions sit in the side panel, open while any wait until the user closes it.
  const waiting = canEdit ? pendingCount(proposals.data ?? []) : 0;
  const [suggestionsChoice, setSuggestionsChoice] = useState<boolean | null>(null);
  const suggestionsOpen = waiting > 0 && (suggestionsChoice ?? true);
  // The route a hovered suggestion would add, shown faded on the canvas.
  const [preview, setPreview] = useState<Preview | null>(null);
  const askReview = () => editor.run({ kind: "review" });

  const graph = toc.data;
  const report = graph?.report ?? null;

  // The report while it is written (A13): only a first report streams
  // (S7b, A22), so the live parts show only while there is no report.
  const parts = tocParts(stream?.liveSections ?? {});
  const runStatus = stream?.run?.status;
  const showLive =
    graph != null &&
    report === null &&
    parts.size > 0 &&
    (runStatus === "running" || runStatus === "paused" || runStatus === "succeeded" || runStatus === "degraded");
  const active = useActivePart(parts);
  const sources = useLiveSourceNames(stream?.run?.id ?? null, [...parts.values()]);

  // "Update the report" (A17): the old report stays, with the working line,
  // until the new one swaps in. The update's walk rewrites the report and
  // searches nothing; the reader's press says so before its first step.
  const [requested, setRequested] = useState<{ from: string | null } | null>(null);
  const key = reportKey(report);
  const stages = stream?.stages ?? [];
  const updateRunning =
    (runStatus === "running" || runStatus === "paused") && stages.length > 0 && stages.every((entry) => UPDATE_STAGES.has(entry.stage));
  if (requested !== null && graph != null && (key !== requested.from || graph.check_status === "failed" || graph.check_status === "stopped")) {
    setRequested(null);
  }
  const updating = report !== null && (updateRunning || requested !== null);

  // The swap (S7): the committed report replaces the live one, or the old
  // one, in place; what it brings fades in once (058's swap). A cut under
  // reduced motion. A reader who watched it written finds its sections open.
  const [swap, setSwap] = useState<{ from: string | null; waiting: boolean; arriving: boolean }>({ from: null, waiting: false, arriving: false });
  if ((showLive || updating) && !swap.waiting) {
    if (showLive) seedReportExpanded(taskId);
    setSwap({ from: key, waiting: true, arriving: false });
  } else if (swap.waiting && !showLive && !updating) {
    if (report !== null && key !== swap.from) setSwap({ from: null, waiting: false, arriving: !reduceMotion });
    else if (runStatus === "failed" || runStatus === "aborted" || runStatus === "interrupted") setSwap({ from: null, waiting: false, arriving: false });
  }
  const arriving = swap.arriving ? "anim-swap-in" : "";

  // Each judged document's row, so a citation or a reference opens its dossier.
  const rows: SourceRows = new Map(
    (evidence.data?.links ?? []).flatMap((link) => link.documents.map((doc) => [doc.evidence_id, doc.task_source_snapshot_id] as const)),
  );

  // Select a box or link and centre the canvas on it.
  const focusOn = (target: Selection) => {
    setSelection(target);
    setFocus((current) => ({ target, count: (current?.count ?? 0) + 1 }));
  };
  // A code clicked in the chat (?focus=#5) selects that box or connection here (round 6).
  const [params, setParams] = useSearchParams();
  const wanted = params.get("focus");
  const [handled, setHandled] = useState<string | null>(null);
  if (wanted !== handled && (wanted === null || graph != null)) {
    setHandled(wanted);
    const target = wanted !== null && graph != null ? codeTargets(graph).get(wanted) : undefined;
    if (target !== undefined) focusOn(target);
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
  // Before any draft the owner may draw their own theory here; the draft keeps it as drawn.
  const sketching = graph != null && graph.check_status === "none" && canEdit;

  // The first draft drawn while it is written (S12). The stream's sketch is
  // held until the stored graph has boxes, so the swap shows no empty
  // canvas: the stage's end comes before `GET /toc` returns the graph, and
  // a new walk (the check that follows) clears the stream's sketch. An
  // empty sketch while the draft runs means it is written again, so the
  // held one goes; a failed draft drops it.
  const streamSketch = stream?.liveSketch ?? null;
  const draftStage = stages.findLast((entry) => entry.stage === "toc_draft");
  const draftFailed = draftStage?.status === "failed" || runStatus === "failed" || runStatus === "aborted" || runStatus === "interrupted";
  const stored = graph != null && graph.boxes.length > 0;
  const [held, setHeld] = useState<{ sketch: LiveSketch | null; retired: LiveSketch | null }>({ sketch: null, retired: null });
  const reset = streamSketch === null && draftStage?.status === "started";
  if (streamSketch !== null && streamSketch !== held.sketch && streamSketch !== held.retired && !stored && !draftFailed) {
    setHeld({ sketch: streamSketch, retired: held.retired });
  } else if (held.sketch !== null && (stored || draftFailed)) {
    // Retired: the stream may keep the replaced sketch until its walk ends.
    setHeld({ sketch: null, retired: held.sketch === EMPTY_SKETCH ? held.retired : held.sketch });
  } else if (held.sketch !== null && held.sketch !== EMPTY_SKETCH && reset) {
    // Written again: the canvas empties and the retry is drawn from its first box.
    setHeld({ sketch: EMPTY_SKETCH, retired: held.sketch });
  }
  const drawing = held.sketch !== null && graph != null && !stored && !draftFailed ? held.sketch : null;
  // The page showed its empty state before the first box: the canvas then
  // arrives, and the first box rises in with it.
  const [sawEmpty, setSawEmpty] = useState(false);

  if (graph == null || (graph.boxes.length === 0 && !sketching && drawing === null)) {
    if (graph != null && !sawEmpty && graph.check_status === "drafting") setSawEmpty(true);
    return (
      <ReportPage className="md:max-w-[1180px]">
        <p aria-busy={toc.isPending} className="text-body text-grey">
          {toc.isPending ? "Loading the theory of change…" : graph?.check_status === "none" ? "There is no theory of change yet." : "The theory of change is being drafted."}
        </p>
      </ReportPage>
    );
  }

  // A code in the report selects its box or link, brings the canvas into view and centres it there.
  const showCanvas = () => {
    const canvas = document.querySelector('[aria-label="Theory of change canvas"]');
    if (canvas instanceof HTMLElement && typeof canvas.scrollIntoView === "function") canvas.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
  };
  const select = (target: Selection) => {
    focusOn(target);
    showCanvas();
  };
  // A pathway named in the report: the canvas shows that pathway alone, as the bar's dropdown does.
  const showPathway = (pathwayId: string) => {
    setPathway(pathwayId);
    showCanvas();
  };
  // A reference's title or number opens its dossier: by its document row when the report names it.
  const openReference = (title: string) => {
    const source = report?.sources.find((item) => (item.title ?? item.citation) === title);
    const evidenceId = source?.evidence_id ?? null;
    setReference((evidenceId !== null ? rows.get(evidenceId) : undefined) ?? title);
  };
  const updateReport = () => {
    setRequested({ from: key });
    editor.run({ kind: "updateReport" });
  };
  // The drafted and failed banners' retry: the evidence check of the whole theory.
  const checkEvidence = canEdit && (
    <Button
      variant="start"
      disabled={editor.busy}
      onClick={() => {
        askForFinishAlerts();
        editor.run({ kind: "checkFull" });
      }}
    >
      Check the evidence
    </Button>
  );

  // The facts line (A14): the sources the report cites out of those found,
  // and the years they were published.
  const facts: ReportFact[] = [];
  if (report !== null && report.sources.length > 0) {
    const found = funnel.data?.found;
    facts.push([
      "Sources",
      `${formatCount(report.sources.length)} cited${typeof found === "number" ? ` out of ${formatCount(found)} found` : ""}`,
      "#references",
    ]);
    const years = report.sources.map((source) => source.year).filter((year): year is number => typeof year === "number");
    if (years.length > 0) {
      const from = Math.min(...years);
      const to = Math.max(...years);
      facts.push(["Published", from === to ? String(from) : `${from}–${to}`, null]);
    }
  }
  const lastRun = task.data?.latest_run;
  const lastUpdated = report !== null && lastRun?.status !== "running" && lastRun?.status !== "paused" ? (lastRun?.ended_at ?? null) : null;
  const titlePart = parts.get("title");
  const liveTitle = showLive && titlePart !== undefined ? (titlePart.state === "filled" ? (titlePart.prose ?? "") : (titlePart.draft ?? "")) : "";
  const entries = report !== null ? reportSections(report) : showLive ? liveSections(parts) : undefined;
  // What the canvas draws: the sketch while the draft is written, else the stored graph.
  const shown = drawing !== null ? sketchGraph(drawing, graph) : graph;
  // The page first showed its empty state: what replaces it fades in once.
  const appeared = sawEmpty ? "anim-swap-in" : "";
  // The key's "Being checked" shows only while a connection is being checked.
  const checkingNow = graph.links.some((link) => link.state === "checking");

  return (
    // The contents sit inside the paper beside the report's narrative, so the
    // canvas and the Assumptions table keep the paper's width (owner, 2026-11-10).
    <ReportPage entries={entries} contents="within" className="md:max-w-[1180px]">
      <header className={appeared}>
        <ReportKindRow kind="Report">
          {/* Download arrives with the committed report (058). */}
          {report !== null && !isPublicView && (
            <span className={arriving}>
              <TocDownload graph={graph} />
            </span>
          )}
        </ReportKindRow>
        {/* The report's own short title (decision 4: it stays the h1); the
            task's name until it is written. */}
        <h1 className={REPORT_TITLE_CLASS}>
          {liveTitle.trim() !== "" ? <RevealedWords text={scrub(liveTitle)} /> : scrub(report?.title ?? task.data?.name ?? tocTitle(graph))}
        </h1>
        {lastUpdated !== null && (
          <p className={cn(REPORT_DATELINE_CLASS, arriving)}>
            Last updated <time dateTime={lastUpdated}>{formatDate(lastUpdated, "long")}</time>
          </p>
        )}
        {/* The action line under the title, as Evidence search's: the plan
            card leaves on start, so the report links back to the plan. */}
        {!isPublicView && (
          <div className={REPORT_ACTIONS_CLASS}>
            <SeePlanLink onClick={planPanel.openPlan} />
          </div>
        )}
        <div className={arriving}>
          <ReportFacts facts={facts} />
        </div>
        {/* A report written before the reader's latest changes says so; the
            update is the reader's (decision 10, S9). While it runs, the
            working line stands in its place and the old report stays. */}
        {updating ? (
          <div className="mt-3">
            <ActionLine label="Updating the report" live arrivalId={`toc-update:${taskId}`} />
          </div>
        ) : (
          report?.stale === true && (
            <p className="mt-3 text-meta text-grey">
              Written before your latest changes.
              {canEdit && (
                <button type="button" disabled={editor.busy} onClick={updateReport} className={cn(QUIET_CONTROL_CLASS, "ml-2")}>
                  Update the report
                </button>
              )}
            </p>
          )
        )}
        <HeaderParts report={report} parts={showLive ? parts : new Map()} sources={sources} arriving={arriving} />
        {sketching && (
          <p className={`mt-3 max-w-[56em] ${REPORT_BODY_CLASS}`}>
            Draw your own theory here if you like: add boxes with <b>Add box</b> and join them with <b>Connect</b>. When the Task Agent drafts the theory, it keeps what
            you drew and suggests the rest.
          </p>
        )}
        {graph.check_status === "drafted" && (
          // An uploaded theory (increment 5): the user checks the reading before the evidence check.
          <div role="status" className="mt-4 flex max-w-[1100px] flex-wrap items-center gap-4 border-l-2 border-blue bg-blue-tint-2 px-4 py-3">
            <p className={`min-w-0 flex-1 ${REPORT_BODY_CLASS}`}>
              This is how Policy Atlas read your diagram. Solid dark connections are drawn in your diagram. Dashed blue ones are connections Policy Atlas suggested where your diagram grouped boxes or left them unconnected. What Policy Atlas would add to complete the theory waits under Suggestions, beside the canvas. Compare it with your original in the plan, fix anything that is wrong, then check the evidence.
            </p>
            {checkEvidence}
          </div>
        )}
        {graph.check_status === "stopped" && (
          <p className={`mt-4 max-w-[1100px] ${REPORT_BODY_CLASS}`}>The check was stopped. What it finished stays; connections it did not reach show Needs evidence.</p>
        )}
        {graph.check_status === "failed" && (
          // A check that ended with an error: say so and offer the retry the chat names (owner, 2026-11-04).
          // A failure is a Red Tint surface (DESIGN.md § Callout), as a failed turn is.
          <div role="alert" className="mt-4 flex max-w-[1100px] flex-wrap items-center gap-4 border border-red-tint bg-red-tint/40 px-4 py-3">
            <p className={`min-w-0 flex-1 ${REPORT_BODY_CLASS}`}>The evidence check stopped with an error. What it finished stays on the canvas.</p>
            {checkEvidence}
          </div>
        )}
      </header>
      {/* The full-screen area: the bar, what it opens, and the canvas with its detail panel. */}
      <div id="toc-canvas" className={cn("mt-6 flex scroll-mt-4 flex-col border border-line bg-paper [&:fullscreen]:overflow-y-auto", appeared)}>
        {/* While the draft is drawn the bar is the reader's: no edits on a sketch. */}
        <CanvasBar
          graph={shown}
          pathway={drawing !== null ? "all" : pathway}
          onPathway={setPathway}
          editor={canEdit && drawing === null ? editor : null}
          mode={mode}
          onMode={setMode}
          onAddBox={() => setAdding(true)}
          onReview={askReview}
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
              <p role="alert" className="my-2 text-body text-red">
                {error}
              </p>
            )}
            {reviewing && <p className="my-2 text-body text-grey">Policy Atlas is reviewing the theory. Its suggestions appear here.</p>}
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
          graph={shown}
          live={drawing !== null ? { enterAll: sawEmpty } : null}
          preview={drawing !== null ? null : preview}
          pathway={drawing !== null ? "all" : pathway}
          selection={drawing !== null ? null : selection}
          focus={focus}
          onSelect={(target) => {
            setSelection(target);
            // Below lg the panel sits under the canvas: bring it into view once it has rendered.
            if (target === null || typeof window.matchMedia !== "function" || window.matchMedia("(min-width: 64rem)").matches) return;
            window.requestAnimationFrame(() =>
              document.querySelector("#toc-canvas aside")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" }),
            );
          }}
          editing={
            canEdit && drawing === null
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
        {drawing === null && selection === null && suggestionsOpen && (
          <SidePanel label="Suggestions" panel={panel} onClose={() => { setSuggestionsChoice(false); setPreview(null); }}>
            <Suggestions proposals={proposals.data ?? []} editor={editor} onPreview={setPreview} checkNew={graph.check_status !== "none" && graph.check_status !== "drafted"} />
          </SidePanel>
        )}
        {drawing === null && selection !== null && (
          <DetailPanel taskId={taskId} graph={graph} evidence={evidence.data} selection={selection} editor={canEdit ? editor : null} onClose={() => setSelection(null)} panel={panel} />
        )}
        </div>
      </div>
      <div className={appeared}>
        <VerdictLegend checking={drawing === null && checkingNow} />
      </div>
      {/* The report under the canvas: live while it is written, then the
          committed report in its place. Before writing starts, nothing. */}
      {(showLive || report !== null) && (
        <section aria-label="Detailed information" className="mt-10 border-t border-line pt-6">
          {report !== null ? (
            <ReportBody taskId={taskId} graph={graph} rows={rows} arriving={arriving} onSelect={select} onPathway={showPathway} onOpenReference={openReference} />
          ) : (
            <LiveReportBody parts={parts} active={active} sources={sources} still={reduceMotion || stream?.connectionStatus !== "connected"} />
          )}
        </section>
      )}
      {reference !== null && <SourceDossier taskId={taskId} sourceRef={reference} onClose={() => setReference(null)} />}
      {toast !== null && <UndoToast text={toast} onUndo={undoLast} onClose={dismissToast} />}
    </ReportPage>
  );
}
