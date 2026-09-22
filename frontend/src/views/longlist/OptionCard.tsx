import { useState } from "react";
import { Link, useParams } from "react-router";

import { useExcludeOption, useIncludeOption } from "../../api/mutations";
import { useOption, useTask } from "../../api/queries";
import { errorCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { useDocumentTitle } from "../../lib/title";
import { Button } from "../../ui/brand/Button";
import { Card } from "../../ui/brand/Card";
import { Chip } from "../../ui/brand/Chip";
import { ReauthRedirect } from "../../ui/feedback";
import {
  MENTION_NOT_SUPPORT,
  capitalise,
  joinCounts,
  leverLine,
  originLabel,
  relationLabel,
  verdictLabel,
  whereTriedGroupLabel,
  whereTriedSentence,
} from "./longlistPresentation";

/**
 * The option card (contract deliverable 9, D15): assembled from the
 * discovery, evidence-profile and constrain passes — no writer call, no
 * summary prose beyond these templated sentences. The words "how sure"
 * appear nowhere on this page (trust § Provenance labels; a locked test).
 */
export function OptionCard() {
  const { taskId = "", optionId = "" } = useParams();
  const task = useTask(taskId);
  const option = useOption(taskId, optionId);
  const excludeOption = useExcludeOption(taskId);
  const includeOption = useIncludeOption(taskId);
  const [excluding, setExcluding] = useState(false);
  const [reason, setReason] = useState("");

  useDocumentTitle(task.data?.name, option.data?.name ?? "Option");

  if (option.isPending) {
    return (
      <main aria-busy="true" aria-label="Loading the option" className="mx-auto max-w-3xl px-6 py-10">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="mb-4 h-20 animate-pulse border border-line bg-paper-2" />
        ))}
      </main>
    );
  }

  if (option.isError) {
    const code = errorCode(option.error);
    if (code === "unauthenticated") return <ReauthRedirect />;
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
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
      <main className="mx-auto max-w-3xl px-6 py-10">
        <Card role="status" className="p-8 text-center text-body text-grey">
          This option isn't on the longlist.
        </Card>
      </main>
    );
  }

  const item = option.data;
  const evidence = item.evidence;
  const byRole = evidence.by_role ?? {};
  const evidenceTypeSentence = joinCounts(evidence.by_evidence_type);
  const tierSentence = joinCounts(evidence.by_tier);
  const populationsSentence = (evidence.populations ?? []).join(", ");
  const settingsSentence = (evidence.settings ?? []).join(", ");
  const outcomesSentence = (evidence.outcomes ?? []).join(", ");

  const submitExclude = () => {
    const trimmed = reason.trim();
    if (trimmed === "" || excludeOption.isPending) return;
    excludeOption.mutate(
      { optionId, reason: trimmed },
      { onSuccess: () => { setExcluding(false); setReason(""); } },
    );
  };

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <nav aria-label="Breadcrumb" className="text-body text-grey">
        <Link to={`/tasks/${taskId}/result?view=longlist`} className="hover:underline">
          Longlist
        </Link>{" "}
        › {scrub(item.name)}
      </nav>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <h1 className="text-title font-bold text-navy">{scrub(item.name)}</h1>
        <Chip tone="blue">{scrub(item.depth_label)}</Chip>
      </div>

      <div className="mt-3">
        {item.state === "included" ? (
          excluding ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                autoFocus
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Why exclude this option?"
                className="flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body focus-visible:outline-2 focus-visible:outline-blue"
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={reason.trim() === "" || excludeOption.isPending}
                onClick={submitExclude}
              >
                Exclude
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExcluding(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="secondary" size="sm" onClick={() => setExcluding(true)}>
              Exclude
            </Button>
          )
        ) : (
          <Button
            variant="secondary"
            size="sm"
            disabled={includeOption.isPending}
            onClick={() => includeOption.mutate({ optionId })}
          >
            Include again
          </Button>
        )}
      </div>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">What it is</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-body text-navy">
          {item.design.design_features.map((feature, index) => (
            <li key={index}>{scrub(feature)}</li>
          ))}
        </ul>
        <p className="mt-2 text-body text-navy">
          {leverLine(item.primary_lever_type, item.secondary_lever_types, item.lever_none_fits_reason)}
        </p>
        {item.ambition != null && (
          <p className="mt-1 text-body text-navy">
            Ambition: {capitalise(item.ambition)} — {scrub(item.ambition_reason ?? "")}
          </p>
        )}
        <p className="mt-1 text-caption text-grey">as described, not measured · Policy Atlas's reasoning</p>
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">What it is for</h2>
        {(item.outcomes_served?.length ?? 0) > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-body text-navy">
            {(item.outcomes_served ?? []).map((outcome, index) => (
              <li key={index}>{scrub(outcome)}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-body text-grey">No outcomes recorded.</p>
        )}
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">Where tried</h2>
        <p className="mt-2 text-body text-navy">
          {whereTriedSentence(item.where_tried, item.where_label)}
        </p>
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">What the evidence base holds so far</h2>
        <div className="mt-2 space-y-1.5 text-body text-navy">
          <p>
            {evidence.documents} documents name this option; {byRole.evaluated ?? 0} evaluated it,{" "}
            {byRole.described ?? 0} described it, {byRole.recommended ?? 0} recommended it,{" "}
            {byRole.mentioned ?? 0} mentioned it.
          </p>
          {evidenceTypeSentence !== "" && <p>By evidence type: {evidenceTypeSentence}.</p>}
          {tierSentence !== "" && <p>By quality tier: {tierSentence}.</p>}
          {populationsSentence !== "" && <p>Populations: {populationsSentence}.</p>}
          {settingsSentence !== "" && <p>Settings: {settingsSentence}.</p>}
          {outcomesSentence !== "" && <p>Outcomes measured: {outcomesSentence}.</p>}
          {evidence.flagged_not_stated > 0 && (
            <p>
              {evidence.flagged_not_stated} of the {evidence.documents} documents do not state a feature that
              defines this option.
            </p>
          )}
          <p>{evidence.abstract_only} read from the abstract only.</p>
          <p className="font-semibold">{MENTION_NOT_SUPPORT}</p>
        </div>
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">Constraints and guesses</h2>
        <ul className="mt-2 space-y-1.5 text-body text-navy">
          {(item.judgements ?? []).map((judgement) => (
            <li key={judgement.constraint_id}>
              {scrub(judgement.constraint_text)}: {verdictLabel(judgement.verdict)} — {scrub(judgement.reason)}
            </li>
          ))}
          {(item.guesses ?? []).map((guess) => (
            <li key={guess.constraint_id}>
              {scrub(guess.constraint_text)}: {scrub(guess.guess)}
            </li>
          ))}
          {item.transferability != null && <li>Transferable to your Where: {item.transferability}</li>}
          {item.in_scope != null && (
            <li>
              No in-scope evidence: none of the {item.in_scope.documents} documents pass{" "}
              {scrub(item.in_scope.restriction)}.
            </li>
          )}
        </ul>
      </section>

      <section className="mt-8 border-t border-line pt-6">
        <h2 className="text-heading font-bold text-navy">Where it came from and what it relates to</h2>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Chip tone="soft">{originLabel(item.origin, item.document_count)}</Chip>
          {(item.relations ?? []).map((relation) => (
            <Chip key={`${relation.kind}-${relation.other_option_id}`} tone="soft">
              {relationLabel(relation)}
            </Chip>
          ))}
        </div>
        <details className="mt-3 text-body text-navy">
          <summary className="cursor-pointer font-semibold text-blue hover:underline">Show the documents</summary>
          <ul className="mt-2 space-y-2">
            {(item.documents ?? []).map((document, index) => (
              <li key={document.task_source_snapshot_id ?? index} className="border-b border-line pb-2 last:border-b-0">
                <p className="font-semibold">{scrub(document.title)}</p>
                <p className="text-caption text-grey">
                  {[
                    document.role,
                    document.evidence_type ?? undefined,
                    document.tier ?? "not rated",
                    document.design_feature_not_stated ? "feature not stated" : undefined,
                    whereTriedGroupLabel(document.where_tried_group, item.where_label),
                    document.source_task_id != null ? "inherited from a linked task" : undefined,
                  ]
                    .filter((part): part is string => part !== undefined)
                    .map((part) => scrub(part))
                    .join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        </details>
      </section>
    </main>
  );
}
