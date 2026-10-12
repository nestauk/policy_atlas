import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import type { components } from "../../api/gen/types";
import { useExcludeOption, useIncludeOption } from "../../api/mutations";
import { useOption, useTask } from "../../api/queries";
import { errorCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { isRunActive } from "../scopingActivity";
import { useDocumentTitle } from "../../lib/title";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { ReauthRedirect } from "../../ui/feedback";
import { REPORT_BODY_CLASS } from "../artefactPresentation";
import { SectionDisclosure, type SidebarEntry } from "../ArtefactOutline";
import { LIFECYCLE_PAGE_CLASS } from "../listPageChrome";
import { REPORT_TITLE_CLASS, ReportKindRow, ReportPage } from "../reportPage";
import {
  actionFailedNotice,
  authorityWords,
  GRID_COLUMN_LINES,
  LEVEL_WORD_CLASS,
  LEVEL_WORDS,
  LINE_NAMES,
  MIDDLE_WORD,
  PROFILE_LINE_KEYS,
  capitalise,
  constraintLabel,
  constraintNotices,
  deliveredLeadIn,
  documentsSummary,
  evidenceOpener,
  evidenceSignal,
  leverLine,
  noOutcomeMeasuredLine,
  originLabel,
  outcomeCountLabel,
  placeWithDetail,
  relationLabel,
  servesOutcome,
} from "./longlistPresentation";

type OptionDocumentOut = components["schemas"]["OptionDocumentOut"];

/** Documents shown in a group before "Show all N". */
const DOCUMENTS_SHOWN = 5;
/** Design features shown on the card (R63; § 2.5). */
const FEATURES_SHOWN = 6;

/** The names that join the parts of a document's second line. */
const Dot = () => <span aria-hidden="true"> · </span>;

/** One document in the disclosure (task 046, amendment 4, R81): the linked title; a grey line of
 *  programme, place (the level below in brackets), the folded kind and what it measured; a grey
 *  line of tier, evidence type and year; "+N more" to the dossier when several records name it. */
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
  const dossier = linked
    ? `/tasks/${taskId}/sources/all?source=${document.task_source_snapshot_id}&option=${optionId}`
    : null;
  const { place, detail } = placeWithDetail(document.place, document.place_detail);
  const recordParts: ReactNode[] = [];
  if (linked && document.programme_name != null && document.programme_name !== "") {
    recordParts.push(<strong key="programme" className="font-bold">{scrub(document.programme_name)}</strong>);
  }
  if (linked && place !== null) {
    recordParts.push(
      <span key="place">
        {scrub(place)}
        {detail !== null && <span className="text-grey"> ({scrub(detail)})</span>}
      </span>,
    );
  }
  if (linked && document.tried_on_kind != null && document.tried_on_kind !== "") {
    recordParts.push(<span key="kind">{scrub(document.tried_on_kind)}</span>);
  }
  if (linked && document.measured != null && document.measured !== "") {
    recordParts.push(<span key="measured">{scrub(document.measured)}</span>);
  }
  const qualityLine = [document.tier, document.evidence_type, document.year]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .map((part) => scrub(String(part)))
    .join(" · ");
  const more = (document.records_count ?? 0) - 1;
  return (
    <li>
      <p className={`${REPORT_BODY_CLASS} font-bold`}>
        {dossier !== null ? (
          <Link className="underline underline-offset-2" to={dossier}>
            {scrub(document.title)}
          </Link>
        ) : (
          scrub(document.title)
        )}
      </p>
      {recordParts.length > 0 && (
        <p className="text-meta text-grey">
          {recordParts.flatMap((part, index) => (index === 0 ? [part] : [<Dot key={`dot-${index}`} />, part]))}
        </p>
      )}
      {qualityLine !== "" && <p className="text-meta text-grey">{qualityLine}</p>}
      {dossier !== null && more > 0 && (
        <p className="text-meta">
          <Link className="text-blue underline underline-offset-2" to={dossier}>
            +{more} more
          </Link>
        </p>
      )}
    </li>
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
      <p className="font-bold text-navy">
        {heading} · {documents.length}
      </p>
      <ul role="list" className="grid gap-3">
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
  { id: "how-it-works", title: "How it works" },
  { id: "what-it-would-take", title: "What it would take" },
  { id: "evidence-base", title: "Evidence" },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

/** The sidebar lists the sections the card shows: "What it would take" is
 *  absent for an option with no profile (R37). */
const sidebarEntries = (hasProfile: boolean): SidebarEntry[] =>
  SECTIONS.filter(({ id }) => hasProfile || id !== "what-it-would-take").map(({ id, title }) => ({ id, title }));

/** The label beside the profile section's heading, in both states (R37). */
const ESTIMATE_LABEL = "Policy Atlas's estimate";

/** A card section on the report's disclosure (EB as-is): the heading row
 *  toggles, `summary` is the one line shown while collapsed. `summaryNode`
 *  replaces that line with a node (the profile's row of cells only). */
function CardSection({
  id,
  summary,
  children,
  defaultOpen = true,
  meta,
  summaryNode,
}: {
  id: SectionId;
  summary: string;
  children: ReactNode;
  defaultOpen?: boolean;
  meta?: ReactNode;
  summaryNode?: ReactNode;
}) {
  const { title } = SECTIONS.find((section) => section.id === id) ?? { title: id };
  return (
    <SectionDisclosure
      id={id}
      section={{ title, role: "standard", blocks: summary === "" ? null : [{ prose: summary }] }}
      defaultOpen={defaultOpen}
      collapsible
      meta={meta}
      summaryNode={summaryNode}
    >
      <div className={`max-w-prose-measure space-y-3 ${REPORT_BODY_CLASS}`}>{children}</div>
    </SectionDisclosure>
  );
}

/** The authority word's tint beside "Who decides" (R70): pale tint, dark text, as the level words. */
const AUTHORITY_WORD_CLASS: Record<"within_your_power" | "needs_action_by" | "unclear", string> = {
  within_your_power: "inline-block bg-green-tint px-1.5 py-0.5 text-meta font-semibold leading-tight text-navy",
  needs_action_by: "inline-block bg-yellow-tint px-1.5 py-0.5 text-meta font-semibold leading-tight text-navy",
  unclear: "inline-block bg-paper-2 px-1.5 py-0.5 text-meta font-semibold leading-tight text-grey",
};

/** The profile table's cells: three columns from `sm` up; stacked blocks below it, so the
 *  sentence keeps the full width at 390 px (22b, after the browser check). */
const PROFILE_NAME_CELL = "block pt-2.5 pr-4 align-top font-semibold text-navy sm:w-48 sm:table-cell sm:py-2.5";
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
  const task = useTask(taskId);
  const option = useOption(taskId, optionId);
  const excludeOption = useExcludeOption(taskId);
  const includeOption = useIncludeOption(taskId);
  const [excluding, setExcluding] = useState(false);
  const [reason, setReason] = useState("");
  // Task 045 (F15): a refused exclude / include says so under the header.
  const [notice, setNotice] = useState<string | null>(null);
  const walkActive = isRunActive(task.data);

  useDocumentTitle(task.data?.name, option.data?.name ?? "Option");

  if (option.isPending) {
    return (
      <main aria-busy="true" aria-label="Loading the option" className={PAGE_CLASS}>
        <div className="h-4 w-40 animate-pulse bg-paper-2" />
        <div className="mt-4 h-9 w-2/3 animate-pulse bg-paper-2" />
        <div className="mt-3 h-6 w-full animate-pulse bg-paper-2" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="mt-8 h-24 animate-pulse border-t border-line bg-paper-2" />
        ))}
      </main>
    );
  }

  if (option.isError) {
    const code = errorCode(option.error);
    if (code === "unauthenticated") return <ReauthRedirect />;
    return (
      <main className={PAGE_CLASS}>
        <Card role="alert" className="p-8 text-center text-body text-navy">
          This option couldn't be loaded.{" "}
          <button
            type="button"
            className="cursor-pointer font-bold text-blue hover:underline"
            onClick={() => void option.refetch()}
          >
            Retry
          </button>
        </Card>
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
  const evidence = item.evidence;
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
  const planOutcomes = evidence.outcome_counts?.by_outcome ?? [];
  const noneMeasured = planOutcomes.length > 0 && planOutcomes.every((entry) => entry.evaluated === 0);
  const opener = evidenceOpener(item.evaluated_count, item.document_count);
  const profile = item.profile ?? null;
  const profileLines = profile === null ? [] : PROFILE_LINE_KEYS.map((key) => ({ key, line: profile.lines.find((line) => line.key === key) }));
  const cellLines = profile === null ? [] : GRID_COLUMN_LINES.map((key) => ({
    key,
    mark: key === "ambition" ? (item.ambition ?? null) : (profile.lines.find((line) => line.key === key)?.mark ?? null),
  }));
  const ambitionMark = item.ambition ?? null;
  const leverText = leverLine(item.primary_lever_type, item.secondary_lever_types);
  // One reason only: the none-fits reason says what the option does instead.
  const leverReason = (item.primary_lever_type == null ? (item.lever_none_fits_reason ?? item.lever_reason) : item.lever_reason) ?? "";
  const headerLine = [
    item.primary_lever_type == null ? "No lever fits" : capitalise(item.primary_lever_type),
    originLabel(item.origin, item.document_count, item.from_section),
    ...(item.relations ?? []).map(relationLabel),
    ...((item.also_found_as ?? []).length > 0 ? [`also found as: ${(item.also_found_as ?? []).join(", ")}`] : []),
  ].join(" · ");

  // The reason is optional (owner, 2026-09-24): blank sends none.
  const submitExclude = () => {
    const trimmed = reason.trim();
    if (excludeOption.isPending || walkActive) return;
    setNotice(null);
    excludeOption.mutate(
      trimmed === "" ? { optionId } : { optionId, reason: trimmed },
      {
        onSuccess: () => {
          setExcluding(false);
          setReason("");
        },
        onError: (error) => setNotice(actionFailedNotice(error, "The option couldn't be excluded. Try again.")),
      },
    );
  };

  const includeAgain = () => {
    if (includeOption.isPending || walkActive) return;
    setNotice(null);
    includeOption.mutate(
      { optionId },
      { onError: (error) => setNotice(actionFailedNotice(error, "The option couldn't be included again. Try again.")) },
    );
  };

  return (
    <ReportPage entries={sidebarEntries(item.profile != null)}>
      <nav aria-label="Breadcrumb" className="print-hide mb-4 text-meta text-grey">
        <Link to={`/tasks/${taskId}/result?view=longlist`} className="font-semibold text-blue underline-offset-4 hover:underline">
          Longlist
        </Link>
        <span aria-hidden="true" className="mx-2">/</span>
        <span>{scrub(item.name)}</span>
      </nav>

      <header className="mb-8">
        <ReportKindRow kind="Option">
          <div className="print-hide flex items-center gap-2">
            {excluded ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={includeOption.isPending || walkActive}
                onClick={includeAgain}
              >
                Include again
              </Button>
            ) : (
              !excluding && (
                <Button variant="secondary" size="sm" disabled={walkActive} onClick={() => setExcluding(true)}>
                  Exclude
                </Button>
              )
            )}
          </div>
        </ReportKindRow>
        <h1 className={cn(REPORT_TITLE_CLASS, excluded && "text-grey")}>{scrub(item.name)}</h1>
        <p className={`mt-3 max-w-prose-measure ${REPORT_BODY_CLASS}`}>{scrub(item.description)}</p>
        <p className="mt-2 text-body text-grey">{scrub(headerLine)}</p>
        <p className="mt-1.5 text-body text-navy">{evidenceSignal(item)}</p>

        {excluding && (
          <form
            className="mt-4 flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              submitExclude();
            }}
          >
            <input
              autoFocus
              aria-label="Why exclude this option?"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Why exclude this option?"
              className="min-w-0 flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body text-ink placeholder:text-grey/80 focus-visible:outline-2 focus-visible:outline-blue"
            />
            <Button type="submit" variant="secondary" size="sm" disabled={excludeOption.isPending || walkActive}>
              Exclude
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setExcluding(false)}>
              Cancel
            </Button>
          </form>
        )}

        {notice !== null && (
          <p role="alert" className="mt-3 text-body text-red">
            {notice}
          </p>
        )}

        {(excluded || item.no_in_scope_evidence || item.search_pending || notices.length > 0) && (
          <Card className="mt-5 space-y-2 p-4 text-body text-ink">
            {excluded && item.exclusion != null && (
              <p>
                <Chip tone="red" className="mr-2 align-middle">excluded</Chip>
                Breaks "{constraintLabel(scrub(item.exclusion.constraint))}". {scrub(item.exclusion.reason)}
              </p>
            )}
            {item.no_in_scope_evidence && item.in_scope != null && (
              <p>
                <Chip tone="yellow" className="mr-2 align-middle">no in-scope evidence</Chip>
                None of its {item.in_scope.documents} documents pass {scrub(item.in_scope.restriction)}. It stays on
                the longlist until the scope changes.
              </p>
            )}
            {item.search_pending && <p className="text-grey">Its own evidence search is still running.</p>}
            {notices.map((notice) => (
              <p key={notice.key}>
                <Chip tone={notice.tone} className="mr-2 align-middle">{notice.chip}</Chip>
                {scrub(notice.text)}
              </p>
            ))}
          </Card>
        )}
      </header>

      <CardSection id="how-it-works" summary={leverText}>
        <div>
          <p>
            <strong className="font-bold text-navy">Lever:</strong> {leverText.replace(/^Lever: /, "")}
          </p>
          {leverReason.trim() !== "" && <p className="text-body text-grey">{scrub(leverReason)}</p>}
        </div>
        <p>{scrub(deliveredLeadIn(profile?.settings))}</p>
        {item.design.design_features.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-body">
            {item.design.design_features.slice(0, FEATURES_SHOWN).map((feature, index) => (
              <li key={index}>{capitalise(scrub(feature))}</li>
            ))}
          </ul>
        )}
      </CardSection>

      {profile !== null && (
        <CardSection
          id="what-it-would-take"
          summary=""
          defaultOpen={false}
          meta={ESTIMATE_LABEL}
          summaryNode={
            <ul role="list" className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
              {cellLines.map(({ key, mark }) => (
                <li key={key}>
                  <span className="block text-meta text-grey">{LINE_NAMES[key]}</span>
                  <span className="mt-1 block min-h-6">
                    {mark === null ? (
                      <span className="text-meta font-semibold text-navy">{MIDDLE_WORD}</span>
                    ) : (
                      <span className={LEVEL_WORD_CLASS[mark]}>{LEVEL_WORDS[key][mark]}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          }
        >
          <table className="w-full border-collapse text-left">
            <tbody className="divide-y divide-line">
              <tr>
                <th scope="row" className={PROFILE_NAME_CELL}>{LINE_NAMES.ambition}</th>
                <td className={PROFILE_WORD_CELL}>
                  {ambitionMark === null ? (
                    <span className="font-semibold text-navy">{MIDDLE_WORD}</span>
                  ) : (
                    <span className={LEVEL_WORD_CLASS[ambitionMark]}>{LEVEL_WORDS.ambition[ambitionMark]}</span>
                  )}
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
                      ) : marked && mark === null ? (
                        <span className="font-semibold text-navy">{MIDDLE_WORD}</span>
                      ) : marked && mark !== null ? (
                        <span className={LEVEL_WORD_CLASS[mark]}>{LEVEL_WORDS[key][mark]}</span>
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

      <CardSection id="evidence-base" summary={opener}>
        <p>{opener}</p>
        {item.document_count > 0 && (
          <>
            {planOutcomes.length > 0 && (
              <div>
                <p className="font-bold text-navy">Your outcomes</p>
                {noneMeasured ? (
                  <p>{noOutcomeMeasuredLine(planOutcomes.length)}</p>
                ) : (
                  <ul role="list" aria-label="Your outcomes" className="divide-y divide-line">
                    {planOutcomes.map((entry) => (
                      <li key={entry.outcome} className="flex items-baseline justify-between gap-4 py-1.5">
                        <span>{scrub(entry.outcome)}</span>
                        <span className="shrink-0 text-right">
                          {entry.evaluated === 0 ? (
                            <span className="text-grey">none</span>
                          ) : (
                            outcomeCountLabel(entry.evaluated)
                          )}
                          {!servesOutcome(item.outcomes_served, entry.outcome) && (
                            <span className="ml-2 text-grey">not a target of this option</span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {placeSentences.length > 0 && (
              <div>
                <p className="font-bold text-navy">Where it has been evaluated</p>
                <dl aria-label="Where it has been evaluated" className="divide-y divide-line">
                  {placeSentences.map((entry) => (
                    <div
                      key={entry.place}
                      data-where={entry.where ? "true" : undefined}
                      className={cn("grid gap-x-4 py-1.5 sm:grid-cols-[10rem_1fr]", entry.where && "bg-aqua-tint")}
                    >
                      <dt className="font-bold text-navy">{scrub(entry.place)}</dt>
                      <dd>{scrub(entry.sentence)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            <details className="group">
              <summary className="cursor-pointer font-bold text-navy">
                {documentsSummary(documents.length)}
              </summary>
              <div className="mt-3 space-y-4">
                <DocumentGroup heading="Evaluated it" taskId={taskId} optionId={item.option_id} documents={evaluatedDocuments} />
                <DocumentGroup
                  heading="Describe or recommend it"
                  taskId={taskId}
                  optionId={item.option_id}
                  documents={describingDocuments}
                />
              </div>
            </details>
          </>
        )}
      </CardSection>
    </ReportPage>
  );
}
