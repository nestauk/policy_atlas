import { useState, type ReactNode } from "react";
import { Link } from "react-router";

import { formatCount } from "../../lib/format";
import { scrub } from "../../lib/scrub";
import type { LiveSection } from "../../store";
import { BulletList } from "../../ui/brand/BulletList";
import { cn } from "../../ui/brand/cn";
import { DisclosureToggle } from "../../ui/brand/DisclosureToggle";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { COLUMN_HEADER_TEXT_CLASS, SortableColumnHeader } from "../../ui/brand/SortableColumnHeader";
import { VERDICT_COLOUR, VerdictMark } from "../../ui/brand/verdictTones";
import { Tooltip } from "../../ui/radix/Tooltip";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { CITATION_MARKER_CLASS, LiveDraft, LiveSubhead, PlaceholderLines, ReferencesSection } from "../ArtefactView";
import { FullReportExpandAllButton, FullReportExpandProvider, SectionDisclosure, type OutlineSection } from "../ArtefactOutline";
import type { SidebarEntry } from "../ArtefactOutline";
import { ContentsBeside } from "../reportPage";
import type { Selection } from "./DetailPanel";
import { CitationMarker, type TocCitation } from "./Documents";
import { isListPart, partText, pendingCitations, type TocPartKey } from "./liveReport";
import { CriticalIcon } from "./ReadingGuide";
import { VERDICT_LABEL } from "./tocModel";
import type { TocGraph, TocLink, TocPathway, Verdict } from "./types";

type Report = NonNullable<TocGraph["report"]>;

const P = `mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`;
/** Metadata lines (the scope): body size, grey. */
const GREY = P.replace("text-ink", "text-grey");
const TOKEN = /(#\d+|\b[APSLIF]\d+\b|\[\d+\])/;

const CITES = /\s*(?:\[\d+\])+/g;

/** Each judged document's row in the task (`task_source_snapshot_id`), by
 *  its judgement (`evidence_id`): a numbered source's way into its dossier. */
export type SourceRows = ReadonlyMap<string, string>;

/** A numbered source as a citation: its quote, shown in its passage when the judgement is stored. */
function sourceCitation(source: Report["sources"][number], rows: SourceRows): TocCitation {
  const evidenceId = source.evidence_id ?? null;
  return {
    n: source.n,
    evidenceId,
    title: source.title ?? source.citation,
    url: source.url,
    quote: null,
    fallbackQuote: source.quote ?? "",
    sourceId: evidenceId !== null ? (rows.get(evidenceId) ?? null) : null,
  };
}

/**
 * Report text with its codes and source numbers made live: a box or
 * connection code ("#2", "S3") selects it on the canvas and opens its panel;
 * "[n]" opens the source's quote in context beside the sentence it grounds,
 * as the Evidence search does: the sentence may summarise, the quote is exact.
 */
type RichProps = {
  taskId: string;
  codes: Map<string, Selection>;
  sources: Report["sources"];
  rows: SourceRows;
  onSelect: (selection: Selection) => void;
  /** Opens a numbered source's dossier, by its title: the way in for a
   *  report written before sources carried their judgement. */
  onOpenReference: (title: string) => void;
};

function Rich({ text, ...props }: RichProps & { text: string }) {
  const sentences = scrub(text).split(/(?<=[.!?](?:\[\d+\])*)\s+/);
  return (
    <>
      {sentences.map((sentence, at) => (
        <span key={at}>
          {at > 0 && " "}
          <RichSentence sentence={sentence} {...props} />
        </span>
      ))}
    </>
  );
}

function RichSentence({ taskId, sentence, codes, sources, rows, onSelect, onOpenReference }: RichProps & { sentence: string }) {
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
            <CitationMarker key={index} taskId={taskId} claim={claim} citations={[sourceCitation(source, rows)]} />
          );
        }
        // A report written before sources carried their judgement: the same
        // marker, opening the source's dossier as its number in the References does.
        if (source !== undefined) {
          const title = source.title ?? source.citation;
          return (
            <button key={index} type="button" aria-label={`Source ${source.n}: ${scrub(title)}`} onClick={() => onOpenReference(title)} className={CITATION_MARKER_CLASS}>
              [{source.n}]
            </button>
          );
        }
        if (cite !== null) return part;
        const target = codes.get(part);
        if (target === undefined) return part;
        // A box or connection code: the link to it on the canvas.
        return (
          <button key={index} type="button" onClick={() => onSelect(target)} className={LINK_CLASS} aria-label={`Show ${part} on the canvas`}>
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
  ["Confident", "supported"],
  ["Not confident: evidence against", "against"],
]);

