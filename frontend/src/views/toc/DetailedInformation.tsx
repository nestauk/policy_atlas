import { useState } from "react";
import { Link } from "react-router";

import { scrub } from "../../lib/scrub";
import { referenceAuthorsLine, REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import type { Selection } from "./DetailPanel";
import { CitationMarker, CitationSheet } from "./Documents";
import { VERDICT_LABEL } from "./tocModel";
import type { TocGraph, Verdict } from "./types";

type Report = NonNullable<TocGraph["report"]>;

const P = `mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`;
/** Metadata lines (the scope): body size, grey. */
const GREY = P.replace("text-ink", "text-grey");
const H3 = `mt-8 ${REPORT_SECTION_HEADING_CLASS}`;
const TOKEN = /(#\d+|\b[APSLIF]\d+\b|\[\d+\])/;

const CITES = /\s*(?:\[\d+\])+/g;

/** A numbered source as a citation: its quote, shown in its passage when the judgement is stored. */
function sourceCitation(source: Report["sources"][number]) {
  return { n: source.n, evidenceId: source.evidence_id ?? null, title: source.title ?? source.citation, url: source.url, quote: null, fallbackQuote: source.quote ?? "" };
}

/**
 * Report text with its codes and source numbers made live: a box or
 * connection code ("#2", "S3") selects it on the canvas and opens its panel;
 * "[n]" opens the source's quote in context beside the sentence it grounds,
 * as the Evidence search does: the sentence may summarise, the quote is exact.
 */
function Rich({ taskId, text, codes, sources, onSelect }: { taskId: string; text: string; codes: Map<string, Selection>; sources: Report["sources"]; onSelect: (selection: Selection) => void }) {
  const sentences = scrub(text).split(/(?<=[.!?](?:\[\d+\])*)\s+/);
  return (
    <>
      {sentences.map((sentence, at) => (
        <span key={at}>
          {at > 0 && " "}
          <RichSentence taskId={taskId} sentence={sentence} codes={codes} sources={sources} onSelect={onSelect} />
        </span>
      ))}
    </>
  );
}

function RichSentence({ taskId, sentence, codes, sources, onSelect }: { taskId: string; sentence: string; codes: Map<string, Selection>; sources: Report["sources"]; onSelect: (selection: Selection) => void }) {
  const claim = sentence.replace(CITES, "").trim();
  return (
    <>
      {sentence.split(TOKEN).map((part, index) => {
        const cite = /^\[(\d+)\]$/.exec(part);
        const source = cite === null ? undefined : sources.find((item) => item.n === Number(cite[1]));
        if (source !== undefined && (source.evidence_id || source.quote)) {
          // The Evidence search's marker: opens the source and its quote beside this sentence
          // (in its passage when the judgement is stored; the whole programme's, the quote alone).
          return (
            <CitationMarker key={index} taskId={taskId} claim={claim} citations={[sourceCitation(source)]} />
          );
        }
        if (cite !== null) {
          // A report written before sources carried their judgement: jump to the list.
          return (
            <a key={index} href={`#toc-source-${cite[1]}`} className="hover:underline">
              {part}
            </a>
          );
        }
        const target = codes.get(part);
        if (target === undefined) return part;
        return (
          <button key={index} type="button" onClick={() => onSelect(target)} className="cursor-pointer hover:underline" aria-label={`Show ${part} on the canvas`}>
            {part}
          </button>
        );
      })}
    </>
  );
}

/** The canvas selection each box and link code stands for. */
export function codeTargets(graph: TocGraph): Map<string, Selection> {
  const codes = new Map<string, Selection>();
  for (const box of graph.boxes) if (box.code !== null) codes.set(box.code, { kind: "box", id: box.box_id });
  for (const link of graph.links) if (link.code !== null) codes.set(link.code, { kind: "link", id: link.link_id });
  return codes;
}

const VERDICT_OF = new Map<string, Verdict>([
  ...Object.entries(VERDICT_LABEL).map(([verdict, label]) => [label, verdict as Verdict] as const),
  // The labels on reports written before 2026-11-04.
  ["Confident", "confident"],
  ["Not confident: evidence against", "not_confident"],
]);

/** A verdict as text, in its colour (the canvas's verdict colours, as text). */
function VerdictText({ label }: { label: string }) {
  const verdict = VERDICT_OF.get(label);
  return <span className={verdict !== undefined ? `toc-verdict-${verdict}` : undefined}>{label}</span>;
}

type Row = Report["assumptions"][number];
/** Rows the collapsed table shows: the top of the server's order (supported risks, then the most central). */
const COLLAPSED_ROWS = 5;
type SortKey = "code" | "importance" | "verdict";

/** The values a column sorts by; the default order is the server's (flagged, most central, worst verdict). */
const SORT: Record<SortKey, (row: Row) => number> = {
  code: (row) => Number(row.code.replace(/\D/g, "")) || 0,
  // Risks sort below every success connection.
  importance: (row) => row.share ?? -1,
  verdict: (row) => row.verdict_rank ?? 0,
};

/**
 * Assumptions and evidence: one row per connection. Code, Importance and
 * Evidence sort on a click (again to reverse); the server's order is the default.
 * The first rows of that order show; the others on a click, and in print.
 */
function AssumptionsTable({ rows, rich }: { rows: Row[]; rich: (text: string) => React.ReactNode }) {
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean } | null>(null);
  // The first rows of the default order show; the rest on request, and always in print.
  const [all, setAll] = useState(false);
  const first = new Set(rows.slice(0, COLLAPSED_ROWS));
  const key = (row: Row) => first.has(row);
  const extra = Math.max(rows.length - COLLAPSED_ROWS, 0);
  const hidden = all ? 0 : extra;
  const shown =
    sort === null
      ? rows
      : [...rows].sort((left, right) => (SORT[sort.key](left) - SORT[sort.key](right)) * (sort.descending ? -1 : 1));
  const head = (label: string, key?: SortKey) => {
    const active = key !== undefined && sort?.key === key;
    return (
      <th key={label} scope="col" aria-sort={active ? (sort.descending ? "descending" : "ascending") : undefined} className={`whitespace-nowrap border-b border-line-2 py-1.5 pr-2 text-left ${REPORT_LABEL_CLASS}`}>
        {key === undefined ? (
          label
        ) : (
          <button
            type="button"
            className="cursor-pointer uppercase tracking-[0.06em] hover:text-navy"
            // Importance opens most central first; the others lowest first.
            onClick={() => setSort({ key, descending: active ? !sort.descending : key === "importance" })}
          >
            {label} {active ? (sort.descending ? "▼" : "▲") : "↕"}
          </button>
        )}
      </th>
    );
  };
  return (
    <div className="mt-2 overflow-x-auto">
      <table className={`w-full border-collapse ${REPORT_BODY_CLASS}`}>
        <thead>
          <tr>
            {head("Code", "code")}
            {head("Assumption (connection)")}
            {head("Conditions")}
            {head("Importance", "importance")}
            {head("Evidence", "verdict")}
            {head("Why")}
            {head("Sources")}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => (
            <tr key={`${row.code}-${index}`} className={hidden > 0 && !key(row) ? "hidden print:table-row" : undefined}>
              <td className="whitespace-nowrap border-b border-line py-2 pr-2 align-top">
                {row.flag && (
                  <span role="img" aria-label="Central and weakly evidenced" title="Central and weakly evidenced" className="mr-1 text-[var(--color-verdict-against-text)]">
                    ⚠
                  </span>
                )}
                {rich(row.code)}
              </td>
              <td className="border-b border-line py-2 pr-2 align-top">{scrub(row.statement)}</td>
              <td className="border-b border-line py-2 pr-2 align-top">
                {(row.conditions ?? []).length > 0 && (
                  <ul className="list-disc pl-4">
                    {(row.conditions ?? []).map((condition) => (
                      <li key={condition}>{scrub(condition)}</li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="whitespace-nowrap border-b border-line py-2 pr-2 align-top">{row.importance ?? (row.kind === "risk" ? "Risk" : "")}</td>
              <td className="border-b border-line py-2 pr-2 align-top">
                <VerdictText label={row.verdict} />
              </td>
              <td className="border-b border-line py-2 pr-2 align-top">{rich(row.why)}</td>
              <td className="border-b border-line py-2 pr-2 align-top">{rich(row.sources.map((n) => `[${n}]`).join(""))}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {extra > 0 && (
        <button type="button" onClick={() => setAll((open) => !open)} className="print-hide mt-2 cursor-pointer border border-navy bg-paper px-3 py-1.5 text-meta font-semibold text-navy hover:bg-blue-tint-2">
          {all ? "Collapse table" : `Show all ${rows.length} connections`}
        </button>
      )}
    </div>
  );
}

/**
 * The numbered sources, as the Evidence search lists its references: the
 * number, the title (opens the source's quote in the citation sidebar), then
 * authors, year and venue in grey. Reports written before those fields show
 * their one-line citation.
 */
function SourceList({ taskId, sources }: { taskId: string; sources: Report["sources"] }) {
  const [opened, setOpened] = useState<Report["sources"][number] | null>(null);
  if (sources.length === 0) return null;
  return (
    <>
      <ol className={`mt-3 max-w-[44em] space-y-1.5 ${REPORT_BODY_CLASS}`}>
        {sources.map((source) => {
          const authors = referenceAuthorsLine((source.authors ?? []).map((name) => ({ name })));
          const title = source.title ?? source.citation;
          return (
            <li key={source.n} id={`toc-source-${source.n}`} className="flex gap-2">
              <span className="font-bold text-blue">[{source.n}]</span>
              <span>
                {source.evidence_id != null ? (
                  <button type="button" className="cursor-pointer text-left hover:underline" onClick={() => setOpened(source)}>
                    {scrub(title)}
                  </button>
                ) : source.url !== null ? (
                  <a href={source.url} target="_blank" rel="noreferrer" className="hover:underline">
                    {scrub(title)}
                  </a>
                ) : (
                  scrub(title)
                )}
                {authors !== null && <span className="text-grey"> — {scrub(authors)}</span>}
                {source.year != null && <span className="text-grey"> ({source.year})</span>}
                {source.venue != null && <span className="text-grey"> · {scrub(source.venue)}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {opened !== null && (
        <CitationSheet
          taskId={taskId}
          claim={null}
          numbered={false}
          citations={[sourceCitation(opened)]}
          onClose={() => setOpened(null)}
        />
      )}
    </>
  );
}

function ReportBody({ taskId, report, graph, onSelect, onPathway }: { taskId: string; report: Report; graph: TocGraph; onSelect: (selection: Selection) => void; onPathway: (pathwayId: string) => void }) {
  const codes = codeTargets(graph);
  const rich = (text: string) => <Rich taskId={taskId} text={text} codes={codes} sources={report.sources} onSelect={onSelect} />;
  const { summary } = report;
  const fail = report.how_it_could_fail ?? summary.weakest_links;
  const setAside = graph.pathways.filter((pathway) => pathway.status === "set_aside");
  const LIST = `mt-2 max-w-[44em] list-decimal space-y-1.5 pl-5 ${REPORT_BODY_CLASS}`;
  // A report before toc_report_v7 has no question or verdict reason: it keeps its Goal and its own whole-programme line.
  const older = report.verdict_reason == null;
  const supporting = report.supporting_activities ?? [];
  const expansions = report.expansions ?? [];
  const sections = [
    ["toc-summary", "Summary"],
    ["toc-routes", "Pathways"],
    ...(fail !== "" ? [["toc-fail", "How it could fail"]] : []),
    ...(report.tests.length > 0 ? [["toc-tests", "What to test first"]] : []),
    ...(expansions.length > 0 ? [["toc-expand", "How it could be expanded"]] : []),
    ...(supporting.length > 0 ? [["toc-supporting", "Supporting activities"]] : []),
    ["toc-assumptions", "Assumptions"],
    ["toc-references", "References"],
  ];
  return (
    <>
      {/* The narrative beside a short contents list; the table below takes the full width. */}
      <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_13rem] lg:gap-10">
      <div className="min-w-0">
      <h3 id="toc-summary" className={H3}>Summary</h3>
      {/* The setting and the question, as one paragraph (owner, 2026-11-04). */}
      {summary.question != null && summary.question !== "" ? (
        <p className={P}>
          {summary.context !== "" && <>{rich(summary.context)} </>}
          {rich(summary.question)}
        </p>
      ) : (
        <>
          {summary.context !== "" && <p className={P}>{rich(summary.context)}</p>}
          <p className={P}>
            <b>Goal:</b> {scrub(summary.goal.replace(/\.?$/, "."))}
          </p>
        </>
      )}
      <p className={P}>
        {summary.if_then_because.split(/\b(if|If|then|because)\b/).map((part, index) =>
          index % 2 === 1 ? <b key={index}>{part}</b> : <span key={index}>{rich(part)}</span>,
        )}
      </p>
      {report.verdict_reason != null && report.verdict_reason !== "" && (
        <p className={P}>
          <b>Verdict: {report.verdict != null ? scrub(report.verdict.label.replace(/\.?$/, ".")) : ""}</b> {rich(report.verdict_reason)}
        </p>
      )}
      {older && report.whole_programme != null && report.whole_programme !== "" && (
        <p className={P}>
          <b>Evaluations of the whole programme.</b> {rich(report.whole_programme)}
        </p>
      )}

      <h3 id="toc-routes" className={H3}>Pathways</h3>
      {report.pathways.map((pathway, index) => {
        const title = scrub(pathway.title.replace(/[.:]?$/, ""));
        return (
          <div key={index} className="mt-4 max-w-[44em]">
            <h4 className="text-lead font-bold text-navy">
              {pathway.pathway_id != null ? (
                <button type="button" className="cursor-pointer text-left hover:underline" onClick={() => onPathway(pathway.pathway_id as string)} aria-label={`Show the pathway ${title} on the canvas`}>
                  {title}
                </button>
              ) : (
                title
              )}
              {pathway.strength != null && <span className="font-normal"> ({pathway.strength})</span>}
            </h4>
            <p className={`mt-1 ${REPORT_BODY_CLASS}`}>{rich(pathway.paragraph)}</p>
          </div>
        );
      })}
      {setAside.length > 0 && (
        <p className={`${GREY} mt-4`}>
          <b>Considered and set aside:</b>{" "}
          {setAside.map((pathway, index) => (
            <span key={pathway.pathway_id}>
              {index > 0 && " "}
              {scrub(pathway.label.replace(/\.?$/, "."))}
              {pathway.reason !== null && <> {scrub(pathway.reason)}</>}
            </span>
          ))}
        </p>
      )}

      {fail !== "" && (
        <>
          <h3 id="toc-fail" className={H3}>How it could fail</h3>
          <p className={P}>{rich(fail)}</p>
        </>
      )}

      {report.tests.length > 0 && (
        <>
          <h3 id="toc-tests" className={H3}>What to test first</h3>
          <ol className={LIST}>
            {report.tests.map((test, index) => (
              <li key={index}>
                <b>{rich(test.link)}</b>{" "}
                {test.sentence != null ? (
                  rich(test.sentence)
                ) : (
                  <>
                    {rich(test.question ?? "")} <i>Measure</i> {rich((test.indicator ?? "").replace(/\.?$/, ";"))} <i>test</i> {rich(test.test_and_learn ?? "")}
                  </>
                )}
              </li>
            ))}
          </ol>
        </>
      )}

      {expansions.length > 0 && (
        <>
          <h3 id="toc-expand" className={H3}>How it could be expanded</h3>
          <p className={P}>
            The evidence describes {expansions.length === 1 ? "a route" : `${expansions.length} routes`} your diagram does not show. You can add{" "}
            {expansions.length === 1 ? "it" : "any of them"} from Suggestions above the canvas.
          </p>
          <ul className={`mt-2 max-w-[44em] list-disc space-y-1.5 pl-5 ${REPORT_BODY_CLASS}`}>
            {expansions.map((route, index) => {
              // Live: a route the user accepted is on the canvas now, as a pathway of that name.
              const added = graph.pathways.some((pathway) => pathway.label === route.label && pathway.status === "kept");
              return (
                <li key={index}>
                  <b>{scrub(route.label.replace(/\.?$/, "."))}</b>
                  {route.kind === "failure" && <i> (a way it could go wrong)</i>} {rich(route.sentence)}
                  {added && <span className="ml-2 text-meta font-semibold text-[var(--color-verdict-confident-text)]">Added to your theory</span>}
                </li>
              );
            })}
          </ul>
        </>
      )}
      {supporting.length > 0 && (
        <>
          <h3 id="toc-supporting" className={H3}>Supporting activities</h3>
          <ul className={`mt-2 max-w-[44em] list-disc space-y-1.5 pl-5 ${REPORT_BODY_CLASS}`}>
            {supporting.map((text, index) => (
              <li key={index}>{rich(text)}</li>
            ))}
          </ul>
        </>
      )}
      </div>
      <nav aria-label="Report contents" className="print-hide mt-8 max-lg:hidden">
        <p className={REPORT_LABEL_CLASS}>Contents</p>
        <ul className={`mt-2 space-y-1.5 border-l border-line pl-3 ${REPORT_BODY_CLASS}`}>
          {sections.map(([id, label]) => (
            <li key={id}>
              <button type="button" className="cursor-pointer text-left text-navy hover:text-blue hover:underline" onClick={() => document.getElementById(id as string)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      </div>

      <h3 id="toc-assumptions" className={H3}>Assumptions</h3>
      <p className={P}>
        Each connection in the theory corresponds to a causal assumption. The Importance measure indicates either the share of success pathways that go through the connection, or that it is a risk connection leading to a failure.
      </p>
      <AssumptionsTable rows={report.assumptions} rich={rich} />

      <h3 id="toc-references" className={H3}>References</h3>
      <SourceList taskId={taskId} sources={report.sources} />
      <p className={GREY}>
        These are the documents the report cites.{" "}
        <Link to={`/tasks/${taskId}/sources/all`} className="font-bold text-blue hover:underline">
          See every document found in the Sources tab
        </Link>
        .
      </p>
    </>
  );
}

/**
 * The report under the canvas (C38), and the PDF: an Overview (goal, logic,
 * scope, context, pathways strongest first, how it could fail, what to test),
 * the Assumptions and evidence table and the References. Nothing collapses,
 * so the print view shows it whole.
 */
export function DetailedInformation({ taskId, graph, onSelect, onPathway }: { taskId: string; graph: TocGraph; onSelect: (selection: Selection) => void; onPathway: (pathwayId: string) => void }) {
  return (
    <section aria-label="Detailed information" className="mt-10 border-t border-line pt-6">
      {graph.report === null || graph.report === undefined ? (
        <p className={P}>The report is written when the evidence check finishes.</p>
      ) : (
        <ReportBody taskId={taskId} report={graph.report} graph={graph} onSelect={onSelect} onPathway={onPathway} />
      )}
    </section>
  );
}
