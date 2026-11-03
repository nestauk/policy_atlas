import { useState } from "react";
import { Link } from "react-router";

import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { referenceAuthorsLine, REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import type { Selection } from "./DetailPanel";
import { CitationMarker, CitationSheet } from "./Documents";
import { LineSample } from "./ReadingGuide";
import { VERDICT_LABEL } from "./tocModel";
import type { TocGraph, Verdict } from "./types";

type Report = NonNullable<TocGraph["report"]>;

const P = `mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`;
/** Metadata lines (the scope): body size, grey. */
const GREY = P.replace("text-ink", "text-grey");
const H3 = `mt-8 ${REPORT_SECTION_HEADING_CLASS}`;
const TOKEN = /(#\d+|\b[APSLIF]\d+\b|\[\d+\])/;

const CITES = /\s*(?:\[\d+\])+/g;

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
        if (source?.evidence_id) {
          // The Evidence search's marker: opens the source and its quote beside this sentence.
          return (
            <CitationMarker
              key={index}
              taskId={taskId}
              claim={claim}
              citations={[
                {
                  n: source.n,
                  evidenceId: source.evidence_id,
                  title: source.title ?? source.citation,
                  url: source.url,
                  quote: null,
                  fallbackQuote: source.quote ?? "",
                },
              ]}
            />
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
function codeTargets(graph: TocGraph): Map<string, Selection> {
  const codes = new Map<string, Selection>();
  for (const box of graph.boxes) if (box.code !== null) codes.set(box.code, { kind: "box", id: box.box_id });
  for (const link of graph.links) if (link.code !== null) codes.set(link.code, { kind: "link", id: link.link_id });
  return codes;
}

const VERDICT_OF = new Map(Object.entries(VERDICT_LABEL).map(([verdict, label]) => [label, verdict as Verdict]));

/** A verdict as the canvas draws it: its line style, then its label. */
function VerdictTag({ label }: { label: string }) {
  const verdict = VERDICT_OF.get(label);
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {verdict !== undefined && <LineSample verdict={verdict} />}
      {label}
    </span>
  );
}

type Row = Report["assumptions"][number];
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
 */
function AssumptionsTable({ rows, rich }: { rows: Row[]; rich: (text: string) => React.ReactNode }) {
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean } | null>(null);
  const shown =
    sort === null
      ? rows
      : [...rows].sort((left, right) => (SORT[sort.key](left) - SORT[sort.key](right)) * (sort.descending ? -1 : 1));
  const head = (label: string, key?: SortKey) => {
    const active = key !== undefined && sort?.key === key;
    return (
      <th key={label} scope="col" aria-sort={active ? (sort.descending ? "descending" : "ascending") : undefined} className={`border-b border-line-2 py-1.5 pr-2 text-left ${REPORT_LABEL_CLASS}`}>
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
            {head("Assumption")}
            {head("Conditions")}
            {head("Importance", "importance")}
            {head("Evidence", "verdict")}
            {head("Why")}
            {head("Sources")}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => (
            <tr key={`${row.code}-${index}`}>
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
                <VerdictTag label={row.verdict} />
              </td>
              <td className="border-b border-line py-2 pr-2 align-top">{rich(row.why)}</td>
              <td className="border-b border-line py-2 pr-2 align-top">{rich(row.sources.map((n) => `[${n}]`).join(""))}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
          citations={[{ n: opened.n, evidenceId: opened.evidence_id ?? null, title: opened.title ?? opened.citation, url: opened.url, quote: null, fallbackQuote: opened.quote ?? "" }]}
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
  const goal = summary.goal.replace(/\.?$/, ".");
  const scope = [
    ["Population", summary.population],
    ["Time horizon", summary.time_horizon],
    ["Directly influenced", `up to ${summary.directly_influenced}`],
  ].filter((item): item is [string, string] => item[1] !== null);
  const fail = report.how_it_could_fail ?? summary.weakest_links;
  const setAside = graph.pathways.filter((pathway) => pathway.status === "set_aside");
  const LABEL = `mt-5 ${REPORT_LABEL_CLASS}`;
  const LIST = `mt-1 max-w-[44em] list-disc space-y-1.5 pl-5 ${REPORT_BODY_CLASS}`;
  return (
    <>
      <h3 id="toc-overview" className={H3}>Overview</h3>
      <p className={P}>
        <b>Goal:</b> {scrub(goal)}
      </p>
      <p className={P}>
        {summary.if_then_because.split(/\b(If|then|because)\b/).map((part, index) =>
          index % 2 === 1 ? <b key={index}>{part}</b> : <span key={index}>{rich(part)}</span>,
        )}
      </p>
      <ul className={LIST}>
        {scope.map(([label, value]) => (
          <li key={label}>
            <b>{label}:</b> {scrub(value)}
          </li>
        ))}
      </ul>
      {summary.context !== "" && (
        <p className={P}>
          <b>Context.</b> {rich(summary.context)}
        </p>
      )}

      <p className={LABEL}>How change happens</p>
      <ul className={LIST}>
        {report.pathways.map((pathway, index) => {
          const title = scrub(pathway.title.replace(/[.:]?$/, ""));
          return (
            <li key={index}>
              {pathway.pathway_id != null ? (
                <button type="button" className="cursor-pointer text-left font-bold hover:underline" onClick={() => onPathway(pathway.pathway_id as string)} aria-label={`Show the pathway ${title} on the canvas`}>
                  {title}
                </button>
              ) : (
                <b>{title}</b>
              )}
              {pathway.strength != null && (
                <span className="ml-2 text-meta text-grey">
                  <VerdictTag label={pathway.strength} />
                </span>
              )}
              {": "}
              {rich(pathway.paragraph)}
            </li>
          );
        })}
      </ul>
      {setAside.length > 0 && (
        <p className={GREY}>
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
        <p className={P}>
          <b>How it could fail.</b> {rich(fail)}
        </p>
      )}

      {report.tests.length > 0 && (
        <>
          <p className={LABEL}>What to test</p>
          <ul className={LIST}>
            {report.tests.map((test, index) => (
              <li key={index}>
                <b>{rich(test.link)}</b>: {rich(test.question)} <i>Measure</i> {rich(test.indicator.replace(/\.?$/, ";"))} <i>test</i> {rich(test.test_and_learn)}
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 id="toc-assumptions" className={H3}>Assumptions and evidence</h3>
      <p className={P}>
        Each connection on the canvas is an assumption: that the box before it leads to the box after it. Importance is the share of success pathways the connection is on, or Risk for a connection on a failure pathway only; Evidence is its verdict. <span aria-hidden="true" className="text-[var(--color-verdict-against-text)]">⚠</span> marks a connection on more than half the pathways with Mixed or weaker evidence. Click a column heading to sort.
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
      <div className="flex items-center justify-end gap-4 pb-2">
        <Button variant="secondary" size="sm" className="print-hide border border-navy" onClick={() => window.print()}>
          Download as PDF
        </Button>
      </div>
      {graph.report === null || graph.report === undefined ? (
        <p className={P}>The report is written when the evidence check finishes.</p>
      ) : (
        <ReportBody taskId={taskId} report={graph.report} graph={graph} onSelect={onSelect} onPathway={onPathway} />
      )}
    </section>
  );
}