/** A verdict as text: its tone square, then the word in ink (decision 7); a
 *  word outside the vocabulary keeps its word and has no square. */
function VerdictText({ label }: { label: string }) {
  const verdict = VERDICT_OF.get(label);
  return <VerdictMark colour={verdict !== undefined ? VERDICT_COLOUR[verdict] : null} word={label} />;
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
  // The table's head (DESIGN.md § Tables): the Label style at Caption size,
  // one line, bottom-aligned, over a Line hairline; the sortable columns take
  // the shared header and its arrow.
  const TH = "border-b border-line py-1.5 pr-2 text-left align-bottom";
  const onSort = (key: SortKey) =>
    // Importance opens most central first; the others lowest first; again to reverse.
    setSort((current) => ({ key, descending: current?.key === key ? !current.descending : key === "importance" }));
  const head = (label: string, key?: SortKey) =>
    key === undefined ? (
      <th key={label} scope="col" className={cn(TH, COLUMN_HEADER_TEXT_CLASS)}>
        {/* The sortable header's box, so every label shares one baseline. */}
        <span className="inline-flex min-h-6 items-center py-1">{label}</span>
      </th>
    ) : (
      <SortableColumnHeader
        key={label}
        column={{ key, label }}
        activeSort={sort?.key ?? null}
        activeOrder={sort === null ? null : sort.descending ? "desc" : "asc"}
        onSort={onSort}
        className={TH}
      />
    );
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
                  // The critical connection's mark, as the canvas and the panel draw it.
                  <Tooltip content="Central and weakly evidenced" className="text-meta">
                    <span role="img" aria-label="Central and weakly evidenced" className="mr-1 cursor-help">
                      <CriticalIcon />
                    </span>
                  </Tooltip>
                )}
                {rich(row.code)}
              </td>
              <td className="border-b border-line py-2 pr-2 align-top">{scrub(row.statement)}</td>
              <td className="border-b border-line py-2 pr-2 align-top">
                {/* The report's square bullet, as the other capabilities' (owner, 2026-11-10). */}
                {(row.conditions ?? []).length > 0 && <BulletList items={(row.conditions ?? []).map((condition) => scrub(condition))} className="space-y-1" />}
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
        <DisclosureToggle open={all} onToggle={() => setAll((open) => !open)} className="print-hide mt-2 text-meta">
          {all ? "Hide" : `Show all ${formatCount(rows.length)} connections`}
        </DisclosureToggle>
      )}
    </div>
  );
}

/**
 * A set-aside pathway's line (§ 8): "Set aside by Policy Atlas · Too little
 * evidence for 2 of its 4 connections.", counting its connections judged not
 * enough evidence. A pathway set aside for another reason (merged, over the
 * limit) keeps the reason it was given.
 *
 * Args:
 *   pathway: The set-aside pathway.
 *   links: The theory's connections.
 *
 * Returns:
 *   The line.
 */
