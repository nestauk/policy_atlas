import type { BoxLayer, Origin, Support, TocBox, TocDocument, TocFigure, TocGraph, TocLink, TocPathway, Verdict } from "./types";

/*
 * Pure helpers for the theory-of-change Result page (task 054): wording,
 * which pathways are shown, the canvas layout and the Assumptions grouping.
 * No React here, so the layout and the grouping are unit-tested directly.
 */

export const VERDICT_LABEL: Record<Verdict, string> = {
  confident: "Confident",
  leaning_supports: "Leaning supports",
  not_sure_mixed: "Mixed",
  not_sure_insufficient: "Not enough evidence",
  leaning_against: "Leaning against",
  not_confident: "Not confident: evidence against",
};

/** The legend's order: supports to against, then not enough evidence. */
export const VERDICTS: readonly Verdict[] = ["confident", "leaning_supports", "not_sure_mixed", "leaning_against", "not_confident", "not_sure_insufficient"];

/** The CSS variable that colours a verdict's dot and arrowhead (defined once in `index.css`). */
export const VERDICT_VAR: Record<Verdict, string> = {
  confident: "var(--color-verdict-confident)",
  leaning_supports: "var(--color-verdict-confident)",
  leaning_against: "var(--color-verdict-against)",
  not_sure_mixed: "var(--color-verdict-mixed)",
  not_sure_insufficient: "var(--color-verdict-little)",
  not_confident: "var(--color-verdict-against)",
};

/** What makes a connection critical: the rule in the backend's `critical_link` (C6, C36). */
export const CRITICAL_DEFINITION =
  "The weakest step on the routes to the impact: of the connections on the kept pathways, the one with the lowest evidence verdict. When several tie, it is the one the most pathways pass through. Test it first.";

export const SUPPORT_LABEL: Record<Support, string> = {
  strong: "Strongly supports",
  weak: "Weakly supports",
  mixed: "Mixed",
  refutes: "Refutes",
  not_about: "Not about this step",
};

/** The hover text of an edge: its verdict. */
export function linkTip(link: TocLink): string {
  if (link.state === "checking" || link.state === "unchecked") return "Checking the evidence…";
  const critical = link.critical ? "Critical connection. " : "";
  return `${critical}${VERDICT_LABEL[link.verdict]}`;
}

/** The evidence balance's four columns, left to right (C36). */
export const BALANCE: readonly Exclude<Support, "not_about">[] = ["refutes", "mixed", "weak", "strong"];

/** Each column's documents, heaviest first; documents not about the step are left out. */
export function evidenceBalance<T extends Pick<TocDocument, "support" | "weight">>(documents: T[]): { support: Exclude<Support, "not_about">; docs: T[] }[] {
  return BALANCE.map((support) => ({
    support,
    docs: documents.filter((doc) => doc.support === support).sort((a, b) => b.weight - a.weight),
  }));
}

/** Figures that say the same thing, shown as one line (C37). */
export interface FigureGroup {
  key: string;
  figures: TocFigure[];
}

const plain = (text: string | null) => (text ?? "").toLowerCase().replace(/[^a-z0-9%]+/g, " ").trim();

/**
 * Figures grouped by what they measure, their unit and effect type, in the
 * order they first appear. Never averaged or pooled.
 */
export function figureGroups(figures: TocFigure[]): FigureGroup[] {
  // ponytail: exact match on a normalised measure, so two wordings of one measure stay apart; group by meaning (embeddings or a model call) if that splits too often.
  const groups = new Map<string, TocFigure[]>();
  for (const figure of figures) {
    const key = [plain(figure.measure), plain(figure.unit), figure.effect_size_type].join("|");
    groups.set(key, [...(groups.get(key) ?? []), figure]);
  }
  return [...groups].map(([key, items]) => ({ key, figures: items }));
}

/** The value with its unit, never twice: "45%" stays "45%", not "45%%". */
export function withUnit(value: string, unit: string | null): string {
  if (unit === null || unit.trim() === "") return value;
  const u = unit.trim();
  if (value.trim().toLowerCase().endsWith(u.toLowerCase())) return value;
  return u === "%" ? `${value}%` : `${value} ${u}`;
}

