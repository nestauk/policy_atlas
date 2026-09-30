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
  ABSTRACTS_NOTE,
  actionFailedNotice,
  authorityWords,
  BUILT_IN_CHECK_IDS,
  GRID_COLUMN_LINES,
  LEVEL_WORD_CLASS,
  LEVEL_WORDS,
  LINE_NAMES,
  MIDDLE_WORD,
  PROFILE_LINE_KEYS,
  capitalise,
  checksSummary,
  constraintLabel,
  deliveredThroughLine,
  documentPlaceLabel,
  documentsSentence,
  leverLine,
  triedOnSentence,
  exampleLine,
  originLabel,
  relationLabel,
  roleLabel,
  servesOutcome,
  verdictLabel,
  wherePlaceLine,
  whereTopLine,
} from "./longlistPresentation";

type OptionDocumentOut = components["schemas"]["OptionDocumentOut"];

/** Documents shown before "Show all N". */
const DOCUMENTS_SHOWN = 5;
/** Design features and examples shown on the card (R63; § 2.5). */
const FEATURES_SHOWN = 6;
const EXAMPLES_SHOWN = 5;

/** The document's grey meta line: quality, type, role, place, year (task 046,
 *  amendment 3, R67; the place is its where-tried top level, R72). */
const documentMeta = (document: OptionDocumentOut): string =>
  [document.tier, document.evidence_type, roleLabel(document.role), documentPlaceLabel(document.place), document.year]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .map((part) => scrub(String(part)))
    .join(" · ");

/** The option's documents: a linked title (plain when this task holds no row),
 *  one grey meta line each, five shown then "Show all N". */
function DocumentList({
  taskId,
  optionId,
  documents,
}: {
  taskId: string | undefined;
  optionId: string;
  documents: OptionDocumentOut[];
}) {
  const [showAll, setShowAll] = useState(false);
  if (documents.length === 0) return <p className="text-grey">No documents found yet.</p>;
  const shown = showAll ? documents : documents.slice(0, DOCUMENTS_SHOWN);
  return (
    <>
      <ul role="list" className="grid gap-3">
        {shown.map((document, index) => (
          <li key={document.task_source_snapshot_id ?? `${document.title}-${index}`}>
            <p className={`${REPORT_BODY_CLASS} font-bold`}>
              {document.task_source_snapshot_id != null && taskId !== undefined ? (
                <Link
                  className="underline underline-offset-2"
                  to={`/tasks/${taskId}/sources/all?source=${document.task_source_snapshot_id}&option=${optionId}`}
                >
                  {scrub(document.title)}
                </Link>
              ) : (
                scrub(document.title)
              )}
            </p>
            <p className="text-meta text-grey">{documentMeta(document)}</p>
          </li>
        ))}
      </ul>
      {!showAll && documents.length > DOCUMENTS_SHOWN && (
        <Button variant="secondary" onClick={() => setShowAll(true)}>
          Show all {documents.length}
        </Button>
      )}
    </>
  );
}

const PAGE_CLASS = `${LIFECYCLE_PAGE_CLASS} py-8`;

/** The card's sections, in contract order (deliverable 9; Where tried folds
 *  into the evidence section — owner, 2026-09-23). */
