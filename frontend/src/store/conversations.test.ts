import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
import {
  ChatStreamProtocolError,
  chatTranscriptRows,
  consumeChatStream,
  initialOptimisticChatTranscriptState,
  reduceOptimisticChatTranscript,
  retryInputForOptimisticChatTurn,
  useChatConversation,
  useComposerDraft,
} from "./conversations";
import type { ChatTurn, OptimisticChatTurn } from "./conversations";

const conversationId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const clientTurnId = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const turnId = "cccccccc-cccc-cccc-cccc-cccccccccccc";

const optimisticTurn: OptimisticChatTurn = {
  clientTurnId,
  userMessage: "What does the evidence say?",
  createdAt: "2026-08-11T10:00:00Z",
  answer: "",
  status: "pending",
  activityLabels: [],
};

function chatTurn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  return {
    id: turnId,
    conversation_id: conversationId,
    turn_index: 0,
    client_turn_id: clientTurnId,
    user_message: optimisticTurn.userMessage,
    answer: "A grounded answer.",
    status: "completed",
    created_at: "2026-08-11T10:00:00Z",
    completed_at: "2026-08-11T10:00:02Z",
    claims: [],
    citations: [],
    enrichment: null,
    warning_not_evidence_checked: false,
    handoff: null,
    stopped_before_evidence_check: false,
    ...overrides,
  };
}

function ndjsonResponse(lines: unknown[]): Response {
  const body = new TextEncoder().encode(lines.map((line) => `${JSON.stringify(line)}\n`).join(""));
  return new Response(new ReadableStream({ start: (controller) => { controller.enqueue(body); controller.close(); } }));
}

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

function hookWrapper(auth = makeAuth()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      AuthContext.Provider,
      { value: auth },
      createElement(QueryClientProvider, { client: queryClient }, children),
    );
  };
}

function requestInfo(input: RequestInfo | URL, init?: RequestInit) {
  // Node's Request rejects relative URLs; the app requests them (same-origin
  // proxy base), so resolve strings by hand instead of constructing Request.
  if (input instanceof Request) return { method: input.method, url: input.url };
  return { method: init?.method ?? "GET", url: String(input) };
}

beforeEach(() => {
  // Node's fetch (undici) rejects relative URLs; the app's same-origin ""
  // base is a browser affordance. Absolute base keeps the stubs intercepting.
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:3000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

describe("optimistic chat transcript", () => {
  it("adds immediately, retains retry input, and replaces the local row with the terminal payload", () => {
    const submitted = reduceOptimisticChatTranscript(initialOptimisticChatTranscriptState, {
      type: "submitted",
      turn: optimisticTurn,
    });
    const failed = reduceOptimisticChatTranscript(submitted, {
      type: "failed",
      clientTurnId,
      errorMessage: "The provider is unavailable.",
    });
    expect(retryInputForOptimisticChatTurn(failed, clientTurnId)).toEqual({
      message: optimisticTurn.userMessage,
      clientTurnId,
    });

    const completed = reduceOptimisticChatTranscript(failed, {
      type: "completed",
      clientTurnId,
      turn: chatTurn(),
    });
    expect(completed.turns).toEqual([chatTurn()]);
    expect(chatTranscriptRows([chatTurn()], completed.turns)).toEqual([chatTurn()]);
  });
});

describe("consumeChatStream", () => {
  it("dispatches progress and deltas in order, then ignores post-terminal frames", async () => {
    const events: string[] = [];
    await consumeChatStream(
      ndjsonResponse([
        { type: "progress", label: "Searching the evidence…" },
        { type: "delta", text: "First " },
        { type: "delta", text: "answer." },
        { type: "completed", turn: chatTurn() },
        { type: "delta", text: "ignored" },
      ]).body!,
      (event) => events.push(event.type),
    );
    expect(events).toEqual(["progress", "delta", "delta", "completed"]);
  });

  it("preserves a failed terminal event and rejects malformed NDJSON without crashing", async () => {
    const events: string[] = [];
    await consumeChatStream(
      ndjsonResponse([{ type: "failed", turn_id: turnId, error: { code: "provider", message: "No answer." } }]).body!,
      (event) => events.push(event.type),
    );
    expect(events).toEqual(["failed"]);

    const malformed = new Response(new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode("not json\n")); controller.close(); },
    }));
    await expect(consumeChatStream(malformed.body!, () => undefined)).rejects.toBeInstanceOf(ChatStreamProtocolError);
  });
});

