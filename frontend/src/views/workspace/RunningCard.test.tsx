import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { PlanDraft, StageEntry } from "../../store";
import { RunningCard } from "./RunningCard";
import {
  CHAT_PRIMARY_CTA_CLASS,
  collapsedStatusLine,
  completedSignposts,
  elapsedSeconds,
  formatElapsed,
  resultsSignpost,
  RUN_FINISHED_MESSAGE,
  runFinishedSignpost,
  RUNNING_CARD_SHELL_CLASS,
  runningCardCopy,
  SEE_PLAN_CTA_CLASS,
  signpostForStage,
  stageDetailLines,
  stageRows,
} from "./runProgress";

const TASK_ID = "11111111-1111-1111-1111-111111111111";

function stage(overrides: Partial<StageEntry> & Pick<StageEntry, "stage" | "label" | "status">): StageEntry {
  return overrides;
}

function planWithSteps(): PlanDraft {
  return {
    analysis_depth: "standard",
    assumptions: null,
    backend_scope: "both",
    component_rationale: null,
    components: null,
    expected_artefact_shape: null,
    extract_profiles: null,
    grouping_facets: null,
    question: null,
    ready: true,
    scope_constraints: null,
    scoping_notes: null,
    screening_criteria: null,
    search_effort: "standard",
    section_budget: null,
    steering_mode: "moderate",
    steps: [
      { stage: "acquire", label: "Searching sources", blurb: "Queries out." },
      { stage: "screen", label: "Screening for relevance", blurb: "Titles and abstracts." },
    ],
    time_band: null,
    title: null,
  };
}

