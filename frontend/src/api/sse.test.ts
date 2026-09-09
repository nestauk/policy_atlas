import { describe, expect, it, vi } from "vitest";

import { connectEventStream, consumeEventStream, nextBackoffDelayMs } from "./sse";
import { narrowSseFrame, type SseFrame } from "./sseFrame";

function emptyStreamResponse(status = 200): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.close();
    },
  });
  return new Response(stream, { status });
}

function headersOf(call: unknown[]): Record<string, string> {
  return (call[1] as { headers: Record<string, string> }).headers;
}

/**
 * A `sleepImpl` that yields a real macrotask (not just a resolved
 * microtask) between reconnect attempts. `connectEventStream`'s loop calls
 * `sleepImpl` between every cycle, including successful ones — without a
 * macrotask yield here, the loop would spin as fast as the microtask queue
 * allows and could starve `vi.waitFor`'s (macrotask-based) polling
 * entirely, since these tests intentionally let the mocked stream "end"
 * and reconnect repeatedly until the assertions run and `close()` is called.
 */
function fastSleep(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("consumeEventStream — SSE line parsing", () => {
  it("assembles id/event/data triples across chunked boundaries and ignores comments", async () => {
    const text =
      ": heartbeat\n" +
      "id:5\n" +
      "event:stage.completed\n" +
      'data:{"type":"stage.completed","stage":"screen","label":"Screening","occurred_at":"2026-07-21T10:00:00Z","sequence":5,"summary":{"included":3},"seconds":2}\n' +
      "\n" +
      "event:tick\n" +
      'data:{"type":"tick","note":"hi","stage":null,"occurred_at":"2026-07-21T10:00:01Z","ephemeral":true}\n' +
      "\n";

    const bytes = new TextEncoder().encode(text);
    // Cut at proportional, non-newline-aligned offsets so a line is split
    // mid-field regardless of exact text length — simulating real network
    // chunk boundaries.
    const fractions = [0.03, 0.12, 0.28, 0.55, 0.85];
    const cutPoints = fractions.map((f) => Math.floor(bytes.length * f));
    const chunks: Uint8Array[] = [];
    let start = 0;
    for (const cut of cutPoints) {
      chunks.push(bytes.slice(start, cut));
      start = cut;
    }
    chunks.push(bytes.slice(start));

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(chunk);
        controller.close();
      },
    });

    const frames: SseFrame[] = [];
    const finalCursor = await consumeEventStream(stream, 0, (frame) => frames.push(frame));

    expect(frames).toHaveLength(2);
    expect(frames[0]).toMatchObject({ type: "stage.completed", stage: "screen", sequence: 5 });
    expect(frames[1]).toMatchObject({ type: "tick", note: "hi" });
    // The tick carries no `id:` line at all and must never move the cursor.
    expect(finalCursor).toBe(5);
  });
});

describe("narrowSseFrame — live artefact vocabulary", () => {
  it("accepts the generated live-section frame types", () => {
    expect(
      narrowSseFrame({
        type: "artefact.section_completed",
        index: 2,
        title: "Conclusion",
        prose: "The evidence is mixed.",
        occurred_at: "2026-07-28T10:00:00Z",
        sequence: 7,
      }),
    ).toMatchObject({ type: "artefact.section_completed", index: 2, sequence: 7 });
  });
});

