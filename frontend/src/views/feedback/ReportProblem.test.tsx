import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import { attachedContext, ReportProblem } from "./ReportProblem";

const state = vi.hoisted(() => ({ submit: vi.fn(), isSuccess: false }));
vi.mock("../../api/feedback", () => ({
  useSubmitFeedback: () => ({
    mutate: state.submit,
    isPending: false,
    isError: false,
    isSuccess: state.isSuccess,
  }),
}));

const TASK = {
  task_id: "task-1",
  question: "What works for school attendance?",
  active_run: {
    capability_run_id: "12345678-aaaa-bbbb-cccc-000000000000",
    status: "running",
    stage: "screen",
    stage_label: "Screening",
  },
} as unknown as components["schemas"]["TaskOut"];

function renderButton(task: components["schemas"]["TaskOut"] | undefined) {
  return render(
    <MemoryRouter initialEntries={["/tasks/task-1/result"]}>
      <ReportProblem task={task} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  state.submit.mockReset();
  state.isSuccess = false;
});

describe("attachedContext", () => {
  it("takes the run and the step from the task's active run", () => {
    const context = attachedContext(TASK, "/tasks/task-1/result", new Date("2026-11-18T09:00:00Z"));

    expect(context.runId).toBe("12345678-aaaa-bbbb-cccc-000000000000");
    expect(context.stepReached).toBe("Screening");
    expect(context.stepStatus).toBe("running");
    expect(context.page).toBe("/tasks/task-1/result");
  });

  it("has no run on a page with no task", () => {
    const context = attachedContext(undefined, "/new", new Date());

    expect(context.runId).toBeNull();
    expect(context.stepReached).toBeNull();
  });
});

describe("ReportProblem", () => {
  it("opens a dialog that shows what is attached automatically", async () => {
    const user = userEvent.setup();
    renderButton(TASK);

    await user.click(screen.getByRole("button", { name: "Report a problem" }));

    const dialog = screen.getByRole("dialog", { name: "Report a problem" });
    expect(dialog).toHaveTextContent("Attached automatically");
    expect(dialog).toHaveTextContent("12345678");
    expect(dialog).not.toHaveTextContent("12345678-aaaa");
    expect(dialog).toHaveTextContent("Screening · running");
    expect(dialog).toHaveTextContent("/tasks/task-1/result");
    expect(dialog).toHaveTextContent("Goes to the Policy Atlas team");
  });

  it("sends the kind, the description and the question, which is on by default", async () => {
    const user = userEvent.setup();
    renderButton(TASK);
    await user.click(screen.getByRole("button", { name: "Report a problem" }));

    await user.click(screen.getByRole("radio", { name: "Search stalled or took too long" }));
    await user.type(screen.getByLabelText("What happened?"), "No progress for an hour");
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(state.submit).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "problem_report",
        surface: "app_header",
        task_id: "task-1",
        problem_kind: "stalled",
        description: "No progress for an hour",
        page: "/tasks/task-1/result",
        step_reached: "Screening",
        step_status: "running",
        query_text: "What works for school attendance?",
      }),
    );
    expect(state.submit.mock.calls[0][0].client.browser).toBe(navigator.userAgent);
  });

  it("leaves the question out when its checkbox is cleared, and needs no kind", async () => {
    const user = userEvent.setup();
    renderButton(TASK);
    await user.click(screen.getByRole("button", { name: "Report a problem" }));

    await user.click(screen.getByRole("checkbox", { name: "Include my research question text" }));
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(state.submit).toHaveBeenCalledWith(
      expect.objectContaining({ problem_kind: "other", query_text: null }),
    );
  });

  it("works on a page with no task, with no question checkbox", async () => {
    const user = userEvent.setup();
    renderButton(undefined);
    await user.click(screen.getByRole("button", { name: "Report a problem" }));

    expect(screen.getByRole("dialog")).toHaveTextContent("No run");
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(state.submit).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: null, step_reached: null, query_text: null }),
    );
  });

  it("confirms after the report is sent", async () => {
    state.isSuccess = true;
    const user = userEvent.setup();
    renderButton(TASK);

    await user.click(screen.getByRole("button", { name: "Report a problem" }));

    expect(screen.getByRole("status")).toHaveTextContent("Your report was sent");
  });
});
