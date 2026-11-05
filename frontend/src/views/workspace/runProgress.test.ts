import { STAGE_COUNTS } from "../../mock/fixtures";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import type { PlanDraft, StageEntry, StageLiveness } from "../../store";
import {
  cardRows,
  collapsedStatusLine,
  currentRow,
  FINISHED_NOTICE,
  finishedNotice,
  formatElapsed,
  formatMinutes,
  isFinished,
  READY_WORDS,
  rowCounts,
  rowDetail,
  rowLink,
  rowLiveness,
  rowSeconds,
  runFinishedSignpost,
  runningCardCopy,
  walkKind,
} from "./runProgress";

const T0 = "2026-11-05T10:00:00Z";
const at = (seconds: number) => new Date(Date.parse(T0) + seconds * 1000).toISOString();

function entry(overrides: Partial<StageEntry> & Pick<StageEntry, "stage" | "status">): StageEntry {
  // The server puts the done row's counts on the frame (task 058, N17); the
  // test derives them from the summary with the mock's copy of that table.
  const counts = STAGE_COUNTS[overrides.stage].flatMap(([key, noun]) => {
    const value = overrides.summary?.[key];
    return typeof value === "number" ? [{ value, noun }] : [];
  });
  return { label: "Searching and screening", startedAt: T0, counts, ...overrides };
}

/** The server's plan steps for a standard Evidence search (STAGE_ROW,
 *  STAGE_PRESENTATION in `api/stage_vocabulary.py`). */
function standardPlan(): PlanDraft {
  const step = (stage: string, label: string, row: string) => ({ stage, label, row, blurb: "" }) as never;
  return {
    steps: [
      step("acquire", "Searching and screening", "search_screen"),
      step("screen", "Searching and screening", "search_screen"),
      step("classify", "Classifying", "categorise"),
      step("appraise", "Classifying", "categorise"),
      step("ingest", "Reading the full texts", "ingest"),
      step("characterise", "Mapping", "characterise"),
      step("select", "Shortlisting", "select"),
      step("synthesise", "Writing", "synthesise"),
    ],
  } as unknown as PlanDraft;
}

function tick(overrides: Partial<StageLiveness> = {}): StageLiveness {
  return { activity: "40 of 118 classified", heartbeat: false, dropped: 0, occurredAt: T0, ...overrides };
}

describe("cardRows — rows from the server's plan steps (task 058, D5)", () => {
  it("groups the steps by row: six Evidence search rows, upcoming before anything runs", () => {
    const rows = cardRows([], standardPlan(), "running");
    expect(rows.map((row) => row.label)).toEqual([
      "Searching and screening",
      "Classifying",
      "Reading the full texts",
      "Mapping",
      "Shortlisting",
      "Writing",
    ]);
    expect(rows.every((row) => row.state === "upcoming")).toBe(true);
    expect(rows[0].stages).toEqual(["acquire", "screen"]);
  });

  it("keeps search and screen one row in progress between them, then done", () => {
    const searched = [entry({ stage: "acquire", status: "completed", seconds: 30 })];
    expect(cardRows(searched, standardPlan(), "running")[0].state).toBe("progress");
    const screened = [...searched, entry({ stage: "screen", status: "completed", startedAt: at(30), seconds: 34 })];
    const rows = cardRows(screened, standardPlan(), "running");
    expect(rows[0].state).toBe("done");
    expect(rows[1].state).toBe("upcoming");
  });

  it("never numbers rounds: a second search pass stays on the same row", () => {
    const stages = [
      entry({ stage: "acquire", status: "completed", seconds: 20 }),
      entry({ stage: "screen", status: "completed", startedAt: at(20), seconds: 10 }),
      entry({ stage: "acquire", status: "started", startedAt: at(30) }),
    ];
    const rows = cardRows(stages, standardPlan(), "running");
    expect(rows.filter((row) => row.label.startsWith("Searching"))).toHaveLength(1);
    expect(rows[0].state).toBe("progress");
    expect(rows.some((row) => /Round/.test(row.label))).toBe(false);
  });

  it("builds rows from the frames alone when the stream has no plan steps (scoping), with none to come", () => {
    const stages = [
      entry({ stage: "inherit", label: "Reading the linked search", status: "completed", summary: { documents: 1 } }),
      entry({ stage: "suggest", label: "Suggesting options", status: "completed", summary: { suggested: 12 } }),
      entry({ stage: "option_searches", label: "Searching for each option", status: "started" }),
    ];
    const rows = cardRows(stages, null, "running");
    expect(rows.map((row) => [row.label, row.state])).toEqual([
      ["Reading the linked search", "done"],
      ["Suggesting options", "done"],
      ["Searching for each option", "progress"],
    ]);
  });

  it("reads failed and skipped rows as such", () => {
    const rows = cardRows(
      [
        entry({ stage: "acquire", status: "completed" }),
        entry({ stage: "screen", status: "completed" }),
        entry({ stage: "classify", label: "Classifying", status: "failed" }),
      ],
      standardPlan(),
      "failed",
    );
    expect(rows[1].state).toBe("failed");
  });
});

