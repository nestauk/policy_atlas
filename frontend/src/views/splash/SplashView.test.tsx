import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { SplashView } from "./SplashView";

vi.mock("../../auth", () => ({
  useAuth: () => ({
    user: null,
    status: "unauthenticated",
    signIn: vi.fn(),
    signOut: vi.fn(),
    onUnauthenticated: vi.fn(),
    getAccessToken: async () => null,
  }),
}));

vi.mock("../../auth/DevTokenAuthProvider", () => ({
  acceptDevToken: vi.fn(),
}));

describe("SplashView", () => {
  it("renders the hero and Request access / Sign in CTAs", () => {
    render(
      <MemoryRouter>
        <SplashView />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /create policy plans you can trust/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /request access/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^request access$/i })).toBeInTheDocument();
    // Feature steps stay hidden until screenshots are ready.
    expect(screen.queryByText(/quickly become an expert/i)).not.toBeInTheDocument();
  });
});
