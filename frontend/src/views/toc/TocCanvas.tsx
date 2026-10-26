import "@xyflow/react/dist/style.css";

import {
  BaseEdge,
  Controls,
  getBezierPath,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import { scrub } from "../../lib/scrub";
import type { Selection } from "./DetailPanel";
import {
  BOX_H,
  BOX_W,
  COLUMN_LABELS,
  COL_GAP,
  GRADE_VAR,
  HEADER_H,
  layoutToc,
  linkTip,
  visibleLinkIds,
} from "./tocModel";
import type { Grade, TocBox, TocGraph, TocLink } from "./types";

interface BoxData extends Record<string, unknown> {
  box: TocBox;
  dim: boolean;
  selected: boolean;
}
interface EdgeData extends Record<string, unknown> {
  grade: Grade;
  pending: boolean;
  critical: boolean;
  selected: boolean;
  tip: string;
}
interface LabelData extends Record<string, unknown> {
  text: string;
  width?: number;
  line?: boolean;
}

type BoxNode = Node<BoxData, "box">;
type LabelNode = Node<LabelData, "label">;
type TocEdge = Edge<EdgeData, "toc">;

const HANDLE_CLASS = "!h-1 !w-1 !border-0 !bg-transparent";

function BoxView({ data }: NodeProps<BoxNode>) {
  const { box } = data;
  const criteria = box.result_criteria;
  const tip = [criteria.definition, criteria.indicator !== null ? `Indicator: ${criteria.indicator}` : null].filter(Boolean).join(" · ");
  return (
    <div
      title={tip === "" ? undefined : scrub(tip)}
      className={[
        "flex cursor-pointer items-center rounded-lg border-[1.5px] bg-paper px-3.5 text-meta font-semibold leading-snug text-navy shadow-sm",
        data.selected ? "border-blue ring-4 ring-blue-tint" : "border-grey/40",
        data.dim ? "opacity-20" : "",
      ].join(" ")}
      style={{ width: BOX_W, height: BOX_H }}
    >
      <Handle id="l" type="target" position={Position.Left} className={HANDLE_CLASS} />
      <Handle id="t" type="target" position={Position.Top} className={HANDLE_CLASS} />
      <span className="line-clamp-3">{scrub(box.text)}</span>
      <Handle id="r" type="source" position={Position.Right} className={HANDLE_CLASS} />
      <Handle id="b" type="source" position={Position.Bottom} className={HANDLE_CLASS} />
    </div>
  );
}

function LabelView({ data }: NodeProps<LabelNode>) {
  if (data.line) return <div className="border-t border-line-2" style={{ width: data.width }} />;
  return <p className="text-meta font-semibold text-grey">{data.text}</p>;
}

function TocEdgeView({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd }: EdgeProps<TocEdge>) {
  const [path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  if (data === undefined) return null;
  const kind = data.pending ? "pending" : data.grade;
  return (
    <g>
      <title>{data.tip}</title>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={18}
        className={`toc-edge toc-edge--${kind}${data.selected ? " toc-edge--selected" : ""}`}
      />
      {data.critical && <circle data-testid="toc-critical-dot" className="toc-critical-dot" cx={labelX} cy={labelY} r={6.5} />}
    </g>
  );
}

const nodeTypes = { box: BoxView, label: LabelView };
const edgeTypes = { toc: TocEdgeView };

/** A link is "pending" while its check has not produced a grade. */
const isPending = (link: TocLink) => link.state === "checking" || link.state === "unchecked";

// Handles are declared up front so edges draw before the first measurement.
const HANDLES = [
  { id: "l", type: "target" as const, position: Position.Left, x: 0, y: BOX_H / 2, width: 1, height: 1 },
  { id: "t", type: "target" as const, position: Position.Top, x: BOX_W / 2, y: 0, width: 1, height: 1 },
  { id: "r", type: "source" as const, position: Position.Right, x: BOX_W, y: BOX_H / 2, width: 1, height: 1 },
  { id: "b", type: "source" as const, position: Position.Bottom, x: BOX_W / 2, y: BOX_H, width: 1, height: 1 },
];

/**
 * The canvas: boxes in four layer columns, curved connections coloured by
 * their lower grade, failure pathways under a line. Read-only; clicking a box
 * or a connection selects it. Set-aside pathways never appear here.
 */
export function TocCanvas({
  graph,
  pathway,
  selection,
  onSelect,
}: {
  graph: TocGraph;
  /** "all" or one kept pathway's id. */
  pathway: string;
  selection: Selection | null;
  onSelect: (selection: Selection | null) => void;
}) {
  const layout = layoutToc(graph);
  const shown = visibleLinkIds(graph, pathway);
  const keptLinks = visibleLinkIds(graph, "all");
  const boxById = new Map(graph.boxes.map((box) => [box.box_id, box]));
  const columnOf = new Map(layout.boxes.map((placed) => [placed.id, placed.column]));
  const inView = new Set<string>();
  for (const link of graph.links) {
    if (shown.has(link.link_id)) {
      inView.add(link.source_box_id);
      inView.add(link.target_box_id);
    }
  }

  const nodes: Array<BoxNode | LabelNode> = [
    ...COLUMN_LABELS.map(
      (text, index): LabelNode => ({
        id: `col-${index}`,
        type: "label",
        position: { x: index * (BOX_W + COL_GAP), y: HEADER_H - 36 },
        data: { text },
        draggable: false,
        selectable: false,
        focusable: false,
      }),
    ),
    ...(layout.lineY === null
      ? []
      : [
          {
            id: "line",
            type: "label",
            position: { x: 0, y: layout.lineY },
            data: { text: "", line: true, width: layout.width },
            draggable: false,
            selectable: false,
            focusable: false,
          } as LabelNode,
          {
            id: "line-label",
            type: "label",
            position: { x: 0, y: layout.lineY + 10 },
            data: { text: "If it goes wrong" },
            draggable: false,
            selectable: false,
            focusable: false,
          } as LabelNode,
        ]),
    ...layout.boxes.flatMap((placed): BoxNode[] => {
      const box = boxById.get(placed.id);
      if (box === undefined) return [];
      return [
        {
          id: placed.id,
          type: "box",
          position: { x: placed.x, y: placed.y },
          width: BOX_W,
          height: BOX_H,
          handles: HANDLES,
          data: { box, dim: !inView.has(placed.id), selected: selection?.kind === "box" && selection.id === placed.id },
          draggable: false,
          connectable: false,
        },
      ];
    }),
  ];

  const edges: TocEdge[] = graph.links
    .filter((link) => keptLinks.has(link.link_id) && shown.has(link.link_id) && columnOf.has(link.source_box_id) && columnOf.has(link.target_box_id))
    .map((link) => {
      const sameColumn = columnOf.get(link.source_box_id) === columnOf.get(link.target_box_id);
      const pending = isPending(link);
      return {
        id: link.link_id,
        type: "toc",
        source: link.source_box_id,
        target: link.target_box_id,
        sourceHandle: sameColumn ? "b" : "r",
        targetHandle: sameColumn ? "t" : "l",
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: pending ? "var(--color-line-2)" : GRADE_VAR[link.lower_grade] },
        data: {
          grade: link.lower_grade,
          pending,
          critical: link.critical,
          selected: selection?.kind === "link" && selection.id === link.link_id,
          tip: linkTip(link),
        },
        selectable: false,
        focusable: false,
      };
    });

  return (
    <div className="toc-canvas h-[560px] min-w-0 flex-1 border border-line bg-paper-2" role="group" aria-label="Theory of change canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        fitView
        fitViewOptions={{ padding: 0.08 }}
        minZoom={0.3}
        onNodeClick={(_, node) => {
          if (node.type === "box") onSelect({ kind: "box", id: node.id });
        }}
        onEdgeClick={(_, edge) => onSelect({ kind: "link", id: edge.id })}
        onPaneClick={() => onSelect(null)}
      >
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
