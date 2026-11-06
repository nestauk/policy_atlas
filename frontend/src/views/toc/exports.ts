// The theory's downloads (contract item 6), built in the browser from the graph
// the page already holds: the references as CSV, the graph as JSON, a draw.io
// file and the canvas as PNG or SVG. PowerPoint is parked (owner, 2026-11-04):
// the draw.io file covers editing elsewhere.
import { toPng, toSvg } from "html-to-image";

import { scrub } from "../../lib/scrub";
import { csvCell, downloadFilename, triggerTextDownload, triggerUrlDownload } from "../artefactPresentation";
import { BOX_H, BOX_W, HEADER_H, layoutToc, VERDICT_LABEL, visibleLinkIds } from "./tocModel";
import type { TocGraph, Verdict } from "./types";

/** The file name, from the report's title. */
function exportName(graph: TocGraph, extension: string): string {
  return downloadFilename(graph.report?.title ?? "Theory of change", extension);
}

/** The report's reference list, with the connections each document is cited for. */
export function referencesCsv(graph: TocGraph): string {
  const sources = graph.report?.sources ?? [];
  const citedBy = new Map<number, string[]>();
  for (const row of graph.report?.assumptions ?? []) {
    for (const n of row.sources) citedBy.set(n, [...(citedBy.get(n) ?? []), row.code]);
  }
  const header = ["Number", "Citation", "Title", "Authors", "Year", "Publisher", "URL", "Connections", "Quote"];
  return [
    header.map(csvCell).join(","),
    ...sources.map((source) =>
      [
        source.n,
        scrub(source.citation),
        source.title,
        source.authors.join("; "),
        source.year,
        source.venue,
        source.url,
        (citedBy.get(source.n) ?? []).join(", "),
        source.quote,
      ]
        .map(csvCell)
        .join(","),
    ),
  ].join("\r\n");
}

// draw.io has no CSS variables: the verdict colours and dashes from index.css, written out.
const DRAWIO_EDGE: Record<Verdict, string> = {
  supported: "strokeColor=#18a48c;",
  leaning_supports: "strokeColor=#18a48c;dashed=1;dashPattern=12 5;",
  not_sure_mixed: "strokeColor=#f0a823;",
  not_sure_insufficient: "strokeColor=#b4b4bb;dashed=1;dashPattern=6 5;",
  leaning_against: "strokeColor=#d93a12;dashed=1;dashPattern=12 5;",
  against: "strokeColor=#d93a12;dashed=1;dashPattern=2 5;",
};
const NAVY = "#0f294a";
const GREY = "#646363";

const xml = (text: string) =>
  text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");

/**
 * A draw.io file: one shape per box, one arrow per connection joined to its two
 * boxes, the column headings, the two dividers and a key to the colours.
 * Miro, Lucidchart and diagrams.net open it.
 */
export function drawioXml(graph: TocGraph): string {
  const layout = layoutToc(graph);
  const boxById = new Map(graph.boxes.map((box) => [box.box_id, box]));
  const placed = new Set(layout.boxes.map((item) => item.id));
  const kept = visibleLinkIds(graph, "all");
  const cells: string[] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>'];
  const text = (id: string, value: string, x: number, y: number, w: number, h: number, style = "") =>
    cells.push(
      `<mxCell id="${id}" value="${xml(value)}" style="text;html=1;whiteSpace=wrap;fontColor=${GREY};fontStyle=1;${style}" vertex="1" parent="1"><mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry"/></mxCell>`,
    );
  const line = (id: string, x1: number, y1: number, x2: number, y2: number, style: string) =>
    cells.push(
      `<mxCell id="${id}" style="endArrow=none;html=1;${style}" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="${x1}" y="${y1}" as="sourcePoint"/><mxPoint x="${x2}" y="${y2}" as="targetPoint"/></mxGeometry></mxCell>`,
    );

  layout.headings.forEach((heading, index) => text(`col-${index}`, heading.label, heading.x, HEADER_H - 36, BOX_W, 20));
  const bottom = layout.height + 40;
  line("ceiling", layout.ceilingX, 0, layout.ceilingX, bottom, `strokeColor=${GREY};dashed=1;`);
  text("ceiling-left", "Directly influenced", layout.ceilingX - 208, layout.height + 12, 200, 20, "align=right;");
  text("ceiling-right", "Contributes to", layout.ceilingX + 8, layout.height + 12, 200, 20);
  if (layout.lineY !== null) {
    line("line", 0, layout.lineY, layout.width, layout.lineY, "strokeColor=#d3d3d8;");
    text("line-label", "If it goes wrong", 0, layout.lineY + 10, 200, 20);
  }
  for (const item of layout.boxes) {
    const box = boxById.get(item.id);
    if (box === undefined) continue;
    const label = `${box.code !== null ? `<font color="${GREY}">${xml(box.code)}</font><br>` : ""}${xml(scrub(box.text))}`;
    cells.push(
      `<mxCell id="${xml(item.id)}" value="${xml(label)}" style="rounded=1;arcSize=8;whiteSpace=wrap;html=1;align=left;spacingLeft=10;spacingRight=10;fillColor=#ffffff;strokeColor=#b2b1b1;fontColor=${NAVY};fontStyle=1;" vertex="1" parent="1"><mxGeometry x="${item.x}" y="${item.y}" width="${BOX_W}" height="${BOX_H}" as="geometry"/></mxCell>`,
    );
  }
  for (const link of graph.links) {
    if (!kept.has(link.link_id) || !placed.has(link.source_box_id) || !placed.has(link.target_box_id)) continue;
    const style = link.state === "unchecked" ? "strokeColor=#d3d3d8;" : DRAWIO_EDGE[link.verdict];
    cells.push(
      `<mxCell id="${xml(link.link_id)}" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeWidth=2;${style}" edge="1" parent="1" source="${xml(link.source_box_id)}" target="${xml(link.target_box_id)}"><mxGeometry relative="1" as="geometry"/></mxCell>`,
    );
  }
  const key = (Object.keys(DRAWIO_EDGE) as Verdict[])
    .map((verdict) => `<font color="${/#[0-9a-f]{6}/.exec(DRAWIO_EDGE[verdict])?.[0] ?? GREY}">■</font> ${xml(VERDICT_LABEL[verdict])}`)
    .join("<br>");
  text("key", `Evidence for each connection<br>${key}`, 0, bottom + 10, 260, 120, "fontStyle=0;verticalAlign=top;");
  const title = xml(graph.report?.title ?? "Theory of change");
  return `<mxfile host="Policy Atlas"><diagram name="${title}"><mxGraphModel><root>${cells.join("")}</root></mxGraphModel></diagram></mxfile>`;
}

