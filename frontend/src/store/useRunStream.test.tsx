import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SseFrame } from "../api/sseFrame";
import {
  RUN_STREAM_INVALIDATE_DEBOUNCE_MS,
  RunStreamProvider,
  useRunStream,
} from "./useRunStream";

const sseState = vi.hoisted(() => ({
  onFrame: null as null | ((frame: SseFrame) => void),
  close: vi.fn(),
}));

vi.mock("../api/sse", () => ({
  connectEventStream: (options: { onFrame: (frame: SseFrame) => void }) => {
    sseState.onFrame = options.onFrame;
    return { close: sseState.close };
  },
}));

const authApi = vi.hoisted(() => ({
  getAccessToken: async () => "token",
  onUnauthenticated: vi.fn(),
}));

vi.mock("../auth", () => ({
  useAuth: () => authApi,
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

describe("RunStreamProvider / useRunStream", () => {
  beforeEach(() => {
    sseState.onFrame = null;
    sseState.close.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shares one connection's state with consumers", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useRunStream(PROJECT_ID), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
          <RunStreamProvider projectId={PROJECT_ID}>{children}</RunStreamProvider>
        </QueryClientProvider>
      ),
    });
    expect(result.current.connectionStatus).toBe("connecting");
    expect(sseState.onFrame).not.toBeNull();
  });

  it("coalesces stage.completed invalidations into one trailing refresh", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateQueries = vi.spyOn(client, "invalidateQueries").mockResolvedValue(undefined);

    renderHook(() => useRunStream(PROJECT_ID), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
          <RunStreamProvider projectId={PROJECT_ID}>{children}</RunStreamProvider>
        </QueryClientProvider>
      ),
    });
    expect(sseState.onFrame).not.toBeNull();

    act(() => {
      sseState.onFrame?.({
        type: "stage.completed",
        stage: "screen",
        label: "Screening",
        summary: { included: 10 },
        seconds: 5,
        occurred_at: "2026-07-21T10:00:05Z",
        sequence: 1,
      });
      sseState.onFrame?.({
        type: "stage.completed",
        stage: "classify",
        label: "Classifying",
        summary: {},
        seconds: 2,
        occurred_at: "2026-07-21T10:00:07Z",
        sequence: 2,
      });
      sseState.onFrame?.({
        type: "run.status",
        capability_run_id: "r1",
        status: "succeeded",
        occurred_at: "2026-07-21T10:00:08Z",
        sequence: 3,
      });
    });

    expect(invalidateQueries).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    });
    expect(invalidateQueries).toHaveBeenCalledTimes(1);
  });

  it("throws when used outside the provider", () => {
    expect(() => renderHook(() => useRunStream(PROJECT_ID))).toThrow(/RunStreamProvider/);
  });

  it("closes the connection on unmount", () => {
    const { unmount } = render(
      <QueryClientProvider client={new QueryClient()}>
        <RunStreamProvider projectId={PROJECT_ID}>
          <div />
        </RunStreamProvider>
      </QueryClientProvider>,
    );
    expect(sseState.onFrame).not.toBeNull();
    unmount();
    expect(sseState.close).toHaveBeenCalled();
  });
});
