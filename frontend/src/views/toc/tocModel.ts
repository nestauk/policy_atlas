import type { BoxLayer, Origin, Support, TocBox, TocDocument, TocGraph, TocLink, TocPathway, Verdict } from "./types";

/*
 * Pure helpers for the theory-of-change Result page (task 054): wording,
 * which pathways are shown, the canvas layout and the Assumptions grouping.
 * No React here, so the layout and the grouping are unit-tested directly.
 */

export const VERDICT_LABEL: Record<Verdict, string> = {
  confident: "Confident",
  not_sure_mixed: "Not sure: mixed",
  not_sure_insufficient: "Not sure: too little evidence",
  not_confident: "Not confident: evidence against",
};

/** Best first: the legend's order. */
export const VERDICTS: readonly Verdict[] = ["confident", "not_sure_mixed", "not_sure_insufficient", "not_confident"];

/** The CSS variable that colours a verdict's dot and arrowhead (defined once in `index.css`). */
export const VERDICT_VAR: Record<Verdict, string> = {
  confident: "var(--color-verdict-confident)",
  not_sure_mixed: "var(--color-verdict-mixed)",
  not_sure_insufficient: "var(--color-verdict-little)",
  not_confident: "var(--color-verdict-against)",
};

export const SUPPORT_LABEL: Record<Support, string> = {
  strong: "Strongly supports",
  weak: "Weakly supports",
  mixed: "Mixed",
  refutes: "Refutes",
  not_about: "Not about this step",
};

export const NEAR_THRESHOLD = "Close to the threshold: one more study could change this verdict.";

/** The hover text of an edge: its verdict, and whether it is close to changing. */
export function linkTip(link: TocLink): string {
  if (link.state === "checking" || link.state === "unchecked") return "Checking the evidence…";
  const critical = link.critical ? "Critical connection · test this first. " : "";
  return `${critical}${VERDICT_LABEL[link.verdict]}${link.near_threshold ? " · close to the threshold" : ""}`;
}

/** The evidence balance's four columns, left to right (C36). */
export const BALANCE: readonly Exclude<Support, "not_about">[] = ["refutes", "mixed", "weak", "strong"];

/** Each column's document weights, heaviest first; documents not about the step are left out. */
export function evidenceBalance(documents: Pick<TocDocument, "support" | "weight">[]): { support: Exclude<Support, "not_about">; weights: number[] }[] {
  return BALANCE.map((support) => ({
    support,
    weights: documents
      .filter((doc) => doc.support === support)
      .map((doc) => doc.weight)
      .sort((a, b) => b - a),
  }));
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
