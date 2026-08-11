import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ChatTurn, OptimisticChatTurn } from "../../../store";
import { ChatMessages } from "./ChatMessages";

function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  return { id: "t1", client_turn_id: "ct1", conversation_id: "c1", turn_index: 0, created_at: "2026-08-11T10:00:00Z", completed_at: "2026-08-11T10:01:00Z", user_message: "What changed?", answer: "Costs fell [1]", status: "completed", stopped_before_evidence_check: false, warning_not_evidence_checked: false, citations: [{ id: "chunk-1", quote: "Costs fell", grounding_tier: "tier_2" }], claims: [], ...overrides };
}

function optimisticTurn(overrides: Partial<OptimisticChatTurn> = {}): OptimisticChatTurn {
  return { clientTurnId: "ct-opt", userMessage: "What does the evidence say?", createdAt: "2026-08-11T10:00:00Z", answer: "", status: "pending", activityLabels: [], ...overrides };
}

describe("ChatMessages", () => {
  it("renders citation markers, references, verdicts, warnings and handoff", async () => {
    const openPlanning = vi.fn();
    render(<ChatMessages projectId="p1" rows={[turn({ warning_not_evidence_checked: true, handoff: "evidence_not_held" }), turn({ id: "t2", client_turn_id: "ct2", status: "cancelled", stopped_before_evidence_check: true, answer: "Partial" })]} onOpenPlanning={openPlanning} />);
    expect(screen.getAllByRole("button", { name: "[1]" })).not.toHaveLength(0);
    expect(screen.getAllByText("Tier 2 · grounded").length).toBeGreaterThan(0);
    expect(screen.getByText("Not evidence-checked")).toBeInTheDocument();
    expect(screen.getByText("Stopped before evidence check")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Open planning" }));
    expect(openPlanning).toHaveBeenCalledOnce();
  });

  it("shows an unresolved citation as unchecked and a failed one as flagged", () => {
    render(<ChatMessages projectId="p1" rows={[turn({ id: "t3", client_turn_id: "ct3", answer: "Costs fell [1] and uptake held [2]", citations: [{ id: "chunk-1", quote: "Costs fell" }, { id: "chunk-2", quote: "Uptake held", grounding_tier: "unsupported_mis_cited" }] })]} onOpenPlanning={vi.fn()} />);
    expect(screen.getByText("Unchecked · awaiting evidence check")).toBeInTheDocument();
    expect(screen.getByText("Unsupported — flagged")).toBeInTheDocument();
  });

  it("renders a still-streaming optimistic turn's activity summary and partial prose", () => {
    render(<ChatMessages projectId="p1" rows={[optimisticTurn({ activityLabels: ["Searching sources", "Reading passages"], answer: "Costs fell so " })]} onOpenPlanning={vi.fn()} />);
    expect(screen.getByText("Reading passages — 2 searches")).toBeInTheDocument();
    expect(screen.getByText("Costs fell so", { exact: false })).toBeInTheDocument();
  });
});
