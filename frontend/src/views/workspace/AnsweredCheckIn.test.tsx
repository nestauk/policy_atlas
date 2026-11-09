import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResolvedDecision, StageEntry } from "../../store";
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

const STAGES: StageEntry[] = [
  { stage: "acquire", label: "Searching and screening", status: "completed" } as StageEntry,
];

const CHECK_IN: CheckInOut = {
  boundary: "after_component",
  bundle: null,
  check_in_id: "c1",
  component: "acquire",
  created_at: "2026-07-28T10:00:00Z",
  kind: "steer_point",
  options: [
    { id: "continue", label: "Looks right, assess these", description: "", requires_user_input: false, suggested: true, why: null, endorsement: null },
    { id: "deepen_search", label: "Search deeper", description: "", requires_user_input: false, suggested: false, why: null, endorsement: null },
  ],
  render: "Does this look right before I assess the sources?",
  rerun_component: null,
  segment_reentry_allowed: false,
  sequence: 8,
  stage: "acquire",
  status: "decided",
  triggers: [],
};

describe("AnsweredCheckIn (task 058, N19)", () => {
  it("builds You chose from the durable frame: the option's own label and where it sat", () => {
    render(
      <AnsweredCheckIn
        decision={decision({ response: { kind: "option", option_id: "continue", params: null } })}
        checkIn={CHECK_IN}
        stages={STAGES}
      />,
    );
    expect(
      screen.getByText("You chose: Looks right, assess these · after searching and screening"),
    ).toBeInTheDocument();
  });

  it("reads the same with nothing in session storage (a reload, another device)", () => {
    window.sessionStorage.clear();
    render(
      <AnsweredCheckIn
        decision={decision({ response: { kind: "option", option_id: "deepen_search" } })}
        checkIn={CHECK_IN}
        stages={STAGES}
      />,
    );
    expect(screen.getByText(/^You chose: Search deeper/)).toBeInTheDocument();
  });

  it("words a stop and a free-text steer", () => {
    const { rerender } = render(
      <AnsweredCheckIn decision={decision({ response: { kind: "abort" } })} checkIn={CHECK_IN} stages={STAGES} />,
    );
    expect(screen.getByText("You chose: Stop the run · after searching and screening")).toBeInTheDocument();
    rerender(
      <AnsweredCheckIn
        decision={decision({ response: { text: "prioritise UK school-based studies" } })}
        checkIn={CHECK_IN}
        stages={STAGES}
      />,
    );
    expect(screen.getByText(/^You chose: prioritise UK school-based studies/)).toBeInTheDocument();
  });

  it("attributes a decision the Agent took to the Agent (038 V4)", () => {
    render(
      <AnsweredCheckIn
        decision={decision({ decidedBy: "agent", response: { option_id: "continue" } })}
        checkIn={CHECK_IN}
        stages={STAGES}
      />,
    );
    expect(screen.getByText(/^The Agent decided: Looks right, assess these/)).toBeInTheDocument();
  });

  it("never renders raw params or ids", () => {
    render(
      <AnsweredCheckIn
        decision={decision({
          response: { option_id: "raw_id_should_not_render", internal_blob: "x9" },
          decidedBy: "standing_default",
        })}
        stages={STAGES}
      />,
    );
    expect(screen.queryByText(/raw_id_should_not_render/)).toBeNull();
    expect(screen.queryByText(/internal_blob/)).toBeNull();
    expect(screen.getByText("The run continued as suggested.")).toBeInTheDocument();
  });
});
