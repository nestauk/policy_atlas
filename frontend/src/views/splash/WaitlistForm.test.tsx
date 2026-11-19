import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WAITLIST_LIMITS, WaitlistForm } from "./WaitlistForm";

describe("WaitlistForm length limits", () => {
  it("shows a live over-limit warning and disables submit", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<WaitlistForm />);

    const role = screen.getByLabelText(/what would you like to use policy atlas for/i);
    await user.click(role);
    await user.paste("x".repeat(WAITLIST_LIMITS.roleOrReason + 5));

    expect(screen.getByRole("alert")).toHaveTextContent(/too long/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/5 characters over/i);
    expect(screen.getByRole("button", { name: /^submit$/i })).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("does not submit while a field is over the limit", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ entry_id: "1", email: "a@b.co", created_at: "2026-01-01" }), {
        status: 201,
      }),
    );
    render(<WaitlistForm />);

    await user.type(screen.getByLabelText(/^email$/i), "ada@example.com");
    await user.type(screen.getByLabelText(/^name$/i), "Ada");
    await user.click(screen.getByLabelText(/what would you like to use policy atlas for/i));
    await user.paste("x".repeat(WAITLIST_LIMITS.roleOrReason + 1));

    await user.click(screen.getByRole("button", { name: /^submit$/i }));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("WaitlistForm CAPTCHA", () => {
  // Trailing slash as AWS returns it; the form must not load `…//jsapi.js`.
  const SCRIPT_URL = "https://abc123.edge.sdk.awswaf.com/abc123/def456/";

  beforeEach(() => {
    vi.stubEnv("VITE_WAF_CAPTCHA_SCRIPT_URL", SCRIPT_URL);
    vi.stubEnv("VITE_WAF_CAPTCHA_API_KEY", "key-1");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    vi.useRealTimers();
    delete window.AwsWafCaptcha;
    document.head.querySelectorAll("script[data-waf-captcha]").forEach((s) => s.remove());
  });

  /** A solved-at-once puzzle; installed before render so no script is injected. */
  function installFakeCaptcha() {
    const renderCaptcha = vi.fn(
      (_container: HTMLElement, options: { onSuccess: (token: string) => void }) => {
        options.onSuccess("tok-1");
      },
    );
    window.AwsWafCaptcha = { renderCaptcha };
    return renderCaptcha;
  }

  function mockFetch(response: Response) {
    return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
  }

  async function fillForm(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText(/^email$/i), "ada@example.com");
    await user.type(screen.getByLabelText(/^name$/i), "Ada");
    await user.type(screen.getByLabelText(/what would you like to use policy atlas for/i), "Research");
  }

  function sentHeaders(fetchSpy: ReturnType<typeof mockFetch>): Record<string, string> {
    return fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
  }

  const created = () =>
    new Response(JSON.stringify({ entry_id: "1", email: "ada@example.com", created_at: "x" }), {
      status: 201,
    });

  it("without a script URL shows no puzzle and sends no token", async () => {
    vi.unstubAllEnvs();
    const user = userEvent.setup();
    const fetchSpy = mockFetch(created());
    render(<WaitlistForm />);

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(screen.queryByTestId("waf-captcha")).not.toBeInTheDocument();
    expect(document.head.querySelector("script[data-waf-captcha]")).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(sentHeaders(fetchSpy)).toEqual({ "Content-Type": "application/json" });
  });

  it("renders the puzzle on first focus and sends its token", async () => {
    const renderCaptcha = installFakeCaptcha();
    const user = userEvent.setup();
    const fetchSpy = mockFetch(created());
    render(<WaitlistForm />);
    expect(renderCaptcha).not.toHaveBeenCalled();

    const box = screen.getByTestId("waf-captcha");
    await fillForm(user);
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(renderCaptcha).toHaveBeenCalledTimes(1);
    expect(renderCaptcha.mock.calls[0][0]).toBe(box);
    expect(sentHeaders(fetchSpy)["x-aws-waf-token"]).toBe("tok-1");
  });

  it("asks for the puzzle again when the firewall refuses the token", async () => {
    const renderCaptcha = installFakeCaptcha();
    const user = userEvent.setup();
    mockFetch(new Response(null, { status: 405, headers: { "x-amzn-waf-action": "captcha" } }));
    render(<WaitlistForm />);

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(await screen.findByRole("status")).toHaveTextContent("Please solve the puzzle again");
    expect(renderCaptcha).toHaveBeenCalledTimes(2);
  });

  it("treats a 405 without the firewall header as the generic error", async () => {
    const renderCaptcha = installFakeCaptcha();
    const user = userEvent.setup();
    mockFetch(new Response(null, { status: 405 }));
    render(<WaitlistForm />);

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
    expect(renderCaptcha).toHaveBeenCalledTimes(1);
  });

  it("shows the reload message when the SDK throws instead of rendering", async () => {
    window.AwsWafCaptcha = {
      renderCaptcha: () => {
        throw new Error("bad api key");
      },
    };
    const user = userEvent.setup();
    render(<WaitlistForm />);

    await user.click(screen.getByLabelText(/^email$/i));

    expect(
      screen.getByText("The sign-up check did not load. Reload the page to try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^submit$/i })).toBeDisabled();
  });

  it("says so when the script does not load, and recovers when it does", async () => {
    // Real time still trickles through (testing-library drains with a real `setTimeout(0)`
    // that Vitest's fake clock would never fire); the 10-second wait is advanced by hand.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchSpy = mockFetch(created());
    render(<WaitlistForm />);

    await fillForm(user);
    const scripts = document.head.querySelectorAll<HTMLScriptElement>("script[data-waf-captcha]");
    expect(scripts).toHaveLength(1);
    const script = scripts[0];
    expect(script.src).toMatch(/\/jsapi\.js$/);
    expect(script.src).not.toMatch(/\/\/jsapi\.js$/);

    const reload = "The sign-up check did not load. Reload the page to try again.";
    expect(screen.queryByText(reload)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByText(reload)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /^submit$/i });
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(fetchSpy).not.toHaveBeenCalled();

    const renderCaptcha = installFakeCaptcha();
    act(() => {
      script.dispatchEvent(new Event("load"));
    });
    expect(screen.queryByText(reload)).not.toBeInTheDocument();
    expect(renderCaptcha).toHaveBeenCalledTimes(1);
    expect(submit).toBeEnabled();
  });
});
