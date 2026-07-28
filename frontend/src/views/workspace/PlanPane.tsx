import { useState } from "react";
import type { ReactNode } from "react";

import { useStartRun } from "../../api/mutations";
import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { conflictSentences, isConflictCode } from "../../lib/errors";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { Divider, PaneHeading } from "../../ui/brand/Card";
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

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] font-bold uppercase tracking-wider text-grey">{label}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

/** A labelled setting row; hides itself entirely when the locked vocabulary
 *  has no label for the key (unknown key → omit, never leak). */
function Setting({ label, value }: { label: string; value: string | null }) {
  if (value === null) return null;
  return (
    <Field label={label}>
      <span className="text-sm font-medium text-navy">{value}</span>
    </Field>
  );
}

/**
 * The forming plan as a first-class right-pane surface (contract strand 2),
 * replacing the collapsible plan disclosure: question · focus/scoping chips ·
 * constraint chips (geography-collapse rule) · labelled settings · steps
 * checklist (pre-ready: the planned components; at ready: server-labelled
 * steps) · ready/forming chip · time band · the full-width start CTA with a
 * starting-lock.
 */
export function PlanPane({ projectId }: { projectId: string }) {
  const planQuery = usePlan(projectId);
  const startRun = useStartRun(projectId);
  const [startNotice, setStartNotice] = useState<string | null>(null);
  const plan: PlanDraft | null = planQuery.data?.plan ?? null;

  if (plan === null || (!plan.question && (plan.steps ?? []).length === 0)) {
    return (
      <section aria-label="Plan" className="flex h-full flex-col">
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
  const components_ = plan.components ?? [];
  const starting = startRun.isPending;

  return (
    <section aria-label="Plan" className="flex h-full flex-col">
      <div className="flex items-center justify-between pr-4">
        <PaneHeading>Plan</PaneHeading>
        <div className="flex items-center gap-2">
          {plan.time_band !== null && plan.time_band !== "" && (
            <span className="text-[12px] text-grey">{scrub(plan.time_band)}</span>
          )}
          <Chip tone={plan.ready ? "green" : "soft"}>{plan.ready ? "ready" : "forming…"}</Chip>
        </div>
      </div>
      <Divider />
      <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        <p className="text-[12.5px] text-grey">
          Agreed here before anything runs. The analysis follows it.
        </p>

        <Field label="Question">
          <p className="text-[15px] font-semibold leading-snug text-navy">
            {plan.question !== null && plan.question !== "" ? (
              scrub(plan.question)
            ) : (
              <span className="text-grey">Not set yet</span>
            )}
          </p>
        </Field>

        {scopingNotes.length > 0 && (
          <Field label="Focus">
            <div className="flex flex-wrap gap-2">
              {scopingNotes.map((note) => (
                <Chip key={note} tone="soft">
                  {scrub(note)}
                </Chip>
              ))}
            </div>
            {screeningCriteria.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[12px] text-grey">
                {screeningCriteria.map((criterion) => (
                  <li key={criterion}>{scrub(criterion)}</li>
                ))}
              </ul>
            )}
          </Field>
        )}

        {constraints.length > 0 && (
          <Field label="Constraints">
            <div className="flex flex-wrap gap-2">
              {constraints.map((chip) => (
                <Chip key={chip} tone="soft">
                  {scrub(chip)}
                </Chip>
              ))}
            </div>
          </Field>
        )}

        <Setting label="Search effort" value={vocabLabel(SEARCH_EFFORT_LABEL, plan.search_effort)} />
        <Setting label="Analysis depth" value={vocabLabel(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)} />
        <Setting label="Sources" value={vocabLabel(SOURCES_LABEL, plan.backend_scope)} />
        <Setting label="Check-ins" value={vocabLabel(STEERING_MODE_LABEL, plan.steering_mode)} />

        {steps.length > 0 ? (
          <Field label="Steps">
            <ol className="space-y-2.5">
              {steps.map((step) => (
                <li key={step.stage} className="flex items-start gap-2.5 text-[13px] text-navy">
                  <span aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0 border border-line-2" />
                  <div>
                    <div>{scrub(step.label)}</div>
                    {step.blurb !== "" && <div className="text-[12px] text-grey">{scrub(step.blurb)}</div>}
                  </div>
                </li>
              ))}
            </ol>
          </Field>
        ) : (
          components_.length > 0 && (
            <Field label="Planned steps">
              <ul className="space-y-1.5 text-[13px] text-navy">
                {components_
                  .map((component) => vocabLabel(COMPONENT_LABEL, component))
                  .filter((label): label is string => label !== null)
                  .map((label) => (
                    <li key={label}>{label}</li>
                  ))}
              </ul>
            </Field>
          )
        )}
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