describe("connectEventStream — bearer auth, never a query-string token", () => {
  it("never puts the token in the request URL", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async () => emptyStreamResponse());
    const getAccessToken = vi.fn(async () => "super-secret-token");

    const connection = connectEventStream({
      taskId: "proj-1",
      cursor: 0,
      fetchImpl: fetchMock,
      getAccessToken,
      onFrame: () => {},
      sleepImpl: fastSleep,
    });

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    connection.close();

    for (const call of fetchMock.mock.calls) {
      const url = String(call[0]);
      expect(url).not.toContain("super-secret-token");
      expect(url).not.toMatch(/[?&]token=/);
    }
    expect(headersOf(fetchMock.mock.calls[0]).Authorization).toBe("Bearer super-secret-token");
  });

  it("on a 401, refreshes once and reconnects at the same cursor", async () => {
    let callCount = 0;
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) return new Response(null, { status: 401 });
      return emptyStreamResponse();
    });
    const getAccessToken = vi.fn(async (forceRefresh?: boolean) =>
      forceRefresh ? "refreshed-token" : "initial-token",
    );

    const connection = connectEventStream({
      taskId: "proj-1",
      cursor: 5,
      fetchImpl: fetchMock,
      getAccessToken,
      onFrame: () => {},
      sleepImpl: fastSleep,
    });

    await vi.waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2));
    connection.close();

    const [firstCall, secondCall] = fetchMock.mock.calls;
    expect(String(firstCall[0])).toContain("cursor=5");
    expect(String(secondCall[0])).toContain("cursor=5"); // reconnect preserves the cursor
    expect(headersOf(firstCall).Authorization).toBe("Bearer initial-token");
    expect(headersOf(secondCall).Authorization).toBe("Bearer refreshed-token");

    const forcedRefreshCalls = getAccessToken.mock.calls.filter(([force]) => force === true);
    expect(forcedRefreshCalls).toHaveLength(1); // exactly one silent-refresh attempt
  });

  it("surfaces onUnauthenticated and stops when the refreshed token still 401s", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 401 }));
    const getAccessToken = vi.fn(async (forceRefresh?: boolean) =>
      forceRefresh ? "still-bad-token" : "initial-token",
    );
    const onUnauthenticated = vi.fn();

    connectEventStream({
      taskId: "proj-1",
      cursor: 0,
      fetchImpl: fetchMock,
      getAccessToken,
      onFrame: () => {},
      onUnauthenticated,
      sleepImpl: fastSleep,
    });

    await vi.waitFor(() => expect(onUnauthenticated).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledTimes(2); // one attempt + one refreshed retry, then it stops
  });

  it.each([403, 404])(
    "surfaces onAccessEnded and stops reconnecting on a %d, rather than looping forever",
    async (status) => {
      const fetchMock = vi.fn(async () => new Response(null, { status }));
      const getAccessToken = vi.fn(async () => "token");
      const onAccessEnded = vi.fn();
      const onError = vi.fn();

      connectEventStream({
        taskId: "proj-1",
        cursor: 0,
        fetchImpl: fetchMock,
        getAccessToken,
        onFrame: () => {},
        onAccessEnded,
        onError,
        sleepImpl: fastSleep,
      });

      await vi.waitFor(() => expect(onAccessEnded).toHaveBeenCalled());
      expect(fetchMock).toHaveBeenCalledTimes(1); // no 401-style refresh retry, and no backoff reconnect
      expect(onError).not.toHaveBeenCalled(); // terminal, not an error to back off from
    },
  );

  it("on revocation mid-stream (clean end, then a 404 reconnect), stops without ever surfacing onError", async () => {
    let callCount = 0;
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) return emptyStreamResponse(); // the backend's clean end
      return new Response(null, { status: 404 }); // the reconnect that follows
    });
    const getAccessToken = vi.fn(async () => "token");
    const onAccessEnded = vi.fn();
    const onDisconnected = vi.fn();
    const onError = vi.fn();

    connectEventStream({
      taskId: "proj-1",
      cursor: 0,
      fetchImpl: fetchMock,
      getAccessToken,
      onFrame: () => {},
      onAccessEnded,
      onDisconnected,
      onError,
      sleepImpl: fastSleep,
    });

    await vi.waitFor(() => expect(onAccessEnded).toHaveBeenCalled());
    expect(onDisconnected).toHaveBeenCalledTimes(1); // the clean end still reports as a disconnect
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onError).not.toHaveBeenCalled();
  });
});

describe("nextBackoffDelayMs — capped exponential backoff with jitter", () => {
  it("never exceeds the 30s cap, at any attempt count", () => {
    for (const attempt of [0, 1, 2, 5, 10, 20]) {
      expect(nextBackoffDelayMs(attempt, () => 1)).toBeLessThanOrEqual(30000);
      expect(nextBackoffDelayMs(attempt, () => 0)).toBeLessThanOrEqual(30000);
    }
  });

  it("grows with attempt count before hitting the cap", () => {
    const at0 = nextBackoffDelayMs(0, () => 1);
    const at1 = nextBackoffDelayMs(1, () => 1);
    const at2 = nextBackoffDelayMs(2, () => 1);
    expect(at0).toBeLessThan(at1);
    expect(at1).toBeLessThan(at2);
  });

  it("stays within the 1s floor at attempt 0", () => {
    const delay = nextBackoffDelayMs(0, () => 0);
    expect(delay).toBeGreaterThanOrEqual(500);
    expect(delay).toBeLessThanOrEqual(1000);
  });
});
