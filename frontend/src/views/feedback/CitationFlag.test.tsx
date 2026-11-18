import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CitationFlag } from "./CitationFlag";

const state = vi.hoisted(() => ({
  records: [] as Array<{ feedback_event_id: string; target_id: string; payload: object }>,
  submit: vi.fn(),
  retract: vi.fn(),
}));
vi.mock("../../api/feedback", () => ({
  useFeedback: () => ({ data: state.records }),
  useSubmitFeedback: () => ({ mutate: state.submit, isPending: false, isError: false }),
  useRetractFeedback: () => ({ mutate: state.retract, isPending: false, isError: false }),
}));

const BODY = {
  kind: "citation_flag",
  surface: "report_references",
  task_id: "task-1",
  artefact_id: "artefact-1",
  source_id: "doc-1",
};

function renderFlag() {
  return render(
    <CitationFlag
      taskId="task-1"
      artefactId="artefact-1"
      sourceId="doc-1"
      title="A cited paper"
      surface="report_references"
    />,
  );
}

beforeEach(() => {
  state.records = [];
  state.submit.mockReset();
  state.retract.mockReset();
});

describe("CitationFlag", () => {
  it("has two named toggle buttons, not pressed before a flag", () => {
    renderFlag();

    const useful = screen.getByRole("button", { name: "Useful: A cited paper" });
    const notRelevant = screen.getByRole("button", { name: "Not relevant: A cited paper" });
    expect(useful).toHaveAttribute("aria-pressed", "false");
    expect(notRelevant).toHaveAttribute("aria-pressed", "false");
    expect(useful).toHaveClass("size-11");
  });

  it("saves Useful on the first click, with no panel", async () => {
    const user = userEvent.setup();
    renderFlag();

    await user.click(screen.getByRole("button", { name: /^Useful/ }));

    expect(state.submit).toHaveBeenCalledWith({ ...BODY, action: "useful" });
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("shows a stored flag as pressed, and a second click retracts it", async () => {
    state.records = [
      { feedback_event_id: "event-1", target_id: "doc-1", payload: { action: "useful" } },
      { feedback_event_id: "event-2", target_id: "doc-2", payload: { action: "not_relevant" } },
    ];
    const user = userEvent.setup();
    renderFlag();

    const useful = screen.getByRole("button", { name: /^Useful/ });
    expect(useful).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Not relevant/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await user.click(useful);

    expect(state.retract).toHaveBeenCalledWith("event-1");
    expect(state.submit).not.toHaveBeenCalled();
  });

  it("saves Not relevant on the first click, then refines it with a reason and a note", async () => {
    const user = userEvent.setup();
    renderFlag();

    await user.click(screen.getByRole("button", { name: /^Not relevant/ }));
    expect(state.submit).toHaveBeenCalledWith({ ...BODY, action: "not_relevant" });

    await user.click(screen.getByRole("button", { name: "Wrong population or setting" }));
    await user.type(screen.getByLabelText(/Note/), "Adults only");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(state.submit).toHaveBeenLastCalledWith({
      ...BODY,
      action: "not_relevant",
      reason: "wrong_population",
      note: "Adults only",
    });
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("retracts the flag from Undo in the panel", async () => {
    const user = userEvent.setup();
    const view = renderFlag();
    await user.click(screen.getByRole("button", { name: /^Not relevant/ }));
    state.records = [
      { feedback_event_id: "event-9", target_id: "doc-1", payload: { action: "not_relevant" } },
    ];
    view.rerender(
      <CitationFlag
        taskId="task-1"
        artefactId="artefact-1"
        sourceId="doc-1"
        title="A cited paper"
        surface="report_references"
      />,
    );

    await user.click(screen.getByRole("button", { name: "Undo" }));

    expect(state.retract).toHaveBeenCalledWith("event-9");
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });
});
