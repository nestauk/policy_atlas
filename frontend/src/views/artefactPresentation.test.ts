import { describe, expect, it } from "vitest";

import { mostRelevantSources, sectionNavLabel } from "./artefactPresentation";

describe("mostRelevantSources", () => {
  it("ranks by how many claims cite each source, not how many citation rows", () => {
    const sections = [
      {
        title: "Findings",
        blocks: [
          {
            claims: [
              // One claim citing source A twice: counts once for this claim.
              {
                citations: [
                  { source_id: "a", source_title: "Source A" },
                  { source_id: "a", source_title: "Source A" },
                ],
              },
              { citations: [{ source_id: "a", source_title: "Source A" }] },
              { citations: [{ source_id: "b", source_title: "Source B" }] },
            ],
          },
        ],
      },
    ];
    const result = mostRelevantSources(sections);
    expect(result.map((s) => [s.sourceId, s.citationCount])).toEqual([
      ["a", 2],
      ["b", 1],
    ]);
  });

  it("returns at most `limit` sources", () => {
    const sections = [
      {
        title: "Findings",
        blocks: [
          {
            claims: ["a", "b", "c", "d"].map((id) => ({
              citations: [{ source_id: id, source_title: `Source ${id}` }],
            })),
          },
        ],
      },
    ];
    expect(mostRelevantSources(sections)).toHaveLength(3);
    expect(mostRelevantSources(sections, 2)).toHaveLength(2);
  });

  it("breaks a genuine three-way tie by appraisal tier, then title", () => {
    const sections = [
      {
        title: "Findings",
        blocks: [
          {
            claims: [
              { citations: [{ source_id: "z-low", source_title: "Zeta report", appraisal_label: "low" }] },
              { citations: [{ source_id: "a-high", source_title: "Alpha report", appraisal_label: "high" }] },
              // Same tier as z-low ("low"), so this pair breaks on title.
              { citations: [{ source_id: "b-low", source_title: "Beta report", appraisal_label: "low" }] },
            ],
          },
        ],
      },
    ];
    const result = mostRelevantSources(sections);
    // All three have citationCount 1: high tier first, then low-tier ties broken A→Z.
    expect(result.map((s) => s.sourceId)).toEqual(["a-high", "b-low", "z-low"]);
  });

  it("sorts an unknown or absent appraisal label last, without throwing", () => {
    const sections = [
      {
        title: "Findings",
        blocks: [
          {
            claims: [
              { citations: [{ source_id: "unknown-tier", source_title: "Unknown tier", appraisal_label: "not_a_real_tier" }] },
              { citations: [{ source_id: "no-tier", source_title: "No tier at all" }] },
              { citations: [{ source_id: "high-tier", source_title: "High tier", appraisal_label: "high" }] },
            ],
          },
        ],
      },
    ];
    expect(() => mostRelevantSources(sections)).not.toThrow();
    const result = mostRelevantSources(sections);
    expect(result[0].sourceId).toBe("high-tier");
    // The unclassified ones sort after, ordered between themselves by title.
    expect(result.slice(1).map((s) => s.sourceId)).toEqual(["no-tier", "unknown-tier"]);
  });

  it("lists each citing section once, in page order", () => {
    const sections = [
      {
        title: "Introduction",
        blocks: [{ claims: [{ citations: [{ source_id: "a", source_title: "Source A" }] }] }],
      },
      {
        title: "Discussion",
        blocks: [
          {
            claims: [
              { citations: [{ source_id: "a", source_title: "Source A" }] },
              { citations: [{ source_id: "a", source_title: "Source A" }] },
            ],
          },
        ],
      },
    ];
    const [source] = mostRelevantSources(sections);
    expect(source.citedInSections).toEqual(["Introduction", "Discussion"]);
  });

  it("returns an empty array for empty or undefined sections", () => {
    expect(mostRelevantSources([])).toEqual([]);
    expect(mostRelevantSources(undefined)).toEqual([]);
  });
});

describe("sectionNavLabel", () => {
  it("returns nav_label when present", () => {
    expect(sectionNavLabel({ title: "A very long section title indeed", nav_label: "Short" })).toBe("Short");
  });

  it("falls back to the title when nav_label is absent, null, or empty", () => {
    expect(sectionNavLabel({ title: "Findings" })).toBe("Findings");
    expect(sectionNavLabel({ title: "Findings", nav_label: null })).toBe("Findings");
    expect(sectionNavLabel({ title: "Findings", nav_label: "" })).toBe("Findings");
  });

  it("returns a title at or under max unchanged", () => {
    const title = "Exactly28CharsLongTitleXX";
    expect(title.length).toBeLessThanOrEqual(28);
    expect(sectionNavLabel({ title })).toBe(title);
  });

  it("clips a longer title on a word boundary with an ellipsis", () => {
    const title = "This is a much longer section title than the limit allows";
    const result = sectionNavLabel({ title });
    expect(result.endsWith("…")).toBe(true);
    expect(result).not.toContain(title);
  });

  it("never clips beyond max + 1 characters", () => {
    const titles = [
      "This is a much longer section title than the limit allows",
      "Supercalifragilisticexpialidocious extra long word section",
      "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z 1 2 3 4 5",
    ];
    for (const title of titles) {
      const result = sectionNavLabel({ title });
      expect(result.length).toBeLessThanOrEqual(29);
    }
  });
});
