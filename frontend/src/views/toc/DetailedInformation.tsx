import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { REPORT_BODY_CLASS, REPORT_LABEL_CLASS, REPORT_PART_HEADING_CLASS, REPORT_SECTION_HEADING_CLASS } from "../artefactPresentation";
import type { Selection } from "./DetailPanel";
import { CitationMarker } from "./Documents";
import type { TocGraph } from "./types";

type Report = NonNullable<TocGraph["report"]>;

const P = `mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`;
/** Metadata lines (the scope, the method): body size, grey. */
const GREY = P.replace("text-ink", "text-grey");
const H3 = `mt-8 ${REPORT_SECTION_HEADING_CLASS}`;
const TOKEN = /(#\d+|\b[APSLIF]\d+\b|\[\d+\])/;

/**
 * Report text with its codes and source numbers made live: a box or link code
 * ("#2", "S3") selects it on the canvas and opens its panel; "[n]" jumps to
 * the source list. Both look like the text around them.
 */
function Rich({ taskId, text, codes, sources, onSelect }: { taskId: string; text: string; codes: Map<string, Selection>; sources: Report["sources"]; onSelect: (selection: Selection) => void }) {
  return (
    <>
      {scrub(text)
        .split(TOKEN)
        .map((part, index) => {
          const cite = /^\[(\d+)\]$/.exec(part);
          const source = cite === null ? undefined : sources.find((item) => item.n === Number(cite[1]));
          if (source?.evidence_id) {
            // The Evidence search's marker: opens the source and its quote in context.
            return (
              <CitationMarker
                key={index}
                taskId={taskId}
                claim={null}
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

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="mt-2 overflow-x-auto">
      <table className={`w-full border-collapse ${REPORT_BODY_CLASS}`}>
        <thead>
          <tr>
            {head.map((cell) => (
              <th key={cell} className={`border-b border-line-2 py-1.5 pr-2 text-left ${REPORT_LABEL_CLASS}`}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, column) => (
                <td key={column} className="border-b border-line py-2 pr-2 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReportBody({ taskId, report, graph, onSelect }: { taskId: string; report: Report; graph: TocGraph; onSelect: (selection: Selection) => void }) {
  const codes = codeTargets(graph);
  const rich = (text: string) => <Rich taskId={taskId} text={text} codes={codes} sources={report.sources} onSelect={onSelect} />;
  const { summary } = report;
  const goal = summary.goal.replace(/\.?$/, ".");
  const scope = [`Population: ${summary.population}`, summary.time_horizon !== null ? `Time horizon: ${summary.time_horizon}` : null, `Directly influenced: up to ${summary.directly_influenced}`]
    .filter(Boolean)
    .join(" · ");
  const setAside = graph.pathways.filter((pathway) => pathway.status === "set_aside");
  return (
    <>
      <h3 className={H3}>Summary</h3>
      <p className={P}>
        <b>Goal:</b> {scrub(goal)}{" "}
        {summary.if_then_because.split(/\b(If|then|because)\b/).map((part, index) =>
          index % 2 === 1 ? <i key={index}>{part}</i> : <span key={index}>{rich(part)}</span>,
        )}
      </p>
      <p className={GREY}>{scrub(scope)}.</p>
      {summary.context !== "" && (
        <p className={P}>
          <b>Context.</b> {rich(summary.context)}
        </p>
      )}
      {summary.weakest_links !== "" && (
        <p className={P}>
          <b>Weakest critical links.</b> {rich(summary.weakest_links)}
        </p>
      )}

      <h3 className={H3}>How change happens</h3>
      {report.pathways.map((pathway, index) => (
        <p key={index} className={P}>
          <b>{scrub(pathway.title.replace(/\.?$/, "."))}</b> {rich(pathway.paragraph)}
        </p>
      ))}
      {setAside.length > 0 && (
        <>
          <p className={`mt-4 ${REPORT_LABEL_CLASS}`}>Considered and set aside</p>
          <ul className={`mt-1 max-w-[44em] ${REPORT_BODY_CLASS}`}>
            {setAside.map((pathway) => (
              <li key={pathway.pathway_id}>
                <b>{scrub(pathway.label)}.</b>
                {pathway.reason !== null && <> {scrub(pathway.reason)}</>}
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className={H3}>Assumptions and evidence</h3>
      <Table
        head={["Code", "Assumption", "Kind", "Verdict", "Why", "Sources"]}
        rows={report.assumptions.map((row) => [
          rich(row.code),
          scrub(row.statement),
          row.kind === "risk" ? "Risk" : "Assumption",
          row.verdict,
          rich(row.why),
          rich(row.sources.map((n) => `[${n}]`).join("")),
        ])}
      />

      <h3 className={H3}>What to test and measure</h3>
      <Table
        head={["Weak link", "Question", "Indicator and data", "Test and learn"]}
        rows={report.tests.map((row) => [rich(row.link), rich(row.question), rich(row.indicator), rich(row.test_and_learn)])}
      />

      <h3 className={H3}>Sources and method</h3>
      {report.sources.length > 0 && (
        <p className={P}>
          {report.sources.map((source, index) => (
            <span key={source.n} id={`toc-source-${source.n}`}>
              {index > 0 && " · "}[{source.n}]{" "}
              {source.url !== null ? (
                <a href={source.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {scrub(source.citation)}
                </a>
              ) : (
                scrub(source.citation)
              )}
            </span>
          ))}
        </p>
      )}
      <p className={GREY}>{scrub(report.method)}</p>
    </>
  );
}

/**
 * Detailed information: a short narrative report beside the canvas (C38),
 * and the PDF. Five sections, the report's four text styles only; nothing
 * collapses, so the print view shows it whole.
 */
export function DetailedInformation({ taskId, graph, onSelect }: { taskId: string; graph: TocGraph; onSelect: (selection: Selection) => void }) {
  return (
    <section aria-label="Detailed information" className="mt-10 border-t border-line pt-6">
      <div className="flex items-center justify-between gap-4 pb-2">
        <h2 className={REPORT_PART_HEADING_CLASS}>Detailed information</h2>
        <Button variant="secondary" size="sm" className="print-hide border border-navy" onClick={() => window.print()}>
          Download as PDF
        </Button>
      </div>
      {graph.report === null || graph.report === undefined ? (
        <p className={P}>The report is written when the evidence check finishes.</p>
      ) : (
        <ReportBody taskId={taskId} report={graph.report} graph={graph} onSelect={onSelect} />
      )}
    </section>
  );
}
