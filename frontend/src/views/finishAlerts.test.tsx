import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as queries from "../api/queries";
import { tocAlertText, useFinishAlerts } from "./finishAlerts";

vi.mock("../api/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/queries")>();
  return { ...actual, useTasks: vi.fn(), useApiClient: vi.fn() };
});

const shown: { title: string; body?: string }[] = [];
class FakeNotification {
  static permission = "granted";
  onclick: (() => void) | null = null;
  constructor(title: string, options?: { body?: string }) {
    shown.push({ title, body: options?.body });
  }
  close() {}
}

function task(status: string | null, capability = "evidence_search") {
  return {
    task_id: "t1",
    name: "Food advert limits",
    capability,
    latest_run: status === null ? { capability_run_id: "r1", status: "succeeded", started_at: "" } : { capability_run_id: "r1", status, started_at: "" },
  };
}

function setTasks(...list: ReturnType<typeof task>[]) {
  vi.mocked(queries.useTasks).mockReturnValue({ data: { data: list } } as unknown as ReturnType<typeof queries.useTasks>);
}

const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter>{children}</MemoryRouter>;

describe("finish alerts", () => {
  beforeEach(() => {
    shown.length = 0;
    vi.stubGlobal("Notification", FakeNotification);
    vi.mocked(queries.useApiClient).mockReturnValue({
      GET: vi.fn(async () => ({ data: { check_status: "checked" } })),
    } as unknown as ReturnType<typeof queries.useApiClient>);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("alerts once when a running task finishes, not on the first sighting", () => {
    setTasks(task("running"));
    const { rerender } = renderHook(() => useFinishAlerts(), { wrapper });
    expect(shown).toHaveLength(0);
    setTasks(task(null));
    rerender();
    expect(shown).toEqual([{ title: "Food advert limits", body: "Your results are ready." }]);
    rerender();
    expect(shown).toHaveLength(1);
  });

  it("says when a walk waits for an answer", () => {
    setTasks(task("running"));
    const { rerender } = renderHook(() => useFinishAlerts(), { wrapper });
    setTasks(task("paused"));
    rerender();
    expect(shown[0]?.body).toBe("Policy Atlas has a question for you.");
  });

  it("names what a theory of change finished", async () => {
    setTasks(task("running", "theory_of_change"));
    const { rerender } = renderHook(() => useFinishAlerts(), { wrapper });
    setTasks(task(null, "theory_of_change"));
    rerender();
    await waitFor(() => expect(shown[0]?.body).toBe("The evidence check is finished."));
    expect(tocAlertText("drafted")).toMatch(/drafted/);
    expect(tocAlertText("checking")).toBeNull();
  });

  it("stays quiet without permission", () => {
    FakeNotification.permission = "default";
    setTasks(task("running"));
    const { rerender } = renderHook(() => useFinishAlerts(), { wrapper });
    setTasks(task(null));
    rerender();
    expect(shown).toHaveLength(0);
    FakeNotification.permission = "granted";
  });
});
