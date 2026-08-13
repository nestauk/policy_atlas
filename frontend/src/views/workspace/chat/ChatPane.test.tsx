import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatPane } from "./ChatPane";

const state = vi.hoisted(() => ({
  rows: [] as unknown[],
  isPending: false,
  isStreaming: false,
  sendTurn: vi.fn(),
  retry: vi.fn(),
  cancelTurn: vi.fn(),
  optimisticTurns: [] as unknown[],
  refetch: vi.fn(),
}));

vi.mock("../../../api/queries", () => ({ useConversation: () => ({ data: undefined }) }));
vi.mock("../../../store", () => ({ useChatConversation: () => state }));
vi.mock("./ContextBar", () => ({ ContextBar: () => null }));
vi.mock("./ChatMessages", () => ({ ChatMessages: () => <div data-testid="messages" /> }));
vi.mock("./ChatComposer", () => ({
  ChatComposer: ({ disabledReason }: { disabledReason?: string | null }) => (
    <div data-testid="composer">{disabledReason ?? ""}</div>
  ),
}));

describe("ChatPane — composer fencing (contract strand 6: fence states show why)", () => {
  it("gives the pending-turn reason when a durable turn is pending but this client isn't streaming it (e.g. after a reload)", () => {
    state.rows = [{ id: "t1", status: "pending", client_turn_id: "ct1" }];
    state.isStreaming = false;
    render(<ChatPane projectId="p1" conversationId="c1" onOpenPlanning={vi.fn()} />);
    expect(screen.getByTestId("composer")).toHaveTextContent("Waiting for the current answer…");
  });

  it("leaves the composer reason empty once this client owns the stream (the Stop bar covers it instead)", () => {
    state.rows = [{ id: "t1", status: "pending", client_turn_id: "ct1" }];
    state.isStreaming = true;
    render(<ChatPane projectId="p1" conversationId="c1" onOpenPlanning={vi.fn()} />);
    expect(screen.getByTestId("composer")).toHaveTextContent("");
  });

  it("leaves the composer reason empty with no pending turn at all", () => {
    state.rows = [{ id: "t1", status: "completed", client_turn_id: "ct1" }];
    state.isStreaming = false;
    render(<ChatPane projectId="p1" conversationId="c1" onOpenPlanning={vi.fn()} />);
    expect(screen.getByTestId("composer")).toHaveTextContent("");
  });
});
