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
  ViewportPortal,
} from "@xyflow/react";

import { prefersReducedMotion } from "../../lib/motion";
import { scrub } from "../../lib/scrub";
import type { Selection } from "./DetailPanel";
import { imageBounds } from "./exports";
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
import type { Preview } from "./Suggestions";
import type { TocBox, TocGraph, TocLink, TocPathway, Verdict } from "./types";

/** Ids of what a hovered suggestion would add: drawn faded, never clickable. */
const PREVIEW = "preview:";

/**
 * The theory with a suggested route added, for the canvas only: its new boxes,
 * links and pathway get preview ids. Existing boxes and links are named by code.
 */
function withPreview(graph: TocGraph, preview: Preview | null): TocGraph {
  if (preview === null) return graph;
  const boxId = (ref: string) => graph.boxes.find((box) => box.code === ref)?.box_id ?? PREVIEW + ref;
  const linkId = (ref: string) => graph.links.find((link) => link.code === ref)?.link_id ?? PREVIEW + ref;
  const boxes = preview.boxes.map(
    (box) =>
      ({
        box_id: PREVIEW + box.key,
        code: null,
        layer: box.layer,
        text: box.text,
        origin: "drafted",
        revision: 0,
        position: null,
        result_criteria: { definition: null, indicator: null },
      }) as unknown as TocBox,
  );
  const links = preview.links.map(
    (link) =>
      ({
        link_id: PREVIEW + link.key,
        code: null,
        source_box_id: boxId(link.source),
        target_box_id: boxId(link.dest),
        verdict: "not_sure_insufficient",
        state: "checked",
        pending_count: 0,
        critical: false,
        origin: "drafted",
        sentence: "",
        conditions: [],
      }) as unknown as TocLink,
  );
  const pathways =
    preview.pathway === null
      ? []
      : [
          {
            pathway_id: `${PREVIEW}route`,
            kind: preview.pathway.kind,
            status: "kept",
            label: "",
            link_ids: preview.pathway.links.map(linkId),
            origin: "drafted",
            broken: false,
            reason: null,
          } as unknown as TocPathway,
        ];
  return { ...graph, boxes: [...graph.boxes, ...boxes], links: [...graph.links, ...links], pathways: [...graph.pathways, ...pathways] };
}

interface BoxData extends Record<string, unknown> {
  box: TocBox;
  dim: boolean;
  selected: boolean;
  /** A box the user added that no check has found evidence for yet (C41). */
  needsEvidence: boolean;
  /** The source picked in Connect mode. */
  connecting: boolean;
  /** Part of a hovered suggestion: drawn faded. */
  ghost: boolean;
}
interface EdgeData extends Record<string, unknown> {
  /** Columns from source to target; 0 inside one column. */
  span: number;
  /** A box at either end was moved: a right-angle route with rounded corners, side to side (C47). */
  curved: boolean;
  /** Something waits for the user here: new evidence, or an edit's evidence to review (C43, C44). */
  attention: boolean;
  verdict: Verdict;
  pending: boolean;
  /** No check has looked at it yet: a still grey line (C41, C48). */
  unchecked: boolean;
  /** An uploaded theory waiting for review: a connection Policy Atlas suggested (increment 5). */
  suggested: boolean;
  /** An uploaded theory waiting for review: a connection from the user's own diagram, not yet checked. */
  drawn: boolean;
  /** Part of a hovered suggestion: drawn faded. */
  ghost: boolean;
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
/** The furthest the view zooms out: far enough for the fit button to show a large theory whole. */
const MIN_ZOOM = 0.1;
const VIEW_PADDING = 0.08;
const HANDLE_CLASS = "!h-1 !w-1 !border-0 !bg-transparent";

/**
 * A text node on the canvas: never dragged, selected or focused. `passThrough`
 * also lets a click through to a box or a connection under it.
 */
function labelNode(id: string, x: number, y: number, data: LabelData, passThrough = false): LabelNode {
  return {
    id,
    type: "label",
    position: { x, y },
    data,
    // Explicit sizes: a node without them loses its measurement each time the
    // nodes array is rebuilt, and React Flow's "fit view" then waits forever.
    width: LABEL_W,
    height: LABEL_H,
    draggable: false,
    selectable: false,
    focusable: false,
    ...(passThrough ? { style: { pointerEvents: "none" as const } } : {}),
  };
}

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
        data.ghost ? "border-dashed !border-blue opacity-60" : "",
      ].join(" ")}
      style={{ width: BOX_W, height: BOX_H }}
    >
      {HANDLES.map((handle) => (
        <Handle key={handle.id} id={handle.id} type={handle.type} position={handle.position} className={HANDLE_CLASS} />
      ))}
      {box.code !== null && <span className="absolute left-3.5 top-0.5 text-caption leading-none text-grey">{box.code}</span>}
      <span className="line-clamp-3">{scrub(box.text)}</span>
      {data.needsEvidence && <span className="absolute bottom-0.5 right-3 text-caption font-normal italic leading-none text-grey">Needs evidence</span>}
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

