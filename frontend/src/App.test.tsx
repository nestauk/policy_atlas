import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App, { queryClient } from "./App";
import { TASK } from "./lib/vocabulary";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // The landing heading moved from "Projects" to "Tasks" with the 032
  // vocabulary split: a backend `task` row is a Task on screen. The
  // assertion reads the word from the shared vocabulary module rather than
  // repeating the literal, so it cannot drift from what the app renders.
  it("renders the tasks landing heading", () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    render(<App />);
    expect(screen.getByRole("heading", { name: TASK.many })).toBeInTheDocument();
  });

  // Review fix (task 037): the cache clear used to run in a passive effect,
  // AFTER the swapped router had already rendered — a frame where cached
  // private data could show up on a public Task's URL. Signing out is a
  // real settled-status change reachable through the UI (Account → Sign
  // out), so it exercises the render-time clear directly rather than the
  // internals.
  it("clears the query cache on a settled status change", async () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    const user = userEvent.setup();
    render(<App />);
    queryClient.setQueryData(["test-cache-probe"], "sensitive-cached-value");
    expect(queryClient.getQueryData(["test-cache-probe"])).toBe("sensitive-cached-value");

    await user.click(await screen.findByRole("button", { name: "Account" }));
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(queryClient.getQueryData(["test-cache-probe"])).toBeUndefined();
  });
});
