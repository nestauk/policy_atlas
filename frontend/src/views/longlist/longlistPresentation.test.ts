import { describe, expect, it } from "vitest";

import {
  shortlistedFirst,
  AUTHORITY_LABELS,
  GRID_COLUMN_LINES,
  LEVEL_WORDS,
  LINE_NAMES,
  PROFILE_LINE_KEYS,
  authorityWords,
  leverDefinitionFor,
  leverLabel,
  leverLine,
  constraintNotices,
  countsLine,
  documentFacts,
  groupCountWords,
  uncoveredLevers,
  seeInSourcesWords,
  midSentence,
  outcomeCoverage,
  outcomeCoverageLines,
  targetCoverage,
  targetCoverageWords,
  deliveredLeadInParts,
  leverLineParts,
  actsOnParts,
  documentsToggleWords,
  exclusionLine,
  EXCLUDE_OPTION_TOOLTIP,
  EXCLUDE_TOOLTIP,
  profilePoints,
  leverCount,
  rowMetaFields,
  countryWithArticle,
  deliveredLeadIn,
  documentsSummary,
  evidenceSignal,
  middleSummary,
  originLabel,
  placeWithDetail,
  MATURITY_WORDS,
  holdsPlace,
} from "./longlistPresentation";

// Task 046: the card's new lines and the lever definition by version.
describe("longlist presentation (task 046)", () => {
  const byVersion = {
    lever_types_v2: [{ key: "subsidise", definition: "pay for it, or fund a provider" }],
    lever_types_v1: [{ key: "subsidise", definition: "pay for it" }],
  };

  it("shows the definition of the version a group's options were typed under", () => {
    const typedV1 = [{ taxonomy_version: "lever_types_v1" }, { taxonomy_version: "lever_types_v1" }];
    expect(leverDefinitionFor("subsidise", typedV1, byVersion, "Current.")).toBe("Pay for it.");
  });

  it("falls back to the current definition for a mixed or unknown version", () => {
    const mixed = [{ taxonomy_version: "lever_types_v1" }, { taxonomy_version: "lever_types_v2" }];
    expect(leverDefinitionFor("subsidise", mixed, byVersion, "Current.")).toBe("Current.");
    expect(leverDefinitionFor("subsidise", [{ taxonomy_version: null }], byVersion, "Current.")).toBe("Current.");
    expect(leverDefinitionFor("subsidise", [], undefined, "Current.")).toBe("Current.");
  });

  // Task 046, amendment 3 (§ 2.5): the lever line, the secondary types after "with".
  it("words the lever line with its secondary types joined by and", () => {
    // Round 12 (owner): the lever nouns in one sentence.
    expect(leverLine("subsidise", ["inform", "provide a service"])).toBe("Lever: subsidies, with information and services.");
    expect(leverLine("subsidise", ["inform"])).toBe("Lever: subsidies, with information.");
    expect(leverLine("regulate", [])).toBe("Lever: regulation.");
    expect(leverLine("subsidise", undefined)).toBe("Lever: subsidies.");
    expect(leverLine(null, [])).toBe("Lever: other.");
  });

  // Task 046, amendment 4 (R83): the header never says "0 excluded".
  it("words the counts line without an excluded part at zero", () => {
    const counts = { options: 40, themes: 12, excluded: 3, no_in_scope: 2 } as Parameters<typeof countsLine>[0];
    expect(countsLine(counts)).toBe("40 options in 12 themes · 3 excluded · 2 with no in-scope evidence");
    expect(countsLine({ ...counts, excluded: 0, no_in_scope: 0 })).toBe("40 options in 12 themes");
    // Before the theme step runs the line carries no theme count.
    expect(countsLine({ ...counts, themes: 0, excluded: 0, no_in_scope: 0 })).toBe("40 options");
    expect(countsLine({ ...counts, options: 1, themes: 1, excluded: 0 })).toBe(
      "1 option in 1 theme · 2 with no in-scope evidence",
    );
  });

  // Round 11 (review finding 4): the lever or the theme, the evidence's
  // first part, "No in-scope evidence" last; relations and the rest of the
  // signal are the card's.
  it("gives a row's one meta line in a fixed order", () => {
    const option = {
      origin: "added_by_you",
      relations: [{ kind: "part_of", other_option_id: "x", other_name: "A bundle" }],
      search_pending: false,
      document_count: 9,
      evaluated_count: 5,
      evaluated_countries: [],
      outcomes_evaluated: 1,
      outcomes_total: 2,
      no_in_scope_evidence: false,
      shortlist: { state: "proposed", reason: "r" },
    } as unknown as Parameters<typeof rowMetaFields>[0];
    expect(rowMetaFields(option, "Subsidise", null)).toEqual(["Subsidise", "9 documents"]);
    expect(rowMetaFields({ ...option, document_count: 1 }, null, null)).toEqual(["1 document"]);
    expect(rowMetaFields({ ...option, search_pending: true }, null, null)).toEqual(["searching for its evidence…"]);
    expect(
      rowMetaFields({ ...option, document_count: 0, no_in_scope_evidence: true }, null, "Staying in work"),
    ).toEqual(["Staying in work", "No documents yet", "No in-scope evidence"]);
  });

  // Round 10, C1: one origin vocabulary; the card adds the report's section.
  it("words the card's origin in the list's vocabulary, with the report section", () => {
    expect(originLabel("from_evidence_search", "What works")).toBe("from your report · What works");
    expect(originLabel("from_evidence_search", "  ")).toBe("from your report");
    expect(originLabel("suggested")).toBe("suggested by Policy Atlas");
    expect(originLabel("clustered", "ignored")).toBe("found in the evidence");
  });

  // Round 10, lead ruling on finding 7: "Middle" said once for the unmarked lines.
  it("summarises the unmarked profile lines once", () => {
    expect(middleSummary(6, 8)).toBe("Middle on 6 of 8");
    expect(middleSummary(8, 8)).toBe("No line stands out");
    expect(middleSummary(0, 8)).toBe("Middle on 0 of 8");
  });
});

