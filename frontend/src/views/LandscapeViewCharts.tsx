import {
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Link, useNavigate } from "react-router";

import { scrub } from "../lib/scrub";
import { cn } from "../ui/brand/cn";
import { fillYearRange, humaniseLabel, normaliseGeographies } from "../ui/charts/EvidenceDistributionChart";
import "./landscape.css";
import { PANE_LABEL_CLASS } from "../ui/brand/label";
import { evidenceTypeLabel, FULL_TEXT } from "../ui/brand/evidence";

/* ---------------------------------------------------------------------------
 * Landscape charts (task 058, landscape polish; lead rulings 2026-11-05).
 *
 * The funnel, evidence types, geographies and finding groups are ranked bars
 * drawn as a real HTML table (`RankedBars`): labels wrap instead of clipping
 * on a phone, every value is in a cell (no hover needed), and a screen reader
 * hears a named table. The publication years are upright columns drawn in
 * HTML (`PublicationYears`), a listbox where a year or a range is chosen,
 * with a visually hidden table beside them.
 * ------------------------------------------------------------------------- */

/** One row of a ranked-bar table. */
export type RankedRow = {
  key: string;
  label: string;
  /** The row's value; `null` while the stage that fills it has not landed it. */
  count: number | null;
  /** Grey for missing data and folded tails ("Not reported", "Unknown"…). */
  tone?: "navy" | "grey";
  /** A placeholder bar breathes in the bar cell (a running stage will fill it). */
  pending?: boolean;
  /** The label in Grey: a stage still to come. */
  muted?: boolean;
  /** Where the row leads: All sources (or Findings) filtered to its value.
   *  Absent on rows that lead nowhere (folded tails, "Not reported", a
   *  funnel stage the table cannot filter to), which then take no hover
   *  either (owner, consistency pass; the funnel links since round 11). */
  href?: string;
};

/** Placeholder lengths (percent of the bar track), cycling down the rows. */
const PLACEHOLDER_WIDTHS = [64, 47, 31] as const;

/**
 * The rows whose value has replaced a breathing placeholder since the table
 * first showed (the animation sweep's entry 7). Derived state: when the set
 * of pending rows changes, a row that was pending and now has its value is
 * added to the landed set, so its value fades in once, at the render that
 * brings it. A value already there at first paint holds still.
 */
function useLandedRows(rows: RankedRow[]): ReadonlySet<string> {
  const pendingKey = rows
    .filter((row) => row.pending)
    .map((row) => row.key)
    .join("\u0000");
  const [tracked, setTracked] = useState<{ pending: string; landed: ReadonlySet<string> }>(() => ({
    pending: pendingKey,
    landed: new Set(),
  }));
  if (tracked.pending !== pendingKey) {
    const before = new Set(tracked.pending.split("\u0000"));
    const landed = new Set(tracked.landed);
    for (const row of rows) if (before.has(row.key) && row.count !== null) landed.add(row.key);
    setTracked({ pending: pendingKey, landed });
  }
  return tracked.landed;
}

/**
 * A ranked-bar table: label | bar with its value at the bar's end.
 *
 * A value that replaces its breathing placeholder fades in over 300 ms,
 * opacity only, on the strong ease-out (`anim-swap-in`; a cut under reduced
 * motion). Nothing else moves: no bar grows, no row shifts.
 *
 * Args:
 *   caption: The table's accessible name (the section heading's words).
 *   rows: The rows in display order; the longest bar is the largest value.
 *   busy: True while a stage is still filling the rows (`aria-busy`).
 */
