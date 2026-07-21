import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the project landing heading", () => {
    vi.stubEnv("VITE_DEV_TOKEN", "test-token");
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "Your evidence projects" }),
    ).toBeInTheDocument();
  });
});
