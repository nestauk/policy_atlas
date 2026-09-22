import { useState } from "react";

import type { components } from "../../api/gen/types";
import { usePatchPlan } from "../../api/mutations";
import { usePlan, useTask } from "../../api/queries";
import { seedComposer } from "../../lib/composerSeed";
import { scrub } from "../../lib/scrub";
import { COPY } from "../../lib/vocabulary";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../../ui/radix/Popover";
import { Tooltip } from "../../ui/radix/Tooltip";
import { READING_COLUMN_MAX_W } from "../listPageChrome";
import {
  displayedEnum,
  displayedGeography,
  displayedQuestion,
  displayedScreening,
  displayedYearAfter,
  displayedYearBefore,
  mergeOverlayChanges,
  screeningOverlayError,
  type PlanOverlay,
} from "./planOverlay";
import { START_SEARCH_CLASS, scopingStatusLine, usePlanStart, useScopingPlanStart } from "./planStart";
import {
  ANALYSIS_DEPTH_LABEL,
  ANALYSIS_QUESTION,
  ANALYSIS_TITLE,
  axesForResearchApproach,
  CONSTRAINT_CHECKED_AT_LABEL,
  constraintEffectLines,
  DEFAULT_CONSTRAINT_RIDER,
  RESEARCH_APPROACH_CUSTOM,
  RESEARCH_APPROACH_HINT,
  RESEARCH_APPROACH_PRESET_LABEL,
  RESEARCH_APPROACH_TITLE,
  researchApproachId,
  researchApproachLabel,
  SCOPING_DEPTH_LABEL,
  SCOPING_STEERING_MODE_LABEL,
  SEARCH_EFFORT_LABEL,
  SEARCH_SCOPE_HINT,
  SEARCH_SCOPE_TITLE,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  stepsForAnalysisDepth,
  TAG_ORIGIN_LABEL,
  timeBandFor,
  vocabLabel,
  YOUR_CONTEXT_TYPE_LABEL,
  YOUR_OPTIONS_ASSUMED_TAG,
  YOUR_OPTIONS_DESIGN_LABEL,
  YOUR_OPTIONS_DESIGN_PENDING,
  YOUR_OPTIONS_NONE,
  YOUR_OPTIONS_TITLE,
} from "./planVocabulary";

type ScopingPlanDraft = components["schemas"]["ScopingPlanDraft"];
type TaggedOut = components["schemas"]["TaggedOut"];
type ScopingConstraintOut = components["schemas"]["ScopingConstraintOut"];
type YourContextOut = components["schemas"]["YourContextOut"];
type YourOptionOut = components["schemas"]["YourOptionOut"];
type TaskLinkOut = components["schemas"]["TaskLinkOut"];

const panelLabelClass = "text-lead font-bold text-white";
const panelEditButtonClass =
  "cursor-pointer border border-white/25 px-3 py-1.5 text-body font-semibold text-white hover:bg-white/10";
const panelFieldClass =
  "w-full border border-white/25 bg-[#0a1f38] px-3 py-2.5 text-lead text-white focus-visible:outline-2 focus-visible:outline-blue";
const panelValueClass = "mt-0.5 text-lead text-white";
const panelHintClass = "text-body text-[#c5d0dc]";

function InfoHint({ label, hint }: { label: string; hint: string }) {
  return (
    <Tooltip content={hint} className="whitespace-pre-line">
      <button
        type="button"
        aria-label={`About ${label}`}
        className="inline-flex h-5 w-5 shrink-0 cursor-pointer items-center justify-center text-[#97a8bc] hover:text-white focus-visible:outline-2 focus-visible:outline-blue"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.25" />
          <circle cx="8" cy="5.25" r="0.85" fill="currentColor" />
          <path d="M8 7.4v4.1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>
    </Tooltip>
  );
}

function FieldTitle({
  id,
  label,
  hint,
  className = panelHintClass,
}: {
  id?: string;
  label: string;
  hint?: string;
  className?: string;
}) {
  return (
    <span className="mb-1.5 flex items-center gap-1.5">
      <span id={id} className={className}>
        {label}
      </span>
      {hint != null && hint !== "" && <InfoHint label={label} hint={hint} />}
    </span>
  );
}

function PanelSection({
  label,
  editing,
  onEdit,
  onCancel,
  onSave,
  children,
  view,
  readOnly = false,
}: {
  label: string;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  view: React.ReactNode;
  children: React.ReactNode;
  readOnly?: boolean;
}) {
  return (
    <section className="border-b border-white/15 pb-6 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <h3 className={panelLabelClass}>{label}</h3>
        {!readOnly &&
          (editing ? (
          <div className="flex shrink-0 items-center gap-2">
            <button type="button" className={panelEditButtonClass} onClick={onCancel}>
              Cancel
            </button>
            <button
              type="button"
              className={cn(panelEditButtonClass, "border-blue bg-blue text-white hover:bg-[#0000d6]")}
              onClick={onSave}
            >
              Save
            </button>
          </div>
        ) : (
          <button type="button" className={panelEditButtonClass} onClick={onEdit}>
            Edit
          </button>
        ))}
      </div>
      <div className="mt-3">{editing ? children : view}</div>
    </section>
  );
}

