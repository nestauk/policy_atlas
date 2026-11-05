import { beforeAll, describe, expect, it, vi } from "vitest";

import { consumeEventStream } from "../api/sse";
import type { SseFrame } from "../api/sseFrame";
import { mockFetch, resetMockScenario, setMockMe, setMockPace } from "./api";
import {
  MOCK_CHAT_CITATION_CHUNK_ID,
  MOCK_CHAT_CITATION_QUOTE,
  MOCK_CHECK_IN_ID,
  MOCK_TASK_AGENT_CONVERSATION_ID,
  MOCK_PROJECT_ID,
  MOCK_TASK_ID,
  MOCK_THEME_ID_ACTIVE_TRAVEL,
  MOCK_THEME_ID_SCHOOL_FOOD,
  MOCK_CASE_STUDIES_INDEX,
  MOCK_STREAMED_SECTION_INDEX,
  mockArtefact,
  mockArtefactSectionProse,
  mockArtefactSectionRepairedProse,
  mockCaseStudiesProse,
  mockCaseStudyCards,
  mockCheckIn,
  mockSectionOneRevisingSpan,
  mockEvidenceThemeIds,
  mockMeEnrolled,
  foldMockOptionRows,
  mockWalkLonglist,
  seedMockOptionRows,
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

// The scripted walks wait 400 ms between ticks; the tests play them at 2%.
beforeAll(() => setMockPace(0.02));

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
    expect(frames.filter((frame) => frame.type === "artefact.section_completed")).toHaveLength(3);
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
      { method: "POST", body: JSON.stringify({ kind: "option", option_id: "continue" }) },
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
      const any = (await longlist()).options[0].option_id;
      const confirm = await mockFetch(`${base}/plan/confirm-baseline`, {
        method: "POST",
        body: JSON.stringify({ artefact_id: "artefact-1", plan_version: 1 }),
      });
      expect(confirm.status).toBe(200);
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

  // Task 058, N26: the mock plays the new frames, fields and routes.
  describe("task 058 contract (N26)", () => {
    const base = `http://localhost/api/v1/tasks/${MOCK_TASK_ID}`;
    type Tick = Extract<SseFrame, { type: "tick" }>;
    type Frame<T extends SseFrame["type"]> = Extract<SseFrame, { type: T }>;
    const ofType = <T extends SseFrame["type"]>(frames: SseFrame[], type: T) =>
      frames.filter((frame): frame is Frame<T> => frame.type === type);

    async function freshTask(capability: "evidence_search" | "options_scoping") {
      resetMockScenario();
      await mockFetch("http://localhost/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify({ name: "Task 058", capability, question: "What works to raise take-up of free childcare places?" }),
      });
    }

    /** Start an Evidence search run, answer its check-in and read every frame. */
    async function playEvidenceWalk(scenario?: string): Promise<SseFrame[]> {
      await freshTask("evidence_search");
      await mockFetch(`${base}/runs`, { method: "POST" });
      const query = scenario === undefined ? "" : `?mockScenario=${scenario}`;
      const response = await mockFetch(`${base}/events${query}`);
      const frames: SseFrame[] = [];
      const consumed = consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
      if (scenario !== "reload-mid-section") {
        await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
        await mockFetch(`${base}/check-ins/${MOCK_CHECK_IN_ID}/response`, {
          method: "POST",
          body: JSON.stringify({ kind: "option", option_id: "continue" }),
        });
      }
      await consumed;
      return frames;
    }

    it("uses the server's stage labels and blurbs, rows on the plan steps and the live stage on the task", async () => {
      const frames = await playEvidenceWalk();
      const started = new Map(ofType(frames, "stage.started").map((frame) => [frame.stage, frame]));
      expect(started.get("acquire")).toMatchObject({ label: "Searching and screening", blurb: "Querying academic and policy databases." });
      expect(started.get("classify")).toMatchObject({ label: "Classifying", blurb: "Labelling each source by its evidence type." });
      expect(started.get("synthesise")).toMatchObject({ label: "Writing", blurb: "A cited report, checked claim by claim." });
      expect(started.get("appraise")?.label).toBe("Classifying");

      const plan = (await (await mockFetch(`${base}/plan`)).json()) as { plan: { steps: { stage: string; row: string }[] } };
      const rows = Object.fromEntries(plan.plan.steps.map((step) => [step.stage, step.row]));
      expect(rows).toMatchObject({ acquire: "search_screen", screen: "search_screen", classify: "categorise", appraise: "categorise", characterise: "characterise", synthesise: "synthesise" });
      await freshTask("options_scoping");
      const scoping = (await (await mockFetch(`${base}/plan`)).json()) as { scoping: { steps: { row: string }[] } };
      expect(scoping.scoping.steps.map((step) => step.row)).toEqual(["baseline", "longlist", "shortlist"]);
    });

    it("stamps the live run with its stage and the server's label while the walk is paused", async () => {
      await freshTask("evidence_search");
      await mockFetch(`${base}/runs`, { method: "POST" });
      const response = await mockFetch(`${base}/events?mockScenario=paused-strip`);
      const frames: SseFrame[] = [];
      void consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
      await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
      const task = (await (await mockFetch(base)).json()) as {
        latest_run: { stage: string; stage_label: string };
        active_run: { stage: string; stage_label: string };
      };
      expect(task.latest_run).toMatchObject({ stage: "screen", stage_label: "Searching and screening" });
      expect(task.active_run).toMatchObject({ stage: "screen", stage_label: "Searching and screening" });
    });

    it("sends ticks in the new shape and none of the old ones", async () => {
      const frames = await playEvidenceWalk();
      const ticks = ofType(frames, "tick");
      expect(ticks.length).toBeGreaterThan(10);
      for (const entry of ticks) {
        expect(Object.keys(entry).sort()).toEqual(
          ["activity", "done", "dropped", "ephemeral", "heartbeat", "occurred_at", "section", "stage", "total", "type", "unit"],
        );
        expect(entry.dropped).toBe(0);
        expect(entry).not.toHaveProperty("sequence");
      }
      const lines = ticks.map((entry) => entry.activity);
      expect(lines).toEqual(expect.arrayContaining([
        "searching · 184 found so far",
        "screening 61 new abstracts · 107 relevant so far",
        "40 of 118 classified",
        "Assigning themes · batch 1 of 3",
        "Looking for: evidence on subsidy uptake among low-income households",
        "Reading findings",
        "Writing",
        "Checking claims",
        "Revising 1 claim",
      ]));
      expect(ticks.find((entry) => entry.activity === "40 of 118 classified")).toMatchObject({ done: 40, total: 118, unit: "documents" });
      expect(ticks.find((entry) => entry.activity === "Writing")?.section).toBe("Section 2 of 2 · Implications for local action");
      // One heartbeat per stage with ticks.
      const heartbeats = ticks.filter((entry): entry is Tick => entry.heartbeat);
      expect(heartbeats.map((entry) => entry.stage)).toEqual(["acquire", "screen", "classify", "appraise", "characterise"]);
    });

    it("streams section 1 as deltas, then the revising span, then the repaired section", async () => {
      const frames = await playEvidenceWalk();
      const draft = mockArtefactSectionProse[1];
      const deltas = ofType(frames, "artefact.section_delta");
      expect(deltas.length).toBeGreaterThan(3);
      expect(deltas.every((entry) => entry.index === MOCK_STREAMED_SECTION_INDEX && entry.mode === "append")).toBe(true);
      expect(deltas.map((entry) => entry.text).join("")).toBe(draft);
      for (const entry of deltas) {
        const words = entry.text.trim().split(/\s+/).length;
        expect(words).toBeGreaterThanOrEqual(1);
        expect(words).toBeLessThanOrEqual(6);
      }
      const [revising] = ofType(frames, "artefact.section_revising");
      expect(revising.spans).toEqual([mockSectionOneRevisingSpan]);
      expect(revising.spans[0].start).toBeGreaterThan(0);
      expect(revising.spans[0].end).toBeLessThanOrEqual(draft.length);
      expect(draft.slice(revising.spans[0].start, revising.spans[0].end)).toBe(
        "Schools that added a walking bus saw 8 more children arrive on foot in every 100.",
      );
      const completed = ofType(frames, "artefact.section_completed").find((entry) => entry.index === MOCK_STREAMED_SECTION_INDEX)!;
      expect(completed.prose).toBe(mockArtefactSectionRepairedProse[1]);
      expect(completed.prose.slice(0, revising.spans[0].start)).toBe(draft.slice(0, revising.spans[0].start));
      const order = frames.map((frame) => frame.type);
      expect(order.lastIndexOf("artefact.section_delta")).toBeLessThan(order.indexOf("artefact.section_revising"));
      expect(order.indexOf("artefact.section_revising")).toBeLessThan(order.lastIndexOf("artefact.section_completed"));
    });

    it("names the sources read before the prose and the writer's citations after it (evidence shown live)", async () => {
      const frames = await playEvidenceWalk();
      const draft = mockArtefactSectionProse[1];
      const sources = ofType(frames, "artefact.section_sources");
      expect(sources.map((entry) => entry.sources.length)).toEqual([2, 5]);
      expect(sources.every((entry) => entry.index === MOCK_STREAMED_SECTION_INDEX)).toBe(true);
      const claims = ofType(frames, "artefact.section_claim");
      expect(claims).toHaveLength(2);
      for (const claim of claims) {
        expect(claim.index).toBe(MOCK_STREAMED_SECTION_INDEX);
        expect(claim.end).toBeLessThanOrEqual(Array.from(draft).length);
        expect(claim.sources.length).toBeGreaterThan(0);
      }
      expect(draft.slice(claims[1].start, claims[1].end)).toBe(
        "Schools that added a walking bus saw 8 more children arrive on foot in every 100.",
      );
      const order = frames.map((frame) => frame.type);
      expect(order.indexOf("artefact.section_sources")).toBeLessThan(order.indexOf("artefact.section_delta"));
      expect(order.lastIndexOf("artefact.section_delta")).toBeLessThan(order.indexOf("artefact.section_claim"));
      expect(order.lastIndexOf("artefact.section_claim")).toBeLessThan(order.indexOf("artefact.section_revising"));
    });

    it("completes each section with citations numbered as the final report numbers them (round 7)", async () => {
      const frames = await playEvidenceWalk();
      const completed = ofType(frames, "artefact.section_completed");
      expect(completed.map((entry) => entry.index)).toEqual([0, MOCK_STREAMED_SECTION_INDEX, MOCK_CASE_STUDIES_INDEX]);
      const [keyFindings] = completed;
      const finalClaim = mockArtefact.sections![0].blocks![0].claims![0];
      expect(keyFindings.citations).toHaveLength(1);
      const [citation] = keyFindings.citations!;
      expect([citation.start, citation.end]).toEqual(finalClaim.span);
      expect(citation.n).toBe(finalClaim.citations![0].n);
      expect(citation.title).toBe(finalClaim.citations![0].source_title);
      expect(citation.tier).toBe(finalClaim.citations![0].grounding_tier);
      expect(keyFindings.prose.slice(citation.start, citation.end)).toBe(finalClaim.text);
      // Every section's live citations are the committed report's, span by span.
      for (const entry of completed) {
        const section = mockArtefact.sections!.find((candidate) => candidate.title === entry.title)!;
        const expected = section.blocks!.flatMap((block) =>
          (block.claims ?? [])
            .filter((claim) => claim.span != null)
            .sort((left, right) => left.span![0] - right.span![0])
            .flatMap((claim) =>
              (claim.citations ?? []).map((cited) => ({
                start: claim.span![0],
                end: claim.span![1],
                n: cited.n,
                title: cited.source_title,
                tier: cited.grounding_tier,
              })),
            ),
        );
        expect(
          (entry.citations ?? []).map(({ start, end, n, title, tier }) => ({ start, end, n, title, tier })),
        ).toEqual(expected);
        for (const each of entry.citations ?? []) {
          expect(entry.prose.slice(each.start, each.end).length).toBeGreaterThan(0);
        }
      }
      expect(completed.find((entry) => entry.index === MOCK_STREAMED_SECTION_INDEX)!.citations).toHaveLength(3);
      expect(completed.find((entry) => entry.index === MOCK_CASE_STUDIES_INDEX)!.citations).toHaveLength(1);
      const referenceNumbers = new Set((mockArtefact.references ?? []).map((reference) => reference.n));
      for (const entry of completed) {
        for (const each of entry.citations ?? []) expect(referenceNumbers.has(each.n)).toBe(true);
      }
      expect([...referenceNumbers].sort()).toEqual([1, 2, 3]);
    });

    it("streams the case studies card by card into their slot, then the checked cards (round 7)", async () => {
      const frames = await playEvidenceWalk();
      const order = frames.map((frame) => frame.type);
      const started = frames.findIndex(
        (frame) => frame.type === "artefact.section_started" && frame.index === MOCK_CASE_STUDIES_INDEX,
      );
      const cards = ofType(frames, "artefact.section_card");
      expect(cards.map((card) => ({ title: card.title, prose: card.prose }))).toEqual(mockCaseStudyCards);
      expect(cards.every((card) => card.index === MOCK_CASE_STUDIES_INDEX && card.ephemeral)).toBe(true);
      expect(cards.every((card) => !("sequence" in card))).toBe(true);
      const completed = ofType(frames, "artefact.section_completed").find(
        (entry) => entry.index === MOCK_CASE_STUDIES_INDEX,
      )!;
      expect(completed.title).toBe("Case studies");
      expect(completed.prose).toBe(mockCaseStudiesProse);
      expect(started).toBeGreaterThan(0);
      expect(started).toBeLessThan(order.indexOf("artefact.section_card"));
      expect(order.lastIndexOf("artefact.section_card")).toBeLessThan(frames.indexOf(completed));
      // The slot is last and names its role, so body indexes keep their places.
      const [skeleton] = ofType(frames, "artefact.skeleton");
      expect(skeleton.sections.map((slot) => slot.role)).toEqual(["key_findings", "body", "case_studies"]);
      expect(skeleton.sections.at(-1)?.index).toBe(MOCK_CASE_STUDIES_INDEX);
      const line = ofType(frames, "tick").find((entry) => entry.activity === "Writing the case studies");
      expect(line?.section).toBe("Case studies");
      const finalSection = mockArtefact.sections!.find((section) => section.role === "case_studies");
      expect(finalSection?.cards?.map((card) => card.title)).toEqual(mockCaseStudyCards.map((card) => card.title));
    });

    it("serves the planner turn as a stream: progress, deltas, one completed last", async () => {
      await freshTask("evidence_search");
      const post = async (message: string) => {
        const response = await mockFetch(`${base}/task-agent-turns`, {
          method: "POST",
          body: JSON.stringify({ client_turn_id: crypto.randomUUID(), message }),
        });
        expect(response.headers.get("Content-Type")).toBe("application/x-ndjson");
        return readNdjson(response);
      };
      const first = await post("What works to raise take-up of free childcare places?");
      expect(first[0]).toEqual({ type: "progress", label: "Drafting the plan" });
      expect(first.filter((event) => event.type === "completed")).toHaveLength(1);
      expect(first.at(-1)?.type).toBe("completed");
      const deltas = first.filter((event) => event.type === "delta");
      expect(deltas.length).toBeGreaterThan(2);
      const turn = (first.at(-1) as { turn: { reply: string; question: string; suggestions: string[]; part: { id: string; options: { id: string; primary: boolean; reason: string | null }[] } } }).turn;
      expect(deltas.map((event) => event.text).join("")).toBe(turn.reply);
      expect(turn.question).toBe("Is the question as you want it, or do you want to narrow it?");
      expect(turn.suggestions).toEqual(["That's my question", "Narrow it"]);
      expect(turn.part.id).toBe("question");
      expect(turn.part.options.map((option) => option.primary)).toEqual([true, false]);
      expect(turn.part.options[0].reason).toBe("It names the outcome, the group and the setting.");

      const second = (await post("That's my question")).at(-1) as { turn: { part: { id: string; chips: unknown[] } } };
      expect(second.turn.part.id).toBe("scope");
      expect(second.turn.part.chips).toHaveLength(3);
      const third = (await post("Looks right")).at(-1) as { turn: { part: { id: string; options: { label: string; primary: boolean; sub: string }[] } } };
      expect(third.turn.part.id).toBe("thoroughness");
      // Fastest to slowest, in the planner's order (owner, polish round 3).
      expect(third.turn.part.options.map((option) => option.label)).toEqual(["Rapid overview", "Standard report", "Detailed report"]);
      expect(third.turn.part.options[1].primary).toBe(true);
      expect(third.turn.part.options[1].sub).toContain("~10-20 min");

      const transcript = (await (await mockFetch(`${base}/task-agent-turns`)).json()) as { data: { question: string | null }[] };
      expect(transcript.data.map((row) => row.question)).toEqual([turn.question, null, null]);
    });

    it("pauses at a real check-in kind after searching and screening", async () => {
      expect(mockCheckIn).toMatchObject({ kind: "steer_point", boundary: "after_component", component: "acquire", stage: "acquire" });
      expect(mockCheckIn.options?.map((option) => option.id)).toEqual(["continue", "deepen_search", "rescope_filters", "guide_queries", "abort"]);
      expect(mockCheckIn.options?.[0]).toMatchObject({ suggested: true, why: "Coverage matches the plan and the second round added little." });
      const frames = await playEvidenceWalk();
      const order = frames.map((frame) => (frame.type === "stage.started" ? `start:${frame.stage}` : frame.type));
      expect(order.indexOf("checkin.pending")).toBeGreaterThan(order.indexOf("start:screen"));
      expect(order.indexOf("checkin.pending")).toBeLessThan(order.indexOf("start:classify"));
      const read = (await (await mockFetch(`${base}/check-ins`)).json()) as { data: { kind: string }[] };
      expect(read.data[0].kind).toBe("steer_point");
    });

    describe("the scoping walk", () => {
      /** Open the scoping run, confirm the baseline gate and read frames until
       *  the longlist walk's parent run succeeds. */
      async function playScopingWalk() {
        await freshTask("options_scoping");
        await mockFetch(`${base}/runs`, { method: "POST" });
        const response = await mockFetch(`${base}/events`);
        const frames: SseFrame[] = [];
        void consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
        await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
        await mockFetch(`${base}/check-ins/4c1acbe7-c4a1-4e0b-8d5a-bb25ea2ef635/response`, {
          method: "POST",
          body: JSON.stringify({ kind: "option", option_id: "confirm_plan" }),
        });
        return frames;
      }
      const walkDone = (frames: SseFrame[]) =>
        ofType(frames, "run.status").some(
          (frame) => frame.status === "succeeded" && ofType(frames, "stage.completed").some((done) => done.stage === "shortlist"),
        );

      it("walks every stage with server labels and child searches, ten at once then two", async () => {
        const frames = await playScopingWalk();
        const optionsBefore = (await (await mockFetch(`${base}/options`)).json()) as { options: unknown[] };
        expect(optionsBefore.options).toEqual([]);
        expect((await mockFetch(`${base}/longlist`)).status).toBe(404);
        await vi.waitFor(() => expect(walkDone(frames)).toBe(true), { timeout: 8000 });

        const parent = ofType(frames, "stage.started").find((frame) => frame.stage === "inherit")!.capability_run_id!;
        const parentStages = ofType(frames, "stage.started").filter((frame) => frame.capability_run_id === parent);
        expect(parentStages.map((frame) => frame.stage)).toEqual([
          "inherit", "suggest", "option_searches", "extract_interventions", "longlist", "option_profile", "constrain", "theme", "shortlist",
        ]);
        expect(parentStages.find((frame) => frame.stage === "option_searches")?.label).toBe("Searching for each option");

        const childIds = ofType(frames, "run.status")
          .filter((frame) => frame.status === "running" && frame.capability_run_id.startsWith("b1000000"))
          .map((frame) => frame.capability_run_id);
        expect(childIds).toHaveLength(12);
        expect(new Set(childIds).size).toBe(12);
        expect(childIds).not.toContain(parent);
        for (const childId of childIds) {
          const acquire = frames.filter((frame) => "capability_run_id" in frame && frame.capability_run_id === childId);
          expect(acquire.map((frame) => (frame.type === "run.status" ? `${frame.type}:${frame.status}` : `${frame.type}:${"stage" in frame ? frame.stage : ""}`))).toEqual([
            "run.status:running", "stage.started:acquire", "stage.completed:acquire", "run.status:succeeded",
          ]);
        }
        // Ten start before the first one ends; the last two wait for a slot.
        const order = frames.map((frame) =>
          frame.type === "run.status" && childIds.includes(frame.capability_run_id) ? frame.status : frame.type === "stage.completed" && childIds.includes(frame.capability_run_id ?? "") ? "done" : "",
        ).filter(Boolean);
        expect(order.slice(0, 10)).toEqual(Array(10).fill("running"));

        const searchLines = ofType(frames, "tick").filter((entry) => entry.stage === "option_searches").map((entry) => entry.activity);
        expect(searchLines).toHaveLength(12);
        expect(searchLines[3]).toMatch(/^4 of 12 searches done · [\d,]+ sources so far$/);
        const done = ofType(frames, "stage.completed").find((frame) => frame.stage === "option_searches")!;
        expect(done.summary).toMatchObject({ total: 12, finished: 12, sources: expect.any(Number) });

        // The options read follows the child walks and the clustering.
        const options = (await (await mockFetch(`${base}/options`)).json()) as {
          options: { name: string; origin: string; merged_into_option_id: string | null; search_status: string; found: number | null }[];
        };
        expect(options.options).toHaveLength(14);
        const searched = options.options.slice(0, 12);
        expect(searched.every((row) => row.search_status === "searched" && row.found !== null)).toBe(true);
        expect(searched.reduce((total, row) => total + (row.found ?? 0), 0)).toBe(done.summary?.sources);
        expect(options.options.filter((row) => row.merged_into_option_id !== null).map((row) => row.name)).toEqual(["Transport subsidies for young job seekers"]);
        expect(options.options.slice(12).map((row) => row.origin)).toEqual(["clustered", "clustered"]);
        expect((await mockFetch(`${base}/longlist`)).status).toBe(200);
      });

      it("serves the longlist read over the same option ids as the options read", async () => {
        const frames = await playScopingWalk();
        // Poll quickly: the walk-time longlist read ends when the walk does.
        await vi.waitFor(async () => expect((await mockFetch(`${base}/longlist`)).status).toBe(200), { interval: 1, timeout: 8000 });
        const longlist = (await (await mockFetch(`${base}/longlist`)).json()) as { options: { option_id: string; name: string; origin: string }[] };
        const rows = (await (await mockFetch(`${base}/options`)).json()) as {
          options: { option_id: string; name: string; origin: string; merged_into_option_id: string | null }[];
        };
        const live = rows.options.filter((row) => row.merged_into_option_id === null);
        expect(longlist.options.map((option) => [option.option_id, option.name, option.origin])).toEqual(
          live.map((row) => [row.option_id, row.name, row.origin]),
        );
        expect(rows.options).toHaveLength(14);
        expect(live).toHaveLength(13);
        await vi.waitFor(() => expect(walkDone(frames)).toBe(true), { timeout: 8000 });
      });

      it("grows the longlist read in four steps after the longlist stage", () => {
        const rows = foldMockOptionRows(seedMockOptionRows()).map((row, index) => ({ ...row, found: row.found ?? 100 + index }));
        const read = (stage: Parameters<typeof mockWalkLonglist>[1]) => mockWalkLonglist(rows, stage);

        const built = read("longlist");
        expect(built.options).toHaveLength(13);
        expect(built.options!.every((option) => option.document_count > 0)).toBe(true);
        expect(built.options!.every((option) => option.primary_lever_type == null && option.ambition_reason == null)).toBe(true);
        expect(built.options!.every((option) => option.state === "included" && option.exclusion == null)).toBe(true);
        expect(built.themes).toEqual([]);
        expect(built.options!.every((option) => option.shortlist == null)).toBe(true);

        const profiled = read("option_profile");
        expect(profiled.options!.every((option) => option.primary_lever_type != null && option.ambition_reason != null)).toBe(true);
        expect(profiled.options!.some((option) => option.state === "excluded")).toBe(false);
        expect(profiled.themes).toEqual([]);

        const constrained = read("constrain");
        const excluded = constrained.options!.filter((option) => option.state === "excluded");
        expect(excluded).toHaveLength(2);
        expect(excluded.every((option) => (option.exclusion?.reason ?? "") !== "")).toBe(true);
        expect(constrained.themes).toEqual([]);
        expect(constrained.options!.every((option) => option.shortlist == null)).toBe(true);

        const themed = read("theme");
        expect(themed.themes).toHaveLength(2);
        const themedIds = themed.themes!.flatMap((theme) => theme.option_ids ?? []);
        expect(themedIds.sort()).toEqual(themed.options!.filter((option) => option.state === "included").map((option) => option.option_id).sort());
        expect(themed.options!.every((option) => option.shortlist == null)).toBe(true);

        const shortlisted = read("shortlist");
        expect(shortlisted.options!.filter((option) => option.shortlist != null)).toHaveLength(3);
      });

      it("shows rows from the end of suggest, queued then searching then searched", async () => {
        const frames = await playScopingWalk();
        await vi.waitFor(() => expect(ofType(frames, "run.status").filter((frame) => frame.status === "running").length).toBeGreaterThan(2));
        const mid = (await (await mockFetch(`${base}/options`)).json()) as { options: { search_status: string; found: number | null }[] };
        expect(mid.options).toHaveLength(12);
        expect(mid.options.filter((row) => row.search_status === "searching").length).toBeLessThanOrEqual(10);
        expect(mid.options.every((row) => (row.search_status === "searched") === (row.found !== null))).toBe(true);
        await vi.waitFor(() => expect(walkDone(frames)).toBe(true), { timeout: 8000 });
      });
    });

    it("selects paused-strip, which holds at the check-in even once it is answered", async () => {
      await freshTask("evidence_search");
      await mockFetch(`${base}/runs`, { method: "POST" });
      const response = await mockFetch(`${base}/events?mockScenario=paused-strip`);
      const frames: SseFrame[] = [];
      void consumeEventStream(response.body!, 0, (frame) => frames.push(frame));
      await vi.waitFor(() => expect(frames.at(-1)?.type).toBe("checkin.pending"));
      await mockFetch(`${base}/check-ins/${MOCK_CHECK_IN_ID}/response`, { method: "POST", body: JSON.stringify({ kind: "option", option_id: "continue" }) });
      await new Promise((resolve) => setTimeout(resolve, 100));
      expect(frames.at(-1)?.type).toBe("checkin.pending");
      expect(ofType(frames, "run.status").at(-1)?.status).toBe("paused");
    });

    it("selects reload-mid-section: replay to section 1, one replace of the first half, then appends", async () => {
      const frames = await playEvidenceWalk("reload-mid-section");
      const draft = mockArtefactSectionProse[1];
      const started = frames.findIndex((frame) => frame.type === "artefact.section_started" && frame.index === MOCK_STREAMED_SECTION_INDEX);
      expect(started).toBeGreaterThan(0);
      // The replay is durable frames only; ticks are never replayed.
      expect(frames.slice(0, started).some((frame) => frame.type === "tick" || frame.type === "artefact.section_delta")).toBe(false);
      const deltas = ofType(frames, "artefact.section_delta");
      expect(frames[started + 1]).toBe(deltas[0]);
      expect(deltas[0].mode).toBe("replace");
      expect(deltas.slice(1).every((entry) => entry.mode === "append")).toBe(true);
      expect(deltas[0].text.length).toBeGreaterThan(0);
      expect(deltas[0].text.length).toBeLessThan(draft.length);
      expect(draft.startsWith(deltas[0].text)).toBe(true);
      expect(deltas.map((entry) => entry.text).join("")).toBe(draft);
      expect(frames.at(-1)).toMatchObject({ type: "run.status", status: "succeeded" });
    });
  });
});
