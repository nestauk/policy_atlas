import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

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
import { AppraisalChip } from "../ArtefactView";
import { LIFECYCLE_PAGE_CLASS } from "../listPageChrome";
import { REPORT_TITLE_CLASS, ReportKindRow, ReportPage, SnapshotCells } from "../reportPage";
import {
  SCOPING_PASS_SENTENCE,
  abstractOnlySentence,
  actionFailedNotice,
  LEVEL_WORD_CLASS,
  LEVEL_WORDS,
  LINE_NAMES,
  PROFILE_LINE_KEYS,
  ambitionSentence,
  authorityLine,
  capitalise,
  checksSummary,
  constraintLabel,
  deliveredThroughLine,
  documentsSentence,
  leverLine,
  runnerUpLine,
  triedOnSentence,
  variantLine,
  originLabel,
  originShort,
  outcomeCountItem,
  outcomeCountsSentence,
  outcomesSentence,
  relationLabel,
  roleLabel,
  verdictLabel,
  whereTriedGroupLabel,
  whereTriedSentence,
} from "./longlistPresentation";

const PAGE_CLASS = `${LIFECYCLE_PAGE_CLASS} py-8`;

/** The card's sections, in contract order (deliverable 9; Where tried folds
 *  into the evidence section — owner, 2026-09-23). */