// Task 046, amendment 2 (R40, R41, R42, R43, R44): the words of the profile.
describe("longlist presentation (amendment 2 words)", () => {
  it("names the nine lines and ambition exactly, Potential impact last", () => {
    expect(PROFILE_LINE_KEYS.map((key) => LINE_NAMES[key])).toEqual([
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Who decides",
      "Dependencies",
      "Coordination requirements",
      "Delivery complexity",
      "Potential impact",
    ]);
    expect(LINE_NAMES.ambition).toBe("Ambition");
    expect(GRID_COLUMN_LINES).toContain("potential_impact");
  });

  it("gives each line exactly the table's level words", () => {
    const words = (key: keyof typeof LEVEL_WORDS) => [LEVEL_WORDS[key].less, LEVEL_WORDS[key].more];
    expect(words("cost")).toEqual(["Cheaper", "Costlier"]);
    expect(words("time_to_set_up")).toEqual(["Quicker", "Slower"]);
    expect(words("time_to_effect")).toEqual(["Quicker", "Slower"]);
    expect(words("workforce")).toEqual(["Lower", "Higher"]);
    expect(words("who_decides")).toEqual([null, null]);
    expect(words("dependencies")).toEqual([null, null]);
    expect(words("coordination")).toEqual(["Lower", "Higher"]);
    expect(words("delivery_complexity")).toEqual(["Simpler", "More complex"]);
    expect(words("potential_impact")).toEqual(["Lower", "Higher"]);
    expect(words("ambition")).toEqual(["Smaller", "Bigger"]);
    const all = Object.values(LEVEL_WORDS).flatMap((pair) => [pair.less, pair.more]);
    expect(all.filter((word) => word !== null)).toHaveLength(16);
    expect(all).not.toContain("Middle");
  });

  it("offers the eight lines that carry a mark as grid columns, ambition first", () => {
    expect(GRID_COLUMN_LINES.map((key) => LINE_NAMES[key])).toEqual([
      "Ambition",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
      "Potential impact",
    ]);
  });

  it("words the authority labels, naming the body when there is one", () => {
    expect(AUTHORITY_LABELS).toEqual({
      within_your_power: "Within your power",
      needs_action_by: "Needs action by another body",
      unclear: "Unclear who can act",
    });
    expect(authorityWords({ label: "needs_action_by", body: "the Treasury", reason: "It sets the rate." })).toBe(
      "Needs action by the Treasury",
    );
    expect(authorityWords({ label: "needs_action_by", body: null, reason: null })).toBe("Needs action by another body");
    expect(authorityWords({ label: "unclear", reason: "Not stated." })).toBe("Unclear who can act");
  });

  it("labels a row with its lever only", () => {
    expect(leverLabel({ primary_lever_type: "provide a service", ambition: "more" } as never)).toBe("Provide a service");
    expect(leverLabel({ primary_lever_type: null, ambition: "less" } as never)).toBe("Other");
  });
});

