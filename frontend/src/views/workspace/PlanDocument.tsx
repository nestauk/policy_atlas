import { useState } from "react";

import { usePlan } from "../../api/queries";
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
  type PlanOverlay,
} from "./planOverlay";
import { START_SEARCH_CLASS, usePlanStart } from "./planStart";
import {
  ANALYSIS_DEPTH_LABEL,
  ANALYSIS_QUESTION,
  ANALYSIS_TITLE,
  axesForResearchApproach,
  RESEARCH_APPROACH_CUSTOM,
  RESEARCH_APPROACH_HINT,
  RESEARCH_APPROACH_PRESET_LABEL,
  RESEARCH_APPROACH_TITLE,
  researchApproachId,
  researchApproachLabel,
  SEARCH_EFFORT_LABEL,
  SEARCH_SCOPE_HINT,
  SEARCH_SCOPE_TITLE,
  SOURCES_LABEL,
  STEERING_MODE_LABEL,
  stepsForAnalysisDepth,
  timeBandFor,
  vocabLabel,
} from "./planVocabulary";

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
  className,
}: {
  showDock: boolean;
  onDock?: () => void;
  onClose: () => void;
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
      <button type="button" aria-label="Close the search plan" onClick={onClose} className={controlClass}>
        <PlanChromeIcon>
          <path d="M6 6 18 18" />
          <path d="M18 6 6 18" />
        </PlanChromeIcon>
      </button>
    </div>
  );
}

/**
 * The search plan, edited in place. Saves stay local until Start search —
 * a planner round-trip on every field would rewrite the whole plan.
 */
export function PlanDocument({
  projectId,
  placement = "side",
  runActive = false,
  readOnly = false,
  onClose,
  onDock,
  onStarted,
  overlay,
  onOverlayChange,
}: {
  projectId: string;
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
  const planQuery = usePlan(projectId);
  const draft = planQuery.data?.plan;
  const { start, startNotice, disabled: startDisabled, label: startLabel } = usePlanStart({
    projectId,
    overlay,
    runActive,
    onStarted,
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
  const [screeningDraft, setScreeningDraft] = useState("");

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
    setScreeningDraft(displayedScreening(draft, overlay).join("\n"));
    setEditingScreening(true);
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
      aria-label="Search plan"
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
              className="pointer-events-auto absolute top-0 right-0 translate-x-[calc(100%+0.5rem)] max-[52rem]:translate-x-0"
            />
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={cn("mx-auto w-full px-5 py-8", READING_COLUMN_MAX_W)}>
          <div className="mb-6 flex items-start justify-between gap-3 border-b border-white/15 pb-6">
            <header className="min-w-0 flex-1">
              <h2 className="text-heading font-extrabold text-white">Search plan</h2>
              {expectedRunTime != null && expectedRunTime !== "" && (
                <p className="mt-1 text-body text-[#97a8bc]">
                  Expected run time: {scrub(expectedRunTime)}
                </p>
              )}
            </header>
            {placement === "side" && (
              <PlanChrome showDock={false} onClose={onClose} className="shrink-0" />
            )}
          </div>

          {planQuery.isPending && <p className="text-body text-[#c5d0dc]">Loading the plan…</p>}
          {planQuery.isError && (
            <p role="alert" className="text-body text-red-tint">
              The plan couldn't be loaded.
            </p>
          )}

          {draft !== undefined && (
            <div className="space-y-6">
            <PanelSection
              readOnly={readOnly}
              label="Research question"
              editing={editingQuestion}
              onEdit={beginQuestionEdit}
              onCancel={() => setEditingQuestion(false)}
              onSave={() => {
                onOverlayChange({ ...overlay, question: questionDraft });
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
                onOverlayChange({
                  ...overlay,
                  search_effort: settingsDraft.search_effort,
                  analysis_depth: settingsDraft.analysis_depth,
                  steering_mode: settingsDraft.steering_mode,
                });
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
                onOverlayChange({
                  ...overlay,
                  backend_scope: filterDraft.backend_scope,
                  published_after_year: filterDraft.published_after_year.trim(),
                  published_before_year: filterDraft.published_before_year.trim(),
                  geography: filterDraft.geography.trim(),
                });
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
              onCancel={() => setEditingScreening(false)}
              onSave={() => {
                onOverlayChange({
                  ...overlay,
                  screening_criteria: screeningDraft
                    .split("\n")
                    .map((line) => line.trim())
                    .filter((line) => line.length > 0),
                });
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
              <textarea
                rows={6}
                value={screeningDraft}
                onChange={(event) => setScreeningDraft(event.target.value)}
                placeholder="One screening rule per line"
                className={cn(panelFieldClass, "resize-y")}
              />
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

          {!readOnly && (
          <div className="pt-8">
            <Button className={cn(START_SEARCH_CLASS)} disabled={startDisabled} onClick={start}>
              {startLabel}
            </Button>
            {startNotice != null && (
              <p role="alert" className="mt-2 text-body text-red-tint">
                {startNotice}
              </p>
            )}
          </div>
          )}
        </div>
      </div>
    </aside>
  );
}
