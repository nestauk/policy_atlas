import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../auth";
import { buildAuthHeaders } from "../api/authMiddleware";
import { apiBaseUrl } from "../api/client";
import { queryKeys, useApiClient, useChatTurns } from "../api/queries";
import type { components } from "../api/gen/types";

export type ChatTurn = components["schemas"]["ChatTurnOut"];

export interface OptimisticChatTurn {
  clientTurnId: string;
  userMessage: string;
  createdAt: string;
  answer: string;
  status: "pending" | "failed" | "cancelled" | "interrupted";
  activityLabels: string[];
  turnId?: string;
  errorMessage?: string;
  errorCode?: string;
}

export type ChatConversationRow = ChatTurn | OptimisticChatTurn;

export interface OptimisticChatTranscriptState {
  turns: ChatConversationRow[];
}

export type OptimisticChatTranscriptAction =
  | { type: "submitted"; turn: OptimisticChatTurn }
  | { type: "progress"; clientTurnId: string; label: string }
  | { type: "delta"; clientTurnId: string; text: string }
  | { type: "completed"; clientTurnId: string; turn: ChatTurn }
  | { type: "cancelled"; clientTurnId: string; turn: ChatTurn }
  | { type: "failed"; clientTurnId: string; errorMessage: string; errorCode?: string; turnId?: string }
  | { type: "interrupted"; clientTurnId: string; errorMessage?: string }
  | { type: "cancel-status"; turnId: string; status: ChatTurn["status"] }
  | { type: "reset" }
  | { type: "discarded"; clientTurnId: string };

export const initialOptimisticChatTranscriptState: OptimisticChatTranscriptState = { turns: [] };

/**
 * Fold local chat-stream transitions without changing the durable turn query.
 *
 * Args:
 *   state: Current transient turn rows.
 *   action: A composer, stream, cancel, or reconciliation transition.
 *
 * Returns:
 *   The next local state. Terminal payloads replace their optimistic row until
 *   the durable turns query catches up.
 */
export function reduceOptimisticChatTranscript(
  state: OptimisticChatTranscriptState,
  action: OptimisticChatTranscriptAction,
): OptimisticChatTranscriptState {
  switch (action.type) {
    case "submitted":
      return {
        turns: state.turns.some((turn) => clientTurnIdOf(turn) === action.turn.clientTurnId)
          ? state.turns.map((turn) =>
              clientTurnIdOf(turn) === action.turn.clientTurnId ? action.turn : turn,
            )
          : [...state.turns, action.turn],
      };
    case "progress":
      return updateOptimisticTurn(state, action.clientTurnId, (turn) => ({
        ...turn,
        activityLabels: [...turn.activityLabels, action.label],
      }));
    case "delta":
      return updateOptimisticTurn(state, action.clientTurnId, (turn) => ({
        ...turn,
        answer: turn.answer + action.text,
      }));
    case "completed":
    case "cancelled":
      return {
        turns: state.turns.map((turn) =>
          clientTurnIdOf(turn) === action.clientTurnId ? action.turn : turn,
        ),
      };
    case "failed":
      return updateOptimisticTurn(state, action.clientTurnId, (turn) => ({
        ...turn,
        status: "failed",
        turnId: action.turnId ?? turn.turnId,
        errorMessage: action.errorMessage,
        errorCode: action.errorCode,
      }));
    case "interrupted":
      return updateOptimisticTurn(state, action.clientTurnId, (turn) => ({
        ...turn,
        status: "interrupted",
        errorMessage: action.errorMessage ?? "The connection was interrupted. Checking the saved turn…",
      }));
    case "cancel-status":
      return {
        turns: state.turns.map((turn) => {
          if ("id" in turn && turn.id === action.turnId) return { ...turn, status: action.status };
          if (!("id" in turn) && turn.turnId === action.turnId && action.status !== "completed") {
            // An optimistic turn never carries "completed" — the terminal
            // stream event / refetch replaces it with the durable row.
            return { ...turn, status: action.status };
          }
          return turn;
        }),
      };
    case "reset":
      return initialOptimisticChatTranscriptState;
    case "discarded":
      return {
        turns: state.turns.filter((turn) => clientTurnIdOf(turn) !== action.clientTurnId),
      };
    default:
      return assertNever(action);
  }
}

