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

export const COLUMN_LABELS = ["Inputs", "Outputs", "Outcomes", "Impact"] as const;
const LAYER_COLUMN: Record<BoxLayer, number> = { input: 0, output: 1, outcome: 2, impact: 3, failure_outcome: 2 };

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
export const COL_GAP = 90;
export const ROW_GAP = 28;
const COL_STEP = BOX_W + COL_GAP;
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

export interface TocLayout {
  boxes: PlacedBox[];
  /** The y of the "If it goes wrong" line, or null when nothing sits under it. */
  lineY: number | null;
  width: number;
}

/**
 * Where every box of a kept pathway goes. Deterministic, no layout library.
 *
 * Four columns by layer. Boxes on a success pathway sit above the line, in
 * rows by order of first appearance along the kept pathways. Boxes found only
 * on failure pathways sit under the line, one band of rows per failure
 * pathway; a `failure_outcome` box goes in the column after its source.
 */
export function layoutToc(graph: Pick<TocGraph, "boxes" | "links" | "pathways">): TocLayout {
  const boxById = new Map<string, TocBox>(graph.boxes.map((box) => [box.box_id, box]));
  const linkById = new Map(graph.links.map((link) => [link.link_id, link]));
  const column = new Map<string, number>();
  const onSuccess = new Set<string>();
  /** First failure pathway (its rank among failure pathways) that holds a box. */
  const failRank = new Map<string, number>();
  const order: string[] = [];

  let failIndex = -1;
  for (const pathway of keptPathways(graph)) {
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
          column.set(
            id,
            box.layer === "failure_outcome" && id === link.target_box_id && sourceColumn !== undefined
              ? Math.min(sourceColumn + 1, 3)
              : LAYER_COLUMN[box.layer],
          );
        }
        if (pathway.kind === "success") onSuccess.add(id);
        else if (!failRank.has(id)) failRank.set(id, failIndex);
      }
    }
  }

  const placed: PlacedBox[] = [];
  const rowOf = new Map<string, number>();
  const successRows = new Map<number, number>();
  for (const id of order) {
    if (!onSuccess.has(id)) continue;
    const col = column.get(id) ?? 0;
    const row = successRows.get(col) ?? 0;
    successRows.set(col, row + 1);
    rowOf.set(id, row);
    placed.push({ id, column: col, row, x: col * COL_STEP, y: HEADER_H + row * (BOX_H + ROW_GAP), failure: false });
  }
  const successRowCount = Math.max(0, ...successRows.values());
  const lineY = HEADER_H + successRowCount * (BOX_H + ROW_GAP) + 8;

  const failureIds = order.filter((id) => !onSuccess.has(id));
  const stack = new Map<string, number>();
  const bandRows = new Map<number, number>();
  for (const id of failureIds) {
    const rank = failRank.get(id) ?? 0;
    const col = column.get(id) ?? 0;
    const key = `${rank}:${col}`;
    const depth = stack.get(key) ?? 0;
    stack.set(key, depth + 1);
    bandRows.set(rank, Math.max(bandRows.get(rank) ?? 0, depth + 1));
  }
  const bandTop = new Map<number, number>();
  let top = lineY + 44;
  for (const rank of [...bandRows.keys()].sort((a, b) => a - b)) {
    bandTop.set(rank, top);
    top += (bandRows.get(rank) ?? 1) * (BOX_H + ROW_GAP);
  }
  const used = new Map<string, number>();
  for (const id of failureIds) {
    const rank = failRank.get(id) ?? 0;
    const col = column.get(id) ?? 0;
    const key = `${rank}:${col}`;
    const depth = used.get(key) ?? 0;
    used.set(key, depth + 1);
    placed.push({
      id,
      column: col,
      row: depth,
      x: col * COL_STEP,
      y: (bandTop.get(rank) ?? lineY) + depth * (BOX_H + ROW_GAP),
      failure: true,
    });
  }
  return { boxes: placed, lineY: failureIds.length > 0 ? lineY : null, width: 3 * COL_STEP + BOX_W };
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
  const impacts = layout.boxes.filter((box) => !box.failure && box.column === 3);
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
