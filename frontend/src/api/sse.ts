import { narrowSseFrame, type SseFrame } from "./sseFrame";

/** Default API base URL when `VITE_API_BASE_URL` is unset (local dev proxy). */
const DEFAULT_BASE_URL = "/api";

/** Minimum reconnect backoff, per web-api.md's fetch-stream reconnect posture. */
const MIN_BACKOFF_MS = 1000;
/** Maximum reconnect backoff. */
const MAX_BACKOFF_MS = 30000;

export interface ConnectEventStreamOptions {
  /** Project whose event stream to open. */
  projectId: string;
  /** API base URL. Defaults to `VITE_API_BASE_URL`, falling back to `/api`. */
  baseUrl?: string;
  /** Starting cursor (last-seen `event_log` sequence). Defaults to 0 (full replay). */
  cursor?: number;
  /** Resolve the current bearer token; `forceRefresh` requests a silent refresh. */
  getAccessToken: (forceRefresh?: boolean) => Promise<string | null>;
  /** Called for every parsed frame, in arrival order. */
  onFrame: (frame: SseFrame) => void;
  /** Called once if a 401 survives a forced-refresh retry — the stream stops. */
  onUnauthenticated?: () => void;
  /** Called after the server accepts an SSE connection. */
  onConnected?: () => void;
  /** Called when an accepted stream ends and a reconnect is about to start. */
  onDisconnected?: () => void;
  /** Called for connection/stream errors that trigger a backoff-and-retry. */
  onError?: (error: unknown) => void;
  /** External abort signal (in addition to the `close()` returned below). */
  signal?: AbortSignal;
  /** Injectable for tests. Defaults to `globalThis.fetch`. */
  fetchImpl?: typeof fetch;
  /** Injectable for tests. Defaults to a real `setTimeout`-based sleep. */
  sleepImpl?: (ms: number, signal?: AbortSignal) => Promise<void>;
  /** Injectable for tests — overrides the 1s floor. */
  minBackoffMs?: number;
  /** Injectable for tests — overrides the 30s cap. */
  maxBackoffMs?: number;
}

export interface EventStreamConnection {
  /** Abort the stream and stop reconnecting. */
  close: () => void;
}

/**
 * Open the durable replay-then-tail SSE stream for one project
 * (`GET /api/v1/projects/{id}/events?cursor=`), authenticating via the
 * bearer header (never a query-string token) and reconnecting on drop with
 * exponential backoff + jitter. On a 401, attempts exactly one silent
 * refresh and retries at the same cursor before surfacing
 * `onUnauthenticated` — cursor semantics mean a reconnect never loses or
 * duplicates events.
 */
export function connectEventStream(options: ConnectEventStreamOptions): EventStreamConnection {
  const {
    projectId,
    baseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL,
    cursor: initialCursor = 0,
    getAccessToken,
    onFrame,
    onUnauthenticated,
    onError,
    onConnected,
    onDisconnected,
    fetchImpl = fetch,
    sleepImpl = defaultSleep,
    minBackoffMs = MIN_BACKOFF_MS,
    maxBackoffMs = MAX_BACKOFF_MS,
  } = options;

  const controller = new AbortController();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let cursor = initialCursor;

  function buildUrl(): string {
    return `${baseUrl}/api/v1/projects/${projectId}/events?cursor=${cursor}`;
  }

  async function fetchWithToken(token: string | null): Promise<Response> {
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetchImpl(buildUrl(), { headers, signal: controller.signal });
  }

  /** One connect attempt (with the single 401-refresh-retry), consuming the
   *  stream to completion. Returns why the attempt ended. */
  async function connectOnce(): Promise<"stream-ended" | "unauthenticated"> {
    const token = await getAccessToken();
    let response = await fetchWithToken(token);

    if (response.status === 401) {
      const refreshed = await getAccessToken(true);
      if (refreshed === null) return "unauthenticated";
      response = await fetchWithToken(refreshed);
      if (response.status === 401) return "unauthenticated";
    }

    if (!response.ok || !response.body) {
      throw new Error(`SSE connect failed with status ${response.status}`);
    }

    onConnected?.();
    cursor = await consumeEventStream(response.body, cursor, onFrame, controller.signal);
    return "stream-ended";
  }

  void (async () => {
    let attempt = 0;
    while (!controller.signal.aborted) {
      try {
        const outcome = await connectOnce();
        if (outcome === "unauthenticated") {
          onUnauthenticated?.();
          return;
        }
        onDisconnected?.();
        attempt = 0; // a full connect+stream cycle succeeded — reset backoff
      } catch (error) {
        if (controller.signal.aborted) return;
        onError?.(error);
      }
      if (controller.signal.aborted) return;
      const delay = nextBackoffDelayMs(attempt++, Math.random, minBackoffMs, maxBackoffMs);
      await sleepImpl(delay, controller.signal);
    }
  })().catch((error: unknown) => {
    if (!controller.signal.aborted) onError?.(error);
  });

  return { close: () => controller.abort() };
}