/**
 * Return a retry payload only for a failed or interrupted local turn.
 *
 * Args:
 *   state: Current local chat rows.
 *   clientTurnId: Caller-minted id for the logical question.
 *
 * Returns:
 *   The original message and id, or null when the row cannot be retried.
 */
export function retryInputForOptimisticChatTurn(
  state: OptimisticChatTranscriptState,
  clientTurnId: string,
): { message: string; clientTurnId: string } | null {
  const turn = state.turns.find(
    (candidate): candidate is OptimisticChatTurn =>
      !("id" in candidate) && candidate.clientTurnId === clientTurnId,
  );
  if (turn === undefined || (turn.status !== "failed" && turn.status !== "interrupted")) return null;
  return { message: turn.userMessage, clientTurnId: turn.clientTurnId };
}

/**
 * Combine the durable turn page and local rows, favouring durable rows once
 * their matching client id has been read back.
 *
 * Args:
 *   durableTurns: Server-provided turn rows in ascending order.
 *   optimisticTurns: Stream-local rows not yet reflected in the query.
 *
 * Returns:
 *   A single display-ready sequence without duplicate logical turns.
 */
export function chatTranscriptRows(
  durableTurns: ChatTurn[],
  optimisticTurns: ChatConversationRow[],
): ChatConversationRow[] {
  const durableIds = new Set(durableTurns.map((turn) => turn.client_turn_id));
  return [...durableTurns, ...optimisticTurns.filter((turn) => !durableIds.has(clientTurnIdOf(turn)))];
}

export type ChatStreamEvent =
  | { type: "progress"; label: string }
  | { type: "delta"; text: string }
  | { type: "completed"; turn: ChatTurn }
  | { type: "failed"; error: { code: string; message: string }; turn_id: string }
  | { type: "cancelled"; turn: ChatTurn };

/** A malformed or otherwise invalid NDJSON chat-stream event, or a non-2xx
 *  response to the turn-creating POST before the stream ever opened. */
export class ChatStreamProtocolError extends Error {
  /** The server's `error.code`, when the failure carried an envelope. */
  code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.name = "ChatStreamProtocolError";
    this.code = code;
  }
}

/** A chat response whose connection ended before a terminal event. */
export class ChatStreamInterruptedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ChatStreamInterruptedError";
  }
}

/**
 * Parse one NDJSON chat response and stop dispatching after its terminal event.
 *
 * Args:
 *   body: The stream response body from the chat-turn endpoint.
 *   onEvent: Receives each validated event in wire order.
 *
 * Returns:
 *   A promise fulfilled after the terminal event.
 *
 * Raises:
 *   ChatStreamProtocolError: The wire has malformed JSON or an unknown shape.
 *   ChatStreamInterruptedError: The body ends before a terminal event.
 */
export async function consumeChatStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;

  const consumeLine = (line: string) => {
    if (!line.trim() || terminal) return;
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      throw new ChatStreamProtocolError("The chat stream contained malformed JSON.");
    }
    const event = narrowChatStreamEvent(value);
    onEvent(event);
    terminal = isTerminal(event);
  };

  try {
    while (!terminal) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) consumeLine(line.endsWith("\r") ? line.slice(0, -1) : line);
    }
    if (!terminal) {
      const tail = buffer + decoder.decode();
      if (tail.trim()) consumeLine(tail.endsWith("\r") ? tail.slice(0, -1) : tail);
    }
  } finally {
    reader.releaseLock();
  }
  if (!terminal) throw new ChatStreamInterruptedError("The chat stream ended before it completed.");
}

const ENRICHMENT_POLL_MS = 3_000;
const ENRICHMENT_POLL_CAP_MS = 60_000;
const DISCONNECT_REFETCH_DELAY_MS = 1_000;
const COMPOSER_DRAFT_PREFIX = "policy-atlas.chat-draft.";

/**
 * Query and stream a single chat conversation with optimistic local turns.
 *
 * Args:
 *   conversationId: URL-addressable chat whose state this hook owns.
 *
 * Returns:
 *   Durable query state, merged rows, stream/cancel/retry controls, and the
 *   current activity labels. Changing the id changes every query and local key.
 */