// Task 046, amendment 4 (R76-R82; S36): the card's new words.
describe("longlist presentation (amendment 4)", () => {
  const signal = {
    document_count: 29,
    evaluated_count: 17,
    evaluated_countries: [
      { country: "United Kingdom", documents: 6 },
      { country: "Denmark", documents: 3 },
      { country: "Germany", documents: 2 },
    ],
    outcomes_evaluated: 2,
    outcomes_total: 3,
  };

  it("words the evidence signal in its four forms", () => {
    expect(evidenceSignal(signal)).toBe(
      "17 documents evaluated it · 12 more describe it · Evaluated in the United Kingdom and 2 other countries · Measures 2 of your 3 outcomes",
    );
    expect(evidenceSignal({ ...signal, evaluated_count: 0, document_count: 3 })).toBe(
      "No evaluations, 3 documents describe it",
    );
    expect(evidenceSignal({ ...signal, evaluated_countries: [] })).toContain(" · No evaluation gives a place · ");
    expect(evidenceSignal({ ...signal, document_count: 0, evaluated_count: 0 })).toBe("No documents yet");
  });

  it("words the signal's small cases", () => {
    const one = { ...signal, document_count: 1, evaluated_count: 1, outcomes_evaluated: 1, outcomes_total: 1 };
    expect(evidenceSignal({ ...one, evaluated_countries: [{ country: "Denmark", documents: 1 }] })).toBe(
      "1 document evaluated it · Evaluated in Denmark · Measures 1 of your 1 outcome",
    );
    expect(evidenceSignal({ ...one, evaluated_countries: signal.evaluated_countries.slice(0, 2) })).toContain(
      "Evaluated in the United Kingdom and Denmark",
    );
    expect(evidenceSignal({ ...signal, evaluated_countries: signal.evaluated_countries.slice(0, 3) })).toContain(
      "and 2 other countries",
    );
    expect(
      evidenceSignal({ ...signal, evaluated_countries: [signal.evaluated_countries[0], signal.evaluated_countries[1], ...signal.evaluated_countries.slice(0, 0)] }),
    ).toContain("Evaluated in the United Kingdom and Denmark");
    expect(evidenceSignal({ ...signal, outcomes_evaluated: 0 })).toMatch(/ · Measures none of your outcomes$/);
  });

  it("puts 'the' before the countries that take it", () => {
    for (const name of ["United States", "Netherlands", "Philippines", "Czech Republic", "Gambia", "Bahamas", "Maldives", "Dominican Republic", "Democratic Republic of the Congo", "Republic of the Congo"]) {
      expect(countryWithArticle(name)).toBe(`the ${name}`);
    }
    expect(countryWithArticle("Denmark")).toBe("Denmark");
  });

  // Round 12 (owner): a document's one Meta line of facts.
  it("words the documents toggle", () => {
    expect(documentsToggleWords(false, 2, 4)).toBe("Show 6 documents · 2 evaluated it · 4 describe it");
    expect(documentsToggleWords(false, 1, 1)).toBe("Show 2 documents · 1 evaluated it · 1 describes it");
    expect(documentsToggleWords(false, 0, 1)).toBe("Show 1 document · 1 describes it");
    expect(documentsToggleWords(false, 3, 0)).toBe("Show 3 documents · 3 evaluated it");
    expect(documentsToggleWords(true, 2, 4)).toBe("Hide documents");
  });


  it("words the lead-in in its three forms", () => {
    expect(deliveredLeadIn([])).toBe("It typically involves:");
    expect(deliveredLeadIn(undefined)).toBe("It typically involves:");
    expect(deliveredLeadIn(["school"])).toBe("Delivered in schools. It typically involves:");
    expect(deliveredLeadIn(["school", "home"])).toBe("Delivered in schools and at home. It typically involves:");
    expect(deliveredLeadIn(["workplace", "online"])).toBe("Delivered at work and online. It typically involves:");
    expect(deliveredLeadIn(["clinic"])).toBe("Delivered in clinics. It typically involves:");
    expect(deliveredLeadIn(["library"])).toBe("Delivered in libraries. It typically involves:");
    expect(deliveredLeadIn(["church"])).toBe("Delivered in churches. It typically involves:");
    expect(deliveredLeadIn(["Delivered through"])).not.toMatch(/^Delivered through/);
  });

  it("words the callout's six cases and shows nothing for a pass", () => {
    const judgement = (constraint_id: string, verdict: "passes" | "breaks" | "cannot_check") => ({
      constraint_id,
      constraint_text: `Rule ${constraint_id}.`,
      verdict,
      reason: "Because.",
    });
    const guess = (constraint_id: string, leaning: "likely_meets" | "likely_falls_short" | "cannot_say") => ({
      constraint_id,
      constraint_text: `Rule ${constraint_id}.`,
      guess: "A guess.",
      leaning,
    });
    expect(
      constraintNotices(
        [judgement("req-1", "breaks"), judgement("req-2", "cannot_check"), judgement("req-3", "passes"), judgement("relevant", "breaks")],
        [guess("pref-1", "likely_falls_short"), guess("pref-2", "cannot_say"), guess("pref-3", "likely_meets")],
      ).map(({ tone, word, text }) => [tone, word, text]),
    ).toEqual([
      ["red", "Breaks", '"Rule req-1". Because.'],
      ["grey", "Cannot check", '"Rule req-2". Because.'],
      ["navy", "May fall short", '"Rule pref-1". A guess.'],
      ["grey", "Cannot check", '"Rule pref-2". A guess.'],
    ]);
  });

  it("words the documents summary and a document's place", () => {
    expect(documentsSummary(29)).toBe("Documents · 29 · read from titles and abstracts only");
    expect(documentsSummary(0)).toBe("Documents · 0");
    expect(placeWithDetail("United Kingdom", "south-west England")).toEqual({
      place: "United Kingdom",
      detail: "south-west England",
    });
    expect(placeWithDetail("Denmark", "denmark").detail).toBeNull();
    expect(placeWithDetail("not stated", null)).toEqual({ place: "place not stated", detail: null });
  });
});

