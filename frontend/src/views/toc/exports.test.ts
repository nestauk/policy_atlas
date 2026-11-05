import { describe, expect, it } from "vitest";

import { drawioXml, referencesCsv, theoryJson } from "./exports";
import { box, BOXES, tocGraphFixture } from "./fixture";
import { layoutToc, visibleLinkIds } from "./tocModel";

describe("theory exports", () => {
  it("lists each reference with the connections that cite it", () => {
    const rows = referencesCsv(tocGraphFixture()).split("\r\n");
    expect(rows[0]).toBe('"Number","Citation","Title","Authors","Year","Publisher","URL","Connections","Quote"');
    expect(rows).toHaveLength(4);
    expect(rows[1]).toContain('"#3"');
    expect(rows[3]).toContain('"#3, #5"');
    expect(rows[1]).toContain('"Ann Smith; Bo Lee"');
  });

  it("writes the graph as JSON that reads back the same", () => {
    const graph = tocGraphFixture();
    expect(JSON.parse(theoryJson(graph))).toEqual(graph);
  });

  it("draws one shape per box and one joined arrow per connection, escaped", () => {
    const graph = tocGraphFixture({ boxes: [...BOXES.slice(0, -1), box(BOXES.length, BOXES.at(-1)!.layer, 'Fewer "sweets" & <snacks>')] });
    const doc = new DOMParser().parseFromString(drawioXml(graph), "application/xml");
    expect(doc.querySelector("parsererror")).toBeNull();
    const placed = layoutToc(graph).boxes.map((item) => item.id);
    const vertices = [...doc.querySelectorAll('mxCell[vertex="1"]')].filter((cell) => placed.includes(cell.id));
    expect(vertices).toHaveLength(placed.length);
    const arrows = [...doc.querySelectorAll("mxCell[source]")];
    expect(arrows).toHaveLength([...visibleLinkIds(graph, "all")].length);
    for (const arrow of arrows) {
      expect(placed).toContain(arrow.getAttribute("source"));
      expect(placed).toContain(arrow.getAttribute("target"));
    }
    // The attribute holds HTML, so the box's own text is escaped once more inside it.
    expect(vertices.map((v) => v.getAttribute("value")).join()).toContain("Fewer &quot;sweets&quot; &amp; &lt;snacks&gt;");
  });
});
