import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatSidePanel } from "./ChatSidePanel";

/*
 * The sidebar on a theory of change (task 054's 058 alignment, decision 11,
 * A10): it no longer opens by itself on the Task Agent; the run status bar
 * shows the run.
 */

const state = vi.hoisted(() => ({ setActiveConversation: vi.fn() }));

vi.mock("../../planPanel", () => ({ usePlanPanel: () => ({ open: false, openPlan: vi.fn(), closePlan: vi.fn() }) }));
vi.mock("react-router", () => ({ useNavigate: () => vi.fn(), Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a> }));
vi.mock("../../../api/queries", () => ({
  useToc: () => ({ data: undefined }),
  useConversations: () => ({
    data: { data: [{ id: "ta-1", kind: "task_agent", status: "active", closed_at: null, title: "Task Agent", created_at: "2026-11-09T10:00:00Z", entry_artefact_id: null, latest_turn_preview: null }] },
    isSuccess: true,
  }),
  useArtefact: () => ({ data: null }),
  useTask: () => ({ data: { task_id: "t1", capability: "theory_of_change", latest_run: null } }),
}));
vi.mock("./conversationState", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./conversationState")>();
  return {
    ...actual,
    useActiveConversation: () => ({ activeConversationId: null, draftEntryArtefactId: null, setActiveConversation: state.setActiveConversation, openDraftChat: vi.fn() }),
    useConversationMutations: () => ({ create: vi.fn(), archive: vi.fn() }),
  };
});
vi.mock("../../../store", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../store")>();
  return { ...actual, useRunStream: () => actual.createInitialRunStreamState() };
});
vi.mock("../TaskAgentPane", () => ({ TaskAgentPane: () => <div data-testid="task_agent-pane" /> }));

describe("ChatSidePanel on a theory of change", () => {
  it("stays shut until the reader opens it (decision 11)", () => {
    render(<ChatSidePanel taskId="t1" isOwner />);
    expect(state.setActiveConversation).not.toHaveBeenCalled();
  });
});
