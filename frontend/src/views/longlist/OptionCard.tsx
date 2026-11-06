import { Fragment, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import type { components } from "../../api/gen/types";
import { useOption, usePlan, useTask } from "../../api/queries";
import { errorCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { isRunActive } from "../scopingActivity";
import { useDocumentTitle } from "../../lib/title";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { cn } from "../../ui/brand/cn";
import { ReauthRedirect } from "../../ui/feedback";
import { SectionDisclosure, type SidebarEntry } from "../ArtefactOutline";
import { LIFECYCLE_PAGE_CLASS } from "../listPageChrome";
import { REPORT_TITLE_CLASS, ReportPage } from "../reportPage";
import { REPORT_BODY_CLASS, referenceParts } from "../artefactPresentation";
import {
  authorityWords,
  GRID_COLUMN_LINES,
  LEVEL_MARKED_CLASS,
  LEVEL_MIDDLE_CLASS,
  LEVEL_WORDS,
  LINE_NAMES,
  MIDDLE_WORD,
  NOT_EVALUATED_LINE,
  outcomeCoverage,
  outcomeCoverageWords,
  targetCoverage,
  targetCoverageWords,
  actsOnParts,
  NO_IN_SCOPE_WORDS,
  PROFILE_LINE_KEYS,
  capitalise,
  constraintLabel,
  constraintNotices,
  deliveredLeadInParts,
  leverLineParts,
  ABSTRACTS_NOTE,
  documentFactLines,
  documentsToggleWords,
  exclusionLine,
  profileSentenceParts,
  type SentencePart,
  originLabel,
  relationLabel,
} from "./longlistPresentation";
import { ExcludeReasonForm, OptionActionButton, ShortlistToggle, useOptionActions } from "./optionActions";
import { RetryCard } from "../../ui/feedback/RetryCard";
import { LINK_CLASS } from "../../ui/brand/inlineActions";
import { InfoHint } from "./InfoHint";
import { BulletList } from "../../ui/brand/BulletList";
import { ChevronIcon } from "../../ui/brand/icons";
import { OptionDossier } from "./OptionDossier";

type OptionDocumentOut = components["schemas"]["OptionDocumentOut"];

/** A sentence's runs, its takeaways in Semibold Navy and the joining words
 *  regular (round 12, owner): the profile sentence, the lever and the
 *  delivery setting. */
function SentenceRuns({ parts }: { parts: readonly SentencePart[] }) {
  return (
    <>
      {parts.map((part, index) =>
        part.strong ? (
          <strong key={index} className="font-semibold text-navy">
            {scrub(part.text)}
          </strong>
        ) : (
          <Fragment key={index}>{scrub(part.text)}</Fragment>
        ),
      )}
    </>
  );
}

/** A heading inside a block (round 12, owner): the report's subheading,
 *  the case study title's Lead Bold Navy, Body below `md`. */
const BLOCK_SUBHEADING_CLASS = "text-lead font-bold text-navy max-md:text-body";

/** A document group's heading ("Evaluated it · 3"): Body Semibold Navy. */
const DOCUMENT_GROUP_HEADING_CLASS = "text-body font-semibold text-navy";

/** Documents shown in a group before "Show all N". */
const DOCUMENTS_SHOWN = 5;
/** Design features shown on the card (R63; § 2.5). */
const FEATURES_SHOWN = 6;

/** One document, two lines (round 12, owner): the reference in the
 *  References form (authors, year, the title as the link to its dossier,
 *  which opens over the card, the venue), then one Meta Grey
 *  line of its facts joined by the middot, nothing under it. */
/** A reference's title as the report's References show it (round 12, item
 *  28): Navy over a Line 2 underline that turns Navy on hover. */
const REFERENCE_TITLE_LINK_CLASS =
  "text-navy underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 hover:decoration-navy";

function DocumentLine({
  taskId,
  optionId,
  document,
}: {
  taskId: string | undefined;
  optionId: string;
  document: OptionDocumentOut;
}) {
  const linked = document.task_source_snapshot_id != null && taskId !== undefined;
  // The dossier opens over the card, the reader staying on it (round 12,
  // owner): the same path with `source` and `option`, which the card reads.
  const dossier = linked
    ? { search: `?${new URLSearchParams({ source: String(document.task_source_snapshot_id), option: optionId })}` }
    : null;
  // The References form (round 12): authors, year, the title, the venue; a
  // part the read lacks is left out, so the title alone still reads.
  const { lead, title, afterTitle, venue } = referenceParts({
    title: scrub(document.title),
    year: document.year ?? null,
    venue: document.venue == null ? null : scrub(document.venue),
    authorships: (document.authors ?? []).map((name) => ({ name: scrub(name) })),
  });
  const facts = documentFactLines(document).map(scrub);
  return (
    <li>
      <p className="text-body text-ink [overflow-wrap:anywhere]">
        {lead}
        {dossier !== null ? (
          <Link className={REFERENCE_TITLE_LINK_CLASS} to={dossier}>
            {title}
          </Link>
        ) : (
          <span className="text-navy">{title}</span>
        )}
        {afterTitle}
        {venue !== null && <span className="text-grey"> {venue}</span>}
      </p>
      {/* Its facts at Body in Grey (round 12, owner): where and how, then
          the outcome on its own line. */}
      {facts.map((fact) => (
        <p key={fact} className="mt-1 text-body text-grey">
          {fact}
        </p>
      ))}
    </li>
  );
}

/** The documents behind the option, closed by default (round 12, owner):
 *  "Show 6 documents" / "Hide documents" after the chevron, the quiet
 *  control's look, the one disclosure language. */
function DocumentsDisclosure({
  evaluated,
  describing,
  children,
}: {
  evaluated: number;
  describing: number;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="group inline-flex min-h-6 cursor-pointer items-center gap-1 text-meta font-semibold text-grey"
      >
        <ChevronIcon
          size={12}
          className={cn("shrink-0 transition-transform duration-200 ease-[var(--ease-out-strong)]", open && "rotate-90")}
        />
        <span className="underline decoration-line-2 underline-offset-[3px] transition-colors duration-150 group-hover:text-navy group-hover:decoration-navy">
          {documentsToggleWords(open, evaluated, describing)}
        </span>
      </button>
      {open && <div className="mt-3 space-y-4">{children}</div>}
    </div>
  );
}

/** One group of the disclosure: a heading with its count, five lines, then "Show all N". */
function DocumentGroup({
  heading,
  taskId,
  optionId,
  documents,
}: {
  heading: string;
  taskId: string | undefined;
  optionId: string;
  documents: OptionDocumentOut[];
}) {
  const [showAll, setShowAll] = useState(false);
  if (documents.length === 0) return null;
  const shown = showAll ? documents : documents.slice(0, DOCUMENTS_SHOWN);
  return (
    <div className="space-y-3">
      {/* A subheading, not a label (round 12, owner). */}
      <h3 className={DOCUMENT_GROUP_HEADING_CLASS}>
        {heading} · {documents.length}
      </h3>
      <ul role="list" className="space-y-3">
        {shown.map((document, index) => (
          <DocumentLine
            key={document.task_source_snapshot_id ?? `${document.title}-${index}`}
            taskId={taskId}
            optionId={optionId}
            document={document}
          />
        ))}
      </ul>
      {!showAll && documents.length > DOCUMENTS_SHOWN && (
        <Button variant="secondary" onClick={() => setShowAll(true)}>
          Show all {documents.length}
        </Button>
      )}
    </div>
  );
}

const PAGE_CLASS = `${LIFECYCLE_PAGE_CLASS} py-8`;

/** The card's sections, in order (task 046, amendment 4, R78). */
const SECTIONS = [
  // Round 12 (owner): what it is, then Evidence, then What it could take.
  { id: "how-it-works", title: "How it works" },
  { id: "evidence-base", title: "Evidence" },
  { id: "what-it-would-take", title: "What it could take" },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

/** The sidebar lists the sections the card shows: "What it would take" is
 *  absent for an option with no profile (R37). */
const sidebarEntries = (hasProfile: boolean): SidebarEntry[] =>
  SECTIONS.filter(({ id }) => hasProfile || id !== "what-it-would-take").map(({ id, title }) => ({ id, title }));

/** The info glyph's name after "What it would take" (R37; round 12: the
 *  words left the heading for the glyph). */
const ESTIMATE_LABEL = "Policy Atlas's estimate";
/** Its tooltip (round 12, owner). */
const ESTIMATE_NOTE = "Policy Atlas's estimate from the abstracts. Not an assessment.";

/**
 * The small "i" after a section's heading (round 12, owner), its tooltip
 * saying what the block is. The heading is a disclosure button, and a
 * button cannot hold another, so the glyph's own button sits beside the
 * heading's, placed just after the title's last word: measured from the
 * title's text and kept there as the column reflows or the fonts load. A
 * 16 px glyph in a 24 px target, Grey turning Navy; focusable, and the
 * tooltip opens on hover and on keyboard focus.
 */
function HeadingInfo({ sectionId, label, note }: { sectionId: string; label: string; note: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const holder = ref.current?.parentElement;
    if (holder == null) return;
    const measure = () => {
      const title = holder.querySelector(`#${sectionId} button > span`);
      if (title === null || typeof document.createRange !== "function") return;
      const range = document.createRange();
      range.selectNodeContents(title);
      if (typeof range.getClientRects !== "function") return;
      const rects = range.getClientRects();
      const last = rects.length > 0 ? rects[rects.length - 1] : null;
      if (last === null || last.width === 0) return;
      const box = holder.getBoundingClientRect();
      setPlace({ left: last.right - box.left + 6, top: last.top + last.height / 2 - box.top });
    };
    measure();
    void document.fonts?.ready.then(measure);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(holder);
    return () => observer.disconnect();
  }, [sectionId]);
  return (
    <span
      ref={ref}
      className={cn("print-hide absolute -translate-y-1/2", place === null && "invisible")}
      style={place === null ? undefined : { left: place.left, top: place.top }}
    >
      <InfoHint label={label} note={note} />
    </span>
  );
}

/** A card section on the report's disclosure (EB as-is): the heading row
 *  toggles, `summary` is the one line shown while collapsed. `summaryNode`
 *  replaces that line with a node (the profile's row of cells only). */
function CardSection({
  id,
  summary = "",
  children,
  defaultOpen = true,
  collapsible = false,
  info,
  summaryNode,
}: {
  id: SectionId;
  /** The line shown while shut (a collapsible block only). */
  summary?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  /** Only What it could take folds (round 12, owner); the short blocks are
   *  always open, with no Show / Hide. */
  collapsible?: boolean;
  /** An "i" after the heading: its name and its tooltip. */
  info?: { label: string; note: string };
  summaryNode?: ReactNode;
}) {
  const { title } = SECTIONS.find((section) => section.id === id) ?? { title: id };
  // Each block under the one rule, its sentences at Body (round 11, item 4:
  // no Lead on the card).
  return (
    <div className="relative border-t border-line pt-6">
      <SectionDisclosure
        id={id}
        section={{ title, role: "standard", blocks: summary === "" ? null : [{ prose: summary }] }}
        defaultOpen={defaultOpen}
        collapsible={collapsible}
        summaryNode={summaryNode}
      >
        <div className={cn("max-w-prose-measure space-y-4", REPORT_BODY_CLASS)}>{children}</div>
      </SectionDisclosure>
      {info !== undefined && <HeadingInfo sectionId={id} label={info.label} note={info.note} />}
    </div>
  );
}

/** The authority words beside "Who decides" (R70), in the column's one
 *  type: Navy Semibold, Grey when it is unclear who can act (round 10: no
 *  tint, as the level words). */
const AUTHORITY_WORD_CLASS: Record<"within_your_power" | "needs_action_by" | "unclear", string> = {
  within_your_power: "text-meta font-semibold text-navy",
  needs_action_by: "text-meta font-semibold text-navy",
  unclear: "text-meta font-semibold text-grey",
};

/** A line's level word in the one Navy look after a 6 px Navy square, the
 *  word saying the direction ("Quicker", "Higher"); "Middle" in Grey when the
 *  line has no mark (round 10, lead ruling on finding 7). */
function LevelWord({ line, mark }: { line: keyof typeof LEVEL_WORDS; mark: "less" | "more" | null }) {
  return mark === null ? (
    <span className={LEVEL_MIDDLE_CLASS}>{MIDDLE_WORD}</span>
  ) : (
    <span className={LEVEL_MARKED_CLASS}>
      <span aria-hidden="true" className="inline-block size-1.5 flex-none bg-navy" />
      {LEVEL_WORDS[line][mark]}
    </span>
  );
}

/** A notice's word in its tone: Red only for a failure (an exclusion, a
 *  break), Navy for a likely shortfall or no in-scope evidence, Grey when it
 *  cannot be said. */
const NOTICE_WORD_CLASS = { red: "font-semibold text-red", navy: "font-semibold text-navy", grey: "font-semibold text-grey" } as const;

/** The profile table's cells: three columns from `sm` up; stacked blocks below it, so the
 *  sentence keeps the full width at 390 px (22b, after the browser check). */
const PROFILE_NAME_CELL = "block pt-2.5 pr-4 align-top text-meta font-normal text-grey sm:w-44 sm:table-cell sm:py-2.5";
const PROFILE_WORD_CELL = "block pr-4 align-top sm:w-40 sm:table-cell sm:py-2.5";
const PROFILE_SENTENCE_CELL = "block pb-2.5 align-top sm:table-cell sm:py-2.5";

/**
 * The option card (contract deliverable 9, D15) on the report's page chrome:
 * assembled from the discovery, evidence-profile and constrain passes — no
 * writer call, no summary prose beyond these templated sentences. The
 * documents render as the report's source cards (EB-modified: the
 * most-relevant-sources card shape, with role and place chips). The words
 * "how sure" appear nowhere on this page (trust § Provenance labels; a
 * locked test).
 */
export function OptionCard() {
  const { taskId = "", optionId = "" } = useParams();
  const titleRef = useRef<HTMLHeadingElement>(null);
  const openedFor = useRef<string | null>(null);
  // An option opens at its top with focus on its title (round 12, owner
  // bug: it opened at the foot, the app's scrolling pane keeping the
  // longlist's offset). Once per option, so a dossier opening over the card
  // or an action's notice never moves the reader; a link to a section (a
  // hash) keeps its own scroll.
  useLayoutEffect(() => {
    const title = titleRef.current;
    if (title === null || openedFor.current === optionId) return;
    openedFor.current = optionId;
    if (window.location.hash !== "") return;
    for (let node = title.parentElement; node !== null && node !== document.body; node = node.parentElement) {
      const overflowY = getComputedStyle(node).overflowY;
      if (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") node.scrollTop = 0;
    }
    if (document.scrollingElement != null) document.scrollingElement.scrollTop = 0;
    title.focus({ preventScroll: true });
  });
  const task = useTask(taskId);
  const plan = usePlan(taskId);
  const option = useOption(taskId, optionId);
  // Task 045 (F15): a refused exclude / include says so under the header.
  const actions = useOptionActions(taskId, isRunActive(task.data));
  // A document's dossier, open over the card (round 12): Close or Back
  // returns to the card and the URL stays on it.
  const [searchParams, setSearchParams] = useSearchParams();
  const dossierSource = searchParams.get("source");
  const closeDossier = () =>
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("source");
      next.delete("option");
      return next;
    });

  useDocumentTitle(task.data?.name, option.data?.name ?? "Option");

  if (option.isPending) {
    return (
      <main aria-busy="true" aria-label="Loading the option" className={PAGE_CLASS}>
        <div className="h-4 w-40 anim-breathe bg-paper-2" />
        <div className="mt-4 h-9 w-2/3 anim-breathe bg-paper-2" />
        <div className="mt-3 h-6 w-full anim-breathe bg-paper-2" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="mt-8 h-24 anim-breathe border-t border-line bg-paper-2" />
        ))}
      </main>
    );
  }

  if (option.isError) {
    const code = errorCode(option.error);
    if (code === "unauthenticated") return <ReauthRedirect />;
    return (
      <main className={PAGE_CLASS}>
        <RetryCard copy="This option couldn't be loaded." onRetry={() => void option.refetch()} />
      </main>
    );
  }

  if (option.data === null || option.data === undefined) {
    return (
      <main className={PAGE_CLASS}>
        <Card role="status" className="p-8 text-center text-body text-grey">
          This option isn't on the longlist.
        </Card>
      </main>
    );
  }

  const item = option.data;
  const excluded = item.state === "excluded";
  // The constraint callout (R78); a judgement on the constraint the option is already
  // excluded for is said once, by the exclusion line (30b).
  const excludedFor = item.state === "excluded" ? constraintLabel(item.exclusion?.constraint ?? "") : null;
  const notices = constraintNotices(item.judgements ?? [], item.guesses ?? []).filter(
    (notice) => excludedFor === null || notice.constraint !== excludedFor,
  );
  // One entry per document, evaluated first then by quality (the read model, R67).
  const documents = item.documents ?? [];
  const evaluatedDocuments = documents.filter((document) => document.role === "evaluated");
  const describingDocuments = documents.filter((document) => document.role !== "evaluated");
  const placeSentences = item.place_sentences ?? [];
  // The plan's outcomes and how the documents cover each (round 12, owner).
  const coverage = outcomeCoverage(
    (item.evidence.outcome_counts?.by_outcome ?? []).map((entry) => entry.outcome),
    documents,
  );
  // The plan's target first (round 12, owner).
  const targetUnit = plan.data?.scoping?.target_unit?.text?.trim() ?? "";
  // The row is left out when no document's target is known.
  // The row is left out when no document's target is known.
  const targetFound = targetUnit === "" ? null : targetCoverage(targetUnit, documents);
  const target = targetFound !== null && targetFound.known > 0 ? targetFound : null;
  const profile = item.profile ?? null;
  const profileLines = profile === null ? [] : PROFILE_LINE_KEYS.map((key) => ({ key, line: profile.lines.find((line) => line.key === key) }))
    // A profile written before the ninth line existed has eight; show no empty row.
    .filter(({ key, line }) => key !== "potential_impact" || line !== undefined);
  const cellLines = profile === null ? [] : GRID_COLUMN_LINES
    // Likewise no Potential impact cell for a profile without that line.
    .filter((key) => key !== "potential_impact" || profile.lines.some((line) => line.key === key))
    .map((key) => ({
      key,
      mark: key === "ambition" ? (item.ambition ?? null) : (profile.lines.find((line) => line.key === key)?.mark ?? null),
    }));
  // The sentence's lines: those the profile carries, ambition apart.
  const sentenceLines = cellLines.filter(({ key }) => key !== "ambition");
  const ambitionMark = item.ambition ?? null;
  // One reason only: the none-fits reason says what the option does instead.
  const leverReason = (item.primary_lever_type == null ? (item.lever_none_fits_reason ?? item.lever_reason) : item.lever_reason) ?? "";
  // Each thing said once (round 10, finding 7): the lever lives in How it
  // works, the counts in the evidence line, so the grey line is where the
  // option came from and how it relates to others.
  const headerLine = [
    originLabel(item.origin, item.from_section),
    ...(item.relations ?? []).map(relationLabel),
    ...((item.also_found_as ?? []).length > 0 ? [`also found as: ${(item.also_found_as ?? []).join(", ")}`] : []),
  ].join(" · ");
  const hasNotices = excluded || item.no_in_scope_evidence || item.search_pending || notices.length > 0;

  return (
    <ReportPage entries={sidebarEntries(item.profile != null)}>
      <header className="mb-8">
        {/* The breadcrumb names the page's kind, so no "Option" label sits
            over the title (round 10, C4); the option's controls share its row. */}
        <div className="print-hide mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <nav aria-label="Breadcrumb" className="min-w-0 text-meta text-grey">
            <Link to={`/tasks/${taskId}/result?view=longlist`} className={LINK_CLASS}>
              Longlist
            </Link>
            <span aria-hidden="true" className="mx-2">/</span>
            <span>{scrub(item.name)}</span>
          </nav>
          <div className="-my-1 flex items-center gap-3">
            <ShortlistToggle
              actions={actions}
              optionId={optionId}
              shortlistState={item.shortlist?.state}
              excluded={excluded}
            />
            <OptionActionButton actions={actions} optionId={optionId} excluded={excluded} />
          </div>
        </div>
        <h1 ref={titleRef} tabIndex={-1} className={cn(REPORT_TITLE_CLASS, "outline-none", excluded && "text-grey")}>
          {scrub(item.name)}
        </h1>
        {/* What it is (round 11, item 4): the description at Body, then one
            Meta Grey line of where it came from and how it relates. */}
        <p className={cn("mt-3 max-w-prose-measure", REPORT_BODY_CLASS)}>{scrub(item.description)}</p>
        <p className="mt-2 text-meta text-grey">{scrub(headerLine)}</p>

        <ExcludeReasonForm actions={actions} optionId={optionId} className="mt-4 flex flex-wrap items-center gap-2" />

        {actions.notice !== null && (
          <p role="alert" className="mt-3 text-body text-red">
            {actions.notice.text}
          </p>
        )}

      </header>

      <CardSection id="how-it-works">
        {/* One sentence, not an eyebrow over a value (round 12, owner). */}
        <div>
          <p>
            <SentenceRuns parts={leverLineParts(item.primary_lever_type, item.secondary_lever_types)} />
          </p>
          {leverReason.trim() !== "" && <p className="text-grey">{scrub(leverReason)}</p>}
        </div>
        <p>
          <SentenceRuns parts={deliveredLeadInParts(profile?.settings, actsOnParts(profile?.acts_on))} />
        </p>
        {item.design.design_features.length > 0 && (
          // The report's Electric Blue squares (round 12, owner).
          <BulletList items={item.design.design_features.slice(0, FEATURES_SHOWN).map((feature) => capitalise(scrub(feature)))} />
        )}
      </CardSection>

      {/* The counts are the header's evidence line; the section opens with
          the evaluations' standing (round 10, C7: no opener repeating them). */}
      <CardSection id="evidence-base">
        {/* Where it has been evaluated first, then the notices, then the
            documents (round 12, owner: the Sources lines and Your outcomes
            went; the counts are the row's and the collapsed summary's). */}
        {/* With no evaluation the subheading stays and says so (round 12,
            owner), so the section never drops to the documents alone. */}
        {item.document_count > 0 && item.evaluated_count === 0 && (
          <div>
            <h3 className={BLOCK_SUBHEADING_CLASS}>Where it has been evaluated</h3>
            <p className="text-grey">{NOT_EVALUATED_LINE}</p>
          </div>
        )}
        {item.document_count > 0 && item.evaluated_count > 0 && placeSentences.length > 0 && (
              <div>
                <h3 className={BLOCK_SUBHEADING_CLASS}>Where it has been evaluated</h3>
                <dl aria-label="Where it has been evaluated" className="divide-y divide-line">
                  {placeSentences.map((entry) => (
                    <div
                      key={entry.place}
                      data-where={entry.where ? "true" : undefined}
                      className="grid gap-x-4 py-1.5 sm:grid-cols-[10rem_1fr]"
                    >
                      {/* The plan's own place carries the profile's Navy mark,
                          not a tint (round 10). */}
                      <dt className="flex items-baseline gap-1.5 text-navy">
                        {entry.where && (
                          <span aria-hidden="true" className="inline-block size-1.5 flex-none -translate-y-0.5 bg-navy" />
                        )}
                        {scrub(entry.place)}
                      </dt>
                      <dd>{scrub(entry.sentence)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
          )}
        {/* Your target and outcomes (round 12, owner): the report's
            method-table pattern, the plan's words left and their coverage
            right; the target first. Tabular figures are left off: under
            them the fallback face widens the spaces between the words, as
            the report's table found. */}
        {item.document_count > 0 && (target !== null || coverage.length > 0) && (
          <div>
            <h3 id="your-outcomes-heading" className={BLOCK_SUBHEADING_CLASS}>
              Your target and outcomes
            </h3>
            <table aria-labelledby="your-outcomes-heading" className="mt-1.5 w-full border-t border-line text-body">
              <tbody>
                {target !== null && (
                  <tr className="border-b border-line">
                    <th scope="row" className="py-1.5 pr-6 text-left align-top font-normal text-ink">
                      {scrub(target.unit)}
                    </th>
                    <td
                      className={cn(
                        "py-1.5 text-right align-top",
                        target.targeted > 0 ? "text-navy" : "text-grey",
                      )}
                    >
                      {targetCoverageWords(target)}
                    </td>
                  </tr>
                )}
                {coverage.map((entry) => {
                  const covered = entry.measured + entry.discussed > 0;
                  return (
                    <tr key={entry.outcome} className="border-b border-line">
                      <th scope="row" className="py-1.5 pr-6 text-left align-top font-normal text-ink">
                        {scrub(entry.outcome)}
                      </th>
                      <td
                        className={cn(
                          "whitespace-nowrap py-1.5 text-right align-top",
                          covered ? "text-navy" : "text-grey",
                        )}
                      >
                        {outcomeCoverageWords(entry)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {/* The notices (round 11, item 4): a flat
            block with a hairline rule, each a word in its tone then its
            sentence (round 10, finding 7: no card inside the sheet, no chips). */}
        {hasNotices && (
          <div className="max-w-prose-measure space-y-2 border-l border-line-2 pl-3">
            {excluded && item.exclusion != null && (
              <p>
                <span className={NOTICE_WORD_CLASS.red}>Excluded:</span> {scrub(exclusionLine(item.exclusion))}
              </p>
            )}
            {item.no_in_scope_evidence && item.in_scope != null && (
              <p>
                <span className={NOTICE_WORD_CLASS.navy}>{NO_IN_SCOPE_WORDS}:</span> None of its{" "}
                {item.in_scope.documents} documents pass {scrub(item.in_scope.restriction)}. It stays on the longlist
                until the scope changes.
              </p>
            )}
            {item.search_pending && <p className="text-grey">Its own evidence search is still running.</p>}
            {notices.map((notice) => (
              <p key={notice.key}>
                <span className={NOTICE_WORD_CLASS[notice.tone]}>{notice.word}:</span> {scrub(notice.text)}
              </p>
            ))}
          </div>
        )}
        {item.document_count === 0 && <p className="text-grey">No document names this option yet.</p>}
        {item.document_count > 0 && (
            <DocumentsDisclosure evaluated={evaluatedDocuments.length} describing={describingDocuments.length}>
              <p className="text-meta text-grey">{capitalise(ABSTRACTS_NOTE)}.</p>
              <DocumentGroup heading="Evaluated it" taskId={taskId} optionId={item.option_id} documents={evaluatedDocuments} />
              <DocumentGroup
                heading="Describe or recommend it"
                taskId={taskId}
                optionId={item.option_id}
                documents={describingDocuments}
              />
            </DocumentsDisclosure>
        )}
      </CardSection>
      {profile !== null && (
        <CardSection
          id="what-it-would-take"
          collapsible
          defaultOpen={false}
          info={{ label: ESTIMATE_LABEL, note: ESTIMATE_NOTE }}
          summaryNode={
            // Shut: one sentence naming only the lines not in the middle
            // (round 12, owner); open, the table of lines.
            // The takeaways in Semibold Navy, the joining words regular.
            <p className={cn("max-w-prose-measure", REPORT_BODY_CLASS)}>
              <SentenceRuns parts={profileSentenceParts(ambitionMark, sentenceLines)} />
            </p>
          }
        >
          <table className="w-full border-collapse text-left">
            <tbody className="divide-y divide-line">
              <tr>
                <th scope="row" className={PROFILE_NAME_CELL}>{LINE_NAMES.ambition}</th>
                <td className={PROFILE_WORD_CELL}>
                  <LevelWord line="ambition" mark={ambitionMark} />
                </td>
                <td className={PROFILE_SENTENCE_CELL}>{scrub(item.ambition_reason ?? "")}</td>
              </tr>
              {profileLines.map(({ key, line }) => {
                const mark = line?.mark ?? null;
                const marked = LEVEL_WORDS[key].less !== null;
                const authority = key === "who_decides" ? item.authority : null;
                return (
                  <tr key={key}>
                    <th scope="row" className={PROFILE_NAME_CELL}>{LINE_NAMES[key]}</th>
                    <td className={PROFILE_WORD_CELL}>
                      {authority != null ? (
                        <span className={AUTHORITY_WORD_CLASS[authority.label]}>{authorityWords(authority)}</span>
                      ) : marked ? (
                        <LevelWord line={key} mark={mark} />
                      ) : null}
                    </td>
                    <td className={PROFILE_SENTENCE_CELL}>{scrub(line?.sentence ?? "")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardSection>
      )}

      {dossierSource !== null && (
        <OptionDossier
          taskId={taskId}
          sourceId={dossierSource}
          optionId={searchParams.get("option") ?? optionId}
          onClose={closeDossier}
        />
      )}
    </ReportPage>
  );
}