/**
 * A group's bold line. Two or more numbers: "Evidence suggests A to B <unit>
 * <measure> (n studies)", from the lowest and highest value. One: "<value>
 * <unit> <measure>", with its range when the document gives one.
 */
export function figureHeadline(group: FigureGroup): string {
  const [first] = group.figures;
  if (first === undefined) return "";
  const values = group.figures.map((figure) => figure.value).filter((value): value is number => value !== null);
  if (values.length >= 2) {
    const [low, high] = [Math.min(...values), Math.max(...values)];
    const span = low === high ? String(low) : `${low} to ${high}`;
    const studies = new Set(group.figures.map((figure) => figure.task_source_snapshot_id)).size;
    return `Evidence suggests ${withUnit(span, first.unit)} ${first.measure} (${studies} ${studies === 1 ? "study" : "studies"})`;
  }
  const range = first.ci_lower_text !== null && first.ci_upper_text !== null ? ` (range ${first.ci_lower_text} to ${first.ci_upper_text})` : "";
  return `${withUnit(first.value_text, first.unit)} ${first.measure}${range}`;
}

export const ORIGIN_LABEL: Record<Origin, string> = {
  drafted: "Drafted by Policy Atlas",
  found_in_evidence: "Found in the evidence",
  imported: "From your theory",
  user: "Added by you",
  options_scoping: "From your options scoping",
};

/** One box's layer, as the detail panel and the report name it. */
export const LAYER_LABEL: Record<BoxLayer, string> = {
  input: "Input or activity",
  output: "Output",
  outcome_short: "Short-term outcome",
  outcome_long: "Long-term outcome",
  impact: "Impact",
  failure_outcome: "Outcome if it goes wrong",
};

/** Kept pathways, success first, then failure (each in the API's order). */
export function keptPathways(graph: Pick<TocGraph, "pathways">): TocPathway[] {
  const kept = graph.pathways.filter((pathway) => pathway.status === "kept");
  return [...kept.filter((p) => p.kind === "success"), ...kept.filter((p) => p.kind === "failure")];
}

/**
 * The link ids shown for a pathway choice ("all" or one pathway id). One
 * pathway shows its own chain plus every input and output that feeds into
 * it: several activities often meet at a shared outcome, and each of them
 * contributes to every route that leaves it.
 */
export function visibleLinkIds(graph: Pick<TocGraph, "pathways" | "links" | "boxes">, choice: string): Set<string> {
  const chosen = keptPathways(graph).filter((p) => choice === "all" || p.pathway_id === choice);
  const shown = new Set(chosen.flatMap((p) => p.link_ids));
  if (choice === "all") return shown;
  const kept = new Set(keptPathways(graph).flatMap((p) => p.link_ids));
  const layerOf = new Map(graph.boxes.map((box) => [box.box_id, box.layer]));
  const feeds = graph.links.filter((link) => kept.has(link.link_id) && ["input", "output"].includes(layerOf.get(link.source_box_id) ?? ""));
  const reached = new Set(graph.links.filter((link) => shown.has(link.link_id)).map((link) => link.target_box_id));
  for (let grew = true; grew; ) {
    grew = false;
    for (const link of feeds) {
      if (!shown.has(link.link_id) && reached.has(link.target_box_id)) {
        shown.add(link.link_id);
        reached.add(link.source_box_id);
        grew = true;
      }
    }
  }
  return shown;
}

export const BOX_W = 200;
export const BOX_H = 76;
export const COL_GAP = 80;
export const ROW_GAP = 28;
export const COL_STEP = BOX_W + COL_GAP;
const ROW_STEP = BOX_H + ROW_GAP;
/** Space kept for the column headings above the first row. */
export const HEADER_H = 48;

export interface PlacedBox {
  id: string;
  column: number;
  /** Row inside its half of the canvas (above or below the line). */
  row: number;
  x: number;
  y: number;
  /** True for a box that sits only on failure pathways (under the line). */
  failure: boolean;
}

