import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { queryKeys } from "../../../api/queries";
import {
  isPlanningConversation,
  stashFirstMessage,
  takeFirstMessage,
  PLANNING_TAB_ID,
  taskAgentConversationId,
  useActiveConversation,
  useConversationMutations,
} from "./conversationState";

const post = vi.fn(async () => ({ data: { id: "c-new" }, error: undefined }));

vi.mock("../../../api/queries", async () => {
  const actual = await vi.importActual<typeof import("../../../api/queries")>("../../../api/queries");
  return { ...actual, useApiClient: () => ({ POST: post }) };
});

function routerWrapper(initialPath: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(MemoryRouter, { initialEntries: [initialPath] }, children);
  };
}

describe("useActiveConversation", () => {
  it("reads a non-empty chat id from the URL", () => {
    const { result } = renderHook(() => useActiveConversation(), {
      wrapper: routerWrapper("/tasks/p1?chat=c1"),
    });
    expect(result.current.activeConversationId).toBe("c1");
  });

  it('treats a present-but-empty "?chat=" as closed, not a panel bound to id ""', () => {
    const { result } = renderHook(() => useActiveConversation(), {
      wrapper: routerWrapper("/tasks/p1?chat="),
    });
    expect(result.current.activeConversationId).toBeNull();
  });

  it("treats a missing chat param as closed", () => {
    const { result } = renderHook(() => useActiveConversation(), {
      wrapper: routerWrapper("/tasks/p1"),
    });
    expect(result.current.activeConversationId).toBeNull();
  });
});

describe("useConversationMutations", () => {
  it("invalidates the conversations root prefix, reaching filtered consumer queries", async () => {
    const queryClient = new QueryClient();
    // Seeded the way `useConversations(taskId, { kind, status })` keys its
    // cache entry — the bug invalidated a 5-element key with explicit
    // `undefined`s that never partial-matches this filtered key.
    queryClient.setQueryData(queryKeys.conversations("p1", { kind: "chat", status: "active" }), { data: [] });
    // The archived list shares that prefix. A conversation minted active has
    // no business in it — seeded there, it flashes under "Archived" until
    // that list refetches (the Agent tab's sidebar keeps it in cache).
    queryClient.setQueryData(queryKeys.conversations("p1", { status: "archived" }), { data: [] });
    function Wrapper({ children }: { children: ReactNode }) {
      return createElement(QueryClientProvider, { client: queryClient }, children);
    }
    const { result } = renderHook(() => useConversationMutations("p1"), { wrapper: Wrapper });

    await act(async () => {
      await result.current.create(null);
    });

    expect(
      queryClient.getQueryData(queryKeys.conversations("p1", { kind: "chat", status: "active" })),
    ).toEqual({ data: [{ id: "c-new", latest_turn_preview: null }] });
    expect(queryClient.getQueryData(queryKeys.conversation("c-new"))).toEqual({ id: "c-new" });
    expect(queryClient.getQueryData(queryKeys.conversations("p1", { status: "archived" }))).toEqual({ data: [] });
    expect(
      queryClient.getQueryState(queryKeys.conversations("p1", { kind: "chat", status: "active" }))?.isInvalidated,
    ).toBe(true);
  });
});

describe("taskAgentConversationId", () => {
  it("returns the planning row, falling back to the planning tab token", () => {
    expect(taskAgentConversationId([])).toBe(PLANNING_TAB_ID);
    expect(
      taskAgentConversationId([
        { id: "c1", kind: "chat" },
        { id: "p1", kind: "planning" },
      ]),
    ).toBe("p1");
  });

  it("prefers the open planning lineage over any closed one, whatever the list order", () => {
    expect(
      taskAgentConversationId([
        { id: "p3", kind: "planning", closed_at: "2026-09-03T10:00:00Z" },
        { id: "p-open", kind: "planning", closed_at: null },
        { id: "p2", kind: "planning", closed_at: "2026-09-01T10:00:00Z" },
      ]),
    ).toBe("p-open");
  });

  it("falls back to the most recently closed lineage once the run has closed the open one", () => {
    expect(
      taskAgentConversationId([
        { id: "p2", kind: "planning", closed_at: "2026-09-01T10:00:00Z" },
        { id: "p3", kind: "planning", closed_at: "2026-09-03T10:00:00Z" },
        { id: "c1", kind: "chat", closed_at: null },
      ]),
    ).toBe("p3");
  });
});

describe("isPlanningConversation", () => {
  it("treats the planning tab token and a planning row id as planning", () => {
    const rows = [
      { id: "c1", kind: "chat" },
      { id: "p1", kind: "planning" },
    ];
    expect(isPlanningConversation(null, rows)).toBe(false);
    expect(isPlanningConversation("c1", rows)).toBe(false);
    expect(isPlanningConversation("p1", rows)).toBe(true);
    expect(isPlanningConversation(PLANNING_TAB_ID, rows)).toBe(true);
  });
});

describe("first-message hand-off", () => {
  it("hands the stashed message over exactly once", () => {
    stashFirstMessage("c-1", "hello");
    expect(takeFirstMessage("c-1")).toBe("hello");
    expect(takeFirstMessage("c-1")).toBeNull();
    expect(takeFirstMessage("c-2")).toBeNull();
  });
});
