import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResolvedDecision } from "../../store";
import { recordSessionAnsweredCheckIn } from "../../store/thread";
import type { CheckInOut } from "../../store/types";
import { AnsweredCheckIn } from "./AnsweredCheckIn";

function decision(overrides: Partial<ResolvedDecision>): ResolvedDecision {
  return {
    checkInId: "c1",
    response: {},
    decidedBy: "user",
    occurredAt: "2026-07-28T10:00:00Z",
    sequence: 12,
    ...overrides,
  };
}

describe("AnsweredCheckIn", () => {
  it("echoes who decided and the typed prose", () => {
    render(
      <AnsweredCheckIn
        decision={decision({ response: { text: "prioritise UK school-based studies" } })}
      />,
    );
    expect(screen.getByText("Answered")).toBeInTheDocument();
    expect(screen.getByText("You decided")).toBeInTheDocument();
    expect(screen.getByText(/prioritise UK school-based studies/)).toBeInTheDocument();
  });

  it("never renders raw params — only allowlisted friendly-labelled detail", () => {
    render(
      <AnsweredCheckIn
        decision={decision({
          response: { option_id: "raw_id_should_not_render", internal_blob: "x9" },
          decidedBy: "standing_default",
        })}
      />,
    );
    expect(screen.queryByText(/raw_id_should_not_render/)).toBeNull();
    expect(screen.queryByText(/internal_blob/)).toBeNull();
    expect(screen.getByText("Your standing rule decided")).toBeInTheDocument();
    expect(screen.getByText("The run continued as suggested.")).toBeInTheDocument();
  });

  it("keeps the selected label visible and discloses the rejected server options", () => {
    const checkIn: CheckInOut = {
      boundary: "after_component",
      bundle: null,
      check_in_id: "c1",
      component: "screen_full",
      created_at: "2026-07-28T10:00:00Z",
      kind: "pause",
      options: [
        { id: "continue", label: "Continue with this evidence", description: "", requires_user_input: false, suggested: true, why: null, endorsement: null },
        { id: "adjust", label: "Change the approach", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
      ],
      render: "Screening paused.",
      rerun_component: null,
      segment_reentry_allowed: false,
      sequence: 8,
      stage: "screen",
      status: "decided",
      triggers: [],
    };
    recordSessionAnsweredCheckIn("c1", "Continue with this evidence", ["Change the approach"]);

    render(<AnsweredCheckIn decision={decision({})} checkIn={checkIn} />);

    expect(screen.getByText("Continue with this evidence")).toBeInTheDocument();
    expect(screen.getByText("Other options")).toBeInTheDocument();
    expect(screen.getByText("Change the approach")).toBeInTheDocument();
  });
});