export interface ColumnHeading {
  label: string;
  x: number;
}

export interface TocLayout {
  boxes: PlacedBox[];
  /** One heading per layer, over its first column. */
  headings: ColumnHeading[];
  /** The y of the "If it goes wrong" line, or null when nothing sits under it. */
  lineY: number | null;
  /** The x of the accountability ceiling: the dashed line after the outputs (C35). */
  ceilingX: number;
  width: number;
  /** The y just below the lowest box. */
  height: number;
}

/**
 * Where every box of a kept pathway goes. Deterministic, no layout library.
 *
 * Columns follow the layers, left to right. Short-term and long-term outcomes
 * each take as many columns as their longest chain inside the layer: an
 * outcome sits one column after the same-layer outcome that leads to it, so a
 * chain reads left to right and the impact comes after the last long-term
 * outcome. Boxes on a success pathway sit above the line; each takes the
 * average row of the boxes that lead into it (so a chain stays on one row and
 * fewer connections cross), and boxes in a column never share a row. Boxes
 * found only on failure pathways sit under the line, one band of rows per
 * failure pathway; a `failure_outcome` box goes in the column after its source.
 */
export function layoutToc(graph: Pick<TocGraph, "boxes" | "links" | "pathways">): TocLayout {
  const boxById = new Map<string, TocBox>(graph.boxes.map((box) => [box.box_id, box]));
  const linkById = new Map(graph.links.map((link) => [link.link_id, link]));
  const pathways = keptPathways(graph);
  const keptLinks = pathways.flatMap((p) => p.link_ids.map((id) => linkById.get(id))).filter((l): l is TocLink => l !== undefined);
  const layerOf = (id: string) => boxById.get(id)?.layer;

  // Outcome depth: the longest chain of same-layer links leading to an outcome.
  const sameLayerSources = new Map<string, string[]>();
  for (const link of keptLinks) {
    const layer = layerOf(link.source_box_id);
    if ((layer === "outcome_short" || layer === "outcome_long") && layer === layerOf(link.target_box_id)) {
      sameLayerSources.set(link.target_box_id, [...(sameLayerSources.get(link.target_box_id) ?? []), link.source_box_id]);
    }
  }
  const depth = new Map<string, number>();
  const depthOf = (id: string, seen: Set<string>): number => {
    const known = depth.get(id);
    if (known !== undefined) return known;
    if (seen.has(id)) return 0; // a loop: break it here
    seen.add(id);
    const d = Math.max(-1, ...(sameLayerSources.get(id) ?? []).map((source) => depthOf(source, seen))) + 1;
    depth.set(id, d);
    return d;
  };
  const columnsOf = (layer: BoxLayer) =>
    Math.max(1, ...graph.boxes.filter((box) => box.layer === layer).map((box) => depthOf(box.box_id, new Set()) + 1));
  const shortColumns = columnsOf("outcome_short");
  const longColumn = 2 + shortColumns;
  const impactColumn = longColumn + columnsOf("outcome_long");

  const column = new Map<string, number>();
  const onSuccess = new Set<string>();
  /** First failure pathway (its rank among failure pathways) that holds a box. */
  const failRank = new Map<string, number>();
  const order: string[] = [];
  let failIndex = -1;
  for (const pathway of pathways) {
    if (pathway.kind === "failure") failIndex += 1;
    for (const linkId of pathway.link_ids) {
      const link = linkById.get(linkId);
      if (link === undefined) continue;
      for (const id of [link.source_box_id, link.target_box_id]) {
        const box = boxById.get(id);
        if (box === undefined) continue;
        if (!column.has(id)) {
          order.push(id);
          const sourceColumn = column.get(link.source_box_id);
          const byLayer = {
            input: 0,
            output: 1,
            outcome_short: 2 + (depth.get(id) ?? 0),
            outcome_long: longColumn + (depth.get(id) ?? 0),
            impact: impactColumn,
            failure_outcome: 2,
          }[box.layer];
          column.set(
            id,
            box.layer === "failure_outcome" && id === link.target_box_id && sourceColumn !== undefined
              ? Math.min(sourceColumn + 1, impactColumn)
              : byLayer,
          );
        }
        if (pathway.kind === "success") onSuccess.add(id);
        else if (!failRank.has(id)) failRank.set(id, failIndex);
      }
    }
  }

  // Success rows, column by column: the average row of each box's sources.
  const sourcesOf = new Map<string, string[]>();
  for (const link of keptLinks) sourcesOf.set(link.target_box_id, [...(sourcesOf.get(link.target_box_id) ?? []), link.source_box_id]);
  const rowOf = new Map<string, number>();
  const placed: PlacedBox[] = [];
  const firstSeen = new Map(order.map((id, index) => [id, index]));
  let successRowCount = 0;
  for (let col = 0; col <= impactColumn; col += 1) {
    const ids = order.filter((id) => onSuccess.has(id) && column.get(id) === col);
    const wanted = new Map<string, number>();
    for (const id of ids) {
      const rows = (sourcesOf.get(id) ?? []).map((source) => rowOf.get(source)).filter((r): r is number => r !== undefined);
      wanted.set(id, rows.length > 0 ? rows.reduce((a, b) => a + b, 0) / rows.length : Number.POSITIVE_INFINITY);
    }
    ids.sort((a, b) => (wanted.get(a) ?? 0) - (wanted.get(b) ?? 0) || (firstSeen.get(a) ?? 0) - (firstSeen.get(b) ?? 0));
    let next = 0;
    for (const id of ids) {
      const target = wanted.get(id) ?? Number.POSITIVE_INFINITY;
      const row = Number.isFinite(target) ? Math.max(next, Math.round(target)) : next;
      next = row + 1;
      rowOf.set(id, row);
      placed.push({ id, column: col, row, x: col * COL_STEP, y: HEADER_H + row * ROW_STEP, failure: false });
    }
    successRowCount = Math.max(successRowCount, next);
  }
  const lineY = HEADER_H + successRowCount * ROW_STEP + 8;

  const failureIds = order.filter((id) => !onSuccess.has(id));
  const stack = new Map<string, number>();
  const bandRows = new Map<number, number>();
  for (const id of failureIds) {
    const rank = failRank.get(id) ?? 0;
    const key = `${rank}:${column.get(id) ?? 0}`;
    const depthInBand = stack.get(key) ?? 0;
    stack.set(key, depthInBand + 1);
    bandRows.set(rank, Math.max(bandRows.get(rank) ?? 0, depthInBand + 1));
  }
  const bandTop = new Map<number, number>();
  let top = lineY + 44;
  for (const rank of [...bandRows.keys()].sort((a, b) => a - b)) {
    bandTop.set(rank, top);
    top += (bandRows.get(rank) ?? 1) * ROW_STEP;
  }
  const used = new Map<string, number>();
  for (const id of failureIds) {
    const rank = failRank.get(id) ?? 0;
    const col = column.get(id) ?? 0;
    const key = `${rank}:${col}`;
    const row = used.get(key) ?? 0;
    used.set(key, row + 1);
    placed.push({ id, column: col, row, x: col * COL_STEP, y: (bandTop.get(rank) ?? lineY) + row * ROW_STEP, failure: true });
  }

  const headings: ColumnHeading[] = [
    { label: "Inputs and activities", x: 0 },
    { label: "Outputs", x: COL_STEP },
    { label: "Short-term outcomes", x: 2 * COL_STEP },
    { label: "Long-term outcomes", x: longColumn * COL_STEP },
    { label: "Impact", x: impactColumn * COL_STEP },
  ];
  return {
    boxes: placed,
    headings,
    lineY: failureIds.length > 0 ? lineY : null,
    ceilingX: COL_STEP + BOX_W + COL_GAP / 2,
    width: impactColumn * COL_STEP + BOX_W,
    height: Math.max(HEADER_H + BOX_H, ...placed.map((box) => box.y + BOX_H)),
  };
}

