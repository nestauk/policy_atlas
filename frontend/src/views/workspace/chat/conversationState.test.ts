import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "../../../api/queries";
import {
  isChatUnread,
  isPlanningConversation,
  markChatSeen,
  recentChats,
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

describe("new-reply marks", () => {
  // This jsdom exposes no working localStorage: stand one in for the marks.
  const store = new Map<string, string>();
  beforeEach(() => {
    store.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  const chat = (id: string, reply: string | null, at = "2026-09-05T10:00:00Z") => ({
    id,
    kind: "chat" as const,
    title: `Chat ${id}`,
    latest_turn_preview: { at, user_message: "q", reply_snippet: reply },
  });

  it("dots a reply until it has been on screen, and clears it once seen", () => {
    expect(isChatUnread(chat("c-1", null))).toBe(false); // no answer yet
    const answered = chat("c-1", "An answer.");
    expect(isChatUnread(answered)).toBe(true);
    markChatSeen(answered);
    expect(isChatUnread(answered)).toBe(false);
    // A later reply is new again.
    expect(isChatUnread(chat("c-1", "Another.", "2026-09-05T11:00:00Z"))).toBe(true);
  });

  it("lists the newest chats only, never dotting the one on show", () => {
    const rows = [
      { id: "p-1", kind: "planning" as const, title: "Planning", latest_turn_preview: null },
      ...["c-1", "c-2", "c-3", "c-4", "c-5"].map((id) => chat(id, "reply")),
    ];
    const marks = recentChats(rows, "c-2");
    expect(marks.map((mark) => mark.id)).toEqual(["c-1", "c-2", "c-3", "c-4"]);
    expect(marks.map((mark) => mark.unread)).toEqual([true, false, true, true]);
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
