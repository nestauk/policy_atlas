import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "../../../ui/radix/Tooltip";

import type { ChatTurn, OptimisticChatTurn } from "../../../store";
import { ChatMessages } from "./ChatMessages";

function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  // `state: "verdict:<tier>"` is the only shape the floor's allowlist can
  // ever emit — a bare `grounding_tier`/`verdict` key on the citation is
  // dead-payload territory (ChatMessages no longer reads it).
  return { id: "t1", client_turn_id: "ct1", conversation_id: "c1", turn_index: 0, created_at: "2026-08-11T10:00:00Z", completed_at: "2026-08-11T10:01:00Z", user_message: "What changed?", answer: "Costs fell [1]", status: "completed", stopped_before_evidence_check: false, warning_not_evidence_checked: false, citations: [{ id: "chunk-1", quote: "Costs fell", state: "verdict:tier_2" }], claims: [], ...overrides };
}

function optimisticTurn(overrides: Partial<OptimisticChatTurn> = {}): OptimisticChatTurn {
  return { clientTurnId: "ct-opt", userMessage: "What does the evidence say?", createdAt: "2026-08-11T10:00:00Z", answer: "", status: "pending", activityLabels: [], ...overrides };
}

describe("ChatMessages", () => {
  it("renders citation markers, references, verdicts, warnings and handoff", async () => {
    const openPlanning = vi.fn();
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[turn({ warning_not_evidence_checked: true, handoff: "evidence_not_held" }), turn({ id: "t2", client_turn_id: "ct2", status: "cancelled", stopped_before_evidence_check: true, answer: "Partial" })]} onOpenPlanning={openPlanning} onRetry={vi.fn()} /></TooltipProvider>);
    expect(screen.getAllByRole("button", { name: "[1]" })).not.toHaveLength(0);
    expect(screen.getAllByText("Tier 2 · grounded").length).toBeGreaterThan(0);
    expect(screen.getByText("Not evidence-checked")).toBeInTheDocument();
    expect(screen.getByText("Stopped before evidence check")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Open planning" }));
    expect(openPlanning).toHaveBeenCalledOnce();
  });

  it("shows an unresolved citation as unchecked and a failed one as flagged", () => {
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[turn({ id: "t3", client_turn_id: "ct3", answer: "Costs fell [1] and uptake held [2]", citations: [{ id: "chunk-1", quote: "Costs fell" }, { id: "chunk-2", quote: "Uptake held", state: "verdict:unsupported_mis_cited" }] })]} onOpenPlanning={vi.fn()} onRetry={vi.fn()} /></TooltipProvider>);
    expect(screen.getByText("Unchecked · awaiting evidence check")).toBeInTheDocument();
    expect(screen.getByText("Unsupported — flagged")).toBeInTheDocument();
  });

  it("ignores a bare grounding_tier/verdict key on the citation itself (dead payload shape)", () => {
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[turn({ id: "t3b", client_turn_id: "ct3b", answer: "Costs fell [1]", citations: [{ id: "chunk-1", quote: "Costs fell", grounding_tier: "tier_2", verdict: "tier_2" }] })]} onOpenPlanning={vi.fn()} onRetry={vi.fn()} /></TooltipProvider>);
    expect(screen.getByText("Unchecked · awaiting evidence check")).toBeInTheDocument();
    expect(screen.queryByText("Tier 2 · grounded")).not.toBeInTheDocument();
  });

  it("renders a still-streaming optimistic turn's activity summary and partial prose", () => {
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[optimisticTurn({ activityLabels: ["Searching sources", "Reading passages"], answer: "Costs fell so " })]} onOpenPlanning={vi.fn()} onRetry={vi.fn()} /></TooltipProvider>);
    expect(screen.getByText("Reading passages — 2 searches")).toBeInTheDocument();
    expect(screen.getByText("Costs fell so", { exact: false })).toBeInTheDocument();
  });

  it("renders a failed turn honestly with a known conflict sentence and a wired retry", async () => {
    const onRetry = vi.fn();
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[optimisticTurn({ status: "failed", errorCode: "chat_turn_in_progress", errorMessage: "a chat turn is already running" })]} onOpenPlanning={vi.fn()} onRetry={onRetry} /></TooltipProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent("A chat turn is already running. Refresh to see it finish.");
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledWith("ct-opt");
  });

  it("falls back to a generic honest sentence for an unrecognised or durable (code-less) failure", () => {
    render(<TooltipProvider><ChatMessages projectId="p1" rows={[turn({ id: "t4", client_turn_id: "ct4", status: "failed", answer: null })]} onOpenPlanning={vi.fn()} onRetry={vi.fn()} /></TooltipProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent("This answer failed.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