export interface EdgeRoute {
  path: string;
  labelX: number;
  labelY: number;
}

/** An SVG path through the points, with each corner rounded to at most `radius`. */
function roundedPath(points: [number, number][], radius: number): string {
  const first = points[0];
  if (first === undefined) return "";
  let d = `M ${first[0]},${first[1]}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const [px, py] = points[i - 1] as [number, number];
    const [cx, cy] = points[i] as [number, number];
    const [nx, ny] = points[i + 1] as [number, number];
    const r = Math.min(radius, Math.hypot(cx - px, cy - py) / 2, Math.hypot(nx - cx, ny - cy) / 2);
    const inX = cx - Math.sign(cx - px) * r;
    const inY = cy - Math.sign(cy - py) * r;
    const outX = cx + Math.sign(nx - cx) * r;
    const outY = cy + Math.sign(ny - cy) * r;
    d += ` L ${inX},${inY} Q ${cx},${cy} ${outX},${outY}`;
  }
  const last = points[points.length - 1] as [number, number];
  return `${d} L ${last[0]},${last[1]}`;
}

/**
 * A right-angled route from a box's right side to a later column's left side
 * that never crosses a box. To the next column it turns once, in the gap
 * between the two. Across several columns it turns in the gap after the
 * source, runs along the empty lane just above the target's row, and turns
 * down in the gap before the target. Connections leaving one box share their
 * first stretch, so a fan-out reads as one trunk with branches. The label
 * point (the critical connection's mark) is the route's middle: the turn into
 * the target's row in the gap, or the middle of the lane.
 */
export function routeEdge(sourceX: number, sourceY: number, targetX: number, targetY: number, span: number): EdgeRoute {
  const radius = 10;
  const afterSource = sourceX + COL_GAP / 2;
  if (span <= 1 || Math.abs(targetY - sourceY) < 1) {
    const points: [number, number][] = [[sourceX, sourceY], [afterSource, sourceY], [afterSource, targetY], [targetX, targetY]];
    // The middle of the gap, on the target's row: this connection's own stretch.
    return { path: roundedPath(points, radius), labelX: afterSource, labelY: targetY };
  }
  const beforeTarget = targetX - COL_GAP / 2;
  const lane = targetY - BOX_H / 2 - ROW_GAP / 2;
  const points: [number, number][] = [
    [sourceX, sourceY],
    [afterSource, sourceY],
    [afterSource, lane],
    [beforeTarget, lane],
    [beforeTarget, targetY],
    [targetX, targetY],
  ];
  // The middle of the lane.
  return { path: roundedPath(points, radius), labelX: (afterSource + beforeTarget) / 2, labelY: lane };
}

/** "Intervention → intended change", from the first input and the last impact. */
export function tocTitle(graph: Pick<TocGraph, "boxes" | "links" | "pathways">, fallback?: string): string {
  const layout = layoutToc(graph);
  const textOf = (id: string) => graph.boxes.find((box) => box.box_id === id)?.text;
  const first = layout.boxes.find((box) => !box.failure && box.column === 0);
  const impacts = layout.boxes.filter((box) => !box.failure && graph.boxes.find((b) => b.box_id === box.id)?.layer === "impact");
  const input = first === undefined ? undefined : textOf(first.id);
  const impact = impacts.length === 0 ? undefined : textOf(impacts[0]?.id ?? "");
  if (input !== undefined && impact !== undefined) return `${input} → ${impact}`;
  return fallback ?? "Theory of change";
}

/** "Pathway 1 · label" for success pathways, "If it goes wrong · label" for failure ones. */
export function pathwayTitles(graph: Pick<TocGraph, "pathways">): Map<string, string> {
  const titles = new Map<string, string>();
  let n = 0;
  for (const pathway of keptPathways(graph)) {
    titles.set(pathway.pathway_id, pathway.kind === "success" ? `Pathway ${(n += 1)} · ${pathway.label}` : `If it goes wrong · ${pathway.label}`);
  }
  return titles;
}