describe("runningCard helpers", () => {
  it("labels each run status", () => {
    expect(runningCardCopy("running").title).toBe("Analysis running…");
    expect(runningCardCopy("paused").eyebrow).toBe("PAUSED");
    expect(runningCardCopy("succeeded").title).toBe("The evidence base is ready");
    expect(runningCardCopy("failed").eyebrow).toBe("STOPPED");
  });

  it("formats elapsed seconds", () => {
    expect(formatElapsed(13)).toBe("13s");
    expect(formatElapsed(60)).toBe("1m");
    expect(formatElapsed(124)).toBe("2m 4s");
  });

  it("freezes elapsed time at endedAt rather than the live clock", () => {
    const started = "2026-07-21T10:00:00Z";
    const ended = "2026-07-21T10:02:04Z";
    expect(elapsedSeconds(started, ended, Date.parse("2026-08-18T16:00:00Z"))).toBe(124);
  });

  it("uses plan-panel step labels, not SSE copy", () => {
    const rows = stageRows(
      [stage({ stage: "acquire", label: "Finding relevant sources", status: "completed" })],
      planWithSteps(),
    );
    expect(rows[0]).toMatchObject({
      stage: "acquire",
      label: "Searching",
      blurb: "Querying academic and policy databases.",
      status: "completed",
    });
    expect(rows.map((row) => row.stage)).toEqual([
      "acquire",
      "screen",
      "classify",
      "appraise",
      "characterise",
      "select",
      "synthesise",
    ]);
    expect(rows[1]?.status).toBe("upcoming");
    expect(rows[1]?.label).toBe("Screening");
  });

  it("keeps every search/screen round and numbers them when there is more than one", () => {
    const rows = stageRows(
      [
        stage({
          stage: "acquire",
          label: "Searching",
          status: "completed",
          summary: { round_index: 1 },
        }),
        stage({
          stage: "screen",
          label: "Screening",
          status: "completed",
          summary: { round_index: 1 },
        }),
        stage({
          stage: "acquire",
          label: "Searching",
          status: "completed",
          summary: { round_index: 2 },
        }),
        stage({
          stage: "screen",
          label: "Screening",
          status: "started",
          summary: { round_index: 2 },
        }),
      ],
      planWithSteps(),
    );
    expect(rows.filter((row) => row.stage === "acquire").map((row) => row.label)).toEqual([
      "Searching (Round 1)",
      "Searching (Round 2)",
    ]);
    expect(rows.filter((row) => row.stage === "screen").map((row) => row.label)).toEqual([
      "Screening (Round 1)",
      "Screening (Round 2)",
    ]);
    expect(new Set(rows.map((row) => row.id)).size).toBe(rows.length);
  });

  it("numbers Screening from the preceding Searching round when the screen summary has no round_index", () => {
    const rows = stageRows(
      [
        stage({
          stage: "acquire",
          label: "Searching",
          status: "completed",
          summary: { round_index: 1 },
        }),
        stage({ stage: "screen", label: "Screening", status: "completed" }),
        stage({
          stage: "acquire",
          label: "Searching",
          status: "completed",
          summary: { round_index: 2 },
        }),
        stage({ stage: "screen", label: "Screening", status: "completed" }),
      ],
      planWithSteps(),
    );
    expect(rows.filter((row) => row.stage === "screen").map((row) => row.label)).toEqual([
      "Screening (Round 1)",
      "Screening (Round 2)",
    ]);
  });

  it("signposts Sources after acquire and Results when the write-up exists", () => {
    expect(signpostForStage("acquire", TASK_ID, false)).toEqual({
      href: `/tasks/${TASK_ID}/sources/all`,
      label: "Sources are ready",
      message: "Searching has finished.",
    });
    expect(signpostForStage("extract", TASK_ID, false)).toBeNull();
    expect(signpostForStage("extract", TASK_ID, true)?.href).toContain("/findings");
    expect(signpostForStage("extract", TASK_ID, true)?.message).toBe("Findings are ready.");
    expect(resultsSignpost(TASK_ID, "succeeded")?.label).toBe("Read the report");
    expect(resultsSignpost(TASK_ID, "running")).toBeNull();
    expect(runFinishedSignpost(TASK_ID, "succeeded")).toEqual({
      href: `/tasks/${TASK_ID}/result`,
      label: "Result",
      message: RUN_FINISHED_MESSAGE,
    });
    expect(runFinishedSignpost(TASK_ID, "running")).toBeNull();
  });

  it("lists completed signposts in stage order", () => {
    expect(
      completedSignposts(
        [
          stage({ stage: "acquire", label: "Searching", status: "completed" }),
          stage({ stage: "characterise", label: "Mapping", status: "completed" }),
        ],
        TASK_ID,
        false,
      ).map((entry) => entry.label),
    ).toEqual(["Sources are ready", "The landscape is ready"]);
    expect(signpostForStage("characterise", TASK_ID, false)?.message).toBe(
      "Mapping has finished.",
    );
  });

  it("lists blurb, counts and elapsed on a completed step", () => {
    expect(
      stageDetailLines({
        id: "acquire:1:1",
        stage: "acquire",
        label: "Searching",
        status: "completed",
        blurb: "Querying academic and policy databases.",
        summary: { found: 12 },
        seconds: 8,
      }),
    ).toEqual(["Querying academic and policy databases.", "12 found", "Took 8s"]);
  });

  it("builds the collapsed one-liner from the current step", () => {
    const line = collapsedStatusLine(
      "running",
      [
        {
          id: "acquire:1:1",
          stage: "acquire",
          label: "Searching",
          status: "started",
        },
      ],
      "13s",
    );
    expect(line).toBe("RUNNING · Searching · 13s");
  });
});