export function setAsideLine(pathway: Pick<TocPathway, "link_ids" | "reason">, links: readonly Pick<TocLink, "link_id" | "verdict" | "state">[]): string {
  const own = links.filter((link) => pathway.link_ids.includes(link.link_id));
  const thin = own.filter((link) => link.state !== "checking" && link.state !== "unchecked" && link.verdict === "not_sure_insufficient").length;
  const total = pathway.link_ids.length;
  const why =
    thin > 0
      ? `Too little evidence for ${formatCount(thin)} of its ${formatCount(total)} ${total === 1 ? "connection" : "connections"}.`
      : pathway.reason !== null && pathway.reason.trim() !== ""
        ? pathway.reason.trim()
        : null;
  return why === null ? "Set aside by Policy Atlas." : `Set aside by Policy Atlas · ${why}`;
}

/** The page's anchor for each report section (the contents point here). */
export const SECTION_ID: Readonly<Record<Exclude<TocPartKey, "title" | "verdict" | "question" | "in_brief">, string>> = {
  summary: "toc-summary",
  pathways: "toc-routes",
  how_it_could_fail: "toc-fail",
  tests: "toc-tests",
  found_routes: "toc-expand",
  supporting_activities: "toc-supporting",
  assumptions: "toc-assumptions",
  references: "references",
};

/** The parts that take the paper's full width under the narrative and its
 *  contents: the Assumptions table and the References (owner, 2026-11-10). */
const WIDE_PARTS: ReadonlySet<TocPartKey> = new Set(["assumptions", "references"]);

/** A section of the report as the shared disclosure reads it. */
function outline(title: string): OutlineSection {
  return { title, role: "standard" };
}

/** The committed report's sections in today's order (§ 8), each with its
 *  page anchor: the contents list and the page read the same list. */
export function reportSections(report: Report): { id: string; title: string }[] {
  const fail = report.how_it_could_fail ?? report.summary.weakest_links;
  return [
    { id: SECTION_ID.summary, title: "Summary" },
    { id: SECTION_ID.pathways, title: "Pathways" },
    ...(fail !== "" ? [{ id: SECTION_ID.how_it_could_fail, title: "How it could fail" }] : []),
    ...(report.tests.length > 0 ? [{ id: SECTION_ID.tests, title: "What to test first" }] : []),
    ...((report.expansions ?? []).length > 0 ? [{ id: SECTION_ID.found_routes, title: "How it could be expanded" }] : []),
    ...((report.supporting_activities ?? []).length > 0 ? [{ id: SECTION_ID.supporting_activities, title: "Supporting activities" }] : []),
    { id: SECTION_ID.assumptions, title: "Assumptions" },
    ...(report.sources.length > 0 ? [{ id: SECTION_ID.references, title: "References" }] : []),
  ];
}

/** The live report's contents: its sections as the skeleton set them out. */
export function liveSections(parts: ReadonlyMap<TocPartKey, LiveSection>): SidebarEntry[] {
  return [...parts.entries()]
    .filter(([key]) => key in SECTION_ID)
    .sort(([, left], [, right]) => left.index - right.index)
    .map(([key, section]) => ({ id: SECTION_ID[key as keyof typeof SECTION_ID], title: section.title }));
}

/**
 * The committed report under the canvas (C38), in the shared report page's
 * sections (task 054, A14): each section a disclosure with its `h2`, folding
 * with the page's expand state; the content and its order as they were
 * (decision 4). The references are the shared References.
 *
 * Args:
 *   taskId: The task.
 *   graph: The theory, with its report.
 *   rows: Each judgement's document row, for the dossiers.
 *   arriving: The swap's fade class for what the committed report brings.
 *   onSelect: Selects a box or connection on the canvas.
 *   onPathway: Shows a pathway on the canvas.
 *   onOpenReference: Opens a reference's dossier, by its title.
 */
