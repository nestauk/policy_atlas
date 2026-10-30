import "@xyflow/react/dist/style.css";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BaseEdge,
  ControlButton,
  Controls,
  getViewportForBounds,
  getSmoothStepPath,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
  useReactFlow,
  useStore,
  useStoreApi,
} from "@xyflow/react";

import { scrub } from "../../lib/scrub";
import type { Selection } from "./DetailPanel";
import { CriticalMark } from "./ReadingGuide";
import {
  BOX_H,
  BOX_W,
  HEADER_H,
  layoutToc,
  linkTip,
  routeEdge,
  VERDICT_VAR,
  visibleLinkIds,
} from "./tocModel";
import type { TocBox, TocGraph, TocLink, Verdict } from "./types";

interface BoxData extends Record<string, unknown> {
  box: TocBox;
  dim: boolean;
  selected: boolean;
  /** A box the user added that no check has found evidence for yet (C41). */
  needsEvidence: boolean;
  /** The source picked in Connect mode. */
  connecting: boolean;
}
interface EdgeData extends Record<string, unknown> {
  /** Columns from source to target; 0 inside one column. */
  span: number;
  /** A box at either end was moved: a smooth curve between the facing sides (C47). */
  curved: boolean;
  verdict: Verdict;
  pending: boolean;
  critical: boolean;
  selected: boolean;
  tip: string;
}
interface LabelData extends Record<string, unknown> {
  text: string;
  alignRight?: boolean;
}

type BoxNode = Node<BoxData, "box">;
type LabelNode = Node<LabelData, "label">;
type TocEdge = Edge<EdgeData, "toc">;

const LABEL_W = 200;
const LABEL_H = 20;
/** Never zoom out below this on load: smaller and the box text is hard to read. */
const MIN_START_ZOOM = 1;
const VIEW_PADDING = 0.08;
const HANDLE_CLASS = "!h-1 !w-1 !border-0 !bg-transparent";
/** Display-only nodes: never selected, never catching a click meant for a box or a connection. */
const DECOR = { draggable: false, selectable: false, focusable: false, style: { pointerEvents: "none" as const } };

function BoxView({ data }: NodeProps<BoxNode>) {
  const { box } = data;
  const criteria = box.result_criteria;
  const tip = [criteria.definition, criteria.indicator !== null ? `Indicator: ${criteria.indicator}` : null].filter(Boolean).join(" · ");
  return (
    <div
      title={tip === "" ? undefined : scrub(tip)}
      className={[
        "relative flex cursor-pointer items-center rounded-lg border-[1.5px] bg-paper px-3.5 text-meta font-semibold leading-snug text-navy shadow-sm",
        box.code !== null ? "pt-3.5" : "",
        data.selected || data.connecting ? "border-blue ring-4 ring-blue-tint" : "border-grey/40",
        data.dim ? "opacity-20" : "",
      ].join(" ")}
      style={{ width: BOX_W, height: BOX_H }}
    >
      <Handle id="l" type="target" position={Position.Left} className={HANDLE_CLASS} />
      <Handle id="t" type="target" position={Position.Top} className={HANDLE_CLASS} />
      {box.code !== null && <span className="absolute left-3.5 top-0.5 text-caption leading-none text-grey">{box.code}</span>}
      <span className="line-clamp-3">{scrub(box.text)}</span>
      {data.needsEvidence && <span className="absolute bottom-0.5 right-3 text-caption font-normal italic leading-none text-grey">Needs evidence</span>}
      <Handle id="r" type="source" position={Position.Right} className={HANDLE_CLASS} />
      <Handle id="b" type="source" position={Position.Bottom} className={HANDLE_CLASS} />
      <Handle id="ts" type="source" position={Position.Top} className={HANDLE_CLASS} />
      <Handle id="bt" type="target" position={Position.Bottom} className={HANDLE_CLASS} />
    </div>
  );
}

function LabelView({ data }: NodeProps<LabelNode>) {
  return <p className={`text-meta font-semibold text-grey${data.alignRight ? " text-right" : ""}`}>{data.text}</p>;
}

/**
 * The two dividers, edge to edge of the view however it pans: the "If it goes
 * wrong" line and the dashed accountability ceiling (C35). Drawn as two
 * screen-sized lines that follow the viewport, not as nodes: a node long
 * enough to reach past any pan made every pan and zoom slow.
 */
