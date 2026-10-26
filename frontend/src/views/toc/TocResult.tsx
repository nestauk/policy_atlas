import { useState } from "react";

import { useToc, useTocEvidence } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { DetailedInformation } from "./DetailedInformation";
import { DetailPanel, type Selection } from "./DetailPanel";
import { ReadingGuide } from "./ReadingGuide";
import { TocCanvas } from "./TocCanvas";
import { keptPathways, pathwayTitles, tocTitle } from "./tocModel";

/** The theory-of-change Result tab: header, canvas with its detail panel, Detailed information. */
export function TocResult({ taskId }: { taskId: string }) {
  const toc = useToc(taskId);
  const evidence = useTocEvidence(taskId);
  const [pathway, setPathway] = useState("all");
  const [guideOpen, setGuideOpen] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);

  const graph = toc.data;
  if (graph == null || graph.boxes.length === 0) {
    return (
      <main aria-busy={toc.isPending} className="mx-auto w-full max-w-[1280px] px-6 py-10">
        <p className="text-body text-grey">{toc.isPending ? "Loading the theory of change…" : "The theory of change is being drafted."}</p>
      </main>
    );
  }

  const running = graph.check_status === "drafting" || graph.check_status === "checking";
  const titles = pathwayTitles(graph);
  return (
    <main className="mx-auto w-full max-w-[1280px] px-6 py-8 max-md:px-4">
      <h1 className="text-title font-extrabold leading-tight tracking-[-0.2px] text-navy">{scrub(tocTitle(graph))}</h1>
      {(graph.summary !== null || running) && (
        <div className="mt-3 grid max-w-[1000px] gap-x-8 gap-y-3 text-body md:grid-cols-2">
          {running ? (
            <p className="md:col-span-2">Policy Atlas is checking each step against the evidence. Steps take their colour as they are checked.</p>
          ) : (
            graph.summary !== null && (
              <>
                <div>
                  <h2 className="text-body font-bold text-navy">About this theory</h2>
                  <p>{scrub(graph.summary.about)}</p>
                </div>
                <div>
                  <h2 className="text-body font-bold text-navy">What the evidence says</h2>
                  <p>{scrub(graph.summary.evidence_says)}</p>
                </div>
              </>
            )
          )}
        </div>
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
        <Button variant="secondary" size="sm" aria-expanded={guideOpen} onClick={() => setGuideOpen((open) => !open)}>
          How to read this
        </Button>
      </div>
      {guideOpen && <ReadingGuide graph={graph} />}
      <div className="flex border border-line bg-paper max-lg:flex-col">
        <TocCanvas graph={graph} pathway={pathway} selection={selection} onSelect={setSelection} />
        {selection !== null && <DetailPanel graph={graph} evidence={evidence.data} selection={selection} onClose={() => setSelection(null)} />}
      </div>
      <DetailedInformation graph={graph} evidence={evidence.data} />
    </main>
  );
}