/** The same two dividers, bounded and inside the viewport, for the downloaded image only. */
function ExportDividers({ graph, lineY, ceilingX }: { graph: TocGraph; lineY: number | null; ceilingX: number }) {
  const { x, y, width, height } = imageBounds(graph);
  return (
    <ViewportPortal>
      {lineY !== null && <div className="toc-export-only absolute border-t border-line-2" style={{ left: x, top: lineY, width }} />}
      <div className="toc-export-only absolute border-l border-dashed border-grey" style={{ left: ceilingX, top: y, height }} />
    </ViewportPortal>
  );
}

function TocEdgeView({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd }: EdgeProps<TocEdge>) {
  if (data === undefined) return null;
  const [path, markX, markY] = data.curved
    ? // A moved box keeps the right-angle style with rounded corners, side to side.
      getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition: Position.Right, targetPosition: Position.Left, borderRadius: 10 })
    : data.span > 0
      ? (({ path: p, labelX, labelY }) => [p, labelX, labelY] as const)(routeEdge(sourceX, sourceY, targetX, targetY, data.span))
      : getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 10 });
  const kind = data.ghost ? "preview" : data.pending ? "pending" : data.suggested ? "suggested" : data.drawn ? "drawn" : data.unchecked ? "unchecked" : data.verdict;
  return (
    <g>
      <title>{data.tip}</title>
      {/* The selected connection gets the boxes' blue halo, under its own line. */}
      {data.selected && <path d={path} data-testid="toc-edge-halo" className="toc-edge-halo" />}
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={18}
        className={`toc-edge toc-edge--${kind}${data.selected ? " toc-edge--selected" : ""}`}
      />
      {data.critical && <CriticalMark x={markX} y={markY} />}
      {data.attention && <circle data-testid="toc-edge-attention" cx={markX} cy={data.critical ? markY - 16 : markY} r={5.5} className="pointer-events-none fill-blue stroke-paper" strokeWidth={2} />}
    </g>
  );
}

const nodeTypes = { box: BoxView, label: LabelView };
const edgeTypes = { toc: TocEdgeView };