export function useChatConversation(conversationId: string) {
  const auth = useAuth();
  const client = useApiClient();
  const queryClient = useQueryClient();
  const turnsQuery = useChatTurns(conversationId);
  const [optimistic, dispatch] = useReducer(reduceOptimisticChatTranscript, initialOptimisticChatTranscriptState);
  const currentConversationId = useRef(conversationId);
  const controllers = useRef(new Set<AbortController>());
  const terminalTurnIds = useRef(new Set<string>());
  const pollTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const mounted = useRef(true);
  const [isStreaming, setIsStreaming] = useState(false);

  // The sanctioned derive-state-during-render adjustment: on a conversation
  // switch the old rows never flash (no effect roundtrip), and in-flight
  // old-stream callbacks become no-ops via the effect below.
  const [renderedConversationId, setRenderedConversationId] = useState(conversationId);
  const conversationChanged = renderedConversationId !== conversationId;
  if (conversationChanged) {
    setRenderedConversationId(conversationId);
    dispatch({ type: "reset" });
    setIsStreaming(false);
  }

  const clearPoll = useCallback((turnId: string) => {
    const timer = pollTimers.current.get(turnId);
    if (timer !== undefined) clearTimeout(timer);
    pollTimers.current.delete(turnId);
  }, []);

  const clearPolls = useCallback(() => {
    for (const timer of pollTimers.current.values()) clearTimeout(timer);
    pollTimers.current.clear();
  }, []);

  useEffect(() => {
    currentConversationId.current = conversationId;
    terminalTurnIds.current.clear();
    const owned = controllers.current;
    return () => {
      clearPolls();
      for (const controller of owned) controller.abort();
      owned.clear();
    };
  }, [clearPolls, conversationId]);

  useEffect(() => {
    // Set (not just `useRef(true)`-initialised) on the mount side too: React
    // 18 StrictMode's dev-only mount -> cleanup -> remount rehearsal runs
    // this cleanup once immediately after the first mount, and a ref's
    // initial value never re-applies on that rehearsal's remount — without
    // this, `mounted.current` is left permanently `false`, so `isCurrent()`
    // never passes again and every stream event this hook ever receives is
    // silently dropped (a real bug this found: the whole chat surface hangs
    // at "Checking the evidence…" under `pnpm dev`).
    mounted.current = true;
    const owned = controllers.current;
    return () => {
      mounted.current = false;
      clearPolls();
      for (const controller of owned) controller.abort();
      owned.clear();
    };
  }, [clearPolls]);

  const isCurrent = useCallback(
    () => mounted.current && currentConversationId.current === conversationId,
    [conversationId],
  );

  const startEnrichmentPoll = useCallback(
    (turn: ChatTurn) => {
      if (enrichmentStatus(turn) !== "pending") return;
      clearPoll(turn.id);
      const startedAt = Date.now();
      const schedule = (delay: number) => {
        pollTimers.current.set(turn.id, setTimeout(() => void poll(), delay));
      };
      const poll = async () => {
        if (!isCurrent()) return;
        pollTimers.current.delete(turn.id);
        const result = await turnsQuery.refetch();
        const refreshed = result.data?.data.find((candidate) => candidate.id === turn.id);
        if (refreshed !== undefined && isTerminalEnrichmentStatus(enrichmentStatus(refreshed))) return;
        const remaining = ENRICHMENT_POLL_CAP_MS - (Date.now() - startedAt);
        if (remaining <= 0 || !isCurrent()) return;
        schedule(Math.min(ENRICHMENT_POLL_MS, remaining));
      };
      schedule(ENRICHMENT_POLL_MS);
    },
    [clearPoll, isCurrent, turnsQuery],
  );

  const invalidateTurns = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.chatTurns(conversationId) });
  }, [conversationId, queryClient]);

  const sendTurn = useCallback(
    async (message: string, clientTurnId = createClientTurnId()) => {
      const controller = new AbortController();
      controllers.current.add(controller);
      dispatch({
        type: "submitted",
        turn: {
          clientTurnId,
          userMessage: message,
          createdAt: new Date().toISOString(),
          answer: "",
          status: "pending",
          activityLabels: [],
        },
      });
      setIsStreaming(true);
      let terminalSeen = false;
      try {
        const postStream = async (forceRefresh = false) => {
          const headers = await buildAuthHeaders(auth, forceRefresh);
          headers.set("Content-Type", "application/json");
          headers.set("Accept", "application/x-ndjson");
          return fetch(`${apiBaseUrl()}/api/v1/conversations/${conversationId}/turns`, {
            method: "POST",
            headers,
            body: JSON.stringify({ message, client_turn_id: clientTurnId }),
            signal: controller.signal,
          });
        };
        let response = await postStream();
        if (response.status === 401) response = await postStream(true);
        if (!response.ok) {
          const failure = await chatTurnFailureEnvelope(response);
          throw new ChatStreamProtocolError(failure.message, failure.code);
        }
        if (response.body === null) throw new ChatStreamInterruptedError("The chat stream had no body.");
        await consumeChatStream(response.body, (event) => {
          if (terminalSeen || !isCurrent()) return;
          switch (event.type) {
            case "progress":
              dispatch({ type: "progress", clientTurnId, label: event.label });
              break;
            case "delta":
              dispatch({ type: "delta", clientTurnId, text: event.text });
              break;
            case "completed":
              terminalSeen = true;
              terminalTurnIds.current.add(event.turn.id);
              dispatch({ type: "completed", clientTurnId, turn: event.turn });
              invalidateTurns();
              startEnrichmentPoll(event.turn);
              break;
            case "cancelled":
              terminalSeen = true;
              terminalTurnIds.current.add(event.turn.id);
              dispatch({ type: "cancelled", clientTurnId, turn: event.turn });
              invalidateTurns();
              break;
            case "failed":
              terminalSeen = true;
              terminalTurnIds.current.add(event.turn_id);
              dispatch({
                type: "failed",
                clientTurnId,
                turnId: event.turn_id,
                errorCode: event.error.code,
                errorMessage: event.error.message,
              });
              invalidateTurns();
              break;
            default:
              assertNever(event);
          }
        });
      } catch (error) {
        if (!terminalSeen && isCurrent() && !controller.signal.aborted) {
          if (error instanceof ChatStreamProtocolError) {
            dispatch({ type: "failed", clientTurnId, errorMessage: error.message, errorCode: error.code });
          } else {
            dispatch({
              type: "interrupted",
              clientTurnId,
              errorMessage: error instanceof Error ? error.message : undefined,
            });
            setTimeout(() => {
              if (isCurrent()) void turnsQuery.refetch();
            }, DISCONNECT_REFETCH_DELAY_MS);
          }
        }
        throw error;
      } finally {
        controllers.current.delete(controller);
        if (isCurrent()) setIsStreaming(controllers.current.size > 0);
      }
    },
    [auth, conversationId, invalidateTurns, isCurrent, startEnrichmentPoll, turnsQuery],
  );

  const retry = useCallback(
    async (clientTurnId: string) => {
      const input = retryInputForOptimisticChatTurn(optimistic, clientTurnId);
      if (input === null) return null;
      return sendTurn(input.message, input.clientTurnId);
    },
    [optimistic, sendTurn],
  );

  const cancelTurn = useCallback(
    async (turnId: string) => {
      const { data, error } = await client.POST(
        "/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel",
        { params: { path: { conversation_id: conversationId, turn_id: turnId } } },
      );
      if (data === undefined) {
        throw Object.assign(new Error("Cancel failed"), { detail: error });
      }
      // A stream terminal that won the race is authoritative; a delayed
      // idempotent cancel response must never regress it to pending.
      if (terminalTurnIds.current.has(turnId)) return data;
      dispatch({ type: "cancel-status", turnId, status: data.status });
      queryClient.setQueryData<components["schemas"]["Page_ChatTurnOut_"]>(
        queryKeys.chatTurns(conversationId),
        (page) => page === undefined
          ? page
          : { ...page, data: page.data.map((turn) => turn.id === turnId ? { ...turn, status: data.status } : turn) },
      );
      if (data.status !== "pending") invalidateTurns();
      return data;
    },
    [client, conversationId, invalidateTurns, queryClient],
  );

  const visibleOptimistic = conversationChanged ? [] : optimistic.turns;
  return {
    ...turnsQuery,
    optimisticTurns: visibleOptimistic,
    rows: chatTranscriptRows(turnsQuery.data?.data ?? [], visibleOptimistic),
    activityLabels: visibleOptimistic.flatMap((turn) => "id" in turn ? [] : turn.activityLabels),
    sendTurn,
    retry,
    cancelTurn,
    isStreaming,
  };
}

