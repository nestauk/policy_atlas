import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fieldErrorsFromEnvelope } from "../../lib/errors";
import { AuthContext } from "../../auth/AuthContext";
import {
  FieldErrors,
  InterruptedRunCard,
  NotFoundView,
  ReconnectingBanner,
  ReauthRedirect,
} from "./index";

describe("feedback error surfaces", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts the auth-layer recovery for an expired session", () => {
    const onUnauthenticated = vi.fn();
    render(
      <AuthContext.Provider value={{
        getAccessToken: async () => null,
        signIn: vi.fn(),
        signOut: vi.fn(),
        onUnauthenticated,
        user: null,
        status: "unauthenticated",
      }}>
        <ReauthRedirect />
      </AuthContext.Provider>,
    );
    expect(onUnauthenticated).toHaveBeenCalledOnce();
    expect(screen.getByRole("status")).toHaveTextContent("session expired");
  });

  it("renders owner-indistinguishable not-found copy", () => {
    render(<NotFoundView />);
    expect(screen.getByRole("heading", { name: "This task is unavailable" })).toBeInTheDocument();
  });

  it("maps 422 envelope locations to field-anchored messages", () => {
    const errors = fieldErrorsFromEnvelope({ detail: [{ loc: ["body", "name"], msg: "Name is required" }] });
    render(<FieldErrors field="name" errors={errors} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required");
  });

  it("renders reconnect and interrupted-run recovery surfaces", () => {
    const startFresh = vi.fn();
    render(<><ReconnectingBanner connectionStatus="reconnecting" /><InterruptedRunCard onStartFreshRun={startFresh} /></>);
    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting");
    expect(screen.getByRole("button", { name: "Start a fresh run" })).toBeInTheDocument();
  });

  it("does not show the reconnect banner for the initial connecting state", () => {
    render(<ReconnectingBanner connectionStatus="connecting" />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("marks a reconnecting stream stale after 30 seconds", () => {
    vi.useFakeTimers();
    render(<ReconnectingBanner connectionStatus="reconnecting" />);
    act(() => vi.advanceTimersByTime(30_000));
    expect(screen.getByRole("status")).toHaveTextContent("Updates may be stale");
  });
});
