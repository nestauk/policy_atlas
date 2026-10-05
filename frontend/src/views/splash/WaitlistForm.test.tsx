import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
