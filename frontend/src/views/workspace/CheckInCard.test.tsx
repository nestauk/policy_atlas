import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { components } from "../../api/gen/types";
import type { CheckInOut, StageEntry } from "../../store/types";
import { CheckInCard } from "./CheckInCard";

type CheckInOption = components["schemas"]["CheckInOption"];

const mutate = vi.fn();

vi.mock("../../api/mutations", () => ({
  useAnswerCheckIn: () => ({ mutate, isPending: false }),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const CHECK_IN_ID = "22222222-2222-2222-2222-222222222222";

function baseCheckIn(overrides: Partial<CheckInOut> = {}): CheckInOut {
  return {
    boundary: "after_component",
    check_in_id: CHECK_IN_ID,
    component: "screen",
    created_at: "2026-07-21T10:00:00Z",
    kind: "pause",
    options: [],
    render: "Screening paused for review.",
    rerun_component: null,
    segment_reentry_allowed: false,
    sequence: 3,
    stage: "screen",
    status: "pending",
    triggers: [],
    ...overrides,
  };
}

function option(overrides: Partial<CheckInOption> = {}): CheckInOption {
  return {
    id: "some-option",
    label: "Some option",
    description: "",
    requires_user_input: false,
    suggested: false,
    ...overrides,
  };
}

function renderCard(checkIn: CheckInOut, stages: StageEntry[] = []) {
  return render(<CheckInCard projectId={PROJECT_ID} checkIn={checkIn} stages={stages} />);
}

describe("CheckInCard — option parameters", () => {
  it("submits change_mode with new_mode from the mode select, not a made-up { value }", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(
      baseCheckIn({
        options: [
          option({
            id: "change_mode",
            label: "Change how often I check in",
            description: "Pick a new steering cadence.",
            requires_user_input: true,
          }),
        ],
      }),
    );

    await user.click(screen.getByRole("button", { name: "Change how often I check in" }));
    await user.selectOptions(screen.getByLabelText("New steering mode"), "minimal");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(mutate).toHaveBeenCalledOnce();
    expect(mutate.mock.calls[0][0]).toMatchObject({
      checkInId: CHECK_IN_ID,
      body: { kind: "option", option_id: "change_mode", params: { new_mode: "minimal" } },
    });
  });

  it("other requires_user_input options pre-seed and focus the free-text steer instead of a generic form", async () => {
    mutate.mockClear();
    const user = userEvent.setup();
    renderCard(
      baseCheckIn({
        options: [
          option({
            id: "add-local-context",
            label: "Add local context",
            description: "Tell us which local programme to prioritise.",
            requires_user_input: true,
          }),
        ],
      }),
    );

    await user.click(screen.getByRole("button", { name: "Add local context" }));

    const freeText = screen.getByLabelText("Or steer in your own words") as HTMLInputElement;
    expect(freeText).toHaveValue("Add local context: ");
    expect(freeText).toHaveFocus();
    // No server-shaped-params text form was invented for this option, and
    // no premature submission happened.
    expect(screen.queryByLabelText(/Details for/)).not.toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });
});

describe("CheckInCard — stage chip", () => {
  it("renders the server-supplied stage label, not the raw stage key", () => {
    renderCard(
      baseCheckIn({ stage: "screen" }),
      [{ stage: "screen", label: "Screening sources", status: "completed" }] as StageEntry[],
    );

    expect(screen.getByText("Screening sources")).toBeInTheDocument();
    expect(screen.queryByText("screen")).not.toBeInTheDocument();
  });

  it("hides the chip entirely when no label is known for the check-in's stage", () => {
    renderCard(baseCheckIn({ stage: "classify" }), []);

    const header = screen.getByText("Waiting on your input").parentElement;
    expect(header?.children).toHaveLength(1);
  });
});
