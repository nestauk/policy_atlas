import { STAGE_COUNTS } from "../../mock/fixtures";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import type { PlanDraft, StageEntry, StageLiveness } from "../../store";
import {
  cardRows,
  currentRow,
  endedLine,
  formatElapsed,
  isFinished,
  rowCounts,
  rowDetail,
  rowLink,
  rowLiveness,
  rowSeconds,
  STALLED_LINE,
  stepCount,
  traceWords,
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
      step("ingest", "Collecting the full texts", "ingest"),
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
      "Collecting the full texts",
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

  // Lead, round 8 (superseding round 4's "after Mapping"): a done
  // Classifying row links to the landscape at once.
  it("links Sources after searching and screening; Landscape on categorising at once", () => {
    const early = done([...searchScreen, entry({ stage: "classify", label: "Classifying", status: "completed" }), entry({ stage: "appraise", label: "Classifying", status: "completed" })]);
    expect(rowLink(early[0], early, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(rowLink(early[1], early, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/sources/landscape", label: "Landscape" });
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
      entry({ stage: "ingest", label: "Collecting the full texts", status: "completed" }),
      entry({ stage: "select", label: "Shortlisting", status: "completed" }),
      entry({ stage: "synthesise", label: "Writing", status: "completed" }),
    ]);
    const byLabel = (label: string) => rows.find((row) => row.label === label)!;
    expect(rowLink(byLabel("Collecting the full texts"), rows, "t1", "evidence_search", false)).toBeNull();
    expect(rowLink(byLabel("Shortlisting"), rows, "t1", "evidence_search", false)).toBeNull();
    expect(rowLink(byLabel("Writing"), rows, "t1", "evidence_search", false)).toEqual({ href: "/tasks/t1/result", label: "Report" });
  });

  // Owner, round 11: a longlist walk searches, screens and classifies as an
  // Evidence search does, so those rows link as an Evidence search's do.
  it("links a longlist walk's done Searching and Screening to Sources and Classifying to the landscape", () => {
    const rows = cardRows(
      [
        entry({ stage: "suggest", label: "Suggesting options", status: "completed" }),
        entry({ stage: "acquire", label: "Searching", status: "completed" }),
        entry({ stage: "screen", label: "Screening", status: "completed" }),
        entry({ stage: "classify", label: "Classifying", status: "completed" }),
        entry({ stage: "appraise", label: "Classifying", status: "completed" }),
        entry({ stage: "extract_interventions", label: "Reading the abstracts", status: "started" }),
      ],
      null,
      "running",
    );
    const byLabel = (label: string) => rows.find((row) => row.label === label)!;
    expect(rowLink(byLabel("Searching"), rows, "t1", "longlist", false)).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(rowLink(byLabel("Screening"), rows, "t1", "longlist", false)).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(rowLink(byLabel("Classifying"), rows, "t1", "longlist", false)).toEqual({
      href: "/tasks/t1/sources/landscape",
      label: "Landscape",
    });
  });

  // Owner, round 12: done scoping rows link where their output is.
  it("links a longlist walk's done rows that make the longlist to it, and Shortlisting to the shortlist", () => {
    const rows = cardRows(
      [
        entry({ stage: "inherit", label: "Reading the linked search", status: "completed" }),
        entry({ stage: "suggest", label: "Suggesting options", status: "completed" }),
        entry({ stage: "option_searches", label: "Searching for each option", status: "completed" }),
        entry({ stage: "extract_interventions", label: "Reading the abstracts", status: "completed" }),
        entry({ stage: "longlist", label: "Clustering into options", status: "completed" }),
        entry({ stage: "option_profile", label: "Estimating what each option would take", status: "completed" }),
        entry({ stage: "constrain", label: "Applying your constraints", status: "completed" }),
        entry({ stage: "theme", label: "Grouping into themes", status: "completed" }),
        entry({ stage: "shortlist", label: "Shortlisting", status: "completed" }),
      ],
      null,
      "succeeded",
    );
    const link = (label: string) => rowLink(rows.find((row) => row.label === label)!, rows, "t1", "longlist", false);
    for (const label of [
      "Suggesting options",
      "Clustering into options",
      "Estimating what each option would take",
      "Applying your constraints",
      "Grouping into themes",
    ]) {
      expect(link(label)).toEqual({ href: "/tasks/t1/result", label: "Longlist" });
    }
    expect(link("Shortlisting")).toEqual({ href: "/tasks/t1/result?view=shortlist", label: "Shortlist" });
    expect(link("Reading the linked search")).toBeNull();
    // The option searches' results are in the Sources table (lead, round 12).
    expect(link("Searching for each option")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(link("Reading the abstracts")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
  });

  it("links the shortlist walk's done Shortlisting row to the shortlist, and nothing while it runs", () => {
    const ended = cardRows([entry({ stage: "shortlist", label: "Shortlisting", status: "completed" })], null, "succeeded");
    expect(rowLink(ended[0], ended, "t1", "shortlist", false)).toEqual({
      href: "/tasks/t1/result?view=shortlist",
      label: "Shortlist",
    });
    const running = cardRows([entry({ stage: "shortlist", label: "Shortlisting", status: "started" })], null, "running");
    expect(rowLink(running[0], running, "t1", "shortlist", false)).toBeNull();
  });

  it("maps the baseline walk as an Evidence search, its Writing row to the baseline (round 10, D4)", () => {
    const rows = done([...searchScreen, entry({ stage: "synthesise", label: "Writing", status: "completed" })]);
    expect(rowLink(rows[0], rows, "t1", "baseline", false)).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    const writing = rows.find((row) => row.label === "Writing")!;
    expect(rowLink(writing, rows, "t1", "baseline", false)).toEqual({
      href: "/tasks/t1/result?view=baseline",
      label: "Baseline",
    });
  });

  it("links nothing on an added option's search or the shortlist walk", () => {
    const rows = done(searchScreen);
    expect(rowLink(rows[0], rows, "t1", "option_search", false)).toBeNull();
    expect(rowLink(rows[0], rows, "t1", "shortlist", false)).toBeNull();
  });
});

// Owner, round 8: the step in progress links to the page its output lands
// on, before it finishes.
describe("rowLink — where the step in progress points", () => {
  const live = (stage: StageEntry["stage"], label: string) => {
    const rows = cardRows([entry({ stage, label, status: "started" })], standardPlan(), "running");
    return { rows, row: rows.find((row) => row.state === "progress")! };
  };

  it.each([
    ["acquire", "Searching and screening", "/tasks/t1/sources/all", "Sources"],
    ["screen", "Searching and screening", "/tasks/t1/sources/all", "Sources"],
    ["classify", "Classifying", "/tasks/t1/sources/landscape", "Landscape"],
    ["characterise", "Mapping", "/tasks/t1/sources", "Themes"],
    ["synthesise", "Writing", "/tasks/t1/result", "Report"],
  ] as const)("links %s to its page while it runs", (stage, label, href, name) => {
    const { rows, row } = live(stage, label);
    expect(rowLink(row, rows, "t1", "evidence_search", false)).toEqual({ href, label: name });
  });

  it("gives reading and shortlisting no link while they run", () => {
    const reading = live("ingest", "Collecting the full texts");
    expect(rowLink(reading.row, reading.rows, "t1", "evidence_search", false)).toBeNull();
    const shortlisting = live("select", "Shortlisting");
    expect(rowLink(shortlisting.row, shortlisting.rows, "t1", "evidence_search", false)).toBeNull();
  });

  it("points a longlist walk's Searching and Screening at Sources and its Classifying at the landscape while they run", () => {
    for (const [stage, label, href, name] of [
      ["acquire", "Searching", "/tasks/t1/sources/all", "Sources"],
      ["screen", "Screening", "/tasks/t1/sources/all", "Sources"],
      ["classify", "Classifying", "/tasks/t1/sources/landscape", "Landscape"],
      ["appraise", "Classifying", "/tasks/t1/sources/landscape", "Landscape"],
    ] as const) {
      const rows = cardRows(
        [
          entry({ stage: "suggest", label: "Suggesting options", status: "completed" }),
          entry({ stage, label, status: "started" }),
        ],
        null,
        "running",
      );
      const row = rows.find((candidate) => candidate.state === "progress")!;
      expect(rowLink(row, rows, "t1", "longlist", false)).toEqual({ href, label: name });
    }
  });

  it("points a longlist walk's step in progress at the longlist being built, from Suggesting options on (D4)", () => {
    const walk = (stages: StageEntry[]) => {
      const rows = cardRows(stages, null, "running");
      return { rows, row: rows.find((row) => row.state === "progress")! };
    };
    const reading = walk([entry({ stage: "inherit", label: "Reading the linked search", status: "started" })]);
    expect(rowLink(reading.row, reading.rows, "t1", "longlist", false)).toBeNull();
    for (const [stage, label] of [
      ["suggest", "Suggesting options"],
      ["option_searches", "Searching for each option"],
      ["extract_interventions", "Reading the abstracts"],
      ["longlist", "Clustering into options"],
      ["option_profile", "Writing what each option would take"],
      ["constrain", "Applying your constraints"],
      ["theme", "Grouping into themes"],
      ["shortlist", "Shortlisting"],
    ] as const) {
      const { rows, row } = walk([entry({ stage, label, status: "started" })]);
      expect(rowLink(row, rows, "t1", "longlist", false)).toEqual({ href: "/tasks/t1/result", label: "Longlist" });
    }
  });

  it("points the baseline walk's Writing at the baseline while it runs", () => {
    const { rows, row } = live("synthesise", "Writing");
    expect(rowLink(row, rows, "t1", "baseline", false)).toEqual({ href: "/tasks/t1/result?view=baseline", label: "Baseline" });
  });

  it("links a step still to come nowhere", () => {
    const { rows } = live("acquire", "Searching and screening");
    const upcoming = rows.find((row) => row.state === "upcoming")!;
    expect(rowLink(upcoming, rows, "t1", "evidence_search", false)).toBeNull();
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

  it("puts the writer's section before the activity in the trace's header", () => {
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

  it("formats the folded trace line's, History's and the task list's minutes", () => {
    const toTheMinute = (seconds: number) => formatElapsed(seconds, { withSeconds: false });
    expect(toTheMinute(45)).toBe("45 s");
    expect(toTheMinute(372)).toBe("6 min");
    expect(toTheMinute(14 * 60 + 59)).toBe("14 min");
    expect(toTheMinute(3840)).toBe("1 h 4 min");
  });
});

describe("the trace's header words (annex § The run trace)", () => {
  const rows = cardRows(
    [entry({ stage: "acquire", status: "completed" }), entry({ stage: "screen", status: "started" })],
    standardPlan(),
    "running",
  );

  it("names the row in progress, else the last that ran", () => {
    expect(currentRow(rows)?.label).toBe("Searching and screening");
    const done = cardRows([entry({ stage: "acquire", status: "completed" }), entry({ stage: "screen", status: "completed" })], standardPlan(), "paused");
    expect(currentRow(done)?.label).toBe("Searching and screening");
  });

  it("reads the row's label, then what it is doing, in the server's words", () => {
    expect(traceWords(currentRow(rows), "184 found so far", "live", true)).toBe("Searching and screening · 184 found so far");
    expect(traceWords(currentRow(rows), null, "live", true)).toBe("Searching and screening");
    expect(traceWords(null, null, "live", true)).toBe("");
  });

  it("says the step is still working after two quiet minutes, with no counter", () => {
    expect(traceWords(currentRow(rows), "collecting 21 of 38", "stalled", true)).toBe(`Searching and screening · ${STALLED_LINE}`);
    expect(STALLED_LINE).toBe("Still working on this step");
  });

  it("names who a paused run waits on: the owner, else the owner's first name", () => {
    expect(traceWords(currentRow(rows), "184 found so far", "paused", true)).toBe("Paused · waiting on you");
    expect(traceWords(currentRow(rows), "184 found so far", "paused", false, "Grace Hopper")).toBe("Paused · waiting on Grace");
    expect(traceWords(currentRow(rows), "184 found so far", "paused", false)).toBe("Paused");
  });

  it("counts the steps", () => {
    expect(stepCount(1)).toBe("1 step");
    expect(stepCount(6)).toBe("6 steps");
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

  it("folds an ended run to its finish words, with the Result tab as its one link", () => {
    expect(isFinished("degraded")).toBe(true);
    expect(isFinished("failed")).toBe(false);
    expect(endedLine("succeeded", "evidence_search")).toEqual({ words: "Report ready", tone: "complete", link: true });
    expect(endedLine("degraded", "longlist")).toEqual({ words: "The longlist is ready", tone: "complete", link: true });
  });

  it("reads a bad ending as Stopped or Failed with no link; a degraded shortlist walk says it proposed none", () => {
    expect(endedLine("failed", "evidence_search")).toEqual({ words: "Failed", tone: "failed", link: false });
    expect(endedLine("aborted", "evidence_search")).toEqual({ words: "Stopped", tone: "failed", link: false });
    expect(endedLine("interrupted", "baseline")).toEqual({ words: "Stopped", tone: "failed", link: false });
    expect(endedLine("degraded", "shortlist")).toEqual({
      words: "Policy Atlas could not propose a shortlist. Your places are unchanged.",
      tone: "failed",
      link: false,
    });
  });

  it("has no ended line while the run is live", () => {
    expect(endedLine("running", "evidence_search")).toBeNull();
    expect(endedLine("paused", "evidence_search")).toBeNull();
    expect(endedLine(undefined, "evidence_search")).toBeNull();
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
    // ponytail: the theory of change's own trace still keeps its step copy on
    // the client (task 054, merged before its move to the server table).
    const hits = sourceFiles(root).filter((path) => !path.endsWith("TocTrace.tsx")).flatMap((path) => {
      const text = readFileSync(path, "utf8");
      return RETIRED_STAGE_LABELS.filter((label) => text.includes(label)).map((label) => `${relative(root, path)}: ${label}`);
    });
    expect(hits).toEqual([]);
  });
});

describe("traceWords, a verb that repeats the label", () => {
  it("drops the detail when it only repeats the row's label", () => {
    const row = { key: "categorise", label: "Classifying", stages: ["classify"], entries: [], state: "progress" as const };
    expect(traceWords(row, "Classifying", "live", true)).toBe("Classifying");
    expect(traceWords(row, "1,200 of 2,410 classified", "live", true)).toBe("Classifying · 1,200 of 2,410 classified");
  });
});
