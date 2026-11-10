import { describe, expect, it } from "vitest";

import type { RunStreamState, StageEntry, TaskAgentThreadRun } from "../../store";
import { READY_WORDS } from "../../ui/brand/taskStatus";
import { cardRows, endedLine, resultHref, rowLink, walkKind } from "./runProgress";
import { BETWEEN_WALKS_MS, joinTocWalks, pendingLead, waitsForCheck } from "./tocWalks";

/*
 * The theory of change's walks in the shared run card (task 054's 058
 * alignment, A6, A7 and A23). The labels below stand for the server's.
 */

const T0 = "2026-11-09T10:00:00Z";
const at = (seconds: number) => new Date(Date.parse(T0) + seconds * 1000).toISOString();

const stage = (key: string, label: string, status: StageEntry["status"] = "completed"): StageEntry => ({
  stage: key as StageEntry["stage"],
  label,
  status,
  startedAt: T0,
});

function run(id: string, overrides: Partial<TaskAgentThreadRun> = {}): TaskAgentThreadRun {
  return {
    capability_run_id: id,
    task_id: "t1",
    plan_id: "p1",
    plan_version: 1,
    status: "succeeded",
    started_at: T0,
    ended_at: at(60),
    stages: [],
    ...overrides,
  } as TaskAgentThreadRun;
}

type RunRef = NonNullable<RunStreamState["run"]>;
const live = (overrides: Partial<RunRef> = {}): RunRef => ({ id: "draft", status: "succeeded", startedAt: T0, endedAt: at(60), ...overrides });

describe("ToC walk kinds and finish words (A6)", () => {
  it("follows the run read's toc_walk, else the first step", () => {
    expect(walkKind("theory_of_change", [], null, "draft")).toBe("toc_draft");
    expect(walkKind("theory_of_change", [], null, "read")).toBe("toc_read");
    expect(walkKind("theory_of_change", [], null, "check")).toBe("toc_check");
    expect(walkKind("theory_of_change", [], null, "report_update")).toBe("toc_report_update");
    expect(walkKind("theory_of_change", [stage("toc_read", "Reading")])).toBe("toc_read");
    expect(walkKind("theory_of_change", [stage("toc_draft", "Drafting")])).toBe("toc_draft");
    expect(walkKind("theory_of_change", [stage("toc_select", "Screening")])).toBe("toc_check");
  });

  it("ends a check with Evidence checked and an upload's read with Theory drafted, each with Read it", () => {
    expect(READY_WORDS.toc_check).toBe("Evidence checked");
    expect(READY_WORDS.toc_read).toBe("Theory drafted");
    expect(READY_WORDS.toc_draft).toBe("Theory drafted");
    expect(endedLine("succeeded", "toc_check")).toEqual({ words: "Evidence checked", tone: "complete", link: true });
    expect(endedLine("succeeded", "toc_read")).toEqual({ words: "Theory drafted", tone: "complete", link: true });
    expect(endedLine("failed", "toc_check")).toEqual({ words: "Failed", tone: "failed", link: false });
    expect(endedLine("aborted", "toc_check")).toEqual({ words: "Stopped", tone: "failed", link: false });
  });

  it("points Read it at the theory of change's Result", () => {
    expect(resultHref("t1", "toc_check")).toBe("/tasks/t1/result");
    expect(resultHref("t1", "toc_read")).toBe("/tasks/t1/result");
  });
});

describe("ToC row links (§ 8: the brief's table)", () => {
  const rows = cardRows(
    [
      stage("toc_draft", "Drafting"),
      stage("toc_item_searches", "Searching each"),
      stage("toc_select", "Screening"),
      stage("toc_merge", "Merging"),
      stage("toc_search_new", "New connections"),
      stage("toc_new_link_searches", "New connections"),
      stage("toc_judge", "Judging"),
      stage("classify", "Classifying"),
      stage("appraise", "Classifying"),
      stage("toc_figures", "Figures"),
      stage("toc_report", "Writing", "started"),
    ],
    null,
    "running",
  );
  const link = (label: string) => rowLink(rows.find((row) => row.label === label)!, rows, "t1", "toc_check", false);

  it("merges the fan-out into its step's row by their shared label (S1)", () => {
    expect(rows.find((row) => row.label === "New connections")?.stages).toEqual(["toc_search_new", "toc_new_link_searches"]);
    expect(rows.find((row) => row.label === "Classifying")?.stages).toEqual(["classify", "appraise"]);
  });

  it("links the theory, the sources and the report, and leaves merging and the figures plain", () => {
    expect(link("Drafting")).toEqual({ href: "/tasks/t1/result", label: "Theory" });
    expect(link("Searching each")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(link("Screening")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(link("New connections")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(link("Judging")).toEqual({ href: "/tasks/t1/result", label: "Theory" });
    expect(link("Classifying")).toEqual({ href: "/tasks/t1/sources/all", label: "Sources" });
    expect(link("Merging")).toBeNull();
    expect(link("Figures")).toBeNull();
    expect(link("Writing")).toEqual({ href: "/tasks/t1/result", label: "Report" });
  });
});

describe("the automatic chain as one card (A7, A23, S10)", () => {
  it("pairs a check the server started with its draft, and leaves a walk the reader started alone", () => {
    const draft = run("draft", { toc_walk: "draft" });
    const check = run("check", { toc_walk: "check", follows_capability_run_id: "draft", started_at: at(61) });
    const later = run("later", { toc_walk: "check", started_at: at(500) });
    const chain = joinTocWalks([draft, check, later]);
    expect([...chain.joined]).toEqual(["draft"]);
    expect(chain.leadOf.get("check")?.capability_run_id).toBe("draft");
    expect(chain.leadOf.has("later")).toBe(false);
  });

  it("keeps a finished draft running until its check starts, for a short while only", () => {
    const stages = [stage("toc_draft", "Drafting")];
    expect(waitsForCheck(live(), stages, "draft", false, Date.parse(at(65)))).toBe(true);
    // A refused check: the card ends with the draft's own words.
    expect(waitsForCheck(live(), stages, "draft", false, Date.parse(at(60)) + BETWEEN_WALKS_MS + 1)).toBe(false);
    // The check is in the read: the check's card carries on.
    expect(waitsForCheck(live(), stages, "draft", true, Date.parse(at(65)))).toBe(false);
    // An upload's read waits for the reader, and a failed draft ends.
    expect(waitsForCheck(live(), [stage("toc_read", "Reading")], "read", false, Date.parse(at(65)))).toBe(false);
    expect(waitsForCheck(live({ status: "failed" }), stages, "draft", false, Date.parse(at(65)))).toBe(false);
  });

  it("finds the draft a live check follows before the runs read has caught up", () => {
    const draft = run("draft", { toc_walk: "draft" });
    const check = live({ id: "check", status: "running", startedAt: at(61), endedAt: undefined });
    expect(pendingLead([draft], check, joinTocWalks([draft]))?.capability_run_id).toBe("draft");
    // A check long after a draft is the reader's own.
    const late = live({ id: "check", status: "running", startedAt: at(60 + BETWEEN_WALKS_MS / 1000 + 5), endedAt: undefined });
    expect(pendingLead([draft], late, joinTocWalks([draft]))).toBeNull();
    // An upload's read is never followed by itself.
    expect(pendingLead([run("read", { toc_walk: "read" })], check, joinTocWalks([]))).toBeNull();
  });
});