describe("useChatConversation", () => {
  it("turns a malformed stream line into an honest retryable error row", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (requestInfo(input, init).method === "POST") {
        return new Response(new ReadableStream({
          start(controller) { controller.enqueue(new TextEncoder().encode("not json\n")); controller.close(); },
        }));
      }
      return new Response(JSON.stringify({ data: [], pagination: { page: 1, page_size: 50, total_items: 0 } }), {
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChatConversation(conversationId), { wrapper: hookWrapper() });

    await act(async () => {
      await expect(result.current.sendTurn(optimisticTurn.userMessage, clientTurnId)).rejects.toBeInstanceOf(ChatStreamProtocolError);
    });
    expect(result.current.optimisticTurns).toMatchObject([{ status: "failed" }]);
  });

  it("streams an answer and applies a cancel response without double-applying the later terminal frame", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestInfo(input, init);
      if (request.method === "POST" && request.url.endsWith(`/turns/${turnId}/cancel`)) {
        return new Response(JSON.stringify({ status: "cancelled" }), { headers: { "Content-Type": "application/json" } });
      }
      if (request.method === "POST") {
        return ndjsonResponse([
          { type: "delta", text: "Partial answer." },
          { type: "cancelled", turn: chatTurn({ status: "cancelled", answer: "Partial answer." }) },
          { type: "completed", turn: chatTurn() },
        ]);
      }
      return new Response(JSON.stringify({
        data: [chatTurn({ status: "cancelled", answer: "Partial answer." })],
        pagination: { page: 1, page_size: 50, total_items: 1 },
      }), {
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChatConversation(conversationId), { wrapper: hookWrapper() });

    await act(async () => { await result.current.sendTurn(optimisticTurn.userMessage, clientTurnId); });
    expect(result.current.rows.find((row) => "id" in row && row.id === turnId)).toMatchObject({ status: "cancelled" });

    await act(async () => { await result.current.cancelTurn(turnId); });
    expect(fetchMock.mock.calls.some((call) => requestInfo(call[0], call[1]).url.endsWith(`/turns/${turnId}/cancel`))).toBe(true);
  });

  it("polls pending enrichment every three seconds, stops once enriched, and clears polling on unmount", async () => {
    vi.useFakeTimers();
    let turnReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestInfo(input, init);
      if (request.method === "POST") {
        return ndjsonResponse([{ type: "completed", turn: chatTurn({ enrichment: { status: "pending" } }) }]);
      }
      turnReads += 1;
      const status = turnReads >= 4 ? "enriched" : "pending";
      return new Response(JSON.stringify({
        data: [chatTurn({ enrichment: { status } })],
        pagination: { page: 1, page_size: 50, total_items: 1 },
      }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useChatConversation(conversationId), { wrapper: hookWrapper() });

    await act(async () => { await result.current.sendTurn(optimisticTurn.userMessage, clientTurnId); });
    await act(async () => { await vi.advanceTimersByTimeAsync(9_000); });
    expect(turnReads).toBeGreaterThanOrEqual(3);
    const readsAfterEnrichment = turnReads;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(turnReads).toBe(readsAfterEnrichment);

    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(turnReads).toBe(readsAfterEnrichment);
    vi.useRealTimers();
  });

  it("honours the sixty-second poll cap without pretending pending enrichment settled", async () => {
    vi.useFakeTimers();
    let turnReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (requestInfo(input, init).method === "POST") {
        return ndjsonResponse([{ type: "completed", turn: chatTurn({ enrichment: { status: "pending" } }) }]);
      }
      turnReads += 1;
      return new Response(JSON.stringify({
        data: [chatTurn({ enrichment: { status: "pending" } })],
        pagination: { page: 1, page_size: 50, total_items: 1 },
      }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useChatConversation(conversationId), { wrapper: hookWrapper() });

    await act(async () => { await result.current.sendTurn(optimisticTurn.userMessage, clientTurnId); });
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    const readsAtCap = turnReads;
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(turnReads).toBe(readsAtCap);
    expect(result.current.rows.find((row) => "id" in row && row.id === turnId)).toMatchObject({
      enrichment: { status: "pending" },
    });
  });

  it("cancels a pending enrichment timer when the conversation unmounts", async () => {
    vi.useFakeTimers();
    let turnReads = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (requestInfo(input, init).method === "POST") {
        return ndjsonResponse([{ type: "completed", turn: chatTurn({ enrichment: { status: "pending" } }) }]);
      }
      turnReads += 1;
      return new Response(JSON.stringify({
        data: [chatTurn({ enrichment: { status: "pending" } })],
        pagination: { page: 1, page_size: 50, total_items: 1 },
      }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { result, unmount } = renderHook(() => useChatConversation(conversationId), { wrapper: hookWrapper() });

    await act(async () => { await result.current.sendTurn(optimisticTurn.userMessage, clientTurnId); });
    const readsBeforeUnmount = turnReads;
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(turnReads).toBe(readsBeforeUnmount);
  });
});

describe("useComposerDraft", () => {
  it("persists drafts per conversation in sessionStorage and restores them after a switch", () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useComposerDraft(id),
      { initialProps: { id: conversationId } },
    );
    act(() => result.current[1]("A session-local draft"));
    expect(result.current[0]).toBe("A session-local draft");

    rerender({ id: "dddddddd-dddd-dddd-dddd-dddddddddddd" });
    expect(result.current[0]).toBe("");
    rerender({ id: conversationId });
    expect(result.current[0]).toBe("A session-local draft");
  });
});