const SECTIONS = [
  { id: "what-it-is", title: "What it is" },
  { id: "what-it-is-for", title: "What it is for" },
  { id: "what-it-would-take", title: "What it would take" },
  { id: "evidence-base", title: "What the evidence base holds so far" },
  { id: "constraints", title: "Constraints and guesses" },
  { id: "origin", title: "Where it came from and what it relates to" },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

/** The sidebar lists the sections the card shows: "What it would take" is
 *  absent for an option with no profile (R37). */
const sidebarEntries = (hasProfile: boolean): SidebarEntry[] =>
  SECTIONS.filter(({ id }) => hasProfile || id !== "what-it-would-take").map(({ id, title }) => ({ id, title }));

/** The label beside the profile section's heading, in both states (R37). */
const ESTIMATE_LABEL = "Estimate, before assessment";

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
  const populationsSentence = (evidence.populations ?? []).join(", ");
  const settingsSentence = (evidence.settings ?? []).join(", ");
  const measuredSentence = (evidence.outcomes ?? []).join(", ");
  const excluded = item.state === "excluded";
  const judgements = item.judgements ?? [];
  const documentsLine = documentsSentence(evidence.documents, byRole);
  // The read model can repeat a document once per mention (issue #75): one
  // card per document, the first mention's role.
  const seen = new Set<string>();
  const documents = (item.documents ?? []).filter((document) => {
    const key = document.task_source_snapshot_id ?? document.title;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const whereLine = whereTriedSentence(item.where_tried, item.where_label);
  const outcomeCounts = evidence.outcome_counts;
  const outcomeCountsLine = outcomeCountsSentence(outcomeCounts);
  const profile = item.profile ?? null;
  const ambitionLine = ambitionSentence(item.ambition, item.ambition_reason);
  const deliveredLine = deliveredThroughLine(profile?.settings);
  const profileLines = profile === null ? [] : PROFILE_LINE_KEYS.map((key) => ({ key, line: profile.lines.find((line) => line.key === key) }));
  const checksLine = checksSummary(judgements.map((judgement) => judgement.verdict));
  const originSentence = `${capitalise(
    [originLabel(item.origin, item.document_count, item.from_section), ...(item.relations ?? []).map(relationLabel)].join(" · "),
  )}.`;

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
        <ReportKindRow kind="Option" tag={<Chip tone="blue" title={SCOPING_PASS_SENTENCE}>{scrub(item.depth_label)}</Chip>}>
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
        {/* Duplicates merged into this option: their documents are its documents. */}
        {(item.also_found_as ?? []).length > 0 && (
          <p className="mt-2 text-meta text-grey">Also found as: {scrub((item.also_found_as ?? []).join(", "))}</p>
        )}

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

        <SnapshotCells
          cells={[
            ["Documents", String(item.document_count), null],
            ["Evaluated", `${item.evaluated_count} of ${item.document_count}`, null],
            [`Tried in ${item.where_label}`, `${item.where_tried.where} of ${item.document_count}`, null],
            ["Origin", capitalise(originShort(item.origin) ?? "clustered from the search"), null],
          ]}
        />

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

      <CardSection id="what-it-is" summary={leverLine(item.primary_lever_type, item.secondary_lever_types, item.lever_none_fits_reason)}>
        {item.design.design_features.length > 0 && (
          <ul className="list-disc space-y-1 pl-5">
            {item.design.design_features.map((feature, index) => (
              <li key={index}>{capitalise(scrub(feature))}</li>
            ))}
          </ul>
        )}
        <p>{leverLine(item.primary_lever_type, item.secondary_lever_types, item.lever_none_fits_reason, item.lever_reason)}</p>
        {item.runner_up_lever_type != null && <p>{runnerUpLine(item.runner_up_lever_type)}</p>}
        {ambitionLine !== "" && <p>{scrub(ambitionLine)}</p>}
        {deliveredLine !== "" && <p>{scrub(deliveredLine)}</p>}
        {item.authority != null && <p>{scrub(authorityLine(item.authority))}</p>}
        {(item.variants ?? []).length > 0 && (
          <div>
            <p className="font-bold text-navy">Variants</p>
            <ul className="list-disc space-y-1 pl-5">
              {(item.variants ?? []).map((variant, index) => (
                <li key={index}>{scrub(variantLine(variant))}</li>
              ))}
            </ul>
          </div>
        )}
      </CardSection>

      <CardSection id="what-it-is-for" summary={outcomesSentence(item.outcomes_served) || "No outcomes recorded."}>
        {(item.outcomes_served?.length ?? 0) > 0 ? (
          <ul className="list-disc space-y-1 pl-5">
            {(item.outcomes_served ?? []).map((outcome, index) => (
              <li key={index}>{capitalise(scrub(outcome))}</li>
            ))}
          </ul>
        ) : (
          <p className="text-grey">No outcomes recorded.</p>
        )}
      </CardSection>

      {profile !== null && (
        <CardSection
          id="what-it-would-take"
          summary=""
          defaultOpen={false}
          meta={ESTIMATE_LABEL}
          summaryNode={
            <ul role="list" className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 lg:grid-cols-8">
              {profileLines.map(({ key, line }) => {
                const mark = line?.mark ?? null;
                const word = mark === null ? null : LEVEL_WORDS[key][mark];
                return (
                  <li key={key}>
                    <span className="block text-caption uppercase tracking-[0.06em] text-grey">{LINE_NAMES[key]}</span>
                    <span className="mt-1 block min-h-6">
                      {word !== null && mark !== null && <span className={LEVEL_WORD_CLASS[mark]}>{word}</span>}
                    </span>
                  </li>
                );
              })}
            </ul>
          }
        >
          <dl className="divide-y divide-line">
            {profileLines.map(({ key, line }) => {
              const mark = line?.mark ?? null;
              const word = mark === null ? null : LEVEL_WORDS[key][mark];
              return (
                <div key={key} className="grid grid-cols-[12rem_1fr] gap-x-6 py-2.5 max-md:grid-cols-1 max-md:gap-y-1">
                  <dt>
                    <span className="block font-semibold text-navy">{LINE_NAMES[key]}</span>
                    {word !== null && mark !== null && (
                      <span className="mt-1 block">
                        <span className={LEVEL_WORD_CLASS[mark]}>{word}</span>
                      </span>
                    )}
                  </dt>
                  <dd className="max-w-prose-measure">{line === undefined ? "" : scrub(line.sentence)}</dd>
                </div>
              );
            })}
          </dl>
        </CardSection>
      )}

      <CardSection id="evidence-base" summary={documentsLine}>
        <p>{documentsLine}</p>
        <p>{whereLine}</p>
        {outcomeCountsLine !== "" && (
          <>
            <p>{outcomeCountsLine}</p>
            <ul className="list-disc space-y-1 pl-5">
              {(outcomeCounts?.by_outcome ?? []).map((entry) => (
                <li key={entry.outcome}>{scrub(outcomeCountItem(entry.outcome, entry.documents))}</li>
              ))}
            </ul>
          </>
        )}
        {documents.length > 0 && (
          <ul role="list" className="grid gap-3">
            {documents.map((document, index) => (
              <li key={document.task_source_snapshot_id ?? index} className="border border-line p-4">
                <p className={`${REPORT_BODY_CLASS} font-bold`}>{scrub(document.title)}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {document.tier != null && <AppraisalChip label={document.tier} evidenceType={document.evidence_type} />}
                  {document.evidence_type != null && <Chip tone="soft">{scrub(document.evidence_type)}</Chip>}
                  <Chip tone="soft">{roleLabel(document.role)}</Chip>
                  <Chip tone="soft">{scrub(whereTriedGroupLabel(document.where_tried_group, item.where_label))}</Chip>
                  {document.source_task_id != null && <Chip tone="soft">inherited from a linked task</Chip>}
                </div>
              </li>
            ))}
          </ul>
        )}
        {populationsSentence !== "" && <p>Populations: {populationsSentence}.</p>}
        {(evidence.tried_on ?? []).length > 0 && <p>{scrub(triedOnSentence(evidence.tried_on ?? []))}</p>}
        {settingsSentence !== "" && <p>Settings: {settingsSentence}.</p>}
        {measuredSentence !== "" && <p>Outcomes measured: {measuredSentence}.</p>}
        <p className="text-meta text-grey">{abstractOnlySentence(evidence.abstract_only, evidence.documents)}</p>
      </CardSection>

      <CardSection id="constraints" summary={checksLine}>
        <ul className="space-y-2">
          {judgements.map((judgement) => (
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
          {item.transferability != null && (
            <li>
              <span className="font-semibold text-navy">Transferable to {scrub(item.where_label)}:</span>{" "}
              <span className="text-grey">{item.transferability}.</span>
            </li>
          )}
          {item.no_in_scope_evidence && item.in_scope != null && (
            <li>
              No in-scope evidence: none of the {item.in_scope.documents} documents pass{" "}
              {scrub(item.in_scope.restriction)}.
            </li>
          )}
        </ul>
      </CardSection>

      <CardSection id="origin" summary={scrub(originSentence)}>
        <p>{scrub(originSentence)}</p>
      </CardSection>
    </ReportPage>
  );
}
