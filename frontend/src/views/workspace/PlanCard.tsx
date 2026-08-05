import { useState } from "react";

import { useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { PaneHeading } from "../../ui/brand/Card";
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
 * The ready plan as an inline chat card (028 strand 3): the plan card is the
 * only start surface — it renders at the foot of the planning thread once the
 * draft reaches ready (server status "approved"), details open by default
 * pre-run. A draft that supersedes the approval demotes server-side (GET
 * /plan returns "draft") and the card withdraws until the planner reaches
 * ready again; a stale start 409s `plan_stale` with honest copy.
 */
export function PlanCard({ projectId, runActive }: { projectId: string; runActive: boolean }) {
  const planQuery = usePlan(projectId);
  const startRun = useStartRun(projectId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(true);

  const plan: PlanDraft | null = planQuery.data?.plan ?? null;
  const approved = planQuery.data?.status === "approved";
  if (plan === null || !approved || !plan.ready) return null;

  const scopingNotes = plan.scoping_notes ?? [];
  const screeningCriteria = plan.screening_criteria ?? [];
  const constraints = scopeChips(plan.scope_constraints);
  const steps = plan.steps ?? [];
  const componentLabels = (plan.components ?? [])
    .map((component) => vocabLabel(COMPONENT_LABEL, component))
    .filter((label): label is string => label !== null);
  const settings: Array<[string, string | null]> = [
    ["Thoroughness", vocabLabel(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)],
    ["Search effort", vocabLabel(SEARCH_EFFORT_LABEL, plan.search_effort)],
    ["Sources", vocabLabel(SOURCES_LABEL, plan.backend_scope)],
    ["Check-ins", vocabLabel(STEERING_MODE_LABEL, plan.steering_mode)],
  ];
  const knownSettings = settings.filter((item): item is [string, string] => item[1] !== null);
  const starting = startRun.isPending;
  const unattended = plan.steering_mode === "unattended";

  return (
    <div className="anim-rise mr-8 border border-blue bg-paper shadow-sm" data-testid="plan-card">
      <button
        className="flex w-full min-w-0 items-baseline gap-3 px-4 py-3 text-left hover:bg-ground"
        onClick={() => setDetailsOpen((value) => !value)}
        aria-expanded={detailsOpen}
        aria-label="Toggle plan details"
      >
        <span className="shrink-0 text-caption font-bold uppercase tracking-wide text-grey">
          The plan
        </span>
        <span className="min-w-0 flex-1 truncate text-meta font-semibold text-navy">
          {plan.question !== null && plan.question !== "" ? scrub(plan.question) : "Not set yet"}
        </span>
        <Chip className="shrink-0" tone="green">
          ready
        </Chip>
        <span className="shrink-0 text-caption text-grey">{detailsOpen ? "Hide" : "Details"}</span>
      </button>

      {detailsOpen && (
        <div className="min-w-0 border-t border-line px-4 pb-3 pt-3">
          {knownSettings.length > 0 && (
            <div className="grid gap-px border border-line bg-line sm:grid-cols-2">
              {knownSettings.map(([label, value]) => (
                <div key={label} className="min-w-0 bg-paper px-3 py-2">
                  <p className="text-caption font-bold uppercase tracking-wide text-grey">{label}</p>
                  <p className="break-words text-caption font-medium text-navy">{value}</p>
                </div>
              ))}
            </div>
          )}
          {constraints.length > 0 && (
            <div className="mt-3">
              <PaneHeading className="p-0">Search filters</PaneHeading>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {constraints.map((chip) => (
                  <Chip key={chip} tone="blue">
                    {scrub(chip)}
                  </Chip>
                ))}
              </div>
            </div>
          )}
          {(scopingNotes.length > 0 || screeningCriteria.length > 0) && (
            <div className="mt-3">
              <PaneHeading className="p-0">Screening rules</PaneHeading>
              {/* Scoping-note chips summarise the same per-document rules the
                  list below details, so they live under the same heading. */}
              {scopingNotes.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {scopingNotes.map((note) => (
                    <Chip key={note} tone="soft">
                      {scrub(note)}
                    </Chip>
                  ))}
                </div>
              )}
              {screeningCriteria.length > 0 && (
                <ul className="mt-1 space-y-1 text-caption text-navy">
                  {screeningCriteria.map((criterion) => (
                    <li key={criterion} className="break-words">
                      • {scrub(criterion)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {steps.length > 0 && (
            <div className="mt-3">
              <PaneHeading className="p-0">Steps</PaneHeading>
              <ol className="mt-1 space-y-1 text-caption text-navy">
                {steps.map((step, index) => (
                  <li key={step.stage} className="break-words">
                    {index + 1}. {scrub(step.label)}
                    {step.blurb !== "" && <span className="text-grey"> — {scrub(step.blurb)}</span>}
                  </li>
                ))}
              </ol>
            </div>
          )}
          {componentLabels.length > 0 && steps.length === 0 && (
            <div className="mt-3">
              <PaneHeading className="p-0">Planned components</PaneHeading>
              <ul className="mt-1 space-y-1 text-caption text-navy">
                {componentLabels.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          )}
          {(plan.assumptions ?? []).length > 0 && (
            <div className="mt-3">
              <PaneHeading className="p-0">Assumptions</PaneHeading>
              <ul className="mt-1 space-y-1 text-caption text-grey">
                {plan.assumptions?.map((assumption) => (
                  <li key={assumption} className="break-words">
                    • {scrub(assumption)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-3 border-t border-line px-4 py-3">
        <Button
          disabled={starting || runActive}
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
        <p className="text-caption text-grey">
          {plan.time_band !== null && plan.time_band !== "" ? scrub(plan.time_band) : ""}
          {!unattended &&
            `${plan.time_band !== null && plan.time_band !== "" ? " · " : ""}You can steer or pause at any check-in.`}
        </p>
      </div>
      {startNotice !== null && (
        <p role="alert" className="border-t border-line px-4 py-2 text-caption text-red">
          {startNotice}
        </p>
      )}
    </div>
  );
}
