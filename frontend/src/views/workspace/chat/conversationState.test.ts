import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { queryKeys } from "../../../api/queries";
import {
  isPlanningConversation,
  PLANNING_TAB_ID,
  planningConversationId,
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
      wrapper: routerWrapper("/projects/p1?chat=c1"),
    });
    expect(result.current.activeConversationId).toBe("c1");
  });

  it('treats a present-but-empty "?chat=" as closed, not a panel bound to id ""', () => {
    const { result } = renderHook(() => useActiveConversation(), {
      wrapper: routerWrapper("/projects/p1?chat="),
    });
    expect(result.current.activeConversationId).toBeNull();
  });

  it("treats a missing chat param as closed", () => {
    const { result } = renderHook(() => useActiveConversation(), {
      wrapper: routerWrapper("/projects/p1"),
    });
    expect(result.current.activeConversationId).toBeNull();
  });
});

describe("useConversationMutations", () => {
  it("invalidates the conversations root prefix, reaching filtered consumer queries", async () => {
    const queryClient = new QueryClient();
    // Seeded the way `useConversations(projectId, { kind, status })` keys its
    // cache entry — the bug invalidated a 5-element key with explicit
    // `undefined`s that never partial-matches this filtered key.
    queryClient.setQueryData(queryKeys.conversations("p1", { kind: "chat", status: "active" }), { data: [] });
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
    expect(
      queryClient.getQueryState(queryKeys.conversations("p1", { kind: "chat", status: "active" }))?.isInvalidated,
    ).toBe(true);
  });
});

describe("planningConversationId", () => {
  it("returns the newest planning row, falling back to the planning tab token", () => {
    expect(planningConversationId([])).toBe(PLANNING_TAB_ID);
    expect(
      planningConversationId([
        { id: "c1", kind: "chat" },
        { id: "p1", kind: "planning" },
      ]),
    ).toBe("p1");
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
