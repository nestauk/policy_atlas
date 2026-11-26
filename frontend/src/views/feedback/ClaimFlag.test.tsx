import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ClaimFlagBlock, ClaimFlagProvider, FlagClaimButton, FlaggableSource } from "./ClaimFlag";

type Stored = { feedback_event_id: string; target_id: string; payload: object };
const state = vi.hoisted(() => ({
  flags: [] as Stored[],
  submit: vi.fn(),
  retract: vi.fn(),
}));
vi.mock("../../api/feedback", () => ({
  useFeedback: () => ({ data: state.flags }),
  useSubmitFeedback: () => ({ mutate: state.submit, isPending: false, isError: false }),
  useRetractFeedback: () => ({ mutate: state.retract, isPending: false, isError: false }),
}));

const BODY = {
  kind: "claim_flag",
  surface: "report_claim_sidebar",
  task_id: "task-1",
  artefact_id: "report-1",
  claim_id: "claim-1",
};

/** The sheet's flag parts: two cited sources, then the form. */
function renderSheet(openAtFlag = false) {
  return render(
    <ClaimFlagProvider
      taskId="task-1"
      artefactId="report-1"
      claimId="claim-1"
      openAtFlag={openAtFlag}
    >
      <FlaggableSource citationIds={["cit-1", "cit-2"]}>
        <p>Source one</p>
      </FlaggableSource>
      <FlaggableSource citationIds={["cit-3"]}>
        <p>Source two</p>
      </FlaggableSource>
      <ClaimFlagBlock />
    </ClaimFlagProvider>,
  );
}

beforeEach(() => {
  state.flags = [];
  state.submit.mockReset();
  state.retract.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("the claim flag", () => {
  it("requires a reason", async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose what is wrong with the claim.");
    expect(state.submit).not.toHaveBeenCalled();
  });

  it("submits Overstated with an optional note and no failing citation", async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByRole("radio", { name: /^Overstated/ }));
    await user.type(screen.getByLabelText(/Note/), "The source says may");
    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(state.submit.mock.calls[0][0]).toEqual({
      ...BODY,
      reason: "overstated",
      failing_citation_ids: [],
      provenance_viewed: [],
      note: "The source says may",
    });
  });

  it("refuses Citation doesn't support it with no source ticked", async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByRole("radio", { name: /^Citation doesn't support it/ }));
    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Tick at least one source above.");
    expect(state.submit).not.toHaveBeenCalled();
  });

  it("sends the citations of each ticked source as failing", async () => {
    const user = userEvent.setup();
    renderSheet();
    const boxes = screen.getAllByRole("checkbox", { name: "Doesn't support the claim" });

    await user.click(boxes[0]);
    expect(boxes[0]).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("radio", { name: /^Citation doesn't support it/ }));
    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(state.submit.mock.calls[0][0]).toMatchObject({
      reason: "unsupported",
      failing_citation_ids: ["cit-1", "cit-2"],
    });
  });

  it("sends the sources that came into view as viewed", async () => {
    const observers: Array<(entries: Array<{ isIntersecting: boolean }>) => void> = [];
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: (entries: Array<{ isIntersecting: boolean }>) => void) {
          observers.push(callback);
        }
        observe() {}
        disconnect() {}
      },
    );
    const user = userEvent.setup();
    renderSheet();

    // The second source scrolls into view; the first one never does.
    const { act } = await import("@testing-library/react");
    act(() => observers[1]([{ isIntersecting: true }]));
    await user.click(screen.getByRole("radio", { name: /^Wrong/ }));
    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(state.submit.mock.calls[0][0]).toMatchObject({ provenance_viewed: ["cit-3"] });
  });

  it("shows an existing flag, which can be changed or removed", async () => {
    state.flags = [
      { feedback_event_id: "event-0", target_id: "claim-9", payload: { reason: "wrong" } },
      {
        feedback_event_id: "event-1",
        target_id: "claim-1",
        payload: { reason: "overstated", note: "Too sure" },
      },
    ];
    const user = userEvent.setup();
    renderSheet();

    expect(screen.getByRole("status")).toHaveTextContent("You flagged this claim: Overstated.");
    await user.click(screen.getByRole("button", { name: "Change" }));
    expect(screen.getByRole("radio", { name: /^Overstated/ })).toBeChecked();
    expect(screen.getByLabelText(/Note/)).toHaveValue("Too sure");

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Remove flag" }));

    expect(state.retract).toHaveBeenCalledWith("event-1");
  });

  it("clears the form from Cancel", async () => {
    const user = userEvent.setup();
    renderSheet();
    const box = screen.getAllByRole("checkbox")[0];

    await user.click(box);
    await user.click(screen.getByRole("radio", { name: /^Wrong/ }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(box).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: /^Wrong/ })).not.toBeChecked();
  });

  it("scrolls to the form when the sheet opens from the flag control", () => {
    const scrolled = vi.fn();
    const original = window.HTMLElement.prototype.scrollIntoView;
    window.HTMLElement.prototype.scrollIntoView = scrolled;
    try {
      renderSheet(true);
      expect(scrolled).toHaveBeenCalledOnce();
    } finally {
      window.HTMLElement.prototype.scrollIntoView = original;
    }
  });
});

describe("FlagClaimButton", () => {
  it("is a named button that opens the sheet at the flag", async () => {
    const onFlag = vi.fn();
    const user = userEvent.setup();
    render(<FlagClaimButton onFlag={onFlag} />);

    await user.click(screen.getByRole("button", { name: "Flag this claim" }));

    expect(onFlag).toHaveBeenCalledOnce();
  });
});