describe("rowCounts — the counts the server names per stage", () => {
  it("shows found and relevant on the merged row, in table order", () => {
    const [row] = cardRows(
      [
        entry({ stage: "acquire", status: "completed", summary: { acquired: 312, results: 900 } }),
        entry({ stage: "screen", status: "completed", summary: { relevant: 118, screened_out: 317 } }),
      ],
      standardPlan(),
      "running",
    );
    expect(rowCounts(row)).toEqual(["312 found", "118 relevant"]);
  });

  it("formats thousands and shows the two counts of the option-search fan-out", () => {
    const [row] = cardRows(
      [entry({ stage: "option_searches", label: "Searching for each option", status: "completed", summary: { total: 12, sources: 2410, finished: 12 } })],
      null,
      "running",
    );
    expect(rowCounts(row)).toEqual(["12 searches", "2,410 sources"]);
  });

  it("shows nothing for a key the summary does not carry, and never a string", () => {
    const [row] = cardRows(
      [entry({ stage: "acquire", status: "completed", summary: { reason: "x" } })],
      null,
      "succeeded",
    );
    expect(rowCounts(row)).toEqual([]);
  });
});

describe("rowSeconds — wall time per row (N5)", () => {
  it("uses the one stage's seconds on a single-stage row", () => {
    const rows = cardRows(
      [entry({ stage: "characterise", label: "Mapping", status: "completed", seconds: 48 })],
      standardPlan(),
      "running",
    );
    expect(rowSeconds(rows.find((row) => row.label === "Mapping")!, 0)).toBe(48);
  });

  it("spans a merged row from the first stage's start to the last stage's end", () => {
    const [row] = cardRows(
      [
        entry({ stage: "acquire", status: "completed", startedAt: at(0), seconds: 30 }),
        entry({ stage: "screen", status: "completed", startedAt: at(40), seconds: 24 }),
      ],
      standardPlan(),
      "running",
    );
    expect(rowSeconds(row, 0)).toBe(64);
  });

  it("counts an in-progress row up from its start", () => {
    const [row] = cardRows([entry({ stage: "acquire", status: "started", startedAt: at(0) })], standardPlan(), "running");
    expect(rowSeconds(row, Date.parse(at(75)))).toBe(75);
  });
});

