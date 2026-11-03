import { useEffect, useState } from "react";

import type { TaskAgentThreadDecision } from "../../store";
import { scrub } from "../../lib/scrub";

type Detail = Record<string, unknown>;

const num = (detail: Detail | undefined, key: string): number => (typeof detail?.[key] === "number" ? (detail[key] as number) : 0);
/** "1 study", "3 studies", "2 searches", "4 documents". */
function plural(count: number, noun: string): string {
  if (count === 1) return `${count} ${noun}`;
  if (noun.endsWith("y")) return `${count} ${noun.slice(0, -1)}ies`;
  return `${count} ${noun}${noun.endsWith("h") || noun.endsWith("x") ? "es" : "s"}`;
}

/** One finished step as a plain line, from the counts its completion event carries; null to leave it out. */
function doneLine(detail: Detail): string | null {
  switch (detail.component) {
    case "toc_draft":
      return num(detail, "boxes") > 0
        ? `Drafted ${plural(num(detail, "boxes"), "box")}, ${plural(num(detail, "links"), "connection")} and ${plural(num(detail, "pathways"), "pathway")}.`
        : "Drafted the boxes, connections and pathways.";
    case "toc_select": {
      const screened = num(detail, "screened");
      if (screened === 0) return "Found no new documents to read.";
      const relevant = num(detail, "relevant");
      return `Read ${plural(screened, "title")} and abstracts: ${relevant} look on topic, ${screened - relevant} set aside.`;
    }
    case "toc_judge": {
      const judged = num(detail, "judgements");
      if (judged === 0) return null;
      const off = num(detail, "screened_out_not_about");
      return `Judged ${plural(judged, "document")} against the steps: ${judged - off} test them, ${off} do not.`;
    }
    case "toc_figures":
      return num(detail, "figures") > 0 ? `Took ${plural(num(detail, "figures"), "figure")} from the abstracts.` : null;
    case "classify":
      return num(detail, "classified") > 0 ? `Named the design of ${plural(num(detail, "classified"), "study")}.` : null;
    case "appraise":
      return num(detail, "appraised") > 0 ? `Rated the quality of ${plural(num(detail, "appraised"), "study")}.` : null;
    case "toc_discover":
      return "Looked for other routes in the evidence.";
    case "toc_merge":
      return "Merged steps that say the same thing.";
    case "toc_choose":
      return "Chose the pathways to keep.";
    case "toc_summarise":
      return "Wrote the titles and the summary.";
    case "toc_report":
      return "Wrote the report.";
    default:
      return null;
  }
}

/** What a step is doing while it runs, with the counts the steps before it already know. */
function nowLine(component: string, done: Map<string, Detail>, searches: number): string {
  switch (component) {
    case "toc_draft":
      return "Drafting the theory";
    case "toc_item_searches":
    case "toc_search_new":
      return searches > 0 ? `Searching for evidence: ${plural(searches, "search")} done` : "Searching for evidence on each connection";
    case "toc_select":
      return "Reading titles and abstracts";
    case "toc_discover":
      return "Looking for other routes in the evidence";
    case "toc_merge":
      return "Merging steps that say the same thing";
    case "toc_judge": {
      const relevant = num(done.get("toc_select"), "relevant");
      return relevant > 0 ? `Judging ${plural(relevant, "document")} against the steps` : "Judging the documents against the steps";
    }
    case "toc_figures":
      return "Taking figures from the abstracts";
    case "classify":
      return "Naming each study's design";
    case "appraise": {
      const classified = num(done.get("classify"), "classified");
      return classified > 0 ? `Rating the quality of ${plural(classified, "study")}` : "Rating the quality of the studies";
    }
    case "toc_choose":
      return "Choosing the pathways to keep";
    case "toc_summarise":
      return "Writing the titles and the summary";
    case "toc_report":
      return "Writing the report";
    default:
      return "Working";
  }
}

export interface TocTraceView {
  /** Whether this walk drafts the theory (one model call: no steps to show while it runs). */
  drafting: boolean;
  /** When the step running now started, for the timer. */
  since: string | null;
  /** The walk's name: "Drafting the theory" while it runs, "Drafted the theory" after. */
  title: string;
  /** What runs now, present tense; null once the walk has ended. */
  now: string | null;
  /** Finished steps, oldest first. */
  lines: string[];
}

/**
 * Read a theory-of-change walk from its events: one line per search (its
 * queries and what they found) and per finished step, and the step running now.
 */
