import { narrowSseFrame, type SseFrame } from "./sseFrame";

/** Default API base: same-origin — the events path below already carries
 * the full /api/v1 prefix (matches the REST client convention). */
const DEFAULT_BASE_URL = "";

/** Minimum reconnect backoff, per web-api.md's fetch-stream reconnect posture. */
const MIN_BACKOFF_MS = 1000;
/** Maximum reconnect backoff. */
const MAX_BACKOFF_MS = 30000;
/**
 * How long the stream may go without a single byte before the client treats
 * the connection as dead, drops it and reconnects at its cursor (task 058,
 * N15). The server sends a keep-alive comment every 15 s and repeats the
 * current tick every 10 s while a model call runs, so 45 s of silence means
 * the connection is gone even if the browser has not noticed.
 */
export const READ_INACTIVITY_MS = 45_000;

/** Display-only frames: never replayed, so they never move the cursor. */
const EPHEMERAL_FRAME_TYPES: ReadonlySet<SseFrame["type"]> = new Set([
  "tick",
  "artefact.section_delta",
  "artefact.section_revising",
  "artefact.section_sources",
  "artefact.section_claim",
  "artefact.section_card",
  "artefact.source_note",
  "search.query",
  "characterise.themes",
  "toc.sketch",
] satisfies SseFrame["type"][]);

interface ConnectEventStreamOptions {
  /** Project whose event stream to open. */
  taskId: string;
  /** API base URL. Defaults to `VITE_API_BASE_URL`, falling back to same-origin. */
  baseUrl?: string;
  /** Starting cursor (last-seen `event_log` sequence). Defaults to 0 (full replay). */
  cursor?: number;
  /** Resolve the current bearer token; `forceRefresh` requests a silent refresh. */
  getAccessToken: (forceRefresh?: boolean) => Promise<string | null>;
  /** Called for every parsed frame, in arrival order. */
  onFrame: (frame: SseFrame) => void;
  /** Called once if a 401 survives a forced-refresh retry — the stream stops. */
  onUnauthenticated?: () => void;
  /** Called once if a connect or reconnect attempt gets a 403 or 404 — e.g.
   *  the task's access was revoked or it no longer exists. The backend
   *  ends an active stream cleanly on revocation, so this fires on the
   *  reconnect that follows rather than mid-stream; like `onUnauthenticated`,
   *  it is terminal — retrying a 403/404 forever would just poll a state
   *  that will never clear itself. */
  onAccessEnded?: () => void;
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
  /** Injectable for tests — overrides the 45 s read-inactivity watchdog. */
  readInactivityMs?: number;
}

interface EventStreamConnection {
  /** Abort the stream and stop reconnecting. */
  close: () => void;
}

/**
 * Open the durable replay-then-tail SSE stream for one task
 * (`GET /api/v1/tasks/{id}/events?cursor=`), authenticating via the
 * bearer header (never a query-string token) and reconnecting on drop with
 * exponential backoff + jitter. On a 401, attempts exactly one silent
 * refresh and retries at the same cursor before surfacing
 * `onUnauthenticated` — cursor semantics mean a reconnect never loses or
 * duplicates events.
 */