/** The area the image covers: every box, the headings and the ceiling's labels, with a margin. */
export function imageBounds(graph: TocGraph): { x: number; y: number; width: number; height: number } {
  const layout = layoutToc(graph);
  const margin = 24;
  const xs = layout.boxes.map((item) => item.x);
  const ys = layout.boxes.map((item) => item.y);
  const x = Math.min(0, ...xs) - margin;
  const y = Math.min(0, ...ys) - margin;
  const right = Math.max(layout.width, ...xs.map((value) => value + BOX_W)) + margin;
  const bottom = Math.max(layout.height + 32, ...ys.map((value) => value + BOX_H)) + margin;
  return { x, y, width: right - x, height: bottom - y };
}

/**
 * The whole canvas as a picture, whatever part of it is in view: the canvas's
 * viewport drawn at scale 1 over the theory's bounds. The `toc-exporting` class
 * shows the dividers drawn inside the viewport, which the screen hides.
 */
async function canvasDataUrl(graph: TocGraph, kind: "png" | "svg"): Promise<string | null> {
  const canvas = document.querySelector<HTMLElement>("#toc-canvas .toc-canvas");
  const viewport = canvas?.querySelector<HTMLElement>(".react-flow__viewport");
  if (canvas == null || viewport == null) return null;
  const { x, y, width, height } = imageBounds(graph);
  const options = {
    backgroundColor: "#ffffff",
    width,
    height,
    pixelRatio: 2,
    style: { width: `${width}px`, height: `${height}px`, transform: `translate(${-x}px, ${-y}px) scale(1)` },
  };
  canvas.classList.add("toc-exporting");
  try {
    return kind === "png" ? await toPng(viewport, options) : await toSvg(viewport, options);
  } finally {
    canvas.classList.remove("toc-exporting");
  }
}

export async function canvasImage(graph: TocGraph, kind: "png" | "svg"): Promise<void> {
  const url = await canvasDataUrl(graph, kind);
  if (url !== null) triggerUrlDownload(url, exportName(graph, kind));
}

/**
 * The PDF report: the whole canvas, fitted to the page width as a picture in
 * place of the live canvas, then the report below it. A plain Ctrl+P prints the
 * live canvas as it is on screen.
 */
export async function printReport(graph: TocGraph): Promise<void> {
  const area = document.getElementById("toc-canvas");
  // If the picture fails, the live canvas prints instead.
  const url = await canvasDataUrl(graph, "png").catch(() => null);
  if (area === null || url === null) {
    window.print();
    return;
  }
  const image = document.createElement("img");
  image.className = "toc-print-image";
  image.alt = "The theory of change canvas";
  image.src = url;
  await image.decode();
  area.append(image);
  window.addEventListener("afterprint", () => image.remove(), { once: true });
  window.print();
}

export function downloadReferences(graph: TocGraph): void {
  // UTF-8 BOM so spreadsheet apps decode non-ASCII titles correctly.
  triggerTextDownload(exportName(graph, "csv"), `\uFEFF${referencesCsv(graph)}`, "text/csv");
}

/** The graph as the API returns it, for other tools. */
export function downloadJson(graph: TocGraph): void {
  triggerTextDownload(exportName(graph, "json"), JSON.stringify(graph, null, 2), "application/json");
}

export function downloadDrawio(graph: TocGraph): void {
  triggerTextDownload(exportName(graph, "drawio"), drawioXml(graph), "application/xml");
}