export function ReportBody({
  taskId,
  graph,
  rows,
  arriving,
  onSelect,
  onPathway,
  onOpenReference,
}: {
  taskId: string;
  graph: TocGraph;
  rows: SourceRows;
  arriving: string;
  onSelect: (selection: Selection) => void;
  onPathway: (pathwayId: string) => void;
  onOpenReference: (title: string) => void;
}) {
  const report = graph.report;
  if (report == null) return null;
  const codes = codeTargets(graph);
  const rich = (text: string) => <Rich taskId={taskId} text={text} codes={codes} sources={report.sources} rows={rows} onSelect={onSelect} onOpenReference={onOpenReference} />;
  const { summary } = report;
  const fail = report.how_it_could_fail ?? summary.weakest_links;
  const setAside = graph.pathways.filter((pathway) => pathway.status === "set_aside");
  const LIST = `mt-2 max-w-[44em] list-decimal space-y-1.5 pl-5 ${REPORT_BODY_CLASS}`;
  // A report before toc_report_v7 has no question or verdict reason: it keeps its Goal and its own whole-programme line.
  const older = report.verdict_reason == null;
  const supporting = report.supporting_activities ?? [];
  const expansions = report.expansions ?? [];
  const section = (id: string, title: string, children: ReactNode) => (
    <SectionDisclosure key={id} id={id} section={outline(title)} collapsible defaultOpen={false} arrivingClass={arriving}>
      <div className={arriving}>{children}</div>
    </SectionDisclosure>
  );
  return (
    <FullReportExpandProvider>
      <div className={`mb-4 flex justify-end ${arriving}`}>
        <FullReportExpandAllButton />
      </div>
      {/* The narrative beside the contents; the Assumptions table and the
          References under it take the paper's full width (owner, 2026-11-10). */}
      <ContentsBeside entries={reportSections(report)}>
      {section(
        SECTION_ID.summary,
        "Summary",
        <>
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
        </>,
      )}
      {section(
        SECTION_ID.pathways,
        "Pathways",
        <>
          {report.pathways.map((pathway, index) => {
            const title = scrub(pathway.title.replace(/[.:]?$/, ""));
            return (
              <div key={index} className="mt-4 max-w-[44em]">
                <h3 className="text-lead font-bold text-navy">
                  {pathway.pathway_id != null ? (
                    <button type="button" className="cursor-pointer text-left hover:underline" onClick={() => onPathway(pathway.pathway_id as string)} aria-label={`Show the pathway ${title} on the canvas`}>
                      {title}
                    </button>
                  ) : (
                    title
                  )}
                  {pathway.strength != null && <span className="font-normal"> ({pathway.strength})</span>}
                </h3>
                <p className={`mt-1 ${REPORT_BODY_CLASS}`}>{rich(pathway.paragraph)}</p>
              </div>
            );
          })}
          {/* A pathway Policy Atlas set aside: its name in Grey, then who set
              it aside and why (§ 8). No control: Include again waits (S11). */}
          {setAside.map((pathway) => (
            <div key={pathway.pathway_id} data-testid="set-aside-pathway" className="mt-4 max-w-[44em]">
              <h3 className="text-lead font-bold text-grey">{scrub(pathway.label.replace(/[.:]?$/, ""))}</h3>
              <p className={cn(GREY, "mt-1")}>{setAsideLine(pathway, graph.links)}</p>
            </div>
          ))}
        </>,
      )}
      {fail !== "" && section(SECTION_ID.how_it_could_fail, "How it could fail", <p className={P}>{rich(fail)}</p>)}
      {report.tests.length > 0 &&
        section(
          SECTION_ID.tests,
          "What to test first",
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
          </ol>,
        )}
      {expansions.length > 0 &&
        section(
          SECTION_ID.found_routes,
          "How it could be expanded",
          <>
            <p className={P}>
              The evidence describes {expansions.length === 1 ? "a route" : `${expansions.length} routes`} your diagram does not show. You can add{" "}
              {expansions.length === 1 ? "it" : "any of them"} from Suggestions, beside the canvas.
            </p>
            <BulletList
              className={`mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`}
              items={expansions.map((route) => {
                // Live: a route the user accepted is on the canvas now, as a pathway of that name.
                const added = graph.pathways.some((pathway) => pathway.label === route.label && pathway.status === "kept");
                return (
                  <>
                    <b>{scrub(route.label.replace(/\.?$/, "."))}</b>
                    {route.kind === "failure" && <i> (a way it could go wrong)</i>} {rich(route.sentence)}
                    {added && <span className="ml-2 text-meta font-semibold text-green-deep">Added to your theory</span>}
                  </>
                );
              })}
            />
          </>,
        )}
      {supporting.length > 0 &&
        section(
          SECTION_ID.supporting_activities,
          "Supporting activities",
          <BulletList className={`mt-2 max-w-[44em] ${REPORT_BODY_CLASS}`} items={supporting.map((text) => rich(text))} />,
        )}
      </ContentsBeside>
      {section(
        SECTION_ID.assumptions,
        "Assumptions",
        <>
          <p className={P}>
            Each connection in the theory corresponds to a causal assumption. The Importance measure indicates either the share of success pathways that go through the connection, or that it is a risk connection leading to a failure.
          </p>
          <AssumptionsTable rows={report.assumptions} rich={rich} />
        </>,
      )}
      {report.sources.length > 0 && (
        <ReferencesSection
          references={report.sources.map((source) => ({
            n: source.n,
            title: source.title ?? source.citation,
            year: source.year ?? null,
            venue: source.venue ?? null,
            url: source.url,
            authorships: (source.authors ?? []).map((name) => ({ name })),
          }))}
          onOpenReference={onOpenReference}
        />
      )}
      <p className={GREY}>
        These are the documents the report cites.{" "}
        <Link to={`/tasks/${taskId}/sources/all`} className={LINK_CLASS}>
          See every document found in the Sources tab
        </Link>
        .
      </p>
    </FullReportExpandProvider>
  );
}