export function connectEventStream(options: ConnectEventStreamOptions): EventStreamConnection {
  const {
    taskId,
    baseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL,
    cursor: initialCursor = 0,
    getAccessToken,
    onFrame,
    onUnauthenticated,
    onAccessEnded,
    onError,
    onConnected,
    onDisconnected,
    fetchImpl = fetch,
    sleepImpl = defaultSleep,
    minBackoffMs = MIN_BACKOFF_MS,
    maxBackoffMs = MAX_BACKOFF_MS,
    readInactivityMs = READ_INACTIVITY_MS,
  } = options;

  const controller = new AbortController();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    else options.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let cursor = initialCursor;

  function buildUrl(): string {
    return `${baseUrl}/api/v1/tasks/${taskId}/events?cursor=${cursor}`;
  }

  async function fetchWithToken(token: string | null, signal: AbortSignal): Promise<Response> {
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetchImpl(buildUrl(), { headers, signal });
  }

  /** One connect attempt (with the single 401-refresh-retry), consuming the
   *  stream to completion. Returns why the attempt ended. Each attempt has
   *  its own abort controller, chained to the outer one, so a dead
   *  connection can be dropped without closing the whole stream. */
  async function connectOnce(): Promise<"stream-ended" | "unauthenticated" | "access-ended"> {
    const attempt = new AbortController();
    const abortAttempt = () => attempt.abort();
    controller.signal.addEventListener("abort", abortAttempt, { once: true });
    try {
      const token = await getAccessToken();
      let response = await fetchWithToken(token, attempt.signal);

      if (response.status === 401) {
        const refreshed = await getAccessToken(true);
        if (refreshed === null) return "unauthenticated";
        response = await fetchWithToken(refreshed, attempt.signal);
        if (response.status === 401) return "unauthenticated";
      }

      // A revoked or gone task: the backend ends an active stream cleanly
      // on revocation, and any reconnect after that gets a 403/404 — a state
      // no amount of backoff-and-retry will ever clear.
      if (response.status === 403 || response.status === 404) return "access-ended";

      if (!response.ok || !response.body) {
        throw new Error(`SSE connect failed with status ${response.status}`);
      }

      onConnected?.();
      cursor = await consumeEventStream(
        response.body,
        cursor,
        onFrame,
        attempt.signal,
        readInactivityMs,
      );
      return "stream-ended";
    } finally {
      // Tears down this attempt's request, whether it ended cleanly, went
      // silent past the watchdog, or failed.
      controller.signal.removeEventListener("abort", abortAttempt);
      attempt.abort();
    }
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
        if (outcome === "access-ended") {
          onAccessEnded?.();
          return;
        }
        if (controller.signal.aborted) return;
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
 * reconnect cursor) — the ephemeral frames (`tick`, the section deltas and
 * revising marks) carry no `id:` and never advance it.
 *
 * Args:
 *   body: The response body to read.
 *   startCursor: The cursor to return if no frame with an `id:` arrives.
 *   onFrame: Called for every parsed frame, in arrival order.
 *   signal: Stops reading when aborted.
 *   readInactivityMs: The watchdog (task 058, N15). When set, reading stops
 *     and the function returns the cursor so far if no bytes at all (frames,
 *     ticks or keep-alive comments) arrive for this long. The caller then
 *     reconnects at that cursor as for any ended stream.
 *
 * Returns:
 *   The last frame `id:` seen, or `startCursor`.
 */
export async function consumeEventStream(
  body: ReadableStream<Uint8Array>,
  startCursor: number,
  onFrame: (frame: SseFrame) => void,
  signal?: AbortSignal,
  readInactivityMs?: number,
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
    if (!EPHEMERAL_FRAME_TYPES.has(frame.type) && pendingId !== undefined) {
      const parsed = Number(pendingId);
      if (Number.isFinite(parsed)) cursor = parsed;
    }
    onFrame(frame);
  }

  // Resolves when reading should stop without more bytes: the watchdog ran
  // out (no bytes for `readInactivityMs`) or the caller aborted. A new
  // timer starts for every read, so every chunk resets it.
  let stopTimer: ReturnType<typeof setTimeout> | undefined;
  let removeAbortListener: (() => void) | undefined;
  function stopSignal(): Promise<"stop"> {
    return new Promise((resolve) => {
      const stop = () => resolve("stop");
      if (readInactivityMs !== undefined) stopTimer = setTimeout(stop, readInactivityMs);
      if (signal) {
        signal.addEventListener("abort", stop, { once: true });
        removeAbortListener = () => signal.removeEventListener("abort", stop);
      }
    });
  }
  function clearStopSignal() {
    if (stopTimer !== undefined) clearTimeout(stopTimer);
    stopTimer = undefined;
    removeAbortListener?.();
    removeAbortListener = undefined;
  }

  let stopped = false;
  try {
    while (true) {
      if (signal?.aborted) break;
      const result = await Promise.race([reader.read(), stopSignal()]);
      clearStopSignal();
      if (result === "stop") {
        stopped = true;
        break;
      }
      const { value, done } = result;
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
    clearStopSignal();
    if (stopped) {
      // A read is still pending; cancelling ends it and frees the body.
      // Nothing to do if the stream has already gone away.
      await reader.cancel().catch(() => undefined);
    }
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
