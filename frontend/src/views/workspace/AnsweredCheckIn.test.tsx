import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResolvedDecision } from "../../store";
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
});