describe("rowLink — where a done row points", () => {
  const done = (stages: StageEntry[]) => cardRows(stages, standardPlan(), "running");
  const searchScreen = [
    entry({ stage: "acquire", status: "completed" }),
    entry({ stage: "screen", status: "completed" }),
  ];

  it("links Sources after searching and screening; Landscape on categorising only once mapping is done", () => {
    const early = done([...searchScreen, entry({ stage: "classify", label: "Classifying", status: "completed" }), entry({ stage: "appraise", label: "Classifying", status: "completed" })]);
    expect(rowLink(early[0], early, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(rowLink(early[1], early, "t1", "evidence_search", false)).toBeNull();
    const mapped = done([
      ...searchScreen,
      entry({ stage: "classify", label: "Classifying", status: "completed" }),
      entry({ stage: "appraise", label: "Classifying", status: "completed" }),
      entry({ stage: "characterise", label: "Mapping", status: "completed" }),
    ]);
    expect(rowLink(mapped[1], mapped, "t1", "evidence_search", false)?.label).toBe("Landscape");
    // Mapping's own link is the themes, the Sources tab's first view (owner, polish round 2).
    expect(rowLink(mapped[3], mapped, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/sources", label: "Themes" });
  });

  it("gives Shortlisting and Reading no link, Writing the report", () => {
    const rows = done([
      ...searchScreen,
      entry({ stage: "ingest", label: "Reading the full texts", status: "completed" }),
      entry({ stage: "select", label: "Shortlisting", status: "completed" }),
      entry({ stage: "synthesise", label: "Writing", status: "completed" }),
    ]);
    const byLabel = (label: string) => rows.find((row) => row.label === label)!;
    expect(rowLink(byLabel("Reading the full texts"), rows, "t1", "evidence_search", false)).toBeNull();
    expect(rowLink(byLabel("Shortlisting"), rows, "t1", "evidence_search", false)).toBeNull();
    expect(rowLink(byLabel("Writing"), rows, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/result", label: "Report" });
  });

  it("links nothing on a scoping walk's rows", () => {
    const rows = done(searchScreen);
    expect(rowLink(rows[0], rows, "t1", "longlist", false)).toBeNull();
  });
});

describe("the activity line", () => {
  it("reads the newest tick among the row's stages, in the server's words", () => {
    const [row] = cardRows([entry({ stage: "screen", status: "started" })], standardPlan(), "running");
    const liveness = {
      acquire: tick({ activity: "searching · 312 found so far", occurredAt: at(1) }),
      screen: tick({ activity: "screening 61 new abstracts · 107 relevant so far", occurredAt: at(5) }),
    };
    expect(rowLiveness(row, liveness)?.activity).toBe("screening 61 new abstracts · 107 relevant so far");
  });

  it("puts the writer's section before the activity on the strip", () => {
    expect(rowDetail(tick({ section: "Section 3 of 7 · Costs and funding", activity: "Writing" }))).toBe(
      "Section 3 of 7 · Costs and funding",
    );
    expect(rowDetail(tick({ activity: "40 of 118 classified" }))).toBe("40 of 118 classified");
    expect(rowDetail(undefined)).toBeNull();
  });
});

describe("elapsed time in words", () => {
  it("formats the card's durations", () => {
    expect(formatElapsed(13)).toBe("13 s");
    expect(formatElapsed(64)).toBe("1 min 4 s");
    expect(formatElapsed(372)).toBe("6 min 12 s");
    expect(formatElapsed(360)).toBe("6 min");
    expect(formatElapsed(3840)).toBe("1 h 4 min");
  });

  it("formats the strip's and the task list's minutes", () => {
    expect(formatMinutes(45)).toBe("45 s");
    expect(formatMinutes(372)).toBe("6 min");
    expect(formatMinutes(14 * 60 + 59)).toBe("14 min");
  });
});

describe("the collapsed line and the current row", () => {
  it("names the row in progress, else the last that ran", () => {
    const rows = cardRows(
      [entry({ stage: "acquire", status: "completed" }), entry({ stage: "screen", status: "completed" })],
      standardPlan(),
      "paused",
    );
    expect(currentRow(rows)?.label).toBe("Searching and screening");
    expect(collapsedStatusLine("paused", rows, "6 min 12 s")).toBe("PAUSED · Searching and screening · 6 min 12 s");
  });
});

describe("walk kinds and finished words (tasks 045, 055, 058)", () => {
  it("reads the walk kind from the capability, the purpose and the stages", () => {
    expect(walkKind("evidence_search", [])).toBe("evidence_search");
    expect(walkKind("options_scoping", [])).toBe("baseline");
    expect(walkKind("options_scoping", [], "targeted")).toBe("option_search");
    expect(walkKind("options_scoping", [], "shortlist")).toBe("shortlist");
    expect(walkKind("options_scoping", [{ stage: "suggest" } as never])).toBe("longlist");
    expect(walkKind("options_scoping", [{ stage: "theme" }, { stage: "shortlist" }] as never, null)).toBe("longlist");
    expect(walkKind("options_scoping", [{ stage: "shortlist" } as never], null)).toBe("shortlist");
  });

  it("words the top line by status; a degraded shortlist walk stopped, a degraded finish done", () => {
    expect(runningCardCopy("running")).toEqual({ tone: "running", eyebrow: "RUNNING" });
    expect(runningCardCopy("paused")).toEqual({ tone: "paused", eyebrow: "PAUSED" });
    expect(runningCardCopy("degraded")).toEqual({ tone: "done", eyebrow: "DONE" });
    expect(runningCardCopy("degraded", "shortlist")).toEqual({ tone: "stopped", eyebrow: "STOPPED" });
    expect(isFinished("degraded")).toBe(true);
    expect(isFinished("failed")).toBe(false);
  });

  it("keeps the finished notices and the strip's ready words per walk", () => {
    expect(READY_WORDS.evidence_search).toBe("Report ready");
    expect(READY_WORDS.longlist).toBe("The longlist is ready");
    expect(FINISHED_NOTICE.shortlist.before).toContain("proposed a shortlist");
    expect(finishedNotice("shortlist", "degraded").before).toBe(
      "Policy Atlas could not propose a shortlist. Your places are unchanged. Open the",
    );
    expect(runFinishedSignpost("t1", "degraded", "shortlist")?.href).toBe("/tasks/t1/result?view=shortlist");
    expect(runFinishedSignpost("t1", "succeeded")?.message).toBe(
      "Evidence search is finished. You can read the report in the Result tab.",
    );
  });
});

/** The client stage labels N17 retired: the server is the one source of stage
 *  copy, so none of these may come back outside tests and the mock. */
const RETIRED_STAGE_LABELS = [
  "Searching sources",
  "Screening for relevance",
  "Sorting by evidence type",
  "Appraising quality",
  "Mapping the landscape",
  "Writing the report",
];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "mock" || name === "gen" ? [] : sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("one source of stage copy (task 058, N17)", () => {
  it("leaves none of the old stage labels in frontend/src outside tests and the mock", () => {
    const root = "src";
    const hits = sourceFiles(root).flatMap((path) => {
      const text = readFileSync(path, "utf8");
      return RETIRED_STAGE_LABELS.filter((label) => text.includes(label)).map((label) => `${relative(root, path)}: ${label}`);
    });
    expect(hits).toEqual([]);
  });
});