describe("MATURITY_WORDS (task 055)", () => {
  it("words the four rungs", () => {
    expect(MATURITY_WORDS).toEqual({
      proposal_only: "Proposed, not yet implemented",
      described: "Implemented, not yet evaluated",
      evaluated: "Evaluated",
      reviewed: "Evaluated, including a review",
    });
  });
});

describe("places (task 055)", () => {
  it("holds a place for a pick and a user place, none for set-aside", () => {
    expect(holdsPlace({ shortlist: { state: "set_aside", reason: null } })).toBe(false);
    expect(holdsPlace({ shortlist: { state: "proposed", reason: "r" } })).toBe(true);
  });
});

// Round 12 (owner): one order for a group and a grid cell.
describe("shortlistedFirst", () => {
  it("puts the held first and keeps each part's own order, without changing the input", () => {
    const rows = ["a", "B", "c", "D", "e"];
    const held = (row: string) => row === row.toUpperCase();
    expect(shortlistedFirst(rows, held)).toEqual(["B", "D", "a", "c", "e"]);
    expect(rows).toEqual(["a", "B", "c", "D", "e"]);
    expect(shortlistedFirst([], held)).toEqual([]);
  });
});

// Round 12 (owner): the count line counts the levers too.
describe("the count line's levers", () => {
  const counts = { options: 24, themes: 5, excluded: 0, no_in_scope: 0 } as Parameters<typeof countsLine>[0];
  it("says the themes and the levers, in the singular for one", () => {
    expect(countsLine(counts, 3)).toBe("24 options in 5 themes and 3 levers");
    expect(countsLine({ ...counts, themes: 1 }, 1)).toBe("24 options in 1 theme and 1 lever");
    expect(countsLine({ ...counts, themes: 0 }, 2)).toBe("24 options in 2 levers");
    expect(countsLine(counts)).toBe("24 options in 5 themes");
  });

  it("counts the distinct lever types of the included options only", () => {
    expect(
      leverCount([
        { state: "included", primary_lever_type: "regulate" },
        { state: "included", primary_lever_type: "regulate" },
        { state: "included", primary_lever_type: "inform" },
        { state: "included", primary_lever_type: null },
        { state: "excluded", primary_lever_type: "tax or charge" },
      ] as Parameters<typeof leverCount>[0]),
    ).toBe(2);
    expect(leverCount(undefined)).toBe(0);
  });
});