/**
 * The report's sections while it is written (task 054, A13): each in its
 * page place, its placeholder lines until its words arrive, then the
 * model's words paced in, its "[n]" markers as the muted "[·]" chips with
 * their sources' names on hover. The part being written reads "◆ Writing".
 * Through the shared live pieces, so the page reads as the Evidence search's
 * live report does.
 *
 * Args:
 *   parts: The live parts.
 *   active: The part being written now.
 *   sources: Each numbered source's short name, by its number.
 *   still: The marks and lines hold still (reduced motion, a lapsed stream).
 */
export function LiveReportBody({
  parts,
  active,
  sources,
  still,
}: {
  parts: ReadonlyMap<TocPartKey, LiveSection>;
  active: TocPartKey | null;
  sources: ReadonlyMap<string, string>;
  still: boolean;
}) {
  const sections = [...parts.entries()]
    .filter(([key]) => key in SECTION_ID)
    .sort(([, left], [, right]) => left.index - right.index);
  // As the committed report: the narrative beside the contents, the wide parts under it.
  const narrative = sections.filter(([key]) => !WIDE_PARTS.has(key));
  const wide = sections.filter(([key]) => WIDE_PARTS.has(key));
  const render = ([key, section]: (typeof sections)[number]) => {
    const id = SECTION_ID[key as keyof typeof SECTION_ID];
    const writing = key === active;
    const text = key === "references" ? "" : partText(key, section);
    const marked = pendingCitations(text, sources);
    return (
      <SectionDisclosure
        key={id}
        id={id}
        section={outline(section.title)}
        collapsible={false}
        defaultOpen
        busy={writing}
        subhead={
          <LiveSubhead
            section={{ ...section, role: "standard", sources: undefined }}
            active={writing}
            activity="Writing"
            terminal={false}
            still={still}
          />
        }
      >
        {marked.text.trim() === "" ? (
          <PlaceholderLines index={section.index} still={still} />
        ) : (
          <LiveDraft draft={marked.text} claims={marked.claims} complete={false} layout={isListPart(key) ? "list" : "prose"} />
        )}
      </SectionDisclosure>
    );
  };
  return (
    <>
      <ContentsBeside entries={liveSections(parts)}>{narrative.map(render)}</ContentsBeside>
      {wide.map(render)}
    </>
  );
}