function Dividers({ lineY, ceilingX }: { lineY: number | null; ceilingX: number }) {
  const [x, y, zoom] = useStore((state) => state.transform);
  return (
    <>
      {lineY !== null && <div data-testid="toc-line" className="pointer-events-none absolute inset-x-0 border-t border-line-2" style={{ top: y + lineY * zoom }} />}
      <div data-testid="toc-ceiling" className="pointer-events-none absolute inset-y-0 border-l border-dashed border-grey" style={{ left: x + ceilingX * zoom }} />
    </>
  );
}

/** A smooth curve from a box's right side to another's left side, with its middle (C47; the prototype's rule). */
function curve(sx: number, sy: number, tx: number, ty: number): readonly [string, number, number] {
  const pull = Math.max(40, Math.abs(tx - sx) / 2);
  return [`M ${sx},${sy} C ${sx + pull},${sy} ${tx - pull},${ty} ${tx},${ty}`, (sx + tx) / 2, (sy + ty) / 2] as const;
}

function TocEdgeView({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd }: EdgeProps<TocEdge>) {
  if (data === undefined) return null;
  const [path, markX, markY] = data.curved
    ? curve(sourceX, sourceY, targetX, targetY)
    : data.span > 0
      ? (({ path: p, labelX, labelY }) => [p, labelX, labelY] as const)(routeEdge(sourceX, sourceY, targetX, targetY, data.span))
      : getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 10 });
  const kind = data.pending ? "pending" : data.verdict;
  return (
    <g>
      <title>{data.tip}</title>
      {/* The selected connection gets the boxes' blue halo, under its own line. */}
      {data.selected && <path d={path} data-testid="toc-edge-halo" className="toc-edge-halo" />}
      {/* Mixed is two-tone: an amber line under the green dash. */}
      {kind === "not_sure_mixed" && <path d={path} className="toc-edge-under" />}
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={18}
        className={`toc-edge toc-edge--${kind}${data.selected ? " toc-edge--selected" : ""}`}
      />
      {data.critical && <CriticalMark x={markX} y={markY} />}
    </g>
  );
}

const nodeTypes = { box: BoxView, label: LabelView };
const edgeTypes = { toc: TocEdgeView };

/** A link is "pending" while a check is working on it. */
const isPending = (link: TocLink) => link.state === "checking";

/** What the canvas needs to edit (C41, C47). */
export interface CanvasEditing {
  /** "connect": the next two box clicks make a connection. */
  mode: "view" | "connect";
  onMove: (boxId: string, revision: number, x: number, y: number) => void;
  onConnect: (sourceId: string, targetId: string) => void;
  onCancelConnect: () => void;
}

// Handles are declared up front so edges draw before the first measurement.
const HANDLES = [
  { id: "l", type: "target" as const, position: Position.Left, x: 0, y: BOX_H / 2, width: 1, height: 1 },
  { id: "t", type: "target" as const, position: Position.Top, x: BOX_W / 2, y: 0, width: 1, height: 1 },
  { id: "r", type: "source" as const, position: Position.Right, x: BOX_W, y: BOX_H / 2, width: 1, height: 1 },
  { id: "b", type: "source" as const, position: Position.Bottom, x: BOX_W / 2, y: BOX_H, width: 1, height: 1 },
  { id: "ts", type: "source" as const, position: Position.Top, x: BOX_W / 2, y: 0, width: 1, height: 1 },
  { id: "bt", type: "target" as const, position: Position.Bottom, x: BOX_W / 2, y: BOX_H, width: 1, height: 1 },
];

/**
 * Sets the viewport: the whole graph (or the chosen pathway) fitted to the
 * view but never below MIN_START_ZOOM. When the graph is wider than fits at
 * that zoom it starts at the left edge, vertically centred, so the user pans
 * right. Also serves the "fit view" button and full-screen changes.
 */