/**
 * Persist one chat composer draft in this browser session only.
 *
 * Args:
 *   conversationId: Conversation-specific storage key.
 *
 * Returns:
 *   The current draft and a setter that writes it to sessionStorage.
 */
export function useComposerDraft(conversationId: string) {
  const [draft, setDraftState] = useState(() => readComposerDraft(conversationId));
  const [draftConversationId, setDraftConversationId] = useState(conversationId);
  if (draftConversationId !== conversationId) {
    setDraftConversationId(conversationId);
    setDraftState(readComposerDraft(conversationId));
  }

  const setDraft = useCallback((value: string) => {
    setDraftState(value);
    if (typeof window === "undefined") return;
    try {
      if (value) window.sessionStorage.setItem(composerDraftKey(conversationId), value);
      else window.sessionStorage.removeItem(composerDraftKey(conversationId));
    } catch {
      // A private-session storage failure only loses this non-durable convenience.
    }
  }, [conversationId]);

  return [draft, setDraft] as const;
}

function clientTurnIdOf(turn: ChatConversationRow): string {
  return "id" in turn ? turn.client_turn_id : turn.clientTurnId;
}

function updateOptimisticTurn(
  state: OptimisticChatTranscriptState,
  clientTurnId: string,
  update: (turn: OptimisticChatTurn) => OptimisticChatTurn,
): OptimisticChatTranscriptState {
  return {
    turns: state.turns.map((turn) =>
      !("id" in turn) && turn.clientTurnId === clientTurnId ? update(turn) : turn,
    ),
  };
}