// Round 12 (owner): "What it could take" shut is one sentence of the lines
// that are not in the middle.
describe("profilePoints", () => {
  it("gives the ambition first and the impact second, then each other marked line in order", () => {
    expect(
      profilePoints("more", [
        { key: "cost", mark: null },
        { key: "time_to_set_up", mark: "more" },
        { key: "workforce", mark: "more" },
        { key: "delivery_complexity", mark: "less" },
        { key: "potential_impact", mark: "more" },
      ]),
    ).toEqual(["More ambitious", "Higher potential impact", "Longer to set up", "Higher workforce requirements", "Simpler to deliver"]);
  });

  it("says Average ambition and Average potential impact when both are in the middle or missing", () => {
    expect(profilePoints(null, [{ key: "cost", mark: "more" }, { key: "potential_impact", mark: null }])).toEqual([
      "Average ambition",
      "Average potential impact",
      "Costs more",
    ]);
    expect(profilePoints(undefined, [{ key: "time_to_effect", mark: "less" }])).toEqual([
      "Average ambition",
      "Average potential impact",
      "Shows results sooner",
    ]);
    expect(profilePoints("less", [{ key: "potential_impact", mark: "less" }, { key: "coordination", mark: "more" }])).toEqual([
      "Less ambitious",
      "Lower potential impact",
      "Needs more coordination",
    ]);
  });

  it("ends with average on the rest when every other line is in the middle", () => {
    expect(profilePoints(null, [{ key: "cost", mark: null }, { key: "workforce", mark: null }])).toEqual([
      "Average ambition",
      "Average potential impact",
      "Average on cost, time, workforce, coordination and delivery",
    ]);
  });

  it("leaves out a line it has no words for, and every point has no full stop", () => {
    const points = profilePoints(null, [{ key: "who_decides", mark: "more" }, { key: "cost", mark: "less" }]);
    expect(points).toEqual(["Average ambition", "Average potential impact", "Costs less"]);
    for (const point of points) expect(point).not.toMatch(/\.$/);
  });
});

// Round 12 (owner): "Breaks your decision" was unclear.
// Round 13 (owner): the tooltips end at "under Excluded".
describe("Exclude's tooltips", () => {
  it("say what Exclude does and where the options stay", () => {
    expect(EXCLUDE_TOOLTIP).toBe("Excludes these options from being shortlisted. They stay on the longlist under Excluded.");
    expect(EXCLUDE_OPTION_TOOLTIP).toBe("Excludes this option from being shortlisted. It stays on the longlist under Excluded.");
  });
});

describe("exclusionLine", () => {
  it("says the user's own exclusion as Excluded by you, the reason after it when there is one", () => {
    expect(exclusionLine({ by: "user", constraint: "your decision", reason: "Out of our remit" })).toBe(
      "Excluded by you · Out of our remit",
    );
    expect(exclusionLine({ by: "user", constraint: "your decision", reason: "  " })).toBe("Excluded by you");
  });

  it("says a constraint's exclusion as Breaks with the constraint, then the reason", () => {
    expect(
      exclusionLine({
        by: "constrain",
        constraint: "Only include options a local authority can fund directly.",
        reason: "A local authority cannot withdraw a national benefit directly.",
      }),
    ).toBe(
      'Breaks "Only include options a local authority can fund directly" · A local authority cannot withdraw a national benefit directly.',
    );
  });
});

