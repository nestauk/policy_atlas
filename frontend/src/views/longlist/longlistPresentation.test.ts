import { describe, expect, it } from "vitest";

import {
  AUTHORITY_LABELS,
  GRID_COLUMN_LINES,
  LEVEL_WORDS,
  LINE_NAMES,
  PROFILE_LINE_KEYS,
  authorityWords,
  servesOutcome,
  leverDefinitionFor,
  leverLabel,
  leverLine,
  constraintNotices,
  countsLine,
  rowMetaParts,
  countryWithArticle,
  deliveredLeadIn,
  documentsSummary,
  evidenceOpener,
  evidenceSignal,
  noOutcomeMeasuredLine,
  outcomeCountLabel,
  placeWithDetail,
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
    expect(leverLine("subsidise", ["inform", "provide a service"])).toBe("Lever: Subsidise, with Inform and Provide a service.");
    expect(leverLine("subsidise", ["inform"])).toBe("Lever: Subsidise, with Inform.");
    expect(leverLine("subsidise", [])).toBe("Lever: Subsidise.");
    expect(leverLine("subsidise", undefined)).toBe("Lever: Subsidise.");
    expect(leverLine(null, [])).toBe("Lever: none fits.");
  });

  // Task 046, amendment 4 (R83): the header never says "0 excluded".
  it("words the counts line without an excluded part at zero", () => {
    const counts = { options: 40, themes: 12, excluded: 3, no_in_scope: 2 } as Parameters<typeof countsLine>[0];
    expect(countsLine(counts)).toBe("40 options in 12 themes · 3 excluded · 2 with no in-scope evidence");
    expect(countsLine({ ...counts, excluded: 0, no_in_scope: 0 })).toBe("40 options in 12 themes");
    expect(countsLine({ ...counts, options: 1, themes: 1, excluded: 0 })).toBe(
      "1 option in 1 theme · 2 with no in-scope evidence",
    );
  });

  // R85: the signal's parts close the grey line; pending search stands in for them.
  it("ends a row's meta parts with the evidence signal and drops the document count", () => {
    const option = {
      origin: "clustered",
      relations: [],
      search_pending: false,
      document_count: 3,
      evaluated_count: 0,
      evaluated_countries: [],
      outcomes_evaluated: 0,
      outcomes_total: 2,
    } as unknown as Parameters<typeof rowMetaParts>[0];
    expect(rowMetaParts(option)).toEqual(["No evaluations, 3 documents describe it"]);
    expect(rowMetaParts({ ...option, search_pending: true })).toEqual(["searching for its evidence…"]);
    expect(rowMetaParts({ ...option, origin: "added_by_you", document_count: 0 })).toEqual([
      "added by you",
      "No documents yet",
    ]);
  });
});

// Task 046, amendment 2 (R40, R41, R42, R43, R44): the words of the profile.
describe("longlist presentation (amendment 2 words)", () => {
  it("names the eight lines and ambition exactly", () => {
    expect(PROFILE_LINE_KEYS.map((key) => LINE_NAMES[key])).toEqual([
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Who decides",
      "Dependencies",
      "Coordination requirements",
      "Delivery complexity",
    ]);
    expect(LINE_NAMES.ambition).toBe("Ambition");
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
    expect(words("ambition")).toEqual(["Smaller", "Bigger"]);
    const all = Object.values(LEVEL_WORDS).flatMap((pair) => [pair.less, pair.more]);
    expect(all.filter((word) => word !== null)).toHaveLength(14);
    expect(all).not.toContain("Middle");
  });

  it("offers the seven lines that carry a mark as grid columns, ambition first", () => {
    expect(GRID_COLUMN_LINES.map((key) => LINE_NAMES[key])).toEqual([
      "Ambition",
      "Cost",
      "Time to set up",
      "Time to effect",
      "Workforce requirements",
      "Coordination requirements",
      "Delivery complexity",
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

  it("matches a served outcome with case and spacing folded", () => {
    expect(servesOutcome(["NEET rate at 6 months"], " neet rate at 6 months ")).toBe(true);
    expect(servesOutcome(["Attendance"], "Wellbeing")).toBe(false);
    expect(servesOutcome(undefined, "Wellbeing")).toBe(false);
  });

  it("labels a row with its lever only", () => {
    expect(leverLabel({ primary_lever_type: "provide a service", ambition: "more" } as never)).toBe("Provide a service");
    expect(leverLabel({ primary_lever_type: null, ambition: "less" } as never)).toBe("No lever fits");
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

  it("words the evidence opener in its three forms", () => {
    expect(evidenceOpener(17, 29)).toBe("Evaluated in 17 documents. 12 more describe or recommend it.");
    expect(evidenceOpener(2, 2)).toBe("Evaluated in 2 documents.");
    expect(evidenceOpener(0, 4)).toBe("No evaluations. 4 documents describe or recommend it.");
    expect(evidenceOpener(0, 0)).toBe("No document names this option yet.");
  });

  it("words the outcomes lines", () => {
    expect(noOutcomeMeasuredLine(3)).toBe("No evaluation measured any of your three outcomes.");
    expect(noOutcomeMeasuredLine(12)).toBe("No evaluation measured any of your 12 outcomes.");
    expect(noOutcomeMeasuredLine(1)).toBe("No evaluation measured any of your outcome.");
    expect(outcomeCountLabel(11)).toBe("11 evaluations");
    expect(outcomeCountLabel(1)).toBe("1 evaluation");
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
      ).map(({ tone, chip, text }) => [tone, chip, text]),
    ).toEqual([
      ["red", "breaks", 'Breaks "Rule req-1". Because.'],
      ["soft", "cannot check", 'Cannot check "Rule req-2". Because.'],
      ["yellow", "may fall short", '"Rule pref-1". A guess.'],
      ["soft", "cannot check", 'Cannot check "Rule pref-2". A guess.'],
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