function ViewFitter({ boxes, bounds, refit }: { boxes: number; bounds: Bounds; refit: number }) {
  const { setViewport } = useReactFlow();
  const store = useStoreApi();
  const ready = useStore((state) => state.width > 0 && state.height > 0);
  const { x, y, width, height } = bounds;
  useEffect(() => {
    if (!ready) return;
    const { width: viewW, height: viewH } = store.getState();
    const fitted = getViewportForBounds({ x, y, width, height }, viewW, viewH, 0.1, 2, VIEW_PADDING);
    if (fitted.zoom >= MIN_START_ZOOM) {
      void setViewport(fitted);
      return;
    }
    void setViewport({ x: 24 - x * MIN_START_ZOOM, y: (viewH - height * MIN_START_ZOOM) / 2 - y * MIN_START_ZOOM, zoom: MIN_START_ZOOM });
  }, [ready, boxes, x, y, width, height, refit, setViewport, store]);
  return null;
}

/** Most zoom a focus may use: a box or connection close enough to read, with its neighbours in view. */
const FOCUS_MAX_ZOOM = 1.25;

/**
 * Centres the view on a box, or on both ends of a connection, when the report
 * asks (a code clicked there). Zooms in to at most FOCUS_MAX_ZOOM.
 */
function Focuser({ count, rect }: { count: number; rect: Bounds | null }) {
  const { setViewport } = useReactFlow();
  const store = useStoreApi();
  const { x = 0, y = 0, width = 0, height = 0 } = rect ?? {};
  const has = rect !== null;
  useEffect(() => {
    if (count === 0 || !has) return;
    const view = store.getState();
    void setViewport(getViewportForBounds({ x, y, width, height }, view.width, view.height, 0.5, FOCUS_MAX_ZOOM, 0.25), { duration: 400 });
  }, [count, has, x, y, width, height, setViewport, store]);
  return null;
}

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The canvas: boxes in layer columns, curved connections styled by their
 * evidence verdict (the critical one marked with a warning triangle), failure pathways under a line, and a dashed line (the
 * accountability ceiling) between outputs and short-term outcomes. Read-only; clicking a box
 * or a connection selects it. Set-aside pathways never appear here.
 */
