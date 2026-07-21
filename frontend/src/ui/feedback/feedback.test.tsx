import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fieldErrorsFromEnvelope } from "../../lib/errors";
import { AuthContext } from "../../auth/AuthContext";
import { ToastProvider } from "../radix/Toast";
import {
  FieldErrors,
  InlineConflictNotice,
  InterruptedRunCard,
  NotFoundView,
  ReconnectingBanner,
  ReauthRedirect,
  useServerErrorToast,
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
    expect(screen.getByRole("heading", { name: "This project is unavailable" })).toBeInTheDocument();
  });

  it("maps 422 envelope locations to field-anchored messages", () => {
    const errors = fieldErrorsFromEnvelope({ detail: [{ loc: ["body", "name"], msg: "Name is required" }] });
    render(<FieldErrors field="name" errors={errors} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required");
  });

  it("offers keyboard-reachable refresh and dismiss controls for conflicts", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    render(<InlineConflictNotice code="run_active" onRefetch={refetch} />);
    await user.tab();
    expect(screen.getByRole("button", { name: "Refresh" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(refetch).toHaveBeenCalledOnce();
    await user.tab();
    expect(screen.getByRole("button", { name: "Dismiss" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders reconnect and interrupted-run recovery surfaces", () => {
    const startFresh = vi.fn();
    render(<><ReconnectingBanner connectionStatus="reconnecting" /><InterruptedRunCard onStartFreshRun={startFresh} /></>);
    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting");
    expect(screen.getByRole("button", { name: "Start a fresh run" })).toBeInTheDocument();
  });

  it("marks a reconnecting stream stale after 30 seconds", () => {
    vi.useFakeTimers();
    render(<ReconnectingBanner connectionStatus="reconnecting" />);
    act(() => vi.advanceTimersByTime(30_000));
    expect(screen.getByRole("status")).toHaveTextContent("Updates may be stale");
  });
});

function ErrorToastHarness({ retry }: { retry: () => void }) {
  const reportServerError = useServerErrorToast();
  return <button type="button" onClick={() => reportServerError(retry)}>Trigger error</button>;
}

describe("server error toast", () => {
  it("keeps a retry action focusable by keyboard", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(<ToastProvider><ErrorToastHarness retry={retry} /></ToastProvider>);
    await user.click(screen.getByRole("button", { name: "Trigger error" }));
    await user.tab();
    await user.tab();
    expect(screen.getByRole("button", { name: "Retry" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(retry).toHaveBeenCalledOnce();
  });
});
