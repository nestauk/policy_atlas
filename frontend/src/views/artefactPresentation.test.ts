import { describe, expect, it } from "vitest";

import { mockArtefact } from "../mock/fixtures";
import { mostRelevantSources, sectionNavLabel, artefactMarkdown, downloadFilename, fullReportIntro, splitLeadColon, cardEvidenceChipLabels } from "./artefactPresentation";

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

describe("artefactMarkdown", () => {
  const artefact = {
    title: "Policy options for healthier childhoods",
    summary: "Universal provision helps.",
    summary_status: "verified" as const,
    sections: [
      {
        title: "Implications",
        role: "conclusions" as const,
        blocks: [{ prose: "Pair food with travel." }],
      },
      {
        title: "What appears to help",
        role: "key_findings" as const,
        blocks: [
          {
            prose: "Universal breakfast helps children eat.",
            claims: [
              {
                claim_type: "citation",
                span: [9, 25],
                citations: [{ n: 1 }],
              },
            ],
          },
        ],
      },
    ],
    references: [{ n: 1, title: "A study", year: 2022, venue: "BMJ Open" }],
  };

  it("writes title, part labels, sections in report order, citation markers, and references", () => {
    const markdown = artefactMarkdown(artefact);
    expect(markdown).toContain("# Policy options for healthier childhoods");
    expect(markdown).toContain("## Executive summary");
    expect(markdown).not.toContain("**In brief**");
    expect(markdown.indexOf("### What appears to help")).toBeLessThan(markdown.indexOf("### Implications"));
    expect(markdown).toContain("Universal breakfast helps[1] children eat.");
    expect(markdown).toContain("## Full report");
    expect(markdown).not.toContain("group the evidence by theme");
    expect(markdown).toContain("### References");
    expect(markdown).toContain("1. A study (2022, BMJ Open)");
  });

  it("omits an unverified summary — same honesty as the on-screen callout", () => {
    const markdown = artefactMarkdown({ ...artefact, summary_status: "pending" });
    expect(markdown).not.toContain("Universal provision helps.");
  });

  it("puts citation numbers back into mock artefact prose and keeps the reference list", () => {
    const markdown = artefactMarkdown(mockArtefact);
    expect(markdown).toContain("support more consistent breakfast consumption[1]");
    expect(markdown).toContain("### References");
    expect(markdown).toMatch(/^1\. /m);
  });

  it("bolds lead-colon key-findings bullets and lists most relevant sources before the body", () => {
    const markdown = artefactMarkdown({
      title: "Report",
      summary: "Takeaway.",
      summary_status: "verified",
      sections: [
        {
          title: "Key findings",
          role: "key_findings",
          blocks: [
            {
              prose: "- Universal breakfast helped: eleven of fifteen evaluations reported higher uptake.\n- No colon on this line.",
            },
          ],
        },
        {
          title: "What works",
          role: "standard",
          blocks: [
            {
              prose: "Body prose.",
              claims: [
                {
                  citations: [
                    {
                      n: 1,
                      source_id: "src-1",
                      source_title: "A breakfast study",
                      appraisal_label: "high",
                      evidence_type: "Trial",
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
      references: [{ n: 1, title: "A breakfast study" }],
    });
    expect(markdown).toContain("- **Universal breakfast helped:** eleven of fifteen evaluations reported higher uptake.");
    expect(markdown).toContain("- No colon on this line.");
    expect(markdown.indexOf("### Most relevant sources")).toBeGreaterThan(markdown.indexOf("### Key findings"));
    expect(markdown.indexOf("### Most relevant sources")).toBeLessThan(markdown.indexOf("### What works"));
    expect(markdown).toContain("**A breakfast study**");
  });
});

describe("fullReportIntro", () => {
  it("returns null for zero sections", () => {
    expect(fullReportIntro(0)).toBeNull();
  });

  it("returns the generated intro when supplied", () => {
    expect(fullReportIntro(3, "Custom intro text.")).toBe("Custom intro text.");
  });

  it("returns null when no generated intro is available", () => {
    expect(fullReportIntro(3)).toBeNull();
  });
});

describe("cardEvidenceMeta", () => {
  it("falls back to claim citations when rollup metadata is absent", () => {
    expect(
      cardEvidenceChipLabels({
        strength: null,
        design: null,
        claims: [
          {
            citations: [
              { appraisal_label: "Strong", evidence_type: "RCTs and Quasi-Experimental Studies" },
            ],
          },
        ],
      }),
    ).toEqual(["Strong", "RCTs and Quasi-Experimental Studies"]);
  });
});

describe("splitLeadColon", () => {
  it("splits on the first colon-space and leaves no-colon lines alone", () => {
    expect(splitLeadColon("Universal breakfast helped: eleven of fifteen.")).toEqual({
      lead: "Universal breakfast helped",
      rest: "eleven of fifteen.",
    });
    expect(splitLeadColon("No colon here.")).toBeNull();
    expect(splitLeadColon(": leading colon is not a lead")).toBeNull();
  });
});

describe("artefactMarkdown case studies", () => {
  it("renders case study cards in the executive summary as markdown", () => {
    const markdown = artefactMarkdown({
      title: "Report",
      sections: [
        {
          title: "Case studies",
          role: "case_studies",
          blocks: [],
          cards: [
            { title: "Finland — School meals", prose: "Universal provision since 1948.", strength: "high", design: "Trial", since_year: 1948 },
            { title: "Sweden — Free lunches", prose: "Nutritional gains observed.", strength: null, design: null, since_year: null },
          ],
        },
      ],
    });
    expect(markdown).toContain("### Case studies");
    expect(markdown).toContain("**Finland — School meals**");
    expect(markdown).toContain("Universal provision since 1948.");
    expect(markdown).toContain("high · Trial · Since 1948");
    expect(markdown).toContain("**Sweden — Free lunches**");
  });

  it("omits case studies section when no cards", () => {
    const markdown = artefactMarkdown({
      title: "Report",
      sections: [
        { title: "Case studies", role: "case_studies", blocks: [], cards: [] },
      ],
    });
    expect(markdown).not.toContain("### Case studies");
    expect(markdown).not.toContain("**Finland");
  });

  it("includes grounded most-relevant notes in the markdown download", () => {
    const markdown = artefactMarkdown({
      title: "Report",
      summary_status: "verified",
      sections: [
        {
          title: "Findings",
          role: "key_findings",
          blocks: [
            {
              prose: "A cited claim.",
              claims: [
                {
                  claim_type: "citation",
                  span: [0, 13],
                  citations: [
                    {
                      n: 1,
                      source_id: "src-1",
                      source_title: "Landmark trial",
                      appraisal_label: "high",
                      evidence_type: "Trial",
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
      most_relevant_notes: [{ source_id: "src-1", note: "A grounded note about the trial." }],
    });
    expect(markdown).toContain("A grounded note about the trial.");
  });

  it("bolds case-study results before inserting citation markers", () => {
    const markdown = artefactMarkdown({
      title: "Report",
      sections: [
        {
          title: "Case studies",
          role: "case_studies",
          blocks: [],
          cards: [
            {
              title: "Finland",
              prose: "Lead sentence. Result sentence here.",
              result_claim_id: "result-1",
              claims: [
                {
                  claim_id: "lead-1",
                  claim_type: "citation",
                  span: [0, 14],
                  citations: [{ n: 1, source_id: "a", source_title: "Source A" }],
                },
                {
                  claim_id: "result-1",
                  claim_type: "citation",
                  span: [15, 36],
                  citations: [{ n: 2, source_id: "b", source_title: "Source B" }],
                },
              ],
            },
          ],
        },
      ],
    });
    expect(markdown).toContain("Lead sentence.[1] **Result sentence here.**");
  });
});

describe("mostRelevantSources with notes", () => {
  it("passes through the note field untouched", () => {
    const sections = [
      {
        title: "Findings",
        blocks: [{ claims: [{ citations: [{ source_id: "a", source_title: "Source A" }] }] }],
      },
    ];
    const result = mostRelevantSources(sections);
    expect(result[0].note).toBeUndefined();
  });
});

describe("mostRelevantSources case-study cards", () => {
  it("counts citations from case-study card claims", () => {
    const sections = [
      {
        title: "Case studies",
        role: "case_studies",
        blocks: [],
        cards: [
          {
            title: "Finland",
            claims: [
              {
                citations: [
                  { source_id: "card-source", source_title: "Card Source", appraisal_label: "Strong" },
                ],
              },
            ],
          },
        ],
      },
      {
        title: "Findings",
        blocks: [{ claims: [{ citations: [{ source_id: "block-source", source_title: "Block Source" }] }] }],
      },
    ];
    const result = mostRelevantSources(sections);
    expect(result).toHaveLength(2);
    expect(result.map((source) => source.sourceId).sort()).toEqual(["block-source", "card-source"]);
  });

  it("counts a claim once when a card re-tasks its section block's claim", () => {
    const sharedClaim = {
      claim_id: "claim-1",
      citations: [{ source_id: "shared-source", source_title: "Shared Source" }],
    };
    const sections = [
      {
        title: "Case studies",
        role: "case_studies",
        blocks: [{ claims: [sharedClaim] }],
        cards: [{ title: "Finland", claims: [sharedClaim] }],
      },
    ];
    const result = mostRelevantSources(sections);
    expect(result).toHaveLength(1);
    expect(result[0].citationCount).toBe(1);
  });
});

describe("downloadFilename", () => {
  it("slugs the title and keeps a safe fallback", () => {
    expect(downloadFilename("What retains early years staff?", "md")).toBe(
      "what-retains-early-years-staff.md",
    );
    expect(downloadFilename("???", "pdf")).toBe("report.pdf");
  });
});