describe("RunningCard", () => {
  it("renders the running card with a minimisable step list", async () => {
    const user = userEvent.setup();
    let minimised = false;
    const { rerender } = render(
      <MemoryRouter>
        <RunningCard
          taskId={TASK_ID}
          status="running"
          stages={[
            stage({
              stage: "acquire",
              label: "Finding relevant sources",
              status: "completed",
              blurb: "Queries out.",
              summary: { found: 12 },
              seconds: 4,
            }),
            stage({ stage: "screen", label: "Screening sources", status: "started" }),
          ]}
          plan={planWithSteps()}
          startedAt="2026-07-21T10:00:00Z"
          hasFindings={false}
          minimised={minimised}
          onMinimisedChange={(next) => {
            minimised = next;
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Analysis running…" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Analysis run" }).className).toContain("bg-[#DDF2EE]");
    expect(screen.getByRole("region", { name: "Analysis run" }).className).toContain("border-[#17A88D]");
    expect(RUNNING_CARD_SHELL_CLASS).toContain("bg-[#DDF2EE]");
    expect(screen.getByRole("button", { name: "Minimise" }).className).toContain("text-blue");
    expect(screen.getByText("Mapping").className).toContain("text-grey");
    expect(screen.getByText("Done").className).toContain("text-navy");
    expect(screen.getByRole("list", { name: "Stage timeline" })).toHaveTextContent("Searching");
    expect(screen.queryByRole("link", { name: /Sources are ready/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Searching" }));
    expect(screen.getByRole("link", { name: /Sources are ready/ })).toHaveAttribute(
      "href",
      `/tasks/${TASK_ID}/sources/all`,
    );
    expect(screen.getByText("Querying academic and policy databases.")).toBeInTheDocument();
    expect(screen.getByText("12 found")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Minimise" }));
    rerender(
      <MemoryRouter>
        <RunningCard
          taskId={TASK_ID}
          status="running"
          stages={[
            stage({
              stage: "acquire",
              label: "Finding relevant sources",
              status: "completed",
              summary: { found: 12 },
              seconds: 4,
            }),
          ]}
          plan={null}
          startedAt="2026-07-21T10:00:00Z"
          hasFindings={false}
          minimised
          onMinimisedChange={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("list", { name: "Stage timeline" })).toBeNull();
    expect(screen.getByRole("button", { name: "Expand" })).toBeInTheDocument();
  });

  it("offers Read the report and See plan when the run has succeeded", async () => {
    const onSeePlan = vi.fn();
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RunningCard
          taskId={TASK_ID}
          status="succeeded"
          stages={[stage({ stage: "synthesise", label: "Writing the report", status: "completed" })]}
          plan={null}
          startedAt="2026-07-21T10:00:00Z"
          endedAt="2026-07-21T10:12:00Z"
          hasFindings={false}
          minimised={false}
          onMinimisedChange={() => undefined}
          onSeePlan={onSeePlan}
        />
      </MemoryRouter>,
    );
    const results = screen.getByRole("link", { name: "Read the report" });
    expect(results).toHaveAttribute("href", `/tasks/${TASK_ID}/result`);
    expect(results.className).toContain("px-6");
    expect(results.className).toContain("text-body");
    expect(CHAT_PRIMARY_CTA_CLASS).toContain("px-6 py-3.5 text-body font-bold");
    expect(SEE_PLAN_CTA_CLASS).toContain("border-2");
    expect(SEE_PLAN_CTA_CLASS).toContain("bg-paper");
    await user.click(screen.getByRole("button", { name: "See plan" }));
    expect(onSeePlan).toHaveBeenCalledTimes(1);
  });

  it("expands only the Searching round that was clicked", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RunningCard
          taskId={TASK_ID}
          status="running"
          stages={[
            stage({
              stage: "acquire",
              label: "Searching",
              status: "completed",
              summary: { round_index: 1, found: 12 },
              seconds: 4,
            }),
            stage({
              stage: "screen",
              label: "Screening",
              status: "completed",
              summary: { round_index: 1 },
            }),
            stage({
              stage: "acquire",
              label: "Searching",
              status: "completed",
              summary: { round_index: 2, found: 8 },
              seconds: 6,
            }),
            stage({
              stage: "screen",
              label: "Screening",
              status: "completed",
              summary: { round_index: 2 },
            }),
          ]}
          plan={planWithSteps()}
          startedAt="2026-07-21T10:00:00Z"
          hasFindings={false}
          minimised={false}
          onMinimisedChange={() => undefined}
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Searching (Round 2)" }));
    expect(screen.getByText("Took 6s")).toBeInTheDocument();
    expect(screen.queryByText("Took 4s")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Searching (Round 1)" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("button", { name: "Searching (Round 2)" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Screening (Round 1)" }));
    expect(screen.getByRole("button", { name: "Searching (Round 2)" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("button", { name: "Screening (Round 1)" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("button", { name: "Screening (Round 2)" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });
});