export function tocTrace(
  walkId: string,
  decisions: TaskAgentThreadDecision[],
  live: boolean,
  /** The walk's kind when the caller knows it: the first walk drafts, every later one checks. */
  kind?: "draft" | "check",
): TocTraceView {
  const ordered = [...decisions].sort((a, b) => a.sequence - b.sequence);
  const searches = new Map<string, { at: number; queries: string[]; found?: Detail }>();
  const steps: { at: number; text: string }[] = [];
  const done = new Map<string, Detail>();
  let running: string | null = null;
  let since: string | null = null;
  for (const decision of ordered) {
    const detail = (decision.detail ?? {}) as Detail;
    const owner = decision.capability_run_id ?? walkId;
    const component = typeof detail.component === "string" ? detail.component : null;
    if (decision.kind === "search.executed" && typeof detail.query === "string") {
      const entry = searches.get(owner) ?? { at: decision.sequence, queries: [] };
      entry.queries.push(detail.query);
      searches.set(owner, entry);
    } else if (decision.kind === "component.started" && component !== null && owner === walkId) {
      running = component;
      since = decision.occurred_at;
    } else if (decision.kind === "component.completed" && component === "acquire") {
      const entry = searches.get(owner);
      if (entry !== undefined) entry.found = detail;
    } else if (decision.kind === "component.completed" && component !== null) {
      done.set(component, detail);
      if (component === running) running = null;
      const text = doneLine(detail);
      if (text !== null) steps.push({ at: decision.sequence, text });
    }
  }
  const searchLines = [...searches.values()].map(({ at, queries, found }) => {
    // The shortest query reads best: the keyword one, not the step's full sentence.
    const shortest = queries.reduce((a, b) => (b.length < a.length ? b : a));
    const shown = shortest.length > 90 ? `${shortest.slice(0, 88)}…` : shortest;
    const head = `Searched ${plural(queries.length, "query")}, e.g. “${shown}”`;
    const tail = found === undefined ? "…" : `: ${plural(num(found, "results_returned"), "result")}, ${num(found, "acquired")} new to this task.`;
    return { at, text: head + tail };
  });
  const lines = [...searchLines, ...steps].sort((a, b) => a.at - b.at).map((line) => line.text);
  const drafting =
    kind !== undefined ? kind === "draft" : done.has("toc_draft") || running === "toc_draft" || (searches.size === 0 && steps.length === 0 && running === null);
  const finishedSearches = [...searches.values()].filter((entry) => entry.found !== undefined).length;
  return {
    drafting,
    since: live && running !== null ? since : null,
    title: drafting ? (live ? "Drafting the theory" : "Drafted the theory") : live ? "Searching for evidence" : "Searched for evidence",
    now: live ? (running === null && !drafting && searches.size === 0 ? "Starting the evidence check" : nowLine(running ?? (drafting ? "toc_draft" : "toc_item_searches"), done, finishedSearches)) : null,
    lines,
  };
}

/**
 * A theory-of-change walk in the chat (rounds 5 and 6): while it runs, the
 * step running now and, under it, the last finished step fading in; the full
 * list opens on a click. Folded to its name once it ends. The Task Agent's
 * own message after it says what it found.
 */
export function TocTrace({
  walkId,
  decisions,
  live,
  kind,
}: {
  walkId: string;
  decisions: TaskAgentThreadDecision[];
  live: boolean;
  kind?: "draft" | "check";
}) {
  const [open, setOpen] = useState(false);
  const view = tocTrace(walkId, decisions, live, kind);
  const elapsed = useElapsed(view.since);
  const last = view.lines.at(-1);
  return (
    <div className="mr-8" role={live ? "status" : undefined} aria-live={live ? "polite" : undefined}>
      <button
        type="button"
        aria-expanded={open}
        disabled={view.lines.length === 0}
        onClick={() => setOpen((value) => !value)}
        className="flex cursor-pointer items-center gap-2 text-left text-caption font-semibold text-grey hover:text-navy disabled:cursor-default disabled:hover:text-grey"
      >
        {live ? (
          <span aria-hidden="true" className="anim-breathe h-1.5 w-1.5 shrink-0 bg-blue" />
        ) : (
          <span aria-hidden="true" className={`inline-block w-2 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}>
            ›
          </span>
        )}
        <span key={view.now ?? view.title} className={live ? "anim-rise" : undefined}>
          {live ? `${view.now}…` : view.title}
        </span>
        {elapsed !== null && <span className="font-normal tabular-nums">{elapsed}</span>}
        {view.lines.length > 0 && <span className="font-normal">· {open ? "hide steps" : plural(view.lines.length, "step")}</span>}
      </button>
      {live && view.drafting && (
        // The draft is one model call: say what it does and how long it takes, as there are no steps to show.
        <p className="mt-0.5 border-l border-line pl-3 text-caption text-grey">
          Writing the boxes, connections and pathways from your plan in one pass. This usually takes 1 to 2 minutes; then the evidence check starts.
        </p>
      )}
      {open ? (
        <ul className="mt-1 space-y-0.5 border-l border-line pl-3">
          {view.lines.map((line, index) => (
            <li key={index} className="anim-rise text-caption text-grey">
              {scrub(line)}
            </li>
          ))}
        </ul>
      ) : (
        live &&
        last !== undefined && (
          // The last finished step, fading in as each new one lands.
          <p key={last} className="anim-rise mt-0.5 border-l border-line pl-3 text-caption text-grey">
            {scrub(last)}
          </p>
        )
      )}
    </div>
  );
}

/** "1:05" since a moment, ticking each second; null without one. */
function useElapsed(since: string | null): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [since]);
  if (since === null) return null;
  const seconds = Math.max(0, Math.round((now - Date.parse(since)) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