/**
 * Read one SSE body to completion, parsing `id:`/`event:`/`data:` fields
 * (comment lines and blank heartbeats are ignored) and dispatching one
 * frame per blank-line-terminated event. Tolerant of chunk boundaries that
 * split a line in the middle. Returns the last frame `id:` seen (the new
 * reconnect cursor) — `tick` frames carry no `id:` and never advance it.
 */
export async function consumeEventStream(
  body: ReadableStream<Uint8Array>,
  startCursor: number,
  onFrame: (frame: SseFrame) => void,
  signal?: AbortSignal,
): Promise<number> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let cursor = startCursor;

  let eventId: string | undefined;
  let dataLines: string[] = [];
  let sawField = false;

  function dispatchPendingEvent() {
    if (!sawField) return;
    const dataText = dataLines.join("\n");
    const pendingId = eventId;
    eventId = undefined;
    dataLines = [];
    sawField = false;

    if (!dataText) return;
    let payload: unknown;
    try {
      payload = JSON.parse(dataText);
    } catch {
      return; // malformed payload — drop rather than crash the stream
    }
    const frame = narrowSseFrame(payload);
    if (!frame) return;
    if (frame.type !== "tick" && pendingId !== undefined) {
      const parsed = Number(pendingId);
      if (Number.isFinite(parsed)) cursor = parsed;
    }
    onFrame(frame);
  }

  try {
    while (true) {
      if (signal?.aborted) break;
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIndex: number;
      while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
        let line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        if (line.endsWith("\r")) line = line.slice(0, -1);

        if (line === "") {
          dispatchPendingEvent();
          continue;
        }
        if (line.startsWith(":")) continue; // comment — e.g. the 15s heartbeat

        const colonIndex = line.indexOf(":");
        const field = colonIndex === -1 ? line : line.slice(0, colonIndex);
        let fieldValue = colonIndex === -1 ? "" : line.slice(colonIndex + 1);
        if (fieldValue.startsWith(" ")) fieldValue = fieldValue.slice(1);

        if (field === "id") {
          eventId = fieldValue;
          sawField = true;
        } else if (field === "data") {
          dataLines.push(fieldValue);
          sawField = true;
        } else if (field === "event") {
          sawField = true; // frame type also travels in the JSON `.type`; the
          // `event:` line itself isn't consumed separately.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  return cursor;
}

/**
 * Exponential backoff with jitter, capped: `min(min(base * 2^attempt, max)
 * * [0.5, 1.0), max)`. Exported standalone so the cap/growth can be tested
 * without driving the full reconnect loop.
 */
export function nextBackoffDelayMs(
  attempt: number,
  random: () => number = Math.random,
  minMs: number = MIN_BACKOFF_MS,
  maxMs: number = MAX_BACKOFF_MS,
): number {
  const exponential = Math.min(minMs * 2 ** attempt, maxMs);
  const jittered = exponential * (0.5 + random() * 0.5);
  return Math.min(Math.round(jittered), maxMs);
}

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}
