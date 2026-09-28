import { describe, expect, it } from "vitest";

import { beatSentence } from "./runProgress";

describe("beatSentence", () => {
  it("suggest: counts suggestions, appends the from-report clause when positive", () => {
    expect(beatSentence("suggest", { suggested: 1, from_report: 0 })).toBe("Suggested 1 option");
    expect(beatSentence("suggest", { suggested: 4, from_report: 2 })).toBe(
      "Suggested 4 options · 2 from your evidence search",
    );
    expect(beatSentence("suggest", { from_report: 2 })).toBeNull();
  });

  it("option_searches: null on missing total, a dedicated zero line, else a ratio", () => {
    expect(beatSentence("option_searches", {})).toBeNull();
    expect(beatSentence("option_searches", { total: 0 })).toBe("No option searches to run");
    expect(beatSentence("option_searches", { total: 3, finished: 3, failed: 0 })).toBe(
      "Searched for 3 of 3 options",
    );
    expect(beatSentence("option_searches", { total: 1, finished: 1, failed: 0 })).toBe(
      "Searched for 1 of 1 option",
    );
    expect(beatSentence("option_searches", { total: 3, finished: 2, failed: 1 })).toBe(
      "Searched for 2 of 3 options · 1 failed",
    );
  });

  it("inherit: null on missing documents, pluralises documents and linked tasks", () => {
    expect(beatSentence("inherit", { links: 1, failed_links: 0 })).toBeNull();
    expect(beatSentence("inherit", { documents: 1, links: 1, failed_links: 0 })).toBe(
      "1 document from 1 linked task",
    );
    expect(beatSentence("inherit", { documents: 5, links: 2, failed_links: 0 })).toBe(
      "5 documents from 2 linked tasks",
    );
    expect(beatSentence("inherit", { documents: 5, links: 2, failed_links: 1 })).toBe(
      "5 documents from 2 linked tasks · 1 could not be read",
    );
  });

  it("extract_interventions: null when both counts absent, omits a null part", () => {
    expect(beatSentence("extract_interventions", {})).toBeNull();
    expect(beatSentence("extract_interventions", { documents: 10, records: 3 })).toBe(
      "Read 10 abstracts · 3 interventions covered",
    );
    expect(beatSentence("extract_interventions", { documents: 1 })).toBe("Read 1 abstract");
    expect(beatSentence("extract_interventions", { records: 1 })).toBe("1 intervention covered");
  });

  it("longlist: null on missing options, omits each null part", () => {
    expect(beatSentence("longlist", {})).toBeNull();
    expect(
      beatSentence("longlist", { options: 6, themes: 2, unclustered: 4, not_an_option: 1 }),
    ).toBe("6 options in 2 themes · 4 records unclustered · 1 not an option");
    expect(beatSentence("longlist", { options: 1, themes: 1 })).toBe("1 option in 1 theme");
    expect(beatSentence("longlist", { options: 3 })).toBe("3 options");
  });

  it("constrain: null when both counts absent, omits a null part", () => {
    expect(beatSentence("constrain", {})).toBeNull();
    expect(beatSentence("constrain", { excluded: 2, no_in_scope: 1 })).toBe(
      "2 excluded · 1 with no in-scope evidence",
    );
    expect(beatSentence("constrain", { excluded: 2 })).toBe("2 excluded");
    expect(beatSentence("constrain", { no_in_scope: 1 })).toBe("1 with no in-scope evidence");
  });

  it("never returns a beat for an Evidence search stage", () => {
    expect(beatSentence("acquire", { found: 40, relevant: 12 })).toBeNull();
  });

  it("never returns a beat for an unknown stage", () => {
    expect(beatSentence("some_future_stage", { total: 5 })).toBeNull();
  });
});
