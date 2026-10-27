import { describe, expect, it, vi } from "vitest";

import { consumeEventStream } from "../api/sse";
import type { SseFrame } from "../api/sseFrame";
import { mockFetch, resetMockScenario, setMockMe } from "./api";
import {
  MOCK_CHAT_CITATION_CHUNK_ID,
  MOCK_CHAT_CITATION_QUOTE,
  MOCK_CHECK_IN_ID,
  MOCK_TASK_AGENT_CONVERSATION_ID,
  MOCK_PROJECT_ID,
  MOCK_TASK_ID,
  MOCK_THEME_ID_ACTIVE_TRAVEL,
  MOCK_THEME_ID_SCHOOL_FOOD,
  mockEvidenceThemeIds,
  mockMeEnrolled,
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
    const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/landscape`);
    const landscape = await response.json() as { evidence_types: Record<string, number>; themes: { size: number }[] };
    expect(Object.values(landscape.evidence_types).reduce((total, count) => total + count, 0)).toBe(46);
    expect(landscape.themes.reduce((total, theme) => total + theme.size, 0)).toBe(46);
  });

  // 028 strand 7: the sources table's server-side `sort`/`order`/`theme`
  // params — honoured honestly in mock mode so `?VITE_MOCK=1` behaviour
  // doesn't diverge from `repository.evidence`'s real sort/filter logic.
  describe("evidence sort/order/theme (028 strand 7)", () => {
    it("sorts by year descending by default (the server's own default direction)", async () => {
      const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/evidence?sort=year`);
      const { data } = await response.json() as { data: { year: number | null }[] };
      const years = data.map((item) => item.year);
      const nonNullYears = years.filter((year): year is number => year !== null);
      expect(nonNullYears.length).toBeGreaterThan(0);
      expect(nonNullYears).toEqual([...nonNullYears].sort((a, b) => b - a));
      // Nulls sort last regardless of direction.
      expect(years.slice(-years.filter((year) => year === null).length).every((year) => year === null)).toBe(true);
    });

    it("flips to ascending when `order=asc` is explicit, nulls still last", async () => {
      const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/evidence?sort=year&order=asc`);
      const { data } = await response.json() as { data: { year: number | null }[] };
      const nonNullYears = data.map((item) => item.year).filter((year): year is number => year !== null);
      expect(nonNullYears).toEqual([...nonNullYears].sort((a, b) => a - b));
      expect(data.at(-1)?.year).toBeNull();
    });

    it("sorts by title case-insensitively", async () => {
      const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/evidence?sort=title&order=asc`);
      const { data } = await response.json() as { data: { title: string }[] };
      const titles = data.map((item) => item.title);
      expect(titles).toEqual([...titles].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())));
    });

    it("filters collection-true by theme id", async () => {
      const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/evidence?theme=${MOCK_THEME_ID_SCHOOL_FOOD}`);
      const { data } = await response.json() as { data: { source_id: string }[] };
      const expectedIds = Object.entries(mockEvidenceThemeIds)
        .filter(([, themeIds]) => themeIds.includes(MOCK_THEME_ID_SCHOOL_FOOD))
        .map(([sourceId]) => sourceId);
      expect(data.map((item) => item.source_id).sort()).toEqual(expectedIds.sort());
      expect(data.length).toBeGreaterThan(0);
    });

    it("combines theme and sort — a different theme returns a disjoint, still-sorted set", async () => {
      const response = await mockFetch(
        `http://localhost/api/v1/tasks/${MOCK_TASK_ID}/evidence?theme=${MOCK_THEME_ID_ACTIVE_TRAVEL}&sort=title&order=asc`,
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
    const started = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/runs`, { method: "POST" });
    expect(started.status).toBe(201);
    const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/events`);
    const frames: SseFrame[] = [];
    const consumed = consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
    const answer = await mockFetch(
      `http://localhost/api/v1/tasks/${MOCK_TASK_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`,
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
    const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/events`);
    const frames: SseFrame[] = [];
    void consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    // Give the (already-open) stream a turn to misbehave before asserting
    // silence — there is no run yet, so nothing should have been emitted.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(frames).toHaveLength(0);
  });

  it("serves a ready plan and the durable transcript with an honest incomplete turn", async () => {
    resetMockScenario();
    const planResponse = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/plan`);
    const plan = await planResponse.json() as { plan: { ready: boolean; search_effort: string } };
    expect(plan.plan.ready).toBe(true);
    expect(plan.plan.search_effort).toBe("rapid");

    const turnsResponse = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/task-agent-turns`);
    const turns = await turnsResponse.json() as {
      data: {
        status: string;
        reply: string | null;
        part: {
          id: string;
          body: string | null;
          chips: { kind: string; label: string }[] | null;
        } | null;
      }[];
    };
    expect(turns.data.some((turn) => turn.status === "failed")).toBe(true);
    const scope = turns.data.find((turn) => turn.part?.id === "scope");
    expect(scope?.part?.body).toBeNull();
    expect(scope?.reply).toContain("I'll search from 2016 onward");
    expect(scope?.part?.chips).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: "text", label: "UK primary" }),
        expect.objectContaining({ kind: "date_range", label: "Since 2016" }),
      ]),
    );
  });

  it("persists a PATCH onto the current mock plan", async () => {
    resetMockScenario();
    const patched = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/plan`, {
      method: "PATCH",
      body: JSON.stringify({ backend_scope: "academic_only" }),
    });
    expect(patched.status).toBe(200);
    const body = await patched.json() as { plan: { backend_scope: string } };
    expect(body.plan.backend_scope).toBe("academic_only");
    const reread = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/plan`);
    const again = await reread.json() as { plan: { backend_scope: string } };
    expect(again.plan.backend_scope).toBe("academic_only");
  });

  it("streams a terminal-partial banner fixture (failed after a partial artefact)", async () => {
    resetMockScenario();
    await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/runs`, { method: "POST" });
    const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/events?mockScenario=failed-partial`);
    const frames: SseFrame[] = [];
    const consumed = consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
    await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
    await mockFetch(
      `http://localhost/api/v1/tasks/${MOCK_TASK_ID}/check-ins/${MOCK_CHECK_IN_ID}/response`,
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
    it("lists the seeded task_agent conversation when kind is not filtered to chat", async () => {
      resetMockScenario();
      const listed = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations?status=active`);
      const { data } = await listed.json() as { data: { id: string; kind: string; title: string }[] };
      expect(data).toEqual(expect.arrayContaining([
        expect.objectContaining({
          id: MOCK_TASK_AGENT_CONVERSATION_ID,
          kind: "task_agent",
          title: "Planning",
        }),
      ]));
      const chatsOnly = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations?kind=chat&status=active`);
      const { data: chats } = await chatsOnly.json() as { data: { id: string }[] };
      expect(chats.map((row) => row.id)).not.toContain(MOCK_TASK_AGENT_CONVERSATION_ID);
    });

    it("creates, lists, updates, and archives/unarchives a conversation", async () => {
      resetMockScenario();
      const created = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations`, {
        method: "POST",
        body: JSON.stringify({ entry_artefact_id: "artefact-1" }),
      });
      expect(created.status).toBe(201);
      const conversation = await created.json() as { id: string; title: string; status: string; entry_artefact_id: string | null };
      expect(conversation).toMatchObject({ title: "New chat", status: "active", entry_artefact_id: "artefact-1" });

      const listed = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations?kind=chat&status=active`);
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
      const afterArchive = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations?kind=chat&status=active`);
      const { data: activeAfterArchive } = await afterArchive.json() as { data: { id: string }[] };
      expect(activeAfterArchive.map((row) => row.id)).not.toContain(conversation.id);

      const unarchived = await mockFetch(`http://localhost/api/v1/conversations/${conversation.id}/unarchive`, { method: "POST" });
      expect(await unarchived.json()).toMatchObject({ status: "active", archived_at: null });
    });

    it("streams progress + two deltas + a completed turn with a pending-enrichment citation, then flips to enriched on the second turns read", async () => {
      resetMockScenario();
      const created = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations`, { method: "POST", body: JSON.stringify({}) });
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
      const created = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/conversations`, { method: "POST", body: JSON.stringify({}) });
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
        `http://localhost/api/v1/tasks/${MOCK_TASK_ID}/chunks/${MOCK_CHAT_CITATION_CHUNK_ID}/context?quote=${encodeURIComponent(MOCK_CHAT_CITATION_QUOTE)}`,
      );
      const context = await response.json() as { context: string; clamped: boolean };
      expect(context.context).toContain(MOCK_CHAT_CITATION_QUOTE.slice(0, 30));
      expect(context.clamped).toBe(false);
    });
  });

  // Task 033 phase 10a: /me and the project routes the § 11 journeys
  // need that the mock never served before this phase.
  describe("identity + projects (task 033 phase 10a)", () => {
    it("GET /me defaults to the unenrolled fixture — dark launch", async () => {
      resetMockScenario();
      const response = await mockFetch("http://localhost/api/v1/me");
      const me = await response.json() as { organisation: unknown };
      expect(me.organisation).toBeNull();
    });

    it("GET /me reflects setMockMe(mockMeEnrolled) for tests that need the enrolled journey", async () => {
      resetMockScenario();
      setMockMe(mockMeEnrolled);
      const response = await mockFetch("http://localhost/api/v1/me");
      const me = await response.json() as { organisation: { name: string } | null };
      expect(me.organisation?.name).toBe(mockMeEnrolled.organisation?.name);
    });

    it("GET /projects returns the fixture project", async () => {
      resetMockScenario();
      const response = await mockFetch("http://localhost/api/v1/projects");
      const { data } = await response.json() as { data: { project_id: string }[] };
      expect(data).toHaveLength(1);
      expect(data[0].project_id).toBe(MOCK_PROJECT_ID);
    });

    it("GET /projects/{id} resolves the fixture and 404s for an unknown id", async () => {
      resetMockScenario();
      const found = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}`);
      expect(found.status).toBe(200);
      expect((await found.json() as { project_id: string }).project_id).toBe(MOCK_PROJECT_ID);

      const missing = await mockFetch("http://localhost/api/v1/projects/00000000-0000-4000-8000-000000000000");
      expect(missing.status).toBe(404);
    });

    it("GET /tasks?project_id= narrows to that project's members, server-side", async () => {
      resetMockScenario();
      const matching = await mockFetch(`http://localhost/api/v1/tasks?project_id=${MOCK_PROJECT_ID}`);
      const { data: matchingData } = await matching.json() as { data: { task_id: string }[] };
      expect(matchingData).toHaveLength(1);
      expect(matchingData[0].task_id).toBe(MOCK_TASK_ID);

      const nonMatching = await mockFetch(
        "http://localhost/api/v1/tasks?project_id=00000000-0000-4000-8000-000000000000",
      );
      const { data: nonMatchingData } = await nonMatching.json() as { data: unknown[] };
      expect(nonMatchingData).toHaveLength(0);

      const unfiltered = await mockFetch("http://localhost/api/v1/tasks");
      const { data: unfilteredData } = await unfiltered.json() as { data: unknown[] };
      expect(unfilteredData).toHaveLength(1);
    });

    it("PATCH /tasks/{id} refuses a rename bundled with a visibility conflict all-or-nothing — the name is never assigned before the 409", async () => {
      resetMockScenario();
      // `mockTask.project_ids` is seeded non-empty (task 033 phase 10a
      // fixture), so any `visibility` in the body always conflicts here.
      const response = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}`, {
        method: "PATCH",
        body: JSON.stringify({ name: "Renamed while conflicted", visibility: "private" }),
      });
      expect(response.status).toBe(409);
      const body = await response.json() as { error: { code: string } };
      expect(body.error.code).toBe("visibility_conflict");

      const reread = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}`);
      const task = await reread.json() as { name: string; visibility: string };
      expect(task.name).not.toBe("Renamed while conflicted");
      expect(task.visibility).toBe("org");
    });
  });

  // Task 044, phase 3.4: POST /tasks with from_task_ids builds a Link and a
  // ready scoping plan, so mock mode and the e2e can show the plan document
  // without scripting every intermediate Task Agent turn.
  describe("options scoping: create with Starts from (task 044)", () => {
    it("builds a Link carrying the previous task's name, and a ready scoping plan", async () => {
      resetMockScenario();
      const sourceName = (await (await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}`)).json() as { name: string }).name;

      const response = await mockFetch("http://localhost/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({
          name: "Cutting NEET numbers",
          question: "How can we reduce NEET numbers?",
          capability: "options_scoping",
          project_ids: [MOCK_PROJECT_ID],
          from_task_ids: [MOCK_TASK_ID],
        }),
      });
      expect(response.status).toBe(201);
      const task = await response.json() as {
        capability: string;
        links: { source_task_name: string; flagged: boolean }[];
      };
      expect(task.capability).toBe("options_scoping");
      expect(task.links).toHaveLength(1);
      expect(task.links[0].source_task_name).toBe(sourceName);
      expect(task.links[0].flagged).toBe(false);

      const planResponse = await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/plan`);
      const plan = await planResponse.json() as {
        capability: string;
        plan: unknown;
        scoping: { ready: boolean } | null;
      };
      expect(plan.capability).toBe("options_scoping");
      expect(plan.plan).toBeNull();
      expect(plan.scoping?.ready).toBe(true);
    });

    it("carries no link when from_task_ids is empty", async () => {
      resetMockScenario();
      const response = await mockFetch("http://localhost/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({ name: "A scoping task with no source", capability: "options_scoping" }),
      });
      const task = await response.json() as { links: unknown[] };
      expect(task.links).toEqual([]);
    });

    it("starts the new task's Task Agent transcript empty — no stale turns from a previous task", async () => {
      resetMockScenario();
      const before = await (await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/task-agent-turns`)).json() as { data: unknown[] };
      expect(before.data.length).toBeGreaterThan(0);

      await mockFetch("http://localhost/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({ name: "A fresh task", capability: "evidence_search" }),
      });

      const after = await (await mockFetch(`http://localhost/api/v1/tasks/${MOCK_TASK_ID}/task-agent-turns`)).json() as { data: unknown[] };
      expect(after.data).toEqual([]);
    });
  });

  describe("shortlist (task 055)", () => {
    const base = `http://localhost/api/v1/tasks/${MOCK_TASK_ID}`;
    const post = (path: string) => mockFetch(`${base}${path}`, { method: "POST" });
    const longlist = async () =>
      (await (await mockFetch(`${base}/longlist`)).json()) as {
        options: { option_id: string; name: string; shortlist: { state: string; reason: string | null } | null }[];
        shortlist: { note: string | null; stale: boolean };
      };

    it("serves two places, a set-aside option and a note", async () => {
      resetMockScenario();
      const body = await longlist();
      const states = body.options.map((option) => option.shortlist?.state ?? "none").sort();
      expect(states).toEqual(["added_by_you", "none", "proposed", "set_aside"]);
      expect(body.shortlist.note).not.toBeNull();
      expect(body.shortlist.stale).toBe(false);
    });

    it("shortlist turns a set-aside option into added_by_you; unshortlist sets a pick aside and clears a user place", async () => {
      resetMockScenario();
      const before = await longlist();
      const id = (state: string) => before.options.find((option) => option.shortlist?.state === state)!.option_id;
      const added = await (await post(`/options/${id("set_aside")}/shortlist`)).json() as { shortlist: { state: string } };
      expect(added.shortlist.state).toBe("added_by_you");
      const aside = await (await post(`/options/${id("proposed")}/unshortlist`)).json() as { shortlist: { state: string } };
      expect(aside.shortlist.state).toBe("set_aside");
      const cleared = await (await post(`/options/${id("added_by_you")}/unshortlist`)).json() as { shortlist: unknown };
      expect(cleared.shortlist).toBeNull();
    });

    it("refuses an excluded option with not_included", async () => {
      resetMockScenario();
      const excluded = await mockFetch(`${base}/longlist`).then((r) => r.json() as Promise<{ options: { option_id: string; state: string }[] }>);
      const response = await post(`/options/${excluded.options.find((o) => o.state === "excluded")!.option_id}/shortlist`);
      expect(response.status).toBe(409);
      expect(((await response.json()) as { error: { code: string } }).error.code).toBe("not_included");
    });

    it("suggest refuses with nothing_to_propose, then fills the open places once a place is cleared", async () => {
      resetMockScenario();
      const first = await post("/shortlist/suggest");
      expect(first.status).toBe(409);
      expect(((await first.json()) as { error: { code: string } }).error.code).toBe("nothing_to_propose");

      const before = await longlist();
      const user = before.options.find((option) => option.shortlist?.state === "added_by_you")!;
      await post(`/options/${user.option_id}/unshortlist`);
      const second = await post("/shortlist/suggest");
      expect(second.status).toBe(202);
      expect(((await second.json()) as { status: string }).status).toBe("succeeded");
      const after = await longlist();
      const filled = after.options.find((option) => option.option_id === user.option_id)!;
      expect(filled.shortlist).toEqual({ state: "proposed", reason: "Mock reason: names a fact on the card." });
    });

    it("suggest still adds one place when five or more places are held", async () => {
      resetMockScenario();
      const added: string[] = [];
      for (const text of ["Option A", "Option B", "Option C", "Option D"]) {
        const body = (await (
          await mockFetch(`${base}/options`, { method: "POST", body: JSON.stringify({ text }) })
        ).json()) as { option: { option_id: string } };
        added.push(body.option.option_id);
      }
      // Two places in the fixture plus three added by you: five held, one open.
      for (const id of added.slice(0, 3)) await post(`/options/${id}/shortlist`);
      const response = await post("/shortlist/suggest");
      expect(response.status).toBe(202);
      const after = await longlist();
      expect(after.options.find((option) => option.option_id === added[3])!.shortlist?.state).toBe("proposed");
      resetMockScenario();
    });

    it("exclude clears a place but keeps a set-aside mark", async () => {
      resetMockScenario();
      const before = await longlist();
      const exclude = (id: string) =>
        mockFetch(`${base}/options/${id}/exclude`, { method: "POST", body: JSON.stringify({ reason: "No." }) }).then(
          (r) => r.json() as Promise<{ shortlist: { state: string } | null }>,
        );
      for (const state of ["proposed", "added_by_you"]) {
        const id = before.options.find((option) => option.shortlist?.state === state)!.option_id;
        expect((await exclude(id)).shortlist).toBeNull();
      }
      const asideId = before.options.find((option) => option.shortlist?.state === "set_aside")!.option_id;
      expect((await exclude(asideId)).shortlist).toEqual({ state: "set_aside", reason: null });
      resetMockScenario();
    });

    it("refuses every shortlist route with run_active while a walk is running", async () => {
      resetMockScenario();
      const confirm = await mockFetch(`${base}/plan/confirm-baseline`, {
        method: "POST",
        body: JSON.stringify({ artefact_id: "artefact-1", plan_version: 1 }),
      });
      expect(confirm.status).toBe(200);
      const any = (await longlist()).options[0].option_id;
      for (const path of [`/options/${any}/shortlist`, `/options/${any}/unshortlist`, "/shortlist/suggest"]) {
        const response = await post(path);
        expect(response.status).toBe(409);
        expect(((await response.json()) as { error: { code: string } }).error.code).toBe("run_active");
      }
      resetMockScenario();
    });

    it("an appetite patch mints a version and marks the proposal stale until the next suggest", async () => {
      resetMockScenario();
      await mockFetch("http://localhost/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({ name: "Scoping", capability: "options_scoping" }),
      });
      const response = await mockFetch(`${base}/plan`, {
        method: "PATCH",
        body: JSON.stringify({ scoping: { risk_appetite: "tried_only" } }),
      });
      const plan = (await response.json()) as { version: number; scoping: { risk_appetite: string } };
      expect(plan.scoping.risk_appetite).toBe("tried_only");
      expect(plan.version).toBeGreaterThan(1);
      const stale = await longlist();
      expect(stale.shortlist.stale).toBe(true);
      const longlistBody = (await (await mockFetch(`${base}/longlist`)).json()) as { plan_inputs_changed: boolean };
      expect(longlistBody.plan_inputs_changed).toBe(false);
    });
  });
});
