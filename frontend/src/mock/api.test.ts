import { describe, expect, it, vi } from "vitest";

import { consumeEventStream } from "../api/sse";
import type { SseFrame } from "../api/sseFrame";
import { mockFetch, resetMockScenario } from "./api";
import { MOCK_CHECK_IN_ID, MOCK_PROJECT_ID } from "./fixtures";

describe("mock API", () => {
  it("serves deterministic, screened-in landscape fixtures", async () => {
    const response = await mockFetch(`http://localhost/api/v1/projects/${MOCK_PROJECT_ID}/landscape`);
    const landscape = await response.json() as { evidence_types: Record<string, number>; themes: { size: number }[] };
    expect(Object.values(landscape.evidence_types).reduce((total, count) => total + count, 0)).toBe(46);
    expect(landscape.themes.reduce((total, theme) => total + theme.size, 0)).toBe(46);
  });

  it("holds the scripted stream at the check-in then completes after an answer", async () => {
    resetMockScenario();
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
    expect(frames.at(-1)).toMatchObject({ type: "run.status", status: "succeeded" });
  });
});