// Round 12 (lead): an outcome after "Measures " reads mid-sentence.
describe("midSentence", () => {
  it("lowers the first letter unless the word is an acronym", () => {
    expect(midSentence("Sustained employment or training at 12 months")).toBe("sustained employment or training at 12 months");
    expect(midSentence("NEET rate at 6 months")).toBe("NEET rate at 6 months");
    expect(midSentence("prevalence of obesity")).toBe("prevalence of obesity");
    expect(midSentence("A")).toBe("A");
  });
});

// Round 12 (owner): a document's facts as a small labelled list.
describe("documentFacts", () => {
  const base = {
    role: "evaluated" as const,
    place: "United Kingdom",
    evidence_type: "randomised or quasi-experimental study",
    measured: "NEET rate at 6 months",
    tried_on_kind: "16-24 year-olds",
  };
  it("lists Where, Type, Targeted and Measures in order, the type through the shared label", () => {
    expect(documentFacts(base)).toEqual([
      { label: "Where", value: "United Kingdom" },
      { label: "Type", value: "Randomised or quasi-experimental study" },
      { label: "Targeted", value: "16-24 year-olds" },
      { label: "Measures", value: "NEET rate at 6 months" },
    ]);
  });
  it("says Discusses on a document that only describes, recommends or mentions it", () => {
    for (const role of ["described", "recommended", "mentioned"] as const) {
      expect(documentFacts({ ...base, role }).at(-1)).toEqual({ label: "Discusses", value: "NEET rate at 6 months" });
    }
  });
  it("leaves out a row with no value, and an unstated place", () => {
    expect(documentFacts({ ...base, place: "not stated", evidence_type: null, tried_on_kind: null, measured: null })).toEqual([]);
    expect(documentFacts({ ...base, place: "other", evidence_type: " ", tried_on_kind: "", measured: null })).toEqual([
      { label: "Where", value: "Other place" },
    ]);
  });
});

// Round 12 (owner): how the documents cover the plan's outcomes.
describe("outcomeCoverage", () => {
  it("counts the evaluations that measure each outcome and the other documents that discuss it, in the plan's order", () => {
    const documents = [
      { role: "evaluated" as const, measured: "NEET rate at 6 months" },
      { role: "evaluated" as const, measured: " neet rate at 6 months " },
      { role: "described" as const, measured: "NEET rate at 6 months" },
      { role: "recommended" as const, measured: "Wellbeing" },
      { role: "evaluated" as const, measured: null },
    ];
    expect(outcomeCoverage(["Attendance", "NEET rate at 6 months", "Wellbeing"], documents)).toEqual([
      { outcome: "Attendance", measured: 0, discussed: 0 },
      { outcome: "NEET rate at 6 months", measured: 2, discussed: 1 },
      { outcome: "Wellbeing", measured: 0, discussed: 1 },
    ]);
  });

  it("words the coverage as lines, leaving out a line with none", () => {
    expect(outcomeCoverageLines({ measured: 6, discussed: 7 })).toEqual(["Measured in 6", "Discussed in 7"]);
    expect(outcomeCoverageLines({ measured: 1, discussed: 0 })).toEqual(["Measured in 1"]);
    expect(outcomeCoverageLines({ measured: 0, discussed: 3 })).toEqual(["Discussed in 3"]);
    expect(outcomeCoverageLines({ measured: 0, discussed: 0 })).toEqual(["Not covered"]);
  });
});

