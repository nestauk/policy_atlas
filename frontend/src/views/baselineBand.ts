import { usePlan, useRuns } from "../api/queries";
import { SCOPING_CONFIRMED_LINE, scopingWalkStatus } from "./workspace/planStart";

/**
 * The Result band for an options-scoping baseline (task 044, deliverable 9;
 * A17, C18).
 *
 * The band says three things and nothing else: what this artefact is, what it
 * is for, and where the run has got to. The state is words, never a colour,
 * and it is read off the same walk-status rule the plan document's start area
 * uses (`scopingWalkStatus`) so the two surfaces cannot disagree.
 */

/** The roll-up's template key for a baseline (`counts.template`, written by
 *  synthesise in baseline mode). */
export const BASELINE_TEMPLATE = "baseline";

/** What the baseline is for — the band's middle clause. */
export const BASELINE_PURPOSE = "the situation these options would change";

/** The artefact is written but the plan is not settled yet. */
export const BASELINE_AWAITING_LINE = "ready · awaiting your confirmation";

/** The two fields these functions read off an artefact — narrower than the
 *  full `ArtefactOut` (the same narrowing `artefactMarkdown` uses) because
 *  `useArtefact`'s response type and the schema type disagree on
 *  `coverage_snapshot.year_range`'s tuple-vs-array shape, for reasons that
 *  have nothing to do with these two fields. */
interface ArtefactTemplateFields {
  template?: string | null;
  depth_label?: string | null;
}

/** Whether this artefact is an options-scoping baseline. Reads the roll-up's
 *  own word — never inferred from the section titles or the task's kind. */
export function isBaselineArtefact(artefact: ArtefactTemplateFields | null | undefined): boolean {
  return artefact?.template === BASELINE_TEMPLATE;
}

/** How deep the pass behind this artefact went, in the roll-up's own words
 *  (`"scoping pass"` for a baseline) — or null when it recorded none. */
export function artefactDepthLabel(artefact: ArtefactTemplateFields | null | undefined): string | null {
  const label = artefact?.depth_label;
  return typeof label === "string" && label !== "" ? label : null;
}

/** The band's rendered pieces: the state words, and the plan-version mark
 *  when the plan has moved on since the walk that wrote the baseline. */
export interface BaselineBand {
  /** `"Baseline"`, the purpose clause and the state, dot-separated. */
  line: string;
  /** `"built from plan version N"`, or null when the baseline is current. */
  planVersionMark: string | null;
}

/**
 * Compose the band from the walk status.
 *
 * Two states, because only two are true of an artefact that exists: either
 * the plan behind it is settled and the longlist is next, or the baseline is
 * sitting there waiting for the reader to confirm. A plan edited since the
 * walk adds the mark — the reader is looking at a baseline built from an
 * older version of the plan, and that is a fact the page must not swallow.
 *
 * Args:
 *   status: The walk status from `scopingWalkStatus`.
 *
 * Returns:
 *   The band's line and its optional plan-version mark.
 */
export function baselineBand(status: ReturnType<typeof scopingWalkStatus>): BaselineBand {
  // Mid-band the confirmed line reads on from the purpose clause, so it drops
  // its standalone capital (the plan document keeps it as a line of its own).
  const state = status.confirmed
    ? SCOPING_CONFIRMED_LINE.charAt(0).toLowerCase() + SCOPING_CONFIRMED_LINE.slice(1)
    : BASELINE_AWAITING_LINE;
  return {
    line: `Baseline · ${BASELINE_PURPOSE} · ${state}`,
    planVersionMark:
      status.newerVersionThanBaselineRun && status.baselineRun !== null
        ? `built from plan version ${status.baselineRun.plan_version}`
        : null,
  };
}

/** The server page-size cap — one page covers every walk a scoping task has
 *  run in this slice (mirrors `useScopingPlanStart`). */
const SCOPING_RUNS_PAGE_SIZE = 200;

/** The band for one scoping task, off the plan and its walks. */
export function useBaselineBand(taskId: string): BaselineBand {
  const planQuery = usePlan(taskId);
  const runsQuery = useRuns(taskId, { page_size: SCOPING_RUNS_PAGE_SIZE });
  return baselineBand(
    scopingWalkStatus({
      runs: runsQuery.data?.data ?? [],
      currentVersion: planQuery.data?.version ?? null,
      baselineConfirmed: planQuery.data?.scoping?.baseline_confirmed ?? null,
    }),
  );
}
