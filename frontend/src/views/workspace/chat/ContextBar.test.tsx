import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ContextBar } from "./ContextBar";

const state = vi.hoisted(() => ({ update: vi.fn() }));
vi.mock("./conversationState", () => ({ useConversationMutations: () => ({ update: state.update }) }));

describe("ContextBar", () => {
  it("shows the zero state or a removable report chip", async () => {
    const { rerender } = render(<MemoryRouter><ContextBar taskId="p1" conversationId="c1" entryArtefactId={null} /></MemoryRouter>);
    // No entry context renders NOTHING — the "Whole task" zero-state
    // label was cut at the owner live check (2026-08-11).
    expect(screen.queryByText("Whole task")).not.toBeInTheDocument();
    rerender(<MemoryRouter><ContextBar taskId="p1" conversationId="c1" entryArtefactId="a1" /></MemoryRouter>);
    expect(screen.getByText("Report")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Clear report context" }));
    expect(state.update).toHaveBeenCalledWith("c1", { entry_artefact_id: null });
  });
});