// Round 12 (owner): the plan's target in the documents.
describe("targetCoverage", () => {
  const kinds = (...names: (string | null)[]) => names.map((tried_on_kind) => ({ tried_on_kind }));

  it("counts the documents that target the unit directly out of those with a known target", () => {
    const coverage = targetCoverage("16-24 year-olds", kinds("16-24 year-olds", " 16-24 Year-Olds ", "parents", "outlets", null));
    expect(coverage).toEqual({ unit: "16-24 year-olds", targeted: 2, known: 4 });
    expect(targetCoverageWords(coverage)).toBe("Directly targeted in 2");
    expect(targetCoverageWords({ targeted: 1 })).toBe("Directly targeted in 1");
    expect(targetCoverageWords(targetCoverage("children", kinds("outlets")))).toBe("Not directly targeted");
  });

});

// Round 12 (owner): the takeaway words of the lever and the setting are strong.
describe("leverLineParts and deliveredLeadInParts", () => {
  const strong = (parts: { text: string; strong: boolean }[]) => parts.filter((part) => part.strong).map((part) => part.text);
  it("marks the lever nouns strong", () => {
    expect(strong(leverLineParts("regulate", ["provide a service", "inform"]))).toEqual(["regulation", "services", "information"]);
    expect(leverLineParts("regulate", []).map((part) => part.text).join("")).toBe("Lever: regulation.");
    expect(strong(leverLineParts(null, []))).toEqual(["other"]);
  });
  it("marks the setting strong and leaves a settingless lead-in plain", () => {
    expect(strong(deliveredLeadInParts(["school", "home"]))).toEqual(["in schools and at home"]);
    expect(deliveredLeadInParts(["school"]).map((part) => part.text).join("")).toBe("Delivered in schools. It typically involves:");
    expect(strong(deliveredLeadInParts([]))).toEqual([]);
  });
});

// Round 12 (owner): whom the option acts on, the model's call (`acts_on`).
describe("actsOnParts", () => {
  const text = (parts: { text: string }[]) => parts.map((part) => part.text).join("");
  const strong = (parts: { text: string; strong: boolean }[]) => parts.filter((part) => part.strong).map((part) => part.text);
  it("says whom it acts on with the names strong, and nothing when there are none", () => {
    const parts = actsOnParts(["food outlets", "parents", "councils"]);
    expect(text(parts)).toBe("Acts on food outlets, parents and councils.");
    expect(strong(parts)).toEqual(["food outlets", "parents", "councils"]);
    expect(actsOnParts([])).toEqual([]);
    expect(actsOnParts(undefined)).toEqual([]);
  });
  it("names six, then and k more", () => {
    expect(text(actsOnParts(["a", "b", "c", "d", "e", "f", "g", "h"]))).toBe("Acts on a, b, c, d, e, f and 2 more.");
    expect(text(actsOnParts(["a", "b", "c", "d", "e", "f"]))).toBe("Acts on a, b, c, d, e and f.");
  });
  it("sits between the setting and the lead-in's close", () => {
    expect(text(deliveredLeadInParts(["school"], actsOnParts(["parents"])))).toBe(
      "Delivered in schools. Acts on parents. It typically involves:",
    );
    expect(text(deliveredLeadInParts([], actsOnParts(["parents"])))).toBe("Acts on parents. It typically involves:");
  });
});

// Round 12 (owner): the link to the option's documents in Sources.
describe("seeInSourcesWords", () => {
  it("names the count, in the singular for one", () => {
    expect(seeInSourcesWords(12)).toBe("See these 12 documents in Sources");
    expect(seeInSourcesWords(1)).toBe("See this document in Sources");
  });
});

// Round 13 (owner): a group's count says how many are shortlisted.
describe("groupCountWords and uncoveredLevers", () => {
  it("adds the shortlisted count when there is one", () => {
    expect(groupCountWords(12, 3)).toBe("12 options · 3 shortlisted");
    expect(groupCountWords(1, 1)).toBe("1 option · 1 shortlisted");
    expect(groupCountWords(12, 0)).toBe("12 options");
  });
  // Round 14 (owner): an excluded option still covers its lever; only the
  // lever types no option carries at all are listed.
  it("lists the lever types no option carries, included or excluded, never Other", () => {
    expect(
      uncoveredLevers(["regulate", "inform", "devolve"], [
        { primary_lever_type: "regulate" },
        { primary_lever_type: "inform" },
        { primary_lever_type: null },
      ]),
    ).toEqual(["devolve"]);
  });
});