function narrowChatStreamEvent(value: unknown): ChatStreamEvent {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ChatStreamProtocolError("The chat stream contained an invalid event.");
  }
  const event = value as Record<string, unknown>;
  if (event.type === "progress" && typeof event.label === "string") return event as ChatStreamEvent;
  if (event.type === "delta" && typeof event.text === "string") return event as ChatStreamEvent;
  if ((event.type === "completed" || event.type === "cancelled") && isChatTurn(event.turn)) {
    return event as ChatStreamEvent;
  }
  if (
    event.type === "failed" &&
    typeof event.turn_id === "string" &&
    isFailedEventError(event.error)
  ) return event as ChatStreamEvent;
  throw new ChatStreamProtocolError("The chat stream contained an invalid event.");
}

function isChatTurn(value: unknown): value is ChatTurn {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && typeof (value as Record<string, unknown>).id === "string"
    && typeof (value as Record<string, unknown>).client_turn_id === "string";
}

function isFailedEventError(value: unknown): value is { code: string; message: string } {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && typeof (value as Record<string, unknown>).code === "string"
    && typeof (value as Record<string, unknown>).message === "string";
}

/**
 * Read the turn-creating POST's error envelope so a pre-header failure (a
 * fenced turn, a capacity conflict) reaches the user with the server's own
 * code and message instead of a bare status number.
 *
 * Args:
 *   response: The non-ok response to the chat-turn POST.
 *
 * Returns:
 *   The envelope's `code`/`message`, or a status-text fallback when the body
 *   isn't the `{error:{code,message}}` shape (or isn't JSON at all).
 */
async function chatTurnFailureEnvelope(response: Response): Promise<{ code?: string; message: string }> {
  try {
    const body: unknown = await response.json();
    const message = (body as { error?: { message?: unknown } } | null)?.error?.message;
    if (typeof message === "string" && message) {
      const code = (body as { error?: { code?: unknown } }).error?.code;
      return { code: typeof code === "string" ? code : undefined, message };
    }
  } catch {
    // Not a JSON body — fall through to the status-text fallback below.
  }
  const status = `${response.status}${response.statusText ? ` ${response.statusText}` : ""}`;
  return { message: `The chat request failed (${status}).` };
}

function isTerminal(event: ChatStreamEvent): boolean {
  return event.type === "completed" || event.type === "failed" || event.type === "cancelled";
}

function enrichmentStatus(turn: ChatTurn): string | null {
  const enrichment = turn.enrichment;
  if (enrichment === null || enrichment === undefined || typeof enrichment.status !== "string") return null;
  return enrichment.status;
}

function isTerminalEnrichmentStatus(status: string | null): boolean {
  return status === "enriched" || status === "failed" || status === "not_applicable";
}

function composerDraftKey(conversationId: string): string {
  return `${COMPOSER_DRAFT_PREFIX}${conversationId}`;
}

function readComposerDraft(conversationId: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.sessionStorage.getItem(composerDraftKey(conversationId)) ?? "";
  } catch {
    return "";
  }
}

function createClientTurnId(): string {
  return globalThis.crypto.randomUUID();
}

function assertNever(value: never): never {
  throw new Error(`Unhandled chat conversation action: ${JSON.stringify(value)}`);
}