export function RankedBars({ caption, rows, busy = false }: { caption: string; rows: RankedRow[]; busy?: boolean }) {
  const max = Math.max(1, ...rows.map((row) => row.count ?? 0));
  const landed = useLandedRows(rows);
  return (
    <div className="ranked-bars">
      {/* Explicit roles: the grid display on these elements must not strip
          the table semantics in any engine. */}
      <table role="table" className="ranked-bars__table" aria-busy={busy || undefined}>
        <caption className="sr-only">{caption}</caption>
        <tbody role="rowgroup" className="ranked-bars__body">
          {rows.map((row, index) => (
            <tr
              key={row.key}
              role="row"
              className="ranked-bars__row"
              data-tone={row.tone ?? "navy"}
              data-muted={row.muted ? "" : undefined}
              data-link={row.href !== undefined ? "" : undefined}
            >
              <th role="rowheader" scope="row" className="ranked-bars__label">
                {row.href !== undefined ? (
                  // The link stretches over the whole row (ranked-bars__link),
                  // so the bar is a pointer target too.
                  <Link to={row.href} className="ranked-bars__link">
                    {row.label}
                  </Link>
                ) : (
                  row.label
                )}
              </th>
              <td role="cell" className="ranked-bars__cell">
                {row.count !== null ? (
                  <>
                    {row.count > 0 && (
                      <span
                        aria-hidden="true"
                        data-testid="ranked-bar"
                        className={cn("ranked-bars__bar", landed.has(row.key) && "anim-swap-in")}
                        style={{ "--share": row.count / max } as CSSProperties}
                      />
                    )}
                    <span className={cn("ranked-bars__value", landed.has(row.key) && "anim-swap-in")}>
                      {row.count}
                    </span>
                  </>
                ) : row.pending ? (
                  <span
                    aria-hidden="true"
                    className="placeholder-bar ranked-bars__placeholder"
                    style={{ width: `${PLACEHOLDER_WIDTHS[index % PLACEHOLDER_WIDTHS.length]}%` }}
                  />
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* The funnel                                                                 */
/* ------------------------------------------------------------------------- */

/** The funnel's source stages in the run's own order (it fetches the full
 *  texts, then shortlists: owner, landscape polish), each with the run
 *  stages that fill it. "Full text" counts the sources whose full text was
 *  obtained; the word "read" is kept for steps where a model reads (owner). Every row counts sources, so the bars only shrink (Findings, a count
 *  of findings, left the funnel: lead ruling, landscape polish). */
const FUNNEL_STAGES = [
  { key: "found", label: "Found", stages: ["acquire"] },
  { key: "relevant", label: "Relevant", stages: ["screen"] },
  { key: "quality_checked", label: "Quality-checked", stages: ["classify", "appraise"] },
  { key: "read_in_full", label: FULL_TEXT, stages: ["ingest"] },
  { key: "selected", label: "Shortlisted", stages: ["select"] },
  { key: "cited", label: "Cited", stages: ["synthesise"] },
] as const;

type FunnelCounts = Partial<Record<(typeof FUNNEL_STAGES)[number]["key"], number | null>>;

/**
 * The funnel's rows. Outside a live run a stage with no count is left out.
 * While a run is live all six stages stand from the start: a stage still to
 * come is its label in Grey with an empty bar cell, the stage running now
 * breathes a placeholder bar, and a stage with its count shows its bar.
 *
 * Args:
 *   funnel: The funnel read model (any field may be missing).
 *   runLive: True while the task's run is running or paused.
 *   live: The run stages in progress now (`liveStages`).
 */
export function funnelRows(
  funnel: FunnelCounts | undefined,
  runLive: boolean,
  live: ReadonlySet<string>,
): RankedRow[] {
  return FUNNEL_STAGES.flatMap(({ key, label, stages }): RankedRow[] => {
    const count = funnel?.[key];
    if (typeof count === "number") return [{ key, label, count }];
    if (!runLive) return [];
    const pending = (stages as ReadonlyArray<string>).some((stage) => live.has(stage));
    return [{ key, label, count: null, pending, muted: !pending }];
  });
}

/* ------------------------------------------------------------------------- */
/* Evidence types                                                             */
/* ------------------------------------------------------------------------- */

/** The classifier's own vocabulary order (`EVIDENCE_TYPES` in
 *  `core/schema.py`): strongest designs first, so the page reads the
 *  strength of the evidence base top-down. */
export const EVIDENCE_TYPE_ORDER = [
  "Systematic Review and Meta-Analysis",
  "RCTs and Quasi-Experimental Studies",
  "Observational Research Studies",
  "Modelling & Simulation",
  "Policy Syntheses & Guidance Documents",
  "Qualitative & Contextual Evidence",
  "Expert Opinion and Commentary",
] as const;

/** Missing or non-evidence buckets: pinned last, in Grey. */
const EVIDENCE_TYPE_PINNED = ["Other (Non-evidence documents)", "Unknown / Insufficient information"] as const;

function cleanKeys(data: Record<string, number>): Map<string, number> {
  const clean = new Map<string, number>();
  for (const [raw, count] of Object.entries(data)) {
    const label = scrub(raw).trim();
    clean.set(label, (clean.get(label) ?? 0) + count);
  }
  return clean;
}

function byCountThenLabel(a: [string, number], b: [string, number]): number {
  return b[1] - a[1] || a[0].localeCompare(b[0]);
}

/**
 * The evidence-type rows in a fixed order, so rows never swap while the
 * classifier fills them, each label in sentence case (round 10; the key keeps
 * the classifier's value for the link). The seven substantive types always stand (a zero
 * reads "0", no bar); a label outside the vocabulary follows them, largest
 * first; Other and Unknown come last in Grey, only when non-zero. While
 * Classifying runs every row stands and a row without a value breathes a
 * placeholder in its bar cell; a value replaces it in place.
 *
 * Args:
 *   data: Counts by evidence-type label.
 *   classifying: True while the Classifying stage runs.
 */
export function evidenceTypeRows(data: Record<string, number>, classifying: boolean): RankedRow[] {
  const counts = cleanKeys(data);
  const known = new Set<string>([...EVIDENCE_TYPE_ORDER, ...EVIDENCE_TYPE_PINNED]);
  const valueOf = (label: string): number | null => counts.get(label) ?? (classifying ? null : 0);
  const substantive: RankedRow[] = EVIDENCE_TYPE_ORDER.map((label) => {
    const count = valueOf(label);
    return { key: label, label: evidenceTypeLabel(label), count, pending: count === null };
  });
  const others: RankedRow[] = [...counts]
    .filter(([label]) => !known.has(label))
    .sort(byCountThenLabel)
    .map(([label, count]) => ({ key: label, label: evidenceTypeLabel(humaniseLabel(label)), count }));
  const pinned: RankedRow[] = EVIDENCE_TYPE_PINNED.flatMap((label) => {
    const count = valueOf(label);
    if (!classifying && !count) return [];
    return [{ key: label, label: evidenceTypeLabel(label), count, tone: "grey" as const, pending: count === null }];
  });
  return [...substantive, ...others, ...pinned];
}

/* ------------------------------------------------------------------------- */
/* Geographies                                                                */
/* ------------------------------------------------------------------------- */

const NOT_REPORTED = "Not reported";
/** At most this many rows; past it the smallest countries fold into one. */
export const MAX_GEOGRAPHY_ROWS = 12;

/**
 * Publisher-country rows: largest first, "Not reported" pinned last in Grey
 * whatever its count, and past twelve rows the tail folds into one Grey row,
 * "Other countries (N)", so the bars still add up to the sources drawn.
 *
 * Args:
 *   data: Counts by publisher-country label (ISO codes and names mixed).
 */
export function geographyRows(data: Record<string, number>): RankedRow[] {
  const counts = normaliseGeographies(data);
  const notReported = counts[NOT_REPORTED];
  const countries = Object.entries(counts)
    .filter(([label]) => label !== NOT_REPORTED)
    .sort(byCountThenLabel);
  const budget = MAX_GEOGRAPHY_ROWS - (notReported !== undefined ? 1 : 0);
  const shown = countries.length > budget ? countries.slice(0, budget - 1) : countries;
  const folded = countries.slice(shown.length);
  const rows: RankedRow[] = shown.map(([label, count]) => ({ key: label, label, count }));
  if (folded.length > 0) {
    rows.push({
      key: "other-countries",
      label: `Other countries (${folded.length})`,
      count: folded.reduce((sum, [, count]) => sum + count, 0),
      tone: "grey",
    });
  }
  if (notReported !== undefined) {
    rows.push({ key: NOT_REPORTED, label: NOT_REPORTED, count: notReported, tone: "grey" });
  }
  return rows;
}

/** True when no publisher country was reported at all (only the residual). */
export function onlyNotReported(data: Record<string, number>): boolean {
  const labels = Object.keys(normaliseGeographies(data));
  return labels.length > 0 && labels.every((label) => label === NOT_REPORTED);
}

/* ------------------------------------------------------------------------- */
/* Finding groups                                                             */
/* ------------------------------------------------------------------------- */

/** One facet's groups as rows: largest first, "Ungrouped" pinned last in Grey. */
export function facetRows(groups: ReadonlyArray<{ label: string; size: number }>, ungrouped: number): RankedRow[] {
  const rows: RankedRow[] = [...groups]
    .map((group): [string, number] => [scrub(group.label), group.size])
    .sort(byCountThenLabel)
    .map(([label, count]) => ({ key: label, label, count }));
  if (ungrouped > 0) rows.push({ key: "ungrouped", label: "Ungrouped", count: ungrouped, tone: "grey" });
  return rows;
}

/* ------------------------------------------------------------------------- */
/* Small counts: a sentence in place of a one-bar chart                      */
/* ------------------------------------------------------------------------- */

const plural = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

/** "1 source: Systematic Review and Meta-Analysis." when one type is all
 *  there is (the evidence-type rows hold a single non-zero value). */
export function singleTypeSentence(rows: RankedRow[]): string | null {
  const nonZero = rows.filter((row) => (row.count ?? 0) > 0);
  if (nonZero.length !== 1 || rows.some((row) => row.count === null)) return null;
  return `${plural(nonZero[0].count ?? 0, "source")}: ${nonZero[0].label}.`;
}

/** "All from 2024." or "From 2023 and 2024." when two or fewer years hold
 *  any source; `null` when the years deserve a chart. */
export function fewYearsSentence(data: Record<string, number>): string | null {
  const years = fillYearRange(data)
    .filter((row) => row.count > 0)
    .map((row) => row.label);
  if (years.length === 1) return `All from ${years[0]}.`;
  if (years.length === 2) return `From ${years[0]} and ${years[1]}.`;
  return null;
}

/* ------------------------------------------------------------------------- */
/* Publication years                                                          */
/* ------------------------------------------------------------------------- */

/** Below this plot width (30rem) the chart uses its compact size and ticks. */
const NARROW_PX = 480;

/**
 * The year labels: every year for a short span (12 years, or 6 when narrow),
 * otherwise the multiples of 5 (of 10 past 30 years), plus the first year
 * when it stands far enough from the next label not to collide. Explicit, so
 * the step never looks broken.
 *
 * Args:
 *   years: The filled year range, ascending.
 *   narrow: True when the plot is under 30rem wide.
 */
export function yearTicks(years: number[], narrow: boolean): number[] {
  if (years.length === 0) return [];
  const first = years[0];
  const span = years[years.length - 1] - first + 1;
  if (span <= (narrow ? 6 : 12)) return years;
  const step = span > 30 ? 10 : 5;
  const steps = years.filter((year) => year % step === 0);
  const minGap = narrow ? 3 : 2;
  if (steps.length > 0 && steps[0] !== first && steps[0] - first >= minGap) return [first, ...steps];
  return steps;
}

/** The years chart's value axis: at most four steps of a round size
 *  (1, 2, 5, 10, 20, 25, 50…), the top a whole step at or above `max`. */
export function yearAxis(max: number): number[] {
  const steps = [1, 2, 5];
  for (let scale = 1; ; scale *= 10) {
    for (const base of [...steps, 2.5].sort((a, b) => a - b)) {
      const step = base * scale;
      if (!Number.isInteger(step)) continue;
      const top = Math.max(step, Math.ceil(max / step) * step);
      if (top / step <= 4) return Array.from({ length: top / step + 1 }, (_, index) => index * step);
    }
  }
}

/** The years a selection covers, first to last. */
type Span = { from: number; to: number };

const spanOf = (a: number, b: number): Span => ({ from: Math.min(a, b), to: Math.max(a, b) });

/**
 * Publication years as upright columns in Navy, every year of the range
 * shown even at zero, with explicit year labels (task 058, landscape
 * polish). A column with sources leads to All sources for that year, and a
 * range of years can be chosen at once (owner, round 10):
 *
 * - Pointer: press and drag across the columns. The covered columns turn
 *   Electric Blue as the pointer moves and a small Meta label above them
 *   reads "2015 to 2020"; release opens All sources filtered to the range
 *   (`?year_from=&year_to=`). A press and release on one column opens that
 *   year. Touch drags the same way (the chart lets vertical scrolling
 *   through), and the label sits in its own band above the columns, clear
 *   of the finger.
 * - Keyboard: the chart is a horizontal listbox. The arrow keys, Home and
 *   End move between the years; with Shift they extend the range from where
 *   it started; Enter opens it (one year when no range is held); Escape
 *   drops the range.
 * - Hover (fine pointers): the column under the pointer turns Electric
 *   Blue and the band reads its count and year.
 *
 * Colour is the whole state, so reduced motion changes nothing; nothing
 * animates. A visually hidden table beside the chart carries one row per
 * year for assistive technology.
 *
 * Args:
 *   data: Counts by year label.
 *   caption: The section heading's words (the chart's and table's names).
 *   rangeHref: Where a range of years leads; the chart chooses nothing
 *     when absent.
 */
export function PublicationYears({
  data,
  caption,
  rangeHref,
}: {
  data: Record<string, number>;
  caption: string;
  rangeHref?: (from: string, to: string) => string;
}) {
  const rows = fillYearRange(data);
  const navigate = useNavigate();
  const listId = useId();
  const root = useRef<HTMLDivElement>(null);
  const plot = useRef<HTMLDivElement>(null);
  const [narrow, setNarrow] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ anchor: number; end: number } | null>(null);
  const [active, setActive] = useState(0);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [keyboard, setKeyboard] = useState(false);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    const element = root.current;
    if (element === null || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < NARROW_PX));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  if (rows.length === 0) return null;
  const last = rows.length - 1;
  const axis = yearAxis(Math.max(1, ...rows.map((row) => row.count)));
  const top = axis[axis.length - 1];
  const ticks = new Set(yearTicks(rows.map((row) => Number(row.label)), narrow).map(String));
  const choosing = rangeHref !== undefined;

  const selection: Span | null =
    drag !== null ? spanOf(drag.anchor, drag.end) : focused && keyboard && anchor !== null ? spanOf(anchor, active) : null;
  const ranged = selection !== null && selection.from !== selection.to;
  const sum = (span: Span) => rows.slice(span.from, span.to + 1).reduce((total, row) => total + row.count, 0);
  const words = (span: Span) =>
    span.from === span.to ? rows[span.from].label : `${rows[span.from].label} to ${rows[span.to].label}`;

  /** Open All sources for the span, when it holds any source. */
  const open = (span: Span) => {
    if (rangeHref === undefined || sum(span) === 0) return;
    void navigate(rangeHref(rows[span.from].label, rows[span.to].label));
  };

  const indexAt = (clientX: number) => {
    const box = plot.current?.getBoundingClientRect();
    if (box === undefined || box.width === 0) return 0;
    return Math.min(last, Math.max(0, Math.floor(((clientX - box.left) / box.width) * rows.length)));
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    setKeyboard(false);
    if (!choosing || event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const index = indexAt(event.clientX);
    setActive(index);
    setAnchor(null);
    setDrag({ anchor: index, end: index });
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const index = indexAt(event.clientX);
    if (drag !== null) {
      if (index !== drag.end) setDrag({ ...drag, end: index });
    } else if (event.pointerType === "mouse") {
      setHover(index);
    }
  };
  const onPointerUp = () => {
    if (drag === null) return;
    setDrag(null);
    open(spanOf(drag.anchor, drag.end));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowRight: Math.min(last, active + 1),
      ArrowLeft: Math.max(0, active - 1),
      Home: 0,
      End: last,
    };
    setKeyboard(true);
    if (event.key in moves) {
      event.preventDefault();
      if (event.shiftKey) setAnchor(anchor ?? active);
      else setAnchor(null);
      setActive(moves[event.key]);
    } else if (event.key === "Enter") {
      event.preventDefault();
      open(anchor !== null ? spanOf(anchor, active) : { from: active, to: active });
    } else if (event.key === "Escape" && anchor !== null) {
      event.preventDefault();
      setAnchor(null);
    }
  };

  const hovered = drag === null && !ranged && hover !== null ? rows[hover] : null;
  // Centred over the span, held inside the chart at either end.
  const centre = (span: Span) =>
    `clamp(3.75rem, ${(((span.from + span.to + 1) / 2) / rows.length) * 100}%, calc(100% - 3.75rem))`;
  const blue = (index: number) =>
    selection !== null ? index >= selection.from && index <= selection.to : hover === index && drag === null;

  return (
    <div ref={root} className="years-chart min-w-0">
      <div
        className={cn("years-chart__frame", narrow && "years-chart__frame--narrow")}
        data-testid="years-chart"
      >
        {/* The band above the columns: the range in words while one is held,
            else the hovered column's count and year. */}
        <div className="years-chart__band" aria-hidden="true">
          {ranged && selection !== null ? (
            <span className="years-chart__label" data-testid="years-range-label" style={{ left: centre(selection) }}>
              {words(selection)}
            </span>
          ) : hovered !== null && hover !== null ? (
            <span className="years-chart__label years-chart__label--hover" style={{ left: centre({ from: hover, to: hover }) }}>
              <span className="font-semibold text-navy">{plural(hovered.count, "source")}</span> {hovered.label}
            </span>
          ) : null}
        </div>
        <div className="years-chart__body">
          <div className="years-chart__axis" aria-hidden="true">
            {axis.map((value) => (
              <span key={value} style={{ bottom: `${(value / top) * 100}%` }}>
                {value}
              </span>
            ))}
          </div>
          <div className="years-chart__plot">
            {axis.map((value) => (
              <span key={value} aria-hidden="true" className="years-chart__grid" style={{ bottom: `${(value / top) * 100}%` }} />
            ))}
            <div
              ref={plot}
              role={choosing ? "listbox" : undefined}
              aria-hidden={choosing ? undefined : true}
              aria-orientation={choosing ? "horizontal" : undefined}
              aria-multiselectable={choosing || undefined}
              aria-label={caption}
              aria-activedescendant={choosing && focused ? `${listId}-${active}` : undefined}
              tabIndex={choosing ? 0 : undefined}
              className="years-chart__columns"
              data-choosing={choosing ? "" : undefined}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={() => setDrag(null)}
              onPointerLeave={() => setHover(null)}
              onKeyDown={choosing ? onKeyDown : undefined}
              onFocus={() => setFocused(true)}
              onBlur={() => {
                setFocused(false);
                setAnchor(null);
              }}
            >
              {rows.map((row, index) => (
                <div
                  key={row.label}
                  id={`${listId}-${index}`}
                  role={choosing ? "option" : undefined}
                  aria-selected={choosing ? selection !== null && index >= selection.from && index <= selection.to : undefined}
                  aria-label={choosing ? `${row.label}: ${plural(row.count, "source")}` : undefined}
                  className="years-chart__column"
                  data-blue={blue(index) ? "" : undefined}
                  data-active={choosing && focused && keyboard && index === active ? "" : undefined}
                >
                  {row.count > 0 && (
                    <span className="years-chart__bar" data-testid="year-bar" style={{ height: `${(row.count / top) * 100}%` }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="years-chart__years" aria-hidden="true">
          {rows.map((row) => (
            <span key={row.label}>{ticks.has(row.label) ? <span>{row.label}</span> : null}</span>
          ))}
        </div>
      </div>
      {/* A held range, said once as it changes, for a screen reader. */}
      <span className="sr-only" aria-live="polite">
        {focused && anchor !== null && selection !== null && ranged ? words(selection) : ""}
      </span>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Year</th>
            <th scope="col">Sources</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td>{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


/* ------------------------------------------------------------------------- */
/* A section on the panel                                                     */
/* ------------------------------------------------------------------------- */

/**
 * One Landscape section, uncarded on the Sources panel: the pane heading as
 * a real `h2` (Label style), its population figure or its control
 * right-aligned, a Line hairline, then the content.
 */
export function LandscapeSection({
  title,
  figure,
  control,
  children,
}: {
  title: string;
  figure?: string | null;
  /** A control at the heading row's right end (the List / Map switch). */
  control?: ReactNode;
  children: ReactNode;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className="landscape-section min-w-0">
      <div
        className={cn(
          "flex flex-wrap justify-between gap-x-4 gap-y-0.5 border-b border-line pt-3.5",
          control ? "items-center pb-2" : "items-baseline pb-2.5",
        )}
      >
        <h2 id={headingId} className={PANE_LABEL_CLASS}>
          {title}
        </h2>
        {figure ? <p className="text-meta text-grey">{figure}</p> : null}
        {control}
      </div>
      <div className="min-w-0 pt-4">{children}</div>
    </section>
  );
}

/** "112 with a year" and its kin: the population a heading counts. */
export const population = {
  withYear: (n: number) => `${n} with a year`,
  findings: (n: number) => plural(n, "finding"),
  classifiedSoFar: (classified: number, relevant: number) =>
    `Classified so far: ${classified} of ${plural(relevant, "relevant source")}`,
};

