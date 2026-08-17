import type { ReactNode } from "react";

import { usePlan } from "../../api/queries";
import type { components } from "../../api/gen/types";
import { seedComposer } from "../../lib/composerSeed";
import { scrub } from "../../lib/scrub";
import { COPY } from "../../lib/vocabulary";
import { Button } from "../../ui/brand/Button";

type PlanDraft = components["schemas"]["PlanDraft"];

/**
 * One readable part of the plan, and the sentence that asks to change it.
 *
 * `seed` is what "Change this" puts in the composer — a first-person sentence
 * the person can edit rather than a command, because what follows is a
 * negotiation with the planner, not a form submission.
 */
type Part = {
  key: string;
  label: string;
  /** The rendered value, or `null` when the plan has not decided it yet. */
  value: (plan: PlanDraft) => ReactNode;
  seed: string;
};

function list(values: readonly string[] | null | undefined): ReactNode {
  if (values == null || values.length === 0) return null;
  return (
    <ul className="list-disc space-y-1 pl-5">
      {values.map((value, index) => (
        <li key={index}>{scrub(value)}</li>
      ))}
    </ul>
  );
}

function text(value: string | null | undefined): ReactNode {
  return value == null || value.trim() === "" ? null : scrub(value);
}

/** Every field the plan object carries, in the order a reader meets them. */
const PARTS: readonly Part[] = [
  {
    key: "question",
    label: "The question",
    value: (plan) => text(plan.question),
    seed: "I'd like to change the question to ",
  },
  {
    key: "scoping_notes",
    label: "Scope",
    value: (plan) => list(plan.scoping_notes),
    seed: "I'd like to change the scope: ",
  },
  {
    key: "screening_criteria",
    label: "What counts as relevant",
    value: (plan) => list(plan.screening_criteria),
    seed: "I'd like to change what counts as relevant: ",
  },
  {
    key: "scope_constraints",
    label: "Limits on the evidence",
    value: (plan) => {
      const constraints = plan.scope_constraints;
      if (constraints == null) return null;
      const countries = constraints.author_affiliation_countries;
      const parts = [
        constraints.published_after != null ? `Published on or after ${constraints.published_after}` : null,
        constraints.published_before != null ? `Published on or before ${constraints.published_before}` : null,
        constraints.publisher_country != null ? `Publisher in ${constraints.publisher_country}` : null,
        countries != null && countries.length > 0
          ? `Authors affiliated in ${countries.join(", ")}`
          : null,
        constraints.country_group != null ? `Country group: ${constraints.country_group}` : null,
      ].filter((part): part is string => part !== null);
      return parts.length > 0 ? list(parts) : null;
    },
    seed: "I'd like to change the limits on the evidence: ",
  },
  {
    key: "search_effort",
    label: "How widely to search",
    value: (plan) => text(plan.search_effort),
    seed: "I'd like to change how widely we search: ",
  },
  {
    key: "analysis_depth",
    label: "How deeply to analyse",
    value: (plan) => text(plan.analysis_depth),
    seed: "I'd like to change how deeply we analyse: ",
  },
  {
    key: "components",
    label: "What the analysis will do",
    value: (plan) => list(plan.components),
    seed: "I'd like to change what the analysis does: ",
  },
  {
    key: "grouping_facets",
    label: "How findings are grouped",
    value: (plan) => list(plan.grouping_facets),
    seed: "I'd like to change how findings are grouped: ",
  },
  {
    key: "extract_profiles",
    label: "What to extract",
    value: (plan) => list(plan.extract_profiles),
    seed: "I'd like to change what we extract: ",
  },
  {
    key: "section_budget",
    label: "How long the report should be",
    value: (plan) =>
      plan.section_budget == null ? null : `${plan.section_budget} sections`,
    seed: "I'd like to change how long the report is: ",
  },
  {
    key: "steering_mode",
    label: "When to check in with you",
    value: (plan) => text(plan.steering_mode),
    seed: "I'd like to change when you check in with me: ",
  },
  {
    key: "steps",
    label: "The agreed steps",
    value: (plan) =>
      plan.steps == null || plan.steps.length === 0
        ? null
        : (
            <ol className="list-decimal space-y-1 pl-5">
              {plan.steps.map((step, index) => (
                <li key={index}>{scrub(step.label)}</li>
              ))}
            </ol>
          ),
    seed: "I'd like to change the steps: ",
  },
  {
    key: "assumptions",
    label: "Assumptions we are making",
    value: (plan) => list(plan.assumptions),
    seed: "I'd like to revisit an assumption: ",
  },
  {
    key: "time_band",
    label: "Roughly how long it will take",
    value: (plan) => text(plan.time_band),
    seed: "I'd like to change how long this takes: ",
  },
];

/**
 * The plan, read as a document rather than as a card in the thread.
 *
 * Every part renders, including the ones the plan has not decided yet — an
 * undecided part says so. Hiding it would make the plan look more settled
 * than it is, and the empty parts are exactly the ones worth talking about.
 */
export function PlanDocument({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const plan = usePlan(projectId);
  const draft = plan.data?.plan;

  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-label="The plan"
      className="absolute inset-y-0 right-0 z-20 w-full max-w-[560px] overflow-y-auto border-l border-line bg-paper p-6 shadow-lg"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-heading font-bold text-navy">The plan</h2>
          {plan.data != null && (
            <p className="mt-1 text-caption uppercase tracking-[0.06em] text-grey">
              {plan.data.status} · version {plan.data.version}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-label="Close the plan"
          onClick={onClose}
          className="cursor-pointer text-heading leading-none text-grey hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          ×
        </button>
      </div>

      {plan.isPending && <p className="mt-6 text-body text-grey">Loading the plan…</p>}
      {plan.isError && (
        <p role="alert" className="mt-6 text-body text-navy">
          The plan couldn't be loaded.
        </p>
      )}

      {draft !== undefined && (
        <dl className="mt-6 space-y-6">
          {PARTS.map((part) => {
            const value = part.value(draft);
            return (
              <div key={part.key} className="border-b border-line pb-5 last:border-b-0">
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-caption font-bold uppercase tracking-[0.06em] text-grey">
                    {part.label}
                  </dt>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      seedComposer(part.seed);
                      onClose();
                    }}
                  >
                    Change this
                  </Button>
                </div>
                <dd className="mt-2 text-body text-navy">
                  {value ?? <span className="text-grey italic">{COPY.notDecided}</span>}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </aside>
  );
}
