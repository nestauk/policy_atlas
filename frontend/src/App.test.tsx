import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { TASK } from "./lib/vocabulary";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // The landing heading moved from "Projects" to "Tasks" with the 032
  // vocabulary split: a backend `project` row is a Task on screen. The
  // assertion reads the word from the shared vocabulary module rather than
  // repeating the literal, so it cannot drift from what the app renders.
  it("renders the tasks landing heading", () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    render(<App />);
    expect(screen.getByRole("heading", { name: TASK.many })).toBeInTheDocument();
  });
});
