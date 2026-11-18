import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MissingPaperForm, ScreeningOverrideButton } from "./MissingPaper";

type Resolution = { failure_stage: string | null; resolved_id: string | null };
const record = (resolution: Resolution) => ({ feedback_event_id: "event-1", resolution });

const state = vi.hoisted(() => ({
  reported: undefined as object | undefined,
  polled: undefined as object | undefined,
  overrides: [] as Array<{ feedback_event_id: string; target_id: string }>,
  submit: vi.fn(),
  reset: vi.fn(),
  retract: vi.fn(),
}));
vi.mock("../../api/feedback", () => ({
  useSubmitFeedback: () => ({
    mutate: state.submit,
    reset: state.reset,
    data: state.reported,
    isPending: false,
    isError: false,
  }),
  useFeedbackRecord: () => ({ data: state.polled }),
  useFeedback: () => ({ data: state.overrides }),
  useRetractFeedback: () => ({ mutate: state.retract, isPending: false, isError: false }),
}));

function renderForm() {
  return render(
    <MemoryRouter>
      <MissingPaperForm taskId="task-1" artefactId="artefact-1" surface="report_foot" />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  state.reported = undefined;
  state.polled = undefined;
  state.overrides = [];
  state.submit.mockReset();
  state.reset.mockReset();
  state.retract.mockReset();
});

describe("MissingPaperForm", () => {
  it("sends the input and the optional reason, and needs an input", async () => {
    const user = userEvent.setup();
    renderForm();
    const send = screen.getByRole("button", { name: "Report missing paper" });
    expect(send).toBeDisabled();

    await user.type(screen.getByLabelText("DOI, web address or title"), " 10.1000/x ");
    await user.type(screen.getByLabelText(/Why does it matter/), "The main UK trial");
    await user.click(send);

    expect(state.submit).toHaveBeenCalledWith({
      kind: "missing_paper",
      surface: "report_foot",
      task_id: "task-1",
      artefact_id: "artefact-1",
      raw_input: "10.1000/x",
      why: "The main UK trial",
    });
  });

  it("says that it is checking while the resolution is pending", () => {
    state.reported = record({ failure_stage: null, resolved_id: null });

    renderForm();

    expect(screen.getByRole("status")).toHaveTextContent("Checking where this paper went");
  });

  it.each([
    ["not_cited", "The search found this paper, but the report does not cite it."],
    ["not_selected", "The search found this paper, but the report does not cite it."],
    ["cited", "This paper is in the report's references."],
  ])("links a found paper (%s) to All sources", (stage, words) => {
    state.reported = record({ failure_stage: stage, resolved_id: "doc-7" });

    renderForm();

    expect(screen.getByRole("status")).toHaveTextContent(words);
    expect(screen.getByRole("link", { name: "Open it in All sources" })).toHaveAttribute(
      "href",
      "/tasks/task-1/sources/all?status=all&source=doc-7",
    );
  });

  it.each([
    ["screened_out_s1", "Recorded as a screening override."],
    ["screened_out_s2", "Recorded as a screening override."],
    ["not_retrieved", "Added to the checks we run on every search update."],
    ["unresolved", "Thanks — we couldn't match this automatically; we'll review it."],
  ])("confirms %s with no link", (stage, words) => {
    state.reported = record({ failure_stage: stage, resolved_id: "x" });

    renderForm();

    expect(screen.getByRole("status")).toHaveTextContent(words);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows the stage that a later poll brings", () => {
    state.reported = record({ failure_stage: null, resolved_id: null });
    state.polled = record({ failure_stage: "not_retrieved", resolved_id: "10.1000/x" });

    renderForm();

    expect(screen.getByRole("status")).toHaveTextContent("The search did not find this paper.");
  });

  it("resets the form from Add another", async () => {
    state.reported = record({ failure_stage: "unresolved", resolved_id: null });
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: "Add another" }));

    expect(state.reset).toHaveBeenCalledOnce();
  });
});

describe("ScreeningOverrideButton", () => {
  it("records the override with no free text", async () => {
    const user = userEvent.setup();
    render(<ScreeningOverrideButton taskId="task-1" sourceId="doc-1" title="A paper" />);
    const button = screen.getByRole("button", { name: "Should have been kept: A paper" });
    expect(button).toHaveAttribute("aria-pressed", "false");

    await user.click(button);

    expect(state.submit).toHaveBeenCalledWith({
      kind: "screening_override",
      surface: "screened_out_row",
      task_id: "task-1",
      source_id: "doc-1",
    });
  });

  it("shows a stored override as pressed, and a second click retracts it", async () => {
    state.overrides = [{ feedback_event_id: "event-3", target_id: "doc-1" }];
    const user = userEvent.setup();
    render(<ScreeningOverrideButton taskId="task-1" sourceId="doc-1" title="A paper" />);
    const button = screen.getByRole("button", { name: "Should have been kept: A paper" });
    expect(button).toHaveAttribute("aria-pressed", "true");

    await user.click(button);

    expect(state.retract).toHaveBeenCalledWith("event-3");
  });
});