/** What the canvas needs to edit (C41, C47). */
interface CanvasEditing {
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
 * right. Also serves full-screen changes; the fit button uses FitTo.
 */
function ViewFitter({ boxes, bounds, refit }: { boxes: number; bounds: Bounds; refit: number }) {
  const { setViewport } = useReactFlow();
  const store = useStoreApi();
  const ready = useStore((state) => state.width > 0 && state.height > 0);
  const { x, y, width, height } = bounds;
  // The load, a new box count or full screen fit the view; a pathway change only pans to it.
  const fittedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!ready) return;
    const { width: viewW, height: viewH, transform } = store.getState();
    const key = `${boxes}:${refit}`;
    if (fittedFor.current === key) {
      const zoom = transform[2];
      void setViewport({ x: viewW / 2 - (x + width / 2) * zoom, y: viewH / 2 - (y + height / 2) * zoom, zoom }, { duration: prefersReducedMotion() ? 0 : 300 });
      return;
    }
    fittedFor.current = key;
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
 * Fits the view to `rect` each time `count` moves on (nothing while it is 0
 * or there is no rect): the fit button's whole graph, or the box or
 * connection the report asks to centre on.
 */
function FitTo({ count, rect, minZoom, maxZoom, padding, duration }: { count: number; rect: Bounds | null; minZoom: number; maxZoom: number; padding: number; duration: number }) {
  const { setViewport } = useReactFlow();
  const store = useStoreApi();
  const { x = 0, y = 0, width = 0, height = 0 } = rect ?? {};
  const has = rect !== null;
  useEffect(() => {
    if (count === 0 || !has) return;
    const view = store.getState();
    void setViewport(getViewportForBounds({ x, y, width, height }, view.width, view.height, minZoom, maxZoom, padding), { duration: prefersReducedMotion() ? 0 : duration });
  }, [count, has, x, y, width, height, minZoom, maxZoom, padding, duration, setViewport, store]);
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
  graph: theory,
  pathway,
  selection,
  focus,
  onSelect,
  editing,
  preview,
}: {
  graph: TocGraph;
  /** "all" or one kept pathway's id. */
  pathway: string;
  selection: Selection | null;
  /** A box or connection to centre on, from the report. */
  focus: { target: Selection; count: number } | null;
  onSelect: (selection: Selection | null) => void;
  /** Editing controls for an editor (C41, C47); null keeps the canvas read-only. */
  editing: CanvasEditing | null;
  /** A hovered suggestion's route, drawn faded (owner, 2026-11-04). */
  preview: Preview | null;
}) {
  const graph = withPreview(theory, preview);
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
  // A box the user added whose connections no check has judged yet; nothing to say before the first check.
  const needsEvidence = (box: TocBox) =>
    graph.check_status !== "none" && box.origin === "user" && graph.links.filter((link) => link.source_box_id === box.box_id || link.target_box_id === box.box_id).every((link) => link.state === "unchecked");
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
  // Full screen takes the canvas's whole area: its bar, the canvas and the detail panel.
  const fsEl = () => boxRef.current?.closest<HTMLElement>("#toc-canvas") ?? boxRef.current?.parentElement ?? null;
  const [fullscreen, setFullscreen] = useState(false);
  const [refit, setRefit] = useState(0);
  const [fitWhole, setFitWhole] = useState(0);
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
    ...layout.headings.map((heading, index) => labelNode(`col-${index}`, heading.x, HEADER_H - 36, { text: heading.label })),
    ...(layout.lineY === null ? [] : [labelNode("line-label", 0, layout.lineY + 10, { text: "If it goes wrong" })]),
    // The accountability ceiling (C35): what the programme directly influences, and what it contributes to.
    labelNode("ceiling-left", layout.ceilingX - 8 - LABEL_W, ceilingLabelY, { text: "Directly influenced", alignRight: true }, true),
    labelNode("ceiling-right", layout.ceilingX + 8, ceilingLabelY, { text: "Contributes to" }, true),
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
            ghost: placed.id.startsWith(PREVIEW),
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
      // A link is "pending" while a check is working on it.
      const pending = link.state === "checking";
      const unchecked = link.state === "unchecked";
      const reviewing = graph.check_status === "drafted";
      return {
        id: link.link_id,
        type: "toc",
        source: link.source_box_id,
        target: link.target_box_id,
        sourceHandle: sameColumn ? (upward ? "ts" : "b") : "r",
        targetHandle: sameColumn ? (upward ? "bt" : "t") : "l",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: pending || (unchecked && !reviewing) ? "var(--color-line-2)" : reviewing ? (link.origin === "imported" ? "var(--color-navy)" : "var(--color-blue)") : VERDICT_VAR[link.verdict],
        },
        data: {
          span: sameColumn ? 0 : (columnOf.get(link.target_box_id) ?? 0) - (columnOf.get(link.source_box_id) ?? 0),
          curved,
          attention: link.pending_count > 0 || link.state === "pending",
          verdict: link.verdict,
          pending,
          unchecked,
          suggested: reviewing && link.origin !== "imported",
          drawn: reviewing && link.origin === "imported",
          ghost: link.link_id.startsWith(PREVIEW),
          critical: link.critical,
          selected: selection?.kind === "link" && selection.id === link.link_id,
          tip: linkTip(link),
        },
        selectable: false,
        focusable: !link.link_id.startsWith(PREVIEW),
        ariaLabel: linkTip(link),
      };
    });

  const clickBox = (id: string) => {
    if (connecting) {
      if (connectFrom === null) setConnectFrom(id);
      else if (connectFrom !== id) {
        editing?.onConnect(connectFrom, id);
        setConnectFrom(null);
      }
      return;
    }
    onSelect({ kind: "box", id });
  };

  return (
    <div ref={boxRef} className="toc-canvas h-[640px] min-w-0 flex-1 bg-paper-2 lg:h-full" role="group" aria-label="Theory of change canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={editing !== null && !connecting}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={MIN_ZOOM}
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
          if (node.type === "box") clickBox(node.id);
        }}
        onEdgeClick={(_, edge) => onSelect({ kind: "link", id: edge.id })}
        // Keyboard: Enter or Space on a focused box or connection acts as a click.
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          const target = event.target as Element;
          const id = target.getAttribute("data-id");
          if (id === null) return;
          if (target.classList.contains("react-flow__node-box")) clickBox(id);
          else if (target.classList.contains("react-flow__edge")) onSelect({ kind: "link", id });
          else return;
          event.preventDefault();
        }}
        onPaneClick={() => onSelect(null)}
      >
        <Dividers lineY={layout.lineY} ceilingX={layout.ceilingX} />
        <ExportDividers graph={graph} lineY={layout.lineY} ceilingX={layout.ceilingX} />
        {connecting && (
          <p className="pointer-events-none absolute left-3 top-3 z-10 bg-paper px-2.5 py-1 text-meta font-semibold text-blue">
            {connectFrom === null ? "Click the box the connection starts from" : "Click the box it leads to"} · Esc to cancel
          </p>
        )}
        <FitTo count={focus?.count ?? 0} rect={focus === null ? null : rectOf(focus.target)} minZoom={0.5} maxZoom={FOCUS_MAX_ZOOM} padding={0.25} duration={400} />
        <ViewFitter boxes={layout.boxes.length} bounds={bounds} refit={refit} />
        {/* The fit button: the whole graph (or the chosen pathway) in view, however far out that takes the zoom. */}
        <FitTo count={fitWhole} rect={bounds} minZoom={MIN_ZOOM} maxZoom={2} padding={VIEW_PADDING} duration={300} />
        <Controls showInteractive={false} showFitView={false}>
          {/* Our own fit button: the whole diagram, below the start zoom when it must be. */}
          <ControlButton onClick={() => setFitWhole((count) => count + 1)} title="Fit the whole diagram" aria-label="Fit the whole diagram">
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
