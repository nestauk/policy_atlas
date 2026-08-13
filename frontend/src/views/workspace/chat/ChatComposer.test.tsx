import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatComposer } from "./ChatComposer";

const state = vi.hoisted(() => ({ draft: "Question" }));
vi.mock("../../../store", () => ({ useComposerDraft: () => [state.draft, (value: string) => { state.draft = value; }] }));

describe("ChatComposer", () => {
  it("uses the shared composer and swaps it for Stop while streaming", async () => {
    const onSend = vi.fn();
    const { rerender } = render(<ChatComposer conversationId="c1" isStreaming={false} onSend={onSend} onStop={vi.fn()} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Question");
    rerender(<ChatComposer conversationId="c1" isStreaming onSend={onSend} onStop={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
  });

  it("shows a fence reason and disables sending without submitting", async () => {
    const onSend = vi.fn();
    render(<ChatComposer conversationId="c1" isStreaming={false} disabledReason="A turn is already pending." onSend={onSend} onStop={vi.fn()} />);
    expect(screen.getByText("A turn is already pending.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).not.toHaveBeenCalled();
  });
});
