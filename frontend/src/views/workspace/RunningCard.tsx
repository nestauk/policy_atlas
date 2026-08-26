import { useEffect, useState } from "react";
import { Link } from "react-router";

import { scrub } from "../../lib/scrub";
import type { PlanDraft, RunStatus, StageEntry } from "../../store";
import { cn } from "../../ui/brand/cn";
import {
  CHAT_PRIMARY_CTA_CLASS,
  collapsedStatusLine,
  elapsedSeconds,
  formatElapsed,
  resultsSignpost,
  RUNNING_CARD_RULE_CLASS,
  RUNNING_CARD_SHELL_CLASS,
  runningCardCopy,
  SEE_PLAN_CTA_CLASS,
  signpostForStage,
  stageDetailLines,
  stageRows,
  type StageRow,
} from "./runProgress";

function useElapsedSeconds(
  startedAt: string | undefined,
  endedAt: string | undefined,
  ticking: boolean,
): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [ticking]);
  return elapsedSeconds(startedAt, ticking ? undefined : endedAt, now);
}

function StepRow({
  projectId,
  row,
  expanded,
  hasFindings,
  onToggle,
}: {
  projectId: string;
  row: StageRow;
  expanded: boolean;
  hasFindings: boolean;
  onToggle: () => void;
}) {
  const done = row.status === "completed";
  const pending = !done;
  const signpost = done ? signpostForStage(row.stage, projectId, hasFindings) : null;
  const details = expanded && done ? stageDetailLines(row) : [];
  const statusLabel =
    row.status === "completed"
      ? "Done"
      : row.status === "started"
        ? "In progress"
        : row.status === "failed"
          ? "Stopped"
          : row.status === "skipped"
            ? "Skipped"
            : null;
  const labelClass = cn("min-w-0 text-lead", pending ? "text-grey" : "text-navy");
  const statusClass = cn(
    "shrink-0 text-body font-semibold",
    pending ? "text-grey" : "text-navy",
  );

  return (
    <li className={RUNNING_CARD_RULE_CLASS}>
      {done ? (
        <button
          type="button"
          aria-label={row.label}
          aria-expanded={expanded}
          onClick={onToggle}
          className="flex w-full cursor-pointer items-baseline justify-between gap-3 py-2.5 text-left"
        >
          <span className={labelClass}>{scrub(row.label)}</span>
          <span className={statusClass}>{statusLabel}</span>
        </button>
      ) : (
        <div className="flex items-baseline justify-between gap-3 py-2.5">
          <span className={labelClass}>{scrub(row.label)}</span>
          {statusLabel !== null && <span className={statusClass}>{statusLabel}</span>}
        </div>
      )}
      {expanded && done && (
        <div className="space-y-1 pb-3">
          {details.map((line) => (
            <p key={line} className="text-body text-grey">
              {scrub(line)}
            </p>
          ))}
          {signpost !== null && (
            <Link to={signpost.href} className="inline-block text-body font-semibold text-blue underline">
              {signpost.label} →
            </Link>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * In-thread run progress: Option C tinted card with expandable completed steps.
 * Minimise collapses this card in place; a parent may dock a copy when it
 * scrolls out of view.
 */
export function RunningCard({
  projectId,
  status,
  stages,
  plan,
  startedAt,
  endedAt,
  hasFindings,
  minimised,
  onMinimisedChange,
  onSeePlan,
}: {
  projectId: string;
  status: RunStatus | undefined;
  stages: StageEntry[];
  plan: PlanDraft | null | undefined;
  startedAt?: string;
  endedAt?: string;
  hasFindings: boolean;
  minimised: boolean;
  onMinimisedChange: (minimised: boolean) => void;
  onSeePlan?: () => void;
}) {
  const { eyebrow, title, tone } = runningCardCopy(status);
  const rows = stageRows(stages, plan);
  const ticking = status === "running" || status === "paused";
  const elapsed = useElapsedSeconds(startedAt, endedAt, ticking);
  const elapsedLabel = formatElapsed(elapsed);
  const results = resultsSignpost(projectId, status);
  const [expandedStage, setExpandedStage] = useState<string | null>(null);

  if (minimised) {
    return (
      <section aria-label="Analysis run" className={cn(RUNNING_CARD_SHELL_CLASS, "px-4 py-3")}>
        <div className="flex items-center justify-between gap-3">
          <p className="min-w-0 truncate text-lead font-semibold text-navy">
            {collapsedStatusLine(status, rows, elapsedLabel)}
          </p>
          <button
            type="button"
            className="shrink-0 cursor-pointer text-body font-semibold text-blue underline"
            onClick={() => onMinimisedChange(false)}
          >
            Expand
          </button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Analysis run" className={cn(RUNNING_CARD_SHELL_CLASS, "px-4 py-4")}>
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-meta font-bold tracking-label text-navy">
          <span aria-hidden="true" className="inline-block size-2 rounded-full bg-[#17A88D]" />
          {eyebrow}
        </p>
        {tone !== "stopped" && (
          <button
            type="button"
            className="shrink-0 cursor-pointer text-body font-semibold text-blue underline"
            onClick={() => onMinimisedChange(true)}
          >
            Minimise
          </button>
        )}
      </div>
      <h2 className="mt-1 text-lead font-bold text-navy">{title}</h2>
      <p className="mt-0.5 text-body text-grey">Total time {elapsedLabel}</p>

      {rows.length > 0 && (
        <ol aria-label="Stage timeline" className="mt-3">
          {rows.map((row) => (
            <StepRow
              key={row.id}
              projectId={projectId}
              row={row}
              expanded={expandedStage === row.id}
              hasFindings={hasFindings}
              onToggle={() =>
                setExpandedStage((current) => (current === row.id ? null : row.id))
              }
            />
          ))}
        </ol>
      )}

      {results !== null || onSeePlan !== undefined ? (
        <div className={cn("mt-3 flex flex-wrap items-center gap-3 pt-3", RUNNING_CARD_RULE_CLASS)}>
          {results !== null && (
            <Link to={results.href} className={CHAT_PRIMARY_CTA_CLASS}>
              {results.label}
            </Link>
          )}
          {onSeePlan !== undefined && (
            <button type="button" className={SEE_PLAN_CTA_CLASS} onClick={onSeePlan}>
              See plan
            </button>
          )}
        </div>
      ) : null}
    </section>
  );
}

/** Collapsed strip above the composer when the in-thread card is off-screen. */
export function RunningCardDock({
  status,
  stages,
  plan,
  elapsedLabel,
  onOpen,
}: {
  status: RunStatus | undefined;
  stages: StageEntry[];
  plan: PlanDraft | null | undefined;
  elapsedLabel: string;
  onOpen: () => void;
}) {
  const rows = stageRows(stages, plan);
  return (
    <button
      type="button"
      aria-label="Show the analysis run"
      onClick={onOpen}
      className={cn(
        RUNNING_CARD_SHELL_CLASS,
        "flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-2.5 text-left",
      )}
    >
      <span className="min-w-0 truncate text-body font-semibold text-navy">
        {collapsedStatusLine(status, rows, elapsedLabel)}
      </span>
      <span className="shrink-0 text-body text-blue underline">Show</span>
    </button>
  );
}
