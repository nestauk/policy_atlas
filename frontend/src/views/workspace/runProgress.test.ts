import { describe, expect, it } from "vitest";

import type { StageEntry } from "../../store";
import {
  beatSentence,
  collapsedStatusLine,
  FINISHED_NOTICE,
  finishedNotice,
  rowLabel,
  runFinishedSignpost,
  runningCardCopy,
  stageRows,
  walkKind,
} from "./runProgress";

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

  it("longlist: null on missing options, omits each null part, never reads a theme count", () => {
    // Task 046: theme moved to its own step, so a `themes` count in the
    // longlist summary (an older frame) is ignored here.
    expect(beatSentence("longlist", {})).toBeNull();
    expect(
      beatSentence("longlist", { options: 6, themes: 2, unclustered: 4, not_an_option: 1 }),
    ).toBe("6 options · 4 records unclustered · 1 not an option");
    expect(beatSentence("longlist", { options: 1 })).toBe("1 option");
    expect(beatSentence("longlist", { options: 3 })).toBe("3 options");
  });

  it("option_profile: no beat, whatever its summary counts", () => {
    expect(beatSentence("option_profile", {})).toBeNull();
    expect(beatSentence("option_profile", { options: 6, typed: 5, kept: 1, invalid: 1 })).toBeNull();
  });

  it("theme: null on missing themes, else the theme count", () => {
    expect(beatSentence("theme", {})).toBeNull();
    expect(beatSentence("theme", { themes: 2, no_theme: 1 })).toBe("2 themes");
    expect(beatSentence("theme", { themes: 1 })).toBe("1 theme");
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

describe("full-text reading progress (task 056, S5)", () => {
  it("beatSentence ingest: read count once any is read, fetched before, else the label alone", () => {
    expect(beatSentence("ingest", { fetched: 5, parsed: 3, total: 10 })).toBe(
      "Reading the full texts: 3 of 10 read",
    );
    expect(beatSentence("ingest", { fetched: 4, parsed: 0, total: 10 })).toBe(
      "Reading the full texts: 4 fetched",
    );
    expect(beatSentence("ingest", { fetched: 0, parsed: 0, total: 10 })).toBeNull();
    expect(beatSentence("ingest", {})).toBeNull();
    expect(beatSentence("ingest", undefined)).toBeNull();
    // The completed frame's own summary carries no live counts.
    expect(beatSentence("ingest", { eligible: 10, ingested: 7 })).toBeNull();
  });

  const started: StageEntry = { stage: "ingest", label: "Reading the full texts", status: "started" };

  it("an in-flight ingest row reads as its live counts, on the row and the collapsed line", () => {
    const rows = stageRows([started], null, {
      ingest: { note: "3 of 10 read, 5 fetched.", occurredAt: "2026-11-02T10:00:00Z", fetched: 5, parsed: 3, total: 10 },
    });
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe("Reading the full texts");
    expect(rowLabel(rows[0])).toBe("Reading the full texts: 3 of 10 read");
    expect(collapsedStatusLine("running", rows, "1m")).toBe(
      "RUNNING · Reading the full texts: 3 of 10 read · 1m",
    );
  });

  it("without counts, or once finished, the row reads as its label", () => {
    const noCounts = stageRows([started], null, {
      ingest: { note: "n", occurredAt: "2026-11-02T10:00:00Z" },
    });
    expect(rowLabel(noCounts[0])).toBe("Reading the full texts");
    expect(rowLabel(stageRows([started], null)[0])).toBe("Reading the full texts");
    const done = stageRows([{ ...started, status: "completed", summary: { eligible: 10 } }], null, {
      ingest: { note: "n", occurredAt: "2026-11-02T10:00:00Z", fetched: 10, parsed: 8, total: 10 },
    });
    expect(done[0].summary).toEqual({ eligible: 10 });
    expect(rowLabel(done[0])).toBe("Reading the full texts");
  });
});

describe("walkKind — the shortlist walk (task 055)", () => {
  it("names a shortlist walk by its purpose and by its stage", () => {
    expect(walkKind("options_scoping", [], "shortlist")).toBe("shortlist");
    expect(walkKind("options_scoping", [{ stage: "shortlist" } as never], null)).toBe("shortlist");
    // The longlist walk ends in a shortlist step: still a longlist walk.
    expect(walkKind("options_scoping", [{ stage: "theme" }, { stage: "shortlist" }] as never, null)).toBe("longlist");
    expect(runningCardCopy("running", "shortlist").title).toBe("Proposing a shortlist…");
    expect(runningCardCopy("succeeded", "shortlist").title).toBe("The shortlist is proposed");
    expect(FINISHED_NOTICE.shortlist.before).toContain("proposed a shortlist");
  });

  it("says the proposal failed when a shortlist walk ends degraded", () => {
    expect(runningCardCopy("degraded", "shortlist")).toEqual({
      tone: "stopped",
      eyebrow: "STOPPED",
      title: "Policy Atlas could not propose",
    });
    expect(finishedNotice("shortlist", "degraded")).toEqual({
      before: "Policy Atlas could not propose a shortlist. Your places are unchanged. Open the",
      after: "tab.",
    });
    expect(runFinishedSignpost("t1", "degraded", "shortlist")?.message).toMatch(
      /^Policy Atlas could not propose a shortlist\. Your places are unchanged\. Open the .+ tab\.$/,
    );
    expect(runFinishedSignpost("t1", "degraded", "shortlist")?.href).toBe("/tasks/t1/result?view=shortlist");
    // A degraded longlist walk keeps its done words.
    expect(runningCardCopy("degraded", "longlist").tone).toBe("done");
    expect(finishedNotice("shortlist", "succeeded")).toBe(FINISHED_NOTICE.shortlist);
  });
});
