import { describe, expect, it, vi } from "vitest";

import { consumeEventStream } from "../api/sse";
import type { SseFrame } from "../api/sseFrame";
import { mockFetch, resetMockScenario } from "./api";
import {
  MOCK_CHAT_CITATION_CHUNK_ID,
  MOCK_CHAT_CITATION_QUOTE,
  MOCK_CHECK_IN_ID,
  MOCK_PROJECT_ID,
  MOCK_THEME_ID_ACTIVE_TRAVEL,
  MOCK_THEME_ID_SCHOOL_FOOD,
  mockEvidenceThemeIds,
} from "./fixtures";

interface MockChatTurn {
  id: string;
  status: string;
  answer: string;
  citations?: { grounding_tier?: string; state?: string }[];
  enrichment?: { status: string } | null;
}

async function readNdjson(response: Response): Promise<Record<string, unknown>[]> {
  const text = await response.text();
  return text.trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
}

describe("mock API", () => {
  it("serves deterministic, screened-in landscape fixtures", async () => {
    const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/landscape`);
    const landscape = await response.json() as { evidence_types: Record<string, number>; themes: { size: number }[] };
    expect(Object.values(landscape.evidence_types).reduce((total, count) => total + count, 0)).toBe(46);
    expect(landscape.themes.reduce((total, theme) => total + theme.size, 0)).toBe(46);
  });

  // 028 strand 7: the sources table's server-side `sort`/`order`/`theme`
  // params — honoured honestly in mock mode so `?VITE_MOCK=1` behaviour
  // doesn't diverge from `repository.evidence`'s real sort/filter logic.
  describe("evidence sort/order/theme (028 strand 7)", () => {
    it("sorts by year descending by default (the server's own default direction)", async () => {
      const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/evidence?sort=year`);
      const { data } = await response.json() as { data: { year: number | null }[] };
      const years = data.map((item) => item.year);
      const nonNullYears = years.filter((year): year is number => year !== null);
      expect(nonNullYears.length).toBeGreaterThan(0);
      expect(nonNullYears).toEqual([...nonNullYears].sort((a, b) => b - a));
      // Nulls sort last regardless of direction.
      expect(years.slice(-years.filter((year) => year === null).length).every((year) => year === null)).toBe(true);
    });

    it("flips to ascending when `order=asc` is explicit, nulls still last", async () => {
      const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/evidence?sort=year&order=asc`);
      const { data } = await response.json() as { data: { year: number | null }[] };
      const nonNullYears = data.map((item) => item.year).filter((year): year is number => year !== null);
      expect(nonNullYears).toEqual([...nonNullYears].sort((a, b) => a - b));
      expect(data.at(-1)?.year).toBeNull();
    });

    it("sorts by title case-insensitively", async () => {
      const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/evidence?sort=title&order=asc`);
      const { data } = await response.json() as { data: { title: string }[] };
      const titles = data.map((item) => item.title);
      expect(titles).toEqual([...titles].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())));
    });

    it("filters collection-true by theme id", async () => {
      const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/evidence?theme=${MOCK_THEME_ID_SCHOOL_FOOD}`);
      const { data } = await response.json() as { data: { source_id: string }[] };
      const expectedIds = Object.entries(mockEvidenceThemeIds)
        .filter(([, themeIds]) => themeIds.includes(MOCK_THEME_ID_SCHOOL_FOOD))
        .map(([sourceId]) => sourceId);
      expect(data.map((item) => item.source_id).sort()).toEqual(expectedIds.sort());
      expect(data.length).toBeGreaterThan(0);
    });

    it("combines theme and sort — a different theme returns a disjoint, still-sorted set", async () => {
      const response = await mockFetch(
        `http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/evidence?theme=${MOCK_THEME_ID_ACTIVE_TRAVEL}&sort=title&order=asc`,
      );
      const { data } = await response.json() as { data: { source_id: string; title: string }[] };
      const expectedIds = Object.entries(mockEvidenceThemeIds)
        .filter(([, themeIds]) => themeIds.includes(MOCK_THEME_ID_ACTIVE_TRAVEL))
        .map(([sourceId]) => sourceId);
      expect(data.map((item) => item.source_id)).toEqual(expectedIds);
      const titles = data.map((item) => item.title);
      expect(titles).toEqual([...titles].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())));
    });
  });

  it("holds the scripted stream at the check-in then completes after an answer", async () => {
    resetMockScenario();
    // The event stream is gated behind a real run start (027 F.2): nothing
    // streams until "Start the analysis" — i.e. `POST .../runs` — succeeds.
    const started = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/runs`, { method: "POST" });
    expect(started.status).toBe(201);
    const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/events`);
    const frames: SseFrame[] = [];
    const consumed = consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
    const answer = await mockFetch(
      `http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`,
      { method: "POST", body: JSON.stringify({ kind: "free_text", text: "Keep family support visible" }) },
    );
    expect(answer.status).toBe(202);
    expect(await answer.json()).toMatchObject({ confirm_token: expect.any(String), render: expect.any(String) });
    await consumed;
    // Live artefact sections streamed in before the run's terminal status.
    expect(frames.some((frame) => frame.type === "artefact.skeleton")).toBe(true);
    expect(frames.filter((frame) => frame.type === "artefact.section_completed")).toHaveLength(2);
    expect(frames.at(-1)).toMatchObject({ type: "run.status", status: "succeeded" });
  });

  it("gates the stream until a run actually starts", async () => {
    resetMockScenario();
    const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/events`);
    const frames: SseFrame[] = [];
    void consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    // Give the (already-open) stream a turn to misbehave before asserting
    // silence — there is no run yet, so nothing should have been emitted.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(frames).toHaveLength(0);
  });

  it("serves a ready plan and the durable transcript with an honest incomplete turn", async () => {
    resetMockScenario();
    const planResponse = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/plan`);
    const plan = await planResponse.json() as { plan: { ready: boolean; search_effort: string } };
    expect(plan.plan.ready).toBe(true);
    expect(plan.plan.search_effort).toBe("rapid");

    const turnsResponse = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/planning-turns`);
    const turns = await turnsResponse.json() as { data: { status: string }[] };
    expect(turns.data.some((turn) => turn.status === "failed")).toBe(true);
  });

  it("streams a terminal-partial banner fixture (failed after a partial artefact)", async () => {
    resetMockScenario();
    await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/runs`, { method: "POST" });
    const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/events?mockScenario=failed-partial`);
    const frames: SseFrame[] = [];
    const consumed = consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
    await mockFetch(
      `http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`,
      { method: "POST", body: JSON.stringify({ kind: "option", option_id: "suggested-balanced" }) },
    );
    await consumed;
    expect(frames.filter((frame) => frame.type === "artefact.section_completed")).toHaveLength(2);
    expect(frames.at(-1)).toMatchObject({ type: "run.status", status: "failed" });
  });

  // Task 029 phase G3: the chat conversation library, streamed turns, the
  // async enrichment poll's second-read flip, and the chat citation's own
  // chunk-context read.
  describe("chat conversations", () => {
    it("creates, lists, updates, and archives/unarchives a conversation", async () => {
      resetMockScenario();
      const created = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/conversations`, {
        method: "POST",
        body: JSON.stringify({ entry_artefact_id: "artefact-1" }),
      });
      expect(created.status).toBe(201);
      const conversation = await created.json() as { id: string; title: string; status: string; entry_artefact_id: string | null };
      expect(conversation).toMatchObject({ title: "New chat", status: "active", entry_artefact_id: "artefact-1" });

      const listed = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/conversations?kind=chat&status=active`);
      const { data: active } = await listed.json() as { data: { id: string }[] };
      expect(active.map((row) => row.id)).toContain(conversation.id);

      const fetched = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}`);
      expect(await fetched.json()).toMatchObject({ id: conversation.id });

      const renamed = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: "Breakfast findings" }),
      });
      expect(await renamed.json()).toMatchObject({ title: "Breakfast findings" });

      const cleared = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}`, {
        method: "PATCH",
        body: JSON.stringify({ entry_artefact_id: null }),
      });
      expect(await cleared.json()).toMatchObject({ entry_artefact_id: null });

      const archived = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/archive`, { method: "POST" });
      expect(await archived.json()).toMatchObject({ status: "archived" });
      const afterArchive = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/conversations?kind=chat&status=active`);
      const { data: activeAfterArchive } = await afterArchive.json() as { data: { id: string }[] };
      expect(activeAfterArchive.map((row) => row.id)).not.toContain(conversation.id);

      const unarchived = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/unarchive`, { method: "POST" });
      expect(await unarchived.json()).toMatchObject({ status: "active", archived_at: null });
    });

    it("streams progress + two deltas + a completed turn with a pending-enrichment citation, then flips to enriched on the second turns read", async () => {
      resetMockScenario();
      const created = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/conversations`, { method: "POST", body: JSON.stringify({}) });
      const conversation = await created.json() as { id: string };

      const streamed = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/turns`, {
        method: "POST",
        body: JSON.stringify({ client_turn_id: "11111111-1111-4111-8111-111111111111", message: "What does the evidence show?" }),
      });
      expect(streamed.headers.get("Content-Type")).toBe("application/x-ndjson");
      const events = await readNdjson(streamed);
      expect(events.map((event) => event.type)).toEqual(["progress", "delta", "delta", "completed"]);
      const completedTurn = events.at(-1)?.turn as MockChatTurn;
      expect(completedTurn.status).toBe("completed");
      expect(completedTurn.answer).toContain("[1]");
      expect(completedTurn.citations?.[0]?.grounding_tier).toBeUndefined();
      expect(completedTurn.enrichment).toMatchObject({ status: "pending" });

      // First GET turns (the `completed` event's own `invalidateTurns()`
      // refetch): still honestly unchecked.
      const firstRead = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/turns`);
      const { data: firstTurns } = await firstRead.json() as { data: MockChatTurn[] };
      expect(firstTurns[0].enrichment).toMatchObject({ status: "pending" });
      expect(firstTurns[0].citations?.[0]?.grounding_tier).toBeUndefined();

      // Second GET turns (the async enrichment poll): now enriched with a
      // tier verdict on the one citation.
      const secondRead = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/turns`);
      const { data: secondTurns } = await secondRead.json() as { data: MockChatTurn[] };
      expect(secondTurns[0].enrichment).toMatchObject({ status: "enriched" });
      expect(secondTurns[0].citations?.[0]?.state).toBe("verdict:tier_2");
    });

    it("cancels a turn idempotently by its durable status", async () => {
      resetMockScenario();
      const created = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/conversations`, { method: "POST", body: JSON.stringify({}) });
      const conversation = await created.json() as { id: string };
      const streamed = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/turns`, {
        method: "POST",
        body: JSON.stringify({ client_turn_id: "22222222-2222-4222-8222-222222222222", message: "Cancel me" }),
      });
      const events = await readNdjson(streamed);
      const turn = events.at(-1)?.turn as MockChatTurn;

      const cancelled = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/turns/${turn.id}/cancel`, { method: "POST" });
      expect(await cancelled.json()).toEqual({ status: "completed" });
    });

    it("resolves the chat citation's chunk-context read, distinct from the artefact citation-key read", async () => {
      const response = await mockFetch(
        `http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/chunks/${MOCK_CHAT_CITATION_CHUNK_ID}/context?quote=${encodeURIComponent(MOCK_CHAT_CITATION_QUOTE)}`,
      );
      const context = await response.json() as { context: string; clamped: boolean };
      expect(context.context).toContain(MOCK_CHAT_CITATION_QUOTE.slice(0, 30));
      expect(context.clamped).toBe(false);
    });
  });
});
