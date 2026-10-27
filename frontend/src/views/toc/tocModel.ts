import type { BoxLayer, Grade, Origin, TocBox, TocGraph, TocLink, TocPathway } from "./types";

/*
 * Pure helpers for the theory-of-change Result page (task 054): wording,
 * which pathways are shown, the canvas layout and the Assumptions grouping.
 * No React here, so the layout and the grouping are unit-tested directly.
 */

export const GRADE_LABEL: Record<Grade, string> = {
  strong: "Strong",
  medium: "Medium",
  weak: "Weak",
  none: "No evidence found",
};

export const GRADES: readonly Grade[] = ["strong", "medium", "weak", "none"];

/** The CSS variable that colours a grade (defined once in `index.css`). */
export const GRADE_VAR: Record<Grade, string> = {
  strong: "var(--color-grade-strong)",
  medium: "var(--color-grade-medium)",
  weak: "var(--color-grade-weak)",
  none: "var(--color-grade-none)",
};

/** "Medium evidence it worked elsewhere." and its siblings. */
export function gradeSentence(grade: Grade, question: "elsewhere" | "here" | "merged"): string {
  if (grade === "none") {
    if (question === "here") return "No evidence found on whether it holds here.";
    if (question === "elsewhere") return "No evidence found that it worked elsewhere.";
    return "No evidence found.";
  }
  const tail = { elsewhere: "it worked elsewhere", here: "it holds here", merged: "including here" }[question];
  const comma = question === "merged" ? "," : "";
  return `${GRADE_LABEL[grade]} evidence${comma} ${tail}.`;
}

/** The hover text of an edge: both grades, or one when one answer covers both. */
export function linkTip(link: TocLink): string {
  if (link.state === "checking" || link.state === "unchecked") return "Checking the evidence…";
  const critical = link.critical ? "Critical connection · test this first. " : "";
  if (link.merged) return `${critical}${gradeSentence(link.elsewhere.grade, "merged").replace(/\.$/, "")}`;
  const part = (grade: Grade, tail: string) =>
    grade === "none" ? `No evidence found ${tail}` : `${GRADE_LABEL[grade]} evidence ${tail}`;
  return `${critical}${part(link.elsewhere.grade, "it worked elsewhere")} · ${part(link.here.grade, "it holds here")}`;
}

export const ORIGIN_LABEL: Record<Origin, string> = {
  drafted: "Drafted by Policy Atlas",
  found_in_evidence: "Found in the evidence",
  imported: "From your theory",
  user: "Added by you",
  options_scoping: "From your options scoping",
};

export const LAYER_LABEL: Record<BoxLayer, string> = {
  input: "Input",
  output: "Output",
  outcome: "Outcome",
  impact: "Impact",
  failure_outcome: "Outcome if it goes wrong",
};

/** Kept pathways, success first, then failure (each in the API's order). */
export function keptPathways(graph: Pick<TocGraph, "pathways">): TocPathway[] {
  const kept = graph.pathways.filter((pathway) => pathway.status === "kept");
  return [...kept.filter((p) => p.kind === "success"), ...kept.filter((p) => p.kind === "failure")];
}

/** The link ids shown for a pathway choice ("all" or one pathway id). */
export function visibleLinkIds(graph: Pick<TocGraph, "pathways">, choice: string): Set<string> {
  const chosen = keptPathways(graph).filter((p) => choice === "all" || p.pathway_id === choice);
  return new Set(chosen.flatMap((p) => p.link_ids));
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
  width: number;
}

/**
 * Where every box of a kept pathway goes. Deterministic, no layout library.
 *
 * Columns follow the layers, left to right, and outcomes take as many columns
 * as their longest chain: an outcome sits one column after the outcome that
 * leads to it, so a chain reads left to right and the impact comes after the
 * last outcome. Boxes on a success pathway sit above the line; each takes the
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

  // Outcome depth: the longest chain of outcome-to-outcome links leading to it.
  const outcomeSources = new Map<string, string[]>();
  for (const link of keptLinks) {
    if (layerOf(link.source_box_id) === "outcome" && layerOf(link.target_box_id) === "outcome") {
      outcomeSources.set(link.target_box_id, [...(outcomeSources.get(link.target_box_id) ?? []), link.source_box_id]);
    }
  }
  const depth = new Map<string, number>();
  const depthOf = (id: string, seen: Set<string>): number => {
    const known = depth.get(id);
    if (known !== undefined) return known;
    if (seen.has(id)) return 0; // a loop: break it here
    seen.add(id);
    const d = Math.max(-1, ...(outcomeSources.get(id) ?? []).map((source) => depthOf(source, seen))) + 1;
    depth.set(id, d);
    return d;
  };
  for (const box of graph.boxes) if (box.layer === "outcome") depthOf(box.box_id, new Set());
  const outcomeColumns = Math.max(1, ...[...depth.values()].map((d) => d + 1));
  const impactColumn = 2 + outcomeColumns;

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
          const byLayer = { input: 0, output: 1, outcome: 2 + (depth.get(id) ?? 0), impact: impactColumn, failure_outcome: 2 }[box.layer];
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
    { label: "Inputs", x: 0 },
    { label: "Outputs", x: COL_STEP },
    { label: "Outcomes", x: 2 * COL_STEP },
    { label: "Impact", x: impactColumn * COL_STEP },
  ];
  return { boxes: placed, headings, lineY: failureIds.length > 0 ? lineY : null, width: impactColumn * COL_STEP + BOX_W };
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
 * point (the critical connection's dot) is on the last stretch, which is the
 * connection's own.
 */
export function routeEdge(sourceX: number, sourceY: number, targetX: number, targetY: number, span: number): EdgeRoute {
  const radius = 10;
  const afterSource = sourceX + COL_GAP / 2;
  if (span <= 1 || Math.abs(targetY - sourceY) < 1) {
    const points: [number, number][] = [[sourceX, sourceY], [afterSource, sourceY], [afterSource, targetY], [targetX, targetY]];
    return { path: roundedPath(points, radius), labelX: (afterSource + targetX) / 2, labelY: targetY };
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
  return { path: roundedPath(points, radius), labelX: (beforeTarget + targetX) / 2, labelY: targetY };
}

/** Assumption types in the order the Assumptions section lists them. */
export const ASSUMPTION_TYPES: readonly { key: string; label: string }[] = [
  { key: "delivery", label: "Delivery" },
  { key: "take-up", label: "Take-up" },
  { key: "behaviour change", label: "Behaviour change" },
  { key: "benefits and side effects", label: "Benefits and side effects" },
  { key: "if it goes wrong", label: "If it goes wrong" },
];

export interface AssumptionGroup {
  key: string;
  label: string;
  items: { condition: string; link: TocLink }[];
}

/** Every condition of every kept link, grouped by assumption type. */
export function groupAssumptions(graph: Pick<TocGraph, "links" | "pathways">): AssumptionGroup[] {
  const keptIds = visibleLinkIds(graph, "all");
  const groups = new Map<string, AssumptionGroup>(
    ASSUMPTION_TYPES.map((t) => [t.key, { key: t.key, label: t.label, items: [] }]),
  );
  for (const link of graph.links) {
    if (!keptIds.has(link.link_id)) continue;
    let group = groups.get(link.assumption_type);
    if (group === undefined) {
      const label = link.assumption_type.charAt(0).toUpperCase() + link.assumption_type.slice(1);
      group = { key: link.assumption_type, label, items: [] };
      groups.set(link.assumption_type, group);
    }
    for (const condition of link.conditions) group.items.push({ condition, link });
  }
  return [...groups.values()].filter((group) => group.items.length > 0);
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
