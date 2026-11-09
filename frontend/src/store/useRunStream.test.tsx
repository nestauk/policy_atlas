import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SseFrame } from "../api/sseFrame";
import {
  INGEST_REFRESH_THROTTLE_MS,
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

const TASK_ID = "11111111-1111-1111-1111-111111111111";

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
    const { result } = renderHook(() => useRunStream(TASK_ID), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
          <RunStreamProvider taskId={TASK_ID}>{children}</RunStreamProvider>
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

    renderHook(() => useRunStream(TASK_ID), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
          <RunStreamProvider taskId={TASK_ID}>{children}</RunStreamProvider>
        </QueryClientProvider>
      ),
    });
    expect(sseState.onFrame).not.toBeNull();

    act(() => {
      sseState.onFrame?.({
        type: "stage.completed", capability_run_id: null,
        stage: "screen",
        label: "Screening",
        summary: { included: 10 },
        seconds: 5,
        occurred_at: "2026-07-21T10:00:05Z",
        sequence: 1,
      });
      sseState.onFrame?.({
        type: "stage.completed", capability_run_id: null,
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

  function mountWithSpy() {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateQueries = vi.spyOn(client, "invalidateQueries").mockResolvedValue(undefined);
    renderHook(() => useRunStream(TASK_ID), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>
          <RunStreamProvider taskId={TASK_ID}>{children}</RunStreamProvider>
        </QueryClientProvider>
      ),
    });
    const invalidatedKeys = () =>
      invalidateQueries.mock.calls.map((call) => (call[0] as { queryKey: unknown[] }).queryKey);
    return { invalidateQueries, invalidatedKeys };
  }

  const status = (id: string, value: "running" | "succeeded", sequence: number): SseFrame => ({
    type: "run.status",
    capability_run_id: id,
    status: value,
    occurred_at: "2026-07-21T10:00:00Z",
    sequence,
  });

  const tick = (stage: "ingest" | "classify"): SseFrame => ({
    type: "tick",
    activity: "Reading full texts",
    capability_run_id: null,
    stage,
    done: null,
    total: null,
    unit: null,
    section: null,
    heartbeat: false,
    dropped: 0,
    occurred_at: "2026-07-21T10:00:00Z",
    ephemeral: true,
  });

  it("a parent stage.completed refreshes every query under the task", async () => {
    const { invalidatedKeys } = mountWithSpy();
    act(() => {
      sseState.onFrame?.(status("walk", "running", 1));
      sseState.onFrame?.({
        type: "stage.completed", capability_run_id: "walk",
        stage: "acquire", label: "Searching", summary: {}, seconds: 3,
        occurred_at: "2026-07-21T10:00:03Z", sequence: 2,
      });
    });
    await act(async () => {
      vi.advanceTimersByTime(RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    });
    expect(invalidatedKeys()).toEqual([["tasks", TASK_ID]]);
  });

  it("a child walk's frames refresh the options query only (task 058, N23)", async () => {
    const { invalidatedKeys } = mountWithSpy();
    act(() => sseState.onFrame?.(status("walk", "running", 1)));
    await act(async () => {
      vi.advanceTimersByTime(RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    });
    expect(invalidatedKeys()).toEqual([["tasks", TASK_ID]]);

    act(() => {
      sseState.onFrame?.(status("child", "running", 2));
      sseState.onFrame?.({
        type: "stage.completed", capability_run_id: "child",
        stage: "acquire", label: "Searching", summary: { found: 12 }, seconds: 4,
        occurred_at: "2026-07-21T10:00:04Z", sequence: 3,
      });
      sseState.onFrame?.(status("child", "succeeded", 4));
    });
    await act(async () => {
      vi.advanceTimersByTime(RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    });
    expect(invalidatedKeys()).toEqual([["tasks", TASK_ID], ["tasks", TASK_ID, "options"]]);
  });

  it("a window with both parent and child frames refreshes everything once", async () => {
    const { invalidatedKeys } = mountWithSpy();
    act(() => {
      sseState.onFrame?.(status("walk", "running", 1));
      sseState.onFrame?.(status("child", "running", 2));
    });
    await act(async () => {
      vi.advanceTimersByTime(RUN_STREAM_INVALIDATE_DEBOUNCE_MS);
    });
    expect(invalidatedKeys()).toEqual([["tasks", TASK_ID]]);
  });

  it("ingest ticks refresh the sources list and the landscape once per 5 s window (task 058, N16)", async () => {
    const { invalidatedKeys } = mountWithSpy();
    act(() => {
      sseState.onFrame?.(tick("ingest"));
      sseState.onFrame?.(tick("ingest"));
    });
    await act(async () => {
      vi.advanceTimersByTime(INGEST_REFRESH_THROTTLE_MS - 1);
    });
    act(() => sseState.onFrame?.(tick("ingest")));
    expect(invalidatedKeys()).toEqual([]);
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(invalidatedKeys()).toEqual([
      ["tasks", TASK_ID, "evidence"],
      ["tasks", TASK_ID, "landscape"],
    ]);

    // A tick after the window closes opens the next one.
    act(() => sseState.onFrame?.(tick("ingest")));
    await act(async () => {
      vi.advanceTimersByTime(INGEST_REFRESH_THROTTLE_MS);
    });
    expect(invalidatedKeys()).toHaveLength(4);
  });

  it("a tick from any other stage refreshes nothing", async () => {
    const { invalidateQueries } = mountWithSpy();
    act(() => sseState.onFrame?.(tick("classify")));
    await act(async () => {
      vi.advanceTimersByTime(INGEST_REFRESH_THROTTLE_MS * 2);
    });
    expect(invalidateQueries).not.toHaveBeenCalled();
  });

  it("throws when used outside the provider", () => {
    expect(() => renderHook(() => useRunStream(TASK_ID))).toThrow(/RunStreamProvider/);
  });

  it("closes the connection on unmount", () => {
    const { unmount } = render(
      <QueryClientProvider client={new QueryClient()}>
        <RunStreamProvider taskId={TASK_ID}>
          <div />
        </RunStreamProvider>
      </QueryClientProvider>,
    );
    expect(sseState.onFrame).not.toBeNull();
    unmount();
    expect(sseState.close).toHaveBeenCalled();
  });
});
