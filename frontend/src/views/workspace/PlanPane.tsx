import { useState } from "react";

import { useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { Card, Divider, PaneHeading } from "../../ui/brand/Card";
import {
  ANALYSIS_DEPTH_LABEL,
  COMPONENT_LABEL,
  SEARCH_EFFORT_LABEL,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  scopeChips,
  vocabLabel,
} from "./planVocabulary";

type PlanDraft = components["schemas"]["PlanDraft"];

/**
 * The forming plan as a first-class right-pane surface. It uses the in-run
 * journey recap's compact disclosure grammar, while preserving the pre-run
 * readiness state, planned components, and start control.
 */
export function PlanPane({ projectId }: { projectId: string }) {
  const planQuery = usePlan(projectId);
  const startRun = useStartRun(projectId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  // Open by default (owner, 2026-07-29): pre-run, the plan IS this pane's
  // content — the collapsed grammar is borrowed from the in-run recap, where
  // the journey competes for the same space. Collapsing stays one click away.
  const [detailsOpen, setDetailsOpen] = useState(true);
  const plan: PlanDraft | null = planQuery.data?.plan ?? null;

  if (plan === null || (!plan.question && (plan.steps ?? []).length === 0)) {
    return (
      <section aria-label="Plan" className="flex h-full min-w-0 flex-col">
        <PaneHeading>Plan</PaneHeading>
        <Divider />
        <div className="flex flex-1 items-center justify-center px-6">
          <p role="status" className="max-w-xs text-center text-[12.5px] text-grey">
            Forms here as you talk. Nothing runs until you approve it.
          </p>
        </div>
      </section>
    );
  }

  const scopingNotes = plan.scoping_notes ?? [];
  const screeningCriteria = plan.screening_criteria ?? [];
  const constraints = scopeChips(plan.scope_constraints);
  const steps = plan.steps ?? [];
  const componentLabels = (plan.components ?? [])
    .map((component) => vocabLabel(COMPONENT_LABEL, component))
    .filter((label): label is string => label !== null);
  const settings: Array<[string, string | null]> = [
    ["Search effort", vocabLabel(SEARCH_EFFORT_LABEL, plan.search_effort)],
    ["Analysis depth", vocabLabel(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)],
    ["Sources", vocabLabel(SOURCES_LABEL, plan.backend_scope)],
    ["Check-ins", vocabLabel(STEERING_MODE_LABEL, plan.steering_mode)],
  ];
  const knownSettings = settings.filter((item): item is [string, string] => item[1] !== null);
  const starting = startRun.isPending;

  return (
    <section aria-label="Plan" className="flex h-full min-w-0 flex-col">
      <PaneHeading>Plan</PaneHeading>
      <Divider />
      <div className="min-w-0 flex-1 overflow-y-auto px-5 py-5">
        <Card className="min-w-0">
          <button
            className="flex w-full min-w-0 items-baseline gap-3 px-4 py-3 text-left hover:bg-ground"
            onClick={() => setDetailsOpen((value) => !value)}
            aria-expanded={detailsOpen}
            aria-label="Toggle plan details"
          >
            <PaneHeading className="shrink-0 p-0">The plan</PaneHeading>
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-navy">
              {plan.question !== null && plan.question !== "" ? scrub(plan.question) : "Not set yet"}
            </span>
            {plan.time_band !== null && plan.time_band !== "" && (
              <Chip className="max-w-32 shrink truncate" tone="soft">
                {scrub(plan.time_band)}
              </Chip>
            )}
            <Chip className="shrink-0" tone={plan.ready ? "green" : "soft"}>
              {plan.ready ? "ready" : "forming…"}
            </Chip>
            <span className="shrink-0 text-[11px] text-grey">{detailsOpen ? "Hide" : "Details"}</span>
          </button>
          {detailsOpen && (
            <div className="min-w-0 border-t border-line px-4 pb-4 pt-3">
              <p className="mb-3 text-[12.5px] text-grey">
                Agreed here before anything runs. The analysis follows it.
              </p>
              {knownSettings.length > 0 && (
                <div className="grid gap-px border border-line bg-line sm:grid-cols-2">
                  {knownSettings.map(([label, value]) => (
                    <div key={label} className="min-w-0 bg-paper px-3 py-2">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-grey">{label}</p>
                      <p className="break-words text-[12px] font-medium text-navy">{value}</p>
                    </div>
                  ))}
                </div>
              )}
              {scopingNotes.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {scopingNotes.map((note) => <Chip key={note} tone="soft">{scrub(note)}</Chip>)}
                </div>
              )}
              {constraints.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {constraints.map((chip) => <Chip key={chip} tone="blue">{scrub(chip)}</Chip>)}
                </div>
              )}
              {screeningCriteria.length > 0 && (
                <div className="mt-3">
                  <PaneHeading className="p-0">Screening criteria</PaneHeading>
                  <ul className="mt-1 space-y-1 text-[12px] text-navy">
                    {screeningCriteria.map((criterion) => <li key={criterion} className="break-words">• {scrub(criterion)}</li>)}
                  </ul>
                </div>
              )}
              {steps.length > 0 && (
                <div className="mt-3">
                  <PaneHeading className="p-0">Agreed steps</PaneHeading>
                  <ol className="mt-1 space-y-1 text-[12px] text-navy">
                    {steps.map((step, index) => (
                      <li key={step.stage} className="break-words">
                        {index + 1}. {scrub(step.label)}
                        {step.blurb !== "" && <span className="text-grey"> — {scrub(step.blurb)}</span>}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {!plan.ready && componentLabels.length > 0 && (
                <div className="mt-3">
                  <PaneHeading className="p-0">Planned components</PaneHeading>
                  <ul className="mt-1 space-y-1 text-[12px] text-navy">
                    {componentLabels.map((label) => <li key={label}>{label}</li>)}
                  </ul>
                </div>
              )}
              {(plan.assumptions ?? []).length > 0 && (
                <div className="mt-3">
                  <PaneHeading className="p-0">Assumptions</PaneHeading>
                  <ul className="mt-1 space-y-1 text-[12px] text-grey">
                    {plan.assumptions?.map((assumption) => <li key={assumption} className="break-words">• {scrub(assumption)}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {plan.ready && (
        <div className="border-t border-line px-5 py-4">
          <Button
            className="w-full justify-center"
            disabled={starting}
            onClick={() => {
              setStartNotice(null);
              startRun.mutate(undefined, {
                onError: (error) => {
                  const code = (error as { code?: string }).code;
                  setStartNotice(
                    isConflictCode(code)
                      ? conflictSentences[code]
                      : "The analysis couldn't start. Try again.",
                  );
                },
              });
            }}
          >
            {starting ? "Starting…" : "Start the analysis"}
          </Button>
          {startNotice !== null && (
            <p role="alert" className="mt-2 text-center text-xs text-red">
              {startNotice}
            </p>
          )}
          <p className="mt-2 text-center text-[12px] text-grey">
            {plan.time_band !== null && plan.time_band !== "" ? `${scrub(plan.time_band)} · ` : ""}
            You can steer or pause at any check-in.
          </p>
        </div>
      )}
    </section>
  );
}