export function TocCanvas({
  graph,
  pathway,
  selection,
  focus = null,
  onSelect,
  editing = null,
}: {
  graph: TocGraph;
  /** "all" or one kept pathway's id. */
  pathway: string;
  selection: Selection | null;
  /** A box or connection to centre on, from the report. */
  focus?: { target: Selection; count: number } | null;
  onSelect: (selection: Selection | null) => void;
  /** Editing controls for an editor (C41, C47); null keeps the canvas read-only. */
  editing?: CanvasEditing | null;
}) {
  // Where a box is while dragged and until the saved position comes back (its revision moves on).
  const [dragged, setDragged] = useState<Map<string, { x: number; y: number; revision: number }>>(new Map());
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const connecting = editing?.mode === "connect";
  useEffect(() => {
    if (!connecting) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setConnectFrom(null);
        editing?.onCancelConnect();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [connecting, editing]);
  const computed = layoutToc(graph);
  const revisionOf = new Map(graph.boxes.map((box) => [box.box_id, box.revision]));
  const layout = {
    ...computed,
    boxes: computed.boxes.map((placed) => {
      const at = dragged.get(placed.id);
      return at !== undefined && at.revision === revisionOf.get(placed.id) ? { ...placed, x: at.x, y: at.y, moved: true } : placed;
    }),
  };
  const movedIds = new Set(layout.boxes.filter((placed) => placed.moved).map((placed) => placed.id));
  // A box the user added whose connections no check has judged yet.
  const needsEvidence = (box: TocBox) =>
    box.origin === "user" && graph.links.filter((link) => link.source_box_id === box.box_id || link.target_box_id === box.box_id).every((link) => link.state === "unchecked");
  // The ceiling's two labels sit below the lowest box.
  const ceilingLabelY = layout.height + 12;
  const shown = visibleLinkIds(graph, pathway);
  const keptLinks = visibleLinkIds(graph, "all");
  const boxById = new Map(graph.boxes.map((box) => [box.box_id, box]));
  const columnOf = new Map(layout.boxes.map((placed) => [placed.id, placed.column]));
  const yOf = new Map(layout.boxes.map((placed) => [placed.id, placed.y]));
  const inView = new Set<string>();
  for (const link of graph.links) {
    if (shown.has(link.link_id)) {
      inView.add(link.source_box_id);
      inView.add(link.target_box_id);
    }
  }

  const placedInView = layout.boxes.filter((placed) => pathway === "all" || inView.has(placed.id));
  const bounds: Bounds =
    placedInView.length === 0
      ? { x: 0, y: 0, width: layout.width, height: BOX_H }
      : (() => {
          const left = pathway === "all" ? 0 : Math.min(...placedInView.map((placed) => placed.x));
          const right = pathway === "all" ? layout.width : Math.max(...placedInView.map((placed) => placed.x + BOX_W));
          const top = pathway === "all" ? 0 : Math.min(...placedInView.map((placed) => placed.y));
          const bottom = pathway === "all" ? ceilingLabelY + LABEL_H : Math.max(...placedInView.map((placed) => placed.y + BOX_H));
          return { x: left, y: top, width: right - left, height: bottom - top };
        })();
  // The area a focus centres on: the box, or both ends of the connection.
  const rectOf = (target: Selection): Bounds | null => {
    const link = target.kind === "link" ? graph.links.find((item) => item.link_id === target.id) : undefined;
    const ids = target.kind === "box" ? [target.id] : link === undefined ? [] : [link.source_box_id, link.target_box_id];
    const placed = layout.boxes.filter((box) => ids.includes(box.id));
    if (placed.length === 0) return null;
    const x = Math.min(...placed.map((box) => box.x));
    const y = Math.min(...placed.map((box) => box.y));
    return { x, y, width: Math.max(...placed.map((box) => box.x + BOX_W)) - x, height: Math.max(...placed.map((box) => box.y + BOX_H)) - y };
  };
  const boxRef = useRef<HTMLDivElement>(null);
  // Full screen takes the whole row (canvas and detail panel), which is the canvas's parent.
  const fsEl = () => boxRef.current?.parentElement ?? null;
  const [fullscreen, setFullscreen] = useState(false);
  const [refit, setRefit] = useState(0);
  const canFullscreen = typeof document !== "undefined" && document.fullscreenEnabled === true;
  useEffect(() => {
    const onChange = () => {
      setFullscreen(document.fullscreenElement === fsEl());
      // Let the canvas settle to its new size, then fit again.
      window.setTimeout(() => setRefit((count) => count + 1), 150);
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement === fsEl()) void document.exitFullscreen();
    else void fsEl()?.requestFullscreen();
  }, []);

  const nodes: Array<BoxNode | LabelNode> = [
    ...layout.headings.map(
      (heading, index): LabelNode => ({
        id: `col-${index}`,
        type: "label",
        position: { x: heading.x, y: HEADER_H - 36 },
        data: { text: heading.label },
        // Explicit sizes: a node without them loses its measurement each time the
        // nodes array is rebuilt, and React Flow's "fit view" then waits forever.
        width: LABEL_W,
        height: LABEL_H,
        draggable: false,
        selectable: false,
        focusable: false,
      }),
    ),
    ...(layout.lineY === null
      ? []
      : [
          {
            id: "line-label",
            type: "label",
            position: { x: 0, y: layout.lineY + 10 },
            data: { text: "If it goes wrong" },
            width: LABEL_W,
            height: LABEL_H,
            draggable: false,
            selectable: false,
            focusable: false,
          } as LabelNode,
        ]),
    // The accountability ceiling (C35): what the programme directly influences, and what it contributes to.
    {
      id: "ceiling-left",
      type: "label",
      position: { x: layout.ceilingX - 8 - LABEL_W, y: ceilingLabelY },
      data: { text: "Directly influenced", alignRight: true },
      width: LABEL_W,
      height: LABEL_H,
      ...DECOR,
    } as LabelNode,
    {
      id: "ceiling-right",
      type: "label",
      position: { x: layout.ceilingX + 8, y: ceilingLabelY },
      data: { text: "Contributes to" },
      width: LABEL_W,
      height: LABEL_H,
      ...DECOR,
    } as LabelNode,
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
          data: {
            box,
            dim: !inView.has(placed.id),
            selected: selection?.kind === "box" && selection.id === placed.id,
            needsEvidence: needsEvidence(box),
            connecting: connectFrom === placed.id,
          },
          draggable: editing !== null && !connecting,
          connectable: false,
        },
      ];
    }),
  ];

  const edges: TocEdge[] = graph.links
    .filter((link) => keptLinks.has(link.link_id) && shown.has(link.link_id) && columnOf.has(link.source_box_id) && columnOf.has(link.target_box_id))
    .map((link) => {
      const curved = movedIds.has(link.source_box_id) || movedIds.has(link.target_box_id);
      const sameColumn = !curved && columnOf.get(link.source_box_id) === columnOf.get(link.target_box_id);
      // Inside one column a connection runs bottom to top, or top to bottom when it goes up.
      const upward = sameColumn && (yOf.get(link.target_box_id) ?? 0) < (yOf.get(link.source_box_id) ?? 0);
      const pending = isPending(link);
      return {
        id: link.link_id,
        type: "toc",
        source: link.source_box_id,
        target: link.target_box_id,
        sourceHandle: sameColumn ? (upward ? "ts" : "b") : "r",
        targetHandle: sameColumn ? (upward ? "bt" : "t") : "l",
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: pending ? "var(--color-line-2)" : VERDICT_VAR[link.verdict] },
        data: {
          span: sameColumn ? 0 : (columnOf.get(link.target_box_id) ?? 0) - (columnOf.get(link.source_box_id) ?? 0),
          curved,
          verdict: link.verdict,
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
    <div ref={boxRef} className={`toc-canvas min-w-0 flex-1 border border-line bg-paper-2 ${fullscreen ? "h-screen" : "h-[640px]"}`} role="group" aria-label="Theory of change canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={editing !== null && !connecting}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={0.3}
        onNodesChange={(changes) => {
          // Only drags change anything: follow the box while it moves.
          const moves = changes.filter((change) => change.type === "position" && change.position !== undefined);
          if (moves.length === 0) return;
          setDragged((current) => {
            const next = new Map(current);
            for (const change of moves) {
              if (change.type !== "position" || change.position === undefined) continue;
              next.set(change.id, { ...change.position, revision: revisionOf.get(change.id) ?? 0 });
            }
            return next;
          });
        }}
        onNodeDragStop={(_, node) => {
          const revision = revisionOf.get(node.id);
          if (editing !== null && revision !== undefined) editing.onMove(node.id, revision, Math.round(node.position.x), Math.round(node.position.y));
        }}
        onNodeClick={(_, node) => {
          if (node.type !== "box") return;
          if (connecting) {
            if (connectFrom === null) setConnectFrom(node.id);
            else if (connectFrom !== node.id) {
              editing?.onConnect(connectFrom, node.id);
              setConnectFrom(null);
            }
            return;
          }
          onSelect({ kind: "box", id: node.id });
        }}
        onEdgeClick={(_, edge) => onSelect({ kind: "link", id: edge.id })}
        onPaneClick={() => onSelect(null)}
      >
        <Dividers lineY={layout.lineY} ceilingX={layout.ceilingX} />
        {connecting && (
          <p className="pointer-events-none absolute left-3 top-3 z-10 rounded bg-paper px-2.5 py-1 text-meta font-semibold text-blue shadow-sm">
            {connectFrom === null ? "Click the box the connection starts from" : "Click the box it leads to"} · Esc to cancel
          </p>
        )}
        <Focuser count={focus?.count ?? 0} rect={focus === null ? null : rectOf(focus.target)} />
        <ViewFitter boxes={layout.boxes.length} bounds={bounds} refit={refit} />
        <Controls showInteractive={false} showFitView={false}>
          {/* Our own fit button: the library's would fit below the minimum zoom. */}
          <ControlButton onClick={() => setRefit((count) => count + 1)} title="Fit view" aria-label="Fit view">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <rect x="5" y="5" width="14" height="14" />
            </svg>
          </ControlButton>
          {canFullscreen && (
            <ControlButton onClick={toggleFullscreen} title={fullscreen ? "Exit full screen" : "Full screen"} aria-label={fullscreen ? "Exit full screen" : "Full screen"}>
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                {fullscreen ? <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" /> : <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />}
              </svg>
            </ControlButton>
          )}
        </Controls>
      </ReactFlow>
    </div>
  );
}
