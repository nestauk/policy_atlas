import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("SplashView Request access", () => {
  const INVITE_LINE = "You are using an invite link.";

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  function renderSplash() {
    return render(
      <MemoryRouter>
        <SplashView />
      </MemoryRouter>,
    );
  }

  async function sendRequest(): Promise<Record<string, unknown>> {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ entry_id: "1", email: "ada@example.com", created_at: "x" }), {
        status: 201,
      }),
    );
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email$/i), "ada@dhsc.example");
    await user.type(screen.getByLabelText(/^name$/i), "Ada");
    await user.type(screen.getByLabelText(/what would you like to use policy atlas for/i), "Research");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    return JSON.parse(fetchSpy.mock.calls[0][1]?.body as string) as Record<string, unknown>;
  }

  it("shows the intro and, once sent, the same success message to everyone", async () => {
    renderSplash();

    expect(
      screen.getByText(
        "Tell us a little about yourself. If your organisation already has access, we email " +
          "your sign-in details in a few minutes. If not, we review your request and get in touch.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(INVITE_LINE)).not.toBeInTheDocument();

    const body = await sendRequest();

    expect(body).not.toHaveProperty("invite_code");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Thanks. Check your email in a few minutes. If nothing arrives, we are reviewing your " +
        "request and will get in touch. Already have an account? Use Sign in.",
    );
  });

  it("with an invite link, says so, sends the code and clears it from the address", async () => {
    const scrollIntoView = vi.spyOn(HTMLElement.prototype, "scrollIntoView");
    window.history.replaceState(null, "", "/#invite=K7Q2-M9XD-3FHP");
    renderSplash();

    expect(screen.getByText(INVITE_LINE)).toBeInTheDocument();
    expect(window.location.hash).toBe("#access");
    expect(scrollIntoView).toHaveBeenCalled();

    const body = await sendRequest();

    expect(body.invite_code).toBe("K7Q2-M9XD-3FHP");
  });
});
