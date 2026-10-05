import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
import { useChatTurns, useMe, useTask } from "./queries";

const conversationId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

function makeAuth(): AuthApi {
  return {
    getAccessToken: vi.fn(async () => "token-a"),
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    user: { sub: "user-1" },
    status: "authenticated",
  };
}

function wrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      AuthContext.Provider,
      { value: makeAuth() },
      createElement(QueryClientProvider, { client: queryClient }, children),
    );
  };
}

function chatTurn(index: number) {
  return {
    id: `t${index}`,
    conversation_id: conversationId,
    turn_index: index,
    client_turn_id: `ct${index}`,
    user_message: "q",
    answer: "a",
    status: "completed",
    created_at: "2026-08-11T10:00:00Z",
    completed_at: "2026-08-11T10:00:02Z",
    claims: [],
    citations: [],
    enrichment: null,
    warning_not_evidence_checked: false,
    handoff: null,
    stopped_before_evidence_check: false,
  };
}

beforeEach(() => {
  // Node's fetch (undici) rejects relative URLs; the app's same-origin ""
  // base is a browser affordance — an absolute base keeps stubs intercepting.
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:3000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("useChatTurns", () => {
  it("walks every page and accumulates turns past the server's page cap (fix: chats >50 turns silently lost the newest ones)", async () => {
    const totalItems = 210;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      // `input` may be a `Request` (not a bare string/URL) — `String(request)`
      // is `"[object Request]"`, not its URL, so read `.url` explicitly.
      const url = new URL(input instanceof Request ? input.url : String(input), "http://localhost:3000");
      const page = Number(url.searchParams.get("page") ?? "1");
      const pageSize = Number(url.searchParams.get("page_size") ?? "200");
      const start = (page - 1) * pageSize;
      const data = Array.from(
        { length: Math.max(0, Math.min(pageSize, totalItems - start)) },
        (_, i) => chatTurn(start + i),
      );
      return new Response(
        JSON.stringify({ data, pagination: { page, page_size: pageSize, total_items: totalItems } }),
        { headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useChatTurns(conversationId), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.data?.data).toHaveLength(totalItems));
    // 200 (server max) is requested directly, so a 210-turn chat needs
    // exactly one extra round trip, not five default-sized ones.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.data?.data.at(-1)).toMatchObject({ id: "t209" });
  });

  it("stops after one page when the first page is already short", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ data: [chatTurn(0)], pagination: { page: 1, page_size: 200, total_items: 1 } }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useChatTurns(conversationId), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.data?.data).toHaveLength(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

function meResponse(body: unknown) {
  return async () => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
}

const unenrolledMe = {
  user_id: "u1",
  display_name: "Ada Lovelace",
  email: null,
  organisation: null,
  is_admin: false,
};

const enrolledMe = {
  user_id: "u1",
  display_name: "Ada Lovelace",
  email: "ada@example.gov.uk",
  organisation: { org_id: "org-1", name: "Department for Local Growth" },
  is_admin: false,
};

describe("useMe", () => {
  it("resolves an unenrolled caller — organisation: null", async () => {
    const fetchMock = vi.fn(meResponse(unenrolledMe));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMe(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.organisation).toBeNull();
  });

  it("resolves an enrolled caller's organisation", async () => {
    const fetchMock = vi.fn(meResponse(enrolledMe));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMe(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.organisation?.name).toBe("Department for Local Growth");
  });

  it("does not refetch across a remount sharing a QueryClient (documented staleTime: Infinity)", async () => {
    const fetchMock = vi.fn(meResponse(unenrolledMe));
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = ({ children }: { children: ReactNode }) =>
      createElement(
        AuthContext.Provider,
        { value: makeAuth() },
        createElement(QueryClientProvider, { client: queryClient }, children),
      );

    const first = renderHook(() => useMe(), { wrapper: Wrapper });
    await waitFor(() => expect(first.result.current.data).toBeDefined());
    first.unmount();

    const second = renderHook(() => useMe(), { wrapper: Wrapper });
    await waitFor(() => expect(second.result.current.data).toBeDefined());

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("useTask", () => {
  it("does not retry a 404 (task 037: an anonymous read must fail fast, not after ~7s of retries)", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { code: "not_found", message: "not found" } }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTask(conversationId), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect((result.current.error as Error & { status?: number }).status).toBe(404);
  });
});
