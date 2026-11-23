import { render, screen, within } from "@testing-library/react";
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

  it("has a banner, one main region and a footer; links that leave say they open a new tab", () => {
    render(
      <MemoryRouter>
        <SplashView />
      </MemoryRouter>,
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(within(main).getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(within(main).getByRole("heading", { name: /^request access$/i })).toBeInTheDocument();
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("link", { name: /^About Nesta\s*\(opens in new tab\)$/ })).toHaveAttribute("target", "_blank");
  });
});