const SECTIONS = [
  { id: "what-it-is", title: "What it is" },
  { id: "what-it-would-take", title: "What it would take" },
  { id: "evidence-base", title: "What the evidence base holds so far" },
  { id: "constraints", title: "Constraints and guesses" },
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

const VERDICT_CLASS: Record<"passes" | "breaks" | "cannot_check", string> = {
  passes: "text-navy",
  breaks: "text-red",
  cannot_check: "text-grey",
};

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
  const byRole = evidence.by_role ?? {};
  const excluded = item.state === "excluded";
  const judgements = item.judgements ?? [];
  const documentsLine = documentsSentence(evidence.documents, byRole);
  // One entry per document, evaluated first then by quality (the read model, R67).
  const documents = item.documents ?? [];
  const whereTried = item.where_tried ?? [];
  const outcomeCounts = evidence.outcome_counts;
  const planOutcomes = outcomeCounts?.by_outcome ?? [];
  const otherOutcomes = outcomeCounts?.other ?? [];
  const profile = item.profile ?? null;
  const deliveredLine = deliveredThroughLine(profile?.settings);
  const profileLines = profile === null ? [] : PROFILE_LINE_KEYS.map((key) => ({ key, line: profile.lines.find((line) => line.key === key) }));
  const cellLines = profile === null ? [] : GRID_COLUMN_LINES.map((key) => ({
    key,
    mark: key === "ambition" ? (item.ambition ?? null) : (profile.lines.find((line) => line.key === key)?.mark ?? null),
  }));
  const ambitionMark = item.ambition ?? null;
  const leverText = leverLine(item.primary_lever_type, item.secondary_lever_types);
  // One reason only: the none-fits reason says what the option does instead.
  const leverReason = (item.primary_lever_type == null ? (item.lever_none_fits_reason ?? item.lever_reason) : item.lever_reason) ?? "";
  const userJudgements = judgements.filter((judgement) => !BUILT_IN_CHECK_IDS.includes(judgement.constraint_id));
  const builtInJudgements = judgements.filter((judgement) => BUILT_IN_CHECK_IDS.includes(judgement.constraint_id));
  const builtInsPass = builtInJudgements.every((judgement) => judgement.verdict === "passes");
  const checksLine = checksSummary(judgements.map((judgement) => judgement.verdict));
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

        {(excluded || item.no_in_scope_evidence || item.search_pending) && (
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
          </Card>
        )}
      </header>

      <CardSection id="what-it-is" summary={leverText}>
        <div>
          <p>
            <strong className="font-bold text-navy">Lever:</strong> {leverText.replace(/^Lever: /, "")}
          </p>
          {leverReason.trim() !== "" && <p className="text-body">{scrub(leverReason)}</p>}
        </div>
        {deliveredLine !== "" && <p>{scrub(deliveredLine)}</p>}
        {item.design.design_features.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-body">
            {item.design.design_features.slice(0, FEATURES_SHOWN).map((feature, index) => (
              <li key={index}>{capitalise(scrub(feature))}</li>
            ))}
          </ul>
        )}
        {(item.examples ?? []).length > 0 && (
          <div>
            <p className="font-bold text-navy">Examples</p>
            <ul className="list-disc space-y-1 pl-5 text-body">
              {(item.examples ?? []).slice(0, EXAMPLES_SHOWN).map((example, index) => (
                <li key={index}>{scrub(exampleLine(example))}</li>
              ))}
            </ul>
          </div>
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
                <th scope="row" className="w-48 py-2.5 pr-4 align-top font-semibold text-navy">{LINE_NAMES.ambition}</th>
                <td className="w-40 py-2.5 pr-4 align-top">
                  {ambitionMark === null ? (
                    <span className="font-semibold text-navy">{MIDDLE_WORD}</span>
                  ) : (
                    <span className={LEVEL_WORD_CLASS[ambitionMark]}>{LEVEL_WORDS.ambition[ambitionMark]}</span>
                  )}
                </td>
                <td className="py-2.5 align-top">{scrub(item.ambition_reason ?? "")}</td>
              </tr>
              {profileLines.map(({ key, line }) => {
                const mark = line?.mark ?? null;
                const marked = LEVEL_WORDS[key].less !== null;
                const authority = key === "who_decides" ? item.authority : null;
                const authorityReason = (authority?.reason ?? "").trim();
                return (
                  <tr key={key}>
                    <th scope="row" className="w-48 py-2.5 pr-4 align-top font-semibold text-navy">{LINE_NAMES[key]}</th>
                    <td className="w-40 py-2.5 pr-4 align-top">
                      {authority != null ? (
                        <span className="font-semibold text-navy">{authorityWords(authority)}</span>
                      ) : marked && mark === null ? (
                        <span className="font-semibold text-navy">{MIDDLE_WORD}</span>
                      ) : marked && mark !== null ? (
                        <span className={LEVEL_WORD_CLASS[mark]}>{LEVEL_WORDS[key][mark]}</span>
                      ) : null}
                    </td>
                    <td className="py-2.5 align-top">
                      {scrub(authority != null && authorityReason !== "" ? authorityReason : (line?.sentence ?? ""))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardSection>
      )}

      <CardSection id="evidence-base" summary={documentsLine}>
        {(planOutcomes.length > 0 || otherOutcomes.length > 0) && (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="text-meta text-grey">
                <th scope="col" className="py-1.5 pr-4 font-semibold">Outcome</th>
                <th scope="col" className="py-1.5 pr-4 font-semibold">Documents</th>
                <th scope="col" className="py-1.5 font-semibold">Evaluated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {planOutcomes.map((entry) => (
                <tr key={`plan-${entry.outcome}`}>
                  <th scope="row" className="py-2 pr-4 align-top font-normal">
                    {scrub(entry.outcome)}
                    {servesOutcome(item.outcomes_served, entry.outcome) && <span className="text-grey"> · serves</span>}
                  </th>
                  <td className="py-2 pr-4 align-top">{entry.documents}</td>
                  <td className="py-2 align-top">{entry.evaluated}</td>
                </tr>
              ))}
              {otherOutcomes.map((entry) => (
                <tr key={`other-${entry.kind}`}>
                  <th scope="row" className="py-2 pr-4 align-top font-normal">{scrub(entry.kind)}</th>
                  <td className="py-2 pr-4 align-top">{entry.documents}</td>
                  <td className="py-2 align-top">{entry.evaluated}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p>{documentsLine}</p>
        {whereTried.length > 0 && (
          <div>
            <p className="font-bold text-navy">Where tried</p>
            <ul aria-label="Where tried" className="list-disc space-y-1 pl-5">
              {whereTried.map((entry) => (
                <li key={entry.top}>
                  {scrub(whereTopLine(entry))}
                  {(entry.places ?? []).length > 0 && (
                    <ul className="list-[circle] space-y-0.5 pl-5 text-grey">
                      {(entry.places ?? []).map((place) => (
                        <li key={place.place}>{scrub(wherePlaceLine(place))}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(evidence.tried_on ?? []).length > 0 && <p>{scrub(triedOnSentence(evidence.tried_on ?? []))}</p>}
        <p className="text-body text-grey">{ABSTRACTS_NOTE}</p>
        <DocumentList taskId={taskId} optionId={item.option_id} documents={documents} />
      </CardSection>

      <CardSection id="constraints" summary={checksLine}>
        <ul className="space-y-2">
          {userJudgements.map((judgement) => (
            <li key={judgement.constraint_id}>
              <span className="font-semibold text-navy">{capitalise(constraintLabel(scrub(judgement.constraint_text)))}:</span>{" "}
              <span className={VERDICT_CLASS[judgement.verdict]}>{verdictLabel(judgement.verdict)}.</span>{" "}
              <span className="text-grey">{scrub(judgement.reason)}</span>
            </li>
          ))}
          {(item.guesses ?? []).map((guess) => (
            <li key={guess.constraint_id}>
              <span className="font-semibold text-navy">{capitalise(constraintLabel(scrub(guess.constraint_text)))}:</span>{" "}
              <span className="text-grey">{scrub(guess.guess)}</span>
            </li>
          ))}
          {builtInJudgements.length > 0 && builtInsPass && (
            <li>
              <span className="font-semibold text-navy">Built-in checks:</span>{" "}
              <span className={VERDICT_CLASS.passes}>all pass.</span>
            </li>
          )}
          {!builtInsPass &&
            builtInJudgements.map((judgement) => (
              <li key={judgement.constraint_id}>
                <span className="font-semibold text-navy">{capitalise(constraintLabel(scrub(judgement.constraint_text)))}:</span>{" "}
                <span className={VERDICT_CLASS[judgement.verdict]}>{verdictLabel(judgement.verdict)}.</span>{" "}
                <span className="text-grey">{scrub(judgement.reason)}</span>
              </li>
            ))}
          {item.no_in_scope_evidence && item.in_scope != null && (
            <li>
              No in-scope evidence: none of the {item.in_scope.documents} documents pass{" "}
              {scrub(item.in_scope.restriction)}.
            </li>
          )}
        </ul>
      </CardSection>
    </ReportPage>
  );
}