function PlanPicker({
  id,
  label,
  hint,
  value,
  options,
  displayValue,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  options: Record<string, string>;
  displayValue?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = displayValue ?? options[value] ?? value;

  const pick = (key: string) => {
    onChange(key);
    setOpen(false);
  };

  return (
    <div>
      <FieldTitle id={`${id}-label`} label={label} hint={hint} />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            id={id}
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-labelledby={`${id}-label`}
            className="flex w-full cursor-pointer items-center justify-between gap-3 border border-white/25 bg-[#0a1f38] px-3 py-2.5 text-left text-lead font-normal text-white hover:border-white/50 focus-visible:outline-2 focus-visible:outline-blue"
          >
            <span className="min-w-0 flex-1 text-pretty">{selected}</span>
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="h-4 w-4 shrink-0 text-[#97a8bc]"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-1 text-body">
          <ul role="listbox" aria-labelledby={`${id}-label`} className="flex flex-col">
            {Object.entries(options).map(([key, optionLabel]) => (
              <li key={key} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={value === key}
                  onClick={() => pick(key)}
                  className={cn(
                    "block w-full cursor-pointer px-3 py-2.5 text-left text-lead font-normal text-pretty text-navy hover:bg-blue-tint-2 hover:text-blue",
                    value === key && "bg-blue-tint-2 font-medium",
                  )}
                >
                  {optionLabel}
                </button>
              </li>
            ))}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}

type FilterDraft = {
  backend_scope: string;
  published_after_year: string;
  published_before_year: string;
  geography: string;
};

type SettingsDraft = {
  search_effort: string;
  analysis_depth: string;
  steering_mode: string;
};

function PlanChromeIcon({ children }: { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="block size-4"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

function PlanChrome({
  showDock,
  onDock,
  onClose,
  closeLabel = "Close the search plan",
  className,
}: {
  showDock: boolean;
  onDock?: () => void;
  onClose: () => void;
  closeLabel?: string;
  className?: string;
}) {
  const controlClass =
    "inline-flex size-8 shrink-0 cursor-pointer items-center justify-center p-0 text-[#97a8bc] hover:text-white focus-visible:outline-2 focus-visible:outline-blue";
  return (
    <div className={cn("flex h-8 items-center", className)}>
      {showDock && onDock !== undefined && (
        <button
          type="button"
          aria-label="Move the plan to the side"
          title="Move to the side"
          onClick={onDock}
          className={controlClass}
        >
          <PlanChromeIcon>
            <path d="m9 6 6 6-6 6" />
          </PlanChromeIcon>
        </button>
      )}
      <button type="button" aria-label={closeLabel} onClick={onClose} className={controlClass}>
        <PlanChromeIcon>
          <path d="M6 6 18 18" />
          <path d="M18 6 6 18" />
        </PlanChromeIcon>
      </button>
    </div>
  );
}

// --- Scoping plan sections (task 044, contract deliverable 5, C18) --------
//
// The scoping plan has no inline field editor of its own: its fields are
// Task Agent-negotiated (provenance-tagged), not raw strings a form can
// safely overwrite. Edit seeds the Task Agent composer instead — the same
// "put it in the conversation" idiom `PartCard`'s own Change control uses,
// carried over the DOM event `lib/composerSeed.ts` exists for (its docstring
// names exactly this cross-subtree case).

/** A field's origin tag, rendered as the fixed screen words (never the raw
 *  enum). Omitted for an unknown or absent origin — the same fail-soft rule
 *  every lookup on this page follows. */
function OriginTag({ origin }: { origin?: TaggedOut["origin"] | null }) {
  const label = origin != null ? TAG_ORIGIN_LABEL[origin] : null;
  if (label == null) return null;
  return <span className={cn("ml-2 italic", panelHintClass)}>({label})</span>;
}

/** One scoping section's frame: the same label/border chrome as the ES's
 *  `PanelSection`, but Edit seeds the composer rather than opening an inline
 *  form — there is nothing here to edit in place. */
function ScopingSection({
  label,
  onEdit,
  readOnly,
  children,
}: {
  label: string;
  /** Omitted entirely for a section the ES pattern also leaves un-editable
   *  (Starts from, Steps and check-ins). */
  onEdit?: () => void;
  readOnly: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-white/15 pb-6 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <h3 className={panelLabelClass}>{label}</h3>
        {!readOnly && onEdit !== undefined && (
          <button type="button" className={panelEditButtonClass} onClick={onEdit}>
            Edit
          </button>
        )}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** One provenance-tagged field, rendered with its origin words. */
function TaggedField({ label, tagged }: { label: string; tagged?: TaggedOut | null }) {
  return (
    <div>
      <dt className={panelHintClass}>{label}</dt>
      <dd className={panelValueClass}>
        {tagged != null ? (
          <>
            {scrub(tagged.text)}
            <OriginTag origin={tagged.origin} />
          </>
        ) : (
          <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>
        )}
      </dd>
    </div>
  );
}

/** A list of provenance-tagged fields (Outcomes: zero, one or several). */
function TaggedListField({ label, items }: { label: string; items?: TaggedOut[] | null }) {
  const list = items ?? [];
  return (
    <div>
      <dt className={panelHintClass}>{label}</dt>
      <dd className={panelValueClass}>
        {list.length === 0 ? (
          <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>
        ) : (
          <ul className="space-y-1">
            {list.map((item, index) => (
              <li key={`${item.origin}-${item.text}-${index}`}>
                {scrub(item.text)}
                <OriginTag origin={item.origin} />
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

/** "Starts from": one line per Link (C18), hidden entirely with none. Not
 *  editable — a Link is fixed at task creation (contract deliverable 4). */
function StartsFromSection({ links }: { links: TaskLinkOut[] }) {
  if (links.length === 0) return null;
  return (
    <section className="border-b border-white/15 pb-6 last:border-b-0">
      <h3 className={panelLabelClass}>Starts from</h3>
      <ul className="mt-3 space-y-1.5 text-lead text-white">
        {links.map((link) => (
          <li key={link.link_id}>
            {link.source_task_name === null
              ? "Evidence search: a task you can't open · linked"
              : `Evidence search: ${scrub(link.source_task_name)} · linked`}
            {link.flagged && (
              <span className={panelHintClass}> · no longer shares a project</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** "Question and intended change": the user's ask, plain, then what we are
 *  trying to change, tagged. */
function QuestionAndChangeSection({
  scoping,
  onEdit,
  readOnly,
}: {
  scoping: ScopingPlanDraft;
  onEdit: () => void;
  readOnly: boolean;
}) {
  return (
    <ScopingSection label="Question and intended change" onEdit={onEdit} readOnly={readOnly}>
      <div className="space-y-3">
        <p className="text-lead text-white">
          {scoping.question != null && scoping.question !== "" ? scrub(scoping.question) : COPY.notDecided}
        </p>
        <dl>
          <TaggedField label="What we are trying to change" tagged={scoping.intended_change} />
        </dl>
      </div>
    </ScopingSection>
  );
}

/** "Settings": who or what should change, where, outcomes, depth and
 *  check-ins — the same five-row shape the ES's own Settings section has. */
function ScopingSettingsSection({
  scoping,
  onEdit,
  readOnly,
}: {
  scoping: ScopingPlanDraft;
  onEdit: () => void;
  readOnly: boolean;
}) {
  const depthLabel = scoping.depth != null ? (SCOPING_DEPTH_LABEL[scoping.depth] ?? null) : null;
  const checkInsLabel =
    scoping.steering_mode != null ? (SCOPING_STEERING_MODE_LABEL[scoping.steering_mode] ?? null) : null;
  return (
    <ScopingSection label="Settings" onEdit={onEdit} readOnly={readOnly}>
      <dl className="space-y-3">
        <TaggedField label="Who or what should change" tagged={scoping.target_unit} />
        <TaggedField label="Where" tagged={scoping.where} />
        <TaggedListField label="Outcomes" items={scoping.outcomes} />
        <div>
          <dt className={panelHintClass}>Depth</dt>
          <dd className={panelValueClass}>
            {depthLabel ?? <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>}
          </dd>
        </div>
        <div>
          <dt className={panelHintClass}>Check-ins</dt>
          <dd className={panelValueClass}>
            {checkInsLabel ?? <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>}
          </dd>
        </div>
      </dl>
    </ScopingSection>
  );
}

/** "Constraints and preferences": what was asked for, the fixed effect
 *  sentence for its kind, and when it is checked. */
function ConstraintsSection({
  constraints,
  onEdit,
  readOnly,
  onRemoveDefault,
}: {
  constraints: ScopingConstraintOut[];
  onEdit: () => void;
  readOnly: boolean;
  /** Removes a code-minted default row by a direct plan edit (task 045,
   *  D22) — the Task Agent never authors the default, so it cannot remove
   *  it either. Omitted while the plan cannot be edited directly. */
  onRemoveDefault?: (constraint: ScopingConstraintOut) => void;
}) {
  return (
    <ScopingSection label="Constraints and preferences" onEdit={onEdit} readOnly={readOnly}>
      {constraints.length === 0 ? (
        <p className="text-lead text-[#97a8bc] italic">{COPY.notDecided}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-lead text-white">
            <thead>
              <tr className={cn("text-body font-normal", panelHintClass)}>
                <th className="pb-2 pr-3 font-normal">What you asked for</th>
                <th className="pb-2 pr-3 font-normal">What happens</th>
                <th className="pb-2 font-normal">Checked at</th>
              </tr>
            </thead>
            <tbody>
              {constraints.map((constraint, index) => (
                <tr
                  key={`${constraint.kind}-${constraint.text}-${index}`}
                  className="border-t border-white/10 align-top"
                >
                  <td className="py-2 pr-3">
                    {scrub(constraint.text)}
                    {constraint.default != null && DEFAULT_CONSTRAINT_RIDER[constraint.default] != null && (
                      <span className={cn("block", panelHintClass)}>
                        {DEFAULT_CONSTRAINT_RIDER[constraint.default]}
                      </span>
                    )}
                    {constraint.default != null && !readOnly && onRemoveDefault !== undefined && (
                      <button
                        type="button"
                        className={cn("mt-1 block underline", panelHintClass)}
                        onClick={() => onRemoveDefault(constraint)}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-[#e8edf2]">
                    {constraintEffectLines(constraint).map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </td>
                  <td className="py-2">
                    {CONSTRAINT_CHECKED_AT_LABEL[constraint.checked_at] ?? constraint.checked_at}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ScopingSection>
  );
}

/** "Options you already have in mind" (task 045, D19): the user's words,
 *  then the design Policy Atlas proposed back, features it supplied marked
 *  assumed. Hidden until the plan has asked (the slot is null); an empty
 *  list — the user said they have none — shows "None". */
function YourOptionsSection({
  options,
  onEdit,
  readOnly,
}: {
  options: YourOptionOut[] | null | undefined;
  onEdit: () => void;
  readOnly: boolean;
}) {
  if (options == null) return null;
  return (
    <ScopingSection label={YOUR_OPTIONS_TITLE} onEdit={onEdit} readOnly={readOnly}>
      {options.length === 0 ? (
        <p className="text-lead text-[#97a8bc] italic">{YOUR_OPTIONS_NONE}</p>
      ) : (
        <ul className="space-y-4 text-lead text-white">
          {options.map((option, index) => (
            <li key={`${option.text}-${index}`} data-testid="your-option">
              <p>{scrub(option.text)}</p>
              {option.design != null ? (
                <div className="mt-1.5">
                  <p className={panelHintClass}>
                    {YOUR_OPTIONS_DESIGN_LABEL}: {scrub(option.design.name)}
                  </p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[#e8edf2]">
                    {option.design.design_features.map((feature, featureIndex) => (
                      <li key={`${feature}-${featureIndex}`}>
                        {scrub(feature)}
                        {(option.design?.assumed ?? []).includes(feature) && (
                          <span className={cn("ml-2 italic", panelHintClass)}>
                            ({YOUR_OPTIONS_ASSUMED_TAG})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className={cn("mt-1 italic", panelHintClass)}>{YOUR_OPTIONS_DESIGN_PENDING}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </ScopingSection>
  );
}

/** "Your context": verbatim entries, hidden entirely with none. */
function YourContextSection({
  entries,
  onEdit,
  readOnly,
}: {
  entries: YourContextOut[];
  onEdit: () => void;
  readOnly: boolean;
}) {
  if (entries.length === 0) return null;
  return (
    <ScopingSection label="Your context" onEdit={onEdit} readOnly={readOnly}>
      <ul className="space-y-2 text-lead text-white">
        {entries.map((entry, index) => (
          <li key={`${entry.turn_index}-${index}`}>
            {scrub(entry.text)}
            <span className={cn("ml-2 italic", panelHintClass)}>
              (
              {YOUR_CONTEXT_TYPE_LABEL[entry.type] ?? entry.type}
              {entry.test_as_condition ? ", test as a condition" : ""}
              )
            </span>
          </li>
        ))}
      </ul>
    </ScopingSection>
  );
}

/** "Steps and check-ins": the three display steps, un-editable like the
 *  ES's own Plan steps section. */
function ScopingStepsSection({ steps }: { steps: ScopingPlanDraft["steps"] }) {
  const list = steps ?? [];
  if (list.length === 0) return null;
  return (
    <section className="border-b border-white/15 pb-6 last:border-b-0">
      <h3 className={panelLabelClass}>Steps and check-ins</h3>
      <ol className="mt-3 list-none space-y-2 pl-1 text-lead text-[#e8edf2]">
        {list.map((step, index) => (
          <li key={step.stage} className="flex gap-1.5">
            <span aria-hidden="true" className="w-4 shrink-0 tabular-nums">
              {index + 1}.
            </span>
            <div className="min-w-0 flex-1">
              {step.label}
              <span className={cn("block", panelHintClass)}>{step.blurb}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The scoping plan's start area, in its states (contract deliverable 5;
 *  task 045 adds the longlist's); `useScopingPlanStart` carries the state
 *  logic and `scopingStatusLine` the one sentence each state says. */
function ScopingStartActions({
  taskId,
  runActive,
  onStarted,
}: {
  taskId: string;
  runActive: boolean;
  onStarted?: () => void;
}) {
  const state = useScopingPlanStart({ taskId, runActive, onStarted });
  const line = scopingStatusLine(state);
  const lineElement = line !== null && <p className="text-lead text-white">{line}</p>;

  // A walk is running or paused. Before the plan is confirmed the gate's own
  // check-in card and the Task Agent chat own the decision; after it the line
  // says the longlist is being built. Either way confirm-baseline is 409
  // `run_active` while it's live, so there is nothing safe to offer.
  if (state.kind === "none" || state.kind === "longlist_built") {
    return lineElement || null;
  }

  if (state.kind === "confirmed" || state.kind === "rebuild_longlist") {
    const action = state.kind === "confirmed" ? state.build : state.rebuild;
    return (
      <div className="space-y-3">
        {lineElement}
        <Button className={cn(START_SEARCH_CLASS)} disabled={action.disabled} onClick={action.onConfirm}>
          {action.label}
        </Button>
        {state.notice != null && (
          <p role="alert" className="text-body text-red-tint">
            {state.notice}
          </p>
        )}
      </div>
    );
  }

  if (state.kind === "build") {
    return (
      <div>
        <Button className={cn(START_SEARCH_CLASS)} disabled={state.disabled} onClick={state.onStart}>
          {state.label}
        </Button>
        {state.timeBand != null && state.timeBand !== "" && (
          <p className="mt-2 text-body text-[#97a8bc]">{scrub(state.timeBand)}</p>
        )}
        {state.notice != null && (
          <p role="alert" className="mt-2 text-body text-red-tint">
            {state.notice}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button className={cn(START_SEARCH_CLASS)} disabled={state.rebuild.disabled} onClick={state.rebuild.onStart}>
        {state.rebuild.label}
      </Button>
      <Button variant="secondary" disabled={state.confirm.disabled} onClick={state.confirm.onConfirm}>
        {state.confirm.label}
      </Button>
      {state.notice != null && (
        <p role="alert" className="w-full text-body text-red-tint">
          {state.notice}
        </p>
      )}
    </div>
  );
}

/** The scoping plan's sections, in the contract's fixed order (deliverable
 *  5). Isolated from the ES render path so an Evidence search plan never
 *  pays for `useTask`/`useRuns`/`useArtefact` it has no use for. */
function ScopingPlanSections({
  taskId,
  scoping,
  readOnly,
  runActive,
  approved,
  onStarted,
}: {
  taskId: string;
  scoping: ScopingPlanDraft;
  readOnly: boolean;
  runActive: boolean;
  /** Whether an approved version exists — a direct plan edit needs one. */
  approved: boolean;
  onStarted?: () => void;
}) {
  const taskQuery = useTask(taskId);
  const links = taskQuery.data?.links ?? [];
  const patchPlan = usePatchPlan(taskId);
  const constraints = scoping.constraints ?? [];
  const removeDefault =
    approved && !runActive
      ? (row: ScopingConstraintOut) =>
          patchPlan.mutate({ scoping: { constraints: constraints.filter((c) => c !== row) } })
      : undefined;

  return (
    <>
      <div className="space-y-6">
        <StartsFromSection links={links} />
        <QuestionAndChangeSection
          scoping={scoping}
          onEdit={() => seedComposer("Change the question or intended change: ")}
          readOnly={readOnly}
        />
        <ScopingSettingsSection
          scoping={scoping}
          onEdit={() => seedComposer("Change a setting: ")}
          readOnly={readOnly}
        />
        <ConstraintsSection
          constraints={constraints}
          onEdit={() => seedComposer("Change a constraint or preference: ")}
          readOnly={readOnly}
          onRemoveDefault={removeDefault}
        />
        <YourOptionsSection
          options={scoping.your_options}
          onEdit={() => seedComposer("Change the options I have in mind: ")}
          readOnly={readOnly}
        />
        <YourContextSection
          entries={scoping.your_context ?? []}
          onEdit={() => seedComposer("Add to your context: ")}
          readOnly={readOnly}
        />
        <ScopingStepsSection steps={scoping.steps} />
      </div>

      {/* A live walk makes the plan read-only, but the start area still says
          where things stand ("Building the longlist") — it offers nothing to
          click while a walk runs (task 045). */}
      {(!readOnly || runActive) && (
        <div className="pt-8">
          <ScopingStartActions taskId={taskId} runActive={runActive} onStarted={onStarted} />
        </div>
      )}
    </>
  );
}

/**
 * The search plan, edited in place. Saves stay local until Start search —
 * a task_agent round-trip on every field would rewrite the whole plan.
 */
export function PlanDocument({
  taskId,
  placement = "side",
  runActive = false,
  readOnly = false,
  onClose,
  onDock,
  onStarted,
  overlay,
  onOverlayChange,
}: {
  taskId: string;
  /** Centre overlay vs docked side panel. */
  placement?: "center" | "side";
  runActive?: boolean;
  /** After Start search the plan is a record — visible, not editable. */
  readOnly?: boolean;
  onClose: () => void;
  onDock?: () => void;
  onStarted?: () => void;
  overlay: PlanOverlay;
  onOverlayChange: (overlay: PlanOverlay) => void;
}) {
  const planQuery = usePlan(taskId);
  // A scoping task's `PlanOut.plan` is null (task 044) — its fields live on
  // `scoping` instead, rendered by a wholly separate section set below. This
  // normalizes `draft` to `undefined` for a scoping task so every existing
  // `draft !== undefined` check below stays an honest "no ES plan to show",
  // never a null slipping through as a truthy-looking draft object.
  const isScoping = planQuery.data?.capability === "options_scoping";
  const draft = isScoping ? undefined : (planQuery.data?.plan ?? undefined);
  const {
    start,
    discardAndStart,
    hasLocalEdits,
    startNotice,
    disabled: startDisabled,
    label: startLabel,
  } = usePlanStart({
    taskId,
    overlay,
    runActive,
    onStarted,
    onOverlayApplied: () => onOverlayChange({}),
    onDiscardOverlay: () => onOverlayChange({}),
  });

  const [editingQuestion, setEditingQuestion] = useState(false);
  const [editingSettings, setEditingSettings] = useState(false);
  const [editingFilters, setEditingFilters] = useState(false);
  const [editingScreening, setEditingScreening] = useState(false);

  const [questionDraft, setQuestionDraft] = useState("");
  const [settingsDraft, setSettingsDraft] = useState<SettingsDraft>({
    search_effort: "standard",
    analysis_depth: "standard",
    steering_mode: "moderate",
  });
  const [filterDraft, setFilterDraft] = useState<FilterDraft>({
    backend_scope: "both",
    published_after_year: "",
    published_before_year: "",
    geography: "",
  });
  const [screeningDraft, setScreeningDraft] = useState<string[]>([""]);
  const [screeningError, setScreeningError] = useState<string | null>(null);

  const beginQuestionEdit = () => {
    if (draft === undefined) return;
    setQuestionDraft(displayedQuestion(draft, overlay));
    setEditingQuestion(true);
  };
  const beginSettingsEdit = () => {
    if (draft === undefined) return;
    setSettingsDraft({
      search_effort: displayedEnum(overlay.search_effort, draft.search_effort) || "standard",
      analysis_depth: displayedEnum(overlay.analysis_depth, draft.analysis_depth) || "standard",
      steering_mode: displayedEnum(overlay.steering_mode, draft.steering_mode) || "moderate",
    });
    setEditingSettings(true);
  };
  const beginFiltersEdit = () => {
    if (draft === undefined) return;
    setFilterDraft({
      backend_scope: displayedEnum(overlay.backend_scope, draft.backend_scope) || "both",
      published_after_year: displayedYearAfter(draft, overlay),
      published_before_year: displayedYearBefore(draft, overlay),
      geography: displayedGeography(draft, overlay),
    });
    setEditingFilters(true);
  };
  const beginScreeningEdit = () => {
    if (draft === undefined) return;
    const current = displayedScreening(draft, overlay);
    setScreeningDraft(current.length > 0 ? current : [""]);
    setScreeningError(null);
    setEditingScreening(true);
  };
  const addScreeningRule = () => {
    setScreeningDraft((current) =>
      current.some((rule) => rule.trim() === "") ? current : [...current, ""],
    );
  };
  const updateScreeningRule = (index: number, value: string) => {
    setScreeningDraft((current) => current.map((rule, i) => (i === index ? value : rule)));
  };
  const removeScreeningRule = (index: number) => {
    setScreeningDraft((current) => current.filter((_, i) => i !== index));
  };

  const yearAfter = draft !== undefined ? displayedYearAfter(draft, overlay) : "";
  const yearBefore = draft !== undefined ? displayedYearBefore(draft, overlay) : "";
  const geography = draft !== undefined ? displayedGeography(draft, overlay) : "";
  const screening = draft !== undefined ? displayedScreening(draft, overlay) : [];
  const question = draft !== undefined ? displayedQuestion(draft, overlay) : "";
  const searchEffort =
    draft !== undefined ? displayedEnum(overlay.search_effort, draft.search_effort) : "";
  const analysisDepth =
    draft !== undefined ? displayedEnum(overlay.analysis_depth, draft.analysis_depth) : "";
  const sources = draft !== undefined ? displayedEnum(overlay.backend_scope, draft.backend_scope) : "";
  const checkIns = draft !== undefined ? displayedEnum(overlay.steering_mode, draft.steering_mode) : "";
  const previewEffort = editingSettings ? settingsDraft.search_effort : searchEffort;
  const previewDepth = editingSettings ? settingsDraft.analysis_depth : analysisDepth;
  const previewSources = editingFilters ? filterDraft.backend_scope : sources;
  const expectedRunTime = timeBandFor(previewEffort, previewDepth) ?? draft?.time_band ?? null;
  const agreedSteps = stepsForAnalysisDepth(previewDepth, previewSources);

  return (
    <aside
      role="dialog"
      aria-modal={placement === "center"}
      aria-label={isScoping ? "Scoping plan" : "Search plan"}
      className={cn(
        "relative flex h-full min-h-0 flex-col overflow-hidden bg-navy text-white",
        placement === "side"
          ? cn("min-w-0 flex-1 border-l border-[#1a3a5c]", READING_COLUMN_MAX_W)
          : "w-full",
      )}
    >
      {placement === "center" && (
        <div className="pointer-events-none absolute inset-x-0 top-8 z-10 px-5">
          <div className={cn("relative mx-auto w-full", READING_COLUMN_MAX_W)}>
            <PlanChrome
              showDock
              onDock={onDock}
              onClose={onClose}
              closeLabel={isScoping ? "Close the scoping plan" : "Close the search plan"}
              className="pointer-events-auto absolute top-0 right-0 translate-x-[calc(100%+0.5rem)] max-[52rem]:translate-x-0"
            />
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={cn("mx-auto w-full px-5 py-8", READING_COLUMN_MAX_W)}>
          <div className="mb-6 flex items-start justify-between gap-3 border-b border-white/15 pb-6">
            <header className="min-w-0 flex-1">
              <h2 className="text-heading font-extrabold text-white">
                {isScoping ? "Scoping plan" : "Search plan"}
              </h2>
              {!isScoping && expectedRunTime != null && expectedRunTime !== "" && (
                <p className="mt-1 text-body text-[#97a8bc]">
                  Expected run time: {scrub(expectedRunTime)}
                </p>
              )}
            </header>
            {placement === "side" && (
              <PlanChrome
                showDock={false}
                onClose={onClose}
                closeLabel={isScoping ? "Close the scoping plan" : "Close the search plan"}
                className="shrink-0"
              />
            )}
          </div>

          {planQuery.isPending && <p className="text-body text-[#c5d0dc]">Loading the plan…</p>}
          {planQuery.isError && (
            <p role="alert" className="text-body text-red-tint">
              The plan couldn't be loaded.
            </p>
          )}

          {isScoping && planQuery.data?.scoping != null && (
            <ScopingPlanSections
              taskId={taskId}
              scoping={planQuery.data.scoping}
              readOnly={readOnly}
              runActive={runActive}
              approved={planQuery.data.status === "approved"}
              onStarted={onStarted}
            />
          )}

          {!isScoping && draft !== undefined && (
            <div className="space-y-6">
            <PanelSection
              readOnly={readOnly}
              label="Research question"
              editing={editingQuestion}
              onEdit={beginQuestionEdit}
              onCancel={() => setEditingQuestion(false)}
              onSave={() => {
                if (draft === undefined) return;
                onOverlayChange(mergeOverlayChanges(overlay, draft, { question: questionDraft }));
                setEditingQuestion(false);
              }}
              view={
                <p className="text-lead text-white">
                  {question.trim() !== "" ? scrub(question) : COPY.notDecided}
                </p>
              }
            >
              <textarea
                rows={4}
                value={questionDraft}
                onChange={(event) => setQuestionDraft(event.target.value)}
                className={cn(panelFieldClass, "resize-y")}
              />
            </PanelSection>

            <PanelSection
              readOnly={readOnly}
              label="Settings"
              editing={editingSettings}
              onEdit={beginSettingsEdit}
              onCancel={() => setEditingSettings(false)}
              onSave={() => {
                if (draft === undefined) return;
                onOverlayChange(
                  mergeOverlayChanges(overlay, draft, {
                    search_effort: settingsDraft.search_effort,
                    analysis_depth: settingsDraft.analysis_depth,
                    steering_mode: settingsDraft.steering_mode,
                  }),
                );
                setEditingSettings(false);
              }}
              view={
                <dl className="space-y-3">
                  {(
                    [
                      [
                        RESEARCH_APPROACH_TITLE,
                        RESEARCH_APPROACH_HINT,
                        researchApproachLabel(searchEffort, analysisDepth),
                      ],
                      [SEARCH_SCOPE_TITLE, SEARCH_SCOPE_HINT, vocabLabel(SEARCH_EFFORT_LABEL, searchEffort)],
                      [ANALYSIS_TITLE, ANALYSIS_QUESTION, vocabLabel(ANALYSIS_DEPTH_LABEL, analysisDepth)],
                      ["Check-ins", undefined, vocabLabel(STEERING_MODE_LABEL, checkIns)],
                    ] as const
                  ).map(([label, hint, value]) => (
                    <div key={label}>
                      <dt>
                        <FieldTitle label={label} hint={hint} className={panelHintClass} />
                      </dt>
                      <dd className={panelValueClass}>
                        {value ?? <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>}
                      </dd>
                    </div>
                  ))}
                </dl>
              }
            >
              <div className="space-y-3">
                <PlanPicker
                  id="plan-research-approach"
                  label={RESEARCH_APPROACH_TITLE}
                  hint={RESEARCH_APPROACH_HINT}
                  value={researchApproachId(settingsDraft.search_effort, settingsDraft.analysis_depth) ?? "custom"}
                  options={RESEARCH_APPROACH_PRESET_LABEL}
                  displayValue={
                    researchApproachLabel(settingsDraft.search_effort, settingsDraft.analysis_depth) ??
                    RESEARCH_APPROACH_CUSTOM
                  }
                  onChange={(id) => {
                    const axes = axesForResearchApproach(id);
                    if (axes === null) return;
                    setSettingsDraft((current) => ({ ...current, ...axes }));
                  }}
                />
                <PlanPicker
                  id="plan-search-effort"
                  label={SEARCH_SCOPE_TITLE}
                  hint={SEARCH_SCOPE_HINT}
                  value={settingsDraft.search_effort}
                  options={SEARCH_EFFORT_LABEL}
                  onChange={(value) => setSettingsDraft((current) => ({ ...current, search_effort: value }))}
                />
                <PlanPicker
                  id="plan-analysis-depth"
                  label={ANALYSIS_TITLE}
                  hint={ANALYSIS_QUESTION}
                  value={settingsDraft.analysis_depth}
                  options={ANALYSIS_DEPTH_LABEL}
                  onChange={(value) => setSettingsDraft((current) => ({ ...current, analysis_depth: value }))}
                />
                <PlanPicker
                  id="plan-check-ins"
                  label="Check-ins"
                  value={settingsDraft.steering_mode}
                  options={STEERING_MODE_LABEL}
                  onChange={(value) => setSettingsDraft((current) => ({ ...current, steering_mode: value }))}
                />
              </div>
            </PanelSection>

            <PanelSection
              readOnly={readOnly}
              label="Search filters"
              editing={editingFilters}
              onEdit={beginFiltersEdit}
              onCancel={() => setEditingFilters(false)}
              onSave={() => {
                if (draft === undefined) return;
                onOverlayChange(
                  mergeOverlayChanges(overlay, draft, {
                    backend_scope: filterDraft.backend_scope,
                    published_after_year: filterDraft.published_after_year.trim(),
                    published_before_year: filterDraft.published_before_year.trim(),
                    geography: filterDraft.geography.trim(),
                  }),
                );
                setEditingFilters(false);
              }}
              view={
                <dl className="space-y-3">
                  <div>
                    <dt className={panelHintClass}>Sources</dt>
                    <dd className={panelValueClass}>
                      {vocabLabel(SOURCES_LABEL, sources) ?? (
                        <span className="text-[#97a8bc] italic">{COPY.notDecided}</span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className={panelHintClass}>Publication years</dt>
                    <dd className={`${panelValueClass} text-[#e8edf2]`}>
                      {yearAfter === "" && yearBefore === ""
                        ? "No preference"
                        : yearAfter !== "" && yearBefore !== ""
                          ? `${yearAfter}–${yearBefore}`
                          : yearAfter !== ""
                            ? `From ${yearAfter}`
                            : `Until ${yearBefore}`}
                    </dd>
                  </div>
                  <div>
                    <dt className={panelHintClass}>Source geography</dt>
                    <dd className={`${panelValueClass} text-[#e8edf2]`}>
                      {geography !== "" ? scrub(geography) : "None selected"}
                    </dd>
                  </div>
                </dl>
              }
            >
              <div className="space-y-3">
                <PlanPicker
                  id="plan-sources"
                  label="Sources"
                  value={filterDraft.backend_scope}
                  options={SOURCES_LABEL}
                  onChange={(value) => setFilterDraft((current) => ({ ...current, backend_scope: value }))}
                />
                <label className="block">
                  <span className={`mb-1 block ${panelHintClass}`}>Published from (year)</span>
                  <input
                    type="number"
                    min={1900}
                    max={2100}
                    placeholder="Any"
                    value={filterDraft.published_after_year}
                    onChange={(event) =>
                      setFilterDraft((current) => ({ ...current, published_after_year: event.target.value }))
                    }
                    className={panelFieldClass}
                  />
                </label>
                <label className="block">
                  <span className={`mb-1 block ${panelHintClass}`}>Published until (year)</span>
                  <input
                    type="number"
                    min={1900}
                    max={2100}
                    placeholder="Any"
                    value={filterDraft.published_before_year}
                    onChange={(event) =>
                      setFilterDraft((current) => ({ ...current, published_before_year: event.target.value }))
                    }
                    className={panelFieldClass}
                  />
                </label>
                <label className="block">
                  <span className={`mb-1 block ${panelHintClass}`}>Source geography</span>
                  <input
                    type="text"
                    placeholder="For example, UK"
                    value={filterDraft.geography}
                    onChange={(event) =>
                      setFilterDraft((current) => ({ ...current, geography: event.target.value }))
                    }
                    className={panelFieldClass}
                  />
                </label>
              </div>
            </PanelSection>

            <PanelSection
              readOnly={readOnly}
              label="Screening rules"
              editing={editingScreening}
              onEdit={beginScreeningEdit}
              onCancel={() => {
                setEditingScreening(false);
                setScreeningError(null);
              }}
              onSave={() => {
                if (draft === undefined) return;
                const trimmed = screeningDraft
                  .map((rule) => rule.trim())
                  .filter((rule) => rule.length > 0);
                const error = screeningOverlayError(trimmed, displayedQuestion(draft, overlay));
                if (error != null) {
                  setScreeningError(error);
                  return;
                }
                setScreeningError(null);
                onOverlayChange(mergeOverlayChanges(overlay, draft, { screening_criteria: trimmed }));
                setEditingScreening(false);
              }}
              view={
                screening.length > 0 ? (
                  <ul className="list-disc space-y-1.5 pl-5 text-lead text-[#e8edf2]">
                    {screening.map((criterion) => (
                      <li key={criterion}>{scrub(criterion)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-lead text-[#97a8bc] italic">{COPY.notDecided}</p>
                )
              }
            >
              <div className="space-y-2">
                {screeningDraft.map((rule, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={rule}
                      onChange={(event) => updateScreeningRule(index, event.target.value)}
                      placeholder="Screening rule"
                      className={panelFieldClass}
                    />
                    <button
                      type="button"
                      aria-label={`Remove rule ${index + 1}`}
                      onClick={() => removeScreeningRule(index)}
                      className={panelEditButtonClass}
                    >
                      −
                    </button>
                  </div>
                ))}
                <button type="button" onClick={addScreeningRule} className={panelEditButtonClass}>
                  + Add rule
                </button>
                {screeningError != null && (
                  <p role="alert" className="text-body text-red-tint">
                    {screeningError}
                  </p>
                )}
              </div>
            </PanelSection>

            {agreedSteps.length > 0 && (
              <section className="border-b border-white/15 pb-6 last:border-b-0">
                <h3 className={panelLabelClass}>Plan steps</h3>
                <ol className="mt-3 list-none space-y-2 pl-1 text-lead text-[#e8edf2]">
                  {agreedSteps.map((step, index) => (
                    <li key={step.stage} className="flex gap-1.5">
                      <span aria-hidden="true" className="w-4 shrink-0 tabular-nums">
                        {index + 1}.
                      </span>
                      <div className="min-w-0 flex-1">
                        {step.label}
                        <span className={`block ${panelHintClass}`}>{step.blurb}</span>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </div>
          )}

          {!isScoping && !readOnly && (
          <div className="pt-8">
            <Button className={cn(START_SEARCH_CLASS)} disabled={startDisabled} onClick={start}>
              {startLabel}
            </Button>
            {startNotice != null && (
              <div className="mt-2 space-y-2">
                <p role="alert" className="text-body text-red-tint">
                  {startNotice}
                </p>
                {hasLocalEdits && (
                  <button
                    type="button"
                    className={panelEditButtonClass}
                    onClick={discardAndStart}
                  >
                    Discard edits and start
                  </button>
                )}
              </div>
            )}
          </div>
          )}
        </div>
      </div>
    </aside>
  );
}
